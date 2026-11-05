"""
    Resultados do random walk gravados pelo menu, numerados como os do CA.

    Cada result_000.npz guarda a grade escavada (matrix, True = vazio), a
    classificação auxiliar (0 fora, 1 borda, 2 interno), os caminhos e os
    waypoints, para dar para plotar depois sem gerar de novo, e os parâmetros
    que geraram a caverna.
"""
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.storage import build_path, next_id, used_ids
from cavegen.generators.random_walk.cena import Grafo
from cavegen.generators.random_walk.generator import CAVERNA_PADRAO, gerar_caverna
from cavegen.generators.random_walk.voxelizacao import LADO_PADRAO, RAIO_PADRAO, classificar
from cavegen.profiling.resource_tracker import track_resources

# Pasta onde os resultados do RW são gravados, ao lado deste arquivo.
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULT_PREFIX = "result"

# Parâmetros gravados em todo resultado, com o tipo em que voltam na leitura.
CAMPOS_INFO = {
    "result_id": int,
    "caverna": str,
    "seed": int,
    "size": int,
    "weight": float,
    "k": float,
    "spacer": float,
    "radius": float,
    "raio_voxels": float,
    "raio_proporcional": float,
    "escala": float,
}

def config_do_run(argumentos: dict) -> str:
    """
        Rótulo da configuração de um run, para separar as linhas na planilha de recursos.
        argumentos: argumentos da chamada de run_and_save, por nome.
    """
    raio = argumentos.get("raio_voxels", RAIO_PADRAO)
    trocas = "".join(f" {p}{argumentos[p]:g}" for p in ("weight", "k", "spacer")
                     if argumentos.get(p) is not None)
    return (f"{argumentos.get('caverna', CAVERNA_PADRAO)} seed{argumentos['seed']} "
            f"{argumentos.get('lado', LADO_PADRAO)}^3 "
            f"r{'proporcional' if raio is None else f'{raio:g}'}{trocas}")

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

@track_resources(label=config_do_run)
def run_and_save(seed: int, caverna: str = CAVERNA_PADRAO, lado: int = LADO_PADRAO,
                 raio_voxels: float | None = RAIO_PADRAO, weight: float | None = None,
                 k: float | None = None, spacer: float | None = None,
                 directory: Path = RESULTS_DIR) -> Path:
    """
        Gera a caverna e guarda tudo em um npz novo.
        seed: seed do numpy_rng.
        caverna, lado, raio_voxels, weight, k, spacer: os de gerar_caverna.
        directory: pasta onde os resultados são gravados.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    gerada = gerar_caverna(lado, seed, caverna, weight, k, spacer, raio_voxels)
    p = gerada.grafo.parametros

    result_id = next_id(directory, RESULT_PREFIX)
    np.savez_compressed(
        result_path(result_id, directory),
        matrix=gerada.vazio,
        classificacao=classificar(gerada.vazio),
        pontos=gerada.pontos,
        inicios=gerada.inicios,
        waypoints=gerada.grafo.posicoes,
        nomes=np.array(gerada.grafo.nomes),
        arestas=gerada.grafo.arestas,
        deslocamento=gerada.info["deslocamento"],
        result_id=result_id,
        caverna=gerada.grafo.nome,
        seed=int(seed),
        size=lado,
        weight=p["weight"],
        k=p["k"],
        spacer=p["spacer"],
        radius=p["radius"],
        raio_voxels=gerada.info["raio_voxels"],
        raio_proporcional=gerada.info["raio_proporcional"],
        escala=gerada.info["escala"],
    )

    return result_path(result_id, directory)

def load_result_info(result_id: int, directory: Path = RESULTS_DIR) -> dict:
    """
        Lê só os parâmetros gravados no resultado, sem descomprimir as matrizes.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    with np.load(result_path(result_id, directory)) as arquivo:
        return {campo: tipo(arquivo[campo]) for campo, tipo in CAMPOS_INFO.items()}

def load_result(result_id: int, directory: Path = RESULTS_DIR) -> dict:
    """
        Lê de volta a grade, a classificação e os caminhos junto dos parâmetros.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
    """
    dados = load_result_info(result_id, directory)
    with np.load(result_path(result_id, directory)) as arquivo:
        for campo in ("matrix", "classificacao", "pontos", "inicios", "deslocamento"):
            dados[campo] = arquivo[campo]
        dados["grafo"] = Grafo(
            nome=dados["caverna"],
            nomes=[str(n) for n in arquivo["nomes"]],
            posicoes=arquivo["waypoints"],
            arestas=arquivo["arestas"],
            parametros={p: dados[p] for p in ("weight", "k", "spacer", "radius")},
        )

    return dados
