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

def descrever_vazio(minimo: float, maximo: float | None) -> str:
    """A faixa de vazio aceita em texto; maximo None ou inf = sem limite de cima."""
    if maximo is None or not math.isfinite(maximo):
        return f"vazio aceito a partir de {minimo:.0f}"
    return f"vazio aceito de {minimo:.0f} a {maximo:.0f}"

def formatar_nota(nota: float) -> str:
    return f"{nota:+.3f}" if math.isfinite(nota) else "cortado"

def formatar_desvio(desvio: float) -> str:
    # Sem desvio (NaN) quando alguma caverna foi cortada.
    return f"{desvio:.3f}" if math.isfinite(desvio) else "-"

def motivos_do_corte(detalhes: dict) -> list[str]:
    """
        Onde o vazio terminou nas sementes que acabaram fora da faixa
        (vazio_demais, vazio_de_menos), sem repetir. Um candidato cortado tem
        pelo menos uma semente assim: senão a última iteração teria nota.
    """
    fins = {fim for caverna in detalhes.get("cavernas", {}).values()
            for fim in caverna.get("fim", [])}
    return sorted(fins - {"na_faixa"})

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

    def caverna(self, nome: str, origem: str, forma: tuple, campo_min: float, campo_max: float,
                positivos: int, faixa: tuple[float, float], copia: float,
                aviso: str | None = None, cheia: float | None = None):
        """
            Duas linhas da etapa de carga: de onde veio o campo da caverna, a
            grade, os voxels positivos do alvo, a faixa de vazio aceita, a
            cópia pura (a nota máxima, 1) e a grade cheia (a régua das notas
            negativas). aviso: uma terceira linha, em amarelo, se vier.
        """
        e = self.estilo
        grade = "x".join(str(lado) for lado in forma)
        self.escrever(f"  {e.pintar(nome, NEGRITO)}  {origem}")
        self.escrever(f"      grade {grade}, campo de {campo_min:+.2f} a {campo_max:+.2f}, "
                      f"{positivos} voxels positivos; {descrever_vazio(*faixa)}")
        regua = f"      cópia pura {e.nota(copia)}"
        if cheia is not None:
            regua += f", grade cheia {e.nota(cheia)}"
        self.escrever(regua)
        if aviso:
            self.escrever("      " + e.icone("⚠️") + e.pintar(aviso, AMARELO))

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
            motivos = motivos_do_corte(avaliacao.detalhes)
            puro = "cortado" + (f" (no fim: {', '.join(motivos)})" if motivos else "")
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
        # Mediana, não média: as notas vão de 1 a cerca de -4000, e um candidato
        # que enche a grade puxaria a média da geração inteira para lá.
        mediana = e.nota(float(np.median(validas))) if validas.size else "  -   "
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
            f"{e.icone('📊')}mediana {mediana} | {e.icone('⏱')}{tempo:.1f} s{recorde}")
        self.melhor_no_resumo = self.melhor.nota
        self.inicio_bloco = time.perf_counter()
        self.lote = []

    # Fim da busca ----------------------------------------------------------

    def conferido(self, posicao: int, total: int, genes: dict, ajuste: float, reservadas: dict):
        """
            Uma linha da etapa das sementes reservadas.
            ajuste: a nota da busca (média entre as cavernas nas sementes de ajuste).
            reservadas: o que AvaliadorCA.conferir devolve (media, por_caverna,
                        pior_semente...).
        """
        e = self.estilo
        aviso = ""
        if not math.isfinite(reservadas["pior_semente"]):
            aviso = " " + e.icone("⚠️") + e.pintar("frágil: cortado em seed nova", VERMELHO)
        por_caverna = ""
        if len(reservadas["por_caverna"]) > 1:
            por_caverna = " (" + ", ".join(f"{nome} {e.nota(nota)}" for nome, nota
                                           in reservadas["por_caverna"].items()) + ")"
        self.escrever(f"  {posicao:>2}/{total} {formatar_genes(genes)}: ajuste {e.nota(ajuste)}, "
                      f"reservadas {e.nota(reservadas['media'], NEGRITO)}{por_caverna}, "
                      f"pior seed {e.nota(reservadas['pior_semente'])}{aviso}")

    def tabela_melhores(self, lista: list[dict], genes: list[str], cavernas: list[str],
                        ajuste: int, reservadas: int):
        """
            A lista final dos melhores parâmetros; os 3 primeiros ganham medalha.
            Com uma caverna, a nota de ajuste é a média das sementes dela. Com
            várias, é a média entre as cavernas (o critério da ordem), seguida do
            mínimo, do máximo e do desvio entre elas e da nota de cada uma.
            genes, cavernas: nomes, na ordem das colunas.
            ajuste, reservadas: quantas sementes de cada tipo, para o título.
        """
        e = self.estilo
        medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}
        varias = len(cavernas) > 1
        if varias:
            titulo = (f"{len(lista)} melhores parâmetros, ordenados pela média entre as "
                      f"{len(cavernas)} cavernas nas {ajuste} seeds de ajuste:")
            legenda = ("mín, máx e desvio: entre as cavernas; reservadas: média entre as "
                       f"cavernas nas {reservadas} seeds reservadas; pior seed: a menor nota "
                       "entre elas")
        else:
            titulo = (f"{len(lista)} melhores parâmetros, ordenados pela nota de ajuste "
                      f"(média das {ajuste} seeds de ajuste em {cavernas[0]}):")
            legenda = (f"reservadas: média nas {reservadas} seeds reservadas; pior seed: a "
                       "menor nota entre elas")
        self.escrever()
        self.escrever(e.icone("🏆") + e.pintar(titulo, NEGRITO))
        self.escrever(e.pintar(f"  {legenda}", FRACO))
        if not lista:
            self.escrever(e.pintar("  nenhum: todos os candidatos foram cortados", VERMELHO))
            return

        # (título, largura, valor do item, é desvio, códigos de estilo)
        colunas = [("média ajuste" if varias else "nota ajuste", 12 if varias else 11,
                    lambda item: item["nota_ajuste"], False, ())]
        if varias:
            colunas += [("mín", 7, lambda item: item["ajuste"]["min"], False, ()),
                        ("máx", 7, lambda item: item["ajuste"]["max"], False, ()),
                        ("desvio", 6, lambda item: item["ajuste"]["desvio"], True, ())]
            colunas += [(nome, max(len(nome), 7),
                         lambda item, nome=nome: item["ajuste"]["por_caverna"][nome], False, ())
                        for nome in cavernas]
        colunas += [("reservadas", 10, lambda item: item["nota_reservada_media"], False,
                     (NEGRITO,)),
                    ("pior seed", 9, lambda item: item["reservadas"]["pior_semente"], False, ())]
        # A nota vai de 1 a cerca de -4000: cada coluna cresce até caber o seu
        # maior número, para a tabela não desalinhar.
        colunas = [(titulo, max(largura, *(len(formatar_desvio(valor(item)) if desvio
                                               else formatar_nota(valor(item)))
                                           for item in lista)), valor, desvio, codigos)
                   for titulo, largura, valor, desvio, codigos in colunas]

        # Com emoji, a medalha ocupa a coluna do número nos 3 primeiros (2 de largura + espaço).
        self.escrever(e.pintar(f"{'#':>3} " + " ".join(f"{n:>15}" for n in genes)
                               + f" {'iteracoes':>9}"
                               + "".join(f" {titulo:>{largura}}"
                                         for titulo, largura, *_ in colunas), NEGRITO))
        for item in lista:
            posicao = item["posicao"]
            if e.emojis and posicao in medalhas:
                coluna = f"{medalhas[posicao]} "
            else:
                coluna = f"{posicao:>3}"
            valores = " ".join(f"{item['genes'][n]:>15.4g}" for n in genes)
            linha_genes = f"{valores} {item['iteracoes']:>9}"
            if posicao == 1:
                linha_genes = e.pintar(linha_genes, NEGRITO)
            celulas = "".join(
                " " + (f"{formatar_desvio(valor(item)):>{largura}}" if desvio
                       else self._nota_alinhada(valor(item), largura, *codigos))
                for _, largura, valor, desvio, codigos in colunas)
            self.escrever(f"{coluna} {linha_genes}{celulas}")

    def _nota_alinhada(self, nota: float, largura: int, *codigos: str) -> str:
        # Alinha pelo texto visível: os códigos de cor não aparecem na tela.
        return " " * max(largura - len(formatar_nota(nota)), 0) + self.estilo.nota(nota, *codigos)

    def referencias(self, copias: dict[str, float], destino: str,
                    cheias: dict[str, float] | None = None):
        """
            A nota de referência de cada caverna e onde o resultado foi gravado.
            copias: nota da cópia pura (peso > 0 vira vazio, sem rodar o CA) por
                    caverna; com o alvo igual ao peso, ela é 1.
            cheias: nota da grade toda vazia por caverna, a régua das negativas.
        """
        e = self.estilo
        self.escrever()
        notas = ", ".join(f"{nome} {e.nota(nota)}" for nome, nota in copias.items())
        self.escrever(f"{e.icone('📊')}referência: cópia pura (peso > 0 vira vazio, sem rodar "
                      f"o CA): {notas}")
        if cheias:
            notas = ", ".join(f"{nome} {e.nota(nota)}" for nome, nota in cheias.items())
            self.escrever(f"   grade cheia (tudo vazio): {notas}")
        self.escrever(f"{e.icone('📁')}gravado em {e.pintar(destino, CIANO)}")
