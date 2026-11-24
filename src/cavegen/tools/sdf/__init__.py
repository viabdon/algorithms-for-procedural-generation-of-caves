"""Escala de visualização dos campos de distância com sinal."""

import numpy as np

from cavegen.sdf.manipulacao import manipular_sdf

CORTE_NEGATIVO = -10.0


def corte_do_campo(limiar: float = 0.0, escala_log: float | None = None) -> float:
    """
        Valor do campo a CORTE_NEGATIVO voxels da borda, do lado de fora. Como as
        manipulações só crescem, o que passa do corte no campo é o que passava
        no SDF base.
        limiar, escala_log: os de manipular_sdf.
    """
    corte = np.array([CORTE_NEGATIVO], dtype=np.float32)
    return float(manipular_sdf(corte, limiar, escala_log)[0])

def opacidade(valor: float, maximo: float, corte: float = CORTE_NEGATIVO) -> float:
    """
        Rampa linear: o corte fica 100% transparente e o valor mais positivo
        fica opaco.
        valor: nível do campo.
        maximo: maior valor do campo.
        corte: valor do campo onde a opacidade é 0.
    """
    return (valor - corte) / (maximo - corte)
