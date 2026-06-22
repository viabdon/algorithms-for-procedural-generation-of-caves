from __future__ import annotations

import numpy as np
from scipy import ndimage

_STRUCTURE_6 = ndimage.generate_binary_structure(rank=3, connectivity=1)
_STRUCTURE_26 = ndimage.generate_binary_structure(rank=3, connectivity=3)


def connected_components(volume: np.ndarray, connectivity: int = 6) -> tuple[np.ndarray, int]:
    structure = _STRUCTURE_6 if connectivity == 6 else _STRUCTURE_26
    labeled, count = ndimage.label(np.asarray(volume, dtype=bool), structure=structure)
    return labeled, int(count)


def largest_component(volume: np.ndarray, connectivity: int = 6) -> np.ndarray:
    labeled, count = connected_components(volume, connectivity=connectivity)
    if count == 0:
        return np.zeros_like(volume, dtype=bool)
    component_sizes = np.bincount(labeled.ravel())
    component_sizes[0] = 0
    largest_label = int(component_sizes.argmax())
    return labeled == largest_label


def largest_component_ratio(volume: np.ndarray, connectivity: int = 6) -> float:
    volume_bool = np.asarray(volume, dtype=bool)
    open_voxels = int(volume_bool.sum())
    if open_voxels == 0:
        return 0.0
    return float(largest_component(volume_bool, connectivity=connectivity).sum() / open_voxels)
