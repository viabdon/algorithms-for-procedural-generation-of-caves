"""Read cave centreline graphs and locate points along unbranched passages."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def read_graph(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read an Elaphes NPZ or a Racine nodes/link table pair."""
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as data:
            nodes, edges = data["nodes_xyz"], data["edges"]
    elif path.name.endswith("_nodes_from_LBC.txt"):
        links = path.with_name(path.name.replace("_nodes_from_LBC.txt", "_links_from_LBC.txt"))
        nodes = np.loadtxt(path, dtype=np.float64, ndmin=2)
        edges = np.loadtxt(links, dtype=np.int64, ndmin=2)
    else:
        raise ValueError("Informe um NPZ de linha central ou o arquivo *_nodes_from_LBC.txt.")
    if (
        nodes.ndim != 2 or nodes.shape[1] != 3 or not np.isfinite(nodes).all()
        or edges.ndim != 2 or edges.shape[1] != 2 or not len(edges)
        or not np.issubdtype(edges.dtype, np.integer)
        or np.any(edges < 0) or np.any(edges >= len(nodes))
    ):
        raise ValueError("Grafo inválido: esperados nós XYZ finitos e arestas por índice.")
    if np.any(np.all(nodes[edges[:, 0]] == nodes[edges[:, 1]], axis=1)):
        raise ValueError("O grafo contém aresta de comprimento zero.")
    return nodes.astype(np.float64, copy=False), edges


@dataclass(frozen=True)
class Passage:
    xyz: np.ndarray
    stations: np.ndarray
    junctions: tuple[bool, bool]

    def at(self, stations):
        return np.stack([np.interp(stations, self.stations, axis) for axis in self.xyz.T], axis=-1)


def passages_from_graph(nodes: np.ndarray, edges: np.ndarray) -> list[Passage]:
    """Walk from leaves or junctions through chains of degree-two nodes."""
    neighbours = [set() for _ in nodes]
    unused = {tuple(sorted((int(a), int(b)))) for a, b in edges}
    for a, b in unused:
        neighbours[a].add(b)
        neighbours[b].add(a)
    passages = []
    for start, adjacent in enumerate(neighbours):
        if len(adjacent) == 2:
            continue
        for next_node in sorted(adjacent):
            path = [start]
            while (edge := tuple(sorted((path[-1], next_node)))) in unused:
                unused.remove(edge)
                path.append(next_node)
                if len(neighbours[next_node]) != 2:
                    break
                next_node = next(iter(neighbours[next_node] - {path[-2]}))
            if len(path) > 1:
                xyz = nodes[path]
                stations = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(xyz, axis=0), axis=1))]
                passages.append(Passage(xyz, stations, (len(adjacent) > 2, len(neighbours[path[-1]]) > 2)))
    if unused or not passages:
        raise ValueError("O planejamento exige uma linha central em árvore, sem laços fechados.")
    return passages


class CentrelineIndex:
    """Index sampled graph edges, then project onto the winning edge."""

    def __init__(self, passages: list[Passage], spacing: float):
        centers, starts, directions, lengths, stations, owners = [], [], [], [], [], []
        sample_stations = []
        for owner, path in enumerate(passages):
            starts_xyz = path.xyz[:-1]
            length = np.diff(path.stations)
            direction = np.diff(path.xyz, axis=0) / length[:, None]
            count = np.ceil(length / spacing).astype(int)
            edge = np.repeat(np.arange(len(length)), count)
            preceding = np.repeat(np.r_[0, np.cumsum(count[:-1])], count)
            along = (np.arange(len(edge)) - preceding + 0.5) * (length / count)[edge]
            centers.append(starts_xyz[edge] + along[:, None] * direction[edge])
            starts.append(starts_xyz[edge])
            directions.append(direction[edge])
            lengths.append(length[edge])
            stations.append(path.stations[:-1][edge])
            sample_stations.append(stations[-1] + along)
            owners.append(np.full(len(edge), owner, dtype=int))
        self.tree = cKDTree(np.concatenate(centers))
        self.starts = np.concatenate(starts)
        self.directions = np.concatenate(directions)
        self.lengths = np.concatenate(lengths)
        self.stations = np.concatenate(stations)
        self.sample_stations = np.concatenate(sample_stations)
        self.owners = np.concatenate(owners)
        self.spacing = spacing

    def locate(self, xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _, nearest = self.tree.query(xyz)
        offset = xyz - self.starts[nearest]
        direction = self.directions[nearest]
        along = np.clip(np.einsum("ij,ij->i", offset, direction), 0, self.lengths[nearest])
        distance = np.linalg.norm(offset - along[:, None] * direction, axis=1)
        return self.owners[nearest], self.stations[nearest] + along, distance

    def has_nearby_passage(self, path: Passage, owner: int, cuts: tuple[float, float], radius: float):
        # A remote portion of the same curve can be spatially close in a U.
        positions = np.linspace(*cuts, num=17)
        for station, point in zip(positions, path.at(positions)):
            neighbours = self.tree.query_ball_point(point, 2 * radius + self.spacing)
            if any(
                self.owners[i] != owner or abs(self.sample_stations[i] - station) > 3 * radius
                for i in neighbours
            ):
                return True
        return False
