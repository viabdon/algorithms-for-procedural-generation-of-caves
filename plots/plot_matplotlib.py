"""Plotagem 3D da caverna com Matplotlib (figura estática para o TCC).

Os dados vêm prontos de matriz.py — aqui só se desenha.

    uv run python plots/plot_matplotlib.py
    uv run python plots/plot_matplotlib.py results/volumes/cellular_automata_seed_0.npz
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt

# Permite rodar tanto como "python plots/plot_matplotlib.py" quanto
# "python -m plots.plot_matplotlib".
sys.path.append(str(Path(__file__).resolve().parent))

from matriz import MatrizVoxels, caminho_da_figura, caminho_do_argumento, preparar_matriz


def plotar(matriz: MatrizVoxels, salvar: bool = True, mostrar: bool = True) -> Path | None:
    figura = plt.figure(figsize=(8, 8))
    eixos_3d = figura.add_subplot(111, projection="3d")

    pontos = eixos_3d.scatter(
        matriz.coordenada_x,
        matriz.coordenada_y,
        matriz.coordenada_z,
        c=matriz.coordenada_z,  # colore pela profundidade, ajuda a dar noção 3D
        cmap="viridis",         # escala sequencial: claro = raso, escuro = fundo
        marker="s",             # quadradinho, fica mais parecido com voxel
        s=6,
        alpha=0.6,
    )

    eixos_3d.set_title(matriz.titulo)
    eixos_3d.set_xlabel("X (width)")
    eixos_3d.set_ylabel("Y (height)")
    eixos_3d.set_zlabel("Z (depth)")

    # Mantém os 3 eixos na mesma escala para a caverna não ficar distorcida.
    eixos_3d.set_box_aspect(matriz.proporcao_eixos)

    barra_de_cores = figura.colorbar(pontos, ax=eixos_3d, shrink=0.6, pad=0.1)
    barra_de_cores.set_label("Z (depth)")

    figura.tight_layout()

    destino = None
    if salvar:
        destino = caminho_da_figura(matriz, "3d_matplotlib", "png")
        figura.savefig(destino, dpi=130)

    if mostrar:
        # Abre a janela interativa, onde dá para girar a caverna com o mouse.
        plt.show()
    else:
        plt.close(figura)

    return destino


if __name__ == "__main__":
    matriz_voxels = preparar_matriz(caminho_do_argumento())
    print(matriz_voxels.resumo())
    arquivo_gerado = plotar(matriz_voxels)
    print("figura salva em:", arquivo_gerado)
