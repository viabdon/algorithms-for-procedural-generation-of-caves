"""Compare direct Poisson with small-radius thickening over a full PLY sample.

The sampled points are shared by all runs. Thickening uses sparse, overlapping
voxel tiles so distant outliers do not require one enormous dense array.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage.measure import marching_cubes

from cavegen.meshing.morphological_thickening import mesh_metrics, sample_oriented_surface
from cavegen.meshing.poisson import reconstruct_poisson


def sparse_thickened_boundary(
    points_xyz: np.ndarray, *, voxel_size: float, radius_voxels: int,
    tile_size: int = 96, progress: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Return the Marching Cubes boundary of dilated sampled-point voxels.

    Every tile includes a halo of source voxels. A tile is processed whenever
    dilated occupancy can reach it, including otherwise empty neighboring tiles.
    Vertices are assigned to one half-open tile to avoid seam duplicates.
    """
    points = np.asarray(points_xyz, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("points_xyz must contain at least three finite XYZ points")
    if not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("voxel_size must be finite and positive")
    if isinstance(radius_voxels, bool) or not isinstance(radius_voxels, int) or radius_voxels < 1:
        raise ValueError("radius_voxels must be a positive integer")
    if tile_size < 2 * radius_voxels + 4:
        raise ValueError("tile_size is too small for the dilation radius")

    halo = radius_voxels + 2
    origin = np.floor(points.min(axis=0) / voxel_size) * voxel_size - halo * voxel_size
    indices = np.floor((points - origin) / voxel_size).astype(np.int64)
    indices = np.unique(indices, axis=0)
    source_tiles = np.floor_divide(indices, tile_size)
    tile_to_indices: dict[tuple[int, int, int], np.ndarray] = {}
    unique_source, inverse = np.unique(source_tiles, axis=0, return_inverse=True)
    for n, tile in enumerate(unique_source):
        tile_to_indices[tuple(tile)] = indices[inverse == n]

    # The eight shifted corners identify every tile touched by a dilated voxel.
    candidates = []
    for dx in (-radius_voxels, radius_voxels):
        for dy in (-radius_voxels, radius_voxels):
            for dz in (-radius_voxels, radius_voxels):
                shifted = indices + np.array((dx, dy, dz), dtype=np.int64)
                candidates.append(np.floor_divide(shifted, tile_size))
    tiles = np.unique(np.concatenate(candidates), axis=0)
    offsets = np.indices((2 * radius_voxels + 1,) * 3) - radius_voxels
    ball = np.sum(offsets * offsets, axis=0) <= radius_voxels**2
    all_vertices: list[np.ndarray] = []
    all_normals: list[np.ndarray] = []
    side = tile_size + 2 * halo
    for tile_number, tile in enumerate(tiles, start=1):
        if progress and tile_number % 100 == 0:
            print(f"Boundary tiles: {tile_number:,}/{len(tiles):,}", flush=True)
        tile_start = tile * tile_size
        local_start = tile_start - halo
        occupied = np.zeros((side, side, side), dtype=bool)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    nearby = tile_to_indices.get(tuple(tile + (dx, dy, dz)))
                    if nearby is None:
                        continue
                    local = nearby - local_start
                    valid = np.all((local >= 0) & (local < side), axis=1)
                    selected = local[valid]
                    occupied[tuple(selected.T)] = True
        if not occupied.any():
            continue
        dilated = ndimage.binary_dilation(occupied, structure=ball)
        if dilated.all():
            continue
        vertices, _, normals, _ = marching_cubes(
            dilated.astype(np.uint8), level=0.5,
            spacing=(voxel_size,) * 3, gradient_direction="descent",
        )
        grid_vertices = vertices / voxel_size + local_start
        owned = np.all((grid_vertices >= tile_start) & (grid_vertices < tile_start + tile_size), axis=1)
        if np.any(owned):
            all_vertices.append(vertices[owned] + origin + local_start * voxel_size)
            all_normals.append(normals[owned])
    if not all_vertices:
        raise ValueError("dilated occupancy has no boundary vertices")
    surface = np.concatenate(all_vertices)
    normals = np.concatenate(all_normals).astype(np.float64)
    lengths = np.linalg.norm(normals, axis=1)
    valid = np.isfinite(normals).all(axis=1) & (lengths > 1e-8)
    surface, normals, lengths = surface[valid], normals[valid], lengths[valid]
    normals /= lengths[:, None]
    return surface, normals, {
        "voxel_size": voxel_size, "radius_voxels": radius_voxels,
        "radius_xyz_units": radius_voxels * voxel_size,
        "tile_size_voxels": tile_size, "occupied_voxels": len(indices),
        "processed_tiles": len(tiles), "boundary_points": len(surface),
    }


def run_full_extent_experiment(
    sample_path: str | Path, output_prefix: str | Path, *,
    figure_dir: str | Path,
    voxel_size: float = 0.05, max_boundary_points: int = 100_000,
    plot_points: int = 50_000, depth: int = 8, threads: int = 1,
) -> dict[str, object]:
    """Generate three OBJ meshes, three HTML views, and one metrics JSON."""
    import open3d as o3d
    from plots.plot_elaphes import amostrar_pontos, montar_malhas

    sample_path, prefix, figure_dir = Path(sample_path), Path(output_prefix), Path(figure_dir)
    with np.load(sample_path, allow_pickle=False) as archive:
        points = np.asarray(archive["points_xyz"], dtype=np.float64)
        sample_info = {key: archive[key].tolist() for key in (
            "bins_xyz", "source_count", "source_sha256", "bounds_xyz",
            "max_points", "sampling_rule",
        ) if key in archive}
    names = ("baseline", "radius_005", "radius_010")
    outputs = [(prefix.with_name(prefix.name + "_" + name + ".obj"),
                figure_dir / (prefix.name + "_" + name + ".html")) for name in names]
    report_path = prefix.with_name(prefix.name + "_summary.json")
    existing = [str(p) for pair in outputs for p in pair if p.exists()]
    if report_path.exists():
        existing.append(str(report_path))
    if existing:
        raise FileExistsError("outputs already exist: " + ", ".join(existing))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "status": "diagnostic_only_not_validated_interior", "complete": False,
        "sample_path": str(sample_path), "sample_info": sample_info,
        "sampled_points": len(points), "poisson_depth": depth,
        "normal_neighbors": 30, "orientation_neighbors": 30,
        "voxel_size": voxel_size, "max_boundary_points": max_boundary_points,
        "runs": {},
    }
    cloud = amostrar_pontos(points, plot_points, 0)
    for name, (obj_path, html_path) in zip(names, outputs, strict=True):
        print(f"Starting {name}", flush=True)
        if name == "baseline":
            mesh, _ = reconstruct_poisson(points, depth=depth, threads=threads)
            thickening = None
            poisson_input_count = len(points)
        else:
            radius_voxels = 1 if name == "radius_005" else 2
            surface, normals, thickening = sparse_thickened_boundary(
                points, voxel_size=voxel_size, radius_voxels=radius_voxels,
                progress=True,
            )
            surface, normals = sample_oriented_surface(
                surface, normals, max_points=max_boundary_points,
            )
            poisson_input_count = len(surface)
            mesh, _ = reconstruct_poisson(
                surface, depth=depth, threads=threads, oriented_normals_xyz=normals,
            )
        if not o3d.io.write_triangle_mesh(str(obj_path), mesh):
            raise OSError(f"failed to save {obj_path}")
        print(f"Computing metrics for {name}", flush=True)
        metrics = mesh_metrics(mesh, points, points, evaluation_label="measured_sample")
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.triangles)
        figure = montar_malhas(cloud, [(name, vertices, faces)])
        figure.update_layout(title=f"Elaphes completo: {name} e pontos amostrados")
        figure.write_html(html_path, include_plotlyjs=True)
        report["runs"][name] = {
            "mesh_path": str(obj_path), "html_path": str(html_path),
            "poisson_input_points": poisson_input_count,
            "thickening": thickening, **metrics,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Completed {name}: {html_path}", flush=True)
    report["complete"] = True
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--figure-dir", required=True)
    parser.add_argument("--voxel-size", type=float, default=0.05)
    parser.add_argument("--max-boundary-points", type=int, default=100_000)
    parser.add_argument("--plot-points", type=int, default=50_000)
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    result = run_full_extent_experiment(
        args.sample, args.output_prefix, figure_dir=args.figure_dir,
        voxel_size=args.voxel_size,
        max_boundary_points=args.max_boundary_points, plot_points=args.plot_points,
        depth=args.depth, threads=args.threads,
    )
    print(json.dumps({"summary": str(args.output_prefix) + "_summary.json", "complete": result["complete"]}))


if __name__ == "__main__":
    main()
