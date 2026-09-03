import numpy as np

def cellular_automata(matrix: np.ndarray, sensitivity: int, border_treatment: str, iterations: int) -> np.ndarray:
    """
        Aplica o autômato celular sobre a matriz, repetindo o passo N vezes.
        matrix: matriz binária inicial.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: estratégia de borda, ainda sem efeito (ver TODO em count_neighbors).
        iterations: quantas vezes o passo é repetido.
    """
    for i in range(iterations):
        matrix = iterate(matrix, sensitivity, border_treatment)

    return matrix

def iterate(matrix: np.ndarray, sensitivity: int, border_treatment: str) -> np.ndarray:
    """
        Executa um único passo do autômato, gerando a matriz seguinte.
        matrix: matriz binária do passo anterior.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: estratégia de borda, ainda sem efeito (ver TODO em count_neighbors).
    """
    temp_matrix = np.zeros(matrix.shape, dtype=int)

    for x in range(matrix.shape[0]):
        for y in range(matrix.shape[1]):
            for z in range(matrix.shape[2]):
                neighbors = count_neighbors(matrix, x, y, z)
                if neighbors >= sensitivity:
                    temp_matrix[x, y, z] = 1
                else:
                    temp_matrix[x, y, z] = 0

    return temp_matrix

def count_neighbors(matrix: np.ndarray, x: int, y: int, z: int) -> int:
    """
        Soma as células vivas no cubo 3x3x3 centrado em (x, y, z), incluindo a própria célula.
        matrix: matriz binária consultada.
        x, y, z: índices da célula analisada.
    """
    neighbors = 0
    base = np.array([x, y, z])

    for i in range(3):
        for j in range(3):
            for k in range(3):
                offset = np.array([i - 1, j - 1, k - 1])
                current = base + offset

                if (current < 0).any() or (current >= matrix.shape).any():
                    # COLOCAR TRATAMENTO DE BORDA AQUI
                    neighbors = neighbors + 0
                else:
                    neighbors = neighbors + matrix[tuple(current)]

    return neighbors