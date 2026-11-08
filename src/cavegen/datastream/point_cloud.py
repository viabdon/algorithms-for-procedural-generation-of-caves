"""Select a streaming coordinate reader by point-cloud extension."""

from collections.abc import Iterator
from pathlib import Path

import numpy as np

from cavegen.datastream.f32 import iter_f32_xyz
from cavegen.datastream.las import iter_las_xyz
from cavegen.datastream.ply import iter_ply_xyz
from cavegen.datastream.xyz import iter_xyz_xyz


def iter_point_cloud_xyz(path: str | Path, batch_size: int) -> Iterator[np.ndarray]:
    """Read XYZ batches from PLY, XYZ text, fixed-record F32, or LAS sources."""
    readers = {".ply": iter_ply_xyz, ".xyz": iter_xyz_xyz, ".f32": iter_f32_xyz,
               ".las": iter_las_xyz}
    suffix = Path(path).suffix.lower()
    if suffix not in readers:
        raise ValueError(f"Unsupported point-cloud format {suffix!r}; use .ply, .xyz, .f32 or .las.")
    yield from readers[suffix](path, batch_size)
