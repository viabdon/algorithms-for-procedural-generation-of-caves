"""Visual inspection of observed surfaces versus flood-fill candidate interiors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from cavegen.training.reference_data import read_reference


def plot_audit(root: str | Path, audit: dict, output: str | Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    records = [r for r in audit["records"] if r["candidate"] or r["verified_air"]]
    figure, axes = plt.subplots(len(records), 3, figsize=(12, 3 * len(records)), squeeze=False)
    colors = ListedColormap(["#f2f5fa", "#2580b5", "#eb6a20"])
    for row, record in enumerate(records):
        air, _, _ = read_reference(Path(root) / record["path"])
        surface, _, _ = read_reference((Path(root) / record["path"]).parent / "surface.npz")
        # Each projection displays every occupied voxel along the suppressed axis.
        for col, axis in enumerate((0, 1, 2)):
            projection = surface.any(axis=axis).astype(np.uint8)
            projection[air.any(axis=axis)] = 2
            axes[row, col].imshow(projection, origin="lower", cmap=colors, vmin=0, vmax=2,
                                  interpolation="nearest")
            axes[row, col].set_title(f"{record['group']} | projection {'YX' if axis == 0 else 'ZX' if axis == 1 else 'ZY'}")
            axes[row, col].set_xlabel(f"air={int(air.sum())}; surface={int(surface.sum())}")
    figure.suptitle("64³ reference audit | blue: observed surface | orange: inferred air", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150)
    plt.close(figure)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/processed/references")
    parser.add_argument("--audit", default="docs/auditoria/gan/reference_audit.json")
    parser.add_argument("--output", default="docs/auditoria/gan/projections.png")
    args = parser.parse_args(argv)
    plot_audit(args.root, json.loads(Path(args.audit).read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    main()
