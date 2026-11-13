"""Garante que a bancada Streamlit do CA não diverge do pacote do CA.

A bancada roda o CA passo a passo e grava os próprios npz; se o laço ou o
formato saírem diferentes, o que se vê na interface não é o que o menu, o plot
e o benchmark enxergam.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.generators.cellular_automata.generator import (
    BorderTreatment,
    ModoPeso,
    cellular_automata,
)
from cavegen.generators.cellular_automata.results import load_result, load_result_info
from cavegen.generators.cellular_automata.seeds import load_seed_info, load_seed_matrix
from cavegen.ui.cellular_automata.dados import (
    Execucao,
    historico_dos_passos,
    transicoes_dos_passos,
    rodar_passo_a_passo,
    salvar,
)
from cavegen.ui.cellular_automata.figuras import (
    celulas_visiveis,
    fatia,
    figura_3d,
    figura_cortes,
)

APP = Path(__file__).resolve().parents[1] / "src" / "cavegen" / "ui" / "cellular_automata" / "app.py"


def seed_aleatoria(lado: int = 12) -> np.ndarray:
    return (numpy_rng(7).random((lado, lado, lado)) < 0.5).astype(int)


def execucao_de(seed: np.ndarray, peso_id=None, seed_id=None) -> Execucao:
    passos, segundos = rodar_passo_a_passo(seed, 14, BorderTreatment.ZEROS, 3)
    return Execucao(seed=passos[0], final=passos[-1], historico=historico_dos_passos(passos),
                    sensitivity=14, border_treatment="zeros", iterations=3, passos=passos,
                    seed_id=seed_id, one_probability=0.5, peso_id=peso_id, segundos=segundos)


class RodarPassoAPassoTests(unittest.TestCase):
    def test_final_e_historico_batem_com_cellular_automata(self) -> None:
        seed = seed_aleatoria()
        peso = numpy_rng(3).integers(-4, 5, size=seed.shape)
        for borda in (BorderTreatment.ZEROS, BorderTreatment.ONES):
            for peso_usado in (None, peso):
                with self.subTest(borda=borda, peso=peso_usado is not None):
                    passos, _ = rodar_passo_a_passo(seed, 14, borda, 4, peso_usado)
                    final, historico, viraram_1, viraram_0 = cellular_automata(
                        seed, 14, borda, 4, peso=peso_usado)

                    self.assertEqual(len(passos), 5)
                    np.testing.assert_array_equal(passos[0], seed.astype(bool))
                    np.testing.assert_array_equal(passos[-1], final.astype(bool))
                    np.testing.assert_array_equal(historico_dos_passos(passos), historico)
                    para_1, para_0 = transicoes_dos_passos(passos)
                    np.testing.assert_array_equal(para_1, viraram_1)
                    np.testing.assert_array_equal(para_0, viraram_0)

    def test_modo_so_negativo_bate_com_cellular_automata(self) -> None:
        seed = seed_aleatoria()
        peso = numpy_rng(3).integers(-4, 5, size=seed.shape)
        passos, _ = rodar_passo_a_passo(seed, 14, BorderTreatment.ZEROS, 4, peso,
                                        modo_peso=ModoPeso.SO_NEGATIVO)
        final, historico, _, _ = cellular_automata(seed, 14, BorderTreatment.ZEROS, 4,
                                                   peso=peso, modo_peso=ModoPeso.SO_NEGATIVO)
        completo, _ = rodar_passo_a_passo(seed, 14, BorderTreatment.ZEROS, 4, peso)

        np.testing.assert_array_equal(passos[-1], final.astype(bool))
        np.testing.assert_array_equal(historico_dos_passos(passos), historico)
        # Sem isso o teste passaria com a bancada ignorando o modo.
        self.assertFalse(np.array_equal(passos[-1], completo[-1]))

    def test_progress_recebe_cada_passo(self) -> None:
        chamadas = []
        rodar_passo_a_passo(seed_aleatoria(), 14, "zeros", 3,
                            progress=lambda passo, total: chamadas.append((passo, total)))
        self.assertEqual(chamadas, [(1, 3), (2, 3), (3, 3)])


class SalvarTests(unittest.TestCase):
    def test_seed_nova_e_resultado_sao_lidos_pelo_pacote_do_ca(self) -> None:
        execucao = execucao_de(seed_aleatoria(), peso_id=2)
        with tempfile.TemporaryDirectory() as pasta:
            seeds, results = Path(pasta) / "seeds", Path(pasta) / "results"
            seed_id, result_id = salvar(execucao, seeds, results)

            self.assertEqual((seed_id, result_id), (1, 1))
            self.assertEqual(load_seed_info(seed_id, seeds),
                             {"seed_id": 1, "size": 12, "one_probability": 0.5})
            np.testing.assert_array_equal(load_seed_matrix(seed_id, seeds), execucao.seed)

            dados = load_result(result_id, results)
            self.assertEqual(dados["seed_id"], 1)
            self.assertEqual(dados["sensitivity"], 14)
            self.assertEqual(dados["border_treatment"], "zeros")
            self.assertEqual(dados["iterations"], 3)
            self.assertEqual(dados["peso_id"], 2)
            self.assertEqual(dados["modo_peso"], "completo")
            np.testing.assert_array_equal(dados["matrix"], execucao.final)
            np.testing.assert_array_equal(dados["live_cells_history"], execucao.historico)
            para_1, para_0 = transicoes_dos_passos(execucao.passos)
            np.testing.assert_array_equal(dados["viraram_1_history"], para_1)
            np.testing.assert_array_equal(dados["viraram_0_history"], para_0)

    def test_modo_do_peso_e_gravado_como_no_run_and_save(self) -> None:
        execucao = execucao_de(seed_aleatoria(), peso_id=2, seed_id=5)
        execucao.modo_peso = ModoPeso.SO_NEGATIVO.value
        with tempfile.TemporaryDirectory() as pasta:
            results = Path(pasta) / "results"
            _, result_id = salvar(execucao, Path(pasta) / "seeds", results)
            self.assertEqual(load_result_info(result_id, results)["modo_peso"], "so_negativo")

    def test_volume_lido_de_arquivo_salva_sem_transicoes(self) -> None:
        execucao = execucao_de(seed_aleatoria(), seed_id=5)
        execucao.passos = None
        with tempfile.TemporaryDirectory() as pasta:
            _, result_id = salvar(execucao, Path(pasta) / "seeds", Path(pasta) / "results")
            dados = load_result(result_id, Path(pasta) / "results")

        self.assertIsNone(dados["viraram_1_history"])
        self.assertIsNone(dados["viraram_0_history"])

    def test_seed_gravada_nao_e_duplicada_e_ca_basico_nao_leva_peso(self) -> None:
        execucao = execucao_de(seed_aleatoria(), seed_id=5)
        with tempfile.TemporaryDirectory() as pasta:
            seeds, results = Path(pasta) / "seeds", Path(pasta) / "results"
            seed_id, result_id = salvar(execucao, seeds, results)

            self.assertEqual(seed_id, 5)
            self.assertFalse(seeds.exists())
            info = load_result_info(result_id, results)
            self.assertNotIn("peso_id", info)
            self.assertNotIn("modo_peso", info)


class FigurasTests(unittest.TestCase):
    def test_superficie_de_um_cubo_cheio_e_a_casca(self) -> None:
        cheio = np.ones((5, 5, 5), dtype=bool)
        visiveis = celulas_visiveis(cheio)

        self.assertEqual(int(visiveis.sum()), 5 ** 3 - 3 ** 3)
        self.assertFalse(visiveis[1:-1, 1:-1, 1:-1].any())

    def test_fatia_deixa_a_altura_em_pe_nos_cortes_verticais(self) -> None:
        matriz = np.zeros((4, 5, 6))  # (depth, height, width)
        self.assertEqual(fatia(matriz, "altura", 0).shape, (4, 6))
        self.assertEqual(fatia(matriz, "profundidade", 0).shape, (5, 6))
        self.assertEqual(fatia(matriz, "largura", 0).shape, (5, 4))

    def test_figura_3d_aguenta_volume_vazio(self) -> None:
        for modo in ("altura", "vizinhos"):
            with self.subTest(modo=modo):
                figura = figura_3d(np.zeros((6, 6, 6), dtype=bool), "zeros", modo=modo)
                self.assertEqual(figura.layout.uirevision, "cubo")

    def test_corte_do_peso_usa_o_minimo_e_o_maximo_e_nao_espelha_o_zero(self) -> None:
        # Peso só negativo: com zmid=0 a escala iria de -6 a +6.
        corte = np.array([[-6.0, -2.0], [-1.0, 0.0]])
        figura = figura_cortes([("peso", corte, "peso")], "altura")
        heatmap = figura.data[0]

        self.assertIsNone(heatmap.zmid)
        self.assertNotEqual(heatmap.zauto, False)


@unittest.skipIf(importlib.util.find_spec("streamlit") is None, "extra ui não instalado")
class AppTests(unittest.TestCase):
    def test_app_abre_e_roda_o_ca_sem_erro(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(APP), default_timeout=60).run()
        self.assertFalse(app.exception)

        app.sidebar.number_input[0].set_value(16)
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIsNotNone(app.session_state["execucao"])
        self.assertEqual(app.session_state["execucao"].lado, 16)


if __name__ == "__main__":
    unittest.main()
