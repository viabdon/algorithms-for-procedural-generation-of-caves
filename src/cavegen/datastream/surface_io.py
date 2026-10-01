"""Persist observed-surface voxel grids as compressed NPZ archives.

Surface grids use a format separate from ``Volume3D`` archives: their ``True``
values mark observed reference surface, rather than open cave space. JSON
metadata records the context needed to interpret and reproduce the grid.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np


def save_surface_npz(
    surface_voxels: np.ndarray,
    path: str | Path,
    metadata: Mapping[str, Any],
) -> None:
    """Save a 3D observed-surface grid and JSON-compatible metadata as NPZ.

    ``True`` in ``surface_voxels`` means an observed surface voxel. Parent
    directories are created when necessary; data is encoded as ``uint8`` and
    restored to ``bool`` by :func:`load_surface_npz`.
    """

    _validate_surface_voxels(surface_voxels)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        surface_voxels=surface_voxels.astype(np.uint8),
        metadata=json.dumps(dict(metadata)),
    )


def load_surface_npz(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    """Load a surface NPZ archive as a boolean grid and its metadata.

    The archive must contain ``surface_voxels`` and valid JSON metadata. This
    strict validation prevents a cave-volume archive from being mistaken for a
    surface reference.
    """

    with np.load(Path(path), allow_pickle=False) as file:
        if "surface_voxels" not in file or "metadata" not in file:
            raise ValueError("Surface archive must contain surface_voxels and metadata.")
        surface_voxels = file["surface_voxels"].astype(bool)
        metadata_raw = str(file["metadata"])

    _validate_surface_voxels(surface_voxels)
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError as error:
        raise ValueError("Surface archive metadata must be valid JSON.") from error
    if not isinstance(metadata, dict):
        raise ValueError("Surface archive metadata must be a JSON object.")
    return surface_voxels, metadata


def _validate_surface_voxels(surface_voxels: np.ndarray) -> None:
    """Validate the public three-dimensional surface-grid contract."""

    if not isinstance(surface_voxels, np.ndarray):
        raise TypeError("surface_voxels must be a numpy.ndarray.")
    if surface_voxels.ndim != 3:
        raise ValueError(
            "surface_voxels must be a 3D array, "
            f"got shape {surface_voxels.shape}."
        )
    if surface_voxels.dtype != np.bool_:
        raise TypeError("surface_voxels must use bool dtype.")
