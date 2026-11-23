"""Nota de uma caverna gerada contra o campo-alvo, o vazio mínimo aceito e o
resumo das notas entre as cavernas.

A nota é a soma do campo-alvo nos voxels vazios da caverna, dividida pela soma
do campo onde ele é positivo:

    nota = soma(alvo[vazio]) / soma(alvo[alvo > 0])

O denominador é o máximo que o numerador alcança (vazio em todo voxel positivo
e em nenhum negativo), então a nota é a fração desse máximo: 1 no melhor caso,
0 sem nenhum vazio e negativa quando o vazio fora da forma pesa mais que o de
dentro. Multiplicar o alvo por uma constante não muda a nota (ela aparece em
cima e embaixo).

O alvo de cada caverna é o campo do peso, o SDF dela comprimido com
2 · ln(1 + |d|) e sem deslocar o zero (`cavegen/tools/sdf/sdf.py --log 2`), mais
um acréscimo somado a todo voxel (ca.ACRESCIMO_ALVO: 1 em ga_015, 1,5 desde
ga_016, valor em aberto). Ele
fica fixo durante toda a busca. A explicação completa, com os números do Elaphes, está no
README do módulo.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

# Nota de quem foi cortado: abaixo de qualquer nota possível, então nunca vence.
NOTA_MINIMA = -np.inf

@dataclass(frozen=True)
class Cortes:
    """
        Faixa de vazio aceita, relativa aos voxels positivos do alvo (não à grade).
        fator_minimo: vazio abaixo de fator_minimo x positivos do alvo é pouco.
        fator_maximo: vazio acima de fator_maximo x positivos do alvo é demais;
                      None (o padrão desde 22/11/2026) = sem limite de cima.
        Fora da faixa, a nota do passo é NOTA_MINIMA. A faixa não interrompe o
        CA: ele roda todas as iterações, e ela só decide a nota de cada passo.

        Só o mínimo fica porque a grade vazia tem nota 0 e, sem ele, ganharia
        de todo candidato com nota negativa. O excesso de vazio a própria nota
        já pune (encher a grade do Elaphes dava -4033 com o alvo log x1; com o
        log x2 e o acréscimo de 1,5, dá -604), e o limite de cima
        cortava a maioria dos candidatos, sem dar direção à seleção. Atenção:
        a iteração escolhida é a de maior nota, então um candidato que enche a
        grade aos poucos leva a nota do passo menos cheio (quase sempre o 1),
        não a da grade cheia.
    """
    fator_minimo: float = 0.5
    fator_maximo: float | None = None

    def __post_init__(self):
        if not 0 < self.fator_minimo < 1:
            raise ValueError("O fator mínimo precisa de 0 < mínimo < 1.")
        if self.fator_maximo is not None and not self.fator_maximo > 1:
            raise ValueError("O fator máximo precisa ser maior que 1 (ou None, sem limite).")

    def como_dict(self) -> dict:
        return asdict(self)

class Alvo:
    """
        Campo-alvo da aptidão, guardado como cópia somente leitura: a busca não
        consegue mexer nele.
        campo: matriz float (ZYX), positivo onde vale a pena ter vazio.
    """
    def __init__(self, campo: np.ndarray):
        campo = np.array(campo, dtype=np.float32, copy=True)
        if not np.all(np.isfinite(campo)):
            raise ValueError("O alvo tem valores não finitos.")
        positivo = campo > 0
        if not positivo.any():
            raise ValueError("O alvo não tem região positiva: nada para acertar.")
        campo.setflags(write=False)
        self.campo = campo
        self.referencia = int(positivo.sum())
        self.soma_positiva = float(campo[positivo].sum(dtype=np.float64))

    @property
    def shape(self) -> tuple:
        return self.campo.shape

    def nota(self, vazio: np.ndarray) -> float:
        """Nota de uma caverna (True ou 1 = vazio), entre -inf e 1."""
        vazio = np.asarray(vazio).astype(bool, copy=False)
        if vazio.shape != self.campo.shape:
            raise ValueError(f"A caverna tem formato {vazio.shape}, o alvo {self.campo.shape}.")
        return float(self.campo[vazio].sum(dtype=np.float64)) / self.soma_positiva

    def faixa(self, cortes: Cortes) -> tuple[float, float]:
        """Quantidade de vazio aceita: (mínimo, máximo), em voxels; máximo inf sem limite."""
        maximo = math.inf if cortes.fator_maximo is None else cortes.fator_maximo * self.referencia
        return cortes.fator_minimo * self.referencia, maximo

    def nota_da_grade_cheia(self) -> float:
        """
            Nota de tudo vazio (no Elaphes, -604 com o log x2 e o acréscimo
            de 1,5; -4033 com o alvo log x1): a régua para ler uma nota
            negativa, já que ela depende da caverna. Não é o piso: vazio só no
            lado negativo dá 1 a menos (a nota da grade cheia soma o 1 da
            parte positiva).
        """
        return float(self.campo.sum(dtype=np.float64)) / self.soma_positiva

    def dentro_da_faixa(self, vazios: int, cortes: Cortes) -> bool:
        minimo, maximo = self.faixa(cortes)
        return minimo <= vazios <= maximo

def situacao_do_vazio(vazios: int, alvo: Alvo, cortes: Cortes) -> str:
    """
        Onde uma quantidade de vazio cai na faixa aceita: "vazio_de_menos",
        "vazio_demais" ou "na_faixa". Só descreve; quem corta é nota_do_passo.
    """
    minimo, maximo = alvo.faixa(cortes)
    if vazios < minimo:
        return "vazio_de_menos"
    if vazios > maximo:
        return "vazio_demais"
    return "na_faixa"

def nota_do_passo(vazio: np.ndarray, alvo: Alvo, cortes: Cortes) -> float:
    """Nota da caverna num passo: NOTA_MINIMA se o vazio está fora da faixa."""
    if not alvo.dentro_da_faixa(int(np.count_nonzero(vazio)), cortes):
        return NOTA_MINIMA
    return alvo.nota(vazio)

def nota_da_copia_pura(peso: np.ndarray, alvo: Alvo) -> float:
    """
        Nota do próprio peso binarizado (peso > 0 vira vazio), sem rodar o CA e
        sem passar pela faixa de vazio: a caverna que só copia o sinal do peso.
        Com o alvo igual ao peso, ela dá exatamente 1, o máximo da nota. Com o
        acréscimo do alvo (desde 22/11/2026) ela fica abaixo de 1, porque a
        casca de borda (peso 0), e com 1,5 também a primeira camada de fora,
        passa a ser positiva no alvo e a cópia não a pinta. Fica como régua: a nota do CA mede o quanto ele chega perto de
        copiar o campo, não ganho gerativo.
    """
    return alvo.nota(np.asarray(peso) > 0)

def resumo_entre_cavernas(por_caverna: dict[str, float]) -> dict:
    """
        Junta as notas de um candidato nas várias cavernas.
        media: o critério do ranking; cada caverna pesa igual.
        min, max: a pior e a melhor caverna.
        desvio: desvio padrão populacional entre as cavernas (0 com uma só). Fica
                NaN se alguma caverna foi cortada: não há dispersão com -inf.
        por_caverna: as notas de cada caverna, como vieram.
        Uma caverna cortada (NOTA_MINIMA) leva a média e o mínimo para
        NOTA_MINIMA: o candidato precisa funcionar em todas.
    """
    if not por_caverna:
        raise ValueError("Precisa da nota de pelo menos uma caverna.")
    notas = np.array([float(n) for n in por_caverna.values()], dtype=np.float64)
    finitas = bool(np.all(np.isfinite(notas)))
    return {"media": float(np.mean(notas)), "min": float(notas.min()),
            "max": float(notas.max()), "desvio": float(np.std(notas)) if finitas else math.nan,
            "por_caverna": {nome: float(n) for nome, n in por_caverna.items()}}
