"""Report point-count milestones while preserving streamed batches."""

from collections.abc import Callable, Iterable, Iterator

import numpy as np


def report_point_progress(
    batches: Iterable[np.ndarray],
    every: int | None = None,
    callback: Callable[[int], None] | None = None,
) -> Iterator[np.ndarray]:
    """Report each crossed milestone, including multiple milestones per batch.

    Callbacks receive milestone counts, not batch-end counts. Notifications
    happen at batch boundaries, after those points have been read.
    """
    if every is not None:
        if isinstance(every, bool) or not isinstance(every, (int, np.integer)) or every <= 0:
            raise ValueError("progress_every must be a positive integer when provided.")
        if callback is None:
            raise ValueError("progress_callback is required when progress_every is set.")
    total = 0
    milestone = every
    for batch in batches:
        total += len(batch)
        while milestone is not None and total >= milestone:
            callback(milestone)
            milestone += every
        yield batch
