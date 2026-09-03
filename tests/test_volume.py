"""Test the common boolean Volume3D container."""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.core.volume import Volume3D


class Volume3DTests(unittest.TestCase):
    """Verify shape validation, boolean conversion, and helper constructors."""

    def test_converts_data_and_reports_volume_statistics(self) -> None:
        """Convert input to bool while preserving its three-dimensional shape."""
        volume = Volume3D.from_array(np.array([[[0, 2], [1, 0]]]), source="test")

        self.assertEqual(volume.data.dtype, np.bool_)
        self.assertEqual(volume.shape, (1, 2, 2))
        self.assertEqual(volume.open_voxels, 2)
        self.assertEqual(volume.fill_ratio, 0.5)
        self.assertEqual(volume.metadata, {"source": "test"})

    def test_builds_empty_and_full_volumes_and_rejects_non_3d_data(self) -> None:
        """Provide boolean helper constructors and reject arrays without three axes."""
        empty = Volume3D.empty((2, 2, 2), label="empty")
        full = Volume3D.full_open((2, 2, 2))

        self.assertFalse(empty.data.any())
        self.assertEqual(empty.metadata, {"label": "empty"})
        self.assertTrue(full.data.all())
        with self.assertRaisesRegex(ValueError, "3D"):
            Volume3D(np.zeros((2, 2), dtype=bool))


if __name__ == "__main__":
    unittest.main()
