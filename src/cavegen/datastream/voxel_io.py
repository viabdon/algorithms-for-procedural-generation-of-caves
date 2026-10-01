"""Persist ``Volume3D`` cave volumes as compressed NPZ archives.

The archive stores boolean voxel data as compact ``uint8`` values and metadata
as JSON. It follows :class:`cavegen.core.volume.Volume3D`'s convention: ``True``
means open cave space. Surface-occupancy grids require separate persistence
because their ``True`` values have a different meaning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from cavegen.core.volume import Volume3D


def save_volume_npz(volume: Volume3D, path: str | Path) -> None:
    """Save a cave volume and JSON-compatible metadata to a compressed NPZ file.

    Parent directories are created when needed. The boolean data is encoded as
    ``uint8`` to keep the archive format explicit and is restored to ``bool``
    by :func:`load_volume_npz`.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, data=volume.data.astype(np.uint8), metadata=json.dumps(volume.metadata))


def load_volume_npz(path: str | Path) -> Volume3D:
    """Load a compressed NPZ archive into a ``Volume3D`` instance.

    Archives without metadata, or legacy archives whose metadata is not valid
    JSON, receive an empty metadata dictionary. Data is always converted back
    to a boolean array before constructing the volume.
    """

    with np.load(Path(path), allow_pickle=False) as file:
        data = file["data"].astype(bool)
        metadata_raw = str(file["metadata"]) if "metadata" in file else "{}"
    try:
        metadata: dict[str, Any] = json.loads(metadata_raw)
    except json.JSONDecodeError:
        metadata = {}
    return Volume3D(data=data, metadata=metadata)
