"""Data structures describing the supported PLY vertex layout.

These immutable records separate the information extracted from a PLY header
from the code that reads its payload. They can therefore be shared by header
validation, binary memory mapping, and ASCII streaming without coupling those
operations to one another.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PlyFormat = Literal["ascii", "binary_little_endian", "binary_big_endian"]


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
