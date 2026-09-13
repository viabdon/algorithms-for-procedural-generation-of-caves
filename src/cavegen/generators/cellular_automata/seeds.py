from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.storage import build_path, next_id, storage_dir, used_ids

# Pasta onde as seeds do CA sao gravadas, ao lado deste arquivo.
SEEDS_DIR = storage_dir("seeds")
SEED_PREFIX = "seed"

def generate_seed_matrix(size: int, one_probability: float) -> np.ndarray:
    """
        Gera uma matriz binária cúbica (size x size x size).
        size: tamanho de cada lado da matriz.
        one_probability: chance (entre 0 e 1) de cada célula nascer como 1.
    """
    shape = (size, size, size)
    matrix = np.random.rand(*shape) < one_probability
    return matrix.astype(int)

def used_seed_ids(directory: Path = SEEDS_DIR) -> set:
    """
        Números de 3 dígitos já ocupados por seeds na pasta.
        directory: pasta onde as seeds são gravadas.
    """
    return used_ids(directory, SEED_PREFIX)

def next_seed_id(directory: Path = SEEDS_DIR) -> int:
    """
        Próximo número da sequência, um acima do maior já usado na pasta.
        directory: pasta onde as seeds são gravadas.
    """
    return next_id(directory, SEED_PREFIX)

def seed_path(seed_id: int, directory: Path = SEEDS_DIR) -> Path:
    """
        Caminho do arquivo de uma seed, no formato seed_000.npz.
        seed_id: número de identificação da seed.
        directory: pasta onde as seeds são gravadas.
    """
    return build_path(directory, SEED_PREFIX, seed_id)

def save_seed_matrix(size: int, one_probability: float, directory: Path = SEEDS_DIR) -> Path:
    """
        Gera uma matriz e grava em um npz novo, devolvendo o caminho do arquivo.
        size: tamanho de cada lado da matriz.
        one_probability: chance (entre 0 e 1) de cada célula nascer como 1.
        directory: pasta onde as seeds são gravadas.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    seed_id = next_seed_id(directory)
    matrix = generate_seed_matrix(size, one_probability)

    np.savez_compressed(
        seed_path(seed_id, directory),
        matrix=matrix,
        seed_id=seed_id,
        size=size,
        one_probability=one_probability,
    )

    return seed_path(seed_id, directory)

def load_seed_info(seed_id: int, directory: Path = SEEDS_DIR) -> dict:
    """
        Lê só os parâmetros gravados na seed, sem descomprimir a matriz.
        seed_id: número de identificação da seed.
        directory: pasta onde as seeds são gravadas.
    """
    with np.load(seed_path(seed_id, directory)) as arquivo:
        info = {
            "seed_id": int(arquivo["seed_id"]),
            "size": int(arquivo["size"]),
            "one_probability": float(arquivo["one_probability"]),
        }

        # Seeds nascidas de uma modificação trazem a origem; as sorteadas não.
        if "origem_seed_id" in arquivo.files:
            info["origem_seed_id"] = int(arquivo["origem_seed_id"])
            info["modificacao"] = str(arquivo["modificacao"])

        return info

def load_seed_matrix(seed_id: int, directory: Path = SEEDS_DIR) -> np.ndarray:
    """
        Lê de volta a matriz gravada em uma seed.
        seed_id: número de identificação da seed.
        directory: pasta onde as seeds são gravadas.
    """
    with np.load(seed_path(seed_id, directory)) as arquivo:
        return arquivo["matrix"]
