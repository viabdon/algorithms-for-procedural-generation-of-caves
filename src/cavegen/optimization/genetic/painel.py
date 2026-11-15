"""Mostra no terminal o andamento da busca, etapa por etapa.

O Painel é o observador que o motor (algoritmo.py) chama a cada candidato e a
cada geração. Ele só imprime: nada do que faz muda a busca nem o resultado.

    [2/4] Busca genética: 400 candidatos, população 20
      geração  0 |  20/400 | melhor +0.577 (chance_inicial=0.3, sensibilidade=9) | ...
      candidato 47/400 · geração 3 · chance_inicial=0.559 sensibilidade=13 -> +0.612

A linha do candidato é reescrita no lugar (só num terminal de verdade); as
linhas de geração ficam, para dar para ver a evolução.
"""
from __future__ import annotations

import math
import sys
import time
from typing import TextIO

import numpy as np


def formatar_genes(genes: dict) -> str:
    return " ".join(f"{nome}={valor:.4g}" if isinstance(valor, float) else f"{nome}={valor}"
                    for nome, valor in genes.items())

def formatar_nota(nota: float) -> str:
    return f"{nota:+.3f}" if math.isfinite(nota) else "cortado"

class Painel:
    """
        orcamento: total de candidatos, para mostrar "47/400".
        por_lote: True na busca aleatória, que não tem gerações: o resumo sai a
                  cada tamanho_lote candidatos.
        tamanho_lote: tamanho do lote da busca aleatória.
        saida: para onde imprimir (padrão: o terminal).
        ao_vivo: reescrever a linha do candidato no lugar. Padrão: só se a
                 saída é um terminal, para não encher arquivo de log.
    """
    def __init__(self, orcamento: int, por_lote: bool = False, tamanho_lote: int = 20,
                 saida: TextIO | None = None, ao_vivo: bool | None = None):
        self.orcamento = orcamento
        self.por_lote = por_lote
        self.tamanho_lote = tamanho_lote
        self.saida = sys.stdout if saida is None else saida
        self.ao_vivo = self.saida.isatty() if ao_vivo is None else ao_vivo
        self.avaliados = 0
        self.melhor = None
        self.inicio_bloco = time.perf_counter()
        self.lote: list = []
        self._largura = 0

    # Saída -----------------------------------------------------------------

    def _linha_viva(self, texto: str):
        if not self.ao_vivo:
            return
        self.saida.write("\r" + texto.ljust(self._largura))
        self.saida.flush()
        self._largura = len(texto)

    def _limpar_linha_viva(self):
        if self.ao_vivo and self._largura:
            self.saida.write("\r" + " " * self._largura + "\r")
            self._largura = 0

    def escrever(self, texto: str = ""):
        self._limpar_linha_viva()
        print(texto, file=self.saida, flush=True)

    def etapa(self, numero: int, total: int, texto: str):
        self.escrever()
        self.escrever(f"[{numero}/{total}] {texto}")

    # Eventos do motor ------------------------------------------------------

    def __call__(self, evento: str, dados: dict):
        if evento == "candidato":
            self._candidato(dados["avaliacao"], dados["repetido"])
        elif evento == "geracao":
            self._geracao(dados["geracao"], dados["populacao"])

    def _candidato(self, avaliacao, repetido: bool):
        self.avaliados += 1
        self.lote.append(avaliacao)
        if self.melhor is None or avaliacao.nota > self.melhor.nota:
            self.melhor = avaliacao

        if math.isfinite(avaliacao.nota):
            resultado = f"{avaliacao.nota:+.3f} ({avaliacao.detalhes['iteracoes']} it)"
        else:
            motivos = sorted(set(avaliacao.detalhes.get("motivos", [])) - {"convergiu", "maximo"})
            resultado = "cortado" + (f" ({', '.join(motivos)})" if motivos else "")
        if repetido:
            resultado += " [repetido]"
        melhor = formatar_nota(self.melhor.nota)
        self._linha_viva(f"  candidato {self.avaliados}/{self.orcamento} · geração "
                         f"{avaliacao.geracao} · {formatar_genes(avaliacao.genes)} -> "
                         f"{resultado} · melhor {melhor}")

        # A busca aleatória não tem geração: resume a cada lote.
        if self.por_lote and (len(self.lote) == self.tamanho_lote
                              or self.avaliados == self.orcamento):
            self._resumo(f"lote {math.ceil(self.avaliados / self.tamanho_lote):>3}", self.lote)

    def _geracao(self, numero: int, populacao: list):
        self._resumo(f"geração {numero:>3}", populacao)

    def _resumo(self, titulo: str, grupo: list):
        notas = np.array([a.nota for a in grupo])
        validas = notas[np.isfinite(notas)]
        media = f"{validas.mean():+.3f}" if validas.size else "  -   "
        tempo = time.perf_counter() - self.inicio_bloco
        largura = len(str(self.orcamento))
        self.escrever(
            f"  {titulo} | {self.avaliados:>{largura}}/{self.orcamento} | melhor "
            f"{formatar_nota(self.melhor.nota)} ({formatar_genes(self.melhor.genes)}) | "
            f"válidos {validas.size}/{len(grupo)} | média {media} | {tempo:.1f} s")
        self.inicio_bloco = time.perf_counter()
        self.lote = []
