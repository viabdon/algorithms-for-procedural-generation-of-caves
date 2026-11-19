"""Confere o observador do motor do GA e o painel que mostra o andamento.

    uv run python -m unittest tests/test_genetic_painel.py -v
"""
import io
import re
import unittest
from unittest import mock

from cavegen.optimization.genetic.algoritmo import (
    Avaliacao,
    ConfiguracaoGA,
    Gene,
    busca_aleatoria,
    evoluir,
)
from cavegen.optimization.genetic.aptidao import NOTA_MINIMA
from cavegen.optimization.genetic.painel import Estilo, Painel

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

class TerminalFalso(io.StringIO):
    """StringIO que diz ser terminal, com a codificação escolhida."""
    def __init__(self, encoding="utf-8"):
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self):
        return self._encoding

    def isatty(self):
        return True

def melhores_falsos(nota_min=0.5):
    return [{"posicao": i, "genes": {"x": 0.5 + i / 100, "n": 13}, "iteracoes": 20 + i,
             "nota_ajuste": 0.6 - i / 100, "nota_reservada_media": 0.62,
             "nota_reservada_min": nota_min if i == 4 else 0.5} for i in range(1, 6)]

ATIVAR_ANSI = "cavegen.optimization.genetic.painel._ativar_ansi"

class EstiloTests(unittest.TestCase):
    def test_fora_do_terminal_sai_texto_puro(self):
        saida = io.StringIO()
        painel = Painel(40, saida=saida)
        evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=40), seed=3, observar=painel)
        painel.etapa(3, 4, "Conferindo", "🔍")
        painel.conferido(1, 1, {"x": 0.5, "n": 3}, 0.6, 0.61, NOTA_MINIMA)
        painel.tabela_melhores(melhores_falsos(), ["x", "n"], 10)
        painel.referencias(0.1, 1.0, "results/ga_001.npz")
        texto = saida.getvalue()
        self.assertNotIn("\033", texto)
        # Nada de emoji: só letras, acentos e o ponto do meio.
        self.assertTrue(all(ord(c) < 0x2000 or c == "·" for c in texto))

    def test_terminal_com_cor_pinta_e_poe_emoji(self):
        saida = TerminalFalso()
        with mock.patch.dict("os.environ"), mock.patch(ATIVAR_ANSI, return_value=True):
            import os
            os.environ.pop("NO_COLOR", None)
            estilo = Estilo.para(saida)
        self.assertTrue(estilo.cores and estilo.emojis)
        painel = Painel(40, saida=saida, ao_vivo=False, estilo=estilo)
        evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=40), seed=3, observar=painel)
        texto = saida.getvalue()
        self.assertIn("\033[", texto)
        self.assertIn("🧬", texto)
        self.assertIn("🏆", texto)

    def test_no_color_desliga_as_cores(self):
        with mock.patch.dict("os.environ", {"NO_COLOR": "1"}), \
                mock.patch(ATIVAR_ANSI, return_value=True):
            estilo = Estilo.para(TerminalFalso())
        self.assertFalse(estilo.cores)

    def test_terminal_sem_unicode_fica_sem_emoji(self):
        with mock.patch(ATIVAR_ANSI, return_value=True):
            estilo = Estilo.para(TerminalFalso(encoding="cp1252"))
        self.assertFalse(estilo.emojis)
        saida = TerminalFalso(encoding="cp1252")
        Painel(10, saida=saida, estilo=estilo).etapa(1, 4, "Carregando", "📂")
        saida.getvalue().encode("cp1252")  # não pode ter caractere que o console não imprime

    def test_tabela_alinhada_com_cor_e_sem_cor(self):
        for estilo in (Estilo(), Estilo(cores=True)):
            saida = io.StringIO()
            Painel(10, saida=saida, estilo=estilo).tabela_melhores(
                melhores_falsos(NOTA_MINIMA), ["x", "n"], 10)
            linhas = [re.sub(r"\033\[[0-9;]*m", "", linha)
                      for linha in saida.getvalue().splitlines()[2:]]
            self.assertEqual(len({len(linha) for linha in linhas}), 1, linhas)
            self.assertIn("cortado", linhas[4])

    def test_novo_recorde_so_quando_o_melhor_sobe(self):
        saida = io.StringIO()
        painel = Painel(6, saida=saida)

        def geracao(numero, notas):
            populacao = [Avaliacao({"x": 0.5, "n": 3}, nota, {"iteracoes": 1}, numero, 0)
                         for nota in notas]
            for avaliacao in populacao:
                painel("candidato", {"avaliacao": avaliacao, "restante": 0, "repetido": False})
            painel("geracao", {"geracao": numero, "populacao": populacao})

        geracao(0, [0.1, 0.2])
        geracao(1, [0.2, 0.15])    # empatou com o melhor: não é recorde
        geracao(2, [0.2001, 0.0])  # subiu, mesmo que o terminal mostre +0.200 de novo
        linhas = saida.getvalue().splitlines()
        self.assertEqual(["novo recorde" in linha for linha in linhas], [False, False, True])

    def test_fragil_aparece_quando_uma_seed_reservada_corta(self):
        saida = io.StringIO()
        Painel(10, saida=saida).conferido(1, 2, {"x": 0.5}, 0.6, NOTA_MINIMA, NOTA_MINIMA)
        self.assertIn("frágil", saida.getvalue())

if __name__ == "__main__":
    unittest.main()
