"""
    Gerador de cavernas do random walk ponderado, no contrato Volume3D do projeto.

    Junta as etapas: carrega o grafo de waypoints da caverna, caminha entre os
    waypoints ligados (caminhada.py) e escava os caminhos numa grade cúbica
    (voxelizacao.py). O resultado é booleano (depth, height, width), ZYX, com
    True = vazio, como o do CA.

    A forma da caverna vem dos waypoints, postos à mão sobre cavernas reais no
    projeto base; o random walk dá a irregularidade do trajeto entre eles.

    uv run python -m cavegen.generators.random_walk.generator [seed] [lado] [raio|proporcional]
"""
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.core.volume import Volume3D
from cavegen.generators.random_walk.caminhada import PASTA_NPZ, SEED_PADRAO, gerar_caminhos
from cavegen.generators.random_walk.cena import (
    Grafo,
    apelido,
    carregar_caverna,
    cavernas_disponiveis,
)
from cavegen.generators.random_walk.voxelizacao import LADO_PADRAO, MARGEM, RAIO_PADRAO, voxelizar

CAVERNA_PADRAO = "knotlow_cavern"

@dataclass
class CavernaGerada:
    """
        Tudo o que sai de uma geração: o grafo com os parâmetros usados, os
        caminhos (eixos da Unity) e a grade escavada (depth, height, width).
    """
    grafo: Grafo
    pontos: np.ndarray
    inicios: np.ndarray
    vazio: np.ndarray
    info: dict

def gerar_caverna(lado: int = LADO_PADRAO, seed: int | None = None,
                  caverna: str = CAVERNA_PADRAO, weight: float | None = None,
                  k: float | None = None, spacer: float | None = None,
                  raio_voxels: float | None = RAIO_PADRAO) -> CavernaGerada:
    """
        Caminha e voxeliza, guardando as etapas intermediárias (para o menu e os plots).
        lado: lado da grade cúbica.
        Os outros argumentos são os de generate_random_walk.
    """
    # Com lado - 1 - 2 * MARGEM <= 0 a escala do encaixe fica zero ou negativa
    # (caverna colapsada num ponto ou espelhada) sem nenhum erro.
    if lado <= 1 + 2 * MARGEM:
        raise ValueError(f"O lado da grade precisa passar de {1 + 2 * MARGEM} voxels, "
                         f"recebeu {lado}.")

    grafo = carregar_caverna(caverna)
    trocas = {"weight": weight, "k": k, "spacer": spacer}
    parametros = {**grafo.parametros, **{p: float(v) for p, v in trocas.items() if v is not None}}
    grafo = replace(grafo, parametros=parametros)

    pontos, inicios = gerar_caminhos(grafo, numpy_rng(seed))
    vazio, info = voxelizar(pontos, inicios, parametros["radius"], lado, raio_voxels)
    return CavernaGerada(grafo, pontos, inicios, vazio, info)

def generate_random_walk(shape: tuple[int, int, int] = (LADO_PADRAO,) * 3, seed: int | None = None,
                         caverna: str = CAVERNA_PADRAO, weight: float | None = None,
                         k: float | None = None, spacer: float | None = None,
                         raio_voxels: float | None = RAIO_PADRAO) -> Volume3D:
    """
        Gera a caverna com o random walk ponderado e devolve o Volume3D.
        shape: (depth, height, width) da grade; precisa ser cúbica, porque a
               caverna é encaixada com a mesma escala nos três eixos.
        seed: seed do numpy_rng; None sorteia (não reproduzível).
        caverna: nome ou apelido de uma caverna de configs/random_walk/.
        weight, k, spacer: parâmetros do CaveGenerator; None usa o valor da cena.
        raio_voxels: raio do tubo em voxels; None usa o radius da cena
                     convertido pela escala (ver voxelizacao.py).
    """
    if len(shape) != 3 or len(set(shape)) != 1:
        raise ValueError(f"O random walk precisa de uma grade cúbica, recebeu {tuple(shape)}.")

    gerada = gerar_caverna(int(shape[0]), seed, caverna, weight, k, spacer, raio_voxels)
    grafo, pontos, inicios, vazio, info = (gerada.grafo, gerada.pontos, gerada.inicios,
                                           gerada.vazio, gerada.info)
    parametros = grafo.parametros

    return Volume3D(
        vazio,
        metadata={
            "algorithm": "random_walk",
            # int(): seed vinda de rng.integers é np.int64, que o json não serializa.
            "seed": None if seed is None else int(seed),
            "caverna": grafo.nome,
            "weight": parametros["weight"],
            "k": parametros["k"],
            "spacer": parametros["spacer"],
            "radius": parametros["radius"],
            "raio_voxels": float(info["raio_voxels"]),
            "raio_proporcional": float(info["raio_proporcional"]),
            "escala": float(info["escala"]),
            "deslocamento": [float(v) for v in info["deslocamento"]],
            "caminhos": int(len(inicios) - 1),
            "pontos": int(len(pontos)),
        },
    )

class RandomWalkGenerator:
    def __init__(self, caverna: str = CAVERNA_PADRAO, weight: float | None = None,
                 k: float | None = None, spacer: float | None = None,
                 raio_voxels: float | None = RAIO_PADRAO) -> None:
        self.caverna = caverna
        self.weight = weight
        self.k = k
        self.spacer = spacer
        self.raio_voxels = raio_voxels

    def generate(self, shape: tuple[int, int, int], seed: int | None = None) -> Volume3D:
        return generate_random_walk(shape=shape, seed=seed, caverna=self.caverna,
                                    weight=self.weight, k=self.k, spacer=self.spacer,
                                    raio_voxels=self.raio_voxels)

def caminho_volume(caverna: str, seed: int, lado: int) -> Path:
    """
        Arquivo do Volume3D de uma caverna, ao lado dos npz das etapas.
        caverna: nome ou apelido da caverna.
        seed: seed da caminhada.
        lado: lado da grade.
    """
    return PASTA_NPZ / f"{apelido(caverna)}_seed{seed:03d}_{lado}_volume.npz"

def main():
    from cavegen.datastream.voxel_io import save_volume_npz

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else SEED_PADRAO
    lado = int(sys.argv[2]) if len(sys.argv) > 2 else LADO_PADRAO
    raio_pedido = sys.argv[3] if len(sys.argv) > 3 else str(RAIO_PADRAO)
    raio = None if raio_pedido == "proporcional" else float(raio_pedido)

    for caverna in cavernas_disponiveis():
        volume = generate_random_walk((lado,) * 3, seed, caverna, raio_voxels=raio)
        saida = caminho_volume(caverna, seed, lado)
        save_volume_npz(volume, saida)
        print(f"{volume.metadata['caverna']}: {volume.open_voxels} vazios "
              f"({np.round(volume.fill_ratio * 100, 2)}%) -> {saida.name}")

if __name__ == "__main__":
    main()
