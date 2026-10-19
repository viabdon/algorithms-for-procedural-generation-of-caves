"""Public geometry contract for tiled full-extent thickening."""

import unittest

import numpy as np

from cavegen.meshing.full_extent_experiment import sparse_thickened_boundary
from cavegen.meshing.morphological_thickening import boundary_from_occupancy


class SparseThickenedBoundaryTests(unittest.TestCase):
    def test_tiled_boundary_matches_dense_grid_across_tile_seams(self) -> None:
        points = np.array([
            [7.0, 7.0, 7.0], [7.9, 7.0, 7.0], [8.0, 7.0, 7.0],
            [8.1, 7.0, 7.0], [15.9, 8.0, 7.0], [16.0, 8.0, 7.0],
        ])
        for radius in (1, 2):
            with self.subTest(radius=radius):
                sparse, _, metadata = sparse_thickened_boundary(
                    points, voxel_size=0.1, radius_voxels=radius, tile_size=16,
                )
                origin = np.floor(points.min(axis=0) / 0.1) * 0.1 - (radius + 2) * 0.1
                indices = np.floor((points - origin) / 0.1).astype(int)
                shape = tuple(indices.max(axis=0) + radius + 4)
                occupied = np.zeros(shape, dtype=bool)
                occupied[tuple(indices.T)] = True
                dense, _, _ = boundary_from_occupancy(
                    occupied, origin, voxel_size=0.1, radius_voxels=radius,
                )
                sparse_set = {tuple(v) for v in np.round(sparse, 5)}
                dense_set = {tuple(v) for v in np.round(dense, 5)}
                self.assertEqual(sparse_set, dense_set)
                self.assertEqual(metadata["radius_xyz_units"], radius * 0.1)

    def test_rejects_invalid_radius(self) -> None:
        points = np.array([[0., 0., 0.], [1., 1., 1.], [2., 2., 2.]])
        with self.assertRaises(ValueError):
            sparse_thickened_boundary(points, voxel_size=0.1, radius_voxels=0)


if __name__ == "__main__":
    unittest.main()
