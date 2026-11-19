"""Propose and extract gallery crops from a point cloud and its centreline."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from cavegen.datastream.centreline import CentrelineIndex, Passage, passages_from_graph, read_graph
from cavegen.datastream.centreline_extraction import (
    ExtractionSettings,
    generate_centreline,
    source_anchor,
)
from cavegen.datastream.crop_preview import ply_header
from cavegen.datastream.gallery_crop import CROP_FORMATS
from cavegen.datastream.point_cloud import iter_point_cloud_xyz
from cavegen.datastream.progress import report_point_progress


class _Sample:
    """Keep a uniform, bounded sample by retaining the smallest random keys."""

    def __init__(self, limit: int):
        self.limit = limit
        self.rows = np.empty((0, 4))
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
    samples: _Sample = field(default_factory=lambda: _Sample(4096))
    station: float = 0.0
    point: np.ndarray = field(default_factory=lambda: np.zeros(3))
    direction: np.ndarray = field(default_factory=lambda: np.zeros(3))
    u: np.ndarray = field(default_factory=lambda: np.zeros(3))
    polygon: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    coverage: int = 0


@dataclass
class _Window:
    owner: int
    start: _Boundary
    end: _Boundary
    folder: Path
    samples: _Sample = field(default_factory=lambda: _Sample(12000))
    reasons: list[str] = field(default_factory=list)
    radius: float = 0.0
    count: int = 0
    lo: np.ndarray = field(default_factory=lambda: np.full(3, np.inf))
    hi: np.ndarray = field(default_factory=lambda: np.full(3, -np.inf))


def _allocate(passages: list[Passage], count: int, size: float):
    limits = []
    for path in passages:
        # Keep a section margin from junctions; end sections can use samples on both sides.
        length = path.stations[-1]
        limits.append((size * (3 if path.junctions[0] else 1),
                       length - size * (3 if path.junctions[1] else 1)))
    usable = np.array([end - start for start, end in limits])
    allocation = np.zeros(len(passages), dtype=int)
    for _ in range(count):
        # Prioritize the longest current interval, with shorter-than-eight-voxel proposals excluded.
        score = usable / np.maximum(allocation, 1)
        score[usable < (allocation + 1) * 8 * size] = -np.inf
        owner = int(np.argmax(score))
        if not np.isfinite(score[owner]):
            break
        allocation[owner] += 1
    return limits, allocation


def _fit_boundary(boundary: _Boundary, path: Passage, size: float) -> None:
    samples = boundary.samples.rows[:, :3]
    best = None
    for shift in (0.0, -size, size):
        station = np.clip(boundary.nominal + shift, size / 2, path.stations[-1] - size / 2)
        point = path.at(station)
        direction = path.at(station + size) - path.at(station - size)
        norm = np.linalg.norm(direction)
        if norm <= 1e-12:
            continue
        direction /= norm
        # Pick the global axis least parallel to the normal to orient U.
        axis = np.eye(3)[np.argmin(np.abs(direction))]
        u = axis - (axis @ direction) * direction
        u /= np.linalg.norm(u)
        v = np.cross(direction, u)
        delta = samples - point
        near = np.abs(delta @ direction) <= 2 * size
        uv = delta[near] @ np.column_stack((u, v))
        radius = np.linalg.norm(uv, axis=1)
        angles = np.mod(np.arctan2(uv[:, 1], uv[:, 0]), 2 * np.pi)
        bins = np.floor(angles / (2 * np.pi / 16)).astype(int).clip(0, 15)
        radii = np.full(16, np.nan)
        for i in range(16):
            observed = radius[(bins == i) & (radius > size)]
            if len(observed) >= 2:
                radii[i] = np.quantile(observed, 0.75) + size / 2
        supported = np.flatnonzero(np.isfinite(radii))
        gaps = np.diff(np.r_[supported, supported[:1] + 16])
        complete = len(supported) >= 14 and gaps.max() <= 2
        score = (complete, len(supported), -abs(shift))
        if best is not None and score <= best:
            continue
        best = score
        boundary.station, boundary.point, boundary.direction, boundary.u = station, point, direction, u
        boundary.coverage = len(supported)
        if complete:
            theta = (np.arange(16) + 0.5) * (2 * np.pi / 16)
            r = np.interp(np.arange(16), supported, radii[supported], period=16)
            boundary.polygon = np.column_stack((r * np.cos(theta), r * np.sin(theta)))
        else:
            boundary.polygon = np.empty((0, 2))


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
    size = spec.get("voxel_size")
    if type(size) not in (int, float) or not np.isfinite(size) or size <= 0:
        raise ValueError("voxel_size deve ser positivo e finito.")
    return spec


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
        limits, allocation = _allocate(passages, spec["count"], size)
        if not allocation.any():
            raise ValueError("Nenhuma passagem comporta oito voxels de comprimento com essa escala.")
        spacing = size / 2
        index = CentrelineIndex(passages, spacing)
        rng = np.random.default_rng(17)
        groups = {}
        for owner in np.flatnonzero(allocation):
            boundaries = [_Boundary(s) for s in np.linspace(*limits[owner], allocation[owner] + 1)]
            windows = []
            for j, (start, end) in enumerate(zip(boundaries, boundaries[1:]), 1):
                windows.append(_Window(int(owner), start, end, staged / f"ramo_{owner + 1:03d}_{j:03d}"))
            groups[owner] = boundaries, windows

        for xyz in _source_batches(source, origin, spec["batch_size"], progress, "estimar"):
            owners, along, radial = index.locate(xyz)
            for owner in np.intersect1d(np.unique(owners), list(groups)):
                part = owners == owner
                points, station = np.column_stack((xyz[part], radial[part])), along[part]
                boundaries, windows = groups[owner]
                for boundary in boundaries:
                    boundary.samples.add(points[np.abs(station - boundary.nominal) <= 4 * size], rng)
                for window in windows:
                    inside = (station >= window.start.nominal) & (station <= window.end.nominal)
                    window.samples.add(points[inside], rng)

        for owner, (boundaries, windows) in groups.items():
            path = passages[owner]
            for boundary in boundaries:
                _fit_boundary(boundary, path, size)
            for window in windows:
                rows = window.samples.rows
                if not len(rows):
                    window.reasons.append("sem_apoio_amostral_no_trecho")
                    continue
                caps = (window.start, window.end)
                support = [np.linalg.norm(b.polygon, axis=1).max(initial=0) for b in caps]
                window.radius = max(np.quantile(rows[:, 3], 0.99) + size, *support)
                if any(not len(b.polygon) for b in caps):
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
        (staged / "plan.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.rename(staged, output)
    return manifest
