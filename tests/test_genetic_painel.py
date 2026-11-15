"""Confere o observador do motor do GA e o painel que mostra o andamento.

    uv run python -m unittest tests/test_genetic_painel.py -v
"""
import io
import unittest

from cavegen.optimization.genetic.algoritmo import (
    ConfiguracaoGA,
    Gene,
    busca_aleatoria,
    evoluir,
)
from cavegen.optimization.genetic.aptidao import NOTA_MINIMA
from cavegen.optimization.genetic.painel import Painel

GENES = (Gene("x", 0.0, 1.0), Gene("n", 1, 20, inteiro=True))

def sintetica(genes: dict) -> tuple[float, dict]:
    if genes["n"] > 15:
        return NOTA_MINIMA, {"iteracoes": 1, "motivos": ["vazio_demais"]}
    return -((genes["x"] - 0.3) ** 2), {"iteracoes": 3, "motivos": ["convergiu"]}

class ObservadorTests(unittest.TestCase):
    def test_observar_nao_muda_a_busca(self):
        config = ConfiguracaoGA(orcamento=90)
        eventos = []
        sem = evoluir(GENES, sintetica, config, seed=5)
        com = evoluir(GENES, sintetica, config, seed=5,
                      observar=lambda nome, dados: eventos.append(nome))
        self.assertEqual([a.genes for a in sem.avaliacoes], [a.genes for a in com.avaliacoes])
        self.assertEqual([a.nota for a in sem.avaliacoes], [a.nota for a in com.avaliacoes])
        self.assertEqual(eventos.count("candidato"), 90)

        aleatoria = []
        busca_aleatoria(GENES, sintetica, 30, seed=5,
                        observar=lambda nome, dados: aleatoria.append(nome))
        self.assertEqual(aleatoria, ["candidato"] * 30)

    def test_uma_geracao_por_populacao_completa(self):
        # 20 iniciais + 18 filhos por geração: 90 = 20 + 18 * 3 + 16.
        geracoes = []
        evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=90), seed=1,
                observar=lambda nome, dados: nome == "geracao" and geracoes.append(
                    (dados["geracao"], len(dados["populacao"]))))
        self.assertEqual(geracoes, [(0, 20), (1, 20), (2, 20), (3, 20), (4, 18)])

    def test_aviso_de_repetido(self):
        repetidos = []
        resultado = evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=200), seed=2,
                            observar=lambda nome, dados: nome == "candidato"
                            and repetidos.append(dados["repetido"]))
        self.assertEqual(sum(repetidos), resultado.reaproveitadas)

class PainelTests(unittest.TestCase):
    def test_ga_imprime_uma_linha_por_geracao_sem_linha_viva_fora_do_terminal(self):
        saida = io.StringIO()
        painel = Painel(90, saida=saida)
        evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=90), seed=1, observar=painel)
        linhas = saida.getvalue().splitlines()

        self.assertFalse(painel.ao_vivo)  # StringIO não é terminal
        self.assertNotIn("\r", saida.getvalue())
        self.assertEqual(len(linhas), 5)
        self.assertTrue(linhas[0].startswith("  geração   0 | 20/90 | melhor"))
        self.assertIn("90/90", linhas[-1])

    def test_linha_viva_mostra_cada_candidato_e_os_cortados(self):
        saida = io.StringIO()
        painel = Painel(40, saida=saida, ao_vivo=True)
        evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=40), seed=3, observar=painel)
        texto = saida.getvalue()

        self.assertIn("\r  candidato 1/40 · geração 0 · ", texto)
        self.assertIn("candidato 40/40", texto)
        self.assertIn("cortado (vazio_demais)", texto)

    def test_busca_aleatoria_resume_por_lote(self):
        saida = io.StringIO()
        painel = Painel(50, por_lote=True, tamanho_lote=20, saida=saida)
        busca_aleatoria(GENES, sintetica, 50, seed=4, observar=painel)
        linhas = saida.getvalue().splitlines()

        self.assertEqual([linha.split("|")[0].strip() for linha in linhas],
                         ["lote   1", "lote   2", "lote   3"])
        self.assertIn("50/50", linhas[-1])

    def test_etapa(self):
        saida = io.StringIO()
        Painel(10, saida=saida).etapa(2, 4, "Busca genética")
        self.assertEqual(saida.getvalue(), "\n[2/4] Busca genética\n")

if __name__ == "__main__":
    unittest.main()
