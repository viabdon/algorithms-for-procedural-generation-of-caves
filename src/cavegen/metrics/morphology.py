from __future__ import annotations

import numpy as np
from scipy import ndimage


def open_ratio(volume: np.ndarray) -> float:
    volume_bool = np.asarray(volume, dtype=bool)
    return float(volume_bool.sum() / volume_bool.size)


def distance_transform_stats(volume: np.ndarray) -> dict[str, float]:
    """Approximate tunnel-width descriptors from distance to solid voxels."""
    volume_bool = np.asarray(volume, dtype=bool)
    if not volume_bool.any():
        return {"dt_mean": 0.0, "dt_median": 0.0, "dt_max": 0.0}
    distances = ndimage.distance_transform_edt(volume_bool)
    open_distances = distances[volume_bool]
    return {
        "dt_mean": float(open_distances.mean()),
        "dt_median": float(np.median(open_distances)),
        "dt_max": float(open_distances.max()),
    }
