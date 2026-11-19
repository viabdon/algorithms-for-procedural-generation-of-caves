"""Mostra no terminal o andamento da busca, etapa por etapa.

O Painel é o observador que o motor (algoritmo.py) chama a cada candidato e a
cada geração. Ele só imprime: nada do que faz muda a busca nem o resultado.

    [2/4] 🧬 Busca genética: 400 candidatos, população 20
      🧬 geração  0 |  20/400 | 🏆 melhor +0.577 (chance_inicial=0.3 sensibilidade=9) | ...
      candidato 47/400 · geração 3 · chance_inicial=0.56 sensibilidade=13 -> +0.612

A linha do candidato é reescrita no lugar (só num terminal de verdade); as
linhas de geração ficam, para dar para ver a evolução.

Cores e emojis só aparecem num terminal que aceita os dois. Fora dele (saída
indo para arquivo, testes) ou com a variável NO_COLOR definida, o texto sai
puro, sem códigos de cor.
"""
from __future__ import annotations

import io
import math
import os
import sys
import time
from typing import TextIO

import numpy as np

# Códigos ANSI de cor e estilo.
NEGRITO, FRACO = "1", "2"
VERMELHO, VERDE, AMARELO, AZUL, MAGENTA, CIANO = "31", "32", "33", "34", "35", "36"
EMOJIS_USADOS = "📂🧬🎲🔍💾🏆⭐✅📊⏱♻️🥇🥈🥉⚠️📁"

def formatar_genes(genes: dict) -> str:
    return " ".join(f"{nome}={valor:.4g}" if isinstance(valor, float) else f"{nome}={valor}"
                    for nome, valor in genes.items())

def formatar_nota(nota: float) -> str:
    return f"{nota:+.3f}" if math.isfinite(nota) else "cortado"

def _ativar_ansi(saida: TextIO) -> bool:
    """
        Liga as cores no console do Windows (fora dele, os terminais já
        entendem ANSI). Devolve False se não conseguiu, e aí o painel sai sem cor.
    """
    if os.name != "nt":
        return True
    try:
        import ctypes
        import msvcrt
        kernel32 = ctypes.windll.kernel32
        handle = msvcrt.get_osfhandle(saida.fileno())
        modo = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(modo)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, modo.value | 0x0004))
    except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
        return False

def _aceita_emojis(saida: TextIO) -> bool:
    try:
        EMOJIS_USADOS.encode(saida.encoding or "ascii")
    except (UnicodeEncodeError, LookupError, AttributeError, TypeError):
        return False
    return True

class Estilo:
    """
        Cores e emojis do painel. Desligados, os métodos devolvem o texto puro.
        cores: pintar com códigos ANSI.
        emojis: pôr os emojis na frente das linhas.
    """
    def __init__(self, cores: bool = False, emojis: bool = False):
        self.cores = cores
        self.emojis = emojis

    @classmethod
    def para(cls, saida: TextIO) -> Estilo:
        """Liga cores e emojis só num terminal de verdade que aceite os dois."""
        try:
            terminal = saida.isatty()
        except (AttributeError, ValueError):
            terminal = False
        if not terminal:
            return cls()
        cores = "NO_COLOR" not in os.environ and _ativar_ansi(saida)
        return cls(cores=cores, emojis=_aceita_emojis(saida))

    def pintar(self, texto: str, *codigos: str) -> str:
        if not self.cores or not codigos:
            return texto
        return f"\033[{';'.join(codigos)}m{texto}\033[0m"

    def icone(self, emoji: str) -> str:
        """O emoji seguido de espaço, ou nada se os emojis estão desligados."""
        return f"{emoji} " if self.emojis else ""

    def nota(self, nota: float, *extra: str) -> str:
        """Nota formatada: verde se positiva, amarela se negativa, vermelha se cortada."""
        if not math.isfinite(nota):
            cor = VERMELHO
        else:
            cor = VERDE if nota >= 0 else AMARELO
        return self.pintar(formatar_nota(nota), cor, *extra)

class Painel:
    """
        orcamento: total de candidatos, para mostrar "47/400".
        por_lote: True na busca aleatória, que não tem gerações: o resumo sai a
                  cada tamanho_lote candidatos.
        tamanho_lote: tamanho do lote da busca aleatória.
        saida: para onde imprimir (padrão: o terminal).
        ao_vivo: reescrever a linha do candidato no lugar. Padrão: só se a
                 saída é um terminal, para não encher arquivo de log.
        estilo: cores e emojis. Padrão: ligados só num terminal que aceite.
    """
    def __init__(self, orcamento: int, por_lote: bool = False, tamanho_lote: int = 20,
                 saida: TextIO | None = None, ao_vivo: bool | None = None,
                 estilo: Estilo | None = None):
        self.orcamento = orcamento
        self.por_lote = por_lote
        self.tamanho_lote = tamanho_lote
        self.saida = sys.stdout if saida is None else saida
        self.ao_vivo = self.saida.isatty() if ao_vivo is None else ao_vivo
        self.estilo = Estilo.para(self.saida) if estilo is None else estilo
        self.avaliados = 0
        self.melhor = None
        self.melhor_no_resumo = None  # melhor nota no resumo anterior, para o "novo recorde"
        self.inicio_bloco = time.perf_counter()
        self.lote: list = []
        self._largura = 0

    # Saída -----------------------------------------------------------------

    def _linha_viva(self, texto: str, visivel: int):
        # visivel: tamanho do texto sem os códigos de cor, para apagar a linha certa.
        if not self.ao_vivo:
            return
        self.saida.write("\r" + texto + " " * max(self._largura - visivel, 0))
        self.saida.flush()
        self._largura = visivel

    def _limpar_linha_viva(self):
        if self.ao_vivo and self._largura:
            self.saida.write("\r" + " " * self._largura + "\r")
            self._largura = 0

    def escrever(self, texto: str = ""):
        self._limpar_linha_viva()
        print(texto, file=self.saida, flush=True)

    def etapa(self, numero: int, total: int, texto: str, emoji: str = ""):
        e = self.estilo
        self.escrever()
        self.escrever(e.pintar(f"[{numero}/{total}] ", NEGRITO, CIANO)
                      + e.icone(emoji) + e.pintar(texto, NEGRITO))

    # Eventos do motor ------------------------------------------------------

    def __call__(self, evento: str, dados: dict):
        if evento == "candidato":
            self._candidato(dados["avaliacao"], dados["repetido"])
        elif evento == "geracao":
            self._geracao(dados["geracao"], dados["populacao"])

    def _candidato(self, avaliacao, repetido: bool):
        e = self.estilo
        self.avaliados += 1
        self.lote.append(avaliacao)
        if self.melhor is None or avaliacao.nota > self.melhor.nota:
            self.melhor = avaliacao

        if math.isfinite(avaliacao.nota):
            puro = f"{formatar_nota(avaliacao.nota)} ({avaliacao.detalhes['iteracoes']} it)"
            resultado = f"{e.nota(avaliacao.nota)} ({avaliacao.detalhes['iteracoes']} it)"
        else:
            motivos = sorted(set(avaliacao.detalhes.get("motivos", [])) - {"convergiu", "maximo"})
            puro = "cortado" + (f" ({', '.join(motivos)})" if motivos else "")
            resultado = e.pintar(puro, VERMELHO)
        if repetido:
            puro += " [repetido]"
            resultado += e.pintar(" [repetido]", FRACO)
        inicio = (f"  candidato {self.avaliados}/{self.orcamento} · geração "
                  f"{avaliacao.geracao} · {formatar_genes(avaliacao.genes)} -> ")
        fim = f" · melhor {formatar_nota(self.melhor.nota)}"
        self._linha_viva(e.pintar(inicio, FRACO) + resultado
                         + e.pintar(" · melhor ", FRACO) + e.nota(self.melhor.nota, NEGRITO),
                         len(inicio) + len(puro) + len(fim))

        # A busca aleatória não tem geração: resume a cada lote.
        if self.por_lote and (len(self.lote) == self.tamanho_lote
                              or self.avaliados == self.orcamento):
            self._resumo(f"lote {math.ceil(self.avaliados / self.tamanho_lote):>3}", self.lote,
                         "🎲")

    def _geracao(self, numero: int, populacao: list):
        self._resumo(f"geração {numero:>3}", populacao, "🧬")

    def _resumo(self, titulo: str, grupo: list, emoji: str):
        e = self.estilo
        notas = np.array([a.nota for a in grupo])
        validas = notas[np.isfinite(notas)]
        media = e.nota(float(validas.mean())) if validas.size else "  -   "
        tempo = time.perf_counter() - self.inicio_bloco
        largura = len(str(self.orcamento))
        if validas.size == len(grupo):
            cor_validos = VERDE
        else:
            cor_validos = AMARELO if validas.size else VERMELHO
        recorde = ""
        if self.melhor_no_resumo is not None and self.melhor.nota > self.melhor_no_resumo:
            recorde = " " + e.icone("⭐") + e.pintar("novo recorde", NEGRITO, AMARELO)
        self.escrever(
            f"  {e.icone(emoji)}{e.pintar(titulo, NEGRITO, MAGENTA)} | "
            f"{self.avaliados:>{largura}}/{self.orcamento} | {e.icone('🏆')}melhor "
            f"{e.nota(self.melhor.nota, NEGRITO)} ({formatar_genes(self.melhor.genes)}) | "
            f"{e.icone('✅')}válidos {e.pintar(f'{validas.size}/{len(grupo)}', cor_validos)} | "
            f"{e.icone('📊')}média {media} | {e.icone('⏱')}{tempo:.1f} s{recorde}")
        self.melhor_no_resumo = self.melhor.nota
        self.inicio_bloco = time.perf_counter()
        self.lote = []

    # Fim da busca ----------------------------------------------------------

    def conferido(self, posicao: int, total: int, genes: dict, ajuste: float,
                  media: float, minimo: float):
        """Uma linha da etapa das sementes reservadas."""
        e = self.estilo
        aviso = ""
        if not math.isfinite(minimo):
            aviso = " " + e.icone("⚠️") + e.pintar("frágil: cortado em seed nova", VERMELHO)
        self.escrever(f"  {posicao:>2}/{total} {formatar_genes(genes)}: ajuste {e.nota(ajuste)}, "
                      f"reservadas {e.nota(media, NEGRITO)} (mín {e.nota(minimo)}){aviso}")

    def tabela_melhores(self, lista: list[dict], nomes: list[str], reservadas: int):
        """A lista final dos melhores parâmetros; os 3 primeiros ganham medalha."""
        e = self.estilo
        medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}
        self.escrever()
        self.escrever(e.icone("🏆") + e.pintar(
            f"{len(lista)} melhores parâmetros (nota nas sementes de ajuste e média e "
            f"mínimo nas {reservadas} reservadas):", NEGRITO))
        if not lista:
            self.escrever(e.pintar("  nenhum: todos os candidatos foram cortados", VERMELHO))
            return
        # Com emoji, a medalha ocupa a coluna do número nos 3 primeiros (2 de largura + espaço).
        self.escrever(e.pintar(f"{'#':>3} " + " ".join(f"{n:>15}" for n in nomes)
                               + f" {'iteracoes':>9} {'nota ajuste':>11} {'reservadas':>10} "
                               f"{'mín':>7}", NEGRITO))
        for item in lista:
            posicao = item["posicao"]
            if e.emojis and posicao in medalhas:
                coluna = f"{medalhas[posicao]} "
            else:
                coluna = f"{posicao:>3}"
            valores = " ".join(f"{item['genes'][n]:>15.4g}" for n in nomes)
            linha_genes = f"{valores} {item['iteracoes']:>9}"
            if posicao == 1:
                linha_genes = e.pintar(linha_genes, NEGRITO)
            self.escrever(f"{coluna} {linha_genes} "
                          f"{self._nota_alinhada(item['nota_ajuste'], 11)} "
                          f"{self._nota_alinhada(item['nota_reservada_media'], 10, NEGRITO)} "
                          f"{self._nota_alinhada(item['nota_reservada_min'], 7)}")

    def _nota_alinhada(self, nota: float, largura: int, *codigos: str) -> str:
        # Alinha pelo texto visível: os códigos de cor não aparecem na tela.
        return " " * max(largura - len(formatar_nota(nota)), 0) + self.estilo.nota(nota, *codigos)

    def referencias(self, copia: float, teto: float, destino: str):
        e = self.estilo
        self.escrever()
        self.escrever(f"{e.icone('📊')}referências: cópia pura {e.nota(copia)}; "
                      f"teto trivial {e.nota(teto)}")
        self.escrever(f"{e.icone('📁')}gravado em {e.pintar(destino, CIANO)}")
