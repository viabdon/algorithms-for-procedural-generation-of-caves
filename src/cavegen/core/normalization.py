"""Normalize streamed XYZ point batches into voxel-grid indices.

The normalizer maps continuous ``float32`` surface coordinates in XYZ order to
integer ZYX indices for volumes shaped ``(depth, height, width)``. It uses one
shared scale and centers the result, preserving the point cloud's proportions
instead of stretching each coordinate axis independently.
"""

from __future__ import annotations

import numpy as np


def normalize_xyz_to_zyx_indices(
    xyz_batch: np.ndarray,
    min_xyz: np.ndarray,
    max_xyz: np.ndarray,
    volume_shape: tuple[int, int, int],
) -> np.ndarray:
    """Map an XYZ batch to valid ZYX indices in a voxel grid.

    Parameters
    ----------
    xyz_batch
        Finite ``float32`` coordinates with shape ``(N, 3)`` in XYZ order.
    min_xyz, max_xyz
        Finite ``float32`` global bounds with shape ``(3,)`` in XYZ order.
    volume_shape
        Target volume shape in ``(depth, height, width)`` order. Every
        dimension must be at least two voxels.

    Returns
    -------
    numpy.ndarray
        Integer indices with shape ``(N, 3)`` in ZYX order, suitable for
        ``volume[indices[:, 0], indices[:, 1], indices[:, 2]]``.

    Notes
    -----
    A single scale preserves spatial proportions. Remaining space is divided
    equally around the cloud. A degenerate source axis is placed at the center
    of its target axis.
    """

    _validate_xyz_batch(xyz_batch)
    _validate_bounds(min_xyz, max_xyz)
    _validate_volume_shape(volume_shape)
    if np.any(xyz_batch < min_xyz) or np.any(xyz_batch > max_xyz):
        raise ValueError("xyz_batch coordinates must be within the global XYZ bounds.")

    if xyz_batch.shape[0] == 0:
        return np.empty((0, 3), dtype=np.intp)

    # Convert the volume's ZYX shape to XYZ spans, whose last valid indices
    # are respectively width - 1, height - 1, and depth - 1.
    depth, height, width = volume_shape
    target_span_xyz = np.array((width - 1, height - 1, depth - 1), dtype=np.float32)
    source_span_xyz = max_xyz - min_xyz
    non_degenerate = source_span_xyz > 0

    # Choose one scale from the axes that have an extent, avoiding distortion.
    if np.any(non_degenerate):
        scale = np.min(target_span_xyz[non_degenerate] / source_span_xyz[non_degenerate])
    else:
        scale = np.float32(0.0)

    # Translate the global minimum to zero, scale it, then center the cloud.
    padding_xyz = (target_span_xyz - source_span_xyz * scale) / np.float32(2.0)
    grid_xyz = (xyz_batch - min_xyz) * scale + padding_xyz

    # A flat source axis has no geometric extent, so place every point from
    # that axis at the center of its corresponding grid dimension.
    for axis, has_extent in enumerate(non_degenerate):
        if not has_extent:
            grid_center = target_span_xyz[axis] / np.float32(2.0)
            grid_xyz[:, axis] = grid_center

    # Round to voxel indices and clip boundary-rounding imprecision safely.
    indices_xyz = np.rint(grid_xyz).astype(np.intp)
    np.clip(
        a=indices_xyz,
        a_min=0,
        a_max=target_span_xyz.astype(np.intp),
        out=indices_xyz,
    )

    # NumPy volumes use ZYX indexing, while the source coordinates are XYZ.
    return indices_xyz[:, (2, 1, 0)]


def _validate_xyz_batch(xyz_batch: np.ndarray) -> None:
    """Validate one finite XYZ ``float32`` batch."""

    if not isinstance(xyz_batch, np.ndarray):
        raise TypeError("xyz_batch must be a numpy.ndarray.")
    if xyz_batch.ndim != 2 or xyz_batch.shape[1] != 3:
        raise ValueError(f"xyz_batch must have shape (N, 3), got {xyz_batch.shape}.")
    if xyz_batch.dtype != np.float32:
        raise TypeError(f"xyz_batch must use float32, got {xyz_batch.dtype}.")
    if not np.isfinite(xyz_batch).all():
        raise ValueError("xyz_batch must contain only finite coordinates.")


def _validate_bounds(min_xyz: np.ndarray, max_xyz: np.ndarray) -> None:
    """Validate finite ordered XYZ bounds."""

    for name, bound in (("min_xyz", min_xyz), ("max_xyz", max_xyz)):
        if not isinstance(bound, np.ndarray):
            raise TypeError(f"{name} must be a numpy.ndarray.")
        if bound.shape != (3,):
            raise ValueError(f"{name} must have shape (3,), got {bound.shape}.")
        if bound.dtype != np.float32:
            raise TypeError(f"{name} must use float32, got {bound.dtype}.")
        if not np.isfinite(bound).all():
            raise ValueError(f"{name} must contain only finite coordinates.")

    if np.any(min_xyz > max_xyz):
        raise ValueError("min_xyz must be less than or equal to max_xyz on every axis.")


def _validate_volume_shape(volume_shape: tuple[int, int, int]) -> None:
    """Validate a non-degenerate volume shape in ZYX order."""

    if len(volume_shape) != 3:
        raise ValueError(f"volume_shape must have three dimensions, got {volume_shape}.")
    if any(isinstance(size, bool) or not isinstance(size, (int, np.integer)) for size in volume_shape):
        raise TypeError("volume_shape dimensions must be integers.")
    if any(size < 2 for size in volume_shape):
        raise ValueError("volume_shape dimensions must be at least 2.")
