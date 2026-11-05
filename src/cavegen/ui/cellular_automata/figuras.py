"""Figuras da bancada do CA: a nuvem 3D do plot.py, cortes 2D e a evolução.

A nuvem 3D reaproveita figura_volumetrica, então sai com o mesmo visual de
radar dos HTML de plots/. Aqui só se ajusta o que muda dentro de uma página:
largura elástica e câmera que não volta ao lugar quando um controle muda.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cavegen.generators.cellular_automata.generator import BorderTreatment, neighbor_counts
from cavegen.generators.cellular_automata.plot import (
    COR_CAIXA,
    MAX_VIZINHOS,
    MIN_VIZINHOS,
    dados_da_matriz,
    figura_volumetrica,
    opacidade_por_vizinhos,
)

ALTURA_3D = 720

# Rocha e vazio nos cortes: cinza escuro e o verde do gizmo.
COR_ROCHA, COR_VAZIO = "#1a1a1a", "#00e676"

# Eixo do corte -> (eixo da matriz ZYX, rótulo do x da imagem, rótulo do y).
# A matriz é (depth, height, width); nos cortes verticais a altura fica em pé.
EIXOS_CORTE = {
    "altura": (1, "largura", "profundidade"),
    "profundidade": (0, "largura", "altura"),
    "largura": (2, "profundidade", "altura"),
}


def celulas_visiveis(matriz: np.ndarray) -> np.ndarray:
    """
        Máscara das células vivas que encostam em rocha ou na borda do volume.
        Uma célula com os 27 vizinhos vivos fica escondida no miolo e não
        aparece na nuvem, então desenhá-la só pesa no navegador.
        A borda conta como rocha aqui de propósito: a face do cubo é visível.
        matriz: matriz binária de um passo do CA.
    """
    vivas = np.asarray(matriz, dtype=bool)
    vizinhos = neighbor_counts(vivas.astype(np.int16), BorderTreatment.ZEROS)
    return vivas & (vizinhos < MAX_VIZINHOS)


def figura_3d(matriz: np.ndarray, border_treatment: str, modo: str = "vizinhos",
              paleta: str = "Purp", so_superficie: bool = True, titulo: str = "") -> go.Figure:
    """
        Nuvem 3D de um passo do CA, nos modos de cor do plot.py.
        matriz: matriz binária do passo.
        border_treatment: borda usada pelo CA, para a contagem de vizinhos bater com a dele.
        modo: "altura" ou "vizinhos".
        paleta: uma das PALETAS do plot.py.
        so_superficie: desenha só as células visíveis (ver celulas_visiveis).
        titulo: texto no topo da figura.
    """
    vivas = np.asarray(matriz, dtype=bool)
    desenhadas = celulas_visiveis(vivas) if so_superficie else vivas
    x, y, z = dados_da_matriz(desenhadas)
    lado = vivas.shape[0]

    if modo == "altura":
        valores, rotulo, limites, opacidades = z, "altura (z)", (0, lado - 1), None
    else:
        # A contagem é feita no volume inteiro e só depois filtrada, então a
        # célula da superfície mostra os mesmos vizinhos que no plot.py.
        vizinhos = neighbor_counts(vivas.astype(np.int16), border_treatment)
        valores = vizinhos[desenhadas]
        rotulo, limites = "vizinhos", (MIN_VIZINHOS, MAX_VIZINHOS)
        opacidades = opacidade_por_vizinhos(valores)

    figura = figura_volumetrica(
        x, y, z, valores, titulo,
        minimos=[-0.5, -0.5, -0.5],
        maximos=[lado - 0.5] * 3,
        rotulo_escala=rotulo,
        limites_cor=limites,
        paleta=paleta,
        opacidades=opacidades,
    )
    # uirevision fixo: o plotly mantém a câmera do usuário entre redesenhos.
    figura.update_layout(width=None, height=ALTURA_3D, uirevision="cubo",
                         margin=dict(l=60, r=0, t=40, b=0))
    return figura


def fatia(matriz: np.ndarray, eixo: str, indice: int) -> np.ndarray:
    """
        Corte 2D da matriz, orientado para a imagem (linha = y, coluna = x).
        matriz: volume (depth, height, width).
        eixo: uma das chaves de EIXOS_CORTE.
        indice: posição do corte ao longo do eixo.
    """
    eixo_matriz = EIXOS_CORTE[eixo][0]
    corte = np.take(matriz, indice, axis=eixo_matriz)
    # Cortar na largura deixa (depth, height); transposto, a altura vai para y.
    return corte.T if eixo == "largura" else corte


def figura_cortes(paineis: list, eixo: str) -> go.Figure:
    """
        Cortes lado a lado na mesma posição, como seed | resultado | peso.
        paineis: lista de (titulo, corte 2D, "binario" ou "peso").
        eixo: uma das chaves de EIXOS_CORTE, para rotular os eixos.
    """
    _, rotulo_x, rotulo_y = EIXOS_CORTE[eixo]
    figura = make_subplots(rows=1, cols=len(paineis), horizontal_spacing=0.04,
                           subplot_titles=[titulo for titulo, _, _ in paineis])

    for coluna, (_, corte, tipo) in enumerate(paineis, start=1):
        if tipo == "binario":
            trace = go.Heatmap(
                z=np.asarray(corte, dtype=int), zmin=0, zmax=1,
                colorscale=[[0, COR_ROCHA], [1, COR_VAZIO]], showscale=False,
                hovertemplate="x=%{x} y=%{y}<br>%{z}<extra></extra>",
            )
        else:
            # SDF: interno positivo (azul), externo negativo (vermelho), zero no meio.
            trace = go.Heatmap(
                z=corte, colorscale="RdBu", zmid=0,
                colorbar=dict(title="peso", thickness=12, len=0.8),
                hovertemplate="x=%{x} y=%{y}<br>peso=%{z:.2f}<extra></extra>",
            )
        figura.add_trace(trace, row=1, col=coluna)
        sufixo = "" if coluna == 1 else str(coluna)
        figura.update_xaxes(title_text=rotulo_x, row=1, col=coluna)
        figura.update_yaxes(title_text=rotulo_y if coluna == 1 else None,
                            scaleanchor=f"x{sufixo}", constrain="domain", row=1, col=coluna)

    figura.update_layout(template="plotly_dark", paper_bgcolor="black", plot_bgcolor="black",
                         height=460, margin=dict(l=40, r=10, t=40, b=40))
    return figura


def figura_evolucao(historico, total_celulas: int, passo_atual: int | None = None) -> go.Figure:
    """
        Células vivas por iteração, com o passo escolhido destacado.
        historico: células vivas em cada passo, do 0 (seed) ao último.
        total_celulas: tamanho do volume, para o eixo em porcentagem.
        passo_atual: passo marcado em destaque, ou None.
    """
    historico = np.asarray(historico)
    passos = np.arange(historico.size)
    porcentagem = 100 * historico / total_celulas

    figura = go.Figure(go.Scatter(
        x=passos, y=porcentagem,
        mode="lines+markers",
        line=dict(color=COR_CAIXA, width=2),
        marker=dict(color=COR_CAIXA, size=8, line=dict(color="black", width=2)),
        customdata=historico,
        hovertemplate="iteracao %{x}<br>%{customdata:,d} celulas vivas"
                      "<br>%{y:.1f}% do volume<extra></extra>",
        showlegend=False,
    ))
    if passo_atual is not None:
        figura.add_trace(go.Scatter(
            x=[passo_atual], y=[porcentagem[passo_atual]], mode="markers",
            marker=dict(color=COR_VAZIO, size=14, line=dict(color="black", width=2)),
            hoverinfo="skip", showlegend=False,
        ))

    figura.update_layout(
        template="plotly_dark", paper_bgcolor="black", plot_bgcolor="black",
        height=320, margin=dict(l=50, r=10, t=10, b=40),
        xaxis=dict(title="iterações", tickformat="d",
                   dtick=max(1, int(np.ceil(passos.size / 10))), gridcolor="#333333"),
        yaxis=dict(title="% de vazio", gridcolor="#333333", ticksuffix="%"),
    )
    return figura
