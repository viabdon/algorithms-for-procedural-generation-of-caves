"""Garante o contrato do random walk ponderado portado do projeto base.

O RW precisa continuar fiel ao do TCC base (3D-Cave-Generation, commit
7a6c617), então os testes travam o que vem dele: o grafo de waypoints
exportado da cena, o caminho que sai de um waypoint e chega no outro e o
tamanho dos passos. Também travam o que é do projeto: a mesma seed dá a mesma
caverna e a saída segue o contrato Volume3D (booleano ZYX, True = vazio).

Os passos do meio do caminho são movimentos sorteados vezes spacer, então
ficam entre 0,5 * spacer (meio passo num eixo) e sqrt(3) * spacer (passo
inteiro nos três). O último passo é outro caso: o original para quando chega
a menos de spacer do destino e acrescenta o destino, então ele pode ser
qualquer distância até spacer.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.datastream.voxel_io import load_volume_npz, save_volume_npz
from cavegen.generators.random_walk import (
    RAIO_PADRAO,
    carregar_caverna,
    cavernas_disponiveis,
    classificar,
    gerar_caminhos,
    generate_random_walk,
    movimentos_com_meio_passo,
)
from cavegen.generators.random_walk.caminhada import iguais
from cavegen.generators.random_walk.exportar_cena import CENA, ler_cena
from cavegen.generators.random_walk.voxelizacao import BORDA, FORA, INTERNO, encaixe, para_grade
from cavegen.metrics.connectivity import largest_component_ratio

CAVERNAS = ("example", "knotlow_cavern", "upper_long_churns", "odins_mine")
LADO = 64


class CenaExportadaTest(unittest.TestCase):
    def test_as_quatro_cavernas_foram_exportadas_na_ordem_da_cena(self) -> None:
        self.assertEqual(cavernas_disponiveis(), list(CAVERNAS))

    def test_tamanho_dos_grafos_e_parametros(self) -> None:
        esperado = {"example": (19, 18), "knotlow_cavern": (72, 71),
                    "upper_long_churns": (77, 78), "odins_mine": (140, 140)}
        for caverna, (waypoints, ligacoes) in esperado.items():
            grafo = carregar_caverna(caverna)
            self.assertEqual(len(grafo.nomes), waypoints, caverna)
            self.assertEqual(len(grafo.arestas), ligacoes, caverna)
            self.assertEqual(len(set(grafo.nomes)), waypoints, caverna)
            p = grafo.parametros
            self.assertEqual((p["weight"], p["k"], p["spacer"], p["segments"]),
                             (1.0, 30.0, 5.0, 6.0), caverna)

    @unittest.skipUnless(CENA.exists(), "projeto base fora de external/ (não vai para o Git)")
    def test_arquivos_exportados_sao_identicos_a_cena(self) -> None:
        for da_cena in ler_cena():
            do_arquivo = carregar_caverna(da_cena.nome)
            self.assertEqual(do_arquivo.nome, da_cena.nome)
            self.assertEqual(do_arquivo.nomes, da_cena.nomes)
            np.testing.assert_array_equal(do_arquivo.posicoes, da_cena.posicoes)
            np.testing.assert_array_equal(do_arquivo.arestas, da_cena.arestas)
            self.assertEqual(do_arquivo.parametros, da_cena.parametros)

    def test_caverna_desconhecida_avisa_as_disponiveis(self) -> None:
        with self.assertRaisesRegex(ValueError, "knotlow_cavern"):
            carregar_caverna("nao_existe")


class CaminhadaTest(unittest.TestCase):
    def test_124_movimentos_na_ordem_do_csharp(self) -> None:
        movimentos = movimentos_com_meio_passo()
        self.assertEqual(movimentos.shape, (124, 3))
        # x no laço de fora, z no de dentro, sem o (0, 0, 0).
        np.testing.assert_array_equal(movimentos[0], [-1.0, -1.0, -1.0])
        np.testing.assert_array_equal(movimentos[1], [-1.0, -1.0, -0.5])
        np.testing.assert_array_equal(movimentos[61], [0.0, 0.0, -0.5])
        np.testing.assert_array_equal(movimentos[62], [0.0, 0.0, 0.5])
        np.testing.assert_array_equal(movimentos[-1], [1.0, 1.0, 1.0])

    def test_mesma_seed_mesmos_caminhos(self) -> None:
        grafo = carregar_caverna("example")
        pontos_a, inicios_a = gerar_caminhos(grafo, numpy_rng(7))
        pontos_b, inicios_b = gerar_caminhos(grafo, numpy_rng(7))
        np.testing.assert_array_equal(pontos_a, pontos_b)
        np.testing.assert_array_equal(inicios_a, inicios_b)

    def test_todo_caminho_vai_do_waypoint_de_origem_ao_de_destino(self) -> None:
        for caverna in CAVERNAS:
            grafo = carregar_caverna(caverna)
            pontos, inicios = gerar_caminhos(grafo, numpy_rng(1))
            self.assertEqual(len(inicios) - 1, len(grafo.arestas), caverna)
            for (a, b), (inicio, fim) in zip(grafo.arestas, pairwise(inicios)):
                np.testing.assert_array_equal(pontos[inicio], grafo.posicoes[a])
                np.testing.assert_array_equal(pontos[fim - 1], grafo.posicoes[b])

    def test_tamanho_dos_passos(self) -> None:
        for caverna in CAVERNAS:
            grafo = carregar_caverna(caverna)
            spacer = grafo.parametros["spacer"]
            for seed in (1, 2):
                pontos, inicios = gerar_caminhos(grafo, numpy_rng(seed))
                for inicio, fim in pairwise(inicios):
                    passos = np.linalg.norm(np.diff(pontos[inicio:fim], axis=0), axis=1)
                    meio, ultimo = passos[:-1], passos[-1]
                    self.assertTrue(np.all(meio >= 0.5 * spacer - 1e-9), caverna)
                    self.assertTrue(np.all(meio <= np.sqrt(3) * spacer + 1e-9), caverna)
                    self.assertGreater(ultimo, 0, caverna)
                    self.assertLessEqual(ultimo, spacer + 1e-9, caverna)

    def test_caminho_sem_ponto_repetido_depois_do_corte_de_lacos(self) -> None:
        grafo = carregar_caverna("knotlow_cavern")
        pontos, inicios = gerar_caminhos(grafo, numpy_rng(1))
        for inicio, fim in pairwise(inicios):
            caminho = pontos[inicio:fim]
            for i in range(len(caminho)):
                for j in range(i + 1, len(caminho)):
                    self.assertFalse(iguais(caminho[i], caminho[j]))


class GeradorTest(unittest.TestCase):
    def test_mesma_seed_mesmo_volume_e_seeds_diferentes_mudam(self) -> None:
        a = generate_random_walk((LADO,) * 3, seed=3, caverna="example")
        b = generate_random_walk((LADO,) * 3, seed=3, caverna="example")
        c = generate_random_walk((LADO,) * 3, seed=4, caverna="example")
        np.testing.assert_array_equal(a.data, b.data)
        self.assertFalse(np.array_equal(a.data, c.data))

    def test_contrato_volume3d_booleano_zyx_com_vazio_true(self) -> None:
        volume = generate_random_walk((LADO,) * 3, seed=1, caverna="knotlow_cavern")
        self.assertEqual(volume.data.dtype, np.bool_)
        self.assertEqual(volume.shape, (LADO,) * 3)
        self.assertGreater(volume.open_voxels, 0)
        self.assertLess(volume.fill_ratio, 0.5)

        # Todo waypoint cai num voxel vazio quando levado à grade como (z, y, x) da Unity;
        # na ordem errada dos eixos eles cairiam na rocha.
        grafo = carregar_caverna("knotlow_cavern")
        meta = volume.metadata
        indices = np.rint(para_grade(grafo.posicoes) * meta["escala"]
                          + np.array(meta["deslocamento"])).astype(int)
        self.assertTrue(np.all(volume.data[tuple(indices.T)]))
        trocados = np.rint(grafo.posicoes * meta["escala"]
                           + np.array(meta["deslocamento"])).astype(int)
        dentro = np.all((trocados >= 0) & (trocados < LADO), axis=1)
        self.assertFalse(np.all(volume.data[tuple(trocados[dentro].T)]))

    def test_caverna_num_componente_so_com_o_raio_padrao(self) -> None:
        for caverna in CAVERNAS:
            volume = generate_random_walk((LADO,) * 3, seed=1, caverna=caverna)
            self.assertEqual(volume.metadata["raio_voxels"], RAIO_PADRAO)
            self.assertEqual(largest_component_ratio(volume.data, connectivity=6), 1.0, caverna)

    def test_parametros_none_sao_os_da_cena(self) -> None:
        p = carregar_caverna("example").parametros
        padrao = generate_random_walk((32,) * 3, seed=1, caverna="example")
        explicito = generate_random_walk((32,) * 3, seed=1, caverna="example",
                                         weight=p["weight"], k=p["k"], spacer=p["spacer"])
        np.testing.assert_array_equal(padrao.data, explicito.data)

    def test_grade_nao_cubica_e_recusada(self) -> None:
        with self.assertRaisesRegex(ValueError, "cúbica"):
            generate_random_walk((32, 64, 64), seed=1)

    def test_metadados_viajam_no_npz(self) -> None:
        volume = generate_random_walk((32,) * 3, seed=1, caverna="example")
        json.dumps(volume.metadata)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "rw.npz"
            save_volume_npz(volume, caminho)
            lido = load_volume_npz(caminho)
        np.testing.assert_array_equal(lido.data, volume.data)
        self.assertEqual(lido.metadata["caverna"], "Example")
        self.assertEqual(lido.metadata["seed"], 1)


class VoxelizacaoTest(unittest.TestCase):
    def test_encaixe_deixa_a_caverna_dentro_da_grade_com_margem(self) -> None:
        grafo = carregar_caverna("odins_mine")
        pontos, _ = gerar_caminhos(grafo, numpy_rng(1))
        na_grade = para_grade(pontos)
        escala, deslocamento = encaixe(na_grade, grafo.parametros["radius"], LADO)
        indices = na_grade * escala + deslocamento
        self.assertGreaterEqual(indices.min(), 2 - 1e-9)
        self.assertLessEqual(indices.max(), LADO - 1 - 2 + 1e-9)

    def test_classificacao_borda_e_interno(self) -> None:
        vazio = np.zeros((5, 5, 5), dtype=bool)
        vazio[1:4, 1:4, 1:4] = True
        classificacao = classificar(vazio)
        self.assertEqual(classificacao[2, 2, 2], INTERNO)
        self.assertEqual(classificacao[1, 1, 1], BORDA)
        self.assertEqual(classificacao[0, 0, 0], FORA)
        self.assertEqual(int((classificacao == BORDA).sum()), 26)

        # Fora da grade é rocha: vazio encostado na beira é borda.
        cheio = np.ones((3, 3, 3), dtype=bool)
        self.assertEqual(int((classificar(cheio) == INTERNO).sum()), 1)


if __name__ == "__main__":
    unittest.main()
