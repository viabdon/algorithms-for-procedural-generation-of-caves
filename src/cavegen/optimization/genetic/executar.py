"""Roda o ajuste do CA (GA ou busca aleatória de controle) nas cavernas e grava o resultado.

    uv run python -m cavegen.optimization.genetic.executar                     # GA, só o Elaphes
    uv run python -m cavegen.optimization.genetic.executar --metodo aleatoria  # busca aleatória
    uv run python -m cavegen.optimization.genetic.executar --cavernas elaphes indian_tunnel
    uv run python -m cavegen.optimization.genetic.executar --orcamento 100 --seed 2

Cada caverna tem um campo só, o SDF dela com ln(1 + |d|), escala 1 e sem
limiar, que é o peso do CA e o alvo da nota. Ele é gerado uma vez com a
ferramenta do SDF:

    uv run python -m tools.sdf.sdf --log 1                         # Elaphes (padrão)
    uv run python -m tools.sdf.sdf <grade_de_superficie.npz> --log 1

Em --cavernas, um nome (elaphes) vira tools/sdf/npz/<nome>_surface_64_sdf_log1.npz;
um caminho .npz é usado como está. O campo entra no CA exatamente como está no
arquivo, e o arquivo, o hash e a manipulação de cada caverna ficam gravados no
resultado (`cavernas`).

No fim, mostra e grava a lista dos melhores parâmetros (--top, padrão 10),
ordenada pela média das notas entre as cavernas: cada combinação uma vez só,
com a nota de cada caverna, o mínimo, o máximo e o desvio entre elas, nas
sementes de ajuste e nas reservadas. Cada execução grava results/ga_NNN.npz ao
lado deste arquivo, com a configuração inteira, todas as avaliações, essa lista
e a nota da cópia pura de cada caverna. O consumo de recursos da busca inteira
vai para a planilha do track_resources.
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
from cavegen.optimization.genetic.aptidao import Cortes, nota_da_copia_pura
from cavegen.optimization.genetic.ca import (
    BORDA,
    GENES_CA,
    MAX_ITERACOES,
    MODO_PESO,
    AvaliadorCA,
    Caverna,
)
from cavegen.optimization.genetic.painel import Painel
from cavegen.profiling.resource_tracker import track_resources

NPZ_SDF = RAIZ_DO_PROJETO / "tools" / "sdf" / "npz"
# O tools/sdf grava o campo da grade <nome>_surface_64.npz como
# <nome>_surface_64_sdf_log1.npz quando roda com --log 1 e sem limiar.
SUFIXO_GRADE = "_surface_64"
SUFIXO_CAMPO = "_sdf_log1"
CAVERNAS_PADRAO = ("elaphes",)
CAMPO_ELAPHES = NPZ_SDF / f"elaphes{SUFIXO_GRADE}{SUFIXO_CAMPO}.npz"
COMANDO_ELAPHES = "uv run python -m tools.sdf.sdf --log 1"
COMANDO_SDF = "uv run python -m tools.sdf.sdf <grade_de_superficie.npz> --log 1"
LADO_DO_PROTOCOLO = 64
RESULTS_DIR = Path(__file__).resolve().parent / "results"
PREFIXO = "ga"
# Uma seed é só o número que inicializa o sorteador da matriz inicial; a
# porcentagem de vazio é o gene chance_inicial. Todo candidato roda nas mesmas
# 5 seeds de ajuste, com a mesma chance nas 5: só o ruído muda de uma para
# outra. Fixas, elas deixam a comparação justa (todos enfrentam as mesmas
# grades) e a nota determinística (o que permite o cache de repetidos).
SEMENTES_AJUSTE = (1, 2, 3, 4, 5)
# As reservadas são outras 10 seeds, que a busca nunca vê: só a lista dos
# melhores roda nelas, no fim. Os números 101 a 110 são só rótulos, para não
# coincidir com as de ajuste: são 10 grades, não 110.
SEMENTES_RESERVADAS = tuple(range(101, 111))
TOP_PADRAO = 10
CRITERIO = "média das notas entre as cavernas, nas seeds de ajuste"

def caminho_da_caverna(caverna: str) -> Path:
    """
        Arquivo do campo de uma caverna. Um .npz é usado como está; um nome
        (como "elaphes") vira tools/sdf/npz/<nome>_surface_64_sdf_log1.npz.
    """
    if caverna.lower().endswith(".npz"):
        return Path(caverna)
    return NPZ_SDF / f"{caverna}{SUFIXO_GRADE}{SUFIXO_CAMPO}.npz"

def nome_da_caverna(caminho: Path) -> str:
    """Rótulo da caverna: o nome do arquivo sem _sdf_log1 e sem _surface_64 (elaphes)."""
    nome = Path(caminho).stem
    for sufixo in (SUFIXO_CAMPO, SUFIXO_GRADE):
        nome = nome.removesuffix(sufixo)
    return nome

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

def carregar_caverna(caminho: Path) -> tuple[Caverna, dict]:
    """
        Carrega o campo de uma caverna e confere que é o do GA: log de escala 1
        e sem limiar. Erro (ValueError) diz qual caverna e por quê.
    """
    nome = nome_da_caverna(caminho)
    campo, info = carregar_campo(caminho)
    if info["limiar"] != 0 or info["escala_log"] != 1:
        log = "sem log" if info["escala_log"] is None else f"log x{info['escala_log']:g}"
        raise ValueError(f"A caverna {nome} ({info['origem']}) tem limiar {info['limiar']:g} e "
                         f"{log}, mas o GA usa o SDF com log x1 e sem limiar. Gere com: "
                         f"{COMANDO_SDF}")
    return Caverna(nome, campo), info

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

def rotulo(argumentos: dict) -> str:
    # O nome do arquivo no rótulo liga a linha da planilha de recursos ao npz.
    cavernas = "+".join(argumentos["avaliador"].nomes)
    return (f"{argumentos['execucao']} {argumentos['metodo']} "
            f"orcamento={argumentos['config'].orcamento} seed={argumentos['seed']} "
            f"cavernas={cavernas}")

@track_resources(label=rotulo)
def buscar(metodo: str, avaliador: AvaliadorCA, config: ConfiguracaoGA, seed: int,
           execucao: str = "", observar=None) -> ResultadoBusca:
    if metodo == "genetico":
        return evoluir(GENES_CA, avaliador, config, seed, observar)
    return busca_aleatoria(GENES_CA, avaliador, config.orcamento, seed, observar)

def lista_dos_melhores(resultado: ResultadoBusca, avaliador: AvaliadorCA,
                       quantidade: int, painel: Painel | None = None) -> list[dict]:
    """
        Os melhores parâmetros da busca, do primeiro ao último pela média entre
        as cavernas nas sementes de ajuste (a nota da busca), cada um rodado
        também nas sementes reservadas, em todas as cavernas, com as iterações
        já escolhidas.
        painel: se vier, mostra cada um conforme é conferido.
    """
    lista = []
    escolhidos = resultado.melhores(quantidade)
    for posicao, avaliacao in enumerate(escolhidos, start=1):
        iteracoes = avaliacao.detalhes["iteracoes"]
        reservadas = avaliador.conferir(avaliacao.genes, iteracoes, SEMENTES_RESERVADAS)
        lista.append({"posicao": posicao, "genes": avaliacao.genes, "iteracoes": iteracoes,
                      "nota_ajuste": avaliacao.nota,
                      "ajuste": avaliacao.detalhes["entre_cavernas"],
                      "nota_reservada_media": reservadas["media"],
                      "reservadas": reservadas,
                      "ordem": avaliacao.ordem, "geracao": avaliacao.geracao})
        if painel is not None:
            painel.conferido(posicao, len(escolhidos), avaliacao.genes, avaliacao.nota,
                             reservadas)
    return lista

def descrever_gene(gene) -> str:
    passo = f", de {gene.passo:g} em {gene.passo:g}" if gene.passo is not None else ""
    return f"{gene.nome} [{gene.minimo:g}, {gene.maximo:g}{passo}]"

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
    parser.add_argument("--metodo", choices=("genetico", "aleatoria"), default="genetico",
                        help="genetico: o algoritmo genético; aleatoria: a busca aleatória de "
                             "controle, que só sorteia (sem seleção nem cruzamento)")
    parser.add_argument("--cavernas", nargs="+", default=list(CAVERNAS_PADRAO),
                        metavar="CAVERNA",
                        help="nomes (elaphes, indian_tunnel) ou npz do tools/sdf com log 1 e sem "
                             "limiar; o campo de cada caverna é o peso e o alvo dela "
                             "(padrão: elaphes)")
    parser.add_argument("--orcamento", type=int, default=ConfiguracaoGA.orcamento)
    parser.add_argument("--populacao", type=int, default=ConfiguracaoGA.tamanho_populacao)
    parser.add_argument("--seed", type=int, default=0, help="semente da busca (não do CA)")
    parser.add_argument("--saida", type=Path, default=RESULTS_DIR)
    parser.add_argument("--top", type=int, default=TOP_PADRAO,
                        help="quantos melhores parâmetros listar no fim")
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top precisa ser pelo menos 1.")

    caminhos = [caminho_da_caverna(c) for c in args.cavernas]
    for caminho in caminhos:
        if not caminho.exists():
            comando = COMANDO_ELAPHES if caminho == CAMPO_ELAPHES else COMANDO_SDF
            parser.error(f"{caminho} não existe. Gere o SDF da caverna com: {comando}")
    nomes = [nome_da_caverna(c) for c in caminhos]
    if len(set(nomes)) != len(nomes):
        parser.error(f"--cavernas tem caverna repetida: {nomes}")

    config = ConfiguracaoGA(tamanho_populacao=args.populacao, orcamento=args.orcamento)
    genetico = args.metodo == "genetico"
    painel = Painel(config.orcamento, por_lote=not genetico,
                    tamanho_lote=config.tamanho_populacao)

    painel.etapa(1, 4, "Carregando as cavernas (o campo de cada uma é o peso e o alvo dela)",
                 "📂")
    try:
        carregadas = [carregar_caverna(c) for c in caminhos]
    except ValueError as erro:
        parser.error(str(erro))
    # O mesmo arquivo com outro nome (uma cópia, ou "Elaphes" no Windows, que não
    # diferencia maiúsculas) pesaria em dobro na média entre as cavernas.
    por_conteudo = {}
    for caverna, info in carregadas:
        igual = por_conteudo.setdefault(info["sha256"], caverna.nome)
        if igual != caverna.nome:
            parser.error(f"--cavernas tem caverna repetida: {igual} e {caverna.nome} são o "
                         "mesmo campo (mesmo sha256)")
    cavernas = [caverna for caverna, _ in carregadas]
    cortes = Cortes()
    avaliador = AvaliadorCA(cavernas, SEMENTES_AJUSTE, MAX_ITERACOES, cortes)
    copias = {c.nome: nota_da_copia_pura(c.peso, c.alvo) for c in cavernas}
    for caverna, info in carregadas:
        aviso = None
        if caverna.lado != LADO_DO_PROTOCOLO:
            aviso = (f"grade {caverna.lado}³, fora do protocolo de {LADO_DO_PROTOCOLO}³: o CA "
                     "roda, mas um voxel dela não tem o tamanho dos das outras")
        painel.caverna(caverna.nome, info["origem"], caverna.peso.shape,
                       float(caverna.peso.min()), float(caverna.peso.max()),
                       caverna.alvo.referencia, caverna.alvo.faixa(cortes),
                       copias[caverna.nome], aviso)
    faixas = ", ".join(descrever_gene(g) for g in GENES_CA)
    painel.escrever(f"  genes {faixas}")
    painel.escrever(f"  seeds de ajuste {list(SEMENTES_AJUSTE)}; reservadas "
                    f"{SEMENTES_RESERVADAS[0]} a {SEMENTES_RESERVADAS[-1]} "
                    f"({len(SEMENTES_RESERVADAS)} seeds); {MAX_ITERACOES} iterações sempre")

    destino = build_path(args.saida, PREFIXO, next_id(args.saida, PREFIXO))
    if genetico:
        painel.etapa(2, 4, f"Busca genética: {config.orcamento} candidatos, população "
                           f"{config.tamanho_populacao}, elite {config.elite}, seed {args.seed}",
                     "🧬")
    else:
        painel.etapa(2, 4, f"Busca aleatória de controle (só sorteia, sem seleção nem "
                           f"cruzamento): {config.orcamento} candidatos, seed {args.seed}", "🎲")
    resultado = buscar(args.metodo, avaliador, config, args.seed, execucao=destino.stem,
                       observar=painel)
    painel.escrever(f"  {len(resultado.avaliacoes)} avaliações ({resultado.reaproveitadas} "
                    "repetidas, sem refazer o CA)")
    campeao = resultado.melhor

    painel.etapa(3, 4, f"Conferindo os {args.top} melhores nas {len(SEMENTES_RESERVADAS)} "
                       f"seeds reservadas, em {len(cavernas)} caverna(s)", "🔍")
    melhores = lista_dos_melhores(resultado, avaliador, args.top, painel)
    # O primeiro da lista é o campeão; só se tudo foi cortado a lista vem vazia.
    if melhores:
        reservadas = melhores[0]["reservadas"]
    else:
        reservadas = avaliador.conferir(campeao.genes, campeao.detalhes["iteracoes"],
                                        SEMENTES_RESERVADAS)

    extras = {
        "config": asdict(config), "seed": args.seed,
        "genes_limites": [g.como_dict() for g in GENES_CA],
        "cortes": cortes.como_dict(),
        "max_iteracoes": MAX_ITERACOES, "borda": BORDA.value, "modo_peso": MODO_PESO.value,
        "sementes_ajuste": list(SEMENTES_AJUSTE),
        "sementes_reservadas": list(SEMENTES_RESERVADAS),
        "cavernas": [{"nome": caverna.nome, **info, "forma": list(caverna.peso.shape),
                      "referencia_alvo": caverna.alvo.referencia,
                      "faixa_vazio": list(caverna.alvo.faixa(cortes))}
                     for caverna, info in carregadas],
        "criterio_ranking": CRITERIO,
        "campeao": {"genes": campeao.genes, "nota_ajuste": campeao.nota,
                    "iteracoes": campeao.detalhes["iteracoes"], "ordem": campeao.ordem,
                    "ajuste": campeao.detalhes["entre_cavernas"], "reservadas": reservadas},
        "nota_reservada_media": reservadas["media"],
        "melhores": melhores,
        "nota_copia_pura": copias,
        "ambiente": ambiente(),
    }
    painel.etapa(4, 4, "Gravando o resultado", "💾")
    gravar(resultado, extras, destino)

    painel.tabela_melhores(melhores, [gene.nome for gene in GENES_CA], avaliador.nomes,
                           len(SEMENTES_AJUSTE), len(SEMENTES_RESERVADAS))
    painel.referencias(copias, caminho_legivel(destino))
    return destino

if __name__ == "__main__":
    main()
