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

    Plot: paleta Emrld do plotly, do verde claro (mais negativo) ao
    verde-azulado escuro (mais positivo). A opacidade sobe em linha reta do CORTE_NEGATIVO
    (transparente) até o valor mais positivo (opaco). Abaixo do corte o voxel
    nem entra no plot.

    uv run python sdf_temp/sdf.py
"""
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from scipy.ndimage import distance_transform_edt

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    gizmo_eixos,
)

from inundacao import BORDA, INTERNO

PASTA = Path(__file__).resolve().parent
ENTRADA = PASTA / "npz" / "elaphes_surface_64_inundacao.npz"
SAIDA_NPZ = PASTA / "npz" / "elaphes_surface_64_sdf.npz"
SAIDA_PLOT = PASTA / "plots" / "elaphes_surface_64_sdf.html"

# 1: interno positivo e externo negativo. -1 inverte para a convenção do projeto.
SINAL_INTERNO = 1
CONVENCAO = "interno positivo, externo negativo, borda 0; distância em voxels"

# Onde a opacidade chega a 0: o que está abaixo disso não é plotado.
CORTE_NEGATIVO = -5.0

PALETA = "Emrld"

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

def opacidade(valor: float, maximo: float) -> float:
    """
        Rampa linear: o CORTE_NEGATIVO fica 100% transparente e o valor mais
        positivo fica opaco.
        valor: nível do SDF.
        maximo: maior valor do SDF.
    """
    return (valor - CORTE_NEGATIVO) / (maximo - CORTE_NEGATIVO)

def regiao(valor: float) -> str:
    """
        Nome da região de um nível do SDF, para o hover.
        valor: nível do SDF.
    """
    if valor > 0:
        return "interno"
    return "borda" if valor == 0 else "externo"

def trace_do_nivel(sdf: np.ndarray, valor: float, maximo: float,
                   com_escala: bool) -> go.Scatter3d:
    """
        Um Scatter3d por nível: o plotly só aceita uma opacidade por trace.
        Numa grade de voxels as distâncias são raízes de inteiros, então os
        níveis se repetem muito e viram poucas dezenas de traces.
        Mesma troca de eixos dos outros plots: x é a largura, y é a
        profundidade e z é a altura da grade (depth, height, width).
        sdf: campo com sinal.
        valor: nível plotado nesse trace.
        maximo: maior valor do SDF, topo da escala de cor e da opacidade.
        com_escala: desenha a barra de cores (só um dos traces precisa).
    """
    indices = np.argwhere(sdf == valor)
    x, y, z = indices[:, 2], indices[:, 0], indices[:, 1]
    marcas = list(range(int(CORTE_NEGATIVO), int(np.floor(maximo)) + 1))
    escala = dict(
        title=dict(text="SDF (voxels)", font=dict(color="white", size=12)),
        tickvals=marcas,
        x=-0.06, xanchor="left", len=0.75, thickness=14,
        bgcolor="black", outlinecolor="white", outlinewidth=1,
        tickfont=dict(color="white", size=11),
    )

    return go.Scatter3d(
        x=x, y=y, z=z,
        mode="markers",
        marker=dict(
            size=4,
            color=np.full(x.size, valor),
            colorscale=PALETA,
            cmin=CORTE_NEGATIVO,
            cmax=maximo,
            opacity=opacidade(valor, maximo),
            showscale=com_escala,
            colorbar=escala if com_escala else None,
        ),
        hovertemplate=f"(%{{x}}, %{{y}}, %{{z}})<br>{regiao(valor)}: {valor:.2f}<extra></extra>",
        showlegend=False,
    )

def figura(sdf: np.ndarray, titulo: str) -> go.Figure:
    """
        Monta a figura com um trace por nível acima do corte, caixa e gizmo,
        no estilo dos plots do CA.
        sdf: campo com sinal.
        titulo: texto do topo da figura.
    """
    profundidade, altura, largura = sdf.shape
    minimos = [-0.5, -0.5, -0.5]
    maximos = [largura - 0.5, profundidade - 0.5, altura - 0.5]
    olho = camera_isometrica()
    maximo = float(sdf.max())

    fig = go.Figure()
    # Do mais negativo ao mais positivo: o interno, opaco, é desenhado por último.
    niveis = np.unique(sdf[sdf > CORTE_NEGATIVO]).tolist()
    for valor in niveis:
        fig.add_trace(trace_do_nivel(sdf, valor, maximo, com_escala=valor == niveis[-1]))
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
        margin=dict(l=110, r=10, t=50, b=10),
        scene=dict(
            xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
            bgcolor="black",
            aspectmode="data",
            camera=dict(eye=olho),
        ),
    )
    return fig

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

    plotados = int((sdf > CORTE_NEGATIVO).sum())
    largura = sdf.shape[2]
    titulo = (f"Elaphes {largura}^3 - SDF (interno +, externo -): {plotados} voxels "
              f"acima de {CORTE_NEGATIVO:g}")
    SAIDA_PLOT.parent.mkdir(exist_ok=True)
    figura(sdf, titulo).write_html(SAIDA_PLOT, include_plotlyjs="cdn")

    print(f"borda: {int(borda.sum())}, interno: {int(interno.sum())}")
    print(f"sdf de {sdf.min():.2f} (externo) a {sdf.max():.2f} (interno)")
    print(f"plotados {plotados} voxels acima de {CORTE_NEGATIVO:g}")
    print(f"npz salvo em {SAIDA_NPZ}")
    print(f"figura salva em {SAIDA_PLOT}")

if __name__ == "__main__":
    main()
