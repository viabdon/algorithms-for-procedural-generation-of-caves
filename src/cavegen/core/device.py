from __future__ import annotations


def detect_torch_device() -> str:
    """Return 'cuda', 'mps' or 'cpu'. ROCm builds of PyTorch also report CUDA APIs.

    PyTorch exposes AMD/ROCm devices through the CUDA-compatible API surface. For the
    project code this is useful: generation/training code can remain backend-agnostic.
    """
    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
