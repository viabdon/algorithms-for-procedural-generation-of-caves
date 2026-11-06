"""Contratos das transições do CA, do controle do peso e dos extremos do log.

As transições são só observação: o volume final e o histórico têm de continuar
iguais aos de antes delas, porque o CA sem peso é o baseline da comparação. Os
hashes abaixo saíram do generator.py anterior à mudança (commit 748e387).
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from cavegen.generators.cellular_automata.generator import (
    BorderTreatment,
    cellular_automata,
    contar_transicoes,
    iterate,
)
from cavegen.generators.cellular_automata.pesos import comprimir_log, importar_sdf
from cavegen.generators.cellular_automata.plot import (
    ETAPA_PESO,
    adicionar_controle_do_peso,
    corte_do_peso,
    dados_da_matriz,
    figura_volumetrica,
    opacidade_por_vizinhos,
    plotar_resultado,
    traces_do_peso,
)
from cavegen.generators.cellular_automata.results import load_result, result_path, run_and_save
from cavegen.generators.random_walk.plot import figura_classificacao
from cavegen.ui.cellular_automata.dados import Execucao, rodar_passo_a_passo, salvar
from cavegen.ui.cellular_automata.figuras import figura_3d


def matriz_aleatoria(formato: tuple[int, int, int], seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 2, size=formato)


def peso_aleatorio(formato: tuple[int, int, int], seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-5, 2, size=formato).astype(np.float32)


def resumo(matriz: np.ndarray) -> str:
    return hashlib.sha256(matriz.astype(np.uint8).tobytes()).hexdigest()[:16]


class BaselineTests(unittest.TestCase):
    def test_final_e_historico_iguais_aos_de_antes_das_transicoes(self) -> None:
        inicial = matriz_aleatoria((9, 10, 11), 11)
        peso = peso_aleatorio(inicial.shape, 12)
        esperados = {
            ("zeros", False): ("0ad0c89cbc90d12f", [485, 249, 158, 108, 78]),
            ("zeros", True): ("3449ddf7ca912858", [485, 134, 17, 0, 0]),
            ("ones", False): ("3e421d986fbb49db", [485, 731, 862, 937, 970]),
            ("ones", True): ("e141bfe3d62b91e4", [485, 543, 520, 507, 506]),
        }

        for (borda, com_peso), (hash_final, historico_antigo) in esperados.items():
            with self.subTest(borda=borda, com_peso=com_peso):
                final, historico, _, _ = cellular_automata(
                    inicial, 14, borda, 4, peso=peso if com_peso else None)

                self.assertEqual(resumo(final), hash_final)
                self.assertEqual(historico.tolist(), historico_antigo)

    def test_contagem_nao_consome_o_sorteio_da_borda_aleatoria(self) -> None:
        # Não exige reprodutibilidade da borda: só que contar não muda a sequência.
        inicial = matriz_aleatoria((6, 7, 8), 13)
        for peso in (None, peso_aleatorio(inicial.shape, 14)):
            with self.subTest(com_peso=peso is not None):
                np.random.seed(5)
                esperado = inicial
                for _ in range(3):
                    esperado = iterate(esperado, 13, BorderTreatment.RANDOM, peso)

                np.random.seed(5)
                final, *_ = cellular_automata(inicial, 13, BorderTreatment.RANDOM, 3, peso=peso)

                np.testing.assert_array_equal(final, esperado)

    def test_entrada_nao_e_alterada(self) -> None:
        inicial = matriz_aleatoria((5, 6, 7), 15)
        copia = inicial.copy()

        cellular_automata(inicial, 13, "ones", 3)

        np.testing.assert_array_equal(inicial, copia)


class ContagemTests(unittest.TestCase):
    def test_contagem_conferida_a_mao(self) -> None:
        anterior = np.array([[[0, 0, 1, 1, 1]]])
        seguinte = np.array([[[1, 0, 0, 0, 1]]])

        self.assertEqual(contar_transicoes(anterior, seguinte), (1, 2))
        self.assertEqual(contar_transicoes(anterior, anterior), (0, 0))

    def test_tipos_da_seed_nao_mudam_a_contagem(self) -> None:
        base = matriz_aleatoria((7, 8, 9), 16)
        seguinte = iterate(base, 13, BorderTreatment.ZEROS)
        esperado = contar_transicoes(base, seguinte)

        for tipo in (bool, np.uint8, np.int8, np.int16, np.int64, np.float32):
            with self.subTest(tipo=tipo.__name__):
                self.assertEqual(contar_transicoes(base.astype(tipo), seguinte), esperado)
                self.assertEqual(
                    contar_transicoes(base.astype(tipo), seguinte.astype(bool)), esperado)

    def test_saldo_e_a_variacao_do_historico_em_todos_os_casos(self) -> None:
        base = matriz_aleatoria((7, 8, 9), 17)
        peso = peso_aleatorio(base.shape, 18)

        for tipo in (bool, np.uint8, np.int64):
            for borda in BorderTreatment:
                for peso_usado in (None, peso):
                    with self.subTest(tipo=tipo.__name__, borda=borda,
                                      peso=peso_usado is not None):
                        _, historico, para_1, para_0 = cellular_automata(
                            base.astype(tipo), 13, borda, 4, peso=peso_usado)

                        self.assertEqual((para_1.size, para_0.size), (4, 4))
                        self.assertEqual((para_1.dtype, para_0.dtype), (np.int64, np.int64))
                        np.testing.assert_array_equal(np.diff(historico), para_1 - para_0)

    def test_extremos_de_volume_e_sensibilidade(self) -> None:
        formato = (4, 5, 6)
        total = 4 * 5 * 6
        vazio, cheio = np.zeros(formato, dtype=int), np.ones(formato, dtype=int)

        _, _, para_1, para_0 = cellular_automata(vazio, 0, "zeros", 2)
        self.assertEqual((para_1.tolist(), para_0.tolist()), ([total, 0], [0, 0]))

        _, _, para_1, para_0 = cellular_automata(cheio, 28, "ones", 2)
        self.assertEqual((para_1.tolist(), para_0.tolist()), ([0, 0], [total, 0]))

        _, historico, para_1, para_0 = cellular_automata(vazio, 13, "zeros", 2)
        self.assertEqual(historico.tolist(), [0, 0, 0])
        self.assertEqual((para_1.tolist(), para_0.tolist()), ([0, 0], [0, 0]))


class PersistenciaTests(unittest.TestCase):
    def test_run_and_save_grava_as_transicoes_de_cellular_automata(self) -> None:
        inicial = matriz_aleatoria((6, 6, 6), 19)
        peso = peso_aleatorio(inicial.shape, 20)
        modulo = "cavegen.generators.cellular_automata.results"

        with tempfile.TemporaryDirectory() as pasta:
            planilha = Path(pasta) / "recursos.csv"
            with (mock.patch(f"{modulo}.load_seed_matrix", return_value=inicial),
                  mock.patch(f"{modulo}.load_peso_matrix", return_value=peso),
                  mock.patch("cavegen.profiling.resource_tracker.CSV_PADRAO", planilha)):
                run_and_save(1, 13, "zeros", 3, Path(pasta) / "results", peso_id=7)

            dados = load_result(1, Path(pasta) / "results")
            linhas = planilha.read_text(encoding="utf-8").splitlines()

        final, historico, para_1, para_0 = cellular_automata(inicial, 13, "zeros", 3, peso=peso)
        np.testing.assert_array_equal(dados["matrix"], final)
        np.testing.assert_array_equal(dados["live_cells_history"], historico)
        np.testing.assert_array_equal(dados["viraram_1_history"], para_1)
        np.testing.assert_array_equal(dados["viraram_0_history"], para_0)
        self.assertEqual(len(linhas), 2)

    def test_salvar_sem_iteracoes_grava_transicoes_vazias(self) -> None:
        seed = matriz_aleatoria((5, 5, 5), 21)
        passos, _ = rodar_passo_a_passo(seed, 13, "zeros", 0)
        execucao = Execucao(seed=seed, final=seed, historico=np.array([int(seed.sum())]),
                            sensitivity=13, border_treatment="zeros", iterations=0,
                            passos=passos, seed_id=1)

        with tempfile.TemporaryDirectory() as pasta:
            _, result_id = salvar(execucao, Path(pasta) / "seeds", Path(pasta) / "results")
            dados = load_result(result_id, Path(pasta) / "results")

        self.assertEqual(dados["viraram_1_history"].size, 0)
        self.assertEqual(dados["viraram_0_history"].size, 0)


def figura_em_modo_vizinhos(historico=None, **argumentos):
    matriz = np.zeros((6, 6, 6), dtype=int)
    matriz[1:4, 1:5, 2:6] = 1
    x, y, z = dados_da_matriz(matriz)
    valores = np.arange(x.size) % 5 + 1
    return figura_volumetrica(x, y, z, valores, "teste", historico=historico,
                              total_celulas=216, opacidades=opacidade_por_vizinhos(valores),
                              **argumentos)


def peso_em_rampa() -> np.ndarray:
    return np.linspace(-14, 3, 6 ** 3, dtype=np.float32).reshape(6, 6, 6)


class ControleDoPesoTests(unittest.TestCase):
    def conferir_mascaras(self, figura) -> None:
        antes = list(figura.data)
        nuvem = [t.type == "scatter3d" and t.mode == "markers" for t in antes]

        adicionar_controle_do_peso(figura, peso_em_rampa(), "r", "p")

        novos = len(figura.data) - len(antes)
        self.assertGreater(novos, 0)
        controle = figura.layout.sliders[0]
        no_peso = list(controle.steps[0].args[0]["visible"])
        no_resultado = list(controle.steps[1].args[0]["visible"])
        self.assertEqual(no_peso, [not e for e in nuvem] + [True] * novos)
        self.assertEqual(no_resultado, [True] * len(antes) + [False] * novos)
        # O estado inicial da figura é o do passo ativo.
        ativo = list(controle.steps[controle.active].args[0]["visible"])
        self.assertEqual([t.visible is not False for t in figura.data], ativo)

    def test_mascaras_com_varias_nuvens_e_com_historico(self) -> None:
        self.conferir_mascaras(figura_em_modo_vizinhos(
            historico=np.array([100, 40, 30]), viraram_1=np.array([5, 2]),
            viraram_0=np.array([65, 12])))

    def test_mascaras_sem_historico(self) -> None:
        self.conferir_mascaras(figura_em_modo_vizinhos())

    def test_mascaras_sem_nenhuma_celula_viva(self) -> None:
        vazio = np.array([], dtype=int)
        self.conferir_mascaras(figura_volumetrica(
            vazio, vazio, vazio, vazio, "teste", minimos=[-0.5] * 3, maximos=[5.5] * 3,
            opacidades=np.array([], dtype=float)))

    def test_peso_fica_na_orientacao_do_volume_em_grade_nao_cubica(self) -> None:
        peso = np.full((4, 5, 6), -50.0, dtype=np.float32)
        peso[1, 2, 3] = 1.0
        volume = peso > 0

        trace, = traces_do_peso(peso)

        x, y, z = dados_da_matriz(volume)
        self.assertEqual((list(trace.x), list(trace.y), list(trace.z)), (list(x), list(y), list(z)))
        self.assertEqual((trace.x[0], trace.y[0], trace.z[0]), (3, 1, 2))

    def test_log_mostra_os_mesmos_voxels_em_qualquer_escala(self) -> None:
        # Distâncias exatas de uma grade: o voxel a 10 fica de fora nos dois casos.
        sdf = np.array([[[-11.0, -10.0, -9.0, 0.0, 1.0]]], dtype=np.float32)
        sem_log = sdf > corte_do_peso()

        for escala in (1.0, 2.0, 2.5, 3.0, 4.7, 8.9, 9.4):
            with self.subTest(escala=escala):
                com_log = comprimir_log(sdf, escala) > corte_do_peso(escala)

                np.testing.assert_array_equal(com_log, sem_log)


class CompatibilidadeTests(unittest.TestCase):
    def test_bancada_e_random_walk_seguem_sem_os_argumentos_novos(self) -> None:
        matriz = matriz_aleatoria((6, 6, 6), 22)
        classes = np.where(matriz == 1, 2, 0)
        classes[0, 0, 0] = 1

        for figura in (figura_3d(matriz, "zeros"), figura_3d(matriz, "ones", modo="altura"),
                       figura_classificacao(classes, "rw")):
            self.assertEqual(len(figura.layout.sliders), 0)
            self.assertFalse(any(t.type == "scatter" for t in figura.data))


class PlotarExtremosTests(unittest.TestCase):
    def test_volume_sem_ar_e_todo_aberto_plotam_com_peso_comprimido(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            origem = raiz / "sdf.npz"
            np.savez_compressed(origem, sdf=peso_em_rampa(), convencao="interno positivo")
            importar_sdf(origem, raiz / "pesos", escala_log=2.0)
            (raiz / "results").mkdir()

            for result_id, valor in ((1, 0), (2, 1)):
                np.savez_compressed(
                    result_path(result_id, raiz / "results"),
                    matrix=np.full((6, 6, 6), valor), result_id=result_id, seed_id=1, size=6,
                    sensitivity=13, border_treatment="zeros", iterations=0, peso_id=1,
                    live_cells_history=np.array([valor * 216]),
                    viraram_1_history=np.array([], dtype=np.int64),
                    viraram_0_history=np.array([], dtype=np.int64),
                )
                for modo in ("altura", "vizinhos"):
                    with self.subTest(result_id=result_id, modo=modo):
                        destino = plotar_resultado(
                            result_id, raiz / "results", refazer=True, modo=modo,
                            pesos_dir=raiz / "pesos", figuras=raiz / "plots")

                        self.assertIn(ETAPA_PESO, destino.read_text(encoding="utf-8"))


class ExtremosDoLogTests(unittest.TestCase):
    def test_escala_que_nao_e_finita_falha(self) -> None:
        # A validação `escala <= 0` deixa NaN passar, e o peso inteiro vira NaN:
        # no CA, vizinhos + NaN >= s é sempre falso e o volume fecha sem aviso.
        for escala in (float("nan"), float("inf")):
            with self.subTest(escala=escala), np.errstate(invalid="ignore"):
                with self.assertRaises(ValueError):
                    comprimir_log(np.array([-1.0, 0.0, 1.0]), escala)

    def test_nan_e_infinito_do_sdf_nao_viram_numero_e_o_dtype_fica(self) -> None:
        sdf = np.array([np.nan, np.inf, -np.inf, 0.0, -0.0, 1.0], dtype=np.float32)
        copia = sdf.copy()

        saida = comprimir_log(sdf, 2.0)

        self.assertEqual(saida.dtype, np.float32)
        self.assertTrue(np.isnan(saida[0]))
        self.assertEqual((saida[1], saida[2]), (np.inf, -np.inf))
        self.assertEqual((saida[3], saida[4]), (0.0, 0.0))
        np.testing.assert_array_equal(sdf, copia)

    def test_campo_inteiro_tambem_sai_em_float32(self) -> None:
        saida = comprimir_log(np.array([-2, 0, 3]), 2.0)

        self.assertEqual(saida.dtype, np.float32)
        np.testing.assert_allclose(saida, [-2 * np.log(3), 0, 2 * np.log(4)], rtol=1e-6)


if __name__ == "__main__":
    unittest.main()
