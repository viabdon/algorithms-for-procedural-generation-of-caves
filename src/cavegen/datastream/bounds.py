"""Compute exact spatial bounds from incremental XYZ point batches.

This module will consume validated ``float32`` arrays with shape ``(N, 3)``
and return the global minimum and maximum coordinates without retaining the
full point cloud in memory. It is intentionally independent of the F32 and
PLY readers so either source can provide the batches.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def calculate_xyz_bounds(batches: Iterable[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Return global XYZ minimum and maximum from point batches.

    Each batch must have dtype ``float32``, shape ``(N, 3)``, and finite
    coordinates.
    """

    global_min = np.full(3, np.inf, dtype=np.float32)
    global_max = np.full(3, -np.inf, dtype=np.float32)
    points_total = 0

    for i, batch in enumerate(batches):

        if not isinstance(batch, np.ndarray):
            raise TypeError(f"Batch ({i}) does not match the expected np.ndarray type")
        
        if batch.ndim != 2 or batch.shape[1] != 3:
          raise ValueError(
              f"Batch {i} must have shape (N, 3), got {batch.shape}."
          )

        if batch.dtype != np.float32:
            raise TypeError(f"Batch doesn't use np.float32 elements! batch.dtype = {batch.dtype}")

        if not np.isfinite(batch).all():
            raise ValueError("The batch has non-finite coordinates!")

        ## Skipping if there are no lines
        if batch.shape[0] == 0:
            continue

        batch_min = np.min(batch, axis=0)
        batch_max = np.max(batch, axis=0)

        global_min = np.minimum(batch_min, global_min)
        global_max = np.maximum(batch_max, global_max)
        points_total += batch.shape[0]

    if points_total == 0:
        raise ValueError("There are no points to calculate the limits.")

    return (global_min, global_max)