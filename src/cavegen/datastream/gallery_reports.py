"""Write compact gallery diagnostics and replay the independent flood-fill checks."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from importlib.metadata import version
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np
from scipy.ndimage import generate_binary_structure, label

from cavegen.core.surface_filling import EXTERIOR, INTERIOR, classify_surface_by_flood_fill
from cavegen.datastream.surface_io import load_surface_npz
from cavegen.datastream.voxel_io import load_volume_npz

if TYPE_CHECKING:
    from cavegen.datastream.gallery_crop import GalleryCrop

REPORT_FOLDER = "diagnostics"
SUMMARY_FILE = "summary.csv"
PREVIEW_FILE = "preview_data.npz"
CHECK_COLUMNS = ("check", "result", "expected", "passed", "voxel_count", "z", "y", "x")
PROBE_PARAMETERS = (
    "window_voxels", "stride_voxels", "min_window_voxels", "max_cap_offset_voxels",
    "max_patch_voxels", "min_raw_points",
)


def check(name, result, expected=None, *, count=None, voxel=(None, None, None)) -> dict:
    return dict(zip(CHECK_COLUMNS, (
        name, result, expected, None if expected is None else bool(result == expected),
        count, *voxel,
    )))


def _seed_state(classification: np.ndarray, seed: tuple[int, int, int]) -> str:
    if classification[seed] == EXTERIOR:
        return "exterior"
    return "interior" if classification[seed] == INTERIOR else "blocked"


def audit_flood_fill(
    surface: np.ndarray,
    caps: np.ndarray,
    repair: np.ndarray,
    seed: tuple[int, int, int],
    air: np.ndarray | None,
    *,
    expected_original: str,
    auxiliary: np.ndarray | None = None,
) -> list[dict]:
    """Flood from the grid boundary, independently of the repair search from the seed."""
    original = surface | caps.any(axis=0)
    original_classification = classify_surface_by_flood_fill(original)
    original_state = _seed_state(original_classification, seed)
    checks = [check("outside_fill_without_repair", original_state, expected_original)]
    if air is None:
        return checks

    if auxiliary is None:
        auxiliary = np.zeros_like(surface)
    if auxiliary.any():
        checks.append(check("auxiliary_overlap", int((auxiliary & (original | repair | air)).sum()), 0))
        without = classify_surface_by_flood_fill(original | repair)
        checks.append(check("remove_auxiliary_caps", _seed_state(without, seed), "exterior"))
    additions = repair | auxiliary
    final = classify_surface_by_flood_fill(original | additions) if additions.any() else original_classification
    state = _seed_state(final, seed)
    checks.append(check("outside_fill_final", state, "interior"))
    labels, _ = label(final == INTERIOR, structure=generate_binary_structure(3, 1))
    isolated = (labels == labels[seed]) if state == "interior" else np.zeros_like(air)
    checks.append(check("candidate_air_component", "match" if np.array_equal(isolated, air) else "mismatch",
                        "match", count=int(np.count_nonzero(isolated))))
    overlap = int(np.count_nonzero(repair & (original | air)))
    checks.append(check("repair_overlap", overlap, 0, count=overlap))
    for index, name in enumerate(("remove_initial_cap", "remove_final_cap")):
        reduced = surface | caps[1 - index] | additions
        checks.append(check(name, _seed_state(classify_surface_by_flood_fill(reduced), seed)))
    for voxel in map(tuple, np.argwhere(repair)):
        reduced = original | additions
        reduced[voxel] = original[voxel]
        state = _seed_state(classify_surface_by_flood_fill(reduced), seed)
        checks.append(check("remove_repair_voxel", state, "exterior", voxel=voxel))
    return checks


def _write_csv(path: Path, fields, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _coords(values, axes, prefix="") -> dict:
    return {f"{prefix}{axis}": value for axis, value in zip(axes, values)}


def _write_leak_tables(folder: Path, report: dict, *, published: bool) -> None:
    span_columns = ("from_start", "to_start")
    probe_columns = (
        "probe", "stage", *span_columns, "offset_start_voxels", "offset_end_voxels",
        "seed_z", "seed_y", "seed_x", "outcome",
    )
    rows = [{"probe": "full_end_planes", "outcome": report["full_temporary_end_planes"]}]
    rows.extend({
        "probe": "double_cap",
        "offset_start_voxels": trial["offset_voxels"][0],
        "offset_end_voxels": trial["offset_voxels"][1],
        "outcome": trial["outcome"],
    } for trial in report["double_cap_trials"])
    refined_leaks = set(map(tuple, report["leaking_intervals"]))
    rows.extend({
        "probe": "transverse_window",
        "stage": row["stage"],
        **dict(zip(span_columns, row["from_start"])),
        **_coords(row["seed_zyx"], "zyx", "seed_"),
        "outcome": row["outcome"],
    } for row in report["windows"])
    _write_csv(folder / "probes.csv", (*probe_columns, "refined_leak_interval"), (
        {**row, "refined_leak_interval": (
            (row["from_start"], row["to_start"]) in refined_leaks if row["probe"] == "transverse_window"
            else None
        )} for row in rows
    ))

    repaired = set(map(tuple, report["repair_zyx"])) if published else set()
    attempted = set(map(tuple, report["tested_patch_zyx"]))
    on_path = {tuple(voxel) for route in report["escape_paths"] for voxel in route["voxels_zyx"]}
    raw_origin = np.array(report["raw_grid_origin_xyz"])
    spacing = report["voxel_size"]
    evidence = ("crop_points", "raw_points", "raw_points_in_selection", "opposite_wall_pairs", "support")
    columns = ("z", "y", "x", "source_x", "source_y", "source_z", *evidence,
               "on_escape_path", "eligible", "tested", "published")

    def bins():
        for row in report["point_comparison"]["candidate_bins"]:
            loc = tuple(row["voxel_zyx"])
            center = raw_origin + (np.array(loc[::-1]) + 0.5) * spacing
            yield {
                **_coords(loc, "zyx"),
                **_coords(center, "xyz", "source_"),
                **{key: row[key] for key in evidence},
                "on_escape_path": loc in on_path, "eligible": row["eligible"],
                "tested": loc in attempted, "published": loc in repaired,
            }

    _write_csv(folder / "bins.csv", columns, bins())
    _write_csv(folder / "paths.csv", ("route", *span_columns, "step", "z", "y", "x"), (
        {
            "route": i, **dict(zip(span_columns, route["window"] or (None, None))),
            "step": step, **_coords(voxel, "zyx"),
        }
        for i, route in enumerate(report["escape_paths"])
        for step, voxel in enumerate(route["voxels_zyx"])
    ))

    focus = report["focus"]
    masks = {key: np.asarray(focus[key]) for key in ("surface", "caps", "repair", "escape")}
    if not published:
        masks["repair"] = np.zeros_like(masks["repair"])
    np.savez_compressed(
        folder / PREVIEW_FILE,
        **masks, voxel_zyx=focus["voxel_zyx"], min_zyx=focus["min_zyx"],
        **{key: np.asarray(focus[key], dtype=np.float32) for key in ("crop_sample_zyx", "raw_sample_zyx")},
    )


def write_report(
    folder: Path, crop: GalleryCrop, record: dict, checks: list[dict], *,
    outcome: str, leak: dict | None = None, error: str | None = None,
) -> None:
    """Publish small tabular evidence. Reusable local plotting data stays in NPZ."""
    folder.mkdir()
    comparison = leak["point_comparison"] if leak is not None else {}
    raw_origin = crop.origin_xyz + np.array(crop.config.get("source_origin_xyz", [0, 0, 0]))
    summary = {
        "schema": "gallery_voxelization_report_v1",
        "cave": crop.config["cave"], "survey": crop.config["survey"], "fold": crop.config["fold"],
        "plan_id": crop.config.get("plan_id"), "crop_id": crop.config["crop_id"],
        "partition": crop.partition, "outcome": outcome, "review_status": record.get("status"),
        "method": record.get("method"), "error": error,
        "config_path": str(crop.config_path), "crop_source": str(crop.source),
        "crop_source_size_bytes": record["source_size_bytes"],
        "crop_source_mtime_ns": record["source_mtime_ns"],
        "axis_order": "ZYX", "units": crop.config["units"], "voxel_size": crop.voxel_size,
        **_coords(crop.shape_zyx, "zyx", "shape_"),
        **_coords(crop.seed_zyx, "zyx", "seed_"),
        **_coords(crop.origin_xyz, "xyz", "crop_grid_origin_"),
        **_coords(raw_origin, "xyz", "source_grid_origin_"),
        **{f"points_{key}": value for key, value in record["counts"].items()},
        "surface_voxels": record.get("surface_voxels"),
        "initial_cap_voxels": record.get("cap_voxels", [None, None])[0],
        "final_cap_voxels": record.get("cap_voxels", [None, None])[1],
        "auxiliary_cap_voxels": record.get("auxiliary_cap_voxels", 0),
        "auxiliary_cap_radius_voxels": record.get("auxiliary_cap_radius_voxels", 0),
        "repair_voxels": record.get("repair_voxels"),
        "candidate_air_voxels": record.get("air_voxels"),
        "candidate_volume": record.get("candidate_volume"),
        "diagnostic_method": leak["method"] if leak is not None else None,
        "axis_source": leak["axis_source"] if leak is not None else None,
        "centreline_path": leak["centreline_path"] if leak is not None else None,
        "raw_comparison": comparison.get("raw_status", "not_needed"),
        "raw_source": comparison.get("raw_source_path"), "raw_error": comparison.get("raw_error"),
        "raw_source_size_bytes": comparison.get("raw_source_size_bytes"),
        "raw_source_mtime_ns": comparison.get("raw_source_mtime_ns"),
        "protected_seeds": leak["protected_seed_count"] if leak is not None else None,
        "eligible_voxels": comparison.get("eligible_voxels"),
        **{key: leak["parameters"][key] if leak is not None else None for key in PROBE_PARAMETERS},
        "numpy": np.__version__, "scipy": version("scipy"), "scikit_image": version("scikit-image"),
    }
    _write_csv(folder / SUMMARY_FILE, tuple(summary), [summary])
    _write_csv(folder / "checks.csv", CHECK_COLUMNS, checks)
    if leak is not None:
        _write_leak_tables(folder, leak, published=outcome == "repaired")


def write_failed_report(crop: GalleryCrop, record: dict, checks: list[dict], **details) -> Path:
    root = crop.destination.with_name(f"{crop.destination.name}.diagnostics")
    root.mkdir(parents=True, exist_ok=True)
    attempt = root / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{uuid4().hex[:8]}"
    with TemporaryDirectory(dir=root) as staged:
        folder = Path(staged) / REPORT_FOLDER
        write_report(folder, crop, record, checks, **details)
        os.rename(folder, attempt)
    return attempt


def find_report(path: Path) -> Path | None:
    """Resolve a result, an attempt or a report file, including legacy JSON."""
    if path.is_file() and path.suffix == ".json":
        return path
    if path.is_file() and path.suffix == ".csv":
        summary = path.with_name(SUMMARY_FILE)
        return summary if summary.is_file() else None
    if (path / SUMMARY_FILE).is_file():
        return path / SUMMARY_FILE
    report = path / REPORT_FOLDER / SUMMARY_FILE
    if report.is_file():
        return report
    if not path.is_dir() or path.name.endswith(".diagnostics"):
        failed = path if path.is_dir() else path.with_name(f"{path.name}.diagnostics")
        reports = sorted(failed.glob(f"*/{SUMMARY_FILE}"))
        if reports:
            return reports[-1]
    legacy = path / "leak_diagnostics.json" if path.is_dir() else path.with_name(f"{path.name}.leak.json")
    return legacy if legacy.is_file() else None


def replay_checks(folder: Path) -> Path:
    """Verify the saved masks and air without rescanning the point clouds."""
    surface, _ = load_surface_npz(folder / "surface.npz")
    interior = load_volume_npz(folder / "interior.npz")
    with np.load(folder / "masks.npz", allow_pickle=False) as masks:
        repair = masks["repair"] if "repair" in masks else np.zeros_like(surface)
        checks = audit_flood_fill(
            surface, masks["caps"], repair, tuple(interior.metadata["seed_zyx"]), interior.data,
            auxiliary=masks.get("auxiliary_caps"),
            expected_original="exterior" if repair.any() or np.any(masks.get("auxiliary_caps", False)) else "interior",
        )
    reports = folder / REPORT_FOLDER
    reports.mkdir(exist_ok=True)
    output = reports / "checks_replay.csv"
    _write_csv(output, CHECK_COLUMNS, checks)
    if any(row["passed"] is False for row in checks):
        raise ValueError(f"A reclassificação não reproduziu o resultado salvo. Veja {output}.")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclassifica um recorte salvo e registra as ablações em CSV.")
    parser.add_argument("folder", type=Path, help="pasta da resolução com surface.npz, interior.npz e masks.npz")
    args = parser.parse_args()
    try:
        print(replay_checks(args.folder))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
