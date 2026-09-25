from __future__ import annotations

import argparse
import csv
from pathlib import Path
from time import perf_counter
from typing import Any

from cavegen.core.config import load_yaml
from cavegen.generators.cellular_automata import generate_cellular_automata
from cavegen.generators.random_walk import generate_random_walk
from cavegen.io.voxel_io import save_volume_npz
from cavegen.metrics.connectivity import largest_component_ratio
from cavegen.metrics.morphology import distance_transform_stats, open_ratio
from cavegen.profiling.resource_tracker import ResourceSampler, resumo_da_execucao


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
            volume, recursos = _medir(
                "random_walk", f"seed{seed}",
                lambda: generate_random_walk(shape=shape, seed=seed, **params),
            )
            path = volumes_dir / f"random_walk_seed_{seed}.npz"
            save_volume_npz(volume, path)
            rows.append(_row("random_walk", seed, volume, recursos, path))

        if "cellular_automata" in algorithms:
            params = algorithms["cellular_automata"] or {}
            volume, recursos = _medir(
                "cellular_automata", f"seed{seed}",
                lambda: generate_cellular_automata(shape=shape, seed=seed, **params),
            )
            path = volumes_dir / f"cellular_automata_seed_{seed}.npz"
            save_volume_npz(volume, path)
            rows.append(_row("cellular_automata", seed, volume, recursos, path))

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with out_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _medir(algorithm: str, label: str, executar) -> tuple[Any, dict[str, Any]]:
    """Roda o gerador amostrando recursos e devolve (volume, resumo dos recursos).

    Usa o mesmo amostrador e a mesma agregacao do decorator track_resources, para
    que uma linha desta planilha e uma linha de results/profiling signifiquem a
    mesma coisa. Comparar algoritmos exige a mesma regua nos dois lados.
    """
    with ResourceSampler() as amostrador:
        inicio = perf_counter()
        volume = executar()
        duracao = perf_counter() - inicio

    resumo = resumo_da_execucao(
        algorithm=algorithm,
        label=label,
        status="sucesso",
        error="",
        duration_seconds=duracao,
        samples=amostrador.samples,
    )
    return volume, resumo


def _row(algorithm: str, seed: int, volume, recursos: dict[str, Any], path: Path) -> dict[str, Any]:
    row = {
        "algorithm": algorithm,
        "seed": seed,
        "shape": "x".join(str(v) for v in volume.shape),
        "open_ratio": open_ratio(volume.data),
        "largest_component_ratio": largest_component_ratio(volume.data),
        "open_voxels": volume.open_voxels,
        "volume_path": str(path),
    }
    # Metricas de recurso ja agregadas, com os mesmos nomes de coluna do CSV
    # cumulativo; algorithm e label sairiam repetidos e por isso ficam de fora.
    row.update({chave: valor for chave, valor in recursos.items()
                if chave not in ("algorithm", "label", "status", "error")})
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
