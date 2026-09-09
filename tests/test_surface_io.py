"""Test persistence dedicated to observed-surface voxel grids."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.datastream.surface_io import load_surface_npz, save_surface_npz


class SurfaceIOTests(unittest.TestCase):
    """Verify surface archives preserve their distinct data contract."""

    def test_round_trips_surface_grid_and_metadata(self) -> None:
        """Restore boolean surface data and reproduction metadata unchanged."""
        surface = np.array([[[True, False], [False, True]]])
        metadata = {
            "semantic": "true_means_observed_surface",
            "volume_shape_zyx": [1, 2, 2],
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "surface.npz"
            save_surface_npz(surface, path, metadata)
            restored_surface, restored_metadata = load_surface_npz(path)

        np.testing.assert_array_equal(restored_surface, surface)
        self.assertEqual(restored_surface.dtype, np.bool_)
        self.assertEqual(restored_metadata, metadata)

    def test_rejects_non_3d_surface_grid_and_wrong_archive_kind(self) -> None:
        """Reject invalid data and archives that do not use the surface format."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "not_surface.npz"
            with self.assertRaisesRegex(ValueError, "3D"):
                save_surface_npz(np.ones((2, 2), dtype=bool), path, {})
            with self.assertRaisesRegex(TypeError, "bool"):
                save_surface_npz(np.ones((1, 1, 1), dtype=np.uint8), path, {})

            np.savez_compressed(path, data=np.ones((1, 1, 1), dtype=np.uint8))
            with self.assertRaisesRegex(ValueError, "surface_voxels"):
                load_surface_npz(path)


if __name__ == "__main__":
    unittest.main()
