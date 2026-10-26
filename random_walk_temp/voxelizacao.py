"""
    Voxeliza os caminhos do random walk numa grade cúbica (depth, height, width).

    No projeto base o caminho vira uma malha: um tubo de raio radius com
    segments lados em volta de cada trecho. Aqui o tubo é escavado direto na
    grade: todo voxel cujo centro fica a até raio do trecho entre dois pontos
    seguidos vira vazio (uma cápsula por trecho). Com segments = 6 o tubo do
    original é um hexágono; a cápsula é a versão redonda dele.

    Eixos: a Unity tem y para cima, então depth = z, height = y e width = x
    da Unity. A caverna inteira é encaixada na grade com a mesma escala nos
    três eixos e centralizada, com MARGEM voxels de folga em volta.

    Raio: RAIO_PADRAO voxels, escolhido para o 64³. Encaixando a caverna
    inteira no cubo, o radius da cena (7) vira 0,2 a 0,3 voxel e o túnel some
    abaixo do tamanho do voxel; com 1,5 a caverna fica com a ordem de grandeza
    de vazios do Elaphes e com um pouco de interno para o SDF positivo.
    Com "proporcional" no lugar do raio, vale o radius convertido pela escala,
    com o mínimo de meia diagonal do voxel (√3/2): com ele todo ponto do
    caminho tem um centro de voxel ao alcance e o caminho não se parte.

    Classificação, nos mesmos códigos da inundação do sdf_temp, para o SDF
    seguir igual:
    0: fora da caverna (rocha).
    1: borda, vazio que encosta em rocha por alguma face.
    2: interno, vazio que não encosta em rocha.
    Fora da grade conta como rocha.

    uv run python random_walk_temp/voxelizacao.py [seed] [lado] [raio_em_voxels|proporcional]
"""
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_erosion

from cavegen.generators.cellular_automata.plot import figura_volumetrica

from caminhada import PASTA_NPZ, PASTA_PLOTS, SEED_PADRAO

FORA = 0
BORDA = 1
INTERNO = 2

LADO_PADRAO = 64
MARGEM = 2
RAIO_PADRAO = 1.5
RAIO_MINIMO = np.sqrt(3) / 2

# Cruz 3D: borda é o vazio com algum vizinho de face fora da caverna.
VIZINHANCA_FACES = np.zeros((3, 3, 3), dtype=bool)
VIZINHANCA_FACES[1, 1, :] = VIZINHANCA_FACES[1, :, 1] = VIZINHANCA_FACES[:, 1, 1] = True

def para_grade(pontos: np.ndarray) -> np.ndarray:
    """
        Troca os eixos da Unity (x, y, z) para a ordem da grade (depth, height, width).
        pontos: array (n, 3) nos eixos da Unity.
    """
    return pontos[:, [2, 1, 0]]

def encaixe(pontos: np.ndarray, raio: float, lado: int) -> tuple[float, np.ndarray]:
    """
        Escala e deslocamento que levam a caverna (com o raio do tubo) para dentro da grade.
        Devolve (escala, deslocamento): indice = ponto * escala + deslocamento.
        pontos: caminhos já na ordem da grade.
        raio: raio do tubo na unidade da Unity.
        lado: lado da grade cúbica.
    """
    minimos = pontos.min(axis=0) - raio
    maximos = pontos.max(axis=0) + raio
    escala = (lado - 1 - 2 * MARGEM) / float((maximos - minimos).max())
    # Centraliza: a sobra de cada eixo fica dividida entre os dois lados.
    sobra = (lado - 1) - (maximos - minimos) * escala
    deslocamento = sobra / 2 - minimos * escala
    return escala, deslocamento

def escavar_trecho(vazio: np.ndarray, a: np.ndarray, b: np.ndarray, raio: float) -> None:
    """
        Marca como vazio os voxels a até raio do segmento de a até b (uma cápsula).
        vazio: grade booleana, alterada no lugar.
        a, b: pontas do trecho, em coordenadas de índice.
        raio: raio do tubo, em voxels.
    """
    baixo = np.maximum(np.floor(np.minimum(a, b) - raio).astype(int), 0)
    alto = np.minimum(np.ceil(np.maximum(a, b) + raio).astype(int) + 1, vazio.shape)
    centros = np.stack(np.meshgrid(*(np.arange(i, f) for i, f in zip(baixo, alto)),
                                   indexing="ij"), axis=-1).astype(float)

    trecho = b - a
    comprimento2 = float(trecho @ trecho)
    t = np.zeros(centros.shape[:-1]) if comprimento2 == 0 else \
        np.clip(((centros - a) @ trecho) / comprimento2, 0, 1)
    mais_perto = a + t[..., None] * trecho
    dentro = np.linalg.norm(centros - mais_perto, axis=-1) <= raio

    janela = tuple(slice(i, f) for i, f in zip(baixo, alto))
    vazio[janela] |= dentro

def voxelizar(pontos: np.ndarray, inicios: np.ndarray, raio_unity: float, lado: int,
              raio_voxels: float | None = None) -> tuple[np.ndarray, dict]:
    """
        Escava os caminhos numa grade lado³ e devolve (vazio, info).
        pontos, inicios: caminhos gravados pela caminhada (eixos da Unity).
        raio_unity: radius do CaveGenerator.
        lado: lado da grade.
        raio_voxels: força o raio em voxels; None usa o radius convertido pela escala.
    """
    na_grade = para_grade(pontos)
    escala, deslocamento = encaixe(na_grade, raio_unity, lado)
    proporcional = raio_unity * escala
    raio = raio_voxels if raio_voxels is not None else max(proporcional, RAIO_MINIMO)

    indices = na_grade * escala + deslocamento
    vazio = np.zeros((lado, lado, lado), dtype=bool)
    for inicio, fim in pairwise(inicios):
        caminho = indices[inicio:fim]
        for a, b in pairwise(caminho):
            escavar_trecho(vazio, a, b, raio)

    info = dict(escala=escala, deslocamento=deslocamento, raio_voxels=raio,
                raio_proporcional=proporcional)
    return vazio, info

def classificar(vazio: np.ndarray) -> np.ndarray:
    """
        0 fora, 1 borda e 2 interno, como a inundação do sdf_temp.
        vazio: grade booleana da caverna.
    """
    # border_value=0: o que está fora da grade é rocha, então o vazio na beira é borda.
    interno = binary_erosion(vazio, structure=VIZINHANCA_FACES, border_value=0)
    classificacao = np.full(vazio.shape, FORA, dtype=np.uint8)
    classificacao[vazio] = BORDA
    classificacao[interno] = INTERNO
    return classificacao

def caminho_classificacao(caminhos: Path, lado: int) -> Path:
    """
        Arquivo da classificação, ao lado do npz dos caminhos.
        caminhos: npz gravado pela caminhada.
        lado: lado da grade.
    """
    return caminhos.with_name(caminhos.name.replace("_caminhos", f"_{lado}_classificacao"))

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else SEED_PADRAO
    lado = int(sys.argv[2]) if len(sys.argv) > 2 else LADO_PADRAO
    raio_pedido = sys.argv[3] if len(sys.argv) > 3 else str(RAIO_PADRAO)
    # None faz voxelizar() usar o radius da cena convertido pela escala.
    raio_forcado = None if raio_pedido == "proporcional" else float(raio_pedido)

    for caminhos in sorted(PASTA_NPZ.glob(f"*_seed{seed:03d}_caminhos.npz")):
        dados = np.load(caminhos)
        vazio, info = voxelizar(dados["pontos"], dados["inicios"], float(dados["radius"]), lado,
                                raio_forcado)
        classificacao = classificar(vazio)

        saida = caminho_classificacao(caminhos, lado)
        np.savez_compressed(
            saida,
            classificacao=classificacao,
            caverna=dados["caverna"],
            seed=seed,
            origem=caminhos.name,
            **info,
        )

        borda = int((classificacao == BORDA).sum())
        interno = int((classificacao == INTERNO).sum())
        caverna = str(dados["caverna"])
        titulo = (f"{caverna} {lado}^3 (seed {seed}) - raio {info['raio_voxels']:.2f} voxels: "
                  f"{borda} borda, {interno} interno")
        vivas = np.argwhere(vazio)
        valores = classificacao[vazio]
        # Mesma troca de eixos dos outros plots: x largura, y profundidade, z altura.
        figura = figura_volumetrica(
            vivas[:, 2], vivas[:, 0], vivas[:, 1], valores, titulo,
            minimos=[-0.5] * 3, maximos=[lado - 0.5] * 3,
            rotulo_escala="1 borda, 2 interno", limites_cor=(BORDA, INTERNO), paleta="Magma",
            opacidades=np.where(valores == INTERNO, 1.0, 0.35),
        )
        figura.write_html(PASTA_PLOTS / saida.with_suffix(".html").name, include_plotlyjs="cdn")

        print(f"{caverna}: escala {info['escala']:.4f} voxel/unidade, raio proporcional "
              f"{info['raio_proporcional']:.2f} -> usado {info['raio_voxels']:.2f}; "
              f"borda {borda}, interno {interno} -> {saida.name}")

if __name__ == "__main__":
    main()
