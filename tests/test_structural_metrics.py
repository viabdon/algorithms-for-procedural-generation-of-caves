"""Verify structural contracts using hand-built caves and independent geometry."""

from __future__ import annotations

import csv
from dataclasses import FrozenInstanceError
from io import StringIO
import itertools
import json
import unittest

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.metrics import evaluate_structure
from cavegen.metrics.connectivity import (
    connected_components,
    largest_component,
    largest_component_ratio,
)
from cavegen.metrics.morphology import distance_transform_stats, open_ratio
from cavegen.metrics.validation import validate_connectivity, validate_spacing, validate_volume


def reference_distances(data: np.ndarray, spacing: tuple[float, float, float]) -> list[float]:
    """Compute nearest-solid distances by enumeration, without EDT or padding."""
    solid = [
        point
        for point in itertools.product(*(range(-1, size + 1) for size in data.shape))
        if any(index < 0 or index >= size for index, size in zip(point, data.shape))
        or not data[point]
    ]
    return [
        min(
            sum(((int(p) - q) * step) ** 2 for p, q, step in zip(point, other, spacing))
            ** 0.5
            for other in solid
        )
        for point in np.argwhere(data)
    ]


class StructuralValidationTests(unittest.TestCase):
    """Reject invalid measurement settings, including on degenerate inputs."""

    def test_rejects_wrong_volume_type_dtype_rank_and_empty_axes(self) -> None:
        cases = [
            ([[[True]]], TypeError, "numpy.ndarray"),
            (np.ones((2, 2, 2), dtype=np.uint8), TypeError, "bool"),
            (np.ones((2, 2, 2), dtype=float), TypeError, "bool"),
            (np.ones((2, 2), dtype=bool), ValueError, "3D"),
            (np.ones((0, 2, 3), dtype=bool), ValueError, "nonempty"),
            (np.ones((2, 0, 3), dtype=bool), ValueError, "nonempty"),
        ]
        for value, error, message in cases:
            for function in (validate_volume, connected_components, largest_component,
                             largest_component_ratio, open_ratio, distance_transform_stats):
                with self.subTest(function=function.__name__, shape=getattr(value, "shape", None)):
                    with self.assertRaisesRegex(error, message):
                        function(value)
        with self.assertRaisesRegex(TypeError, "Volume3D"):
            evaluate_structure(np.zeros((3, 3, 3), dtype=bool))

    def test_rejects_invalid_connectivity_even_for_all_solid(self) -> None:
        data = np.zeros((3, 3, 3), dtype=bool)
        for value in (0, 1, 18, -6, 6.0, True, np.bool_(False), "6", None):
            expected = ValueError if type(value) is int else TypeError
            for function in (connected_components, largest_component, largest_component_ratio):
                with self.subTest(function=function.__name__, connectivity=value):
                    with self.assertRaisesRegex(expected, "connectivity"):
                        function(data, value)
            with self.assertRaisesRegex(expected, "connectivity"):
                evaluate_structure(Volume3D(data), connectivity=value)
        self.assertEqual(validate_connectivity(np.int64(26)), 26)

    def test_rejects_invalid_spacing_before_degenerate_shortcut(self) -> None:
        cases = [
            ((0, 1, 1), ValueError), ((-1, 1, 1), ValueError),
            ((np.nan, 1, 1), ValueError), ((np.inf, 1, 1), ValueError),
            ((1, 1), ValueError), ((1, 1, 1, 1), ValueError),
            (((1, 1, 1),), ValueError), (1, TypeError), ("111", TypeError),
            ((True, 1, 1), TypeError), (("1", 1, 1), TypeError),
            ((1j, 1, 1), TypeError),
        ]
        for spacing, error in cases:
            with self.subTest(spacing=spacing):
                with self.assertRaisesRegex(error, "spacing_zyx"):
                    validate_spacing(spacing)
                with self.assertRaisesRegex(error, "spacing_zyx"):
                    distance_transform_stats(np.zeros((2, 2, 2), dtype=bool), spacing_zyx=spacing)
                with self.assertRaisesRegex(error, "spacing_zyx"):
                    evaluate_structure(Volume3D.full_open((2, 2, 2)), spacing_zyx=spacing)
        self.assertEqual(validate_spacing(np.array([2, 3, 4], dtype=np.float32)), (2., 3., 4.))


class ConnectivityMetricTests(unittest.TestCase):
    """Measure reachable open space under an explicit digital neighborhood."""

    def test_face_neighbors_form_one_component(self) -> None:
        data = np.zeros((4, 4, 4), dtype=bool)
        data[1, 1, 1:3] = True
        labels, count = connected_components(data)
        self.assertEqual(count, 1)
        self.assertTrue((labels[data] > 0).all())
        self.assertTrue((labels[~data] == 0).all())
        self.assertEqual(largest_component_ratio(data), 1.)

    def test_edge_and_corner_contacts_depend_on_neighborhood(self) -> None:
        for other in ((1, 2, 2), (2, 2, 2)):
            data = np.zeros((4, 4, 4), dtype=bool)
            data[1, 1, 1] = data[other] = True
            for connectivity, expected in ((6, 2), (26, 1)):
                with self.subTest(other=other, connectivity=connectivity):
                    result = evaluate_structure(Volume3D(data), connectivity=connectivity)
                    self.assertEqual(result.component_count, expected)
                    self.assertEqual(result.largest_component_ratio, 1 / expected)

    def test_two_unequal_components_use_open_voxel_denominator(self) -> None:
        data = np.zeros((5, 5, 5), dtype=bool)
        data[1, 1, 1:4] = True
        data[3, 3, 3] = True
        result = evaluate_structure(Volume3D(data))
        self.assertEqual(result.component_count, 2)
        self.assertEqual(result.largest_component_voxels, 3)
        self.assertEqual(result.largest_component_ratio, 3 / 4)
        self.assertEqual(result.open_ratio, 4 / 125)
        self.assertFalse(result.is_degenerate)
        expected = np.zeros_like(data)
        expected[1, 1, 1:4] = True
        np.testing.assert_array_equal(largest_component(data), expected)

    def test_boundaries_do_not_wrap_and_ties_are_deterministic(self) -> None:
        data = np.zeros((3, 3, 5), dtype=bool)
        data[1, 1, 0] = data[1, 1, -1] = True
        for connectivity in (6, 26):
            self.assertEqual(connected_components(data, connectivity)[1], 2)
            selected = largest_component(data, connectivity)
            self.assertEqual(int(selected.sum()), 1)
            self.assertTrue(selected[1, 1, 0])


class DistanceMetricTests(unittest.TestCase):
    """Check distances in voxel and anisotropic units against known geometry."""

    def test_open_cube_has_known_center_mean_and_median(self) -> None:
        data = np.zeros((5, 5, 5), dtype=bool)
        data[1:4, 1:4, 1:4] = True
        stats = distance_transform_stats(data)
        self.assertAlmostEqual(stats["dt_mean"], 28 / 27)
        self.assertEqual(stats["dt_median"], 1.)
        self.assertEqual(stats["dt_max"], 2.)

    def test_single_voxel_and_thin_straight_tunnel(self) -> None:
        for count in (1, 5):
            data = np.zeros((7, 3, 3), dtype=bool)
            data[1:count + 1, 1, 1] = True
            result = evaluate_structure(Volume3D(data))
            self.assertEqual(result.open_voxels, count)
            self.assertEqual(result.component_count, 1)
            self.assertEqual(result.distance_mean, 1.)
            self.assertEqual(result.distance_median, 1.)
            self.assertEqual(result.distance_max, 1.)

    def test_matches_independent_exhaustive_distances_with_solid_exterior(self) -> None:
        rng = np.random.default_rng(503)
        mixed = rng.random((3, 4, 5)) < .7
        near_full = np.ones((3, 4, 5), dtype=bool)
        near_full[0, 0, 0] = False
        for data in (mixed, near_full):
            for spacing in ((1., 1., 1.), (2., 3., 5.)):
                expected = reference_distances(data, spacing)
                actual = distance_transform_stats(data, spacing_zyx=spacing)
                with self.subTest(spacing=spacing, open_count=int(data.sum())):
                    self.assertAlmostEqual(actual["dt_mean"], float(np.mean(expected)))
                    self.assertAlmostEqual(actual["dt_median"], float(np.median(expected)))
                    self.assertAlmostEqual(actual["dt_max"], max(expected))

    def test_spacing_follows_zyx_and_euclidean_diagonals(self) -> None:
        # Open voxel and its immediate solid neighbors: closest face is X at 2.
        data = np.zeros((3, 3, 3), dtype=bool)
        data[1, 1, 1] = True
        self.assertEqual(distance_transform_stats(data, spacing_zyx=(7, 5, 2))["dt_max"], 2.)
        for axis, expected in enumerate((7., 5., 2.)):
            slab = np.zeros((9, 9, 9), dtype=bool)
            section = [slice(None)] * 3
            section[axis] = 4
            slab[tuple(section)] = True
            self.assertEqual(distance_transform_stats(slab, spacing_zyx=(7, 5, 2))["dt_max"],
                             expected)
        # Single internal solid: include the open diagonal, bounded by exterior.
        data = np.ones((5, 5, 5), dtype=bool)
        data[2, 2, 2] = False
        expected = reference_distances(data, (1., 1., 1.))
        self.assertAlmostEqual(distance_transform_stats(data)["dt_max"], max(expected))
        self.assertIn(2 ** .5, expected)

    def test_touching_exterior_uses_centers_without_half_voxel_correction(self) -> None:
        data = np.ones((1, 3, 4), dtype=bool)
        data[0, 0, 0] = False
        self.assertEqual(distance_transform_stats(data),
                         {"dt_mean": 1., "dt_median": 1., "dt_max": 1.})


class StructuralResultTests(unittest.TestCase):
    """Verify degenerate contracts, repeatability and a flat serialization."""

    def test_all_solid_and_all_open_are_explicitly_degenerate(self) -> None:
        for full, reason in ((False, "no_open_voxels"), (True, "no_solid_voxels")):
            volume = Volume3D(np.full((3, 4, 5), full, dtype=bool))
            result = evaluate_structure(volume)
            self.assertEqual(result.total_voxels, 60)
            self.assertEqual(result.open_voxels, 60 if full else 0)
            self.assertEqual(result.open_ratio, float(full))
            self.assertEqual(result.component_count, int(full))
            self.assertEqual(result.largest_component_voxels, 60 if full else 0)
            self.assertEqual(result.largest_component_ratio, float(full))
            self.assertTrue(result.is_degenerate)
            self.assertEqual(result.degenerate_reason, reason)
            self.assertIsNone(result.distance_mean)
            self.assertIsNone(result.distance_median)
            self.assertIsNone(result.distance_max)
            self.assertEqual(distance_transform_stats(volume.data),
                             {"dt_mean": None, "dt_median": None, "dt_max": None})

    def test_repeatable_on_readonly_view_and_does_not_mutate_metadata(self) -> None:
        base = np.random.default_rng(42).random((6, 7, 8)) < .4
        view = base[::-1, :, ::2]
        view.setflags(write=False)
        volume = Volume3D(view, metadata={"seed": 42})
        before = base.copy()
        state_before = np.random.get_state()
        first = evaluate_structure(volume)
        second = evaluate_structure(volume)
        self.assertEqual(first, second)
        self.assertIs(validate_volume(view), view)
        np.testing.assert_array_equal(base, before)
        self.assertEqual(volume.metadata, {"seed": 42})
        state_after = np.random.get_state()
        np.testing.assert_array_equal(state_before[1], state_after[1])
        self.assertEqual(state_before[2:], state_after[2:])
        with self.assertRaises(FrozenInstanceError):
            first.open_voxels = 0

    def test_flat_record_preserves_units_nulls_and_column_order(self) -> None:
        result = evaluate_structure(Volume3D.empty((2, 3, 4)))
        record = result.to_record()
        self.assertEqual(record["structural_schema_version"], "structural-v1")
        self.assertEqual(record["distance_unit"], "voxel")
        self.assertEqual(record["axis_order"], "ZYX")
        self.assertEqual(record["exterior_policy"], "solid")
        self.assertEqual(record["distance_reference"], "voxel_centers")
        self.assertIsNone(json.loads(json.dumps(record, allow_nan=False))["dt_max"])
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(record))
        writer.writeheader()
        writer.writerow(record)
        buffer.seek(0)
        self.assertEqual(next(csv.DictReader(buffer))["dt_max"], "")
        scaled = evaluate_structure(Volume3D.full_open((3, 3, 3)), spacing_zyx=(2, 3, 4))
        self.assertEqual(scaled.to_record()["distance_unit"], "spacing_unit")
        self.assertEqual(list(record), list(scaled.to_record()))


if __name__ == "__main__":
    unittest.main()
