from __future__ import annotations

from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Estrutura de um arquivo .f32
# ---------------------------------------------------------------------------
# O arquivo é um binário contendo uma sequência de números float32.
# Cada ponto da nuvem é descrito por 7 atributos, sempre nesta ordem:
#
#   [x_coord] [y_coord] [z_coord] [nir_reflectance] [red] [green] [blue]
#
# Portanto, o arquivo inteiro é:
#
#   ponto_1: x y z nir r g b | ponto_2: x y z nir r g b | ...
#
ATRIBUTOS_POR_PONTO = 7

INDICE_COLUNA_X = 0
INDICE_COLUNA_Y = 1
INDICE_COLUNA_Z = 2
INDICE_COLUNA_NIR = 3  # refletância no infravermelho próximo (sempre descartada)
INDICE_COLUNA_RED = 4
INDICE_COLUNA_GREEN = 5
INDICE_COLUNA_BLUE = 6

COLUNAS_XYZ = [INDICE_COLUNA_X, INDICE_COLUNA_Y, INDICE_COLUNA_Z]
COLUNAS_RGB = [INDICE_COLUNA_RED, INDICE_COLUNA_GREEN, INDICE_COLUNA_BLUE]


def load_f32_points(caminho_do_arquivo: str | Path, incluir_rgb: bool = False) -> np.ndarray:
    """Lê uma nuvem de pontos de um arquivo binário ``.f32``.

    O arquivo é uma sequência de ``float32`` com 7 atributos por ponto, nesta ordem::

        [x_coord] [y_coord] [z_coord] [nir_reflectance] [red] [green] [blue]

    Parameters
    ----------
    caminho_do_arquivo:
        Caminho para o arquivo ``.f32``.
    incluir_rgb:
        Se ``False`` (padrão), retorna apenas as coordenadas ``XYZ``.
        Se ``True``, retorna ``XYZ`` concatenado com ``RGB``.
        A refletância no infravermelho (NIR) é sempre descartada.

    Returns
    -------
    numpy.ndarray
        Array ``float32`` de forma ``(numero_de_pontos, 3)`` quando
        ``incluir_rgb=False`` ou ``(numero_de_pontos, 6)`` quando
        ``incluir_rgb=True``.
    """
    caminho_do_arquivo = Path(caminho_do_arquivo)

    # 1) Lê o arquivo inteiro como uma lista plana (1D) de números float32.
    valores_em_sequencia = np.fromfile(caminho_do_arquivo, dtype=np.float32)

    # 2) Decide quais colunas vamos manter no resultado final.
    if incluir_rgb:
        colunas_desejadas = COLUNAS_XYZ + COLUNAS_RGB
    else:
        colunas_desejadas = COLUNAS_XYZ

    # 3) Caso o arquivo esteja vazio, devolve um array vazio com o número
    #    correto de colunas, evitando erros mais à frente.
    if valores_em_sequencia.size == 0:
        numero_de_colunas = len(colunas_desejadas)
        return np.empty((0, numero_de_colunas), dtype=np.float32)

    # 4) Validação: a quantidade de números precisa ser múltipla de 7,
    #    senão o arquivo está corrompido ou não segue o formato esperado.
    quantidade_de_valores = valores_em_sequencia.size
    if quantidade_de_valores % ATRIBUTOS_POR_PONTO != 0:
        raise ValueError(
            f"Arquivo .f32 inválido: {quantidade_de_valores} valores não são "
            f"múltiplos de {ATRIBUTOS_POR_PONTO} atributos por ponto "
            f"({caminho_do_arquivo})."
        )

    # 5) Reorganiza a lista plana em uma tabela onde cada linha é um ponto
    #    e cada coluna é um atributo. O -1 deixa o numpy calcular o número
    #    de pontos automaticamente.
    tabela_de_pontos = valores_em_sequencia.reshape(-1, ATRIBUTOS_POR_PONTO)

    # 6) Seleciona apenas as colunas desejadas (XYZ, e opcionalmente RGB).
    pontos_filtrados = tabela_de_pontos[:, colunas_desejadas]
    return pontos_filtrados
