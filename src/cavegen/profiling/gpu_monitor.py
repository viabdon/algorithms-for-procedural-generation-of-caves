from __future__ import annotations


def gpu_available() -> bool:
    try:
        import pynvml  # noqa: F401
    except ImportError:
        return False
    return True


def read_first_gpu_snapshot() -> dict[str, int | float | str] | None:
    """Read one NVML GPU snapshot when available. Returns None on CPU-only environments."""
    try:
        import pynvml
    except ImportError:
        return None

    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="replace")
        return {
            "name": name,
            "gpu_utilization_percent": int(util.gpu),
            "gpu_memory_used_bytes": int(mem.used),
            "gpu_memory_total_bytes": int(mem.total),
        }
    except Exception:
        return None
