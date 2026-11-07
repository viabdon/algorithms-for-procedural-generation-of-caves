"""Point milestones are independent of source format and batch boundaries."""
import unittest
import numpy as np
from cavegen.datastream.progress import report_point_progress


class PointProgressTests(unittest.TestCase):
    def test_reports_every_milestone_when_a_batch_crosses_many(self):
        batches = [np.zeros((5, 3), np.float32), np.zeros((2, 3), np.float32)]
        counts = []
        result = list(report_point_progress(batches, 2, counts.append))
        self.assertEqual(counts, [2, 4, 6])
        self.assertIs(result[0], batches[0])
        self.assertIs(result[1], batches[1])

    def test_default_million_interval(self):
        counts = []
        # No coordinate storage is needed to exercise point-count milestones.
        list(report_point_progress([np.empty((2000001, 0))], 1000000, counts.append))
        self.assertEqual(counts, [1000000, 2000000])

    def test_disabled_progress_and_invalid_configuration(self):
        batches = [np.zeros((1, 3), np.float32)]
        self.assertEqual(len(list(report_point_progress(batches))), 1)
        for every, callback in [(0, print), (-1, print), (True, print), (1.5, print), (1, None)]:
            with self.subTest(every=every), self.assertRaises(ValueError):
                list(report_point_progress(batches, every, callback))
