"""Garante que o menu do random walk grava e plota o mesmo que o gerador produz.

O menu é a porta de entrada para gerar as cavernas da análise comparativa,
então o resultado gravado por ele precisa ser o mesmo volume de
generate_random_walk com os mesmos parâmetros, bit a bit. Os testes gravam
tudo em pastas temporárias e desviam a planilha de recursos, para não sujar
results/ do projeto.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from functools import partial
from pathlib import Path
from unittest import mock

import numpy as np

from cavegen.generators.random_walk import menu
from cavegen.generators.random_walk.generator import generate_random_walk
from cavegen.generators.random_walk.plot import plotar_resultado
from cavegen.generators.random_walk.results import (
    load_result,
    load_result_info,
    result_path,
    run_and_save,
    used_result_ids,
)
from cavegen.generators.random_walk.voxelizacao import classificar


class PastasTemporariasTest(unittest.TestCase):
    def setUp(self) -> None:
        temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(temporaria.cleanup)
        raiz = Path(temporaria.name)
        self.resultados = raiz / "results"
        self.figuras = raiz / "plots"
        planilha = mock.patch("cavegen.profiling.resource_tracker.CSV_PADRAO",
                              raiz / "resource_usage.csv")
        planilha.start()
        self.addCleanup(planilha.stop)
        self.planilha = raiz / "resource_usage.csv"


class ResultadosTest(PastasTemporariasTest):
    def test_resultado_gravado_e_o_volume_do_gerador(self) -> None:
        destino = run_and_save(3, "example", 32, directory=self.resultados)
        dados = load_result(int(destino.stem[-3:]), self.resultados)

        esperado = generate_random_walk((32,) * 3, seed=3, caverna="example")
        np.testing.assert_array_equal(dados["matrix"], esperado.data)
        np.testing.assert_array_equal(dados["classificacao"], classificar(esperado.data))
        self.assertEqual(dados["caverna"], "Example")
        self.assertEqual(dados["seed"], 3)
        self.assertEqual(dados["size"], 32)
        self.assertEqual(dados["raio_voxels"], esperado.metadata["raio_voxels"])
        self.assertEqual(len(dados["inicios"]) - 1, esperado.metadata["caminhos"])
        self.assertTrue(self.planilha.exists())

    def test_numeracao_segue_e_trocas_ficam_gravadas(self) -> None:
        run_and_save(1, "example", 32, directory=self.resultados)
        segundo = run_and_save(1, "example", 32, raio_voxels=None, weight=0.5, k=10, spacer=3,
                               directory=self.resultados)
        self.assertEqual(segundo, result_path(2, self.resultados))
        self.assertEqual(used_result_ids(self.resultados), {1, 2})

        info = load_result_info(2, self.resultados)
        self.assertEqual((info["weight"], info["k"], info["spacer"]), (0.5, 10.0, 3.0))
        esperado = generate_random_walk((32,) * 3, seed=1, caverna="example", raio_voxels=None,
                                        weight=0.5, k=10, spacer=3)
        np.testing.assert_array_equal(load_result(2, self.resultados)["matrix"], esperado.data)
        self.assertEqual(info["raio_voxels"], esperado.metadata["raio_voxels"])

    def test_plota_os_dois_modos(self) -> None:
        run_and_save(1, "example", 32, directory=self.resultados)
        for modo in ("caminhos", "classificacao"):
            destino = plotar_resultado(1, modo, self.resultados, self.figuras)
            self.assertTrue(destino.exists(), modo)
            self.assertIn("plotly", destino.read_text(encoding="utf-8"))

        with self.assertRaises(ValueError):
            plotar_resultado(1, "altura", self.resultados, self.figuras)


class MenuTest(PastasTemporariasTest):
    def rodar_menu(self, respostas: list[str]) -> str:
        """Roda o menu com as respostas digitadas, gravando nas pastas temporárias."""
        trocas = {
            "run_and_save": partial(run_and_save, directory=self.resultados),
            "used_result_ids": partial(used_result_ids, self.resultados),
            "load_result": partial(load_result, directory=self.resultados),
            "load_result_info": partial(load_result_info, directory=self.resultados),
            "plotar_resultado": partial(plotar_resultado, directory=self.resultados,
                                        figuras=self.figuras),
            "figura_ja_existe": lambda result_id, modo: False,
        }
        saida = io.StringIO()
        with mock.patch("builtins.input", side_effect=respostas), redirect_stdout(saida):
            with mock.patch.multiple(menu, **trocas):
                menu.main()
        return saida.getvalue()

    def test_gerar_com_padroes_e_plotar(self) -> None:
        # opção 1: caverna 1 (Example), seed padrão, lado 32, raio padrão, sem trocas;
        # opção 2: último resultado, figura 2 (classificacao); 0 sai.
        texto = self.rodar_menu(["1", "1", "", "32", "", "", "2", "", "2", "0"])

        dados = load_result(1, self.resultados)
        esperado = generate_random_walk((32,) * 3, seed=menu.SEED_PADRAO, caverna="example")
        np.testing.assert_array_equal(dados["matrix"], esperado.data)
        self.assertTrue((self.figuras / "result_001_classificacao.html").exists())
        self.assertIn("resultado gravado: result_001.npz", texto)

    def test_raio_proporcional_e_trocas_dentro_das_faixas_do_csharp(self) -> None:
        # raio "p"; trocar s; weight 5 (acima de 1) é recusado e vira 0.5; k 10; spacer 0
        # (abaixo de 1) é recusado e vira 4.
        self.rodar_menu(["1", "1", "7", "32", "p", "s", "5", "0.5", "10", "0", "4", "0"])

        info = load_result_info(1, self.resultados)
        self.assertEqual((info["seed"], info["weight"], info["k"], info["spacer"]),
                         (7, 0.5, 10.0, 4.0))
        esperado = generate_random_walk((32,) * 3, seed=7, caverna="example", raio_voxels=None,
                                        weight=0.5, k=10, spacer=4)
        np.testing.assert_array_equal(load_result(1, self.resultados)["matrix"], esperado.data)

    def test_lado_abaixo_do_minimo_e_recusado(self) -> None:
        texto = self.rodar_menu(["1", "1", "", "5", "32", "", "", "0"])
        self.assertIn("valor abaixo do minimo permitido", texto)
        self.assertEqual(load_result_info(1, self.resultados)["size"], 32)


if __name__ == "__main__":
    unittest.main()
