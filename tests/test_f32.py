"""Test incremental reading and validation of fixed-record F32 point clouds."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.datastream.f32 import count_f32_points, iter_f32_xyz, open_f32_records


class F32ReaderTests(unittest.TestCase):
    """Verify F32 record validation, read-only mapping, and XYZ batches."""

    def test_counts_maps_and_iterates_xyz_records(self) -> None:
        """Read a valid F32 file incrementally while preserving float32 XYZ."""
        records = np.array(
            ((1, 2, 3, 10, 20, 30, 40), (4, 5, 6, 11, 21, 31, 41), (7, 8, 9, 12, 22, 32, 42)),
            dtype=np.float32,
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "points.f32"
            path.write_bytes(records.tobytes())
            point_count = count_f32_points(path)
            mapped = open_f32_records(path)
            batches = list(iter_f32_xyz(path, batch_size=2))

        self.assertEqual(point_count, 3)
        self.assertEqual(mapped.shape, (3, 7))
        self.assertEqual(mapped.mode, "r")
        self.assertEqual([batch.shape for batch in batches], [(2, 3), (1, 3)])
        self.assertTrue(all(batch.dtype == np.float32 for batch in batches))
        np.testing.assert_array_equal(
            np.vstack(batches),
            np.array(((1, 2, 3), (4, 5, 6), (7, 8, 9)), dtype=np.float32),
        )

    def test_rejects_invalid_files_and_batch_sizes(self) -> None:
        """Reject missing, empty, malformed, and improperly batched F32 data."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "points.f32"

            with self.assertRaises(FileNotFoundError):
                count_f32_points(path)

            path.write_bytes(b"")
            self.assertEqual(count_f32_points(path), 0)
            with self.assertRaisesRegex(ValueError, "empty"):
                open_f32_records(path)

            path.write_bytes(b"invalid")
            with self.assertRaisesRegex(ValueError, "multiple"):
                count_f32_points(path)

            valid_record = np.zeros((1, 7), dtype=np.float32)
            path.write_bytes(valid_record.tobytes())
            for batch_size, error_type, message in (
                (0, ValueError, "positive"),
                (True, TypeError, "integer"),
                (1.5, TypeError, "integer"),
            ):
                with self.subTest(batch_size=batch_size):
                    with self.assertRaisesRegex(error_type, message):
                        list(iter_f32_xyz(path, batch_size))


if __name__ == "__main__":
    unittest.main()
