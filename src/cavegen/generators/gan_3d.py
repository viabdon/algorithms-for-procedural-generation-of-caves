from __future__ import annotations

from pathlib import Path
import secrets
from typing import TYPE_CHECKING

from cavegen.core.volume import Volume3D

if TYPE_CHECKING:
    import numpy as np


class GAN3DGenerator:
    """Seeded checkpoint inference; load torch only when a GAN is requested."""

    def __init__(self, checkpoint_path: str | Path, *, device: str = "cpu",
                 threshold: float | None = None) -> None:
        import torch
        from cavegen.training.gan_models import Generator3D, ModelConfig
        from cavegen.training.reference_data import sha256_file
        from cavegen.training.gan_training import CHECKPOINT_SCHEMA

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
            raise ValueError("Unsupported GAN checkpoint schema")
        self.config = ModelConfig(**checkpoint["model_config"])
        self.device = torch.device(device)
        self.model = Generator3D(self.config).to(self.device).eval()
        self.model.load_state_dict(checkpoint["generator"])
        self.threshold = checkpoint["config"]["threshold"] if threshold is None else threshold
        if not 0 < self.threshold < 1:
            raise ValueError("threshold must lie inside (0,1)")
        self.checkpoint_sha256 = sha256_file(checkpoint_path)
        self.provenance = checkpoint["provenance"]
        self.training_step = checkpoint["step"]

    def generate_field(self, seed: int) -> "np.ndarray":
        import torch
        from cavegen.training.gan_models import latent_for_seed

        with torch.inference_mode():
            z = latent_for_seed(seed, self.config.latent_dim).to(self.device)
            return self.model(z)[0, 0].cpu().numpy()

    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        from cavegen.training.gan_data import decode_volume

        if shape != (self.config.resolution,) * 3:
            raise ValueError("Output shape must match checkpoint resolution; no hidden resizing")
        effective_seed = secrets.randbelow(2**63) if seed is None else seed
        field = self.generate_field(effective_seed)
        return Volume3D(decode_volume(field, self.config, self.threshold), metadata={
            "algorithm": "gan_" + self.config.representation, "semantic": "true_means_cave_air",
            "axis_order": "ZYX", "seed": effective_seed, "threshold": self.threshold,
            "model_config": self.config.to_dict(), "checkpoint_sha256": self.checkpoint_sha256,
            "training_step": self.training_step, "provenance": self.provenance,
            "postprocessing": "none", "backend": str(self.device)})
