"""Run one reproducible PLY surface-voxelization pass from the command line.

The resulting surface grid is saved as a surface-specific NPZ archive, keeping
its meaning separate from a cave ``Volume3D`` where ``True`` means open space.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np

from cavegen.datastream.reference_preprocessing import load_xyz_bounds, voxelize_ply_surface
from cavegen.datastream.surface_io import save_surface_npz


def run(
    ply_path: str | Path,
    bounds_path: str | Path,
    volume_shape: tuple[int, int, int],
    batch_size: int,
    progress_every: int | None = None,
) -> np.ndarray:
    """Voxelize a PLY surface with persisted bounds and return its ZYX grid.

    When ``progress_every`` is set, print cumulative processed-vertex counts
    as the streamed PLY batches cross each interval.
    """

    return voxelize_ply_surface(
        ply_path,
        bounds_path,
        volume_shape,
        batch_size,
        progress_every=progress_every,
        progress_callback=lambda count: print(f"Processed {count:,} vertices..."),
    )


def _parse_arguments() -> argparse.Namespace:
    """Parse command-line paths and resource parameters for one voxelization."""

    parser = argparse.ArgumentParser(
        description="Voxelize a PLY reference surface incrementally and save it as NPZ."
    )
    parser.add_argument("--ply", required=True, help="Path to the source PLY file.")
    parser.add_argument(
        "--output",
        required=True,
        help="Destination surface NPZ path, e.g. data/processed/references/elaphes_32.npz.",
    )
    parser.add_argument(
        "--bounds",
        default="data/params/elaphes_xyz_bounds.json",
        help="Path to the JSON file containing min_xyz and max_xyz.",
    )
    parser.add_argument(
        "--shape",
        type=int,
        nargs=3,
        metavar=("DEPTH", "HEIGHT", "WIDTH"),
        default=(32, 32, 32),
        help="Target ZYX grid shape; defaults to 32 32 32.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=65_536,
        help="Maximum PLY vertices processed per batch; defaults to 65536.",
    )
    parser.add_argument(
        "--report-slices",
        action="store_true",
        help="Print the number of marked surface voxels in every Z slice.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1_000_000,
        metavar="VERTICES",
        help="Print progress every VERTICES vertices; use 0 to disable (default: 1000000).",
    )
    return parser.parse_args()


def _print_summary(surface_voxels: np.ndarray, elapsed_seconds: float, report_slices: bool) -> None:
    """Print occupancy statistics for a completed surface-voxelization pass."""

    occupied = int(surface_voxels.sum())
    total = surface_voxels.size
    print(f"Elapsed time: {elapsed_seconds:.1f} s")
    print(f"Surface voxels: {occupied} / {total} ({occupied / total:.2%})")

    if report_slices:
        for z_index, voxel_count in enumerate(surface_voxels.sum(axis=(1, 2))):
            print(f"z={z_index:03d}: {int(voxel_count)} surface voxels")


def _build_metadata(
    ply_path: str | Path,
    bounds_path: str | Path,
    volume_shape: tuple[int, int, int],
) -> dict[str, object]:
    """Describe the source and normalization convention of one surface grid."""

    min_xyz, max_xyz = load_xyz_bounds(bounds_path)
    return {
        "kind": "surface_voxels",
        "semantic": "true_means_observed_surface",
        "source_ply": str(ply_path),
        "bounds_path": str(bounds_path),
        "min_xyz": min_xyz.tolist(),
        "max_xyz": max_xyz.tolist(),
        "volume_shape_zyx": list(volume_shape),
        "normalization": {
            "source_coordinate_order": "XYZ",
            "grid_index_order": "ZYX",
            "shared_scale_preserves_proportions": True,
            "symmetric_padding": True,
            "degenerate_axes": "placed_at_grid_center",
        },
    }


def main() -> None:
    """Execute a PLY surface-voxelization pass requested through CLI arguments."""

    args = _parse_arguments()
    volume_shape = tuple(args.shape)
    start = perf_counter()
    progress_every = args.progress_every or None
    surface_voxels = run(
        args.ply,
        args.bounds,
        volume_shape,
        args.batch_size,
        progress_every=progress_every,
    )
    save_surface_npz(
        surface_voxels,
        args.output,
        _build_metadata(args.ply, args.bounds, volume_shape),
    )
    _print_summary(surface_voxels, perf_counter() - start, args.report_slices)
    print(f"Saved surface archive: {args.output}")


if __name__ == "__main__":
    main()
