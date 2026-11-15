"""Testes adversariais do revisor para o GA do CA guiado por SDF e a borda NEAREST.

    uv run python -m unittest tests/test_genetic_revisor.py -v
"""
import contextlib
import io
import json
import tempfile
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
    evoluir,
)
from cavegen.optimization.genetic.aptidao import NOTA_MINIMA, Alvo
from cavegen.optimization.genetic.ca import GENES_CA, MAX_ITERACOES, AvaliadorCA, rodar_ca

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
        limites = {g.nome: (g.minimo, g.maximo, g.inteiro) for g in GENES_CA}
        self.assertEqual(limites, {"chance_inicial": (0.3, 0.7, False),
                                   "sensibilidade": (1, 20, True)})
        self.assertEqual(MAX_ITERACOES, 50)
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

    def test_busca_so_usa_sementes_de_ajuste_e_reservadas_so_no_campeao(self):
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
        na_busca, no_fim = usadas[:-10], usadas[-10:]
        self.assertEqual(len(na_busca), 3 * unicas)
        self.assertTrue(set(na_busca) <= set(executar.SEMENTES_AJUSTE), set(na_busca))
        self.assertEqual(no_fim, list(executar.SEMENTES_RESERVADAS))

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


if __name__ == "__main__":
    unittest.main()
