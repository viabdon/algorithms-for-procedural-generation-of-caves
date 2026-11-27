"""Measured transverse sections and a bounded search between fixed centreline anchors."""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_fill_holes, distance_transform_edt, label
from scipy.spatial import cKDTree

from cavegen.datastream.centreline import Passage
from cavegen.datastream.crop_planner import _section_frame

SECTION_RADIUS = 32
MAX_SHIFT = 8
MAX_CANDIDATES = 4
MAX_DISTANCE = 58
MAX_STEP = 4


@dataclass(frozen=True)
class Centre:
    xyz: np.ndarray
    clearance: float
    shift: float
    region: int = 0


def _crossings(vertices, wall, size):
    cells = set()
    for start, end in zip(vertices[:-1], vertices[1:]):
        count = max(1, int(np.ceil(4 * np.linalg.norm(end - start) / size)))
        samples = np.linspace(start, end, count + 1)
        occupied = np.floor(samples[:, ::-1] / size).astype(int)
        cells.update(wall.intersection(map(tuple, occupied)))
    return cells


def _section_centres(line, station, points, tree, size):
    frame = _section_frame(line, station, size)
    if frame is None:
        return None, []
    point, normal, u = frame
    radius = SECTION_RADIUS * size
    nearby = tree.query_ball_point(point, np.hypot(radius, size))
    relative = points[nearby] - point
    basis = np.column_stack((u, np.cross(normal, u)))
    uv = relative[abs(relative @ normal) <= size] @ basis
    cells = np.floor(uv / size + .5).astype(int)
    cells = cells[np.all(abs(cells) <= SECTION_RADIUS, axis=1)] + SECTION_RADIUS
    wall = np.zeros((2 * SECTION_RADIUS + 1,) * 2, dtype=bool)
    wall[tuple(cells[:, ::-1].T)] = True
    labels, count = label(binary_fill_holes(wall) & ~wall)
    clearance = distance_transform_edt(labels > 0) * size
    middle = (SECTION_RADIUS, SECTION_RADIUS)
    anchor = Centre(point, float(clearance[middle]), 0.) if clearance[middle] >= 2 * size else None
    regions = []
    for component in range(1, count + 1):
        cells = np.argwhere(labels == component)
        uv = (cells[:, ::-1] - SECTION_RADIUS) * size
        shifts = np.linalg.norm(uv, axis=1)
        depth = clearance[tuple(cells.T)]
        eligible = np.flatnonzero((shifts <= MAX_SHIFT * size) & (depth >= 2 * size))
        if len(eligible):
            deepest = eligible[np.lexsort((shifts[eligible], -depth[eligible]))[0]]
            nearest = eligible[np.lexsort((-depth[eligible], shifts[eligible]))[0]]
            regions.append([
                Centre(point + basis @ uv[i], float(depth[i]), float(shifts[i]), component)
                for i in dict.fromkeys((nearest, deepest))
            ])
    regions.sort(key=lambda candidates: (candidates[0].shift, -candidates[0].clearance))
    return anchor, [centre for region in regions[:MAX_CANDIDATES] for centre in region]


def _paths(layers, wall, size):
    """Keep the two lowest-cost distinct region sequences per vertex."""
    scores = [[(0., (0,), (0,))]]
    for previous, current in zip(layers, layers[1:]):
        next_scores = []
        for j, centre in enumerate(current):
            candidates = {}
            for i, neighbour in enumerate(previous):
                if not scores[i]:
                    continue
                edge = np.vstack((neighbour.xyz, centre.xyz))
                distance = np.linalg.norm(centre.xyz - neighbour.xyz)
                if distance > MAX_STEP * size or _crossings(edge, wall, size):
                    continue
                cost = distance + centre.shift / 4 + size**2 / (4 * centre.clearance)
                for score, path, regions in scores[i]:
                    signature = (*regions, centre.region)
                    choice = (score + cost, (*path, j), signature)
                    if signature not in candidates or choice < candidates[signature]:
                        candidates[signature] = choice
            next_scores.append(sorted(candidates.values())[:2])
        scores = next_scores
    return scores[0]


def recenter_passage(line, tip, points, wall, size, *, tree=None):
    """Return a locally repaired passage or keep the original when support is ambiguous."""
    length = line.stations[-1]
    extent = min(length, MAX_DISTANCE * size)
    distance = np.unique(np.r_[np.arange(0, extent, size), extent])
    along = distance if tip == 0 else length - distance
    vertices = line.at(along)
    hits = [_crossings(vertices[i:i + 2], wall, size) for i in range(len(vertices) - 1)]
    faulty = [i for i, hit in enumerate(hits) if hit]
    if not faulty:
        return line, {"resultado": "eixo_sem_cruzamento"}

    before = len(set().union(*hits))
    report = {"voxels_de_parede_antes": before}
    if tree is None:
        tree = cKDTree(points)

    sections = [_section_centres(line, station, points, tree, size) for station in along]
    left = next((i for i in range(faulty[0], -1, -1) if sections[i][0] is not None), None)
    right = next((i for i in range(faulty[-1] + 1, len(sections)) if sections[i][0] is not None), None)
    if left is None or right is None:
        return line, {**report, "resultado": "sem_duas_ancoras", "ancora_antes": left is not None,
                      "ancora_depois": right is not None}
    report["ancoras_do_no_m"] = [float(distance[left]), float(distance[right])]
    layers = [[sections[left][0]], *(candidates for _, candidates in sections[left + 1:right]),
              [sections[right][0]]]
    if not all(layers):
        return line, {**report, "resultado": "fatia_sem_interior_sustentado",
                      "fatias_sem_candidata": sum(not layer for layer in layers)}
    paths = _paths(layers, wall, size)
    if not paths:
        return line, {**report, "resultado": "sem_caminho_entre_ancoras"}
    if len(paths) > 1 and paths[1][0] - paths[0][0] <= size / 2:
        return line, {**report, "resultado": "trajetorias_ambiguas"}
    chosen = [layer[i] for layer, i in zip(layers, paths[0][1])]
    corrected = np.array([c.xyz for c in chosen])
    if tip:
        corrected = corrected[::-1]
    lower, upper = sorted(along[[left, right]])
    xyz = np.vstack((line.xyz[line.stations < lower], corrected, line.xyz[line.stations > upper]))
    lengths = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    if np.any(lengths <= 0):
        return line, {**report, "resultado": "eixo_degenerado"}
    passage = Passage(xyz, np.r_[0., np.cumsum(lengths)], line.junctions)
    return passage, {**report, "resultado": "eixo_recentrado",
                     "voxels_de_parede_no_ajuste": len(_crossings(corrected, wall, size)),
                     "maior_deslocamento_m": max(c.shift for c in chosen)}
