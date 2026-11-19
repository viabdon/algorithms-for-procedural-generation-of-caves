"""Stream uncompressed LAS point clouds with their stored coordinate transform.

Global coordinates follow the pipeline's float32 XYZ contract by default.
An optional origin enables local float64 decoding for georeferenced crops.
No CRS reprojection or classification filter is applied.
"""

from collections.abc import Iterator
from pathlib import Path

import laspy
import numpy as np


def _validate_header(header: laspy.LasHeader, source: Path) -> None:
    if header.are_points_compressed:
        raise ValueError(f"Compressed LAS/LAZ is not supported by this reader: {source}")
    if not np.isfinite(header.scales).all() or np.any(header.scales <= 0):
        raise ValueError(f"LAS coordinate scales must be finite and positive: {source}")
    if not np.isfinite(header.offsets).all():
        raise ValueError(f"LAS coordinate offsets must be finite: {source}")
    if header.point_count == 0:
        raise ValueError(f"LAS file has no points: {source}")
    minimum_size = header.offset_to_point_data + header.point_count * header.point_format.size
    if source.stat().st_size < minimum_size:
        raise ValueError(f"Truncated LAS point records: {source}")


def read_las_metadata(path: str | Path) -> dict[str, object]:
    """Describe the LAS coordinate decoding recorded alongside derived grids."""
    source = Path(path)
    try:
        with laspy.open(source, read_evlrs=False) as reader:
            header = reader.header
            _validate_header(header, source)
            return {
                "version": str(header.version),
                "point_format_id": header.point_format.id,
                "point_count": header.point_count,
                "scales_xyz": header.scales.tolist(),
                "offsets_xyz": header.offsets.tolist(),
                "coordinate_decoding": "raw_integer * scale + offset",
                "reprojection_applied": False,
            }
    except laspy.errors.LaspyException as error:
        raise ValueError(f"Invalid LAS file {source}: {error}") from error


def iter_las_xyz(
    path: str | Path,
    batch_size: int,
    *,
    origin_xyz: np.ndarray | None = None,
) -> Iterator[np.ndarray]:
    """Yield independent finite XYZ batches of at most batch_size points.

    LAS 1.0–1.4 point formats supported by laspy are read in chunks; only the
    current chunk is retained. Truncated point records and invalid transforms
    are rejected. When an origin is supplied, return local float64 coordinates
    by subtracting it from the LAS offset before adding the scaled integers.
    Otherwise return global float32 coordinates.
    """
    if (isinstance(batch_size, bool) or not isinstance(batch_size, (int, np.integer))
            or batch_size <= 0):
        raise ValueError("batch_size must be a positive integer.")
    origin = None if origin_xyz is None else np.asarray(origin_xyz, dtype=np.float64)
    if origin is not None and (origin.shape != (3,) or not np.isfinite(origin).all()):
        raise ValueError("origin_xyz must contain three finite coordinates.")
    source = Path(path)
    total = 0
    try:
        with laspy.open(source, read_evlrs=False) as reader:
            _validate_header(reader.header, source)
            expected = reader.header.point_count
            scale = reader.header.scales
            local_offset = None if origin is None else reader.header.offsets - origin
            for points in reader.chunk_iterator(int(batch_size)):
                with np.errstate(over="ignore", invalid="ignore"):
                    if local_offset is None:
                        xyz = np.column_stack((points.x, points.y, points.z)).astype(np.float32)
                    else:
                        raw = np.column_stack((points.X, points.Y, points.Z))
                        xyz = raw * scale + local_offset
                if not np.isfinite(xyz).all():
                    raise ValueError(
                        f"LAS coordinates must be finite {xyz.dtype} values: {source}, "
                        f"batch starting at point {total}"
                    )
                total += len(xyz)
                yield xyz
            if total != expected:
                raise ValueError(f"Truncated LAS file {source}: expected {expected} points, got {total}.")
    except laspy.errors.LaspyException as error:
        raise ValueError(f"Invalid LAS file {source}: {error}") from error
