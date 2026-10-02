"""Bounded spatial sampling and a first Screened Poisson mesh candidate.

The PLY reader streams XYZ coordinates; reconstruction only receives one point
per spatial bin. No 32³ surface occupancy grid is involved in this path.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from time import perf_counter

import numpy as np

from cavegen.datastream.ply import iter_ply_xyz, read_ply_header
from cavegen.datastream.reference_preprocessing import load_xyz_bounds


def spatial_bin_shape(min_xyz: np.ndarray, max_xyz: np.ndarray, max_points: int) -> tuple[int, int, int]:
    """Choose XYZ bin counts with a product no larger than ``max_points``."""
    if isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 1:
        raise ValueError("max_points must be a positive integer")
    extent = np.asarray(max_xyz, dtype=np.float64) - np.asarray(min_xyz, dtype=np.float64)
    if extent.shape != (3,) or not np.isfinite(extent).all() or np.any(extent < 0):
        raise ValueError("min_xyz and max_xyz must be finite, ordered XYZ bounds")
    if not np.any(extent):
        return (1, 1, 1)

    # Binary search for the finest shared physical bin width within the cap.
    lo, hi = 0.0, float(extent.max())
    for _ in range(64):
        width = (lo + hi) / 2
        if width == 0:
            break
        shape = np.maximum(1, np.ceil(extent / width).astype(np.int64))
        if int(np.prod(shape)) <= max_points:
            hi = width
        else:
            lo = width
    shape = np.maximum(1, np.ceil(extent / hi).astype(np.int64))
    return tuple(int(value) for value in shape)


def sample_spatial_bins(
    batches: Iterable[np.ndarray],
    min_xyz: np.ndarray,
    max_xyz: np.ndarray,
    max_points: int,
    *,
    sampling_rule: str = "first",
    return_stats: bool = False,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple:
    """Represent each occupied XYZ bin by its first point or centroid.

    Returns sampled coordinates, XYZ bin shape, and number of source points.
    With ``return_stats``, also returns per-bin counts and XYZ standard
    deviations. These are available for ``centroid`` and ``None`` for ``first``.
    """
    if sampling_rule not in {"first", "centroid"}:
        raise ValueError("sampling_rule must be 'first' or 'centroid'")
    shape = spatial_bin_shape(min_xyz, max_xyz, max_points)
    count = int(np.prod(shape))
    if sampling_rule == "first":
        samples = np.empty((count, 3), dtype=np.float32)
        occupied = np.zeros(count, dtype=bool)
    else:
        bin_counts = np.zeros(count, dtype=np.int64)
        sums = np.zeros((count, 3), dtype=np.float64)
        sums_squared = np.zeros((count, 3), dtype=np.float64)
    lower = np.asarray(min_xyz, dtype=np.float64)
    extent = np.asarray(max_xyz, dtype=np.float64) - lower
    safe_extent = np.where(extent > 0, extent, 1)
    shape_array = np.asarray(shape, dtype=np.int64)
    seen = 0
    next_report = 1_000_000

    for batch in batches:
        if not isinstance(batch, np.ndarray) or batch.ndim != 2 or batch.shape[1] != 3:
            raise ValueError("each XYZ batch must have shape (N, 3)")
        if batch.dtype != np.float32 or not np.isfinite(batch).all():
            raise ValueError("each XYZ batch must contain finite float32 coordinates")
        if np.any(batch < min_xyz) or np.any(batch > max_xyz):
            raise ValueError("XYZ point lies outside the persisted bounds")
        seen += len(batch)
        if progress_callback is not None and seen >= next_report:
            progress_callback(seen)
            next_report = (seen // 1_000_000 + 1) * 1_000_000
        if not len(batch):
            continue
        indices = np.floor(
            (batch.astype(np.float64) - lower) / safe_extent * shape_array
        ).astype(np.int64)
        np.clip(indices, 0, shape_array - 1, out=indices)
        flat = np.ravel_multi_index(indices.T, shape)
        if sampling_rule == "first":
            unique_flat, first = np.unique(flat, return_index=True)
            new = ~occupied[unique_flat]
            samples[unique_flat[new]] = batch[first[new]]
            occupied[unique_flat[new]] = True
        else:
            unique_flat, inverse = np.unique(flat, return_inverse=True)
            bin_counts[unique_flat] += np.bincount(inverse, minlength=len(unique_flat))
            for axis in range(3):
                values = batch[:, axis].astype(np.float64)
                sums[unique_flat, axis] += np.bincount(
                    inverse, weights=values, minlength=len(unique_flat)
                )
                sums_squared[unique_flat, axis] += np.bincount(
                    inverse, weights=values * values, minlength=len(unique_flat)
                )

    if not seen:
        raise ValueError("the point cloud has no vertices")
    if sampling_rule == "first":
        result = (samples[occupied], shape, seen)
        return (*result, None, None) if return_stats else result
    occupied = bin_counts > 0
    counts = bin_counts[occupied]
    means = sums[occupied] / counts[:, None]
    variances = np.maximum(sums_squared[occupied] / counts[:, None] - means**2, 0)
    result = (means.astype(np.float32), shape, seen)
    return (*result, counts, np.sqrt(variances).astype(np.float32)) if return_stats else result


def reconstruct_poisson(
    points_xyz: np.ndarray,
    *,
    depth: int = 8,
    normal_neighbors: int = 30,
    orientation_neighbors: int = 30,
    interior_seed_xyz: tuple[float, float, float] | None = None,
    threads: int = 1,
):
    """Return Open3D's Screened Poisson mesh and vertex density estimates.

    A candidate mesh still needs geometric and semantic review. A known point
    inside the cave can resolve the global normal sign; otherwise it is free.
    """
    if points_xyz.ndim != 2 or points_xyz.shape[1] != 3 or len(points_xyz) < 3:
        raise ValueError("at least three XYZ points are required")
    if not np.isfinite(points_xyz).all():
        raise ValueError("points_xyz must be finite")
    if depth < 2 or normal_neighbors < 3 or orientation_neighbors < 3:
        raise ValueError("depth and normal-neighbor counts are too small")
    if threads < 1:
        raise ValueError("threads must be positive")
    try:
        import open3d as o3d
    except ImportError as error:
        raise RuntimeError("Install the reconstruction extra: uv pip install -e '.[reconstruction]'") from error

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points_xyz.astype(np.float64))
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=normal_neighbors))
    pcd.orient_normals_consistent_tangent_plane(orientation_neighbors)
    if interior_seed_xyz is not None:
        seed = np.asarray(interior_seed_xyz, dtype=np.float64)
        if seed.shape != (3,) or not np.isfinite(seed).all():
            raise ValueError("interior_seed_xyz must be three finite XYZ coordinates")
        normals = np.asarray(pcd.normals)
        vectors = np.asarray(pcd.points) - seed
        if np.median(np.einsum("ij,ij->i", normals, vectors)) < 0:
            pcd.normals = o3d.utility.Vector3dVector(-normals)
    return o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth, n_threads=threads
    )


def run(
    ply_path: str | Path,
    bounds_path: str | Path,
    output_path: str | Path | None,
    *,
    max_points: int = 100_000,
    batch_size: int = 65_536,
    depth: int = 8,
    normal_neighbors: int = 30,
    orientation_neighbors: int = 30,
    interior_seed_xyz: tuple[float, float, float] | None = None,
    threads: int = 1,
    sample_path: str | Path | None = None,
    sample_only: bool = False,
    sampling_rule: str = "first",
) -> dict[str, object]:
    """Stream a PLY or reuse a sample, then optionally reconstruct a mesh."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if sampling_rule not in {"first", "centroid"}:
        raise ValueError("sampling_rule must be 'first' or 'centroid'")
    if not sample_only:
        if depth < 2 or normal_neighbors < 3 or orientation_neighbors < 3 or threads < 1:
            raise ValueError("invalid Poisson depth, neighbors, or threads")
        if interior_seed_xyz is not None:
            seed = np.asarray(interior_seed_xyz, dtype=np.float64)
            if seed.shape != (3,) or not np.isfinite(seed).all():
                raise ValueError("interior_seed_xyz must be three finite XYZ coordinates")
    if sample_only and sample_path is None:
        raise ValueError("sample_only requires sample_path")
    if not sample_only and output_path is None:
        raise ValueError("output_path is required for reconstruction")
    ply_path, bounds_path = Path(ply_path), Path(bounds_path)
    header = read_ply_header(ply_path)
    with bounds_path.open(encoding="utf-8") as file:
        bounds_metadata = json.load(file)
    if header.vertex_count != bounds_metadata.get("source", {}).get("vertex_count"):
        raise ValueError("PLY vertex count differs from the persisted bounds metadata")
    if ply_path.stat().st_size != bounds_metadata.get("source", {}).get("size_bytes"):
        raise ValueError("PLY byte size differs from the persisted bounds metadata")
    min_xyz, max_xyz = load_xyz_bounds(bounds_path)
    if not sample_only and sample_path is None:
        _require_open3d()  # Fail before spending minutes streaming a large ASCII PLY.
    start = perf_counter()
    if sample_path is not None and Path(sample_path).exists() and not sample_only:
        with np.load(sample_path, allow_pickle=False) as archive:
            points = archive["points_xyz"]
            bins_xyz = tuple(int(x) for x in archive["bins_xyz"])
            source_count = int(archive["source_count"])
            source_hash = str(archive["source_sha256"])
            cached_bounds = archive["bounds_xyz"]
            cached_max_points = int(archive["max_points"]) if "max_points" in archive else None
            cached_rule = str(archive["sampling_rule"])
            bin_counts = archive["bin_counts"] if "bin_counts" in archive else None
            bin_std_xyz = archive["bin_std_xyz"] if "bin_std_xyz" in archive else None
        if source_hash != bounds_metadata["source"].get("sha256"):
            raise ValueError("sample cache belongs to a different source PLY")
        if source_count != header.vertex_count or (
            cached_max_points is not None and cached_max_points != max_points
        ) or bins_xyz != spatial_bin_shape(min_xyz, max_xyz, max_points):
            raise ValueError("sample cache does not match source count or max_points")
        if not np.array_equal(cached_bounds, np.stack((min_xyz, max_xyz))):
            raise ValueError("sample cache has different XYZ bounds")
        if cached_rule != sampling_rule and not (
            sampling_rule == "first" and cached_rule.startswith("first source point")
        ):
            raise ValueError("sample cache uses a different sampling rule")
        _require_open3d()
    else:
        points, bins_xyz, source_count, bin_counts, bin_std_xyz = sample_spatial_bins(
            iter_ply_xyz(ply_path, batch_size), min_xyz, max_xyz, max_points,
            sampling_rule=sampling_rule,
            return_stats=True,
            progress_callback=lambda count: print(f"Read {count:,} source points...", flush=True),
        )
        if source_count != header.vertex_count:
            raise ValueError("PLY payload vertex count differs from its header")
        if sample_path is not None:
            sample_path = Path(sample_path)
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            sample_data = dict(
                points_xyz=points,
                bins_xyz=np.asarray(bins_xyz, dtype=np.int64),
                source_count=source_count,
                source_sha256=bounds_metadata["source"].get("sha256"),
                bounds_xyz=np.stack((min_xyz, max_xyz)),
                max_points=max_points,
                sampling_rule=sampling_rule,
                uses_random_sampling=False,
            )
            if bin_counts is not None:
                sample_data["bin_counts"] = bin_counts
                sample_data["bin_std_xyz"] = bin_std_xyz
                sample_data["bin_variance_xyz"] = np.square(bin_std_xyz)
            np.savez_compressed(sample_path, **sample_data)
    sample_seconds = perf_counter() - start
    spread = np.linalg.norm(bin_std_xyz, axis=1) if bin_std_xyz is not None else None
    bin_stats = {
        "points_per_bin_max": int(bin_counts.max()) if bin_counts is not None else None,
        "points_per_bin_median": float(np.median(bin_counts)) if bin_counts is not None else None,
        "spread_p95_xyz_units": float(np.percentile(spread, 95)) if spread is not None else None,
        "spread_max_xyz_units": float(spread.max()) if spread is not None else None,
    }
    if sample_only:
        return {
            "status": "sample_ready",
            "sample_path": str(sample_path),
            "source_sha256_from_bounds_json": bounds_metadata["source"].get("sha256"),
            "source_vertices": source_count,
            "sampled_vertices": int(len(points)),
            "spatial_bins_xyz": list(bins_xyz),
            "max_points": max_points,
            "sampling_rule": sampling_rule,
            "random_seed": None,
            "uses_random_sampling": False,
            "sampling_seconds": sample_seconds,
            **bin_stats,
        }
    assert output_path is not None
    output_path = Path(output_path)
    mesh, densities = reconstruct_poisson(
        points,
        depth=depth,
        normal_neighbors=normal_neighbors,
        orientation_neighbors=orientation_neighbors,
        interior_seed_xyz=interior_seed_xyz,
        threads=threads,
    )
    o3d = _require_open3d()
    if len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
        raise ValueError("Poisson returned an empty mesh")
    triangles = np.asarray(mesh.triangles)
    edges = np.sort(
        np.concatenate((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]])),
        axis=1,
    )
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)
    triangle_clusters, _, _ = mesh.cluster_connected_triangles()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not o3d.io.write_triangle_mesh(str(output_path), mesh):
        raise OSError(f"could not write mesh: {output_path}")
    density_array = np.asarray(densities)
    metadata: dict[str, object] = {
        "status": "candidate_requires_validation",
        "method": "Open3D Screened Poisson",
        "source_ply": str(ply_path),
        "source_sha256_from_bounds_json": bounds_metadata["source"].get("sha256"),
        "bounds_json": str(bounds_path),
        "coordinates": "XYZ source coordinates; original scale, unit unverified",
        "source_bounds_xyz": [min_xyz.tolist(), max_xyz.tolist()],
        "mesh_bounds_xyz": [mesh.get_min_bound().tolist(), mesh.get_max_bound().tolist()],
        "source_vertices": source_count,
        "sampled_vertices": int(len(points)),
        "spatial_bins_xyz": list(bins_xyz),
        "max_points": max_points,
        "sample_path": str(sample_path) if sample_path is not None else None,
        "sampling_rule": sampling_rule,
        "random_seed": None,
        "uses_random_sampling": False,
        "sampling_seconds": sample_seconds,
        **bin_stats,
        "depth": depth,
        "poisson_threads": threads,
        "open3d_version": o3d.__version__,
        "normal_neighbors": normal_neighbors,
        "orientation_neighbors": orientation_neighbors,
        "interior_seed_xyz": interior_seed_xyz,
        "mesh_vertices": len(mesh.vertices),
        "mesh_triangles": len(mesh.triangles),
        "mesh_watertight": bool(mesh.is_watertight()),
        "mesh_boundary_edges": int(np.count_nonzero(edge_counts == 1)),
        "mesh_nonmanifold_edges": int(np.count_nonzero(edge_counts > 2)),
        "mesh_components": int(np.max(triangle_clusters)) + 1,
        "density_min": float(density_array.min()),
        "density_max": float(density_array.max()),
        "elapsed_seconds": perf_counter() - start,
    }
    output_path.with_suffix(output_path.suffix + ".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def _require_open3d():
    try:
        import open3d as o3d
    except ImportError as error:
        raise RuntimeError(
            "Open3D is absent from this Python environment; install the reconstruction extra"
        ) from error
    return o3d


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Screened Poisson mesh candidate from a PLY.")
    parser.add_argument("--ply", required=True)
    parser.add_argument("--bounds", default="data/params/elaphes_xyz_bounds.json")
    parser.add_argument("--output", help="Candidate mesh path, e.g. results/meshes/elaphes.obj")
    parser.add_argument("--sample-path", help="Reusable sampled XYZ archive (.npz).")
    parser.add_argument("--sample-only", action="store_true", help="Prepare the sample without Open3D.")
    parser.add_argument("--sampling-rule", choices=("first", "centroid"), default="first")
    parser.add_argument("--max-points", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=65_536)
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--normal-neighbors", type=int, default=30)
    parser.add_argument("--orientation-neighbors", type=int, default=30)
    parser.add_argument("--threads", type=int, default=1, help="Poisson CPU threads; defaults to 1.")
    parser.add_argument("--interior-seed-xyz", type=float, nargs=3, metavar=("X", "Y", "Z"))
    args = parser.parse_args()
    metadata = run(
        args.ply, args.bounds, args.output,
        max_points=args.max_points,
        batch_size=args.batch_size,
        depth=args.depth,
        normal_neighbors=args.normal_neighbors,
        orientation_neighbors=args.orientation_neighbors,
        interior_seed_xyz=tuple(args.interior_seed_xyz) if args.interior_seed_xyz else None,
        threads=args.threads,
        sample_path=args.sample_path,
        sample_only=args.sample_only,
        sampling_rule=args.sampling_rule,
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
