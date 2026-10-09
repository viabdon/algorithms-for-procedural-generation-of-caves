"""Contratos de visualização 3D de nuvens, grafos e malhas do Elaphes."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import trimesh

from plots.plot_elaphes import amostrar_pontos, carregar_grafo, main, montar_linha


class PlotElaphesTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
