"""Test the callable entry point for one reference voxelization pass."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from cavegen.datastream.run_reference_voxelization import main, run
from cavegen.datastream.surface_io import load_surface_npz


class ReferenceVoxelizationRunnerTests(unittest.TestCase):
    """Verify that the runner delegates to the streamed PLY preprocessing flow."""

    def test_runs_a_small_ply_without_persisting_the_surface_grid(self) -> None:
        """Return the expected surface grid from command-independent arguments."""
        header = (
            b"ply\nformat ascii 1.0\nelement vertex 2\nproperty float x\n"
            b"property float y\nproperty float z\nend_header\n"
        )
        bounds = {"min_xyz": [0, 0, 0], "max_xyz": [1, 1, 1]}

        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            ply_path = directory_path / "reference.ply"
            bounds_path = directory_path / "bounds.json"
            ply_path.write_bytes(header + b"0 0 0\n1 1 1\n")
            bounds_path.write_text(json.dumps(bounds), encoding="utf-8")
            surface = run(ply_path, bounds_path, (2, 2, 2), batch_size=1)

        expected = np.zeros((2, 2, 2), dtype=bool)
        expected[0, 0, 0] = True
        expected[1, 1, 1] = True
        np.testing.assert_array_equal(surface, expected)

    def test_command_saves_surface_archive_with_reproduction_metadata(self) -> None:
        """Write the surface grid and its source/normalization context to NPZ."""
        header = (
            b"ply\nformat ascii 1.0\nelement vertex 2\nproperty float x\n"
            b"property float y\nproperty float z\nend_header\n"
        )
        bounds = {"min_xyz": [0, 0, 0], "max_xyz": [1, 1, 1]}

        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            ply_path = directory_path / "reference.ply"
            bounds_path = directory_path / "bounds.json"
            output_path = directory_path / "surface.npz"
            ply_path.write_bytes(header + b"0 0 0\n1 1 1\n")
            bounds_path.write_text(json.dumps(bounds), encoding="utf-8")
            arguments = [
                "run_reference_voxelization",
                "--ply",
                str(ply_path),
                "--bounds",
                str(bounds_path),
                "--shape",
                "2",
                "2",
                "2",
                "--batch-size",
                "1",
                "--progress-every",
                "0",
                "--output",
                str(output_path),
            ]
            with patch("sys.argv", arguments), redirect_stdout(StringIO()) as stdout:
                main()
            surface, metadata = load_surface_npz(output_path)

        self.assertIn("Saved surface archive", stdout.getvalue())
        self.assertEqual(metadata["semantic"], "true_means_observed_surface")
        self.assertEqual(metadata["volume_shape_zyx"], [2, 2, 2])
        np.testing.assert_array_equal(
            surface,
            np.array([[[True, False], [False, False]], [[False, False], [False, True]]]),
        )


if __name__ == "__main__":
    unittest.main()
