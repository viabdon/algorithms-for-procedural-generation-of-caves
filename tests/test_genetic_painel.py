"""Confere o observador do motor do GA e o painel que mostra o andamento.

    uv run python -m unittest tests/test_genetic_painel.py -v
"""
import io
import math
import re
import unittest
from unittest import mock

from cavegen.generators.cellular_automata.genetico.algoritmo import (
    Avaliacao,
    ConfiguracaoGA,
    Gene,
    busca_aleatoria,
    evoluir,
)
from cavegen.generators.cellular_automata.genetico.aptidao import NOTA_MINIMA
from cavegen.generators.cellular_automata.genetico.painel import Estilo, Painel, descrever_vazio

GENES = (Gene("x", 0.0, 1.0), Gene("n", 1, 20, inteiro=True))

def sintetica(genes: dict) -> tuple[float, dict]:
    # Os detalhes imitam os do AvaliadorCA: onde o vazio terminou em cada semente.
    if genes["n"] > 15:
        return NOTA_MINIMA, {"iteracoes": 1,
                             "cavernas": {"c": {"fim": ["vazio_demais", "na_faixa"]}}}
    return -((genes["x"] - 0.3) ** 2), {"iteracoes": 3,
                                        "cavernas": {"c": {"fim": ["na_faixa", "na_faixa"]}}}

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
        self.assertIn("cortado (no fim: vazio_demais)", texto)

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

def reservadas(media=0.62, pior=0.5, por_caverna=None):
    por_caverna = {"c": media} if por_caverna is None else por_caverna
    return {"media": media, "min": min(por_caverna.values()), "max": max(por_caverna.values()),
            "desvio": 0.0, "por_caverna": por_caverna, "pior_semente": pior}

def melhores_falsos(nota_min=0.5):
    return [{"posicao": i, "genes": {"x": 0.5 + i / 100, "n": 13}, "iteracoes": 20 + i,
             "nota_ajuste": 0.6 - i / 100,
             "ajuste": {"media": 0.6 - i / 100, "min": 0.6 - i / 100, "max": 0.6 - i / 100,
                        "desvio": 0.0, "por_caverna": {"c": 0.6 - i / 100}},
             "nota_reservada_media": 0.62,
             "reservadas": reservadas(pior=nota_min if i == 4 else 0.5)} for i in range(1, 6)]

ATIVAR_ANSI = "cavegen.generators.cellular_automata.genetico.painel._ativar_ansi"

class EstiloTests(unittest.TestCase):
    def test_fora_do_terminal_sai_texto_puro(self):
        saida = io.StringIO()
        painel = Painel(40, saida=saida)
        evoluir(GENES, sintetica, ConfiguracaoGA(orcamento=40), seed=3, observar=painel)
        painel.etapa(3, 4, "Conferindo", "🔍")
        painel.conferido(1, 1, {"x": 0.5, "n": 3}, 0.6, reservadas(0.61, NOTA_MINIMA))
        painel.tabela_melhores(melhores_falsos(), ["x", "n"], ["c"], 5, 10)
        painel.referencias({"c": 1.0}, "results/ga_001.npz")
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
                melhores_falsos(NOTA_MINIMA), ["x", "n"], ["c"], 5, 10)
            linhas = [re.sub(r"\033\[[0-9;]*m", "", linha)
                      for linha in saida.getvalue().splitlines()[3:]]
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
        Painel(10, saida=saida).conferido(1, 2, {"x": 0.5}, 0.6,
                                          reservadas(NOTA_MINIMA, NOTA_MINIMA))
        self.assertIn("frágil", saida.getvalue())

    def test_conferido_mostra_cada_caverna_so_quando_ha_varias(self):
        uma, varias = io.StringIO(), io.StringIO()
        Painel(10, saida=uma).conferido(1, 1, {"x": 0.5}, 0.6, reservadas(0.62, 0.4))
        Painel(10, saida=varias).conferido(
            1, 1, {"x": 0.5}, 0.6, reservadas(0.55, 0.3, {"a": 0.5, "b": 0.6}))
        self.assertEqual(uma.getvalue().strip(),
                         "1/1 x=0.5: ajuste +0.600, reservadas +0.620, pior seed +0.400")
        self.assertIn("reservadas +0.550 (a +0.500, b +0.600), pior seed +0.300",
                      varias.getvalue())
        self.assertNotIn("frágil", uma.getvalue() + varias.getvalue())

    def test_referencia_e_so_a_copia_pura(self):
        saida = io.StringIO()
        Painel(10, saida=saida).referencias({"a": 1.0, "b": 1.0}, "results/ga_001.npz")
        texto = saida.getvalue()
        self.assertIn("referência: cópia pura (peso > 0 vira vazio, sem rodar o CA): "
                      "a +1.000, b +1.000", texto)
        self.assertNotIn("teto", texto)

    def test_caverna_fora_do_protocolo_ganha_aviso(self):
        saida = io.StringIO()
        painel = Painel(10, saida=saida)
        painel.caverna("e", "e.npz", (64, 64, 64), -4.16, 1.1, 292, (146.0, 1460.0), 1.0)
        painel.caverna("p", "p.npz", (32, 32, 32), -3.0, 1.0, 40, (20.0, 200.0), 1.0,
                       aviso="grade 32³, fora do protocolo de 64³")
        linhas = saida.getvalue().splitlines()
        self.assertEqual(linhas[1].strip(), "grade 64x64x64, campo de -4.16 a +1.10, 292 voxels "
                         "positivos; vazio aceito de 146 a 1460")
        self.assertEqual(linhas[2].strip(), "cópia pura +1.000")
        self.assertEqual(len(linhas), 7)
        self.assertIn("fora do protocolo", linhas[6])

    def test_caverna_sem_limite_de_cima_e_com_a_grade_cheia(self):
        saida = io.StringIO()
        Painel(10, saida=saida).caverna("e", "e.npz", (64, 64, 64), -4.16, 1.1, 292,
                                        (146.0, math.inf), 1.0, cheia=-4033.246)
        linhas = saida.getvalue().splitlines()
        self.assertTrue(linhas[1].strip().endswith("292 voxels positivos; vazio aceito a partir "
                                                   "de 146"), linhas[1])
        self.assertEqual(linhas[2].strip(), "cópia pura +1.000, grade cheia -4033.246")
        self.assertEqual(descrever_vazio(146.0, None), "vazio aceito a partir de 146")
        self.assertEqual(descrever_vazio(146.0, 1460.0), "vazio aceito de 146 a 1460")

    def test_tabela_dos_melhores_alinha_com_notas_de_milhares(self):
        saida = io.StringIO()
        item = {"posicao": 1, "genes": {"g": 0.5}, "iteracoes": 1, "nota_ajuste": -4033.246,
                "nota_reservada_media": -4045.606,
                "ajuste": {"min": -4045.606, "max": -4020.886, "desvio": 12.36,
                           "por_caverna": {"a": -4045.606, "b": -4020.886}},
                "reservadas": {"pior_semente": -4045.606}}
        outro = {**item, "posicao": 2, "nota_ajuste": 0.5, "nota_reservada_media": 0.4,
                 "ajuste": {"min": 0.4, "max": 0.6, "desvio": 0.1,
                            "por_caverna": {"a": 0.4, "b": 0.6}},
                 "reservadas": {"pior_semente": 0.3}}
        Painel(10, saida=saida).tabela_melhores([item, outro], ["g"], ["a", "b"], 5, 10)
        linhas = saida.getvalue().splitlines()[-3:]
        # Cabeçalho e linhas com o mesmo comprimento: nenhuma coluna estourou.
        self.assertEqual(len({len(linha.rstrip()) for linha in linhas}), 1, linhas)

if __name__ == "__main__":
    unittest.main()
