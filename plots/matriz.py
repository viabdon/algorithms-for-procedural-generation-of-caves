"""Preparação dos dados que vão para as plotagens 3D.

Este módulo NÃO desenha nada. Ele só carrega o volume booleano gerado pelos
algoritmos e transforma a matriz 3D em listas de coordenadas (x, y, z) prontas
para qualquer biblioteca de plotagem.

Quem plota (plot_matplotlib.py e plot_plotly.py) importa daqui, então a regra de
"como os dados viram pontos" fica escrita em um lugar só.

Também dá para rodar direto para inspecionar um volume:
    uv run python plots/matriz.py
    uv run python plots/matriz.py results/volumes/cellular_automata_seed_0.npz
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.io.voxel_io import load_volume_npz

# Raiz do projeto (a pasta que contém src/, results/, ...). Usar isso deixa os
# scripts funcionando independente de onde o terminal está aberto.
RAIZ_PROJETO = Path(__file__).resolve().parents[1]

# Volume usado quando nenhum caminho é informado.
VOLUME_PADRAO = "results/volumes/random_walk_seed_0.npz"

# Onde as figuras geradas são salvas.
PASTA_FIGURAS = RAIZ_PROJETO / "results" / "figures"


@dataclass(slots=True)
class MatrizVoxels:
    """Volume já "achatado" em pontos, pronto para virar gráfico."""

    volume: Volume3D
    coordenada_x: np.ndarray  # eixo width
    coordenada_y: np.ndarray  # eixo height
    coordenada_z: np.ndarray  # eixo depth (também usado para colorir)
    caminho: Path
    total_pontos_originais: int

    @property
    def nome(self) -> str:
        """Nome do arquivo sem extensão, ex.: 'random_walk_seed_0'."""
        return self.caminho.stem

    @property
    def shape(self) -> tuple[int, int, int]:
        """Formato do volume na convenção (depth, height, width)."""
        return self.volume.shape

    @property
    def proporcao_eixos(self) -> tuple[int, int, int]:
        """Proporção (x, y, z) = (width, height, depth).

        Serve para os 3 eixos ficarem na mesma escala e a caverna não sair
        distorcida no gráfico.
        """
        return self.shape[::-1]

    @property
    def foi_amostrado(self) -> bool:
        return self.coordenada_z.size < self.total_pontos_originais

    @property
    def titulo(self) -> str:
        if self.foi_amostrado:
            return (
                f"Caverna gerada — {self.nome} "
                f"({self.coordenada_z.size} de {self.total_pontos_originais} voxels abertos)"
            )
        return f"Caverna gerada — {self.nome} (todos os voxels abertos)"

    def resumo(self) -> str:
        return (
            f"arquivo: {self.caminho.relative_to(RAIZ_PROJETO)}\n"
            f"shape (depth, height, width): {self.shape}\n"
            f"voxels abertos: {self.volume.open_voxels}\n"
            f"fill ratio: {self.volume.fill_ratio:.4f}\n"
            f"pontos plotados: {self.coordenada_z.size}"
        )


def resolver_caminho(caminho: str | Path) -> Path:
    """Aceita caminho relativo à raiz do projeto ou caminho absoluto."""
    caminho = Path(caminho)
    return caminho if caminho.is_absolute() else RAIZ_PROJETO / caminho


def carregar_volume(caminho: str | Path = VOLUME_PADRAO) -> Volume3D:
    """Carrega o volume booleano (.npz) gerado pelo algoritmo."""
    caminho_completo = resolver_caminho(caminho)
    if not caminho_completo.exists():
        raise FileNotFoundError(
            f"Volume não encontrado: {caminho_completo}\n"
            f"Rode o gerador antes, ou confira os arquivos em results/volumes/."
        )
    return load_volume_npz(caminho_completo)


def extrair_voxels_abertos(volume: Volume3D) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Devolve as coordenadas (z, y, x) de TODOS os voxels abertos.

    np.argwhere devolve uma tabela (N, 3) com uma linha por voxel aberto, nas
    colunas (z, y, x) seguindo a convenção (depth, height, width).
    """
    coordenadas_abertas = np.argwhere(volume.data)
    return (
        coordenadas_abertas[:, 0],  # z
        coordenadas_abertas[:, 1],  # y
        coordenadas_abertas[:, 2],  # x
    )


def _amostrar(
    quantidade_total: int, max_pontos: int, semente: int
) -> np.ndarray:
    """Sorteia índices para reduzir a nuvem de pontos, de forma reprodutível."""
    gerador = np.random.default_rng(semente)
    indices = gerador.choice(quantidade_total, size=max_pontos, replace=False)
    return np.sort(indices)


def preparar_matriz(
    caminho: str | Path = VOLUME_PADRAO,
    max_pontos: int | None = None,
    semente: int = 0,
) -> MatrizVoxels:
    """Ponto de entrada usado pelos scripts de plotagem.

    Args:
        caminho: .npz do volume (relativo à raiz do projeto ou absoluto).
        max_pontos: se informado e o volume tiver mais voxels abertos que isso,
            sorteia uma amostra desse tamanho (útil para volumes grandes no
            Plotly, que fica pesado com centenas de milhares de pontos).
        semente: semente do sorteio, para a amostra ser sempre a mesma.
    """
    caminho_completo = resolver_caminho(caminho)
    volume = carregar_volume(caminho_completo)
    coordenada_z, coordenada_y, coordenada_x = extrair_voxels_abertos(volume)

    total_original = int(coordenada_z.size)
    if max_pontos is not None and total_original > max_pontos:
        indices = _amostrar(total_original, max_pontos, semente)
        coordenada_z = coordenada_z[indices]
        coordenada_y = coordenada_y[indices]
        coordenada_x = coordenada_x[indices]

    return MatrizVoxels(
        volume=volume,
        coordenada_x=coordenada_x,
        coordenada_y=coordenada_y,
        coordenada_z=coordenada_z,
        caminho=caminho_completo,
        total_pontos_originais=total_original,
    )


def caminho_da_figura(matriz: MatrizVoxels, sufixo: str, extensao: str) -> Path:
    """Monta results/figures/<nome>_<sufixo>.<extensao> e garante a pasta."""
    PASTA_FIGURAS.mkdir(parents=True, exist_ok=True)
    return PASTA_FIGURAS / f"{matriz.nome}_{sufixo}.{extensao}"


def caminho_do_argumento(padrao: str = VOLUME_PADRAO) -> str:
    """Lê o volume passado na linha de comando, se houver."""
    return sys.argv[1] if len(sys.argv) > 1 else padrao


if __name__ == "__main__":
    print(preparar_matriz(caminho_do_argumento()).resumo())
