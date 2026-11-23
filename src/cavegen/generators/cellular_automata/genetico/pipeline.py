"""O fluxo inteiro do GA do CA, etapa por etapa.

    1_entrada/     as grades de superfície das cavernas reais, 64³ (você põe aqui)
        │  etapa 2, campos.py: o SDF de cada grade, com log x1 e sem limiar
    2_campos/      um campo por caverna: o peso do CA e o alvo da nota
        │  etapa 3, busca.py: o GA (ou a busca aleatória de controle) nos campos
        │  etapa 4, resultados.py: a lista legível e as figuras
    3_resultados/  ga_NNN.npz, ga_NNN_melhores.md e ga_NNN_relatorio.html

    uv run python -m cavegen.generators.cellular_automata.genetico.pipeline
    uv run python -m cavegen.generators.cellular_automata.genetico.pipeline --cavernas elaphes
    uv run python -m cavegen.generators.cellular_automata.genetico.pipeline --orcamento 40 --forcar

Sem --cavernas, usa todas as cavernas da entrada. Os campos que faltam ou
estão desatualizados são refeitos antes da busca, e os em dia são
reaproveitados (--forcar refaz todos). Cada etapa também roda sozinha, pelo
próprio módulo (campos, busca, resultados).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cavegen.generators.cellular_automata.genetico import busca, campos, resultados
from cavegen.generators.cellular_automata.genetico.algoritmo import ConfiguracaoGA


def main(argv=None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cavernas", nargs="+", metavar="CAVERNA",
                        help="nomes das cavernas da entrada (padrão: todas)")
    parser.add_argument("--forcar", action="store_true",
                        help="refaz todos os campos, mesmo os em dia")
    parser.add_argument("--metodo", choices=("genetico", "aleatoria"), default="genetico",
                        help="genetico: o algoritmo genético; aleatoria: a busca aleatória de "
                             "controle, que só sorteia (sem seleção nem cruzamento)")
    parser.add_argument("--orcamento", type=int, default=ConfiguracaoGA.orcamento)
    parser.add_argument("--populacao", type=int, default=ConfiguracaoGA.tamanho_populacao)
    parser.add_argument("--seed", type=int, default=0, help="semente da busca (não do CA)")
    parser.add_argument("--top", type=int, default=busca.TOP_PADRAO,
                        help="quantos melhores parâmetros listar no fim")
    parser.add_argument("--entrada", type=Path, default=campos.ENTRADA_DIR)
    parser.add_argument("--campos", type=Path, default=campos.CAMPOS_DIR)
    parser.add_argument("--saida", type=Path, default=busca.RESULTS_DIR,
                        help="pasta dos resultados")
    args = parser.parse_args(argv)

    print("\n== Etapa 2: campos (SDF com log x1, sem limiar) ==")
    try:
        feitos = campos.preparar(args.cavernas, args.forcar, args.entrada, args.campos)
    except ValueError as erro:
        parser.error(str(erro))

    print("\n== Etapa 3: busca ==")
    destino = busca.main(["--cavernas", *feitos, "--metodo", args.metodo,
                          "--orcamento", str(args.orcamento), "--populacao", str(args.populacao),
                          "--seed", str(args.seed), "--top", str(args.top),
                          "--entrada", str(args.entrada), "--campos", str(args.campos),
                          "--saida", str(args.saida)])

    print("\n== Etapa 4: resultados ==")
    resultados.gerar(destino, imprimir=False)
    return destino

if __name__ == "__main__":
    main()
