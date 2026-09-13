"""Modificacoes pontuais em uma seed ja gravada.

Cada modificacao le uma seed existente, aplica a alteracao e grava o resultado
como uma seed nova, na proxima posicao da sequencia. A seed de origem nunca e
sobrescrita, entao da para rodar o CA sobre as duas e comparar o efeito da
estrutura introduzida.

A seed nova registra de quem veio e o que foi feito, do mesmo jeito que um
resultado registra os parametros que o geraram.
"""

from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.seeds import (
    SEEDS_DIR,
    load_seed_info,
    load_seed_matrix,
    next_seed_id,
    seed_path,
)

ESPESSURA_PADRAO = 3

# A coluna atravessa o eixo 2, que e o que aparece de pe na plotagem: a figura
# mostra a coluna em pe, do topo ao fundo do cubo.
EIXO_COLUNA = 2

def faixa_central(tamanho: int, espessura: int) -> slice:
    """
        Índices que centralizam uma faixa de N células ao longo de um lado.
        tamanho: lado do cubo, em células.
        espessura: largura da faixa.
    """
    inicio = (tamanho - espessura) // 2
    return slice(inicio, inicio + espessura)

def add_center_column(seed_id: int, thickness: int = ESPESSURA_PADRAO,
                      directory: Path = SEEDS_DIR) -> Path:
    """
        Crava uma coluna de rocha atravessando a seed pelo centro, como seed nova.
        A coluna tem seção quadrada, é centrada nos outros dois eixos e vai de
        ponta a ponta do eixo 2.
        seed_id: número da seed usada como origem.
        thickness: lado da seção quadrada da coluna, em células.
        directory: pasta onde as seeds são gravadas.
    """
    matrix = load_seed_matrix(seed_id, directory)
    origem = load_seed_info(seed_id, directory)
    lado = origem["size"]

    if thickness < 1 or thickness > lado:
        raise ValueError(f"A espessura precisa ficar entre 1 e {lado}, recebeu {thickness}.")

    faixa = faixa_central(lado, thickness)
    matrix[faixa, faixa, :] = 1

    novo_id = next_seed_id(directory)
    np.savez_compressed(
        seed_path(novo_id, directory),
        matrix=matrix,
        seed_id=novo_id,
        size=lado,
        one_probability=origem["one_probability"],
        origem_seed_id=seed_id,
        modificacao=f"coluna central {thickness}x{thickness}",
    )

    return seed_path(novo_id, directory)

def celulas_da_coluna(lado: int, thickness: int) -> int:
    """
        Quantas células a coluna ocupa no volume.
        lado: lado do cubo, em células.
        thickness: lado da seção quadrada da coluna.
    """
    return thickness * thickness * lado
