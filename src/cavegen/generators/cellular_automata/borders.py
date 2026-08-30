"""Border handling for the 3D cellular automaton.

Three independent strategies decide what happens at the faces of the volume,
where a voxel does not have the full Moore neighborhood of 26 neighbors:

``OUTSIDE_OPEN``
    Everything outside the grid counts as open space (1). Borders tend to
    erode into cave.
``OUTSIDE_SOLID``
    Everything outside the grid counts as solid (0). Borders tend to close.
``ADAPTIVE``
    Nothing outside the grid is counted. Instead, every voxel gets its own
    threshold, computed as a fraction of the neighbors it actually has
    (26 in the interior, 17 on a face, 11 on an edge, 7 on a corner).
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

import numpy as np
from scipy import ndimage

KERNEL_26 = np.ones((3, 3, 3), dtype=np.int16)
KERNEL_26[1, 1, 1] = 0

MAX_NEIGHBORS = 26


class BorderMode(str, Enum):
    OUTSIDE_OPEN = "outside_open"
    OUTSIDE_SOLID = "outside_solid"
    ADAPTIVE = "adaptive"


@lru_cache(maxsize=8)
def valid_neighbor_count(shape: tuple[int, int, int]) -> np.ndarray:
    """How many of the 26 neighbors of each voxel lie inside the grid."""
    counts = ndimage.convolve(
        np.ones(shape, dtype=np.int16), KERNEL_26, mode="constant", cval=0
    )
    counts.flags.writeable = False
    return counts


def count_open_neighbors(volume: np.ndarray, mode: BorderMode) -> np.ndarray:
    """Open neighbors of every voxel, under the given border assumption."""
    cval = 1 if BorderMode(mode) is BorderMode.OUTSIDE_OPEN else 0
    return ndimage.convolve(
        volume.astype(np.int16, copy=False), KERNEL_26, mode="constant", cval=cval
    )


def neighbor_threshold(
    shape: tuple[int, int, int],
    mode: BorderMode,
    threshold_open_neighbors: int,
    threshold_open_ratio: float,
) -> np.ndarray | np.int16:
    """Minimum number of open neighbors for a voxel to be open next step.

    Scalar for the fixed-outside modes, per-voxel array for ``ADAPTIVE``.
    """
    if BorderMode(mode) is BorderMode.ADAPTIVE:
        return np.ceil(threshold_open_ratio * valid_neighbor_count(shape)).astype(np.int16)
    return np.int16(threshold_open_neighbors)
