"""Explicit GAN optimization, validation and resumable Colab checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from cavegen.training.gan_data import ReferenceDataset, decode_volume
from cavegen.training.gan_evaluation import compare_distributions
from cavegen.training.gan_models import Discriminator3D, Generator3D, ModelConfig, latent_for_seed
from cavegen.training.reference_data import canonical_hash, sha256_file

CHECKPOINT_SCHEMA = "cavegan-checkpoint-v1"


@dataclass(frozen=True)
class TrainingConfig:
    model: ModelConfig = ModelConfig()
    seed: int = 17
    steps: int = 5000
    batch_size: int = 2
    learning_rate: float = 0.0001
    beta1: float = 0.0
    beta2: float = 0.99
    r1_gamma: float = 10.0
    r1_interval: int = 16
    instance_noise: float = 0.1
    noise_decay_steps: int = 2500
    yaw_augmentation: bool = True
    validation_interval: int = 250
    validation_seed_start: int = 1_000_000
    validation_count: int = 16
    threshold: float = 0.5
    max_minutes: float = 60.0
    allow_candidate_proxy: bool = False
    require_cuda: bool = True

    def __post_init__(self) -> None:
        latent_for_seed(self.seed, 1)
        latent_for_seed(self.validation_seed_start + self.validation_count - 1, 1)
        if min(self.steps, self.batch_size, self.r1_interval, self.noise_decay_steps,
               self.validation_interval, self.validation_count) < 1:
            raise ValueError("Step, batch and interval counts must be positive")
        if not all(math.isfinite(v) for v in (self.learning_rate, self.r1_gamma,
                   self.instance_noise, self.max_minutes, self.threshold)):
            raise ValueError("Training scalars must be finite")
        if self.learning_rate <= 0 or self.max_minutes <= 0:
            raise ValueError("Learning rate and time budget must be positive")
        if self.r1_gamma < 0 or self.instance_noise < 0 or not 0 < self.threshold < 1:
            raise ValueError("Invalid regularization or threshold")
        if not 0 <= self.beta1 < 1 or not 0 <= self.beta2 < 1:
            raise ValueError("Adam betas must be in [0,1)")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "TrainingConfig":
        payload = dict(payload)
        payload["model"] = ModelConfig(**payload.get("model", {}))
        return cls(**payload)


def augment_yaw(x: torch.Tensor) -> torch.Tensor:
    """Differentiable yaw rotations; preserve vertical Z and binary labels."""
    turns = torch.randint(4, (len(x),), device="cpu").tolist()
    return torch.stack([torch.rot90(sample, turn, dims=(-2, -1))
                        for sample, turn in zip(x, turns)])


def finite_optimizer_step(loss: torch.Tensor, model: nn.Module,
                          optimizer: torch.optim.Optimizer) -> None:
    if not torch.isfinite(loss):
        raise FloatingPointError("Nonfinite adversarial loss; stopping")
    loss.backward()
    if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
        optimizer.zero_grad(set_to_none=True)
        raise FloatingPointError("Nonfinite gradient; stopping")
    optimizer.step()


class GANTrainer:
    """1 D + 1 G step, non-saturating logistic loss with lazy real-data R1."""

    def __init__(self, config: TrainingConfig, device: str = "cpu") -> None:
        self.config, self.device = config, torch.device(device)
        torch.manual_seed(config.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config.seed)
        self.generator = Generator3D(config.model).to(self.device)
        self.discriminator = Discriminator3D(config.model).to(self.device)
        kwargs = {"lr": config.learning_rate, "betas": (config.beta1, config.beta2)}
        self.g_optimizer = torch.optim.Adam(self.generator.parameters(), **kwargs)
        self.d_optimizer = torch.optim.Adam(self.discriminator.parameters(), **kwargs)
        self.step = 0
        self.elapsed_seconds = 0.0
        self.best_score = math.inf

    def _input(self, field: torch.Tensor, sigma: float) -> torch.Tensor:
        if self.config.yaw_augmentation:
            field = augment_yaw(field)
        # Same augmentation/noise distribution for real and fake; no clamping.
        return field + sigma * torch.randn_like(field) if sigma > 0 else field

    def optimization_step(self, real: torch.Tensor) -> dict:
        """Public single-step contract; local tests use synthetic fixtures only."""
        cfg = self.config
        real = real.to(self.device)
        if not torch.isfinite(real).all():
            raise ValueError("Nonfinite reference batch")
        low, high = (0, 1) if cfg.model.representation == "occupancy" else (-1, 1)
        if real.min() < low or real.max() > high:
            raise ValueError("Reference batch outside representation domain")
        sigma = cfg.instance_noise * max(0, 1 - self.step / cfg.noise_decay_steps)
        apply_r1 = self.step % cfg.r1_interval == 0 and cfg.r1_gamma > 0
        self.generator.train()
        self.discriminator.train().requires_grad_(True)
        self.d_optimizer.zero_grad(set_to_none=True)
        real = real.detach().requires_grad_(apply_r1)
        z = torch.randn(len(real), cfg.model.latent_dim, device=self.device)
        with torch.no_grad():
            fake = self.generator(z)
        real_logits = self.discriminator(self._input(real, sigma))
        fake_logits = self.discriminator(self._input(fake, sigma))
        d_loss = F.softplus(-real_logits).mean() + F.softplus(fake_logits).mean()
        r1 = torch.zeros((), device=self.device)
        if apply_r1:
            gradients = torch.autograd.grad(real_logits.sum(), real, create_graph=True)[0]
            r1 = gradients.flatten(1).square().sum(1).mean()
            d_loss = d_loss + 0.5 * cfg.r1_gamma * cfg.r1_interval * r1
        finite_optimizer_step(d_loss, self.discriminator, self.d_optimizer)
        self.discriminator.requires_grad_(False)
        self.g_optimizer.zero_grad(set_to_none=True)
        try:
            z = torch.randn(len(real), cfg.model.latent_dim, device=self.device)
            fake = self.generator(z)
            g_loss = F.softplus(-self.discriminator(self._input(fake, sigma))).mean()
            finite_optimizer_step(g_loss, self.generator, self.g_optimizer)
        finally:
            self.discriminator.requires_grad_(True)
        self.step += 1
        return {"step": self.step, "d_loss": float(d_loss.detach()),
                "g_loss": float(g_loss.detach()), "r1": float(r1.detach()), "noise_sigma": sigma,
                "real_logit_mean": float(real_logits.detach().mean()),
                "fake_logit_mean": float(fake_logits.detach().mean())}

    @torch.no_grad()
    def fields(self, seeds: list[int]) -> list[np.ndarray]:
        self.generator.eval()
        return [self.generator(latent_for_seed(seed, self.config.model.latent_dim).to(self.device))
                [0, 0].cpu().numpy() for seed in seeds]

    def checkpoint(self, provenance: dict) -> dict:
        return {"schema": CHECKPOINT_SCHEMA, "config": self.config.to_dict(),
                "model_config": self.config.model.to_dict(), "step": self.step,
                "elapsed_seconds": self.elapsed_seconds, "best_score": self.best_score,
                "generator": self.generator.state_dict(),
                "discriminator": self.discriminator.state_dict(),
                "g_optimizer": self.g_optimizer.state_dict(),
                "d_optimizer": self.d_optimizer.state_dict(),
                "rng_cpu": torch.get_rng_state(),
                "rng_cuda": torch.cuda.get_rng_state_all() if self.device.type == "cuda" else [],
                "provenance": provenance}

    def restore(self, checkpoint: dict, provenance: dict) -> None:
        if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
            raise ValueError("Unknown checkpoint schema")
        if checkpoint["config"] != self.config.to_dict():
            raise ValueError("Resume requires identical effective configuration")
        if checkpoint["provenance"]["experiment_id"] != provenance["experiment_id"]:
            raise ValueError("Resume data/fold/configuration identity mismatch")
        self.generator.load_state_dict(checkpoint["generator"])
        self.discriminator.load_state_dict(checkpoint["discriminator"])
        self.g_optimizer.load_state_dict(checkpoint["g_optimizer"])
        self.d_optimizer.load_state_dict(checkpoint["d_optimizer"])
        self.step, self.elapsed_seconds = checkpoint["step"], checkpoint["elapsed_seconds"]
        self.best_score = checkpoint["best_score"]
        torch.set_rng_state(checkpoint["rng_cpu"].cpu())
        if self.device.type == "cuda" and checkpoint["rng_cuda"]:
            torch.cuda.set_rng_state_all([x.cpu() for x in checkpoint["rng_cuda"]])


def save_checkpoint(path: str | Path, checkpoint: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(checkpoint, temporary)
    temporary.replace(path)


def environment_record(device: torch.device) -> dict:
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    return {"python": platform.python_version(), "torch": str(torch.__version__),
            "numpy": np.__version__, "platform": platform.platform(), "device": str(device),
            "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
            "cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
            "git_commit": revision, "git_dirty": dirty}


def preflight(root: str | Path, splits: dict, fold: str, config: TrainingConfig) -> dict:
    """No model execution. Rejects the current almost-empty reference interiors."""
    datasets = {split: ReferenceDataset(root, splits, fold, split, config.model,
                                       allow_candidate_proxy=config.allow_candidate_proxy)
                for split in ("train", "validation", "test")}
    return {"counts": {k: len(v) for k, v in datasets.items()}, "fold": fold,
            "splits_id": splits["splits_id"], "config": config.to_dict()}


def train(root: str | Path, splits: dict, fold: str, config: TrainingConfig,
          output: str | Path, *, resume: bool = False, device: str | None = None) -> Path:
    """Explicit opt-in; never called by imports or the notebook's default cells."""
    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    preflight(root, splits, fold, config)
    if config.require_cuda and device.type != "cuda":
        raise RuntimeError("CUDA required; select a GPU Colab runtime")
    datasets = {split: ReferenceDataset(root, splits, fold, split, config.model,
                                       allow_candidate_proxy=config.allow_candidate_proxy)
                for split in ("train", "validation")}
    output = Path(output)
    if output.exists() and any(output.iterdir()) and not resume:
        raise FileExistsError("Use a new run directory or resume=True")
    output.mkdir(parents=True, exist_ok=True)
    provenance = {"splits_id": splits["splits_id"], "audit_id": splits["audit_id"],
                  "fold": fold, "environment": environment_record(device),
                  "reference_mode": "candidate_proxy" if config.allow_candidate_proxy else "validated_air"}
    source_root = Path(__file__).resolve().parents[1]
    provenance["code_sha256"] = canonical_hash({p.relative_to(source_root).as_posix(): sha256_file(p)
        for p in sorted(source_root.rglob("*.py"))})
    provenance["experiment_id"] = canonical_hash({"splits_id": splits["splits_id"],
        "audit_id": splits["audit_id"], "fold": fold, "config": config.to_dict(),
        "code_sha256": provenance["code_sha256"]})
    trainer = GANTrainer(config, str(device))
    if resume:
        trainer.restore(torch.load(output / "latest.pt", map_location=device, weights_only=True),
                        provenance)
        with (output / "resume_sessions.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(),
                                     "step": trainer.step, **provenance}) + "\n")
    else:
        (output / "run.json").write_text(json.dumps({"provenance": provenance,
            "config": config.to_dict(), "started_utc": datetime.now(timezone.utc).isoformat(),
            "splits": splits}, indent=2) + "\n", encoding="utf-8")
        save_checkpoint(output / "latest.pt", trainer.checkpoint(provenance))
    clock_start, previous_elapsed = time.monotonic(), trainer.elapsed_seconds
    status, failure, stopped_error = "step_budget", None, None
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    try:
        while trainer.step < config.steps:
            trainer.elapsed_seconds = previous_elapsed + time.monotonic() - clock_start
            if trainer.elapsed_seconds >= config.max_minutes * 60:
                status = "time_budget"
                break
            # Sampling with replacement; augmented samples remain the same source caves.
            indices = torch.randint(len(datasets["train"]), (config.batch_size,)).tolist()
            real = torch.stack([datasets["train"][i] for i in indices])
            record = trainer.optimization_step(real)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            trainer.elapsed_seconds = previous_elapsed + time.monotonic() - clock_start
            record.update(elapsed_seconds=trainer.elapsed_seconds,
                          peak_cuda_bytes=torch.cuda.max_memory_allocated(device)
                          if device.type == "cuda" else None)
            with (output / "losses.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
            if trainer.step % config.validation_interval == 0 or trainer.step == config.steps:
                seeds = list(range(config.validation_seed_start,
                                   config.validation_seed_start + config.validation_count))
                arrays = [decode_volume(f, config.model, config.threshold) for f in trainer.fields(seeds)]
                comparison = compare_distributions(arrays, datasets["validation"].arrays,
                                                   datasets["train"].arrays)
                improved = comparison["selection_score"] < trainer.best_score
                trainer.best_score = min(trainer.best_score, comparison["selection_score"])
                trainer.elapsed_seconds = previous_elapsed + time.monotonic() - clock_start
                with (output / "validation.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"step": trainer.step, "seeds": seeds,
                                             **comparison}, allow_nan=False) + "\n")
                if improved:
                    save_checkpoint(output / "best.pt", trainer.checkpoint(provenance))
                save_checkpoint(output / "latest.pt", trainer.checkpoint(provenance))
                print(f"step={trainer.step} validation={comparison['selection_score']:.5g}", flush=True)
    except (Exception, KeyboardInterrupt) as error:
        status, failure = "stopped", f"{type(error).__name__}: {error}"
        stopped_error = error
    finally:
        trainer.elapsed_seconds = previous_elapsed + time.monotonic() - clock_start
        # A failed step can partially update D; only resume the last completed checkpoint.
        if status != "stopped":
            save_checkpoint(output / "latest.pt", trainer.checkpoint(provenance))
        (output / "status.json").write_text(json.dumps({"status": status, "failure": failure,
            "step": trainer.step, "elapsed_seconds": trainer.elapsed_seconds,
            "best_score": trainer.best_score if math.isfinite(trainer.best_score) else None,
            "resume_from_last_periodic_checkpoint_if_failed": status == "stopped"}, indent=2)
            + "\n", encoding="utf-8")
    if stopped_error is not None:
        raise stopped_error
    return output
