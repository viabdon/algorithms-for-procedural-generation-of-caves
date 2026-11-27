"""Propose and extract gallery crops from a point cloud and its centreline."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from cavegen.datastream.centreline import CentrelineIndex, Passage, passages_from_graph, read_graph
from cavegen.datastream.centreline_extraction import generate_centreline, source_anchor
from cavegen.datastream.crop_preview import ply_header
from cavegen.datastream.gallery_crop import CROP_FORMATS
from cavegen.datastream.point_cloud import iter_point_cloud_xyz
from cavegen.datastream.progress import report_point_progress
from cavegen.tools.centreline import ExtractionSettings


class _Sample:
    """Keep a uniform, bounded sample by retaining the smallest random keys."""

    def __init__(self, limit: int, columns: int = 4):
        self.limit = limit
        self.rows = np.empty((0, columns))
        self.keys = np.empty(0)

    def add(self, rows, rng):
        if not len(rows):
            return
        keys = rng.random(len(rows))
        if len(self.keys) == self.limit:
            keep = keys < self.keys.max()
            rows, keys = rows[keep], keys[keep]
        keys = np.concatenate((self.keys, keys))
        rows = np.concatenate((self.rows, rows))
        indices = np.argpartition(keys, self.limit - 1)[:self.limit] if len(keys) > self.limit else slice(None)
        self.rows, self.keys = rows[indices], keys[indices]


@dataclass
class _Boundary:
    nominal: float
    fixed: bool = False
    connected_contour: bool = False
    samples: _Sample = field(default_factory=lambda: _Sample(4096))
    station: float = 0.0
    point: np.ndarray = field(default_factory=lambda: np.zeros(3))
    direction: np.ndarray = field(default_factory=lambda: np.zeros(3))
    u: np.ndarray = field(default_factory=lambda: np.zeros(3))
    polygon: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    coverage: int = 0
    competing_contours: bool = False


@dataclass
class _Window:
    owner: int
    start: _Boundary
    end: _Boundary
    folder: Path
    samples: _Sample = field(default_factory=lambda: _Sample(12000, columns=5))
    reasons: list[str] = field(default_factory=list)
    radius: float = 0.0
    count: int = 0
    lo: np.ndarray = field(default_factory=lambda: np.full(3, np.inf))
    hi: np.ndarray = field(default_factory=lambda: np.full(3, -np.inf))


@dataclass
class _SectionProbe:
    station: float
    point: np.ndarray
    direction: np.ndarray
    u: np.ndarray
    counts: np.ndarray = field(default_factory=lambda: np.zeros((4, 16), dtype=np.int64))
    samples: _Sample = field(default_factory=lambda: _Sample(4096, columns=2))


def _allocate(passages: list[Passage], count: int, size: float, selection: list[int] | None = None):
    limits = []
    for path in passages:
        # Keep a section margin from junctions; end sections can use samples on both sides.
        length = path.stations[-1]
        limits.append((size * (3 if path.junctions[0] else 1),
                       length - size * (3 if path.junctions[1] else 1)))
    usable = np.array([end - start for start, end in limits])
    allocation = np.zeros(len(passages), dtype=int)
    if selection is not None:
        if max(selection) > len(passages):
            raise ValueError("A lista de passagens aponta para uma passagem inexistente.")
        selected = np.asarray(selection) - 1
        short = selected[usable[selected] < 8 * size]
        if len(short):
            names = ", ".join(str(i + 1) for i in short)
            raise ValueError(f"Passagens com menos de oito voxels úteis: {names}.")
        allocation[selected] = 1
        usable[allocation == 0] = -np.inf
    for _ in range(count - int(allocation.sum())):
        # Prioritize the longest current interval, with shorter-than-eight-voxel proposals excluded.
        score = usable / np.maximum(allocation, 1)
        score[usable < (allocation + 1) * 8 * size] = -np.inf
        owner = int(np.argmax(score))
        if not np.isfinite(score[owner]):
            break
        allocation[owner] += 1
    return limits, allocation


def _angular_bins(uv: np.ndarray) -> np.ndarray:
    angles = np.mod(np.arctan2(uv[:, 1], uv[:, 0]), 2 * np.pi)
    return np.floor(angles / (2 * np.pi / 16)).astype(int).clip(0, 15)


def _angular_radii(uv: np.ndarray, size: float) -> np.ndarray:
    radius = np.linalg.norm(uv, axis=1)
    bins = _angular_bins(uv)
    radii = np.full(16, np.nan)
    for i in range(16):
        observed = radius[(bins == i) & (radius > size)]
        if len(observed) >= 2:
            radii[i] = np.quantile(observed, 0.75) + size / 2
    return radii


def _has_angular_support(radii: np.ndarray) -> bool:
    supported = np.flatnonzero(np.isfinite(radii))
    if len(supported) < 14:
        return False
    gaps = np.diff(np.r_[supported, supported[:1] + 16])
    return bool(gaps.max() <= 2)


def _fit_contour(uv: np.ndarray, size: float, connected: bool) -> tuple[np.ndarray, bool]:
    if not connected or not len(uv):
        radii = _angular_radii(uv, size)
        return radii, _has_angular_support(radii)

    # Link neighbouring occupied cells of the section plane. A detached cluster
    # must not supply radii for the wall loop surrounding the centreline.
    cells, inverse = np.unique(np.floor(uv / (2 * size)), axis=0, return_inverse=True)
    pairs = cKDTree(cells).query_pairs(1, p=np.inf, output_type="ndarray")
    adjacency = csr_matrix((np.ones(len(pairs), dtype=bool), (pairs[:, 0], pairs[:, 1])),
                           shape=(len(cells), len(cells)))
    count, labels = connected_components(adjacency, directed=False)
    point_labels = labels[inverse]
    radii_by_component = [_angular_radii(uv[point_labels == i], size) for i in range(count)]
    supported = [radii for radii in radii_by_component if _has_angular_support(radii)]
    if supported:
        # Leave an ambiguous section unclosed, even if each wall has full coverage.
        return supported[0], len(supported) == 1
    return max(radii_by_component, key=lambda radii: np.count_nonzero(np.isfinite(radii))), False


def _section_frame(path: Passage, station: float, size: float):
    point = path.at(station)
    direction = path.at(station + size) - path.at(station - size)
    norm = np.linalg.norm(direction)
    if norm <= 1e-12:
        return None
    direction /= norm
    axis = np.eye(3)[np.argmin(np.abs(direction))]
    u = axis - (axis @ direction) * direction
    return point, direction, u / np.linalg.norm(u)


def _set_boundary(boundary, station, frame, radii, complete):
    boundary.station = station
    boundary.point, boundary.direction, boundary.u = frame
    supported = np.flatnonzero(np.isfinite(radii))
    boundary.coverage = len(supported)
    boundary.competing_contours = not complete and _has_angular_support(radii)
    if complete:
        theta = (np.arange(16) + 0.5) * (2 * np.pi / 16)
        r = np.interp(np.arange(16), supported, radii[supported], period=16)
        boundary.polygon = np.column_stack((r * np.cos(theta), r * np.sin(theta)))
    else:
        boundary.polygon = np.empty((0, 2))


def _fit_boundary(boundary: _Boundary, path: Passage, size: float) -> None:
    samples = boundary.samples.rows[:, :3]
    best = None
    shifts = (0.0,) if boundary.fixed else (0.0, -size, size)
    for shift in shifts:
        station = np.clip(boundary.nominal + shift, size / 2, path.stations[-1] - size / 2)
        frame = _section_frame(path, station, size)
        if frame is None:
            continue
        point, direction, u = frame
        v = np.cross(direction, u)
        delta = samples - point
        near = np.abs(delta @ direction) <= 2 * size
        uv = delta[near] @ np.column_stack((u, v))
        radii, complete = _fit_contour(uv, size, boundary.connected_contour)
        supported = np.flatnonzero(np.isfinite(radii))
        score = (complete, len(supported), -abs(shift))
        if best is not None and score <= best:
            continue
        best = score
        _set_boundary(boundary, station, frame, radii, complete)


def _section_probes(groups, passages, size, steps):
    for owner, (boundaries, _) in groups.items():
        path = passages[owner]
        lower = (2 if path.junctions[0] else 0.5) * size
        upper = path.stations[-1] - (2 if path.junctions[1] else 0.5) * size
        for cut, boundary in enumerate(boundaries):
            probes = []
            offsets = [0, *(offset for step in range(1, steps + 1) for offset in (-step, step))]
            for offset in ([0] if boundary.fixed else offsets):
                station = boundary.station + offset * size
                if offset and not lower <= station <= upper:
                    continue
                frame = _section_frame(path, station, size)
                if frame is not None:
                    probes.append(_SectionProbe(station, *frame))
            yield owner, cut, probes


def _measure_section_probes(batches, probes, index, size, context):
    rng = np.random.default_rng(17)
    search_radius = np.hypot(context, 2 * size)
    for xyz in batches:
        if not len(xyz):
            continue
        tree = cKDTree(xyz)
        owners, along, _ = index.locate(xyz)
        for owner, _, trials in probes:
            for trial in trials:
                nearby = np.asarray(tree.query_ball_point(trial.point, search_radius), dtype=np.intp)
                delta = xyz[nearby] - trial.point
                uv = delta @ np.column_stack((trial.u, np.cross(trial.direction, trial.u)))
                radius = np.linalg.norm(uv, axis=1)
                slab = (np.abs(delta @ trial.direction) <= 2 * size) & (radius <= context)
                nearby, uv, radius = nearby[slab], uv[slab], radius[slab]
                filtered = (owners[nearby] == owner) & (np.abs(along[nearby] - trial.station) <= 4 * size)
                bins = _angular_bins(uv)
                for row, keep in enumerate((np.ones(len(bins), dtype=bool), radius > size,
                                            filtered, filtered & (radius > size))):
                    trial.counts[row] += np.bincount(bins[keep], minlength=16)
                trial.samples.add(uv[filtered], rng)


def _review_sections(groups, passages, index, size, spec, batches):
    probes = list(_section_probes(groups, passages, size, spec["section_search_radius_voxels"]))
    _measure_section_probes(batches, probes, index, size, spec["section_search_context"])
    reviews = []
    for owner, cut, trials in probes:
        boundaries = groups[owner][0]
        boundary = boundaries[cut]
        before = boundary.station
        lo = boundaries[cut - 1].station + 8 * size if cut else -np.inf
        hi = boundaries[cut + 1].station - 8 * size if cut + 1 < len(boundaries) else np.inf
        selected = best = None
        records = []
        for trial in trials:
            uv = trial.samples.rows
            radii, complete = _fit_contour(uv, size, connected=True)
            coverage = int(np.isfinite(radii).sum())
            fits = bool(lo - 1e-10 * size <= trial.station <= hi + 1e-10 * size)
            record = {
                "station": trial.station, "spacing_ok": fits,
                "raw_bins": trial.counts[0].tolist(),
                "raw_bins_above_min_radius": trial.counts[1].tolist(),
                "filtered_bins": trial.counts[2].tolist(),
                "filtered_bins_above_min_radius": trial.counts[3].tolist(),
                "connected_bins_supported": coverage, "connected_complete": complete,
            }
            if complete:
                candidate = _Boundary(trial.station)
                _set_boundary(candidate, trial.station, (trial.point, trial.direction, trial.u), radii, True)
                record["section"] = _section(candidate, end=False)
            records.append(record)
            if fits and complete and selected is None:
                selected = trial, radii
            if trial.station == before:
                best = trial, radii
        if boundary.fixed:
            outcome = "fixed"
        elif selected is not None:
            trial, radii = selected
            _set_boundary(boundary, trial.station, (trial.point, trial.direction, trial.u), radii, True)
            outcome = "refit" if trial.station == before else "moved"
        else:
            if best is not None:
                trial, radii = best
                _set_boundary(boundary, trial.station, (trial.point, trial.direction, trial.u), radii, False)
            outcome = "pending"
        reviews.append({
            "passage": int(owner) + 1, "cut": cut, "original_station": before,
            "selected_station": boundary.station, "outcome": outcome, "trials": records,
        })
    return reviews


def _section(boundary: _Boundary, *, end: bool) -> dict:
    normal = -boundary.direction if end else boundary.direction
    polygon = boundary.polygon
    if end:
        polygon = (polygon * [1, -1])[::-1]
    return {
        "point_xyz": boundary.point.tolist(),
        "inward_normal_xyz": normal.tolist(),
        "u_xyz": boundary.u.tolist(),
        "polygon_uv": polygon.tolist(),
    }


def _source_batches(source, origin, batch, progress, phase) -> Iterator[np.ndarray]:
    batches = iter_point_cloud_xyz(source, batch, origin_xyz=origin)
    if progress is not None:
        batches = report_point_progress(batches, 1_000_000, lambda count: progress(phase, count))
    yield from batches


def _record_config(window, spec, path, size, source_origin):
    seed = path.at((window.start.station + window.end.station) / 2)
    sections = [_section(window.start, end=False), _section(window.end, end=True)]
    bounds = np.stack((window.lo, window.hi, seed))
    cap_xyz = [seed[None]]
    for section in sections:
        polygon = np.asarray(section["polygon_uv"])
        if len(polygon):
            normal, u = np.array(section["inward_normal_xyz"]), np.array(section["u_xyz"])
            cap_xyz.append(np.asarray(section["point_xyz"]) + polygon @ np.stack((u, np.cross(normal, u))))
    if not window.count:
        bounds = path.at([window.start.nominal, window.end.nominal])
    vertices = np.concatenate((bounds, *cap_xyz))
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    padding = spec["padding_voxels"] * size
    origin = low - padding
    shape_xyz = np.maximum(64, np.ceil((high - low + 2 * padding) / size).astype(int))
    if max(shape_xyz) > 64:
        window.reasons.append("grade_excede_64_com_voxel_escolhido")
    if not window.count:
        window.reasons.append("sem_pontos_retidos")
    return {
        "cave": spec["cave"],
        "survey": spec["survey"],
        "crop_id": window.folder.name,
        "plan_id": spec["plan_id"],
        "fold": spec["fold"],
        "branch": f"passagem_{window.owner + 1:03d}",
        "source": "cloud.ply",
        "source_origin_xyz": source_origin.tolist(),
        "units": spec["units"],
        "origin_xyz": origin.tolist(),
        "selection_min_xyz": (low - size / 100).tolist(),
        "selection_max_xyz": (high + size / 100).tolist(),
        "shape_zyx": shape_xyz[::-1].tolist(),
        "voxel_size": size,
        "sections": sections,
        "seed_xyz": seed.tolist(),
        "batch_size": spec["batch_size"],
    }


def read_plan_config(config: Path) -> dict:
    """Load the plan and fill defaults shared by the menu and planner."""
    spec = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise ValueError("A configuração do planejamento deve ser um objeto JSON.")
    for key in ("source", "units"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f"Informe {key} no JSON do planejamento.")
    spec.setdefault("plan_id", config.stem)
    for key in ("cave", "survey", "fold", "plan_id"):
        value = spec.get(key)
        if (
            not isinstance(value, str) or not value.strip()
            or value in (".", "..") or "/" in value or "\\" in value
        ):
            raise ValueError(f"Informe {key} como identificador simples.")
    line = spec.get("centreline")
    if line is not None and not isinstance(line, str):
        raise ValueError("centreline deve ser um caminho ou ficar em branco.")
    spec["centreline"] = line.strip() if line else ""
    for key, default, minimum in (("count", 6, 1), ("batch_size", 65536, 1), ("padding_voxels", 2, 2)):
        value = spec.setdefault(key, default)
        if type(value) is not int or value < minimum:
            raise ValueError(f"{key} deve ser um inteiro ≥ {minimum}.")
    selection = spec.get("passages")
    if selection is not None and (
        not isinstance(selection, list) or not selection
        or any(type(passage) is not int or passage < 1 for passage in selection)
        or len(set(selection)) != len(selection) or len(selection) > spec["count"]
    ):
        raise ValueError("Informe passagens distintas por índice positivo e um count que cubra a lista.")
    size = spec.get("voxel_size")
    if type(size) not in (int, float) or not np.isfinite(size) or size <= 0:
        raise ValueError("voxel_size deve ser positivo e finito.")
    steps = spec.get("section_search_radius_voxels", 0)
    if type(steps) is not int or not 0 <= steps <= 16:
        raise ValueError("section_search_radius_voxels deve ser um inteiro entre 0 e 16.")
    if steps:
        context = spec.setdefault("section_search_context", max(5.0, 4 * size))
        if type(context) not in (int, float) or not np.isfinite(context) or context <= size:
            raise ValueError("section_search_context deve ser finito e maior que um voxel.")
    overrides = spec.get("section_overrides", [])
    if not isinstance(overrides, list):
        raise ValueError("section_overrides deve ser uma lista.")
    seen = set()
    for override in overrides:
        if not isinstance(override, dict):
            raise ValueError("Cada ajuste de seção deve ser um objeto JSON.")
        passage, cut = override.get("passage"), override.get("cut")
        station = override.get("station")
        if type(passage) is not int or passage < 1 or type(cut) is not int or cut < 0:
            raise ValueError("Informe passage ≥ 1 e cut ≥ 0 como inteiros em section_overrides.")
        if type(station) not in (int, float) or not np.isfinite(station) or station <= 0:
            raise ValueError("Informe station positiva e finita em section_overrides.")
        if override.get("contour", "radial") not in ("radial", "connected"):
            raise ValueError("contour deve ser radial ou connected em section_overrides.")
        if (passage, cut) in seen:
            raise ValueError("Cada corte pode ter apenas um ajuste em section_overrides.")
        seen.add((passage, cut))
    return spec


def _plan_boundaries(spec, passages, limits, allocation, size):
    boundaries_by_owner = {
        owner: [_Boundary(s) for s in np.linspace(*limits[owner], allocation[owner] + 1)]
        for owner in np.flatnonzero(allocation)
    }
    adjusted = set()
    for override in spec.get("section_overrides", []):
        owner, cut = override["passage"] - 1, override["cut"]
        station = override["station"]
        if owner not in boundaries_by_owner or cut >= len(boundaries_by_owner[owner]):
            raise ValueError("Ajuste de seção aponta para um corte inexistente.")
        if not size / 2 <= station <= passages[owner].stations[-1] - size / 2:
            raise ValueError("Ajuste de seção fora dos limites da passagem.")
        connected = override.get("contour") == "connected"
        boundaries_by_owner[owner][cut] = _Boundary(
            station, fixed=True, connected_contour=connected,
            samples=_Sample(16384 if connected else 4096),
        )
        adjusted.add(owner)
    for owner in adjusted:
        if np.any(np.diff([b.nominal for b in boundaries_by_owner[owner]]) < 8 * size):
            raise ValueError("Ajustes de seção devem manter os cortes em ordem e separados por oito voxels.")
    return boundaries_by_owner


def default_plan_destination(spec: dict) -> Path:
    return (
        Path("data/processed/crop_plans") / spec["cave"] / spec["survey"]
        / spec["fold"] / spec["plan_id"]
    )


def propose_crops(
    config: Path,
    output: Path | None = None,
    *,
    centreline: Path | None = None,
    progress: Callable[[str, int], None] | None = None,
) -> dict:
    """Extract candidate PLYs, estimating and saving a centreline when absent."""
    spec = read_plan_config(config)
    size = float(spec["voxel_size"])
    if output is None:
        output = default_plan_destination(spec)
    source = (config.parent / Path(spec["source"]).expanduser()).resolve()
    graph = centreline
    if graph is None and spec["centreline"]:
        graph = config.parent / Path(spec["centreline"]).expanduser()
    if not source.is_file() or source.suffix.lower() not in CROP_FORMATS:
        raise ValueError(f"Fonte XYZ, LAS, PLY ou F32 inválida: {source}")
    if output.exists():
        raise FileExistsError(f"Já existe uma execução em {output}.")
    before = source.stat()

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        staged = Path(staging)
        extraction = None
        if graph is None:
            settings = ExtractionSettings(**spec.get("centreline_extraction", {}))
            anchor = source_anchor(source)
            batches = _source_batches(source, anchor, spec["batch_size"], progress, "linha_central")
            graph = staged / "centreline.npz"
            extraction = generate_centreline(batches, anchor, graph, settings)
        else:
            graph = graph.expanduser().resolve()
        nodes, edges = read_graph(graph)
        origin = nodes[0].copy()
        passages = passages_from_graph(nodes - origin, edges)
        limits, allocation = _allocate(passages, spec["count"], size, spec.get("passages"))
        if not allocation.any():
            raise ValueError("Nenhuma passagem comporta oito voxels de comprimento com essa escala.")
        spacing = size / 2
        search_steps = spec.get("section_search_radius_voxels", 0)
        search_margin = (search_steps + 1) * size if search_steps else 0.0
        index = CentrelineIndex(passages, spacing)
        rng = np.random.default_rng(17)
        groups = {}
        for owner, boundaries in _plan_boundaries(spec, passages, limits, allocation, size).items():
            windows = []
            for j, (start, end) in enumerate(zip(boundaries, boundaries[1:]), 1):
                windows.append(_Window(int(owner), start, end, staged / f"ramo_{owner + 1:03d}_{j:03d}"))
            groups[owner] = boundaries, windows

        for xyz in _source_batches(source, origin, spec["batch_size"], progress, "estimar"):
            owners, along, radial = index.locate(xyz)
            for owner in np.intersect1d(np.unique(owners), list(groups)):
                part = owners == owner
                station = along[part]
                points = np.column_stack((xyz[part], radial[part], station))
                boundaries, windows = groups[owner]
                for boundary in boundaries:
                    near = np.abs(station - boundary.nominal) <= 4 * size
                    boundary.samples.add(points[near, :4], rng)
                for window in windows:
                    inside = (
                        (station >= window.start.nominal - search_margin)
                        & (station <= window.end.nominal + search_margin)
                    )
                    window.samples.add(points[inside], rng)

        for owner, (boundaries, _) in groups.items():
            for boundary in boundaries:
                _fit_boundary(boundary, passages[owner], size)
            if any(b.fixed for b in boundaries) and np.any(
                np.diff([b.station for b in boundaries]) < 8 * size
            ):
                raise ValueError("Os cortes ajustados ficaram separados por menos de oito voxels.")

        section_reviews = None
        if search_steps:
            batches = _source_batches(source, origin, spec["batch_size"], progress, "revisar_secoes")
            section_reviews = _review_sections(groups, passages, index, size, spec, batches)

        for owner, (boundaries, windows) in groups.items():
            path = passages[owner]
            for window in windows:
                rows = window.samples.rows
                if search_steps:
                    rows = rows[(rows[:, 4] >= window.start.station) & (rows[:, 4] <= window.end.station)]
                if not len(rows):
                    window.reasons.append("sem_apoio_amostral_no_trecho")
                    continue
                caps = (window.start, window.end)
                support = [np.linalg.norm(b.polygon, axis=1).max(initial=0) for b in caps]
                window.radius = max(np.quantile(rows[:, 3], 0.99) + size, *support)
                if any(b.competing_contours for b in caps):
                    window.reasons.append("tampa_com_contornos_concorrentes")
                if any(not len(b.polygon) and not b.competing_contours for b in caps):
                    window.reasons.append("tampa_com_cobertura_insuficiente")
                if index.has_nearby_passage(
                    path, owner, (window.start.station, window.end.station), window.radius
                ):
                    window.reasons.append("outra_passagem_ou_retorno_proximo")
                start, end = window.start.station, window.end.station
                internal = path.stations[(path.stations > start) & (path.stations < end)]
                spine = path.at(np.r_[start, internal, end])
                if (np.any((spine - window.start.point) @ window.start.direction < -size)
                        or np.any((spine - window.end.point) @ window.end.direction > size)):
                    window.reasons.append("curva_cruza_plano_de_extremidade")
                window.folder.mkdir()
                (window.folder / "cloud.ply").write_bytes(ply_header(0))

        for xyz in _source_batches(source, origin, spec["batch_size"], progress, "extrair"):
            owners, along, radial = index.locate(xyz)
            for owner in np.intersect1d(np.unique(owners), list(groups)):
                _, windows = groups[owner]
                part = owners == owner
                points, station, distance = xyz[part], along[part], radial[part]
                for window in windows:
                    if not window.radius:
                        continue
                    start, end = window.start, window.end
                    keep = (
                        (station >= start.station - spacing) & (station <= end.station + spacing)
                        & (distance <= window.radius)
                    )
                    candidates = points[keep]
                    retained = candidates[
                        ((candidates - start.point) @ start.direction >= -size * 1e-6)
                        & ((candidates - end.point) @ end.direction < size * 1e-6)
                    ]
                    if len(retained):
                        with (window.folder / "cloud.ply").open("ab") as stream:
                            stream.write(retained.astype("<f8", copy=False).tobytes())
                        window.count += len(retained)
                        window.lo = np.minimum(window.lo, retained.min(axis=0))
                        window.hi = np.maximum(window.hi, retained.max(axis=0))

        after = source.stat()
        if (before.st_size, before.st_mtime_ns, before.st_dev, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_dev, after.st_ino
        ):
            raise ValueError("A fonte mudou durante a leitura.")
        records = []
        for owner, (_, windows) in groups.items():
            for window in windows:
                if extraction is not None:
                    window.reasons.append("linha_central_estimada")
                if window.folder.exists():
                    with (window.folder / "cloud.ply").open("r+b") as stream:
                        stream.write(ply_header(window.count))
                else:
                    window.folder.mkdir()
                proposal = _record_config(window, spec, passages[owner], size, origin)
                record = {
                    "crop_id": window.folder.name,
                    "status": "pending_review",
                    "review_reasons": window.reasons,
                    "retained_points": window.count,
                    "cut_stations": [window.start.station, window.end.station],
                    "section_bins_supported": [window.start.coverage, window.end.coverage],
                    "selection_radius": window.radius,
                }
                proposal["proposal"] = record
                (window.folder / "crop.json").write_text(
                    json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                records.append(record)
        manifest = {
            "source": str(source),
            "centreline": graph.name if extraction is not None else str(graph),
            "centreline_extraction": extraction,
            "source_origin_xyz": origin.tolist(),
            "parameters": spec, "requested": spec["count"], "proposed": len(records), "crops": records,
        }
        if section_reviews is not None:
            manifest["section_reviews"] = section_reviews
        (staged / "plan.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.rename(staged, output)
    return manifest
