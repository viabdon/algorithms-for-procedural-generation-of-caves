"""Manipulações de um SDF pronto: deslocar o zero e comprimir com logaritmo.

São transformações do campo, não do gerador: o SDF é calculado em tools/sdf e
pode ser manipulado antes de virar peso do CA ou alvo do algoritmo genético.
Ficam no pacote (e não em tools/sdf) porque o CA e o GA também as usam, e o
pacote não importa de tools/.

As duas só crescem, então a ordem dos voxels não muda. Quando as duas entram,
a ordem é fixa (manipular_sdf): deslocar e depois comprimir, para o zero
continuar no limiar.
"""
import numpy as np


def deslocar_zero(sdf: np.ndarray, limiar: float) -> np.ndarray:
    """
        Passa o zero do campo para d = limiar: campo = d - limiar. Com limiar
        negativo o zero vai para fora da borda e tudo de dentro ganha |limiar|;
        com limiar positivo o zero entra na caverna. 0 devolve o mesmo campo.
        sdf: campo com sinal, em voxels.
        limiar: valor do SDF onde o zero passa a ficar, finito.
    """
    # NaN ou infinito passariam pela conta e estragariam o campo inteiro sem erro.
    if not np.isfinite(limiar):
        raise ValueError(f"O limiar precisa ser finito, veio {limiar}.")

    return (sdf - np.float32(limiar)).astype(np.float32)

def manipular_sdf(sdf: np.ndarray, limiar: float = 0.0,
                  escala_log: float | None = None) -> np.ndarray:
    """
        Aplica o limiar e depois o logaritmo, nesta ordem fixa. Deslocar antes
        mantém o zero exatamente no limiar, porque o log leva 0 em 0.
        sdf: campo com sinal, em voxels (o SDF base).
        limiar: valor do SDF onde o zero passa a ficar; 0 não desloca.
        escala_log: escala do comprimir_log; None não comprime.
    """
    campo = deslocar_zero(sdf, limiar)
    if escala_log is not None:
        campo = comprimir_log(campo, escala_log)
    return campo

def comprimir_log(sdf: np.ndarray, escala: float) -> np.ndarray:
    """
        Aplica escala * sinal(d) * ln(1 + |d|) ao SDF pronto. O 1 + |d| evita o
        infinito negativo em d = 0, e o sinal mantém o externo negativo, porque o
        logaritmo sozinho só enxerga a distância.
        A escala é o que mantém o guia funcionando: os vizinhos vão só até 27,
        então com escala 1 o peso mais forte do volume mal passa de -4 e a célula
        nasce em qualquer lugar. Com escala 2 o peso quase não muda até 3 voxels
        da superfície e cresce bem menos depois disso.
        sdf: campo com sinal, em voxels.
        escala: multiplicador do logaritmo, finito e maior que 0.
    """
    # NaN passaria por um "escala <= 0" e zeraria o volume do CA sem nenhum erro.
    if not np.isfinite(escala) or escala <= 0:
        raise ValueError(f"A escala do logaritmo precisa ser finita e maior que 0, veio {escala}.")

    return (escala * np.sign(sdf) * np.log1p(np.abs(sdf))).astype(np.float32)
