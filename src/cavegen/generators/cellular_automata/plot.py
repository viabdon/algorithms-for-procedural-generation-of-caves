"""Visualizacao volumetrica 3D no estilo radar/sonar/GPR.

Le um volume ja processado pelo CA (pasta results/) e monta a figura interativa
do plotly: fundo preto, caixa wireframe (arestas de tras pontilhadas) e um
gizmo de eixos no canto.

A cor vem da altura da celula ou da quantidade de vizinhos vivos dela, em uma
das PALETAS. Por vizinhos, a opacidade tambem acompanha a contagem: a celula
com menos vizinhos fica meio transparente e a mais cercada, opaca.

O grafico de linha mostra, na mesma paleta, as celulas vivas e as que viraram 1
e 0 em cada iteracao. Um resultado rodado com peso ganha um controle deslizante
que troca o volume pelo peso (o SDF) que guiou o CA, na mesma camera.

O HTML vai para plots/, ao lado do codigo, e o caminho e impresso para copiar
no navegador. A pasta results/ guarda apenas os npz.

    uv run python -m cavegen.generators.cellular_automata.plot 1 [altura|vizinhos] [paleta]
"""

import sys
from itertools import product
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.colors import get_colorscale, sample_colorscale, unlabel_rgb
from plotly.subplots import make_subplots

from cavegen.generators.cellular_automata.generator import neighbor_counts
from cavegen.generators.cellular_automata.pesos import (
    PESOS_DIR,
    load_peso_info,
    load_peso_matrix,
)
from cavegen.generators.cellular_automata.results import RESULTS_DIR, load_result
from cavegen.generators.cellular_automata.storage import storage_dir
from cavegen.sdf.manipulacao import comprimir_log

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

# Contraste minimo de uma linha contra o fundo preto (WCAG para elementos graficos).
# As pontas escuras das paletas sumiriam no fundo, entao ficam de fora das linhas.
CONTRASTE_MINIMO_LINHA = 3.0

# Peso no estilo do plot do SDF (cavegen/tools/sdf/sdf.py): a paleta Tropic e a opacidade em
# rampa, transparente no corte e opaca no valor mais positivo. Longe da superficie
# nao ha nada para ver, entao o que esta a mais de CORTE_PESO_VOXELS nem entra.
PALETA_PESO = "Tropic"
CORTE_PESO_VOXELS = 10.0
TAMANHO_PONTO_PESO = 4

ETAPA_PESO, ETAPA_RESULTADO = "peso (SDF)", "resultado"


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


def corte_do_peso(escala_log=None):
    """
        Valor do peso a CORTE_PESO_VOXELS da superfície, do lado de fora. Com o log,
        o corte passa pela mesma conta, então os voxels mostrados são os mesmos do
        SDF sem log.
        escala_log: escala do logaritmo do peso; None se ele não foi comprimido.
    """
    # float32 como o peso gravado: em float64 o arredondamento pode ser outro, e o
    # voxel exatamente no corte apareceria com log e sumiria sem log.
    corte = np.array(-CORTE_PESO_VOXELS, dtype=np.float32)
    return float(corte if escala_log is None else comprimir_log(corte, escala_log))

def traces_do_peso(peso, escala_log=None):
    """
        Um Scatter3d por nível do peso, porque o plotly só aceita uma opacidade por
        trace. Numa grade de voxels as distâncias se repetem muito, então são poucas
        dezenas de traces. Do mais negativo ao mais positivo: o interno, opaco, é
        desenhado por último. Todos saem escondidos, e o controle deslizante mostra.
        peso: matriz do peso (depth, height, width).
        escala_log: escala do logaritmo do peso; None se ele não foi comprimido.
    """
    corte = corte_do_peso(escala_log)
    niveis = np.unique(peso[peso > corte])
    if niveis.size == 0:
        return []

    maximo = float(niveis[-1])
    traces = []
    for nivel in niveis:
        x, y, z = dados_da_matriz(peso == nivel)
        com_escala = bool(nivel == niveis[-1])
        traces.append(go.Scatter3d(
            x=x, y=y, z=z,
            mode="markers",
            visible=False,
            marker=dict(
                size=TAMANHO_PONTO_PESO,
                color=np.full(x.size, float(nivel)),
                colorscale=PALETA_PESO,
                cmin=corte,
                cmax=maximo,
                opacity=(float(nivel) - corte) / (maximo - corte),
                showscale=com_escala,
                colorbar=dict(
                    title=dict(text="peso", font=dict(color="white", size=12)),
                    x=-0.06, xanchor="left", len=0.75, thickness=14,
                    bgcolor="black", outlinecolor="white", outlinewidth=1,
                    tickfont=dict(color="white", size=11),
                ) if com_escala else None,
            ),
            hovertemplate=f"(%{{x}}, %{{y}}, %{{z}})<br>peso: {float(nivel):.2f}<extra></extra>",
            showlegend=False,
        ))
    return traces

def titulo_do_peso(peso_id, info, voxels):
    """
        Título da etapa do peso no controle deslizante.
        peso_id: número do peso.
        info: dicionário de load_peso_info.
        voxels: quantos voxels do peso aparecem na figura.
    """
    log = f", log x{info['escala_log']:g}" if info["escala_log"] is not None else ""
    return (f"Peso {peso_id:03d} que guiou este resultado - {info['origem']}{log} - "
            f"{voxels} voxels a ate {CORTE_PESO_VOXELS:g} da superficie")

def adicionar_controle_do_peso(figura, peso, titulo_resultado, titulo_peso, escala_log=None):
    """
        Põe o peso na figura e um controle deslizante embaixo que troca a nuvem do
        resultado por ele. Caixa, gizmo e linhas ficam nas duas etapas. A figura abre
        no resultado, e o peso vem antes no controle porque veio antes no processo.
        figura: saída de figura_volumetrica.
        peso: matriz do peso (depth, height, width).
        titulo_resultado, titulo_peso: título de cada etapa.
        escala_log: escala do logaritmo do peso; None se ele não foi comprimido.
    """
    # A nuvem do resultado é o que já está na figura como marcadores 3D.
    eh_resultado = [t.type == "scatter3d" and t.mode == "markers" for t in figura.data]
    traces = traces_do_peso(peso, escala_log)
    figura.add_traces(traces)

    no_resultado = [True] * len(eh_resultado) + [False] * len(traces)
    no_peso = [not e for e in eh_resultado] + [True] * len(traces)
    passos = [
        dict(label=ETAPA_PESO, method="update",
             args=[{"visible": no_peso}, {"title.text": titulo_peso}]),
        dict(label=ETAPA_RESULTADO, method="update",
             args=[{"visible": no_resultado}, {"title.text": titulo_resultado}]),
    ]
    figura.update_layout(
        height=880,
        margin=dict(b=90),
        # uirevision fixo: trocar de etapa não mexe na câmera que o usuário girou.
        uirevision="etapas",
        scene=dict(uirevision="etapas"),
        sliders=[dict(
            active=1, steps=passos, x=0.03, len=0.5, pad=dict(t=10, b=10),
            font=dict(color="white", size=12),
            currentvalue=dict(visible=False),
            bgcolor="#2a2a27", activebgcolor="#ffffff", bordercolor="#666666",
            tickcolor="#666666",
        )],
    )


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
                     modo="altura", paleta="Jet", pesos_dir=PESOS_DIR, figuras=PASTA_FIGURAS):
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
        pesos_dir: pasta onde os pesos são gravados.
        figuras: pasta onde os HTML são gravados.
    """
    if modo not in MODOS_COR:
        raise ValueError(f"modo precisa ser um de {MODOS_COR}, recebeu {modo!r}.")

    destino = caminho_da_figura(result_id, modo, paleta, figuras)
    if destino.exists() and not refazer and not mostrar:
        return destino

    dados = load_result(result_id, directory)
    x, y, z = dados_da_matriz(dados["matrix"])
    titulo = titulo_do_resultado(dados, x.size)

    # Os pesos não vão para o Git: num clone sem o arquivo, o resultado ainda plota.
    peso, info_peso = None, None
    if "peso_id" in dados:
        try:
            peso = load_peso_matrix(dados["peso_id"], pesos_dir)
            info_peso = load_peso_info(dados["peso_id"], pesos_dir)
        except FileNotFoundError:
            titulo += " (arquivo do peso nao encontrado)"

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
        viraram_1=dados["viraram_1_history"],
        viraram_0=dados["viraram_0_history"],
    )

    if peso is not None:
        escala_log = info_peso["escala_log"]
        voxels = int((peso > corte_do_peso(escala_log)).sum())
        adicionar_controle_do_peso(figura, peso, titulo,
                                   titulo_do_peso(dados["peso_id"], info_peso, voxels), escala_log)

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
