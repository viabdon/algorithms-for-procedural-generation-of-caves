from __future__ import annotations

from cavegen.core.volume import Volume3D


class GAN3DGenerator:
    """Placeholder for the GAN inference wrapper.

    Planned path:
        1. train a small 3D DCGAN/WGAN in Colab;
        2. save checkpoints under models/checkpoints/;
        3. load checkpoint here;
        4. return Volume3D with the same convention used by classical algorithms.
    """

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self.checkpoint_path = checkpoint_path

    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        raise NotImplementedError("GAN3DGenerator will be implemented after the classical baseline pipeline is stable.")
