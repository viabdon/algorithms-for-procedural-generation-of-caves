"""
    Calcula o SDF do Elaphes a partir da classificação da inundação.

    Etapas, na ordem:
    1. Lê a classificação (0 vazio, 1 borda, 2 interno) do npz da inundação.
    2. Tira os voxels 2 e binariza: só a borda fica 1. O interno vira 0 junto
       com o lado de fora, mas a máscara dele é guardada para o passo 4.
    3. Mede a distância euclidiana de cada voxel até o voxel de borda mais
       próximo, em unidades de voxel. A borda fica com 0.
    4. Volta com o sinal pela máscara guardada: interno positivo, externo
       negativo.

    A superfície é o próprio voxel de borda, então o zero cai no centro dele e
    não precisa de correção de meio voxel.

    A distância vem do distance_transform_edt do scipy, que é exato (algoritmo
    de Maurer et al., 2003). Qualquer EDT exata dá o mesmo resultado, então a
    implementação do artigo pode entrar no lugar de distancia_ate_borda() sem
    mudar o resto.

    O sinal segue o combinado neste experimento (interno positivo). O
    docs/architecture.md usa o inverso (SDF < 0 no VOID), por isso o sinal
    fica em SINAL_INTERNO, para inverter fácil.

    uv run python sdf_temp/sdf.py
"""
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

from inundacao import BORDA, INTERNO

PASTA = Path(__file__).resolve().parent
ENTRADA = PASTA / "npz" / "elaphes_surface_64_inundacao.npz"
SAIDA_NPZ = PASTA / "npz" / "elaphes_surface_64_sdf.npz"

# 1: interno positivo e externo negativo. -1 inverte para a convenção do projeto.
SINAL_INTERNO = 1
CONVENCAO = "interno positivo, externo negativo, borda 0; distância em voxels"

def binarizar_borda(classificacao: np.ndarray) -> np.ndarray:
    """
        Tira os voxels internos (2) e deixa a matriz binária: True só na borda (1).
        classificacao: matriz com 0, 1 e 2 da inundação.
    """
    return classificacao == BORDA

def distancia_ate_borda(borda: np.ndarray) -> np.ndarray:
    """
        Distância euclidiana de cada voxel até o voxel de borda mais próximo.
        O distance_transform_edt mede de cada True até o False mais próximo,
        então a borda entra invertida: ela é o False que todo voxel procura.
        borda: matriz booleana com True só na borda.
    """
    return distance_transform_edt(~borda)

def aplicar_sinal(distancia: np.ndarray, interno: np.ndarray) -> np.ndarray:
    """
        Volta com o interno que foi tirado na binarização: positivo dentro,
        negativo fora. A borda fica com 0.
        distancia: distância até a borda, sem sinal.
        interno: máscara dos voxels que eram 2 na inundação.
    """
    sdf = np.where(interno, SINAL_INTERNO, -SINAL_INTERNO) * distancia
    # A borda não é interno, então sem isso sairia -0.0 (distância 0 vezes o sinal de fora).
    sdf[distancia == 0] = 0
    return sdf.astype(np.float32)

def main():
    dados = np.load(ENTRADA)
    classificacao = dados["classificacao"]

    borda = binarizar_borda(classificacao)
    interno = classificacao == INTERNO
    sdf = aplicar_sinal(distancia_ate_borda(borda), interno)

    SAIDA_NPZ.parent.mkdir(exist_ok=True)
    np.savez_compressed(
        SAIDA_NPZ,
        sdf=sdf,
        borda=borda.astype(np.uint8),
        interno=interno.astype(np.uint8),
        convencao=CONVENCAO,
        metadata=dados["metadata"],
    )

    print(f"borda: {int(borda.sum())}, interno: {int(interno.sum())}")
    print(f"sdf de {sdf.min():.2f} (externo) a {sdf.max():.2f} (interno)")
    print(f"npz salvo em {SAIDA_NPZ}")

if __name__ == "__main__":
    main()
