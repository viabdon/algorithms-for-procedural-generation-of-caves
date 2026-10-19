"""Observable contracts for diagnostic point-occupancy thickening."""

from __future__ import annotations

import unittest
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from cavegen.meshing.morphological_thickening import (
    boundary_from_occupancy,
    free_space_probe_metrics,
    voxelize_raw_roi,
    run_raw_occupancy_experiment,
    sample_measured_roi,
    sample_oriented_surface,
    thicken_point_occupancy,
    run_experiment,
)


class MorphologicalThickeningTests(unittest.TestCase):
    def test_free_space_probes_distinguish_enclosed_and_exterior_empty(self) -> None:
        grid = np.zeros((9, 9, 9), dtype=bool)
        grid[2:7, 2:7, 2] = True
        grid[2:7, 2:7, 6] = True
        grid[2:7, 2, 2:7] = True
        grid[2:7, 6, 2:7] = True
        grid[2, 2:7, 2:7] = True
        grid[6, 2:7, 2:7] = True
        report = free_space_probe_metrics(
            grid, np.zeros(3), voxel_size=1, radius_voxels=0,
            probe_xyz=np.array([[4., 4., 4.], [0., 0., 0.], [2., 4., 4.]]),
        )
        self.assertEqual(report["unvalidated_probe_enclosed_empty_count"], 1)
        self.assertEqual(report["unvalidated_probe_exterior_connected_count"], 1)
        self.assertEqual(report["unvalidated_probe_occupied_count"], 1)
        self.assertEqual(report["enclosed_empty_voxels"], 27)

    def test_raw_voxelization_uses_all_roi_points_and_radius_zero_is_supported(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ply = root / "points.ply"
            ply.write_text(
                "ply\nformat ascii 1.0\nelement vertex 5\n"
                "property float x\nproperty float y\nproperty float z\n"
                "end_header\n0 0 0\n0.01 0 0\n0.4 0 0\n0.4 0.4 0\n9 0 0\n"
            )
            output = root / "raw.npz"
            report = voxelize_raw_roi(
                ply, output, roi_min_xyz=(-1, -1, -1),
                roi_max_xyz=(1, 1, 1), voxel_size=0.2, batch_size=2,
            )
            self.assertEqual(report["roi_source_count"], 4)
            self.assertEqual(report["occupied_voxels"], 3)
            with np.load(output, allow_pickle=False) as archive:
                occupied = archive["occupied_xyz"]
                origin = archive["origin_xyz"]
            _, normals0, metadata0 = boundary_from_occupancy(
                occupied, origin, voxel_size=0.2, radius_voxels=0
            )
            _, normals1, metadata1 = boundary_from_occupancy(
                occupied, origin, voxel_size=0.2, radius_voxels=1
            )
            self.assertEqual(metadata0["dilated_occupied_voxels"], 3)
            self.assertGreater(metadata1["dilated_occupied_voxels"], 3)
            self.assertTrue(np.isfinite(normals0).all())
            self.assertTrue(np.isfinite(normals1).all())
            with self.assertRaises(FileExistsError):
                voxelize_raw_roi(ply, output)

    def test_roi_sample_uses_only_measured_ply_points_and_preserves_source_count(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ply = root / "points.ply"
            ply.write_text(
                "ply\nformat ascii 1.0\nelement vertex 5\n"
                "property float x\nproperty float y\nproperty float z\n"
                "end_header\n0 0 0\n0.1 0 0\n1 0 0\n2 0 0\n9 0 0\n"
            )
            sample = root / "sample.npz"
            result = sample_measured_roi(
                ply, sample, roi_min_xyz=(0, -1, -1),
                roi_max_xyz=(2, 1, 1), max_bins=100, batch_size=2,
            )
            self.assertEqual(result["source_vertex_count"], 5)
            self.assertEqual(result["roi_source_count"], 4)
            with np.load(sample, allow_pickle=False) as archive:
                self.assertEqual(int(archive["source_vertex_count"]), 5)
                self.assertEqual(int(archive["roi_source_count"]), 4)
                for point in archive["points_xyz"]:
                    self.assertTrue(any(np.allclose(point, original)
                                        for original in ([0, 0, 0], [0.1, 0, 0],
                                                         [1, 0, 0], [2, 0, 0])))
            with self.assertRaises(FileExistsError):
                sample_measured_roi(ply, sample)

    def test_dilation_expands_occupancy_and_returns_finite_boundary(self) -> None:
        points = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0],
                           [0.0, 2.0, 0.0]])
        vertices, normals, metadata = thicken_point_occupancy(
            points, voxel_size=0.5, radius_voxels=1
        )
        self.assertGreater(metadata["dilated_occupied_voxels"],
                           metadata["observed_occupied_voxels"])
        self.assertEqual(vertices.shape, normals.shape)
        self.assertGreater(len(vertices), len(points))
        self.assertTrue(np.isfinite(vertices).all())
        np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1)

    def test_larger_radius_expands_more_and_sampling_keeps_alignment(self) -> None:
        points = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0],
                           [0.0, 2.0, 0.0]])
        _, _, small = thicken_point_occupancy(points, voxel_size=0.5, radius_voxels=1)
        vertices, normals, large = thicken_point_occupancy(
            points, voxel_size=0.5, radius_voxels=2
        )
        self.assertGreater(large["dilated_occupied_voxels"],
                           small["dilated_occupied_voxels"])
        selected_points, selected_normals = sample_oriented_surface(
            vertices, normals, max_points=20
        )
        self.assertEqual(len(selected_points), 20)
        self.assertEqual(selected_points.shape, selected_normals.shape)
        for point, normal in zip(selected_points, selected_normals, strict=True):
            index = np.flatnonzero(np.all(vertices == point, axis=1))
            self.assertEqual(len(index), 1)
            np.testing.assert_array_equal(normal, normals[index[0]])

    def test_rejects_invalid_radius_and_unbounded_grid(self) -> None:
        points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                           [0.0, 1.0, 0.0]])
        with self.assertRaisesRegex(ValueError, "radius_voxels"):
            thicken_point_occupancy(points, voxel_size=0.5, radius_voxels=0)
        with self.assertRaisesRegex(ValueError, "max_grid_voxels"):
            thicken_point_occupancy(
                points, voxel_size=0.01, radius_voxels=1, max_grid_voxels=100
            )

    @unittest.skipUnless(importlib.util.find_spec("open3d"), "Open3D extra is optional")
    def test_experiment_uses_same_training_and_unused_holdout_for_both_meshes(self) -> None:
        n = 300
        i = np.arange(n)
        z = 1 - 2 * (i + 0.5) / n
        angle = i * np.pi * (3 - np.sqrt(5))
        radius = np.sqrt(1 - z * z)
        points = np.column_stack((radius * np.cos(angle), radius * np.sin(angle), z))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sphere.npz"
            np.savez_compressed(sample, points_xyz=points)
            graph = root / "probe.npz"
            np.savez_compressed(graph, nodes_xyz=np.array([[0.0, 0.0, 0.0]]))
            report = run_experiment(
                sample, root / "compare", voxel_size=0.4,
                radii_voxels=(1,), max_boundary_points=1000, depth=5,
                probe_graph_path=graph,
            )
            self.assertTrue(report["complete"])
            self.assertEqual(report["training_points"], 240)
            self.assertEqual(report["holdout_points"], 60)
            self.assertIn("holdout_to_mesh_p95", report["runs"]["baseline"])
            self.assertIn("holdout_to_mesh_p95", report["runs"]["dilate_r1"])
            self.assertEqual(report["unvalidated_probe_count"], 1)
            self.assertEqual(report["runs"]["baseline"]["unvalidated_probe_inside_fraction"], 1.0)
            self.assertTrue((root / "compare_summary.json").is_file())
            self.assertTrue((root / "compare_dilate_r1.input.npz").is_file())
            with self.assertRaises(FileExistsError):
                run_experiment(sample, root / "compare", radii_voxels=(1,))

    @unittest.skipUnless(importlib.util.find_spec("open3d"), "Open3D extra is optional")
    def test_raw_experiment_labels_measured_sample_as_in_sample(self) -> None:
        n = 300
        i = np.arange(n)
        z = 1 - 2 * (i + 0.5) / n
        angle = i * np.pi * (3 - np.sqrt(5))
        radius = np.sqrt(1 - z * z)
        points = np.column_stack((radius * np.cos(angle), radius * np.sin(angle), z))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sphere.npz"
            np.savez_compressed(sample, points_xyz=points, roi_source_count=n)
            occupancy = root / "occupancy.npz"
            origin = np.array([-2.0, -2.0, -2.0])
            grid = np.zeros((11, 11, 11), dtype=bool)
            indices = np.floor((points - origin) / 0.4).astype(int)
            grid[tuple(indices.T)] = True
            np.savez_compressed(
                occupancy, occupied_xyz=grid, origin_xyz=origin, voxel_size=0.4,
                roi_source_count=n, roi_min_xyz=[-1.1] * 3,
                roi_max_xyz=[1.1] * 3, source_ply="synthetic.ply",
            )
            report = run_raw_occupancy_experiment(
                occupancy, sample, root / "raw", radii_voxels=(0, 1),
                max_boundary_points=1000, depth=5,
            )
            self.assertTrue(report["complete"])
            self.assertFalse(report["evaluation_is_holdout"])
            self.assertEqual(report["raw_roi_points"], 300)
            self.assertIn("measured_sample_to_mesh_p95", report["runs"]["raw_r0"])
            self.assertIn("measured_sample_to_mesh_p95", report["runs"]["raw_r1"])
            self.assertNotIn("holdout_to_mesh_p95", report["runs"]["raw_r1"])
            unrelated = root / "unrelated.npz"
            np.savez_compressed(unrelated, points_xyz=points, roi_source_count=n,
                                source_ply="another.ply")
            with self.assertRaisesRegex(ValueError, "same PLY"):
                run_raw_occupancy_experiment(
                    occupancy, unrelated, root / "invalid", radii_voxels=(0,)
                )


if __name__ == "__main__":
    unittest.main()
