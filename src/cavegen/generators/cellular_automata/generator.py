from enum import Enum

import numpy as np
from scipy.ndimage import convolve

# Cubo 3x3x3 de uns: a contagem soma a vizinhança inteira de uma célula de uma
# vez só. O centro vale 1, então a própria célula entra na própria soma, que é o
# comportamento que a versão em laço tinha. Zerar o centro (contar 26 vizinhos em
# vez de 27 células) é uma mudança de regra, não de implementação, e por isso
# fica para uma decisão separada.
KERNEL_VIZINHANCA = np.ones((3, 3, 3), dtype=np.int16)

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

def cellular_automata(matrix: np.ndarray, sensitivity: int, border_treatment: BorderTreatment, iterations: int, progress=None) -> tuple[np.ndarray, np.ndarray]:
    """
        Aplica o autômato celular sobre a matriz, repetindo o passo N vezes.
        Devolve a matriz final e a quantidade de células vivas em cada passo,
        começando pela matriz inicial (passo 0), então o histórico tem iterations + 1 valores.
        matrix: matriz binária inicial.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
        iterations: quantas vezes o passo é repetido.
        progress: função opcional chamada ao fim de cada passo com (passo, iterations).
    """
    border_treatment = BorderTreatment(border_treatment)
    historico = [int(matrix.sum())]

    for i in range(iterations):
        matrix = iterate(matrix, sensitivity, border_treatment)
        historico.append(int(matrix.sum()))
        if progress is not None:
            progress(i + 1, iterations)

    return matrix, np.array(historico, dtype=np.int64)

def iterate(matrix: np.ndarray, sensitivity: int, border_treatment: BorderTreatment) -> np.ndarray:
    """
        Executa um único passo do autômato, gerando a matriz seguinte.
        matrix: matriz binária do passo anterior.
        sensitivity: mínimo de vizinhos para a célula virar 1.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
    """
    vizinhos = neighbor_counts(matrix, border_treatment)

    return (vizinhos >= sensitivity).astype(int)

def neighbor_counts(matrix: np.ndarray, border_treatment: BorderTreatment) -> np.ndarray:
    """
        Soma, para cada célula, as células vivas no cubo 3x3x3 centrado nela.
        Devolve uma matriz de inteiros do mesmo tamanho da entrada, onde cada
        posição é a soma da vizinhança daquela célula.
        matrix: matriz binária consultada.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
    """
    border_treatment = BorderTreatment(border_treatment)
    moldurada = aplicar_moldura(matrix, border_treatment)
    # A moldura já fornece todo vizinho de fora de que as células originais
    # precisam, então o modo de borda da convolução só afeta a própria moldura,
    # que é descartada no recorte.
    somas = convolve(moldurada, KERNEL_VIZINHANCA, mode="constant", cval=0)

    return somas[1:-1, 1:-1, 1:-1]

def aplicar_moldura(matrix: np.ndarray, border_treatment: BorderTreatment) -> np.ndarray:
    """
        Envolve a matriz com uma camada de 1 célula representando o lado de fora.
        Tratar a borda como dado, e não como caso especial da contagem, é o que
        deixa os três tratamentos passarem pelo mesmo caminho de código.
        matrix: matriz binária a ser envolvida.
        border_treatment: membro de BorderTreatment, ou a string equivalente.
    """
    border_treatment = BorderTreatment(border_treatment)
    tamanho_com_moldura = tuple(dimensao + 2 for dimensao in matrix.shape)

    if border_treatment is BorderTreatment.RANDOM:
        moldurada = np.random.randint(0, 2, size=tamanho_com_moldura).astype(np.int16)
    else:
        valor = 1 if border_treatment is BorderTreatment.ONES else 0
        moldurada = np.full(tamanho_com_moldura, valor, dtype=np.int16)

    moldurada[1:-1, 1:-1, 1:-1] = matrix

    return moldurada
