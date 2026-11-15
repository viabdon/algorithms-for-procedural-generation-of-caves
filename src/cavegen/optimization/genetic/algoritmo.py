"""Motor genérico do algoritmo genético e a busca aleatória de mesmo orçamento.

Nada aqui sabe o que é um CA: o motor recebe a lista de genes (nome e limites)
e uma função que dá a nota de um cromossomo. Assim o mesmo motor serve depois
para o Random Walk, e a busca aleatória, que é o controle do GA, usa a mesma
contagem de orçamento.

Um cromossomo é um dict {nome do gene: valor}. A nota é um float, e maior é
melhor; -inf vale como "candidato descartado".
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from cavegen.core.seed import numpy_rng

# A função de avaliação devolve (nota, detalhes). Os detalhes são gravados junto
# com a nota, mas o motor só olha a nota.
Avaliador = Callable[[dict], tuple[float, dict]]
# Observador opcional da busca, para mostrar o andamento. Recebe o nome do
# evento e um dict:
#   "candidato": {"avaliacao", "restante", "repetido"}, depois de cada candidato;
#   "geracao": {"geracao", "populacao", "resultado"}, quando uma geração do GA
#              fica completa (a 0 é a população inicial).
# Ele só lê: nada que faça muda a busca.
Observador = Callable[[str, dict], None]

@dataclass(frozen=True)
class Gene:
    """
        Um parâmetro que a busca pode mexer, com a faixa permitida.
        nome: chave do gene no cromossomo.
        minimo, maximo: limites fechados da faixa.
        inteiro: True para gene que só aceita inteiros (como a sensibilidade).
    """
    nome: str
    minimo: float
    maximo: float
    inteiro: bool = False

    def __post_init__(self):
        if not (math.isfinite(self.minimo) and math.isfinite(self.maximo)):
            raise ValueError(f"O gene {self.nome} precisa de limites finitos.")
        if self.minimo >= self.maximo:
            raise ValueError(f"O gene {self.nome} tem mínimo {self.minimo} >= máximo {self.maximo}.")
        if self.inteiro and math.ceil(self.minimo) > math.floor(self.maximo):
            raise ValueError(f"O gene inteiro {self.nome} não tem nenhum inteiro na faixa.")

    def faixa_inteira(self) -> tuple[int, int]:
        """Menor e maior inteiro dentro da faixa (para limites fracionários)."""
        return math.ceil(self.minimo), math.floor(self.maximo)

    def corrigir(self, valor: float) -> float | int:
        """Leva o valor para dentro da faixa; gene inteiro arredonda antes de limitar."""
        if self.inteiro:
            menor, maior = self.faixa_inteira()
            return min(max(round(float(valor)), menor), maior)
        return min(max(float(valor), self.minimo), self.maximo)

    def sortear(self, rng: np.random.Generator) -> float | int:
        """Valor uniforme dentro da faixa."""
        if self.inteiro:
            menor, maior = self.faixa_inteira()
            return int(rng.integers(menor, maior + 1))
        return float(rng.uniform(self.minimo, self.maximo))

    def como_dict(self) -> dict:
        return {"nome": self.nome, "minimo": self.minimo, "maximo": self.maximo,
                "inteiro": self.inteiro}

@dataclass(frozen=True)
class ConfiguracaoGA:
    """
        Parâmetros do próprio algoritmo genético (não do gerador).
        tamanho_populacao: cromossomos por geração.
        orcamento: total de candidatos avaliados, contando os repetidos.
        tamanho_torneio: quantos são sorteados para disputar cada vaga de pai.
        taxa_cruzamento: chance de o filho misturar os dois pais; senão copia um.
        taxa_mutacao: chance de cada gene do filho sofrer mutação.
        passo_mutacao: desvio da mutação, em fração da faixa do gene.
        elite: quantos melhores passam intactos para a geração seguinte.
    """
    tamanho_populacao: int = 20
    orcamento: int = 400
    tamanho_torneio: int = 3
    taxa_cruzamento: float = 0.9
    taxa_mutacao: float = 0.3
    passo_mutacao: float = 0.1
    elite: int = 2

    def __post_init__(self):
        if self.tamanho_populacao < 2:
            raise ValueError("A população precisa de pelo menos 2 cromossomos.")
        if self.orcamento < self.tamanho_populacao:
            raise ValueError("O orçamento não cobre nem a população inicial.")
        if not 1 <= self.tamanho_torneio <= self.tamanho_populacao:
            raise ValueError("O torneio precisa de 1 até o tamanho da população.")
        if not 0 <= self.elite < self.tamanho_populacao:
            raise ValueError("A elite precisa ser menor que a população.")
        for nome in ("taxa_cruzamento", "taxa_mutacao"):
            if not 0 <= getattr(self, nome) <= 1:
                raise ValueError(f"{nome} precisa ficar entre 0 e 1.")
        if not self.passo_mutacao > 0:
            raise ValueError("passo_mutacao precisa ser positivo.")

@dataclass
class Avaliacao:
    """Um candidato avaliado: cromossomo, nota, detalhes e quando foi avaliado."""
    genes: dict
    nota: float
    detalhes: dict
    geracao: int
    ordem: int

@dataclass
class ResultadoBusca:
    """Todas as avaliações de uma busca, na ordem em que foram feitas."""
    metodo: str
    avaliacoes: list[Avaliacao] = field(default_factory=list)
    reaproveitadas: int = 0

    @property
    def melhor(self) -> Avaliacao:
        """Maior nota; no empate, a avaliada primeiro."""
        return max(self.avaliacoes, key=lambda a: (a.nota, -a.ordem))

    def melhores(self, quantidade: int) -> list[Avaliacao]:
        """
            Os `quantidade` cromossomos de maior nota, cada um uma vez só (fica a
            primeira avaliação dele) e sem os descartados (-inf). No empate, o
            avaliado primeiro. Pode devolver menos, se a busca achou menos.
        """
        if quantidade < 1:
            raise ValueError("A lista de melhores precisa de pelo menos 1 lugar.")
        unicos = {}
        for avaliacao in self.avaliacoes:
            unicos.setdefault(chave(avaliacao.genes), avaliacao)
        validos = [a for a in unicos.values() if math.isfinite(a.nota)]
        return sorted(validos, key=lambda a: (-a.nota, a.ordem))[:quantidade]

    def melhor_acumulado(self) -> np.ndarray:
        """Melhor nota vista até cada avaliação: a curva que compara GA e busca aleatória."""
        return np.maximum.accumulate([a.nota for a in self.avaliacoes])

def chave(genes: dict) -> tuple:
    return tuple(sorted(genes.items()))

class _Orcamento:
    """
        Conta os candidatos e guarda as notas já calculadas. Um cromossomo
        repetido gasta orçamento do mesmo jeito (a busca "pediu" aquele
        candidato), mas a avaliação não é refeita: a nota é determinística.
    """
    def __init__(self, avaliar: Avaliador, orcamento: int, resultado: ResultadoBusca,
                 observar: Observador | None = None):
        self.avaliar = avaliar
        self.observar = observar
        self.restante = orcamento
        self.resultado = resultado
        self.cache: dict[tuple, tuple[float, dict]] = {}

    def __call__(self, genes: dict, geracao: int) -> Avaliacao:
        if self.restante <= 0:
            raise RuntimeError("Orçamento esgotado.")
        self.restante -= 1
        k = chave(genes)
        repetido = k in self.cache
        if repetido:
            self.resultado.reaproveitadas += 1
        else:
            nota, detalhes = self.avaliar(dict(genes))
            self.cache[k] = (float(nota), detalhes)
        nota, detalhes = self.cache[k]
        avaliacao = Avaliacao(dict(genes), nota, detalhes, geracao, len(self.resultado.avaliacoes))
        self.resultado.avaliacoes.append(avaliacao)
        if self.observar is not None:
            self.observar("candidato", {"avaliacao": avaliacao, "restante": self.restante,
                                        "repetido": repetido})
        return avaliacao

def sortear_cromossomo(genes: tuple[Gene, ...], rng: np.random.Generator) -> dict:
    return {gene.nome: gene.sortear(rng) for gene in genes}

def torneio(populacao: list[Avaliacao], tamanho: int, rng: np.random.Generator) -> Avaliacao:
    """Sorteia `tamanho` cromossomos sem repetição e devolve o de maior nota."""
    indices = rng.choice(len(populacao), size=tamanho, replace=False)
    # Empate fica com o primeiro sorteado, para a escolha não depender de float.
    return max((populacao[i] for i in indices), key=lambda a: a.nota)

def cruzar(pai: dict, mae: dict, rng: np.random.Generator) -> dict:
    """Cruzamento uniforme: cada gene vem de um dos pais, com chance 1/2."""
    return {nome: (pai[nome] if rng.random() < 0.5 else mae[nome]) for nome in pai}

def mutar(cromossomo: dict, genes: tuple[Gene, ...], taxa: float, passo: float,
          rng: np.random.Generator) -> dict:
    """
        Soma a cada gene, com chance `taxa`, um desvio normal de `passo` vezes a
        faixa dele, e devolve o valor para dentro da faixa.
    """
    mutado = dict(cromossomo)
    for gene in genes:
        if rng.random() < taxa:
            desvio = rng.normal(0.0, passo * (gene.maximo - gene.minimo))
            mutado[gene.nome] = gene.corrigir(mutado[gene.nome] + desvio)
    return mutado

def evoluir(genes: tuple[Gene, ...], avaliar: Avaliador, config: ConfiguracaoGA,
            seed: int, observar: Observador | None = None) -> ResultadoBusca:
    """
        Roda o algoritmo genético até gastar o orçamento.
        1. população inicial sorteada dentro dos limites;
        2. a cada geração, a elite passa intacta e o resto da população é
           trocado por filhos: dois pais por torneio, cruzamento, mutação;
        3. a última geração pode ficar incompleta, para não passar do orçamento.
        A mesma seed reproduz a mesma sequência de candidatos.
        observar: recebe o andamento (ver Observador); não muda a busca.
    """
    rng = numpy_rng(seed)
    resultado = ResultadoBusca("genetico")
    gastar = _Orcamento(avaliar, config.orcamento, resultado, observar)

    def avisar_geracao(numero: int, populacao: list[Avaliacao]):
        if observar is not None:
            observar("geracao", {"geracao": numero, "populacao": list(populacao),
                                 "resultado": resultado})

    populacao = [gastar(sortear_cromossomo(genes, rng), 0)
                 for _ in range(config.tamanho_populacao)]
    avisar_geracao(0, populacao)
    geracao = 0
    while gastar.restante > 0:
        geracao += 1
        ordenada = sorted(populacao, key=lambda a: (-a.nota, a.ordem))
        filhos = []
        while len(filhos) < config.tamanho_populacao - config.elite and gastar.restante > 0:
            pai = torneio(populacao, config.tamanho_torneio, rng)
            mae = torneio(populacao, config.tamanho_torneio, rng)
            if rng.random() < config.taxa_cruzamento:
                filho = cruzar(pai.genes, mae.genes, rng)
            else:
                filho = dict(pai.genes)
            filho = mutar(filho, genes, config.taxa_mutacao, config.passo_mutacao, rng)
            filhos.append(gastar(filho, geracao))
        populacao = ordenada[:config.elite] + filhos
        avisar_geracao(geracao, populacao)

    return resultado

def busca_aleatoria(genes: tuple[Gene, ...], avaliar: Avaliador, orcamento: int,
                    seed: int, observar: Observador | None = None) -> ResultadoBusca:
    """
        Controle do GA: sorteia `orcamento` cromossomos dentro dos mesmos
        limites e avalia todos. Mesmo orçamento e mesma avaliação que o GA, sem
        seleção nem herança.
    """
    rng = numpy_rng(seed)
    resultado = ResultadoBusca("aleatoria")
    gastar = _Orcamento(avaliar, orcamento, resultado, observar)
    for _ in range(orcamento):
        gastar(sortear_cromossomo(genes, rng), 0)
    return resultado
