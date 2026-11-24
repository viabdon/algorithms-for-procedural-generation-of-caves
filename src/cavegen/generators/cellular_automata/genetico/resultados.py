"""Etapa 4 do pipeline do GA: os resultados de uma execução, para ler sem Python.

    3_resultados/ga_NNN.npz             registro completo da execução (gravado na etapa 3)
    3_resultados/ga_NNN_melhores.md     os N melhores parâmetros, numa tabela de texto
    3_resultados/ga_NNN_relatorio.html  as figuras e a mesma tabela, no navegador

Os dois relatórios saem do npz, e a tabela dos dois sai de uma função só
(tabela_dos_melhores). Esta etapa também imprime o resumo da execução no
terminal, então dá para rever uma execução antiga sem escrever código:

    uv run python -m cavegen.generators.cellular_automata.genetico.resultados          # a última
    uv run python -m cavegen.generators.cellular_automata.genetico.resultados ga_012
    uv run python -m cavegen.generators.cellular_automata.genetico.resultados 12 --comparar 13

--comparar põe a curva da melhor nota de outra execução (a busca aleatória de
controle, por exemplo) na mesma figura.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.genetico.busca import PREFIXO, RESULTS_DIR
from cavegen.generators.cellular_automata.genetico.painel import (
    Painel,
    descrever_vazio,
    formatar_nota,
)
from cavegen.generators.cellular_automata.pesos import caminho_legivel
from cavegen.generators.cellular_automata.storage import build_path, used_ids

# Campos do npz que são arrays; todo o resto é texto JSON.
ARRAYS = ("metodo", "genes_nomes", "genes", "notas", "iteracoes", "geracao", "melhor_acumulado",
          "reaproveitadas")
METODOS = {"genetico": "algoritmo genético", "aleatoria": "busca aleatória de controle"}

def localizar(execucao: str | None, pasta: Path = RESULTS_DIR) -> Path:
    """
        O npz de uma execução: um caminho, um nome (ga_012) ou um número (12);
        sem nada, a última gravada na pasta.
    """
    if execucao is None:
        usados = used_ids(pasta, PREFIXO)
        if not usados:
            raise FileNotFoundError(f"Nenhuma execução em {pasta}.")
        return build_path(pasta, PREFIXO, max(usados))
    if execucao.isdigit():
        return build_path(pasta, PREFIXO, int(execucao))
    caminho = Path(execucao)
    if caminho.suffix != ".npz":
        return Path(pasta) / f"{execucao}.npz"
    # ga_012.npz sem pasta: procura em --pasta antes da pasta atual.
    if not caminho.exists() and caminho.parent == Path(".") and (Path(pasta) / caminho).exists():
        return Path(pasta) / caminho
    return caminho

def ler_execucao(caminho: Path) -> dict:
    """
        Lê o npz de uma execução num dict: os arrays como arrays, os campos JSON
        já convertidos, e "arquivo" e "nome" (ga_012). Erro (ValueError) para as
        execuções de antes de 22/11/2026, que têm outro formato.
    """
    caminho = Path(caminho)
    with np.load(caminho) as r:
        if "cavernas" not in r.files or "criterio_ranking" not in r.files:
            raise ValueError(f"{caminho.name} é de antes de 22/11/2026 (alvo com limiar -3, só o "
                             "Elaphes, sem a nota por caverna): os relatórios não leem esse "
                             "formato.")
        dados = {}
        for nome in r.files:
            if nome == "metodo":
                dados[nome] = str(r[nome])
            elif nome in ARRAYS:
                dados[nome] = r[nome]
            else:
                dados[nome] = json.loads(str(r[nome]))
    dados["arquivo"], dados["nome"] = caminho, caminho.stem
    return dados

def nomes_das_cavernas(execucao: dict) -> list[str]:
    return [c["nome"] for c in execucao["cavernas"]]

def avisos_de_comparacao(execucao: dict, outras: list[dict]) -> list[str]:
    """
        Uma frase por execução de --comparar que não é comparável com esta:
        para a curva da melhor nota ser uma comparação justa (o GA contra a
        busca aleatória), as duas precisam das mesmas cavernas e campos, do
        mesmo orçamento, das mesmas seeds de ajuste, da mesma faixa de vazio,
        das mesmas iterações e das mesmas faixas dos genes.
    """
    def cavernas(e):
        return [(c["nome"], c["sha256"]) for c in e["cavernas"]]

    criterios = (("cavernas ou campos", cavernas),
                 ("orçamento", lambda e: e["config"]["orcamento"]),
                 ("seeds de ajuste", lambda e: e["sementes_ajuste"]),
                 ("faixa de vazio", lambda e: e["cortes"]),
                 # As execuções de antes de 22/11/2026 não gravaram: alvo igual ao peso.
                 ("acréscimo do alvo", lambda e: e.get("acrescimo_alvo", 0.0)),
                 ("iterações", lambda e: e["max_iteracoes"]),
                 ("faixas dos genes", lambda e: e["genes_limites"]))
    avisos = []
    for outra in outras:
        diferentes = [nome for nome, valor in criterios if valor(outra) != valor(execucao)]
        if diferentes:
            avisos.append(f"{outra['nome']} não é comparável com {execucao['nome']}: difere em "
                          f"{', '.join(diferentes)}.")
    return avisos

def tabela_dos_melhores(execucao: dict) -> tuple[list[str], list[list]]:
    """
        As colunas e as linhas da lista dos melhores, com os valores crus (sem
        formatar). É a mesma tabela no Markdown e no HTML.
        Por linha: posição, genes, iterações, a nota média entre as cavernas (o
        critério da ordem), a nota de cada caverna, o mínimo e o desvio entre
        as cavernas, e nas seeds reservadas a média e a pior seed.
    """
    genes = [str(n) for n in execucao["genes_nomes"]]
    cavernas = nomes_das_cavernas(execucao)
    colunas = (["#", *genes, "iterações", "nota média", *cavernas, "mín", "desvio",
                "reservadas", "pior seed"])
    linhas = []
    for item in execucao["melhores"]:
        ajuste, reservadas = item["ajuste"], item["reservadas"]
        linhas.append([item["posicao"], *(item["genes"][g] for g in genes), item["iteracoes"],
                       item["nota_ajuste"], *(ajuste["por_caverna"][c] for c in cavernas),
                       ajuste["min"], ajuste["desvio"], reservadas["media"],
                       reservadas["pior_semente"]])
    return colunas, linhas

def formatar(valor, coluna: str) -> str:
    """Texto de uma célula: notas com sinal, 'cortado' para -inf, '-' sem desvio."""
    if isinstance(valor, (bool, int)):
        return str(valor)
    if coluna == "desvio":
        return f"{valor:.3f}" if math.isfinite(valor) else "-"
    if coluna == "chance_inicial":
        return f"{valor:.4g}"
    return formatar_nota(valor)

def linhas_do_cabecalho(execucao: dict) -> list[str]:
    """O que é a execução, em frases curtas: método, orçamento, cavernas, seeds, ordem."""
    config = execucao["config"]
    metodo = METODOS.get(execucao["metodo"], execucao["metodo"])
    cavernas = ", ".join(f"{c['nome']} ({c['referencia_alvo']} voxels positivos; "
                         f"{descrever_vazio(*c['faixa_vazio'])})"
                         for c in execucao["cavernas"])
    copias = ", ".join(f"{nome} {formatar_nota(n)}"
                       for nome, n in execucao["nota_copia_pura"].items())
    ajuste, reservadas = execucao["sementes_ajuste"], execucao["sementes_reservadas"]
    repetidos = int(execucao["reaproveitadas"])
    return [f"método: {metodo}, seed da busca {execucao['seed']}",
            (f"orçamento: {config['orcamento']} candidatos ({repetidos} repetidos, sem rodar o "
             "CA de novo)"),
            f"cavernas: {cavernas}",
            (f"seeds: {len(ajuste)} de ajuste ({ajuste[0]} a {ajuste[-1]}), {len(reservadas)} "
             f"reservadas ({reservadas[0]} a {reservadas[-1]}); {execucao['max_iteracoes']} "
             "iterações sempre"),
            f"ordem: {execucao['criterio_ranking']}",
            descrever_alvo(execucao),
            f"referência: cópia pura {copias}" + regua_negativa(execucao)]

def descrever_alvo(execucao: dict) -> str:
    """O alvo da nota: o campo do peso, com ou sem o acréscimo."""
    acrescimo = execucao.get("acrescimo_alvo", 0.0)
    if not acrescimo:
        return "alvo: o próprio campo do peso (a cópia pura dá a nota máxima, 1)"
    return (f"alvo: o campo do peso mais {acrescimo:g} em todo voxel (a nota máxima, 1, é "
            "vazio exatamente onde o alvo é positivo; a cópia pura fica abaixo dela)")

def regua_negativa(execucao: dict) -> str:
    """
        A nota da grade cheia de cada caverna, para ler as notas negativas (as
        execuções de antes de 22/11/2026 não a gravaram).
    """
    cheias = [(c["nome"], c["nota_grade_cheia"]) for c in execucao["cavernas"]
              if "nota_grade_cheia" in c]
    if not cheias:
        return ""
    return "; grade cheia " + ", ".join(f"{nome} {formatar_nota(n)}" for nome, n in cheias)

def legenda_colunas(execucao: dict) -> str:
    """
        O que cada coluna quer dizer. O que é `cortado` depende da faixa da
        execução: as de antes da saída do limite de cima (22/11/2026) têm os dois.
    """
    sem_maximo = execucao["cortes"].get("fator_maximo") is None
    cortado = ("vazio abaixo do mínimo aceito" if sem_maximo
               else "vazio fora da faixa aceita (abaixo do mínimo ou acima do máximo)")
    return ("Colunas: `nota média` é a média entre as cavernas nas seeds de ajuste (o critério "
            "da ordem); cada caverna tem a sua coluna; `mín` e `desvio` são entre as cavernas; "
            "`reservadas` é a média nas seeds reservadas e `pior seed` a menor nota entre elas. "
            f"`cortado` quer dizer {cortado} (nota -inf). `iterações` é o passo de maior nota "
            "média: 1 é a nota do primeiro passo a partir do ruído inicial, e uma iteração "
            "escolhida antes da 40 pode ser só um passo de transição (veja a trajetória no "
            "relatório).")

def escala_das_notas(execucao: dict) -> str:
    """Como ler notas que vão de +1 a centenas ou milhares negativos, com a régua gravada."""
    if any("nota_grade_cheia" in c for c in execucao["cavernas"]):
        regua = "(o valor de cada caverna está no cabeçalho)"
    else:
        regua = "(esta execução, de antes de 22/11/2026, não gravou o valor de cada caverna)"
    return ("Como ler a nota: +1 é o máximo (vazio exatamente onde o alvo é positivo), 0 é "
            "a grade sem vazio, e a grade toda vazia dá a nota mais baixa: perto de -4000 com "
            "o alvo log x1 e de centenas negativas com o log x2 e o acréscimo do alvo "
            f"{regua}. Qualquer nota abaixo de -1 já tem mais vazio fora da forma do que a "
            "forma inteira vale. A média, o mínimo e o desvio entre as cavernas estão na mesma "
            "unidade: um desvio de 30 numa nota de -400 é pequeno; o mesmo 30 numa nota perto "
            "de 0 diria que uma caverna vai bem e a outra não.")
COMO_TESTAR_NO_CA = (
    "Para testar uma linha no CA: importe o campo da caverna como peso "
    "(`uv run python -m cavegen.generators.cellular_automata.pesos <campo em 2_campos/>`) e, no "
    "menu do CA (`uv run poe menu-ca`), use a `chance_inicial`, a `sensibilidade`, as "
    "`iterações`, a borda `nearest` e esse peso no modo completo. O menu sorteia a matriz "
    "inicial sem seed fixa, então a caverna sai diferente das seeds de ajuste: a nota da tabela "
    "é a média de 5 grades.")

def markdown_dos_melhores(execucao: dict) -> str:
    """A lista dos melhores num Markdown que se lê em qualquer editor de texto."""
    colunas, linhas = tabela_dos_melhores(execucao)
    texto = [f"# {execucao['nome']}: os {len(linhas)} melhores parâmetros", ""]
    texto += [f"- {linha}" for linha in linhas_do_cabecalho(execucao)]
    texto += [f"- gerado de `{caminho_legivel(execucao['arquivo'])}`", ""]
    if not linhas:
        texto.append("Nenhum: todos os candidatos foram cortados pela faixa de vazio.")
    else:
        texto.append("| " + " | ".join(colunas) + " |")
        texto.append("|" + "|".join("---:" for _ in colunas) + "|")
        for linha in linhas:
            celulas = (formatar(v, c) for v, c in zip(linha, colunas))
            texto.append("| " + " | ".join(celulas) + " |")
    texto += ["", legenda_colunas(execucao), "", escala_das_notas(execucao), "",
              COMO_TESTAR_NO_CA, ""]
    return "\n".join(texto)

def gravar_melhores(execucao: dict, destino: Path | None = None) -> Path:
    destino = Path(destino or execucao["arquivo"].with_name(f"{execucao['nome']}_melhores.md"))
    destino.write_text(markdown_dos_melhores(execucao), encoding="utf-8")
    return destino

def resumir(execucao: dict, painel: Painel):
    """O resumo da execução no terminal, com a mesma tabela que a busca imprime no fim."""
    painel.escrever(painel.estilo.pintar(f"{execucao['nome']}", "1"))
    for linha in linhas_do_cabecalho(execucao):
        painel.escrever(f"  {linha}")
    painel.tabela_melhores(execucao["melhores"], [str(n) for n in execucao["genes_nomes"]],
                           nomes_das_cavernas(execucao), len(execucao["sementes_ajuste"]),
                           len(execucao["sementes_reservadas"]))

def gerar(caminho: Path, comparar: list[Path] | None = None, imprimir: bool = True,
          painel: Painel | None = None) -> tuple[Path, Path]:
    """
        Grava o Markdown e o HTML de uma execução e devolve os dois caminhos.
        comparar: outras execuções cuja curva da melhor nota entra na mesma figura.
        imprimir: mostra o resumo e a tabela (o pipeline desliga, porque a busca
                  acabou de mostrar).
    """
    # Importado aqui: as figuras puxam o plotly, e ler o npz não precisa dele.
    from cavegen.generators.cellular_automata.genetico.figuras import gravar_relatorio

    execucao = ler_execucao(caminho)
    outras = [ler_execucao(c) for c in comparar or []]
    painel = painel or Painel(1)
    if imprimir:
        resumir(execucao, painel)
    for aviso in avisos_de_comparacao(execucao, outras):
        painel.escrever(f"  aviso: {aviso}")
    markdown = gravar_melhores(execucao)
    html = gravar_relatorio(execucao, outras)
    painel.escrever()
    painel.escrever(f"  lista dos melhores  {caminho_legivel(markdown)}")
    painel.escrever(f"  relatório           {caminho_legivel(html)}  (abra no navegador)")
    return markdown, html

def main(argv=None) -> tuple[Path, Path]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("execucao", nargs="?",
                        help="ga_NNN, o número ou o caminho do npz (padrão: a última)")
    parser.add_argument("--comparar", nargs="+", default=[], metavar="EXECUCAO",
                        help="execuções cuja curva da melhor nota entra na mesma figura")
    parser.add_argument("--pasta", type=Path, default=RESULTS_DIR,
                        help="onde procurar as execuções")
    args = parser.parse_args(argv)
    try:
        caminho = localizar(args.execucao, args.pasta)
        comparar = [localizar(c, args.pasta) for c in args.comparar]
        for c in (caminho, *comparar):
            if not c.exists():
                raise FileNotFoundError(f"{c} não existe.")
        return gerar(caminho, comparar)
    except (FileNotFoundError, ValueError) as erro:
        parser.error(str(erro))

if __name__ == "__main__":
    main()
