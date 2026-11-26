"""Localize leaks in a voxelized gallery and test supported, localized repairs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import product
import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from scipy.ndimage import (
    binary_closing, binary_dilation, binary_propagation, distance_transform_edt, generate_binary_structure, label,
)
from skimage.graph import MCP

from cavegen.core.surface_filling import EXTERIOR, INTERIOR, classify_surface_by_flood_fill
from cavegen.datastream.centreline import Passage, passages_from_graph, read_graph
from cavegen.datastream.point_cloud import iter_point_cloud_xyz

if TYPE_CHECKING:
    from cavegen.datastream.gallery_crop import GalleryCrop

CONNECTIVITY = generate_binary_structure(3, 1)
NEIGHBOURHOOD = np.ones((3, 3, 3), dtype=bool)
OPPOSITE_PAIRS = [v for v in product(range(-1, 2), repeat=3) if v > (0, 0, 0)]
WINDOW_VOXELS = 8
STRIDE_VOXELS = 4
MIN_WINDOW_VOXELS = 4
MAX_CAP_OFFSET_VOXELS = 6
MAX_PATCH_VOXELS = 12
MIN_RAW_POINTS = 2
FOCUS_RADIUS_VOXELS = 4
MAX_SAMPLE_POINTS = 2000


def touches_boundary(mask: np.ndarray) -> bool:
    return any(np.take(mask, (0, -1), axis=axis).any() for axis in range(3))


def seed_component(barrier: np.ndarray, seed: tuple[int, int, int]) -> tuple[str, np.ndarray]:
    """Flood through six faces from the seed and test contact with the exterior."""
    component = np.zeros_like(barrier)
    if barrier[seed]:
        return "seed_blocked", component
    component[seed] = True
    component = binary_propagation(component, structure=CONNECTIVITY, mask=~barrier)
    return ("leaking" if touches_boundary(component) else "sealed"), component


@dataclass(frozen=True)
class LeakAnalysis:
    report: dict
    repair: np.ndarray
    air: np.ndarray | None


@dataclass(frozen=True)
class ScanContext:
    passage: Passage
    axis_source: str
    centreline_path: Path | None
    raw_source: Path | None
    raw_offset: np.ndarray


def _scan_context(crop: GalleryCrop) -> ScanContext:
    source_offset = np.asarray(crop.config.get("source_origin_xyz", [0, 0, 0]), dtype=float)
    offset = source_offset + crop.origin_xyz
    raw_source = None
    graph = None
    plan_path = crop.config_path.parent.parent / "plan.json"
    try:
        if crop.source != crop.config_path.parent / "cloud.ply":
            raise ValueError("A nuvem do recorte foi substituída.")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if not any(row["crop_id"] == crop.config["crop_id"] for row in plan["crops"]):
            raise ValueError("Recorte sem correspondência no manifesto do plano.")
        if not np.array_equal(source_offset, plan["source_origin_xyz"]):
            raise ValueError("A origem do recorte diverge do manifesto do plano.")
        raw_source = (plan_path.parent / plan["source"]).resolve()
        graph = plan_path.parent / plan["centreline"]
    except (OSError, KeyError, TypeError, ValueError):
        pass

    override = crop.config.get("leak_diagnostics", {})
    if override.get("raw_source"):
        raw_source = (crop.config_path.parent / Path(override["raw_source"]).expanduser()).resolve()
    if override.get("centreline"):
        graph = (crop.config_path.parent / Path(override["centreline"]).expanduser()).resolve()
    try:
        if graph is None:
            raise ValueError("Linha central ausente.")
        nodes, edges = read_graph(graph)
        pathways = passages_from_graph(nodes - offset, edges)
        branch = crop.config["branch"]
        if not branch.startswith("passagem_"):
            raise ValueError("Ramo sem índice no plano.")
        branch_index = int(branch.removeprefix("passagem_")) - 1
        if not 0 <= branch_index < len(pathways):
            raise ValueError("Ramo fora do grafo.")
        passage = pathways[branch_index]
        start, end = crop.config["proposal"]["cut_stations"]
        endpoints = passage.at([start, end])
        if not (0 <= start < end <= passage.stations[-1]) or not np.allclose(
            endpoints, [s.point for s in crop.sections], rtol=0, atol=crop.voxel_size / 2
        ):
            raise ValueError("Os cortes foram movidos ou divergem da linha central do plano.")
        inner = passage.stations[(passage.stations > start) & (passage.stations < end)]
        stations = np.r_[start, inner, end]
        return ScanContext(
            Passage(passage.at(stations), stations - start, (False, False)),
            "relocated_centreline" if override.get("centreline") else "plan_centreline",
            graph.resolve(), raw_source, offset,
        )
    except (OSError, KeyError, TypeError, ValueError, IndexError):
        # Legacy or manual crops can still be diagnosed in their own frame.
        points = np.stack([
            crop.sections[0].point,
            np.asarray(crop.config["seed_xyz"]) - crop.origin_xyz,
            crop.sections[1].point,
        ])
        stations = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
        return ScanContext(
            Passage(points, stations, (False, False)), "sections_and_seed", None, raw_source,
            offset,
        )


class _WindowScan:
    """Run overlapping probes and refine leaky intervals one voxel at a time."""

    def __init__(self, crop: GalleryCrop, surface: np.ndarray, passage: Passage):
        self.crop = crop
        self.surface = surface
        self.passage = passage
        length = passage.stations[-1]
        self.stations = np.r_[np.arange(0, length, crop.voxel_size), length]
        self.points = passage.at(self.stations)
        self.grid_zyx = [(axis + 0.5) * crop.voxel_size for axis in np.ogrid[
            tuple(slice(n) for n in crop.shape_zyx)
        ]]
        self.trials: dict[tuple[int, int], dict] = {}

    def _plane(self, point, normal):
        z, y, x = self.grid_zyx
        px, py, pz = point
        nx, ny, nz = normal
        dz, dy, dx = (z - pz) * nz, (y - py) * ny, (x - px) * nx
        half_width = self.crop.voxel_size / 2 * np.abs(normal).sum()
        return np.abs(dx + dy + dz) <= half_width + self.crop.config["plane_tolerance"]

    def _point_normal(self, step):
        if step == 0 or step == len(self.stations) - 1:
            section = self.crop.sections[0 if step == 0 else 1]
            return section.point, section.normal if step == 0 else -section.normal
        tangent = self.points[step + 1] - self.points[step - 1]
        length = np.linalg.norm(tangent)
        return self.points[step], tangent / length if length else None

    def _planes(self, start, end):
        lo, forward = self._point_normal(start)
        hi, backward = self._point_normal(end)
        if forward is None or backward is None:
            return None
        spine = self.points[start:end + 1]
        tolerance = self.crop.voxel_size
        if np.any((spine - lo) @ forward < -tolerance) or np.any((spine - hi) @ backward > tolerance):
            return None  # A transverse plane would cut the tested centreline again.
        return self._plane(lo, forward), self._plane(hi, backward)

    def _barrier(self, start, end):
        planes = self._planes(start, end)
        return None if planes is None else self.surface | planes[0] | planes[1]

    def original_cuts(self):
        start, end = self.crop.sections
        barrier = self.surface | self._plane(start.point, start.normal) | self._plane(end.point, end.normal)
        return seed_component(barrier, self.crop.seed_zyx)[0]

    def trial(self, window, stage):
        if window in self.trials:
            return self.trials[window]["outcome"]
        start, end = window
        lo, hi = self.stations[[start, end]]
        seed_xyz = self.passage.at((lo + hi) / 2)
        seed = tuple(int(i) for i in np.floor(seed_xyz[::-1] / self.crop.voxel_size))
        barrier = self._barrier(start, end)
        if barrier is None or not all(0 <= i < n for i, n in zip(seed, self.surface.shape)):
            outcome = "invalid_window"
        else:
            outcome, _ = seed_component(barrier, seed)
        self.trials[window] = {
            "from_start": [float(lo), float(hi)], "stage": stage,
            "seed_zyx": list(seed), "outcome": outcome,
        }
        return outcome

    def sweep(self):
        end_step = len(self.stations) - 1
        span = min(WINDOW_VOXELS, end_step)
        starts = list(range(0, end_step - span + 1, STRIDE_VOXELS))
        if starts[-1] != end_step - span:
            starts.append(end_step - span)
        leaking = [(s, s + span) for s in starts if self.trial((s, s + span), "sweep") == "leaking"]
        refined = set()
        for window in leaking:
            for side in range(2):
                start, end = window
                while end - start > MIN_WINDOW_VOXELS:
                    narrower = (start + 1, end) if side == 0 else (start, end - 1)
                    if self.trial(narrower, "refine") != "leaking":
                        break
                    start, end = narrower
                refined.add((start, end))
        return sorted(refined)

    def trace(self, window):
        barrier = self._barrier(*window)
        return _escape_path(barrier, tuple(self.trials[window]["seed_zyx"]))


def _enclosed_seeds(interior, caps, candidates):
    labels, _ = label(interior, structure=CONNECTIVITY)
    touching = [np.unique(labels[binary_dilation(cap, structure=CONNECTIVITY)]) for cap in caps]
    shared = np.intersect1d(*touching)
    values = labels[tuple(candidates.T)]
    eligible = np.isin(values, shared[shared != 0])
    if len(np.unique(values[eligible])) > 1:
        return None
    return eligible


def recover_seed(crop: GalleryCrop, surface: np.ndarray, caps: np.ndarray, radius: int):
    """Find a nearby enclosed seed, or a leaky seed supported by a sealed local window."""
    center = np.array(crop.seed_zyx)
    axes = [np.arange(max(0, i - radius), min(n, i + radius + 1))
            for i, n in zip(crop.seed_zyx, surface.shape)]
    candidates = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    distances = np.sum((candidates - center) ** 2, axis=1)
    barrier = surface | caps.any(axis=0)
    local = (distances <= radius ** 2) & ~barrier[tuple(candidates.T)]
    xyz = (candidates[:, ::-1] + 0.5) * crop.voxel_size
    local &= np.all((xyz >= crop.selection_min_local) & (xyz < crop.selection_max_local), axis=1)
    for section in crop.sections:
        local &= (xyz - section.point) @ section.normal > crop.config["plane_tolerance"]
    candidates, distances = candidates[local], distances[local]
    if not len(candidates):
        return None, "no_candidate"

    classification = classify_surface_by_flood_fill(barrier)
    eligible = _enclosed_seeds(classification == INTERIOR, caps, candidates)
    if eligible is None:
        return None, "ambiguous_interior"
    mode = "enclosed"
    if not eligible.any():
        mode = "provisional"
        scan = _WindowScan(crop, surface, _scan_context(crop).passage)
        span = min(MIN_WINDOW_VOXELS, len(scan.stations) - 1)
        if span < 2:
            return None, "no_candidate"
        origin = np.asarray(crop.config["seed_xyz"]) - crop.origin_xyz
        closest = int(np.argmin(np.linalg.norm(scan.points - origin, axis=1)))
        exterior = classification[tuple(candidates.T)] == EXTERIOR
        for start in range(max(0, closest - radius - span + 1),
                           min(len(scan.stations) - span, closest + radius + 1)):
            planes = scan._planes(start, start + span)
            if planes is None:
                continue
            window = classify_surface_by_flood_fill(surface | planes[0] | planes[1])
            supported = _enclosed_seeds(window == INTERIOR, planes, candidates)
            if supported is not None:
                eligible |= supported & exterior
    if not eligible.any():
        return None, "no_candidate"

    nearest = candidates[eligible & (distances == distances[eligible].min())]
    clearance = distance_transform_edt(~barrier)[tuple(nearest.T)]
    return tuple(int(i) for i in nearest[clearance.argmax()]), mode


def _escape_path(barrier: np.ndarray, seed: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    edge = np.zeros_like(barrier)
    edge[[0, -1], :, :] = edge[:, [0, -1], :] = edge[:, :, [0, -1]] = True
    ends = np.nonzero(edge & ~barrier)
    if barrier[seed] or not len(ends[0]):
        return []
    search = MCP(np.where(barrier, np.inf, 1.0), fully_connected=False)
    costs, _ = search.find_costs([seed], list(zip(*ends)), find_all_ends=False)
    closest = int(costs[ends].argmin())
    goal = tuple(int(axis[closest]) for axis in ends)
    return search.traceback(goal) if np.isfinite(costs[goal]) else []


def _shifted_caps(crop, surface, caps):
    from cavegen.datastream.gallery_crop import _rasterize_caps

    copies = [caps]
    for offset in range(1, MAX_CAP_OFFSET_VOXELS + 1):
        sections = tuple(
            replace(s, point=s.point + offset * crop.voxel_size * s.normal) for s in crop.sections
        )
        copies.append(_rasterize_caps(replace(crop, sections=sections)))
    trials = []
    for start, end in product(range(len(copies)), repeat=2):
        if not (start or end):
            continue
        barrier = surface | caps.any(axis=0) | copies[start][0] | copies[end][1]
        if touches_boundary(barrier):
            outcome = "touches_grid_boundary"
        else:
            outcome, _ = seed_component(barrier, crop.seed_zyx)
        trials.append({"offset_voxels": [start, end], "outcome": outcome})
    return trials


def _point_evidence(source, offset, crop, region, slices, *, check_selection=False):
    """Count points in relevant bins and keep a bounded example near the focus."""
    counts = np.zeros(crop.shape_zyx, dtype=np.int64)
    selected = np.zeros_like(counts) if check_selection else None
    shown = []
    remaining = MAX_SAMPLE_POINTS
    targets = np.argwhere(region)
    lo = targets.min(axis=0)[::-1] * crop.voxel_size
    hi = (targets.max(axis=0)[::-1] + 1) * crop.voxel_size
    focus_lo = np.array([s.start for s in slices]) * crop.voxel_size
    focus_hi = np.array([s.stop for s in slices]) * crop.voxel_size
    before = source.stat()
    for xyz in iter_point_cloud_xyz(source, crop.config["batch_size"], origin_xyz=offset):
        local = xyz[np.all((xyz >= lo) & (xyz < hi), axis=1)]
        bins_zyx = np.floor(local[:, ::-1] / crop.voxel_size).astype(np.intp)
        valid = np.all(bins_zyx < crop.shape_zyx, axis=1)
        np.add.at(counts, tuple(bins_zyx[valid].T), 1)
        if selected is not None:
            valid &= np.all(
                (local >= crop.selection_min_local) & (local < crop.selection_max_local), axis=1
            )
            for section in crop.sections:
                valid &= (local - section.point) @ section.normal >= -crop.config["plane_tolerance"]
            np.add.at(selected, tuple(bins_zyx[valid].T), 1)
        if remaining and len(local):
            zyx = local[:, ::-1]
            near = zyx[np.all((zyx >= focus_lo) & (zyx < focus_hi), axis=1)]
            if len(near):
                rows = np.linspace(0, len(near) - 1, min(remaining, len(near)), dtype=int)
                shown.extend((near[rows] / crop.voxel_size - 0.5).tolist())
                remaining -= len(rows)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, before.st_dev, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_dev, after.st_ino
    ):
        raise ValueError("A nuvem mudou durante a comparação local.")
    counts[~region] = 0
    return counts, shown, selected, before


def _pair_support(mask, indices):
    support = np.zeros(len(indices), dtype=np.intp)
    for delta in OPPOSITE_PAIRS:
        support += mask[tuple((indices - delta).T)] & mask[tuple((indices + delta).T)]
    return support


def _look_for_patch(barrier, possible, support, seed, protected_seeds):
    """Block a supported voxel on each escaping path, then verify and minimize the patch."""
    repair = np.zeros_like(barrier)
    chosen = []
    for _ in range(MAX_PATCH_VOXELS):
        route = _escape_path(barrier | repair, seed)
        candidates = [voxel for voxel in route if possible[voxel] and not repair[voxel]]
        if not candidates:
            return None, repair, chosen, "escape_path_without_supported_voxels"
        voxel = max(candidates, key=lambda v: support[v])
        repair[voxel] = True
        chosen.append(voxel)
        status, air = seed_component(barrier | repair, seed)
        if status == "sealed":
            break
    else:
        return None, repair, chosen, "patch_budget_exceeded"

    for voxel in reversed(chosen):
        repair[voxel] = False
        status, larger = seed_component(barrier | repair, seed)
        if status == "sealed":
            air = larger
        else:
            repair[voxel] = True
    if not all(air[seed] for seed in protected_seeds):
        return None, repair, chosen, "patch_disconnects_a_probe_seed"
    return air, repair, chosen, "verified"


def analyze_leak(
    crop: GalleryCrop, surface: np.ndarray, caps: np.ndarray, *,
    progress: Callable[[str], None] | None = None,
) -> LeakAnalysis:
    """Diagnose a leak and return a patch only if the full gallery seals."""
    barrier = surface | caps.any(axis=0)
    context = _scan_context(crop)
    scan = _WindowScan(crop, surface, context.passage)
    full_cuts = scan.original_cuts()
    double_cap_trials = _shifted_caps(crop, surface, caps) if full_cuts == "sealed" else []
    windows = scan.sweep()
    paths = [{"window": None, "voxels_zyx": _escape_path(barrier, crop.seed_zyx)}]
    for window in windows:
        paths.append({"window": scan.trials[window]["from_start"], "voxels_zyx": scan.trace(window)})
    paths_mask = np.zeros_like(barrier)
    for path in paths:
        if path["voxels_zyx"]:
            paths_mask[tuple(np.asarray(path["voxels_zyx"]).T)] = True
    near_wall = binary_dilation(surface, structure=NEIGHBOURHOOD)
    candidates = binary_dilation(paths_mask, structure=NEIGHBOURHOOD) & near_wall & ~barrier
    # Preserve pre-existing enclosed voids, the original seed and a collar at the grid edge.
    candidates &= classify_surface_by_flood_fill(barrier) != INTERIOR
    candidates[crop.seed_zyx] = False
    for axis in range(3):
        candidates.swapaxes(0, axis)[[0, -1]] = False
    indices = np.argwhere(candidates)
    wall_pairs = _pair_support(surface, indices)
    barrier_pairs = _pair_support(barrier, indices)
    closing = binary_closing(barrier, structure=NEIGHBOURHOOD)
    seam = binary_dilation(caps.any(axis=0), structure=NEIGHBOURHOOD)
    idx = tuple(indices.T)
    interpolated = closing[idx] & ((wall_pairs >= 2) | (seam[idx] & (wall_pairs >= 1) & (barrier_pairs >= 2)))

    if len(indices):
        # Prefer plausible gaps on the route before choosing a compact inspection region.
        scores = 10 * interpolated + 3 * paths_mask[idx] + wall_pairs
        focus = indices[int(scores.argmax())]
    else:
        focus = np.array(crop.seed_zyx)
    lower = np.maximum(focus - FOCUS_RADIUS_VOXELS, 0)
    upper = np.minimum(focus + FOCUS_RADIUS_VOXELS + 1, surface.shape)
    slices = tuple(slice(int(lo), int(hi)) for lo, hi in zip(lower, upper))
    region = candidates.copy()
    region[slices] = True
    if progress is not None:
        progress(f"Testadas {len(scan.trials)} janelas. Conferindo pontos nos bins suspeitos.")
    crop_counts, crop_points, _, _ = _point_evidence(crop.source, crop.origin_xyz, crop, region, slices)
    raw_counts = raw_selected = None
    raw_points = []
    raw_status = "source_not_in_plan"
    raw_error = None
    raw_stat = None
    if context.raw_source is not None:
        try:
            if progress is not None:
                progress(f"Comparando os mesmos bins na nuvem original: {context.raw_source.name}")
            raw_counts, raw_points, raw_selected, raw_stat = _point_evidence(
                context.raw_source, context.raw_offset, crop, region, slices, check_selection=True
            )
            raw_status = "compared"
        except (OSError, ValueError) as error:
            raw_status = "unavailable"
            raw_error = str(error)

    # Only original points inside the configured crop can support a direct restoration.
    measured = raw_selected[idx] >= MIN_RAW_POINTS if raw_selected is not None else np.zeros(len(indices), bool)
    xyz = (indices[:, ::-1] + 0.5) * crop.voxel_size
    inside_selection = np.all((xyz >= crop.selection_min_local) & (xyz < crop.selection_max_local), axis=1)
    for section in crop.sections:
        inside_selection &= (xyz - section.point) @ section.normal >= -crop.config["plane_tolerance"]

    protected_seeds = {
        tuple(row["seed_zyx"]) for row in scan.trials.values() if row["outcome"] == "sealed"
    }
    spine_bins = np.floor(scan.points[:, ::-1] / crop.voxel_size).astype(int)
    spine_bins = spine_bins[np.all((spine_bins >= 0) & (spine_bins < surface.shape), axis=1)]
    candidates[tuple(spine_bins.T)] = False
    for seed in protected_seeds:
        candidates[seed] = False
    candidates[idx] &= inside_selection & (interpolated | measured)
    support = np.zeros(crop.shape_zyx, dtype=np.intp)
    support[idx] = 100 * measured + 10 * wall_pairs + barrier_pairs
    ambiguous = {"outra_passagem_ou_retorno_proximo", "curva_cruza_plano_de_extremidade"}
    reasons = crop.config.get("proposal", {}).get("review_reasons", [])
    if ambiguous.intersection(reasons):
        air, patch, tested, outcome = None, np.zeros_like(barrier), [], "ambiguous_passage"
    else:
        air, patch, tested, outcome = _look_for_patch(
            barrier, candidates, support, crop.seed_zyx, protected_seeds
        )
    repair = patch if air is not None else np.zeros_like(barrier)

    report = {
        "method": "transverse_probe_local_repair_v1",
        "outcome": outcome,
        "axis_order": "ZYX",
        "voxel_size": crop.voxel_size,
        "units": crop.config["units"],
        "crop_id": crop.config["crop_id"],
        "crop_source_path": str(crop.source),
        "grid_origin_xyz": crop.origin_xyz.tolist(),
        "raw_grid_origin_xyz": context.raw_offset.tolist(),
        "axis_source": context.axis_source,
        "centreline_path": str(context.centreline_path) if context.centreline_path else None,
        "parameters": {
            "window_voxels": WINDOW_VOXELS, "stride_voxels": STRIDE_VOXELS,
            "min_window_voxels": MIN_WINDOW_VOXELS, "max_cap_offset_voxels": MAX_CAP_OFFSET_VOXELS,
            "max_patch_voxels": MAX_PATCH_VOXELS, "min_raw_points": MIN_RAW_POINTS,
        },
        "full_temporary_end_planes": full_cuts,
        "double_cap_trials": double_cap_trials,
        "windows": list(scan.trials.values()),
        "leaking_intervals": [scan.trials[w]["from_start"] for w in windows],
        "escape_paths": paths,
        "point_comparison": {
            "raw_status": raw_status, "raw_error": raw_error,
            "raw_source_path": str(context.raw_source) if context.raw_source else None,
            "raw_source_size_bytes": raw_stat.st_size if raw_stat else None,
            "raw_source_mtime_ns": raw_stat.st_mtime_ns if raw_stat else None,
            "eligible_voxels": int(np.count_nonzero(candidates)),
            "candidate_bins": [
                {
                    "voxel_zyx": loc.tolist(), "crop_points": int(crop_counts[tuple(loc)]),
                    "raw_points": int(raw_counts[tuple(loc)]) if raw_counts is not None else None,
                    "raw_points_in_selection": (
                        int(raw_selected[tuple(loc)]) if raw_selected is not None else None
                    ),
                    "opposite_wall_pairs": int(wall_pairs[i]),
                    "support": "original_points" if measured[i] else (
                        "local_continuity" if interpolated[i] else "insufficient"
                    ),
                    "eligible": bool(candidates[tuple(loc)]),
                }
                for i, loc in enumerate(indices)
            ],
        },
        "protected_seed_count": len(protected_seeds),
        "tested_patch_zyx": tested,
        "repair_zyx": np.argwhere(repair).tolist(),
        "focus": {
            "voxel_zyx": focus.tolist(), "min_zyx": lower.tolist(),
            "surface": surface[slices].tolist(), "caps": caps.any(axis=0)[slices].tolist(),
            "repair": repair[slices].tolist(), "escape": paths_mask[slices].tolist(),
            "crop_sample_zyx": crop_points, "raw_sample_zyx": raw_points,
        },
    }
    return LeakAnalysis(report, repair, air)
