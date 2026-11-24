from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.generator import (
    BorderTreatment,
    ModoPeso,
    cellular_automata,
)
from cavegen.generators.cellular_automata.pesos import load_peso_matrix
from cavegen.generators.cellular_automata.seeds import load_seed_matrix
from cavegen.generators.cellular_automata.storage import build_path, next_id, storage_dir, used_ids
from cavegen.profiling.resource_tracker import track_resources

# Pasta onde os volumes ja processados pelo CA sao gravados, ao lado deste arquivo.
RESULTS_DIR = storage_dir("results")
RESULT_PREFIX = "result"

def config_do_run(argumentos: dict) -> str:
    """
        Rótulo da configuração de um run, para separar as linhas na planilha de recursos.
        Sem isso duas execuções do CA com parâmetros diferentes ficariam
        indistinguíveis na mesma tabela.
        argumentos: argumentos da chamada de run_and_save, por nome.
    """
    borda = BorderTreatment(argumentos["border_treatment"]).value
    peso_id = argumentos.get("peso_id")
    peso = f" peso{peso_id:03d}" if peso_id is not None else ""
    modo = ModoPeso(argumentos.get("modo_peso", ModoPeso.COMPLETO))
    if peso_id is not None and modo is ModoPeso.SO_NEGATIVO:
        peso += " so_negativo"
    return (f"seed{argumentos['seed_id']:03d} s{argumentos['sensitivity']} "
            f"{borda} it{argumentos['iterations']}{peso}")

def used_result_ids(directory: Path = RESULTS_DIR) -> set:
    """
        Números de 3 dígitos já ocupados por resultados na pasta.
        directory: pasta onde os resultados são gravados.
    """
    return used_ids(directory, RESULT_PREFIX)

def next_result_id(directory: Path = RESULTS_DIR) -> int:
    """
        Próximo número da sequência, um acima do maior já usado na pasta.
        directory: pasta onde os resultados são gravados.
    """
    return next_id(directory, RESULT_PREFIX)

def result_path(result_id: int, directory: Path = RESULTS_DIR) -> Path:
    """
        Caminho do arquivo de um resultado, no formato result_000.npz.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    return build_path(directory, RESULT_PREFIX, result_id)

@track_resources(label=config_do_run)
def run_and_save(seed_id: int, sensitivity: int, border_treatment: BorderTreatment,
                iterations: int, directory: Path = RESULTS_DIR, progress=None,
                peso_id: int | None = None,
                modo_peso: ModoPeso = ModoPeso.COMPLETO) -> Path:
    """
        Roda o CA sobre uma seed gravada e guarda o volume final em um npz novo.
        seed_id: número da seed usada como matriz inicial.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
        iterations: quantas vezes o passo é repetido.
        directory: pasta onde os resultados são gravados.
        progress: função opcional chamada ao fim de cada passo com (passo, iterations).
        peso_id: número do peso somado à contagem de vizinhos; None roda o CA básico.
        modo_peso: membro de ModoPeso, ou a string equivalente (só vale com peso).
    """
    modo_peso = ModoPeso(modo_peso)
    border_treatment = BorderTreatment(border_treatment)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    inicial = load_seed_matrix(seed_id)
    peso = load_peso_matrix(peso_id) if peso_id is not None else None
    final, historico, viraram_1, viraram_0 = cellular_automata(
        inicial, sensitivity, border_treatment, iterations, progress, peso, modo_peso)

    # Resultados do CA básico não levam peso_id, como as seeds sorteadas não levam origem.
    extras = {"peso_id": peso_id, "modo_peso": modo_peso.value} if peso_id is not None else {}

    result_id = next_result_id(directory)
    np.savez_compressed(
        result_path(result_id, directory),
        matrix=final,
        live_cells_history=historico,
        viraram_1_history=viraram_1,
        viraram_0_history=viraram_0,
        result_id=result_id,
        seed_id=seed_id,
        size=final.shape[0],
        sensitivity=sensitivity,
        border_treatment=border_treatment.value,
        iterations=iterations,
        **extras,
    )

    return result_path(result_id, directory)

def load_result_info(result_id: int, directory: Path = RESULTS_DIR) -> dict:
    """
        Lê só os parâmetros gravados no resultado, sem descomprimir a matriz.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    with np.load(result_path(result_id, directory)) as arquivo:
        info = {
            "result_id": int(arquivo["result_id"]),
            "seed_id": int(arquivo["seed_id"]),
            "size": int(arquivo["size"]),
            "sensitivity": int(arquivo["sensitivity"]),
            "border_treatment": str(arquivo["border_treatment"]),
            "iterations": int(arquivo["iterations"]),
        }

        # Só resultados rodados com peso trazem o peso_id.
        if "peso_id" in arquivo.files:
            info["peso_id"] = int(arquivo["peso_id"])
            # Resultados com peso gravados antes do modo existir usavam o peso completo.
            info["modo_peso"] = (str(arquivo["modo_peso"]) if "modo_peso" in arquivo.files
                                 else ModoPeso.COMPLETO.value)

        return info

def load_result(result_id: int, directory: Path = RESULTS_DIR) -> dict:
    """
        Lê de volta a matriz de um resultado junto dos parâmetros que o geraram.
        Resultados gravados antes de um histórico existir devolvem esse campo como
        None: live_cells_history, viraram_1_history e viraram_0_history.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    dados = load_result_info(result_id, directory)
    with np.load(result_path(result_id, directory)) as arquivo:
        dados["matrix"] = arquivo["matrix"]
        for campo in ("live_cells_history", "viraram_1_history", "viraram_0_history"):
            dados[campo] = arquivo[campo] if campo in arquivo.files else None

    return dados
