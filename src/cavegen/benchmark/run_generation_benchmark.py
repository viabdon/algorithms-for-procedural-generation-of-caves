from __future__ import annotations

import argparse
import inspect
from collections.abc import Callable, Mapping
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from cavegen.benchmark.records import (
    append_experiment_record,
    create_experiment_context,
    make_experiment_record,
)
from cavegen.core.config import load_yaml
from cavegen.datastream.voxel_io import save_volume_npz
from cavegen.generators.cellular_automata import generate_cellular_automata
from cavegen.generators.random_walk import generate_random_walk
from cavegen.metrics.structural import MetricValue
from cavegen.profiling.resource_tracker import ResourceSampler


def _shape(config: Mapping[str, Any]) -> tuple[int, int, int]:
    value = config.get("shape", [64, 64, 64])
    if len(value) != 3:
        raise ValueError("shape must have three dimensions: [depth, height, width].")
    return tuple(int(v) for v in value)


def run(config_path: str | Path, out_csv: str | Path) -> None:
    """Generate configured volumes and append one structural record per run.

    Parameters
    ----------
    config_path
        YAML configuration; shape defaults to 64 cubed in ZYX. Seeds here
        are geometric samples. This initial runner has one timing repetition.
    out_csv
        Central CSV with the structural-v1 columns. Legacy CSV headers are
        rejected rather than overwritten. Use one writer at a time.
    """
    config = load_yaml(config_path)
    run_configuration(config, out_csv, config_path=str(config_path))


def run_configuration(
    config: Mapping[str, Any],
    out_csv: str | Path,
    *,
    config_path: str = "interactive",
    on_record: Callable[[dict[str, MetricValue]], None] | None = None,
) -> str:
    """Generate from an in-memory configuration shared by menus and YAML CLI.

    Parameters
    ----------
    config
        Same shape, seeds, algorithms and outputs mapping as the YAML runner.
    out_csv
        Central CSV to append after each completed generation/evaluation.
    config_path
        Configuration origin recorded along with effective arguments.
    on_record
        Optional progress callback called only after a row has been saved.

    Returns
    -------
    str
        Unique experiment identifier. No temporary YAML is required.
    """
    shape = _shape(config)
    seeds = [int(seed) for seed in config.get("seeds", [0])]
    algorithms = config.get("algorithms", {})
    volumes_dir = Path(config.get("outputs", {}).get("volumes_dir", "results/volumes"))
    context = create_experiment_context(
        str(config.get("experiment_name", Path(config_path).stem)), config_path
    )
    experiment_id = context["experiment_id"]
    volumes_dir = volumes_dir / experiment_id
    generators = {
        "random_walk": generate_random_walk,
        "cellular_automata": generate_cellular_automata,
    }
    unknown = set(algorithms) - generators.keys()
    if unknown:
        raise ValueError(f"Unknown algorithms in {config_path}: {sorted(unknown)}.")
    for seed in seeds:
        for algorithm, generate in generators.items():
            if algorithm not in algorithms:
                continue
            params = algorithms[algorithm] or {}
            # Mesma regua do track_resources: comparar algoritmos exige o mesmo
            # amostrador nos dois lados.
            with ResourceSampler() as sampler:
                start = perf_counter()
                volume = generate(shape=shape, seed=seed, **params)
                elapsed_seconds = perf_counter() - start
            run_id = uuid4().hex
            path = volumes_dir / f"{algorithm}_{run_id}.npz"
            effective = inspect.signature(generate).bind(shape=shape, seed=seed, **params)
            effective.apply_defaults()
            row = make_experiment_record(
                volume, context=context, algorithm=algorithm, seed=seed,
                volume_path=path, parameters=effective.arguments,
                elapsed_seconds=elapsed_seconds,
                peak_rss_bytes=max((s.rss_bytes for s in sampler.samples), default=None),
                rss_sample_count=len(sampler.samples),
                rss_sampling_interval_seconds=sampler.interval_seconds,
            )
            row["run_id"] = run_id
            save_volume_npz(volume, path)
            append_experiment_record(out_csv, row)
            if on_record is not None:
                on_record(row)
    return experiment_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the initial generation benchmark.")
    parser.add_argument("--config", default="configs/experiments/baseline_64.yaml")
    parser.add_argument("--out", default="results/csv/experiments.csv")
    args = parser.parse_args()
    run(args.config, args.out)


if __name__ == "__main__":
    main()
