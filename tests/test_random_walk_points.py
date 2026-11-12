"""Confere as regras do Random Walk com pontos sorteados (tools/random_walk_points).

    uv run python -m unittest tests/test_random_walk_points.py -v
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.pesos import (
    comprimir_log,
    load_peso_info,
    load_peso_matrix,
)
from cavegen.generators.random_walk.voxelizacao import classificar
from cavegen.metrics.connectivity import connected_components
from tools.random_walk_points.generator import (
    DESCIDA,
    INICIAL,
    LIGACAO,
    angulo_de_desvio,
    candidatos_abaixo,
    descer_no_veio,
    escavar_rede,
    gerar_rede,
    montar_vizinhos,
    par_mais_proximo,
    proximo_no,
    separar_componentes,
    target_mais_proximo,
)
from tools.random_walk_points.peso import calcular_sdf, gerar_peso
from tools.random_walk_points.plot import ETAPAS, figura_progressao
from tools.random_walk_points.results import load_result, run_and_save

SEEDS = range(25)

class RegrasTests(unittest.TestCase):
    def test_angulo_de_desvio(self):
        de = np.array([0.0, 10.0, 0.0])
        self.assertAlmostEqual(angulo_de_desvio(de, np.array([0.0, 0.0, 0.0])), 0.0)
        self.assertAlmostEqual(angulo_de_desvio(de, np.array([10.0, 0.0, 0.0])), 45.0)
        self.assertAlmostEqual(angulo_de_desvio(de, np.array([0.0, 0.0, 10.0])), 45.0)
        self.assertAlmostEqual(angulo_de_desvio(de, np.array([3.0, 10.0, 4.0])), 90.0)

    def test_candidato_e_o_mais_alto_abaixo_de_cada_veio(self):
        pontos = np.array([[0, 50, 0], [0, 60, 0], [0, 40, 0], [0, 30, 0], [0, 20, 0]], float)
        veio_de = {0: 0, 1: 1, 2: 1, 3: 1, 4: 2}

        candidatos = candidatos_abaixo(0, pontos, veio_de, {0})

        # Do veio 1, o nó 1 está acima e o 3 perde para o 2; o veio 2 só tem o 4.
        self.assertEqual(candidatos, [2, 4])

    def test_proximo_no_escolhe_o_menor_angulo_e_ignora_o_resto_do_veio(self):
        # O nó 3 é o mais reto de todos, mas o nó 2 é mais alto no mesmo veio.
        pontos = np.array([[0, 50, 0], [20, 30, 0], [30, 40, 0], [0, 10, 0]], float)
        veio_de = {0: 0, 1: 1, 2: 2, 3: 2}

        self.assertEqual(proximo_no(0, pontos, veio_de, {0}), 1)

    def test_proximo_no_sem_nada_abaixo(self):
        pontos = np.array([[0, 10, 0], [5, 20, 0]], float)

        self.assertIsNone(proximo_no(0, pontos, {0: 0, 1: 1}, {0}))

    def test_descida_no_veio_nao_sobe(self):
        alturas = np.array([30.0, 50.0, 10.0])
        # 0 só alcança 2 passando por 1, que está acima: fica parado em 0.
        vizinhos = {0: [1], 1: [0, 2], 2: [1]}

        self.assertEqual(descer_no_veio(0, vizinhos, alturas), [0])
        self.assertEqual(descer_no_veio(1, vizinhos, alturas), [1, 2])

    def test_par_mais_proximo(self):
        pontos = np.array([[0, 0, 0], [10, 0, 0], [11, 0, 0], [50, 0, 0]], float)

        self.assertEqual(par_mais_proximo([0, 1], [2, 3], pontos), (1, 2))

class RedeTests(unittest.TestCase):
    def test_mesma_seed_da_a_mesma_rede(self):
        a, b = gerar_rede(7), gerar_rede(7)

        np.testing.assert_array_equal(a.pontos, b.pontos)
        self.assertEqual(a.central_nos, b.central_nos)
        self.assertEqual(len(a.caminhos), len(b.caminhos))
        for x, y in zip(a.caminhos, b.caminhos):
            np.testing.assert_array_equal(x.pontos, y.pontos)

    def test_divisao_e_exclusao(self):
        for seed in SEEDS:
            rede = gerar_rede(seed, n_pontos=21)
            self.assertEqual((len(rede.sources), len(rede.targets)), (10, 11))
            self.assertEqual(len(np.intersect1d(rede.sources, rede.targets)), 0)
            self.assertEqual(sum(c.etapa == INICIAL for c in rede.caminhos), len(rede.sources))
            chegaram = {c.destino for c in rede.caminhos if c.etapa == INICIAL}
            self.assertEqual(set(rede.excluidos.tolist()), set(rede.targets.tolist()) - chegaram)
            self.assertEqual(set(rede.nos), set(rede.sources.tolist()) | chegaram)

    def test_source_vai_ao_target_mais_proximo(self):
        for seed in SEEDS:
            rede = gerar_rede(seed)
            for c in (c for c in rede.caminhos if c.etapa == INICIAL):
                self.assertEqual(c.destino, target_mais_proximo(rede.pontos[c.origem], rede.pontos,
                                                                rede.targets))

    def test_caminho_liga_exatamente_seus_dois_nos(self):
        for seed in SEEDS:
            rede = gerar_rede(seed)
            for c in rede.caminhos:
                np.testing.assert_array_equal(c.pontos[0], rede.pontos[c.origem])
                np.testing.assert_array_equal(c.pontos[-1], rede.pontos[c.destino])

    def test_veio_central_desce_do_mais_alto_ao_mais_baixo(self):
        for seed in SEEDS:
            rede = gerar_rede(seed)
            alturas = rede.pontos[rede.central_nos, 1]
            todas = rede.pontos[rede.nos, 1]
            self.assertEqual(alturas[0], todas.max())
            self.assertEqual(alturas[-1], todas.min())
            self.assertTrue(np.all(np.diff(alturas) < 0))
            self.assertEqual(len(set(rede.central_nos)), len(rede.central_nos))

    def test_veio_central_e_uma_linha_continua(self):
        for seed in SEEDS:
            rede = gerar_rede(seed)
            self.assertEqual(len(rede.central_caminhos), len(rede.central_nos) - 1)
            for ordem, indice in enumerate(rede.central_caminhos):
                c = rede.caminhos[indice]
                self.assertEqual({c.origem, c.destino},
                                 {rede.central_nos[ordem], rede.central_nos[ordem + 1]})
                self.assertIn(c.etapa, (INICIAL, DESCIDA))

    def test_tudo_termina_conectado_e_so_por_ligacoes_necessarias(self):
        for seed in SEEDS:
            rede = gerar_rede(seed)
            componentes = separar_componentes(montar_vizinhos(rede.caminhos))
            self.assertEqual(len(componentes), 1)
            self.assertEqual(set(componentes[0]), set(rede.nos))

            ligacoes = [c for c in rede.caminhos if c.etapa == LIGACAO]
            self.assertEqual(len(ligacoes), len(rede.soltos))
            for c, veio in zip(ligacoes, rede.soltos):
                self.assertIn(c.origem, veio)
                self.assertIn(c.destino, rede.central_nos)

    def test_soltos_vem_de_cima_para_baixo(self):
        for seed in SEEDS:
            rede = gerar_rede(seed, n_pontos=40)
            topos = [rede.pontos[veio, 1].max() for veio in rede.soltos]
            self.assertEqual(topos, sorted(topos, reverse=True))

    def test_grade_sai_em_um_pedaco(self):
        for seed in SEEDS:
            vazio, _ = escavar_rede(gerar_rede(seed), 64, 1.5)
            _, pedacos = connected_components(vazio, connectivity=6)
            self.assertEqual(pedacos, 1)

    def test_entradas_invalidas(self):
        for argumentos in (dict(n_pontos=1), dict(weight=0.1, k=1.0), dict(lado=8, raio=3.0)):
            with self.assertRaises(ValueError):
                gerar_rede(1, **argumentos)

    def test_menor_rede_possivel(self):
        rede = gerar_rede(1, n_pontos=2)
        self.assertEqual(len(rede.nos), 2)
        self.assertEqual(len(rede.excluidos), 0)
        self.assertEqual(rede.soltos, [])

class PesoTests(unittest.TestCase):
    def test_sdf_segue_o_contrato_de_sinal(self):
        vazio = np.zeros((11, 11, 11), dtype=bool)
        vazio[2:9, 2:9, 2:9] = True
        classificacao = classificar(vazio)

        sdf = calcular_sdf(classificacao)

        np.testing.assert_array_equal(sdf == 0, classificacao == 1)
        np.testing.assert_array_equal(sdf > 0, classificacao == 2)
        np.testing.assert_array_equal(sdf < 0, classificacao == 0)
        # Miolo do cubo: 3 voxels até a borda. Canto da grade: 2 em cada eixo.
        self.assertEqual(sdf[5, 5, 5], 3)
        self.assertAlmostEqual(float(sdf[0, 0, 0]), -np.sqrt(12), places=5)

    def test_peso_sai_do_resultado_com_o_log_pedido(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            run_and_save(3, directory=pasta)
            destino = gerar_peso(1, 2.0, pasta, pasta / "npz", pasta / "pesos")
            dados = load_result(1, pasta)
            info = load_peso_info(1, pasta / "pesos")
            matriz = load_peso_matrix(1, pasta / "pesos")

        self.assertEqual(destino.name, "peso_001.npz")
        self.assertEqual(info["escala_log"], 2.0)
        self.assertEqual(info["shape"], (64, 64, 64))
        sdf = calcular_sdf(dados["classificacao"])
        np.testing.assert_array_equal(matriz, comprimir_log(sdf, 2.0))

class GravacaoEFiguraTests(unittest.TestCase):
    def test_resultado_gravado_volta_igual(self):
        with tempfile.TemporaryDirectory() as pasta:
            run_and_save(3, n_pontos=24, directory=Path(pasta))
            dados = load_result(1, Path(pasta))

        rede = gerar_rede(3, n_pontos=24)
        lida = dados["rede"]
        np.testing.assert_array_equal(lida.pontos, rede.pontos)
        self.assertEqual(lida.central_nos, rede.central_nos)
        self.assertEqual(lida.central_caminhos, rede.central_caminhos)
        self.assertEqual(lida.soltos, rede.soltos)
        self.assertEqual(lida.veio_de, rede.veio_de)
        for x, y in zip(lida.caminhos, rede.caminhos):
            self.assertEqual((x.origem, x.destino, x.etapa), (y.origem, y.destino, y.etapa))
            np.testing.assert_array_equal(x.pontos, y.pontos)
        np.testing.assert_array_equal(dados["matrix"], escavar_rede(rede, 64, 1.5)[0])

    def test_resultado_sem_soltos_tambem_volta(self):
        with tempfile.TemporaryDirectory() as pasta:
            run_and_save(1, n_pontos=2, directory=Path(pasta))
            self.assertEqual(load_result(1, Path(pasta))["rede"].soltos, [])

    def test_slider_mostra_o_que_cada_etapa_pede(self):
        fig = figura_progressao(gerar_rede(3), "teste")
        passos = fig.layout.sliders[0].steps
        self.assertEqual([p.label for p in passos], list(ETAPAS))

        def nomes(etapa):
            mascara = passos[etapa].args[0]["visible"]
            return {t.name for t, ligado in zip(fig.data, mascara) if ligado and t.name}

        self.assertEqual(len(passos[0].args[0]["visible"]), len(fig.data))
        self.assertLessEqual({"source", "target"}, nomes(0))
        self.assertNotIn("caminhos iniciais", nomes(0))
        self.assertLessEqual({"caminhos iniciais", "target excluído"}, nomes(1))
        self.assertNotIn("veio central", nomes(1))
        self.assertLessEqual({"veio central", "outros veios (apagados)"}, nomes(2))
        self.assertNotIn("ligações", nomes(2))
        self.assertLessEqual({"veio central", "caminhos iniciais", "ligações"}, nomes(3))
        self.assertNotIn("target excluído", nomes(3))

if __name__ == "__main__":
    unittest.main()
