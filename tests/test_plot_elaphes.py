"""Contratos de visualização 3D de nuvens, grafos e malhas do Elaphes."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import trimesh

from cavegen.meshing.normal_orientation import save_orientation
from plots.plot_elaphes import (
    adicionar_revisao_normais, amostrar_pontos, carregar_grafo, main, montar_linha,
)


class PlotElaphesTests(unittest.TestCase):
    def test_default_html_paths_follow_experiment_stages(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cloud, graph, mesh, review = [root / name for name in
                                          ("cloud.npz", "graph.npz", "mesh.obj", "review.npz")]
            points = np.array([[0., 0., 0.], [1., 1., 1.]])
            normals = np.tile([0., 0., 1.], (2, 1))
            np.savez(cloud, points_xyz=points)
            np.savez(graph, nodes_xyz=points, edges=np.array([[0, 1]]))
            trimesh.creation.box().export(mesh)
            save_orientation(review, {
                "points_xyz": points, "baseline_normals_xyz": normals,
                "oriented_normals_xyz": normals.copy(),
                "uncertain_mask": np.array([True, False]),
                "manual_mask": np.zeros(2, dtype=bool),
                "reason_bits": np.array([64, 0], dtype=np.uint16),
                "candidate_branches": np.full((2, 2), -1, dtype=np.int32),
            }, {})
            with patch("plots.plot_elaphes.RAIZ_PROJETO", root), \
                 patch("plotly.graph_objects.Figure.write_html"):
                line = main(["line", "--cloud", str(cloud), "--graph", str(graph)])
                self.assertEqual(line.parent.name, "03_linha_central")
                oriented = main(["line", "--cloud", str(cloud), "--graph", str(graph),
                                 "--orientation", str(review), "--highlight-uncertain"])
                self.assertEqual(oriented.parent.name, "04_orientacao_normais")
                comparison = main(["mesh", "--cloud", str(cloud),
                                   "--mesh", f"Caixa={mesh}"])
                self.assertEqual(comparison.parent.name, "05_comparacao_malhas")

    def test_review_overlay_identifies_exact_points_and_arrows(self) -> None:
        points = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=float)
        normals = np.tile([0., 1., 0.], (len(points), 1))
        result = {
            "points_xyz": points, "baseline_normals_xyz": normals,
            "oriented_normals_xyz": normals.copy(),
            "uncertain_mask": np.array([False, True, False, True]),
            "manual_mask": np.array([False, False, True, False]),
            "reason_bits": np.array([0, 64, 512, 64], dtype=np.uint16),
            "candidate_branches": np.zeros((len(points), 2), dtype=np.int32),
        }
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "review.npz"
            save_orientation(archive, result, {})
            figure = montar_linha(points[:1], points[[0, 3]], np.array([[0, 1]]))
            adicionar_revisao_normais(
                figure, points, archive, destacar_incertos=True,
                mostrar_manuais=True, mostrar_normais=True, max_setas=2,
            )
            uncertain = next(trace for trace in figure.data if trace.name.startswith("Sentido incerto"))
            self.assertEqual(len(uncertain.x), 2)
            self.assertIn("Índice=1", uncertain.text[0])
            self.assertIn("Índice=3", uncertain.text[1])
            self.assertEqual(sum(trace.type == "cone" for trace in figure.data), 1)
            cone = next(trace for trace in figure.data if trace.type == "cone")
            self.assertLessEqual(len(cone.x), 2)
            with self.assertRaisesRegex(ValueError, "não pertence à nuvem"):
                adicionar_revisao_normais(figure, points[::-1], archive, destacar_incertos=True)

    def test_cloud_uses_visible_depth_colors_on_light_background(self) -> None:
        pontos = np.array([[0, 0, 0], [1, 1, 2], [2, 1, 1]], dtype=float)
        nos = np.array([[0.5, 0.5, 0.5], [1.5, 0.8, 1.5]], dtype=float)
        figura = montar_linha(pontos, nos, np.array([[0, 1]]))
        nuvem = figura.data[0]
        self.assertEqual(nuvem.marker.colorscale[0][1], "#440154")
        self.assertGreaterEqual(nuvem.marker.opacity, 0.8)
        np.testing.assert_array_equal(nuvem.marker.color, pontos[:, 2])
        self.assertEqual(figura.layout.template.layout.paper_bgcolor, "white")
        self.assertEqual(figura.layout.scene.aspectmode, "data")

    def test_point_limit_is_deterministic_and_preserves_xyz(self) -> None:
        pontos = np.arange(300, dtype=float).reshape(100, 3)
        primeiro = amostrar_pontos(pontos, 12, 7)
        segundo = amostrar_pontos(pontos, 12, 7)
        np.testing.assert_array_equal(primeiro, segundo)
        self.assertEqual(primeiro.shape, (12, 3))
        with self.assertRaisesRegex(ValueError, "positivo"):
            amostrar_pontos(pontos, 0, 7)

    def test_line_cli_writes_html_and_rejects_invalid_graph(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cloud = root / "cloud.npz"
            graph = root / "graph.npz"
            output = root / "line.html"
            np.savez(cloud, points_xyz=np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float32))
            np.savez(graph, nodes_xyz=np.array([[0, 0, 0], [1, 1, 1]], dtype=float),
                     edges=np.array([[0, 1]], dtype=np.int64))
            self.assertEqual(main(["line", "--cloud", str(cloud), "--graph", str(graph),
                                   "--output", str(output)]), output)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 10_000)
            with output.open() as arquivo:
                self.assertEqual(arquivo.read(6), "<html>")

            np.savez(graph, nodes_xyz=np.array([[0, 0, 0]], dtype=float),
                     edges=np.array([[0, 1]], dtype=np.int64))
            with self.assertRaisesRegex(ValueError, "fora do intervalo"):
                carregar_grafo(graph)

    def test_mesh_cli_writes_candidate_selector(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cloud = root / "cloud.npz"
            mesh_a, mesh_b = root / "a.obj", root / "b.obj"
            output = root / "meshes.html"
            np.savez(cloud, points_xyz=np.array([[0, 0, 0], [1, 1, 1]], dtype=float))
            trimesh.creation.box().export(mesh_a)
            trimesh.creation.icosphere(subdivisions=0).export(mesh_b)
            main(["mesh", "--cloud", str(cloud), "--mesh", f"Caixa={mesh_a}",
                  "--mesh", f"Esfera={mesh_b}", "--output", str(output)])
            html = output.read_text()
            self.assertIn("Caixa", html)
            self.assertIn("Esfera", html)
            self.assertIn("Viridis", html)

            points = np.array([[0., 0., 0.], [1., 1., 1.]])
            normals = np.tile([0., 0., 1.], (2, 1))
            orientation = root / "review.npz"
            save_orientation(orientation, {
                "points_xyz": points, "baseline_normals_xyz": normals,
                "oriented_normals_xyz": normals.copy(),
                "uncertain_mask": np.array([True, False]),
                "manual_mask": np.zeros(2, dtype=bool),
                "reason_bits": np.array([64, 0], dtype=np.uint16),
                "candidate_branches": np.full((2, 2), -1, dtype=np.int32),
            }, {})
            main(["mesh", "--cloud", str(cloud), "--mesh", f"Caixa={mesh_a}",
                  "--mesh", f"Esfera={mesh_b}", "--orientation", str(orientation),
                  "--highlight-uncertain", "--show-normals", "--output", str(output)])
            html = output.read_text()
            self.assertIn("Sentido incerto (1)", html)
            self.assertIn("Normais atuais (1 setas)", html)


if __name__ == "__main__":
    unittest.main()
