"""
    Figuras do random walk, no estilo dos plots do CA.

    Dois modos para um resultado gravado pelo menu:
    caminhos: as linhas da caminhada e os waypoints, nos eixos da Unity.
    classificacao: a grade escavada, borda translúcida e interno opaco.

    uv run python -m cavegen.generators.random_walk.plot <resultado> [caminhos|classificacao]
"""
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    figura_volumetrica,
    gizmo_eixos,
)
from cavegen.generators.random_walk.cena import Grafo
from cavegen.generators.random_walk.results import RESULTS_DIR, load_result
from cavegen.generators.random_walk.voxelizacao import BORDA, INTERNO

PASTA_FIGURAS = Path(__file__).resolve().parent / "plots"
MODOS = ("caminhos", "classificacao")

def figura_caminhos(grafo: Grafo, pontos: np.ndarray, inicios: np.ndarray,
                    titulo: str) -> go.Figure:
    """
        Caminhos em linha amarela e waypoints em verde, no estilo dos outros plots.
        Eixos como nos plots da grade: x é o x da Unity (largura), y é o z da
        Unity (profundidade) e z é o y da Unity (altura).
        grafo: saída de carregar_caverna().
        pontos, inicios: saída de gerar_caminhos().
        titulo: texto do topo da figura.
    """
    # None entre os caminhos quebra a linha, para tudo caber num trace só.
    linhas = [np.vstack([pontos[a:b], [np.nan] * 3]) for a, b in pairwise(inicios)]
    linhas = np.vstack(linhas)
    minimos = np.nanmin(pontos, axis=0)[[0, 2, 1]]
    maximos = np.nanmax(pontos, axis=0)[[0, 2, 1]]
    olho = camera_isometrica()

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=linhas[:, 0], y=linhas[:, 2], z=linhas[:, 1],
        mode="lines", line=dict(color="#ffd54f", width=3),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter3d(
        x=grafo.posicoes[:, 0], y=grafo.posicoes[:, 2], z=grafo.posicoes[:, 1],
        mode="markers", marker=dict(size=3, color="#00e676"),
        text=grafo.nomes, hovertemplate="%{text}<extra></extra>", showlegend=False,
    ))
    for trace in caixa_wireframe(minimos, maximos, olho) + gizmo_eixos(minimos, maximos):
        fig.add_trace(trace)

    eixo_limpo = dict(
        showgrid=False, zeroline=False, showticklabels=False, showbackground=False,
        showspikes=False, title="", visible=False,
    )
    fig.update_layout(
        title=dict(text=titulo, font=dict(color="white", size=14), x=0.5),
        paper_bgcolor="black",
        plot_bgcolor="black",
        width=950, height=800,
        margin=dict(l=10, r=10, t=50, b=10),
        scene=dict(
            xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
            bgcolor="black",
            aspectmode="data",
            camera=dict(eye=olho),
        ),
    )
    return fig

def figura_classificacao(classificacao: np.ndarray, titulo: str) -> go.Figure:
    """
        Grade escavada com a borda translúcida e o interno opaco.
        Mesma troca de eixos dos outros plots: x largura, y profundidade, z altura.
        classificacao: matriz com 0 fora, 1 borda e 2 interno.
        titulo: texto do topo da figura.
    """
    lado = classificacao.shape[0]
    vazio = classificacao != 0
    vivas = np.argwhere(vazio)
    valores = classificacao[vazio]
    return figura_volumetrica(
        vivas[:, 2], vivas[:, 0], vivas[:, 1], valores, titulo,
        minimos=[-0.5] * 3, maximos=[lado - 0.5] * 3,
        rotulo_escala="1 borda, 2 interno", limites_cor=(BORDA, INTERNO), paleta="Magma",
        opacidades=np.where(valores == INTERNO, 1.0, 0.35),
    )

def caminho_da_figura(result_id: int, modo: str, directory: Path = PASTA_FIGURAS) -> Path:
    """
        Arquivo HTML da figura de um resultado.
        result_id: número de identificação do resultado.
        modo: um dos MODOS.
        directory: pasta onde os HTML são gravados.
    """
    return Path(directory) / f"result_{result_id:03d}_{modo}.html"

def figura_ja_existe(result_id: int, modo: str, directory: Path = PASTA_FIGURAS) -> bool:
    """
        Diz se a figura desse resultado, nesse modo, já está gravada.
        result_id: número de identificação do resultado.
        modo: um dos MODOS.
        directory: pasta onde os HTML são gravados.
    """
    return caminho_da_figura(result_id, modo, directory).exists()

def plotar_resultado(result_id: int, modo: str = "caminhos", directory: Path = RESULTS_DIR,
                     figuras: Path = PASTA_FIGURAS, refazer: bool = False) -> Path:
    """
        Grava o HTML da figura e devolve o caminho do arquivo.
        Se a figura já existir, devolve o caminho sem remontar.
        result_id: número de identificação do resultado.
        modo: um dos MODOS.
        directory: pasta onde os resultados são gravados.
        figuras: pasta onde os HTML são gravados.
        refazer: remonta a figura mesmo que o HTML já exista.
    """
    if modo not in MODOS:
        raise ValueError(f"modo precisa ser um de {MODOS}, recebeu {modo!r}.")

    destino = caminho_da_figura(result_id, modo, figuras)
    if destino.exists() and not refazer:
        return destino

    dados = load_result(result_id, directory)
    cabecalho = (f"{dados['caverna']} - resultado {result_id:03d} (seed {dados['seed']}, "
                 f"{dados['size']}^3)")
    if modo == "caminhos":
        inicios = dados["inicios"]
        titulo = (f"{cabecalho}: {len(inicios) - 1} caminhos, "
                  f"{len(dados['pontos'])} pontos")
        figura = figura_caminhos(dados["grafo"], dados["pontos"], inicios, titulo)
    else:
        classificacao = dados["classificacao"]
        titulo = (f"{cabecalho} - raio {dados['raio_voxels']:.2f} voxels: "
                  f"{int((classificacao == BORDA).sum())} borda, "
                  f"{int((classificacao == INTERNO).sum())} interno")
        figura = figura_classificacao(classificacao, titulo)

    destino.parent.mkdir(parents=True, exist_ok=True)
    figura.write_html(destino, include_plotlyjs="cdn")
    return destino

def main(argumentos=None):
    argumentos = argumentos if argumentos is not None else sys.argv[1:]
    if not argumentos:
        raise SystemExit("informe o numero do resultado, ex: ... plot 1 classificacao")

    modo = argumentos[1] if len(argumentos) > 1 else "caminhos"
    destino = plotar_resultado(int(argumentos[0]), modo, refazer=True)
    print("figura salva em:", destino)

if __name__ == "__main__":
    main()
