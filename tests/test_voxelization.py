"""Test incremental surface voxelization from ZYX point-index batches."""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.core.voxelization import voxelize_surface_zyx


class SurfaceVoxelizationTests(unittest.TestCase):
    """Verify surface marking, batching, and index validation."""

    def test_marks_surface_points_from_multiple_batches(self) -> None:
        """Mark ZYX coordinates once even when a point is repeated."""
        batches = [
            np.array(((0, 1, 2), (2, 0, 1)), dtype=np.intp),
            np.empty((0, 3), dtype=np.intp),
            np.array(((2, 0, 1), (1, 3, 0)), dtype=np.intp),
        ]

        surface = voxelize_surface_zyx(batches, volume_shape=(3, 4, 5))

        expected = np.zeros((3, 4, 5), dtype=bool)
        expected[0, 1, 2] = True
        expected[2, 0, 1] = True
        expected[1, 3, 0] = True
        np.testing.assert_array_equal(surface, expected)
        self.assertEqual(surface.dtype, np.bool_)
        self.assertEqual(surface.shape, (3, 4, 5))

    def test_returns_empty_surface_and_rejects_invalid_indices(self) -> None:
        """Return an empty grid for no points and reject invalid index batches."""
        surface = voxelize_surface_zyx([], volume_shape=(2, 2, 2))
        self.assertFalse(surface.any())

        cases = [
            ([np.zeros((1, 2), dtype=np.intp)], (2, 2, 2), ValueError, "shape"),
            ([np.zeros((1, 3), dtype=np.float32)], (2, 2, 2), TypeError, "integer"),
            ([np.array(((2, 0, 0),), dtype=np.intp)], (2, 2, 2), ValueError, "outside"),
            ([np.zeros((1, 3), dtype=np.intp)], (2, 0, 2), ValueError, "positive"),
        ]
        for batches, shape, error_type, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(error_type, message):
                    voxelize_surface_zyx(batches, shape)


if __name__ == "__main__":
    unittest.main()
