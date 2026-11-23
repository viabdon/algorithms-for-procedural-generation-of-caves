"""Garante a troca de eixos e o título do plot do CA.

A matriz do CA é (depth, height, width), a mesma ordem do SDF que o guia. O
plot tem de pôr a altura na vertical, como os plots do Elaphes e do SDF, senão
o CA guiado sai girado em relação à caverna.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.generator import neighbor_counts
from cavegen.generators.cellular_automata.pesos import importar_sdf
from cavegen.generators.cellular_automata.plot import (
    CONTRASTE_MINIMO_LINHA,
    CORTE_PESO_VOXELS,
    ETAPA_PESO,
    ETAPA_RESULTADO,
    MAX_VIZINHOS,
    MIN_VIZINHOS,
    OPACIDADE_MINIMA,
    PALETAS,
    adicionar_controle_do_peso,
    caminho_da_figura,
    contraste_no_preto,
    cores_das_linhas,
    corte_do_peso,
    dados_da_matriz,
    figura_volumetrica,
    opacidade_por_vizinhos,
    plotar_resultado,
    titulo_do_resultado,
    traces_do_peso,
    vizinhos_das_vivas,
)
from cavegen.generators.cellular_automata.results import load_result, result_path
from cavegen.sdf.manipulacao import comprimir_log


class PlotTests(unittest.TestCase):
    def test_altura_vai_para_o_z_do_plot(self) -> None:
        matriz = np.zeros((4, 5, 6), dtype=int)
        profundidade, altura, largura = 1, 3, 5
        matriz[profundidade, altura, largura] = 1

        x, y, z = dados_da_matriz(matriz)

        self.assertEqual((int(x[0]), int(y[0]), int(z[0])), (largura, profundidade, altura))

    def test_titulo_mostra_o_peso_so_quando_ele_existe(self) -> None:
        dados = {"size": 64, "seed_id": 1, "sensitivity": 9, "border_treatment": "zeros",
                 "iterations": 3}

        self.assertNotIn("peso", titulo_do_resultado(dados, 10))
        self.assertIn("peso 001", titulo_do_resultado({**dados, "peso_id": 1}, 10))


class CorPorVizinhosTests(unittest.TestCase):
    def test_vizinhos_saem_na_ordem_das_coordenadas_e_batem_com_o_ca(self) -> None:
        matriz = np.random.default_rng(5).integers(0, 2, size=(6, 7, 8))

        vizinhos = vizinhos_das_vivas(matriz, "zeros")
        x, y, z = dados_da_matriz(matriz)
        esperado = neighbor_counts(matriz, "zeros")[y, z, x]

        np.testing.assert_array_equal(vizinhos, esperado)
        self.assertGreaterEqual(int(vizinhos.min()), MIN_VIZINHOS)

    def test_opacidade_vai_da_minima_ao_opaco(self) -> None:
        opacidades = opacidade_por_vizinhos(np.array([MIN_VIZINHOS, 14, MAX_VIZINHOS]))

        self.assertAlmostEqual(float(opacidades[0]), OPACIDADE_MINIMA)
        # 14 é o meio da faixa de 1 a 27, então fica no meio da rampa.
        self.assertAlmostEqual(float(opacidades[1]), (OPACIDADE_MINIMA + 1) / 2)
        self.assertAlmostEqual(float(opacidades[2]), 1.0)

    def test_cada_opacidade_vira_um_trace_com_uma_so_barra_de_cor(self) -> None:
        matriz = np.zeros((5, 5, 5), dtype=int)
        matriz[1:4, 1:4, 1:4] = 1
        x, y, z = dados_da_matriz(matriz)
        vizinhos = vizinhos_das_vivas(matriz, "zeros")

        figura = figura_volumetrica(x, y, z, vizinhos, "teste", paleta="Mint",
                                    limites_cor=(MIN_VIZINHOS, MAX_VIZINHOS),
                                    opacidades=opacidade_por_vizinhos(vizinhos))
        nuvem = [t for t in figura.data if t.type == "scatter3d" and t.mode == "markers"]

        self.assertEqual(len(nuvem), np.unique(vizinhos).size)
        self.assertEqual(sum(len(t.x) for t in nuvem), int(matriz.sum()))
        self.assertEqual(sum(bool(t.marker.showscale) for t in nuvem), 1)
        self.assertEqual(nuvem[-1].marker.opacity, max(t.marker.opacity for t in nuvem))

    def test_modo_e_paleta_entram_no_nome_da_figura(self) -> None:
        caminho = caminho_da_figura(7, "vizinhos", "Mint", directory=Path(tempfile.gettempdir()))
        self.assertEqual(caminho.name, "result_007_vizinhos_mint.html")


def linhas_do_historico(figura) -> list:
    return [t for t in figura.data if t.type == "scatter"]


def figura_com_historico(**argumentos):
    matriz = np.zeros((6, 6, 6), dtype=int)
    matriz[2:4, 2:4, 2:4] = 1
    x, y, z = dados_da_matriz(matriz)
    return figura_volumetrica(x, y, z, z, "teste", historico=np.array([100, 40, 30]),
                              total_celulas=216, **argumentos)


class LinhasDoHistoricoTests(unittest.TestCase):
    def test_cores_saem_da_paleta_e_aparecem_no_fundo_preto(self) -> None:
        for paleta in PALETAS:
            with self.subTest(paleta=paleta):
                cores = cores_das_linhas(paleta)
                self.assertEqual(len(set(cores)), 3)
                for cor in cores:
                    self.assertGreaterEqual(contraste_no_preto(cor), CONTRASTE_MINIMO_LINHA)

    def test_contraste_nos_extremos(self) -> None:
        self.assertAlmostEqual(contraste_no_preto("rgb(255, 255, 255)"), 21.0)
        self.assertAlmostEqual(contraste_no_preto("rgb(0, 0, 0)"), 1.0)

    def test_tres_linhas_com_as_transicoes_a_partir_da_iteracao_1(self) -> None:
        figura = figura_com_historico(paleta="Burg", viraram_1=np.array([5, 2]),
                                      viraram_0=np.array([65, 12]))
        vivas, para_1, para_0 = linhas_do_historico(figura)

        self.assertEqual((vivas.name, para_1.name, para_0.name),
                         ("celulas vivas", "viraram 1", "viraram 0"))
        self.assertEqual(list(vivas.x), [0, 1, 2])
        self.assertEqual(list(para_1.x), [1, 2])
        self.assertEqual(list(para_1.y), [5, 2])
        self.assertEqual(list(para_0.x), [1, 2])
        self.assertEqual(list(para_0.y), [65, 12])
        self.assertEqual([t.line.color for t in (vivas, para_1, para_0)],
                         list(cores_das_linhas("Burg")))
        self.assertEqual(len({t.line.dash for t in (vivas, para_1, para_0)}), 3)
        self.assertEqual(len({t.marker.symbol for t in (vivas, para_1, para_0)}), 3)
        self.assertTrue(all(t.showlegend for t in (vivas, para_1, para_0)))

    def test_resultado_antigo_fica_so_com_a_linha_de_vivas(self) -> None:
        figura = figura_com_historico(paleta="Mint")
        linhas = linhas_do_historico(figura)

        self.assertEqual(len(linhas), 1)
        self.assertFalse(linhas[0].showlegend)
        self.assertEqual(linhas[0].line.color, cores_das_linhas("Mint")[0])

    def test_porcentagem_do_hover_usa_o_volume_inteiro(self) -> None:
        figura = figura_com_historico(viraram_1=np.array([54, 2]), viraram_0=np.array([1, 1]))

        self.assertAlmostEqual(float(linhas_do_historico(figura)[1].customdata[0]), 25.0)


def sdf_de_teste() -> np.ndarray:
    """Uma esfera em 32^3: interno positivo, externo negativo e casca em 0."""
    eixos = np.indices((32, 32, 32))
    distancia = np.sqrt(((eixos - 15) ** 2).sum(axis=0))
    return (6 - distancia).astype(np.float32)


class PesoNoPlotTests(unittest.TestCase):
    def test_peso_mostra_os_voxels_acima_do_corte_com_as_coordenadas_do_volume(self) -> None:
        sdf = sdf_de_teste()

        traces = traces_do_peso(sdf)

        self.assertEqual(sum(len(t.x) for t in traces), int((sdf > -CORTE_PESO_VOXELS).sum()))
        for trace in traces[::20]:
            valor = trace.marker.color[0]
            for x, y, z in zip(trace.x, trace.y, trace.z):
                self.assertEqual(sdf[y, z, x], valor)

    def test_log_mostra_os_mesmos_voxels_do_sdf_sem_log(self) -> None:
        sdf = sdf_de_teste()
        peso = comprimir_log(sdf, 2.0)

        self.assertEqual(sum(len(t.x) for t in traces_do_peso(peso, 2.0)),
                         sum(len(t.x) for t in traces_do_peso(sdf)))
        self.assertAlmostEqual(corte_do_peso(2.0), -2 * np.log1p(CORTE_PESO_VOXELS), places=5)

    def test_opacidade_cresce_ate_opaco_e_so_uma_barra_de_cor(self) -> None:
        traces = traces_do_peso(sdf_de_teste())
        opacidades = [t.marker.opacity for t in traces]

        self.assertEqual(opacidades, sorted(opacidades))
        self.assertEqual(opacidades[-1], 1.0)
        self.assertGreater(opacidades[0], 0.0)
        self.assertEqual(sum(bool(t.marker.showscale) for t in traces), 1)
        self.assertTrue(all(t.visible is False for t in traces))

    def test_peso_todo_abaixo_do_corte_nao_gera_trace(self) -> None:
        self.assertEqual(traces_do_peso(np.full((3, 3, 3), -50.0, dtype=np.float32)), [])

    def test_controle_troca_so_a_nuvem_e_mantem_linhas_e_caixa(self) -> None:
        figura = figura_com_historico(viraram_1=np.array([5, 2]), viraram_0=np.array([65, 12]))
        resultado = [t for t in figura.data if t.type == "scatter3d" and t.mode == "markers"]
        peso = traces_do_peso(sdf_de_teste())

        adicionar_controle_do_peso(figura, sdf_de_teste(), "titulo r", "titulo p")

        controle = figura.layout.sliders[0]
        self.assertEqual([p.label for p in controle.steps], [ETAPA_PESO, ETAPA_RESULTADO])
        self.assertEqual(controle.active, 1)
        mascara_peso = controle.steps[0].args[0]["visible"]
        mascara_resultado = controle.steps[1].args[0]["visible"]
        self.assertEqual(len(mascara_peso), len(figura.data))
        self.assertEqual(len(mascara_resultado), len(figura.data))
        self.assertEqual(controle.steps[0].args[1]["title.text"], "titulo p")
        self.assertEqual(controle.steps[1].args[1]["title.text"], "titulo r")

        n_resultado, n_peso = len(resultado), len(peso)
        self.assertEqual(sum(mascara_resultado), len(figura.data) - n_peso)
        self.assertEqual(sum(mascara_peso), len(figura.data) - n_resultado)
        for trace, no_peso, no_resultado in zip(figura.data, mascara_peso, mascara_resultado):
            if trace.type == "scatter":
                self.assertTrue(no_peso and no_resultado)
            elif trace.type == "cone" or trace.mode in ("lines", "text"):
                self.assertTrue(no_peso and no_resultado)
            else:
                self.assertNotEqual(no_peso, no_resultado)

    def test_figura_abre_no_resultado(self) -> None:
        figura = figura_com_historico()
        adicionar_controle_do_peso(figura, sdf_de_teste(), "r", "p")
        passo = figura.layout.sliders[0].steps[figura.layout.sliders[0].active]

        for trace, visivel in zip(figura.data, passo.args[0]["visible"]):
            self.assertEqual(trace.visible is not False, visivel)


class PlotarResultadoTests(unittest.TestCase):
    def setUp(self) -> None:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.resultados = Path(pasta.name) / "results"
        self.pesos = Path(pasta.name) / "pesos"
        self.figuras = Path(pasta.name) / "plots"
        self.resultados.mkdir()

        origem = Path(pasta.name) / "sdf.npz"
        np.savez_compressed(origem, sdf=sdf_de_teste(), convencao="interno positivo")
        importar_sdf(origem, self.pesos, escala_log=2.0)

    def gravar(self, **extras) -> None:
        matriz = (sdf_de_teste() >= 0).astype(int)
        np.savez_compressed(
            result_path(1, self.resultados),
            matrix=matriz, result_id=1, seed_id=1, size=32, sensitivity=12,
            border_treatment="zeros", iterations=2, **extras,
        )

    def plotar(self) -> str:
        destino = plotar_resultado(1, self.resultados, modo="vizinhos", paleta="Burg",
                                   pesos_dir=self.pesos, figuras=self.figuras)
        return destino.read_text(encoding="utf-8")

    def test_resultado_com_peso_tem_controle_e_tres_linhas(self) -> None:
        self.gravar(peso_id=1, live_cells_history=np.array([100, 60, 40]),
                    viraram_1_history=np.array([5, 1]), viraram_0_history=np.array([45, 21]))

        html = self.plotar()

        self.assertIn(ETAPA_PESO, html)
        self.assertIn("log x2", html)
        self.assertIn("viraram 1", html)
        self.assertIn("viraram 0", html)

    def test_ca_basico_nao_tem_controle(self) -> None:
        self.gravar(live_cells_history=np.array([100, 60, 40]),
                    viraram_1_history=np.array([5, 1]), viraram_0_history=np.array([45, 21]))

        html = self.plotar()

        self.assertNotIn(ETAPA_PESO, html)
        self.assertIn("viraram 1", html)

    def test_resultado_antigo_continua_plotando(self) -> None:
        self.gravar(peso_id=1, live_cells_history=np.array([100, 60, 40]))

        dados = load_result(1, self.resultados)
        html = self.plotar()

        self.assertIsNone(dados["viraram_1_history"])
        self.assertIsNone(dados["viraram_0_history"])
        self.assertIn(ETAPA_PESO, html)
        self.assertNotIn("viraram 1", html)

    def test_resultado_sem_historico_nenhum_continua_plotando(self) -> None:
        self.gravar(peso_id=1)

        self.assertIn(ETAPA_PESO, self.plotar())

    def test_peso_que_sumiu_nao_impede_o_plot(self) -> None:
        self.gravar(peso_id=9, live_cells_history=np.array([100, 60, 40]))

        html = self.plotar()

        self.assertNotIn(ETAPA_PESO, html)
        self.assertIn("arquivo do peso nao encontrado", html)


if __name__ == "__main__":
    unittest.main()
