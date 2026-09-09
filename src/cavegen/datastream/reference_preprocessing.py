"""Voxelize a PLY reference surface without loading its point cloud at once.

This module connects the PLY reader with the format-independent normalization
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
from cavegen.datastream.ply import iter_ply_xyz


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


def voxelize_ply_surface(
    ply_path: str | Path,
    bounds_path: str | Path,
    volume_shape: tuple[int, int, int],
    batch_size: int,
    progress_every: int | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> np.ndarray:
    """Return a surface grid generated incrementally from a PLY file.

    Each PLY XYZ batch is normalized with the persisted global bounds and is
    immediately consumed by the voxelizer. Memory therefore holds only one
    coordinate batch, one index batch, and the target boolean grid.

    Parameters
    ----------
    ply_path
        Source PLY path accepted by :func:`iter_ply_xyz`.
    bounds_path
        JSON file containing the complete-cloud ``min_xyz`` and ``max_xyz``.
    volume_shape
        Target grid shape in ``(depth, height, width)`` order.
    batch_size
        Maximum number of PLY vertices read at a time.
    progress_every
        Emit progress after this many additional vertices. ``None`` disables
        progress reporting.
    progress_callback
        Function that receives the cumulative number of processed vertices.
        It is required when ``progress_every`` is set.

    Returns
    -------
    numpy.ndarray
        Boolean ``(depth, height, width)`` surface-occupancy grid. ``True``
        means an observed surface voxel, not an open cave voxel.
    """

    if progress_every is not None:
        if progress_every <= 0:
            raise ValueError("progress_every must be positive when provided.")
        if progress_callback is None:
            raise ValueError("progress_callback is required when progress_every is set.")

    min_xyz, max_xyz = load_xyz_bounds(bounds_path)

    def iter_normalized_batches() -> Iterator[np.ndarray]:
        """Normalize batches and report cumulative progress after each interval."""

        processed_vertices = 0
        next_progress = progress_every
        for xyz_batch in iter_ply_xyz(ply_path, batch_size):
            processed_vertices += len(xyz_batch)
            if next_progress is not None and processed_vertices >= next_progress:
                progress_callback(processed_vertices)
                next_progress += progress_every
            yield normalize_xyz_to_zyx_indices(
                xyz_batch, min_xyz, max_xyz, volume_shape
            )

    index_batches = iter_normalized_batches()
    return voxelize_surface_zyx(index_batches, volume_shape)
