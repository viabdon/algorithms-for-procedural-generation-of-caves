from __future__ import annotations

import numpy as np
from scipy import ndimage

from cavegen.metrics.validation import validate_connectivity, validate_volume

_STRUCTURE_6 = ndimage.generate_binary_structure(rank=3, connectivity=1)
_STRUCTURE_26 = ndimage.generate_binary_structure(rank=3, connectivity=3)


def connected_components(volume: np.ndarray, connectivity: int = 6) -> tuple[np.ndarray, int]:
    """Label open components using face or face/edge/corner adjacency.

    Parameters
    ----------
    volume
        Nonempty bool[D,H,W] array; True means open space.
    connectivity
        6 joins faces only; 26 also joins edges and corners. No periodic wrap.

    Returns
    -------
    labeled : numpy.ndarray
        Integer ZYX labels; zero denotes solid voxels.
    count : int
        Number of open components, including isolated single voxels.
    """
    volume = validate_volume(volume)
    connectivity = validate_connectivity(connectivity)
    structure = _STRUCTURE_6 if connectivity == 6 else _STRUCTURE_26
    labeled, count = ndimage.label(volume, structure=structure)
    return labeled, int(count)


def largest_component(volume: np.ndarray, connectivity: int = 6) -> np.ndarray:
    """Return the largest open component as a boolean mask.

    Parameters
    ----------
    volume
        Nonempty boolean ZYX volume.
    connectivity
        Integer 6 or 26, with the same meaning as in connected_components.

    Returns
    -------
    numpy.ndarray
        An all-False mask for all-solid inputs. Ties select the first label
        in array traversal order, making repeated evaluation deterministic.
    """
    labeled, count = connected_components(volume, connectivity=connectivity)
    if count == 0:
        return np.zeros_like(volume, dtype=bool)
    component_sizes = np.bincount(labeled.ravel())
    component_sizes[0] = 0
    largest_label = int(component_sizes.argmax())
    return labeled == largest_label


def largest_component_ratio(volume: np.ndarray, connectivity: int = 6) -> float:
    """Return largest-component size divided by total open voxels.

    Parameters
    ----------
    volume
        Nonempty boolean ZYX volume.
    connectivity
        Integer 6 or 26.

    Returns
    -------
    float
        Fraction in [0, 1]; zero by convention when no open voxels exist.
    """
    volume_bool = validate_volume(volume)
    connectivity = validate_connectivity(connectivity)
    open_voxels = int(volume_bool.sum())
    if open_voxels == 0:
        return 0.0
    return float(largest_component(volume_bool, connectivity=connectivity).sum() / open_voxels)
