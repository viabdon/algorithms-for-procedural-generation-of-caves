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
from cavegen.datastream.voxel_io import load_volume_npz


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

    def test_xyz_command_computes_bounds_and_matches_ply_grid(self) -> None:
        """Voxelize XYZ without a pre-existing bounds file; preserve provenance."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            xyz = root / "cloud.xyz"
            xyz.write_text("# point cloud\n0 0 0 255 0 0\n1 1 1 0 255 0\n")
            output = root / "nested" / "surface.npz"
            arguments = ["voxelize", "--input", str(xyz), "--output", str(output),
                         "--shape", "2", "2", "2", "--batch-size", "1",
                         "--progress-every", "0"]
            with patch("sys.argv", arguments), redirect_stdout(StringIO()):
                main()
            surface, metadata = load_surface_npz(output)
            bounds_path = output.with_suffix(".bounds.json")
            bounds = json.loads(bounds_path.read_text())
            self.assertEqual(bounds["min_xyz"], [0, 0, 0])
            self.assertEqual(bounds["max_xyz"], [1, 1, 1])
            self.assertEqual(metadata["source_format"], "xyz")
            self.assertEqual(metadata["source_path"], str(xyz))
            self.assertEqual(metadata["bounds_path"], str(bounds_path))
            self.assertNotIn("source_ply", metadata)
            self.assertEqual(metadata["semantic"], "true_means_observed_surface")
            np.testing.assert_array_equal(surface, np.eye(2, dtype=bool)[:, :, None]
                                          & np.eye(2, dtype=bool)[None, :, :])
            # Reusing the computed bounds must produce the same grid.
            np.testing.assert_array_equal(run(xyz, bounds_path, (2, 2, 2), 2), surface)

    def test_xyz_command_exports_separate_flood_filled_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            xyz = root / "shell.xyz"
            shell = np.ones((5, 5, 5), dtype=bool)
            shell[1:4, 1:4, 1:4] = False
            np.savetxt(xyz, np.argwhere(shell)[:, ::-1], fmt="%d")
            surface_path, interior_path = root / "surface.npz", root / "interior.npz"
            args = ["voxelize", "--input", str(xyz), "--output", str(surface_path),
                    "--shape", "5", "5", "5", "--interior-output", str(interior_path)]
            with patch("sys.argv", args), redirect_stdout(StringIO()):
                main()
            surface, _ = load_surface_npz(surface_path)
            interior = load_volume_npz(interior_path)
            np.testing.assert_array_equal(surface, shell)
            np.testing.assert_array_equal(interior.data, ~shell)
            self.assertEqual(interior.open_voxels, 27)
            self.assertEqual(interior.metadata["interior_inference"]["connectivity"], 6)
            self.assertEqual(interior.metadata["validation_status"],
                             "candidate_requires_geometric_validation")

    def test_all_formats_support_progress_flood_fill_and_reproduction(self):
        shell = np.ones((5, 5, 5), dtype=bool)
        shell[1:4, 1:4, 1:4] = False
        points = np.argwhere(shell)[:, ::-1].astype(np.float32)
        for extension in ["xyz", "ply", "f32"]:
            with self.subTest(extension=extension), TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ("shell." + extension)
                if extension == "xyz":
                    np.savetxt(source, points)
                elif extension == "f32":
                    np.column_stack([points, np.zeros((len(points), 4), np.float32)]).tofile(source)
                else:
                    header = (f"ply\nformat ascii 1.0\nelement vertex {len(points)}\n"
                              "property float x\nproperty float y\nproperty float z\nend_header\n")
                    with source.open("w") as stream:
                        stream.write(header)
                        np.savetxt(stream, points)
                output, interior = root / "surface.npz", root / "interior.npz"
                args = ["--input", str(source), "--output", str(output),
                        "--interior-output", str(interior), "--shape", "5", "5", "5",
                        "--batch-size", "64", "--progress-every", "25"]
                with redirect_stdout(StringIO()) as log:
                    main(args)
                for stage in ["Bounds", "Voxelization"]:
                    for count in [25, 50, 75]:
                        self.assertIn(f"[{stage}] Processed {count} points", log.getvalue())
                    self.assertNotIn(f"[{stage}] Processed 100 points", log.getvalue())
                volume = load_volume_npz(interior)
                np.testing.assert_array_equal(volume.data, ~shell)
                receipt = json.loads(output.with_suffix(".run.json").read_text())
                self.assertEqual(receipt["status"], "completed")
                self.assertEqual(receipt["source"]["path"], str(source))
                self.assertEqual(receipt["requested_argv"], args)
                self.assertIn("--bounds", receipt["command_argv"])
                self.assertEqual(len(receipt["bounds_sha256"]), 64)
                self.assertEqual(receipt["software"]["numpy"], np.__version__)
                self.assertEqual(receipt["processing"]["bounds_mode"], "computed")
                self.assertEqual(volume.metadata["processing"]["batch_size"], 64)

    def test_rejects_invalid_configuration_before_reading_cloud(self):
        for extra in [["--progress-every", "-1"], ["--batch-size", "0"],
                      ["--shape", "0", "2", "2"], ["--interior-output", "same.npz"]]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                main(["--input", "missing.xyz", "--output", "same.npz", *extra])

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
        self.assertEqual(metadata["source_ply"], str(ply_path))
        self.assertEqual(metadata["volume_shape_zyx"], [2, 2, 2])
        np.testing.assert_array_equal(
            surface,
            np.array([[[True, False], [False, False]], [[False, False], [False, True]]]),
        )


if __name__ == "__main__":
    unittest.main()
