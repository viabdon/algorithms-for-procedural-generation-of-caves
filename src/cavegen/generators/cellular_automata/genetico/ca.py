"""Cromossomo do CA guiado por SDF, as cavernas e a avaliação de um candidato.

Genes (limites medidos no Elaphes 64³ em 12/11/2026, ainda com o alvo antigo de
limiar -3, e chance alargada em 19/11/2026; ver o README do módulo):
    chance_inicial   [0,2; 0,8]   chance de cada célula da semente nascer vazia, de 0,02
                                  em 0,02 (por que o passo: ver o README do módulo)
    sensibilidade    [1, 20]      inteiro; de 18 para cima a caverna sempre morria

Fora do cromossomo, fixos:
    campo: cada caverna tem um campo só, o SDF dela comprimido com ln(1 + |d|) e
           escala 1, que é ao mesmo tempo o peso somado aos vizinhos e o alvo da
           nota. Ele entra no CA como está: nada o multiplica, comprime ou corta.
           A escala é fixa em 1 por decisão metodológica: quando ela era gene, o
           GA a subia até o peso passar dos 27 vizinhos possíveis e o CA virava
           um limiar sobre o SDF (o decalque).
    iterações: o CA roda sempre MAX_ITERACOES, sem parada antecipada, e a nota é
               calculada em todo passo. A melhor iteração (pela média das seeds e
               das cavernas) sai junto com a nota e vale para todas as cavernas.
    borda: sempre NEAREST (não fecha nem abre a beirada da grade).
    modo do peso: sempre COMPLETO. É uma escolha do CA, não da busca: o GA e a
                  busca aleatória usam este mesmo avaliador.

Como nada interrompe o CA, rodar N iterações dá exatamente os N primeiros passos
de uma execução mais longa: o candidato com N iterações se reproduz, inclusive
nas seeds reservadas.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from cavegen.generators.cellular_automata.generator import BorderTreatment, ModoPeso, iterate
from cavegen.generators.cellular_automata.genetico.algoritmo import Gene
from cavegen.generators.cellular_automata.genetico.aptidao import (
    NOTA_MINIMA,
    Alvo,
    Cortes,
    nota_do_passo,
    resumo_entre_cavernas,
    situacao_do_vazio,
)
from cavegen.generators.cellular_automata.seeds import generate_seed_matrix

GENES_CA = (
    Gene("chance_inicial", 0.2, 0.8, passo=0.02),
    Gene("sensibilidade", 1, 20, inteiro=True),
)
MAX_ITERACOES = 40
BORDA = BorderTreatment.NEAREST
MODO_PESO = ModoPeso.COMPLETO
CORTES_PADRAO = Cortes()

class Caverna:
    """
        Uma caverna em que os candidatos são avaliados. Ela tem um campo só,
        que guia o CA (peso) e dá a nota (alvo).
        nome: rótulo da caverna nas notas, no painel e no resultado.
        campo: SDF da caverna com log, cúbico, em ZYX. O peso é uma cópia
               somente leitura com os mesmos valores e o mesmo tipo; o alvo é o
               Alvo do mesmo campo.
    """
    def __init__(self, nome: str, campo: np.ndarray):
        campo = np.asarray(campo)
        if campo.ndim != 3 or len(set(campo.shape)) != 1:
            raise ValueError(f"A caverna {nome} tem grade {campo.shape}: a semente do CA é "
                             "um cubo (lado x lado x lado), então a grade precisa ser cúbica.")
        if not np.all(np.isfinite(campo)):
            raise ValueError(f"A caverna {nome} tem valores não finitos no SDF.")
        if not np.any(campo > 0):
            raise ValueError(
                f"A caverna {nome} não tem nenhum voxel positivo no SDF. A nota divide pela "
                "soma do campo positivo (o interno, que a inundação não alcança), então sem "
                "ele não há o que acertar. Confira a inundação da grade dessa caverna.")
        # O CA recebe exatamente o campo carregado, e a busca não consegue mexer nele.
        peso = np.array(campo, copy=True)
        peso.setflags(write=False)
        self.nome = nome
        self.peso = peso
        self.alvo = Alvo(campo)

    @property
    def lado(self) -> int:
        return self.peso.shape[0]

@dataclass
class Trajetoria:
    """
        Uma execução do CA numa caverna e numa semente, passo a passo. O CA roda
        sempre as max_iteracoes: nada o interrompe antes.
        notas: nota em cada iteração 1..max_iteracoes (NOTA_MINIMA nos passos
               com o vazio fora da faixa).
        vazios, mudancas: vazio e células que trocaram de estado, em cada passo.
        fim: onde o vazio da última iteração cai na faixa ("na_faixa",
             "vazio_demais" ou "vazio_de_menos"), para dizer por que um
             candidato cortado foi cortado.
        final: a caverna na última iteração (True = vazio).
    """
    notas: np.ndarray
    vazios: list[int]
    mudancas: list[int]
    fim: str
    final: np.ndarray

def rodar_ca(genes: dict, caverna: Caverna, semente: int, max_iteracoes: int = MAX_ITERACOES,
             cortes: Cortes = CORTES_PADRAO) -> Trajetoria:
    """
        Roda o CA de um cromossomo numa caverna e numa semente, sempre até
        max_iteracoes, com a nota de cada passo.
        semente: só o número que inicializa o sorteador da matriz inicial
                 (numpy_rng); a porcentagem de vazio vem de chance_inicial.
    """
    if max_iteracoes < 1:
        raise ValueError("O CA precisa de pelo menos 1 iteração.")

    matriz = generate_seed_matrix(caverna.lado, genes["chance_inicial"], seed=semente)
    notas, vazios, mudancas = [], [], []
    for _ in range(max_iteracoes):
        seguinte = iterate(matriz, genes["sensibilidade"], BORDA, caverna.peso, MODO_PESO)
        mudancas.append(int(np.count_nonzero(seguinte != matriz)))
        matriz = seguinte
        vazios.append(int(matriz.sum()))
        notas.append(nota_do_passo(matriz, caverna.alvo, cortes))

    return Trajetoria(np.array(notas, dtype=np.float64), vazios, mudancas,
                      situacao_do_vazio(vazios[-1], caverna.alvo, cortes), matriz.astype(bool))

def media_por_passo(notas: np.ndarray) -> np.ndarray:
    """
        Média de cada coluna (passo) de uma matriz grupos x passos, uma coluna
        por vez. É a mesma conta, na mesma ordem, que a média de um vetor só:
        assim a nota gravada se reproduz bit a bit quando um passo é refeito
        sozinho (nas seeds reservadas ou num teste).
    """
    return np.array([np.mean(coluna) for coluna in np.asarray(notas, dtype=np.float64).T])

class AvaliadorCA:
    """
        Função de avaliação do GA para o CA: roda o cromossomo em cada caverna e
        em cada semente de ajuste, e dá a nota da melhor iteração.
        1. a nota de um passo numa caverna é a média das sementes;
        2. a nota do passo do candidato é a média dessas notas entre as cavernas;
        3. a melhor iteração é a de maior média, uma só para todas as cavernas.
        Uma semente cortada leva a nota da caverna para NOTA_MINIMA naquele passo
        e, com ela, a do candidato: ele precisa ficar dentro da faixa em todas as
        sementes de todas as cavernas.
        cavernas: as cavernas, cada uma com o seu campo (peso e alvo).
        sementes: sementes de ajuste, as mesmas para todos os candidatos.
    """
    def __init__(self, cavernas: Sequence[Caverna], sementes: tuple[int, ...],
                 max_iteracoes: int = MAX_ITERACOES, cortes: Cortes = CORTES_PADRAO):
        cavernas = tuple(cavernas)
        if not cavernas:
            raise ValueError("Precisa de pelo menos uma caverna.")
        nomes = [c.nome for c in cavernas]
        if len(set(nomes)) != len(nomes):
            raise ValueError(f"Há cavernas com o mesmo nome: {nomes}.")
        if not sementes:
            raise ValueError("Precisa de pelo menos uma semente de ajuste.")
        if max_iteracoes < 1:
            raise ValueError("O CA precisa de pelo menos 1 iteração.")
        self.cavernas = cavernas
        self.sementes = tuple(int(s) for s in sementes)
        self.max_iteracoes = max_iteracoes
        self.cortes = cortes

    @property
    def nomes(self) -> list[str]:
        return [c.nome for c in self.cavernas]

    def trajetorias(self, genes: dict, sementes=None,
                    max_iteracoes=None) -> dict[str, list[Trajetoria]]:
        """Uma trajetória por semente, em cada caverna (na ordem das cavernas)."""
        sementes = self.sementes if sementes is None else sementes
        max_iteracoes = self.max_iteracoes if max_iteracoes is None else max_iteracoes
        return {c.nome: [rodar_ca(genes, c, s, max_iteracoes, self.cortes) for s in sementes]
                for c in self.cavernas}

    def __call__(self, genes: dict) -> tuple[float, dict]:
        trajetorias = self.trajetorias(genes)
        por_caverna = {nome: media_por_passo(np.stack([t.notas for t in ts]))
                       for nome, ts in trajetorias.items()}
        media = media_por_passo(np.stack(list(por_caverna.values())))
        melhor = int(np.argmax(media))  # empate fica com a menor iteração
        resumo = resumo_entre_cavernas({nome: notas[melhor] for nome, notas in por_caverna.items()})
        return resumo["media"], {
            "iteracoes": melhor + 1,
            "entre_cavernas": resumo,
            # Por caverna e por semente. viraram_1 - viraram_0 é a variação do
            # vazio e viraram_1 + viraram_0 são as mudanças, então os dois saem
            # destas listas.
            "cavernas": {nome: {"notas_por_semente": [float(t.notas[melhor]) for t in ts],
                                # Média das sementes em cada passo, de onde sai a
                                # escolha da iteração: a curva da nota no CA.
                                "notas_por_passo": por_caverna[nome].tolist(),
                                "fim": [t.fim for t in ts],
                                "vazios": [t.vazios for t in ts],
                                "mudancas": [t.mudancas for t in ts]}
                         for nome, ts in trajetorias.items()},
        }

    def nota_com_iteracoes(self, genes: dict, iteracoes: int,
                           sementes: tuple[int, ...]) -> dict[str, np.ndarray]:
        """
            Nota de cada semente, em cada caverna, com o número de iterações já
            escolhido, sem escolher de novo.
        """
        return {nome: np.array([t.notas[-1] for t in ts])
                for nome, ts in self.trajetorias(genes, sementes, iteracoes).items()}

    def conferir(self, genes: dict, iteracoes: int, sementes: tuple[int, ...]) -> dict:
        """
            É assim que os melhores são conferidos nas sementes reservadas: as
            iterações já escolhidas, em todas as cavernas. Devolve o resumo entre
            as cavernas (media, min, max, desvio, por_caverna, com a média das
            sementes em cada caverna), a pior semente de todas e as notas de
            cada semente em cada caverna.
        """
        notas = self.nota_com_iteracoes(genes, iteracoes, sementes)
        resumo = resumo_entre_cavernas({nome: float(np.mean(v)) for nome, v in notas.items()})
        return {**resumo,
                "pior_semente": float(min(v.min() for v in notas.values())),
                "notas_por_semente": {nome: v.tolist() for nome, v in notas.items()}}

__all__ = ["BORDA", "CORTES_PADRAO", "GENES_CA", "MAX_ITERACOES", "MODO_PESO", "NOTA_MINIMA",
           "AvaliadorCA", "Caverna", "Trajetoria", "media_por_passo", "rodar_ca"]
