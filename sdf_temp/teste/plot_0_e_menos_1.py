"""
    Plota só os níveis 0 (borda) e -1 (primeira camada de água) do SDF.

    Teste visual da inundação: o -1 é a água encostada na borda por uma face,
    então essa camada deve envolver a borda por fora. A borda sai mais
    transparente e com o triplo do tamanho, para a camada -1 aparecer através
    dela em vez de cobri-la.

    Lê o npz da etapa sdf.py e grava a figura nesta mesma pasta.

    uv run python sdf_temp/teste/plot_0_e_menos_1.py
"""
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.colors import diverging

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    gizmo_eixos,
)

PASTA = Path(__file__).resolve().parent
ENTRADA = PASTA.parent / "npz" / "elaphes_surface_64_sdf.npz"
SAIDA_PLOT = PASTA / "elaphes_surface_64_sdf_0_e_menos_1.html"

# Nível do SDF: (nome, cor, opacidade, tamanho do marcador). As cores são as
# pontas da Tropic, a paleta do sdf.py. A borda vem primeiro: a translúcida é
# desenhada antes da opaca.
NIVEIS = {
    0.0: ("borda (0)", diverging.Tropic[-1], 0.25, 6),
    -1.0: ("externo (-1)", diverging.Tropic[0], 1.0, 2),
}

def trace_do_nivel(sdf: np.ndarray, valor: float) -> go.Scatter3d:
    """
        Um Scatter3d por nível, com a cor, a opacidade e o tamanho de NIVEIS.
        Mesma troca de eixos dos outros plots: x é a largura, y é a
        profundidade e z é a altura da grade (depth, height, width).
        sdf: campo com sinal.
        valor: nível plotado nesse trace (uma chave de NIVEIS).
    """
    nome, cor, opacidade, tamanho = NIVEIS[valor]
    indices = np.argwhere(sdf == valor)
    x, y, z = indices[:, 2], indices[:, 0], indices[:, 1]

    return go.Scatter3d(
        x=x, y=y, z=z,
        mode="markers",
        name=f"{nome}: {x.size} voxels",
        marker=dict(size=tamanho, color=cor, opacity=opacidade),
        hovertemplate=f"(%{{x}}, %{{y}}, %{{z}})<br>{nome}<extra></extra>",
    )

def figura(sdf: np.ndarray, titulo: str) -> go.Figure:
    """
        Monta a figura com os dois níveis, caixa e gizmo, no estilo dos plots do CA.
        sdf: campo com sinal.
        titulo: texto do topo da figura.
    """
    profundidade, altura, largura = sdf.shape
    minimos = [-0.5, -0.5, -0.5]
    maximos = [largura - 0.5, profundidade - 0.5, altura - 0.5]
    olho = camera_isometrica()

    fig = go.Figure()
    for valor in NIVEIS:
        fig.add_trace(trace_do_nivel(sdf, valor))
    for trace in caixa_wireframe(minimos, maximos, olho) + gizmo_eixos(minimos, maximos):
        trace.showlegend = False
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
        legend=dict(x=0.02, y=0.95, font=dict(color="white", size=12), bgcolor="black"),
        scene=dict(
            xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
            bgcolor="black",
            aspectmode="data",
            camera=dict(eye=olho),
        ),
    )
    return fig

def main():
    sdf = np.load(ENTRADA)["sdf"]

    largura = sdf.shape[2]
    titulo = f"Elaphes {largura}^3 - SDF só nos níveis 0 (borda) e -1 (externo colado nela)"
    figura(sdf, titulo).write_html(SAIDA_PLOT, include_plotlyjs="cdn")

    for valor, (nome, _, opacidade, tamanho) in NIVEIS.items():
        print(f"{nome}: {int((sdf == valor).sum())} voxels, opacidade {opacidade}, "
              f"tamanho {tamanho}")
    print(f"figura salva em {SAIDA_PLOT}")

if __name__ == "__main__":
    main()
