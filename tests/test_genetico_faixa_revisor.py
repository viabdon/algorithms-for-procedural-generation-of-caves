"""Testes do revisor para a faixa de vazio só com mínimo, a régua da grade cheia e a
escala log simétrica das figuras do GA do CA (22/11/2026).

Cobrem a nota da grade cheia e o piso, a faixa sem limite de cima, uma trajetória
que enche a grade aos poucos, a escala das figuras (ordem, marcas, faixa, cor,
barra de erro, JSON sem constantes), o painel (mediana e colunas) e a leitura das
execuções antigas, gravadas com o máximo. Grades 16³ e seeds fixas.

    uv run python -m unittest tests/test_genetico_faixa_revisor.py -v
"""
import contextlib
import copy
import io
import json
import math
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import plotly.graph_objects as go

from cavegen.core.seed import numpy_rng
from cavegen.generators.cellular_automata.genetico import figuras, pipeline, resultados
from cavegen.generators.cellular_automata.genetico.aptidao import (
    NOTA_MINIMA,
    Alvo,
    Cortes,
    nota_do_passo,
    situacao_do_vazio,
)
from cavegen.generators.cellular_automata.genetico.ca import AvaliadorCA, Caverna
from cavegen.generators.cellular_automata.genetico.painel import Estilo, Painel
from cavegen.sdf.manipulacao import comprimir_log

RASTREADOR = "cavegen.profiling.resource_tracker.registrar_execucao"


def esfera_sdf(lado: int = 16, raio: float = 5.0) -> np.ndarray:
    """SDF de uma bola no centro: positivo dentro, negativo fora (o mesmo do test_genetic)."""
    z, y, x = np.indices((lado, lado, lado))
    centro = (lado - 1) / 2
    return (raio - np.sqrt((z - centro) ** 2 + (y - centro) ** 2 + (x - centro) ** 2)).astype(
        np.float32)


def campo_esfera(raio: float = 5.0, lado: int = 16, escala: float = 2.0) -> np.ndarray:
    """O campo do GA (log x2); escala 1 para os testes que fixam a dinâmica medida com ela."""
    return comprimir_log(esfera_sdf(lado, raio), escala)


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


def sem_constantes(texto: str):
    """json.loads que recusa NaN/Infinity: o JSON que o navegador aceita."""
    def recusar(constante):
        raise ValueError(f"constante fora do JSON: {constante}")
    return json.loads(texto, parse_constant=recusar)


def campo_com_zeros() -> np.ndarray:
    """Campo não cúbico com positivos, negativos e zeros (a borda), sorteado com seed fixa."""
    return numpy_rng(7).integers(-4, 3, size=(5, 6, 7)).astype(np.float32)


class GradeCheiaEPisoTests(unittest.TestCase):
    def setUp(self):
        self.campo = campo_com_zeros()
        self.alvo = Alvo(self.campo)
        self.assertTrue(np.any(self.campo == 0))  # o caso que importa: há borda

    def test_grade_cheia_e_a_nota_de_tudo_vazio(self):
        cheia = np.ones(self.campo.shape, dtype=bool)
        self.assertEqual(self.alvo.nota_da_grade_cheia(), self.alvo.nota(cheia))

    def test_piso_fica_exatamente_1_abaixo_da_grade_cheia(self):
        # Vazio só no lado negativo; os zeros da borda não mudam nada.
        piso = self.alvo.nota(self.campo < 0)
        self.assertAlmostEqual(piso, self.alvo.nota_da_grade_cheia() - 1, places=12)
        self.assertEqual(self.alvo.nota(self.campo <= 0), piso)

    def test_nenhuma_caverna_fica_abaixo_do_piso_nem_acima_de_1(self):
        piso = self.alvo.nota(self.campo < 0)
        rng = numpy_rng(11)
        for _ in range(300):
            vazio = rng.random(self.campo.shape) < rng.random()
            nota = self.alvo.nota(vazio)
            self.assertGreaterEqual(nota, piso - 1e-12)
            self.assertLessEqual(nota, 1 + 1e-12)

    def test_piso_tem_vazio_bastante_para_passar_pelo_minimo(self):
        # O piso é atingível: o vazio dele passa do mínimo, então não vira -inf.
        piso = self.alvo.nota(self.campo < 0)
        self.assertEqual(nota_do_passo(self.campo < 0, self.alvo, Cortes()), piso)

    def test_grade_cheia_nao_muda_com_a_escala_do_campo(self):
        self.assertAlmostEqual(Alvo(self.campo * 7).nota_da_grade_cheia(),
                               self.alvo.nota_da_grade_cheia(), places=9)


class FaixaSemMaximoTests(unittest.TestCase):
    def setUp(self):
        self.alvo = Alvo(campo_esfera(5.0))
        self.total = int(np.prod(self.alvo.shape))

    def test_sem_maximo_nada_e_vazio_demais(self):
        minimo, maximo = self.alvo.faixa(Cortes())
        self.assertTrue(math.isinf(maximo) and maximo > 0)
        self.assertEqual(situacao_do_vazio(self.total, self.alvo, Cortes()), "na_faixa")
        self.assertTrue(self.alvo.dentro_da_faixa(self.total, Cortes()))
        self.assertEqual(situacao_do_vazio(math.ceil(minimo) - 1, self.alvo, Cortes()),
                         "vazio_de_menos")
        self.assertEqual(situacao_do_vazio(math.ceil(minimo), self.alvo, Cortes()), "na_faixa")

    def test_maximo_explicito_continua_inclusivo(self):
        cortes = Cortes(0.5, 5.0)
        _, maximo = self.alvo.faixa(cortes)
        self.assertEqual(situacao_do_vazio(int(maximo), self.alvo, cortes), "na_faixa")
        self.assertEqual(situacao_do_vazio(int(maximo) + 1, self.alvo, cortes), "vazio_demais")

    def test_fator_maximo_invalido_e_recusado(self):
        for fator in (1.0, 0.9, 0.0, -2.0):
            with self.subTest(fator=fator), self.assertRaises(ValueError):
                Cortes(0.5, fator)
        self.assertIsNone(Cortes(0.5, None).fator_maximo)


# Na esfera de raio 5 (16³) com log x1, a grade enche aos poucos: cheia no passo 4,
# não no 1. O comportamento fixado vale para qualquer escala; o log x1 só dá o exemplo.
ENCHE_AOS_POUCOS = {"chance_inicial": 0.2, "sensibilidade": 3}


class TrajetoriaQueEncheTests(unittest.TestCase):
    """
        Característica do contrato, não bug: sem o máximo, quem enche a grade aos
        poucos é avaliado pelo passo menos cheio (a melhor iteração), não pela
        nota da grade cheia. Este teste fixa esse comportamento para o relatório.
    """
    def setUp(self):
        self.caverna = Caverna("a", campo_esfera(5.0, escala=1.0))
        self.cheia = self.caverna.alvo.nota_da_grade_cheia()

    def test_quem_enche_aos_poucos_leva_a_nota_do_primeiro_passo(self):
        avaliador = AvaliadorCA([self.caverna], (1, 2, 3), max_iteracoes=20)
        nota, detalhes = avaliador(ENCHE_AOS_POUCOS)
        trajetorias = avaliador.trajetorias(ENCHE_AOS_POUCOS)["a"]
        for t in trajetorias:
            self.assertEqual(t.vazios[-1], self.caverna.peso.size)  # a grade termina cheia
            self.assertEqual(t.notas[-1], self.cheia)
            self.assertLess(t.vazios[0], self.caverna.peso.size)  # mas não no passo 1
        self.assertEqual(detalhes["iteracoes"], 1)
        self.assertTrue(math.isfinite(nota))
        self.assertGreater(nota, self.cheia + 1)  # bem acima da grade cheia
        # Com o máximo de antes, o mesmo candidato era cortado em todo passo.
        com_teto = AvaliadorCA([self.caverna], (1, 2, 3), max_iteracoes=20,
                               cortes=Cortes(0.5, 5.0))
        self.assertEqual(com_teto(ENCHE_AOS_POUCOS)[0], NOTA_MINIMA)


def item_dos_melhores(posicao: int, media: float, desvio: float, por_caverna: dict) -> dict:
    return {"posicao": posicao, "genes": {"chance_inicial": 0.5, "sensibilidade": posicao},
            "iteracoes": 1, "nota_ajuste": media,
            "ajuste": {"media": media, "min": min(por_caverna.values()),
                       "max": max(por_caverna.values()), "desvio": desvio,
                       "por_caverna": por_caverna},
            "nota_reservada_media": media, "reservadas": {"media": media, "pior_semente": media},
            "ordem": 0, "geracao": 0}


class EscalaDasNotasRevisorTests(unittest.TestCase):
    def test_comprimir_e_estritamente_crescente_inclusive_no_zero(self):
        notas = np.concatenate([np.linspace(-5000, 1, 20001), [-1e-9, 0.0, 1e-9]])
        notas = np.unique(notas)
        comprimidas = np.array([figuras.comprimir(float(n)) for n in notas])
        self.assertTrue(np.all(np.diff(comprimidas) > 0))
        self.assertTrue(np.all(np.sign(comprimidas) == np.sign(notas)))

    def test_eixo_tem_marcas_coerentes_e_cobre_os_dados(self):
        casos = [[-4045.6, -0.07, 0.3], [0.2, 0.9], [-0.05], [], [None, -math.inf, math.nan],
                 [-1e5, 1.0], [1.3, -2.0], [-1000.0]]
        for notas in casos:
            with self.subTest(notas=notas):
                eixo = figuras.eixo_de_notas(notas)
                vals, textos = eixo["tickvals"], eixo["ticktext"]
                baixo, alto = eixo["range"]
                self.assertEqual(len(vals), len(textos))
                self.assertTrue(all(b > a for a, b in pairwise(vals)), vals)
                self.assertTrue(all(baixo <= v <= alto for v in vals))
                for valor, texto in zip(vals, textos):
                    self.assertEqual(valor, figuras.comprimir(float(texto)))
                finitas = [n for n in notas if n is not None and math.isfinite(n)]
                for n in finitas + [0.0, 1.0]:
                    self.assertLessEqual(baixo, figuras.comprimir(n))
                    self.assertGreaterEqual(alto, figuras.comprimir(n))
                self.assertIn("0", textos)
                self.assertTrue(all(math.isfinite(v) for v in [baixo, alto, *vals]))

    def test_escala_de_cor_vai_de_0_a_1_crescente_e_o_plotly_aceita(self):
        escala = figuras.escala_de_cor_das_notas()
        posicoes = [p for p, _ in escala]
        self.assertEqual(posicoes[0], 0.0)
        self.assertEqual(posicoes[-1], 1.0)
        self.assertTrue(all(b > a for a, b in pairwise(posicoes)), posicoes)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in posicoes))
        go.Heatmap(z=[[0.0]], colorscale=escala)  # o validador do plotly não reclama
        # O zero da nota cai exatamente na cor do meio da paleta.
        zmin = figuras.comprimir(figuras.NOTA_MIN_COR)
        zmax = figuras.comprimir(figuras.NOTA_MAX_COR)
        meio = figuras.sample_colorscale(figuras.get_colorscale(figuras.PALETA_NOTA), [0.5])[0]
        no_zero = [c for p, c in escala if math.isclose(p, -zmin / (zmax - zmin))]
        self.assertEqual(no_zero, [meio])

    def test_barra_de_erro_e_media_mais_ou_menos_desvio_mesmo_cruzando_o_zero(self):
        casos = [(0.05, 0.2), (-100.0, 50.0), (0.5, 0.3), (-0.02, 0.0), (-3000.0, 1500.0)]
        melhores = [item_dos_melhores(k + 1, media, desvio,
                                      {"a": media - desvio, "b": media + desvio})
                    for k, (media, desvio) in enumerate(casos)]
        melhores.append(item_dos_melhores(len(casos) + 1, -math.inf, math.nan,
                                          {"a": -math.inf, "b": 0.1}))
        execucao = {"cavernas": [{"nome": "a"}, {"nome": "b"}], "melhores": melhores}
        figura = figuras.figura_notas_por_caverna(execucao)
        media = figura.data[2]
        baixo, alto = figura.layout.yaxis.range
        for k, (nota, desvio) in enumerate(casos):
            with self.subTest(media=nota, desvio=desvio):
                y = media.y[k]
                self.assertGreaterEqual(media.error_y.array[k], 0)
                self.assertGreaterEqual(media.error_y.arrayminus[k], 0)
                self.assertAlmostEqual(y + media.error_y.array[k],
                                       figuras.comprimir(nota + desvio), places=12)
                self.assertAlmostEqual(y - media.error_y.arrayminus[k],
                                       figuras.comprimir(nota - desvio), places=12)
                self.assertLessEqual(baixo, figuras.comprimir(nota - desvio))
                self.assertGreaterEqual(alto, figuras.comprimir(nota + desvio))
        # Do lado negativo, o braço que vai para o zero fica mais comprido.
        self.assertGreater(media.error_y.array[1], media.error_y.arrayminus[1])
        # O cortado fica sem ponto e sem barra.
        self.assertIsNone(media.y[-1])
        self.assertEqual((media.error_y.array[-1], media.error_y.arrayminus[-1]), (0, 0))
        sem_constantes(figura.to_json())


class ComExecucao(unittest.TestCase):
    """Uma execução pequena do pipeline (2 cavernas 16³), feita uma vez para a classe."""
    @classmethod
    def setUpClass(cls):
        cls._pasta = tempfile.TemporaryDirectory()
        raiz = Path(cls._pasta.name)
        entrada, campos, cls.saida = raiz / "1_entrada", raiz / "2_campos", raiz / "3"
        entrada.mkdir()
        gravar_grade(entrada / "a_surface_64.npz", 6.0)
        gravar_grade(entrada / "b_surface_64.npz", 6.5)
        with mock.patch(RASTREADOR), contextlib.redirect_stdout(io.StringIO()):
            cls.destino = pipeline.main(["--orcamento", "20", "--populacao", "4", "--top", "4",
                                         "--entrada", str(entrada), "--campos", str(campos),
                                         "--saida", str(cls.saida)])
        cls.execucao = resultados.ler_execucao(cls.destino)

    @classmethod
    def tearDownClass(cls):
        cls._pasta.cleanup()

    def antiga(self) -> dict:
        """A mesma execução no formato de ga_011/ga_012: com máximo e sem a grade cheia."""
        antiga = copy.deepcopy(self.execucao)
        antiga["nome"] = "ga_011"
        antiga["cortes"] = {"fator_minimo": 0.5, "fator_maximo": 5.0}
        for caverna in antiga["cavernas"]:
            caverna["faixa_vazio"] = [0.5 * caverna["referencia_alvo"],
                                      5.0 * caverna["referencia_alvo"]]
            del caverna["nota_grade_cheia"]
        return antiga


class GravacaoDaFaixaTests(ComExecucao):
    def test_npz_grava_maximo_null_e_grade_cheia_de_cada_caverna(self):
        self.assertEqual(self.execucao["cortes"], {"fator_minimo": 0.5, "fator_maximo": None})
        with np.load(self.destino) as arquivo:
            texto = str(arquivo["cavernas"])
        for caverna in sem_constantes(texto):  # o JSON das cavernas não tem Infinity
            self.assertIsNone(caverna["faixa_vazio"][1])
            self.assertTrue(math.isfinite(caverna["nota_grade_cheia"]))
            # Numa esfera de 16³ o lado de fora é curto e, com o acréscimo do alvo,
            # a grade cheia pode até dar positivo; nas cavernas 64³ ela fica perto
            # de -1000. O contrato é ficar abaixo do máximo, 1.
            self.assertLess(caverna["nota_grade_cheia"], 1)

    def test_figuras_com_notas_extremas_saem_em_json_sem_constantes(self):
        execucao = copy.deepcopy(self.execucao)
        cheia = execucao["cavernas"][0]["nota_grade_cheia"]
        execucao["notas"] = execucao["notas"].copy()
        execucao["notas"][0] = cheia
        execucao["notas"][1] = -math.inf
        execucao["melhor_acumulado"] = execucao["melhor_acumulado"].copy()
        execucao["melhor_acumulado"][0] = -math.inf
        execucao["melhores"][-1]["ajuste"]["desvio"] = math.nan
        execucao["melhores"][-1]["ajuste"]["por_caverna"]["a"] = -math.inf
        execucao["melhores"][-1]["nota_ajuste"] = -math.inf
        execucao["melhores"][-1]["nota_reservada_media"] = -math.inf
        for titulo, _, figura in figuras.figuras_da_execucao(execucao, [self.execucao]):
            with self.subTest(figura=titulo):
                sem_constantes(figura.to_json())

    def test_trajetoria_sem_maximo_sombreia_ate_a_grade_cheia(self):
        figura = figuras.figura_trajetoria(self.execucao)
        tetos = [t for t in figura.data if t.fill == "tonexty"]
        self.assertEqual(len(tetos), len(self.execucao["cavernas"]))
        for teto in tetos:
            self.assertEqual(set(teto.y), {16 ** 3})
            self.assertIn("a partir de", teto.name)


class ExecucaoAntigaTests(ComExecucao):
    def test_antiga_gera_cabecalho_figuras_e_trajetoria_com_os_dois_limites(self):
        antiga = self.antiga()
        cabecalho = "\n".join(resultados.linhas_do_cabecalho(antiga))
        self.assertIn("vazio aceito de", cabecalho)
        self.assertNotIn("grade cheia", cabecalho)
        for titulo, _, figura in figuras.figuras_da_execucao(antiga):
            with self.subTest(figura=titulo):
                sem_constantes(figura.to_json())
        tetos = [t for t in figuras.figura_trajetoria(antiga).data if t.fill == "tonexty"]
        self.assertEqual([set(t.y) for t in tetos],
                         [{5.0 * c["referencia_alvo"]} for c in antiga["cavernas"]])

    def test_antiga_regravada_em_npz_gera_os_dois_relatorios(self):
        antiga = self.antiga()
        caminho = self.saida / "ga_011.npz"
        with np.load(self.destino) as arquivo:
            dados = {nome: arquivo[nome] for nome in arquivo.files}
        dados["cortes"] = np.array(json.dumps(antiga["cortes"]))
        dados["cavernas"] = np.array(json.dumps(antiga["cavernas"], ensure_ascii=False))
        np.savez_compressed(caminho, **dados)
        markdown, relatorio = resultados.gerar(caminho, [self.destino], imprimir=False,
                                               painel=Painel(1, saida=io.StringIO()))
        self.assertIn("vazio aceito de", markdown.read_text(encoding="utf-8"))
        self.assertIn("faixa de vazio", relatorio.read_text(encoding="utf-8"))

    def test_comparar_nova_com_antiga_avisa_so_a_faixa(self):
        aviso = resultados.avisos_de_comparacao(self.execucao, [self.antiga()])
        self.assertEqual(aviso, [(f"ga_011 não é comparável com {self.execucao['nome']}: "
                                  "difere em faixa de vazio.")])
        self.assertEqual(resultados.avisos_de_comparacao(self.antiga(), [self.execucao]),
                         [(f"{self.execucao['nome']} não é comparável com ga_011: difere em "
                           "faixa de vazio.")])

    def test_legenda_da_antiga_nao_diz_que_cortado_e_so_vazio_de_menos(self):
        # Em ga_011/ga_012 (gravadas em 22/11/2026, com o máximo 5x), um cortado
        # pode ser vazio demais: a legenda fixa diz o contrário.
        texto = resultados.markdown_dos_melhores(self.antiga())
        self.assertNotIn("então é vazio de menos", texto)

    def test_legenda_da_antiga_nao_promete_a_grade_cheia_no_cabecalho(self):
        # As execuções antigas não gravaram nota_grade_cheia, e o cabeçalho delas
        # não a mostra; a legenda não pode mandar procurar lá.
        texto = resultados.markdown_dos_melhores(self.antiga())
        self.assertNotIn("grade cheia", "\n".join(resultados.linhas_do_cabecalho(self.antiga())))
        self.assertNotIn("o valor de cada caverna está no cabeçalho", texto)


class PainelMedianaELargurasTests(unittest.TestCase):
    def painel(self) -> tuple[Painel, io.StringIO]:
        saida = io.StringIO()
        return Painel(10, saida=saida, ao_vivo=False, estilo=Estilo()), saida

    @staticmethod
    def avaliacao(nota: float, ordem: int):
        return SimpleNamespace(genes={"chance_inicial": 0.5, "sensibilidade": ordem}, nota=nota,
                               detalhes={"iteracoes": 1, "cavernas": {}}, geracao=0, ordem=ordem)

    def resumo(self, notas: list[float]) -> str:
        painel, saida = self.painel()
        grupo = [self.avaliacao(n, k) for k, n in enumerate(notas)]
        for a in grupo:
            painel("candidato", {"avaliacao": a, "repetido": False})
        painel("geracao", {"geracao": 0, "populacao": grupo})
        return saida.getvalue().splitlines()[-1]

    def test_mediana_ignora_cortados_e_nao_e_arrastada_pelo_extremo(self):
        linha = self.resumo([0.2, -0.1, -4033.246, -math.inf])
        self.assertIn("mediana -0.100", linha)
        self.assertIn("válidos 3/4", linha)

    def test_geracao_toda_cortada_nao_quebra_o_resumo(self):
        linha = self.resumo([-math.inf, -math.inf, -math.inf])
        self.assertIn("mediana   -", linha)
        self.assertIn("válidos 0/3", linha)

    def test_tabela_alinha_com_cortado_desvio_nan_e_milhares(self):
        itens = [item_dos_melhores(1, -0.073, 0.1, {"a": -0.173, "b": 0.028}),
                 item_dos_melhores(2, -4039.332, 6.36, {"a": -4045.6, "b": -4033.2}),
                 item_dos_melhores(3, -math.inf, math.nan, {"a": -math.inf, "b": 0.5})]
        for cavernas in (["a", "b"], ["a"]):
            with self.subTest(cavernas=cavernas):
                painel, saida = self.painel()
                painel.tabela_melhores(itens, ["chance_inicial", "sensibilidade"], cavernas, 5, 10)
                linhas = saida.getvalue().splitlines()[-4:]
                self.assertEqual(len({len(linha.rstrip()) for linha in linhas}), 1, linhas)
                self.assertIn("cortado", linhas[-1])

    def test_tabela_vazia_nao_quebra(self):
        painel, saida = self.painel()
        painel.tabela_melhores([], ["chance_inicial", "sensibilidade"], ["a", "b"], 5, 10)
        self.assertIn("nenhum", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
