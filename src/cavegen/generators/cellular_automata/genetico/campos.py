"""Etapa 2 do pipeline do GA: o campo de cada caverna da entrada.

    1_entrada/<nome>_surface_64.npz  ->  2_campos/<nome>_surface_64_sdf_log2.npz

O campo é o SDF da grade de superfície comprimido com 2 · ln(1 + |d|) (log de
escala 2, o mesmo `--log 2` usado nos pesos do CA), sem limiar. É um arquivo só
por caverna: ele é o peso que guia o CA, e o alvo da nota é ele mais o
acréscimo do alvo (ca.ACRESCIMO_ALVO). Quem calcula é a ferramenta do SDF
(cavegen.tools.sdf.sdf.gravar_campo); nada do cálculo é refeito aqui.

Um campo é refeito quando falta, quando a grade da entrada mudou (o sha256
dela fica gravado no campo) ou quando a versão do cálculo do SDF mudou
(VERSAO_SDF); senão é reaproveitado. --forcar refaz todos os escolhidos.

    uv run python -m cavegen.generators.cellular_automata.genetico.campos
    uv run python -m cavegen.generators.cellular_automata.genetico.campos --forcar
"""
from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.pesos import caminho_legivel
from cavegen.tools.sdf.sdf import VERSAO_SDF, gravar_campo, nome_do_campo

PASTA = Path(__file__).resolve().parent
ENTRADA_DIR = PASTA / "1_entrada"
CAMPOS_DIR = PASTA / "2_campos"
# O campo do GA: log de escala 2 e nenhum limiar (decisão do Felipe em 22/11/2026:
# o mesmo log x2 dos pesos que ele usa no CA; de 15/11 a 22/11/2026 era x1).
LIMIAR, ESCALA_LOG = 0.0, 2.0
SUFIXO_GRADE = "_surface_64"
SUFIXO_CAMPO = nome_do_campo("", LIMIAR, ESCALA_LOG)  # "_sdf_log2"
COMANDO = "uv run python -m cavegen.generators.cellular_automata.genetico.campos"

def sha256(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()

def nome_da_caverna(caminho: Path) -> str:
    """Rótulo da caverna: o nome do arquivo sem _sdf_log2 e sem _surface_64 (elaphes)."""
    nome = Path(caminho).stem
    for sufixo in (SUFIXO_CAMPO, SUFIXO_GRADE):
        nome = nome.removesuffix(sufixo)
    return nome

def cavernas_da_entrada(entrada: Path = ENTRADA_DIR) -> dict[str, Path]:
    """
        As grades de superfície da pasta de entrada, por nome, em ordem
        alfabética. Cada .npz da pasta é uma caverna.
    """
    grades = sorted(Path(entrada).glob("*.npz"))
    cavernas = {}
    for grade in grades:
        nome = nome_da_caverna(grade)
        if nome in cavernas:
            raise ValueError(f"Duas grades viram a caverna {nome} em {entrada}: "
                             f"{cavernas[nome].name} e {grade.name}.")
        cavernas[nome] = grade
    return cavernas

def escolher(disponiveis: dict[str, Path], nomes: list[str] | None = None) -> dict[str, Path]:
    """
        As cavernas pedidas, na ordem pedida; sem pedido, todas. Nome que não
        está na entrada é erro, com a lista do que há.
    """
    if not disponiveis:
        raise ValueError("A pasta de entrada não tem nenhuma caverna (.npz).")
    if nomes is None:
        return dict(disponiveis)
    faltam = [nome for nome in nomes if nome not in disponiveis]
    if faltam:
        raise ValueError(f"Caverna fora da entrada: {', '.join(faltam)}. Há: "
                         f"{', '.join(disponiveis)}.")
    if len(set(nomes)) != len(nomes):
        raise ValueError(f"Caverna repetida: {nomes}.")
    return {nome: disponiveis[nome] for nome in nomes}

def caminho_do_campo(grade: Path, campos: Path = CAMPOS_DIR) -> Path:
    """Onde a ferramenta do SDF grava o campo do GA dessa grade."""
    return Path(campos) / f"{nome_do_campo(Path(grade).stem, LIMIAR, ESCALA_LOG)}.npz"

def situacao(grade: Path, campo: Path) -> str | None:
    """
        None se o campo está em dia com a grade; senão, o motivo para refazer.
    """
    if not Path(campo).exists():
        return "falta"
    with np.load(campo) as arquivo:
        gravado = {nome: arquivo[nome].item() for nome in
                   ("sha256_entrada", "versao", "limiar", "escala_log") if nome in arquivo.files}
    if gravado.get("limiar") != LIMIAR or gravado.get("escala_log") != ESCALA_LOG:
        return "não é o campo do GA (limiar ou log diferente)"
    if "sha256_entrada" not in gravado or "versao" not in gravado:
        return "não diz de que grade e de que versão veio"
    if gravado["sha256_entrada"] != sha256(grade):
        return "a grade da entrada mudou"
    if gravado["versao"] != VERSAO_SDF:
        return f"o cálculo do SDF mudou (versão {gravado['versao']}, agora {VERSAO_SDF})"
    return None

def preparar(nomes: list[str] | None = None, forcar: bool = False,
             entrada: Path = ENTRADA_DIR, campos: Path = CAMPOS_DIR,
             avisar: Callable[[str], None] = print) -> dict[str, Path]:
    """
        Deixa em dia o campo de cada caverna escolhida e devolve {nome: campo}.
        nomes: cavernas da entrada; None = todas.
        forcar: refaz até os que estão em dia.
        avisar: recebe uma linha por caverna (gerado, refeito ou reaproveitado).
    """
    escolhidas = escolher(cavernas_da_entrada(entrada), nomes)
    feitos = {}
    for nome, grade in escolhidas.items():
        with np.load(grade) as arquivo:
            faltam = {"surface_voxels", "metadata"} - set(arquivo.files)
        if faltam:
            raise ValueError(f"A caverna {nome} ({grade.name}) não é uma grade de superfície: "
                             f"falta {', '.join(sorted(faltam))}. A entrada espera o npz da "
                             "voxelização (surface_voxels, 1 = parede observada, e metadata).")
        campo = caminho_do_campo(grade, campos)
        motivo = situacao(grade, campo)
        if forcar and motivo is None:
            motivo = "forçado"
        if motivo is None:
            avisar(f"  {nome}: reaproveitado ({campo.name})")
        else:
            gravar_campo(grade, LIMIAR, ESCALA_LOG, campos)
            acao = "gerado" if motivo == "falta" else f"refeito: {motivo}"
            avisar(f"  {nome}: {acao} ({campo.name})")
        feitos[nome] = campo
    return feitos

def main(argv=None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cavernas", nargs="+", metavar="CAVERNA",
                        help="nomes das cavernas da entrada (padrão: todas)")
    parser.add_argument("--forcar", action="store_true", help="refaz até os campos em dia")
    parser.add_argument("--entrada", type=Path, default=ENTRADA_DIR)
    parser.add_argument("--campos", type=Path, default=CAMPOS_DIR)
    args = parser.parse_args(argv)
    print(f"Campos (SDF com log x{ESCALA_LOG:g}, sem limiar) de "
          f"{caminho_legivel(args.entrada)}")
    try:
        return preparar(args.cavernas, args.forcar, args.entrada, args.campos)
    except ValueError as erro:
        parser.error(str(erro))

if __name__ == "__main__":
    main()
