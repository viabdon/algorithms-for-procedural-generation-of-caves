from __future__ import annotations

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.core.volume import Volume3D

_DIRECTIONS_6 = np.array(
    [
        [1, 0, 0],
        [-1, 0, 0],
        [0, 1, 0],
        [0, -1, 0],
        [0, 0, 1],
        [0, 0, -1],
    ],
    dtype=np.int32,
)


def _carve_brush(volume: np.ndarray, pos: np.ndarray, radius: int) -> None:
    if radius <= 0:
        volume[tuple(pos)] = True
        return

    z, y, x = (int(v) for v in pos)
    z0, z1 = max(0, z - radius), min(volume.shape[0], z + radius + 1)
    y0, y1 = max(0, y - radius), min(volume.shape[1], y + radius + 1)
    x0, x1 = max(0, x - radius), min(volume.shape[2], x + radius + 1)
    volume[z0:z1, y0:y1, x0:x1] = True


def generate_random_walk(
    shape: tuple[int, int, int] = (32, 32, 32),
    seed: int | None = None,
    steps: int = 6000,
    brush_radius: int = 1,
    start: tuple[int, int, int] | None = None,
) -> Volume3D:
    """Generate a cave by carving a 6-neighborhood random walk.

    The resulting boolean volume follows the project convention: True means open cave
    space and False means solid space.
    """
    if any(dim <= 2 for dim in shape):
        raise ValueError("All volume dimensions must be greater than 2.")
    if steps <= 0:
        raise ValueError("steps must be positive.")

    rng = numpy_rng(seed)
    volume = np.zeros(shape, dtype=bool)
    pos = np.array(start if start is not None else tuple(dim // 2 for dim in shape), dtype=np.int32)
    lower = np.array([1, 1, 1], dtype=np.int32)
    upper = np.array(shape, dtype=np.int32) - 2

    _carve_brush(volume, pos, brush_radius)
    for _ in range(steps):
        pos = pos + _DIRECTIONS_6[int(rng.integers(0, len(_DIRECTIONS_6)))]
        pos = np.clip(pos, lower, upper)
        _carve_brush(volume, pos, brush_radius)

    return Volume3D(
        volume,
        metadata={
            "algorithm": "random_walk",
            "seed": seed,
            "steps": steps,
            "brush_radius": brush_radius,
        },
    )


class RandomWalkGenerator:
    def __init__(self, steps: int = 6000, brush_radius: int = 1) -> None:
        self.steps = steps
        self.brush_radius = brush_radius

    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        return generate_random_walk(shape=shape, seed=seed, steps=self.steps, brush_radius=self.brush_radius)
