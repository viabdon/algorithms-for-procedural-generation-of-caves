import numpy as np

def generate_seed_matrix(size: int, one_probability: float) -> np.ndarray:
    """
        Gera uma matriz binária cúbica (size x size x size).
        size: tamanho de cada lado da matriz.
        one_probability: chance (entre 0 e 1) de cada célula nascer como 1.
    """
    shape = (size, size, size)
    matrix = np.random.rand(*shape) < one_probability
    return matrix.astype(int)
