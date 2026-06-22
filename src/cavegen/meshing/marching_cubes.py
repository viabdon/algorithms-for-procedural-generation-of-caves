from __future__ import annotations

import numpy as np
from skimage import measure


def volume_to_mesh(volume: np.ndarray, level: float = 0.5) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Convert a boolean volume to vertices, faces, normals and values using Marching Cubes."""
    volume_float = np.asarray(volume, dtype=np.float32)
    if volume_float.max() == volume_float.min():
        raise ValueError("Marching Cubes requires a volume with both open and closed voxels.")
    verts, faces, normals, values = measure.marching_cubes(volume_float, level=level)
    return verts, faces, normals, values
