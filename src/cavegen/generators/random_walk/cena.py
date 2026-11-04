"""
    Grafos de waypoints das cavernas do projeto base, lidos de configs/random_walk/.

    Cada arquivo tem os waypoints (nome e posição), as ligações entre eles e
    os parâmetros do CaveGenerator de uma caverna da cena Unity. Os arquivos
    são gerados uma vez por exportar_cena.py; daqui em diante o gerador não
    depende da Unity nem do projeto base.

    As posições ficam nos eixos da Unity (x, y, z), com y para cima.
"""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

PASTA_CAVERNAS = Path(__file__).resolve().parents[4] / "configs" / "random_walk"

@dataclass
class Grafo:
    nome: str
    nomes: list[str]
    posicoes: np.ndarray
    arestas: np.ndarray
    parametros: dict = field(default_factory=dict)

def apelido(nome: str) -> str:
    """
        Nome da caverna em minúsculas e com _, para os arquivos.
        nome: nome do objeto na cena, como "Knotlow Cavern".
    """
    return nome.lower().replace(" ", "_")

def caminho_caverna(caverna: str, pasta: Path = PASTA_CAVERNAS) -> Path:
    """
        Arquivo de uma caverna.
        caverna: nome ou apelido da caverna, como "Knotlow Cavern" ou "knotlow_cavern".
        pasta: onde ficam os arquivos.
    """
    return Path(pasta) / f"{apelido(caverna)}.yaml"

def cavernas_disponiveis(pasta: Path = PASTA_CAVERNAS) -> list[str]:
    """
        Apelidos das cavernas exportadas, na ordem em que aparecem na cena.
        pasta: onde ficam os arquivos.
    """
    arquivos = [(yaml.safe_load(c.read_text(encoding="utf-8"))["origem"]["ordem_na_cena"],
                 c.stem) for c in Path(pasta).glob("*.yaml")]
    return [nome for _, nome in sorted(arquivos)]

def carregar_caverna(caverna: str, pasta: Path = PASTA_CAVERNAS) -> Grafo:
    """
        Grafo de uma caverna exportada.
        caverna: nome ou apelido da caverna.
        pasta: onde ficam os arquivos.
    """
    caminho = caminho_caverna(caverna, pasta)
    if not caminho.exists():
        raise ValueError(f"Caverna {caverna!r} não encontrada em {pasta}. "
                         f"Disponíveis: {', '.join(cavernas_disponiveis(pasta))}.")

    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return Grafo(
        nome=dados["caverna"],
        nomes=[w["nome"] for w in dados["waypoints"]],
        posicoes=np.array([w["posicao"] for w in dados["waypoints"]], dtype=np.float64),
        arestas=np.array(dados["ligacoes"], dtype=np.int32).reshape(-1, 2),
        parametros={p: float(v) for p, v in dados["parametros"].items()},
    )
