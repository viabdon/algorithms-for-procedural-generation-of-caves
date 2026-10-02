"""Observable contracts for bounded Poisson input preparation."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.meshing.poisson import run, sample_spatial_bins, spatial_bin_shape


class PoissonPreparationTests(unittest.TestCase):
    def test_centroid_and_spread_are_computed_across_batches(self) -> None:
        lower = np.array([0, 0, 0], dtype=np.float32)
        upper = np.array([2, 0, 0], dtype=np.float32)
        batches = [
            np.array([[0, 0, 0], [2, 0, 0]], dtype=np.float32),
            np.array([[1, 0, 0]], dtype=np.float32),
        ]
        points, bins, seen, counts, std = sample_spatial_bins(
            batches, lower, upper, max_points=1,
            sampling_rule="centroid", return_stats=True,
        )
        self.assertEqual(bins, (1, 1, 1))
        self.assertEqual(seen, 3)
        np.testing.assert_allclose(points, [[1, 0, 0]])
        np.testing.assert_array_equal(counts, [3])
        np.testing.assert_allclose(std, [[np.sqrt(2 / 3), 0, 0]])

    def test_spatial_sampling_is_bounded_and_preserves_xyz_coordinates(self) -> None:
        lower = np.array([0, 0, 0], dtype=np.float32)
        upper = np.array([4, 2, 1], dtype=np.float32)
        batches = [
            np.array([[0, 0, 0], [0.1, 0, 0], [4, 2, 1]], dtype=np.float32),
            np.array([[2, 1, 0.5], [0.2, 0, 0]], dtype=np.float32),
        ]
        points, bins, seen = sample_spatial_bins(batches, lower, upper, max_points=16)
        self.assertEqual(seen, 5)
        self.assertLessEqual(int(np.prod(bins)), 16)
        self.assertLessEqual(len(points), 16)
        self.assertTrue(np.any(np.all(points == [0, 0, 0], axis=1)))
        self.assertFalse(np.any(np.all(points == [0.1, 0, 0], axis=1)))
        self.assertTrue(np.any(np.all(points == [4, 2, 1], axis=1)))

    def test_degenerate_axis_and_invalid_bounds(self) -> None:
        lower = np.array([0, 1, 0], dtype=np.float32)
        upper = np.array([2, 1, 2], dtype=np.float32)
        bins = spatial_bin_shape(lower, upper, 8)
        self.assertEqual(bins[1], 1)
        self.assertLessEqual(int(np.prod(bins)), 8)
        with self.assertRaisesRegex(ValueError, "outside"):
            sample_spatial_bins(
                [np.array([[3, 1, 0]], dtype=np.float32)], lower, upper, 8
            )

    def test_sample_only_reuses_existing_ply_reader_and_writes_cache(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ply = root / "tiny.ply"
            ply.write_bytes(
                b"ply\nformat ascii 1.0\nelement vertex 3\n"
                b"property float x\nproperty float y\nproperty float z\n"
                b"end_header\n0 0 0\n1 0 0\n0 1 0\n"
            )
            bounds = root / "bounds.json"
            bounds.write_text(json.dumps({
                "min_xyz": [0, 0, 0],
                "max_xyz": [1, 1, 0],
                "source": {"vertex_count": 3, "size_bytes": ply.stat().st_size, "sha256": "synthetic"},
            }))
            sample = root / "sample.npz"
            result = run(
                ply, bounds, root / "mesh.obj", max_points=20,
                sample_path=sample, sample_only=True,
            )
            self.assertEqual(result["status"], "sample_ready")
            self.assertEqual(result["source_vertices"], 3)
            self.assertIsNone(result["random_seed"])
            self.assertFalse(result["uses_random_sampling"])
            with np.load(sample, allow_pickle=False) as archive:
                self.assertEqual(archive["points_xyz"].shape, (3, 3))
                self.assertEqual(str(archive["source_sha256"]), "synthetic")
            with self.assertRaisesRegex(ValueError, "different sampling rule"):
                run(
                    ply, bounds, root / "wrong.obj", max_points=20,
                    sample_path=sample, sampling_rule="centroid",
                )

            centroid = root / "centroid.npz"
            result = run(
                ply, bounds, None, max_points=1, sample_path=centroid,
                sample_only=True, sampling_rule="centroid",
            )
            self.assertEqual(result["sampling_rule"], "centroid")
            self.assertEqual(result["points_per_bin_max"], 3)
            with np.load(centroid, allow_pickle=False) as archive:
                np.testing.assert_array_equal(archive["bin_counts"], [3])
                np.testing.assert_allclose(
                    archive["points_xyz"], [[1 / 3, 1 / 3, 0]]
                )
                np.testing.assert_allclose(
                    archive["bin_variance_xyz"], [[2 / 9, 2 / 9, 0]]
                )

    @unittest.skipUnless(importlib.util.find_spec("open3d"), "Open3D extra is optional")
    def test_reconstructs_synthetic_closed_surface_as_obj(self) -> None:
        n = 400
        i = np.arange(n)
        z = 1 - 2 * (i + 0.5) / n
        angle = i * np.pi * (3 - np.sqrt(5))
        radius = np.sqrt(1 - z * z)
        points = np.column_stack((radius * np.cos(angle), radius * np.sin(angle), z))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ply = root / "sphere.ply"
            lines = [
                "ply", "format ascii 1.0", f"element vertex {n}",
                "property float x", "property float y", "property float z", "end_header",
            ]
            lines.extend(" ".join(map(str, point)) for point in points)
            ply.write_text("\n".join(lines) + "\n")
            bounds = root / "bounds.json"
            bounds.write_text(json.dumps({
                "min_xyz": points.min(axis=0).tolist(),
                "max_xyz": points.max(axis=0).tolist(),
                "source": {"vertex_count": n, "size_bytes": ply.stat().st_size, "sha256": "sphere"},
            }))
            mesh_path = root / "sphere.obj"
            result = run(
                ply, bounds, mesh_path,
                max_points=5000, depth=5, interior_seed_xyz=(0, 0, 0),
            )
            self.assertGreater(result["mesh_triangles"], 0)
            self.assertTrue(result["mesh_watertight"])
            self.assertEqual(result["mesh_boundary_edges"], 0)
            self.assertEqual(result["mesh_nonmanifold_edges"], 0)
            self.assertEqual(result["interior_seed_xyz"], (0, 0, 0))
            self.assertEqual(result["poisson_threads"], 1)
            self.assertFalse(result["uses_random_sampling"])
            self.assertTrue(mesh_path.is_file())
            self.assertTrue(mesh_path.with_suffix(".obj.json").is_file())


if __name__ == "__main__":
    unittest.main()
