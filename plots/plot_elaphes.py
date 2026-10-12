"""Visualize amostras XYZ do Elaphes com linha central ou malhas em Plotly.

Exemplos:
    uv run python plots/plot_elaphes.py line
    uv run python plots/plot_elaphes.py mesh
    uv run python plots/plot_elaphes.py line --cloud dados.npz --graph grafo.npz --show

Os HTMLs são salvos sem abrir o navegador, salvo quando ``--show`` é usado.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import plotly.graph_objects as go
import trimesh

from cavegen.meshing.normal_orientation import load_orientation, points_sha256, reason_names

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
NUVEM_LINHA_PADRAO = "data/processed/elaphes_gallery_roi_x12_45.npz"
GRAFO_PADRAO = "data/processed/elaphes_centreline_roi_x12_45_pruned_exploratory.npz"
NUVEM_MALHA_PADRAO = "data/processed/elaphes_global_z_le_8_600k_bins.npz"
MALHAS_PADRAO = (
    ("Poisson d8", "results/meshes/elaphes_global_z_le_8_600k_bins_d8_diagnostic.obj"),
    ("Densidade: retirar 10%", "results/meshes/elaphes_global_dense_density_q10_diagnostic.obj"),
    ("Densidade: retirar 20%", "results/meshes/elaphes_global_dense_density_q20_diagnostic.obj"),
)


def resolver_caminho(caminho: str | Path) -> Path:
    """Interpreta caminhos relativos a partir da raiz do projeto."""
    caminho = Path(caminho)
    return caminho if caminho.is_absolute() else RAIZ_PROJETO / caminho


def carregar_xyz(caminho: str | Path, chave: str) -> np.ndarray:
    """Lê um array XYZ finito de um NPZ, sem permitir objetos serializados."""
    origem = resolver_caminho(caminho)
    with np.load(origem, allow_pickle=False) as arquivo:
        if chave not in arquivo:
            raise ValueError(f"{origem} não contém {chave!r}")
        pontos = arquivo[chave]
    if pontos.ndim != 2 or pontos.shape[1] != 3 or not len(pontos):
        raise ValueError(f"{chave} deve ter forma (N, 3), com N > 0")
    if not np.issubdtype(pontos.dtype, np.number) or not np.isfinite(pontos).all():
        raise ValueError(f"{chave} deve conter coordenadas numéricas finitas")
    return pontos.astype(np.float64, copy=False)


def carregar_grafo(caminho: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Lê nós XYZ e índices de arestas de um NPZ exploratório."""
    origem = resolver_caminho(caminho)
    nos = carregar_xyz(origem, "nodes_xyz")
    with np.load(origem, allow_pickle=False) as arquivo:
        if "edges" not in arquivo:
            raise ValueError(f"{origem} não contém 'edges'")
        arestas = arquivo["edges"]
    if arestas.ndim != 2 or arestas.shape[1] != 2:
        raise ValueError("edges deve ter forma (M, 2)")
    if not np.issubdtype(arestas.dtype, np.integer):
        raise ValueError("edges deve conter índices inteiros")
    if np.any(arestas < 0) or np.any(arestas >= len(nos)):
        raise ValueError("edges contém índice de nó fora do intervalo")
    return nos, arestas.astype(np.int64, copy=False)


def amostrar_pontos(pontos: np.ndarray, max_pontos: int, semente: int) -> np.ndarray:
    """Limita a nuvem para o navegador com a mesma seed do padrão de plots."""
    if max_pontos < 1:
        raise ValueError("max_pontos deve ser positivo")
    if semente < 0:
        raise ValueError("semente deve ser não negativa")
    if len(pontos) <= max_pontos:
        return pontos
    indices = np.sort(np.random.default_rng(semente).choice(len(pontos), max_pontos, replace=False))
    return pontos[indices]


def _nuvem_trace(pontos: np.ndarray) -> go.Scatter3d:
    return go.Scatter3d(
        x=pontos[:, 0], y=pontos[:, 1], z=pontos[:, 2], mode="markers",
        name="Pontos observados",
        marker=dict(
            size=2.4, color=pontos[:, 2], colorscale="Viridis", opacity=0.9,
            colorbar=dict(title="Z (fonte)"),
        ),
        hovertemplate="X=%{x:.3f}<br>Y=%{y:.3f}<br>Z=%{z:.3f}<extra></extra>",
    )


def _layout(figura: go.Figure, titulo: str) -> go.Figure:
    figura.update_layout(
        title=titulo,
        template="plotly_white",
        scene=dict(
            xaxis_title="X (fonte)", yaxis_title="Y (fonte)", zaxis_title="Z (fonte)",
            aspectmode="data", bgcolor="rgb(245, 248, 251)",
        ),
        margin=dict(l=0, r=0, t=55, b=0),
        legend=dict(x=0.01, y=0.99),
    )
    return figura


def montar_linha(pontos: np.ndarray, nos: np.ndarray, arestas: np.ndarray) -> go.Figure:
    """Sobrepõe a árvore vermelha à nuvem colorida por Z, em proporção XYZ real."""
    segmentos = np.full((len(arestas) * 3, 3), np.nan)
    segmentos[0::3] = nos[arestas[:, 0]]
    segmentos[1::3] = nos[arestas[:, 1]]
    figura = go.Figure()
    figura.add_trace(_nuvem_trace(pontos))
    figura.add_trace(go.Scatter3d(
        x=segmentos[:, 0], y=segmentos[:, 1], z=segmentos[:, 2],
        mode="lines", name="Linha central exploratória",
        line=dict(width=6, color="#d62828"),
    ))
    figura.add_trace(go.Scatter3d(
        x=nos[:, 0], y=nos[:, 1], z=nos[:, 2],
        mode="markers", name="Nós", marker=dict(size=3.5, color="#d62828"),
        customdata=np.arange(len(nos)),
        hovertemplate="Nó=%{customdata}<br>X=%{x:.3f}<br>Y=%{y:.3f}<br>Z=%{z:.3f}<extra></extra>",
    ))
    return _layout(figura, "Elaphes: nuvem observada e linha central exploratória")


def adicionar_revisao_normais(
    figura: go.Figure, pontos_completos: np.ndarray, orientacao: str | Path,
    *, destacar_incertos: bool = False, mostrar_manuais: bool = False,
    mostrar_normais: bool = False, max_setas: int = 200, comprimento_seta: float = 0.4,
) -> go.Figure:
    """Highlight exact sample indices and show the arrows reviewed by keep/flip."""
    if max_setas < 1 or not np.isfinite(comprimento_seta) or comprimento_seta <= 0:
        raise ValueError("max_setas e comprimento_seta devem ser positivos")
    resultado = load_orientation(resolver_caminho(orientacao))
    if points_sha256(pontos_completos) != str(resultado["point_sha256"]):
        raise ValueError("a orientação não pertence à nuvem passada em --cloud")
    grupos = []
    if destacar_incertos or mostrar_normais:
        grupos.append(("Sentido incerto", resultado["uncertain_indices"], "#f72585"))
    if mostrar_manuais:
        grupos.append(("Corrigidos manualmente", np.flatnonzero(resultado["manual_mask"]), "#008b58"))
    for nome, indices, cor in grupos:
        if not len(indices):
            continue
        pontos = resultado["points_xyz"][indices]
        normais = resultado["oriented_normals_xyz"][indices]
        detalhes = [
            f"Índice={int(i)}<br>Normal atual=({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})"
            f"<br>Ramos={int(resultado['candidate_branches'][i, 0])},"
            f"{int(resultado['candidate_branches'][i, 1])}"
            f"<br>Motivos={reason_names(int(resultado['reason_bits'][i]))}"
            for i, n in zip(indices, normais)
        ]
        figura.add_trace(go.Scatter3d(
            x=pontos[:, 0], y=pontos[:, 1], z=pontos[:, 2],
            mode="markers", name=f"{nome} ({len(indices)})",
            marker=dict(size=3.5, color=cor, opacity=0.7, symbol="diamond"),
            text=detalhes, hovertemplate="%{text}<br>X=%{x:.3f}<br>Y=%{y:.3f}<br>Z=%{z:.3f}<extra></extra>",
        ))
    if mostrar_normais:
        incertos = resultado["uncertain_indices"]
        manuais = np.flatnonzero(resultado["manual_mask"]) if mostrar_manuais else np.empty(0, dtype=int)
        manuais = manuais[np.linspace(0, len(manuais) - 1, min(len(manuais), max_setas), dtype=int)]
        restantes = max_setas - len(manuais)
        incertos = incertos[np.linspace(0, len(incertos) - 1, min(len(incertos), restantes), dtype=int)]
        indices = np.r_[manuais, incertos]
    else:
        indices = np.empty(0, dtype=int)
    if len(indices):
        origens = resultado["points_xyz"][indices]
        direcoes = resultado["oriented_normals_xyz"][indices]
        pontas = origens + comprimento_seta * direcoes
        linhas = np.full((len(indices) * 3, 3), np.nan)
        linhas[0::3] = origens
        linhas[1::3] = pontas
        figura.add_trace(go.Scatter3d(
            x=linhas[:, 0], y=linhas[:, 1], z=linhas[:, 2],
            mode="lines", name=f"Normais atuais ({len(indices)} setas)",
            line=dict(color="#4b185d", width=4), hoverinfo="skip",
        ))
        figura.add_trace(go.Cone(
            x=pontas[:, 0], y=pontas[:, 1], z=pontas[:, 2],
            u=direcoes[:, 0], v=direcoes[:, 1], w=direcoes[:, 2],
            anchor="tip", sizemode="absolute", sizeref=comprimento_seta * 0.35,
            colorscale=[[0, "#4b185d"], [1, "#4b185d"]], showscale=False,
            name="Sentido das normais", hoverinfo="skip",
        ))
    return figura


def carregar_malha(caminho: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Lê vértices e faces triangulares de uma malha OBJ."""
    origem = resolver_caminho(caminho)
    malha = trimesh.load(origem, force="mesh", process=False)
    vertices = np.asarray(malha.vertices)
    faces = np.asarray(malha.faces)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices):
        raise ValueError(f"malha vazia ou inválida: {origem}")
    if faces.ndim != 2 or faces.shape[1] != 3 or not len(faces):
        raise ValueError(f"malha sem faces triangulares: {origem}")
    if not np.isfinite(vertices).all():
        raise ValueError(f"malha com coordenadas não finitas: {origem}")
    return vertices, faces


def montar_malhas(
    pontos: np.ndarray, malhas: Sequence[tuple[str, np.ndarray, np.ndarray]]
) -> go.Figure:
    """Cria seletor de malhas candidatas sobre a mesma nuvem observada."""
    if not malhas:
        raise ValueError("ao menos uma malha é necessária")
    figura = go.Figure()
    for indice, (nome, vertices, faces) in enumerate(malhas):
        figura.add_trace(go.Mesh3d(
            x=vertices[:, 0], y=vertices[:, 1], z=vertices[:, 2],
            i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
            color="#4b9dc1", opacity=0.42, name=nome, visible=indice == 0,
        ))
    figura.add_trace(_nuvem_trace(pontos))
    if len(malhas) > 1:
        botoes = [dict(
            label=nome, method="update",
            args=[{"visible": [i == indice for i in range(len(malhas))] + [True]}],
        ) for indice, (nome, _, _) in enumerate(malhas)]
        figura.update_layout(updatemenus=[dict(type="dropdown", buttons=botoes, x=0.02, y=0.88)])
    return _layout(figura, "Elaphes: malhas candidatas e nuvem observada (não validadas)")


def _argumentos(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest="tipo", required=True)
    for tipo in ("line", "mesh"):
        comando = comandos.add_parser(tipo)
        comando.add_argument("--cloud", default=NUVEM_LINHA_PADRAO if tipo == "line" else NUVEM_MALHA_PADRAO,
                             help="NPZ com points_xyz, relativo à raiz do projeto ou absoluto")
        comando.add_argument("--output", help="HTML de saída; padrão em results/figures/")
        comando.add_argument("--max-points", type=int, default=120_000)
        comando.add_argument("--seed", type=int, default=0, help="seed só para limite de pontos do gráfico")
        comando.add_argument("--show", action="store_true", help="abre também no navegador")
        comando.add_argument("--orientation", help="NPZ de revisão gerado por normal_orientation prepare/apply")
        comando.add_argument("--highlight-uncertain", action="store_true",
                             help="destaca todos os índices com sentido incerto, mesmo fora de --max-points")
        comando.add_argument("--show-manual", action="store_true", help="destaca pontos corrigidos manualmente")
        comando.add_argument("--show-normals", action="store_true", help="desenha setas de normais selecionadas")
        comando.add_argument("--max-normal-arrows", type=int, default=200)
        comando.add_argument("--normal-arrow-length", type=float, default=0.4)
        if tipo == "line":
            comando.add_argument("--graph", default=GRAFO_PADRAO, help="NPZ com nodes_xyz e edges")
        else:
            comando.add_argument("--mesh", action="append", metavar="NOME=OBJ",
                                 help="candidata; repetir para criar seletor (padrão: global, q10, q20)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> Path:
    argumentos = _argumentos(argv)
    pontos_completos = carregar_xyz(argumentos.cloud, "points_xyz")
    pontos = amostrar_pontos(pontos_completos, argumentos.max_points, argumentos.seed)
    if argumentos.tipo == "line":
        nos, arestas = carregar_grafo(argumentos.graph)
        figura = montar_linha(pontos, nos, arestas)
        nome_padrao = "elaphes_centreline_roi_x12_45_pruned_interactive.html"
    else:
        escolhas = []
        for entrada in argumentos.mesh or []:
            nome, separador, caminho = entrada.partition("=")
            if not separador or not nome or not caminho:
                raise ValueError("--mesh deve usar NOME=OBJ")
            escolhas.append((nome, caminho))
        if not escolhas:
            escolhas = list(MALHAS_PADRAO)
        malhas = [(nome, *carregar_malha(caminho)) for nome, caminho in escolhas]
        figura = montar_malhas(pontos, malhas)
        nome_padrao = "elaphes_global_dense_candidates_interactive.html"
    if argumentos.highlight_uncertain or argumentos.show_manual or argumentos.show_normals:
        if not argumentos.orientation:
            raise ValueError("--orientation é obrigatório para destacar ou mostrar normais")
        adicionar_revisao_normais(
            figura, pontos_completos, argumentos.orientation,
            destacar_incertos=argumentos.highlight_uncertain,
            mostrar_manuais=argumentos.show_manual,
            mostrar_normais=argumentos.show_normals,
            max_setas=argumentos.max_normal_arrows,
            comprimento_seta=argumentos.normal_arrow_length,
        )
        if argumentos.tipo == "mesh" and figura.layout.updatemenus:
            # The mesh selector must keep every review overlay visible.
            menus = list(figura.layout.updatemenus)
            for button in menus[0].buttons:
                visibility = list(button.args[0]["visible"])
                visibility.extend([True] * (len(figura.data) - len(visibility)))
                button.args = ({"visible": visibility},)
    destino = resolver_caminho(argumentos.output or f"results/figures/{nome_padrao}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    figura.write_html(destino, include_plotlyjs=True)
    if argumentos.show:
        figura.show()
    print(f"figura salva em: {destino}")
    return destino


if __name__ == "__main__":
    main()
