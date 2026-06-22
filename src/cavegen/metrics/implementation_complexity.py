from __future__ import annotations

from pathlib import Path


def count_logical_lines(path: str | Path) -> int:
    """Count non-empty, non-comment Python lines as a simple implementation proxy."""
    total = 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            total += 1
    return total
