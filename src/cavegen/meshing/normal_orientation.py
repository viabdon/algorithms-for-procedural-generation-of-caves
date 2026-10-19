"""Experimental centreline-assisted normal orientation with point-level review.

Validated interior references support the original patch-voting path. A separate
cosine path makes provisional proposals directly from the centreline geometry.
The graph remains a hypothesis, not an interior/exterior classification or a
source of SDF signs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


REASON_NO_BRANCH = 1
REASON_BRANCH_AMBIGUOUS = 2
REASON_JUNCTION = 4
REASON_NO_REFERENCE = 8
REASON_TANGENT_REFERENCE = 16
REASON_REFERENCE_CONFLICT = 32
REASON_PATCH_UNDECIDED = 64
REASON_PATCH_CONFLICT = 128
REASON_LOW_NORMAL_QUALITY = 256
REASON_MANUAL = 512
REASON_COSINE_BELOW_THRESHOLD = 1024
REASON_COSINE_CONFLICT = 2048
REASON_CENTRELINE_PROVISIONAL = 4096
REASON_ZERO_RADIAL = 8192
REASONS = {
    REASON_NO_BRANCH: "sem_ramo_plausivel",
    REASON_BRANCH_AMBIGUOUS: "ramos_proximos",
    REASON_JUNCTION: "perto_de_bifurcacao",
    REASON_NO_REFERENCE: "sem_referencia_validada",
    REASON_TANGENT_REFERENCE: "referencia_quase_tangente",
    REASON_REFERENCE_CONFLICT: "referencias_discordam",
    REASON_PATCH_UNDECIDED: "trecho_sem_consenso",
    REASON_PATCH_CONFLICT: "voto_local_contraria_trecho",
    REASON_LOW_NORMAL_QUALITY: "normal_local_instavel",
    REASON_MANUAL: "sentido_revisado_manualmente",
    REASON_COSINE_BELOW_THRESHOLD: "cosseno_abaixo_do_limiar",
    REASON_COSINE_CONFLICT: "cossenos_de_ramos_discordam",
    REASON_CENTRELINE_PROVISIONAL: "linha_central_sem_interior_validado",
    REASON_ZERO_RADIAL: "vetor_linha_parede_nulo",
}


@dataclass(frozen=True)
class Parameters:
    normal_neighbors: int = 30
    orientation_neighbors: int = 30
    max_branch_cost: float = 2.5
    ambiguity_margin: float = 0.15
    junction_radius_factor: float = 1.0
    max_reference_span_factor: float = 3.0
    min_reference_projection: float = 0.25
    max_surface_variation: float = 0.15
    surface_neighbors: int = 8
    max_neighbor_spacing_factor: float = 3.0
    min_neighbor_normal_alignment: float = 0.8
    max_neighbor_normal_offset: float = 0.4
    min_patch_votes: int = 3
    min_patch_agreement: float = 0.8

    def validate(self) -> None:
        if self.normal_neighbors < 3 or self.orientation_neighbors < 3:
            raise ValueError("normal-neighbor counts must be at least three")
        if self.surface_neighbors < 1 or self.min_patch_votes < 1:
            raise ValueError("surface_neighbors and min_patch_votes must be positive")
        for name in ("max_branch_cost", "junction_radius_factor", "max_reference_span_factor",
                     "max_neighbor_spacing_factor"):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive and finite")
        for name in ("ambiguity_margin", "min_reference_projection", "max_surface_variation",
                     "min_neighbor_normal_alignment", "max_neighbor_normal_offset",
                     "min_patch_agreement"):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True)
class Branch:
    nodes: np.ndarray
    edges: np.ndarray
    arc: np.ndarray


def _xyz(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or not len(array) or not np.isfinite(array).all():
        raise ValueError(f"{name} must contain finite XYZ rows")
    return array


def points_sha256(points_xyz: np.ndarray) -> str:
    """Stable identity for ordered XYZ samples, independent of float32/64 input."""
    points = np.ascontiguousarray(_xyz(points_xyz, "points_xyz"), dtype="<f8")
    digest = hashlib.sha256()
    digest.update(np.asarray(points.shape, dtype="<i8").tobytes())
    digest.update(points.tobytes())
    return digest.hexdigest()


def graph_sha256(nodes_xyz: np.ndarray, edges: np.ndarray) -> str:
    nodes = _xyz(nodes_xyz, "nodes_xyz")
    links = np.asarray(edges, dtype=np.int64)
    digest = hashlib.sha256()
    digest.update(points_sha256(nodes).encode("ascii"))
    digest.update(np.asarray(links.shape, dtype="<i8").tobytes())
    digest.update(np.ascontiguousarray(links, dtype="<i8").tobytes())
    return digest.hexdigest()


def split_branches(nodes_xyz: np.ndarray, edges: np.ndarray) -> tuple[list[Branch], np.ndarray]:
    """Split a connected centreline tree at endpoints and junctions."""
    nodes = _xyz(nodes_xyz, "nodes_xyz")
    if len(nodes) < 2:
        raise ValueError("centreline must contain at least two nodes")
    links = np.asarray(edges)
    if links.ndim != 2 or links.shape[1] != 2 or len(links) != len(nodes) - 1:
        raise ValueError("centreline must be a connected tree with N-1 edges")
    if not np.issubdtype(links.dtype, np.integer) or np.any(links < 0) or np.any(links >= len(nodes)):
        raise ValueError("centreline edges must contain valid node indices")
    if np.any(links[:, 0] == links[:, 1]):
        raise ValueError("centreline cannot contain self edges")
    adjacency: list[list[tuple[int, int]]] = [[] for _ in nodes]
    for edge_id, (a, b) in enumerate(links):
        adjacency[int(a)].append((int(b), edge_id))
        adjacency[int(b)].append((int(a), edge_id))
    seen_nodes = {0}
    pending = [0]
    while pending:
        for neighbor, _ in adjacency[pending.pop()]:
            if neighbor not in seen_nodes:
                seen_nodes.add(neighbor)
                pending.append(neighbor)
    if len(seen_nodes) != len(nodes):
        raise ValueError("centreline graph is disconnected or cyclic")
    degrees = np.asarray([len(row) for row in adjacency])
    visited_edges: set[int] = set()
    branches: list[Branch] = []
    for start in np.flatnonzero(degrees != 2):
        for neighbor, first_edge in adjacency[int(start)]:
            if first_edge in visited_edges:
                continue
            path_nodes = [int(start), neighbor]
            path_edges = [first_edge]
            visited_edges.add(first_edge)
            previous, current = int(start), neighbor
            while degrees[current] == 2:
                following = [(n, e) for n, e in adjacency[current] if n != previous]
                next_node, next_edge = following[0]
                path_nodes.append(next_node)
                path_edges.append(next_edge)
                visited_edges.add(next_edge)
                previous, current = current, next_node
            positions = nodes[path_nodes]
            arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(positions, axis=0), axis=1))]
            if np.any(np.diff(arc) <= 0):
                raise ValueError("centreline has zero-length edges")
            branches.append(Branch(np.asarray(path_nodes), np.asarray(path_edges), arc))
    if len(visited_edges) != len(links):
        raise ValueError("centreline contains an unassigned cycle")
    return branches, np.flatnonzero(degrees >= 3)


def _node_radii(points: np.ndarray, nodes: np.ndarray) -> tuple[np.ndarray, float]:
    tree = cKDTree(points)
    distances, _ = tree.query(nodes, k=min(7, len(points)))
    distances = np.atleast_2d(distances)
    if distances.shape[0] != len(nodes):
        distances = distances.T
    radii = np.median(distances, axis=1)
    point_distances, _ = tree.query(points, k=min(2, len(points)))
    spacing = point_distances[:, -1] if point_distances.ndim == 2 else point_distances
    positive = spacing[spacing > 0]
    radius_floor = float(np.median(positive)) if len(positive) else 1e-6
    return np.maximum(radii, radius_floor), radius_floor


def associate_points(
    points_xyz: np.ndarray, nodes_xyz: np.ndarray, edges: np.ndarray,
    *, params: Parameters = Parameters(), chunk_size: int = 2048,
) -> dict[str, np.ndarray | list[Branch]]:
    """Find up to two branch candidates using distance / local radius proxy."""
    params.validate()
    points = _xyz(points_xyz, "points_xyz")
    nodes = _xyz(nodes_xyz, "nodes_xyz")
    branches, junction_nodes = split_branches(nodes, edges)
    links = np.asarray(edges, dtype=np.int64)
    radii, _ = _node_radii(points, nodes)
    count = len(points)
    branch_count = len(branches)
    costs = np.full((count, branch_count), np.inf)
    chosen_edges = np.full((count, branch_count), -1, dtype=np.int32)
    arc_positions = np.full((count, branch_count), np.nan)
    projected_radii = np.full((count, branch_count), np.nan)
    projected_xyz = np.full((count, branch_count, 3), np.nan)
    for branch_id, branch in enumerate(branches):
        branch_edges = links[branch.edges]
        starts = nodes[branch_edges[:, 0]]
        vectors = nodes[branch_edges[:, 1]] - starts
        lengths_squared = np.einsum("ij,ij->i", vectors, vectors)
        for begin in range(0, count, chunk_size):
            end = min(begin + chunk_size, count)
            query = points[begin:end, None, :] - starts[None, :, :]
            fractions = np.clip(np.einsum("ijk,jk->ij", query, vectors) / lengths_squared, 0, 1)
            projections = starts[None, :, :] + fractions[:, :, None] * vectors[None, :, :]
            distances = np.linalg.norm(points[begin:end, None, :] - projections, axis=2)
            local_radii = (1 - fractions) * radii[branch_edges[:, 0]] + fractions * radii[branch_edges[:, 1]]
            normalized = distances / local_radii
            row = np.arange(end - begin)
            local_index = np.argmin(normalized, axis=1)
            edge_id = branch.edges[local_index]
            fraction = fractions[row, local_index]
            path_start = branch.nodes[local_index]
            forward = links[edge_id, 0] == path_start
            path_fraction = np.where(forward, fraction, 1 - fraction)
            costs[begin:end, branch_id] = normalized[row, local_index]
            chosen_edges[begin:end, branch_id] = edge_id
            arc_positions[begin:end, branch_id] = (
                branch.arc[local_index] + path_fraction * np.diff(branch.arc)[local_index]
            )
            projected_radii[begin:end, branch_id] = local_radii[row, local_index]
            projected_xyz[begin:end, branch_id] = projections[row, local_index]
    ranked = np.argsort(costs, axis=1)
    row = np.arange(count)
    first = ranked[:, 0]
    first_cost = costs[row, first]
    valid_first = first_cost <= params.max_branch_cost
    if branch_count > 1:
        second = ranked[:, 1]
        second_cost = costs[row, second]
        margin = (second_cost - first_cost) / np.maximum(second_cost, 1e-12)
        ambiguous = valid_first & (second_cost <= params.max_branch_cost) & (
            margin <= params.ambiguity_margin
        )
    else:
        second = np.full(count, -1, dtype=int)
        second_cost = np.full(count, np.inf)
        margin = np.ones(count)
        ambiguous = np.zeros(count, dtype=bool)
    near_junction = np.zeros(count, dtype=bool)
    if len(junction_nodes):
        distance_to_junction, junction_index = cKDTree(nodes[junction_nodes]).query(points)
        near_junction = distance_to_junction <= (
            params.junction_radius_factor * radii[junction_nodes[junction_index]]
        )
    second_valid = valid_first & (ambiguous | near_junction) & (
        second_cost <= params.max_branch_cost
    )
    candidates = np.column_stack((np.where(valid_first, first, -1), np.where(second_valid, second, -1)))
    candidate_arc = np.full((count, 2), np.nan)
    candidate_radius = np.full((count, 2), np.nan)
    candidate_xyz = np.full((count, 2, 3), np.nan)
    candidate_edges = np.full((count, 2), -1, dtype=np.int32)
    for slot in range(2):
        valid = candidates[:, slot] >= 0
        candidate_arc[valid, slot] = arc_positions[row[valid], candidates[valid, slot]]
        candidate_radius[valid, slot] = projected_radii[row[valid], candidates[valid, slot]]
        candidate_xyz[valid, slot] = projected_xyz[row[valid], candidates[valid, slot]]
        candidate_edges[valid, slot] = chosen_edges[row[valid], candidates[valid, slot]]
    return {
        "branches": branches,
        "junction_nodes": junction_nodes,
        "node_radii": radii,
        "candidate_branches": candidates.astype(np.int32),
        "candidate_arc": candidate_arc,
        "candidate_radius": candidate_radius,
        "candidate_projection_xyz": candidate_xyz,
        "candidate_edges": candidate_edges,
        "best_cost": first_cost,
        "second_cost": second_cost,
        "cost_margin": margin,
        "branch_ambiguous": ambiguous,
        "near_junction": near_junction,
        "best_edge": np.where(valid_first, chosen_edges[row, first], -1),
    }


def estimate_baseline_normals(points_xyz: np.ndarray, params: Parameters) -> np.ndarray:
    """Use the same Open3D estimation and tangent-plane orientation as Poisson."""
    params.validate()
    try:
        import open3d as o3d
    except ImportError as error:
        raise RuntimeError("install the reconstruction extra to estimate normals") from error
    points = _xyz(points_xyz, "points_xyz")
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=params.normal_neighbors))
    cloud.orient_normals_consistent_tangent_plane(params.orientation_neighbors)
    return np.asarray(cloud.normals).copy()


def _normal_quality(points: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    _, indices = cKDTree(points).query(points, k=min(k, len(points)))
    neighbors = points[np.atleast_2d(indices).reshape(len(points), -1)]
    centered = neighbors - neighbors.mean(axis=1, keepdims=True)
    covariance = np.einsum("nik,nil->nkl", centered, centered) / neighbors.shape[1]
    eigenvalues = np.linalg.eigvalsh(covariance)
    variation = eigenvalues[:, 0] / np.maximum(eigenvalues.sum(axis=1), 1e-12)
    second_axis = eigenvalues[:, 1] / np.maximum(eigenvalues[:, 2], 1e-12)
    return variation, second_axis


def _surface_patches(
    points: np.ndarray, normals: np.ndarray, candidates: np.ndarray, params: Parameters,
) -> np.ndarray:
    if len(points) == 1:
        return np.zeros(1, dtype=np.int32)
    distances, indices = cKDTree(points).query(points, k=min(len(points), params.surface_neighbors + 1))
    spacing = distances[:, 1]
    positive = spacing[spacing > 0]
    fallback = float(np.median(positive)) if len(positive) else 1e-6
    spacing = np.where(spacing > 0, spacing, fallback)
    cap = float(np.percentile(spacing, 95)) * params.max_neighbor_spacing_factor
    left = np.repeat(np.arange(len(points)), indices.shape[1] - 1)
    right = indices[:, 1:].reshape(-1)
    distance = distances[:, 1:].reshape(-1)
    offset = points[right] - points[left]
    norm_offset = np.maximum(distance, 1e-12)
    # A patch votes on the sign of its baseline normals. Opposite baseline
    # directions must not share one sign decision even on the same wall.
    aligned = np.einsum("ij,ij->i", normals[left], normals[right])
    tangent_left = np.abs(np.einsum("ij,ij->i", normals[left], offset)) / norm_offset
    tangent_right = np.abs(np.einsum("ij,ij->i", normals[right], offset)) / norm_offset
    related_branches = (
        (candidates[left, :, None] == candidates[right, None, :])
        & (candidates[left, :, None] >= 0)
    ).any(axis=(1, 2))
    safe = (
        (left != right) & (distance > 0) & (distance <= cap)
        & (distance <= params.max_neighbor_spacing_factor * np.maximum(spacing[left], spacing[right]))
        & (aligned >= params.min_neighbor_normal_alignment)
        & (tangent_left <= params.max_neighbor_normal_offset)
        & (tangent_right <= params.max_neighbor_normal_offset)
        & related_branches
    )
    adjacency = coo_matrix(
        (np.ones(np.count_nonzero(safe), dtype=np.int8), (left[safe], right[safe])),
        shape=(len(points), len(points)),
    ).tocsr()
    _, labels = connected_components(adjacency, directed=False)
    return labels.astype(np.int32)


def orient_from_references(
    points_xyz: np.ndarray, baseline_normals_xyz: np.ndarray,
    nodes_xyz: np.ndarray, edges: np.ndarray, validated_node_indices: list[int] | np.ndarray,
    *, params: Parameters = Parameters(),
) -> dict[str, np.ndarray]:
    """Vote for signs within coherent surface patches; preserve uncertain IDs."""
    params.validate()
    points = _xyz(points_xyz, "points_xyz")
    nodes = _xyz(nodes_xyz, "nodes_xyz")
    normals = _xyz(baseline_normals_xyz, "baseline_normals_xyz")
    if len(normals) != len(points):
        raise ValueError("baseline normals must align with ordered sample points")
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths < 1e-8):
        raise ValueError("baseline normals cannot contain zero vectors")
    normals = normals / lengths[:, None]
    raw_references = np.asarray(validated_node_indices)
    if not np.issubdtype(raw_references.dtype, np.integer):
        if raw_references.size:
            raise ValueError("validated references must be integer node indices")
        references = np.asarray([], dtype=np.int64)
    else:
        references = raw_references.astype(np.int64)
    if references.ndim != 1 or np.any(references < 0) or np.any(references >= len(nodes)):
        raise ValueError("validated references must be valid node indices")
    if len(np.unique(references)) != len(references):
        raise ValueError("validated references cannot repeat a node")
    association = associate_points(points, nodes, edges, params=params)
    candidates = association["candidate_branches"]
    arcs = association["candidate_arc"]
    radii = association["candidate_radius"]
    branches: list[Branch] = association["branches"]
    votes = np.zeros((len(points), 2))
    vote_reference = np.full((len(points), 2), -1, dtype=np.int32)
    missing = np.zeros((len(points), 2), dtype=bool)
    tangent = np.zeros((len(points), 2), dtype=bool)
    for branch_id, branch in enumerate(branches):
        branch_references = [int(node) for node in references if node in branch.nodes]
        if not branch_references:
            missing[candidates == branch_id] = True
            continue
        position_by_node = {int(node): float(branch.arc[i]) for i, node in enumerate(branch.nodes)}
        ref_nodes = np.asarray(sorted(branch_references, key=position_by_node.get), dtype=np.int32)
        ref_arc = np.asarray([position_by_node[int(node)] for node in ref_nodes])
        for slot in range(2):
            selected = np.flatnonzero(candidates[:, slot] == branch_id)
            if not len(selected):
                continue
            target = arcs[selected, slot]
            insertion = np.searchsorted(ref_arc, target)
            left = np.clip(insertion - 1, 0, len(ref_arc) - 1)
            right = np.clip(insertion, 0, len(ref_arc) - 1)
            choice = np.where(np.abs(target - ref_arc[left]) <= np.abs(target - ref_arc[right]), left, right)
            ref = ref_nodes[choice]
            span = np.abs(target - ref_arc[choice])
            vector = points[selected] - nodes[ref]
            length = np.linalg.norm(vector, axis=1)
            valid = (length > 1e-8) & (span <= params.max_reference_span_factor * radii[selected, slot])
            projection = np.einsum("ij,ij->i", normals[selected], vector) / np.maximum(length, 1e-12)
            strong = valid & (np.abs(projection) >= params.min_reference_projection)
            votes[selected[strong], slot] = projection[strong]
            vote_reference[selected[strong], slot] = ref[strong]
            missing[selected[~valid], slot] = True
            tangent[selected[valid & ~strong], slot] = True
    variation, second_axis = _normal_quality(points, params.normal_neighbors)
    low_quality = (variation > params.max_surface_variation) | (second_axis < 0.05)
    both = candidates[:, 1] >= 0
    first_valid = votes[:, 0] != 0
    second_valid = votes[:, 1] != 0
    reference_conflict = both & first_valid & second_valid & (np.sign(votes[:, 0]) != np.sign(votes[:, 1]))
    complete_vote = first_valid & (~both | second_valid) & ~reference_conflict & ~low_quality
    local_sign = np.zeros(len(points), dtype=np.int8)
    local_sign[complete_vote] = np.sign(votes[complete_vote, 0]).astype(np.int8)
    local_strength = np.where(both, (np.abs(votes[:, 0]) + np.abs(votes[:, 1])) / 2,
                              np.abs(votes[:, 0]))
    local_strength[~complete_vote] = 0
    patches = _surface_patches(points, normals, candidates, params)
    patch_count = int(patches.max()) + 1
    positive = np.bincount(patches[local_sign > 0], weights=local_strength[local_sign > 0], minlength=patch_count)
    negative = np.bincount(patches[local_sign < 0], weights=local_strength[local_sign < 0], minlength=patch_count)
    counts = np.bincount(patches[local_sign != 0], minlength=patch_count)
    agreement = np.maximum(positive, negative) / np.maximum(positive + negative, 1e-12)
    patch_sign = np.zeros(patch_count, dtype=np.int8)
    decided = (counts >= params.min_patch_votes) & (agreement >= params.min_patch_agreement)
    patch_sign[decided] = np.where(positive[decided] >= negative[decided], 1, -1)
    point_patch_sign = patch_sign[patches]
    patch_conflict = (local_sign != 0) & (point_patch_sign != 0) & (local_sign != point_patch_sign)
    # A distant point cannot inherit a sign just because a connected patch
    # contains a few votes elsewhere. Consensus filters local evidence; it
    # does not replace a direct, sufficiently close reference vote.
    uncertain = (point_patch_sign == 0) | (local_sign == 0) | reference_conflict | patch_conflict
    oriented = normals * np.where(uncertain, 1, point_patch_sign)[:, None]
    reasons = np.zeros(len(points), dtype=np.uint16)
    reasons[candidates[:, 0] < 0] |= REASON_NO_BRANCH
    reasons[association["branch_ambiguous"]] |= REASON_BRANCH_AMBIGUOUS
    reasons[association["near_junction"]] |= REASON_JUNCTION
    reasons[(candidates[:, 0] >= 0) & ((~first_valid) | (both & ~second_valid)) & missing.any(axis=1)] |= REASON_NO_REFERENCE
    reasons[tangent.any(axis=1)] |= REASON_TANGENT_REFERENCE
    reasons[reference_conflict] |= REASON_REFERENCE_CONFLICT
    reasons[point_patch_sign == 0] |= REASON_PATCH_UNDECIDED
    reasons[patch_conflict] |= REASON_PATCH_CONFLICT
    reasons[low_quality] |= REASON_LOW_NORMAL_QUALITY
    return {
        "points_xyz": points,
        "baseline_normals_xyz": normals,
        "oriented_normals_xyz": oriented,
        "uncertain_mask": uncertain,
        "uncertain_indices": np.flatnonzero(uncertain).astype(np.int64),
        "manual_mask": np.zeros(len(points), dtype=bool),
        "reason_bits": reasons,
        "candidate_branches": candidates,
        "best_edge": association["best_edge"].astype(np.int32),
        "best_cost": association["best_cost"],
        "second_cost": association["second_cost"],
        "cost_margin": association["cost_margin"],
        "patch_id": patches,
        "local_vote": local_sign,
        "patch_sign": point_patch_sign,
        "vote_reference_nodes": vote_reference,
        "surface_variation": variation,
        "second_tangent_axis_ratio": second_axis,
    }


def orient_by_centreline_cosine(
    points_xyz: np.ndarray, baseline_normals_xyz: np.ndarray,
    nodes_xyz: np.ndarray, edges: np.ndarray, threshold: float,
    *, params: Parameters = Parameters(),
) -> dict[str, np.ndarray]:
    """Propose signs from local centreline-to-wall vectors, without claiming interior validation.

    Each candidate uses the closest point on its branch edge, not an arbitrarily
    distant node. Near junctions remain uncertain; two plausible branches must
    each pass the threshold with the same sign.
    """
    params.validate()
    if not np.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("cosine threshold must be finite and in (0, 1]")
    points = _xyz(points_xyz, "points_xyz")
    normals = _xyz(baseline_normals_xyz, "baseline_normals_xyz")
    if len(normals) != len(points):
        raise ValueError("baseline normals must align with ordered sample points")
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths < 1e-8):
        raise ValueError("baseline normals cannot contain zero vectors")
    normals = normals / lengths[:, None]
    association = associate_points(points, nodes_xyz, edges, params=params)
    candidates = association["candidate_branches"]
    projection_xyz = association["candidate_projection_xyz"]
    radial = points[:, None, :] - projection_xyz
    radial_length = np.linalg.norm(radial, axis=2)
    valid_vector = (candidates >= 0) & np.isfinite(radial_length) & (radial_length > 1e-8)
    cosines = np.full((len(points), 2), np.nan)
    cosines[valid_vector] = (
        np.einsum("nij,nj->ni", radial, normals)[valid_vector] / radial_length[valid_vector]
    )
    variation, second_axis = _normal_quality(points, params.normal_neighbors)
    low_quality = (variation > params.max_surface_variation) | (second_axis < 0.05)
    strong = valid_vector & (np.abs(cosines) >= threshold)
    both = candidates[:, 1] >= 0
    conflict = both & strong[:, 0] & strong[:, 1] & (np.sign(cosines[:, 0]) != np.sign(cosines[:, 1]))
    complete = strong[:, 0] & (~both | strong[:, 1]) & ~conflict
    decided = complete & ~association["near_junction"] & ~low_quality
    sign = np.zeros(len(points), dtype=np.int8)
    sign[decided] = np.sign(cosines[decided, 0]).astype(np.int8)
    oriented = normals * np.where(sign == 0, 1, sign)[:, None]
    reasons = np.full(len(points), REASON_CENTRELINE_PROVISIONAL, dtype=np.uint16)
    reasons[candidates[:, 0] < 0] |= REASON_NO_BRANCH
    reasons[association["branch_ambiguous"]] |= REASON_BRANCH_AMBIGUOUS
    reasons[association["near_junction"]] |= REASON_JUNCTION
    zero_radial = ((candidates >= 0) & ~valid_vector).any(axis=1)
    reasons[zero_radial] |= REASON_ZERO_RADIAL
    reasons[~complete & (candidates[:, 0] >= 0) & ~conflict & ~zero_radial] |= REASON_COSINE_BELOW_THRESHOLD
    reasons[conflict] |= REASON_COSINE_CONFLICT
    reasons[low_quality] |= REASON_LOW_NORMAL_QUALITY
    uncertain = ~decided
    return {
        "points_xyz": points,
        "baseline_normals_xyz": normals,
        "oriented_normals_xyz": oriented,
        "uncertain_mask": uncertain,
        "uncertain_indices": np.flatnonzero(uncertain).astype(np.int64),
        "manual_mask": np.zeros(len(points), dtype=bool),
        "reason_bits": reasons,
        "candidate_branches": candidates,
        "best_edge": association["best_edge"].astype(np.int32),
        "best_cost": association["best_cost"],
        "second_cost": association["second_cost"],
        "cost_margin": association["cost_margin"],
        "candidate_edges": association["candidate_edges"],
        "candidate_projection_xyz": projection_xyz,
        "candidate_cosines": cosines,
        "cosine_threshold": np.asarray(threshold, dtype=np.float64),
        "automatic_sign": sign,
        "surface_variation": variation,
        "second_tangent_axis_ratio": second_axis,
    }


def _review_sha256(result: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    digest.update(points_sha256(result["points_xyz"]).encode("ascii"))
    digest.update(np.ascontiguousarray(result["oriented_normals_xyz"], dtype="<f8").tobytes())
    digest.update(np.ascontiguousarray(result["uncertain_mask"], dtype=np.uint8).tobytes())
    digest.update(np.ascontiguousarray(result["candidate_branches"], dtype="<i4").tobytes())
    digest.update(np.ascontiguousarray(result["reason_bits"], dtype="<u2").tobytes())
    digest.update(np.ascontiguousarray(result["manual_mask"], dtype=np.uint8).tobytes())
    # Optional fields preserve compatibility with reviews made before the cosine experiment.
    for name, dtype in (("candidate_edges", "<i4"), ("candidate_projection_xyz", "<f8"),
                        ("candidate_cosines", "<f8"), ("cosine_threshold", "<f8"),
                        ("automatic_sign", np.int8)):
        if name in result:
            digest.update(name.encode("ascii"))
            digest.update(np.ascontiguousarray(result[name], dtype=dtype).tobytes())
    return digest.hexdigest()


def reason_names(bits: int) -> str:
    return ";".join(name for flag, name in REASONS.items() if bits & flag)


def save_orientation(
    output_path: str | Path, result: dict[str, np.ndarray], metadata: dict[str, object],
) -> dict[str, object]:
    """Persist every uncertain point by stable sample index and editable CSV."""
    output = Path(output_path)
    if output.suffix.lower() != ".npz":
        raise ValueError("orientation output must have .npz extension")
    output.parent.mkdir(parents=True, exist_ok=True)
    review_hash = _review_sha256(result)
    source_hash = points_sha256(result["points_xyz"])
    uncertain_indices = np.flatnonzero(result["uncertain_mask"])
    archive = dict(result)
    archive["uncertain_indices"] = uncertain_indices.astype(np.int64)
    archive["point_sha256"] = np.asarray(source_hash)
    archive["review_sha256"] = np.asarray(review_hash)
    np.savez_compressed(output, **archive)
    csv_path = output.with_suffix(".uncertain.csv")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(f"# review_sha256={review_hash}\n")
        writer = csv.writer(stream)
        writer.writerow(("point_index", "action", "x", "y", "z", "normal_x", "normal_y", "normal_z",
                         "best_branch", "second_branch", "reasons"))
        for index in uncertain_indices:
            point = result["points_xyz"][index]
            normal = result["oriented_normals_xyz"][index]
            writer.writerow((int(index), "", *point, *normal,
                             *result["candidate_branches"][index],
                             reason_names(int(result["reason_bits"][index]))))
    report = dict(metadata)
    report.update(
        point_sha256=source_hash,
        review_sha256=review_hash,
        sampled_vertices=len(result["points_xyz"]),
        uncertain_count=int(len(uncertain_indices)),
        uncertain_indices_npz=str(output),
        uncertain_csv=str(csv_path),
        manual_corrections=int(np.count_nonzero(result["manual_mask"])),
        reason_legend=REASONS,
    )
    if "automatic_sign" in result:
        report.update(
            automatic_keep_count=int(np.count_nonzero(result["automatic_sign"] == 1)),
            automatic_flip_count=int(np.count_nonzero(result["automatic_sign"] == -1)),
            cosine_threshold=float(result["cosine_threshold"]),
        )
    output.with_suffix(".json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def load_orientation(path: str | Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        result = {key: archive[key] for key in archive.files}
    required = {"points_xyz", "baseline_normals_xyz", "oriented_normals_xyz", "uncertain_mask",
                "uncertain_indices", "manual_mask", "reason_bits", "candidate_branches",
                "point_sha256", "review_sha256"}
    if not required.issubset(result):
        raise ValueError("orientation archive is missing required arrays")
    points = _xyz(result["points_xyz"], "points_xyz")
    if str(result["point_sha256"]) != points_sha256(points):
        raise ValueError("orientation archive point hash differs from its XYZ array")
    if result["oriented_normals_xyz"].shape != points.shape or not np.isfinite(result["oriented_normals_xyz"]).all():
        raise ValueError("orientation archive normals do not match points")
    if result["baseline_normals_xyz"].shape != points.shape or not np.isfinite(result["baseline_normals_xyz"]).all():
        raise ValueError("orientation archive baseline normals do not match points")
    if result["uncertain_mask"].shape != (len(points),) or result["uncertain_mask"].dtype != bool:
        raise ValueError("orientation archive uncertain mask is invalid")
    if result["manual_mask"].shape != (len(points),) or result["manual_mask"].dtype != bool:
        raise ValueError("orientation archive manual mask is invalid")
    if result["candidate_branches"].shape != (len(points), 2) or not np.issubdtype(result["candidate_branches"].dtype, np.integer):
        raise ValueError("orientation archive candidate branches are invalid")
    if result["reason_bits"].shape != (len(points),) or not np.issubdtype(result["reason_bits"].dtype, np.integer):
        raise ValueError("orientation archive reason bits are invalid")
    if np.any(result["manual_mask"] & result["uncertain_mask"]):
        raise ValueError("manual decisions cannot remain uncertain")
    if not np.array_equal(result["uncertain_indices"], np.flatnonzero(result["uncertain_mask"])):
        raise ValueError("orientation archive uncertain indices differ from its mask")
    optional = {"candidate_edges", "candidate_projection_xyz", "candidate_cosines",
                "cosine_threshold", "automatic_sign"}
    if optional & result.keys():
        if not optional <= result.keys():
            raise ValueError("orientation archive has incomplete cosine diagnostics")
        if (result["candidate_edges"].shape != (len(points), 2)
                or result["candidate_projection_xyz"].shape != (len(points), 2, 3)
                or result["candidate_cosines"].shape != (len(points), 2)
                or result["cosine_threshold"].shape != ()
                or result["automatic_sign"].shape != (len(points),)):
            raise ValueError("orientation archive cosine diagnostics have invalid shapes")
        if not np.isin(result["automatic_sign"], [-1, 0, 1]).all():
            raise ValueError("orientation archive automatic signs are invalid")
        if np.any((result["automatic_sign"] != 0) & result["uncertain_mask"]):
            raise ValueError("automatic decisions cannot remain uncertain")
        if not np.isfinite(result["cosine_threshold"]) or not 0 < float(result["cosine_threshold"]) <= 1:
            raise ValueError("orientation archive cosine threshold is invalid")
    if str(result["review_sha256"]) != _review_sha256(result):
        raise ValueError("orientation archive review hash differs from normals or mask")
    return result


def apply_manual_corrections(
    input_path: str | Path, correction_csv: str | Path, output_path: str | Path,
) -> dict[str, object]:
    """Apply keep/flip decisions to the exact arrows reviewed in the CSV."""
    source = Path(input_path)
    if source.resolve() == Path(output_path).resolve():
        raise ValueError("manual corrections need a new output path")
    result = load_orientation(source)
    with Path(correction_csv).open(encoding="utf-8", newline="") as stream:
        first_line = stream.readline().strip()
        if first_line != f"# review_sha256={result['review_sha256']}":
            raise ValueError("correction CSV belongs to a different orientation review")
        reader = csv.DictReader(stream)
        required_columns = {"point_index", "action", "x", "y", "z",
                            "normal_x", "normal_y", "normal_z",
                            "best_branch", "second_branch", "reasons"}
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError("correction CSV is missing review columns")
        decisions: dict[int, str] = {}
        seen_indices: set[int] = set()
        for row in reader:
            action = (row["action"] or "").strip().lower()
            if action and action not in {"keep", "flip"}:
                raise ValueError("action must be keep or flip")
            try:
                index = int(row["point_index"])
            except (TypeError, ValueError) as error:
                raise ValueError("point_index must be an integer") from error
            if index in seen_indices or index < 0 or index >= len(result["points_xyz"]):
                raise ValueError("duplicate or out-of-range point_index")
            seen_indices.add(index)
            if not result["uncertain_mask"][index]:
                raise ValueError("manual correction targets a point that is not uncertain")
            try:
                point = np.asarray([float(row[axis]) for axis in ("x", "y", "z")])
                normal = np.asarray([float(row[axis]) for axis in
                                     ("normal_x", "normal_y", "normal_z")])
            except (TypeError, ValueError) as error:
                raise ValueError("review row has invalid XYZ or normal values") from error
            if not (np.array_equal(point, result["points_xyz"][index]) and
                    np.array_equal(normal, result["oriented_normals_xyz"][index])):
                raise ValueError("review row coordinates or normal differ from point_index")
            try:
                branches = (int(row["best_branch"]), int(row["second_branch"]))
            except (TypeError, ValueError) as error:
                raise ValueError("review row has invalid branch indices") from error
            if (branches != tuple(result["candidate_branches"][index]) or
                    row["reasons"] != reason_names(int(result["reason_bits"][index]))):
                raise ValueError("review row branches or reasons differ from point_index")
            if action:
                decisions[index] = action
    if seen_indices != set(map(int, result["uncertain_indices"])):
        raise ValueError("correction CSV must contain every uncertain point exactly once")
    if not decisions:
        raise ValueError("correction CSV has no keep/flip decisions")
    for index, action in decisions.items():
        if action == "flip":
            result["oriented_normals_xyz"][index] *= -1
        result["uncertain_mask"][index] = False
        result["manual_mask"][index] = True
        result["reason_bits"][index] |= REASON_MANUAL
    prior_metadata_path = source.with_suffix(".json")
    metadata = json.loads(prior_metadata_path.read_text(encoding="utf-8")) if prior_metadata_path.exists() else {}
    metadata["manual_source_artifact"] = str(source)
    metadata["manual_decisions"] = {str(index): action for index, action in sorted(decisions.items())}
    return save_orientation(output_path, result, metadata)


def _load_graph(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        if "nodes_xyz" not in archive or "edges" not in archive:
            raise ValueError("centreline archive needs nodes_xyz and edges")
        nodes, edges = archive["nodes_xyz"], archive["edges"]
    split_branches(nodes, edges)
    return nodes, edges


def _load_validated_references(path: Path | None, nodes: np.ndarray, edges: np.ndarray) -> list[int]:
    if path is None:
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("graph_sha256") != graph_sha256(nodes, edges):
        raise ValueError("interior reference file belongs to a different centreline graph")
    references = record.get("references")
    if not isinstance(references, list):
        raise ValueError("references must be a list")
    accepted: list[int] = []
    for item in references:
        if not isinstance(item, dict) or type(item.get("validated_interior")) is not bool:
            raise ValueError("each reference needs node_index and validated_interior boolean")
        index = item.get("node_index")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(nodes):
            raise ValueError("node_index must be a valid node index")
        if item["validated_interior"]:
            accepted.append(index)
    return accepted


def prepare(
    sample_path: str | Path, graph_path: str | Path, output_path: str | Path,
    *, reference_path: str | Path | None = None, params: Parameters = Parameters(),
) -> dict[str, object]:
    """Build a reviewable orientation artifact from a fixed sampled cloud."""
    params.validate()
    start = perf_counter()
    with np.load(sample_path, allow_pickle=False) as archive:
        if "points_xyz" not in archive:
            raise ValueError("sample archive needs points_xyz")
        points = archive["points_xyz"]
    nodes, edges = _load_graph(Path(graph_path))
    validated = _load_validated_references(Path(reference_path) if reference_path else None, nodes, edges)
    normals = estimate_baseline_normals(points, params)
    result = orient_from_references(points, normals, nodes, edges, validated, params=params)
    import open3d as o3d
    report = save_orientation(output_path, result, {
        "status": "experimental_normal_orientation_requires_visual_review",
        "sample_path": str(sample_path),
        "graph_path": str(graph_path),
        "graph_sha256": graph_sha256(nodes, edges),
        "reference_path": str(reference_path) if reference_path else None,
        "validated_reference_node_indices": validated,
        "open3d_version": o3d.__version__,
        "parameters": vars(params),
        "random_seed": None,
        "elapsed_seconds": perf_counter() - start,
        "branch_ambiguous_count": int(np.count_nonzero(result["reason_bits"] & REASON_BRANCH_AMBIGUOUS)),
        "near_junction_count": int(np.count_nonzero(result["reason_bits"] & REASON_JUNCTION)),
        "low_normal_quality_count": int(np.count_nonzero(result["reason_bits"] & REASON_LOW_NORMAL_QUALITY)),
    })
    template_path = Path(output_path).with_suffix(".references.template.json")
    if not template_path.exists():
        template_path.write_text(json.dumps({
            "graph_sha256": graph_sha256(nodes, edges),
            "references": [{"node_index": 0, "validated_interior": False,
                            "note": "substitua pelo nó conferido em cortes locais"}],
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    report["reference_template"] = str(template_path)
    Path(output_path).with_suffix(".json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def compare_cosine_thresholds(
    baseline_path: str | Path, graph_path: str | Path, output_prefix: str | Path,
    *, thresholds: tuple[float, ...] = (0.5, 0.75, 0.94),
    params: Parameters = Parameters(),
) -> dict[str, object]:
    """Write comparable provisional reviews from one fixed point/normal sample."""
    params.validate()
    if not thresholds or len(set(thresholds)) != len(thresholds):
        raise ValueError("thresholds must be a nonempty set of distinct values")
    for threshold in thresholds:
        if not np.isfinite(threshold) or not 0 < threshold <= 1:
            raise ValueError("cosine thresholds must be finite and in (0, 1]")
    baseline = load_orientation(baseline_path)
    nodes, edges = _load_graph(Path(graph_path))
    prefix = Path(output_prefix)
    outputs = [prefix.with_name(f"{prefix.name}_cos{int(round(t * 100)):03d}.npz") for t in thresholds]
    summary_path = prefix.with_name(f"{prefix.name}_summary.json")
    if len(set(outputs)) != len(outputs):
        raise ValueError("thresholds produce duplicate output names")
    for output in outputs + [summary_path]:
        if output.exists() or (output.suffix == ".npz" and (
                output.with_suffix(".json").exists() or output.with_suffix(".uncertain.csv").exists())):
            raise ValueError(f"output already exists: {output}")
    import open3d as o3d
    reports: list[dict[str, object]] = []
    for threshold, output in zip(thresholds, outputs):
        start = perf_counter()
        result = orient_by_centreline_cosine(
            baseline["points_xyz"], baseline["baseline_normals_xyz"],
            nodes, edges, threshold, params=params,
        )
        report = save_orientation(output, result, {
            "status": "provisional_centreline_cosine_requires_interior_validation",
            "method": "local edge projection, cosine, branch agreement, junction and normal-quality filters",
            "baseline_path": str(baseline_path),
            "baseline_review_sha256": str(baseline["review_sha256"]),
            "graph_path": str(graph_path),
            "graph_sha256": graph_sha256(nodes, edges),
            "open3d_version": o3d.__version__,
            "parameters": vars(params),
            "random_seed": None,
            "elapsed_seconds": perf_counter() - start,
            "no_branch_count": int(np.count_nonzero(result["reason_bits"] & REASON_NO_BRANCH)),
            "branch_ambiguous_count": int(np.count_nonzero(result["reason_bits"] & REASON_BRANCH_AMBIGUOUS)),
            "near_junction_count": int(np.count_nonzero(result["reason_bits"] & REASON_JUNCTION)),
            "low_normal_quality_count": int(np.count_nonzero(result["reason_bits"] & REASON_LOW_NORMAL_QUALITY)),
            "cosine_below_threshold_count": int(np.count_nonzero(result["reason_bits"] & REASON_COSINE_BELOW_THRESHOLD)),
            "cosine_conflict_count": int(np.count_nonzero(result["reason_bits"] & REASON_COSINE_CONFLICT)),
            "zero_radial_count": int(np.count_nonzero(result["reason_bits"] & REASON_ZERO_RADIAL)),
        })
        report["orientation_path"] = str(output)
        reports.append(report)
    summary: dict[str, object] = {
        "status": "provisional_centreline_cosine_requires_interior_validation",
        "baseline_path": str(baseline_path),
        "baseline_review_sha256": str(baseline["review_sha256"]),
        "point_sha256": str(baseline["point_sha256"]),
        "graph_path": str(graph_path),
        "graph_sha256": graph_sha256(nodes, edges),
        "parameters": vars(params),
        "thresholds": reports,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="estimate, associate, orient, and save review files")
    prepare_parser.add_argument("--sample", required=True, help="NPZ with ordered points_xyz")
    prepare_parser.add_argument("--graph", required=True, help="NPZ with nodes_xyz and edges")
    prepare_parser.add_argument("--references", help="JSON with explicitly validated interior nodes")
    prepare_parser.add_argument("--output", required=True, help="orientation NPZ output")
    prepare_parser.add_argument("--normal-neighbors", type=int, default=30)
    prepare_parser.add_argument("--orientation-neighbors", type=int, default=30)
    prepare_parser.add_argument("--ambiguity-margin", type=float, default=0.15)
    apply_parser = commands.add_parser("apply", help="apply keep/flip decisions from uncertain CSV")
    apply_parser.add_argument("--input", required=True, help="orientation NPZ reviewed in the plot")
    apply_parser.add_argument("--corrections", required=True, help="edited .uncertain.csv")
    apply_parser.add_argument("--output", required=True, help="new corrected orientation NPZ")
    cosine_parser = commands.add_parser("cosine", help="compare provisional centreline cosine thresholds")
    cosine_parser.add_argument("--baseline", required=True, help="fixed orientation NPZ with baseline normals")
    cosine_parser.add_argument("--graph", required=True, help="NPZ with nodes_xyz and edges")
    cosine_parser.add_argument("--output-prefix", required=True, help="prefix for three reviews and summary")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        params = Parameters(normal_neighbors=args.normal_neighbors,
                            orientation_neighbors=args.orientation_neighbors,
                            ambiguity_margin=args.ambiguity_margin)
        report = prepare(args.sample, args.graph, args.output,
                         reference_path=args.references, params=params)
    elif args.command == "cosine":
        report = compare_cosine_thresholds(args.baseline, args.graph, args.output_prefix)
    else:
        report = apply_manual_corrections(args.input, args.corrections, args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
