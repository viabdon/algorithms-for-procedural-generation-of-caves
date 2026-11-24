"""
    Resultados do experimento, numerados como os do CA, em
    cavegen/tools/random_walk_points/results/.

    Cada result_000.npz guarda a grade escavada, a classificação e todas as etapas
    da rede, para dar para plotar a progressão depois sem gerar de novo.

    O run não passa pelo track_resources de propósito: a planilha de recursos é
    a da comparação do TCC, e este experimento não entra nela.
"""
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.storage import build_path, next_id, used_ids
from cavegen.generators.random_walk.voxelizacao import classificar
from cavegen.tools.random_walk_points.generator import (
    K_PADRAO,
    LADO_PADRAO,
    N_PONTOS_PADRAO,
    PESO_ANGULO_ANTIGO,
    PESO_ANGULO_PADRAO,
    RAIO_PADRAO,
    SPACER_PADRAO,
    WEIGHT_PADRAO,
    Caminho,
    Rede,
    escavar_rede,
    gerar_rede,
    juntar_caminhos,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULT_PREFIX = "result"

# Parâmetros gravados em todo resultado, com o tipo em que voltam na leitura.
CAMPOS_INFO = {
    "result_id": int,
    "seed": int,
    "n_pontos": int,
    "size": int,
    "raio": float,
    "weight": float,
    "k": float,
    "spacer": float,
    "peso_angulo": float,
    "escala": float,
}

# Campos que resultados antigos não têm, com o valor que equivale ao que eles rodaram.
CAMPOS_ANTIGOS = {"peso_angulo": PESO_ANGULO_ANTIGO}

def used_result_ids(directory: Path = RESULTS_DIR) -> set:
    """
        Números de 3 dígitos já ocupados por resultados na pasta.
        directory: pasta onde os resultados são gravados.
    """
    return used_ids(directory, RESULT_PREFIX)

def result_path(result_id: int, directory: Path = RESULTS_DIR) -> Path:
    """
        Caminho do arquivo de um resultado, no formato result_000.npz.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    return build_path(directory, RESULT_PREFIX, result_id)

def run_and_save(seed: int, n_pontos: int = N_PONTOS_PADRAO, lado: int = LADO_PADRAO,
                 raio: float = RAIO_PADRAO, weight: float = WEIGHT_PADRAO, k: float = K_PADRAO,
                 spacer: float = SPACER_PADRAO, directory: Path = RESULTS_DIR,
                 peso_angulo: float = PESO_ANGULO_PADRAO) -> Path:
    """
        Gera a rede, escava a grade e guarda tudo em um npz novo.
        seed, n_pontos, lado, raio, weight, k, spacer, peso_angulo: os de gerar_rede.
        directory: pasta onde os resultados são gravados.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    rede = gerar_rede(seed, n_pontos, lado, raio, weight, k, spacer, peso_angulo)
    vazio, info = escavar_rede(rede, lado, raio)
    pontos, inicios = juntar_caminhos(rede.caminhos)
    nos = rede.nos
    soltos = [no for veio in rede.soltos for no in veio]
    fim_dos_soltos = np.cumsum([len(veio) for veio in rede.soltos], dtype=int)

    result_id = next_id(directory, RESULT_PREFIX)
    np.savez_compressed(
        result_path(result_id, directory),
        matrix=vazio,
        classificacao=classificar(vazio),
        pontos=rede.pontos,
        sources=rede.sources,
        targets=rede.targets,
        excluidos=rede.excluidos,
        caminho_pontos=pontos,
        caminho_inicios=inicios,
        caminho_origem=[c.origem for c in rede.caminhos],
        caminho_destino=[c.destino for c in rede.caminhos],
        caminho_etapa=[c.etapa for c in rede.caminhos],
        nos=np.array(nos, dtype=int),
        veios=np.array([rede.veio_de[no] for no in nos], dtype=int),
        central_nos=rede.central_nos,
        central_caminhos=rede.central_caminhos,
        soltos=np.array(soltos, dtype=int),
        fim_dos_soltos=fim_dos_soltos,
        result_id=result_id,
        seed=int(seed),
        n_pontos=n_pontos,
        size=lado,
        raio=raio,
        weight=weight,
        k=k,
        spacer=spacer,
        peso_angulo=peso_angulo,
        escala=info["escala"],
    )

    return result_path(result_id, directory)

def load_result_info(result_id: int, directory: Path = RESULTS_DIR) -> dict:
    """
        Lê só os parâmetros gravados no resultado. Resultado antigo, sem algum
        campo de CAMPOS_ANTIGOS, volta com o valor equivalente ao que ele rodou.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    with np.load(result_path(result_id, directory)) as arquivo:
        return {
            campo: tipo(arquivo[campo]) if campo in arquivo.files else CAMPOS_ANTIGOS[campo]
            for campo, tipo in CAMPOS_INFO.items()
        }

def load_result(result_id: int, directory: Path = RESULTS_DIR) -> dict:
    """
        Lê de volta a grade, a classificação e a rede, junto dos parâmetros.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    dados = load_result_info(result_id, directory)
    with np.load(result_path(result_id, directory)) as a:
        dados["matrix"] = a["matrix"]
        dados["classificacao"] = a["classificacao"]

        inicios = a["caminho_inicios"]
        caminhos = [
            Caminho(int(origem), int(destino), a["caminho_pontos"][inicios[i]:inicios[i + 1]],
                    int(etapa))
            for i, (origem, destino, etapa) in enumerate(
                zip(a["caminho_origem"], a["caminho_destino"], a["caminho_etapa"]))
        ]
        soltos = np.split(a["soltos"], a["fim_dos_soltos"][:-1]) if a["soltos"].size else []
        dados["rede"] = Rede(
            pontos=a["pontos"],
            sources=a["sources"],
            targets=a["targets"],
            excluidos=a["excluidos"],
            caminhos=caminhos,
            veio_de=dict(zip(a["nos"].tolist(), a["veios"].tolist())),
            central_nos=a["central_nos"].tolist(),
            central_caminhos=a["central_caminhos"].tolist(),
            soltos=[veio.tolist() for veio in soltos],
        )

    return dados
