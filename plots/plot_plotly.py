"""Plotagem 3D da caverna com Plotly (versão interativa, abre no navegador).

Usa exatamente a mesma preparação de dados do Matplotlib (matriz.py), então os
dois gráficos mostram os mesmos pontos — o que muda é só a renderização.

    uv run python plots/plot_plotly.py
    uv run python plots/plot_plotly.py results/volumes/cellular_automata_seed_0.npz
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

# Permite rodar tanto como "python plots/plot_plotly.py" quanto
# "python -m plots.plot_plotly".
sys.path.append(str(Path(__file__).resolve().parent))

from matriz import MatrizVoxels, caminho_da_figura, caminho_do_argumento, preparar_matriz

# Nuvens muito grandes travam o navegador; acima disso os dados são amostrados.
MAX_PONTOS_INTERATIVO = 120_000


def montar_figura(matriz: MatrizVoxels) -> go.Figure:
    largura, altura, profundidade = matriz.proporcao_eixos
    maior_lado = max(largura, altura, profundidade)

    figura = go.Figure(
        data=go.Scatter3d(
            x=matriz.coordenada_x,
            y=matriz.coordenada_y,
            z=matriz.coordenada_z,
            mode="markers",
            marker=dict(
                size=2,
                color=matriz.coordenada_z,  # mesma ideia do Matplotlib: cor = profundidade
                colorscale="Viridis",       # escala sequencial: claro = raso, escuro = fundo
                opacity=0.6,
                colorbar=dict(title="Z (depth)"),
            ),
            hovertemplate="x=%{x}<br>y=%{y}<br>z=%{z}<extra></extra>",
            name="voxels abertos",
        )
    )

    figura.update_layout(
        title=matriz.titulo,
        template="plotly_white",
        width=900,
        height=800,
        margin=dict(l=0, r=0, t=60, b=0),
        scene=dict(
            xaxis_title="X (width)",
            yaxis_title="Y (height)",
            zaxis_title="Z (depth)",
            # Mantém a proporção real do volume, igual ao set_box_aspect().
            aspectmode="manual",
            aspectratio=dict(
                x=largura / maior_lado,
                y=altura / maior_lado,
                z=profundidade / maior_lado,
            ),
        ),
    )
    return figura


def plotar(matriz: MatrizVoxels, salvar: bool = True, mostrar: bool = True) -> Path | None:
    figura = montar_figura(matriz)

    destino = None
    if salvar:
        # HTML autocontido: dá para abrir e girar a caverna sem rodar Python.
        destino = caminho_da_figura(matriz, "3d_plotly", "html")
        figura.write_html(destino, include_plotlyjs="cdn")

    if mostrar:
        figura.show()

    return destino


if __name__ == "__main__":
    matriz_voxels = preparar_matriz(caminho_do_argumento(), max_pontos=MAX_PONTOS_INTERATIVO)
    print(matriz_voxels.resumo())
    arquivo_gerado = plotar(matriz_voxels)
    print("figura salva em:", arquivo_gerado)
