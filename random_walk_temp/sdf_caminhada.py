"""
    Calcula o SDF da caverna do random walk com as funções do sdf_temp.

    A classificação da voxelização já vem nos códigos da inundação (0 fora,
    1 borda, 2 interno), então as etapas são as mesmas do Elaphes: binariza a
    borda, mede a distância euclidiana exata até ela e volta com o sinal
    (interno positivo, externo negativo, borda 0). O plot também é o do
    sdf_temp, com o mesmo corte e a mesma paleta.

    A diferença está no que é interno. No Elaphes a malha é aberta nas
    entradas, a água da inundação entra nos túneis e o interno é quase só a
    espessura da parede. Aqui o tubo é o próprio vazio da caverna, então o
    interno positivo é o miolo do túnel.

    O npz sai no formato que o pesos.py do CA importa (campos sdf e convencao):
    uv run python -m cavegen.generators.cellular_automata.pesos random_walk_temp/npz/<arquivo>_sdf.npz

    uv run python random_walk_temp/sdf_caminhada.py [seed] [lado]
"""
import sys
from pathlib import Path

import numpy as np

from caminhada import PASTA_NPZ, PASTA_PLOTS, SEED_PADRAO
from voxelizacao import LADO_PADRAO

# As funções do SDF ficam no sdf_temp; o inundacao.py de lá precisa estar no caminho também.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sdf_temp"))
from sdf import (
    CONVENCAO,
    CORTE_NEGATIVO,
    INTERNO,
    aplicar_sinal,
    binarizar_borda,
    distancia_ate_borda,
    figura,
)

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else SEED_PADRAO
    lado = int(sys.argv[2]) if len(sys.argv) > 2 else LADO_PADRAO

    for entrada in sorted(PASTA_NPZ.glob(f"*_seed{seed:03d}_{lado}_classificacao.npz")):
        dados = np.load(entrada)
        classificacao = dados["classificacao"]

        borda = binarizar_borda(classificacao)
        interno = classificacao == INTERNO
        sdf = aplicar_sinal(distancia_ate_borda(borda), interno)

        saida = entrada.with_name(entrada.name.replace("_classificacao", "_sdf"))
        np.savez_compressed(
            saida,
            sdf=sdf,
            borda=borda.astype(np.uint8),
            interno=interno.astype(np.uint8),
            convencao=CONVENCAO,
            caverna=dados["caverna"],
            seed=seed,
            origem=entrada.name,
            raio_voxels=dados["raio_voxels"],
        )

        caverna = str(dados["caverna"])
        plotados = int((sdf > CORTE_NEGATIVO).sum())
        titulo = (f"{caverna} {lado}^3 (seed {seed}) - SDF (interno +, externo -): "
                  f"{plotados} voxels acima de {CORTE_NEGATIVO:g}")
        figura(sdf, titulo).write_html(PASTA_PLOTS / saida.with_suffix(".html").name,
                                       include_plotlyjs="cdn")

        print(f"{caverna}: sdf de {sdf.min():.2f} a {sdf.max():.2f}, borda {int(borda.sum())}, "
              f"interno {int(interno.sum())} -> {saida.name}")

if __name__ == "__main__":
    main()
