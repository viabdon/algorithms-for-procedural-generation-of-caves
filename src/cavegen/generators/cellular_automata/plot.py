"""Visualizacao volumetrica 3D no estilo radar/sonar/GPR.

Le um volume ja processado pelo CA (pasta results/) e monta a figura interativa
do plotly: fundo preto, caixa wireframe (arestas de tras pontilhadas) e um
gizmo de eixos no canto.

A cor vem da altura da celula ou da quantidade de vizinhos vivos dela, em uma
das PALETAS. Por vizinhos, a opacidade tambem acompanha a contagem: a celula
com menos vizinhos fica meio transparente e a mais cercada, opaca.

O HTML vai para plots/, ao lado do codigo, e o caminho e impresso para copiar
no navegador. A pasta results/ guarda apenas os npz.

    uv run python -m cavegen.generators.cellular_automata.plot 1 [altura|vizinhos] [paleta]
"""

import sys
from itertools import product
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cavegen.generators.cellular_automata.generator import neighbor_counts
from cavegen.generators.cellular_automata.results import RESULTS_DIR, load_result
from cavegen.generators.cellular_automata.storage import storage_dir

# Figuras ficam no pacote, nao no temp do sistema: o caminho e estavel e curto,
# da para abrir pelo explorador de arquivos e colar no navegador.
PASTA_FIGURAS = storage_dir("plots")

# Vista isometrica: elevacao 25 graus, azimute -55 graus.
ELEVACAO, AZIMUTE, RAIO = 25.0, -55.0, 1.9

COR_CAIXA = "#ffffff"
CORES_GIZMO = {"X": "#00e676", "Y": "#2196f3", "Z": "#b388ff"}  # verde, azul, roxo

# Faixa da altura da figura (0 = base, 1 = topo) ocupada pelo grafico de linha.
FAIXA_VERTICAL_HISTORICO = (0.2, 0.8)

MODOS_COR = ("altura", "vizinhos")

# A Jet e a paleta de sempre; as outras vao do claro ao escuro, entao a celula
# com menos vizinhos (ou mais baixa) fica mais clara.
PALETAS = ("Jet", "Mint", "Purp", "Teal", "Sunsetdark", "Emrld", "Burg")

# A celula viva entra na propria contagem, entao ela tem de 1 a 27 vizinhos.
MIN_VIZINHOS, MAX_VIZINHOS = 1, 27

# Opacidade da celula com menos vizinhos; a mais cercada fica opaca (1.0).
OPACIDADE_MINIMA = 0.25


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


def adicionar_historico(figura, historico, total_celulas):
    """
        Linha de células vivas por iteração, no painel 2D da direita.
        figura: figura de make_subplots com o painel xy na coluna 2.
        historico: células vivas em cada passo, do 0 (seed) ao último.
        total_celulas: tamanho do volume, para mostrar a porcentagem no hover.
    """
    historico = np.asarray(historico)
    passos = np.arange(historico.size)
    porcentagem = 100 * historico / total_celulas

    figura.add_trace(
        go.Scatter(
            x=passos, y=historico,
            mode="lines+markers",
            line=dict(color=COR_CAIXA, width=2),
            # Anel preto separa os marcadores da linha quando os pontos ficam colados.
            marker=dict(color=COR_CAIXA, size=8, line=dict(color="black", width=2)),
            customdata=porcentagem,
            hovertemplate=("iteracao %{x}<br>%{y} celulas vivas"
                            "<br>%{customdata:.1f}% do volume<extra></extra>"),
            showlegend=False,
        ),
        row=1, col=2,
    )

    eixo = dict(
        color="white", gridcolor="#333333", zeroline=False,
        showline=True, linecolor="#666666", tickfont=dict(size=11),
    )
    figura.update_xaxes(eixo, title_text="iterações", tickformat="d",
                        dtick=max(1, int(np.ceil(passos.size / 10))), row=1, col=2)
    # O painel ocupa so a faixa central da altura: na altura toda da figura a
    # linha ficava alta e estreita demais ao lado do 3D.
    figura.update_yaxes(eixo, title_text="celulas vivas", tickformat=",d",
                        domain=list(FAIXA_VERTICAL_HISTORICO), row=1, col=2)

    inicio, fim = figura.layout.xaxis.domain
    figura.add_annotation(
        text="celulas vivas por iteração",
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
                    historico=None, total_celulas=None, paleta="Jet", opacidades=None):
    """
        Nuvem 3D; com historico, ganha ao lado a linha de células vivas por iteração.
        historico: células vivas em cada passo, do 0 (seed) ao último.
        total_celulas: tamanho do volume, para mostrar a porcentagem no hover.
        paleta: nome de uma escala de cor do plotly, como as de PALETAS.
        opacidades: opacidade de cada ponto; sem ela, a nuvem toda fica com 0.7.
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
        adicionar_historico(figura, historico, total_celulas)

    eixo_limpo = dict(
        showgrid=False, zeroline=False, showticklabels=False, showbackground=False,
        showspikes=False, title="", visible=False,
    )
    figura.update_layout(
        title=dict(text=titulo, font=dict(color="white", size=14), x=0.5),
        paper_bgcolor="black",
        plot_bgcolor="black",
        width=1400 if com_historico else 950, height=800,
        margin=dict(l=110, r=10, t=50, b=10),
        scene=dict(
            xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
            bgcolor="black",
            aspectmode="data",
            camera=dict(eye=olho),
        ),
    )
    return figura


def dados_da_matriz(matrix):
    """
        Converte a matriz binária nas coordenadas das células vivas.
        A matriz é (depth, height, width), então a altura vai para o z do plot:
        x é a largura, y é a profundidade e z é a altura, a mesma troca dos plots
        do Elaphes e do SDF. Sem isso um CA guiado pelo SDF sai girado em relação
        à caverna que o guiou.
        matrix: matriz binária de um resultado do CA.
    """
    vivas = np.argwhere(matrix)
    return vivas[:, 2], vivas[:, 0], vivas[:, 1]

def titulo_do_resultado(dados, celulas_vivas):
    """
        Monta o título da figura com os parâmetros que geraram o resultado.
        dados: dicionário devolvido por load_result.
        celulas_vivas: quantidade de células vivas no volume.
    """
    peso = f" peso {dados['peso_id']:03d}" if "peso_id" in dados else ""
    return (f"CA {dados['size']}^3 - seed {dados['seed_id']:03d} "
            f"s={dados['sensitivity']} b={dados['border_treatment']} "
            f"it={dados['iterations']}{peso} - {celulas_vivas} celulas vivas")

def vizinhos_das_vivas(matrix, border_treatment):
    """
        Contagem de vizinhos vivos de cada célula viva, na mesma ordem de
        dados_da_matriz. É a mesma contagem do passo do CA (cubo 3x3x3 com a
        própria célula), então vai de MIN_VIZINHOS a MAX_VIZINHOS.
        matrix: matriz binária de um resultado do CA.
        border_treatment: a borda que o CA usou, para a contagem na beira bater com a dele.
    """
    vivas = np.asarray(matrix, dtype=bool)
    # A máscara booleana percorre a matriz na mesma ordem do argwhere.
    return neighbor_counts(vivas.astype(np.int16), border_treatment)[vivas]

def opacidade_por_vizinhos(vizinhos):
    """
        Rampa linear: MIN_VIZINHOS fica com OPACIDADE_MINIMA e MAX_VIZINHOS, opaco.
        Os limites são fixos, então a mesma contagem tem a mesma opacidade em
        qualquer resultado.
        vizinhos: contagem de vizinhos de cada célula viva.
    """
    fracao = (np.asarray(vizinhos) - MIN_VIZINHOS) / (MAX_VIZINHOS - MIN_VIZINHOS)
    return OPACIDADE_MINIMA + (1 - OPACIDADE_MINIMA) * fracao

def caminho_da_figura(result_id, modo="altura", paleta="Jet", directory=PASTA_FIGURAS):
    """
        Caminho do HTML da figura, na pasta plots/ do pacote. O modo e a paleta
        entram no nome, então cada combinação tem o seu arquivo.
        result_id: número de identificação do resultado.
        modo: um dos MODOS_COR.
        paleta: uma das PALETAS.
        directory: pasta onde os HTML são gravados.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"result_{result_id:03d}_{modo}_{paleta.lower()}.html"

def figura_ja_existe(result_id, modo="altura", paleta="Jet", directory=PASTA_FIGURAS) -> bool:
    """
        Diz se a figura desse resultado, nesse modo e paleta, já está gravada em plots/.
        result_id: número de identificação do resultado.
        modo: um dos MODOS_COR.
        paleta: uma das PALETAS.
        directory: pasta onde os HTML são gravados.
    """
    return caminho_da_figura(result_id, modo, paleta, directory).exists()

def plotar_resultado(result_id, directory=RESULTS_DIR, mostrar=False, refazer=False,
                     modo="altura", paleta="Jet"):
    """
        Grava o HTML da figura e devolve o caminho do arquivo.
        Se a figura já existir, devolve o caminho sem remontar.
        result_id: número de identificação do resultado.
        directory: pasta onde os resultados são gravados.
        mostrar: abre a figura no navegador além de gravar o HTML.
        refazer: remonta a figura mesmo que o HTML já exista.
        modo: "altura" colore pela altura; "vizinhos" colore pela contagem de
              vizinhos vivos e deixa mais transparente quem tem menos.
        paleta: uma das PALETAS.
    """
    if modo not in MODOS_COR:
        raise ValueError(f"modo precisa ser um de {MODOS_COR}, recebeu {modo!r}.")

    destino = caminho_da_figura(result_id, modo, paleta)
    if destino.exists() and not refazer and not mostrar:
        return destino

    dados = load_result(result_id, directory)
    x, y, z = dados_da_matriz(dados["matrix"])
    titulo = titulo_do_resultado(dados, x.size)

    # A caixa e o volume inteiro, nao a extensao das celulas vivas: mantem a
    # escala comparavel entre resultados e sobrevive a um volume sem nenhuma viva.
    lado = dados["size"]

    # A celula viva nao tem intensidade: o volume e binario. A cor vem da altura
    # ou dos vizinhos, com limites fixos (o volume inteiro, ou 1 a 27), entao a
    # mesma cor significa o mesmo valor em qualquer resultado.
    if modo == "altura":
        valores, rotulo, limites, opacidades = z, "altura (z)", (0, lado - 1), None
    else:
        valores = vizinhos_das_vivas(dados["matrix"], dados["border_treatment"])
        rotulo, limites = "vizinhos", (MIN_VIZINHOS, MAX_VIZINHOS)
        opacidades = opacidade_por_vizinhos(valores)

    figura = figura_volumetrica(
        x, y, z, valores, titulo,
        minimos=[-0.5, -0.5, -0.5],
        maximos=[lado - 0.5, lado - 0.5, lado - 0.5],
        rotulo_escala=rotulo,
        limites_cor=limites,
        historico=dados["live_cells_history"],
        total_celulas=lado ** 3,
        paleta=paleta,
        opacidades=opacidades,
    )

    figura.write_html(destino, include_plotlyjs="cdn")

    if mostrar:
        figura.show()

    return destino

def main(argumentos=None):
    argumentos = argumentos if argumentos is not None else sys.argv[1:]
    if not argumentos:
        raise SystemExit("informe o numero do resultado, ex: ... plot 1 vizinhos Mint")

    modo = argumentos[1] if len(argumentos) > 1 else "altura"
    paleta = argumentos[2] if len(argumentos) > 2 else "Jet"
    destino = plotar_resultado(int(argumentos[0]), refazer=True, modo=modo, paleta=paleta)
    print("figura salva em:", destino)

if __name__ == "__main__":
    main()
