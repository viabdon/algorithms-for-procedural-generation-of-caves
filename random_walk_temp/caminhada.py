"""
    Porta para Python a caminhada aleatória ponderada do projeto base.

    Original em C#: Assets/Scripts/WeightedRandomWalk.cs e PathGenerator.cs de
    external/3D-Cave-Generation. Para cada ligação do grafo, a caminhada sai
    do waypoint de origem e anda até chegar a menos de spacer do destino.

    Passo a passo, como no original:
    1. Os movimentos possíveis são todas as combinações de -1, -0.5, 0, 0.5 e 1
       em x, y e z, menos o (0, 0, 0): 124 direções.
    2. Cada movimento ganha afinidade = cosseno do ângulo com a direção do
       destino, e probabilidade proporcional a exp(afinidade * weight * k)
       (um softmax: com weight * k = 30, quase sempre vai em direção ao alvo).
    3. O movimento sorteado é multiplicado por spacer e somado à posição.
    4. Chegando perto, o destino entra como último ponto.
    5. Os laços (o caminho voltando a um ponto já visitado) são cortados.

    Diferenças do original, todas só de reprodutibilidade:
    - O sorteio usa numpy_rng(seed) em vez do UnityEngine.Random sem semente,
      então a mesma seed dá o mesmo caminho.
    - As contas são em float64 (a Unity usa float32). A igualdade entre pontos
      segue o operador == do Vector3 da Unity: distância menor que 1e-5.

    O caminho sai em pontos nos eixos da Unity (x, y, z). Os pontos de todas
    as ligações vão juntos num array só, com o índice de início de cada uma.

    uv run python random_walk_temp/caminhada.py [seed]
"""
import sys
from itertools import pairwise, product
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from cavegen.core.seed import numpy_rng
from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    gizmo_eixos,
)

from cena import Grafo, apelido, ler_cena

PASTA = Path(__file__).resolve().parent
PASTA_NPZ = PASTA / "npz"
PASTA_PLOTS = PASTA / "plots"

SEED_PADRAO = 1

# Operador == do Vector3 da Unity: iguais se a distância for menor que 1e-5.
TOLERANCIA_UNITY = 1e-5

# Trava de segurança: no original o while não tem limite.
MAXIMO_DE_PASSOS = 100_000

def movimentos_com_meio_passo() -> np.ndarray:
    """
        As 124 direções do original: -1, -0.5, 0, 0.5 e 1 em cada eixo, sem o (0, 0, 0).
        A ordem dos laços (x por fora, z por dentro) é a do C#, para o sorteio
        cair no mesmo movimento quando o número sorteado é o mesmo.
    """
    passos = (-1.0, -0.5, 0.0, 0.5, 1.0)
    return np.array([m for m in product(passos, repeat=3) if m != (0.0, 0.0, 0.0)])

def movimento_ponderado(direcao: np.ndarray, weight: float, k: float, spacer: float,
                        movimentos: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
        Sorteia um movimento, com mais chance para os que apontam ao destino.
        direcao: vetor da posição atual até o destino.
        weight, k: parâmetros do CaveGenerator; o produto controla o viés.
        spacer: tamanho do passo.
        movimentos: saída de movimentos_com_meio_passo().
        rng: gerador de numpy_rng.
    """
    unitarios = movimentos / np.linalg.norm(movimentos, axis=1, keepdims=True)
    afinidades = unitarios @ (direcao / np.linalg.norm(direcao))
    probabilidades = np.exp(afinidades * weight * k)
    acumulada = np.cumsum(probabilidades / probabilidades.sum())

    # Primeiro movimento em que a probabilidade acumulada alcança o sorteio.
    escolhido = int(np.searchsorted(acumulada, rng.random(), side="left"))
    if escolhido == len(movimentos):
        # O original devolve zero quando o arredondamento deixa a soma abaixo do sorteio.
        return np.zeros(3)
    return movimentos[escolhido] * spacer

def iguais(a: np.ndarray, b: np.ndarray) -> bool:
    """
        Igualdade de pontos como na Unity.
        a, b: pontos (x, y, z).
    """
    return bool(np.linalg.norm(a - b) < TOLERANCIA_UNITY)

def cortar_lacos(caminho: list[np.ndarray]) -> list[np.ndarray]:
    """
        Uma passada do corte de laços do original, com a mesma indexação.
        Quando o ponto j repete o ponto i, tudo de i até j - 1 sai e o ponto j
        assume o lugar i. O j segue contando depois do corte, como no for do C#.
        caminho: lista de pontos.
    """
    caminho = list(caminho)
    i = 0
    while i < len(caminho):
        atual = caminho[i]
        j = i + 1
        while j < len(caminho):
            if iguais(atual, caminho[j]):
                del caminho[i:j]
            j += 1
        i += 1
    return caminho

def caminhar(inicio: np.ndarray, fim: np.ndarray, weight: float, k: float, spacer: float,
             rng: np.random.Generator) -> np.ndarray:
    """
        Um caminho de inicio até fim, como WeightedRandomWalk.Generate().
        inicio, fim: posições dos waypoints.
        weight, k, spacer: parâmetros do CaveGenerator.
        rng: gerador de numpy_rng.
    """
    movimentos = movimentos_com_meio_passo()
    caminho = [inicio]
    atual = inicio

    while np.linalg.norm(atual - fim) > spacer:
        if len(caminho) > MAXIMO_DE_PASSOS:
            raise RuntimeError(f"a caminhada passou de {MAXIMO_DE_PASSOS} passos sem chegar")
        atual = atual + movimento_ponderado(fim - atual, weight, k, spacer, movimentos, rng)
        caminho.append(atual)

    if not iguais(atual, fim):
        caminho.append(fim)

    # O original repete a mesma passada duas vezes.
    caminho = cortar_lacos(cortar_lacos(caminho))
    return np.array(caminho)

def gerar_caminhos(grafo: Grafo, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """
        Um caminho por ligação, como PathGenerator.Generate().
        Devolve (pontos, inicios): todos os pontos juntos e o índice onde cada
        caminho começa, com o total no fim (o caminho c vai de inicios[c] a
        inicios[c + 1]).
        grafo: saída de ler_cena().
        rng: gerador de numpy_rng.
    """
    p = grafo.parametros
    caminhos = [caminhar(grafo.posicoes[a], grafo.posicoes[b], p["weight"], p["k"],
                         p["spacer"], rng)
                for a, b in grafo.arestas]
    inicios = np.cumsum([0] + [len(c) for c in caminhos])
    return np.concatenate(caminhos), inicios

def caminho_npz(nome: str, seed: int) -> Path:
    """
        Arquivo dos caminhos de uma caverna.
        nome: nome da caverna na cena.
        seed: seed da caminhada.
    """
    return PASTA_NPZ / f"{apelido(nome)}_seed{seed:03d}_caminhos.npz"

def figura(grafo: Grafo, pontos: np.ndarray, inicios: np.ndarray, titulo: str) -> go.Figure:
    """
        Caminhos em linha amarela e waypoints em verde, no estilo dos outros plots.
        Eixos como nos plots da grade: x é o x da Unity (largura), y é o z da
        Unity (profundidade) e z é o y da Unity (altura).
        grafo: saída de ler_cena().
        pontos, inicios: saída de gerar_caminhos().
        titulo: texto do topo da figura.
    """
    # None entre os caminhos quebra a linha, para tudo caber num trace só.
    linhas = [np.vstack([pontos[a:b], [np.nan] * 3]) for a, b in pairwise(inicios)]
    linhas = np.vstack(linhas)
    minimos = np.nanmin(pontos, axis=0)[[0, 2, 1]]
    maximos = np.nanmax(pontos, axis=0)[[0, 2, 1]]
    olho = camera_isometrica()

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=linhas[:, 0], y=linhas[:, 2], z=linhas[:, 1],
        mode="lines", line=dict(color="#ffd54f", width=3),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter3d(
        x=grafo.posicoes[:, 0], y=grafo.posicoes[:, 2], z=grafo.posicoes[:, 1],
        mode="markers", marker=dict(size=3, color="#00e676"),
        text=grafo.nomes, hovertemplate="%{text}<extra></extra>", showlegend=False,
    ))
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
        margin=dict(l=10, r=10, t=50, b=10),
        scene=dict(
            xaxis=eixo_limpo, yaxis=eixo_limpo, zaxis=eixo_limpo,
            bgcolor="black",
            aspectmode="data",
            camera=dict(eye=olho),
        ),
    )
    return fig

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else SEED_PADRAO
    PASTA_NPZ.mkdir(exist_ok=True)
    PASTA_PLOTS.mkdir(exist_ok=True)

    for grafo in ler_cena():
        # Uma rng por caverna: a caminhada de uma não muda se a ordem da cena mudar.
        pontos, inicios = gerar_caminhos(grafo, numpy_rng(seed))

        saida = caminho_npz(grafo.nome, seed)
        np.savez_compressed(
            saida,
            pontos=pontos,
            inicios=inicios,
            waypoints=grafo.posicoes,
            nomes=np.array(grafo.nomes),
            arestas=grafo.arestas,
            seed=seed,
            caverna=grafo.nome,
            **grafo.parametros,
        )

        titulo = (f"{grafo.nome} - random walk ponderado (seed {seed}): "
                  f"{len(inicios) - 1} caminhos, {len(pontos)} pontos")
        plot = PASTA_PLOTS / saida.with_suffix(".html").name
        figura(grafo, pontos, inicios, titulo).write_html(plot, include_plotlyjs="cdn")

        print(f"{grafo.nome}: {len(inicios) - 1} caminhos, {len(pontos)} pontos -> {saida.name}")

if __name__ == "__main__":
    main()
