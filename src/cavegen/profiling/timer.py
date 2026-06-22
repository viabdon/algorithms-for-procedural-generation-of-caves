from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


@contextmanager
def elapsed_timer() -> Iterator[dict[str, float]]:
    result: dict[str, float] = {}
    start = perf_counter()
    try:
        yield result
    finally:
        result["elapsed_seconds"] = perf_counter() - start
