"""Test exact XYZ bounds calculated from incremental point batches."""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.datastream.bounds import calculate_xyz_bounds


class XYZBoundsTests(unittest.TestCase):
    """Verify global extrema and input validation for XYZ bounds."""

    def test_combines_extrema_from_multiple_batches(self) -> None:
        """Return float32 extrema while ignoring an empty valid batch."""
        batches = [
            np.array([[2, -1, 5], [0, 4, 3]], dtype=np.float32),
            np.empty((0, 3), dtype=np.float32),
            np.array([[-2, 1, 8]], dtype=np.float32),
        ]

        minimum, maximum = calculate_xyz_bounds(batches)

        np.testing.assert_array_equal(minimum, np.array([-2, -1, 3], dtype=np.float32))
        np.testing.assert_array_equal(maximum, np.array([2, 4, 8], dtype=np.float32))
        self.assertEqual(minimum.dtype, np.float32)
        self.assertEqual(maximum.dtype, np.float32)

    def test_rejects_empty_or_invalid_batches(self) -> None:
        """Reject streams without points and batches that violate the contract."""
        cases = [
            ([], ValueError, "no points"),
            (["not an array"], TypeError, "expected np.ndarray"),
            ([np.zeros((2, 2), dtype=np.float32)], ValueError, "shape"),
            ([np.zeros((2, 3), dtype=np.float64)], TypeError, "float32"),
            ([np.array([[np.nan, 0, 0]], dtype=np.float32)], ValueError, "non-finite"),
        ]

        for batches, error_type, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(error_type, message):
                    calculate_xyz_bounds(batches)


if __name__ == "__main__":
    unittest.main()
