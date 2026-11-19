"""Roda o ajuste do CA no Elaphes (GA ou busca aleatória) e grava o resultado.

    uv run python -m cavegen.optimization.genetic.executar                  # GA
    uv run python -m cavegen.optimization.genetic.executar --metodo aleatoria
    uv run python -m cavegen.optimization.genetic.executar --orcamento 100 --seed 2

Antes, gere o peso e o alvo com a ferramenta do SDF (uma vez):

    uv run python -m tools.sdf.sdf --log 1                 # peso: SDF com ln(1 + |d|)
    uv run python -m tools.sdf.sdf --limiar -3 --log 1     # alvo

O peso entra no CA exatamente como está no arquivo, sem escala: o arquivo de
onde ele veio fica gravado no resultado (`peso` e `ambiente`).

No fim, mostra e grava a lista dos melhores parâmetros (--top, padrão 10):
cada combinação uma vez só, com a nota nas sementes de ajuste e nas
reservadas. Cada execução grava results/ga_NNN.npz ao lado deste arquivo, com
a configuração inteira, todas as avaliações, essa lista e a nota da cópia
pura. O consumo de recursos da busca inteira vai para a planilha do
track_resources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import scipy

from cavegen.generators.cellular_automata.pesos import RAIZ_DO_PROJETO, caminho_legivel
from cavegen.generators.cellular_automata.storage import build_path, next_id
from cavegen.optimization.genetic.algoritmo import (
    ConfiguracaoGA,
    ResultadoBusca,
    busca_aleatoria,
    evoluir,
)
from cavegen.optimization.genetic.aptidao import Alvo, Cortes, nota_da_copia_pura
from cavegen.optimization.genetic.ca import BORDA, GENES_CA, MAX_ITERACOES, AvaliadorCA
from cavegen.optimization.genetic.painel import Painel
from cavegen.profiling.resource_tracker import track_resources
from cavegen.sdf.manipulacao import manipular_sdf

NPZ_SDF = RAIZ_DO_PROJETO / "tools" / "sdf" / "npz"
PESO_ELAPHES = NPZ_SDF / "elaphes_surface_64_sdf_log1.npz"
ALVO_ELAPHES = NPZ_SDF / "elaphes_surface_64_sdf_limiar-3_log1.npz"
COMANDO_PESO = "uv run python -m tools.sdf.sdf --log 1"
COMANDO_ALVO = "uv run python -m tools.sdf.sdf --limiar -3 --log 1"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
PREFIXO = "ga"
# Sementes de ajuste (a busca vê) e reservadas (só a lista dos melhores, no fim).
SEMENTES_AJUSTE = (1, 2, 3)
SEMENTES_RESERVADAS = tuple(range(101, 111))
TOP_PADRAO = 10

def carregar_campo(caminho: Path) -> tuple[np.ndarray, dict]:
    """
        Lê o 'sdf' de um npz do tools/sdf e os campos que descrevem a
        manipulação que a ferramenta fez nele (limiar e log), mais o sha256 do
        arquivo para saber depois exatamente qual campo entrou.
    """
    with np.load(caminho) as arquivo:
        campo = arquivo["sdf"].astype(np.float32)
        info = {"origem": caminho_legivel(Path(caminho)),
                "sha256": hashlib.sha256(Path(caminho).read_bytes()).hexdigest(),
                "convencao": str(arquivo["convencao"]) if "convencao" in arquivo.files else "",
                "limiar": float(arquivo["limiar"]) if "limiar" in arquivo.files else 0.0,
                "escala_log": (float(arquivo["escala_log"])
                               if "escala_log" in arquivo.files else None)}
    return campo, info

def ambiente() -> dict:
    """Máquina, versões e commit, para o resultado dizer onde e com que código rodou."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ_DO_PROJETO,
                                capture_output=True, text=True, check=True).stdout.strip()
        sujo = bool(subprocess.run(["git", "status", "--porcelain", "--", "src"],
                                   cwd=RAIZ_DO_PROJETO, capture_output=True, text=True,
                                   check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, sujo = "", None
    return {"commit": commit, "src_com_mudancas": sujo, "python": sys.version.split()[0],
            "numpy": np.__version__, "scipy": scipy.__version__,
            "plataforma": platform.platform(), "processador": platform.processor(),
            "cpus": os.cpu_count()}

def limiar_do_alvo_no_peso(info_peso: dict, info_alvo: dict) -> float:
    """
        O limiar do alvo (em voxels do SDF) escrito na unidade do peso, para o
        teto trivial. O peso pode ter limiar e log próprios, e as duas
        manipulações só crescem, então "SDF > limiar do alvo" é o mesmo que
        "peso > este valor".
    """
    corte = np.array([info_alvo["limiar"]], dtype=np.float32)
    return float(manipular_sdf(corte, info_peso["limiar"], info_peso["escala_log"])[0])

def rotulo(argumentos: dict) -> str:
    # O nome do arquivo no rótulo liga a linha da planilha de recursos ao npz.
    return (f"{argumentos['execucao']} {argumentos['metodo']} "
            f"orcamento={argumentos['config'].orcamento} seed={argumentos['seed']}")

@track_resources(label=rotulo)
def buscar(metodo: str, avaliador: AvaliadorCA, config: ConfiguracaoGA, seed: int,
           execucao: str = "", observar=None) -> ResultadoBusca:
    if metodo == "genetico":
        return evoluir(GENES_CA, avaliador, config, seed, observar)
    return busca_aleatoria(GENES_CA, avaliador, config.orcamento, seed, observar)

def lista_dos_melhores(resultado: ResultadoBusca, avaliador: AvaliadorCA,
                       quantidade: int, painel: Painel | None = None) -> list[dict]:
    """
        Os melhores parâmetros da busca, do primeiro ao último, cada um rodado
        também nas sementes reservadas com as iterações já escolhidas.
        painel: se vier, mostra cada um conforme é conferido.
    """
    lista = []
    escolhidos = resultado.melhores(quantidade)
    for posicao, avaliacao in enumerate(escolhidos, start=1):
        iteracoes = avaliacao.detalhes["iteracoes"]
        reservadas = avaliador.nota_com_iteracoes(avaliacao.genes, iteracoes,
                                                  SEMENTES_RESERVADAS)
        lista.append({"posicao": posicao, "genes": avaliacao.genes, "iteracoes": iteracoes,
                      "nota_ajuste": avaliacao.nota,
                      "nota_reservada_media": float(reservadas.mean()),
                      "nota_reservada_min": float(reservadas.min()),
                      "notas_reservadas": reservadas.tolist(),
                      "ordem": avaliacao.ordem, "geracao": avaliacao.geracao})
        if painel is not None:
            painel.conferido(posicao, len(escolhidos), avaliacao.genes, avaliacao.nota,
                             float(reservadas.mean()), float(reservadas.min()))
    return lista

def gravar(resultado: ResultadoBusca, extras: dict, destino: Path) -> Path:
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
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
        detalhes=np.array(json.dumps([a.detalhes for a in avaliacoes])),
        **{nome: np.array(json.dumps(valor, ensure_ascii=False)) for nome, valor in extras.items()},
    )
    return destino

def main(argv=None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metodo", choices=("genetico", "aleatoria"), default="genetico")
    parser.add_argument("--orcamento", type=int, default=ConfiguracaoGA.orcamento)
    parser.add_argument("--populacao", type=int, default=ConfiguracaoGA.tamanho_populacao)
    parser.add_argument("--seed", type=int, default=0, help="semente da busca (não do CA)")
    parser.add_argument("--peso", type=Path, default=PESO_ELAPHES,
                        help="npz do tools/sdf usado como peso, sem nenhuma escala")
    parser.add_argument("--alvo", type=Path, default=ALVO_ELAPHES)
    parser.add_argument("--saida", type=Path, default=RESULTS_DIR)
    parser.add_argument("--top", type=int, default=TOP_PADRAO,
                        help="quantos melhores parâmetros listar no fim")
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top precisa ser pelo menos 1.")

    for caminho, comando in ((args.peso, COMANDO_PESO), (args.alvo, COMANDO_ALVO)):
        if not Path(caminho).exists():
            parser.error(f"{caminho} não existe. Gere com: {comando}")

    config = ConfiguracaoGA(tamanho_populacao=args.populacao, orcamento=args.orcamento)
    genetico = args.metodo == "genetico"
    painel = Painel(config.orcamento, por_lote=not genetico,
                    tamanho_lote=config.tamanho_populacao)

    painel.etapa(1, 4, "Carregando o peso e o alvo", "📂")
    peso, info_peso = carregar_campo(args.peso)
    campo_alvo, info_alvo = carregar_campo(args.alvo)
    alvo, cortes = Alvo(campo_alvo), Cortes()
    avaliador = AvaliadorCA(peso, alvo, SEMENTES_AJUSTE, MAX_ITERACOES, cortes)
    minimo, maximo = alvo.faixa(cortes)
    faixas = ", ".join(f"{g.nome} [{g.minimo:g}, {g.maximo:g}]" for g in GENES_CA)
    painel.escrever(f"  peso  {info_peso['origem']} (de {peso.min():+.2f} a {peso.max():+.2f})")
    painel.escrever(f"  alvo  {info_alvo['origem']} ({alvo.referencia} voxels positivos; "
                    f"vazio aceito de {minimo:.0f} a {maximo:.0f})")
    painel.escrever(f"  genes {faixas}; seeds de ajuste {list(SEMENTES_AJUSTE)}")

    destino = build_path(args.saida, PREFIXO, next_id(args.saida, PREFIXO))
    if genetico:
        painel.etapa(2, 4, f"Busca genética: {config.orcamento} candidatos, população "
                           f"{config.tamanho_populacao}, elite {config.elite}, seed {args.seed}",
                     "🧬")
    else:
        painel.etapa(2, 4, f"Busca aleatória: {config.orcamento} candidatos, seed {args.seed}",
                     "🎲")
    resultado = buscar(args.metodo, avaliador, config, args.seed, execucao=destino.stem,
                       observar=painel)
    painel.escrever(f"  {len(resultado.avaliacoes)} avaliações ({resultado.reaproveitadas} "
                    "repetidas, sem refazer o CA)")
    campeao = resultado.melhor

    painel.etapa(3, 4, f"Conferindo os {args.top} melhores nas {len(SEMENTES_RESERVADAS)} "
                       "seeds reservadas", "🔍")
    melhores = lista_dos_melhores(resultado, avaliador, args.top, painel)
    # O primeiro da lista é o campeão; só se tudo foi cortado a lista vem vazia.
    if melhores:
        reservadas = np.array(melhores[0]["notas_reservadas"])
    else:
        reservadas = avaliador.nota_com_iteracoes(campeao.genes, campeao.detalhes["iteracoes"],
                                                  SEMENTES_RESERVADAS)
    copia = nota_da_copia_pura(peso, alvo)
    teto = nota_da_copia_pura(peso, alvo, limiar=limiar_do_alvo_no_peso(info_peso, info_alvo))

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
        "melhores": melhores,
        "nota_copia_pura": copia, "nota_teto_trivial": teto,
        "forma": list(peso.shape),
        "ambiente": {**ambiente(), "arquivo_peso": info_peso["origem"],
                     "sha256_peso": info_peso["sha256"]},
    }
    painel.etapa(4, 4, "Gravando o resultado", "💾")
    gravar(resultado, extras, destino)

    painel.tabela_melhores(melhores, [gene.nome for gene in GENES_CA], len(SEMENTES_RESERVADAS))
    painel.referencias(copia, teto, caminho_legivel(destino))
    return destino

if __name__ == "__main__":
    main()
