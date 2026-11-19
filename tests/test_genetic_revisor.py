"""Testes adversariais do revisor para o GA do CA guiado por SDF e a borda NEAREST.

    uv run python -m unittest tests/test_genetic_revisor.py -v
"""
import contextlib
import io
import json
import re
import tempfile
import unicodedata
import unittest
import warnings
from pathlib import Path
from unittest import mock

import numpy as np

from cavegen.generators.cellular_automata.generator import BorderTreatment, neighbor_counts
from cavegen.optimization.genetic import ca as modulo_ca
from cavegen.optimization.genetic.algoritmo import (
    ConfiguracaoGA,
    Gene,
    busca_aleatoria,
    chave,
    evoluir,
    mutar,
)
from cavegen.optimization.genetic.aptidao import NOTA_MINIMA, Alvo
from cavegen.optimization.genetic.ca import GENES_CA, MAX_ITERACOES, AvaliadorCA, rodar_ca
from cavegen.optimization.genetic.painel import Estilo, Painel

# Funções do gerador global que não podem ser usadas no caminho do GA.
GLOBAIS_PROIBIDAS = ("rand", "random", "random_sample", "randint", "uniform", "normal",
                     "choice", "shuffle", "permutation", "seed")


def esfera_sdf(lado: int = 16, raio: float = 4.0) -> np.ndarray:
    """SDF de uma bola no centro: positivo dentro, 0 na casca, negativo fora."""
    z, y, x = np.indices((lado, lado, lado))
    centro = (lado - 1) / 2
    return (raio - np.sqrt((z - centro) ** 2 + (y - centro) ** 2 + (x - centro) ** 2)).astype(
        np.float32)


@contextlib.contextmanager
def sem_gerador_global():
    """Faz qualquer uso do np.random global quebrar o teste."""
    with contextlib.ExitStack() as pilha:
        for nome in GLOBAIS_PROIBIDAS:
            pilha.enter_context(mock.patch.object(
                np.random, nome, side_effect=AssertionError(f"np.random.{nome} global usado")))
        yield


def rodar_executar(pasta: Path, *extra: str) -> Path:
    from cavegen.optimization.genetic import executar

    sdf = esfera_sdf()
    if not (pasta / "peso.npz").exists():
        np.savez_compressed(pasta / "peso.npz", sdf=sdf, convencao=np.array("base"), limiar=0.0)
        np.savez_compressed(pasta / "alvo.npz", sdf=sdf + 3, convencao=np.array("alvo"),
                            limiar=-3.0, escala_log=1.0)
    with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
          contextlib.redirect_stdout(io.StringIO())):
        return executar.main(["--peso", str(pasta / "peso.npz"),
                              "--alvo", str(pasta / "alvo.npz"),
                              "--saida", str(pasta / "results"), *extra])


def extras_gravados(destino: Path) -> dict:
    with np.load(destino) as r:
        return {nome: json.loads(str(r[nome])) for nome in
                ("config", "seed", "genes_limites", "max_iteracoes", "borda", "sementes_ajuste",
                 "sementes_reservadas", "campeao", "notas_reservadas")}


class BordaNearestRevisorTests(unittest.TestCase):
    def test_quina_replica_a_celula_do_canto_nas_tres_direcoes(self):
        # Na quina, o cubo 3x3x3 tem 2 posições por eixo que caem na célula do
        # canto (a de fora replica a de dentro): 2 x 2 x 2 = 8 cópias dela.
        for canto in ((0, 0, 0), (-1, -1, -1), (0, -1, 0), (-1, 0, -1)):
            with self.subTest(canto=canto):
                volume = np.zeros((3, 4, 5), dtype=int)
                volume[canto] = 1
                self.assertEqual(int(neighbor_counts(volume, BorderTreatment.NEAREST)[canto]), 8)

    def test_aresta_replica_em_dois_eixos(self):
        # Na aresta (z = 0, y = 0, x no meio) a célula conta 2 x 2 x 1 = 4 vezes.
        volume = np.zeros((4, 5, 6), dtype=int)
        volume[0, 0, 2] = 1
        self.assertEqual(int(neighbor_counts(volume, BorderTreatment.NEAREST)[0, 0, 2]), 4)

    def test_nearest_nao_usa_o_gerador_global(self):
        volume = (np.random.default_rng(0).random((5, 6, 7)) < 0.5).astype(int)
        esperado = neighbor_counts(volume, BorderTreatment.NEAREST)
        with sem_gerador_global():
            np.testing.assert_array_equal(neighbor_counts(volume, BorderTreatment.NEAREST),
                                          esperado)


class GeneRevisorTests(unittest.TestCase):
    def test_genes_do_ca_batem_com_a_decisao(self):
        limites = {g.nome: (g.minimo, g.maximo, g.inteiro, g.passo) for g in GENES_CA}
        self.assertEqual(limites, {"chance_inicial": (0.2, 0.8, False, 0.02),
                                   "sensibilidade": (1, 20, True, None)})
        self.assertEqual(MAX_ITERACOES, 40)
        self.assertIs(modulo_ca.BORDA, BorderTreatment.NEAREST)

    def test_gene_inteiro_com_limite_fracionario_fica_na_faixa(self):
        # Contrato do Gene: "limites fechados da faixa". Com limites não
        # inteiros, sortear usa int(minimo) e corrigir arredonda depois de
        # limitar, e os dois saem da faixa.
        gene = Gene("k", 0.5, 3.5, inteiro=True)
        rng = np.random.default_rng(0)
        sorteados = {gene.sortear(rng) for _ in range(200)}
        # corrigir(0,5) limita para 0,5 e round(0,5) = 0; corrigir(3,5) dá 4.
        corrigidos = [gene.corrigir(0.5), gene.corrigir(3.5)]
        self.assertTrue(all(0.5 <= v <= 3.5 for v in corrigidos), corrigidos)
        self.assertTrue(all(0.5 <= v <= 3.5 for v in sorteados), sorteados)

    def test_ga_nos_genes_do_ca_respeita_limites_e_tipos_mesmo_empurrado_para_a_borda(self):
        # Aptidão que premia os extremos: a mutação é jogada contra os limites.
        def extremos(genes):
            return (abs(genes["chance_inicial"] - 0.5)
                    + abs(genes["sensibilidade"] - 10.5)), {"iteracoes": 1}

        config = ConfiguracaoGA(orcamento=400, passo_mutacao=0.5, taxa_mutacao=1.0)
        for resultado in (evoluir(GENES_CA, extremos, config, seed=3),
                          busca_aleatoria(GENES_CA, extremos, 400, seed=3)):
            for a in resultado.avaliacoes:
                for gene in GENES_CA:
                    valor = a.genes[gene.nome]
                    self.assertTrue(gene.minimo <= valor <= gene.maximo, (gene.nome, valor))
                self.assertIs(type(a.genes["sensibilidade"]), int)
                self.assertIs(type(a.genes["chance_inicial"]), float)


class OrcamentoRevisorTests(unittest.TestCase):
    def test_orcamento_exato_em_configuracoes_extremas(self):
        def avaliar(genes):
            return float(genes["x"]), {"iteracoes": 1}

        genes = (Gene("x", 0.0, 1.0), Gene("n", 1, 3, inteiro=True))
        configs = (
            ConfiguracaoGA(tamanho_populacao=2, orcamento=2, elite=0, tamanho_torneio=2),
            ConfiguracaoGA(tamanho_populacao=5, orcamento=23, elite=4, tamanho_torneio=5),
            ConfiguracaoGA(tamanho_populacao=7, orcamento=50, elite=0, taxa_cruzamento=0.0,
                           taxa_mutacao=0.0),
            ConfiguracaoGA(tamanho_populacao=3, orcamento=31, taxa_mutacao=1.0),
        )
        for config in configs:
            with self.subTest(config=config):
                chamadas = []
                resultado = evoluir(genes, lambda g, c=chamadas: (c.append(1), avaliar(g))[1],
                                    config, seed=0)
                self.assertEqual(len(resultado.avaliacoes), config.orcamento)
                self.assertEqual(len(chamadas), config.orcamento - resultado.reaproveitadas)
                self.assertEqual([a.ordem for a in resultado.avaliacoes],
                                 list(range(config.orcamento)))

    def test_cromossomo_repetido_nunca_e_reavaliado(self):
        vistos = []

        def avaliar(genes):
            vistos.append(tuple(sorted(genes.items())))
            return -abs(genes["n"] - 2), {"iteracoes": 1}

        # Só 3 cromossomos possíveis: quase tudo é repetido.
        genes = (Gene("n", 1, 3, inteiro=True),)
        resultado = evoluir(genes, avaliar, ConfiguracaoGA(tamanho_populacao=4, orcamento=60),
                            seed=1)
        self.assertEqual(len(vistos), len(set(vistos)))
        self.assertEqual(len(resultado.avaliacoes), 60)

    def test_tudo_cortado_nao_gera_nan_nem_quebra_a_escolha(self):
        resultado = evoluir(GENES_CA, lambda g: (NOTA_MINIMA, {"iteracoes": 1}),
                            ConfiguracaoGA(orcamento=25), seed=0)
        self.assertEqual(resultado.melhor.ordem, 0)
        self.assertFalse(np.isnan(resultado.melhor_acumulado()).any())


class ReprodutibilidadeRevisorTests(unittest.TestCase):
    def setUp(self):
        self.sdf = esfera_sdf()
        self.alvo = Alvo(self.sdf + 3)

    def busca(self, metodo, seed):
        avaliador = AvaliadorCA(self.sdf, self.alvo, (1, 2, 3), max_iteracoes=12)
        if metodo == "genetico":
            return evoluir(GENES_CA, avaliador, ConfiguracaoGA(tamanho_populacao=4, orcamento=10),
                           seed)
        return busca_aleatoria(GENES_CA, avaliador, 10, seed)

    def test_mesma_seed_da_mesma_busca_e_mesmas_notas_sem_gerador_global(self):
        for metodo in ("genetico", "aleatoria"):
            with self.subTest(metodo=metodo):
                np.random.seed(1)
                a = self.busca(metodo, 5)
                np.random.seed(999)
                np.random.rand(1000)
                with sem_gerador_global():
                    b = self.busca(metodo, 5)
                self.assertEqual([x.genes for x in a.avaliacoes], [x.genes for x in b.avaliacoes])
                self.assertEqual([x.nota for x in a.avaliacoes], [x.nota for x in b.avaliacoes])
                self.assertEqual([x.detalhes for x in a.avaliacoes],
                                 [x.detalhes for x in b.avaliacoes])


class ConsistenciaIteracoesRevisorTests(unittest.TestCase):
    """A nota que a busca vê na iteração N tem de ser a que a regra 'até N' dá."""

    GENES = (
        {"chance_inicial": 0.5, "sensibilidade": 8},
        {"chance_inicial": 0.3, "sensibilidade": 14},
        {"chance_inicial": 0.7, "sensibilidade": 1},
        {"chance_inicial": 0.45, "sensibilidade": 20},
        {"chance_inicial": 0.6, "sensibilidade": 12},
        {"chance_inicial": 0.4, "sensibilidade": 17},
    )

    def test_padding_bate_com_nota_com_iteracoes_em_todo_n(self):
        sdf = esfera_sdf()
        sementes = (1, 2, 3)
        maximo = 12
        motivos = set()
        # Dois alvos: com o menor, o corte de excesso fica alcançável na grade 16³.
        for alvo in (Alvo(sdf + 3), Alvo(sdf - 1)):
            avaliador = AvaliadorCA(sdf, alvo, sementes, max_iteracoes=maximo)
            for genes in self.GENES:
                trajetorias = avaliador.trajetorias(genes)
                motivos.update(t.motivo for t in trajetorias)
                por_semente = np.stack([t.notas for t in trajetorias])
                for n in range(1, maximo + 1):
                    with self.subTest(genes=genes, n=n, referencia=alvo.referencia):
                        np.testing.assert_array_equal(
                            avaliador.nota_com_iteracoes(genes, n, sementes),
                            por_semente[:, n - 1])
        # O teste só vale se passou pelos três tipos de parada.
        self.assertTrue({"vazio_demais", "vazio_de_menos", "convergiu"} <= motivos, motivos)

    def test_depois_do_corte_a_nota_e_minima_e_a_media_nao_avisa(self):
        sdf = esfera_sdf()
        alvo = Alvo(sdf + 3)
        avaliador = AvaliadorCA(sdf, alvo, (1, 2, 3), max_iteracoes=10)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for genes in self.GENES:
                nota, detalhes = avaliador(genes)
                self.assertFalse(np.isnan(nota))
                for t in avaliador.trajetorias(genes):
                    if t.motivo in ("vazio_demais", "vazio_de_menos"):
                        self.assertTrue(np.all(t.notas[t.parada - 1:] == NOTA_MINIMA))
                self.assertTrue(1 <= detalhes["iteracoes"] <= 10)

    def test_rodar_ca_nao_aceita_volume_nao_cubico(self):
        sdf = np.zeros((8, 8, 10), dtype=np.float32)
        sdf[3:5, 3:5, 3:7] = 1
        with self.assertRaises(ValueError):
            rodar_ca({"chance_inicial": 0.5, "sensibilidade": 8},
                     sdf, Alvo(sdf), semente=1)


class ExecutarRevisorTests(unittest.TestCase):
    def test_sementes_de_ajuste_e_reservadas_sao_disjuntas(self):
        from cavegen.optimization.genetic import executar

        self.assertFalse(set(executar.SEMENTES_AJUSTE) & set(executar.SEMENTES_RESERVADAS))
        self.assertEqual(len(executar.SEMENTES_RESERVADAS), 10)

    def test_busca_so_usa_sementes_de_ajuste_e_reservadas_so_depois(self):
        from cavegen.optimization.genetic import executar

        usadas = []
        original = modulo_ca.generate_seed_matrix

        def espiar(lado, chance, seed=None):
            usadas.append(seed)
            return original(lado, chance, seed=seed)

        with (tempfile.TemporaryDirectory() as pasta,
              mock.patch.object(modulo_ca, "generate_seed_matrix", side_effect=espiar)):
            destino = rodar_executar(Path(pasta), "--orcamento", "6", "--populacao", "3")
            with np.load(destino) as r:
                unicas = 6 - int(r["reaproveitadas"])
                listados = len(json.loads(str(r["melhores"])))
        # A busca só vê as de ajuste; as reservadas rodam depois, uma vez para
        # cada parâmetro da lista dos melhores.
        na_busca, no_fim = usadas[:3 * unicas], usadas[3 * unicas:]
        self.assertTrue(set(na_busca) <= set(executar.SEMENTES_AJUSTE), set(na_busca))
        self.assertGreater(listados, 0)
        self.assertEqual(no_fim, list(executar.SEMENTES_RESERVADAS) * listados)

    def test_ga_e_aleatoria_gravam_o_mesmo_protocolo_e_se_reproduzem(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            ga = rodar_executar(pasta, "--orcamento", "6", "--populacao", "3", "--seed", "4")
            ga2 = rodar_executar(pasta, "--orcamento", "6", "--populacao", "3", "--seed", "4")
            aleatoria = rodar_executar(pasta, "--metodo", "aleatoria", "--orcamento", "6",
                                       "--populacao", "3", "--seed", "4")
            e_ga, e_al = extras_gravados(ga), extras_gravados(aleatoria)
            for campo in ("genes_limites", "max_iteracoes", "borda", "sementes_ajuste",
                          "sementes_reservadas"):
                self.assertEqual(e_ga[campo], e_al[campo], campo)
            self.assertEqual(e_ga["borda"], "nearest")
            self.assertEqual(e_ga["config"]["orcamento"], e_al["config"]["orcamento"])
            with np.load(ga) as a, np.load(ga2) as b, np.load(aleatoria) as c:
                self.assertEqual(len(a["notas"]), len(c["notas"]))
                np.testing.assert_array_equal(a["notas"], b["notas"])
                np.testing.assert_array_equal(a["genes"], b["genes"])
            self.assertEqual(e_ga["notas_reservadas"], extras_gravados(ga2)["notas_reservadas"])

    def test_nota_gravada_do_campeao_se_reproduz_fora_da_busca(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = rodar_executar(Path(pasta), "--orcamento", "6", "--populacao", "3")
            extras = extras_gravados(destino)
        sdf = esfera_sdf()
        avaliador = AvaliadorCA(sdf, Alvo(sdf + 3), tuple(extras["sementes_ajuste"]))
        campeao = extras["campeao"]
        ajuste = avaliador.nota_com_iteracoes(campeao["genes"], campeao["iteracoes"],
                                              tuple(extras["sementes_ajuste"]))
        reservadas = avaliador.nota_com_iteracoes(campeao["genes"], campeao["iteracoes"],
                                                  tuple(extras["sementes_reservadas"]))
        self.assertEqual(float(ajuste.mean()), campeao["nota_ajuste"])
        self.assertEqual(reservadas.tolist(), extras["notas_reservadas"])


ANSI = re.compile(r"\033\[[0-9;]*m")
CHANCE = GENES_CA[0]
GRADE_CHANCE = [round(0.2 + k * 0.02, 10) for k in range(31)]


class GradeRevisorTests(unittest.TestCase):
    """O gene com passo (chance_inicial de 0,02 em 0,02) e as bordas da grade."""

    def test_grade_da_chance_tem_31_pontos_fixos_que_sobrevivem_ao_json(self):
        self.assertEqual(CHANCE.passos(), 30)
        pontos = [CHANCE.corrigir(0.2 + k * 0.02) for k in range(31)]
        self.assertEqual(pontos, GRADE_CHANCE)
        self.assertEqual(len(set(pontos)), 31)
        for ponto in pontos:
            # corrigir é idempotente e o ponto volta igual do json (campeão no npz).
            self.assertEqual(CHANCE.corrigir(ponto), ponto)
            self.assertEqual(json.loads(json.dumps(ponto)), ponto)

    def test_chances_vizinhas_viram_o_mesmo_candidato_e_a_grade_muda_a_semente(self):
        # O motivo da mudança: 0,5639 e 0,564 eram a mesma caverna; agora são o
        # mesmo candidato (mesma chave do cache).
        a = {"chance_inicial": CHANCE.corrigir(0.5639), "sensibilidade": 9}
        b = {"chance_inicial": CHANCE.corrigir(0.564), "sensibilidade": 9}
        self.assertEqual(chave(a), chave(b))
        vizinhos = (modulo_ca.generate_seed_matrix(16, 0.56, seed=1)
                    != modulo_ca.generate_seed_matrix(16, 0.58, seed=1))
        self.assertGreater(int(vizinhos.sum()), 16 ** 3 * 0.01)

    def test_sortear_com_passo_e_uniforme_inclusive_nas_pontas(self):
        # As pontas não podem ter metade do peso (o que um round sobre uniform daria).
        rng = np.random.default_rng(0)
        contagem = {p: 0 for p in GRADE_CHANCE}
        for _ in range(31 * 1000):
            contagem[CHANCE.sortear(rng)] += 1
        self.assertEqual(set(contagem), set(GRADE_CHANCE))
        self.assertTrue(all(850 <= n <= 1150 for n in contagem.values()), contagem)

    def test_como_dict_reconstroi_o_mesmo_gene_e_aceita_o_formato_antigo(self):
        for gene in GENES_CA:
            self.assertEqual(Gene(**gene.como_dict()), gene)
        antigo = {"nome": "chance_inicial", "minimo": 0.3, "maximo": 0.7, "inteiro": False}
        self.assertIsNone(Gene(**antigo).passo)

    def test_faixa_que_nao_fecha_com_o_passo_fica_na_faixa_e_na_grade(self):
        rng = np.random.default_rng(1)
        for gene in (Gene("a", 0.0, 1.0, passo=0.3), Gene("b", 0.2, 0.81, passo=0.02),
                     Gene("c", -1.0, 0.5, passo=0.4), Gene("d", 0.0, 0.3, passo=0.1)):
            with self.subTest(gene=gene):
                grade = {gene.corrigir(gene.minimo + k * gene.passo)
                         for k in range(gene.passos() + 1)}
                valores = [gene.sortear(rng) for _ in range(300)]
                valores += [gene.corrigir(v) for v in (-1e6, gene.minimo, gene.maximo, 1e6)]
                valores += [mutar({gene.nome: v}, (gene,), 1.0, 2.0, rng)[gene.nome]
                            for v in valores[:100]]
                for v in valores:
                    self.assertTrue(gene.minimo <= v <= gene.maximo, v)
                    self.assertIn(v, grade)
        self.assertEqual(Gene("d", 0.0, 0.3, passo=0.1).passos(), 3)  # 0,3 / 0,1 = 2,999...

    def test_gene_com_passo_nao_sai_da_faixa_quando_o_limite_nao_cabe_em_10_casas(self):
        # Contrato do Gene: limites fechados. O round(..., 10) de _na_grade e a
        # folga de 1e-9 de passos() levam o valor para fora da faixa quando o
        # limite tem mais casas que isso.
        casos = (
            (Gene("fino", 0.12345678901234, 0.5, passo=0.01), 0.0),  # dá 0,123456789 < mínimo
            (Gene("quase", 0.0, 0.99999999999, passo=0.1), 1.0),     # dá 1,0 > máximo
        )
        for gene, valor in casos:
            with self.subTest(gene=gene.nome):
                corrigido = gene.corrigir(valor)
                self.assertTrue(gene.minimo <= corrigido <= gene.maximo, corrigido)

    def test_mutacao_com_passo_nao_fica_presa_no_mesmo_ponto(self):
        # Desvio de 10% da faixa = 3 passos: no meio volta ao mesmo ponto ~13%
        # das vezes; na ponta ~57% (metade dos desvios sai da faixa e é limitada).
        rng = np.random.default_rng(2)
        for inicio, teto in ((0.5, 0.2), (0.8, 0.65), (0.2, 0.65)):
            with self.subTest(inicio=inicio):
                filhos = [mutar({"chance_inicial": inicio}, (CHANCE,), 1.0, 0.1, rng)
                          ["chance_inicial"] for _ in range(4000)]
                self.assertLess(filhos.count(inicio) / len(filhos), teto)
                self.assertGreater(len(set(filhos)), 8)


class TerminalFalsoRevisor(io.StringIO):
    def isatty(self):
        return True


def largura_na_tela(texto: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) == "W" else 1 for c in texto)


def melhores_falsos() -> list[dict]:
    return [{"posicao": i,
             "genes": {"chance_inicial": GRADE_CHANCE[10 + i], "sensibilidade": 9 + i},
             "iteracoes": 10 + i, "nota_ajuste": 0.7 - i / 50,
             "nota_reservada_media": NOTA_MINIMA if i == 5 else 0.6 - i / 50,
             "nota_reservada_min": NOTA_MINIMA if i >= 4 else 0.5 - i / 50}
            for i in range(1, 7)]


def sessao_do_painel(painel: Painel):
    """O que o executar.py mostra, do começo ao fim, com uma busca pequena."""
    def nota(genes):
        if genes["sensibilidade"] > 16:
            return NOTA_MINIMA, {"iteracoes": 1, "motivos": ["vazio_demais"]}
        return (-abs(genes["chance_inicial"] - 0.5) - genes["sensibilidade"] / 100,
                {"iteracoes": 3, "motivos": ["convergiu"]})

    painel.etapa(2, 4, "Busca genética", "🧬")
    resultado = evoluir(GENES_CA, nota, ConfiguracaoGA(orcamento=60), seed=7, observar=painel)
    painel.etapa(3, 4, "Conferindo", "🔍")
    painel.conferido(1, 2, {"chance_inicial": 0.5, "sensibilidade": 3}, 0.6, 0.61, 0.5)
    painel.conferido(2, 2, {"chance_inicial": 0.52, "sensibilidade": 3}, 0.6, NOTA_MINIMA,
                     NOTA_MINIMA)
    painel.tabela_melhores(melhores_falsos(), [g.nome for g in GENES_CA], 10)
    painel.referencias(0.1, 1.0, "results/ga_001.npz")
    return resultado


class PainelRevisorTests(unittest.TestCase):
    def test_painel_colorido_e_ao_vivo_nao_muda_a_busca(self):
        sem = sessao_do_painel(Painel(60, saida=io.StringIO(), ao_vivo=False, estilo=Estilo()))
        com = sessao_do_painel(Painel(60, saida=TerminalFalsoRevisor(), ao_vivo=True,
                                      estilo=Estilo(cores=True, emojis=True)))
        self.assertEqual([a.genes for a in sem.avaliacoes], [a.genes for a in com.avaliacoes])
        self.assertEqual([a.nota for a in sem.avaliacoes], [a.nota for a in com.avaliacoes])
        self.assertEqual(sem.reaproveitadas, com.reaproveitadas)

    def test_cor_so_acrescenta_codigos_ao_texto_puro(self):
        # Com emojis desligados, tirar os códigos ANSI tem de dar exatamente o
        # texto puro, inclusive os espaços que apagam a linha viva.
        for ao_vivo in (False, True):
            with self.subTest(ao_vivo=ao_vivo):
                puro, colorido = io.StringIO(), io.StringIO()
                sessao_do_painel(Painel(60, saida=puro, ao_vivo=ao_vivo, estilo=Estilo()))
                sessao_do_painel(Painel(60, saida=colorido, ao_vivo=ao_vivo,
                                        estilo=Estilo(cores=True)))
                self.assertNotIn("\033", puro.getvalue())
                self.assertIn("\033[", colorido.getvalue())
                self.assertEqual(ANSI.sub("", colorido.getvalue()), puro.getvalue())

    def test_tabela_pura_igual_a_antiga_mostrar_lista_quando_as_notas_sao_finitas(self):
        lista = [dict(item, nota_reservada_media=0.4, nota_reservada_min=0.3)
                 for item in melhores_falsos()]
        nomes = [g.nome for g in GENES_CA]
        antiga = [f"{'#':>3} " + " ".join(f"{n:>15}" for n in nomes)
                  + f" {'iteracoes':>9} {'nota ajuste':>11} {'reservadas':>10} {'mín':>7}"]
        for item in lista:
            valores = " ".join(f"{item['genes'][n]:>15.4g}" for n in nomes)
            antiga.append(f"{item['posicao']:>3} {valores} {item['iteracoes']:>9} "
                          f"{item['nota_ajuste']:>+11.3f} {item['nota_reservada_media']:>+10.3f} "
                          f"{item['nota_reservada_min']:>+7.3f}")
        saida = io.StringIO()
        Painel(10, saida=saida, estilo=Estilo()).tabela_melhores(lista, nomes, 10)
        self.assertEqual(saida.getvalue().splitlines()[2:], antiga)

    def test_tabela_com_medalhas_fica_alinhada_na_tela(self):
        saida = io.StringIO()
        Painel(10, saida=saida, estilo=Estilo(cores=True, emojis=True)).tabela_melhores(
            melhores_falsos(), [g.nome for g in GENES_CA], 10)
        linhas = [ANSI.sub("", linha) for linha in saida.getvalue().splitlines()[2:]]
        self.assertTrue(linhas[1].startswith("🥇 "), linhas[1])
        self.assertEqual(len({largura_na_tela(linha) for linha in linhas}), 1, linhas)

    def test_estilo_para_fora_do_terminal_nunca_liga_nem_chama_o_console(self):
        with mock.patch("cavegen.optimization.genetic.painel._ativar_ansi") as ativar:
            estilo = Estilo.para(io.StringIO())
        self.assertFalse(estilo.cores or estilo.emojis)
        ativar.assert_not_called()


class ExecutarGradeRevisorTests(unittest.TestCase):
    def test_executar_grava_o_passo_e_so_pontos_da_grade(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = rodar_executar(Path(pasta), "--orcamento", "8", "--populacao", "4")
            extras = extras_gravados(destino)
            with np.load(destino) as r:
                nomes = list(r["genes_nomes"])
                chances = r["genes"][:, nomes.index("chance_inicial")].tolist()
                melhores = json.loads(str(r["melhores"]))
        limites = {d["nome"]: d for d in extras["genes_limites"]}
        self.assertEqual(limites["chance_inicial"]["passo"], 0.02)
        self.assertIsNone(limites["sensibilidade"]["passo"])
        self.assertEqual(extras["max_iteracoes"], 40)
        self.assertTrue(set(chances) <= set(GRADE_CHANCE), chances)
        self.assertIn(extras["campeao"]["genes"]["chance_inicial"], GRADE_CHANCE)
        self.assertTrue(all(m["genes"]["chance_inicial"] in GRADE_CHANCE for m in melhores))

    def test_executar_so_imprime_pelo_painel_e_sai_puro_fora_do_terminal(self):
        from cavegen.optimization.genetic import executar

        do_painel = io.StringIO()
        original = executar.Painel

        def painel_capturado(*args, **kwargs):
            return original(*args, saida=do_painel, **kwargs)

        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            sdf = esfera_sdf()
            np.savez_compressed(pasta / "peso.npz", sdf=sdf, convencao=np.array("base"),
                                limiar=0.0)
            np.savez_compressed(pasta / "alvo.npz", sdf=sdf + 3, convencao=np.array("alvo"),
                                limiar=-3.0, escala_log=1.0)
            fora = io.StringIO()
            with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
                  mock.patch.object(executar, "Painel", side_effect=painel_capturado),
                  contextlib.redirect_stdout(fora)):
                executar.main(["--peso", str(pasta / "peso.npz"),
                               "--alvo", str(pasta / "alvo.npz"),
                               "--saida", str(pasta / "results"), "--orcamento", "6",
                               "--populacao", "3"])
        texto = do_painel.getvalue()
        self.assertEqual(fora.getvalue(), "")
        self.assertNotIn("\033", texto)
        self.assertNotIn("\r", texto)
        for trecho in ("[1/4] Carregando", "chance_inicial [0.2, 0.8, de 0.02 em 0.02]",
                       "[4/4] Gravando", "melhores parâmetros", "referências: cópia pura",
                       "gravado em"):
            self.assertIn(trecho, texto)


if __name__ == "__main__":
    unittest.main()
