"""Verify incremental experiment persistence with real generator outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import yaml

from cavegen.benchmark.records import append_experiment_record
from cavegen.benchmark.run_generation_benchmark import run
from cavegen.core.volume import Volume3D
from cavegen.datastream.voxel_io import load_volume_npz
from cavegen.generators.cellular_automata import generate_cellular_automata
from cavegen.generators.random_walk import generate_random_walk
from cavegen.metrics import evaluate_structure


class ExperimentRecordTests(unittest.TestCase):
    """Preserve rows, identity, schema and missing-value semantics."""

    def test_appends_degenerate_and_valid_results_under_one_header(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "experiments.csv"
            data = np.zeros((3, 3, 3), dtype=bool)
            data[1, 1, 1] = True
            for run_id, volume in (("empty", Volume3D.empty((3, 3, 3))),
                                   ("one", Volume3D(data))):
                append_experiment_record(path, {"run_id": run_id,
                                                **evaluate_structure(volume).to_record()})
            with path.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual([row["run_id"] for row in rows], ["empty", "one"])
            self.assertEqual(rows[0]["dt_mean"], "")
            self.assertEqual(rows[0]["degenerate_reason"], "no_open_voxels")
            self.assertEqual(rows[1]["dt_mean"], "1.0")

    def test_rejects_duplicate_identity_and_incompatible_header_without_writing(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "experiments.csv"
            append_experiment_record(path, {"run_id": "one", "metric": 1.})
            before = path.read_bytes()
            for record, message in (({"run_id": "one", "metric": 2.}, "Duplicate"),
                                    ({"run_id": "two", "other": 2.}, "header")):
                with self.subTest(record=record):
                    with self.assertRaisesRegex(ValueError, message):
                        append_experiment_record(path, record)
                    self.assertEqual(path.read_bytes(), before)

    def test_rejects_missing_identity_and_nonscalar_values(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "experiments.csv"
            with self.assertRaisesRegex(ValueError, "run_id"):
                append_experiment_record(path, {"metric": 1})
            with self.assertRaisesRegex(TypeError, "scalar"):
                append_experiment_record(path, {"run_id": "one", "metric": [1, 2]})
            self.assertFalse(path.exists())

    def test_two_benchmark_invocations_append_reproducible_structures(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "small.yaml"
            config.write_text(yaml.safe_dump({
                "shape": [5, 6, 7], "seeds": [42],
                "algorithms": {"random_walk": {"steps": 12},
                               "cellular_automata": {"iterations": 1}},
                "outputs": {"volumes_dir": str(root / "volumes")},
            }), encoding="utf-8")
            path = root / "experiments.csv"
            run(config, path)
            first_rows = self._read_rows(path)
            archives_before = {row["volume_path"]: Path(row["volume_path"]).read_bytes()
                               for row in first_rows}
            run(config, path)
            rows = self._read_rows(path)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len({row["run_id"] for row in rows}), 4)
            self.assertEqual(len({row["experiment_id"] for row in rows}), 2)
            self.assertEqual(len({row["volume_path"] for row in rows}), 4)
            self.assertEqual(first_rows, rows[:2])
            for path_string, original in archives_before.items():
                self.assertEqual(Path(path_string).read_bytes(), original)
            for row in rows:
                saved = load_volume_npz(row["volume_path"])
                self.assertEqual(saved.shape, (5, 6, 7))
                self.assertEqual(row["axis_order"], "ZYX")
                self.assertEqual(row["backend"], "cpu")
                self.assertEqual(row["repetition"], "0")
                self.assertTrue(row["python_version"])
                params = json.loads(row["parameters_json"])
                self.assertEqual(params["seed"], 42)
                self.assertEqual(params["shape"], [5, 6, 7])
                structural = evaluate_structure(saved).to_record()
                for key, value in structural.items():
                    self.assertEqual(row[key], "" if value is None else str(value))
            for first, second in zip(rows[:2], rows[2:]):
                self.assertEqual(first["algorithm"], second["algorithm"])
                np.testing.assert_array_equal(load_volume_npz(first["volume_path"]).data,
                                              load_volume_npz(second["volume_path"]).data)

    def test_generation_defaults_and_missing_config_shape_use_64_cubed(self) -> None:
        # Cheap generation exercises actual defaults, not signature inspection.
        self.assertEqual(generate_random_walk(seed=0, steps=1).shape, (64, 64, 64))
        self.assertEqual(generate_cellular_automata(seed=0, iterations=0).shape, (64, 64, 64))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "default.yaml"
            config.write_text(yaml.safe_dump({
                "seeds": [0], "algorithms": {"random_walk": {"steps": 1}},
                "outputs": {"volumes_dir": str(root / "volumes")},
            }), encoding="utf-8")
            path = root / "experiments.csv"
            run(config, path)
            row = self._read_rows(path)[0]
            self.assertEqual(row["shape"], "64x64x64")
            self.assertEqual(int(row["total_voxels"]), 64 ** 3)

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))


if __name__ == "__main__":
    unittest.main()
