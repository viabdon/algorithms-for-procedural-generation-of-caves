"""Shared validation for boolean cave volumes and ZYX measurement settings."""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral, Real
from typing import Literal

import numpy as np

Connectivity = Literal[6, 26]
SpacingZYX = tuple[float, float, float]


def validate_volume(volume: np.ndarray) -> np.ndarray:
    """Return a nonempty boolean 3D volume without copying or coercing it.

    Parameters
    ----------
    volume
        ZYX array where True denotes open cave space. Every axis must be
        nonempty; small and noncubic grids are allowed for diagnostics/tests.

    Returns
    -------
    numpy.ndarray
        The original array, including read-only arrays and views.

    Raises
    ------
    TypeError
        If the input is not an ndarray with boolean dtype.
    ValueError
        If the array is not 3D or any dimension is zero.
    """
    if not isinstance(volume, np.ndarray):
        raise TypeError("volume must be a numpy.ndarray with bool dtype.")
    if volume.ndim != 3 or any(size == 0 for size in volume.shape):
        raise ValueError(f"volume must have a nonempty 3D ZYX shape, got {volume.shape}.")
    if volume.dtype != np.bool_:
        raise TypeError(f"volume must use bool dtype, got {volume.dtype}.")
    return volume


def validate_connectivity(connectivity: int) -> Connectivity:
    """Validate an integer 6 (faces) or 26 (faces, edges, corners).

    Parameters
    ----------
    connectivity
        Neighborhood size; bool, floats and strings are rejected.

    Returns
    -------
    int
        The validated neighborhood size as a Python integer.
    """
    if isinstance(connectivity, (bool, np.bool_)) or not isinstance(connectivity, Integral):
        raise TypeError("connectivity must be an integer: 6 or 26.")
    if connectivity not in (6, 26):
        raise ValueError("connectivity must be 6 or 26.")
    return 6 if connectivity == 6 else 26


def validate_spacing(spacing_zyx: Sequence[float]) -> SpacingZYX:
    """Validate three finite positive spacings in depth, height, width order.

    Parameters
    ----------
    spacing_zyx
        Real values defining the same distance unit along the three axes.
        Unit spacing expresses distances in voxels; other values carry the
        caller's spacing unit, which must be documented by the experiment.

    Returns
    -------
    tuple of float
        Validated ZYX spacings. Values are not inferred from volume metadata.
    """
    if isinstance(spacing_zyx, (str, bytes)) or not isinstance(
        spacing_zyx, (Sequence, np.ndarray)
    ):
        raise TypeError("spacing_zyx must contain three real numbers in ZYX order.")
    if np.ndim(spacing_zyx) != 1 or len(spacing_zyx) != 3:
        raise ValueError("spacing_zyx must have shape (3,) in ZYX order.")
    for value in spacing_zyx:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise TypeError("spacing_zyx must contain real numbers, excluding bool.")
        if not np.isfinite(value) or value <= 0:
            raise ValueError("spacing_zyx must contain only finite positive values.")
    return tuple(float(value) for value in spacing_zyx)
