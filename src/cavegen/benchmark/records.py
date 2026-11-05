"""Incrementally persist experiment rows with one stable CSV header."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import scipy

from cavegen.core.volume import Volume3D
from cavegen.metrics import evaluate_structure
from cavegen.metrics.structural import MetricValue
from cavegen.metrics.validation import Connectivity, SpacingZYX


def create_experiment_context(name: str, config_path: str) -> dict[str, str]:
    """Capture execution identity and software versions once per experiment.

    Parameters
    ----------
    name
        Human-readable experiment label.
    config_path
        YAML source path or explicit interactive/evaluation origin label.

    Returns
    -------
    dict
        Ordered context shared by generation and structural reevaluation.
    """
    try:
        revision = subprocess.check_output(
            ["git", "describe", "--always", "--dirty"],
            cwd=Path(__file__).resolve().parents[3],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    return {
        "experiment_id": uuid4().hex,
        "experiment_name": name,
        "config_path": config_path,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "platform": platform.platform(),
        "backend": "cpu",
        "code_revision": revision,
    }


def make_experiment_record(
    volume: Volume3D,
    *,
    context: Mapping[str, str],
    algorithm: str,
    seed: int | None,
    volume_path: str | Path,
    parameters: Mapping[str, Any],
    variant: str = "baseline",
    connectivity: Connectivity = 6,
    spacing_zyx: SpacingZYX = (1.0, 1.0, 1.0),
    elapsed_seconds: float | None = None,
    peak_rss_bytes: int | None = None,
    rss_sample_count: int = 0,
    rss_sampling_interval_seconds: float | None = None,
) -> dict[str, MetricValue]:
    """Evaluate a volume and build one row using the existing CSV schema.

    Parameters
    ----------
    volume
        Known open-space Volume3D, never an observed-surface grid.
    context
        Context returned by create_experiment_context.
    algorithm, seed, volume_path, parameters
        Source identity, archived volume and effective parameters/provenance.
    variant
        baseline for generation; structural_evaluation for existing archives.
    connectivity, spacing_zyx
        Explicit structural measurement settings.
    elapsed_seconds, peak_rss_bytes, rss_sample_count, rss_sampling_interval_seconds
        Generation measurements when available. Reevaluation leaves timing
        and RSS absent; its evaluation cost is not reported as generation.

    Returns
    -------
    dict
        Stable scalar columns compatible with the initial structural-v1 CSV.
    """
    row: dict[str, MetricValue] = {
        "run_id": uuid4().hex,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        **context,
        "algorithm": algorithm,
        "variant": variant,
        "seed": seed,
        "repetition": 0,
        "shape": "x".join(str(v) for v in volume.shape),
        "elapsed_seconds": elapsed_seconds,
        "peak_rss_bytes": peak_rss_bytes,
        "rss_sample_count": rss_sample_count,
        "rss_sampling_interval_seconds": rss_sampling_interval_seconds,
        "volume_path": str(volume_path),
    }
    row.update(evaluate_structure(volume, connectivity=connectivity,
                                  spacing_zyx=spacing_zyx).to_record())
    row["parameters_json"] = json.dumps(dict(parameters), sort_keys=True)
    return row


def append_experiment_record(path: str | Path, record: Mapping[str, MetricValue]) -> None:
    """Append a completed execution without replacing earlier experiment rows.

    Parameters
    ----------
    path
        Central CSV destination, used by one sequential writer at a time.
    record
        Flat scalar columns including a nonempty run_id. Column names/order
        must match an existing header; duplicate run identifiers are rejected.

    Raises
    ------
    ValueError
        For missing identity, incompatible headers or duplicate run_id. The
        file is validated before writing, so these errors preserve its bytes.

    Notes
    -----
    None is written as an empty cell, never as zero. This is an append-only
    sequential CSV writer, not a concurrent database or crash recovery log.
    Identity scanning is incremental and retains no previous rows in RAM.
    """
    if not isinstance(record.get("run_id"), str) or not record["run_id"]:
        raise ValueError(f"Experiment record for {path} requires a nonempty run_id.")
    if any(not isinstance(value, (str, int, float, bool, type(None))) for value in record.values()):
        raise TypeError(f"Experiment record for {path} must contain only scalar values.")
    output = Path(path)
    fieldnames = list(record)
    has_header = output.exists() and output.stat().st_size > 0
    if has_header:
        with output.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != fieldnames:
                raise ValueError(f"Incompatible experiment CSV header: {output}.")
            for row in reader:
                if row["run_id"] == record["run_id"]:
                    raise ValueError(f"Duplicate run_id {record['run_id']} in {output}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not has_header:
            writer.writeheader()
        writer.writerow(record)
