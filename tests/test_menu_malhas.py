"""Contratos observáveis do menu de revisão e geração diagnóstica."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

import numpy as np

from cavegen.meshing.normal_orientation import save_orientation
from menu_malhas import inspect_file, list_files, main, suggest_output


class MenuMalhasTests(unittest.TestCase):
    def test_lists_figures_inside_stage_directories(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / "results/figures/03_linha_central"
            stage.mkdir(parents=True)
            (stage / "linha.html").write_text("plot")
            with patch("menu_malhas.ROOT", root), redirect_stdout(StringIO()) as output:
                list_files("figuras")
            self.assertIn("results/figures/03_linha_central/linha.html", output.getvalue())

    def test_suggests_a_new_name_without_overwriting_review(self) -> None:
        with TemporaryDirectory() as directory:
            original = Path(directory) / "review.npz"
            original.write_text("existing")
            suggestion = suggest_output(str(original), review=True)
            self.assertEqual(suggestion, str(Path(directory) / "review_02.npz"))

    def test_inspection_shows_exact_review_point_and_uncertainty(self) -> None:
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "review.npz"
            points = np.array([[1., 2., 3.], [4., 5., 6.]])
            normals = np.tile([0., 0., 1.], (2, 1))
            save_orientation(archive, {
                "points_xyz": points, "baseline_normals_xyz": normals,
                "oriented_normals_xyz": normals.copy(),
                "uncertain_mask": np.array([True, False]),
                "manual_mask": np.zeros(2, dtype=bool),
                "reason_bits": np.array([64, 0], dtype=np.uint16),
                "candidate_branches": np.full((2, 2), -1, dtype=np.int32),
            }, {})
            output = StringIO()
            with redirect_stdout(output):
                inspect_file(archive, 0)
            self.assertIn("incertos: 1", output.getvalue())
            self.assertIn("Ponto 0: XYZ=[1.0, 2.0, 3.0]", output.getvalue())
            self.assertIn("trecho_sem_consenso", output.getvalue())
            self.assertEqual(main(["inspecionar", str(archive), "--indice", "2"]), 1)

    def test_meshing_switches_normal_source_and_protects_existing_output(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "mesh.obj"
            report = {"normal_source": "baseline", "sampled_vertices": 2,
                      "normal_sign_uncertain_count": 1, "mesh_triangles": 4,
                      "mesh_boundary_edges": 0}
            with patch("menu_malhas.run_oriented_sample", return_value=report) as run:
                self.assertEqual(main(["malha", "--orientacao", "review.npz", "--saida",
                                       str(output), "--modo", "baseline"]), 0)
                self.assertEqual(run.call_args.kwargs["normal_source"], "baseline")
                self.assertFalse(run.call_args.kwargs["require_resolved"])
                main(["malha", "--orientacao", "review.npz", "--saida", str(output)])
                self.assertEqual(run.call_args.kwargs["normal_source"], "reviewed")
                self.assertTrue(run.call_args.kwargs["require_resolved"])
                output.write_text("existing")
                self.assertEqual(main(["malha", "--orientacao", "review.npz",
                                       "--saida", str(output)]), 1)
                self.assertEqual(run.call_count, 2)

    def test_cosine_menu_command_summarizes_three_thresholds(self) -> None:
        rows = [{"cosine_threshold": threshold, "automatic_keep_count": 2,
                 "automatic_flip_count": 3, "uncertain_count": 4,
                 "orientation_path": f"cos{threshold}.npz"}
                for threshold in (0.5, 0.75, 0.94)]
        with patch("menu_malhas.compare_cosine_thresholds", return_value={"thresholds": rows}) as compare:
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(main(["cossenos", "--prefixo", "data/processed/teste"]), 0)
            self.assertEqual(compare.call_count, 1)
            self.assertIn("|cos| ≥ 0.94", output.getvalue())
            self.assertIn("incertos=4", output.getvalue())

    def test_test_command_uses_current_interpreter_without_shell(self) -> None:
        with patch("menu_malhas.subprocess.run") as run:
            run.return_value.returncode = 0
            self.assertEqual(main(["testar", "--padrao", "test_normal_orientation.py"]), 0)
            command = run.call_args.args[0]
            self.assertEqual(command, [sys.executable, "-m", "unittest", "discover",
                                       "-s", "tests", "-p", "test_normal_orientation.py", "-v"])
            self.assertFalse(run.call_args.kwargs["check"])

    def test_thickening_command_uses_requested_sample_and_radii(self) -> None:
        report = {"measured_points": 40_000}
        with patch("cavegen.meshing.morphological_thickening.run_experiment",
                   return_value=report) as run:
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(main(["espessar", "--amostra", "sample.npz",
                                       "--prefixo", "results/meshes/teste",
                                       "--voxel", "0.2", "--raios", "1", "2"]), 0)
            self.assertEqual(run.call_args.kwargs["voxel_size"], 0.2)
            self.assertEqual(run.call_args.kwargs["radii_voxels"], (1, 2))
            self.assertIn("40,000", output.getvalue())

    def test_raw_thickening_commands_keep_occupancy_and_sample_explicit(self) -> None:
        with patch("cavegen.meshing.morphological_thickening.voxelize_raw_roi",
                   return_value={"occupancy_path": "raw.npz", "roi_source_count": 100,
                                 "occupied_voxels": 25}) as voxelize:
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["voxelizar-roi", "--ply", "raw.ply",
                                       "--saida", "raw.npz", "--voxel", "0.1"]), 0)
            self.assertEqual(voxelize.call_args.kwargs["voxel_size"], 0.1)
        with patch("cavegen.meshing.morphological_thickening.run_raw_occupancy_experiment",
                   return_value={"raw_roi_points": 100}) as run:
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["espessar-bruto", "--ocupacao", "raw.npz",
                                       "--amostra", "sample.npz", "--prefixo", "compare",
                                       "--raios", "0", "1", "2"]), 0)
            self.assertEqual(run.call_args.kwargs["radii_voxels"], (0, 1, 2))
            self.assertTrue(str(run.call_args.args[0]).endswith("raw.npz"))
            self.assertTrue(str(run.call_args.args[1]).endswith("sample.npz"))


if __name__ == "__main__":
    unittest.main()
