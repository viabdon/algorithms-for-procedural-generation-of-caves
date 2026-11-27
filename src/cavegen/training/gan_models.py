"""Small dense 3D GAN: resize-convolution generator and global discriminator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import torch
from torch import nn


@dataclass(frozen=True)
class ModelConfig:
    resolution: int = 64
    latent_dim: int = 128
    base_channels: int = 16
    representation: str = "occupancy"
    sdf_tau: float = 4.0

    def __post_init__(self) -> None:
        if self.resolution not in (16, 32, 64):
            raise ValueError("Supported resolutions: 16, 32, 64")
        if self.latent_dim < 1 or self.base_channels < 1:
            raise ValueError("latent_dim and base_channels must be positive")
        if self.representation not in ("occupancy", "sdf"):
            raise ValueError("representation must be occupancy or sdf")
        if not math.isfinite(self.sdf_tau) or self.sdf_tau <= 0:
            raise ValueError("sdf_tau must be finite and positive")

    def to_dict(self) -> dict:
        return asdict(self)


class Generator3D(nn.Module):
    """z -> 4^3 features -> repeated nearest resize + Conv3d -> one channel."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        levels = int(math.log2(config.resolution)) - 2
        channels = config.base_channels * 2 ** (levels - 1)
        self.initial_channels = channels
        self.project = nn.Linear(config.latent_dim, channels * 4**3)
        layers = []
        for _ in range(levels):
            next_channels = max(config.base_channels, channels // 2)
            layers += [nn.Upsample(scale_factor=2, mode="nearest"),
                       nn.Conv3d(channels, next_channels, 3, padding=1),
                       nn.GroupNorm(math.gcd(8, next_channels), next_channels), nn.ReLU()]
            channels = next_channels
        layers += [nn.Conv3d(channels, 1, 3, padding=1),
                   nn.Sigmoid() if config.representation == "occupancy" else nn.Tanh()]
        self.blocks = nn.Sequential(*layers)
        self.apply(initialize)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        if z.ndim != 2 or z.shape[1] != self.config.latent_dim:
            raise ValueError("z must have shape (N, latent_dim)")
        features = self.project(z).reshape(-1, self.initial_channels, 4, 4, 4)
        return self.blocks(features)


class Discriminator3D(nn.Module):
    """One real/fake logit per whole volume. No batch-dependent normalization."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.resolution = config.resolution
        levels = int(math.log2(config.resolution)) - 2
        layers = []
        channels = 1
        for level in range(levels):
            out = config.base_channels * 2**level
            layers += [nn.Conv3d(channels, out, 4, stride=2, padding=1),
                       nn.LeakyReLU(0.2)]
            channels = out
        layers += [nn.Conv3d(channels, 1, 4)]
        self.blocks = nn.Sequential(*layers)
        self.apply(initialize)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 5 or tuple(x.shape[1:]) != (1,) + (self.resolution,) * 3:
            raise ValueError("Expected (N,1,D,H,W) at configured resolution")
        return self.blocks(x).flatten(1).squeeze(1)


def initialize(module: nn.Module) -> None:
    if isinstance(module, (nn.Conv3d, nn.Linear)):
        nn.init.normal_(module.weight, 0.0, 0.02)
        if module.bias is not None:
            nn.init.zeros_(module.bias)


def latent_for_seed(seed: int, latent_dim: int) -> torch.Tensor:
    """CPU-local RNG: seed meaning is independent of batch size and CUDA RNG state."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63:
        raise ValueError("Inference seed must be an integer in [0, 2**63)")
    return torch.randn(1, latent_dim, generator=torch.Generator(device="cpu").manual_seed(seed))
