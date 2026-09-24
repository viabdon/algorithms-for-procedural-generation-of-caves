"""Medicao de recursos consumidos por uma execucao completa de um gerador.

O decorator track_resources envolve a funcao que representa a execucao inteira
de um algoritmo, amostra CPU, memoria e (quando houver) GPU em uma thread
paralela, e grava uma linha por execucao em um CSV cumulativo. O valor de
retorno e o comportamento da funcao decorada nao mudam.

A medicao e do PROCESSO, via psutil.Process, nao da maquina: o interesse e o
custo do gerador, nao o do que mais estiver rodando no computador. Isso importa
para o TCC porque a comparacao entre algoritmos de IA e nao-IA precisa da mesma
regua nos dois lados.

    from cavegen.profiling.resource_tracker import track_resources

    @track_resources(label="random_walk")
    def generate(shape, seed):
        ...

O label aceita uma funcao em vez de texto quando a configuracao muda a cada
chamada; ela recebe os argumentos da chamada por nome e devolve o rotulo.
"""

from __future__ import annotations

import csv
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from inspect import signature
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import psutil

from cavegen.profiling.gpu_monitor import gpu_sampler

INTERVALO_PADRAO = 0.1

# Ancorado na raiz do repositorio, nao no diretorio de trabalho: o menu pode ser
# chamado de qualquer lugar e a planilha precisa cair sempre no mesmo arquivo.
RAIZ_PROJETO = Path(__file__).resolve().parents[3]
CSV_PADRAO = RAIZ_PROJETO / "results" / "profiling" / "resource_usage.csv"

BYTES_POR_MB = 1024 ** 2

COLUNAS = [
    "timestamp",
    "algorithm",
    "label",
    "status",
    "error",
    "duration_seconds",
    "samples",
    "cpu_percent_mean",
    "cpu_percent_peak",
    "rss_mb_mean",
    "rss_mb_peak",
    "gpu_percent_mean",
    "gpu_percent_peak",
    "gpu_memory_mb_mean",
    "gpu_memory_mb_peak",
]


@dataclass
class ResourceSample:
    """Uma leitura instantanea do consumo do processo."""

    timestamp: float
    cpu_percent: float
    rss_bytes: int
    gpu_percent: int | None = None
    gpu_memory_bytes: int | None = None


@dataclass
class ResourceSampler:
    """Amostra o consumo do processo em uma thread paralela.

    Usavel como context manager. A thread e daemon para nao segurar a saida do
    programa, e o Event de parada e esperado em vez de dormido, entao stop()
    interrompe na hora em vez de aguardar o intervalo inteiro.
    """

    interval_seconds: float = INTERVALO_PADRAO
    samples: list[ResourceSample] = field(default_factory=list)
    _parar: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        processo = psutil.Process(os.getpid())
        # A primeira leitura de cpu_percent apenas arma o contador; o valor dela
        # nao significa nada e por isso e descartado.
        processo.cpu_percent(interval=None)

        def laco() -> None:
            with gpu_sampler() as ler_gpu:
                # Espera antes de amostrar: cpu_percent mede a fatia desde a
                # leitura anterior, entao amostrar de imediato daria sempre 0.
                while not self._parar.wait(self.interval_seconds):
                    self.samples.append(self._ler(processo, ler_gpu))

                if not self.samples:
                    # Execucao mais curta que um intervalo. Uma amostra cobrindo
                    # o periodo inteiro e melhor que agregados vazios.
                    self.samples.append(self._ler(processo, ler_gpu))

        self._parar.clear()
        self._thread = threading.Thread(target=laco, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def __enter__(self) -> ResourceSampler:
        self.start()
        return self

    def __exit__(self, *_excecao: object) -> None:
        self.stop()

    @staticmethod
    def _ler(processo: psutil.Process, ler_gpu: Callable[[], tuple[int, int] | None] | None) -> ResourceSample:
        gpu_percent, gpu_memoria = None, None
        if ler_gpu is not None:
            leitura = ler_gpu()
            if leitura is not None:
                gpu_percent, gpu_memoria = leitura

        return ResourceSample(
            timestamp=time.time(),
            cpu_percent=processo.cpu_percent(interval=None),
            rss_bytes=processo.memory_info().rss,
            gpu_percent=gpu_percent,
            gpu_memory_bytes=gpu_memoria,
        )


def media_e_pico(valores: list[float | None]) -> tuple[float | None, float | None]:
    """Média e máximo de uma série, ignorando as leituras ausentes.

    Devolve (None, None) quando nada foi medido, em vez de zero: zero afirmaria
    que o consumo foi nulo, e o que houve foi ausencia de medicao.
    """
    medidos = [valor for valor in valores if valor is not None]
    if not medidos:
        return None, None

    return sum(medidos) / len(medidos), max(medidos)


def resumo_da_execucao(algorithm: str, label: str, status: str, error: str,
                       duration_seconds: float, samples: list[ResourceSample]) -> dict[str, Any]:
    """Agrega as amostras de uma execução na linha que vai para o CSV."""
    cpu_media, cpu_pico = media_e_pico([amostra.cpu_percent for amostra in samples])
    rss_media, rss_pico = media_e_pico([amostra.rss_bytes for amostra in samples])
    gpu_media, gpu_pico = media_e_pico([amostra.gpu_percent for amostra in samples])
    gpu_mem_media, gpu_mem_pico = media_e_pico([amostra.gpu_memory_bytes for amostra in samples])

    def mb(valor: float | None) -> float | None:
        return None if valor is None else round(valor / BYTES_POR_MB, 2)

    def pct(valor: float | None) -> float | None:
        return None if valor is None else round(valor, 1)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "algorithm": algorithm,
        "label": label,
        "status": status,
        "error": error,
        "duration_seconds": round(duration_seconds, 4),
        "samples": len(samples),
        "cpu_percent_mean": pct(cpu_media),
        "cpu_percent_peak": pct(cpu_pico),
        "rss_mb_mean": mb(rss_media),
        "rss_mb_peak": mb(rss_pico),
        "gpu_percent_mean": pct(gpu_media),
        "gpu_percent_peak": pct(gpu_pico),
        "gpu_memory_mb_mean": mb(gpu_mem_media),
        "gpu_memory_mb_peak": mb(gpu_mem_pico),
    }


def registrar_execucao(linha: dict[str, Any], csv_path: Path) -> None:
    """Acrescenta a linha ao CSV cumulativo, criando o cabeçalho na primeira vez.

    Campos ausentes viram célula vazia, que pandas lê como NaN.
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    novo = not csv_path.exists()

    with csv_path.open("a", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, extrasaction="ignore")
        if novo:
            escritor.writeheader()
        escritor.writerow({coluna: linha.get(coluna, "") for coluna in COLUNAS})


def argumentos_nomeados(func: Callable[..., Any], args: tuple, kwargs: dict) -> dict[str, Any]:
    """Argumentos da chamada por nome, para o label saber a configuração usada.

    Resolve posicionais e defaults, entao o rotulo nao depende de como a funcao
    foi chamada. Devolve vazio se a assinatura nao casar, sem atrapalhar a chamada.
    """
    try:
        ligacao = signature(func).bind(*args, **kwargs)
        ligacao.apply_defaults()
        return dict(ligacao.arguments)
    except TypeError:
        return {}


def track_resources(label: str | Callable[[dict[str, Any]], str] | None = None,
                    csv_path: Path | str | None = None,
                    interval_seconds: float = INTERVALO_PADRAO):
    """Mede o consumo de recursos de uma execução e grava uma linha no CSV.

    label: texto fixo, ou função que recebe os argumentos da chamada por nome e
        devolve o rótulo da configuração. A função é o que permite separar, na
        mesma planilha, execuções do mesmo algoritmo com parâmetros diferentes.
    csv_path: destino da planilha; o padrão é results/profiling/resource_usage.csv.
    interval_seconds: espaçamento entre amostras.
    """

    def decorador(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            amostrador = ResourceSampler(interval_seconds=interval_seconds)
            status, error = "sucesso", ""
            inicio = perf_counter()
            amostrador.start()

            try:
                return func(*args, **kwargs)
            # BaseException tambem cobre Ctrl+C, que e desfecho comum em run longo.
            except BaseException as excecao:
                status, error = "erro", type(excecao).__name__
                raise
            finally:
                duracao = perf_counter() - inicio
                amostrador.stop()

                if callable(label):
                    rotulo = str(label(argumentos_nomeados(func, args, kwargs)))
                else:
                    rotulo = "" if label is None else str(label)

                linha = resumo_da_execucao(
                    algorithm=func.__name__,
                    label=rotulo,
                    status=status,
                    error=error,
                    duration_seconds=duracao,
                    samples=amostrador.samples,
                )

                try:
                    registrar_execucao(linha, csv_path or CSV_PADRAO)
                except OSError as falha:
                    # Perder a planilha nao pode custar o resultado do gerador,
                    # mas o aviso vai para stderr em vez de sumir em silencio.
                    print(f"[track_resources] nao deu para gravar o CSV: {falha}", file=sys.stderr)

        return wrapper

    return decorador
