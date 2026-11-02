"""Ponte entre a bancada Streamlit e o pacote do autômato celular.

Nada aqui importa o streamlit, então dá para testar sem o extra ui. A
dependência é só de mão única: este módulo chama o CA, o CA não sabe que ele
existe.

O CA roda em memória, passo a passo, para a aba de evolução poder mostrar cada
iteração. Só vira arquivo quando o usuário pede para salvar, e aí no mesmo
formato que run_and_save e save_seed_matrix gravam, para o menu e o plot lerem.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.generator import BorderTreatment, iterate
from cavegen.generators.cellular_automata.results import (
    RESULTS_DIR,
    next_result_id,
    result_path,
)
from cavegen.generators.cellular_automata.seeds import SEEDS_DIR, next_seed_id, seed_path


@dataclass
class Execucao:
    """
        Um volume do CA aberto na bancada, rodado agora ou lido de results/.
        seed: matriz inicial (passo 0).
        final: matriz depois da última iteração.
        historico: células vivas em cada passo, do 0 (seed) ao último.
        passos: matriz de cada passo; None quando o volume veio de um arquivo.
        seed_id: None enquanto a seed sorteada na hora não foi gravada.
        one_probability: chance de 1 da seed, quando conhecida.
        segundos: duração do laço do CA; None quando veio de um arquivo.
        result_id: None enquanto o resultado não foi gravado.
    """
    seed: np.ndarray
    final: np.ndarray
    historico: np.ndarray
    sensitivity: int
    border_treatment: str
    iterations: int
    passos: list | None = None
    seed_id: int | None = None
    one_probability: float | None = None
    peso_id: int | None = None
    segundos: float | None = None
    result_id: int | None = None

    @property
    def lado(self) -> int:
        return int(self.final.shape[0])

    @property
    def total_celulas(self) -> int:
        return int(self.final.size)


def rodar_passo_a_passo(seed: np.ndarray, sensitivity: int, border_treatment: BorderTreatment,
                        iterations: int, peso=None, progress=None) -> tuple[list, float]:
    """
        Repete o passo do CA guardando a matriz de cada iteração.
        É o mesmo laço de cellular_automata, só que sem descartar os passos do meio.
        Devolve a lista de matrizes booleanas (passo 0 = seed) e os segundos do laço.
        A duração é só uma referência de bancada, não entra no benchmark.
        seed: matriz binária inicial.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
        iterations: quantas vezes o passo é repetido.
        peso: matriz opcional somada à contagem de vizinhos.
        progress: função opcional chamada ao fim de cada passo com (passo, iterations).
    """
    border_treatment = BorderTreatment(border_treatment)
    matriz = np.asarray(seed).astype(int)
    passos = [matriz.astype(bool)]

    inicio = time.perf_counter()
    for i in range(iterations):
        matriz = iterate(matriz, sensitivity, border_treatment, peso)
        passos.append(matriz.astype(bool))
        if progress is not None:
            progress(i + 1, iterations)

    return passos, time.perf_counter() - inicio


def historico_dos_passos(passos: list) -> np.ndarray:
    """
        Células vivas em cada passo, como o histórico que cellular_automata devolve.
        passos: matrizes de cada passo.
    """
    return np.array([int(passo.sum()) for passo in passos], dtype=np.int64)


def salvar(execucao: Execucao, seeds_dir: Path = SEEDS_DIR,
           results_dir: Path = RESULTS_DIR) -> tuple[int, int]:
    """
        Grava a execução em results/ e, se a seed foi sorteada na hora, a seed em seeds/.
        Os campos são os mesmos de save_seed_matrix e run_and_save, então o menu e
        o plot leem o arquivo como se ele tivesse saído de lá.
        Devolve (seed_id, result_id).
        execucao: volume aberto na bancada.
        seeds_dir, results_dir: pastas de destino.
    """
    seeds_dir, results_dir = Path(seeds_dir), Path(results_dir)
    seed_id = execucao.seed_id
    if seed_id is None:
        seeds_dir.mkdir(parents=True, exist_ok=True)
        seed_id = next_seed_id(seeds_dir)
        np.savez_compressed(
            seed_path(seed_id, seeds_dir),
            matrix=execucao.seed.astype(int),
            seed_id=seed_id,
            size=execucao.lado,
            one_probability=execucao.one_probability,
        )

    # Resultados do CA básico não levam peso_id, igual ao run_and_save.
    extras = {"peso_id": execucao.peso_id} if execucao.peso_id is not None else {}

    results_dir.mkdir(parents=True, exist_ok=True)
    result_id = next_result_id(results_dir)
    np.savez_compressed(
        result_path(result_id, results_dir),
        matrix=execucao.final.astype(int),
        live_cells_history=np.asarray(execucao.historico, dtype=np.int64),
        result_id=result_id,
        seed_id=seed_id,
        size=execucao.lado,
        sensitivity=execucao.sensitivity,
        border_treatment=BorderTreatment(execucao.border_treatment).value,
        iterations=execucao.iterations,
        **extras,
    )

    return seed_id, result_id
