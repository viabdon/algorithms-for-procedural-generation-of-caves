from __future__ import annotations

import random

import numpy as np


def numpy_rng(seed: int | None = None) -> np.random.Generator:
    return np.random.default_rng(seed)


def seed_python(seed: int | None = None) -> None:
    if seed is not None:
        random.seed(seed)


def seed_torch(seed: int | None = None, deterministic: bool = False) -> None:
    """Seed torch if available, without making torch a hard dependency."""
    if seed is None:
        return
    try:
        import torch
    except ImportError:
        return

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
