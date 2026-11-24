"""Confere o motor do algoritmo genético, a nota sobre o alvo e o avaliador do CA.

    uv run python -m unittest tests/test_genetic.py -v
"""
import contextlib
import io
import json
import math
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import numpy as np

from cavegen.generators.cellular_automata.genetico import ca as modulo_ca
from cavegen.generators.cellular_automata.genetico.algoritmo import (
    ConfiguracaoGA,
    Gene,
    busca_aleatoria,
    cruzar,
    evoluir,
    mutar,
)
from cavegen.generators.cellular_automata.genetico.aptidao import (
    NOTA_MINIMA,
    Alvo,
    Cortes,
    nota_da_copia_pura,
    nota_do_passo,
    resumo_entre_cavernas,
    situacao_do_vazio,
)
from cavegen.generators.cellular_automata.genetico.ca import (
    ACRESCIMO_ALVO,
    GENES_CA,
    MAX_ITERACOES,
    AvaliadorCA,
    Caverna,
    media_por_passo,
    rodar_ca,
)
from cavegen.sdf.manipulacao import comprimir_log

GENES = (Gene("x", 0.0, 1.0), Gene("n", 1, 20, inteiro=True))
# Nas esferas de raio 5 e 6 (16³, com log), estes genes dão nota positiva nas duas.
BONS = {"chance_inicial": 0.6, "sensibilidade": 15}
ENCHE = {"chance_inicial": 0.5, "sensibilidade": 1}    # a grade enche no primeiro passo
MORRE = {"chance_inicial": 0.5, "sensibilidade": 27}   # nem 27 vizinhos bastam: tudo vira rocha

def sintetica(genes: dict) -> tuple[float, dict]:
    """Aptidão de ótimo conhecido: x = 0,3 e n = 7."""
    return -((genes["x"] - 0.3) ** 2) - 0.01 * (genes["n"] - 7) ** 2, {"iteracoes": 1}

class Contadora:
    def __init__(self):
        self.chamadas = 0

    def __call__(self, genes):
        self.chamadas += 1
        return sintetica(genes)

def esfera_sdf(lado: int = 16, raio: float = 4.0) -> np.ndarray:
    """SDF de uma bola no centro: positivo dentro, 0 na casca, negativo fora."""
    z, y, x = np.indices((lado, lado, lado))
    centro = (lado - 1) / 2
    return (raio - np.sqrt((z - centro) ** 2 + (y - centro) ** 2 + (x - centro) ** 2)).astype(
        np.float32)

def campo_esfera(raio: float = 5.0, lado: int = 16, escala: float = 2.0) -> np.ndarray:
    """
        O campo do GA para a esfera: o SDF dela com log de escala 2, sem limiar.
        escala 1 é a do GA até 22/11/2026, que alguns testes de comportamento
        do CA usam porque fixam uma dinâmica medida com ela.
    """
    return comprimir_log(esfera_sdf(lado, raio), escala)

def copia_pura(raio: float) -> float:
    """A nota da cópia pura da esfera com o alvo da busca (o campo mais o acréscimo)."""
    caverna = Caverna("esfera", campo_esfera(raio), ACRESCIMO_ALVO)
    return nota_da_copia_pura(caverna.peso, caverna.alvo)

def gravar_campo(caminho: Path, campo: np.ndarray, limiar: float = 0.0,
                 escala_log: float | None = 2.0) -> Path:
    """Grava um npz no formato do cavegen/tools/sdf."""
    extras = {} if escala_log is None else {"escala_log": escala_log}
    np.savez_compressed(caminho, sdf=campo, convencao=np.array("teste"), limiar=limiar, **extras)
    return caminho

def rodar_main(*argv: str) -> Path:
    from cavegen.generators.cellular_automata.genetico import busca as executar

    # Sem gravar na planilha real do track_resources.
    with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
          contextlib.redirect_stdout(io.StringIO())):
        return executar.main(list(argv))

def erro_do_main(*argv: str) -> str:
    """Roda o main esperando parser.error, e devolve a mensagem."""
    erro = io.StringIO()
    with (contextlib.redirect_stderr(erro), contextlib.redirect_stdout(io.StringIO()),
          mock.patch("cavegen.profiling.resource_tracker.registrar_execucao")):
        from cavegen.generators.cellular_automata.genetico import busca as executar
        try:
            executar.main(list(argv))
        except SystemExit as saida:
            assert saida.code == 2, saida.code
            return erro.getvalue()
    raise AssertionError("o main não falhou")

class GeneTests(unittest.TestCase):
    def test_corrigir_e_sortear_ficam_na_faixa(self):
        rng = np.random.default_rng(0)
        x, n = GENES
        self.assertEqual(x.corrigir(1.7), 1.0)
        self.assertEqual(n.corrigir(-3), 1)
        self.assertEqual(n.corrigir(6.6), 7)
        self.assertIsInstance(n.corrigir(6.6), int)
        for _ in range(200):
            self.assertTrue(0.0 <= x.sortear(rng) <= 1.0)
            self.assertIn(n.sortear(rng), range(1, 21))

    def test_limites_invalidos(self):
        for minimo, maximo in ((1, 1), (2, 1), (0, float("inf")), (float("nan"), 1)):
            with self.assertRaises(ValueError):
                Gene("g", minimo, maximo)

    def test_configuracao_invalida(self):
        for kwargs in ({"tamanho_populacao": 1}, {"orcamento": 5}, {"elite": 20},
                       {"tamanho_torneio": 0}, {"taxa_mutacao": 1.5}, {"passo_mutacao": 0}):
            with self.assertRaises(ValueError):
                ConfiguracaoGA(**kwargs)

    def test_mutacao_e_cruzamento_respeitam_os_limites(self):
        rng = np.random.default_rng(1)
        for _ in range(300):
            filho = cruzar({"x": 0.0, "n": 1}, {"x": 1.0, "n": 20}, rng)
            filho = mutar(filho, GENES, taxa=1.0, passo=2.0, rng=rng)
            self.assertTrue(0.0 <= filho["x"] <= 1.0)
            self.assertIn(filho["n"], range(1, 21))

class GeneComPassoTests(unittest.TestCase):
    """A chance inicial anda de 0,02 em 0,02: só pontos da grade entram no cromossomo."""
    def setUp(self):
        self.gene = Gene("c", 0.2, 0.8, passo=0.02)
        self.grade = {round(0.2 + k * 0.02, 10) for k in range(31)}

    def test_grade_vai_do_minimo_ao_maximo(self):
        self.assertEqual(self.gene.passos(), 30)
        self.assertEqual(self.gene.corrigir(0.2), 0.2)
        self.assertEqual(self.gene.corrigir(0.8), 0.8)

    def test_corrigir_vai_para_o_ponto_mais_perto(self):
        self.assertEqual(self.gene.corrigir(0.5639), 0.56)
        self.assertEqual(self.gene.corrigir(0.571), 0.58)
        self.assertEqual(self.gene.corrigir(0.0), 0.2)
        self.assertEqual(self.gene.corrigir(1.3), 0.8)
        # O mesmo ponto sai sempre o mesmo float, para cair no cache.
        self.assertEqual(self.gene.corrigir(0.3 + 13 * 0.02), 0.56)
        self.assertEqual(repr(self.gene.corrigir(0.5600000000000001)), "0.56")

    def test_sortear_e_mutar_so_dao_pontos_da_grade(self):
        rng = np.random.default_rng(0)
        sorteados = {self.gene.sortear(rng) for _ in range(2000)}
        self.assertEqual(sorteados, self.grade)
        genes = (self.gene,)
        for _ in range(500):
            filho = mutar({"c": 0.5}, genes, taxa=1.0, passo=0.1, rng=rng)
            self.assertIn(filho["c"], self.grade)
            self.assertIs(type(filho["c"]), float)

    def test_passo_que_nao_fecha_a_faixa_nao_passa_do_maximo(self):
        gene = Gene("c", 0.0, 1.0, passo=0.3)
        self.assertEqual(gene.passos(), 3)
        self.assertEqual(gene.corrigir(1.0), 0.9)

    def test_passo_invalido(self):
        for kwargs in ({"passo": 0}, {"passo": -0.1}, {"passo": float("nan")},
                       {"passo": float("inf")}, {"passo": 1e-11}, {"passo": 1, "inteiro": True}):
            with self.assertRaises(ValueError):
                Gene("g", 0, 10, **kwargs)

    def test_busca_com_passo_so_avalia_pontos_da_grade(self):
        genes = (self.gene, Gene("n", 1, 20, inteiro=True))

        def nota(g):
            return -((g["c"] - 0.46) ** 2), {"iteracoes": 1}

        for resultado in (evoluir(genes, nota, ConfiguracaoGA(orcamento=200), seed=3),
                          busca_aleatoria(genes, nota, 100, seed=3)):
            self.assertTrue(all(a.genes["c"] in self.grade for a in resultado.avaliacoes))
        self.assertEqual(evoluir(genes, nota, ConfiguracaoGA(orcamento=200), seed=3)
                         .melhor.genes["c"], 0.46)

    def test_como_dict_grava_o_passo(self):
        self.assertEqual(self.gene.como_dict()["passo"], 0.02)
        self.assertIsNone(Gene("n", 1, 20, inteiro=True).como_dict()["passo"])

class MotorTests(unittest.TestCase):
    def test_ga_se_aproxima_do_otimo_conhecido(self):
        resultado = evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=300), seed=4)

        self.assertAlmostEqual(resultado.melhor.genes["x"], 0.3, delta=0.05)
        self.assertEqual(resultado.melhor.genes["n"], 7)

    def test_mesma_seed_reproduz_a_busca(self):
        for buscar in (lambda s: evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=60), s),
                       lambda s: busca_aleatoria(GENES, sintetica, 60, s)):
            a, b, c = buscar(9), buscar(9), buscar(10)
            self.assertEqual([x.genes for x in a.avaliacoes], [x.genes for x in b.avaliacoes])
            self.assertNotEqual([x.genes for x in a.avaliacoes], [x.genes for x in c.avaliacoes])

    def test_orcamento_nunca_e_ultrapassado(self):
        for orcamento in (20, 21, 37, 100):
            contadora = Contadora()
            resultado = evoluir(GENES, contadora, ConfiguracaoGA(orcamento=orcamento), seed=1)
            self.assertEqual(len(resultado.avaliacoes), orcamento)
            # Repetido gasta orçamento, mas não chama a avaliação de novo.
            self.assertEqual(contadora.chamadas, orcamento - resultado.reaproveitadas)
        contadora = Contadora()
        self.assertEqual(len(busca_aleatoria(GENES, contadora, 33, seed=1).avaliacoes), 33)

    def test_melhor_acumulado_e_a_curva_do_melhor(self):
        resultado = evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=200), seed=2)
        acumulado = resultado.melhor_acumulado()
        self.assertTrue(np.all(np.diff(acumulado) >= 0))
        self.assertEqual(acumulado[-1], resultado.melhor.nota)

    def test_melhores_sem_repetir_em_ordem_e_sem_cortados(self):
        def com_cortes(genes):
            nota, detalhes = sintetica(genes)
            return (NOTA_MINIMA if genes["n"] > 15 else nota), detalhes

        resultado = evoluir(GENES, com_cortes, ConfiguracaoGA(orcamento=200), seed=2)
        self.assertGreater(resultado.reaproveitadas, 0)  # o teste só vale com repetidos
        melhores = resultado.melhores(10)
        chaves = [tuple(sorted(a.genes.items())) for a in melhores]
        notas = [a.nota for a in melhores]

        self.assertEqual(len(chaves), len(set(chaves)))
        self.assertEqual(notas, sorted(notas, reverse=True))
        self.assertTrue(all(np.isfinite(notas)))
        self.assertIs(melhores[0], resultado.melhor)
        # Cada um aparece na sua primeira avaliação.
        for a in melhores:
            primeira = next(x for x in resultado.avaliacoes if x.genes == a.genes)
            self.assertIs(a, primeira)
        # Pedir mais do que existe devolve só os válidos.
        unicos_validos = {tuple(sorted(a.genes.items())) for a in resultado.avaliacoes
                          if np.isfinite(a.nota)}
        self.assertEqual(len(resultado.melhores(10_000)), len(unicos_validos))
        with self.assertRaises(ValueError):
            resultado.melhores(0)

class AptidaoTests(unittest.TestCase):
    def setUp(self):
        self.campo = np.array([[[3.0, 1.0, 0.0, -1.0, -4.0]]], dtype=np.float32)
        self.alvo = Alvo(self.campo)

    def test_nota_vai_de_negativa_ate_1(self):
        self.assertEqual(self.alvo.nota(self.campo > 0), 1.0)
        self.assertEqual(self.alvo.nota(np.zeros_like(self.campo, dtype=bool)), 0.0)
        self.assertEqual(self.alvo.nota(self.campo < 0), -5.0 / 4.0)
        # Vazio no neutro (0) não soma nem tira.
        self.assertEqual(self.alvo.nota(self.campo >= 0), 1.0)

    def test_escala_do_alvo_nao_muda_a_nota(self):
        vazio = np.array([[[True, False, True, True, False]]])
        self.assertAlmostEqual(Alvo(self.campo * 7.5).nota(vazio), self.alvo.nota(vazio))

    def test_alvo_e_somente_leitura_e_copia(self):
        self.campo[0, 0, 0] = 100
        self.assertEqual(float(self.alvo.campo[0, 0, 0]), 3.0)
        with self.assertRaises(ValueError):
            self.alvo.campo[0, 0, 0] = 5

    def test_alvo_invalido(self):
        with self.assertRaises(ValueError):
            Alvo(np.full((2, 2, 2), -1.0))
        with self.assertRaises(ValueError):
            Alvo(np.array([1.0, np.nan]))

    def test_cortes_so_tem_a_faixa_de_vazio(self):
        # A parada por convergência saiu junto com a parada antecipada.
        # Desde 22/11/2026 só o mínimo vale por padrão: o máximo é None.
        self.assertEqual(Cortes().como_dict(), {"fator_minimo": 0.5, "fator_maximo": None})
        self.assertEqual(Cortes(0.5, 5.0).como_dict(), {"fator_minimo": 0.5, "fator_maximo": 5.0})
        with self.assertRaises(TypeError):
            Cortes(fracao_convergencia=1e-4)
        for fatores in ((0.0, 5.0), (1.0, 5.0), (0.5, 1.0), (0.5, 0.4), (0.0, None), (1.0, None)):
            with self.assertRaises(ValueError):
                Cortes(*fatores)

    def test_situacao_do_vazio(self):
        alvo = Alvo(np.ones((10, 10, 10)))  # referência 1000: vazio aceito a partir de 500
        cortes = Cortes()
        self.assertEqual(alvo.faixa(cortes), (500.0, math.inf))
        self.assertEqual(situacao_do_vazio(499, alvo, cortes), "vazio_de_menos")
        self.assertEqual(situacao_do_vazio(500, alvo, cortes), "na_faixa")
        self.assertEqual(situacao_do_vazio(10**9, alvo, cortes), "na_faixa")
        # O limite de cima ainda existe quando pedido (as execuções antigas o usavam).
        com_teto = Cortes(0.5, 5.0)
        self.assertEqual(alvo.faixa(com_teto), (500.0, 5000.0))
        self.assertEqual(situacao_do_vazio(5000, alvo, com_teto), "na_faixa")
        self.assertEqual(situacao_do_vazio(5001, alvo, com_teto), "vazio_demais")

    def test_nota_do_passo_corta_fora_da_faixa(self):
        alvo = Alvo(np.pad(np.ones((2, 2, 2)), 1, constant_values=-1))  # referência 8
        vazio = np.zeros(alvo.shape, dtype=bool)
        vazio[1:3, 1:3, 1:3] = True
        self.assertEqual(nota_do_passo(vazio, alvo, Cortes()), 1.0)
        # Encher a grade não é mais cortado: a nota já pune, e fica a da grade cheia.
        cheia = np.ones(alvo.shape, bool)
        self.assertEqual(nota_do_passo(cheia, alvo, Cortes()), alvo.nota_da_grade_cheia())
        self.assertEqual(alvo.nota_da_grade_cheia(), (8 - 56) / 8)
        self.assertEqual(nota_do_passo(cheia, alvo, Cortes(0.5, 5.0)), NOTA_MINIMA)
        vazio[:] = False
        vazio[1, 1, 1] = True  # 1 < 0,5 x 8
        self.assertEqual(nota_do_passo(vazio, alvo, Cortes()), NOTA_MINIMA)

    def test_copia_pura_do_proprio_campo_vale_1(self):
        # O alvo é o mesmo campo do peso: a cópia pura acerta todo o positivo.
        for campo in (campo_esfera(5.0), campo_esfera(6.0), esfera_sdf()):
            self.assertEqual(nota_da_copia_pura(campo, Alvo(campo)), 1.0)
        # Se o alvo fosse outro campo, ela deixaria de ser 1: é uma conferência.
        sdf = esfera_sdf()
        self.assertTrue(0 < nota_da_copia_pura(sdf, Alvo(sdf + 3)) < 1)

    def test_resumo_entre_cavernas(self):
        resumo = resumo_entre_cavernas({"a": 0.2, "b": 0.6, "c": 0.7})
        self.assertAlmostEqual(resumo["media"], 0.5)
        self.assertEqual((resumo["min"], resumo["max"]), (0.2, 0.7))
        self.assertAlmostEqual(resumo["desvio"], float(np.std([0.2, 0.6, 0.7])))
        self.assertEqual(resumo["por_caverna"], {"a": 0.2, "b": 0.6, "c": 0.7})
        # Uma caverna só: tudo é a nota dela e o desvio é 0.
        self.assertEqual(resumo_entre_cavernas({"a": 0.4}),
                         {"media": 0.4, "min": 0.4, "max": 0.4, "desvio": 0.0,
                          "por_caverna": {"a": 0.4}})
        with self.assertRaises(ValueError):
            resumo_entre_cavernas({})

    def test_resumo_com_caverna_cortada_nao_vence_e_nao_avisa(self):
        # Uma média alta não pode esconder uma caverna cortada.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            resumo = resumo_entre_cavernas({"a": 0.9, "b": NOTA_MINIMA})
        self.assertEqual(resumo["media"], NOTA_MINIMA)
        self.assertEqual(resumo["min"], NOTA_MINIMA)
        self.assertEqual(resumo["max"], 0.9)
        self.assertTrue(math.isnan(resumo["desvio"]))

class CavernaTests(unittest.TestCase):
    def test_acrescimo_vai_so_para_o_alvo(self):
        campo = campo_esfera()
        caverna = Caverna("esfera", campo, 1.0)
        np.testing.assert_array_equal(caverna.peso, campo)  # o peso fica como está
        np.testing.assert_allclose(caverna.alvo.campo, campo + 1.0, rtol=0, atol=1e-6)
        self.assertEqual(caverna.acrescimo_alvo, 1.0)
        # A casca de borda (campo 0) passa a ser positiva no alvo; nada de fora dela.
        self.assertEqual(caverna.alvo.referencia, int((campo > -1.0).sum()))
        self.assertGreater(caverna.alvo.referencia, int((campo > 0).sum()))
        # A nota máxima continua 1, mas a cópia pura não pinta a casca e fica abaixo.
        self.assertAlmostEqual(caverna.alvo.nota(caverna.alvo.campo > 0), 1.0)
        self.assertLess(nota_da_copia_pura(caverna.peso, caverna.alvo), 1.0)

    def test_acrescimo_da_busca_e_positivo_e_o_padrao_da_caverna_e_0(self):
        # O valor da busca está em aberto (1 em ga_015, 1,5 desde ga_016): o
        # contrato é ser um número finito e positivo, não um valor fixo.
        self.assertTrue(math.isfinite(ACRESCIMO_ALVO))
        self.assertGreater(ACRESCIMO_ALVO, 0)
        self.assertEqual(Caverna("esfera", campo_esfera()).acrescimo_alvo, 0.0)
        for ruim in (math.inf, math.nan):
            with self.subTest(acrescimo=ruim), self.assertRaises(ValueError):
                Caverna("esfera", campo_esfera(), ruim)

    def test_acrescimo_pode_dar_positivo_a_um_campo_sem_positivo(self):
        # Campo todo 0 (só borda): sem acréscimo não há o que acertar; com ele, há.
        plano = np.zeros((8, 8, 8), dtype=np.float32)
        with self.assertRaises(ValueError):
            Caverna("borda", plano)
        self.assertEqual(Caverna("borda", plano, 1.0).alvo.referencia, plano.size)

    def test_peso_e_alvo_sao_o_mesmo_campo(self):
        campo = campo_esfera()
        caverna = Caverna("esfera", campo)
        np.testing.assert_array_equal(caverna.peso, campo)
        np.testing.assert_array_equal(caverna.alvo.campo, campo)
        self.assertEqual(caverna.peso.dtype, campo.dtype)
        self.assertEqual(caverna.alvo.referencia, int((campo > 0).sum()))
        self.assertFalse(caverna.peso.flags.writeable)
        campo *= 10  # mexer no original não muda a caverna
        self.assertEqual(float(caverna.peso.max()), float(campo_esfera().max()))

    def test_sem_positivo_falha_dizendo_qual_caverna(self):
        with self.assertRaisesRegex(ValueError, "caverna rocha .*nenhum voxel positivo"):
            Caverna("rocha", np.full((8, 8, 8), -1.0, dtype=np.float32))

    def test_grade_nao_cubica_ou_nao_finita_falha_dizendo_qual_caverna(self):
        campo = np.ones((8, 8, 10), dtype=np.float32)
        with self.assertRaisesRegex(ValueError, "caverna torta tem grade \\(8, 8, 10\\)"):
            Caverna("torta", campo)
        with self.assertRaisesRegex(ValueError, "caverna plana"):
            Caverna("plana", np.ones((8, 8), dtype=np.float32))
        campo = campo_esfera()
        campo[0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "caverna nan .*não finitos"):
            Caverna("nan", campo)

class AvaliadorCATests(unittest.TestCase):
    def setUp(self):
        self.a = Caverna("a", campo_esfera(5.0))
        self.b = Caverna("b", campo_esfera(6.0))

    def test_rodar_ca_e_reproduzivel(self):
        x = rodar_ca(BONS, self.a, semente=3, max_iteracoes=30)
        y = rodar_ca(BONS, self.a, semente=3, max_iteracoes=30)

        np.testing.assert_array_equal(x.final, y.final)
        np.testing.assert_array_equal(x.notas, y.notas)
        self.assertEqual(x.notas.shape, (30,))
        self.assertEqual(int(x.final.sum()), x.vazios[-1])

    def test_sem_parada_antecipada_o_ca_roda_todas_as_iteracoes(self):
        # Enche, morre ou fica na faixa: o CA sempre roda as N iterações.
        chamadas = []
        original = modulo_ca.iterate

        def contar(*args, **kwargs):
            chamadas.append(1)
            return original(*args, **kwargs)

        for genes in (BONS, ENCHE, MORRE):
            with self.subTest(genes=genes):
                chamadas.clear()
                with mock.patch.object(modulo_ca, "iterate", side_effect=contar):
                    t = rodar_ca(genes, self.a, semente=1, max_iteracoes=25)
                self.assertEqual(len(chamadas), 25)
                self.assertEqual(len(t.vazios), 25)
                self.assertEqual(len(t.mudancas), 25)
                self.assertEqual(t.notas.shape, (25,))
        self.assertFalse(hasattr(t, "parada") or hasattr(t, "motivo"))

    def test_a_penalizacao_continua_sem_a_parada(self):
        # Esvaziar a grade é cortado pelo mínimo; encher não é cortado. O ENCHE
        # enche já no passo 1, então todo passo vale a grade cheia, abaixo de
        # qualquer candidato razoável (quem enche aos poucos leva o passo 1: ver
        # test_genetico_faixa_revisor).
        avaliador = AvaliadorCA([self.a], (1, 2, 3, 4, 5), max_iteracoes=15)
        nota, detalhes = avaliador(MORRE)
        self.assertEqual(nota, NOTA_MINIMA)
        self.assertEqual(detalhes["cavernas"]["a"]["fim"], ["vazio_de_menos"] * 5)
        for t in avaliador.trajetorias(MORRE)["a"]:
            self.assertTrue(np.all(t.notas == NOTA_MINIMA))
            self.assertEqual(len(t.vazios), 15)
        nota, detalhes = avaliador(ENCHE)
        self.assertEqual(detalhes["cavernas"]["a"]["fim"], ["na_faixa"] * 5)
        self.assertTrue(np.isfinite(nota))
        self.assertLess(nota, -1)
        self.assertLess(nota, avaliador(BONS)[0])
        for t in avaliador.trajetorias(ENCHE)["a"]:
            self.assertEqual(t.notas[-1], self.a.alvo.nota_da_grade_cheia())
        # Com o limite de cima pedido, encher volta a ser cortado.
        com_teto = AvaliadorCA([self.a], (1, 2, 3, 4, 5), max_iteracoes=15,
                               cortes=Cortes(0.5, 5.0))
        nota, detalhes = com_teto(ENCHE)
        self.assertEqual(nota, NOTA_MINIMA)
        self.assertEqual(detalhes["cavernas"]["a"]["fim"], ["vazio_demais"] * 5)
        # E a lista dos melhores nunca traz um cortado.
        busca = busca_aleatoria(GENES_CA, avaliador, 25, seed=0)
        self.assertTrue(all(np.isfinite(a.nota) for a in busca.melhores(25)))

    def test_melhor_iteracao_e_a_da_media_das_sementes_e_das_cavernas(self):
        sementes = (1, 2, 3, 4, 5)
        avaliador = AvaliadorCA([self.a, self.b], sementes, max_iteracoes=20)
        nota, detalhes = avaliador(BONS)
        trajetorias = avaliador.trajetorias(BONS)
        por_caverna = {nome: np.mean([t.notas for t in ts], axis=0)
                       for nome, ts in trajetorias.items()}
        media = (por_caverna["a"] + por_caverna["b"]) / 2

        melhor = int(np.argmax(media))
        self.assertEqual(detalhes["iteracoes"], melhor + 1)
        self.assertAlmostEqual(nota, float(media.max()))
        self.assertGreater(nota, 0)
        # Uma iteração só, a mesma para as duas cavernas.
        for nome, ts in trajetorias.items():
            self.assertEqual(detalhes["cavernas"][nome]["notas_por_semente"],
                             [float(t.notas[melhor]) for t in ts])
            self.assertEqual(len(detalhes["cavernas"][nome]["vazios"]), len(sementes))
        resumo = detalhes["entre_cavernas"]
        notas = [por_caverna["a"][melhor], por_caverna["b"][melhor]]
        self.assertEqual(resumo["media"], nota)
        self.assertAlmostEqual(resumo["min"], min(notas))
        self.assertAlmostEqual(resumo["max"], max(notas))
        self.assertAlmostEqual(resumo["desvio"], float(np.std(notas)))
        self.assertEqual(set(resumo["por_caverna"]), {"a", "b"})

    def test_caverna_cortada_corta_o_candidato_mesmo_com_media_alta_nas_outras(self):
        sozinha, _ = AvaliadorCA([self.a], (1, 2), max_iteracoes=12)(BONS)
        self.assertGreater(sozinha, 0)
        # Esfera minúscula: com o limite de cima, a faixa vira poucos voxels e o
        # CA sempre passa dela. O que se testa é a agregação: uma caverna
        # cortada corta o candidato.
        minuscula = Caverna("minuscula", campo_esfera(1.0, escala=1.0))
        nota, detalhes = AvaliadorCA([self.a, minuscula], (1, 2), max_iteracoes=12,
                                     cortes=Cortes(0.5, 5.0))(BONS)
        self.assertEqual(nota, NOTA_MINIMA)
        self.assertEqual(detalhes["entre_cavernas"]["min"], NOTA_MINIMA)

    def test_faixa_de_vazio_e_de_cada_caverna(self):
        self.assertEqual(self.a.alvo.faixa(Cortes()), (0.5 * self.a.alvo.referencia, math.inf))
        cortes = Cortes(0.5, 5.0)
        self.assertEqual(self.a.alvo.faixa(cortes), (0.5 * self.a.alvo.referencia,
                                                     5.0 * self.a.alvo.referencia))
        self.assertNotEqual(self.a.alvo.faixa(cortes), self.b.alvo.faixa(cortes))
        # A mesma grade pode estar na faixa de uma caverna e fora da da outra.
        vazios = int(4.9 * self.a.alvo.referencia)
        self.assertEqual(situacao_do_vazio(vazios, self.a.alvo, cortes), "na_faixa")
        self.assertEqual(situacao_do_vazio(int(5.1 * self.a.alvo.referencia), self.a.alvo,
                                           cortes), "vazio_demais")
        self.assertLess(self.a.alvo.referencia, self.b.alvo.referencia)
        self.assertEqual(situacao_do_vazio(int(5.1 * self.a.alvo.referencia), self.b.alvo,
                                           cortes), "na_faixa")

    def test_iteracao_escolhida_se_reproduz_sem_escolher_de_novo(self):
        # É o que garante a avaliação honesta nas sementes reservadas: rodar com
        # N = iteração escolhida dá exatamente a nota que a busca viu.
        sementes = (1, 2, 3, 4, 5)
        avaliador = AvaliadorCA([self.a, self.b], sementes, max_iteracoes=25)
        nota, detalhes = avaliador(BONS)
        conferido = avaliador.conferir(BONS, detalhes["iteracoes"], sementes)

        self.assertEqual(conferido["media"], nota)
        for chave in ("min", "max", "desvio", "por_caverna"):
            self.assertEqual(conferido[chave], detalhes["entre_cavernas"][chave], chave)
        for nome in ("a", "b"):
            self.assertEqual(conferido["notas_por_semente"][nome],
                             detalhes["cavernas"][nome]["notas_por_semente"])
        todas = [n for v in conferido["notas_por_semente"].values() for n in v]
        self.assertEqual(conferido["pior_semente"], min(todas))

    def test_media_por_passo_e_a_media_de_cada_coluna(self):
        notas = np.array([[0.1, 0.2, NOTA_MINIMA], [0.3, 0.6, 0.5]])
        np.testing.assert_array_equal(media_por_passo(notas), [0.2, 0.4, NOTA_MINIMA])

    def test_avaliador_recusa_cavernas_vazias_ou_repetidas(self):
        with self.assertRaises(ValueError):
            AvaliadorCA([], (1,))
        with self.assertRaises(ValueError):
            AvaliadorCA([self.a, Caverna("a", campo_esfera(6.0))], (1,))
        with self.assertRaises(ValueError):
            AvaliadorCA([self.a], ())

    def test_cromossomo_nao_tem_escala_do_peso(self):
        self.assertEqual([g.nome for g in GENES_CA], ["chance_inicial", "sensibilidade"])

    def test_peso_chega_ao_ca_identico_ao_carregado(self):
        # Contrato: nada multiplica, comprime ou corta o peso entre o arquivo e o CA.
        recebidos = []
        original = modulo_ca.iterate

        def espiar(matriz, sensibilidade, borda, peso_recebido=None, *args, **kwargs):
            recebidos.append(peso_recebido)
            return original(matriz, sensibilidade, borda, peso_recebido, *args, **kwargs)

        avaliador = AvaliadorCA([self.a, self.b], (1, 2), max_iteracoes=5)
        with mock.patch.object(modulo_ca, "iterate", side_effect=espiar):
            avaliador(BONS)
            avaliador.conferir(BONS, 3, (101,))
        self.assertEqual(len(recebidos), 2 * 2 * 5 + 2 * 3)
        campos = (campo_esfera(5.0), campo_esfera(6.0))
        for recebido in recebidos:
            self.assertTrue(any(np.array_equal(recebido, c) for c in campos))
            self.assertEqual(recebido.dtype, np.float32)

class ExecutarTests(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self.pasta = Path(self._pasta.name)
        self.esfera = gravar_campo(self.pasta / "esfera_sdf_log2.npz", campo_esfera(5.0))
        self.maior = gravar_campo(self.pasta / "maior_sdf_log2.npz", campo_esfera(6.0))
        self.saida = str(self.pasta / "results")

    def tearDown(self):
        self._pasta.cleanup()

    def test_execucao_curta_grava_tudo(self):
        destino = rodar_main("--orcamento", "6", "--populacao", "3",
                             "--cavernas", str(self.esfera), "--saida", self.saida)
        with np.load(destino) as r:
            self.assertEqual(str(r["metodo"]), "genetico")
            self.assertEqual(r["genes"].shape, (6, 2))
            self.assertEqual(r["notas"].shape, (6,))
            for campo in ("campeao", "nota_reservada_media", "nota_copia_pura", "cortes",
                          "sementes_ajuste", "sementes_reservadas", "cavernas", "genes_limites",
                          "detalhes", "ambiente", "criterio_ranking", "modo_peso"):
                self.assertIn(campo, r.files)
            # Saíram com o alvo único e o teto trivial.
            for campo in ("nota_teto_trivial", "peso", "alvo", "forma", "faixa_vazio",
                          "referencia_alvo", "notas_reservadas"):
                self.assertNotIn(campo, r.files)
            # Com o acréscimo do alvo, a cópia pura não pinta a casca de borda.
            self.assertEqual(json.loads(str(r["nota_copia_pura"])), {"esfera": copia_pura(5.0)})
            self.assertEqual(json.loads(str(r["acrescimo_alvo"])), ACRESCIMO_ALVO)
            self.assertEqual(json.loads(str(r["modo_peso"])), "completo")
            self.assertEqual(json.loads(str(r["sementes_ajuste"])), [1, 2, 3, 4, 5])
            self.assertEqual(json.loads(str(r["cortes"])),
                             {"fator_minimo": 0.5, "fator_maximo": None})
            cavernas = json.loads(str(r["cavernas"]))
            self.assertEqual([c["nome"] for c in cavernas], ["esfera"])
            self.assertTrue(cavernas[0]["origem"].endswith("esfera_sdf_log2.npz"))
            self.assertEqual(len(cavernas[0]["sha256"]), 64)
            self.assertEqual(cavernas[0]["forma"], [16, 16, 16])
            self.assertEqual((cavernas[0]["limiar"], cavernas[0]["escala_log"]), (0.0, 2.0))
            # Os positivos do alvo são os do campo mais o acréscimo (a casca de borda entra).
            alvo = Caverna("esfera", campo_esfera(5.0), ACRESCIMO_ALVO).alvo
            referencia = int((campo_esfera(5.0) + ACRESCIMO_ALVO > 0).sum())
            self.assertGreater(referencia, int((campo_esfera(5.0) > 0).sum()))
            self.assertEqual(cavernas[0]["referencia_alvo"], referencia)
            # Sem limite de cima, o máximo vai como null (o JSON não tem inf).
            self.assertEqual(cavernas[0]["faixa_vazio"], [0.5 * referencia, None])
            self.assertEqual(cavernas[0]["nota_grade_cheia"], alvo.nota_da_grade_cheia())
            self.assertLess(cavernas[0]["nota_grade_cheia"], 1)
            detalhes = json.loads(str(r["detalhes"]))
            self.assertEqual(len(detalhes), 6)
            vazios = detalhes[0]["cavernas"]["esfera"]["vazios"]
            self.assertEqual(len(vazios), 5)  # uma lista por semente
            self.assertTrue(all(len(v) == MAX_ITERACOES for v in vazios))  # sem parada
            melhores = json.loads(str(r["melhores"]))
            campeao = json.loads(str(r["campeao"]))
            self.assertTrue(0 <= len(melhores) <= 6)
            self.assertEqual([m["posicao"] for m in melhores], list(range(1, len(melhores) + 1)))
            if melhores:
                self.assertEqual(melhores[0]["genes"], campeao["genes"])
                self.assertEqual(melhores[0]["nota_reservada_media"],
                                 json.loads(str(r["nota_reservada_media"])))

    def test_varias_cavernas_gravam_a_nota_de_cada_uma_e_o_resumo(self):
        destino = rodar_main("--metodo", "aleatoria", "--orcamento", "20", "--populacao", "3",
                             "--top", "4", "--cavernas", str(self.esfera), str(self.maior),
                             "--saida", self.saida)
        with np.load(destino) as r:
            cavernas = json.loads(str(r["cavernas"]))
            melhores = json.loads(str(r["melhores"]))
            copias = json.loads(str(r["nota_copia_pura"]))
            criterio = json.loads(str(r["criterio_ranking"]))
        self.assertEqual([c["nome"] for c in cavernas], ["esfera", "maior"])
        # A faixa é de cada caverna, relativa ao alvo dela.
        self.assertLess(cavernas[0]["faixa_vazio"][0], cavernas[1]["faixa_vazio"][0])
        self.assertEqual([c["faixa_vazio"][1] for c in cavernas], [None, None])
        self.assertEqual(copias, {"esfera": copia_pura(5.0), "maior": copia_pura(6.0)})
        self.assertIn("média", criterio)
        self.assertGreater(len(melhores), 0)
        notas = [m["nota_ajuste"] for m in melhores]
        self.assertEqual(notas, sorted(notas, reverse=True))  # ordem pela média
        avaliador = AvaliadorCA([Caverna("esfera", campo_esfera(5.0), ACRESCIMO_ALVO),
                                 Caverna("maior", campo_esfera(6.0), ACRESCIMO_ALVO)],
                                (1, 2, 3, 4, 5))
        for item in melhores:
            ajuste = item["ajuste"]
            self.assertEqual(set(ajuste["por_caverna"]), {"esfera", "maior"})
            self.assertEqual(ajuste["media"], item["nota_ajuste"])
            self.assertEqual(ajuste["min"], min(ajuste["por_caverna"].values()))
            self.assertEqual(ajuste["max"], max(ajuste["por_caverna"].values()))
            self.assertAlmostEqual(ajuste["desvio"],
                                   float(np.std(list(ajuste["por_caverna"].values()))))
            reservadas = item["reservadas"]
            self.assertEqual(set(reservadas["notas_por_semente"]), {"esfera", "maior"})
            self.assertTrue(all(len(v) == 10 for v in reservadas["notas_por_semente"].values()))
            refeito = avaliador.conferir(item["genes"], item["iteracoes"], (1, 2, 3, 4, 5))
            self.assertEqual(refeito["media"], item["nota_ajuste"])
            self.assertEqual(refeito["por_caverna"], ajuste["por_caverna"])

    def test_top_limita_a_lista_e_cada_item_se_reproduz(self):
        from cavegen.generators.cellular_automata.genetico import busca as executar

        destino = rodar_main("--metodo", "aleatoria", "--orcamento", "20", "--populacao", "3",
                             "--top", "3", "--cavernas", str(self.esfera), "--saida", self.saida)
        with np.load(destino) as r:
            melhores = json.loads(str(r["melhores"]))
        self.assertLessEqual(len(melhores), 3)
        self.assertGreater(len(melhores), 0)
        avaliador = AvaliadorCA([Caverna("esfera", campo_esfera(5.0), ACRESCIMO_ALVO)],
                                executar.SEMENTES_AJUSTE)
        for item in melhores:
            ajuste = avaliador.conferir(item["genes"], item["iteracoes"], executar.SEMENTES_AJUSTE)
            reservadas = avaliador.conferir(item["genes"], item["iteracoes"],
                                            executar.SEMENTES_RESERVADAS)
            self.assertEqual(ajuste["media"], item["nota_ajuste"])
            self.assertEqual(reservadas["media"], item["nota_reservada_media"])
            self.assertEqual(reservadas["pior_semente"], item["reservadas"]["pior_semente"])
            self.assertEqual(reservadas["notas_por_semente"],
                             item["reservadas"]["notas_por_semente"])

    def test_caverna_sem_positivo_falha_dizendo_qual_e_por_que(self):
        # Bem abaixo de -ACRESCIMO_ALVO: o alvo (campo + acréscimo) continua sem positivo.
        rocha = gravar_campo(self.pasta / "rocha_sdf_log2.npz",
                             np.full((8, 8, 8), -10.0 - ACRESCIMO_ALVO, dtype=np.float32))
        mensagem = erro_do_main("--cavernas", str(self.esfera), str(rocha), "--saida", self.saida)
        self.assertIn("caverna rocha", mensagem)
        self.assertIn("nenhum voxel positivo", mensagem)

    def test_caverna_com_limiar_ou_sem_log_e_recusada(self):
        com_limiar = gravar_campo(self.pasta / "deslocada.npz", campo_esfera(5.0), limiar=-3.0)
        sem_log = gravar_campo(self.pasta / "crua.npz", esfera_sdf(), escala_log=None)
        log1 = gravar_campo(self.pasta / "simples.npz", campo_esfera(5.0), escala_log=1.0)
        for caminho, trecho in ((com_limiar, "limiar -3"), (sem_log, "sem log"),
                                (log1, "log x1")):
            with self.subTest(caminho=caminho.name):
                mensagem = erro_do_main("--cavernas", str(caminho), "--saida", self.saida)
                self.assertIn(trecho, mensagem)
                self.assertIn("log x2 e sem limiar", mensagem)
                self.assertIn("genetico.campos", mensagem)  # o comando da etapa 2

    def test_caverna_nao_cubica_falha_dizendo_qual(self):
        torta = gravar_campo(self.pasta / "torta_sdf_log2.npz",
                             np.ones((8, 8, 10), dtype=np.float32))
        self.assertIn("caverna torta tem grade (8, 8, 10)",
                      erro_do_main("--cavernas", str(torta), "--saida", self.saida))

    def test_caverna_que_falta_ou_repetida(self):
        mensagem = erro_do_main("--cavernas", str(self.pasta / "nada_sdf_log2.npz"))
        self.assertIn("não existe", mensagem)
        self.assertIn("genetico.campos", mensagem)
        mensagem = erro_do_main("--cavernas", str(self.esfera), str(self.esfera))
        self.assertIn("repetida", mensagem)

    def test_nomes_e_caminhos_das_cavernas(self):
        from cavegen.generators.cellular_automata.genetico import campos

        grade = Path("1_entrada/elaphes_surface_64.npz")
        campo = campos.caminho_do_campo(grade, Path("2_campos"))
        self.assertEqual(campo, Path("2_campos/elaphes_surface_64_sdf_log2.npz"))
        self.assertEqual(campos.nome_da_caverna(grade), "elaphes")
        self.assertEqual(campos.nome_da_caverna(campo), "elaphes")
        self.assertEqual(campos.nome_da_caverna(Path("x/indian_tunnel_surface_64.npz")),
                         "indian_tunnel")
        self.assertEqual(campos.nome_da_caverna(Path("x/elaphes_surface_32_pablo_sdf_log2.npz")),
                         "elaphes_surface_32_pablo")

    def test_campo_do_ga_e_o_sdf_com_log_2_sem_limiar(self):
        from cavegen.generators.cellular_automata.genetico import busca as executar
        from cavegen.generators.cellular_automata.genetico import campos

        self.assertEqual((campos.LIMIAR, campos.ESCALA_LOG), (0.0, 2.0))
        self.assertEqual(campos.SUFIXO_CAMPO, "_sdf_log2")
        for antigo in ("ALVO_ELAPHES", "CAMPO_ELAPHES", "CAVERNAS_PADRAO", "NPZ_SDF"):
            self.assertFalse(hasattr(executar, antigo), antigo)

    def test_seeds_de_ajuste_sao_5_e_as_reservadas_10_sem_nenhuma_em_comum(self):
        from cavegen.generators.cellular_automata.genetico import busca as executar

        self.assertEqual(executar.SEMENTES_AJUSTE, (1, 2, 3, 4, 5))
        self.assertEqual(len(executar.SEMENTES_RESERVADAS), 10)
        self.assertFalse(set(executar.SEMENTES_AJUSTE) & set(executar.SEMENTES_RESERVADAS))

if __name__ == "__main__":
    unittest.main()
