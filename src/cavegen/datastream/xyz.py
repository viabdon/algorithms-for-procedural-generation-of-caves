"""Stream text point clouds with whitespace-separated X Y Z columns.

Blank lines and ``#`` comments (including inline comments) are skipped.
Additional columns, such as RGB or intensity, are ignored. There is no header
or point-count line; molecular XYZ files and comma-separated CSV are not this
format. Coordinates must be finite and representable as float32.
"""

from collections.abc import Iterator
from pathlib import Path

import numpy as np


def iter_xyz_xyz(path: str | Path, batch_size: int) -> Iterator[np.ndarray]:
    """Yield independent float32 arrays of shape (N, 3), at most batch_size rows.

    Malformed records raise ValueError with the source path and physical line
    number. An empty/comment-only cloud is rejected. Memory is bounded by one
    batch plus the current text line, independently of the cloud size.
    """
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, (int, np.integer))
        or batch_size <= 0
    ):
        raise ValueError("batch_size must be a positive integer.")
    source = Path(path)
    batch = np.empty((batch_size, 3), dtype=np.float32)
    count = 0
    total = 0
    with source.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            fields = line.partition("#")[0].split()
            if not fields:
                continue
            message = f"Invalid XYZ coordinates in {source} at line {line_number}"
            if len(fields) < 3:
                raise ValueError(f"{message}: expected at least X Y Z columns.")
            try:
                with np.errstate(over="ignore"):
                    point = np.asarray(fields[:3], dtype=np.float32)
            except ValueError as error:
                raise ValueError(f"{message}: expected numeric X Y Z columns.") from error
            if not np.isfinite(point).all():
                raise ValueError(f"{message}: coordinates must be finite float32 values.")
            batch[count] = point
            count += 1
            total += 1
            if count == batch_size:
                yield batch
                batch = np.empty((batch_size, 3), dtype=np.float32)
                count = 0
    if count:
        yield batch[:count].copy()
    if total == 0:
        raise ValueError(f"XYZ file has no points: {source}")
