"""
    Separa borda e interno da caverna por inundação.

    A água entra pelas bordas da grade e se espalha pelos vazios de face em
    face, sem atravessar voxel cheio (binary_fill_holes, conectividade 6). O
    vazio que a água não alcança é buraco fechado.

    Classificação:
    0: vazio, o que a água alcança (não é plotado).
    1: borda, cheio que encosta na água por alguma face (inundável).
    2: interno, tudo o que a água não alcança e não é borda: os cheios que não
       encostam na água e os buracos fechados.

    A borda fica no 1 de propósito: no plot ela sai translúcida e deixa ver o
    interno, que sai opaco.

    Fora da grade conta como água, então voxel cheio na borda da grade é 1.

    uv run python sdf_temp/inundacao.py
"""
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from scipy.ndimage import binary_fill_holes, convolve

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    gizmo_eixos,
)

PASTA = Path(__file__).resolve().parent
ENTRADA = PASTA / "entrada" / "elaphes_surface_64.npz"
SAIDA_NPZ = PASTA / "npz" / "elaphes_surface_64_inundacao.npz"
SAIDA_PLOT = PASTA / "plots" / "elaphes_surface_64_inundacao.html"

VAZIO = 0
BORDA = 1
INTERNO = 2

# Cruz 3D: só os 6 vizinhos de face valem 1, o centro fica fora da conta.
KERNEL_FACES = np.zeros((3, 3, 3), dtype=np.int16)
KERNEL_FACES[0, 1, 1] = KERNEL_FACES[2, 1, 1] = 1
KERNEL_FACES[1, 0, 1] = KERNEL_FACES[1, 2, 1] = 1
KERNEL_FACES[1, 1, 0] = KERNEL_FACES[1, 1, 2] = 1

# Magma começa no preto, então o vazio coincide com o fundo; a borda cai no
# magenta do meio e o interno no amarelo claro do topo.
PALETA = "Magma"
NOMES = {BORDA: "borda (1)", INTERNO: "interno (2)"}
ESCALA = ["0 vazio", "1 borda", "2 interno"]

def inundar(cheio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
        Devolve (agua, buracos_fechados): os vazios ligados ao lado de fora da
        grade e os vazios que a água não alcança.
        cheio: matriz booleana (depth, height, width).
    """
    buracos_fechados = binary_fill_holes(cheio) & ~cheio
    agua = ~cheio & ~buracos_fechados
    return agua, buracos_fechados

def classificar_por_inundacao(cheio: np.ndarray, agua: np.ndarray) -> np.ndarray:
    """
        Monta a matriz com 0 (vazio), 1 (borda) e 2 (interno).
        O interno é o complemento da água sem a borda, então os buracos
        fechados entram nele junto com os cheios que não encostam na água.
        cheio: matriz booleana (depth, height, width).
        agua: vazios ligados ao lado de fora, de inundar().
    """
    # cval=1: o que está fora da grade é água também.
    encosta_na_agua = convolve(agua.astype(np.int16), KERNEL_FACES, mode="constant", cval=1) > 0

    classificacao = np.full(cheio.shape, VAZIO, dtype=np.uint8)
    classificacao[~agua] = INTERNO
    classificacao[cheio & encosta_na_agua] = BORDA
    return classificacao

def opacidade(rotulo: int) -> float:
    """
        Degradê linear de opacidade: rótulo / máximo.
        O vazio daria 0, mas nunca chega aqui porque não é plotado.
        rotulo: valor da classificação.
    """
    return rotulo / INTERNO

def trace_do_rotulo(classificacao: np.ndarray, rotulo: int, com_escala: bool) -> go.Scatter3d:
    """
        Um Scatter3d por rótulo: o plotly só aceita uma opacidade por trace.
        Mesma troca de eixos do plot de referência do Elaphes: x é a largura,
        y é a profundidade e z é a altura da grade (depth, height, width).
        classificacao: matriz com 0, 1 e 2.
        rotulo: valor plotado nesse trace.
        com_escala: desenha a barra de cores (só um dos traces precisa).
    """
    indices = np.argwhere(classificacao == rotulo)
    x, y, z = indices[:, 2], indices[:, 0], indices[:, 1]
    escala = dict(
        title=dict(text="inundação", font=dict(color="white", size=12)),
        tickvals=list(range(len(ESCALA))), ticktext=ESCALA,
        x=-0.06, xanchor="left", len=0.75, thickness=14,
        bgcolor="black", outlinecolor="white", outlinewidth=1,
        tickfont=dict(color="white", size=11),
    )

    return go.Scatter3d(
        x=x, y=y, z=z,
        mode="markers",
        marker=dict(
            size=4,
            color=np.full(x.size, rotulo),
            colorscale=PALETA,
            cmin=VAZIO,
            cmax=INTERNO,
            opacity=opacidade(rotulo),
            showscale=com_escala,
            colorbar=escala if com_escala else None,
        ),
        hovertemplate=f"(%{{x}}, %{{y}}, %{{z}})<br>{NOMES[rotulo]}<extra></extra>",
        showlegend=False,
    )

def figura(classificacao: np.ndarray, titulo: str) -> go.Figure:
    """
        Monta a figura com borda, interno, caixa e gizmo, no estilo dos plots do CA.
        classificacao: matriz com 0, 1 e 2.
        titulo: texto do topo da figura.
    """
    profundidade, altura, largura = classificacao.shape
    minimos = [-0.5, -0.5, -0.5]
    maximos = [largura - 0.5, profundidade - 0.5, altura - 0.5]
    olho = camera_isometrica()

    fig = go.Figure()
    # Começa na borda de propósito: o vazio é a maior parte da grade e não vira ponto.
    for rotulo in (BORDA, INTERNO):
        fig.add_trace(trace_do_rotulo(classificacao, rotulo, com_escala=rotulo == INTERNO))
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
    cheio = dados["surface_voxels"].astype(bool)

    agua, buracos_fechados = inundar(cheio)
    classificacao = classificar_por_inundacao(cheio, agua)

    borda = int((classificacao == BORDA).sum())
    interno = int((classificacao == INTERNO).sum())
    buracos = int(buracos_fechados.sum())

    SAIDA_NPZ.parent.mkdir(exist_ok=True)
    np.savez_compressed(
        SAIDA_NPZ,
        classificacao=classificacao,
        agua=agua.astype(np.uint8),
        buracos_fechados=buracos_fechados.astype(np.uint8),
        metadata=dados["metadata"],
    )

    largura = cheio.shape[2]
    titulo = (f"Elaphes {largura}^3 - inundação: {borda} borda, {interno} interno "
              f"({buracos} deles eram buracos fechados)")
    SAIDA_PLOT.parent.mkdir(exist_ok=True)
    figura(classificacao, titulo).write_html(SAIDA_PLOT, include_plotlyjs="cdn")

    print(f"cheios: {int(cheio.sum())}, água: {int(agua.sum())}, buracos fechados: {buracos}")
    print(f"borda (1): {borda}, interno (2): {interno}")
    print(f"npz salvo em {SAIDA_NPZ}")
    print(f"figura salva em {SAIDA_PLOT}")

if __name__ == "__main__":
    main()
