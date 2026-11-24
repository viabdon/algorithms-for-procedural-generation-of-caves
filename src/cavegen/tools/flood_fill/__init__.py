"""Inundação da grade a partir do exterior, com conectividade de seis faces."""

import numpy as np
from scipy.ndimage import binary_fill_holes


def inundar(cheio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
        Devolve (agua, buracos_fechados): os vazios ligados ao lado de fora da
        grade e os vazios que a água não alcança.
        cheio: matriz booleana (depth, height, width).
    """
    buracos_fechados = binary_fill_holes(cheio) & ~cheio
    agua = ~cheio & ~buracos_fechados
    return agua, buracos_fechados
