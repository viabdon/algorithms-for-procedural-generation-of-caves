"""Manipulações de um SDF pronto: deslocar o zero e comprimir com logaritmo.

São transformações do campo, não do gerador: o SDF é calculado em
cavegen/tools/sdf e pode ser manipulado antes de virar peso do CA ou alvo do
algoritmo genético. Ficam aqui, e não junto do cálculo, porque o CA e o GA
também as usam; vieram para cá quando a ferramenta do SDF ainda ficava fora
do pacote (tools/, até 22/11/2026).

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
        Aplica escala * sinal(d) * ln(1 + |d|) ao SDF pronto. O ln(d) sozinho não
        serve: não existe para d negativo (o externo) e vai a menos infinito em
        d = 0 (a borda). Por isso ele recebe só a distância |d|, o sinal volta no
        fim, e o 1 + leva a borda a ln(1) = 0. A compressão faz a distância
        grande pesar pouco mais que a pequena: no Elaphes, o voxel mais distante
        (d = -63,16) vale -4,16 em vez de -63,16, só 6 vezes o d = -1 (-0,69).
        sdf: campo com sinal, em voxels.
        escala: multiplicador do logaritmo, finito e maior que 0. A ferramenta
                aceita qualquer escala; o GA do CA usa sempre 1, fixa por decisão
                metodológica (ver o README do GA).
    """
    # NaN passaria por um "escala <= 0" e zeraria o volume do CA sem nenhum erro.
    if not np.isfinite(escala) or escala <= 0:
        raise ValueError(f"A escala do logaritmo precisa ser finita e maior que 0, veio {escala}.")

    return (escala * np.sign(sdf) * np.log1p(np.abs(sdf))).astype(np.float32)
