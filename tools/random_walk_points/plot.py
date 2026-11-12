"""
    Figuras do experimento, no estilo dos plots do CA e do RW.

    progressao: uma figura só, com um controle deslizante que passa pelas etapas.
        A câmera fica onde você deixou, então dá para girar e ir avançando.
        1. pontos: os sorteados, divididos em source e target.
        2. conectados: as caminhadas iniciais, com os targets excluídos marcados.
        3. veio central: a linha do topo até o fundo, com o resto apagado.
        4. tudo conectado: os veios soltos ligados ao veio central.
    classificacao: a grade escavada, borda translúcida e interno opaco.

    Eixos como nos outros plots: x é o x, y é o z e z é o y (a altura), para o
    que está em cima no algoritmo aparecer em cima na figura.

    uv run python -m tools.random_walk_points.plot <resultado> [progressao|classificacao]
"""
import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    gizmo_eixos,
)
from cavegen.generators.random_walk.plot import figura_classificacao
from cavegen.generators.random_walk.voxelizacao import BORDA, INTERNO
from tools.random_walk_points.generator import INICIAL, LIGACAO, Rede
from tools.random_walk_points.results import RESULTS_DIR, load_result

PASTA_FIGURAS = Path(__file__).resolve().parent / "plots"
MODOS = ("progressao", "classificacao")

ETAPAS = ("1 pontos", "2 conectados", "3 veio central", "4 tudo conectado")

# Cada papel tem uma cor e também uma segunda marca (símbolo, espessura ou
# traço), para não depender só da cor. Valores conferidos com o validador de
# paleta contra o fundo preto dos plots.
COR_SOURCE = "#3987e5"
COR_TARGET = "#d95926"
COR_INICIAL = "#199e70"
COR_CENTRAL = "#c98500"
COR_LIGACAO = "#d55181"
COR_APAGADO = "#55554f"
COR_TEXTO = "white"

def linhas_de(caminhos: list) -> np.ndarray:
    """
        Junta caminhos num array com NaN entre eles, para caberem num trace só.
        caminhos: lista de Caminho.
    """
    if not caminhos:
        return np.empty((0, 3))
    return np.vstack([np.vstack([c.pontos, [np.nan] * 3]) for c in caminhos])

def trace_linha(caminhos: list, nome: str, cor: str, largura: float, tracejado: bool = False):
    """
        Caminhos como uma linha 3D.
        caminhos: lista de Caminho.
        nome: texto da legenda.
        cor, largura: aparência da linha.
        tracejado: desenha em traços, para as ligações.
    """
    linhas = linhas_de(caminhos)
    return go.Scatter3d(
        x=linhas[:, 0], y=linhas[:, 2], z=linhas[:, 1],
        mode="lines", name=nome, hoverinfo="skip",
        line=dict(color=cor, width=largura, dash="dash" if tracejado else "solid"),
    )

def trace_nos(rede: Rede, indices, nome: str, cor: str, simbolo: str, tamanho: float = 6):
    """
        Pontos como marcadores, com o papel e a altura no hover.
        rede: saída de gerar_rede.
        indices: quais pontos entram.
        nome: texto da legenda.
        cor, simbolo, tamanho: aparência do marcador.
    """
    indices = np.asarray(indices, dtype=int)
    posicoes = rede.pontos[indices]
    textos = [f"{nome} {i}<br>y = {y:.1f}" for i, y in zip(indices, posicoes[:, 1])]
    return go.Scatter3d(
        x=posicoes[:, 0], y=posicoes[:, 2], z=posicoes[:, 1],
        mode="markers", name=nome, text=textos,
        hovertemplate="%{text}<extra></extra>",
        marker=dict(size=tamanho, color=cor, symbol=simbolo),
    )

def trace_ordem_central(rede: Rede):
    """
        Numera os nós do veio central de cima para baixo, para seguir a descida.
        rede: saída de gerar_rede.
    """
    posicoes = rede.pontos[rede.central_nos]
    textos = [f"central {ordem}: nó {no}<br>y = {y:.1f}"
              for ordem, (no, y) in enumerate(zip(rede.central_nos, posicoes[:, 1]), start=1)]
    return go.Scatter3d(
        x=posicoes[:, 0], y=posicoes[:, 2], z=posicoes[:, 1],
        mode="text", name="ordem no veio central", showlegend=False,
        text=[str(i) for i in range(1, len(posicoes) + 1)],
        textposition="top center", textfont=dict(color=COR_TEXTO, size=13),
        hovertext=textos, hoverinfo="text",
    )

def titulos_das_etapas(rede: Rede) -> list:
    """
        Título de cada etapa, com as contagens dela.
        rede: saída de gerar_rede.
    """
    ligacoes = sum(c.etapa == LIGACAO for c in rede.caminhos)
    return [
        f"Etapa 1: {len(rede.pontos)} pontos, {len(rede.sources)} sources e "
        f"{len(rede.targets)} targets",
        f"Etapa 2: {len(rede.nos)} nós em {len(set(rede.veio_de.values()))} veios, "
        f"{len(rede.excluidos)} targets excluídos",
        f"Etapa 3: veio central com {len(rede.central_nos)} nós, "
        f"{len(rede.soltos)} veios soltos",
        f"Etapa 4: {ligacoes} ligações, tudo conectado ao veio central",
    ]

def figura_progressao(rede: Rede, cabecalho: str) -> go.Figure:
    """
        Uma figura com um controle deslizante pelas quatro etapas.
        rede: saída de gerar_rede.
        cabecalho: texto antes do título de cada etapa.
    """
    usados = [t for t in rede.targets if t not in set(rede.excluidos.tolist())]
    centrais = set(rede.central_caminhos)
    iniciais = [c for c in rede.caminhos if c.etapa == INICIAL]
    resto = [c for i, c in enumerate(rede.caminhos) if c.etapa == INICIAL and i not in centrais]
    central = [rede.caminhos[i] for i in rede.central_caminhos]
    ligacoes = [c for c in rede.caminhos if c.etapa == LIGACAO]

    # Cada trace com as etapas em que aparece.
    traces = [
        (trace_linha(iniciais, "caminhos iniciais", COR_INICIAL, 3), {1}),
        (trace_linha(resto, "outros veios (apagados)", COR_APAGADO, 2), {2}),
        (trace_linha(resto, "caminhos iniciais", COR_INICIAL, 3), {3}),
        (trace_linha(ligacoes, "ligações", COR_LIGACAO, 4, tracejado=True), {3}),
        (trace_linha(central, "veio central", COR_CENTRAL, 8), {2, 3}),
        (trace_nos(rede, rede.sources, "source", COR_SOURCE, "circle"), {0, 1, 2, 3}),
        (trace_nos(rede, usados, "target", COR_TARGET, "diamond"), {0, 1, 2, 3}),
        (trace_nos(rede, rede.excluidos, "target", COR_TARGET, "diamond"), {0}),
        (trace_nos(rede, rede.excluidos, "target excluído", COR_APAGADO, "x", 4), {1}),
        (trace_ordem_central(rede), {2, 3}),
    ]
    # Na etapa 1 os dois traces de target aparecem juntos: a legenda mostra um só.
    traces[7][0].showlegend = False

    todos = np.vstack([rede.pontos] + [c.pontos for c in rede.caminhos])
    minimos = todos.min(axis=0)[[0, 2, 1]]
    maximos = todos.max(axis=0)[[0, 2, 1]]
    olho = camera_isometrica()
    fixos = caixa_wireframe(minimos, maximos, olho) + gizmo_eixos(minimos, maximos)

    fig = go.Figure()
    for trace, etapas in traces:
        trace.visible = 0 in etapas
        fig.add_trace(trace)
    for trace in fixos:
        fig.add_trace(trace)

    titulos = [f"{cabecalho}<br>{titulo}" for titulo in titulos_das_etapas(rede)]
    passos = []
    for etapa, rotulo in enumerate(ETAPAS):
        visiveis = [etapa in etapas for _, etapas in traces] + [True] * len(fixos)
        passos.append(dict(
            label=rotulo, method="update",
            args=[{"visible": visiveis}, {"title.text": titulos[etapa]}],
        ))

    eixo_limpo = dict(
        showgrid=False, zeroline=False, showticklabels=False, showbackground=False,
        showspikes=False, title="", visible=False,
    )
    fig.update_layout(
        title=dict(text=titulos[0], font=dict(color=COR_TEXTO, size=14), x=0.5),
        paper_bgcolor="black",
        plot_bgcolor="black",
        width=1050, height=880,
        margin=dict(l=10, r=10, t=70, b=10),
        legend=dict(font=dict(color=COR_TEXTO, size=12), bgcolor="rgba(0,0,0,0)",
                    x=0.01, y=0.97, itemsizing="constant"),
        # uirevision fixo: mudar de etapa não mexe na câmera que você girou.
        uirevision="etapas",
        scene=dict(
            xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
            bgcolor="black",
            aspectmode="data",
            camera=dict(eye=olho),
            uirevision="etapas",
        ),
        sliders=[dict(
            active=0, steps=passos, pad=dict(t=10, b=10), len=0.9, x=0.05,
            font=dict(color=COR_TEXTO, size=12),
            currentvalue=dict(visible=False),
            bgcolor="#2a2a27", activebgcolor=COR_CENTRAL, bordercolor="#55554f",
            tickcolor="#55554f",
        )],
    )
    return fig

def caminho_da_figura(result_id: int, modo: str, directory: Path = PASTA_FIGURAS) -> Path:
    """
        Arquivo HTML da figura de um resultado.
        result_id: número de identificação do resultado.
        modo: um dos MODOS.
        directory: pasta onde os HTML são gravados.
    """
    return Path(directory) / f"result_{result_id:03d}_{modo}.html"

def plotar_resultado(result_id: int, modo: str = "progressao", directory: Path = RESULTS_DIR,
                     figuras: Path = PASTA_FIGURAS) -> Path:
    """
        Grava o HTML da figura e devolve o caminho do arquivo.
        result_id: número de identificação do resultado.
        modo: um dos MODOS.
        directory: pasta onde os resultados são gravados.
        figuras: pasta onde os HTML são gravados.
    """
    if modo not in MODOS:
        raise ValueError(f"modo precisa ser um de {MODOS}, recebeu {modo!r}.")

    dados = load_result(result_id, directory)
    cabecalho = f"Resultado {result_id:03d} (seed {dados['seed']}, {dados['size']}^3)"
    if modo == "progressao":
        figura = figura_progressao(dados["rede"], cabecalho)
    else:
        classificacao = dados["classificacao"]
        titulo = (f"{cabecalho} - raio {dados['raio']:g} voxels: "
                  f"{int((classificacao == BORDA).sum())} borda, "
                  f"{int((classificacao == INTERNO).sum())} interno")
        figura = figura_classificacao(classificacao, titulo)

    destino = caminho_da_figura(result_id, modo, figuras)
    destino.parent.mkdir(parents=True, exist_ok=True)
    figura.write_html(destino, include_plotlyjs="cdn")
    return destino

def main():
    if len(sys.argv) < 2:
        raise SystemExit("informe o resultado, ex: "
                         "python -m tools.random_walk_points.plot 1 progressao")

    modo = sys.argv[2] if len(sys.argv) > 2 else "progressao"
    print("figura salva em:", plotar_resultado(int(sys.argv[1]), modo))

if __name__ == "__main__":
    main()
