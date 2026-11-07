"""Public contracts for streamed XYZ text clouds and format selection."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.datastream.xyz import iter_xyz_xyz
from cavegen.datastream.point_cloud import iter_point_cloud_xyz


class XYZTests(unittest.TestCase):
    def test_streams_whitespace_comments_bom_and_extra_columns(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'cloud.XYZ'
            path.write_text('\ufeff# comment\n\n1 2 3 255 0 0\n4\t5\t6 # point\n-1.5 2e1 .25\n',
                            encoding='utf-8')
            batches = list(iter_point_cloud_xyz(path, 2))
        self.assertEqual([b.shape for b in batches], [(2, 3), (1, 3)])
        self.assertTrue(all(b.dtype == np.float32 for b in batches))
        np.testing.assert_array_equal(np.concatenate(batches),
                                      [[1, 2, 3], [4, 5, 6], [-1.5, 20, .25]])

    def test_batches_remain_independent_as_iteration_advances(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'cloud.xyz'
            path.write_text('1 2 3\n4 5 6\n7 8 9\n')
            iterator = iter_xyz_xyz(path, 1)
            first = next(iterator)
            list(iterator)
            np.testing.assert_array_equal(first, [[1, 2, 3]])

    def test_rejects_bad_records_with_physical_line_number(self):
        for record in ['1 2', 'X Y Z', 'NaN 0 0', '0 inf 0', '1e50 0 0', '1,2,3']:
            with self.subTest(record=record), TemporaryDirectory() as folder:
                path = Path(folder) / 'cloud.xyz'
                path.write_text('# header\n\n' + record + '\n')
                with self.assertRaisesRegex(ValueError, r'cloud.xyz at line 3'):
                    list(iter_xyz_xyz(path, 2))

    def test_yields_first_batch_before_reading_a_later_invalid_record(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'cloud.xyz'
            path.write_text('1 2 3\nnot a point\n')
            iterator = iter_xyz_xyz(path, 1)
            np.testing.assert_array_equal(next(iterator), [[1, 2, 3]])
            with self.assertRaisesRegex(ValueError, 'line 2'):
                next(iterator)

    def test_f32_dispatch_preserves_xyz_columns(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'cloud.f32'
            np.array([[1, 2, 3, 4, 5, 6, 7]], dtype=np.float32).tofile(path)
            batches = list(iter_point_cloud_xyz(path, 1))
            np.testing.assert_array_equal(batches[0], [[1, 2, 3]])

    def test_rejects_empty_cloud_and_invalid_batch_sizes(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'cloud.xyz'
            path.write_text('# comment only\n\n')
            with self.assertRaisesRegex(ValueError, 'no points'):
                list(iter_xyz_xyz(path, 2))
            for size in [0, -1, True, 1.5]:
                with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'positive integer'):
                    list(iter_xyz_xyz(path, size))

    def test_missing_source_and_unsupported_format(self):
        with TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                list(iter_xyz_xyz(Path(folder) / 'missing.xyz', 1))
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                list(iter_point_cloud_xyz(Path(folder) / 'cloud.csv', 1))
