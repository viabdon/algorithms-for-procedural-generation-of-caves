from __future__ import annotations

from cavegen.core.volume import Volume3D


class PCGRL3DGenerator:
    """Placeholder for the PCGRL inference wrapper.

    The training environment should start small and expose rewards for connectivity,
    target open ratio and penalties for isolated components.
    """

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self.checkpoint_path = checkpoint_path

    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        raise NotImplementedError("PCGRL3DGenerator will be implemented after the classical baseline pipeline is stable.")
