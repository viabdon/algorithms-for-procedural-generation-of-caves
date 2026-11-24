"""Infer enclosed regions of a voxelized surface by exterior flood fill.

This is a topological classification, not evidence that the scan encloses cave
air. Unobserved gaps and open entrances let the exterior reach the cavity.
"""

import numpy as np

from cavegen.tools.flood_fill import inundar

EXTERIOR = 0
SURFACE = 1
INTERIOR = 2


def classify_surface_by_flood_fill(surface: np.ndarray) -> np.ndarray:
    """Return uint8 labels: 0 exterior, 1 observed surface, 2 enclosed void.

    Exterior propagation uses six face neighbors, with outside the array
    treated as exterior. Observed voxels stay surface even in thick walls;
    only unobserved, enclosed voxels are interior. No dilation, smoothing or
    entrance closure is applied, and the input is never modified.
    """
    if not isinstance(surface, np.ndarray):
        raise TypeError("surface must be a numpy.ndarray.")
    if surface.ndim != 3 or any(size == 0 for size in surface.shape):
        raise ValueError("surface must be a nonempty 3D grid.")
    if surface.dtype != np.bool_:
        raise TypeError("surface must have boolean dtype.")
    _, enclosed = inundar(surface)
    classification = np.zeros(surface.shape, dtype=np.uint8)
    classification[surface] = SURFACE
    classification[enclosed] = INTERIOR
    return classification
