"""Build boolean surface-occupancy grids from streamed ZYX indices.

The input indices describe observed surface points. Consequently, ``True`` in
the returned array means that a voxel intersects the sampled surface; it does
not mean that the voxel belongs to the cave void used by procedural generators.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def voxelize_surface_zyx(
    index_batches: Iterable[np.ndarray],
    volume_shape: tuple[int, int, int],
) -> np.ndarray:
    """Return a surface-occupancy grid from batches of ZYX indices.

    Parameters
    ----------
    index_batches
        Integer arrays with shape ``(N, 3)`` in ZYX order, such as the output
        of :func:`cavegen.core.normalization.normalize_xyz_to_zyx_indices`.
    volume_shape
        Shape of the returned grid in ``(depth, height, width)`` order.

    Returns
    -------
    numpy.ndarray
        Boolean grid in which ``True`` marks a sampled surface voxel.
    """

    _validate_volume_shape(volume_shape)
    surface_voxels = np.zeros(volume_shape, dtype=bool)

    for batch_index, indices_zyx in enumerate(index_batches):
        _validate_index_batch(indices_zyx, batch_index, volume_shape)
        if indices_zyx.shape[0] == 0:
            continue

        # Advanced indexing marks every normalized surface coordinate at once.
        surface_voxels[
            indices_zyx[:, 0],
            indices_zyx[:, 1],
            indices_zyx[:, 2],
        ] = True

    return surface_voxels


def _validate_volume_shape(volume_shape: tuple[int, int, int]) -> None:
    """Validate the positive ZYX shape of a target surface grid."""

    if not isinstance(volume_shape, tuple) or len(volume_shape) != 3:
        raise ValueError("volume_shape must be a tuple with three dimensions.")
    if any(isinstance(size, bool) or not isinstance(size, (int, np.integer)) for size in volume_shape):
        raise TypeError("volume_shape dimensions must be integers.")
    if any(size <= 0 for size in volume_shape):
        raise ValueError("volume_shape dimensions must be positive.")


def _validate_index_batch(
    indices_zyx: np.ndarray,
    batch_index: int,
    volume_shape: tuple[int, int, int],
) -> None:
    """Validate one batch of in-bounds integer ZYX indices."""

    if not isinstance(indices_zyx, np.ndarray):
        raise TypeError(f"Batch {batch_index} must be a numpy.ndarray.")
    if indices_zyx.ndim != 2 or indices_zyx.shape[1] != 3:
        raise ValueError(f"Batch {batch_index} must have shape (N, 3), got {indices_zyx.shape}.")
    if not np.issubdtype(indices_zyx.dtype, np.integer):
        raise TypeError(f"Batch {batch_index} must contain integer ZYX indices.")
    if np.any(indices_zyx < 0) or np.any(indices_zyx >= volume_shape):
        raise ValueError(f"Batch {batch_index} contains indices outside volume_shape {volume_shape}.")
