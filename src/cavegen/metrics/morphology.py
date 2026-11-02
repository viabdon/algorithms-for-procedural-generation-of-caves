from __future__ import annotations

import numpy as np
from scipy import ndimage

from cavegen.metrics.validation import SpacingZYX, validate_spacing, validate_volume


def open_ratio(volume: np.ndarray) -> float:
    """Return open voxels divided by all voxels in a nonempty boolean ZYX grid.

    Parameters
    ----------
    volume
        bool[D,H,W] array; True means open cave space.

    Returns
    -------
    float
        Open fraction in [0, 1], including zero/one for degenerate volumes.
    """
    volume_bool = validate_volume(volume)
    return float(volume_bool.sum() / volume_bool.size)


def distance_transform_stats(
    volume: np.ndarray,
    *,
    spacing_zyx: SpacingZYX = (1.0, 1.0, 1.0),
) -> dict[str, float | None]:
    """Summarize Euclidean center-to-center distance from open to solid voxels.

    Parameters
    ----------
    volume
        Nonempty boolean ZYX grid. A one-voxel solid exterior surrounds mixed
        volumes; no wrapping and no half-voxel surface correction is applied.
    spacing_zyx
        Finite positive ZYX spacings. Unit spacing yields voxel distances;
        other spacings yield distances in the supplied spacing unit.

    Returns
    -------
    dict
        dt_mean, dt_median and dt_max over all open voxels, including all
        components. Every value is None for all-solid or all-open volumes:
        these are marked as degenerate by evaluate_structure. All-open
        volumes deliberately do not use the synthetic exterior to report
        an apparent tunnel size.

    Notes
    -----
    This unsigned descriptor is neither a signed distance field nor a
    validated tunnel width. SciPy computes temporary distances in float64;
    input coordinates and the boolean volume are never converted or mutated.
    """
    volume_bool = validate_volume(volume)
    spacing_zyx = validate_spacing(spacing_zyx)
    if not volume_bool.any() or volume_bool.all():
        return {"dt_mean": None, "dt_median": None, "dt_max": None}
    padded = np.pad(volume_bool, 1, mode="constant", constant_values=False)
    distances = ndimage.distance_transform_edt(padded, sampling=spacing_zyx)
    open_distances = distances[1:-1, 1:-1, 1:-1][volume_bool]
    return {
        "dt_mean": float(open_distances.mean()),
        "dt_median": float(np.median(open_distances)),
        "dt_max": float(open_distances.max()),
    }
