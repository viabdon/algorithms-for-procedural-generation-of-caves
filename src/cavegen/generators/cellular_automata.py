from __future__ import annotations

import numpy as np
from scipy import ndimage

from cavegen.core.seed import numpy_rng
from cavegen.core.volume import Volume3D

_KERNEL_26 = np.ones((3, 3, 3), dtype=np.int16)
_KERNEL_26[1, 1, 1] = 0


def generate_cellular_automata(
    shape: tuple[int, int, int] = (32, 32, 32),
    seed: int | None = None,
    initial_open_probability: float = 0.45,
    iterations: int = 5,
    threshold_open_neighbors: int = 13,
    keep_border_solid: bool = True,
) -> Volume3D:
    """Generate a 3D cave using a Moore-neighborhood cellular automaton.

    Rule: a voxel is open in the next iteration if at least
    `threshold_open_neighbors` of its 26 neighbors are open.
    """
    if not 0.0 <= initial_open_probability <= 1.0:
        raise ValueError("initial_open_probability must be between 0 and 1.")
    if iterations < 0:
        raise ValueError("iterations must be non-negative.")
    if not 0 <= threshold_open_neighbors <= 26:
        raise ValueError("threshold_open_neighbors must be between 0 and 26.")

    rng = numpy_rng(seed)
    volume = rng.random(shape) < initial_open_probability

    if keep_border_solid:
        _close_border(volume)

    for _ in range(iterations):
        neighbors = ndimage.convolve(volume.astype(np.int16), _KERNEL_26, mode="constant", cval=0)
        volume = neighbors >= threshold_open_neighbors
        if keep_border_solid:
            _close_border(volume)

    return Volume3D(
        volume,
        metadata={
            "algorithm": "cellular_automata",
            "seed": seed,
            "initial_open_probability": initial_open_probability,
            "iterations": iterations,
            "threshold_open_neighbors": threshold_open_neighbors,
        },
    )


def _close_border(volume: np.ndarray) -> None:
    volume[0, :, :] = False
    volume[-1, :, :] = False
    volume[:, 0, :] = False
    volume[:, -1, :] = False
    volume[:, :, 0] = False
    volume[:, :, -1] = False


class CellularAutomataGenerator:
    def __init__(
        self,
        initial_open_probability: float = 0.45,
        iterations: int = 5,
        threshold_open_neighbors: int = 13,
    ) -> None:
        self.initial_open_probability = initial_open_probability
        self.iterations = iterations
        self.threshold_open_neighbors = threshold_open_neighbors

    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        return generate_cellular_automata(
            shape=shape,
            seed=seed,
            initial_open_probability=self.initial_open_probability,
            iterations=self.iterations,
            threshold_open_neighbors=self.threshold_open_neighbors,
        )
