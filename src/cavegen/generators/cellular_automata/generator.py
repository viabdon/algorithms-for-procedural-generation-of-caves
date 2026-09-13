from enum import Enum

import numpy as np

class BorderTreatment(Enum):
    """
        Valores aceitos para o tratamento de borda.
        ZEROS: fora da matriz conta como 0, a borda tende a fechar.
        ONES: fora da matriz conta como 1, a borda tende a abrir.
        RANDOM: fora da matriz sorteia 0 ou 1 a cada vizinho consultado.
    """
    ZEROS = "zeros"
    ONES = "ones"
    RANDOM = "random"

def cellular_automata(matrix: np.ndarray, sensitivity: int, border_treatment: BorderTreatment, iterations: int) -> np.ndarray:
    """
        Aplica o autômato celular sobre a matriz, repetindo o passo N vezes.
        matrix: matriz binária inicial.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
        iterations: quantas vezes o passo é repetido.
    """
    border_treatment = BorderTreatment(border_treatment)

    for i in range(iterations):
        matrix = iterate(matrix, sensitivity, border_treatment)

    return matrix

def iterate(matrix: np.ndarray, sensitivity: int, border_treatment: BorderTreatment) -> np.ndarray:
    """
        Executa um único passo do autômato, gerando a matriz seguinte.
        matrix: matriz binária do passo anterior.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
    """
    border_treatment = BorderTreatment(border_treatment)
    temp_matrix = np.zeros(matrix.shape, dtype=int)

    for x in range(matrix.shape[0]):
        for y in range(matrix.shape[1]):
            for z in range(matrix.shape[2]):
                neighbors = count_neighbors(matrix, x, y, z, border_treatment)
                if neighbors >= sensitivity:
                    temp_matrix[x, y, z] = 1
                else:
                    temp_matrix[x, y, z] = 0

    return temp_matrix

def count_neighbors(matrix: np.ndarray, x: int, y: int, z: int, border_treatment: BorderTreatment) -> int:
    """
        Soma as células vivas no cubo 3x3x3 centrado em (x, y, z), incluindo a própria célula.
        matrix: matriz binária consultada.
        x, y, z: índices da célula analisada.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
    """
    border_treatment = BorderTreatment(border_treatment)
    depth, height, width = matrix.shape
    neighbors = 0

    for i in range(3):
        for j in range(3):
            for k in range(3):
                current_x = x + i - 1
                current_y = y + j - 1
                current_z = z + k - 1
                inside = 0 <= current_x < depth and 0 <= current_y < height and 0 <= current_z < width

                if inside:
                    neighbors = neighbors + matrix[current_x, current_y, current_z]
                    continue

                match border_treatment:
                    case BorderTreatment.ZEROS:
                        neighbors = neighbors + 0
                    case BorderTreatment.ONES:
                        neighbors = neighbors + 1
                    case BorderTreatment.RANDOM:
                        neighbors = neighbors + np.random.randint(0, 2)

    return neighbors