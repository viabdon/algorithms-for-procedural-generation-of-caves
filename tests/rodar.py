"""Roda a suíte unittest com um relatório fácil de ler no terminal.

Mostra uma linha por módulo, junta os problemas no fim com o motivo e o arquivo
de cada um e fecha com um quadro dizendo se passou. Os testes são os mesmos do
unittest, então `python -m unittest discover -s tests` continua valendo.

    uv run poe test                                  # suíte completa
    uv run poe test tests/test_volume.py             # um módulo
    uv run poe test --detalhe                        # cada teste e o traceback inteiro
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import traceback
import unittest
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

PASTA_TESTES = Path(__file__).resolve().parent
RAIZ = PASTA_TESTES.parent

ARQUIVO_NO_TRACEBACK = re.compile(r'File "([^"]+)", line (\d+)')
LINHA_DA_EXCECAO = re.compile(r"^[\w.]*(Error|Exception|Failure|Interrupt|Exit)\b")
MODULO_DO_SETUP = re.compile(r"\((\w+)")
LINHAS_DO_MOTIVO = 4


@dataclass
class Problema:
    """Um teste que falhou (asserção) ou deu erro (exceção), já pronto para mostrar."""

    tipo: str
    modulo: str
    nome: str
    traceback: str


def resumir(texto: str) -> list[str]:
    """Pega do traceback só a exceção final, sem o caminho até ela."""
    linhas = texto.strip().splitlines()
    for indice in range(len(linhas) - 1, -1, -1):
        if LINHA_DA_EXCECAO.match(linhas[indice]):
            return [linha for linha in linhas[indice:] if linha.strip()][:LINHAS_DO_MOTIVO]
    return linhas[-LINHAS_DO_MOTIVO:]


def localizar(texto: str) -> str:
    """Último ponto do traceback dentro do projeto, como tests/test_f32.py:24."""
    for arquivo, linha in reversed(ARQUIVO_NO_TRACEBACK.findall(texto)):
        caminho = Path(arquivo)
        if caminho.is_relative_to(RAIZ):
            return f"{caminho.relative_to(RAIZ).as_posix()}:{linha}"
    return ""


class Relatorio(unittest.TestResult):
    """Imprime uma linha ao terminar cada módulo e guarda os problemas para o fim."""

    def __init__(self, console: Console, detalhe: bool = False) -> None:
        super().__init__()
        self.console = console
        self.detalhe = detalhe
        # A saída dos testes não atrapalha o relatório; a de quem falhou vai no traceback.
        self.buffer = True
        self.problemas: list[Problema] = []
        self.aprovados = 0
        self.modulos = 0
        self._modulo: str | None = None
        self._testes_do_modulo: list[tuple[str, str]] = []
        self._inicio_do_modulo = 0.0

    @staticmethod
    def _modulo_e_nome(test: unittest.TestCase) -> tuple[str, str]:
        if type(test).__name__ == "_FailedTest":
            # Módulo que nem importou: o unittest cria um teste falso com o nome dele.
            return test._testMethodName, "o módulo não importou"
        if not isinstance(test, unittest.TestCase):
            # Erro em setUpClass ou setUpModule: não há teste, só a descrição do erro.
            achado = MODULO_DO_SETUP.search(str(test))
            return (achado.group(1) if achado else str(test)), str(test)
        return type(test).__module__, f"{type(test).__name__}.{test._testMethodName}"

    def _entrar_no_modulo(self, modulo: str) -> None:
        if modulo != self._modulo:
            self._fechar_modulo()
            self._modulo = modulo
            self._testes_do_modulo = []
            self._inicio_do_modulo = perf_counter()

    def _fechar_modulo(self) -> None:
        if self._modulo is None:
            return
        self.modulos += 1
        marcas = [marca for marca, _ in self._testes_do_modulo]
        passaram = marcas.count("ok")
        pulados = marcas.count("pulado")
        problemas = len(marcas) - passaram - pulados
        tempo = perf_counter() - self._inicio_do_modulo

        linha = Text("  ")
        linha.append("✗ " if problemas else "✓ ", "bold red" if problemas else "bold green")
        linha.append(f"{self._modulo:<36}", "bold" if problemas else "")
        linha.append(f"{passaram:>3}/{len(marcas):<3}", "red" if problemas else "green")
        linha.append(f"{tempo:>7.2f}s", "dim")
        if pulados:
            linha.append(f"  {pulados} pulado(s)", "yellow")
        self.console.print(linha)

        if self.detalhe:
            estilos = {"ok": ("✓", "green"), "pulado": ("-", "yellow")}
            for marca, nome in self._testes_do_modulo:
                simbolo, estilo = estilos.get(marca, ("✗", "red"))
                self._recuado(Text(f"{simbolo} {nome}", estilo), 6)

    def _anotar(self, test: unittest.TestCase, marca: str) -> None:
        modulo, nome = self._modulo_e_nome(test)
        self._entrar_no_modulo(modulo)
        self._testes_do_modulo.append((marca, nome))

    def _recuado(self, texto: Text, recuo: int) -> None:
        """Imprime mantendo o recuo também nas linhas que quebram."""
        self.console.print(Padding(texto, (0, 0, 0, recuo)), overflow="fold")

    def _guardar(self, tipo: str, test: unittest.TestCase, err, sufixo: str = "") -> None:
        modulo, nome = self._modulo_e_nome(test)
        texto = "".join(traceback.format_exception(*err))
        self.problemas.append(Problema(tipo, modulo, nome + sufixo, texto))
        if (tipo.lower(), nome) not in self._testes_do_modulo:
            self._anotar(test, tipo.lower())

    def startTest(self, test: unittest.TestCase) -> None:
        super().startTest(test)
        self._entrar_no_modulo(self._modulo_e_nome(test)[0])

    def stopTest(self, test: unittest.TestCase) -> None:
        # Sem isto o unittest repete na tela a saída do teste que falhou.
        self._mirrorOutput = False
        super().stopTest(test)

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        self.aprovados += 1
        self._anotar(test, "ok")

    def addFailure(self, test: unittest.TestCase, err) -> None:
        super().addFailure(test, err)
        self._guardar("FALHA", test, err)

    def addError(self, test: unittest.TestCase, err) -> None:
        super().addError(test, err)
        self._guardar("ERRO", test, err)

    def addSubTest(self, test: unittest.TestCase, subtest: unittest.TestCase, err) -> None:
        super().addSubTest(test, subtest, err)
        if err is not None:
            falhou = issubclass(err[0], test.failureException)
            sufixo = f" {subtest._subDescription()}"
            self._guardar("FALHA" if falhou else "ERRO", test, err, sufixo)

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._anotar(test, "pulado")

    def addExpectedFailure(self, test: unittest.TestCase, err) -> None:
        super().addExpectedFailure(test, err)
        self.aprovados += 1
        self._anotar(test, "ok")

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self.problemas.append(Problema("FALHA", *self._modulo_e_nome(test),
                                       "Passou, mas estava marcado como falha esperada."))
        self._anotar(test, "falha")

    def stopTestRun(self) -> None:
        super().stopTestRun()
        self._fechar_modulo()

    def imprimir_problemas(self) -> None:
        """Lista cada problema com o motivo e o arquivo, ou com o traceback no modo detalhe."""
        if not self.problemas:
            return
        self.console.print()
        self.console.print(Rule(f"Problemas ({len(self.problemas)})", style="red"))
        for problema in self.problemas:
            titulo = Text("  ")
            titulo.append(f"{problema.tipo} ", "bold red")
            titulo.append(problema.modulo, "bold")
            titulo.append(f"  {problema.nome}", "dim")
            self.console.print()
            self.console.print(titulo, overflow="fold")

            local = localizar(problema.traceback)
            if local:
                self._recuado(Text(local, "cyan"), 4)
            linhas = (problema.traceback.strip().splitlines() if self.detalhe
                      else resumir(problema.traceback))
            for linha in linhas:
                # O caminho da raiz só ocupa espaço: o resto já identifica o arquivo.
                self._recuado(Text(linha.replace(f"{RAIZ}{os.sep}", "")), 4)

    def imprimir_quadro(self, duracao: float) -> None:
        """Fecha com o veredito, para não precisar procurar no log se passou."""
        erros = sum(problema.tipo == "ERRO" for problema in self.problemas)
        falhas = len(self.problemas) - erros
        pulados = len(self.skipped)
        passou = self.wasSuccessful() and self.testsRun > 0

        corpo = Text(justify="center")
        corpo.append("PASSOU\n" if passou else "NÃO PASSOU\n",
                     "bold green" if passou else "bold red")
        corpo.append(f"{self.aprovados} ok", "green")
        corpo.append(f"  ·  {erros} erro(s)  ·  {falhas} falha(s)",
                     "red" if erros or falhas else "dim")
        corpo.append(f"  ·  {pulados} pulado(s)", "yellow" if pulados else "dim")
        corpo.append(f"\n{self.testsRun} teste(s) em {self.modulos} módulo(s), {duracao:.1f}s",
                     "dim")
        self.console.print()
        self.console.print(Panel(corpo, border_style="green" if passou else "red"))
        if not passou and not self.detalhe and self.problemas:
            self.console.print(Text("  Traceback completo: uv run poe test --detalhe", "dim"))


def carregar(alvos: list[str]) -> unittest.TestSuite:
    """Suíte inteira, ou só os alvos: caminho (tests/test_x.py) ou nome (test_x.Classe)."""
    carregador = unittest.TestLoader()
    # As ferramentas de tools/ ficam na raiz, fora do pacote instalado: rodando
    # "python tests/rodar.py", a raiz não entra sozinha no sys.path.
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    if not alvos:
        return carregador.discover(str(PASTA_TESTES), top_level_dir=str(PASTA_TESTES))
    if str(PASTA_TESTES) not in sys.path:
        sys.path.insert(0, str(PASTA_TESTES))
    nomes = [Path(alvo).stem if alvo.endswith(".py") else alvo for alvo in alvos]
    return carregador.loadTestsFromNames(nomes)


def rodar(suite: unittest.TestSuite, console: Console, detalhe: bool = False) -> Relatorio:
    """Roda a suíte e imprime o relatório inteiro."""
    relatorio = Relatorio(console, detalhe)
    inicio = perf_counter()
    relatorio.startTestRun()
    suite.run(relatorio)
    relatorio.stopTestRun()
    relatorio.imprimir_problemas()
    relatorio.imprimir_quadro(perf_counter() - inicio)
    return relatorio


def criar_console() -> Console:
    """Console em UTF-8 e com cor também no terminal do Git Bash."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # O Git Bash pode se apresentar ao Python como um pipe. Nesse caso o rich desliga as
    # cores e assume o console antigo do Windows, que também não as emitiria.
    git_bash = bool(os.environ.get("MSYSTEM"))
    arquivo = stat.S_ISREG(os.fstat(sys.stdout.fileno()).st_mode)
    if git_bash and not arquivo:
        return Console(file=sys.stdout, force_terminal=True, legacy_windows=False)
    return Console(file=sys.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Roda os testes com um relatório legível.")
    parser.add_argument("alvos", nargs="*",
                        help="tests/test_x.py ou test_x.Classe; vazio roda tudo")
    parser.add_argument("--detalhe", action="store_true",
                        help="lista cada teste e o traceback inteiro")
    argumentos = parser.parse_args()

    console = criar_console()
    console.print()
    console.print(Rule("Testes do cavegen", style="cyan"))
    console.print()
    relatorio = rodar(carregar(argumentos.alvos), console, argumentos.detalhe)
    return 0 if relatorio.wasSuccessful() and relatorio.testsRun > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
