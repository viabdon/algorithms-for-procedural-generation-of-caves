"""Figuras Plotly compartilhadas e visualização de um Volume3D salvo em NPZ."""

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.colors import get_colorscale, sample_colorscale, unlabel_rgb
from plotly.subplots import make_subplots

from cavegen.datastream.voxel_io import load_volume_npz

# Vista isometrica: elevacao 25 graus, azimute -55 graus.
ELEVACAO, AZIMUTE, RAIO = 25.0, -55.0, 1.9

COR_CAIXA = "#ffffff"
CORES_GIZMO = {"X": "#00e676", "Y": "#2196f3", "Z": "#b388ff"}  # verde, azul, roxo

# Faixa da altura da figura (0 = base, 1 = topo) ocupada pelo grafico de linha.
FAIXA_VERTICAL_HISTORICO = (0.2, 0.8)

# Contraste minimo de uma linha contra o fundo preto (WCAG para elementos graficos).
# As pontas escuras das paletas sumiriam no fundo, entao ficam de fora das linhas.
CONTRASTE_MINIMO_LINHA = 3.0

def camera_isometrica(elevacao=ELEVACAO, azimute=AZIMUTE, raio=RAIO):
    """Converte elevacao/azimute (convencao matplotlib) para o eye do plotly."""
    e, a = np.radians(elevacao), np.radians(azimute)
    return dict(x=raio * np.cos(e) * np.cos(a),
                y=raio * np.cos(e) * np.sin(a),
                z=raio * np.sin(e))


def cena_plotly(olho):
    """Configura os eixos, as proporções e a câmera dos plots de voxels."""
    eixo_limpo = dict(
        showgrid=False, zeroline=False, showticklabels=False, showbackground=False,
        showspikes=False, title="", visible=False,
    )
    return dict(xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
                bgcolor="black", aspectmode="data", camera=dict(eye=olho))


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


def contraste_no_preto(cor):
    """
        Contraste WCAG de uma cor contra o fundo preto.
        cor: texto "rgb(r, g, b)".
    """
    canais = np.array(unlabel_rgb(cor)) / 255
    lineares = np.where(canais <= 0.03928, canais / 12.92, ((canais + 0.055) / 1.055) ** 2.4)
    luminancia = float(lineares @ np.array([0.2126, 0.7152, 0.0722]))
    return (luminancia + 0.05) / 0.05

def cores_das_linhas(paleta):
    """
        Três cores da paleta para as linhas: a primeira, a do meio e a última entre
        as que aparecem no fundo preto. Devolve (vivas, viraram_1, viraram_0).
        paleta: nome de uma escala de cor do plotly, como as de PALETAS.
    """
    amostras = sample_colorscale(get_colorscale(paleta), np.linspace(0, 1, 101).tolist())
    visiveis = [cor for cor in amostras if contraste_no_preto(cor) >= CONTRASTE_MINIMO_LINHA]
    return visiveis[0], visiveis[len(visiveis) // 2], visiveis[-1]

def trace_da_linha(passos, valores, nome, cor, simbolo, tracejado, total_celulas, com_legenda):
    """
        Uma linha do gráfico de histórico. O traço e o símbolo também mudam de uma
        linha para outra, para a leitura não depender só da cor.
        passos, valores: pontos da linha.
        nome: texto da legenda e do hover.
        cor, simbolo, tracejado: aparência da linha.
        total_celulas: tamanho do volume, para mostrar a porcentagem no hover.
        com_legenda: mostra a linha na legenda.
    """
    # Anel preto separa os marcadores da linha quando os pontos ficam colados.
    return go.Scatter(
        x=passos, y=valores,
        mode="lines+markers",
        name=nome,
        line=dict(color=cor, width=2, dash=tracejado),
        marker=dict(color=cor, size=9, symbol=simbolo, line=dict(color="black", width=2)),
        customdata=100 * valores / total_celulas,
        hovertemplate=("iteracao %{x}<br>%{y} " + nome +
                       "<br>%{customdata:.1f}% do volume<extra></extra>"),
        showlegend=com_legenda,
    )

def adicionar_historico(figura, historico, total_celulas, viraram_1=None, viraram_0=None,
                        paleta="Jet"):
    """
        Linhas de células por iteração, no painel 2D da direita.
        figura: figura de make_subplots com o painel xy na coluna 2.
        historico: células vivas em cada passo, do 0 (seed) ao último.
        total_celulas: tamanho do volume, para mostrar a porcentagem no hover.
        viraram_1, viraram_0: células que mudaram em cada iteração; resultados
                              antigos não têm, e ficam só com a linha de vivas.
        paleta: de onde saem as cores das linhas.
    """
    historico = np.asarray(historico)
    passos = np.arange(historico.size)
    com_transicoes = viraram_1 is not None and viraram_0 is not None
    cor_vivas, cor_1, cor_0 = cores_das_linhas(paleta)

    figura.add_trace(
        trace_da_linha(passos, historico, "celulas vivas", cor_vivas, "circle", "solid",
                       total_celulas, com_transicoes),
        row=1, col=2,
    )
    if com_transicoes:
        # A transição acontece entre dois passos: a primeira chega no passo 1.
        iteracoes = np.arange(1, np.asarray(viraram_1).size + 1)
        figura.add_trace(
            trace_da_linha(iteracoes, np.asarray(viraram_1), "viraram 1", cor_1, "triangle-up",
                           "dash", total_celulas, True),
            row=1, col=2,
        )
        figura.add_trace(
            trace_da_linha(iteracoes, np.asarray(viraram_0), "viraram 0", cor_0, "triangle-down",
                           "dot", total_celulas, True),
            row=1, col=2,
        )
        figura.update_layout(legend=dict(
            font=dict(color="white", size=12), bgcolor="rgba(0,0,0,0)",
            x=0.99, xanchor="right", y=FAIXA_VERTICAL_HISTORICO[1] - 0.01, yanchor="top",
        ))

    eixo = dict(
        color="white", gridcolor="#333333", zeroline=False,
        showline=True, linecolor="#666666", tickfont=dict(size=11),
    )
    figura.update_xaxes(eixo, title_text="iterações", tickformat="d",
                        dtick=max(1, int(np.ceil(passos.size / 10))), row=1, col=2)
    # O painel ocupa so a faixa central da altura: na altura toda da figura a
    # linha ficava alta e estreita demais ao lado do 3D.
    figura.update_yaxes(eixo, title_text="celulas" if com_transicoes else "celulas vivas",
                        tickformat=",d", domain=list(FAIXA_VERTICAL_HISTORICO), row=1, col=2)

    inicio, fim = figura.layout.xaxis.domain
    figura.add_annotation(
        text="celulas por iteração" if com_transicoes else "celulas vivas por iteração",
        x=(inicio + fim) / 2, y=FAIXA_VERTICAL_HISTORICO[1],
        xref="paper", yref="paper", xanchor="center", yanchor="bottom",
        yshift=8, showarrow=False, font=dict(color="white", size=13),
    )


def trace_da_nuvem(x, y, z, valores, tamanho, paleta, limites_cor, opacidade,
                   rotulo_escala, com_escala):
    """
        Um Scatter3d da nuvem com uma única opacidade (o plotly só aceita uma por trace).
        com_escala: desenha a barra de cores (só um dos traces precisa).
    """
    cor_minima, cor_maxima = limites_cor
    return go.Scatter3d(
        x=x, y=y, z=z,
        mode="markers",
        marker=dict(
            size=tamanho,
            color=valores,
            colorscale=paleta,
            cmin=cor_minima,
            cmax=cor_maxima,
            opacity=opacidade,
            showscale=com_escala,
            colorbar=dict(
                title=dict(text=rotulo_escala, font=dict(color="white", size=12)),
                x=-0.06, xanchor="left", len=0.75, thickness=14,
                bgcolor="black", outlinecolor="white", outlinewidth=1,
                tickfont=dict(color="white", size=11),
            ) if com_escala else None,
        ),
        hovertemplate="(%{x}, %{y}, %{z})<br>" + rotulo_escala + "=%{marker.color}<extra></extra>",
        showlegend=False,
    )


def figura_volumetrica(x, y, z, valores, titulo, minimos=None, maximos=None,
                    rotulo_escala="intensidade", limites_cor=None,
                    historico=None, total_celulas=None, paleta="Jet", opacidades=None,
                    viraram_1=None, viraram_0=None):
    """
        Nuvem 3D; com historico, ganha ao lado as linhas de células por iteração.
        historico: células vivas em cada passo, do 0 (seed) ao último.
        total_celulas: tamanho do volume, para mostrar a porcentagem no hover.
        paleta: nome de uma escala de cor do plotly, como as de PALETAS.
        opacidades: opacidade de cada ponto; sem ela, a nuvem toda fica com 0.7.
        viraram_1, viraram_0: células que mudaram em cada iteração, se conhecidas.
    """
    x, y, z, valores = (np.asarray(v) for v in (x, y, z, valores))
    # Sem limites explicitos o plotly normaliza pelo min/max dos proprios dados,
    # o que muda a leitura da cor de um resultado para outro.
    limites_cor = limites_cor if limites_cor is not None else (None, None)
    minimos = np.asarray(minimos if minimos is not None
                        else [x.min() - 0.5, y.min() - 0.5, z.min() - 0.5], float)
    maximos = np.asarray(maximos if maximos is not None
                        else [x.max() + 0.5, y.max() + 0.5, z.max() + 0.5], float)

    # Nuvens densas pedem ponto pequeno; poucos pontos somem se ficarem 2px.
    tamanho = 2 if valores.size > 5_000 else 6

    olho = camera_isometrica()
    com_historico = historico is not None
    if com_historico:
        figura = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "scene"}, {"type": "xy"}]],
            column_widths=[0.6, 0.4],
            horizontal_spacing=0.06,
        )
        celula_3d = dict(row=1, col=1)
    else:
        figura = go.Figure()
        celula_3d = {}

    if opacidades is None:
        figura.add_trace(
            trace_da_nuvem(x, y, z, valores, tamanho, paleta, limites_cor, 0.7,
                           rotulo_escala, com_escala=True),
            **celula_3d,
        )
    else:
        # Um trace por opacidade, do mais transparente ao opaco: o opaco é
        # desenhado por último e não fica escondido atrás do translúcido.
        opacidades = np.asarray(opacidades)
        niveis = np.unique(opacidades)
        for nivel in niveis:
            dentro = opacidades == nivel
            figura.add_trace(
                trace_da_nuvem(x[dentro], y[dentro], z[dentro], valores[dentro], tamanho,
                               paleta, limites_cor, float(nivel), rotulo_escala,
                               com_escala=bool(nivel == niveis[-1])),
                **celula_3d,
            )

    for trace in caixa_wireframe(minimos, maximos, olho) + gizmo_eixos(minimos, maximos):
        figura.add_trace(trace, **celula_3d)

    if com_historico:
        adicionar_historico(figura, historico, total_celulas, viraram_1, viraram_0, paleta)

    figura.update_layout(
        title=dict(text=titulo, font=dict(color="white", size=14), x=0.5),
        paper_bgcolor="black",
        plot_bgcolor="black",
        width=1400 if com_historico else 950, height=800,
        margin=dict(l=110, r=10, t=50, b=10),
        scene=cena_plotly(olho),
    )
    return figura


def dados_da_matriz(matrix):
    """Converte a máscara (profundidade, altura, largura) para os eixos da figura."""
    profundidade, altura, largura = np.nonzero(matrix)
    return largura, profundidade, altura


def figura_do_volume(volume, titulo):
    """Desenha os voxels de ar de um Volume3D em coordenadas XYZ."""
    # O contrato do benchmark é ZYX. No gráfico, a altura é Z.
    abertos = np.flatnonzero(volume.data)
    max_pontos = 120_000
    if abertos.size > max_pontos:
        amostra = np.linspace(0, abertos.size - 1, max_pontos, dtype=np.intp)
        abertos = abertos[amostra]
    z, y, x = np.unravel_index(abertos, volume.shape)
    return figura_volumetrica(
        x, y, z, z, titulo, minimos=[-0.5] * 3,
        maximos=np.asarray(volume.shape[::-1]) - 0.5, rotulo_escala="Z (voxel)",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grava um HTML Plotly ao lado do volume NPZ.")
    parser.add_argument("volume", type=Path, help="Volume3D do benchmark (ZYX, True = ar)")
    caminho = parser.parse_args(argv).volume
    if caminho.suffix.lower() != ".npz":
        parser.error("informe um volume .npz")
    volume = load_volume_npz(caminho)
    figura = figura_do_volume(volume, caminho.stem)
    destino = caminho.with_suffix(".html")
    figura.write_html(destino)
    print(destino)


if __name__ == "__main__":
    main()
