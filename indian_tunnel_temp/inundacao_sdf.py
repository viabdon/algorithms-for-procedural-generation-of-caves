"""
    Inundação e SDF do Indian Tunnel com as funções de cavegen/tools/sdf.

    Mesmas etapas do Elaphes, na ordem:
    1. Inundação: a água entra pelas bordas da grade e separa 0 vazio,
       1 borda e 2 interno.
    2. SDF: binariza a borda, mede a distância euclidiana exata até ela e
       volta com o sinal (interno positivo, externo negativo, borda 0).

    Cada etapa grava o seu npz e o seu plot, nos formatos de cavegen/tools/sdf. O npz
    do SDF é o que o pesos.py do CA importa:
    uv run python -m cavegen.generators.cellular_automata.pesos indian_tunnel_temp/npz/indian_tunnel_surface_64_sdf.npz

    uv run python indian_tunnel_temp/inundacao_sdf.py [lado]
"""
import sys

import numpy as np
from voxelizacao import LADO_PADRAO, PASTA_PLOTS, caminho_superficie

# A inundação e o SDF ficam em cavegen/tools/flood_fill e cavegen/tools/sdf, dentro
# do pacote: o import funciona de qualquer pasta.
from cavegen.tools.flood_fill.inundacao import BORDA, INTERNO, classificar_por_inundacao, inundar
from cavegen.tools.flood_fill.inundacao import figura as figura_inundacao
from cavegen.tools.sdf.sdf import (
    CONVENCAO,
    CORTE_NEGATIVO,
    sdf_da_classificacao,
)
from cavegen.tools.sdf.sdf import figura as figura_sdf


def main():
    lado = int(sys.argv[1]) if len(sys.argv) > 1 else LADO_PADRAO
    entrada = caminho_superficie(lado)
    PASTA_PLOTS.mkdir(exist_ok=True)

    dados = np.load(entrada)
    cheio = dados["surface_voxels"].astype(bool)

    agua, buracos_fechados = inundar(cheio)
    classificacao = classificar_por_inundacao(cheio, agua)
    n_borda = int((classificacao == BORDA).sum())
    n_interno = int((classificacao == INTERNO).sum())
    buracos = int(buracos_fechados.sum())

    saida_inundacao = entrada.with_name(entrada.stem + "_inundacao.npz")
    np.savez_compressed(
        saida_inundacao,
        classificacao=classificacao,
        agua=agua.astype(np.uint8),
        buracos_fechados=buracos_fechados.astype(np.uint8),
        metadata=dados["metadata"],
    )
    titulo = (f"Indian Tunnel {lado}^3 - inundação: {n_borda} borda, {n_interno} interno "
              f"({buracos} deles eram buracos fechados)")
    figura_inundacao(classificacao, titulo).write_html(
        PASTA_PLOTS / saida_inundacao.with_suffix(".html").name, include_plotlyjs="cdn")
    print(f"inundação: cheios {int(cheio.sum())}, borda {n_borda}, interno {n_interno} "
          f"({buracos} buracos fechados) -> {saida_inundacao.name}")

    sdf, borda, interno = sdf_da_classificacao(classificacao)

    saida_sdf = entrada.with_name(entrada.stem + "_sdf.npz")
    np.savez_compressed(
        saida_sdf,
        sdf=sdf,
        borda=borda.astype(np.uint8),
        interno=interno.astype(np.uint8),
        convencao=CONVENCAO,
        metadata=dados["metadata"],
    )
    plotados = int((sdf > CORTE_NEGATIVO).sum())
    titulo = (f"Indian Tunnel {lado}^3 - SDF (interno +, externo -): {plotados} voxels "
              f"acima de {CORTE_NEGATIVO:g}")
    figura_sdf(sdf, titulo).write_html(
        PASTA_PLOTS / saida_sdf.with_suffix(".html").name, include_plotlyjs="cdn")
    print(f"sdf de {sdf.min():.2f} a {sdf.max():.2f} -> {saida_sdf.name}")

if __name__ == "__main__":
    main()
