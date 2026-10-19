"""Draw YZ sections of measured points and diagnostic thickening meshes."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh


def plot_sections(
    sample_path: str | Path,
    meshes: list[tuple[str, str | Path]],
    output_path: str | Path,
    *,
    x_positions: tuple[float, ...] = (20, 29.8, 32.9),
    slice_thickness: float = 0.5,
) -> Path:
    """Plot section curves against measured points in matched YZ axes."""
    if not meshes or not x_positions:
        raise ValueError("at least one mesh and X position are required")
    if not np.isfinite(slice_thickness) or slice_thickness <= 0:
        raise ValueError("slice_thickness must be finite and positive")
    with np.load(sample_path, allow_pickle=False) as archive:
        points = archive["points_xyz"]
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("sample points_xyz must have shape (N, 3)")
    loaded = [(name, trimesh.load_mesh(path, process=False)) for name, path in meshes]
    figure, axes = plt.subplots(
        len(x_positions), len(loaded), figsize=(4.5 * len(loaded), 3.5 * len(x_positions)),
        squeeze=False, sharex=True, sharey=True,
    )
    y_limits = (float(points[:, 1].min()) - 0.5, float(points[:, 1].max()) + 0.5)
    z_limits = (float(points[:, 2].min()) - 0.5, float(points[:, 2].max()) + 0.5)
    for row, x in enumerate(x_positions):
        observed = points[np.abs(points[:, 0] - x) <= slice_thickness / 2]
        for column, (name, mesh) in enumerate(loaded):
            axis = axes[row, column]
            axis.scatter(observed[:, 1], observed[:, 2], s=2, c="#555555", alpha=0.35,
                         rasterized=True, label="pontos medidos")
            section = mesh.section(plane_origin=(x, 0, 0), plane_normal=(1, 0, 0))
            if section is not None:
                for curve in section.discrete:
                    axis.plot(curve[:, 1], curve[:, 2], color="#0b77b7", linewidth=0.8)
            axis.set_title(f"{name} · X={x:g}")
            axis.set_xlim(*y_limits)
            axis.set_ylim(*z_limits)
            axis.set_aspect("equal", adjustable="box")
            axis.set_xlabel("Y (unidades XYZ)")
            axis.set_ylabel("Z (unidades XYZ)")
            axis.grid(alpha=0.2)
    figure.suptitle("Elaphes: cortes das malhas diagnósticas e pontos medidos")
    figure.tight_layout()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--mesh", action="append", required=True, metavar="NOME=OBJ")
    parser.add_argument("--output", required=True)
    parser.add_argument("--x", nargs="+", type=float, default=[20, 29.8, 32.9])
    parser.add_argument("--slice-thickness", type=float, default=0.5)
    args = parser.parse_args()
    meshes = []
    for item in args.mesh:
        name, separator, mesh_path = item.partition("=")
        if not separator or not name or not mesh_path:
            parser.error("--mesh must use NOME=OBJ")
        meshes.append((name, mesh_path))
    print(plot_sections(args.sample, meshes, args.output,
                        x_positions=tuple(args.x), slice_thickness=args.slice_thickness))


if __name__ == "__main__":
    main()
