from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cavegen.profiling.resource_tracker import COLUNAS, track_resources


def _linhas(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


class TrackResourcesTests(unittest.TestCase):
    def test_grava_uma_linha_com_as_colunas_esperadas(self) -> None:
        with TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / "sub" / "uso.csv"

            @track_resources(label="dummy", csv_path=destino, interval_seconds=0.01)
            def somar(quantidade: int) -> int:
                return sum(range(quantidade))

            resultado = somar(200_000)

            self.assertEqual(resultado, sum(range(200_000)))
            self.assertTrue(destino.exists(), "o CSV deveria ter sido criado junto da pasta")

            linhas = _linhas(destino)
            self.assertEqual(len(linhas), 1)

            linha = linhas[0]
            self.assertEqual(list(linha.keys()), COLUNAS)
            self.assertEqual(linha["algorithm"], "somar")
            self.assertEqual(linha["label"], "dummy")
            self.assertEqual(linha["status"], "sucesso")
            self.assertEqual(linha["error"], "")
            self.assertGreater(float(linha["duration_seconds"]), 0.0)
            self.assertGreaterEqual(int(linha["samples"]), 1)
            self.assertGreater(float(linha["rss_mb_peak"]), 0.0)

    def test_sem_gpu_as_colunas_de_gpu_ficam_vazias(self) -> None:
        with TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / "uso.csv"

            @track_resources(csv_path=destino, interval_seconds=0.01)
            def nada() -> None:
                return None

            nada()

            linha = _linhas(destino)[0]
            # Em maquina sem GPU monitoravel os campos saem vazios (NaN no pandas),
            # nunca zero: zero afirmaria consumo nulo em vez de ausencia de medida.
            for coluna in ("gpu_percent_mean", "gpu_percent_peak",
                           "gpu_memory_mb_mean", "gpu_memory_mb_peak"):
                self.assertEqual(linha[coluna], "", f"{coluna} deveria estar vazia sem GPU")

    def test_registra_a_falha_e_repassa_a_excecao(self) -> None:
        with TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / "uso.csv"

            @track_resources(label="quebra", csv_path=destino, interval_seconds=0.01)
            def explodir() -> None:
                raise ValueError("falhou no meio")

            with self.assertRaisesRegex(ValueError, "falhou no meio"):
                explodir()

            linha = _linhas(destino)[0]
            self.assertEqual(linha["status"], "erro")
            self.assertEqual(linha["error"], "ValueError")

    def test_execucoes_seguidas_acumulam_sem_repetir_cabecalho(self) -> None:
        with TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / "uso.csv"

            @track_resources(csv_path=destino, interval_seconds=0.01)
            def ping() -> str:
                return "pong"

            ping()
            ping()
            ping()

            self.assertEqual(len(_linhas(destino)), 3)
            self.assertEqual(destino.read_text(encoding="utf-8").count("timestamp,algorithm"), 1)

    def test_label_como_funcao_recebe_os_argumentos_por_nome(self) -> None:
        with TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / "uso.csv"

            def rotular(argumentos: dict) -> str:
                return f"n{argumentos['n']}-modo{argumentos['modo']}"

            @track_resources(label=rotular, csv_path=destino, interval_seconds=0.01)
            def rodar(n: int, modo: str = "rapido") -> int:
                return n

            # Um posicional e um default: o label tem que ver os dois por nome.
            rodar(7)

            self.assertEqual(_linhas(destino)[0]["label"], "n7-modorapido")

    def test_preserva_nome_e_docstring_da_funcao_decorada(self) -> None:
        with TemporaryDirectory() as diretorio:
            @track_resources(csv_path=Path(diretorio) / "uso.csv", interval_seconds=0.01)
            def documentada() -> None:
                """Docstring preservada."""

            self.assertEqual(documentada.__name__, "documentada")
            self.assertEqual(documentada.__doc__, "Docstring preservada.")


if __name__ == "__main__":
    unittest.main()
