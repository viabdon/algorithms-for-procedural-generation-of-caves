"""Figuras de uma execução do GA, em Plotly, e o relatório HTML que junta todas.

Cada função recebe a execução lida por resultados.ler_execucao (um dict) e
devolve uma go.Figure; nada aqui depende de interface. O relatório
(gravar_relatorio) é só uma página que põe as figuras e a tabela dos melhores
uma embaixo da outra. Uma aba do Streamlit pode chamar figuras_da_execucao e
mostrar as mesmas figuras.

O estilo é o dos outros plots do projeto: fundo preto, texto branco, cores que
aparecem no preto e, entre as linhas, símbolo e traço diferentes, para a
leitura não depender só da cor. O plotly vem da internet (CDN), como nos
outros HTML do projeto.

    uv run python -m cavegen.generators.cellular_automata.genetico.resultados ga_012
"""
from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.colors import get_colorscale, sample_colorscale
from plotly.subplots import make_subplots

from cavegen.generators.cellular_automata.genetico.painel import descrever_vazio
from cavegen.generators.cellular_automata.genetico.resultados import (
    avisos_de_comparacao,
    escala_das_notas,
    formatar,
    linhas_do_cabecalho,
    nomes_das_cavernas,
    tabela_dos_melhores,
)
from cavegen.tools.plot_volumes import (
    CONTRASTE_MINIMO_LINHA,
    contraste_no_preto,
)

FUNDO, TEXTO, GRADE, LINHA = "black", "white", "#333333", "#666666"
EIXO = dict(color=TEXTO, gridcolor=GRADE, zeroline=False, showline=True, linecolor=LINHA,
            tickfont=dict(size=11))
PALETA_SERIES = "Jet"
# As notas vão de 1 (o máximo) a milhares negativos (a grade cheia), e o que
# importa ler fica entre -1 e 1. Num eixo linear, um candidato que enche a grade
# achataria todos os outros numa linha só. Por isso todo eixo e toda cor de nota
# usam a escala log simétrica sinal(n) * log10(1 + |n| / NOTA_LINEAR): perto do
# zero (|n| bem menor que NOTA_LINEAR) ela é quase linear e mantém o sinal; longe
# dele, cada década (-1, -10, -100, -1000) ocupa o mesmo espaço. Nada é cortado
# nem escondido; as marcas dos eixos e o hover mostram a nota de verdade.
NOTA_LINEAR = 0.1
MARCAS_NOTA = (-1000, -100, -10, -1, -0.1, 0, 0.1, 0.5, 1)
# A cor do mapa vai de -10000 a +1, fixa: a mesma cor quer dizer a mesma nota em
# qualquer execução. O zero fica no meio da paleta (divergente), então positivo e
# negativo nunca se confundem, mesmo com o lado negativo bem mais comprido.
PALETA_NOTA = "Tropic"
NOTA_MIN_COR, NOTA_MAX_COR = -10000.0, 1.0
COR_CORTADO = "#ff5252"
SIMBOLOS = ("circle", "square", "diamond", "triangle-up", "triangle-down", "cross", "star")
TRACOS = ("solid", "dash", "dot", "dashdot", "longdash")

def cores(n: int, paleta: str = PALETA_SERIES) -> list[str]:
    """n cores espalhadas pela paleta, só entre as que aparecem no fundo preto."""
    amostras = sample_colorscale(get_colorscale(paleta), np.linspace(0, 1, 101).tolist())
    visiveis = [c for c in amostras if contraste_no_preto(c) >= CONTRASTE_MINIMO_LINHA]
    if n == 1:
        return [visiveis[len(visiveis) // 3]]
    return [visiveis[round(i * (len(visiveis) - 1) / (n - 1))] for i in range(n)]

def estilizar(figura: go.Figure, titulo: str, altura: int = 520) -> go.Figure:
    figura.update_layout(
        title=dict(text=titulo, font=dict(color=TEXTO, size=15), x=0.5),
        paper_bgcolor=FUNDO, plot_bgcolor=FUNDO, font=dict(color=TEXTO), height=altura,
        margin=dict(l=70, r=30, t=70, b=60),
        legend=dict(font=dict(color=TEXTO, size=12), bgcolor="rgba(0,0,0,0)"),
    )
    figura.update_xaxes(EIXO)
    figura.update_yaxes(EIXO)
    return figura

def _finita(valor: float):
    """None no lugar de -inf/NaN: o plotly deixa o buraco em vez de esticar o eixo."""
    return float(valor) if math.isfinite(valor) else None

def comprimir(nota: float | None) -> float | None:
    """A nota na escala log simétrica dos eixos; None para -inf/NaN (o buraco)."""
    if nota is None or not math.isfinite(nota):
        return None
    return math.copysign(math.log10(1 + abs(nota) / NOTA_LINEAR), nota)

def _marca(nota: float) -> str:
    return "0" if nota == 0 else f"{nota:+g}"

def eixo_de_notas(notas) -> dict:
    """
        Marcas e faixa de um eixo de notas comprimidas, do menor valor finito
        até o 1 (o teto da nota), sempre com o zero. Para update_yaxes
        ou update_xaxes.
    """
    finitas = [n for n in notas if n is not None and math.isfinite(n)]
    menor, maior = min(finitas + [0.0]), max(finitas + [1.0])
    baixo, alto = comprimir(menor), comprimir(maior)
    margem = 0.04 * (alto - baixo)
    marcas = [m for m in MARCAS_NOTA if menor <= m <= maior]
    return dict(tickvals=[comprimir(m) for m in marcas], ticktext=[_marca(m) for m in marcas],
                range=[baixo - margem, alto + margem])

def escala_de_cor_das_notas() -> list:
    """A paleta divergente com o meio dela exatamente na nota 0 da cor comprimida."""
    baixo, alto = comprimir(NOTA_MIN_COR), comprimir(NOTA_MAX_COR)
    zero = -baixo / (alto - baixo)
    paleta = get_colorscale(PALETA_NOTA)
    negativos = sample_colorscale(paleta, np.linspace(0, 0.5, 6).tolist())
    positivos = sample_colorscale(paleta, np.linspace(0.5, 1, 6).tolist())
    return ([[zero * k / 5, cor] for k, cor in enumerate(negativos)]
            + [[zero + (1 - zero) * k / 5, cor] for k, cor in enumerate(positivos)][1:])

def _rotulo(item: dict) -> str:
    genes = " ".join(f"{nome[0]}={valor:g}" for nome, valor in item["genes"].items())
    return f"#{item['posicao']} {genes}"

def figura_melhor_acumulado(execucoes: list[dict]) -> go.Figure:
    """
        A melhor nota vista até cada avaliação, uma linha por execução. Mostra
        se a busca ainda está subindo e, com a busca aleatória de controle na
        mesma figura, se o GA chega mais alto com o mesmo orçamento.
    """
    figura = go.Figure()
    todas = []
    for i, (execucao, cor) in enumerate(zip(execucoes, cores(len(execucoes)))):
        notas = [_finita(v) for v in execucao["melhor_acumulado"]]
        todas += notas
        figura.add_trace(go.Scatter(
            x=np.arange(1, len(notas) + 1), y=[comprimir(v) for v in notas], customdata=notas,
            mode="lines", name=f"{execucao['nome']} ({execucao['metodo']})",
            line=dict(color=cor, width=2, dash=TRACOS[i % len(TRACOS)]),
            hovertemplate="avaliação %{x}<br>melhor nota %{customdata:+.3f}<extra></extra>"))
    figura.update_xaxes(title_text="avaliações (candidatos, contando os repetidos)")
    figura.update_yaxes(title_text="melhor nota até ali (média entre as cavernas; log simétrico)",
                        **eixo_de_notas(todas))
    titulo = "Melhor nota ao longo das avaliações"
    if all(v is None for v in todas):
        titulo += " (todos cortados)"
    return estilizar(figura, titulo)

def _unicos(execucao: dict) -> dict[tuple, dict]:
    """Cada combinação de genes uma vez, com a nota e quantas vezes foi pedida."""
    unicos = {}
    for genes, nota, iteracoes in zip(execucao["genes"].tolist(), execucao["notas"].tolist(),
                                      execucao["iteracoes"].tolist()):
        chave = tuple(genes)
        if chave in unicos:
            unicos[chave]["vezes"] += 1
        else:
            unicos[chave] = {"nota": nota, "iteracoes": iteracoes, "vezes": 1}
    return unicos

def _eixo_do_gene(limites: dict, valores: list[float]) -> list[float]:
    """Os pontos possíveis do gene (a grade inteira), ou só os que apareceram."""
    if limites.get("inteiro"):
        return list(range(math.ceil(limites["minimo"]), math.floor(limites["maximo"]) + 1))
    if limites.get("passo"):
        n = round((limites["maximo"] - limites["minimo"]) / limites["passo"])
        return [round(limites["minimo"] + k * limites["passo"], 10) for k in range(n + 1)]
    return sorted(set(valores))

def figura_mapa_dos_genes(execucao: dict) -> go.Figure:
    """
        A nota de cada combinação avaliada, com a chance inicial num eixo e a
        sensibilidade no outro: com dois genes, é quase o espaço de busca
        inteiro. Os cortados (vazio fora da faixa) aparecem como X vermelho; as
        células vazias nunca foram avaliadas.
    """
    nomes = [str(n) for n in execucao["genes_nomes"]]
    limites = {g["nome"]: g for g in execucao["genes_limites"]}
    unicos = _unicos(execucao)
    gx, gy = nomes[0], nomes[1]
    xs = _eixo_do_gene(limites[gx], [k[0] for k in unicos])
    ys = _eixo_do_gene(limites[gy], [k[1] for k in unicos])
    z = np.full((len(ys), len(xs)), np.nan)
    # Por célula: a nota de verdade e quantas vezes foi pedida (o z é a comprimida).
    reais = np.full((len(ys), len(xs), 2), np.nan)
    cortados = {"x": [], "y": [], "texto": []}
    for (x, y), dados in unicos.items():
        i = ys.index(min(ys, key=lambda v: abs(v - y)))
        j = xs.index(min(xs, key=lambda v: abs(v - x)))
        if math.isfinite(dados["nota"]):
            z[i, j] = comprimir(dados["nota"])
            reais[i, j] = dados["nota"], dados["vezes"]
        else:
            cortados["x"].append(x)
            cortados["y"].append(y)
            cortados["texto"].append(f"pedido {dados['vezes']}x")

    marcas = [m for m in MARCAS_NOTA if m >= -1000] + [NOTA_MIN_COR]
    figura = go.Figure(go.Heatmap(
        x=xs, y=ys, z=z, customdata=reais, colorscale=escala_de_cor_das_notas(),
        zmin=comprimir(NOTA_MIN_COR), zmax=comprimir(NOTA_MAX_COR), hoverongaps=False,
        name="avaliado",
        colorbar=dict(title=dict(text="nota (log simétrico)", font=dict(color=TEXTO)),
                      tickfont=dict(color=TEXTO), tickvals=[comprimir(m) for m in marcas],
                      ticktext=[_marca(m) for m in marcas]),
        hovertemplate=(f"{gx}=%{{x}}<br>{gy}=%{{y}}<br>nota %{{customdata[0]:+.3f}}"
                       "<br>pedido %{customdata[1]}x<extra></extra>")))
    figura.add_trace(go.Scatter(
        x=cortados["x"], y=cortados["y"], mode="markers",
        name="cortado (vazio fora da faixa aceita)",
        marker=dict(symbol="x", size=9, color=COR_CORTADO, line=dict(width=1, color=COR_CORTADO)),
        text=cortados["texto"],
        hovertemplate=f"{gx}=%{{x}}<br>{gy}=%{{y}}<br>cortado, %{{text}}<extra></extra>"))
    if execucao["melhores"]:
        primeiro = execucao["melhores"][0]["genes"]
        figura.add_trace(go.Scatter(
            x=[primeiro[gx]], y=[primeiro[gy]], mode="markers", name="campeão",
            marker=dict(symbol="star", size=16, color="white", line=dict(width=1, color="black")),
            hovertemplate="campeão<extra></extra>"))
    figura.update_xaxes(title_text=gx)
    figura.update_yaxes(title_text=gy, dtick=1 if limites[gy].get("inteiro") else None)
    figura.update_layout(legend=dict(orientation="h", y=-0.15))
    return estilizar(figura, f"Nota de cada combinação avaliada ({len(unicos)} únicas; cor em "
                             "log simétrico)", altura=620)

def figura_notas_por_caverna(execucao: dict) -> go.Figure:
    """
        A nota de cada caverna nos melhores, lado a lado, com a média (o
        critério) e o desvio entre as cavernas como barra de erro: separa quem
        é consistente de quem só vai bem numa caverna.
    """
    melhores = execucao["melhores"]
    cavernas = nomes_das_cavernas(execucao)
    rotulos = [_rotulo(item) for item in melhores]
    figura = go.Figure()
    todas = []
    for nome, cor in zip(cavernas, cores(len(cavernas))):
        notas = [_finita(item["ajuste"]["por_caverna"][nome]) for item in melhores]
        todas += notas
        figura.add_trace(go.Bar(
            x=rotulos, y=[comprimir(n) for n in notas], customdata=notas, name=nome,
            marker=dict(color=cor), hovertemplate=f"{nome}: %{{customdata:+.3f}}<extra></extra>"))
    # A barra de erro é média ± desvio em nota de verdade; comprimida, ela fica
    # assimétrica (o lado mais longe do zero encolhe mais).
    medias, acima, abaixo = [], [], []
    for item in melhores:
        media, desvio = item["nota_ajuste"], _finita(item["ajuste"]["desvio"]) or 0.0
        medias.append(comprimir(media))
        if medias[-1] is None:
            acima.append(0)
            abaixo.append(0)
            continue
        acima.append(comprimir(media + desvio) - medias[-1])
        abaixo.append(medias[-1] - comprimir(media - desvio))
        todas += [media + desvio, media - desvio]
    figura.add_trace(go.Scatter(
        x=rotulos, y=medias, mode="markers", name="média (± desvio entre as cavernas)",
        marker=dict(symbol="diamond", size=11, color="white", line=dict(color="black", width=1)),
        error_y=dict(type="data", symmetric=False, array=acima, arrayminus=abaixo,
                     color="white", thickness=1.5),
        customdata=[[_finita(item["nota_ajuste"]), _finita(item["ajuste"]["min"]),
                     _finita(item["ajuste"]["desvio"])] for item in melhores],
        hovertemplate=("média %{customdata[0]:+.3f}<br>mín %{customdata[1]:+.3f}<br>"
                       "desvio %{customdata[2]:.3f}<extra></extra>")))
    figura.update_layout(barmode="group")
    figura.update_xaxes(title_text="os melhores, na ordem do ranking")
    figura.update_yaxes(title_text="nota nas seeds de ajuste (log simétrico)",
                        **eixo_de_notas(todas))
    return estilizar(figura, "Nota de cada caverna nos melhores parâmetros")

def _grupos(execucao: dict) -> tuple[str, list[int]]:
    """A geração de cada avaliação; na busca aleatória, que não tem, o lote."""
    if execucao["metodo"] == "genetico":
        return "geração", execucao["geracao"].tolist()
    lote = execucao["config"]["tamanho_populacao"]
    return "lote de sorteios", [i // lote for i in range(len(execucao["notas"]))]

def figura_notas_por_geracao(execucao: dict) -> go.Figure:
    """
        Como as notas se distribuem em cada geração (caixas, com cada candidato
        como ponto) e quantos foram cortados: mostra a busca se concentrando
        nas boas regiões, ou não.
    """
    titulo_grupo, grupos = _grupos(execucao)
    notas = execucao["notas"].tolist()
    numeros = sorted(set(grupos))
    figura = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28],
                           vertical_spacing=0.06)
    cor_caixa, cor_barra = cores(2)
    finitas = [(g, n) for g, n in zip(grupos, notas) if math.isfinite(n)]
    # A caixa é calculada sobre a nota comprimida. Como a compressão só cresce,
    # a mediana e os quartis caem nos mesmos candidatos (a menos da interpolação
    # entre dois vizinhos). O hover fica só nos pontos, com a nota de verdade.
    figura.add_trace(go.Box(
        x=[g for g, _ in finitas], y=[comprimir(n) for _, n in finitas],
        customdata=[n for _, n in finitas], name="notas dos não cortados",
        boxpoints="all", jitter=0.4, pointpos=0, marker=dict(color=cor_caixa, size=4),
        line=dict(color=cor_caixa), fillcolor="rgba(0,0,0,0)", hoveron="points",
        hovertemplate=f"{titulo_grupo} %{{x}}<br>nota %{{customdata:+.3f}}<extra></extra>"),
        row=1, col=1)
    fracao = [100 * sum(1 for g, n in zip(grupos, notas) if g == numero and not math.isfinite(n))
              / grupos.count(numero) for numero in numeros]
    figura.add_trace(go.Bar(
        x=numeros, y=fracao, name="% cortados", marker=dict(color=cor_barra),
        hovertemplate=f"{titulo_grupo} %{{x}}<br>%{{y:.0f}}% cortados<extra></extra>"),
        row=2, col=1)
    figura.update_yaxes(title_text="nota (log simétrico)", row=1, col=1,
                        **eixo_de_notas([n for _, n in finitas]))
    figura.update_yaxes(title_text="% cortados", range=[0, 100], row=2, col=1)
    figura.update_xaxes(title_text=titulo_grupo, dtick=1, row=2, col=1)
    return estilizar(figura, f"Notas por {titulo_grupo}", altura=620)

def figura_trajetoria(execucao: dict, posicao: int = 1) -> go.Figure:
    """
        Um candidato da lista dos melhores (o campeão, por padrão) ao longo das
        iterações do CA: em cima a nota de cada passo (média das seeds) em cada
        caverna e a média entre elas, com a iteração escolhida marcada; embaixo
        o vazio de cada seed, com a faixa aceita de cada caverna sombreada.
    """
    melhores = execucao["melhores"]
    if melhores:
        item = melhores[posicao - 1]
    else:
        item = {**execucao["campeao"], "posicao": 0}
    detalhes = execucao["detalhes"][item["ordem"]]
    cavernas = execucao["cavernas"]
    com_notas = all("notas_por_passo" in detalhes["cavernas"][c["nome"]] for c in cavernas)
    linha_vazio = 2 if com_notas else 1
    figura = make_subplots(rows=linha_vazio, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    paleta = cores(len(cavernas))
    passos = None
    todas = []
    for k, (caverna, cor) in enumerate(zip(cavernas, paleta)):
        nome = caverna["nome"]
        dados = detalhes["cavernas"][nome]
        vazios = np.array(dados["vazios"])
        passos = np.arange(1, vazios.shape[1] + 1)
        if com_notas:
            notas = [_finita(v) for v in dados["notas_por_passo"]]
            todas += notas
            figura.add_trace(go.Scatter(
                x=passos, y=[comprimir(v) for v in notas], customdata=notas,
                mode="lines+markers", name=f"nota em {nome}",
                line=dict(color=cor, width=2, dash=TRACOS[k % 5]),
                marker=dict(symbol=SIMBOLOS[k % len(SIMBOLOS)], size=6, color=cor),
                hovertemplate=(f"{nome}, iteração %{{x}}<br>nota %{{customdata:+.3f}}"
                               "<extra></extra>")),
                row=1, col=1)
        # Sem limite de cima (o padrão desde 22/11/2026), a faixa vai até a grade cheia.
        minimo, maximo = caverna["faixa_vazio"]
        teto = maximo if maximo is not None else int(np.prod(caverna["forma"]))
        figura.add_trace(go.Scatter(x=passos, y=[minimo] * len(passos), mode="lines",
                                    line=dict(color=cor, width=1, dash="dot"),
                                    showlegend=False, hoverinfo="skip"), row=linha_vazio, col=1)
        figura.add_trace(go.Scatter(x=passos, y=[teto] * len(passos), mode="lines",
                                    line=dict(color=cor, width=1, dash="dot"), fill="tonexty",
                                    fillcolor="rgba(255,255,255,0.08)",
                                    name=f"{descrever_vazio(minimo, maximo)} em {nome}",
                                    hoverinfo="skip"), row=linha_vazio, col=1)
        for s, linha in enumerate(vazios):
            # O eixo é log: o 0 (caverna morta) aparece em 1, e o hover diz o valor real.
            figura.add_trace(go.Scatter(
                x=passos, y=np.maximum(linha, 1), customdata=linha, mode="lines",
                line=dict(color=cor, width=1.2, dash=TRACOS[k % 5]), opacity=0.8,
                name=f"vazio em {nome} (uma linha por seed)", legendgroup=f"vazio {nome}",
                showlegend=s == 0,
                hovertemplate=(f"{nome}, seed {execucao['sementes_ajuste'][s]}, iteração %{{x}}"
                               "<br>vazio %{customdata:,d}<extra></extra>")),
                row=linha_vazio, col=1)
    if com_notas:
        media = np.mean([[v for v in detalhes["cavernas"][c["nome"]]["notas_por_passo"]]
                         for c in cavernas], axis=0)
        if len(cavernas) > 1:
            notas = [_finita(v) for v in media]
            figura.add_trace(go.Scatter(
                x=passos, y=[comprimir(v) for v in notas], customdata=notas, mode="lines",
                name="média entre as cavernas",
                line=dict(color="white", width=3),
                hovertemplate="média, iteração %{x}<br>nota %{customdata:+.3f}<extra></extra>"),
                row=1, col=1)
        figura.update_yaxes(title_text="nota do passo (log simétrico)", row=1, col=1,
                            **eixo_de_notas(todas))
    for linha in range(1, linha_vazio + 1):
        figura.add_vline(x=item["iteracoes"], line=dict(color="white", width=1, dash="dash"),
                         row=linha, col=1)
    figura.update_yaxes(title_text="vazio (voxels, escala log; 0 aparece em 1)", type="log",
                        row=linha_vazio, col=1)
    figura.update_xaxes(title_text="iteração do CA", row=linha_vazio, col=1)
    genes = " ".join(f"{n}={v:g}" for n, v in item["genes"].items())
    titulo = f"#{item['posicao']} {genes} ao longo das iterações (escolhida: {item['iteracoes']})"
    if not com_notas:
        titulo += "<br><sup>esta execução não gravou a nota de cada passo, só o vazio</sup>"
    return estilizar(figura, titulo, altura=720)

def figura_ajuste_x_reservadas(execucao: dict) -> go.Figure:
    """
        Para cada um dos melhores, a nota nas seeds de ajuste contra a nota nas
        seeds reservadas, que a busca nunca viu. Abaixo da diagonal, o parâmetro
        foi melhor nas grades da busca que em grades novas; os cortados numa
        seed reservada aparecem como X na base.
    """
    melhores = execucao["melhores"]
    figura = go.Figure()
    ajustes = [item["nota_ajuste"] for item in melhores]
    reservadas = [item["nota_reservada_media"] for item in melhores]
    # Os dois eixos na mesma escala log simétrica: a diagonal continua sendo
    # "igual nas duas", e a distância até ela se lê em décadas.
    eixo = eixo_de_notas([r for r in reservadas if math.isfinite(r)] + ajustes)
    baixo, alto = eixo["range"]
    base = baixo + 0.02 * (alto - baixo)
    figura.add_trace(go.Scatter(x=[baixo, alto], y=[baixo, alto], mode="lines",
                                name="igual nas duas", line=dict(color=LINHA, dash="dash"),
                                hoverinfo="skip"))
    bons = [(a, r, _rotulo(i)) for a, r, i in zip(ajustes, reservadas, melhores)
            if math.isfinite(r)]
    frageis = [(a, _rotulo(i)) for a, r, i in zip(ajustes, reservadas, melhores)
               if not math.isfinite(r)]
    cor = cores(1)[0]
    figura.add_trace(go.Scatter(
        x=[comprimir(a) for a, _, _ in bons], y=[comprimir(r) for _, r, _ in bons],
        customdata=[[a, r] for a, r, _ in bons], text=[t for _, _, t in bons],
        mode="markers+text", textposition="top center", name="nota nas reservadas",
        marker=dict(color=cor, size=10, line=dict(color="black", width=1)),
        hovertemplate=("%{text}<br>ajuste %{customdata[0]:+.3f}<br>"
                       "reservadas %{customdata[1]:+.3f}<extra></extra>")))
    figura.add_trace(go.Scatter(
        x=[comprimir(a) for a, _ in frageis], y=[base] * len(frageis),
        customdata=[a for a, _ in frageis], text=[t for _, t in frageis],
        mode="markers+text", textposition="top center",
        name="cortado em alguma seed reservada (frágil)",
        marker=dict(symbol="x", color=COR_CORTADO, size=11),
        hovertemplate=("%{text}<br>ajuste %{customdata:+.3f}<br>cortado nas reservadas"
                       "<extra></extra>")))
    figura.update_xaxes(title_text="nota nas seeds de ajuste (média entre as cavernas; log "
                                   "simétrico)", **eixo)
    figura.update_yaxes(title_text="nota nas seeds reservadas (média entre as cavernas; log "
                                   "simétrico)", **eixo)
    figura.update_layout(legend=dict(orientation="h", y=-0.18))
    return estilizar(figura, "Ajuste × seeds reservadas, nos melhores")

def figuras_da_execucao(execucao: dict, outras: list[dict] | None = None) -> list[tuple]:
    """
        As figuras do relatório, na ordem, como (título, o que mostra, figura).
        É o que uma interface (uma aba do Streamlit, por exemplo) chamaria.
    """
    tem_melhores = bool(execucao["melhores"])
    lista = [
        ("Melhor nota ao longo das avaliações", LEGENDAS["acumulado"],
         figura_melhor_acumulado([execucao, *(outras or [])])),
        ("Mapa das notas pelos dois genes", LEGENDAS["mapa"], figura_mapa_dos_genes(execucao)),
    ]
    if tem_melhores:
        lista.append(("Nota de cada caverna nos melhores", LEGENDAS["cavernas"],
                      figura_notas_por_caverna(execucao)))
    lista.append(("Notas por geração", LEGENDAS["geracao"], figura_notas_por_geracao(execucao)))
    lista.append(("O campeão ao longo das iterações do CA", LEGENDAS["trajetoria"],
                  figura_trajetoria(execucao)))
    if tem_melhores:
        lista.append(("Ajuste × seeds reservadas", LEGENDAS["reservadas"],
                      figura_ajuste_x_reservadas(execucao)))
    return lista

ESCALA_DOS_EIXOS = (
    "Nas figuras, todo eixo de nota (e a cor do mapa) está em escala log simétrica: entre -0,1 e "
    "+0,1 ela é quase linear, e daí para fora cada década (-1, -10, -100, -1000) ocupa o mesmo "
    "espaço. Assim um candidato que enche a grade não achata os outros, e nada é cortado. As "
    "marcas dos eixos e o hover mostram a nota de verdade.")

# O que cada figura mostra, em uma ou duas frases, para o relatório.
LEGENDAS = {
    "acumulado": ("Se a curva ainda sobe no fim, o orçamento não bastou. Com --comparar, a busca "
                  "aleatória de controle entra na mesma figura: o GA só ajuda se ficar acima "
                  "dela."),
    "mapa": ("Cada célula é uma combinação avaliada; X vermelho é cortado pela faixa de vazio; "
             "célula vazia nunca foi pedida. A estrela é o campeão. Tons do lado positivo da "
             "paleta são notas acima de 0; a escala de cor é a mesma em toda execução."),
    "cavernas": ("Barras próximas entre si: o parâmetro vai bem em todas as cavernas. Uma barra "
                 "alta e outra baixa: a média esconde uma caverna ruim."),
    "geracao": ("Caixas subindo e estreitando: a população se concentra nas boas regiões. A "
                "barra de baixo é a parte cortada de cada geração."),
    "trajetoria": ("A nota de cada passo e o vazio de cada seed, com a faixa aceita sombreada. "
                   "Uma nota que só é boa num passo de transição (o vazio cai ou enche "
                   "depois) dá campeão frágil: compare a iteração escolhida com o passo 40."),
    "reservadas": ("Perto da diagonal: o parâmetro generaliza para grades novas. Abaixo dela ou "
                   "com X: foi bem só nas grades da busca."),
}

def tabela_html(execucao: dict) -> str:
    colunas, linhas = tabela_dos_melhores(execucao)
    if not linhas:
        return "<p>Nenhum: todos os candidatos foram cortados pela faixa de vazio.</p>"
    cabecalho = "".join(f"<th>{html.escape(c)}</th>" for c in colunas)
    corpo = "".join("<tr>" + "".join(f"<td>{html.escape(formatar(v, c))}</td>"
                                     for v, c in zip(linha, colunas)) + "</tr>"
                    for linha in linhas)
    return f"<table><thead><tr>{cabecalho}</tr></thead><tbody>{corpo}</tbody></table>"

ESTILO_PAGINA = """
body { background: black; color: white; font-family: sans-serif; max-width: 1150px;
       margin: 24px auto; padding: 0 16px; }
h1, h2 { font-weight: normal; } p, li { color: #cccccc; }
table { border-collapse: collapse; margin: 8px 0 24px; }
th, td { border: 1px solid #444444; padding: 4px 10px; text-align: right; }
th { background: #1a1a1a; }
"""

def pagina(execucao: dict, outras: list[dict] | None = None) -> str:
    """O HTML do relatório: o cabeçalho da execução, a tabela e as figuras."""
    cabecalho = "".join(f"<li>{html.escape(linha)}</li>"
                        for linha in linhas_do_cabecalho(execucao))
    explicacao = ("<p>nota média: média entre as cavernas nas seeds de ajuste (o critério da "
                  "ordem); mín e desvio: entre as cavernas; reservadas: média nas seeds "
                  "reservadas; pior seed: a menor nota entre elas.</p>"
                  f"<p>{html.escape(escala_das_notas(execucao))}</p><p>{html.escape(ESCALA_DOS_EIXOS)}</p>")
    partes = [f"<h1>{html.escape(execucao['nome'])}</h1><ul>{cabecalho}</ul>",
              f"<h2>Os {len(execucao['melhores'])} melhores parâmetros</h2>", tabela_html(execucao),
              explicacao]
    avisos = avisos_de_comparacao(execucao, outras or [])
    for i, (titulo, legenda, figura) in enumerate(figuras_da_execucao(execucao, outras)):
        partes.append(f"<h2>{html.escape(titulo)}</h2><p>{html.escape(legenda)}</p>")
        if i == 0:
            partes += [f"<p><strong>Aviso:</strong> {html.escape(a)}</p>" for a in avisos]
        partes.append(figura.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False))
    return ("<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(execucao['nome'])}</title><style>{ESTILO_PAGINA}</style>"
            "</head><body>" + "\n".join(partes) + "</body></html>")

def gravar_relatorio(execucao: dict, outras: list[dict] | None = None,
                     destino: Path | None = None) -> Path:
    destino = Path(destino or execucao["arquivo"].with_name(f"{execucao['nome']}_relatorio.html"))
    destino.write_text(pagina(execucao, outras), encoding="utf-8")
    return destino
