"""Destinos públicos das plotagens de volumes gerados."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from plots.matriz import caminho_da_figura


class FigurePathsTests(unittest.TestCase):
    def test_generated_volume_plots_use_procedural_stage(self) -> None:
        with TemporaryDirectory() as directory:
            stage = Path(directory) / "06_geracao_procedural"
            with patch("plots.matriz.PASTA_FIGURAS", stage):
                destination = caminho_da_figura(
                    SimpleNamespace(nome="random_walk_seed_0"), "3d", "png"
                )
            self.assertEqual(destination, stage / "random_walk_seed_0_3d.png")
            self.assertTrue(stage.is_dir())


if __name__ == "__main__":
    unittest.main()
