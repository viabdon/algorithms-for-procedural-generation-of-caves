import numpy as np
import matplotlib.pyplot as plt

from cavegen.io.voxel_io import load_volume_npz

# 1) Carrega o volume booleano gerado pelo algoritmo.
volume = load_volume_npz("results/volumes/random_walk_seed_0.npz")
print(volume.shape, "voxels abertos:", volume.open_voxels, "fill:", volume.fill_ratio)

# 2) Pega as coordenadas de TODOS os voxels abertos (onde data == True).
#    argwhere devolve uma tabela (N, 3) com uma linha por voxel aberto,
#    nas colunas (z, y, x) seguindo a convenção (depth, height, width).
coordenadas_abertas = np.argwhere(volume.data)
coordenada_z = coordenadas_abertas[:, 0]
coordenada_y = coordenadas_abertas[:, 1]
coordenada_x = coordenadas_abertas[:, 2]

# 3) Monta a figura 3D e desenha cada voxel aberto como um ponto.
figura = plt.figure(figsize=(8, 8))
eixos_3d = figura.add_subplot(111, projection="3d")
eixos_3d.scatter(
    coordenada_x,
    coordenada_y,
    coordenada_z,
    c=coordenada_z,        # colore os pontos pela profundidade, ajuda a dar noção 3D
    cmap="viridis",
    marker="s",            # quadradinho, fica mais parecido com voxel
    s=6,                   # tamanho do ponto
    alpha=0.6,
)

eixos_3d.set_title("Caverna gerada (todos os voxels abertos)")
eixos_3d.set_xlabel("X (width)")
eixos_3d.set_ylabel("Y (height)")
eixos_3d.set_zlabel("Z (depth)")

# Deixa os 3 eixos na mesma escala para a caverna não ficar distorcida.
eixos_3d.set_box_aspect(volume.shape[::-1])  # (x, y, z) = (width, height, depth)

plt.tight_layout()

# Salva uma imagem em disco (útil para inspecionar/colocar no TCC)...
figura.savefig("results/figures/random_walk_seed_0_3d.png", dpi=130)
# ...e também abre a janela interativa, onde dá para girar a caverna com o mouse.
plt.show()
