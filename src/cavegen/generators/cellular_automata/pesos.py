"""Pesos do CA: matrizes somadas à contagem de vizinhos, como o SDF.

Um peso é uma cópia do SDF guardada ao lado das seeds, com a origem e a
convenção de sinal anotadas. O SDF original continua onde foi calculado.

    uv run python -m cavegen.generators.cellular_automata.pesos [caminho_do_sdf.npz]
"""
import sys
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.storage import build_path, next_id, storage_dir, used_ids

# Pasta onde os pesos do CA sao gravados, ao lado deste arquivo.
PESOS_DIR = storage_dir("pesos")
PESO_PREFIX = "peso"

RAIZ_DO_PROJETO = Path(__file__).resolve().parents[4]
# SDF do Elaphes calculado no sdf_temp: a origem padrão da importação.
SDF_ELAPHES = RAIZ_DO_PROJETO / "sdf_temp" / "npz" / "elaphes_surface_64_sdf.npz"

def used_peso_ids(directory: Path = PESOS_DIR) -> set:
    """
        Números de 3 dígitos já ocupados por pesos na pasta.
        directory: pasta onde os pesos são gravados.
    """
    return used_ids(directory, PESO_PREFIX)

def peso_path(peso_id: int, directory: Path = PESOS_DIR) -> Path:
    """
        Caminho do arquivo de um peso, no formato peso_000.npz.
        peso_id: número de identificação do peso.
        directory: pasta onde os pesos são gravados.
    """
    return build_path(directory, PESO_PREFIX, peso_id)

def caminho_legivel(caminho: Path) -> str:
    """
        Caminho relativo à raiz do projeto quando está dentro dela, para a origem
        gravada no peso não depender da máquina.
        caminho: arquivo de origem.
    """
    caminho = Path(caminho).resolve()
    try:
        return caminho.relative_to(RAIZ_DO_PROJETO).as_posix()
    except ValueError:
        return caminho.as_posix()

def importar_sdf(origem: Path = SDF_ELAPHES, directory: Path = PESOS_DIR) -> Path:
    """
        Copia o SDF de um npz para um peso novo e devolve o caminho do arquivo.
        origem: npz com o campo "sdf" (o de sdf_temp/sdf.py, por padrão).
        directory: pasta onde os pesos são gravados.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    with np.load(origem) as arquivo:
        matrix = arquivo["sdf"].astype(np.float32)
        convencao = str(arquivo["convencao"]) if "convencao" in arquivo.files else ""

    peso_id = next_id(directory, PESO_PREFIX)
    np.savez_compressed(
        peso_path(peso_id, directory),
        matrix=matrix,
        peso_id=peso_id,
        shape=np.array(matrix.shape),
        origem=caminho_legivel(origem),
        convencao=convencao,
    )

    return peso_path(peso_id, directory)

def load_peso_info(peso_id: int, directory: Path = PESOS_DIR) -> dict:
    """
        Lê só os dados gravados no peso, sem descomprimir a matriz.
        peso_id: número de identificação do peso.
        directory: pasta onde os pesos são gravados.
    """
    with np.load(peso_path(peso_id, directory)) as arquivo:
        return {
            "peso_id": int(arquivo["peso_id"]),
            "shape": tuple(int(lado) for lado in arquivo["shape"]),
            "origem": str(arquivo["origem"]),
            "convencao": str(arquivo["convencao"]),
        }

def load_peso_matrix(peso_id: int, directory: Path = PESOS_DIR) -> np.ndarray:
    """
        Lê de volta a matriz gravada em um peso.
        peso_id: número de identificação do peso.
        directory: pasta onde os pesos são gravados.
    """
    with np.load(peso_path(peso_id, directory)) as arquivo:
        return arquivo["matrix"]

def main():
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else SDF_ELAPHES
    destino = importar_sdf(origem)
    info = load_peso_info(int(destino.stem[-3:]))
    print(f"peso gravado: {destino}")
    print(f"origem: {info['origem']}, formato {info['shape']}, {info['convencao']}")

if __name__ == "__main__":
    main()
