"""Garante que o relatório dos testes não esconde nem inventa resultado.

O relatório é o que se olha para saber se a suíte passou, então o que importa é
que ele conte certo: nenhum problema pode sumir, inclusive módulo que não importa
e falha dentro de subTest, e o veredito precisa bater com o do unittest.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rodar import localizar, resumir, rodar  # noqa: E402


class Ocultos:
    """Dentro de outra classe, para o discover não rodar as falhas de propósito."""

    class Exemplos(unittest.TestCase):
        def test_passa(self) -> None:
            pass

        def test_falha(self) -> None:
            self.assertEqual(1, 2)

        def test_erro(self) -> None:
            raise RuntimeError("quebrou")

        @unittest.skip("sem dados")
        def test_pula(self) -> None:
            pass

        def test_imprime_e_passa(self) -> None:
            print("saida barulhenta do teste")

        def test_subtests_falhando(self) -> None:
            for valor in (1, 2):
                with self.subTest(valor=valor):
                    self.assertEqual(valor, 0)


def executar(*nomes: str, detalhe: bool = False):
    """Roda os testes de Exemplos e devolve (relatório, texto impresso)."""
    saida = io.StringIO()
    console = Console(file=saida, width=120, no_color=True)
    suite = unittest.TestSuite(Ocultos.Exemplos(nome) for nome in nomes)
    return rodar(suite, console, detalhe), saida.getvalue()


class RelatorioTest(unittest.TestCase):
    def test_tudo_passando_da_veredito_positivo(self) -> None:
        relatorio, texto = executar("test_passa")
        self.assertTrue(relatorio.wasSuccessful())
        self.assertEqual(relatorio.aprovados, 1)
        self.assertIn("PASSOU", texto)
        self.assertNotIn("NÃO PASSOU", texto)
        self.assertNotIn("Problemas", texto)

    def test_falha_e_erro_aparecem_com_motivo_e_viram_nao_passou(self) -> None:
        relatorio, texto = executar("test_passa", "test_falha", "test_erro")
        self.assertFalse(relatorio.wasSuccessful())
        self.assertEqual(relatorio.aprovados, 1)
        self.assertIn("NÃO PASSOU", texto)
        self.assertIn("Problemas (2)", texto)
        self.assertIn("FALHA", texto)
        self.assertIn("AssertionError: 1 != 2", texto)
        self.assertIn("RuntimeError: quebrou", texto)
        self.assertIn("Exemplos.test_erro", texto)
        self.assertIn("tests/test_rodar.py:", texto)

    def test_pulado_nao_reprova_e_e_contado(self) -> None:
        relatorio, texto = executar("test_passa", "test_pula")
        self.assertTrue(relatorio.wasSuccessful())
        self.assertIn("1 pulado(s)", texto)
        self.assertIn("PASSOU", texto)

    def test_cada_subteste_com_falha_e_listado_e_reprova(self) -> None:
        relatorio, texto = executar("test_subtests_falhando")
        self.assertFalse(relatorio.wasSuccessful())
        self.assertEqual(relatorio.aprovados, 0)
        self.assertIn("Problemas (2)", texto)
        self.assertIn("0/1", texto)
        self.assertIn("valor=1", texto)
        self.assertIn("valor=2", texto)

    def test_modulo_que_nao_importa_vira_erro_com_o_motivo(self) -> None:
        suite = unittest.TestLoader().loadTestsFromName("modulo_que_nao_existe_xyz")
        saida = io.StringIO()
        relatorio = rodar(suite, Console(file=saida, width=120, no_color=True))
        texto = saida.getvalue()
        self.assertFalse(relatorio.wasSuccessful())
        self.assertIn("o módulo não importou", texto)
        self.assertIn("modulo_que_nao_existe_xyz", texto)
        self.assertIn("NÃO PASSOU", texto)

    def test_saida_do_teste_nao_suja_o_relatorio(self) -> None:
        _, texto = executar("test_imprime_e_passa")
        self.assertNotIn("saida barulhenta", texto)

    def test_detalhe_lista_cada_teste_e_o_traceback_inteiro(self) -> None:
        _, resumido = executar("test_passa", "test_falha")
        _, detalhado = executar("test_passa", "test_falha", detalhe=True)
        self.assertNotIn("Exemplos.test_passa", resumido)
        self.assertNotIn("Traceback (most recent call last)", resumido)
        self.assertIn("Exemplos.test_passa", detalhado)
        self.assertIn("Traceback (most recent call last)", detalhado)

    def test_exemplos_com_falha_nao_entram_na_suite_real(self) -> None:
        suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
        nomes = [teste.id() for grupo in suite for teste in grupo]
        self.assertTrue(nomes)
        self.assertFalse([nome for nome in nomes if "Exemplos" in nome])

    def test_setup_de_classe_com_erro_nao_some(self) -> None:
        class SetupQuebrado(unittest.TestCase):
            @classmethod
            def setUpClass(cls) -> None:
                raise RuntimeError("setup quebrou")

            def test_nunca_roda(self) -> None:
                pass

        saida = io.StringIO()
        suite = unittest.TestLoader().loadTestsFromTestCase(SetupQuebrado)
        relatorio = rodar(suite, Console(file=saida, width=120, no_color=True))
        self.assertFalse(relatorio.wasSuccessful())
        self.assertIn("RuntimeError: setup quebrou", saida.getvalue())


class ResumoDoTracebackTest(unittest.TestCase):
    TRACEBACK = (
        'Traceback (most recent call last):\n'
        f'  File "{Path(__file__).resolve()}", line 7, in test_x\n'
        '    faz()\n'
        '  File "C:\\Python313\\Lib\\shutil.py", line 625, in rm\n'
        '    os.unlink(x)\n'
        'PermissionError: [WinError 32] em uso\n'
    )

    def test_motivo_e_a_excecao_final(self) -> None:
        self.assertEqual(resumir(self.TRACEBACK), ["PermissionError: [WinError 32] em uso"])

    def test_local_e_o_ultimo_arquivo_dentro_do_projeto(self) -> None:
        self.assertEqual(localizar(self.TRACEBACK), "tests/test_rodar.py:7")

    def test_sem_arquivo_do_projeto_nao_inventa_local(self) -> None:
        self.assertEqual(localizar('  File "C:\\Python313\\Lib\\x.py", line 1, in y\n'), "")


if __name__ == "__main__":
    unittest.main()
