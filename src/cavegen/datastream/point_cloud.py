"""Select a streaming coordinate reader by point-cloud extension."""

from collections.abc import Iterator
from pathlib import Path

import numpy as np

from cavegen.datastream.f32 import iter_f32_xyz
from cavegen.datastream.las import iter_las_xyz
from cavegen.datastream.ply import iter_ply_xyz
from cavegen.datastream.xyz import iter_xyz_xyz


def iter_point_cloud_xyz(
    path: str | Path, batch_size: int, *, origin_xyz: np.ndarray | None = None
) -> Iterator[np.ndarray]:
    """Read XYZ batches, optionally translated to a local float64 frame."""
    readers = {".ply": iter_ply_xyz, ".xyz": iter_xyz_xyz, ".f32": iter_f32_xyz,
               ".las": iter_las_xyz}
    suffix = Path(path).suffix.lower()
    if suffix not in readers:
        raise ValueError(f"Unsupported point-cloud format {suffix!r}; use .ply, .xyz, .f32 or .las.")
    if origin_xyz is None:
        yield from readers[suffix](path, batch_size)
    elif suffix == ".las":
        yield from iter_las_xyz(path, batch_size, origin_xyz=origin_xyz)
    else:
        for batch in readers[suffix](path, batch_size):
            yield batch - origin_xyz
