from __future__ import annotations

from typing import Protocol

from cavegen.core.volume import Volume3D


class CaveGenerator(Protocol):
    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        ...
