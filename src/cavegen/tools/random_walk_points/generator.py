"""
    Random walk sem waypoints à mão: os pontos são sorteados e se organizam em veios.

    Experimento para brincar com a ideia. O pacote do RW (src/cavegen) não muda:
    daqui só sai a caminhada (caminhar) e a voxelização (voxelizar).

    Etapas, com os números da descrição da ideia:
    1. Sorteia poucos pontos em lugares aleatórios da grade.
    2. Divide em 50% sources e 50% targets.
    3. Cada source caminha até o target mais próximo. Dois ou mais podem chegar
       ao mesmo target (4).
    5. Quem se conectou vira nó. Target sem source é excluído. Cada conjunto de
       nós ligados por caminhadas é um veio, ainda independente dos outros.
    6. O veio central nasce no nó mais alto de todos e desce até o nó mais baixo
       ligado a ele.
    7. Dos nós abaixo, escolhe o de menor nota, que soma o ângulo de desvio da
       vertical e a distância até o nó (ver nota_dos_candidatos). Só pelo ângulo,
       um nó reto embaixo e lá no fundo sempre ganha e o veio desce quase em
       linha reta; com a distância, um nó um pouco mais torto e mais perto pode
       ganhar, e o veio faz mais curvas.
    8. Só concorre, de cada veio, o nó mais alto entre os que estão abaixo do
       ponto atual.
    9. Caminha até o nó escolhido.
    10. Repete 6 a 9 até não existir nó abaixo. O veio central termina no nó
        mais baixo de todos.
    11. De cima para baixo, cada veio ainda solto liga o nó dele mais próximo do
        veio central ao nó do veio central mais próximo.

    A descida dentro de um veio só anda por nós cada vez mais baixos: um nó de
    entrada cujo target está acima dele não sobe até o target, ele para ali e
    procura o próximo nó pelo ângulo. Sem essa regra o caminho voltaria para
    cima, que é o que a etapa 8 quer evitar.

    As contas são por nó, não por voxel: duas caminhadas que se cruzam no espaço
    continuam sendo veios separados até a etapa 11 ligar os dois.

    Eixos como no resto do RW: y é a altura, e a voxelização leva (x, y, z) para
    (depth, height, width) = (z, y, x).
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.generators.random_walk.caminhada import caminhar
from cavegen.generators.random_walk.voxelizacao import MARGEM, voxelizar

N_PONTOS_PADRAO = 24
LADO_PADRAO = 64
RAIO_PADRAO = 1.5
WEIGHT_PADRAO = 1.0
K_PADRAO = 6.0
SPACER_PADRAO = 1.5

# Peso do ângulo na nota da etapa 7; o resto (1 - peso) vai para a distância.
# 1 é a regra antiga, só pelo ângulo; 0 escolhe só o nó mais perto.
PESO_ANGULO_PADRAO = 0.5
# Resultados gravados antes da nota, que escolhiam só pelo ângulo.
PESO_ANGULO_ANTIGO = 1.0

# Abaixo disso a caminhada quase não sente o destino. Medido em 20 caminhadas de
# 35 voxels: com 0.5 levam 2 s no total e com 0.1 passam de 60 s (o corte de laços
# fica lento em caminhos muito longos).
VIES_MINIMO = 0.5

# Etapa que criou cada caminho.
INICIAL = 0  # source até target (etapa 3)
DESCIDA = 1  # descida do veio central até o próximo nó (etapa 9)
LIGACAO = 2  # veio solto até o veio central (etapa 11)

@dataclass
class Caminho:
    """
        Uma caminhada entre dois nós.
        origem, destino: índices em Rede.pontos.
        pontos: posições da caminhada, com origem e destino nas pontas.
        etapa: INICIAL, DESCIDA ou LIGACAO.
    """
    origem: int
    destino: int
    pontos: np.ndarray
    etapa: int

@dataclass
class Rede:
    """
        Tudo o que sai das etapas, guardado separado para plotar a progressão.
        pontos: todos os pontos sorteados (x, y, z), inclusive os excluídos.
        sources, targets: índices da divisão da etapa 2.
        excluidos: targets que nenhuma source alcançou.
        caminhos: todas as caminhadas, na ordem em que foram feitas.
        veio_de: índice do veio de cada nó (só nós), como saiu da etapa 5.
        central_nos: nós do veio central, de cima para baixo.
        central_caminhos: índices em caminhos que formam o veio central, em ordem.
        soltos: veios (listas de nós) que a etapa 11 precisou ligar.
    """
    pontos: np.ndarray
    sources: np.ndarray
    targets: np.ndarray
    excluidos: np.ndarray = None
    caminhos: list = field(default_factory=list)
    veio_de: dict = field(default_factory=dict)
    central_nos: list = field(default_factory=list)
    central_caminhos: list = field(default_factory=list)
    soltos: list = field(default_factory=list)

    @property
    def nos(self) -> list:
        """Sources e targets que se conectaram, em ordem de índice."""
        return sorted(self.veio_de)

def sortear_pontos(n_pontos: int, lado: int, margem: float,
                   rng: np.random.Generator) -> np.ndarray:
    """
        Etapa 1: pontos uniformes dentro da grade, longe das paredes.
        n_pontos: quantidade de pontos.
        lado: lado da grade cúbica.
        margem: folga até a parede, em voxels.
        rng: gerador de numpy_rng.
    """
    return rng.uniform(margem, lado - 1 - margem, size=(n_pontos, 3))

def dividir_pontos(n_pontos: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """
        Etapa 2: metade source, metade target. Com número ímpar, o target leva o extra.
        n_pontos: quantidade de pontos.
        rng: gerador de numpy_rng.
    """
    embaralhados = rng.permutation(n_pontos)
    metade = n_pontos // 2
    return np.sort(embaralhados[:metade]), np.sort(embaralhados[metade:])

def target_mais_proximo(ponto: np.ndarray, pontos: np.ndarray, targets: np.ndarray) -> int:
    """
        Índice do target mais perto de um ponto.
        ponto: posição da source.
        pontos: todos os pontos.
        targets: índices dos targets.
    """
    distancias = np.linalg.norm(pontos[targets] - ponto, axis=1)
    return int(targets[np.argmin(distancias)])

def montar_vizinhos(caminhos: list) -> dict:
    """
        Lista de vizinhos de cada nó, a partir das caminhadas.
        caminhos: caminhadas consideradas.
    """
    vizinhos = {}
    for caminho in caminhos:
        vizinhos.setdefault(caminho.origem, []).append(caminho.destino)
        vizinhos.setdefault(caminho.destino, []).append(caminho.origem)
    return vizinhos

def separar_componentes(vizinhos: dict) -> list:
    """
        Conjuntos de nós ligados entre si (cada veio é um), em ordem de menor índice.
        vizinhos: saída de montar_vizinhos.
    """
    vistos = set()
    componentes = []
    for inicio in sorted(vizinhos):
        if inicio in vistos:
            continue
        fila = deque([inicio])
        vistos.add(inicio)
        componente = []
        while fila:
            no = fila.popleft()
            componente.append(no)
            for vizinho in vizinhos[no]:
                if vizinho not in vistos:
                    vistos.add(vizinho)
                    fila.append(vizinho)
        componentes.append(sorted(componente))
    return componentes

def descer_no_veio(no: int, vizinhos: dict, alturas: np.ndarray) -> list:
    """
        Etapa 6: o caminho de nós que desce de no até o mais baixo que dá para
        alcançar andando só para baixo. Devolve a lista começando em no.
        no: nó de partida.
        vizinhos: vizinhança das caminhadas iniciais.
        alturas: y de cada ponto.
    """
    melhor = [no]
    for vizinho in vizinhos[no]:
        if alturas[vizinho] < alturas[no]:
            descida = [no] + descer_no_veio(vizinho, vizinhos, alturas)
            if alturas[descida[-1]] < alturas[melhor[-1]]:
                melhor = descida
    return melhor

def angulo_de_desvio(de: np.ndarray, para: np.ndarray) -> float:
    """
        Etapa 7: ângulo, em graus, entre a linha de de até para e a vertical.
        É o triângulo retângulo com a queda em y de um lado e a distância no
        plano xz do outro: 0° é reto para baixo, 90° é na horizontal.
        de, para: posições (x, y, z).
    """
    horizontal = float(np.hypot(para[0] - de[0], para[2] - de[2]))
    queda = float(de[1] - para[1])
    return float(np.degrees(np.arctan2(horizontal, queda)))

def candidatos_abaixo(atual: int, pontos: np.ndarray, veio_de: dict, usados: set) -> list:
    """
        Etapa 8: de cada veio, o nó mais alto entre os que estão abaixo do atual
        e fora do veio central.
        atual: nó onde o veio central está.
        pontos: todos os pontos.
        veio_de: veio de cada nó.
        usados: nós que já estão no veio central.
    """
    mais_alto = {}
    for no, veio in veio_de.items():
        if no in usados or pontos[no, 1] >= pontos[atual, 1]:
            continue
        if veio not in mais_alto or pontos[no, 1] > pontos[mais_alto[veio], 1]:
            mais_alto[veio] = no
    return sorted(mais_alto.values())

def nota_dos_candidatos(atual: int, candidatos: list, pontos: np.ndarray,
                        peso_angulo: float) -> np.ndarray:
    """
        Etapa 7: nota de cada candidato; a menor vence.
        nota = peso_angulo * ângulo / 90° + (1 - peso_angulo) * distância / maior distância
        As duas partes vão de 0 a 1: o ângulo pelo máximo possível (90°, na
        horizontal) e a distância euclidiana pela do candidato mais longe, então
        o peso decide sozinho quanto cada uma conta. A maior distância nunca é 0,
        porque todo candidato está abaixo do nó atual.
        atual: nó onde o veio central está.
        candidatos: nós de candidatos_abaixo.
        pontos: todos os pontos.
        peso_angulo: de 0 (só distância) a 1 (só ângulo).
    """
    de = pontos[atual]
    angulos = np.array([angulo_de_desvio(de, pontos[no]) for no in candidatos])
    distancias = np.linalg.norm(pontos[candidatos] - de, axis=1)
    return peso_angulo * angulos / 90.0 + (1 - peso_angulo) * distancias / distancias.max()

def proximo_no(atual: int, pontos: np.ndarray, veio_de: dict, usados: set,
               peso_angulo: float = PESO_ANGULO_PADRAO) -> int | None:
    """
        Etapas 7 e 8: o candidato de menor nota, ou None se não há nó abaixo.
        No empate vence o de menor índice, como no min() da regra antiga.
        atual: nó onde o veio central está.
        pontos: todos os pontos.
        veio_de: veio de cada nó.
        usados: nós que já estão no veio central.
        peso_angulo: peso do ângulo na nota (ver nota_dos_candidatos).
    """
    candidatos = candidatos_abaixo(atual, pontos, veio_de, usados)
    if not candidatos:
        return None
    notas = nota_dos_candidatos(atual, candidatos, pontos, peso_angulo)
    return candidatos[int(np.argmin(notas))]

def indice_do_caminho(caminhos: list, a: int, b: int) -> int:
    """
        Índice da caminhada inicial que liga dois nós, em qualquer sentido.
        caminhos: caminhadas feitas até aqui.
        a, b: os nós.
    """
    for indice, caminho in enumerate(caminhos):
        if {caminho.origem, caminho.destino} == {a, b}:
            return indice
    raise ValueError(f"não existe caminhada entre {a} e {b}")

def construir_veio_central(rede: Rede, caminhar_entre,
                           peso_angulo: float = PESO_ANGULO_PADRAO) -> None:
    """
        Etapas 6 a 10: desce do nó mais alto até o nó mais baixo, preenchendo
        central_nos e central_caminhos.
        rede: rede com as caminhadas iniciais, alterada no lugar.
        caminhar_entre: função (origem, destino) que devolve os pontos da caminhada.
        peso_angulo: peso do ângulo na nota da etapa 7.
    """
    alturas = rede.pontos[:, 1]
    vizinhos = montar_vizinhos(rede.caminhos)
    atual = max(rede.nos, key=lambda no: alturas[no])
    rede.central_nos.append(atual)

    while True:
        descida = descer_no_veio(atual, vizinhos, alturas)
        for a, b in zip(descida, descida[1:]):
            rede.central_caminhos.append(indice_do_caminho(rede.caminhos, a, b))
            rede.central_nos.append(b)
        atual = descida[-1]

        alvo = proximo_no(atual, rede.pontos, rede.veio_de, set(rede.central_nos), peso_angulo)
        if alvo is None:
            return

        rede.caminhos.append(Caminho(atual, alvo, caminhar_entre(atual, alvo), DESCIDA))
        rede.central_caminhos.append(len(rede.caminhos) - 1)
        rede.central_nos.append(alvo)
        atual = alvo

def par_mais_proximo(veio: list, central: list, pontos: np.ndarray) -> tuple[int, int]:
    """
        Etapa 11: o nó do veio solto e o nó do veio central mais perto um do outro.
        veio: nós do veio solto.
        central: nós do veio central.
        pontos: todos os pontos.
    """
    distancias = np.linalg.norm(pontos[veio, None] - pontos[central][None], axis=2)
    i, j = np.unravel_index(np.argmin(distancias), distancias.shape)
    return veio[int(i)], central[int(j)]

def ligar_soltos(rede: Rede, caminhar_entre) -> None:
    """
        Etapa 11: liga ao veio central cada veio que ficou sem caminho até ele,
        do que tem o nó mais alto para o que tem o nó mais baixo.
        rede: rede com o veio central pronto, alterada no lugar.
        caminhar_entre: função (origem, destino) que devolve os pontos da caminhada.
    """
    alturas = rede.pontos[:, 1]
    central = set(rede.central_nos)
    componentes = separar_componentes(montar_vizinhos(rede.caminhos))
    soltos = [c for c in componentes if not central.intersection(c)]
    rede.soltos = sorted(soltos, key=lambda veio: -alturas[veio].max())

    for veio in rede.soltos:
        origem, destino = par_mais_proximo(veio, rede.central_nos, rede.pontos)
        rede.caminhos.append(Caminho(origem, destino, caminhar_entre(origem, destino), LIGACAO))

def gerar_rede(seed: int, n_pontos: int = N_PONTOS_PADRAO, lado: int = LADO_PADRAO,
               raio: float = RAIO_PADRAO, weight: float = WEIGHT_PADRAO, k: float = K_PADRAO,
               spacer: float = SPACER_PADRAO,
               peso_angulo: float = PESO_ANGULO_PADRAO) -> Rede:
    """
        Roda as etapas 1 a 11 e devolve a rede com tudo guardado.
        seed: seed do numpy_rng.
        n_pontos: quantidade de pontos sorteados; precisa de ao menos 2.
        lado: lado da grade cúbica.
        raio: raio do tubo, em voxels (entra na folga até a parede).
        weight, k: viés da caminhada; o produto precisa ser ao menos VIES_MINIMO.
        spacer: tamanho do passo, em voxels.
        peso_angulo: peso do ângulo na nota da etapa 7, de 0 a 1.
    """
    if n_pontos < 2:
        raise ValueError(f"Precisa de ao menos 2 pontos, recebeu {n_pontos}.")
    # Escrito assim, o NaN também cai aqui (toda comparação com NaN é falsa).
    if not 0 <= peso_angulo <= 1:
        raise ValueError(f"peso_angulo precisa estar entre 0 e 1, recebeu {peso_angulo}.")
    if weight * k < VIES_MINIMO:
        raise ValueError(f"weight * k precisa ser ao menos {VIES_MINIMO}, "
                         f"recebeu {weight * k:g}.")

    if lado - 1 <= 2 * (MARGEM + raio):
        raise ValueError(f"Lado {lado} é pequeno demais para raio {raio}: não sobra espaço "
                         "para sortear os pontos longe das paredes.")

    rng = numpy_rng(seed)
    pontos = sortear_pontos(n_pontos, lado, MARGEM + raio, rng)
    sources, targets = dividir_pontos(n_pontos, rng)
    rede = Rede(pontos, sources, targets)

    def caminhar_entre(origem: int, destino: int) -> np.ndarray:
        return caminhar(pontos[origem], pontos[destino], weight, k, spacer, rng)

    for source in sources:
        target = target_mais_proximo(pontos[source], pontos, targets)
        rede.caminhos.append(Caminho(int(source), target, caminhar_entre(source, target), INICIAL))

    vizinhos = montar_vizinhos(rede.caminhos)
    rede.excluidos = np.array([t for t in targets if t not in vizinhos], dtype=int)
    for veio, nos in enumerate(separar_componentes(vizinhos)):
        rede.veio_de.update({no: veio for no in nos})

    construir_veio_central(rede, caminhar_entre, peso_angulo)
    ligar_soltos(rede, caminhar_entre)
    return rede

def juntar_caminhos(caminhos: list) -> tuple[np.ndarray, np.ndarray]:
    """
        Todos os pontos num array só e o índice de início de cada caminho, com o
        total no fim: o formato que voxelizar() espera.
        caminhos: lista de Caminho.
    """
    inicios = np.cumsum([0] + [len(c.pontos) for c in caminhos])
    return np.concatenate([c.pontos for c in caminhos]), inicios

def escavar_rede(rede: Rede, lado: int, raio: float) -> tuple[np.ndarray, dict]:
    """
        Escava todos os caminhos na grade, com a voxelização do pacote do RW.
        Ela encaixa a caverna na grade, então uma caminhada que saiu um pouco da
        caixa continua inteira, sem ser cortada na parede.
        rede: saída de gerar_rede.
        lado: lado da grade cúbica.
        raio: raio do tubo, em voxels.
    """
    pontos, inicios = juntar_caminhos(rede.caminhos)
    return voxelizar(pontos, inicios, raio, lado, raio)
