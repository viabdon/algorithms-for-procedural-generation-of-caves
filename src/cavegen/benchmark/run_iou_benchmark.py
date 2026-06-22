from __future__ import annotations

import argparse
import csv
from pathlib import Path

from cavegen.io.voxel_io import load_volume_npz
from cavegen.metrics.iou import voxel_iou


def run(reference: str | Path, generated_dir: str | Path, out_csv: str | Path) -> None:
    reference_volume = load_volume_npz(reference)
    generated_paths = sorted(Path(generated_dir).glob("*.npz"))
    rows = []
    for path in generated_paths:
        generated = load_volume_npz(path)
        rows.append({"generated_path": str(path), "reference_path": str(reference), "iou": voxel_iou(reference_volume.data, generated.data)})

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["generated_path", "reference_path", "iou"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute IoU against a reference volume.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--generated-dir", default="results/volumes")
    parser.add_argument("--out", default="results/csv/iou.csv")
    args = parser.parse_args()
    run(args.reference, args.generated_dir, args.out)


if __name__ == "__main__":
    main()
