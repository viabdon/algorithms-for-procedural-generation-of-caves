"""Testes adversariais do random walk ponderado: fidelidade ao C# e casos-limite.

As funções *_csharp abaixo são traduções literais, laço a laço, de
WeightedRandomWalk.cs (3D-Cave-Generation, commit 7a6c617). O port em
caminhada.py usa numpy (searchsorted, del de fatia); estes testes conferem
que a vetorização não muda a escolha nem o corte de laços.
"""

from __future__ import annotations

import json
import random
import unittest
from unittest import mock

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.generators.random_walk import (
    RandomWalkGenerator,
    caminhar,
    carregar_caverna,
    cortar_lacos,
    generate_random_walk,
    movimento_ponderado,
    movimentos_com_meio_passo,
    voxelizar,
)
from cavegen.generators.random_walk.caminhada import TOLERANCIA_UNITY
from cavegen.generators.random_walk.voxelizacao import MARGEM, encaixe

LADO = 32


def iguais_csharp(a: np.ndarray, b: np.ndarray) -> bool:
    # Vector3.operator==: sqrMagnitude da diferença < kEpsilon².
    d = a - b
    return float(d @ d) < TOLERANCIA_UNITY * TOLERANCIA_UNITY


def movimento_csharp(direcao, weight, k, spacer, movimentos, sorteio):
    unitario = direcao / np.linalg.norm(direcao)
    probabilidades = []
    for m in movimentos:
        probabilidades.append(np.exp((unitario @ (m / np.linalg.norm(m))) * weight * k))
    soma = sum(probabilidades)
    probabilidades = [p / soma for p in probabilidades]
    maximo = 0.0
    for i, p in enumerate(probabilidades):
        maximo += p
        if sorteio <= maximo:
            return movimentos[i] * spacer
    return np.zeros(3)


def cortar_lacos_csharp(caminho: list) -> list:
    caminho = list(caminho)
    i = 0
    while i < len(caminho):
        atual = caminho[i]
        j = i + 1
        while j < len(caminho):
            if iguais_csharp(atual, caminho[j]):
                caminho[i:j] = []  # RemoveRange(i, j - i)
            j += 1
        i += 1
    return caminho


class _RngFixo:
    """Stub de rng que devolve sempre o mesmo número em random()."""

    def __init__(self, valor: float) -> None:
        self.valor = valor

    def random(self) -> float:
        return self.valor


class FidelidadeAoCSharpTest(unittest.TestCase):
    def test_sorteio_igual_ao_laco_do_csharp_em_direcoes_aleatorias(self) -> None:
        movimentos = movimentos_com_meio_passo()
        gerador = numpy_rng(11)
        for weight, k in ((1.0, 30.0), (0.1, 1.0), (0.5, 7.0)):
            for _ in range(200):
                direcao = gerador.normal(size=3) * gerador.uniform(6, 500)
                sorteio = float(gerador.random())
                esperado = movimento_csharp(direcao, weight, k, 5.0, movimentos, sorteio)
                obtido = movimento_ponderado(direcao, weight, k, 5.0, movimentos,
                                             _RngFixo(sorteio))
                np.testing.assert_array_equal(obtido, esperado)

    def test_sorteio_igual_a_acumulada_escolhe_esse_movimento(self) -> None:
        # random <= probabilityMax: o empate fica com o movimento i, não com o i + 1.
        movimentos = movimentos_com_meio_passo()
        direcao = np.array([3.0, -1.0, 2.0])
        unitarios = movimentos / np.linalg.norm(movimentos, axis=1, keepdims=True)
        p = np.exp(unitarios @ (direcao / np.linalg.norm(direcao)) * 30.0)
        acumulada = np.cumsum(p / p.sum())
        for i in (0, 40, 61, 100):
            obtido = movimento_ponderado(direcao, 1.0, 30.0, 5.0, movimentos,
                                         _RngFixo(float(acumulada[i])))
            np.testing.assert_array_equal(obtido, movimentos[i] * 5.0)

    def test_sorteio_acima_da_soma_devolve_zero(self) -> None:
        movimentos = movimentos_com_meio_passo()
        acima = float(np.nextafter(1.0, 2.0))
        obtido = movimento_ponderado(np.array([1.0, 2.0, 3.0]), 1.0, 30.0, 5.0, movimentos,
                                     _RngFixo(acima))
        np.testing.assert_array_equal(obtido, np.zeros(3))

    def test_corte_de_lacos_igual_ao_for_do_csharp(self) -> None:
        # Pontos numa grade pequena repetem muito: exercita cortes em sequência.
        gerador = numpy_rng(5)
        for _ in range(300):
            n = int(gerador.integers(2, 25))
            caminho = list(gerador.integers(0, 3, size=(n, 3)).astype(float))
            obtido = cortar_lacos(caminho)
            esperado = cortar_lacos_csharp(caminho)
            self.assertEqual(len(obtido), len(esperado))
            for a, b in zip(obtido, esperado):
                np.testing.assert_array_equal(a, b)

    def test_caminhar_aplica_o_corte_duas_vezes(self) -> None:
        # Roteiro: A, B, A, C, A, B, ... Uma passada deixa A repetido; a segunda tira.
        x, y = np.array([5.0, 0, 0]), np.array([0, 5.0, 0])
        roteiro = [x, -x, y, -y] + [x] * 19
        inicio, fim = np.zeros(3), np.array([100.0, 0, 0])

        esperado = [inicio]
        for m in roteiro:
            esperado.append(esperado[-1] + m)
        esperado.append(fim)
        uma = cortar_lacos_csharp(esperado)
        duas = cortar_lacos_csharp(uma)
        self.assertNotEqual(len(uma), len(duas))

        with mock.patch("cavegen.generators.random_walk.caminhada.movimento_ponderado",
                        side_effect=roteiro):
            obtido = caminhar(inicio, fim, 1.0, 30.0, 5.0, numpy_rng(0))
        np.testing.assert_array_equal(obtido, np.array(duas))

    def test_destino_entra_quando_para_a_menos_de_spacer(self) -> None:
        # Para em x = 96 (distância 4 < spacer): o destino entra como último ponto.
        roteiro = [np.array([4.0, 0, 0])] * 24
        with mock.patch("cavegen.generators.random_walk.caminhada.movimento_ponderado",
                        side_effect=roteiro):
            obtido = caminhar(np.zeros(3), np.array([100.0, 0, 0]), 1.0, 30.0, 5.0,
                              numpy_rng(0))
        self.assertEqual(len(obtido), 26)
        np.testing.assert_array_equal(obtido[-2], [96.0, 0, 0])
        np.testing.assert_array_equal(obtido[-1], [100.0, 0, 0])

    def test_trava_de_passos_dispara_quando_nao_chega(self) -> None:
        # weight negativo afasta do destino; com a trava baixa o erro sai rápido.
        with mock.patch("cavegen.generators.random_walk.caminhada.MAXIMO_DE_PASSOS", 50):
            with self.assertRaises(RuntimeError):
                caminhar(np.zeros(3), np.array([100.0, 0, 0]), -1.0, 30.0, 5.0, numpy_rng(0))


class VoxelizacaoEixosTest(unittest.TestCase):
    def test_cada_eixo_da_unity_vai_para_o_eixo_certo_da_grade(self) -> None:
        # x da Unity -> width (eixo 2), y -> height (eixo 1), z -> depth (eixo 0).
        for eixo_unity, eixo_grade in ((0, 2), (1, 1), (2, 0)):
            fim = np.zeros(3)
            fim[eixo_unity] = 100.0
            pontos = np.array([np.zeros(3), fim])
            vazio, _ = voxelizar(pontos, np.array([0, 2]), 1.0, LADO, raio_voxels=1.0)
            extensao = [np.ptp(np.nonzero(vazio)[e]) for e in range(3)]
            self.assertEqual(int(np.argmax(extensao)), eixo_grade, eixo_unity)

    def test_encaixe_mesma_escala_centralizado_e_com_margem(self) -> None:
        pontos = np.array([[0.0, 0, 0], [10.0, 40.0, 100.0], [3.0, -5.0, 20.0]])
        raio = 2.0
        escala, deslocamento = encaixe(pontos, raio, LADO)
        minimos = (pontos.min(axis=0) - raio) * escala + deslocamento
        maximos = (pontos.max(axis=0) + raio) * escala + deslocamento
        # Eixo mais longo encosta na margem dos dois lados.
        maior = int(np.argmax(maximos - minimos))
        self.assertAlmostEqual(minimos[maior], MARGEM)
        self.assertAlmostEqual(maximos[maior], LADO - 1 - MARGEM)
        # Todos os eixos centralizados no meio da grade.
        np.testing.assert_allclose((minimos + maximos) / 2, (LADO - 1) / 2)


class GeradorAdversarialTest(unittest.TestCase):
    def test_override_de_spacer_muda_o_volume_e_os_metadados(self) -> None:
        padrao = generate_random_walk((LADO,) * 3, seed=1, caverna="example")
        trocado = generate_random_walk((LADO,) * 3, seed=1, caverna="example", spacer=3)
        self.assertEqual(trocado.metadata["spacer"], 3.0)
        self.assertEqual(padrao.metadata["spacer"], 5.0)
        self.assertFalse(np.array_equal(padrao.data, trocado.data))
        # O override não vaza para o grafo carregado depois.
        self.assertEqual(carregar_caverna("example").parametros["spacer"], 5.0)

    def test_override_de_weight_vai_para_os_metadados(self) -> None:
        volume = generate_random_walk((LADO,) * 3, seed=1, caverna="example", weight=0.5)
        self.assertEqual(volume.metadata["weight"], 0.5)

    def test_classe_igual_a_funcao(self) -> None:
        gerador = RandomWalkGenerator(caverna="example", k=10, raio_voxels=1.0)
        a = gerador.generate((LADO,) * 3, seed=2)
        b = generate_random_walk((LADO,) * 3, seed=2, caverna="example", k=10, raio_voxels=1.0)
        np.testing.assert_array_equal(a.data, b.data)
        self.assertEqual(a.metadata, b.metadata)

    def test_nao_mexe_no_rng_global(self) -> None:
        np.random.seed(123)
        random.seed(123)
        antes_np = np.random.get_state()[1].copy()
        antes_py = random.getstate()
        generate_random_walk((LADO,) * 3, seed=1, caverna="example")
        np.testing.assert_array_equal(np.random.get_state()[1], antes_np)
        self.assertEqual(random.getstate(), antes_py)

    def test_metadados_viram_json_com_seed_inteiro_numpy(self) -> None:
        # Seed vinda de rng.integers (ex.: busca do GA) é np.int64.
        volume = generate_random_walk((LADO,) * 3, seed=np.int64(1), caverna="example")
        json.dumps(volume.metadata)

    def test_grade_pequena_demais_para_a_margem_e_recusada(self) -> None:
        # lado - 1 - 2 * MARGEM <= 0 deixa a escala zero ou negativa (caverna espelhada).
        for lado in (3, 4, 5):
            with self.subTest(lado=lado):
                with self.assertRaises(ValueError):
                    generate_random_walk((lado,) * 3, seed=1, caverna="example")


if __name__ == "__main__":
    unittest.main()
