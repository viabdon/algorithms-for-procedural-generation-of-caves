"""
    Calcula o SDF de uma grade de superfície, com o sinal vindo da inundação, e
    o manipula de forma reprodutível (limiar e logaritmo).

    Etapas do SDF base, na ordem:
    1. Lê a grade de superfície e chama o flood fill (tools/flood_fill), que
       classifica 0 vazio, 1 borda e 2 interno pelo que a água alcança.
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

    Manipulação (manipular_sdf, de cavegen.sdf.manipulacao, onde o CA e o GA
    também a usam), sempre nesta ordem, sem recalcular a distância:
    1. Limiar: o zero passa para d = limiar. Com limiar -4, o voxel a 4 voxels
       do lado de fora vira 0 (neutro), a borda vira +4 e o interno sobe junto;
       além dos 4 voxels o campo continua negativo. É só somar uma constante,
       porque a distância até a borda não muda. Do lado de fora, o campo
       deslocado é a distância até a superfície empurrada 4 voxels para fora.
    2. Logaritmo: comprimir_log (escala * sinal * ln(1 + |x|)), aplicado
       ao campo já deslocado, para o zero continuar no limiar.
    O limiar e a escala ficam gravados no npz. Sem os dois, o campo é o SDF base.

    Plot: paleta Tropic do plotly, do verde-azulado (mais negativo) ao rosa
    (mais positivo), esticada do corte até o máximo. A opacidade sobe em linha
    reta do corte (transparente) até o valor mais positivo (opaco). Abaixo do
    corte o voxel nem entra no plot. O corte fica a CORTE_NEGATIVO voxels da
    borda e passa pela mesma manipulação do campo, então os voxels mostrados são
    os mesmos com e sem limiar ou log.

    Sem superfície, usa a grade do Elaphes 64³.

    uv run python -m tools.sdf.sdf [superficie.npz] [--limiar -4] [--log 2]
"""
import argparse
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from scipy.ndimage import distance_transform_edt

from cavegen.generators.cellular_automata.plot import (
    caixa_wireframe,
    camera_isometrica,
    gizmo_eixos,
)
from cavegen.sdf.manipulacao import manipular_sdf
from tools.flood_fill.inundacao import (
    BORDA,
    INTERNO,
    SUPERFICIE_ELAPHES,
    classificar_por_inundacao,
    inundar,
)

PASTA = Path(__file__).resolve().parent
PASTA_NPZ = PASTA / "npz"
PASTA_PLOTS = PASTA / "plots"

# 1: interno positivo e externo negativo. -1 inverte para a convenção do projeto.
SINAL_INTERNO = 1
CONVENCAO = "interno positivo, externo negativo, borda 0; distância em voxels"

# Distância, do lado de fora da borda, em que a opacidade chega a 0: o que está
# além disso não é plotado.
CORTE_NEGATIVO = -10.0

PALETA = "Tropic"

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

def convencao_do_campo(limiar: float = 0.0, escala_log: float | None = None) -> str:
    """
        Texto da convenção gravado no npz, com as manipulações na ordem aplicada.
        limiar, escala_log: os de manipular_sdf.
    """
    partes = [CONVENCAO]
    if limiar != 0:
        partes.append(f"zero deslocado para d = {limiar:g} (campo = d - ({limiar:g}))")
    if escala_log is not None:
        partes.append(f"depois comprimido com {escala_log:g} * sinal(x) * ln(1 + |x|)")
    return "; ".join(partes)

def nome_do_campo(stem: str, limiar: float = 0.0, escala_log: float | None = None) -> str:
    """
        Nome do arquivo, sem extensão: o SDF base é <stem>_sdf e cada manipulação
        entra no nome, como elaphes_surface_64_sdf_limiar-4_log2.
        stem: nome da grade de superfície.
        limiar, escala_log: os de manipular_sdf.
    """
    nome = f"{stem}_sdf"
    if limiar != 0:
        nome += f"_limiar{limiar:g}"
    if escala_log is not None:
        nome += f"_log{escala_log:g}"
    return nome

def sdf_da_superficie(cheio: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
        Etapas 1 a 4: devolve (sdf, borda, interno) de uma grade de superfície.
        cheio: matriz booleana (depth, height, width), True na superfície.
    """
    # O sinal vem do flood fill: o que a água alcança é fora.
    agua, _ = inundar(cheio)
    classificacao = classificar_por_inundacao(cheio, agua)

    borda = binarizar_borda(classificacao)
    interno = classificacao == INTERNO
    return aplicar_sinal(distancia_ate_borda(borda), interno), borda, interno

def gravar_campo(entrada: Path, limiar: float = 0.0, escala_log: float | None = None,
                 pasta: Path = PASTA_NPZ) -> Path:
    """
        Calcula o SDF base da superfície, manipula e grava; devolve o caminho.
        O campo vai no campo "sdf", que é o que o importar_sdf do CA lê.
        entrada: npz com "surface_voxels" e "metadata".
        limiar, escala_log: os de manipular_sdf.
        pasta: onde o npz é gravado.
    """
    entrada = Path(entrada)
    # Valida antes da EDT, para um parâmetro errado não custar o cálculo inteiro.
    manipular_sdf(np.zeros(1, dtype=np.float32), limiar, escala_log)

    with np.load(entrada) as dados:
        cheio = dados["surface_voxels"].astype(bool)
        metadata = dados["metadata"]

    sdf, borda, interno = sdf_da_superficie(cheio)
    extras = {} if escala_log is None else {"escala_log": float(escala_log)}

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{nome_do_campo(entrada.stem, limiar, escala_log)}.npz"
    np.savez_compressed(
        destino,
        sdf=manipular_sdf(sdf, limiar, escala_log),
        borda=borda.astype(np.uint8),
        interno=interno.astype(np.uint8),
        convencao=convencao_do_campo(limiar, escala_log),
        limiar=float(limiar),
        metadata=metadata,
        **extras,
    )
    return destino

def corte_do_campo(limiar: float = 0.0, escala_log: float | None = None) -> float:
    """
        Valor do campo a CORTE_NEGATIVO voxels da borda, do lado de fora. Como as
        manipulações só crescem, o que passa do corte no campo é o que passava
        no SDF base.
        limiar, escala_log: os de manipular_sdf.
    """
    corte = np.array([CORTE_NEGATIVO], dtype=np.float32)
    return float(manipular_sdf(corte, limiar, escala_log)[0])

def opacidade(valor: float, maximo: float, corte: float = CORTE_NEGATIVO) -> float:
    """
        Rampa linear: o corte fica 100% transparente e o valor mais positivo
        fica opaco.
        valor: nível do campo.
        maximo: maior valor do campo.
        corte: valor do campo onde a opacidade é 0.
    """
    return (valor - corte) / (maximo - corte)

def regiao(valor: float, valor_da_borda: float = 0.0) -> str:
    """
        Nome da região de um nível do campo, para o hover.
        valor: nível do campo.
        valor_da_borda: quanto vale a borda no campo (0 no SDF base, |limiar|
            com limiar para fora).
    """
    if valor > valor_da_borda:
        return "interno"
    return "borda" if valor == valor_da_borda else "externo"

def trace_do_nivel(sdf: np.ndarray, valor: float, maximo: float, com_escala: bool,
                   corte: float = CORTE_NEGATIVO,
                   valor_da_borda: float = 0.0) -> go.Scatter3d:
    """
        Um Scatter3d por nível: o plotly só aceita uma opacidade por trace.
        Numa grade de voxels as distâncias são raízes de inteiros, então os
        níveis se repetem muito e viram poucas dezenas de traces.
        Mesma troca de eixos dos outros plots: x é a largura, y é a
        profundidade e z é a altura da grade (depth, height, width).
        sdf: campo com sinal.
        valor: nível plotado nesse trace.
        maximo: maior valor do campo, topo da escala de cor e da opacidade.
        com_escala: desenha a barra de cores (só um dos traces precisa).
        corte: base da escala de cor e da opacidade.
        valor_da_borda: quanto vale a borda no campo, para o hover.
    """
    indices = np.argwhere(sdf == valor)
    x, y, z = indices[:, 2], indices[:, 0], indices[:, 1]
    marcas = list(range(int(np.ceil(corte)), int(np.floor(maximo)) + 1))
    escala = dict(
        title=dict(text="SDF (voxels)", font=dict(color="white", size=12)),
        tickvals=marcas,
        x=-0.06, xanchor="left", len=0.75, thickness=14,
        bgcolor="black", outlinecolor="white", outlinewidth=1,
        tickfont=dict(color="white", size=11),
    )
    nome = regiao(valor, valor_da_borda)

    return go.Scatter3d(
        x=x, y=y, z=z,
        mode="markers",
        marker=dict(
            size=4,
            color=np.full(x.size, valor),
            colorscale=PALETA,
            cmin=corte,
            cmax=maximo,
            opacity=opacidade(valor, maximo, corte),
            showscale=com_escala,
            colorbar=escala if com_escala else None,
        ),
        hovertemplate=f"(%{{x}}, %{{y}}, %{{z}})<br>{nome}: {valor:.2f}<extra></extra>",
        showlegend=False,
    )

def figura(sdf: np.ndarray, titulo: str, corte: float = CORTE_NEGATIVO,
           valor_da_borda: float = 0.0) -> go.Figure:
    """
        Monta a figura com um trace por nível acima do corte, caixa e gizmo,
        no estilo dos plots do CA.
        sdf: campo com sinal.
        titulo: texto do topo da figura.
        corte: o que estiver abaixo não é plotado (corte_do_campo, se manipulado).
        valor_da_borda: quanto vale a borda no campo, para o hover.
    """
    profundidade, altura, largura = sdf.shape
    minimos = [-0.5, -0.5, -0.5]
    maximos = [largura - 0.5, profundidade - 0.5, altura - 0.5]
    olho = camera_isometrica()
    maximo = float(sdf.max())

    fig = go.Figure()
    # Do mais negativo ao mais positivo: o interno, opaco, é desenhado por último.
    niveis = np.unique(sdf[sdf > corte]).tolist()
    for valor in niveis:
        fig.add_trace(trace_do_nivel(sdf, valor, maximo, com_escala=valor == niveis[-1],
                                     corte=corte, valor_da_borda=valor_da_borda))
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
    parser = argparse.ArgumentParser(description="SDF de uma grade de superfície, manipulável.")
    parser.add_argument("superficie", nargs="?", type=Path, default=SUPERFICIE_ELAPHES,
                        help="npz com surface_voxels (padrão: Elaphes 64³)")
    parser.add_argument("--limiar", type=float, default=0.0,
                        help="valor do SDF onde o zero passa a ficar; -4 empurra 4 voxels "
                             "para fora (padrão: 0, sem deslocar)")
    parser.add_argument("--log", dest="escala_log", type=float, default=None,
                        help="escala do logaritmo, aplicado depois do limiar (padrão: sem log)")
    args = parser.parse_args()

    destino = gravar_campo(args.superficie, args.limiar, args.escala_log)
    with np.load(destino) as dados:
        campo, borda, interno = dados["sdf"], dados["borda"], dados["interno"]

    corte = corte_do_campo(args.limiar, args.escala_log)
    valor_da_borda = float(manipular_sdf(np.zeros(1, dtype=np.float32), args.limiar,
                                         args.escala_log)[0])
    plotados = int((campo > corte).sum())
    titulo = (f"{destino.stem} (interno +, externo -): {plotados} voxels a até "
              f"{-CORTE_NEGATIVO:g} da borda")
    saida_plot = PASTA_PLOTS / f"{destino.stem}.html"
    PASTA_PLOTS.mkdir(exist_ok=True)
    figura(campo, titulo, corte, valor_da_borda).write_html(saida_plot, include_plotlyjs="cdn")

    print(f"borda: {int(borda.sum())}, interno: {int(interno.sum())}")
    print(f"campo de {campo.min():.2f} (externo) a {campo.max():.2f} (interno), "
          f"borda em {valor_da_borda:g}")
    print(f"plotados {plotados} voxels a até {-CORTE_NEGATIVO:g} da borda")
    print(f"npz salvo em {destino}")
    print(f"figura salva em {saida_plot}")

if __name__ == "__main__":
    main()
