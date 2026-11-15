"""Cromossomo do CA guiado por SDF e a avaliação de um candidato.

Genes (limites medidos no Elaphes 64³ em 12/11/2026, com folga em volta das
melhores notas; ver docs/methodology-adjustments.md):
    chance_inicial   [0,3; 0,7]   chance de cada célula da semente nascer vazia
    sensibilidade    [1, 20]      inteiro; de 18 para cima a caverna sempre morria

Fora do cromossomo, fixos:
    peso: o campo carregado entra no CA como está, sem escala nem outro
          multiplicador. O SDF é uma dica para o CA, não a resposta: com a
          escala como gene, o GA a subia até o peso passar dos 27 vizinhos
          possíveis e o CA virava um limiar sobre o SDF (o decalque).
    iterações: o CA roda até MAX_ITERACOES, com a nota calculada em todo passo;
               a melhor iteração (pela média das seeds) sai junto com a nota.
    borda: sempre NEAREST (não fecha nem abre a beirada da grade).

A regra de geração é "rodar até N iterações, parando antes se a parada
antecipada disparar". Ela é determinística, então o candidato com N
iterações se reproduz exatamente, inclusive nas seeds reservadas.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cavegen.generators.cellular_automata.generator import BorderTreatment, iterate
from cavegen.generators.cellular_automata.seeds import generate_seed_matrix
from cavegen.optimization.genetic.algoritmo import Gene
from cavegen.optimization.genetic.aptidao import (
    NOTA_MINIMA,
    Alvo,
    Cortes,
    motivo_da_parada,
    nota_do_passo,
)

GENES_CA = (
    Gene("chance_inicial", 0.3, 0.7),
    Gene("sensibilidade", 1, 20, inteiro=True),
)
MAX_ITERACOES = 50
BORDA = BorderTreatment.NEAREST
CORTES_PADRAO = Cortes()

@dataclass
class Trajetoria:
    """
        Uma execução do CA, passo a passo.
        notas: nota em cada iteração 1..max_iteracoes. Depois da parada repete
               a nota do passo em que parou, que é o que a regra de geração dá
               para qualquer N maior.
        vazios, mudancas: vazio e células que trocaram, em cada passo rodado.
        parada: iteração em que parou (igual a max_iteracoes se não parou antes).
        motivo: motivo_da_parada, ou None se chegou ao máximo.
        final: a caverna na iteração `parada` (True = vazio).
    """
    notas: np.ndarray
    vazios: list[int]
    mudancas: list[int]
    parada: int
    motivo: str | None
    final: np.ndarray

def rodar_ca(genes: dict, peso: np.ndarray, alvo: Alvo, semente: int,
             max_iteracoes: int = MAX_ITERACOES, cortes: Cortes = CORTES_PADRAO) -> Trajetoria:
    """
        Roda o CA de um cromossomo numa semente, até max_iteracoes ou até a
        parada antecipada.
        peso: campo somado aos vizinhos, cúbico, usado como está (o padrão do
              GA é o SDF comprimido com ln(1 + |d|)).
        alvo: campo da nota, do mesmo formato.
        semente: semente da matriz inicial (numpy_rng).
    """
    if max_iteracoes < 1:
        raise ValueError("O CA precisa de pelo menos 1 iteração.")
    lado = peso.shape[0]
    if peso.shape != (lado, lado, lado) or alvo.shape != peso.shape:
        raise ValueError(f"Peso {peso.shape} e alvo {alvo.shape} precisam ser o mesmo cubo.")

    matriz = generate_seed_matrix(lado, genes["chance_inicial"], seed=semente)
    vazios_antes = int(matriz.sum())
    notas, vazios, mudancas, motivo = [], [], [], None

    for _ in range(max_iteracoes):
        seguinte = iterate(matriz, genes["sensibilidade"], BORDA, peso)
        mudou = int(np.count_nonzero(seguinte != matriz))
        matriz = seguinte
        vazio = int(matriz.sum())
        notas.append(nota_do_passo(matriz, alvo, cortes))
        vazios.append(vazio)
        mudancas.append(mudou)
        motivo = motivo_da_parada(vazio, vazios_antes, mudou, alvo, cortes)
        if motivo is not None:
            break
        vazios_antes = vazio

    parada = len(notas)
    notas = np.array(notas + [notas[-1]] * (max_iteracoes - parada), dtype=np.float64)
    return Trajetoria(notas, vazios, mudancas, parada, motivo, matriz.astype(bool))

class AvaliadorCA:
    """
        Função de avaliação do GA para o CA: roda o cromossomo em cada semente
        de ajuste e dá a nota da melhor iteração pela média das sementes.
        Uma semente cortada entra na média com NOTA_MINIMA, então o candidato
        que falha em qualquer semente perde.
    """
    def __init__(self, peso: np.ndarray, alvo: Alvo, sementes: tuple[int, ...],
                 max_iteracoes: int = MAX_ITERACOES, cortes: Cortes = CORTES_PADRAO):
        if not sementes:
            raise ValueError("Precisa de pelo menos uma semente de ajuste.")
        # Cópia somente leitura com os mesmos valores e o mesmo tipo: o CA recebe
        # exatamente o campo carregado, e a busca não consegue mexer nele.
        peso = np.array(peso, copy=True)
        if not np.all(np.isfinite(peso)):
            raise ValueError("O peso tem valores não finitos.")
        peso.setflags(write=False)
        self.peso = peso
        self.alvo = alvo
        self.sementes = tuple(int(s) for s in sementes)
        self.max_iteracoes = max_iteracoes
        self.cortes = cortes

    def trajetorias(self, genes: dict, sementes=None, max_iteracoes=None) -> list[Trajetoria]:
        sementes = self.sementes if sementes is None else sementes
        max_iteracoes = self.max_iteracoes if max_iteracoes is None else max_iteracoes
        return [rodar_ca(genes, self.peso, self.alvo, s, max_iteracoes, self.cortes)
                for s in sementes]

    def __call__(self, genes: dict) -> tuple[float, dict]:
        trajetorias = self.trajetorias(genes)
        por_semente = np.stack([t.notas for t in trajetorias])
        with np.errstate(invalid="ignore"):
            media = por_semente.mean(axis=0)
        melhor = int(np.argmax(media))  # empate fica com a menor iteração
        return float(media[melhor]), {
            "iteracoes": melhor + 1,
            "paradas": [t.parada for t in trajetorias],
            "motivos": [t.motivo or "maximo" for t in trajetorias],
            "notas_por_semente": por_semente[:, melhor].tolist(),
            # Por passo e por semente. viraram_1 - viraram_0 é a variação do
            # vazio e viraram_1 + viraram_0 são as mudanças, então os dois saem
            # destas listas.
            "vazios": [t.vazios for t in trajetorias],
            "mudancas": [t.mudancas for t in trajetorias],
        }

    def nota_com_iteracoes(self, genes: dict, iteracoes: int,
                           sementes: tuple[int, ...]) -> np.ndarray:
        """
            Nota de cada semente com o número de iterações já escolhido, sem
            escolher de novo: é assim que o campeão é avaliado nas sementes
            reservadas.
        """
        return np.array([t.notas[-1] for t in self.trajetorias(genes, sementes, iteracoes)])

__all__ = ["BORDA", "CORTES_PADRAO", "GENES_CA", "MAX_ITERACOES", "NOTA_MINIMA", "AvaliadorCA",
           "Trajetoria", "rodar_ca"]
