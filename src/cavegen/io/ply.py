"""Read PLY vertex coordinates incrementally.

PLY files begin with an ASCII header that declares their encoding, elements,
and properties. This module reads that header without loading the payload, then
yields XYZ vertex batches as ``float32`` arrays with shape ``(n_points, 3)``.

Binary PLY files use a structured, read-only :class:`numpy.memmap`. ASCII PLY
files are streamed line by line. Both paths keep memory bounded by the selected
batch size.

Notes
-----
Only scalar vertex properties are supported. Vertex data must be the first PLY
element, so its binary payload starts immediately after the header. Faces and
later elements are intentionally not read.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np


PlyFormat = Literal["ascii", "binary_little_endian", "binary_big_endian"]

_PLY_TYPE_CODES = {
    "char": "i1",
    "int8": "i1",
    "uchar": "u1",
    "uint8": "u1",
    "short": "i2",
    "int16": "i2",
    "ushort": "u2",
    "uint16": "u2",
    "int": "i4",
    "int32": "i4",
    "uint": "u4",
    "uint32": "u4",
    "float": "f4",
    "float32": "f4",
    "double": "f8",
    "float64": "f8",
}
_SUPPORTED_FORMATS = frozenset({"ascii", "binary_little_endian", "binary_big_endian"})
_XYZ_PROPERTY_NAMES = ("x", "y", "z")


@dataclass(frozen=True, slots=True)
class PlyProperty:
    """A scalar property declared for a PLY vertex element.

    Parameters
    ----------
    name:
        Property name declared in the PLY header.
    type_name:
        PLY scalar type name, such as ``float`` or ``uchar``.
    """

    name: str
    type_name: str


@dataclass(frozen=True, slots=True)
class PlyHeader:
    """Validated PLY information required to stream vertex coordinates.

    Parameters
    ----------
    format:
        Payload encoding declared by the PLY header.
    vertex_count:
        Number of vertex records declared in the header.
    vertex_properties:
        Scalar properties of each vertex, in on-disk order.
    data_offset:
        Byte position immediately after the ``end_header`` line.
    """

    format: PlyFormat
    vertex_count: int
    vertex_properties: tuple[PlyProperty, ...]
    data_offset: int


def read_ply_header(path: str | Path) -> PlyHeader:
    """Read and validate a PLY header without reading its payload.

    Parameters
    ----------
    path:
        Path to a PLY file.

    Returns
    -------
    PlyHeader
        Encoding, vertex layout, vertex count, and payload byte offset.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the path is not a file or the PLY header is unsupported or invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"PLY file not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"PLY path is not a regular file: {file_path}")

    with file_path.open("rb") as file:
        first_line = _read_header_line(file, file_path)
        if first_line != "ply":
            raise ValueError(f"Invalid PLY file {file_path}: first line must be 'ply'.")

        file_format: PlyFormat | None = None
        vertex_count: int | None = None
        vertex_properties: list[PlyProperty] = []
        current_element: str | None = None
        element_index = -1
        vertex_element_index: int | None = None

        while True:
            line = _read_header_line(file, file_path)
            if line == "end_header":
                break
            if not line or line.startswith("comment") or line.startswith("obj_info"):
                continue

            fields = line.split()
            keyword = fields[0]
            if keyword == "format":
                file_format = _parse_format(fields, file_path)
            elif keyword == "element":
                current_element, element_count = _parse_element(fields, file_path)
                element_index += 1
                if current_element == "vertex":
                    if vertex_count is not None:
                        raise ValueError(f"Invalid PLY file {file_path}: duplicate vertex element.")
                    vertex_count = element_count
                    vertex_element_index = element_index
            elif keyword == "property" and current_element == "vertex":
                vertex_properties.append(_parse_vertex_property(fields, file_path))

        if file_format is None:
            raise ValueError(f"Invalid PLY file {file_path}: missing format declaration.")
        if vertex_count is None or vertex_element_index is None:
            raise ValueError(f"Invalid PLY file {file_path}: missing vertex element.")
        if vertex_element_index != 0:
            raise ValueError(
                f"Unsupported PLY file {file_path}: vertex must be the first element "
                "for incremental reading."
            )

        _validate_vertex_properties(vertex_properties, file_path)
        return PlyHeader(
            format=file_format,
            vertex_count=vertex_count,
            vertex_properties=tuple(vertex_properties),
            data_offset=file.tell(),
        )


def iter_ply_xyz(path: str | Path, batch_size: int) -> Iterator[np.ndarray]:
    """Yield ``float32`` XYZ vertex batches from a PLY file.

    Parameters
    ----------
    path:
        Path to a validated ASCII or binary PLY file.
    batch_size:
        Maximum number of vertices in each yielded batch. Must be positive.

    Yields
    ------
    numpy.ndarray
        Coordinate array with dtype ``float32`` and shape ``(n_points, 3)``,
        where ``0 < n_points <= batch_size``.

    Raises
    ------
    ValueError
        If ``batch_size`` is invalid, the file has no vertices, or vertex data
        is malformed or contains non-finite coordinates.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, (int, np.integer)):
        raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}.")
    if batch_size <= 0:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size}.")

    header = read_ply_header(path)
    if header.vertex_count == 0:
        raise ValueError(f"PLY file has no vertices: {Path(path)}")

    if header.format == "ascii":
        yield from _iter_ascii_xyz(Path(path), header, int(batch_size))
    else:
        yield from _iter_binary_xyz(Path(path), header, int(batch_size))


def _read_header_line(file: object, file_path: Path) -> str:
    raw_line = file.readline()
    if raw_line == b"":
        raise ValueError(f"Invalid PLY file {file_path}: header ended before 'end_header'.")
    try:
        return raw_line.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise ValueError(f"Invalid PLY header in {file_path}: expected ASCII text.") from error


def _parse_format(fields: list[str], file_path: Path) -> PlyFormat:
    if len(fields) != 3 or fields[2] != "1.0" or fields[1] not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported PLY format declaration in {file_path}: {' '.join(fields)!r}.")
    return fields[1]  # type: ignore[return-value]


def _parse_element(fields: list[str], file_path: Path) -> tuple[str, int]:
    if len(fields) != 3:
        raise ValueError(f"Invalid element declaration in {file_path}: {' '.join(fields)!r}.")
    try:
        count = int(fields[2])
    except ValueError as error:
        raise ValueError(f"Invalid element count in {file_path}: {fields[2]!r}.") from error
    if count < 0:
        raise ValueError(f"Invalid negative element count in {file_path}: {count}.")
    return fields[1], count


def _parse_vertex_property(fields: list[str], file_path: Path) -> PlyProperty:
    if len(fields) >= 2 and fields[1] == "list":
        raise ValueError(f"Unsupported PLY file {file_path}: vertex list properties are not supported.")
    if len(fields) != 3:
        raise ValueError(f"Invalid vertex property declaration in {file_path}: {' '.join(fields)!r}.")
    if fields[1] not in _PLY_TYPE_CODES:
        raise ValueError(f"Unsupported PLY vertex type in {file_path}: {fields[1]!r}.")
    return PlyProperty(name=fields[2], type_name=fields[1])


def _validate_vertex_properties(properties: list[PlyProperty], file_path: Path) -> None:
    names = [property_.name for property_ in properties]
    if len(set(names)) != len(names):
        raise ValueError(f"Invalid PLY file {file_path}: duplicate vertex property names.")
    missing = [name for name in _XYZ_PROPERTY_NAMES if name not in names]
    if missing:
        raise ValueError(f"Invalid PLY file {file_path}: missing vertex properties {missing}.")


def _iter_ascii_xyz(path: Path, header: PlyHeader, batch_size: int) -> Iterator[np.ndarray]:
    property_count = len(header.vertex_properties)
    xyz_indices = [
        next(index for index, property_ in enumerate(header.vertex_properties) if property_.name == name)
        for name in _XYZ_PROPERTY_NAMES
    ]

    with path.open("rb") as file:
        file.seek(header.data_offset)
        for batch_start in range(0, header.vertex_count, batch_size):
            batch_stop = min(batch_start + batch_size, header.vertex_count)
            xyz_batch = np.empty((batch_stop - batch_start, 3), dtype=np.float32)
            for batch_index in range(xyz_batch.shape[0]):
                raw_line = file.readline()
                if raw_line == b"":
                    raise ValueError(
                        f"Invalid ASCII PLY file {path}: expected {header.vertex_count} vertex records."
                    )
                values = np.fromstring(raw_line.decode("ascii"), sep=" ", dtype=np.float32)
                if values.size != property_count:
                    point_index = batch_start + batch_index
                    raise ValueError(
                        f"Invalid ASCII PLY vertex {point_index} in {path}: expected "
                        f"{property_count} values, got {values.size}."
                    )
                xyz_batch[batch_index] = values[xyz_indices]
            _validate_finite_coordinates(xyz_batch, path)
            yield xyz_batch


def _iter_binary_xyz(path: Path, header: PlyHeader, batch_size: int) -> Iterator[np.ndarray]:
    dtype = _vertex_dtype(header)
    records = np.memmap(
        path,
        dtype=dtype,
        mode="r",
        offset=header.data_offset,
        shape=(header.vertex_count,),
    )

    for batch_start in range(0, header.vertex_count, batch_size):
        batch_stop = min(batch_start + batch_size, header.vertex_count)
        vertex_batch = records[batch_start:batch_stop]
        xyz_batch = np.empty((vertex_batch.shape[0], 3), dtype=np.float32)
        for output_index, name in enumerate(_XYZ_PROPERTY_NAMES):
            xyz_batch[:, output_index] = vertex_batch[name]
        _validate_finite_coordinates(xyz_batch, path)
        yield xyz_batch


def _vertex_dtype(header: PlyHeader) -> np.dtype:
    byte_order = "<" if header.format == "binary_little_endian" else ">"
    fields = [
        (property_.name, f"{byte_order}{_PLY_TYPE_CODES[property_.type_name]}")
        for property_ in header.vertex_properties
    ]
    return np.dtype(fields, align=False)


def _validate_finite_coordinates(xyz_batch: np.ndarray, path: Path) -> None:
    if not np.isfinite(xyz_batch).all():
        raise ValueError(f"PLY file contains non-finite XYZ coordinates: {path}")
