"""Garante o contrato do peso somado à contagem de vizinhos do CA.

O peso (o SDF, por exemplo) entra posição por posição na contagem, antes da
comparação com a sensibilidade. O CA sem peso é o baseline da comparação
CA x CA+SDF, então o primeiro contrato é que ele não muda: sem peso e com peso
zero o resultado tem de ser o mesmo do autômato básico, bit a bit.
"""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.generators.cellular_automata.generator import (
    BorderTreatment,
    aplicar_peso,
    cellular_automata,
    iterate,
    neighbor_counts,
)


def matriz_aleatoria(formato: tuple[int, int, int], seed: int) -> np.ndarray:
    """Matriz binária reprodutível com cerca de metade das células vivas."""
    return np.random.default_rng(seed).integers(0, 2, size=formato)


class PesoTests(unittest.TestCase):
    def test_peso_zero_reproduz_o_ca_basico(self) -> None:
        inicial = matriz_aleatoria((9, 10, 11), seed=1)
        zeros = np.zeros(inicial.shape, dtype=np.float32)

        for borda in (BorderTreatment.ZEROS, BorderTreatment.ONES):
            basico, historico_basico = cellular_automata(inicial, 14, borda, 4)
            com_peso, historico_peso = cellular_automata(inicial, 14, borda, 4, peso=zeros)
            np.testing.assert_array_equal(com_peso, basico)
            np.testing.assert_array_equal(historico_peso, historico_basico)

    def test_passo_compara_a_contagem_somada_ao_peso(self) -> None:
        matriz = matriz_aleatoria((8, 8, 8), seed=2)
        peso = np.random.default_rng(3).uniform(-5, 2, size=matriz.shape).astype(np.float32)
        esperado = (neighbor_counts(matriz, BorderTreatment.ZEROS) + peso >= 12).astype(int)

        np.testing.assert_array_equal(iterate(matriz, 12, BorderTreatment.ZEROS, peso), esperado)

    def test_peso_negativo_impede_a_celula_de_virar_1(self) -> None:
        # Tudo vivo: cada célula do miolo tem os 27 vizinhos, mais que a sensibilidade.
        matriz = np.ones((5, 5, 5), dtype=int)
        peso = np.zeros(matriz.shape, dtype=np.float32)
        peso[2, 2, 2] = -27

        saida = iterate(matriz, 14, BorderTreatment.ONES, peso)

        self.assertEqual(saida[2, 2, 2], 0)
        self.assertEqual(int(saida.sum()), matriz.size - 1)

    def test_peso_positivo_faz_a_celula_virar_1_sem_vizinhos(self) -> None:
        matriz = np.zeros((5, 5, 5), dtype=int)
        peso = np.zeros(matriz.shape, dtype=np.float32)
        peso[2, 2, 2] = 14

        saida = iterate(matriz, 14, BorderTreatment.ZEROS, peso)

        self.assertEqual(saida[2, 2, 2], 1)
        self.assertEqual(int(saida.sum()), 1)

    def test_peso_com_formato_diferente_falha(self) -> None:
        vizinhos = np.zeros((4, 4, 4), dtype=np.int16)

        with self.assertRaises(ValueError):
            aplicar_peso(vizinhos, np.zeros((4, 4, 5), dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
