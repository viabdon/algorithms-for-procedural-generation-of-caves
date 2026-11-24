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
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.generator import neighbor_counts
from cavegen.generators.cellular_automata.pesos import (
    PESOS_DIR,
    load_peso_info,
    load_peso_matrix,
)
from cavegen.generators.cellular_automata.results import RESULTS_DIR, load_result
from cavegen.generators.cellular_automata.storage import storage_dir
from cavegen.tools.sdf import CORTE_NEGATIVO, corte_do_campo, opacidade
# Preserve os imports usados pelos menus e pelos scripts de análise existentes.
from cavegen.tools.plot_volumes import (
    AZIMUTE, CORES_GIZMO, CONTRASTE_MINIMO_LINHA, COR_CAIXA, ELEVACAO,
    FAIXA_VERTICAL_HISTORICO, RAIO, adicionar_historico, caixa_wireframe,
    camera_isometrica, contraste_no_preto, cores_das_linhas, dados_da_matriz,
    figura_volumetrica, gizmo_eixos, trace_da_linha, trace_da_nuvem,
)

# Figuras ficam no pacote, nao no temp do sistema: o caminho e estavel e curto,
# da para abrir pelo explorador de arquivos e colar no navegador.
PASTA_FIGURAS = storage_dir("plots")

MODOS_COR = ("altura", "vizinhos")

# A Jet e a paleta de sempre; as outras vao do claro ao escuro, entao a celula
# com menos vizinhos (ou mais baixa) fica mais clara.
PALETAS = ("Jet", "Mint", "Purp", "Teal", "Sunsetdark", "Emrld", "Burg")

# A celula viva entra na propria contagem, entao ela tem de 1 a 27 vizinhos.
MIN_VIZINHOS, MAX_VIZINHOS = 1, 27

# Opacidade da celula com menos vizinhos; a mais cercada fica opaca (1.0).
OPACIDADE_MINIMA = 0.25

# Peso no estilo do plot do SDF (cavegen/tools/sdf/sdf.py): a paleta Tropic e a opacidade em
# rampa, transparente no corte e opaca no valor mais positivo. Longe da superficie
# nao ha nada para ver, entao o que esta a mais de CORTE_PESO_VOXELS nem entra.
PALETA_PESO = "Tropic"
CORTE_PESO_VOXELS = -CORTE_NEGATIVO
TAMANHO_PONTO_PESO = 4

ETAPA_PESO, ETAPA_RESULTADO = "peso (SDF)", "resultado"


def corte_do_peso(escala_log=None):
    """
        Valor do peso a CORTE_PESO_VOXELS da superfície, do lado de fora. Com o log,
        o corte passa pela mesma conta, então os voxels mostrados são os mesmos do
        SDF sem log.
        escala_log: escala do logaritmo do peso; None se ele não foi comprimido.
    """
    return corte_do_campo(escala_log=escala_log)

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
        trace = trace_da_nuvem(
            x, y, z, np.full(x.size, float(nivel)), TAMANHO_PONTO_PESO, PALETA_PESO,
            (corte, maximo), opacidade(float(nivel), maximo, corte), "peso", com_escala,
        )
        trace.visible = False
        trace.hovertemplate = f"(%{{x}}, %{{y}}, %{{z}})<br>peso: {float(nivel):.2f}<extra></extra>"
        traces.append(trace)
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
