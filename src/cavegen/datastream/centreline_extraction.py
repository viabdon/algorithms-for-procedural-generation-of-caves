"""Estimate a centreline by the Elaphes experiment's LBC and MST sequence."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, diags
from scipy.sparse.csgraph import connected_components, minimum_spanning_tree
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

from cavegen.datastream.las import read_las_metadata


@dataclass(frozen=True)
class ExtractionSettings:
    sample_spacing: float = 0.4
    node_spacing: float = 0.5
    max_samples: int = 12_000
    contraction: float = 0.05
    attraction: float = 0.5
    iterations: int = 5
    graph_neighbours: int = 12

    def __post_init__(self):
        for key in ("sample_spacing", "node_spacing", "contraction", "attraction"):
            value = getattr(self, key)
            if type(value) not in (int, float) or not np.isfinite(value) or value <= 0:
                raise ValueError(f"centreline_extraction.{key} deve ser positivo e finito.")
        for key, minimum in (("max_samples", 32), ("iterations", 1), ("graph_neighbours", 1)):
            value = getattr(self, key)
            if type(value) is not int or value < minimum:
                raise ValueError(f"centreline_extraction.{key} deve ser um inteiro ≥ {minimum}.")


def source_anchor(source: Path) -> np.ndarray:
    """Use the stored LAS offset so sub-metre geometry stays near the origin."""
    if source.suffix.lower() == ".las":
        return np.asarray(read_las_metadata(source)["offsets_xyz"], dtype=np.float64)
    return np.zeros(3, dtype=np.float64)


def _first_per_cell(xyz: np.ndarray, spacing: float) -> np.ndarray:
    _, first = np.unique(np.floor(xyz / spacing), axis=0, return_index=True)
    return xyz[np.sort(first)]


def _sample(batches: Iterable[np.ndarray], settings: ExtractionSettings):
    sample = np.empty((0, 3), dtype=np.float64)
    spacing = settings.sample_spacing
    anchor = None
    total = 0
    for batch in batches:
        if anchor is None:
            anchor = batch[0].copy()
        total += len(batch)
        sample = _first_per_cell(np.concatenate((sample, batch - anchor)), spacing)
        while len(sample) > settings.max_samples:
            spacing *= 2
            sample = _first_per_cell(sample, spacing)
    if len(sample) < 32:
        raise ValueError("A linha central requer pelo menos 32 representantes; reduza sample_spacing.")
    distances, _ = cKDTree(sample).query(sample, k=21)
    mean_distances = distances[:, 1:].mean(axis=1)
    threshold = mean_distances.mean() + 2 * mean_distances.std()
    filtered = sample[mean_distances <= threshold]
    if len(filtered) < 32:
        raise ValueError("Restaram menos de 32 representantes após o filtro espacial.")
    return filtered, anchor, spacing, total


def _contract(points, settings, laplacian):
    initial_mass = None
    attraction = np.full(len(points), settings.attraction)
    completed = 0
    for _ in range(settings.iterations):
        operator, mass_matrix = laplacian(points, mollify_factor=1e-5, n_neighbors=30)
        mass = mass_matrix.diagonal()
        if not np.isfinite(mass).all() or np.any(mass <= 0):
            raise ValueError("A contração produziu uma matriz de massa inválida.")
        if initial_mass is None:
            initial_mass = mass
            weight = settings.contraction * 1000 * np.sqrt(mass.mean())
        else:
            if mass.mean() / initial_mass.mean() <= 0.003:
                break
            attraction = np.clip(attraction * np.sqrt(initial_mass / mass), 0.1, 1024)
            weight = np.clip(weight * 2.0, 0.1, 2048)
        # Solve the normal equations of ||w L X||² + ||W (X - points)||².
        attraction_sq = attraction**2
        system = weight**2 * (operator.T @ operator) + diags(attraction_sq)
        points = spsolve(system.tocsc(), attraction_sq[:, None] * points)
        if not np.isfinite(points).all():
            raise ValueError("A contração laplaciana não produziu coordenadas finitas.")
        completed += 1
    return points, completed


def _reduced_nodes(points, spacing):
    cells = np.floor((points - points.min(axis=0)) / spacing)
    _, inverse, counts = np.unique(cells, axis=0, return_inverse=True, return_counts=True)
    sums = np.column_stack([np.bincount(inverse, weights=axis) for axis in points.T])
    return sums / counts[:, None]


def _tree(nodes, neighbours):
    if len(nodes) < 2:
        raise ValueError("A linha central colapsou em menos de dois nós; reveja a escala da contração.")
    count = min(neighbours + 1, len(nodes))
    distances, indices = cKDTree(nodes).query(nodes, k=count)
    graph = csr_matrix(
        (distances[:, 1:].ravel(), (np.repeat(np.arange(len(nodes)), count - 1), indices[:, 1:].ravel())),
        shape=(len(nodes), len(nodes)),
    )
    tree = minimum_spanning_tree(graph).tocoo()
    if not tree.nnz:
        raise ValueError("A linha central não contém arestas válidas.")
    components, _ = connected_components(tree, directed=False)
    edges = np.column_stack((tree.row, tree.col))
    return edges, components


def generate_centreline(
    batches: Iterable[np.ndarray], source_offset: np.ndarray, output: Path, settings: ExtractionSettings
) -> dict:
    """Save an estimated graph in original XYZ and return its provenance."""
    try:
        from robust_laplacian import point_cloud_laplacian
    except ImportError as error:
        raise ValueError(
            "Para estimar a linha central, instale o extra local: uv sync --locked --extra centreline."
        ) from error

    points, anchor, spacing, total = _sample(batches, settings)
    try:
        contracted, iterations = _contract(points, settings, point_cloud_laplacian)
    except RuntimeError as error:
        raise ValueError(f"A contração laplaciana falhou: {error}") from error
    nodes = _reduced_nodes(contracted, settings.node_spacing)
    edges, components = _tree(nodes, settings.graph_neighbours)
    with output.open("xb") as stream:
        np.savez_compressed(stream, nodes_xyz=nodes + (source_offset + anchor), edges=edges)
    return {
        "method": "laplacian_contraction_sparse_mst",
        "status": "pending_review",
        "parameters": asdict(settings),
        "points_read": total,
        "sample_points": len(points),
        "effective_sample_spacing": spacing,
        "iterations_completed": iterations,
        "nodes": len(nodes),
        "edges": len(edges),
        "components": components,
        "max_edge_length": float(np.linalg.norm(nodes[edges[:, 0]] - nodes[edges[:, 1]], axis=1).max()),
        "versions": {"robust-laplacian": version("robust-laplacian"), "numpy": version("numpy"),
                     "scipy": version("scipy")},
    }
