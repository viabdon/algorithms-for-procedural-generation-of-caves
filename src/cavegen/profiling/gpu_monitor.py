from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator


@contextmanager
def gpu_sampler() -> Iterator[Callable[[], tuple[int, int] | None] | None]:
    """Open NVML once and yield a reader of (utilization_percent, memory_used_bytes).

    Yields None when there is no monitorable GPU, so the caller does not have to
    branch on every read. Amostragem continua chama o leitor dezenas de vezes por
    execucao: inicializar o NVML em cada leitura, como faz read_first_gpu_snapshot,
    custaria caro nesse laco.
    """
    try:
        import pynvml
    except ImportError:
        yield None
        return

    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    except Exception:
        yield None
        return

    def read() -> tuple[int, int] | None:
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return int(util.gpu), int(mem.used)
        except Exception:
            return None

    try:
        yield read
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


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
