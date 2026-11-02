"""Exercise public terminal workflows with scripted input and real archives."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import yaml

from cavegen.benchmark.run_generation_benchmark import run_configuration
from cavegen.datastream.surface_io import save_surface_npz
from cavegen.datastream.voxel_io import load_volume_npz
from cavegen.menu import run_menu


class TerminalMenuTests(unittest.TestCase):
    """Test user-visible effects and data preservation, rather than private helpers."""

    def _menu(self, root: Path, answers: list[str | BaseException]) -> str:
        pending = iter(answers)
        messages: list[str] = []

        def read(prompt: str) -> str:
            messages.append(prompt)
            answer = next(pending, EOFError())
            if isinstance(answer, BaseException):
                raise answer
            return answer

        run_menu(read, messages.append, csv_path=root / "experiments.csv",
                 volumes_dir=root / "volumes")
        return "\n".join(messages)

    @staticmethod
    def _rows(root: Path) -> list[dict[str, str]]:
        with (root / "experiments.csv").open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def test_invalid_option_help_and_exit_do_not_create_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            text = self._menu(root, ["9", "6", "0"])
            self.assertIn("Opção inválida", text)
            self.assertIn("Glossário", text)
            self.assertEqual(list(root.iterdir()), [])

    def test_generates_random_walk_then_reevaluates_in_the_same_csv(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self._menu(root, ["1", "1", "42", "10", "0", "0"])
            original = self._rows(root)[0]
            source = Path(original["volume_path"])
            before = source.read_bytes()
            self.assertEqual(load_volume_npz(source).shape, (64, 64, 64))
            params = json.loads(original["parameters_json"])
            self.assertEqual(params["seed"], 42)
            self.assertEqual(params["steps"], 10)
            self.assertEqual(params["brush_radius"], 0)

            text = self._menu(root, ["3", "1", "18", "26", "nan 1 1", "2 3 4", "0"])
            rows = self._rows(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], original)
            self.assertEqual(source.read_bytes(), before)
            second = rows[1]
            self.assertEqual(second["variant"], "structural_evaluation")
            self.assertEqual(second["seed"], "42")
            self.assertEqual(second["volume_path"], str(source))
            self.assertEqual(second["connectivity"], "26")
            self.assertEqual(second["distance_unit"], "spacing_unit")
            self.assertEqual(second["spacing_z"], "2.0")
            self.assertEqual(second["spacing_y"], "3.0")
            self.assertEqual(second["spacing_x"], "4.0")
            self.assertEqual(second["open_voxels"], original["open_voxels"])
            self.assertEqual(second["elapsed_seconds"], "")
            self.assertEqual(second["peak_rss_bytes"], "")
            self.assertEqual(second["rss_sampling_interval_seconds"], "")
            self.assertNotEqual(second["run_id"], original["run_id"])
            self.assertIn("permitidas são 6 e 26", text)
            self.assertIn("positivos e finitos", text)

    def test_ca_retries_probability_and_keeps_effective_parameters(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            text = self._menu(root, ["1", "2", "", "nan", "0.5", "0", "13", "0"])
            row = self._rows(root)[0]
            params = json.loads(row["parameters_json"])
            self.assertEqual(row["algorithm"], "cellular_automata")
            self.assertEqual(params["initial_open_probability"], .5)
            self.assertEqual(params["iterations"], 0)
            self.assertTrue(params["keep_border_solid"])
            self.assertEqual(row["shape"], "64x64x64")
            self.assertIn("número finito", text)

    def test_executes_yaml_and_reports_each_completed_seed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "small experiment.yaml"
            config_path.write_text(yaml.safe_dump({
                "shape": [5, 6, 7], "seeds": [8, 9],
                "algorithms": {"random_walk": {"steps": 1}},
                "outputs": {"volumes_dir": str(root / "yaml volumes")},
            }), encoding="utf-8")
            text = self._menu(root, ["2", f'"{config_path}"', "", "0"])
            rows = self._rows(root)
            self.assertEqual([row["seed"] for row in rows], ["8", "9"])
            self.assertEqual(text.count("Salvo:"), 2)
            self.assertTrue(all(row["shape"] == "5x6x7" for row in rows))
            self.assertTrue(all(row["config_path"] == str(config_path) for row in rows))
            self.assertTrue(all(Path(row["volume_path"]).is_file() for row in rows))

    def test_can_cancel_yaml_before_generation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "small.yaml"
            config.write_text("shape: [64, 64, 64]\n", encoding="utf-8")
            text = self._menu(root, ["2", str(config), "n", "0"])
            self.assertIn("Execução cancelada", text)
            self.assertFalse((root / "experiments.csv").exists())
            self.assertFalse((root / "volumes").exists())

    def test_lists_only_requested_recent_rows_without_writes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "experiments.csv"
            run_configuration({
                "shape": [5, 5, 5], "seeds": [0, 1, 2],
                "algorithms": {"random_walk": {"steps": 1}},
                "outputs": {"volumes_dir": str(root / "volumes")},
            }, path)
            before = path.read_bytes()
            text = self._menu(root, ["4", "2", "0"])
            self.assertIn("seed=1", text)
            self.assertIn("seed=2", text)
            self.assertNotIn("seed=0", text)
            self.assertEqual(path.read_bytes(), before)

    def test_changes_destinations_for_interactive_generation_only(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "new location" / "all.csv"
            volumes = root / "new volumes"
            self._menu(root, ["5", str(csv_path), str(volumes),
                              "1", "1", "0", "1", "0", "0"])
            self.assertFalse((root / "experiments.csv").exists())
            self.assertFalse((root / "volumes").exists())
            with csv_path.open(encoding="utf-8", newline="") as file:
                row = next(csv.DictReader(file))
            self.assertTrue(Path(row["volume_path"]).is_relative_to(volumes))

    def test_missing_and_surface_archives_return_to_menu_without_csv_writes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "surface.npz"
            save_surface_npz(np.zeros((3, 3, 3), dtype=bool), source, {})
            malformed = root / "invalid_metadata.npz"
            np.savez_compressed(malformed, data=np.zeros((3, 3, 3), dtype=bool), metadata="[]")
            before = source.read_bytes()
            for path in (root / "missing.npz", source, malformed):
                with self.subTest(path=path):
                    text = self._menu(root, ["3", str(path), "", "", "0"])
                    self.assertIn("Não foi possível", text)
                    self.assertIn(str(path), text)
                    self.assertFalse((root / "experiments.csv").exists())
            self.assertEqual(source.read_bytes(), before)

    def test_cancel_keyboard_interrupt_and_eof_leave_no_partial_outputs(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for answers in (["1", ":voltar", "0"], ["1", KeyboardInterrupt(), "0"],
                            ["1", EOFError()], [EOFError()]):
                with self.subTest(answers=answers):
                    text = self._menu(root, answers)
                    self.assertTrue("cancelada" in text or "Entrada encerrada" in text)
                    self.assertEqual(list(root.iterdir()), [])

    def test_interrupt_after_a_saved_yaml_row_preserves_completed_work(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "small.yaml"
            config.write_text(yaml.safe_dump({
                "shape": [5, 5, 5], "seeds": [1, 2],
                "algorithms": {"random_walk": {"steps": 1}},
                "outputs": {"volumes_dir": str(root / "volumes")},
            }), encoding="utf-8")
            answers = iter(["2", str(config), "", "0"])
            messages: list[str] = []

            def write(message: str) -> None:
                messages.append(message)
                if message.startswith("Salvo:"):
                    raise KeyboardInterrupt

            run_menu(lambda prompt: next(answers), write,
                     csv_path=root / "experiments.csv", volumes_dir=root / "volumes")
            rows = self._rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["seed"], "1")
            self.assertTrue(Path(rows[0]["volume_path"]).is_file())
            self.assertIn("Ação cancelada", "\n".join(messages))


if __name__ == "__main__":
    unittest.main()
