"""Test spatial normalization from XYZ points to ZYX voxel indices."""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.core.normalization import normalize_xyz_to_zyx_indices


class XYZNormalizationTests(unittest.TestCase):
    """Verify spatial mapping, boundary behavior, and input validation."""

    def test_maps_box_extremes_to_zyx_grid_indices(self) -> None:
        """Map known XYZ extrema to the corresponding ZYX volume corners."""
        points = np.array(((0, 0, 0), (10, 5, 2)), dtype=np.float32)
        minimum = np.array((0, 0, 0), dtype=np.float32)
        maximum = np.array((10, 5, 2), dtype=np.float32)

        indices = normalize_xyz_to_zyx_indices(points, minimum, maximum, (3, 6, 11))

        np.testing.assert_array_equal(indices, np.array(((0, 0, 0), (2, 5, 10))))
        self.assertEqual(indices.dtype, np.intp)

    def test_preserves_proportions_and_centers_unused_space(self) -> None:
        """Use one scale and center a smaller source axis inside the grid."""
        points = np.array(((0, 0, 0), (10, 2, 0)), dtype=np.float32)
        minimum = np.array((0, 0, 0), dtype=np.float32)
        maximum = np.array((10, 2, 0), dtype=np.float32)

        indices = normalize_xyz_to_zyx_indices(points, minimum, maximum, (11, 11, 11))

        np.testing.assert_array_equal(indices, np.array(((5, 4, 0), (5, 6, 10))))

    def test_places_degenerate_axes_at_grid_center(self) -> None:
        """Place a flat source axis at the center of its target dimension."""
        points = np.array(((0, 7, 0), (10, 7, 2)), dtype=np.float32)
        minimum = np.array((0, 7, 0), dtype=np.float32)
        maximum = np.array((10, 7, 2), dtype=np.float32)

        indices = normalize_xyz_to_zyx_indices(points, minimum, maximum, (3, 8, 11))

        np.testing.assert_array_equal(indices, np.array(((0, 4, 0), (2, 4, 10))))

    def test_returns_empty_indices_and_rejects_invalid_input(self) -> None:
        """Keep valid empty batches empty and reject violated contracts."""
        minimum = np.zeros(3, dtype=np.float32)
        maximum = np.ones(3, dtype=np.float32)
        empty = normalize_xyz_to_zyx_indices(np.empty((0, 3), dtype=np.float32), minimum, maximum, (2, 2, 2))
        self.assertEqual(empty.shape, (0, 3))
        self.assertEqual(empty.dtype, np.intp)

        cases = [
            (np.zeros((1, 3), dtype=np.float64), minimum, maximum, (2, 2, 2), TypeError, "float32"),
            (np.zeros((1, 2), dtype=np.float32), minimum, maximum, (2, 2, 2), ValueError, "shape"),
            (np.zeros((1, 3), dtype=np.float32), maximum, minimum, (2, 2, 2), ValueError, "less than"),
            (np.array(((2, 0, 0),), dtype=np.float32), minimum, maximum, (2, 2, 2), ValueError, "within"),
            (np.zeros((1, 3), dtype=np.float32), minimum, maximum, (1, 2, 2), ValueError, "at least 2"),
        ]

        for points, lower, upper, shape, error_type, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(error_type, message):
                    normalize_xyz_to_zyx_indices(points, lower, upper, shape)


if __name__ == "__main__":
    unittest.main()
