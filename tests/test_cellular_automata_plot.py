"""Garante a troca de eixos e o título do plot do CA.

A matriz do CA é (depth, height, width), a mesma ordem do SDF que o guia. O
plot tem de pôr a altura na vertical, como os plots do Elaphes e do SDF, senão
o CA guiado sai girado em relação à caverna.
"""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.generators.cellular_automata.plot import dados_da_matriz, titulo_do_resultado


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


if __name__ == "__main__":
    unittest.main()
