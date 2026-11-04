"""
    Exporta os grafos de waypoints da cena Unity do projeto base para configs/random_walk/.

    Script de uso único: o gerador lê só os arquivos exportados, sem depender
    da Unity nem do projeto base. Rodar de novo só para refazer a exportação.

    No projeto base (external/3D-Cave-Generation, commit 7a6c617) cada caverna
    é um objeto com o componente CaveGenerator. O campo nodes aponta para um
    objeto cujos filhos são os waypoints, posicionados à mão sobre o modelo FBX
    da caverna real. Cada waypoint tem um Linker com a lista de waypoints
    ligados a ele.

    A cena é um YAML da Unity: cada objeto começa em "--- !u!<tipo> &<id>" e
    se refere aos outros pelo fileID. Os tipos usados aqui são 1 (GameObject),
    4 (Transform) e 114 (MonoBehaviour, onde ficam o CaveGenerator e o Linker).

    Os objetos nodes ficam na raiz da cena, na origem, sem rotação e com escala
    1, então a posição local dos waypoints já é a posição no mundo. ler_cena()
    confere isso em vez de compor as transformações.

    As posições ficam nos eixos da Unity (x, y, z), com y para cima.

    Para baixar o projeto base de novo:
    git clone --depth 1 https://github.com/freitasga/3D-Cave-Generation external/3D-Cave-Generation
    rm -rf external/3D-Cave-Generation/.git

    uv run python -m cavegen.generators.random_walk.exportar_cena
"""
import re
from pathlib import Path

import numpy as np
import yaml

from cavegen.generators.random_walk.cena import PASTA_CAVERNAS, Grafo, apelido, caminho_caverna

RAIZ_DO_PROJETO = Path(__file__).resolve().parents[4]
CENA = (RAIZ_DO_PROJETO / "external" / "3D-Cave-Generation" / "Assets" / "Scenes"
        / "SampleScene.unity")
COMMIT_DO_PROJETO_BASE = "7a6c617"

CABECALHO = re.compile(r"^--- !u!(\d+) &(\d+).*$", flags=re.MULTILINE)
REFERENCIA = re.compile(r"\{fileID: (\d+)\}")

# Parâmetros do CaveGenerator gravados na cena, na ordem do Inspector.
PARAMETROS = ("weight", "k", "spacer", "radius", "segments")

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

def para_dicionario(grafo: Grafo, ordem: int) -> dict:
    """
        Conteúdo do arquivo de uma caverna em configs/random_walk/.
        A ordem das ligações é a da cena (waypoint de origem, depois a lista do
        Linker), que é a ordem em que o PathGenerator gera os caminhos.
        grafo: saída de ler_cena().
        ordem: posição do CaveGenerator na cena, só para registro.
    """
    return {
        "caverna": grafo.nome,
        "origem": {
            "projeto": "https://github.com/freitasga/3D-Cave-Generation",
            "commit": COMMIT_DO_PROJETO_BASE,
            "cena": "Assets/Scenes/SampleScene.unity",
            "ordem_na_cena": ordem,
        },
        "eixos": "x, y, z da Unity, com y para cima",
        "parametros": dict(grafo.parametros),
        "waypoints": [{"nome": nome, "posicao": [float(v) for v in posicao]}
                      for nome, posicao in zip(grafo.nomes, grafo.posicoes)],
        "ligacoes": [[int(a), int(b)] for a, b in grafo.arestas],
    }

def exportar(caminho_cena: Path = CENA, pasta: Path = PASTA_CAVERNAS) -> list[Path]:
    """
        Grava um arquivo por caverna da cena e devolve os caminhos gravados.
        caminho_cena: arquivo .unity.
        pasta: destino dos arquivos.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    gravados = []
    for ordem, grafo in enumerate(ler_cena(caminho_cena)):
        destino = caminho_caverna(apelido(grafo.nome), pasta)
        cabecalho = (f"# Exportado de {caminho_cena.name} (projeto base, commit "
                     f"{COMMIT_DO_PROJETO_BASE}) por\n"
                     "# uv run python -m cavegen.generators.random_walk.exportar_cena\n"
                     "# Não editar à mão: refazer a exportação.\n")
        # O PyYAML grava float com repr, então a posição volta idêntica na leitura.
        corpo = yaml.safe_dump(para_dicionario(grafo, ordem), sort_keys=False,
                               allow_unicode=True, default_flow_style=None)
        destino.write_text(cabecalho + corpo, encoding="utf-8")
        gravados.append(destino)
    return gravados

def main():
    for destino in exportar():
        print(f"-> {destino.relative_to(RAIZ_DO_PROJETO)}")

if __name__ == "__main__":
    main()
