"""Diagnostic comparison of raw-point Poisson and voxel-thickened input.

The thickened input is an inferred boundary of dilated point occupancy. It is
not an observed cave surface or a validated interior/exterior classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes

from cavegen.datastream.ply import iter_ply_xyz, read_ply_header
from cavegen.meshing.poisson import reconstruct_poisson, sample_spatial_bins


def sample_measured_roi(
    ply_path: str | Path,
    sample_path: str | Path,
    *,
    roi_min_xyz: tuple[float, float, float] = (12, -3.25, -6.5),
    roi_max_xyz: tuple[float, float, float] = (35, 8, 2),
    max_bins: int = 2_000_000,
    batch_size: int = 100_000,
) -> dict[str, object]:
    """Stream the source PLY and retain one measured point per ROI bin."""
    source = Path(ply_path)
    output = Path(sample_path)
    if output.exists():
        raise FileExistsError(f"sample already exists: {output}")
    lower = np.asarray(roi_min_xyz, dtype=np.float32)
    upper = np.asarray(roi_max_xyz, dtype=np.float32)
    if lower.shape != (3,) or upper.shape != (3,) or not np.isfinite(lower).all() or not np.isfinite(upper).all() or np.any(lower >= upper):
        raise ValueError("ROI bounds must be finite ordered XYZ triples")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    header = read_ply_header(source)
    scanned = 0

    def roi_batches():
        nonlocal scanned
        for batch in iter_ply_xyz(source, batch_size):
            scanned += len(batch)
            if scanned // 10_000_000 != (scanned - len(batch)) // 10_000_000:
                print(f"Scanned {scanned:,} raw points", flush=True)
            within = np.all((batch >= lower) & (batch <= upper), axis=1)
            if np.any(within):
                yield batch[within]

    points, bins, roi_count = sample_spatial_bins(
        roi_batches(), lower, upper, max_bins, sampling_rule="first"
    )
    if scanned != header.vertex_count:
        raise ValueError("PLY payload vertex count differs from its header")
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output, points_xyz=points, bins_xyz=np.asarray(bins),
        roi_min_xyz=lower, roi_max_xyz=upper, roi_source_count=roi_count,
        source_ply=str(source), source_vertex_count=header.vertex_count,
        source_size_bytes=source.stat().st_size,
        sampling_rule="first", max_points=max_bins,
    )
    return {
        "sample_path": str(output), "sampled_points": len(points),
        "roi_source_count": roi_count, "source_vertex_count": scanned,
        "bins_xyz": list(bins), "max_bins": max_bins,
    }


def voxelize_raw_roi(
    ply_path: str | Path,
    occupancy_path: str | Path,
    *,
    roi_min_xyz: tuple[float, float, float] = (12, -3.25, -6.5),
    roi_max_xyz: tuple[float, float, float] = (35, 8, 2),
    voxel_size: float = 0.1,
    padding_voxels: int = 4,
    max_grid_voxels: int = 5_000_000,
    batch_size: int = 100_000,
) -> dict[str, object]:
    """Stream every measured point in an ROI into a padded occupancy grid."""
    source = Path(ply_path)
    output = Path(occupancy_path)
    if output.exists():
        raise FileExistsError(f"occupancy already exists: {output}")
    lower = np.asarray(roi_min_xyz, dtype=np.float64)
    upper = np.asarray(roi_max_xyz, dtype=np.float64)
    if (lower.shape != (3,) or upper.shape != (3,) or
            not np.isfinite(lower).all() or not np.isfinite(upper).all() or
            np.any(lower >= upper)):
        raise ValueError("ROI bounds must be finite ordered XYZ triples")
    if not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("voxel_size must be finite and positive")
    if isinstance(padding_voxels, bool) or not isinstance(padding_voxels, int) or padding_voxels < 1:
        raise ValueError("padding_voxels must be a positive integer")
    if max_grid_voxels < 1 or batch_size < 1:
        raise ValueError("max_grid_voxels and batch_size must be positive")
    origin = lower - padding_voxels * voxel_size
    shape = np.ceil((upper - lower) / voxel_size).astype(int) + 1 + 2 * padding_voxels
    if int(np.prod(shape)) > max_grid_voxels:
        raise ValueError("voxel grid exceeds max_grid_voxels")
    occupied = np.zeros(tuple(shape), dtype=bool)
    header = read_ply_header(source)
    scanned = 0
    roi_count = 0
    for batch in iter_ply_xyz(source, batch_size):
        scanned += len(batch)
        if scanned // 10_000_000 != (scanned - len(batch)) // 10_000_000:
            print(f"Scanned {scanned:,} raw points", flush=True)
        within = np.all((batch >= lower) & (batch <= upper), axis=1)
        selected = batch[within]
        roi_count += len(selected)
        if len(selected):
            indices = np.floor((selected.astype(np.float64) - origin) / voxel_size).astype(int)
            np.clip(indices, 0, shape - 1, out=indices)
            occupied[tuple(indices.T)] = True
    if scanned != header.vertex_count:
        raise ValueError("PLY payload vertex count differs from its header")
    if roi_count == 0:
        raise ValueError("ROI contains no measured points")
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output, occupied_xyz=occupied, origin_xyz=origin, voxel_size=voxel_size,
        roi_min_xyz=lower, roi_max_xyz=upper, roi_source_count=roi_count,
        source_ply=str(source), source_vertex_count=header.vertex_count,
        source_size_bytes=source.stat().st_size, padding_voxels=padding_voxels,
    )
    return {
        "occupancy_path": str(output), "roi_source_count": roi_count,
        "source_vertex_count": scanned, "occupied_voxels": int(occupied.sum()),
        "grid_shape_xyz": shape.tolist(), "voxel_size": voxel_size,
    }


def boundary_from_occupancy(
    occupied_xyz: np.ndarray,
    origin_xyz: np.ndarray,
    *,
    voxel_size: float,
    radius_voxels: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Return the oriented synthetic boundary of a voxelized point cloud."""
    occupied = np.asarray(occupied_xyz, dtype=bool)
    lower = np.asarray(origin_xyz, dtype=np.float64)
    if occupied.ndim != 3 or not np.any(occupied):
        raise ValueError("occupied_xyz must be a nonempty 3D grid")
    if lower.shape != (3,) or not np.isfinite(lower).all():
        raise ValueError("origin_xyz must be a finite XYZ triple")
    if not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("voxel_size must be finite and positive")
    if isinstance(radius_voxels, bool) or not isinstance(radius_voxels, int) or radius_voxels < 0:
        raise ValueError("radius_voxels must be a nonnegative integer")
    offsets = np.indices((2 * radius_voxels + 1,) * 3) - radius_voxels
    ball = np.sum(offsets * offsets, axis=0) <= radius_voxels**2
    dilated = ndimage.binary_dilation(occupied, structure=ball)
    if (np.any(dilated[0]) or np.any(dilated[-1]) or
            np.any(dilated[:, 0]) or np.any(dilated[:, -1]) or
            np.any(dilated[:, :, 0]) or np.any(dilated[:, :, -1])):
        raise ValueError("dilated occupancy touches the grid boundary; add padding")
    connectivity = ndimage.generate_binary_structure(3, 1)
    _, observed_components = ndimage.label(occupied, structure=connectivity)
    _, dilated_components = ndimage.label(dilated, structure=connectivity)

    vertices, _, normals, _ = marching_cubes(
        dilated.astype(np.uint8), level=0.5,
        spacing=(voxel_size, voxel_size, voxel_size),
        gradient_direction="descent",
    )
    vertices = vertices.astype(np.float64) + lower
    normals = normals.astype(np.float64)
    lengths = np.linalg.norm(normals, axis=1)
    valid = np.isfinite(normals).all(axis=1) & (lengths >= 1e-8)
    dropped = int(np.count_nonzero(~valid))
    vertices = vertices[valid]
    normals = normals[valid]
    lengths = lengths[valid]
    if len(vertices) < 3:
        raise ValueError("dilated boundary has fewer than three valid oriented points")
    normals /= lengths[:, None]
    metadata: dict[str, object] = {
        "voxel_size": voxel_size,
        "radius_voxels": radius_voxels,
        "radius_xyz_units": voxel_size * radius_voxels,
        "grid_shape_xyz": list(occupied.shape),
        "observed_occupied_voxels": int(np.count_nonzero(occupied)),
        "dilated_occupied_voxels": int(np.count_nonzero(dilated)),
        "observed_occupancy_components": int(observed_components),
        "dilated_occupancy_components": int(dilated_components),
        "boundary_vertices_without_valid_normals": dropped,
        "boundary_vertices_before_sampling": len(vertices),
    }
    return vertices, normals, metadata


def free_space_probe_metrics(
    occupied_xyz: np.ndarray,
    origin_xyz: np.ndarray,
    *, voxel_size: float,
    radius_voxels: int,
    probe_xyz: np.ndarray,
) -> dict[str, object]:
    """Check whether unvalidated probes remain connected to the grid exterior.

    This is a six-neighbor flood fill on the complement of wall occupancy.
    The ROI has artificial open ends, so these figures are diagnostic only.
    """
    occupied = np.asarray(occupied_xyz, dtype=bool)
    probes = np.asarray(probe_xyz, dtype=np.float64)
    origin = np.asarray(origin_xyz, dtype=np.float64)
    if occupied.ndim != 3 or not occupied.any():
        raise ValueError("occupied_xyz must be a nonempty 3D grid")
    if origin.shape != (3,) or not np.isfinite(origin).all():
        raise ValueError("origin_xyz must be a finite XYZ triple")
    if not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("voxel_size must be finite and positive")
    if probes.ndim != 2 or probes.shape[1] != 3 or not np.isfinite(probes).all():
        raise ValueError("probe_xyz must contain finite (N, 3) points")
    if isinstance(radius_voxels, bool) or not isinstance(radius_voxels, int) or radius_voxels < 0:
        raise ValueError("radius_voxels must be a nonnegative integer")
    offsets = np.indices((2 * radius_voxels + 1,) * 3) - radius_voxels
    ball = np.sum(offsets * offsets, axis=0) <= radius_voxels**2
    dilated = ndimage.binary_dilation(occupied, structure=ball)
    empty = ~dilated
    labels, component_count = ndimage.label(empty, structure=ndimage.generate_binary_structure(3, 1))
    boundary = np.concatenate((
        labels[0].ravel(), labels[-1].ravel(),
        labels[:, 0].ravel(), labels[:, -1].ravel(),
        labels[:, :, 0].ravel(), labels[:, :, -1].ravel(),
    ))
    exterior_labels = np.unique(boundary[boundary != 0])
    exterior_mask = np.isin(labels, exterior_labels)
    indices = np.floor((probes - origin) / voxel_size).astype(int)
    if np.any(indices < 0) or np.any(indices >= np.asarray(occupied.shape)):
        raise ValueError("probe_xyz must lie inside the occupancy grid")
    probe_occupied = dilated[tuple(indices.T)]
    probe_exterior = exterior_mask[tuple(indices.T)]
    return {
        "empty_components_6_connected": int(component_count),
        "exterior_empty_voxels": int(np.count_nonzero(exterior_mask)),
        "enclosed_empty_voxels": int(np.count_nonzero(empty & ~exterior_mask)),
        "unvalidated_probe_occupied_count": int(np.count_nonzero(probe_occupied)),
        "unvalidated_probe_exterior_connected_count": int(np.count_nonzero(probe_exterior)),
        "unvalidated_probe_enclosed_empty_count": int(np.count_nonzero(~probe_occupied & ~probe_exterior)),
    }


def thicken_point_occupancy(
    points_xyz: np.ndarray,
    *,
    voxel_size: float,
    radius_voxels: int,
    max_grid_voxels: int = 5_000_000,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Dilate sampled measured points and return synthetic boundary XYZ/normals."""
    points = np.asarray(points_xyz, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3:
        raise ValueError("points_xyz must have shape (N, 3) with at least three points")
    if not np.isfinite(points).all():
        raise ValueError("points_xyz must be finite")
    if not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("voxel_size must be finite and positive")
    if isinstance(radius_voxels, bool) or not isinstance(radius_voxels, int) or radius_voxels < 1:
        raise ValueError("radius_voxels must be a positive integer")
    if max_grid_voxels < 1:
        raise ValueError("max_grid_voxels must be positive")
    padding = radius_voxels + 2
    lower = points.min(axis=0) - padding * voxel_size
    shape = np.ceil((points.max(axis=0) - points.min(axis=0)) / voxel_size).astype(int)
    shape += 1 + 2 * padding
    if int(np.prod(shape)) > max_grid_voxels:
        raise ValueError("voxel grid exceeds max_grid_voxels")
    indices = np.floor((points - lower) / voxel_size).astype(int)
    np.clip(indices, 0, shape - 1, out=indices)
    occupied = np.zeros(tuple(shape), dtype=bool)
    occupied[tuple(indices.T)] = True
    return boundary_from_occupancy(
        occupied, lower, voxel_size=voxel_size, radius_voxels=radius_voxels
    )


def sample_oriented_surface(
    points_xyz: np.ndarray, normals_xyz: np.ndarray, *, max_points: int
) -> tuple[np.ndarray, np.ndarray]:
    """Retain evenly spaced Marching Cubes vertices and their paired normals."""
    if points_xyz.shape != normals_xyz.shape or points_xyz.ndim != 2 or points_xyz.shape[1] != 3:
        raise ValueError("points and normals must have matching (N, 3) shape")
    if max_points < 3:
        raise ValueError("max_points must be at least three")
    if len(points_xyz) <= max_points:
        return points_xyz, normals_xyz
    indices = np.linspace(0, len(points_xyz) - 1, max_points, dtype=np.int64)
    return points_xyz[indices], normals_xyz[indices]


def mesh_metrics(
    mesh: object, measured_xyz: np.ndarray, holdout_xyz: np.ndarray,
    probe_xyz: np.ndarray | None = None,
    *, evaluation_label: str = "holdout",
) -> dict[str, object]:
    """Summarize topology and distance to a named evaluation point set."""
    import open3d as o3d

    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    if not len(vertices) or not len(triangles):
        raise ValueError("Poisson returned an empty mesh")
    edges = np.sort(np.concatenate((triangles[:, [0, 1]], triangles[:, [1, 2]],
                                    triangles[:, [2, 0]])), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    clusters, _, _ = mesh.cluster_connected_triangles()
    vertex_distance = cKDTree(measured_xyz).query(vertices, workers=1)[0]
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))
    watertight = bool(mesh.is_watertight())
    edge_manifold = bool(mesh.is_edge_manifold(allow_boundary_edges=False))
    vertex_manifold = bool(mesh.is_vertex_manifold())
    orientable = bool(mesh.is_orientable())
    self_intersecting = bool(mesh.is_self_intersecting())
    evaluation_distance = np.concatenate([
        scene.compute_distance(o3d.core.Tensor(chunk.astype(np.float32))).numpy()
        for chunk in np.array_split(holdout_xyz, max(1, int(np.ceil(len(holdout_xyz) / 20_000))))
    ])
    probe_inside_fraction = None
    probe_sdf_p05 = None
    probe_sdf_p50 = None
    probe_sdf_p95 = None
    if probe_xyz is not None and len(probe_xyz) and watertight:
        probe_tensor = o3d.core.Tensor(np.asarray(probe_xyz, dtype=np.float32))
        occupancy = scene.compute_occupancy(probe_tensor).numpy()
        probe_sdf = scene.compute_signed_distance(probe_tensor).numpy()
        probe_inside_fraction = float(np.mean(occupancy))
        probe_sdf_p05 = float(np.percentile(probe_sdf, 5))
        probe_sdf_p50 = float(np.percentile(probe_sdf, 50))
        probe_sdf_p95 = float(np.percentile(probe_sdf, 95))
    return {
        "vertices": len(vertices),
        "triangles": len(triangles),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "components": int(np.max(clusters)) + 1,
        "watertight": watertight,
        "edge_manifold_without_boundary": edge_manifold,
        "vertex_manifold": vertex_manifold,
        "orientable": orientable,
        "self_intersecting": self_intersecting,
        "mesh_bounds_xyz": [mesh.get_min_bound().tolist(), mesh.get_max_bound().tolist()],
        "vertex_to_measured_p95": float(np.percentile(vertex_distance, 95)),
        "vertex_to_measured_p99": float(np.percentile(vertex_distance, 99)),
        "vertex_farther_than_2_fraction": float(np.mean(vertex_distance > 2)),
        f"{evaluation_label}_to_mesh_p95": float(np.percentile(evaluation_distance, 95)),
        f"{evaluation_label}_to_mesh_p99": float(np.percentile(evaluation_distance, 99)),
        "unvalidated_probe_inside_fraction": probe_inside_fraction,
        "unvalidated_probe_signed_distance_p05": probe_sdf_p05,
        "unvalidated_probe_signed_distance_p50": probe_sdf_p50,
        "unvalidated_probe_signed_distance_p95": probe_sdf_p95,
    }


def run_experiment(
    sample_path: str | Path,
    output_prefix: str | Path,
    *,
    voxel_size: float = 0.25,
    radii_voxels: tuple[int, ...] = (1, 2),
    max_boundary_points: int = 100_000,
    depth: int = 8,
    threads: int = 1,
    probe_graph_path: str | Path | None = None,
) -> dict[str, object]:
    """Run comparable baseline and morphological inputs through Poisson."""
    import open3d as o3d

    if not radii_voxels or len(set(radii_voxels)) != len(radii_voxels):
        raise ValueError("radii_voxels must be nonempty and distinct")
    if max_boundary_points < 3:
        raise ValueError("max_boundary_points must be at least three")
    with np.load(sample_path, allow_pickle=False) as archive:
        measured = np.asarray(archive["points_xyz"], dtype=np.float64)
        sample_metadata = {
            key: archive[key].tolist() for key in (
                "bins_xyz", "roi_min_xyz", "roi_max_xyz", "roi_source_count",
                "source_ply", "source_vertex_count", "source_size_bytes",
                "sampling_rule", "max_points",
            ) if key in archive
        }
    if measured.ndim != 2 or measured.shape[1] != 3 or len(measured) < 5:
        raise ValueError("sample must contain at least five XYZ points")
    if not np.isfinite(measured).all():
        raise ValueError("sample coordinates must be finite")
    if not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("voxel_size must be finite and positive")
    if any(isinstance(radius, bool) or not isinstance(radius, int) or radius < 1
           for radius in radii_voxels):
        raise ValueError("radii_voxels must contain positive integers")
    holdout_seed = 20261015
    rng = np.random.default_rng(holdout_seed)
    held_indices = rng.permutation(len(measured))[:max(1, len(measured) // 5)]
    train_mask = np.ones(len(measured), dtype=bool)
    train_mask[held_indices] = False
    training = measured[train_mask]
    holdout = measured[~train_mask]
    probes = None
    if probe_graph_path is not None:
        with np.load(probe_graph_path, allow_pickle=False) as archive:
            probes = np.asarray(archive["nodes_xyz"], dtype=np.float64)
        if probes.ndim != 2 or probes.shape[1] != 3 or not np.isfinite(probes).all():
            raise ValueError("probe graph must contain finite nodes_xyz with shape (N, 3)")
        if "roi_min_xyz" in sample_metadata and "roi_max_xyz" in sample_metadata:
            lower = np.asarray(sample_metadata["roi_min_xyz"])
            upper = np.asarray(sample_metadata["roi_max_xyz"])
            probes = probes[np.all((probes >= lower) & (probes <= upper), axis=1)]
    prefix = Path(output_prefix)
    names = ["baseline", *(f"dilate_r{radius}" for radius in radii_voxels)]
    outputs = [prefix.with_name(prefix.name + "_" + name + ".obj") for name in names]
    input_archives = [output.with_suffix(".input.npz") for output in outputs[1:]]
    summary_path = prefix.with_name(prefix.name + "_summary.json")
    existing = [str(path) for path in (*outputs, *input_archives, summary_path) if path.exists()]
    if existing:
        raise FileExistsError("outputs already exist: " + ", ".join(existing))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "status": "diagnostic_only_not_validated_interior",
        "method": "voxel dilation -> marching-cubes boundary -> Screened Poisson",
        "baseline_normals": "Open3D KNN 30, tangent-plane orientation 30",
        "dilated_normals": "marching-cubes normals of inferred voxel boundary",
        "geometry_semantics": "dilated observed-point occupancy; synthetic wall envelope, not cave void",
        "sample_path": str(sample_path),
        "measured_points": len(measured),
        "training_points": len(training),
        "holdout_points": len(holdout),
        "holdout_seed": holdout_seed,
        "measured_xyz_sha256": hashlib.sha256(measured.astype(np.float32).tobytes()).hexdigest(),
        "sample_metadata": sample_metadata,
        "poisson_depth": depth,
        "poisson_threads": threads,
        "normal_neighbors": 30,
        "orientation_neighbors": 30,
        "voxel_size": voxel_size,
        "max_boundary_points": max_boundary_points,
        "boundary_sampling": "evenly spaced marching-cubes vertex indices, no randomness",
        "probe_graph_path": str(probe_graph_path) if probe_graph_path is not None else None,
        "unvalidated_probe_count": len(probes) if probes is not None else 0,
        "complete": False,
        "runs": {},
    }

    for name, output in zip(names, outputs, strict=True):
        start = perf_counter()
        if name == "baseline":
            mesh, _ = reconstruct_poisson(training, depth=depth, threads=threads)
            input_count = len(training)
            dilation = None
            input_path = None
        else:
            radius = int(name.removeprefix("dilate_r"))
            surface, normals, dilation = thicken_point_occupancy(
                training, voxel_size=voxel_size, radius_voxels=radius
            )
            surface, normals = sample_oriented_surface(
                surface, normals, max_points=max_boundary_points
            )
            input_count = len(surface)
            input_path = output.with_suffix(".input.npz")
            np.savez_compressed(input_path, points_xyz=surface, normals_xyz=normals)
            mesh, _ = reconstruct_poisson(
                surface, depth=depth, threads=threads, oriented_normals_xyz=normals
            )
        if not o3d.io.write_triangle_mesh(str(output), mesh):
            raise OSError(f"could not write mesh: {output}")
        metrics = mesh_metrics(mesh, measured, holdout, probes)
        summary["runs"][name] = {
            "mesh_path": str(output),
            "poisson_input_path": str(input_path) if input_path is not None else None,
            "poisson_input_points": input_count,
            "dilation": dilation,
            "elapsed_seconds": perf_counter() - start,
            **metrics,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"run": name, **summary["runs"][name]}, indent=2), flush=True)
    summary["complete"] = True
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_raw_occupancy_experiment(
    occupancy_path: str | Path,
    sample_path: str | Path,
    output_prefix: str | Path,
    *,
    radii_voxels: tuple[int, ...] = (0, 1, 2),
    max_boundary_points: int = 100_000,
    depth: int = 8,
    threads: int = 1,
    probe_graph_path: str | Path | None = None,
) -> dict[str, object]:
    """Compare Poisson inputs from all raw ROI points at fixed voxel resolution.

    The measured sample is only an in-sample distance check: all its points
    were included when building the raw occupancy. It is not a holdout.
    """
    import open3d as o3d

    if not radii_voxels or len(set(radii_voxels)) != len(radii_voxels):
        raise ValueError("radii_voxels must be nonempty and distinct")
    if any(isinstance(radius, bool) or not isinstance(radius, int) or radius < 0
           for radius in radii_voxels):
        raise ValueError("radii_voxels must contain nonnegative integers")
    if max_boundary_points < 3:
        raise ValueError("max_boundary_points must be at least three")
    with np.load(occupancy_path, allow_pickle=False) as archive:
        occupied = np.asarray(archive["occupied_xyz"], dtype=bool)
        origin = np.asarray(archive["origin_xyz"], dtype=np.float64)
        voxel_size = float(archive["voxel_size"])
        roi_source_count = int(archive["roi_source_count"])
        roi_min = np.asarray(archive["roi_min_xyz"], dtype=np.float64)
        roi_max = np.asarray(archive["roi_max_xyz"], dtype=np.float64)
        source_ply = str(archive["source_ply"])
    with np.load(sample_path, allow_pickle=False) as archive:
        measured = np.asarray(archive["points_xyz"], dtype=np.float64)
        if "roi_source_count" in archive and int(archive["roi_source_count"]) != roi_source_count:
            raise ValueError("sample and occupancy must have the same raw ROI point count")
        if "source_ply" in archive and str(archive["source_ply"]) != source_ply:
            raise ValueError("sample and occupancy must come from the same PLY")
        if "roi_min_xyz" in archive and not np.allclose(archive["roi_min_xyz"], roi_min):
            raise ValueError("sample and occupancy must have the same ROI minimum")
        if "roi_max_xyz" in archive and not np.allclose(archive["roi_max_xyz"], roi_max):
            raise ValueError("sample and occupancy must have the same ROI maximum")
    if measured.ndim != 2 or measured.shape[1] != 3 or len(measured) < 3:
        raise ValueError("measured sample must have shape (N, 3) with at least three points")
    if not np.isfinite(measured).all():
        raise ValueError("measured sample must have finite XYZ coordinates")
    if np.any(measured < roi_min) or np.any(measured > roi_max):
        raise ValueError("measured sample must lie in the occupancy ROI")
    probes = None
    if probe_graph_path is not None:
        with np.load(probe_graph_path, allow_pickle=False) as archive:
            probes = np.asarray(archive["nodes_xyz"], dtype=np.float64)
        if probes.ndim != 2 or probes.shape[1] != 3 or not np.isfinite(probes).all():
            raise ValueError("probe graph must contain finite nodes_xyz with shape (N, 3)")
        probes = probes[np.all((probes >= roi_min) & (probes <= roi_max), axis=1)]
    prefix = Path(output_prefix)
    names = [f"raw_r{radius}" for radius in radii_voxels]
    outputs = [prefix.with_name(prefix.name + "_" + name + ".obj") for name in names]
    inputs = [output.with_suffix(".input.npz") for output in outputs]
    summary_path = prefix.with_name(prefix.name + "_summary.json")
    existing = [str(path) for path in (*outputs, *inputs, summary_path) if path.exists()]
    if existing:
        raise FileExistsError("outputs already exist: " + ", ".join(existing))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "status": "diagnostic_only_not_validated_interior",
        "method": "all raw ROI points -> voxel occupancy -> dilation -> marching-cubes boundary -> Screened Poisson",
        "geometry_semantics": "solid observed-point occupancy and its synthetic wall envelope, not cave void",
        "occupancy_path": str(occupancy_path),
        "sample_path": str(sample_path),
        "source_ply": source_ply,
        "raw_roi_points": roi_source_count,
        "occupied_voxels": int(np.count_nonzero(occupied)),
        "measured_evaluation_points": len(measured),
        "evaluation_is_holdout": False,
        "measured_xyz_sha256": hashlib.sha256(measured.astype(np.float32).tobytes()).hexdigest(),
        "voxel_size": voxel_size,
        "grid_shape_xyz": list(occupied.shape),
        "poisson_depth": depth,
        "poisson_threads": threads,
        "max_boundary_points": max_boundary_points,
        "boundary_sampling": "evenly spaced marching-cubes vertex indices, no randomness",
        "probe_graph_path": str(probe_graph_path) if probe_graph_path is not None else None,
        "unvalidated_probe_count": len(probes) if probes is not None else 0,
        "complete": False,
        "runs": {},
    }
    for radius, name, output, input_path in zip(radii_voxels, names, outputs, inputs, strict=True):
        start = perf_counter()
        surface, normals, dilation = boundary_from_occupancy(
            occupied, origin, voxel_size=voxel_size, radius_voxels=radius
        )
        surface, normals = sample_oriented_surface(
            surface, normals, max_points=max_boundary_points
        )
        np.savez_compressed(input_path, points_xyz=surface, normals_xyz=normals)
        mesh, _ = reconstruct_poisson(
            surface, depth=depth, threads=threads, oriented_normals_xyz=normals
        )
        if not o3d.io.write_triangle_mesh(str(output), mesh):
            raise OSError(f"could not write mesh: {output}")
        metrics = mesh_metrics(
            mesh, measured, measured, probes, evaluation_label="measured_sample"
        )
        free_space = (free_space_probe_metrics(
            occupied, origin, voxel_size=voxel_size,
            radius_voxels=radius, probe_xyz=probes,
        ) if probes is not None else None)
        summary["runs"][name] = {
            "mesh_path": str(output),
            "poisson_input_path": str(input_path),
            "poisson_input_points": len(surface),
            "dilation": dilation,
            "free_space_diagnostic": free_space,
            "elapsed_seconds": perf_counter() - start,
            **metrics,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"run": name, **summary["runs"][name]}, indent=2), flush=True)
    summary["complete"] = True
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", help="NPZ with measured points_xyz")
    parser.add_argument("--prepare-sample", action="store_true",
                        help="stream a PLY into a denser measured-point ROI sample")
    parser.add_argument("--voxelize-raw", action="store_true",
                        help="stream every raw ROI point into a voxel occupancy NPZ")
    parser.add_argument("--raw-occupancy", help="NPZ with raw occupied_xyz for reconstruction")
    parser.add_argument("--ply", help="source PLY for sample/voxelization")
    parser.add_argument("--roi-min", type=float, nargs=3, default=(12, -3.25, -6.5))
    parser.add_argument("--roi-max", type=float, nargs=3, default=(35, 8, 2))
    parser.add_argument("--max-bins", type=int, default=2_000_000)
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--padding-voxels", type=int, default=4)
    parser.add_argument("--output-prefix")
    parser.add_argument("--voxel-size", type=float, default=0.25)
    parser.add_argument("--radii", type=int, nargs="+",
                        help="default: 0 1 2 for raw occupancy; 1 2 for sampled points")
    parser.add_argument("--max-boundary-points", type=int, default=100_000)
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--probe-graph", help="optional unvalidated centreline NPZ diagnostic")
    args = parser.parse_args()
    if args.prepare_sample:
        if not args.ply or not args.sample:
            parser.error("--prepare-sample requires --ply and --sample")
        result = sample_measured_roi(
            args.ply, args.sample, roi_min_xyz=tuple(args.roi_min),
            roi_max_xyz=tuple(args.roi_max), max_bins=args.max_bins,
            batch_size=args.batch_size,
        )
        print(json.dumps(result, indent=2))
        return
    if args.voxelize_raw:
        if not args.ply or not args.raw_occupancy:
            parser.error("--voxelize-raw requires --ply and --raw-occupancy")
        result = voxelize_raw_roi(
            args.ply, args.raw_occupancy, roi_min_xyz=tuple(args.roi_min),
            roi_max_xyz=tuple(args.roi_max), voxel_size=args.voxel_size,
            padding_voxels=args.padding_voxels, batch_size=args.batch_size,
        )
        print(json.dumps(result, indent=2))
        return
    if not args.output_prefix:
        parser.error("--output-prefix is required for reconstruction")
    if not args.sample:
        parser.error("reconstruction requires --sample")
    if args.raw_occupancy:
        run_raw_occupancy_experiment(
            args.raw_occupancy, args.sample, args.output_prefix,
            radii_voxels=tuple(args.radii or (0, 1, 2)), max_boundary_points=args.max_boundary_points,
            depth=args.depth, threads=args.threads, probe_graph_path=args.probe_graph,
        )
        return
    run_experiment(
        args.sample, args.output_prefix, voxel_size=args.voxel_size,
        radii_voxels=tuple(args.radii or (1, 2)), max_boundary_points=args.max_boundary_points,
        depth=args.depth, threads=args.threads, probe_graph_path=args.probe_graph,
    )


if __name__ == "__main__":
    main()
