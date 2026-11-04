"""
    Figuras do random walk, no estilo dos plots do CA.
"""
from itertools import pairwise

import numpy as np
import plotly.graph_objects as go

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    figura_volumetrica,
    gizmo_eixos,
)
from cavegen.generators.random_walk.cena import Grafo
from cavegen.generators.random_walk.voxelizacao import BORDA, INTERNO

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
