from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def summarize(input_csv: str | Path, output_csv: str | Path) -> None:
    df = pd.read_csv(input_csv)
    # Nomes de recurso vindos de profiling.resource_tracker. A filtragem abaixo
    # ignora coluna ausente em silencio, entao um nome errado aqui nao quebra o
    # resumo: ele apenas sai sem a metrica, que e pior. Manter em sincronia.
    numeric = [
        "duration_seconds",
        "cpu_percent_mean",
        "cpu_percent_peak",
        "rss_mb_mean",
        "rss_mb_peak",
        "gpu_percent_mean",
        "gpu_percent_peak",
        "gpu_memory_mb_peak",
        "open_ratio",
        "largest_component_ratio",
        "open_voxels",
        "dt_mean",
        "dt_median",
        "dt_max",
    ]
    numeric = [column for column in numeric if column in df.columns]
    summary = df.groupby("algorithm")[numeric].agg(["mean", "std", "median", "min", "max"])
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_csv)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize benchmark CSV results.")
    parser.add_argument("--input", default="results/csv/baseline_32.csv")
    parser.add_argument("--output", default="results/csv/baseline_32_summary.csv")
    args = parser.parse_args()
    summarize(args.input, args.output)


if __name__ == "__main__":
    main()
