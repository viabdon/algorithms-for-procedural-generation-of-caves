"""Testes adversariais do revisor para o pipeline do GA do CA (22/11/2026).

Cobrem a mudança de lugar (tools/ e optimization/ para dentro do pacote), a
staleness dos campos, a escolha das cavernas, a rastreabilidade do resultado,
a reprodutibilidade e os relatórios. Tudo em pastas temporárias e grades 16³.

    uv run python -m unittest tests/test_genetico_pipeline_revisor.py -v
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from cavegen.generators.cellular_automata.genetico import (
    busca,
    campos,
    figuras,
    pipeline,
    resultados,
)
from cavegen.generators.cellular_automata.genetico.aptidao import Cortes
from cavegen.tools.sdf import sdf as ferramenta_sdf
from cavegen.tools.sdf.sdf import VERSAO_SDF

RASTREADOR = "cavegen.profiling.resource_tracker.registrar_execucao"


def casca(raio: float, lado: int = 16, espessura: float = 1.0) -> np.ndarray:
    """Grade de superfície de uma casca esférica (a mesma do test_genetico_pipeline)."""
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


def sem_constantes(texto: str):
    """json.loads que recusa NaN/Infinity: o JSON que o navegador aceita."""
    def recusar(constante):
        raise ValueError(f"constante fora do JSON: {constante}")
    return json.loads(texto, parse_constant=recusar)


class ComPastasRevisor(unittest.TestCase):
    """Entrada com duas cavernas (a e b), pastas de campos e de resultados vazias."""
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self.raiz = Path(self._pasta.name)
        self.entrada, self.campos, self.saida = (self.raiz / "1_entrada", self.raiz / "2_campos",
                                                 self.raiz / "3")
        self.entrada.mkdir()
        self.grade_a = gravar_grade(self.entrada / "a_surface_64.npz", 6.0)
        self.grade_b = gravar_grade(self.entrada / "b_surface_64.npz", 6.5)
        self.campo_a = self.campos / "a_surface_64_sdf_log2.npz"
        self.campo_b = self.campos / "b_surface_64_sdf_log2.npz"

    def tearDown(self):
        self._pasta.cleanup()

    def preparar(self, nomes=None, forcar=False) -> list[str]:
        avisos = []
        campos.preparar(nomes, forcar, self.entrada, self.campos, avisos.append)
        return avisos

    def busca(self, *argv: str, entrada: Path | None = None):
        """(destino, None) se rodou; (None, mensagem) se o parser recusou."""
        erro = io.StringIO()
        with (mock.patch(RASTREADOR), contextlib.redirect_stdout(io.StringIO()),
              contextlib.redirect_stderr(erro)):
            try:
                destino = busca.main(["--orcamento", "6", "--populacao", "3", "--top", "2",
                                      "--entrada", str(entrada or self.entrada),
                                      "--campos", str(self.campos), "--saida", str(self.saida),
                                      *argv])
            except SystemExit as saida:
                if saida.code != 2:
                    raise
                return None, erro.getvalue()
        return destino, None

    def pipeline(self, *argv: str, saida: Path | None = None) -> Path:
        with mock.patch(RASTREADOR), contextlib.redirect_stdout(io.StringIO()):
            return pipeline.main(["--orcamento", "8", "--populacao", "4", "--top", "3",
                                  "--seed", "3", "--entrada", str(self.entrada),
                                  "--campos", str(self.campos),
                                  "--saida", str(saida or self.saida), *argv])


class CaminhosDepoisDaMudancaRevisorTests(unittest.TestCase):
    def test_raiz_do_projeto_e_a_mesma_no_ca_e_nas_ferramentas(self):
        from cavegen.generators.cellular_automata import pesos
        from cavegen.tools.flood_fill import inundacao
        from cavegen.tools.random_walk_points import results

        self.assertEqual(inundacao.RAIZ_DO_PROJETO, pesos.RAIZ_DO_PROJETO)
        self.assertTrue((pesos.RAIZ_DO_PROJETO / "pyproject.toml").is_file())
        self.assertFalse((pesos.RAIZ_DO_PROJETO / "tools").exists(), "tools/ da raiz voltou")
        # O peso padrão do CA aponta para a pasta npz da ferramenta do SDF, que mudou.
        self.assertEqual(pesos.SDF_ELAPHES, ferramenta_sdf.PASTA_NPZ / "elaphes_surface_64_sdf.npz")
        self.assertEqual(inundacao.SUPERFICIE_ELAPHES, pesos.RAIZ_DO_PROJETO / "data" / "processed"
                         / "references" / "elaphes_surface_64.npz")
        # npz e plots continuam dentro da pasta de cada ferramenta.
        for modulo, pastas in ((ferramenta_sdf, ("PASTA_NPZ", "PASTA_PLOTS")),
                               (inundacao, ("PASTA_NPZ", "PASTA_PLOTS")),
                               (results, ("RESULTS_DIR",))):
            for nome in pastas:
                self.assertEqual(getattr(modulo, nome).parent, Path(modulo.__file__).parent, nome)

    def test_pacote_optimization_sumiu(self):
        self.assertIsNone(importlib.util.find_spec("cavegen.optimization"))

    def test_modulos_rodam_com_dash_m_fora_da_raiz(self):
        with tempfile.TemporaryDirectory() as fora:
            for modulo in ("cavegen.generators.cellular_automata.genetico.pipeline",
                           "cavegen.generators.cellular_automata.genetico.busca",
                           "cavegen.tools.sdf.sdf"):
                with self.subTest(modulo=modulo):
                    feito = subprocess.run([sys.executable, "-m", modulo, "--help"], cwd=fora,
                                           capture_output=True, text=True, encoding="utf-8", check=False,
                                           errors="replace", timeout=120)
                    self.assertEqual(feito.returncode, 0, feito.stderr)
                    self.assertIn("usage", feito.stdout)


class StalenessRevisorTests(ComPastasRevisor):
    def test_campo_em_dia_nao_e_reescrito(self):
        self.preparar()
        antes = self.campo_a.stat().st_mtime_ns, self.campo_b.stat().st_mtime_ns
        self.assertTrue(all("reaproveitado" in a for a in self.preparar()))
        self.assertEqual((self.campo_a.stat().st_mtime_ns, self.campo_b.stat().st_mtime_ns), antes)

    def test_campo_antigo_sem_sha256_da_grade_e_refeito(self):
        # O formato de antes de 22/11/2026: o campo certo (log 1, sem limiar), mas
        # sem dizer de que grade e de que versão veio.
        self.preparar(["a"])
        with np.load(self.campo_a) as campo:
            antigo = {k: campo[k] for k in campo.files
                      if k not in ("entrada", "sha256_entrada", "versao")}
        np.savez_compressed(self.campo_a, **antigo)
        avisos = self.preparar(["a"])
        self.assertEqual(avisos, [("  a: refeito: não diz de que grade e de que versão veio "
                                   "(a_surface_64_sdf_log2.npz)")])
        with np.load(self.campo_a) as campo:
            self.assertEqual(str(campo["sha256_entrada"]), sha256(self.grade_a))

    def test_forcar_com_subconjunto_so_refaz_o_escolhido(self):
        self.preparar()
        antes_b = self.campo_b.stat().st_mtime_ns, sha256(self.campo_b)
        avisos = self.preparar(["a"], forcar=True)
        self.assertEqual(avisos, ["  a: refeito: forçado (a_surface_64_sdf_log2.npz)"])
        self.assertEqual((self.campo_b.stat().st_mtime_ns, sha256(self.campo_b)), antes_b)

    def test_grade_trocada_pela_de_outra_caverna_com_o_mesmo_nome(self):
        self.preparar()
        shutil.copyfile(self.grade_b, self.grade_a)  # outra caverna com o nome de a
        avisos = self.preparar()
        self.assertIn("a grade da entrada mudou", avisos[0])
        self.assertIn("reaproveitado", avisos[1])
        # Agora a e b são a mesma grade, então o campo de a ficou igual ao de b.
        with np.load(self.campo_a) as a, np.load(self.campo_b) as b:
            np.testing.assert_array_equal(a["sdf"], b["sdf"])

    def test_busca_sozinha_recusa_versao_antiga_do_sdf(self):
        self.preparar()
        with mock.patch.object(campos, "VERSAO_SDF", VERSAO_SDF + 1):
            destino, mensagem = self.busca("--cavernas", "a")
        self.assertIsNone(destino)
        self.assertIn("O campo de a não está em dia (o cálculo do SDF mudou", mensagem)

    def test_duas_grades_com_o_mesmo_nome_viram_erro_do_parser(self):
        gravar_grade(self.entrada / "a.npz", 6.0)
        destino, mensagem = self.busca()
        self.assertIsNone(destino)
        self.assertIn("Duas grades viram a caverna a", mensagem)
        with self.assertRaises(SystemExit) as saida, contextlib.redirect_stderr(io.StringIO()):
            self.pipeline()
        self.assertEqual(saida.exception.code, 2)


class EscolhaDasCavernasRevisorTests(ComPastasRevisor):
    def test_sem_pedido_usa_todas_em_ordem_alfabetica(self):
        self.preparar()
        self.assertEqual(busca.resolver_cavernas(None, self.entrada, self.campos),
                         [self.campo_a, self.campo_b])

    def test_entrada_vazia_ou_inexistente(self):
        vazia = self.raiz / "vazia"
        vazia.mkdir()
        for pasta in (vazia, self.raiz / "nao_existe"):
            with self.subTest(pasta=pasta.name):
                with self.assertRaisesRegex(ValueError, "nenhuma caverna"):
                    busca.resolver_cavernas(None, pasta, self.campos)
                destino, mensagem = self.busca(entrada=pasta)
                self.assertIsNone(destino)
                self.assertIn("nenhuma caverna", mensagem)

    def test_nome_repetido_e_nome_mais_o_caminho_do_mesmo_campo(self):
        self.preparar()
        for pedidas in (["a", "a"], ["a", str(self.campo_a)]):
            with self.subTest(pedidas=pedidas), self.assertRaisesRegex(ValueError, "repetida"):
                busca.resolver_cavernas(pedidas, self.entrada, self.campos)

    def test_grade_da_entrada_passada_como_campo_da_erro_claro(self):
        # Contrato (resolver_cavernas e carregar_caverna): erro diz qual caverna e o
        # que fazer. Com 1_entrada/ ao lado de 2_campos/, passar a grade no lugar
        # do campo é um engano provável; hoje sai um KeyError do numpy ('sdf is not
        # a file in the archive') em vez da mensagem do parser.
        try:
            destino, mensagem = self.busca("--cavernas", str(self.grade_a))
        except KeyError as erro:
            self.fail(f"traceback em vez de erro do parser: KeyError {erro}")
        self.assertIsNone(destino)
        self.assertIn("genetico.campos", mensagem)


class RastreabilidadeRevisorTests(ComPastasRevisor):
    def test_npz_direto_grava_grade_campo_e_versao_mesmo_sem_entrada(self):
        self.preparar(["a"])
        vazia = self.raiz / "vazia"
        vazia.mkdir()
        destino, mensagem = self.busca("--cavernas", str(self.campo_a), entrada=vazia)
        self.assertIsNone(mensagem)
        with np.load(destino) as r:
            (caverna,) = json.loads(str(r["cavernas"]))
        self.assertEqual(caverna["nome"], "a")
        self.assertEqual(caverna["sha256"], sha256(self.campo_a))
        self.assertEqual(caverna["sha256_entrada"], sha256(self.grade_a))
        self.assertEqual(caverna["versao_sdf"], VERSAO_SDF)
        self.assertTrue(caverna["entrada"].endswith("a_surface_64.npz"))
        self.assertTrue(caverna["origem"].endswith("a_surface_64_sdf_log2.npz"))

    def test_npz_direto_sem_metadados_grava_nulos_sem_quebrar(self):
        self.preparar(["a"])
        antigo = self.raiz / "antigo_sdf_log2.npz"
        with np.load(self.campo_a) as campo:
            np.savez_compressed(antigo, sdf=campo["sdf"], limiar=0.0, escala_log=2.0)
        destino, mensagem = self.busca("--cavernas", str(antigo))
        self.assertIsNone(mensagem)
        with np.load(destino) as r:
            (caverna,) = json.loads(str(r["cavernas"]))
        self.assertEqual(caverna["sha256"], sha256(antigo))
        self.assertIsNone(caverna["sha256_entrada"])
        self.assertIsNone(caverna["versao_sdf"])


class ReprodutibilidadeRevisorTests(ComPastasRevisor):
    def test_pipeline_em_duas_pastas_da_o_mesmo_resultado_bit_a_bit(self):
        primeira = self.pipeline()
        campos_1 = {p.name: sha256(p) for p in self.campos.glob("*.npz")}
        # Segunda rodada do zero: outra pasta de campos, mesmas grades.
        shutil.rmtree(self.campos)
        segunda = self.pipeline(saida=self.raiz / "4")
        self.assertEqual({p.name: sha256(p) for p in self.campos.glob("*.npz")}, campos_1)
        with np.load(primeira) as r1, np.load(segunda) as r2:
            for nome in ("genes", "notas", "iteracoes", "geracao", "melhor_acumulado"):
                np.testing.assert_array_equal(r1[nome], r2[nome], err_msg=nome)
            for nome in ("detalhes", "melhores", "campeao", "nota_copia_pura", "config"):
                self.assertEqual(str(r1[nome]), str(r2[nome]), nome)
            cavernas = [json.loads(str(r["cavernas"])) for r in (r1, r2)]
        self.assertEqual(*([[c["sha256"], c["sha256_entrada"], c["versao_sdf"]]
                            for c in lista] for lista in cavernas))


class RelatoriosRevisorTests(ComPastasRevisor):
    def setUp(self):
        super().setUp()
        self.destino = self.pipeline()
        self.execucao = resultados.ler_execucao(self.destino)
        self.assertTrue(self.execucao["melhores"])

    def test_tabela_do_markdown_e_do_html_tem_as_mesmas_celulas(self):
        markdown = (self.saida / "ga_001_melhores.md").read_text(encoding="utf-8")
        linhas_md = [[c.strip() for c in linha.strip("|").split("|")]
                     for linha in markdown.splitlines() if linha.startswith("| ")]
        pagina = (self.saida / "ga_001_relatorio.html").read_text(encoding="utf-8")
        tabela = re.search(r"<table>.*?</table>", pagina, re.DOTALL).group(0)
        cabecalho = re.findall(r"<th>(.*?)</th>", tabela)
        corpo = [re.findall(r"<td>(.*?)</td>", tr) for tr in re.findall(r"<tr>(.*?)</tr>",
                                                                          tabela)[1:]]
        self.assertEqual([cabecalho, *corpo], linhas_md)

    def test_figuras_serializam_em_json_estrito(self):
        for titulo, _, figura in figuras.figuras_da_execucao(self.execucao, [self.execucao]):
            with self.subTest(figura=titulo):
                sem_constantes(figura.to_json())

    def test_formato_sem_notas_por_passo_como_o_ga_011_gera_relatorio(self):
        with np.load(self.destino) as r:
            dados = {k: r[k] for k in r.files}
        detalhes = json.loads(str(dados["detalhes"]))
        for d in detalhes:
            for caverna in d["cavernas"].values():
                caverna.pop("notas_por_passo")
        dados["detalhes"] = np.array(json.dumps(detalhes))
        antiga = self.saida / "ga_011.npz"
        np.savez_compressed(antiga, **dados)
        with contextlib.redirect_stdout(io.StringIO()):
            markdown, pagina = resultados.gerar(antiga)
        self.assertTrue(markdown.exists() and pagina.exists())
        trajetoria = figuras.figura_trajetoria(resultados.ler_execucao(antiga))
        self.assertIn("não gravou a nota de cada passo", trajetoria.layout.title.text)
        sem_constantes(trajetoria.to_json())

    def test_formato_antigo_com_melhores_mas_sem_cavernas_e_recusado(self):
        # Os ga_005 a ga_010 já têm "melhores", mas o alvo único com limiar -3.
        antigo = self.saida / "ga_010.npz"
        np.savez_compressed(antigo, metodo="genetico", notas=np.zeros(3),
                            melhores=np.array("[]"), peso=np.array("{}"),
                            alvo=np.array(json.dumps({"limiar": -3.0})))
        with self.assertRaisesRegex(ValueError, "ga_010.npz é de antes de 22/11/2026"):
            resultados.ler_execucao(antigo)
        erro = io.StringIO()
        with (self.assertRaises(SystemExit) as saida, contextlib.redirect_stderr(erro),
              contextlib.redirect_stdout(io.StringIO())):
            resultados.main(["10", "--pasta", str(self.saida)])
        self.assertEqual(saida.exception.code, 2)
        self.assertIn("antes de 22/11/2026", erro.getvalue())
        self.assertFalse((self.saida / "ga_010_melhores.md").exists())


class ExecucaoTodaCortadaRevisorTests(ComPastasRevisor):
    def test_busca_toda_cortada_ainda_gera_markdown_e_html(self):
        self.preparar()
        # Faixa de vazio estreitíssima: nenhum candidato cabe nela.
        with mock.patch.object(busca, "Cortes", lambda: Cortes(0.999, 1.001)):
            destino, mensagem = self.busca()
        self.assertIsNone(mensagem)
        execucao = resultados.ler_execucao(destino)
        self.assertTrue(np.all(np.isneginf(execucao["notas"])))
        self.assertEqual(execucao["melhores"], [])
        with contextlib.redirect_stdout(io.StringIO()):
            markdown, pagina = resultados.gerar(destino)
        self.assertIn("Nenhum", markdown.read_text(encoding="utf-8"))
        self.assertIn("Nenhum", pagina.read_text(encoding="utf-8"))
        for titulo, _, figura in figuras.figuras_da_execucao(execucao):
            with self.subTest(figura=titulo):
                sem_constantes(figura.to_json())


if __name__ == "__main__":
    unittest.main()
