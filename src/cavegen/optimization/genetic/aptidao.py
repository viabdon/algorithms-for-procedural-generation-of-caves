"""Nota de uma caverna contra o campo-alvo, e as regras de parada antecipada.

A nota é a soma do campo-alvo nos voxels vazios da caverna, dividida pela soma
do campo positivo:

    nota = soma(alvo[vazio]) / soma(alvo[alvo > 0])

Vazio onde o alvo é positivo soma, vazio onde é negativo tira. O máximo é 1:
vazio em todo o positivo e em nenhum negativo. Multiplicar o alvo por uma
constante não muda a nota (ela aparece em cima e embaixo), por isso a escala
do log do alvo não importa, só se tem log ou não.

O alvo usado no GA do CA é o SDF do Elaphes com o zero deslocado 3 voxels para
fora e comprimido com log (`tools/sdf/sdf.py --limiar -3 --log 1`). Ele fica
fixo durante toda a busca.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

# Nota de quem foi cortado: abaixo de qualquer nota possível, então nunca vence.
NOTA_MINIMA = -np.inf

@dataclass(frozen=True)
class Cortes:
    """
        Limites da parada antecipada, relativos ao alvo (não à grade).
        fator_minimo: vazio abaixo de fator_minimo x positivos do alvo é pouco.
        fator_maximo: vazio acima de fator_maximo x positivos do alvo é demais.
        fracao_convergencia: se muda menos que essa fração da grade num passo,
                             o CA convergiu.
    """
    fator_minimo: float = 0.5
    fator_maximo: float = 5.0
    fracao_convergencia: float = 1e-4

    def __post_init__(self):
        if not 0 < self.fator_minimo < 1 < self.fator_maximo:
            raise ValueError("Os fatores precisam de 0 < mínimo < 1 < máximo.")
        if not 0 <= self.fracao_convergencia < 1:
            raise ValueError("fracao_convergencia precisa ficar em [0, 1).")

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
        """Quantidade de vazio aceita: (mínimo, máximo), em voxels."""
        return cortes.fator_minimo * self.referencia, cortes.fator_maximo * self.referencia

    def dentro_da_faixa(self, vazios: int, cortes: Cortes) -> bool:
        minimo, maximo = self.faixa(cortes)
        return minimo <= vazios <= maximo

def motivo_da_parada(vazios: int, vazios_antes: int, mudancas: int, alvo: Alvo,
                     cortes: Cortes) -> str | None:
    """
        Diz se o CA para depois deste passo, e por quê.
        "vazio_demais": acima do máximo e não diminuiu no passo.
        "vazio_de_menos": abaixo do mínimo e não aumentou no passo.
        "convergiu": mudou menos que a fração de convergência da grade.
        None: continua.
        Fora da faixa, mas voltando para ela, continua: o ruído inicial nasce
        com muito mais vazio que o alvo e só encolhe com as iterações.
        vazios, vazios_antes: vazio depois e antes do passo.
        mudancas: células que trocaram de estado no passo.
    """
    minimo, maximo = alvo.faixa(cortes)
    if vazios > maximo and vazios >= vazios_antes:
        return "vazio_demais"
    if vazios < minimo and vazios <= vazios_antes:
        return "vazio_de_menos"
    if mudancas < cortes.fracao_convergencia * alvo.campo.size:
        return "convergiu"
    return None

def nota_do_passo(vazio: np.ndarray, alvo: Alvo, cortes: Cortes) -> float:
    """Nota da caverna num passo: NOTA_MINIMA se o vazio está fora da faixa."""
    if not alvo.dentro_da_faixa(int(np.count_nonzero(vazio)), cortes):
        return NOTA_MINIMA
    return alvo.nota(vazio)

def nota_da_copia_pura(peso: np.ndarray, alvo: Alvo, limiar: float = 0.0) -> float:
    """
        Nota do próprio peso binarizado (peso > limiar vira vazio), sem rodar o
        CA e sem passar pelos cortes.
        Com limiar 0 é a cópia pura do SDF (o log não muda o sinal). Com o
        limiar do alvo escrito na unidade do peso é o teto trivial: como o alvo
        é o próprio SDF deslocado, esse corte acerta a região positiva inteira
        e dá 1. As duas servem de referência para ler a
        nota do CA, que mede aderência ao campo e não ganho gerativo: chegar
        perto de 1 pode ser só o CA aprendendo a deslocar o limiar do peso.
    """
    return alvo.nota(np.asarray(peso) > limiar)
