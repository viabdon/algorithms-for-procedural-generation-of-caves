"""Contracts for scaled, streamed LAS coordinates, independent of private layout."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import laspy
import numpy as np

from cavegen.datastream.las import iter_las_xyz, read_las_metadata
from cavegen.datastream.point_cloud import iter_point_cloud_xyz


class LasReaderTests(unittest.TestCase):
    def write_cloud(self, path, point_format=3, version='1.2', scales=None, offsets=None):
        header = laspy.LasHeader(point_format=point_format, version=version)
        header.scales = np.array([.01, .1, .001] if scales is None else scales)
        header.offsets = np.array([1000., -200., 50.] if offsets is None else offsets)
        cloud = laspy.LasData(header)
        cloud.X = [1, 100, -20]
        cloud.Y = [2, -10, 30]
        cloud.Z = [3, 400, -500]
        cloud.intensity = [10, 20, 30]
        cloud.write(path)
        with np.errstate(over="ignore"):
            return np.column_stack((cloud.x, cloud.y, cloud.z)).astype(np.float32)

    def test_scaled_coordinates_and_partial_batches_for_las12_and_las14(self):
        for point_format, version in [(0, '1.2'), (3, '1.2'), (6, '1.4')]:
            with self.subTest(version=version, point_format=point_format), TemporaryDirectory() as d:
                path = Path(d) / 'cloud.LAS'
                expected = self.write_cloud(path, point_format, version)
                batches = list(iter_point_cloud_xyz(path, 2))
                self.assertEqual([len(b) for b in batches], [2, 1])
                self.assertTrue(all(b.shape[1] == 3 and b.dtype == np.float32 for b in batches))
                np.testing.assert_array_equal(np.concatenate(batches), expected)
                metadata = read_las_metadata(path)
                self.assertEqual(metadata['version'], version)
                self.assertEqual(metadata['point_count'], 3)
                self.assertEqual(metadata['scales_xyz'], [.01, .1, .001])
                self.assertEqual(metadata['offsets_xyz'], [1000., -200., 50.])

    def test_retained_batches_are_independent(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'cloud.las'
            expected = self.write_cloud(path)
            iterator = iter_las_xyz(path, 1)
            first = next(iterator)
            list(iterator)
            np.testing.assert_array_equal(first[0], expected[0])

    def test_empty_malformed_missing_and_truncated_clouds(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'cloud.las'
            with self.assertRaises(FileNotFoundError):
                list(iter_las_xyz(path, 1))
            laspy.LasData(laspy.LasHeader(point_format=0, version='1.2')).write(path)
            with self.assertRaisesRegex(ValueError, 'no points'):
                list(iter_las_xyz(path, 1))
            path.write_bytes(b'not a LAS file')
            with self.assertRaisesRegex(ValueError, 'Invalid LAS'):
                list(iter_las_xyz(path, 1))
            self.write_cloud(path)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, 'Truncated LAS'):
                list(iter_las_xyz(path, 2))

    def test_rejects_invalid_batch_sizes_and_coordinate_scales(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'cloud.las'
            self.write_cloud(path)
            for size in [0, -1, True, 1.5]:
                with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'positive integer'):
                    list(iter_las_xyz(path, size))
            self.write_cloud(path, scales=[-1, 1, 1])
            with self.assertRaisesRegex(ValueError, 'scales'):
                list(iter_las_xyz(path, 1))
            self.write_cloud(path, scales=[1e40, 1, 1], offsets=[0, 0, 0])
            with self.assertRaisesRegex(ValueError, 'finite float32'):
                list(iter_las_xyz(path, 1))
