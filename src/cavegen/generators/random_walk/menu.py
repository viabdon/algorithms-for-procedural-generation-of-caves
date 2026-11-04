"""Menu de terminal do random walk.

Roda o ciclo inteiro sem editar codigo: escolher a caverna do projeto base,
gerar com uma seed e plotar o resultado. Cada pergunta explica o que o
parametro faz e em que faixa ele costuma ficar; "enter = X" significa que
apertar enter sem digitar nada aceita o valor X.

    uv run python -m cavegen.generators.random_walk.menu
"""

from cavegen.generators.cellular_automata.menu import explicar, perguntar
from cavegen.generators.random_walk.cena import carregar_caverna, cavernas_disponiveis
from cavegen.generators.random_walk.generator import CAVERNA_PADRAO
from cavegen.generators.random_walk.plot import MODOS, figura_ja_existe, plotar_resultado
from cavegen.generators.random_walk.results import (
    load_result,
    load_result_info,
    run_and_save,
    used_result_ids,
)
from cavegen.generators.random_walk.voxelizacao import (
    BORDA,
    INTERNO,
    LADO_PADRAO,
    MARGEM,
    RAIO_PADRAO,
)
from cavegen.metrics.connectivity import connected_components

SEED_PADRAO = 1

# Faixas do Inspector do CaveGenerator no C# ([Range] de weight, k e spacer).
FAIXA_WEIGHT = (0.1, 1.0)
FAIXA_K = (1, 30)
FAIXA_SPACER = (1, 30)

EXPLICACAO_MODOS = {
    "caminhos": "linhas da caminhada e waypoints, nas unidades da Unity",
    "classificacao": "grade escavada: borda translucida, interno opaco",
}

def escolher_caverna() -> str:
    """
        Lista as cavernas exportadas do projeto base e devolve o apelido da escolhida.
    """
    cavernas = cavernas_disponiveis()
    explicar(
        "Caverna",
        ("Grafo de waypoints posto a mao sobre uma caverna real no projeto base.",
        "A forma geral vem dos waypoints; o random walk da a irregularidade do trajeto.",
        "A Example e uma demonstracao plana, as outras seguem cavernas reais."),
    )
    for numero, caverna in enumerate(cavernas, start=1):
        grafo = carregar_caverna(caverna)
        extensao = grafo.posicoes.max(axis=0) - grafo.posicoes.min(axis=0)
        print(f"    {numero}) {grafo.nome:18s} {len(grafo.nomes):3d} waypoints, "
              f"{len(grafo.arestas):3d} ligacoes, "
              f"{' x '.join(f'{v:.0f}' for v in extensao)} (x, y, z)")

    padrao = cavernas.index(CAVERNA_PADRAO) + 1
    escolha = perguntar("caverna", padrao, int, minimo=1, maximo=len(cavernas))
    return cavernas[escolha - 1]

def ler_raio(texto: str) -> float:
    """
        Converte a resposta do raio: um número em voxels, ou "p" para o proporcional.
        Devolve 0 no proporcional, que o menu troca por None.
        texto: resposta digitada.
    """
    return 0.0 if texto.lower() in ("p", "proporcional") else float(texto)

def perguntar_sim(rotulo: str) -> bool:
    """
        Pergunta de sim ou não, com não como padrão.
        rotulo: pergunta mostrada na linha.
    """
    return input(f"    {rotulo} (s/n, enter = n): ").strip().lower() in ("s", "sim")

def perguntar_parametros_do_projeto_base(caverna: str) -> dict:
    """
        Oferece trocar weight, k e spacer; sem troca, valem os da cena.
        As faixas são as do Inspector no C#, para o random walk continuar sendo
        o do projeto base.
        caverna: apelido da caverna escolhida.
    """
    p = carregar_caverna(caverna).parametros
    explicar(
        "Parametros do projeto base",
        (f"Nesta caverna a cena usa weight {p['weight']:g}, k {p['k']:g} e spacer {p['spacer']:g}.",
        "Trocar sai do que o projeto base gerava; o padrao e manter."),
    )
    if not perguntar_sim("trocar weight, k e spacer?"):
        return {}

    explicar(
        "weight e k",
        ("A chance de cada movimento e proporcional a exp(cos(angulo ate o destino) * weight * k).",
        "Produto MAIOR vai mais reto ao destino; MENOR deixa o caminho mais errante.",
        "Com weight * k perto de 0 a caminhada fica quase aleatoria e demora a chegar."),
        faixa=f"weight {FAIXA_WEIGHT[0]} a {FAIXA_WEIGHT[1]}, k {FAIXA_K[0]} a {FAIXA_K[1]}",
        tipico="weight 1, k 30",
    )
    weight = perguntar("weight", p["weight"], float, *FAIXA_WEIGHT)
    k = perguntar("k", int(p["k"]), int, *FAIXA_K)

    explicar(
        "spacer",
        ("Tamanho do passo, nas unidades da Unity: cada movimento anda 0.5 a 1 spacer por eixo.",
        "MENOR da caminhos com mais pontos e mais curvas; o tubo continua do mesmo raio."),
        faixa=f"{FAIXA_SPACER[0]} a {FAIXA_SPACER[1]}", tipico="5",
    )
    spacer = perguntar("spacer", int(p["spacer"]), int, *FAIXA_SPACER)
    return {"weight": weight, "k": k, "spacer": spacer}

def gerar():
    """
        Pergunta caverna, seed, grade e raio, gera a caverna e grava o resultado.
    """
    print("\n--- Gerar uma caverna ---")

    caverna = escolher_caverna()

    explicar(
        "Seed",
        ("Semente do sorteio dos movimentos. A mesma seed com os mesmos parametros",
        "da sempre a mesma caverna; seeds diferentes mudam so o trajeto entre waypoints."),
        faixa="0 ou mais", tipico="1",
    )
    seed = perguntar("seed", SEED_PADRAO, int, minimo=0)

    explicar(
        "Tamanho do lado",
        ("Lado do cubo, em voxels. A caverna inteira e encaixada no cubo com a mesma",
        f"escala nos tres eixos e {MARGEM} voxels de folga, entao o lado muda a resolucao,",
        "nao o tamanho da caverna."),
        faixa=f"{2 * MARGEM + 2} a 256", tipico=f"{LADO_PADRAO}",
    )
    lado = perguntar("tamanho", LADO_PADRAO, int, minimo=2 * MARGEM + 2)

    explicar(
        "Raio do tubo",
        ("Raio, em voxels, do tubo escavado em volta de cada trecho do caminho.",
        "O radius da cena (7) convertido pela escala fica entre 0.2 e 0.3 voxel no 64^3,",
        "menor que um voxel; por isso o padrao e 1.5, que deixa o tunel com algum miolo.",
        "Digite p para usar o proporcional (com o minimo de 0.87, que nao parte o caminho)."),
        faixa="0.87 a 4", tipico="1.5",
    )
    raio = perguntar("raio", RAIO_PADRAO, ler_raio, minimo=0.0)

    trocas = perguntar_parametros_do_projeto_base(caverna)

    print("\n  gerando...")
    destino = run_and_save(seed, caverna, lado, raio or None, **trocas)
    resumir_resultado(int(destino.stem[-3:]))

def resumir_resultado(result_id: int):
    """
        Mostra o tamanho da caverna gerada e avisa se ela saiu partida.
        result_id: número do resultado gravado por run_and_save.
    """
    dados = load_result(result_id)
    total = dados["size"] ** 3
    vazios = int(dados["matrix"].sum())
    borda = int((dados["classificacao"] == BORDA).sum())
    interno = int((dados["classificacao"] == INTERNO).sum())
    _, pedacos = connected_components(dados["matrix"], connectivity=6)

    print(f"\n  resultado gravado: result_{result_id:03d}.npz")
    print(f"  {dados['caverna']}: {len(dados['inicios']) - 1} caminhos, "
          f"{len(dados['pontos'])} pontos")
    print(f"  vazios: {vazios}/{total} ({100 * vazios / total:.2f}%), "
          f"{borda} borda e {interno} interno, raio {dados['raio_voxels']:.2f} voxels")

    if pedacos > 1:
        print(f"  a caverna saiu em {pedacos} pedacos (vizinhanca de 6): o raio esta pequeno "
              "demais para a grade, tente um raio maior.")
    if interno == 0:
        print("  nenhum voxel interno: o tunel tem 1 voxel de largura, "
              "todo vazio encosta em rocha.")

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
        print(f"    {numero:03d}  {info['caverna']:18s} seed {info['seed']:<4d} "
              f"{info['size']}^3  r={info['raio_voxels']:.2f}  "
              f"w={info['weight']:g} k={info['k']:g} sp={info['spacer']:g}")

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

    if figura_ja_existe(result_id, modo):
        print("\n  esta figura ja estava plotada, reaproveitando o arquivo.")
    else:
        print("\n  montando a figura...")

    destino = plotar_resultado(result_id, modo)
    print("  copie este caminho no navegador:")
    print(f"    {destino}")

OPCOES = {
    "1": ("Gerar uma caverna", gerar),
    "2": ("Plotar um resultado", plotar),
}

def mostrar_menu():
    """
        Imprime as opções disponíveis e o que já existe gravado.
    """
    print("\n=== Random Walk ===")
    print(f"  {len(cavernas_disponiveis())} caverna(s) do projeto base e "
          f"{len(used_result_ids())} resultado(s) gravados")
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
