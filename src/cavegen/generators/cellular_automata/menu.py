"""Menu de terminal do automato celular.

Roda o ciclo inteiro sem editar codigo: gerar uma seed, passar a seed pelo CA e
plotar o resultado. Cada pergunta explica o que o parametro faz e em que faixa
ele costuma ficar; "enter = X" significa que apertar enter sem digitar nada
aceita o valor X.

    uv run python -m cavegen.generators.cellular_automata.menu
"""

from cavegen.generators.cellular_automata.generator import BorderTreatment
from cavegen.generators.cellular_automata.modifiers import (
    ESPESSURA_PADRAO,
    add_center_column,
    celulas_da_coluna,
)
from cavegen.generators.cellular_automata.plot import figura_ja_existe, plotar_resultado
from cavegen.generators.cellular_automata.results import (
    load_result,
    load_result_info,
    run_and_save,
    used_result_ids,
)
from cavegen.generators.cellular_automata.seeds import (
    load_seed_info,
    save_seed_matrix,
    used_seed_ids,
)

TAMANHO_PADRAO = 64
PROBABILIDADE_PADRAO = 0.5
SENSIBILIDADE_PADRAO = 14
ITERACOES_PADRAO = 3

# Vizinhos possiveis no cubo 3x3x3, contando a propria celula.
MAX_VIZINHOS = 27

# Custo medido do CA escrito a mao nesta maquina, por celula por iteracao.
SEGUNDOS_POR_CELULA = 11.5e-6

BORDAS = list(BorderTreatment)
EXPLICACAO_BORDAS = {
    BorderTreatment.ZEROS: "fora da matriz conta como vazio, a caverna fecha nas paredes",
    BorderTreatment.ONES: "fora da matriz conta como cheio, a caverna abre nas paredes",
    BorderTreatment.RANDOM: "fora da matriz sorteia 0 ou 1 a cada consulta, paredes irregulares",
}

def explicar(titulo: str, linhas: tuple, faixa: str = "", tipico: str = ""):
    """
        Imprime o bloco de ajuda de um parâmetro antes da pergunta.
        titulo: nome do parâmetro.
        linhas: frases explicando o que o parâmetro faz.
        faixa: intervalo de valores aceitos, como "0 a 27".
        tipico: valores que costumam dar bom resultado.
    """
    print(f"\n  {titulo}")
    for linha in linhas:
        print(f"    {linha}")

    if faixa:
        rodape = f"    faixa: {faixa}"
        if tipico:
            rodape += f"   |   tipico: {tipico}"
        print(rodape)

def perguntar(rotulo: str, padrao, conversao, minimo=None, maximo=None):
    """
        Lê uma resposta do terminal, repetindo a pergunta enquanto o valor não servir.
        rotulo: nome curto do parâmetro, mostrado na linha da pergunta.
        padrao: valor devolvido quando a resposta vem vazia.
        conversao: função que transforma o texto digitado no tipo esperado.
        minimo, maximo: limites aceitos, ou None quando não há limite.
    """
    while True:
        resposta = input(f"    {rotulo} (enter = {padrao}): ").strip()
        if not resposta:
            return padrao

        try:
            valor = conversao(resposta)
        except ValueError:
            print(f"    resposta invalida: nao da para ler '{resposta}' como numero.")
            continue

        if minimo is not None and valor < minimo:
            print(f"    valor abaixo do minimo permitido ({minimo}).")
            continue

        if maximo is not None and valor > maximo:
            print(f"    valor acima do maximo permitido ({maximo}).")
            continue

        return valor

def formatar_tempo(segundos: float) -> str:
    """
        Escreve uma duração em segundos de um jeito curto.
        segundos: duração estimada.
    """
    if segundos < 60:
        return f"{segundos:.0f}s"

    return f"{int(segundos // 60)}min{int(segundos % 60):02d}s"

def escolher_seed():
    """
        Lista as seeds gravadas com seus parâmetros e devolve a escolhida, ou None.
    """
    disponiveis = used_seed_ids()
    if not disponiveis:
        return None

    print("\n  Seeds gravadas:")
    for numero in sorted(disponiveis):
        info = load_seed_info(numero)
        origem = ""
        if "origem_seed_id" in info:
            origem = f"  <- seed {info['origem_seed_id']:03d} + {info['modificacao']}"
        print(f"    {numero:03d}  {info['size']}^3  p={info['one_probability']}{origem}")

    while True:
        escolha = perguntar("seed", max(disponiveis), int)
        if escolha in disponiveis:
            return escolha

        print("    numero fora da lista acima.")

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
        print(f"    {numero:03d}  {info['size']}^3  seed {info['seed_id']:03d}  "
            f"s={info['sensitivity']}  b={info['border_treatment']}  it={info['iterations']}")

    while True:
        escolha = perguntar("resultado", max(disponiveis), int)
        if escolha in disponiveis:
            return escolha

        print("    numero fora da lista acima.")

def escolher_borda() -> BorderTreatment:
    """
        Explica cada tratamento de borda e devolve o membro de BorderTreatment escolhido.
    """
    explicar(
        "Tratamento de borda",
        ("Define o que o automato enxerga fora dos limites da matriz.",),
    )
    for numero, borda in enumerate(BORDAS, start=1):
        print(f"    {numero}) {borda.value:6s} - {EXPLICACAO_BORDAS[borda]}")

    escolha = perguntar("borda", 1, int, minimo=1, maximo=len(BORDAS))
    return BORDAS[escolha - 1]

def criar_seed():
    """
        Pergunta os parâmetros da matriz inicial e grava uma seed nova.
    """
    print("\n--- Criar seed ---")
    print("  A seed e o ruido aleatorio que serve de ponto de partida para o automato.")

    explicar(
        "Tamanho do lado",
        ("Lado do cubo, em celulas. O volume tem lado^3 celulas,",
        "entao dobrar o lado multiplica o custo por 8."),
        faixa="8 a 128", tipico="64",
    )
    tamanho = perguntar("tamanho", TAMANHO_PADRAO, int, minimo=2)

    explicar(
        "Probabilidade de 1",
        ("Chance de cada celula nascer viva (rocha).",
        "Perto de 0.5 o ruido sai equilibrado; mais baixo nasce mais vazio."),
        faixa="0.0 a 1.0", tipico="0.45 a 0.50",
    )
    probabilidade = perguntar("probabilidade", PROBABILIDADE_PADRAO, float, minimo=0.0, maximo=1.0)

    destino = save_seed_matrix(tamanho, probabilidade)
    print(f"\n  seed gravada: {destino.name}  ({tamanho}^3)")

def rodar_ca():
    """
        Pergunta os parâmetros do autômato, roda sobre uma seed e grava o resultado.
    """
    print("\n--- Rodar o CA sobre uma seed ---")

    seed_id = escolher_seed()
    if seed_id is None:
        print("  Nenhuma seed gravada ainda. Use a opcao 1 primeiro.")
        return

    lado = load_seed_info(seed_id)["size"]

    explicar(
        "Sensibilidade",
        ("Minimo de vizinhos vivos, no cubo 3x3x3 em volta (a propria celula conta),",
        "para a celula virar 1 no passo seguinte.",
        "MENOR deixa mais celulas vivas: abaixo de 10 o volume vira um bloco solido.",
        "MAIOR mata mais celulas: acima de 18 nao sobra quase nada.",
        "Com probabilidade 0.5 a media de vizinhos vivos e ~13.5, entao 14 e o equilibrio."),
        faixa=f"0 a {MAX_VIZINHOS}", tipico="13 a 15",
    )
    sensibilidade = perguntar("sensibilidade", SENSIBILIDADE_PADRAO, int,
                            minimo=0, maximo=MAX_VIZINHOS)

    borda = escolher_borda()

    custo_por_iteracao = lado ** 3 * SEGUNDOS_POR_CELULA
    explicar(
        "Iteracoes",
        ("Quantas vezes o passo do automato se repete.",
        "Cada passo suaviza mais as paredes; o volume costuma estabilizar entre 3 e 5.",
        f"Esta seed e {lado}^3, entao cada iteracao leva ~{formatar_tempo(custo_por_iteracao)}."),
        faixa="1 a 20", tipico="3",
    )
    iteracoes = perguntar("iteracoes", ITERACOES_PADRAO, int, minimo=1)

    estimativa = custo_por_iteracao * iteracoes
    print(f"\n  rodando: {lado}^3 x {iteracoes} iteracoes, estimativa ~{formatar_tempo(estimativa)}")

    def mostrar_passo(passo, total):
        print(f"    passo {passo}/{total} concluido")

    destino = run_and_save(seed_id, sensibilidade, borda, iteracoes, progress=mostrar_passo)
    resumir_resultado(destino)

def resumir_resultado(destino):
    """
        Mostra quantas células sobraram vivas e avisa se o volume saiu degenerado.
        destino: caminho do npz gravado por run_and_save.
    """
    dados = load_result(int(destino.stem[-3:]))
    total = dados["size"] ** 3
    vivas = int(dados["matrix"].sum())

    print(f"\n  resultado gravado: {destino.name}")
    print(f"  celulas vivas: {vivas}/{total} ({100 * vivas / total:.1f}%)")

    if vivas == total:
        print("  volume 100% cheio: a sensibilidade esta baixa demais, tente um valor maior.")
    elif vivas == 0:
        print("  volume 100% vazio: a sensibilidade esta alta demais, tente um valor menor.")

def plotar():
    """
        Monta a figura de um resultado gravado e imprime o link do HTML.
    """
    print("\n--- Plotar um resultado ---")

    result_id = escolher_resultado()
    if result_id is None:
        print("  Nenhum resultado gravado ainda. Use a opcao 2 primeiro.")
        return

    if figura_ja_existe(result_id):
        print("\n  esta figura ja estava plotada, reaproveitando o arquivo.")
    else:
        print("\n  montando a figura...")

    destino = plotar_resultado(result_id)
    print("  copie este caminho no navegador:")
    print(f"    {destino}")

def modificar_seed():
    """
        Crava uma coluna central em uma seed existente e grava o resultado como seed nova.
    """
    print("\n--- Modificar uma seed ---")
    print("  Crava uma coluna de rocha atravessando o volume de cima a baixo,")
    print("  centrada nos outros dois eixos, e grava como uma seed nova.")
    print("  A seed de origem fica intacta, entao da para comparar as duas no CA.")

    seed_id = escolher_seed()
    if seed_id is None:
        print("  Nenhuma seed gravada ainda. Use a opcao 1 primeiro.")
        return

    lado = load_seed_info(seed_id)["size"]

    explicar(
        "Espessura da coluna",
        ("Lado da secao quadrada da coluna, em celulas.",
         f"A coluna atravessa as {lado} celulas do eixo vertical, entao a",
         "espessura so controla a grossura, nao o comprimento."),
        faixa=f"1 a {lado}", tipico="3",
    )
    espessura = perguntar("espessura", ESPESSURA_PADRAO, int, minimo=1, maximo=lado)

    destino = add_center_column(seed_id, espessura)
    ocupadas = celulas_da_coluna(lado, espessura)

    print(f"\n  seed gravada: {destino.name}")
    print(f"  coluna {espessura}x{espessura}x{lado}: {ocupadas} celulas viraram rocha")
    print(f"  ({100 * ocupadas / lado ** 3:.1f}% do volume)")

OPCOES = {
    "1": ("Criar seed", criar_seed),
    "2": ("Rodar o CA sobre uma seed", rodar_ca),
    "3": ("Plotar um resultado", plotar),
    "4": ("Modificar uma seed (coluna central)", modificar_seed),
}

def mostrar_menu():
    """
        Imprime as opções disponíveis e o que já existe gravado.
    """
    print("\n=== Automato Celular ===")
    print(f"  {len(used_seed_ids())} seed(s) e {len(used_result_ids())} resultado(s) gravados")
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
            print("  opcao invalida, digite 0, 1, 2, 3 ou 4.")
            continue

        try:
            OPCOES[escolha][1]()
        except (EOFError, KeyboardInterrupt):
            print("\n  cancelado, voltando ao menu.")

if __name__ == "__main__":
    main()
