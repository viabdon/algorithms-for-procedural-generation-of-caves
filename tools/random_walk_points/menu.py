"""Menu de terminal do experimento, como o do CA e o do RW.

Gera a rede de veios com pontos sorteados e plota a progressão das etapas.
"enter = X" significa que apertar enter sem digitar nada aceita o valor X.

    uv run python -m tools.random_walk_points.menu
"""
import numpy as np

from cavegen.generators.cellular_automata.menu import explicar, perguntar
from cavegen.generators.random_walk.voxelizacao import BORDA, INTERNO
from cavegen.metrics.connectivity import connected_components
from tools.random_walk_points.generator import (
    DESCIDA,
    K_PADRAO,
    LADO_PADRAO,
    N_PONTOS_PADRAO,
    RAIO_PADRAO,
    SPACER_PADRAO,
    VIES_MINIMO,
    WEIGHT_PADRAO,
)
from tools.random_walk_points.plot import MODOS, plotar_resultado
from tools.random_walk_points.results import (
    load_result,
    load_result_info,
    run_and_save,
    used_result_ids,
)

SEED_PADRAO = 1
LADO_MINIMO = 16
FAIXA_N_PONTOS = (2, 200)
FAIXA_RAIO = (0.87, 4.0)
FAIXA_WEIGHT = (0.1, 1.0)
FAIXA_K = (1.0, 30.0)
FAIXA_SPACER = (0.5, 5.0)

EXPLICACAO_MODOS = {
    "progressao": "as 4 etapas na mesma figura, com um controle deslizante",
    "classificacao": "grade escavada: borda translucida, interno opaco",
}

def perguntar_vies() -> tuple[float, float]:
    """
        Pergunta weight e k até o produto dar uma caminhada que chega ao destino.
    """
    while True:
        weight = perguntar("weight", WEIGHT_PADRAO, float, *FAIXA_WEIGHT)
        k = perguntar("k", K_PADRAO, float, *FAIXA_K)
        if weight * k >= VIES_MINIMO:
            return weight, k

        print(f"    weight * k deu {weight * k:g}, o minimo e {VIES_MINIMO:g}.")

def gerar():
    """
        Pergunta os parâmetros, gera a rede e grava o resultado.
    """
    print("\n--- Gerar uma rede de veios ---")

    explicar(
        "Seed",
        ("Semente de tudo: posicao dos pontos, divisao em source e target e caminhadas.",
        "A mesma seed com os mesmos parametros da sempre a mesma rede."),
        faixa="0 ou mais", tipico="1",
    )
    seed = perguntar("seed", SEED_PADRAO, int, minimo=0)

    explicar(
        "Quantidade de pontos",
        ("Pontos sorteados na etapa 1; metade vira source e metade vira target.",
        "MAIS pontos dao mais veios soltos; o veio central cresce pouco."),
        faixa=f"{FAIXA_N_PONTOS[0]} a {FAIXA_N_PONTOS[1]}", tipico="16 a 32",
    )
    n_pontos = perguntar("pontos", N_PONTOS_PADRAO, int, *FAIXA_N_PONTOS)

    explicar(
        "Tamanho do lado",
        ("Lado do cubo, em voxels. Os pontos sao sorteados dentro dele e a rede pronta",
        "e encaixada de volta no cubo, com a mesma escala nos tres eixos."),
        faixa=f"{LADO_MINIMO} a 256", tipico=f"{LADO_PADRAO}",
    )
    lado = perguntar("tamanho", LADO_PADRAO, int, minimo=LADO_MINIMO)

    explicar(
        "Raio do tubo",
        ("Raio, em voxels, do tubo escavado em volta de cada caminhada.",
        "Com menos de 0.87 o caminho pode se partir na grade."),
        faixa=f"{FAIXA_RAIO[0]} a {FAIXA_RAIO[1]:g}", tipico="1.5",
    )
    raio = perguntar("raio", RAIO_PADRAO, float, *FAIXA_RAIO)

    explicar(
        "weight e k",
        ("A chance de cada movimento e proporcional a exp(cos(angulo ate o destino) * weight * k).",
        "Produto MAIOR vai mais reto ao destino; MENOR deixa o caminho mais errante.",
        f"Abaixo de {VIES_MINIMO:g} a caminhada demora demais para chegar."),
        faixa=f"weight {FAIXA_WEIGHT[0]} a {FAIXA_WEIGHT[1]:g}, "
              f"k {FAIXA_K[0]:g} a {FAIXA_K[1]:g}",
        tipico="produto de 3 a 12",
    )
    weight, k = perguntar_vies()

    explicar(
        "spacer",
        ("Tamanho do passo, em voxels: cada movimento anda 0.5 a 1 spacer por eixo.",
        "MENOR da caminhos com mais pontos e mais curvas."),
        faixa=f"{FAIXA_SPACER[0]} a {FAIXA_SPACER[1]:g}", tipico="1 a 2",
    )
    spacer = perguntar("spacer", SPACER_PADRAO, float, *FAIXA_SPACER)

    print("\n  gerando...")
    destino = run_and_save(seed, n_pontos, lado, raio, weight, k, spacer)
    resumir_resultado(int(destino.stem[-3:]))

def resumir_resultado(result_id: int):
    """
        Mostra o que cada etapa produziu e o tamanho da caverna escavada.
        result_id: número do resultado gravado por run_and_save.
    """
    dados = load_result(result_id)
    rede = dados["rede"]
    total = dados["size"] ** 3
    vazios = int(dados["matrix"].sum())
    borda = int((dados["classificacao"] == BORDA).sum())
    interno = int((dados["classificacao"] == INTERNO).sum())
    _, pedacos = connected_components(dados["matrix"], connectivity=6)
    alturas = rede.pontos[rede.central_nos, 1]
    descidas = sum(c.etapa == DESCIDA for c in rede.caminhos)

    print(f"\n  resultado gravado: result_{result_id:03d}.npz")
    print(f"  pontos: {len(rede.pontos)} ({len(rede.sources)} sources, "
          f"{len(rede.targets)} targets, {len(rede.excluidos)} targets excluidos)")
    print(f"  conectados: {len(rede.nos)} nos em {len(set(rede.veio_de.values()))} veios")
    print(f"  veio central: {len(rede.central_nos)} nos, {descidas} descidas novas, "
          f"y de {alturas[0]:.1f} a {alturas[-1]:.1f}")
    print(f"  ligacoes: {len(rede.soltos)} veios soltos ligados ao veio central")
    print(f"  vazios: {vazios}/{total} ({100 * vazios / total:.2f}%), "
          f"{borda} borda e {interno} interno")
    print(f"  pedacos na grade (vizinhanca de 6): {pedacos}")

    if pedacos > 1:
        print("  a grade saiu partida mesmo com a rede conectada: tente um raio maior.")

def escolher_resultado():
    """
        Lista os resultados gravados com seus parâmetros e devolve o escolhido, ou None.
    """
    disponiveis = used_result_ids()
    if not disponiveis:
        return None

    print("\n  Resultados gravados:")
    for numero in sorted(disponiveis):
        info = load_result_info(numero)
        print(f"    {numero:03d}  seed {info['seed']:<4d} {info['n_pontos']:3d} pontos  "
              f"{info['size']}^3  r={info['raio']:g}  w={info['weight']:g} k={info['k']:g} "
              f"sp={info['spacer']:g}")

    while True:
        escolha = perguntar("resultado", max(disponiveis), int)
        if escolha in disponiveis:
            return escolha

        print("    numero fora da lista acima.")

def escolher_modo() -> str:
    """
        Explica cada figura e devolve a escolhida.
    """
    explicar("Figura", ("Define o que a figura mostra.",))
    for numero, modo in enumerate(MODOS, start=1):
        print(f"    {numero}) {modo:13s} - {EXPLICACAO_MODOS[modo]}")

    escolha = perguntar("figura", 1, int, minimo=1, maximo=len(MODOS))
    return MODOS[escolha - 1]

def plotar():
    """
        Monta a figura de um resultado gravado e imprime o link do HTML.
    """
    print("\n--- Plotar um resultado ---")

    result_id = escolher_resultado()
    if result_id is None:
        print("  Nenhum resultado gravado ainda. Use a opcao 1 primeiro.")
        return

    modo = escolher_modo()
    print("\n  montando a figura...")
    destino = plotar_resultado(result_id, modo)
    print("  copie este caminho no navegador:")
    print(f"    {destino}")

OPCOES = {
    "1": ("Gerar uma rede de veios", gerar),
    "2": ("Plotar um resultado", plotar),
}

def mostrar_menu():
    """
        Imprime as opções disponíveis e o que já existe gravado.
    """
    print("\n=== Random Walk com pontos sorteados (tools/random_walk_points) ===")
    print(f"  {len(used_result_ids())} resultado(s) gravados")
    for numero, (rotulo, _) in OPCOES.items():
        print(f"  {numero}) {rotulo}")
    print("  0) Sair")

def main():
    """
        Repete o menu até o usuário escolher sair.
    """
    while True:
        mostrar_menu()

        try:
            escolha = input("opcao: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if escolha == "0":
            return

        if escolha not in OPCOES:
            print("  opcao invalida, digite 0, 1 ou 2.")
            continue

        try:
            OPCOES[escolha][1]()
        except (EOFError, KeyboardInterrupt):
            print("\n  cancelado, voltando ao menu.")

if __name__ == "__main__":
    main()
