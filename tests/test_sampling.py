"""Test bounded, reproducible reservoir sampling of XYZ point batches."""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.datastream.sampling import reservoir_sample_xyz


class ReservoirSamplingTests(unittest.TestCase):
    """Verify reservoir-sampling behavior and input validation."""

    def test_returns_all_points_when_input_is_smaller_than_limit(self) -> None:
        """Keep every point when the stream has fewer points than the limit."""
        batches = [np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)]

        sample = reservoir_sample_xyz(batches, max_points=4, seed=17)

        np.testing.assert_array_equal(sample, batches[0])
        self.assertEqual(sample.dtype, np.float32)

    def test_returns_reproducible_bounded_sample(self) -> None:
        """Produce the same bounded sample for identical input and seed."""
        points = np.arange(60, dtype=np.float32).reshape(20, 3)
        batches = [points[:7], points[7:13], points[13:]]

        first_sample = reservoir_sample_xyz(batches, max_points=5, seed=42)
        second_sample = reservoir_sample_xyz(batches, max_points=5, seed=42)

        self.assertEqual(first_sample.shape, (5, 3))
        np.testing.assert_array_equal(first_sample, second_sample)
        self.assertTrue(all(any(np.array_equal(point, row) for row in points) for point in first_sample))

    def test_rejects_invalid_batches_and_limits(self) -> None:
        """Reject invalid sample limits and XYZ batch contracts."""
        with self.assertRaisesRegex(ValueError, "max_points"):
            reservoir_sample_xyz([], max_points=0, seed=42)
        with self.assertRaisesRegex(TypeError, "max_points"):
            reservoir_sample_xyz([], max_points=True, seed=42)
        with self.assertRaisesRegex(ValueError, "Batch 0"):
            reservoir_sample_xyz([np.zeros((2, 2), dtype=np.float32)], 2, 42)
        with self.assertRaisesRegex(TypeError, "float32"):
            reservoir_sample_xyz([np.zeros((2, 3), dtype=np.float64)], 2, 42)


if __name__ == "__main__":
    unittest.main()
