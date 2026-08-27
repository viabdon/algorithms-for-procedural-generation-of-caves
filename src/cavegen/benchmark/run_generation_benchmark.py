from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from cavegen.core.config import load_yaml
from cavegen.generators.cellular_automata import generate_cellular_automata
from cavegen.generators.random_walk import generate_random_walk
from cavegen.datastream.voxel_io import save_volume_npz
from cavegen.metrics.connectivity import largest_component_ratio
from cavegen.metrics.morphology import distance_transform_stats, open_ratio
from cavegen.profiling.system_monitor import SystemMonitor
from cavegen.profiling.timer import elapsed_timer


def _shape(config: dict[str, Any]) -> tuple[int, int, int]:
    value = config.get("shape", [32, 32, 32])
    if len(value) != 3:
        raise ValueError("shape must have three dimensions: [depth, height, width].")
    return tuple(int(v) for v in value)


def run(config_path: str | Path, out_csv: str | Path) -> None:
    config = load_yaml(config_path)
    shape = _shape(config)
    seeds = [int(seed) for seed in config.get("seeds", [0])]
    algorithms = config.get("algorithms", {})
    volumes_dir = Path(config.get("outputs", {}).get("volumes_dir", "results/volumes"))
    volumes_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []

    for seed in seeds:
        if "random_walk" in algorithms:
            params = algorithms["random_walk"] or {}
            monitor = SystemMonitor()
            monitor.start()
            with elapsed_timer() as timer:
                volume = generate_random_walk(shape=shape, seed=seed, **params)
            monitor.stop()
            path = volumes_dir / f"random_walk_seed_{seed}.npz"
            save_volume_npz(volume, path)
            rows.append(_row("random_walk", seed, volume, timer, monitor, path))

        if "cellular_automata" in algorithms:
            params = algorithms["cellular_automata"] or {}
            monitor = SystemMonitor()
            monitor.start()
            with elapsed_timer() as timer:
                volume = generate_cellular_automata(shape=shape, seed=seed, **params)
            monitor.stop()
            path = volumes_dir / f"cellular_automata_seed_{seed}.npz"
            save_volume_npz(volume, path)
            rows.append(_row("cellular_automata", seed, volume, timer, monitor, path))

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with out_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(algorithm: str, seed: int, volume, timer, monitor: SystemMonitor, path: Path) -> dict[str, Any]:
    row = {
        "algorithm": algorithm,
        "seed": seed,
        "shape": "x".join(str(v) for v in volume.shape),
        "elapsed_seconds": timer["elapsed_seconds"],
        "open_ratio": open_ratio(volume.data),
        "largest_component_ratio": largest_component_ratio(volume.data),
        "open_voxels": volume.open_voxels,
        "peak_rss_bytes": monitor.peak_rss_bytes,
        "volume_path": str(path),
    }
    row.update(distance_transform_stats(volume.data))
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the initial generation benchmark.")
    parser.add_argument("--config", default="configs/experiments/baseline_32.yaml")
    parser.add_argument("--out", default="results/csv/baseline_32.csv")
    args = parser.parse_args()
    run(args.config, args.out)


if __name__ == "__main__":
    main()
