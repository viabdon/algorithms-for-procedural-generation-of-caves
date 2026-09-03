"""Read fixed-record ``.f32`` point clouds incrementally.

Each record contains seven ``float32`` attributes in this order::

    x, y, z, nir_reflectance, red, green, blue

The module validates that the file size is compatible with this layout and
opens the data through :class:`numpy.memmap` in read-only mode. This avoids
loading an entire point cloud into memory. ``iter_f32_xyz`` yields only the XYZ
coordinates in bounded ``float32`` batches, which are suitable for subsequent
normalization and voxelization passes.

Notes
-----
The input represents sampled surface points, not a boolean cave-void volume.
Voxelization must therefore preserve this distinction and document any later
surface-to-void conversion.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
from collections.abc import Iterator

# Estrutura de um arquivo .f32:
# O arquivo é um binário contendo uma sequência de números float32.
# Cada ponto da nuvem é descrito por 7 atributos, sempre nesta ordem:
#
#   [x_coord] [y_coord] [z_coord] [nir_reflectance] [red] [green] [blue]
#
#   Portanto, o arquivo inteiro é:
#
#   ponto_1: x y z nir r g b | ponto_2: x y z nir r g b | ...
#


ATTRIBUTES_PER_POINT = 7
BYTES_PER_POINT = ATTRIBUTES_PER_POINT*np.dtype(np.float32).itemsize
COL_X_INDEX = 0
COL_Y_INDEX = 1
COL_Z_INDEX = 2
COL_NIR_INDEX = 3  # refletância no infravermelho próximo (sempre descartada)
COL_R_INDEX = 4
COL_G_INDEX = 5
COL_B_INDEX = 6

XYZ_COLUMNS = [COL_X_INDEX, COL_Y_INDEX, COL_Z_INDEX]
RGB_COLUMNS = [COL_R_INDEX, COL_G_INDEX, COL_B_INDEX]

def count_f32_points(path: str | Path) -> int:
    """Validate an .f32 file layout and return its record count."""

    file_path: Path = Path(path)

    if not file_path.exists():
      raise FileNotFoundError(f"The .f32 file does not exist in the specified path: {file_path}")

    if not (file_path.is_file()):
        raise ValueError(f"The specified path is not of the .f32 format: {file_path}")

    file_byte_size: int = file_path.stat().st_size

    # If the size of the file is NOT a multiple of the bytesize we need for
    # np.memmap() to work:

    if (file_byte_size % BYTES_PER_POINT != 0):
        raise ValueError(f"The file found on the path: {file_path}, has a size of {file_byte_size} Bytes, which isn't a multiple of {BYTES_PER_POINT} as it is expected.")

    # Using specifically // to get an int!!!
    points_amount: int = file_byte_size // BYTES_PER_POINT
    return points_amount

def open_f32_records(path: str | Path) -> np.memmap:
    """Open validated records with shape (n_points, 7), read-only."""

    # Calls upon the function to validate and return the ammount of points in a .f32 file.
    points_amount: int = count_f32_points(path)


    if points_amount == 0:
        raise ValueError(f"Cannot memory-map an empty .f32 file: {path}")

    # Uses np.memmap() to create accessible data without running out of memory.
    memmapped_data = np.memmap(path, dtype=np.float32, mode='r', shape=(points_amount,ATTRIBUTES_PER_POINT))

    return memmapped_data

def iter_f32_xyz(path: str | Path, batch_size: int) -> Iterator[np.ndarray]:
    """Yield float32 XYZ batches with shape (batch_size, 3)."""

    if isinstance(batch_size, bool) or not isinstance(batch_size, (int, np.integer)):
        raise TypeError("batch_size must be an integer.")
    if batch_size <= 0:
        raise ValueError(f"The value of `batch_size` (currently: {batch_size}) must be a positive integer.")

    records = open_f32_records(path)
    points_amount: int = records.shape[0]

    # Iterating through each batch
    for start in range(0, points_amount, batch_size):
        stop = min(start + batch_size, points_amount)
        xyz = records[start:stop, XYZ_COLUMNS]
        yield xyz
