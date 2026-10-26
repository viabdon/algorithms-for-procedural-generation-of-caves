"""
    Lê os grafos de waypoints da cena Unity do projeto base.

    No projeto base (external/3D-Cave-Generation) cada caverna é um objeto com
    o componente CaveGenerator. O campo nodes aponta para um objeto cujos
    filhos são os waypoints, posicionados à mão sobre o modelo FBX da caverna
    real. Cada waypoint tem um Linker com a lista de waypoints ligados a ele.

    A cena é um YAML da Unity: cada objeto começa em "--- !u!<tipo> &<id>" e
    se refere aos outros pelo fileID. Os tipos usados aqui são 1 (GameObject),
    4 (Transform) e 114 (MonoBehaviour, onde ficam o CaveGenerator e o Linker).

    Os objetos nodes ficam na raiz da cena, na origem, sem rotação e com escala
    1, então a posição local dos waypoints já é a posição no mundo. ler_cena()
    confere isso em vez de compor as transformações.

    As posições ficam nos eixos da Unity (x, y, z), com y para cima.

    uv run python random_walk_temp/cena.py
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PASTA = Path(__file__).resolve().parent
CENA = (PASTA.parent / "external" / "3D-Cave-Generation" / "Assets" / "Scenes"
        / "SampleScene.unity")

CABECALHO = re.compile(r"^--- !u!(\d+) &(\d+).*$", flags=re.MULTILINE)
REFERENCIA = re.compile(r"\{fileID: (\d+)\}")

# Parâmetros do CaveGenerator gravados na cena, na ordem do Inspector.
PARAMETROS = ("weight", "k", "spacer", "radius", "segments")

@dataclass
class Grafo:
    nome: str
    nomes: list[str]
    posicoes: np.ndarray
    arestas: np.ndarray
    parametros: dict = field(default_factory=dict)

def separar_objetos(texto: str) -> dict[str, tuple[str, str]]:
    """
        Divide a cena em {fileID: (tipo, corpo)}.
        texto: conteúdo do .unity.
    """
    partes = CABECALHO.split(texto)
    return {partes[i + 1]: (partes[i], partes[i + 2]) for i in range(1, len(partes), 3)}

def valor(corpo: str, nome: str) -> str:
    """
        Texto depois de "nome:" na primeira linha que tiver o campo.
        corpo: corpo de um objeto da cena.
        nome: nome do campo.
    """
    return re.search(rf"^\s*{nome}: (.*)$", corpo, flags=re.MULTILINE).group(1).strip()

def vetor(corpo: str, nome: str) -> np.ndarray:
    """
        Lê um campo {x: _, y: _, z: _} (ou com w) como array.
        corpo: corpo de um objeto da cena.
        nome: nome do campo, como m_LocalPosition.
    """
    return np.array([float(v) for v in re.findall(r"[xyzw]: ([-\d.e]+)", valor(corpo, nome))])

def lista_de_referencias(corpo: str, nome: str) -> list[str]:
    """
        fileIDs de um campo em lista, como m_Children ou edges.
        corpo: corpo de um objeto da cena.
        nome: nome do campo.
    """
    trecho = corpo.split(f"{nome}:", 1)[1]
    itens = re.match(r"(?:\s*- \{fileID: \d+\})*", trecho).group(0)
    return REFERENCIA.findall(itens)

def componentes_por_objeto(objetos: dict) -> dict[str, dict[str, str]]:
    """
        Índice {fileID do GameObject: {tipo: fileID do componente}}.
        objetos: saída de separar_objetos().
    """
    indice = {}
    for chave, (tipo, corpo) in objetos.items():
        # Configurações da cena e prefabs não pertencem a um GameObject.
        if tipo == "1" or "m_GameObject:" not in corpo:
            continue
        dono = REFERENCIA.search(valor(corpo, "m_GameObject")).group(1)
        indice.setdefault(dono, {})[tipo] = chave
    return indice

def ler_cena(caminho: Path = CENA) -> list[Grafo]:
    """
        Um Grafo por CaveGenerator da cena, na ordem em que aparecem.
        caminho: arquivo .unity.
    """
    objetos = separar_objetos(Path(caminho).read_text(encoding="utf-8"))
    componentes = componentes_por_objeto(objetos)

    grafos = []
    for tipo, corpo in objetos.values():
        if tipo != "114" or "nodes:" not in corpo:
            continue

        dono = REFERENCIA.search(valor(corpo, "m_GameObject")).group(1)
        nome = valor(objetos[dono][1], "m_Name")
        parametros = {p: float(valor(corpo, p)) for p in PARAMETROS}

        raiz = REFERENCIA.search(valor(corpo, "nodes")).group(1)
        transform_raiz = objetos[componentes[raiz]["4"]][1]
        identidade = (np.allclose(vetor(transform_raiz, "m_LocalPosition"), 0)
                      and np.allclose(vetor(transform_raiz, "m_LocalRotation"), [0, 0, 0, 1])
                      and np.allclose(vetor(transform_raiz, "m_LocalScale"), 1)
                      and valor(transform_raiz, "m_Father") == "{fileID: 0}")
        if not identidade:
            raise ValueError(f"{nome}: o objeto nodes saiu da origem, a posição local "
                             "dos waypoints deixa de ser a do mundo.")

        # Mesma ordem do CaveGenerator.Load(): a dos filhos no Transform.
        filhos = lista_de_referencias(transform_raiz, "m_Children")
        waypoints = [REFERENCIA.search(valor(objetos[t][1], "m_GameObject")).group(1)
                     for t in filhos]
        indice = {w: i for i, w in enumerate(waypoints)}

        arestas = []
        for i, w in enumerate(waypoints):
            linker = objetos[componentes[w]["114"]][1]
            arestas += [(i, indice[destino]) for destino in lista_de_referencias(linker, "edges")]

        grafos.append(Grafo(
            nome=nome,
            nomes=[valor(objetos[w][1], "m_Name") for w in waypoints],
            posicoes=np.array([vetor(objetos[t][1], "m_LocalPosition") for t in filhos]),
            arestas=np.array(arestas, dtype=np.int32).reshape(-1, 2),
            parametros=parametros,
        ))

    return grafos

def apelido(nome: str) -> str:
    """
        Nome da caverna em minúsculas e com _, para os arquivos.
        nome: nome do objeto na cena, como "Knotlow Cavern".
    """
    return nome.lower().replace(" ", "_")

def main():
    for grafo in ler_cena():
        extensao = grafo.posicoes.max(axis=0) - grafo.posicoes.min(axis=0)
        print(f"{grafo.nome}: {len(grafo.nomes)} waypoints, {len(grafo.arestas)} ligações, "
              f"extensão (x, y, z) = {np.round(extensao, 1).tolist()}, {grafo.parametros}")

if __name__ == "__main__":
    main()
