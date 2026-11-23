"""Confere o pipeline do GA do CA: entrada, campos, busca, resultados e figuras.

    uv run python -m unittest tests/test_genetico_pipeline.py -v
"""
import contextlib
import copy
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import plotly.graph_objects as go

from cavegen.generators.cellular_automata.genetico import (
    busca,
    campos,
    figuras,
    pipeline,
    resultados,
)
from cavegen.tools.sdf.sdf import VERSAO_SDF


def casca(raio: float, lado: int = 16, espessura: float = 1.0) -> np.ndarray:
    """Grade de superfície de uma casca esférica: a inundação não entra, o miolo é interno."""
    z, y, x = np.indices((lado, lado, lado))
    centro = (lado - 1) / 2
    r = np.sqrt((z - centro) ** 2 + (y - centro) ** 2 + (x - centro) ** 2)
    return ((r >= raio) & (r < raio + espessura)).astype(np.uint8)

def gravar_grade(caminho: Path, raio: float) -> Path:
    metadata = json.dumps({"kind": "surface_voxels", "volume_shape_zyx": [16, 16, 16]})
    np.savez_compressed(caminho, surface_voxels=casca(raio), metadata=np.array(metadata))
    return caminho

def sha256(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()

class ComPastas(unittest.TestCase):
    """Uma entrada com duas cavernas (a e b) e pastas vazias de campos e resultados."""
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        raiz = Path(self._pasta.name)
        self.entrada, self.campos, self.saida = raiz / "1_entrada", raiz / "2_campos", raiz / "3"
        self.entrada.mkdir()
        self.grade_a = gravar_grade(self.entrada / "a_surface_64.npz", 6.0)
        self.grade_b = gravar_grade(self.entrada / "b_surface_64.npz", 6.5)

    def tearDown(self):
        self._pasta.cleanup()

    def preparar(self, nomes=None, forcar=False) -> list[str]:
        avisos = []
        campos.preparar(nomes, forcar, self.entrada, self.campos, avisos.append)
        return avisos

    def rodar_pipeline(self, *extra: str) -> Path:
        with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
              contextlib.redirect_stdout(io.StringIO())):
            return pipeline.main(["--orcamento", "20", "--populacao", "4", "--top", "4",
                                  "--entrada", str(self.entrada), "--campos", str(self.campos),
                                  "--saida", str(self.saida), *extra])

class CamposTests(ComPastas):
    def test_gera_o_que_falta_e_reaproveita_o_que_esta_em_dia(self):
        self.assertEqual(self.preparar(), ["  a: gerado (a_surface_64_sdf_log1.npz)",
                                           "  b: gerado (b_surface_64_sdf_log1.npz)"])
        antes = sha256(self.campos / "a_surface_64_sdf_log1.npz")
        self.assertTrue(all("reaproveitado" in aviso for aviso in self.preparar()))
        self.assertEqual(sha256(self.campos / "a_surface_64_sdf_log1.npz"), antes)

    def test_refaz_so_o_campo_da_grade_que_mudou(self):
        self.preparar()
        gravar_grade(self.grade_a, 3.5)
        avisos = self.preparar()
        self.assertEqual(avisos[0], "  a: refeito: a grade da entrada mudou "
                                    "(a_surface_64_sdf_log1.npz)")
        self.assertIn("reaproveitado", avisos[1])
        with np.load(self.campos / "a_surface_64_sdf_log1.npz") as campo:
            self.assertEqual(str(campo["sha256_entrada"]), sha256(self.grade_a))

    def test_versao_do_sdf_e_campo_errado_tambem_refazem(self):
        self.preparar()
        with mock.patch.object(campos, "VERSAO_SDF", VERSAO_SDF + 1):
            self.assertTrue(all("o cálculo do SDF mudou" in a for a in self.preparar()))
        # Um campo com limiar (o alvo antigo) no lugar do campo do GA.
        np.savez_compressed(self.campos / "b_surface_64_sdf_log1.npz", sdf=np.ones((16,) * 3),
                            limiar=-3.0, escala_log=1.0)
        self.assertIn("não é o campo do GA", self.preparar()[1])

    def test_forcar_refaz_todos(self):
        self.preparar()
        self.assertTrue(all("refeito: forçado" in a for a in self.preparar(forcar=True)))

    def test_campo_grava_de_onde_veio_e_e_o_sdf_com_log_1(self):
        self.preparar(["a"])
        self.assertFalse((self.campos / "b_surface_64_sdf_log1.npz").exists())
        with np.load(self.campos / "a_surface_64_sdf_log1.npz") as campo:
            self.assertEqual(float(campo["limiar"]), 0.0)
            self.assertEqual(float(campo["escala_log"]), 1.0)
            self.assertEqual(int(campo["versao"]), VERSAO_SDF)
            self.assertTrue(str(campo["entrada"]).endswith("a_surface_64.npz"))
            self.assertGreater(int((campo["sdf"] > 0).sum()), 0)

    def test_escolha_de_cavernas(self):
        disponiveis = campos.cavernas_da_entrada(self.entrada)
        self.assertEqual(list(disponiveis), ["a", "b"])
        self.assertEqual(list(campos.escolher(disponiveis)), ["a", "b"])
        self.assertEqual(list(campos.escolher(disponiveis, ["b"])), ["b"])
        with self.assertRaisesRegex(ValueError, "fora da entrada: c. Há: a, b"):
            campos.escolher(disponiveis, ["c"])
        with self.assertRaisesRegex(ValueError, "nenhuma caverna"):
            campos.escolher({})

class BuscaSozinhaTests(ComPastas):
    def rodar_busca(self, *extra):
        erro = io.StringIO()
        with (contextlib.redirect_stderr(erro), contextlib.redirect_stdout(io.StringIO()),
              mock.patch("cavegen.profiling.resource_tracker.registrar_execucao")):
            try:
                return busca.main(["--orcamento", "6", "--populacao", "3", "--top", "1",
                                   "--entrada", str(self.entrada), "--campos", str(self.campos),
                                   "--saida", str(self.saida), *extra])
            except SystemExit:
                return erro.getvalue()

    def test_recusa_campo_que_falta_ou_desatualizado(self):
        mensagem = self.rodar_busca()
        self.assertIn("O campo de a não está em dia (falta)", mensagem)
        self.assertIn("genetico.campos", mensagem)
        self.preparar()
        gravar_grade(self.grade_b, 3.5)
        self.assertIn("O campo de b não está em dia (a grade da entrada mudou)",
                      self.rodar_busca())

    def test_roda_nos_campos_em_dia_e_escolhe_cavernas(self):
        self.preparar()
        with np.load(self.rodar_busca("--cavernas", "b")) as r:
            self.assertEqual([c["nome"] for c in json.loads(str(r["cavernas"]))], ["b"])
        self.assertIn("fora da entrada: c", self.rodar_busca("--cavernas", "c"))

class PipelineTests(ComPastas):
    def test_fluxo_inteiro_grava_npz_lista_e_relatorio_de_todas_as_cavernas(self):
        destino = self.rodar_pipeline()
        self.assertEqual(destino, self.saida / "ga_001.npz")
        for sufixo in ("_melhores.md", "_relatorio.html"):
            self.assertTrue((self.saida / f"ga_001{sufixo}").exists(), sufixo)
        execucao = resultados.ler_execucao(destino)
        cavernas = {c["nome"]: c for c in execucao["cavernas"]}
        self.assertEqual(list(cavernas), ["a", "b"])  # padrão: todas as da entrada
        for nome, grade in (("a", self.grade_a), ("b", self.grade_b)):
            campo = self.campos / f"{nome}_surface_64_sdf_log1.npz"
            # Rastreabilidade: de qual grade, de qual campo e de qual versão.
            self.assertEqual(cavernas[nome]["sha256_entrada"], sha256(grade))
            self.assertEqual(cavernas[nome]["sha256"], sha256(campo))
            self.assertEqual(cavernas[nome]["versao_sdf"], VERSAO_SDF)
            self.assertTrue(cavernas[nome]["entrada"].endswith(grade.name))
        self.assertGreater(len(execucao["melhores"]), 0)  # o resto dos testes depende disso

    def test_segunda_execucao_reaproveita_os_campos_e_escolhe_cavernas(self):
        self.rodar_pipeline()
        antes = {p.name: sha256(p) for p in self.campos.glob("*.npz")}
        destino = self.rodar_pipeline("--cavernas", "b")
        self.assertEqual(destino.name, "ga_002.npz")
        self.assertEqual({p.name: sha256(p) for p in self.campos.glob("*.npz")}, antes)
        self.assertEqual(resultados.nomes_das_cavernas(resultados.ler_execucao(destino)), ["b"])

    def test_nota_por_passo_fica_gravada_para_a_trajetoria(self):
        execucao = resultados.ler_execucao(self.rodar_pipeline())
        item = execucao["melhores"][0]
        detalhes = execucao["detalhes"][item["ordem"]]
        for nome in ("a", "b"):
            passos = detalhes["cavernas"][nome]["notas_por_passo"]
            self.assertEqual(len(passos), execucao["max_iteracoes"])
            self.assertAlmostEqual(passos[item["iteracoes"] - 1],
                                   item["ajuste"]["por_caverna"][nome])

class ResultadosTests(ComPastas):
    def setUp(self):
        super().setUp()
        self.destino = self.rodar_pipeline()
        self.execucao = resultados.ler_execucao(self.destino)

    def test_tabela_dos_melhores_tem_o_que_foi_pedido(self):
        colunas, linhas = resultados.tabela_dos_melhores(self.execucao)
        self.assertEqual(colunas, ["#", "chance_inicial", "sensibilidade", "iterações",
                                   "nota média", "a", "b", "mín", "desvio", "reservadas",
                                   "pior seed"])
        self.assertEqual(len(linhas), len(self.execucao["melhores"]))
        for linha, item in zip(linhas, self.execucao["melhores"], strict=True):
            self.assertEqual(linha[0], item["posicao"])
            self.assertEqual(linha[4], item["nota_ajuste"])
            self.assertEqual(linha[5:7], [item["ajuste"]["por_caverna"][n] for n in "ab"])
            self.assertEqual(linha[-2], item["nota_reservada_media"])

    def test_markdown_abre_sem_codigo(self):
        texto = (self.saida / "ga_001_melhores.md").read_text(encoding="utf-8")
        self.assertTrue(texto.startswith(f"# ga_001: os {len(self.execucao['melhores'])} "
                                         "melhores"))
        linhas = [linha for linha in texto.splitlines() if linha.startswith("| ")]
        self.assertEqual(len(linhas), 1 + len(self.execucao["melhores"]))  # cabeçalho + uma por
        self.assertIn("| # | chance_inicial | sensibilidade | iterações | nota média | a | b |",
                      linhas[0])
        primeiro = self.execucao["melhores"][0]
        self.assertIn(f"| 1 | {primeiro['genes']['chance_inicial']:.4g} | "
                      f"{primeiro['genes']['sensibilidade']} | {primeiro['iteracoes']} | "
                      f"{primeiro['nota_ajuste']:+.3f} |", linhas[1])
        self.assertIn("ordem: média das notas entre as cavernas", texto)
        self.assertIn("menu-ca", texto)
        # Sem limite de cima e com a régua das notas negativas.
        self.assertIn("vazio aceito a partir de", texto)
        self.assertIn("grade cheia a ", texto)
        self.assertIn(resultados.escala_das_notas(self.execucao), texto)
        self.assertIn("o valor de cada caverna está no cabeçalho", texto)
        self.assertIn("`cortado` quer dizer vazio abaixo do mínimo aceito", texto)

    def test_resumo_pela_linha_de_comando_sem_escrever_codigo(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            resultados.main(["--pasta", str(self.saida)])  # sem nome: a última execução
        texto = saida.getvalue()
        self.assertIn("ga_001", texto)
        self.assertIn("melhores parâmetros, ordenados pela média entre as 2 cavernas", texto)
        self.assertIn("ga_001_relatorio.html", texto)

    def test_localizar_execucao(self):
        self.assertEqual(resultados.localizar(None, self.saida), self.destino)
        self.assertEqual(resultados.localizar("1", self.saida), self.destino)
        self.assertEqual(resultados.localizar("ga_001", self.saida), self.destino)
        self.assertEqual(resultados.localizar(str(self.destino), self.saida), self.destino)
        with self.assertRaises(FileNotFoundError):
            resultados.localizar(None, self.entrada)

    def test_formato_antigo_e_recusado_com_motivo(self):
        antigo = self.saida / "ga_009.npz"
        np.savez_compressed(antigo, metodo="genetico", notas=np.zeros(3),
                            alvo=np.array(json.dumps({"limiar": -3.0})))
        with self.assertRaisesRegex(ValueError, "antes de 22/11/2026"):
            resultados.ler_execucao(antigo)

class FigurasTests(ComPastas):
    def setUp(self):
        super().setUp()
        self.execucao = resultados.ler_execucao(self.rodar_pipeline())

    def test_todas_as_figuras_saem_do_npz(self):
        lista = figuras.figuras_da_execucao(self.execucao)
        self.assertEqual([titulo for titulo, _, _ in lista],
                         ["Melhor nota ao longo das avaliações", "Mapa das notas pelos dois genes",
                          "Nota de cada caverna nos melhores", "Notas por geração",
                          "O campeão ao longo das iterações do CA", "Ajuste × seeds reservadas"])
        for titulo, legenda, figura in lista:
            self.assertIsInstance(figura, go.Figure, titulo)
            self.assertTrue(legenda)
            self.assertEqual(figura.layout.paper_bgcolor, "black")  # o estilo do projeto
            figura.to_json()  # serializa (nada de NaN/inf que o plotly não aceite)

    def test_mapa_mostra_os_cortados_e_o_campeao(self):
        figura = figuras.figura_mapa_dos_genes(self.execucao)
        nomes = [trace.name for trace in figura.data]
        self.assertEqual(nomes, ["avaliado", "cortado (vazio fora da faixa aceita)", "campeão"])
        unicos = {tuple(g) for g in self.execucao["genes"].tolist()}
        cortados = len(figura.data[1].x)
        avaliados = int(np.isfinite(np.asarray(figura.data[0].z, dtype=float)).sum())
        self.assertEqual(cortados + avaliados, len(unicos))

    def test_notas_por_caverna_tem_uma_barra_por_caverna_e_a_media(self):
        figura = figuras.figura_notas_por_caverna(self.execucao)
        self.assertEqual([t.name for t in figura.data][:2], ["a", "b"])
        # O y é a nota comprimida (log simétrico); a nota de verdade vai no hover.
        medias = [m["nota_ajuste"] for m in self.execucao["melhores"]]
        self.assertEqual(list(figura.data[2].y), [figuras.comprimir(n) for n in medias])
        self.assertEqual([c[0] for c in figura.data[2].customdata], medias)

    def test_trajetoria_tem_nota_e_vazio_por_passo(self):
        figura = figuras.figura_trajetoria(self.execucao)
        nomes = {t.name for t in figura.data}
        self.assertTrue({"nota em a", "nota em b", "média entre as cavernas"} <= nomes, nomes)
        self.assertEqual(figura.layout.yaxis2.type, "log")

    def test_relatorio_html_tem_tabela_e_figuras_e_carrega_o_plotly_uma_vez(self):
        destino = figuras.gravar_relatorio(self.execucao, [self.execucao])
        texto = destino.read_text(encoding="utf-8")
        self.assertEqual(texto.count('class="plotly-graph-div"'), 6)
        self.assertEqual(texto.count("cdn.plot.ly"), 1)
        self.assertIn("<table>", texto)
        # Com --comparar, a curva da outra execução entra na primeira figura.
        self.assertEqual(len(figuras.figura_melhor_acumulado([self.execucao] * 2).data), 2)

    def test_nota_extrema_nao_achata_as_outras(self):
        # Um dos melhores enche a grade (-4000): as outras notas continuam
        # separadas no eixo, e nada vai para fora da faixa do eixo.
        execucao = copy.deepcopy(self.execucao)
        execucao["melhores"][-1]["ajuste"]["por_caverna"]["a"] = -4000.0
        execucao["melhores"][-1]["nota_ajuste"] = -2000.0
        execucao["melhor_acumulado"][0] = -4000.0
        figura = figuras.figura_notas_por_caverna(execucao)
        baixo, alto = figura.layout.yaxis.range
        self.assertLessEqual(baixo, figuras.comprimir(-4000.0))
        self.assertGreaterEqual(alto, figuras.comprimir(1.0))
        # 0,2 e 0,3 ficam a mais de 2% do eixo um do outro (num eixo linear até
        # -4000, seriam 0,0025%).
        distancia = figuras.comprimir(0.3) - figuras.comprimir(0.2)
        self.assertGreater(distancia / (alto - baixo), 0.02)
        rotulos = list(figura.layout.yaxis.ticktext)
        self.assertEqual(rotulos[-1], "+1")
        self.assertIn("0", rotulos)
        self.assertIn("-1000", rotulos)
        curva = figuras.figura_melhor_acumulado([execucao])
        self.assertLessEqual(curva.layout.yaxis.range[0], figuras.comprimir(-4000.0))
        self.assertEqual(curva.data[0].customdata[0], -4000.0)  # o hover, de verdade

    def test_cor_do_mapa_e_fixa_e_tem_o_zero_no_meio_da_paleta(self):
        figura = figuras.figura_mapa_dos_genes(self.execucao)
        mapa = figura.data[0]
        self.assertEqual((mapa.zmin, mapa.zmax), (figuras.comprimir(figuras.NOTA_MIN_COR),
                                                  figuras.comprimir(figuras.NOTA_MAX_COR)))
        escala = figuras.escala_de_cor_das_notas()
        zero = -mapa.zmin / (mapa.zmax - mapa.zmin)
        meio = [cor for posicao, cor in escala if math.isclose(posicao, zero)]
        paleta = figuras.sample_colorscale(figuras.get_colorscale(figuras.PALETA_NOTA), [0.5])
        self.assertEqual(meio, paleta)
        # O hover mostra a nota de verdade, não a comprimida.
        reais = np.asarray(mapa.customdata, dtype=float)[..., 0]
        z = np.asarray(mapa.z, dtype=float)
        avaliadas = np.isfinite(z)
        np.testing.assert_allclose(z[avaliadas],
                                   [figuras.comprimir(n) for n in reais[avaliadas]])

    def test_relatorio_explica_a_escala(self):
        texto = figuras.pagina(self.execucao)
        self.assertIn("log simétrica", texto)
        self.assertIn("grade cheia", texto)

    def test_execucao_toda_cortada_ainda_gera_relatorio(self):
        cortada = dict(self.execucao, melhores=[],
                       notas=np.full(len(self.execucao["notas"]), -np.inf),
                       melhor_acumulado=np.full(len(self.execucao["notas"]), -np.inf))
        lista = figuras.figuras_da_execucao(cortada)
        self.assertEqual(len(lista), 4)  # sem os gráficos dos melhores
        for _, _, figura in lista:
            figura.to_json()
        self.assertIn("Nenhum", resultados.markdown_dos_melhores(cortada))

class EscalaDasNotasTests(unittest.TestCase):
    def test_comprimir_mantem_ordem_sinal_e_o_zero(self):
        notas = [-4045.6, -540.9, -8.6, -1.0, -0.07, 0.0, 0.03, 0.3, 1.0]
        comprimidas = [figuras.comprimir(n) for n in notas]
        self.assertEqual(comprimidas, sorted(comprimidas))
        self.assertEqual(figuras.comprimir(0.0), 0.0)
        for nota in notas:
            self.assertEqual(figuras.comprimir(-nota), -figuras.comprimir(nota))
        # Perto do zero é quase linear: 0,01 vira ~0,041 (= 0,01 / (0,1 ln 10)).
        self.assertAlmostEqual(figuras.comprimir(0.01) / 0.01, 1 / (0.1 * math.log(10)),
                               delta=0.3)
        # Longe, cada década ocupa o mesmo espaço.
        self.assertAlmostEqual(figuras.comprimir(-1000) - figuras.comprimir(-100), -1, delta=0.01)
        self.assertIsNone(figuras.comprimir(-math.inf))
        self.assertIsNone(figuras.comprimir(math.nan))
        self.assertIsNone(figuras.comprimir(None))

    def test_eixo_de_notas_vai_do_menor_ao_1_e_marca_com_a_nota_real(self):
        eixo = figuras.eixo_de_notas([-540.9, -0.07, None, -math.inf])
        self.assertEqual(eixo["ticktext"], ["-100", "-10", "-1", "-0.1", "0", "+0.1", "+0.5",
                                            "+1"])
        self.assertEqual(eixo["tickvals"], [figuras.comprimir(float(m.replace("+", "")))
                                            for m in eixo["ticktext"]])
        self.assertLess(eixo["range"][0], figuras.comprimir(-540.9))
        self.assertGreater(eixo["range"][1], figuras.comprimir(1.0))
        # Sem nenhuma nota finita, o eixo ainda abre de 0 a 1.
        self.assertEqual(figuras.eixo_de_notas([None])["ticktext"], ["0", "+0.1", "+0.5", "+1"])

class ErrosEAvisosTests(ComPastas):
    def test_grade_sem_surface_voxels_falha_dizendo_qual_caverna(self):
        np.savez_compressed(self.entrada / "c_surface_64.npz", sdf=np.ones((16,) * 3))
        with self.assertRaisesRegex(ValueError, "caverna c .*falta metadata, surface_voxels"):
            self.preparar(["c"])

    def test_forcar_com_campo_que_falta_diz_gerado(self):
        self.assertEqual(self.preparar(["a"], forcar=True),
                         ["  a: gerado (a_surface_64_sdf_log1.npz)"])

    def test_resultado_diz_se_o_campo_foi_conferido_com_a_entrada(self):
        destino = self.rodar_pipeline()
        execucao = resultados.ler_execucao(destino)
        self.assertTrue(all(c["conferido_com_entrada"] for c in execucao["cavernas"]))
        campo = self.campos / "a_surface_64_sdf_log1.npz"
        with (mock.patch("cavegen.profiling.resource_tracker.registrar_execucao"),
              contextlib.redirect_stdout(io.StringIO())):
            direto = busca.main(["--cavernas", str(campo), "--orcamento", "3", "--populacao", "3",
                                 "--top", "1", "--saida", str(self.saida)])
        cavernas = resultados.ler_execucao(direto)["cavernas"]
        self.assertEqual([c["conferido_com_entrada"] for c in cavernas], [False])
        # O nome com .npz, sem pasta, é procurado em --pasta.
        self.assertEqual(resultados.localizar("ga_001.npz", self.saida), destino)

    def test_comparar_avisa_quando_as_execucoes_nao_sao_comparaveis(self):
        execucao = resultados.ler_execucao(self.rodar_pipeline())
        self.assertEqual(resultados.avisos_de_comparacao(execucao, [execucao]), [])
        outra = dict(execucao, nome="ga_009", config={**execucao["config"], "orcamento": 400},
                     cavernas=execucao["cavernas"][:1])
        avisos = resultados.avisos_de_comparacao(execucao, [outra])
        self.assertEqual(avisos, ["ga_009 não é comparável com ga_001: difere em cavernas ou "
                                  "campos, orçamento."])
        self.assertIn("Aviso:", figuras.pagina(execucao, [outra]))

if __name__ == "__main__":
    unittest.main()
