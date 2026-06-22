from __future__ import annotations

import numpy as np


def voxel_iou(a: np.ndarray, b: np.ndarray, empty_value: float = 1.0) -> float:
    """Compute volumetric IoU/Jaccard index between two boolean voxel grids."""
    a_bool = np.asarray(a, dtype=bool)
    b_bool = np.asarray(b, dtype=bool)
    if a_bool.shape != b_bool.shape:
        raise ValueError(f"IoU requires equal shapes, got {a_bool.shape} and {b_bool.shape}.")

    intersection = np.logical_and(a_bool, b_bool).sum(dtype=np.int64)
    union = np.logical_or(a_bool, b_bool).sum(dtype=np.int64)
    if union == 0:
        return float(empty_value)
    return float(intersection / union)
