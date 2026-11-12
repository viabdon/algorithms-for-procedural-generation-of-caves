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
from cavegen.generators.cellular_automata.seeds import generate_seed_matrix

BORDAS_DETERMINISTICAS = (BorderTreatment.ZEROS, BorderTreatment.ONES, BorderTreatment.NEAREST)


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
                elif border_treatment is BorderTreatment.NEAREST:
                    # Fora da matriz vale a célula de dentro mais próxima.
                    neighbors += matrix[min(max(current_x, 0), depth - 1),
                                        min(max(current_y, 0), height - 1),
                                        min(max(current_z, 0), width - 1)]

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

        final, historico, _, _ = cellular_automata(volume, 14, BorderTreatment.ZEROS, 4)

        self.assertTrue(np.array_equal(esperado, final))
        self.assertEqual(historico_esperado, list(historico))

    def test_transicoes_batem_com_a_comparacao_celula_a_celula(self) -> None:
        volume = volume_aleatorio((12, 12, 12), semente=6)
        anterior, esperado_1, esperado_0 = volume.copy(), [], []
        for _ in range(5):
            seguinte = iterate_em_laco(anterior, 13, BorderTreatment.ONES)
            esperado_1.append(sum(int(a == 0 and b == 1)
                                  for a, b in zip(anterior.ravel(), seguinte.ravel())))
            esperado_0.append(sum(int(a == 1 and b == 0)
                                  for a, b in zip(anterior.ravel(), seguinte.ravel())))
            anterior = seguinte

        _, historico, viraram_1, viraram_0 = cellular_automata(volume, 13, BorderTreatment.ONES, 5)

        self.assertEqual(esperado_1, list(viraram_1))
        self.assertEqual(esperado_0, list(viraram_0))
        # O saldo das transições de cada iteração é a variação das células vivas.
        np.testing.assert_array_equal(np.diff(historico), viraram_1 - viraram_0)

    def test_sem_iteracoes_nao_ha_transicoes(self) -> None:
        volume = volume_aleatorio((6, 6, 6), semente=7)

        final, historico, viraram_1, viraram_0 = cellular_automata(volume, 13, "zeros", 0)

        np.testing.assert_array_equal(final, volume)
        self.assertEqual(historico.size, 1)
        self.assertEqual((viraram_1.size, viraram_0.size), (0, 0))

    def test_transicoes_aceitam_seed_booleana(self) -> None:
        booleano = np.random.default_rng(8).random((8, 8, 8)) < 0.5

        _, historico, viraram_1, viraram_0 = cellular_automata(booleano, 13, "zeros", 3)

        np.testing.assert_array_equal(np.diff(historico), viraram_1 - viraram_0)

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

    def test_borda_nearest_nao_fecha_nem_abre_a_beirada(self) -> None:
        # Volume uniforme: com NEAREST, a beirada vê o mesmo que o miolo.
        for valor, esperado in ((1, 27), (0, 0)):
            volume = np.full((6, 6, 6), valor, dtype=int)
            somas = neighbor_counts(volume, BorderTreatment.NEAREST)
            self.assertTrue(np.all(somas == esperado))

    def test_borda_nearest_deixa_o_tunel_atravessar_a_beirada(self) -> None:
        # Túnel 4x4 que vai de uma face à outra no eixo z. Com ZEROS, a ponta
        # dele na beirada perde vizinhos e fecha; com NEAREST, continua aberta.
        volume = np.zeros((10, 10, 10), dtype=int)
        volume[3:7, 3:7, :] = 1

        zeros = cellular_automata(volume, 14, BorderTreatment.ZEROS, 3)[0]
        nearest = cellular_automata(volume, 14, BorderTreatment.NEAREST, 3)[0]

        self.assertTrue(np.all(nearest[4:6, 4:6, [0, -1]] == 1))
        self.assertTrue(np.all(zeros[:, :, [0, -1]] == 0))

    def test_borda_random_sorteia_valores_novos_a_cada_chamada(self) -> None:
        # Documenta a limitacao: RANDOM nao e reproduzivel, entao nao entra em
        # comparacao bit a bit nem em varredura que precise repetir a execucao.
        volume = volume_aleatorio((16, 16, 16), semente=2)
        primeira = iterate(volume, 14, BorderTreatment.RANDOM)
        segunda = iterate(volume, 14, BorderTreatment.RANDOM)

        self.assertFalse(np.array_equal(primeira, segunda))
        # Ainda assim as duas ficam na mesma ordem de grandeza de celulas vivas.
        self.assertAlmostEqual(primeira.mean(), segunda.mean(), delta=0.05)


class SementeTests(unittest.TestCase):
    def test_mesma_semente_da_a_mesma_matriz(self) -> None:
        # Sem isso o ajuste genético não repete a avaliação de um candidato.
        primeira = generate_seed_matrix(16, 0.45, seed=7)
        segunda = generate_seed_matrix(16, 0.45, seed=7)

        np.testing.assert_array_equal(primeira, segunda)
        self.assertFalse(np.array_equal(primeira, generate_seed_matrix(16, 0.45, seed=8)))

    def test_semente_segue_a_probabilidade(self) -> None:
        matriz = generate_seed_matrix(32, 0.3, seed=1)

        self.assertEqual(matriz.shape, (32, 32, 32))
        self.assertEqual(set(np.unique(matriz)), {0, 1})
        self.assertAlmostEqual(float(matriz.mean()), 0.3, delta=0.01)

    def test_semente_nao_mexe_no_gerador_global(self) -> None:
        np.random.seed(123)
        esperado = np.random.rand()
        np.random.seed(123)
        generate_seed_matrix(8, 0.5, seed=2)

        self.assertEqual(np.random.rand(), esperado)


if __name__ == "__main__":
    unittest.main()
