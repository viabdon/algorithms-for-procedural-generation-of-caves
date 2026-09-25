"""Garante que a contagem vetorizada produz o mesmo resultado que o laço original.

A contagem de vizinhos passou de um laço tríplice por célula para uma convolução
3x3x3. Como a mudança é de implementação e não de regra, o laço original fica
preservado aqui como oráculo: ele é lento, mas é a tradução literal da regra do
autômato, e comparar as duas versões é o que sustenta a afirmação de que a
otimização não alterou nenhum resultado do TCC.

A borda RANDOM fica de fora das comparações bit a bit porque sorteia valores a
cada execução: nem o laço original concorda consigo mesmo entre duas chamadas.
"""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.generators.cellular_automata.generator import (
    BorderTreatment,
    cellular_automata,
    iterate,
    neighbor_counts,
)

BORDAS_DETERMINISTICAS = (BorderTreatment.ZEROS, BorderTreatment.ONES)


def count_neighbors_em_laco(matrix: np.ndarray, x: int, y: int, z: int,
                            border_treatment: BorderTreatment) -> int:
    """Soma as células vivas no cubo 3x3x3 centrado em (x, y, z), incluindo a própria."""
    depth, height, width = matrix.shape
    neighbors = 0

    for i in range(3):
        for j in range(3):
            for k in range(3):
                current_x, current_y, current_z = x + i - 1, y + j - 1, z + k - 1
                inside = (0 <= current_x < depth and 0 <= current_y < height
                          and 0 <= current_z < width)

                if inside:
                    neighbors += matrix[current_x, current_y, current_z]
                elif border_treatment is BorderTreatment.ONES:
                    neighbors += 1

    return neighbors


def iterate_em_laco(matrix: np.ndarray, sensitivity: int,
                    border_treatment: BorderTreatment) -> np.ndarray:
    """Um passo do autômato pela versão original, célula por célula."""
    saida = np.zeros(matrix.shape, dtype=int)

    for x in range(matrix.shape[0]):
        for y in range(matrix.shape[1]):
            for z in range(matrix.shape[2]):
                vizinhos = count_neighbors_em_laco(matrix, x, y, z, border_treatment)
                saida[x, y, z] = 1 if vizinhos >= sensitivity else 0

    return saida


def volume_aleatorio(shape: tuple[int, ...], semente: int) -> np.ndarray:
    return (np.random.default_rng(semente).random(shape) < 0.5).astype(int)


class ContagemVetorizadaTests(unittest.TestCase):
    def test_um_passo_bate_com_o_laco_em_toda_a_faixa_de_sensibilidade(self) -> None:
        # 0 e 27 sao os extremos degenerados: tudo vivo e tudo morto.
        for borda in BORDAS_DETERMINISTICAS:
            for sensibilidade in (0, 1, 5, 13, 14, 18, 27):
                with self.subTest(borda=borda.value, sensibilidade=sensibilidade):
                    volume = volume_aleatorio((12, 12, 12), semente=sensibilidade)
                    esperado = iterate_em_laco(volume, sensibilidade, borda)
                    self.assertTrue(np.array_equal(esperado, iterate(volume, sensibilidade, borda)))

    def test_um_passo_bate_com_o_laco_em_volume_nao_cubico(self) -> None:
        for shape in ((8, 12, 10), (5, 5, 16)):
            with self.subTest(shape=shape):
                volume = volume_aleatorio(shape, semente=3)
                esperado = iterate_em_laco(volume, 13, BorderTreatment.ZEROS)
                self.assertTrue(np.array_equal(esperado, iterate(volume, 13, BorderTreatment.ZEROS)))

    def test_matriz_booleana_da_o_mesmo_que_matriz_de_inteiros(self) -> None:
        # As seeds podem chegar como bool; a moldura precisa converter sozinha.
        booleano = np.random.default_rng(11).random((10, 10, 10)) < 0.45
        esperado = iterate_em_laco(booleano.astype(int), 13, BorderTreatment.ONES)
        self.assertTrue(np.array_equal(esperado, iterate(booleano, 13, BorderTreatment.ONES)))

    def test_varias_iteracoes_e_historico_batem_com_o_laco(self) -> None:
        volume = volume_aleatorio((12, 12, 12), semente=5)
        esperado, historico_esperado = volume.copy(), [int(volume.sum())]
        for _ in range(4):
            esperado = iterate_em_laco(esperado, 14, BorderTreatment.ZEROS)
            historico_esperado.append(int(esperado.sum()))

        final, historico = cellular_automata(volume, 14, BorderTreatment.ZEROS, 4)

        self.assertTrue(np.array_equal(esperado, final))
        self.assertEqual(historico_esperado, list(historico))

    def test_contagem_preserva_o_formato_e_respeita_o_maximo(self) -> None:
        volume = np.ones((6, 7, 8), dtype=int)
        somas = neighbor_counts(volume, BorderTreatment.ONES)

        self.assertEqual(volume.shape, somas.shape)
        # Volume cheio com borda cheia: toda celula ve as 27 do cubo.
        self.assertTrue(np.all(somas == 27))

    def test_borda_zeros_conta_menos_que_borda_ones_nas_quinas(self) -> None:
        volume = np.ones((6, 6, 6), dtype=int)
        zeros = neighbor_counts(volume, BorderTreatment.ZEROS)
        ones = neighbor_counts(volume, BorderTreatment.ONES)

        self.assertEqual(8, int(zeros[0, 0, 0]))  # so o octante interno existe
        self.assertEqual(27, int(ones[0, 0, 0]))
        self.assertEqual(int(zeros[3, 3, 3]), int(ones[3, 3, 3]))  # miolo nao muda

    def test_borda_random_sorteia_valores_novos_a_cada_chamada(self) -> None:
        # Documenta a limitacao: RANDOM nao e reproduzivel, entao nao entra em
        # comparacao bit a bit nem em varredura que precise repetir a execucao.
        volume = volume_aleatorio((16, 16, 16), semente=2)
        primeira = iterate(volume, 14, BorderTreatment.RANDOM)
        segunda = iterate(volume, 14, BorderTreatment.RANDOM)

        self.assertFalse(np.array_equal(primeira, segunda))
        # Ainda assim as duas ficam na mesma ordem de grandeza de celulas vivas.
        self.assertAlmostEqual(primeira.mean(), segunda.mean(), delta=0.05)


if __name__ == "__main__":
    unittest.main()
