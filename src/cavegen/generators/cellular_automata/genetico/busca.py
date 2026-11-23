"""Etapa 3 do pipeline do GA: a busca (GA ou busca aleatória de controle) nos campos.

    uv run python -m cavegen.generators.cellular_automata.genetico.busca                    # GA
    uv run python -m cavegen.generators.cellular_automata.genetico.busca --metodo aleatoria
    uv run python -m cavegen.generators.cellular_automata.genetico.busca --cavernas elaphes
    uv run python -m cavegen.generators.cellular_automata.genetico.busca --orcamento 100 --seed 2

Lê os campos de 2_campos/ (etapa 2, campos.py) e grava 3_resultados/ga_NNN.npz.
Sem --cavernas, usa todas as cavernas de 1_entrada/; um nome escolhe uma delas,
e o campo dela precisa estar em dia com a grade (senão, rode a etapa 2). Um
caminho .npz é um campo usado como está. O fluxo inteiro, com a etapa 2 antes e
os relatórios da etapa 4 depois, é o pipeline.py.

Cada caverna tem um campo só, o SDF dela com ln(1 + |d|), escala 1 e sem
limiar, que é o peso do CA e o alvo da nota. Ele entra no CA exatamente como
está no arquivo. O resultado grava, por caverna, a grade de entrada e o sha256
dela, o arquivo e o sha256 do campo e a versão do cálculo do SDF (`cavernas`).

No fim, mostra a lista dos melhores parâmetros (--top, padrão 10), ordenada
pela média das notas entre as cavernas: cada combinação uma vez só, com a nota
de cada caverna, o mínimo, o máximo e o desvio entre elas, nas sementes de
ajuste e nas reservadas. O npz guarda a configuração inteira, todas as
avaliações, essa lista e a nota da cópia pura de cada caverna; o consumo de
recursos da busca inteira vai para a planilha do track_resources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import scipy

from cavegen.generators.cellular_automata.genetico.algoritmo import (
    ConfiguracaoGA,
    ResultadoBusca,
    busca_aleatoria,
    evoluir,
)
from cavegen.generators.cellular_automata.genetico.aptidao import Cortes, nota_da_copia_pura
from cavegen.generators.cellular_automata.genetico.ca import (
    BORDA,
    GENES_CA,
    MAX_ITERACOES,
    MODO_PESO,
    AvaliadorCA,
    Caverna,
)
from cavegen.generators.cellular_automata.genetico.campos import (
    CAMPOS_DIR,
    ENTRADA_DIR,
    caminho_do_campo,
    cavernas_da_entrada,
    escolher,
    nome_da_caverna,
    situacao,
)
from cavegen.generators.cellular_automata.genetico.campos import COMANDO as COMANDO_CAMPOS
from cavegen.generators.cellular_automata.genetico.painel import Painel
from cavegen.generators.cellular_automata.pesos import RAIZ_DO_PROJETO, caminho_legivel
from cavegen.generators.cellular_automata.storage import build_path, next_id
from cavegen.profiling.resource_tracker import track_resources

LADO_DO_PROTOCOLO = 64
RESULTS_DIR = Path(__file__).resolve().parent / "3_resultados"
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

def resolver_cavernas(pedidas: list[str] | None, entrada: Path = ENTRADA_DIR,
                     campos: Path = CAMPOS_DIR) -> list[Path]:
    """
        Os campos que a busca lê, na ordem pedida. Sem pedido, todas as cavernas
        da entrada. Um nome é uma caverna da entrada, e o campo dela precisa
        estar em dia com a grade; um .npz é um campo usado como está. Erro
        (ValueError) diz qual caverna e o que fazer.
    """
    disponiveis = None
    if pedidas is None:
        disponiveis = cavernas_da_entrada(entrada)
        pedidas = list(escolher(disponiveis))
    caminhos = []
    for pedida in pedidas:
        if pedida.lower().endswith(".npz"):
            caminho = Path(pedida)
            if not caminho.exists():
                raise ValueError(f"{caminho} não existe. Gere os campos com: {COMANDO_CAMPOS}")
        else:
            if disponiveis is None:
                disponiveis = cavernas_da_entrada(entrada)
            grade = escolher(disponiveis, [pedida])[pedida]
            caminho = caminho_do_campo(grade, campos)
            motivo = situacao(grade, caminho)
            if motivo is not None:
                raise ValueError(f"O campo de {pedida} não está em dia ({motivo}). Rode a etapa "
                                 f"2: {COMANDO_CAMPOS}")
        caminhos.append(caminho)
    nomes = [nome_da_caverna(c) for c in caminhos]
    if len(set(nomes)) != len(nomes):
        raise ValueError(f"--cavernas tem caverna repetida: {nomes}")
    return caminhos

def carregar_campo(caminho: Path) -> tuple[np.ndarray, dict]:
    """
        Lê o 'sdf' de um npz da ferramenta do SDF e o que descreve o campo: a
        manipulação (limiar e log), o sha256 do arquivo e, se o campo os tem, a
        grade de entrada de onde veio, o sha256 dela e a versão do cálculo.
        Assim o resultado diz exatamente qual campo, de qual grade, entrou.
    """
    with np.load(caminho) as arquivo:
        if "sdf" not in arquivo.files:
            # O engano provável: a grade de 1_entrada/ no lugar do campo de 2_campos/.
            raise ValueError(f"{caminho_legivel(Path(caminho))} não é um campo (não tem 'sdf'"
                             f"; tem {', '.join(arquivo.files)}). Os campos ficam em 2_campos/"
                             f" e saem da etapa 2: {COMANDO_CAMPOS}")

        def texto(nome):
            return str(arquivo[nome]) if nome in arquivo.files else None

        campo = arquivo["sdf"].astype(np.float32)
        info = {"origem": caminho_legivel(Path(caminho)),
                "sha256": hashlib.sha256(Path(caminho).read_bytes()).hexdigest(),
                "convencao": texto("convencao") or "",
                "limiar": float(arquivo["limiar"]) if "limiar" in arquivo.files else 0.0,
                "escala_log": (float(arquivo["escala_log"])
                               if "escala_log" in arquivo.files else None),
                "entrada": texto("entrada"), "sha256_entrada": texto("sha256_entrada"),
                "versao_sdf": int(arquivo["versao"]) if "versao" in arquivo.files else None}
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
                         f"{COMANDO_CAMPOS}")
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
    parser.add_argument("--cavernas", nargs="+", metavar="CAVERNA",
                        help="nomes de cavernas da entrada (elaphes, indian_tunnel) ou npz de "
                             "campos com log 1 e sem limiar; o campo de cada caverna é o peso e "
                             "o alvo dela (padrão: todas as cavernas da entrada)")
    parser.add_argument("--entrada", type=Path, default=ENTRADA_DIR,
                        help="pasta das grades de superfície (etapa 1)")
    parser.add_argument("--campos", type=Path, default=CAMPOS_DIR,
                        help="pasta dos campos (etapa 2)")
    parser.add_argument("--orcamento", type=int, default=ConfiguracaoGA.orcamento)
    parser.add_argument("--populacao", type=int, default=ConfiguracaoGA.tamanho_populacao)
    parser.add_argument("--seed", type=int, default=0, help="semente da busca (não do CA)")
    parser.add_argument("--saida", type=Path, default=RESULTS_DIR)
    parser.add_argument("--top", type=int, default=TOP_PADRAO,
                        help="quantos melhores parâmetros listar no fim")
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top precisa ser pelo menos 1.")

    try:
        caminhos = resolver_cavernas(args.cavernas, args.entrada, args.campos)
        # Por nome, o campo foi conferido com a grade da entrada; um .npz direto, não.
        conferidos = [not str(p).lower().endswith(".npz")
                      for p in (args.cavernas or [None] * len(caminhos))]
    except ValueError as erro:
        parser.error(str(erro))

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
                       copias[caverna.nome], aviso, caverna.alvo.nota_da_grade_cheia())
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
        "cavernas": [{"nome": caverna.nome, **info, "conferido_com_entrada": conferido,
                      "forma": list(caverna.peso.shape),
                      "referencia_alvo": caverna.alvo.referencia,
                      # Sem limite de cima, o máximo fica null (o JSON não tem inf).
                      "faixa_vazio": [v if math.isfinite(v) else None
                                      for v in caverna.alvo.faixa(cortes)],
                      "nota_grade_cheia": caverna.alvo.nota_da_grade_cheia()}
                     for (caverna, info), conferido in zip(carregadas, conferidos, strict=True)],
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
    painel.referencias(copias, caminho_legivel(destino),
                       {c.nome: c.alvo.nota_da_grade_cheia() for c in cavernas})
    return destino

if __name__ == "__main__":
    main()
