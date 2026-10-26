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
from cavegen.generators.cellular_automata.plot import (
    MAX_VIZINHOS,
    MIN_VIZINHOS,
    OPACIDADE_MINIMA,
    caminho_da_figura,
    dados_da_matriz,
    figura_volumetrica,
    opacidade_por_vizinhos,
    titulo_do_resultado,
    vizinhos_das_vivas,
)


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


if __name__ == "__main__":
    unittest.main()
