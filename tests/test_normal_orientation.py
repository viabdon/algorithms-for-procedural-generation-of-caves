"""Public contracts of branch association, sign review, and manual correction."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from cavegen.meshing.normal_orientation import (
    Parameters,
    apply_manual_corrections,
    associate_points,
    graph_sha256,
    load_orientation,
    orient_from_references,
    points_sha256,
    prepare,
    save_orientation,
    split_branches,
)


def tube_sample() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.arange(4, dtype=float)
    angles = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    points = np.asarray([[a, np.cos(t), np.sin(t)] for a in x for t in angles])
    inward = -np.column_stack((np.zeros(len(points)), points[:, 1], points[:, 2]))
    nodes = np.column_stack((x, np.zeros(len(x)), np.zeros(len(x))))
    edges = np.column_stack((np.arange(3), np.arange(1, 4)))
    return points, inward, nodes, edges


class NormalOrientationTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("open3d"), "Open3D extra is optional")
    def test_prepare_requires_explicitly_validated_references(self) -> None:
        points, inward, nodes, edges = tube_sample()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sample, graph = root / "sample.npz", root / "graph.npz"
            np.savez(sample, points_xyz=points)
            np.savez(graph, nodes_xyz=nodes, edges=edges)
            reference = root / "references.json"
            record = {"graph_sha256": graph_sha256(nodes, edges),
                      "references": [{"node_index": 0, "validated_interior": False}]}
            reference.write_text(json.dumps(record))
            with patch("cavegen.meshing.normal_orientation.estimate_baseline_normals",
                       return_value=inward):
                first = prepare(sample, graph, root / "first.npz", reference_path=reference)
            self.assertEqual(first["uncertain_count"], len(points))
            self.assertEqual(first["validated_reference_node_indices"], [])
            record["references"][0]["node_index"] = len(nodes)
            reference.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "valid node index"):
                prepare(sample, graph, root / "invalid-node.npz", reference_path=reference)
            record["references"][0]["node_index"] = 0
            record["graph_sha256"] = "wrong"
            reference.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "different centreline graph"):
                prepare(sample, graph, root / "wrong.npz", reference_path=reference)

    def test_short_real_branch_survives_graph_split(self) -> None:
        nodes = np.asarray([[0, 0, 0], [-2, 0, 0], [2, 0, 0], [0, 0.38, 0]])
        edges = np.asarray([[0, 1], [0, 2], [0, 3]])
        branches, junctions = split_branches(nodes, edges)
        self.assertEqual(len(branches), 3)
        np.testing.assert_array_equal(junctions, [0])
        self.assertTrue(any(np.array_equal(branch.nodes, [0, 3]) for branch in branches))

    def test_branch_ambiguity_retains_two_candidates(self) -> None:
        nodes = np.asarray([[0, 0, 0], [2, 0, 0], [0, 2, 0], [-2, 0, 0]], dtype=float)
        edges = np.asarray([[0, 1], [0, 2], [0, 3]])
        points = np.asarray([[1, 1, 0], [0, 1, 0], [1, 0, 0], [-1, 0, 0],
                             [1.1, 0.9, 0], [0.9, 1.1, 0]], dtype=float)
        result = associate_points(points, nodes, edges, params=Parameters(max_branch_cost=10))
        self.assertTrue(result["branch_ambiguous"][0])
        self.assertTrue(result["near_junction"][1])
        self.assertNotEqual(result["candidate_branches"][0, 0], result["candidate_branches"][0, 1])
        self.assertGreaterEqual(result["candidate_branches"][0].min(), 0)

    def test_validated_tube_references_flip_inward_normals_by_patch(self) -> None:
        points, inward, nodes, edges = tube_sample()
        result = orient_from_references(
            points, inward, nodes, edges, [0, 1, 2, 3],
            params=Parameters(min_patch_votes=1, max_reference_span_factor=10,
                              max_surface_variation=0.2),
        )
        outward = -inward
        self.assertLess(np.count_nonzero(result["uncertain_mask"]), len(points) // 5)
        confident = ~result["uncertain_mask"]
        self.assertTrue(np.all(np.einsum("ij,ij->i", result["oriented_normals_xyz"][confident],
                                            outward[confident]) > 0.9))
        self.assertEqual(len(result["uncertain_indices"]), np.count_nonzero(result["uncertain_mask"]))

    def test_missing_references_keep_every_sign_uncertain(self) -> None:
        points, inward, nodes, edges = tube_sample()
        result = orient_from_references(points, inward, nodes, edges, [])
        self.assertTrue(result["uncertain_mask"].all())
        np.testing.assert_array_equal(result["uncertain_indices"], np.arange(len(points)))

    def test_distant_points_do_not_inherit_sign_from_one_end_of_a_patch(self) -> None:
        x = np.linspace(0, 4, 21)
        y = np.linspace(-0.4, 0.4, 5)
        points = np.asarray([[a, b, 1] for a in x for b in y])
        inward = np.tile([0., 0., -1.], (len(points), 1))
        nodes = np.array([[0., 0., 0.], [4., 0., 0.]])
        result = orient_from_references(
            points, inward, nodes, np.array([[0, 1]]), [0],
            params=Parameters(min_patch_votes=1, max_reference_span_factor=1),
        )
        near = points[:, 0] < 0.4
        far = points[:, 0] > 3
        self.assertTrue(np.any(~result["uncertain_mask"][near]))
        self.assertTrue(result["uncertain_mask"][far].all())
        np.testing.assert_array_equal(result["oriented_normals_xyz"][far], inward[far])

    def test_review_csv_identifies_points_and_applies_only_explicit_decisions(self) -> None:
        points, inward, nodes, edges = tube_sample()
        result = orient_from_references(points, inward, nodes, edges, [])
        with TemporaryDirectory() as directory:
            source = Path(directory) / "orientation.npz"
            corrected = Path(directory) / "corrected.npz"
            report = save_orientation(source, result, {"graph_sha256": graph_sha256(nodes, edges)})
            self.assertEqual(report["uncertain_count"], len(points))
            self.assertEqual(report["point_sha256"], points_sha256(points))
            loaded = load_orientation(source)
            np.testing.assert_array_equal(loaded["uncertain_indices"], np.arange(len(points)))
            csv_path = source.with_suffix(".uncertain.csv")
            lines = csv_path.read_text(encoding="utf-8").splitlines()
            self.assertIn("review_sha256=", lines[0])
            rows = list(csv.DictReader(lines[1:]))
            self.assertEqual([int(row["point_index"]) for row in rows], list(range(len(points))))
            rows[0]["action"] = "flip"
            rows[1]["action"] = "keep"
            rows[0]["point_index"] = "3"
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(lines[0] + "\n")
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "coordinates or normal differ"):
                apply_manual_corrections(source, csv_path, corrected)
            rows[0]["point_index"] = "0"
            rows[2]["normal_x"] = "999"
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(lines[0] + "\n")
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "coordinates or normal differ"):
                apply_manual_corrections(source, csv_path, corrected)
            rows[2]["normal_x"] = str(result["oriented_normals_xyz"][2, 0])
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(lines[0] + "\n")
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows[:-1])
            with self.assertRaisesRegex(ValueError, "every uncertain point"):
                apply_manual_corrections(source, csv_path, corrected)
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(lines[0] + "\n")
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "new output path"):
                apply_manual_corrections(source, csv_path, source)
            revised = apply_manual_corrections(source, csv_path, corrected)
            self.assertEqual(revised["uncertain_count"], len(points) - 2)
            updated = load_orientation(corrected)
            np.testing.assert_allclose(updated["oriented_normals_xyz"][0], -result["oriented_normals_xyz"][0])
            np.testing.assert_allclose(updated["oriented_normals_xyz"][1], result["oriented_normals_xyz"][1])
            np.testing.assert_array_equal(updated["manual_mask"][:3], [True, True, False])
            with self.assertRaisesRegex(ValueError, "different orientation review"):
                apply_manual_corrections(corrected, csv_path, Path(directory) / "wrong.npz")


if __name__ == "__main__":
    unittest.main()
