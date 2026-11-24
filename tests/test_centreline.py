"""Exercise centreline estimation independently of the point-cloud format."""

from importlib.util import find_spec
import unittest

import numpy as np

from cavegen.tools.centreline import ExtractionSettings, estimate_centreline


@unittest.skipUnless(find_spec("robust_laplacian"), "extra centreline não instalado")
class CentrelineTests(unittest.TestCase):
    def test_recovers_original_xyz_from_local_batches(self):
        angles = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        stations, theta = np.meshgrid(np.linspace(0, 24, 241), angles)
        points = np.column_stack((
            stations.ravel(), .8 * np.cos(theta.ravel()), .8 * np.sin(theta.ravel()),
        ))
        offset = np.array([700_000, 9_000_000, 500])
        batches = (points[start:start + 1300] for start in range(0, len(points), 1300))
        nodes, edges, metadata = estimate_centreline(
            batches, ExtractionSettings(), source_offset=offset,
        )

        local_nodes = nodes - offset
        self.assertGreater(np.ptp(local_nodes[:, 0]), 15)
        self.assertLess(np.linalg.norm(local_nodes[:, 1:], axis=1).max(), .6)
        self.assertEqual(len(edges), len(nodes) - 1)
        self.assertEqual(metadata["points_read"], len(points))

    def test_rejects_invalid_xyz_batches(self):
        with self.assertRaisesRegex(ValueError, "lote.*XYZ"):
            estimate_centreline([np.zeros((32, 2))], ExtractionSettings())
