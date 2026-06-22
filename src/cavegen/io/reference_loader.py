from __future__ import annotations

from pathlib import Path

from cavegen.core.volume import Volume3D
from cavegen.io.voxel_io import load_volume_npz


def load_reference_volume(path: str | Path) -> Volume3D:
    """Load a reference cave volume.

    Initial implementation expects a preprocessed .npz volume. Mesh/point-cloud
    voxelization should be added once the reference dataset is selected.
    """
    return load_volume_npz(path)
