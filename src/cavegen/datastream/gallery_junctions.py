"""Bounded search for measured junction volumes with one cap per incident branch."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.ndimage import binary_dilation
from scipy.spatial import cKDTree

from cavegen.core.surface_filling import INTERIOR, classify_surface_by_flood_fill
from cavegen.core.volume import Volume3D
from cavegen.datastream.centreline import CentrelineIndex, passages_from_graph, read_graph
from cavegen.datastream.centreline_recentering import recenter_passage
from cavegen.datastream.crop_planner import _Boundary, _fit_contour, _section, _section_frame, _set_boundary
from cavegen.datastream.gallery_crop import Section, parse_section
from cavegen.datastream.gallery_leaks import _enclosed_seeds, _escape_path, seed_component, touches_boundary
from cavegen.datastream.gallery_reports import (
    CHECK_COLUMNS, _write_csv, audit_flood_fill, audit_junction_axes, junction_axis_checks,
)
from cavegen.datastream.point_cloud import iter_point_cloud_xyz
from cavegen.datastream.surface_io import save_surface_npz
from cavegen.datastream.voxel_io import save_volume_npz
from cavegen.tools.planar_caps import polygons_intersect, raster_cap_voxels, vertices_xyz

# Stations and bounds in voxels, independent of survey scale.
MIN_STATION, MAX_STATION, STRIDE = 8, 50, 4
SHORT_MIN_STATION, TIP_MARGIN = 3, 2
CONTEXT, PADDING = 32, 8
BEAM_WIDTH, MAX_VOLUME_TRIALS = 24, 8
POINT_BATCH = 131072


@dataclass
class Cut:
    branch: int
    distance: float
    section: Section
    config: dict
    curve: np.ndarray
    voxels: np.ndarray
    keys: frozenset
    coverage: int


def _indices(xyz, size):
    return np.floor(xyz[:, ::-1] / size).astype(np.intp)


def _measure_points(points, index, size):
    """Project and index the cloud in batches, preserving source point order."""
    owners = np.empty(len(points), dtype=np.intp)
    along = np.empty(len(points))
    occupied = set()
    for start in range(0, len(points), POINT_BATCH):
        stop = min(start + POINT_BATCH, len(points))
        batch = points[start:stop]
        owners[start:stop], along[start:stop], _ = index.locate(batch)
        occupied.update(map(tuple, np.unique(_indices(batch, size), axis=0)))
    return owners, along, occupied


def _stations(length, size):
    limit = min(length / size - TIP_MARGIN, MAX_STATION)
    if limit < MIN_STATION:
        return np.empty(0)
    return np.unique(np.r_[np.arange(MIN_STATION, limit, STRIDE), limit]) * size


def _branch_stations(length, size):
    stations = _stations(length, size)
    if stations.size:
        return "padrao", stations
    limit = length / size - TIP_MARGIN
    if limit < SHORT_MIN_STATION:
        return "sem_estacao", stations
    short = np.unique(np.r_[np.arange(SHORT_MIN_STATION, limit, 1), limit])[::-1] * size
    return "ramo_curto", short


def _candidate(branch, tip, distance, line, points, along, wall_keys, size, tolerance):
    length = line.stations[-1]
    station = distance if tip == 0 else length - distance
    frame = _section_frame(line, station, size)
    if frame is None:
        return None, "tangente"
    point, direction, u = frame
    # Only locally assigned observations can estimate this branch's rim.
    local = points[abs(along - station) <= 4 * size] - point
    local = local[abs(local @ direction) <= 2 * size]
    uv = local @ np.column_stack((u, np.cross(direction, u)))
    uv = uv[np.linalg.norm(uv, axis=1) <= CONTEXT * size]
    if len(uv) > 16384:
        uv = uv[np.random.default_rng(17).choice(len(uv), 16384, replace=False)]
    radii, complete = _fit_contour(uv, size, connected=True)
    if not complete:
        return None, "contorno"
    boundary = _Boundary(station)
    _set_boundary(boundary, station, frame, radii, True)
    config = _section(boundary, end=tip == 0)
    section = parse_section(config, np.zeros(3))
    # Check the short measured approach, before introducing any caps into the lattice.
    steps = np.linspace(max(0, distance - 2 * size), distance, 9)
    approach = line.at(steps if tip == 0 else length - steps)
    crossing = (approach[-1] - section.point) @ section.uv_basis
    if not section.polygon.contains_point(crossing, radius=-size / 2):
        return None, "eixo_fora_da_tampa"
    if any(tuple(cell) in wall_keys for cell in _indices(approach, size)):
        return None, "eixo_na_parede"
    steps = np.linspace(0, distance, int(np.ceil(4 * distance / size)) + 1)
    curve = line.at(steps if tip == 0 else length - steps)
    if np.any((curve - section.point) @ section.normal < -tolerance):
        return None, "plano_recorta_o_proprio_ramo"
    voxels = raster_cap_voxels(section, size, tolerance)
    keys = frozenset(map(tuple, voxels))
    if not keys & wall_keys:
        return None, "tampa_sem_contato"
    return Cut(branch, float(distance), section, config, curve, voxels, keys, boundary.coverage), None


def _compatible(first, second, size, tolerance):
    if first.keys & second.keys or polygons_intersect(first.section, second.section, tolerance):
        return False
    for cap, other in ((first, second), (second, first)):
        if np.any((other.curve - cap.section.point) @ cap.section.normal < -tolerance):
            return False
        if any(tuple(cell) in cap.keys for cell in _indices(other.curve, size)):
            return False
    return True


def _combinations(candidates, size, tolerance):
    groups = sorted(candidates.values(), key=len)
    options = [item for group in groups for item in group]
    ids = {id(item): i for i, item in enumerate(options)}

    @lru_cache(maxsize=None)
    def pair(a, b):
        return _compatible(options[a], options[b], size, tolerance)

    beams = [(0., ())]
    for group in groups:
        expanded = []
        for score, selected in beams:
            for item in group:
                index = ids[id(item)]
                if all(pair(*sorted((other, index))) for other in selected):
                    # For a short branch there is more room to separate the caps farther from the node.
                    distance_score = item.distance if item.distance >= MIN_STATION * size else -item.distance
                    expanded.append((score + distance_score, (*selected, index)))
        beams = sorted(expanded)[:BEAM_WIDTH]
    return [tuple(sorted((options[i] for i in indices), key=lambda cut: cut.branch)) for _, indices in beams]


def _full_plane(surface, start, section, size, tolerance):
    z, y, x = np.ogrid[tuple(slice(n) for n in surface.shape)]
    px, py, pz = section.point
    nx, ny, nz = section.normal
    distance = ((x + start[2] + .5) * size - px) * nx
    distance = distance + ((y + start[1] + .5) * size - py) * ny
    distance = distance + ((z + start[0] + .5) * size - pz) * nz
    return abs(distance) <= size / 2 * np.abs(section.normal).sum() + tolerance


def _trial(points, cuts, joint, size, tolerance, diagnose):
    curves = np.concatenate([cut.curve for cut in cuts])
    rim = np.concatenate([vertices_xyz(cut.section) for cut in cuts])
    xyz = np.vstack((curves, rim))
    lower = np.floor(xyz.min(axis=0)[::-1] / size).astype(int) - PADDING
    upper = np.floor(xyz.max(axis=0)[::-1] / size).astype(int) + PADDING + 1
    shape = tuple(int(n) for n in upper - lower)
    wall = np.zeros(shape, dtype=bool)
    for start in range(0, len(points), POINT_BATCH):
        batch = points[start:start + POINT_BATCH]
        local = _indices(batch, size) - lower
        keep = np.all((local >= 0) & (local < shape), axis=1)
        for cut in cuts:
            section = cut.section
            keep &= (batch - section.point) @ section.normal >= -tolerance
        wall[tuple(local[keep].T)] = True
    caps = np.zeros((len(cuts), *shape), dtype=bool)
    for cap, cut in zip(caps, cuts):
        cap[tuple((cut.voxels - lower).T)] = True
    barrier = wall | caps.any(axis=0)
    seed = tuple(_indices(joint[None], size)[0] - lower)
    note = {"distancias": {str(c.branch + 1): c.distance for c in cuts}}
    if touches_boundary(barrier):
        return {**note, "resultado": "barreira_na_borda"}, None
    if not all((wall & cap).any() for cap in caps):
        return {**note, "resultado": "tampa_sem_contato_na_selecao"}, None

    status, air = seed_component(barrier, seed)
    adjacent = binary_dilation(air) if status == "sealed" else None
    if status != "sealed" or not all((adjacent & cap).any() for cap in caps):
        # A free voxel in the measured neighbourhood must reach all the same exits.
        nearby = np.argwhere(~barrier[tuple(slice(i - 4, i + 5) for i in seed)]) + np.array(seed) - 4
        distance = np.sum((nearby - seed) ** 2, axis=1)
        near = distance <= 16
        eligible = _enclosed_seeds(classify_surface_by_flood_fill(barrier) == INTERIOR, caps, nearby[near])
        if eligible is not None and eligible.any():
            seed = tuple(nearby[near][eligible][distance[near][eligible].argmin()])
            status, air = seed_component(barrier, seed)
        elif status == "sealed":
            status = "ar_sem_contato_com_todas_as_tampas"
    if status != "sealed":
        note["resultado"] = status
        if status == "leaking" and diagnose:
            full = wall.copy()
            for cut in cuts:
                full |= _full_plane(wall, lower, cut.section, size, tolerance)
            note["planos_completos"] = seed_component(full, seed)[0]
            route = _escape_path(barrier, seed)
            if route:
                xyz = (np.asarray(route)[:, ::-1] + lower[::-1] + .5) * size
                # Attribute a seam only when a route crosses the corresponding outward plane.
                for cut in cuts:
                    signed = (xyz - cut.section.point) @ cut.section.normal
                    if np.any(signed < -tolerance):
                        note["ramos_cruzados_pela_fuga"] = note.get("ramos_cruzados_pela_fuga", []) + [cut.branch + 1]
        return note, None
    checks = audit_flood_fill(wall, caps, np.zeros_like(wall), seed, air,
                              expected_original="interior", require_cap_contact=True)
    if any(c["passed"] is False for c in checks):
        return {**note, "resultado": "falha_na_auditoria"}, None
    axes = []
    for cut, cap in zip(cuts, caps):
        samples = _indices(cut.curve, size) - lower
        distances = np.linspace(0, cut.distance, len(samples))
        terminal = cap[tuple(samples.T)] & (distances >= cut.distance - 2 * size)
        # Only omit the continuous terminal run on this branch's own cap.
        keep = ~np.logical_and.accumulate(terminal[::-1])[::-1]
        axes.append({"ramo": cut.branch + 1, "voxels_zyx": samples[keep].tolist(),
                     "distancias_m": distances[keep].tolist()})
    evidence = audit_junction_axes(wall, caps, air, axes)
    note["validacao_eixos"] = evidence
    axis_checks = junction_axis_checks(evidence)
    if any(row["passed"] is False for row in axis_checks):
        return {**note, "resultado": "eixo_fora_do_ar"}, None
    checks.extend(axis_checks)
    return {**note, "resultado": "volume_salvo"}, (wall, caps, air, seed, lower, checks, axes)


def _solve_measured(points, lines, joint, incident, size, owners, along, wall_keys):
    tolerance = size * 1e-6
    options = {}
    rejections = {}
    for branch, tip in incident:
        good = []
        rejected = Counter()
        same_branch = owners == branch
        branch_points, branch_stations = points[same_branch], along[same_branch]
        search, stations = _branch_stations(lines[branch].stations[-1], size)
        for distance in stations:
            cut, reason = _candidate(branch, tip, distance, lines[branch], branch_points,
                                     branch_stations, wall_keys, size, tolerance)
            if cut is None:
                rejected[reason] += 1
            else:
                good.append(cut)
        options[branch] = good
        rejections[str(branch + 1)] = {
            "aceitos": len(good),
            "busca": search,
            "estacoes_do_no_m": stations.tolist(),
            "rejeicoes": dict(rejected),
            "trajetorias_candidatas": [
                {"distancia_m": cut.distance,
                 "voxels_de_parede_no_eixo": len(wall_keys.intersection(map(tuple, _indices(cut.curve, size))))}
                for cut in good
            ],
        }
    record = {"ramos": rejections, "tentativas": []}
    if not all(options.values()):
        return {**record, "resultado": "ramo_sem_tampa_valida"}, None
    candidates = _combinations(options, size, tolerance)
    if not candidates:
        return {**record, "resultado": "tampas_incompativeis"}, None
    diagnosed = False
    for _ in range(min(MAX_VOLUME_TRIALS, len(candidates))):
        cuts = candidates.pop(0)
        outcome, volume = _trial(points, cuts, joint, size, tolerance, diagnose=not diagnosed)
        record["tentativas"].append(outcome)
        if volume is not None:
            record["tampas"] = [{"ramo": c.branch + 1, "distancia": c.distance, "setores": c.coverage,
                                 "secao": c.config} for c in cuts]
            return {**record, "resultado": "volume_salvo"}, volume
        if "planos_completos" in outcome:
            diagnosed = True
            first = cuts
            branches = set(outcome.get("ramos_cruzados_pela_fuga", []))
            if branches:
                def priority(candidate):
                    changed = {a.branch + 1 for a, b in zip(candidate, first) if a is not b}
                    return not (changed and changed <= branches)
                candidates.sort(key=priority)
    return {**record, "resultado": "sem_fechamento"}, None


def solve_junction(points, lines, index, joint, incident, size, *, recenter_axes=False):
    """Try measured caps first; optionally retry with locally recentered axes."""
    measurement = _measure_points(points, index, size)
    baseline, volume = _solve_measured(points, lines, joint, incident, size, *measurement)
    if not recenter_axes:
        return baseline, volume
    if volume is not None:
        baseline["recentramento"] = {"resultado": "fluxo_original_fechou"}
        return baseline, volume

    tree = cKDTree(points)
    corrected = list(lines)
    reports = {}
    changed = {}
    for branch, tip in incident:
        passage, report = recenter_passage(lines[branch], tip, points, measurement[2], size, tree=tree)
        reports[str(branch + 1)] = report
        if passage is not lines[branch]:
            corrected[branch] = passage
            changed[str(branch + 1)] = passage.xyz.tolist()
    if not changed:
        baseline["recentramento"] = {"resultado": "sem_eixo_ajustado", "ramos": reports}
        return baseline, None

    new_index = CentrelineIndex(corrected, size / 2)
    result, volume = _solve_measured(
        points, corrected, joint, incident, size, *_measure_points(points, new_index, size)
    )
    result["recentramento"] = {"resultado": "voxelizacao_repetida", "ramos": reports,
                             "eixos_locais_xyz": changed, "ensaio_sem_ajuste": baseline}
    return result, volume


def save_junction(destination, record, volume, origin, source, graph, size):
    wall, caps, air, seed, lower, checks, axes = volume
    metadata = {
        "junction": True, "status": "pending_review", "axis_order": "ZYX",
        "config": {"voxel_size": size, "sections": [r["secao"] for r in record["tampas"]]},
        "grid_origin_xyz": (origin + lower[::-1] * size).tolist(),
        "section_origin_xyz": origin.tolist(), "source_path": str(source), "centreline": str(graph),
        "seed_zyx": [int(i) for i in seed], "air_voxels": int(air.sum()),
        "shape_zyx": list(air.shape), "junction_search": record, "junction_axes": axes,
    }
    with TemporaryDirectory(dir=destination.parent) as stage:
        result = Path(stage) / "volume"
        save_surface_npz(wall, result / "surface.npz", metadata)
        save_volume_npz(Volume3D(air, metadata), result / "interior.npz")
        np.savez_compressed(result / "masks.npz", caps=caps)
        (result / "relatorio_volume").mkdir()
        _write_csv(result / "relatorio_volume/checks_replay.csv", CHECK_COLUMNS, checks)
        result.rename(destination)
