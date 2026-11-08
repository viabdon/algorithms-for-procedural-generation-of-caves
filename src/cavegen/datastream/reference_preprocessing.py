"""Voxelize a point-cloud reference surface without loading its point cloud at once.

This module connects the point-cloud readers with the format-independent normalization
and surface-voxelization steps. Bounds are read from the JSON artifact produced
by :mod:`cavegen.datastream.bounds`; the resulting boolean array uses the
surface convention, where ``True`` marks an observed surface voxel.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

from cavegen.core.normalization import normalize_xyz_to_zyx_indices
from cavegen.core.voxelization import voxelize_surface_zyx
from cavegen.datastream.point_cloud import iter_point_cloud_xyz
from cavegen.datastream.progress import report_point_progress


def load_xyz_bounds(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Load and validate ``min_xyz`` and ``max_xyz`` from a bounds JSON file.

    The returned arrays use ``float32`` and XYZ coordinate order, matching the
    contract of :func:`normalize_xyz_to_zyx_indices`.
    """

    bounds_path = Path(path)
    try:
        with bounds_path.open(encoding="utf-8") as file:
            metadata = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid bounds JSON file: {bounds_path}") from error

    try:
        min_xyz = np.asarray(metadata["min_xyz"], dtype=np.float32)
        max_xyz = np.asarray(metadata["max_xyz"], dtype=np.float32)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Bounds file must define numeric min_xyz and max_xyz arrays: {bounds_path}"
        ) from error

    if min_xyz.shape != (3,) or max_xyz.shape != (3,):
        raise ValueError("min_xyz and max_xyz must each have shape (3,).")
    if not np.isfinite(min_xyz).all() or not np.isfinite(max_xyz).all():
        raise ValueError("min_xyz and max_xyz must contain only finite coordinates.")
    if np.any(min_xyz > max_xyz):
        raise ValueError("min_xyz must be less than or equal to max_xyz on every axis.")

    return min_xyz, max_xyz


def voxelize_point_cloud_surface(
    source_path: str | Path,
    bounds_path: str | Path,
    volume_shape: tuple[int, int, int],
    batch_size: int,
    progress_every: int | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> np.ndarray:
    """Return a surface grid generated incrementally from a PLY, XYZ, F32 or LAS file.

    Each XYZ batch is normalized with the persisted global bounds and is
    immediately consumed by the voxelizer. Memory therefore holds only one
    coordinate batch, one index batch, and the target boolean grid.

    Parameters
    ----------
    source_path
        Source path accepted by :func:`iter_point_cloud_xyz`.
    bounds_path
        JSON file containing the complete-cloud ``min_xyz`` and ``max_xyz``.
    volume_shape
        Target grid shape in ``(depth, height, width)`` order.
    batch_size
        Maximum number of points read at a time.
    progress_every
        Report each crossed point-count milestone at batch boundaries. ``None`` disables
        progress reporting.
    progress_callback
        Function that receives the milestone number of processed points.
        It is required when ``progress_every`` is set.

    Returns
    -------
    numpy.ndarray
        Boolean ``(depth, height, width)`` surface-occupancy grid. ``True``
        means an observed surface voxel, not an open cave voxel.
    """

    min_xyz, max_xyz = load_xyz_bounds(bounds_path)

    def iter_normalized_batches() -> Iterator[np.ndarray]:
        batches = report_point_progress(
            iter_point_cloud_xyz(source_path, batch_size), progress_every, progress_callback
        )
        for xyz_batch in batches:
            yield normalize_xyz_to_zyx_indices(
                xyz_batch, min_xyz, max_xyz, volume_shape
            )

    index_batches = iter_normalized_batches()
    return voxelize_surface_zyx(index_batches, volume_shape)


def voxelize_ply_surface(
    ply_path: str | Path,
    bounds_path: str | Path,
    volume_shape: tuple[int, int, int],
    batch_size: int,
    progress_every: int | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> np.ndarray:
    """Backward-compatible PLY entry point for surface voxelization."""
    return voxelize_point_cloud_surface(
        ply_path, bounds_path, volume_shape, batch_size, progress_every, progress_callback
    )
