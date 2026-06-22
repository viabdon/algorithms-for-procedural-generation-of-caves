from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class Volume3D:
    """Boolean 3D cave volume.

    Convention:
        True  -> open cave space
        False -> solid/closed space
    """

    data: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.data.ndim != 3:
            raise ValueError(f"Volume3D expects a 3D array, got shape {self.data.shape}.")
        if self.data.dtype != np.bool_:
            self.data = self.data.astype(bool, copy=False)

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(int(v) for v in self.data.shape)

    @property
    def open_voxels(self) -> int:
        return int(self.data.sum())

    @property
    def fill_ratio(self) -> float:
        return float(self.open_voxels / self.data.size)

    @classmethod
    def empty(cls, shape: tuple[int, int, int], **metadata: Any) -> "Volume3D":
        return cls(np.zeros(shape, dtype=bool), metadata=metadata)

    @classmethod
    def full_open(cls, shape: tuple[int, int, int], **metadata: Any) -> "Volume3D":
        return cls(np.ones(shape, dtype=bool), metadata=metadata)

    @classmethod
    def from_array(cls, array: np.ndarray, **metadata: Any) -> "Volume3D":
        return cls(np.asarray(array, dtype=bool), metadata=metadata)
