"""Select reproducible XYZ point samples with bounded memory.

The functions in this module consume incremental point-cloud batches and keep a
uniform reservoir sample. They are independent of the source format, so the
same sampler can be used with the F32 and PLY readers.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def reservoir_sample_xyz(
    batches: Iterable[np.ndarray],
    max_points: int,
    seed: int | None,
) -> np.ndarray:
    """Return a reproducible uniform sample of XYZ points from ``batches``.

    Parameters
    ----------
    batches
        Iterable of ``float32`` arrays with shape ``(n_points, 3)``.
    max_points
        Maximum number of points retained in memory and returned.
    seed
        Seed for the local random generator. Equal input order and seed yield
        the same sample.

    Returns
    -------
    numpy.ndarray
        A ``float32`` array with shape ``(min(total_points, max_points), 3)``.

    Raises
    ------
    ValueError
        If ``max_points`` is not positive or a batch does not have XYZ shape.
    TypeError
        If ``max_points`` or ``seed`` has an invalid type, or a batch is not
        ``float32``.
    """
    _validate_sampling_arguments(max_points, seed)

    generator = np.random.default_rng(seed)
    reservoir = np.empty((max_points, 3), dtype=np.float32)
    points_seen = 0

    for batch_index, batch in enumerate(batches):
        _validate_xyz_batch(batch, batch_index)

        for point in batch:
            if points_seen < max_points:
                reservoir[points_seen] = point
            else:
                replacement_index = generator.integers(points_seen + 1)
                if replacement_index < max_points:
                    reservoir[replacement_index] = point

            points_seen += 1

    return reservoir[: min(points_seen, max_points)]


def _validate_sampling_arguments(max_points: int, seed: int | None) -> None:
    """Validate public sampling arguments before allocating the reservoir."""
    integer_types = (int, np.integer)

    if isinstance(max_points, bool) or not isinstance(max_points, integer_types):
        raise TypeError("max_points must be a positive integer.")
    if max_points <= 0:
        raise ValueError("max_points must be a positive integer.")
    if seed is not None and (
        isinstance(seed, bool) or not isinstance(seed, integer_types)
    ):
        raise TypeError("seed must be an integer or None.")


def _validate_xyz_batch(batch: np.ndarray, batch_index: int) -> None:
    """Ensure a streamed batch follows the XYZ ``float32`` contract."""
    if not isinstance(batch, np.ndarray):
        raise TypeError(f"Batch {batch_index} must be a numpy.ndarray.")
    if batch.ndim != 2 or batch.shape[1:] != (3,):
        raise ValueError(
            f"Batch {batch_index} must have shape (n_points, 3), got {batch.shape}."
        )
    if batch.dtype != np.float32:
        raise TypeError(f"Batch {batch_index} must have dtype float32, got {batch.dtype}.")
