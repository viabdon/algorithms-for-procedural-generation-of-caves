"""Visualizacao volumetrica 3D no estilo radar/sonar/GPR.

Fundo preto, colormap jet, caixa wireframe (arestas de tras pontilhadas) e um
gizmo de eixos no canto. Interativo, via plotly.

    # o resultado do refatora.py (matriz 5x5x5 de contagem de vizinhos)
    uv run python src/cavegen/generators/cellular_automata/refatora_test.py

    # ou um volume gerado pelo CA, colorido pela contagem de vizinhos abertos
    uv run python src/cavegen/generators/cellular_automata/refatora_test.py results/volumes/ca_seed001_outside_open_it5_t13.npz
"""

import contextlib
import io
import sys
from itertools import product
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

sys.path.append(str(Path(__file__).resolve().parent))

RAIZ_PROJETO = Path(__file__).resolve().parents[4]
PASTA_FIGURAS = RAIZ_PROJETO / "results" / "figures"

# Vista isometrica: elevacao 25 graus, azimute -55 graus.
ELEVACAO, AZIMUTE, RAIO = 25.0, -55.0, 1.9

COR_CAIXA = "#ffffff"
CORES_GIZMO = {"X": "#00e676", "Y": "#2196f3", "Z": "#b388ff"}  # verde, azul, roxo


def camera_isometrica(elevacao=ELEVACAO, azimute=AZIMUTE, raio=RAIO):
    """Converte elevacao/azimute (convencao matplotlib) para o eye do plotly."""
    e, a = np.radians(elevacao), np.radians(azimute)
    return dict(x=raio * np.cos(e) * np.cos(a),
                y=raio * np.cos(e) * np.sin(a),
                z=raio * np.sin(e))


def _arestas(minimos, maximos):
    """Os 8 cantos e as 12 arestas da caixa delimitadora."""
    cantos = [np.array(c) for c in product(*zip(minimos, maximos))]
    arestas = [
        (a, b)
        for i, a in enumerate(cantos)
        for b in cantos[i + 1:]
        if int((a != b).sum()) == 1
    ]
    return cantos, arestas


def caixa_wireframe(minimos, maximos, olho):
    """Caixa branca fina. Arestas do canto mais distante da camera: pontilhadas.

    O canto oculto e o de menor projecao na direcao da camera; as tres arestas
    que saem dele sao exatamente as que ficariam escondidas atras do volume.
    """
    minimos, maximos = np.asarray(minimos, float), np.asarray(maximos, float)
    centro = (minimos + maximos) / 2
    direcao = np.array([olho["x"], olho["y"], olho["z"]])

    cantos, arestas = _arestas(minimos, maximos)
    oculto = min(cantos, key=lambda c: float(np.dot(c - centro, direcao)))

    traces = []
    for tracejada, estilo in ((True, "dot"), (False, "solid")):
        pontos = []
        for a, b in arestas:
            toca_oculto = np.array_equal(a, oculto) or np.array_equal(b, oculto)
            if toca_oculto == tracejada:
                pontos += [a, b, np.full(3, np.nan)]  # NaN quebra a linha
        if not pontos:
            continue
        pontos = np.array(pontos)
        traces.append(
            go.Scatter3d(
                x=pontos[:, 0], y=pontos[:, 1], z=pontos[:, 2],
                mode="lines",
                line=dict(color=COR_CAIXA, width=2, dash=estilo),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return traces


def gizmo_eixos(minimos, maximos):
    """Tres setas curtas saindo de um ponto comum, no canto inferior esquerdo."""
    minimos, maximos = np.asarray(minimos, float), np.asarray(maximos, float)
    extensao = float(np.max(maximos - minimos))
    comprimento = 0.18 * extensao
    origem = minimos - 0.10 * extensao

    traces = []
    for eixo, (rotulo, cor) in enumerate(CORES_GIZMO.items()):
        direcao = np.zeros(3)
        direcao[eixo] = comprimento
        ponta = origem + direcao

        traces.append(
            go.Scatter3d(
                x=[origem[0], ponta[0]], y=[origem[1], ponta[1]], z=[origem[2], ponta[2]],
                mode="lines",
                line=dict(color=cor, width=5),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        traces.append(
            go.Cone(
                x=[ponta[0]], y=[ponta[1]], z=[ponta[2]],
                u=[direcao[0]], v=[direcao[1]], w=[direcao[2]],
                sizemode="absolute", sizeref=0.35 * comprimento, anchor="tip",
                colorscale=[[0, cor], [1, cor]], showscale=False,
                hoverinfo="skip",
            )
        )
        rotulo_pos = origem + direcao * 1.45
        traces.append(
            go.Scatter3d(
                x=[rotulo_pos[0]], y=[rotulo_pos[1]], z=[rotulo_pos[2]],
                mode="text",
                text=[rotulo],
                textfont=dict(color=cor, size=13),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return traces


def figura_volumetrica(x, y, z, valores, titulo, minimos=None, maximos=None,
                       rotulo_escala="intensidade"):
    x, y, z, valores = (np.asarray(v) for v in (x, y, z, valores))
    minimos = np.asarray(minimos if minimos is not None
                         else [x.min() - 0.5, y.min() - 0.5, z.min() - 0.5], float)
    maximos = np.asarray(maximos if maximos is not None
                         else [x.max() + 0.5, y.max() + 0.5, z.max() + 0.5], float)

    # Nuvens densas pedem ponto pequeno; poucos pontos somem se ficarem 2px.
    tamanho = 2 if valores.size > 5_000 else 6

    olho = camera_isometrica()
    figura = go.Figure()

    figura.add_trace(
        go.Scatter3d(
            x=x, y=y, z=z,
            mode="markers",
            marker=dict(
                size=tamanho,
                color=valores,
                colorscale="Jet",
                opacity=0.7,
                showscale=True,
                colorbar=dict(
                    title=dict(text=rotulo_escala, font=dict(color="white", size=12)),
                    x=-0.06, xanchor="left", len=0.75, thickness=14,
                    bgcolor="black", outlinecolor="white", outlinewidth=1,
                    tickfont=dict(color="white", size=11),
                ),
            ),
            hovertemplate="(%{x}, %{y}, %{z})<br>" + rotulo_escala + "=%{marker.color}<extra></extra>",
            showlegend=False,
        )
    )

    for trace in caixa_wireframe(minimos, maximos, olho) + gizmo_eixos(minimos, maximos):
        figura.add_trace(trace)

    eixo_limpo = dict(
        showgrid=False, zeroline=False, showticklabels=False, showbackground=False,
        showspikes=False, title="", visible=False,
    )
    figura.update_layout(
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
    return figura


def dados_do_refatora():
    """Matriz 5x5x5 de contagem de vizinhos produzida pelo refatora.py."""
    with contextlib.redirect_stdout(io.StringIO()):
        from refatora import cellular_automata, matrix
        contagens = cellular_automata(matrix)

    eixo_x, eixo_y, eixo_z = np.indices(contagens.shape)
    return (eixo_x.ravel(), eixo_y.ravel(), eixo_z.ravel(), contagens.ravel(),
            f"refatora.py - contagem de vizinhos {contagens.shape}", "vizinhos")


def dados_do_volume(caminho):
    """Volume do CA: plota so os voxels abertos, coloridos pela contagem de vizinhos."""
    from cavegen.generators.cellular_automata.borders import BorderMode, count_open_neighbors
    from cavegen.io.voxel_io import load_volume_npz

    caminho = Path(caminho)
    volume = load_volume_npz(caminho if caminho.is_absolute() else RAIZ_PROJETO / caminho)
    contagens = count_open_neighbors(volume.data, BorderMode.OUTSIDE_SOLID)

    abertos = np.argwhere(volume.data)
    valores = contagens[volume.data]
    return (abertos[:, 2], abertos[:, 1], abertos[:, 0], valores,
            f"{caminho.stem} - {len(valores)} voxels abertos", "vizinhos abertos")


def main(argumento=None, mostrar=True):
    argumento = argumento if argumento is not None else (sys.argv[1] if len(sys.argv) > 1 else None)
    x, y, z, valores, titulo, rotulo = (
        dados_do_volume(argumento) if argumento else dados_do_refatora()
    )
    print(f"{titulo}\npontos: {valores.size}  faixa: {valores.min()} a {valores.max()}")

    figura = figura_volumetrica(x, y, z, valores, titulo, rotulo_escala=rotulo)

    PASTA_FIGURAS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_FIGURAS / (
        f"{Path(argumento).stem}_volumetrico.html" if argumento else "refatora_volumetrico.html"
    )
    figura.write_html(destino, include_plotlyjs="cdn")
    print("figura salva em:", destino)

    if mostrar:
        figura.show()


if __name__ == "__main__":
    main()
