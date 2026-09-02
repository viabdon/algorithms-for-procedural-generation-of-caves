import numpy as np

# test matrix
matrix = np.zeros((5, 5, 5), dtype=int)
matrix[1, 1, 1] = 1
matrix[1, 1, 2] = 1
matrix[1, 2, 1] = 1
matrix[2, 1, 1] = 1
matrix[2, 2, 2] = 1
print(matrix)
print(matrix.shape)

index = np.array([0, 0, 0])
print(index)
print(matrix[tuple(index)]) 

def cellular_automata(matrix):
    temp_matrix = np.zeros(matrix.shape, dtype=int)
    
    for x in range(matrix.shape[0]):
        for y in range(matrix.shape[1]):
            for z in range(matrix.shape[2]):
                neighbors = count_neighbors(matrix, x, y, z)
                if neighbors >= 4: # TROCAR O VALOR POR UMA PARAMETRO DA FUNÇÃO
                    temp_matrix[x, y, z] = 1
                else:
                    temp_matrix[x, y, z] = 0

    return temp_matrix

def count_neighbors(matrix, x, y, z):
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

print(cellular_automata(matrix))
