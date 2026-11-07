"""Behavioral tests for candidate interiors inferred by flood fill."""
import unittest
import numpy as np
from cavegen.core.surface_filling import (
    EXTERIOR, SURFACE, INTERIOR, classify_surface_by_flood_fill,
)


class SurfaceFillingTests(unittest.TestCase):
    def shell(self):
        surface = np.zeros((7, 7, 7), dtype=bool)
        surface[1:6, 1:6, 1:6] = True
        surface[2:5, 2:5, 2:5] = False
        return surface

    def test_closed_shell_separates_air_surface_and_exterior(self):
        surface = self.shell()
        original = surface.copy()
        labels = classify_surface_by_flood_fill(surface)
        self.assertEqual(labels.dtype, np.uint8)
        self.assertEqual(int((labels == INTERIOR).sum()), 27)
        self.assertEqual(labels[0, 0, 0], EXTERIOR)
        self.assertEqual(labels[1, 3, 3], SURFACE)
        np.testing.assert_array_equal(surface, original)

    def test_open_entrance_leaks_and_is_not_automatically_closed(self):
        surface = self.shell()
        surface[1, 3, 3] = False
        labels = classify_surface_by_flood_fill(surface)
        self.assertFalse((labels == INTERIOR).any())
        self.assertEqual(labels[3, 3, 3], EXTERIOR)

    def test_diagonal_gap_does_not_leak_under_six_connectivity(self):
        surface = self.shell()
        surface[1, 1, 1] = False
        self.assertEqual(int((classify_surface_by_flood_fill(surface) == INTERIOR).sum()), 27)

    def test_full_empty_and_thick_surface_are_not_cave_air(self):
        for value in [False, True]:
            surface = np.full((5, 5, 5), value, dtype=bool)
            labels = classify_surface_by_flood_fill(surface)
            self.assertFalse((labels == INTERIOR).any())
        surface = np.ones((5, 5, 5), dtype=bool)
        surface[2, 2, 2] = False
        labels = classify_surface_by_flood_fill(surface)
        self.assertEqual(int((labels == INTERIOR).sum()), 1)
        np.testing.assert_array_equal(labels == SURFACE, surface)

    def test_invalid_grid_contract(self):
        for surface, exception in [(np.zeros((2, 2), bool), ValueError),
                                   (np.zeros((0, 2, 2), bool), ValueError),
                                   (np.zeros((2, 2, 2)), TypeError), ([], TypeError)]:
            with self.subTest(surface=surface), self.assertRaises(exception):
                classify_surface_by_flood_fill(surface)
