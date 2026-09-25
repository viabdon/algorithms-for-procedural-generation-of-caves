from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator


@contextmanager
def gpu_sampler() -> Iterator[Callable[[], tuple[int, int] | None] | None]:
    """Open NVML once and yield a reader of (utilization_percent, memory_used_bytes).

    Yields None when there is no monitorable GPU, so the caller does not have to
    branch on every read. O NVML e inicializado uma vez e desligado no fim:
    amostragem continua chama o leitor dezenas de vezes por execucao, e pagar um
    nvmlInit por leitura custaria caro nesse laco.
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
