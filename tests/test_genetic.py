"""Confere o motor do algoritmo genético, a nota sobre o alvo e o avaliador do CA.

    uv run python -m unittest tests/test_genetic.py -v
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from cavegen.optimization.genetic import ca as modulo_ca
from cavegen.optimization.genetic.algoritmo import (
    ConfiguracaoGA,
    Gene,
    busca_aleatoria,
    cruzar,
    evoluir,
    mutar,
)
from cavegen.optimization.genetic.aptidao import (
    NOTA_MINIMA,
    Alvo,
    Cortes,
    motivo_da_parada,
    nota_da_copia_pura,
    nota_do_passo,
)
from cavegen.optimization.genetic.ca import GENES_CA, AvaliadorCA, rodar_ca
from cavegen.sdf.manipulacao import comprimir_log

GENES = (Gene("x", 0.0, 1.0), Gene("n", 1, 20, inteiro=True))

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

    def test_regras_de_parada(self):
        alvo = Alvo(np.ones((10, 10, 10)))  # referência 1000: faixa [500, 5000] de vazio
        cortes = Cortes(fracao_convergencia=0.01)  # 10 células
        # Acima do máximo, mas encolhendo: continua (é o ruído inicial).
        self.assertIsNone(motivo_da_parada(6000, 9000, 3000, alvo, cortes))
        self.assertEqual(motivo_da_parada(6000, 6000, 50, alvo, cortes), "vazio_demais")
        self.assertEqual(motivo_da_parada(6100, 6000, 100, alvo, cortes), "vazio_demais")
        # Abaixo do mínimo, mas crescendo: continua.
        self.assertIsNone(motivo_da_parada(400, 300, 100, alvo, cortes))
        self.assertEqual(motivo_da_parada(400, 450, 50, alvo, cortes), "vazio_de_menos")
        self.assertEqual(motivo_da_parada(1000, 1003, 9, alvo, cortes), "convergiu")
        self.assertIsNone(motivo_da_parada(1000, 1003, 10, alvo, cortes))

    def test_nota_do_passo_corta_fora_da_faixa(self):
        alvo = Alvo(np.pad(np.ones((2, 2, 2)), 1, constant_values=-1))  # referência 8
        vazio = np.zeros(alvo.shape, dtype=bool)
        vazio[1:3, 1:3, 1:3] = True
        self.assertEqual(nota_do_passo(vazio, alvo, Cortes()), 1.0)
        self.assertEqual(nota_do_passo(np.ones(alvo.shape, bool), alvo, Cortes()), NOTA_MINIMA)
        vazio[:] = False
        vazio[1, 1, 1] = True  # 1 < 0,5 x 8
        self.assertEqual(nota_do_passo(vazio, alvo, Cortes()), NOTA_MINIMA)

    def test_copia_pura(self):
        sdf = esfera_sdf()
        alvo = Alvo(sdf + 3)  # zero 3 voxels para fora
        nota = nota_da_copia_pura(sdf, alvo)
        self.assertEqual(nota, alvo.nota(sdf > 0))
        self.assertTrue(0 < nota < 1)

class AvaliadorCATests(unittest.TestCase):
    def setUp(self):
        self.sdf = esfera_sdf()
        self.alvo = Alvo(self.sdf + 3)
        self.genes = {"chance_inicial": 0.5, "sensibilidade": 10}

    def test_rodar_ca_e_reproduzivel_e_completa_as_notas(self):
        a = rodar_ca(self.genes, self.sdf, self.alvo, semente=3, max_iteracoes=30)
        b = rodar_ca(self.genes, self.sdf, self.alvo, semente=3, max_iteracoes=30)

        np.testing.assert_array_equal(a.final, b.final)
        np.testing.assert_array_equal(a.notas, b.notas)
        self.assertEqual(a.notas.shape, (30,))
        self.assertEqual(len(a.vazios), a.parada)
        # Depois da parada, a nota repete a do passo em que parou.
        self.assertTrue(np.all(a.notas[a.parada - 1:] == a.notas[a.parada - 1]))
        self.assertEqual(int(a.final.sum()), a.vazios[-1])

    def test_melhor_iteracao_e_a_da_media_das_sementes(self):
        avaliador = AvaliadorCA(self.sdf, self.alvo, (1, 2), max_iteracoes=20)
        nota, detalhes = avaliador(self.genes)
        media = np.mean([t.notas for t in avaliador.trajetorias(self.genes)], axis=0)

        self.assertEqual(detalhes["iteracoes"], int(np.argmax(media)) + 1)
        self.assertEqual(nota, float(media.max()))
        self.assertGreater(nota, 0)

    def test_iteracao_escolhida_se_reproduz_sem_escolher_de_novo(self):
        # É o que garante a avaliação honesta nas sementes reservadas: rodar com
        # N = iteração escolhida dá exatamente a nota que a busca viu.
        avaliador = AvaliadorCA(self.sdf, self.alvo, (1, 2, 3), max_iteracoes=25)
        nota, detalhes = avaliador(self.genes)
        repetida = avaliador.nota_com_iteracoes(self.genes, detalhes["iteracoes"], (1, 2, 3))

        np.testing.assert_array_equal(repetida, detalhes["notas_por_semente"])
        self.assertEqual(float(repetida.mean()), nota)

    def test_candidato_que_morre_recebe_a_nota_minima(self):
        avaliador = AvaliadorCA(self.sdf, self.alvo, (1,), max_iteracoes=10)
        nota, detalhes = avaliador({**self.genes, "sensibilidade": 27})

        self.assertEqual(nota, NOTA_MINIMA)
        self.assertEqual(detalhes["motivos"], ["vazio_de_menos"])

    def test_cromossomo_nao_tem_escala_do_peso(self):
        self.assertEqual([g.nome for g in GENES_CA], ["chance_inicial", "sensibilidade"])

    def test_peso_chega_ao_ca_identico_ao_carregado(self):
        # Contrato: nada multiplica, comprime ou corta o peso entre o arquivo e o CA.
        peso = comprimir_log(self.sdf, 1.0)
        recebidos = []
        original = modulo_ca.iterate

        def espiar(matriz, sensibilidade, borda, peso_recebido=None, *args, **kwargs):
            recebidos.append(peso_recebido)
            return original(matriz, sensibilidade, borda, peso_recebido, *args, **kwargs)

        avaliador = AvaliadorCA(peso, self.alvo, (1, 2), max_iteracoes=5)
        with mock.patch.object(modulo_ca, "iterate", side_effect=espiar):
            avaliador(self.genes)
            avaliador.nota_com_iteracoes(self.genes, 3, (101,))
        self.assertTrue(recebidos)
        for recebido in recebidos:
            self.assertTrue(np.array_equal(recebido, peso))
            self.assertEqual(recebido.dtype, peso.dtype)

    def test_avaliador_guarda_copia_do_peso(self):
        peso = comprimir_log(self.sdf, 1.0)
        avaliador = AvaliadorCA(peso, self.alvo, (1,), max_iteracoes=3)
        antes = avaliador(self.genes)[0]
        peso *= 10  # mexer no original não muda o que o avaliador usa
        self.assertEqual(avaliador(self.genes)[0], antes)
        self.assertFalse(avaliador.peso.flags.writeable)

    def test_peso_e_alvo_precisam_do_mesmo_cubo(self):
        with self.assertRaises(ValueError):
            rodar_ca(self.genes, self.sdf, Alvo(np.ones((8, 8, 8))), semente=1)

class ExecutarTests(unittest.TestCase):
    def test_execucao_curta_grava_tudo(self):
        from cavegen.optimization.genetic import executar

        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            sdf = esfera_sdf()
            np.savez_compressed(pasta / "peso.npz", sdf=sdf, convencao=np.array("base"),
                                limiar=0.0)
            np.savez_compressed(pasta / "alvo.npz", sdf=sdf + 3, convencao=np.array("alvo"),
                                limiar=-3.0, escala_log=1.0)
            # Sem gravar na planilha real do track_resources.
            with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
                  contextlib.redirect_stdout(io.StringIO())):
                destino = executar.main(["--orcamento", "6", "--populacao", "3",
                                         "--peso", str(pasta / "peso.npz"),
                                         "--alvo", str(pasta / "alvo.npz"),
                                         "--saida", str(pasta / "results")])
            with np.load(destino) as r:
                self.assertEqual(str(r["metodo"]), "genetico")
                self.assertEqual(r["genes"].shape, (6, 2))
                self.assertEqual(r["notas"].shape, (6,))
                for campo in ("campeao", "notas_reservadas", "nota_copia_pura", "cortes",
                              "sementes_reservadas", "alvo", "genes_limites", "detalhes",
                              "nota_teto_trivial", "forma", "ambiente"):
                    self.assertIn(campo, r.files)
                # O alvo é o peso deslocado em 3: cortar o peso em -3 acerta tudo.
                self.assertEqual(json.loads(str(r["nota_teto_trivial"])), 1.0)
                detalhes = json.loads(str(r["detalhes"]))
                self.assertEqual(len(detalhes), 6)
                self.assertEqual(len(detalhes[0]["vazios"]), 3)  # uma lista por semente
                self.assertEqual(json.loads(str(r["forma"])), [16, 16, 16])
                ambiente = json.loads(str(r["ambiente"]))
                self.assertTrue(ambiente["arquivo_peso"].endswith("peso.npz"))
                self.assertEqual(len(ambiente["sha256_peso"]), 64)
                melhores = json.loads(str(r["melhores"]))
                campeao = json.loads(str(r["campeao"]))
                self.assertTrue(1 <= len(melhores) <= 6)
                self.assertEqual([m["posicao"] for m in melhores],
                                 list(range(1, len(melhores) + 1)))
                self.assertEqual(melhores[0]["genes"], campeao["genes"])
                self.assertEqual(melhores[0]["nota_reservada_media"],
                                 json.loads(str(r["nota_reservada_media"])))

    def test_top_limita_a_lista_e_cada_item_se_reproduz(self):
        from cavegen.optimization.genetic import executar

        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            sdf = esfera_sdf()
            np.savez_compressed(pasta / "peso.npz", sdf=sdf, convencao=np.array("base"),
                                limiar=0.0)
            np.savez_compressed(pasta / "alvo.npz", sdf=sdf + 3, convencao=np.array("alvo"),
                                limiar=-3.0, escala_log=1.0)
            with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
                  contextlib.redirect_stdout(io.StringIO())):
                destino = executar.main(["--metodo", "aleatoria", "--orcamento", "12",
                                         "--populacao", "3", "--top", "3",
                                         "--peso", str(pasta / "peso.npz"),
                                         "--alvo", str(pasta / "alvo.npz"),
                                         "--saida", str(pasta / "results")])
            with np.load(destino) as r:
                melhores = json.loads(str(r["melhores"]))
        self.assertLessEqual(len(melhores), 3)
        self.assertGreater(len(melhores), 0)
        avaliador = AvaliadorCA(sdf, Alvo(sdf + 3), executar.SEMENTES_AJUSTE)
        for item in melhores:
            ajuste = avaliador.nota_com_iteracoes(item["genes"], item["iteracoes"],
                                                  executar.SEMENTES_AJUSTE)
            reservadas = avaliador.nota_com_iteracoes(item["genes"], item["iteracoes"],
                                                      executar.SEMENTES_RESERVADAS)
            self.assertEqual(float(ajuste.mean()), item["nota_ajuste"])
            self.assertEqual(float(reservadas.mean()), item["nota_reservada_media"])
            self.assertEqual(float(reservadas.min()), item["nota_reservada_min"])

    def test_teto_trivial_com_peso_comprimido_por_log(self):
        # O padrão do GA é o peso com log: o teto converte o limiar do alvo
        # para a unidade do peso e continua acertando tudo.
        from cavegen.optimization.genetic import executar

        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            sdf = esfera_sdf()
            np.savez_compressed(pasta / "peso.npz", sdf=comprimir_log(sdf, 1.0),
                                convencao=np.array("log"), limiar=0.0, escala_log=1.0)
            np.savez_compressed(pasta / "alvo.npz", sdf=sdf + 3, convencao=np.array("alvo"),
                                limiar=-3.0, escala_log=1.0)
            with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
                  contextlib.redirect_stdout(io.StringIO())):
                destino = executar.main(["--orcamento", "3", "--populacao", "3",
                                         "--peso", str(pasta / "peso.npz"),
                                         "--alvo", str(pasta / "alvo.npz"),
                                         "--saida", str(pasta / "results")])
            with np.load(destino) as r:
                self.assertEqual(json.loads(str(r["nota_teto_trivial"])), 1.0)
                self.assertEqual(json.loads(str(r["peso"]))["escala_log"], 1.0)

    def test_peso_padrao_e_o_sdf_com_log_1(self):
        from cavegen.optimization.genetic import executar

        self.assertEqual(executar.PESO_ELAPHES.name, "elaphes_surface_64_sdf_log1.npz")
        self.assertIn("--log 1", executar.COMANDO_PESO)

if __name__ == "__main__":
    unittest.main()
