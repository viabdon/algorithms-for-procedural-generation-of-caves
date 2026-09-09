"""Test the streamed PLY-to-surface-voxel integration."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.datastream.reference_preprocessing import load_xyz_bounds, voxelize_ply_surface


class ReferencePreprocessingTests(unittest.TestCase):
    """Verify persisted bounds and the incremental PLY preprocessing flow."""

    def test_loads_bounds_and_voxelizes_ascii_ply_in_batches(self) -> None:
        """Compose PLY reading, XYZ normalization, and ZYX surface marking."""
        header = (
            b"ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\n"
            b"property float y\nproperty float z\nend_header\n"
        )
        payload = b"0 0 0\n5 1 1\n10 2 1\n"
        bounds = {"min_xyz": [0, 0, 0], "max_xyz": [10, 2, 1]}

        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            ply_path = directory_path / "reference.ply"
            bounds_path = directory_path / "bounds.json"
            ply_path.write_bytes(header + payload)
            bounds_path.write_text(json.dumps(bounds), encoding="utf-8")

            minimum, maximum = load_xyz_bounds(bounds_path)
            surface = voxelize_ply_surface(ply_path, bounds_path, (3, 5, 11), batch_size=2)

        np.testing.assert_array_equal(minimum, np.array((0, 0, 0), dtype=np.float32))
        np.testing.assert_array_equal(maximum, np.array((10, 2, 1), dtype=np.float32))
        expected = np.zeros((3, 5, 11), dtype=bool)
        expected[0, 1, 0] = True
        expected[2, 2, 5] = True
        expected[2, 3, 10] = True
        np.testing.assert_array_equal(surface, expected)

    def test_rejects_malformed_bounds_metadata(self) -> None:
        """Reject missing, malformed, and unordered XYZ bounds before reading PLY."""
        cases = (
            ({"min_xyz": [0, 0, 0]}, "must define"),
            ({"min_xyz": [0, 0], "max_xyz": [1, 1, 1]}, "shape"),
            ({"min_xyz": [2, 0, 0], "max_xyz": [1, 1, 1]}, "less than"),
        )

        with TemporaryDirectory() as directory:
            bounds_path = Path(directory) / "bounds.json"
            for metadata, message in cases:
                with self.subTest(message=message):
                    bounds_path.write_text(json.dumps(metadata), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        load_xyz_bounds(bounds_path)

    def test_reports_cumulative_vertices_at_requested_intervals(self) -> None:
        """Report only after streamed batches cross each configured interval."""
        header = (
            b"ply\nformat ascii 1.0\nelement vertex 5\nproperty float x\n"
            b"property float y\nproperty float z\nend_header\n"
        )
        bounds = {"min_xyz": [0, 0, 0], "max_xyz": [1, 1, 1]}
        reported_counts: list[int] = []

        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            ply_path = directory_path / "reference.ply"
            bounds_path = directory_path / "bounds.json"
            ply_path.write_bytes(header + b"0 0 0\n0 0 0\n0 0 0\n0 0 0\n1 1 1\n")
            bounds_path.write_text(json.dumps(bounds), encoding="utf-8")
            voxelize_ply_surface(
                ply_path,
                bounds_path,
                (2, 2, 2),
                batch_size=2,
                progress_every=2,
                progress_callback=reported_counts.append,
            )

        self.assertEqual(reported_counts, [2, 4])


if __name__ == "__main__":
    unittest.main()
