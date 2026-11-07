"""Run one reproducible point-cloud surface-voxelization pass from the command line.

The resulting surface grid is saved as a surface-specific NPZ archive, keeping
its meaning separate from a cave ``Volume3D`` where ``True`` means open space.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
from datetime import datetime, timezone

import scipy
from pathlib import Path
from time import perf_counter

import numpy as np

from cavegen.core.surface_filling import INTERIOR, classify_surface_by_flood_fill
from cavegen.core.volume import Volume3D
from cavegen.datastream.bounds import calculate_xyz_bounds
from cavegen.datastream.point_cloud import iter_point_cloud_xyz
from cavegen.datastream.progress import report_point_progress
from cavegen.datastream.reference_preprocessing import (
    load_xyz_bounds,
    voxelize_point_cloud_surface,
)
from cavegen.datastream.surface_io import save_surface_npz
from cavegen.datastream.voxel_io import save_volume_npz


def run(
    ply_path: str | Path,
    bounds_path: str | Path,
    volume_shape: tuple[int, int, int],
    batch_size: int,
    progress_every: int | None = None,
) -> np.ndarray:
    """Voxelize a point-cloud surface with persisted bounds and return its ZYX grid.

    When ``progress_every`` is set, print cumulative processed-vertex counts
    as the streamed coordinate batches cross each interval.
    """

    return voxelize_point_cloud_surface(
        ply_path,
        bounds_path,
        volume_shape,
        batch_size,
        progress_every=progress_every,
        progress_callback=lambda count: print(f"[Voxelization] Processed {count:,} points...", flush=True),
    )


def _parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line paths and resource parameters for one voxelization."""

    parser = argparse.ArgumentParser(
        description="Voxelize a PLY/XYZ/F32 reference surface incrementally and save it as NPZ."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", dest="source_path", help="Source PLY, XYZ or F32 file.")
    source.add_argument("--ply", dest="source_path", help="Legacy alias for --input.")
    parser.add_argument(
        "--output",
        required=True,
        help="Destination surface NPZ path, e.g. data/processed/references/elaphes_32.npz.",
    )
    parser.add_argument(
        "--interior-output",
        help="Optional NPZ for candidate cave air inferred by exterior flood fill (6 neighbors).",
    )
    parser.add_argument(
        "--bounds",
        default=None,
        help="Bounds JSON. If omitted, scan the source and save OUTPUT.bounds.json first.",
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
        help="Maximum points processed per batch; defaults to 65536.",
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
    return parser.parse_args(argv)


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
        "source_path": str(ply_path),
        "source_format": Path(ply_path).suffix.lower().lstrip("."),
        **({"source_ply": str(ply_path)} if Path(ply_path).suffix.lower() == ".ply" else {}),
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


def main(argv: list[str] | None = None) -> None:
    """Execute a point-cloud surface-voxelization pass requested through CLI arguments."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    args = _parse_arguments(arguments)
    if args.batch_size <= 0 or any(size <= 0 for size in args.shape):
        raise ValueError("batch-size and shape dimensions must be positive.")
    if args.progress_every < 0:
        raise ValueError("progress-every must be nonnegative (0 disables it).")
    def archive_path(path: str) -> Path:
        return Path(path if path.endswith(".npz") else path + ".npz").resolve()

    outputs = [archive_path(args.output)]
    if args.interior_output:
        outputs.append(archive_path(args.interior_output))
    if len(set(outputs)) != len(outputs):
        raise ValueError("Surface and interior outputs must use different paths.")
    if Path(args.source_path).resolve() in outputs:
        raise ValueError("Output paths must not overwrite the source cloud.")
    source_stat = Path(args.source_path).stat()
    started_at = datetime.now(timezone.utc).isoformat()
    volume_shape = tuple(args.shape)
    start = perf_counter()
    progress_every = args.progress_every or None
    bounds_path = args.bounds
    if bounds_path is None:
        print("Scanning source for global XYZ bounds...", flush=True)
        minimum, maximum = calculate_xyz_bounds(
            report_point_progress(
                iter_point_cloud_xyz(args.source_path, args.batch_size), progress_every,
                lambda count: print(f"[Bounds] Processed {count:,} points...", flush=True),
            )
        )
        bounds_path = Path(args.output).with_suffix(".bounds.json")
        bounds_path.parent.mkdir(parents=True, exist_ok=True)
        bounds_path.write_text(json.dumps({
            "source_path": str(args.source_path),
            "min_xyz": minimum.tolist(), "max_xyz": maximum.tolist(),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Saved bounds: {bounds_path}", flush=True)
    surface_voxels = run(
        args.source_path,
        bounds_path,
        volume_shape,
        args.batch_size,
        progress_every=progress_every,
    )
    metadata = _build_metadata(args.source_path, bounds_path, volume_shape)
    metadata["processing"] = {
        "batch_size": args.batch_size, "progress_every": args.progress_every,
        "bounds_mode": "provided" if args.bounds else "computed",
        "flood_fill_requested": bool(args.interior_output),
    }
    save_surface_npz(surface_voxels, args.output, metadata)
    _print_summary(surface_voxels, perf_counter() - start, args.report_slices)
    print(f"Saved surface archive: {args.output}")
    if args.interior_output:
        print("[Flood fill] Classifying enclosed regions (6 neighbors)...", flush=True)
        classification = classify_surface_by_flood_fill(surface_voxels)
        interior = classification == INTERIOR
        metadata = dict(metadata)
        metadata.update({
            "kind": "candidate_cave_void",
            "semantic": "true_means_enclosed_unobserved_voxel",
            "validation_status": "candidate_requires_geometric_validation",
            "surface_path": str(args.output),
            "interior_inference": {
                "method": "exterior_flood_fill",
                "connectivity": 6,
                "outside_grid": "exterior",
                "observed_surface_included_in_void": False,
                "automatic_closure": False,
            },
        })
        save_volume_npz(Volume3D(interior, metadata), args.interior_output)
        print(f"Enclosed interior voxels (candidate air): {int(interior.sum())}")
        if not interior.any():
            print("No enclosed interior found: check open entrances, gaps and resolution.")
        print(f"Saved candidate interior archive: {args.interior_output}")
    receipt_path = Path(args.output).with_suffix(".run.json")
    final_stat = Path(args.source_path).stat()
    if (source_stat.st_size, source_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
        raise ValueError("Source cloud changed during processing; discard this run's outputs.")
    repository = Path(__file__).resolve().parents[3]
    revision, dirty = None, None
    try:
        revision = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    effective_arguments = [
        "--input", str(Path(args.source_path).resolve()), "--bounds", str(Path(bounds_path).resolve()),
        "--shape", *map(str, volume_shape), "--batch-size", str(args.batch_size),
        "--progress-every", str(args.progress_every), "--output", str(outputs[0]),
    ]
    if args.interior_output:
        effective_arguments += ["--interior-output", str(outputs[1])]
    if args.report_slices:
        effective_arguments += ["--report-slices"]
    command = [sys.executable, "-u", "-m",
               "cavegen.datastream.run_reference_voxelization", *effective_arguments]
    receipt = {
        "schema": "reference-voxelization-run-v1", "status": "completed",
        "started_at_utc": started_at, "elapsed_seconds": perf_counter() - start,
        "working_directory": str(Path.cwd()), "command_argv": command,
        "requested_argv": arguments,
        "command_shell": shlex.join(command),
        "source": {"path": str(Path(args.source_path).resolve()),
                   "size_bytes": source_stat.st_size, "mtime_ns": source_stat.st_mtime_ns,
                   "identity_kind": "path_size_mtime_not_content_hash"},
        "surface_output": str(outputs[0]),
        "interior_output": str(outputs[1]) if len(outputs) > 1 else None,
        "bounds_path": str(Path(bounds_path).resolve()),
        "bounds_sha256": hashlib.sha256(Path(bounds_path).read_bytes()).hexdigest(),
        "surface_metadata": _build_metadata(args.source_path, bounds_path, volume_shape),
        "processing": metadata["processing"],
        "software": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__, "git_commit": revision, "git_dirty": dirty},
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Saved reproduction record: {receipt_path}", flush=True)


if __name__ == "__main__":
    main()
