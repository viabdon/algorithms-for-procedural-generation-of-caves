"""Roda o ajuste do CA no Elaphes (GA ou busca aleatória) e grava o resultado.

    uv run python -m cavegen.optimization.genetic.executar                  # GA
    uv run python -m cavegen.optimization.genetic.executar --metodo aleatoria
    uv run python -m cavegen.optimization.genetic.executar --orcamento 100 --seed 2

Antes, gere o alvo com a ferramenta do SDF (uma vez):

    uv run python -m tools.sdf.sdf --limiar -3 --log 1

Cada execução grava results/ga_NNN.npz ao lado deste arquivo, com a
configuração inteira, todas as avaliações, a nota do campeão nas sementes de
ajuste e nas reservadas e a nota da cópia pura. O consumo de recursos da busca
inteira vai para a planilha do track_resources.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.pesos import RAIZ_DO_PROJETO, SDF_ELAPHES, caminho_legivel
from cavegen.generators.cellular_automata.storage import build_path, next_id
from cavegen.optimization.genetic.algoritmo import (
    ConfiguracaoGA,
    ResultadoBusca,
    busca_aleatoria,
    evoluir,
)
from cavegen.optimization.genetic.aptidao import Alvo, Cortes, nota_da_copia_pura
from cavegen.optimization.genetic.ca import BORDA, GENES_CA, MAX_ITERACOES, AvaliadorCA
from cavegen.profiling.resource_tracker import track_resources

ALVO_ELAPHES = (RAIZ_DO_PROJETO / "tools" / "sdf" / "npz"
                / "elaphes_surface_64_sdf_limiar-3_log1.npz")
RESULTS_DIR = Path(__file__).resolve().parent / "results"
PREFIXO = "ga"
# Sementes de ajuste (a busca vê) e reservadas (só o campeão, no fim).
SEMENTES_AJUSTE = (1, 2, 3)
SEMENTES_RESERVADAS = tuple(range(101, 111))

def carregar_campo(caminho: Path) -> tuple[np.ndarray, dict]:
    """Lê o 'sdf' de um npz do tools/sdf e os campos que descrevem a manipulação."""
    with np.load(caminho) as arquivo:
        campo = arquivo["sdf"].astype(np.float32)
        info = {"origem": caminho_legivel(Path(caminho)),
                "convencao": str(arquivo["convencao"]) if "convencao" in arquivo.files else "",
                "limiar": float(arquivo["limiar"]) if "limiar" in arquivo.files else 0.0,
                "escala_log": (float(arquivo["escala_log"])
                               if "escala_log" in arquivo.files else None)}
    return campo, info

def rotulo(argumentos: dict) -> str:
    return (f"{argumentos['metodo']} orcamento={argumentos['config'].orcamento} "
            f"seed={argumentos['seed']}")

@track_resources(label=rotulo)
def buscar(metodo: str, avaliador: AvaliadorCA, config: ConfiguracaoGA, seed: int) -> ResultadoBusca:
    if metodo == "genetico":
        return evoluir(GENES_CA, avaliador, config, seed)
    return busca_aleatoria(GENES_CA, avaliador, config.orcamento, seed)

def gravar(resultado: ResultadoBusca, extras: dict, directory: Path = RESULTS_DIR) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destino = build_path(directory, PREFIXO, next_id(directory, PREFIXO))
    nomes = [gene.nome for gene in GENES_CA]
    avaliacoes = resultado.avaliacoes
    np.savez_compressed(
        destino,
        metodo=resultado.metodo,
        genes_nomes=np.array(nomes),
        genes=np.array([[a.genes[n] for n in nomes] for a in avaliacoes], dtype=np.float64),
        notas=np.array([a.nota for a in avaliacoes]),
        iteracoes=np.array([a.detalhes["iteracoes"] for a in avaliacoes]),
        geracao=np.array([a.geracao for a in avaliacoes]),
        melhor_acumulado=resultado.melhor_acumulado(),
        reaproveitadas=resultado.reaproveitadas,
        **{nome: np.array(json.dumps(valor, ensure_ascii=False)) for nome, valor in extras.items()},
    )
    return destino

def main(argv=None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metodo", choices=("genetico", "aleatoria"), default="genetico")
    parser.add_argument("--orcamento", type=int, default=ConfiguracaoGA.orcamento)
    parser.add_argument("--populacao", type=int, default=ConfiguracaoGA.tamanho_populacao)
    parser.add_argument("--seed", type=int, default=0, help="semente da busca (não do CA)")
    parser.add_argument("--peso", type=Path, default=SDF_ELAPHES)
    parser.add_argument("--alvo", type=Path, default=ALVO_ELAPHES)
    parser.add_argument("--saida", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    for caminho, comando in ((args.peso, "uv run python -m tools.sdf.sdf"),
                             (args.alvo, "uv run python -m tools.sdf.sdf --limiar -3 --log 1")):
        if not Path(caminho).exists():
            parser.error(f"{caminho} não existe. Gere com: {comando}")

    sdf_base, info_peso = carregar_campo(args.peso)
    campo_alvo, info_alvo = carregar_campo(args.alvo)
    alvo, cortes = Alvo(campo_alvo), Cortes()
    config = ConfiguracaoGA(tamanho_populacao=args.populacao, orcamento=args.orcamento)
    avaliador = AvaliadorCA(sdf_base, alvo, SEMENTES_AJUSTE, MAX_ITERACOES, cortes)

    resultado = buscar(args.metodo, avaliador, config, args.seed)
    campeao = resultado.melhor
    reservadas = avaliador.nota_com_iteracoes(campeao.genes, campeao.detalhes["iteracoes"],
                                              SEMENTES_RESERVADAS)
    copia = nota_da_copia_pura(sdf_base, alvo)

    extras = {
        "config": asdict(config), "seed": args.seed,
        "genes_limites": [g.como_dict() for g in GENES_CA],
        "cortes": cortes.como_dict(), "faixa_vazio": list(alvo.faixa(cortes)),
        "max_iteracoes": MAX_ITERACOES, "borda": BORDA.value,
        "sementes_ajuste": list(SEMENTES_AJUSTE),
        "sementes_reservadas": list(SEMENTES_RESERVADAS),
        "peso": info_peso, "alvo": info_alvo, "referencia_alvo": alvo.referencia,
        "campeao": {"genes": campeao.genes, "nota_ajuste": campeao.nota,
                    "iteracoes": campeao.detalhes["iteracoes"], "ordem": campeao.ordem},
        "notas_reservadas": reservadas.tolist(), "nota_reservada_media": float(reservadas.mean()),
        "nota_copia_pura": copia,
    }
    destino = gravar(resultado, extras, args.saida)

    print(f"{resultado.metodo}: {len(resultado.avaliacoes)} avaliações "
          f"({resultado.reaproveitadas} repetidas, sem refazer o CA)")
    print(f"campeão {campeao.genes} com {campeao.detalhes['iteracoes']} iterações")
    print(f"nota nas sementes de ajuste {campeao.nota:+.3f}, nas reservadas "
          f"{reservadas.mean():+.3f} (mín {reservadas.min():+.3f}); cópia pura {copia:+.3f}")
    print(f"gravado em {caminho_legivel(destino)}")
    return destino

if __name__ == "__main__":
    main()
