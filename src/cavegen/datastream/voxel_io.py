from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from cavegen.core.volume import Volume3D


def save_volume_npz(volume: Volume3D, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, data=volume.data.astype(np.uint8), metadata=json.dumps(volume.metadata))


def load_volume_npz(path: str | Path) -> Volume3D:
    with np.load(Path(path), allow_pickle=False) as file:
        data = file["data"].astype(bool)
        metadata_raw = str(file["metadata"]) if "metadata" in file else "{}"
    try:
        metadata: dict[str, Any] = json.loads(metadata_raw)
    except json.JSONDecodeError:
        metadata = {}
    return Volume3D(data=data, metadata=metadata)
