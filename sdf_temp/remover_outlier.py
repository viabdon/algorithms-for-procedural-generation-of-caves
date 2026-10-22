"""
    Remove voxels soltos do npz base do Elaphes e refaz o plot dele.

    O voxel do plot (13, 60, 31) é o único da grade sem nenhum dos 26 vizinhos
    cheios: um ponto perdido longe da caverna.

    Rodar de novo não muda nada: se o voxel já for 0, só refaz o plot.

    uv run python sdf_temp/remover_outlier.py
"""
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.plot import figura_volumetrica

PASTA = Path(__file__).resolve().parent
BASE = PASTA / "entrada" / "elaphes_surface_64.npz"
PLOT = PASTA / "plots" / "elaphes_surface_64.html"

# Coordenadas como aparecem no hover do plot: (x, y, z) = (largura, profundidade, altura).
OUTLIERS_NO_PLOT = [(13, 60, 31)]

def indice_na_grade(x: int, y: int, z: int) -> tuple[int, int, int]:
    """
        Converte a coordenada do plot para o índice da grade (depth, height, width).
    """
    return y, z, x

def main():
    dados = dict(np.load(BASE))
    superficie = dados["surface_voxels"]

    for ponto in OUTLIERS_NO_PLOT:
        indice = indice_na_grade(*ponto)
        print(f"plot {ponto} -> grade {indice}: era {int(superficie[indice])}, agora 0")
        superficie[indice] = 0

    np.savez_compressed(BASE, **dados)

    # Mesmo estilo do plot de referência: Jet, cor pela altura, limites fixos.
    indices = np.argwhere(superficie)
    x, y, z = indices[:, 2], indices[:, 0], indices[:, 1]
    profundidade, altura, largura = superficie.shape
    figura = figura_volumetrica(
        x, y, z, z,
        f"Elaphes {largura}x{altura}x{profundidade} - superficie observada - {x.size} voxels",
        minimos=[-0.5, -0.5, -0.5],
        maximos=[largura - 0.5, profundidade - 0.5, altura - 0.5],
        rotulo_escala="altura (y)",
        limites_cor=(0, altura - 1),
    )
    PLOT.parent.mkdir(exist_ok=True)
    figura.write_html(PLOT, include_plotlyjs="cdn")
    print(f"{x.size} voxels, figura salva em {PLOT}")

if __name__ == "__main__":
    main()
