"""Auditable reference inventory and cave-level partitions; no torch dependency."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import zoom

from cavegen.core.surface_filling import INTERIOR, classify_surface_by_flood_fill
from cavegen.core.volume import Volume3D
from cavegen.metrics import evaluate_structure

SCHEMA = "gan-reference-audit-v1"
CANDIDATE_SEMANTIC = "true_means_enclosed_unobserved_voxel"
VALID_SEMANTIC = "true_means_cave_air"
GALLERY_EVIDENCE = ("surface.npz", "masks.npz")
AIR_WINDOW_MARGIN = 2


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def voxel_hash(data: np.ndarray) -> str:
    return hashlib.sha256(str(data.shape).encode() + np.packbits(data).tobytes()).hexdigest()


def fit_gallery_air(data: np.ndarray, resolution: int) -> tuple[np.ndarray, dict]:
    """Window or pad an audited air mask with integer translations and no resampling."""
    if type(resolution) is not int or resolution <= 0:
        raise ValueError("Invalid air window resolution")
    source, target = [], []
    for axis, extent in enumerate(data.shape):
        start, stop, pad = 0, extent, 0
        if extent > resolution:
            other_axes = tuple(i for i in range(3) if i != axis)
            occupied = np.flatnonzero(data.any(axis=other_axes))
            if not occupied.size:
                raise ValueError("Empty gallery air mask")
            first, last = int(occupied[0]), int(occupied[-1])
            lower = max(0, last + AIR_WINDOW_MARGIN + 1 - resolution)
            upper = min(extent - resolution, first - AIR_WINDOW_MARGIN)
            if lower > upper:
                raise ValueError("Gallery air does not fit with exterior margin")
            start = min(max((first + last + 1 - resolution) // 2, lower), upper)
            stop = start + resolution
        elif extent < resolution:
            pad = (resolution - extent) // 2
        source.append(slice(start, stop))
        target.append(slice(pad, pad + stop - start))
    fitted = np.zeros((resolution,) * 3, dtype=bool)
    fitted[tuple(target)] = data[tuple(source)]
    if np.count_nonzero(fitted) != np.count_nonzero(data):
        raise ValueError("Gallery air window changed the air count")
    return fitted, {
        "method": "integer_window_v1", "resolution": resolution, "native_shape_zyx": list(data.shape),
        "native_voxel_sha256": voxel_hash(data), "source_start_zyx": [s.start for s in source],
        "source_stop_zyx": [s.stop for s in source], "target_start_zyx": [s.start for s in target],
        "air_voxels": int(np.count_nonzero(data)),
    }


def gallery_training_air(data: np.ndarray, row: dict) -> np.ndarray:
    if "air_window" not in row:
        return data
    window = row["air_window"]
    if "gallery_evidence" not in row or not isinstance(window, dict):
        raise ValueError("Invalid gallery air window")
    fitted, actual = fit_gallery_air(data, window.get("resolution"))
    if actual != window:
        raise ValueError("Gallery air window disagrees with source")
    return fitted


def read_reference(path: str | Path) -> tuple[np.ndarray, dict, str]:
    """Reject ambiguous, nonbinary or malformed archives instead of coercing them."""
    with np.load(path, allow_pickle=False) as archive:
        keys = [key for key in ("data", "surface_voxels") if key in archive]
        if len(keys) != 1 or "metadata" not in archive:
            raise ValueError(f"{path}: expected exactly one voxel field and JSON metadata")
        key = keys[0]
        data = archive[key]
        metadata = json.loads(str(archive["metadata"]))
    if not isinstance(metadata, dict):
        raise ValueError("Reference metadata must be an object")
    if data.ndim != 3 or not data.size or not np.isin(data, [0, 1]).all():
        raise ValueError(f"{path}: expected a nonempty binary ZYX grid")
    return data.astype(bool), metadata, key


def cave_group(source: str) -> str:
    """All resolutions/segments of the same named cave share one group."""
    name = source.lower()
    for prefix, group in (("archamps", "archamps"), ("cascadedemotiers", "cascadedemotiers"),
                          ("markovspodmol", "markovspodmol"), ("indiantunnel", "indian_tunnel"),
                          ("elaphes", "elaphes")):
        if prefix in name:
            return group
    raise ValueError(f"Unknown cave; add an explicit independence group: {source}")


def resize_binary(data: np.ndarray, resolution: int) -> np.ndarray:
    """Nearest-neighbor diagnostic only; training requires matching native size."""
    return zoom(data, [resolution / s for s in data.shape], order=0, prefilter=False)


def audit_references(root: str | Path, origins_csv: str | Path | None = None) -> dict:
    root = Path(root)
    origins = []
    if origins_csv is not None:
        with Path(origins_csv).open(encoding="utf-8-sig", newline="") as stream:
            origins = list(csv.DictReader(stream))
    records = []
    for path in sorted(root.rglob("*.npz")):
        data, metadata, key = read_reference(path)
        group = cave_group(metadata.get("source_path", path.as_posix()))
        semantic = metadata.get("semantic")
        candidate = key == "data" and semantic == CANDIDATE_SEMANTIC
        verified = key == "data" and semantic == VALID_SEMANTIC
        record = {
            "path": path.relative_to(root).as_posix(), "group": group,
            "sha256": sha256_file(path), "voxel_sha256": voxel_hash(data),
            "kind": metadata.get("kind"), "semantic": semantic, "metadata": metadata,
            "shape_zyx": list(data.shape), "axis_order": "ZYX",
            "dtype_on_load": "bool", "true_voxels": int(data.sum()),
            "true_ratio": float(data.mean()), "preprocessing_seed": None,
            "candidate": candidate, "verified_air": verified,
            "eligible_proxy": False, "issues": [], "origin": [], "sidecars": {},
        }
        origin_name = str(metadata.get("source_path", "")).replace("\\", "/").split("/")[-1]
        record["origin"] = [row for row in origins if origin_name and
                            row.get("arquivo_relativo", "").replace("\\", "/").endswith(origin_name)]
        for suffix in ("run.json", "command.json", "bounds.json"):
            sidecar = path.parent / f"surface.{suffix}"
            if sidecar.is_file():
                record["sidecars"][suffix] = {"sha256": sha256_file(sidecar),
                    "content": json.loads(sidecar.read_text(encoding="utf-8"))}
        if metadata.get("min_xyz") is not None and metadata.get("max_xyz") is not None:
            span = np.asarray(metadata["max_xyz"]) - np.asarray(metadata["min_xyz"])
            target_span = np.asarray(data.shape[::-1]) - 1
            positive = span > 0
            if positive.any() and (target_span[positive] > 0).all():
                record["estimated_grid_spacing_source_units"] = float(
                    1 / np.min(target_span[positive] / span[positive]))
        if key == "surface_voxels":
            record["issues"].append("observed_surface_is_not_cave_air")
        elif not (candidate or verified):
            record["issues"].append("unknown_air_semantics")
        if not record["origin"]:
            record["issues"].append("origin_not_matched")
        if candidate or verified:
            record["structure"] = evaluate_structure(Volume3D(data)).to_record()
            if record["structure"]["is_degenerate"]:
                record["issues"].append("degenerate_air")
            coords = np.argwhere(data)
            record["air_bbox_shape_zyx"] = ((coords.max(0) - coords.min(0) + 1).tolist()
                                                   if len(coords) else [0, 0, 0])
            surface_path = path.parent / "surface.npz"
            consistency = False
            if surface_path.is_file():
                surface, surface_meta, surface_key = read_reference(surface_path)
                if surface_key == "surface_voxels" and surface.shape == data.shape:
                    reconstructed = classify_surface_by_flood_fill(surface) == INTERIOR
                    consistency = bool(np.array_equal(data, reconstructed))
                    record["surface_overlap_voxels"] = int((surface & data).sum())
                    record["flood_fill_reproduced"] = consistency
                    bounds_match = all(metadata.get(k) == surface_meta.get(k)
                                       for k in ("min_xyz", "max_xyz", "volume_shape_zyx"))
                    record["surface_metadata_matches"] = bounds_match
                    consistency = consistency and bounds_match
            if candidate and not consistency:
                record["issues"].append("candidate_not_reproduced_from_surface")
            if candidate:
                record["issues"].append("proxy_air_requires_geometric_validation")
            record["eligible_proxy"] = bool((verified or consistency) and data.any()
                                             and not data.all())
            # Engineering screen, not a certification of physical cave geometry.
            # Reject isolated speckles and sub-two-voxel radii before costly GAN runs.
            metrics = record["structure"]
            record["geometry_screen_passed"] = bool(
                metrics["largest_component_voxels"] >= 64 and (metrics["dt_max"] or 0) >= 2)
            if not record["geometry_screen_passed"]:
                record["issues"].append("insufficient_resolved_interior_geometry")
            record["resolution_diagnostics"] = []
            for size in (16, 32, 64):
                reduced = resize_binary(data, size)
                restored = zoom(reduced, [s / size for s in data.shape], order=0,
                                prefilter=False)
                intersection = int((restored & data).sum())
                record["resolution_diagnostics"].append({"resolution": size,
                    **evaluate_structure(Volume3D(reduced)).to_record(),
                    "roundtrip_air_recall": intersection / int(data.sum()) if data.any() else None,
                    "roundtrip_iou": intersection / int((restored | data).sum())
                                     if (restored | data).any() else None})
        records.append(record)
    if not records:
        raise ValueError(f"No NPZ references in {root}")
    # Identical voxel grids may not become nominally independent samples.
    seen = {}
    for record in records:
        if record["eligible_proxy"]:
            previous = seen.get(record["voxel_sha256"])
            if previous:
                raise ValueError(f"Duplicate air grid: {previous} and {record['path']}")
            seen[record["voxel_sha256"]] = record["path"]
    audit = {"schema": SCHEMA, "records": records,
             "interpretation": "candidate interiors are proxies, not validated ground truth",
             "geometry_screen": {"min_largest_component_voxels": 64, "min_dt_max_voxels": 2,
                                 "meaning": "engineering minimum, not physical validation"}}
    audit["audit_id"] = canonical_hash(audit)
    return audit


def make_splits(audit: dict) -> dict:
    """Four-cave rotating holdouts: two train, one validation, one test per fold."""
    records = [r for r in audit["records"] if r["eligible_proxy"]]
    groups = sorted({r["group"] for r in records})
    if len(groups) < 3:
        raise ValueError("At least three independent caves required for train/validation/test")
    folds = []
    for index, test in enumerate(groups):
        validation = groups[(index + 1) % len(groups)]
        assignments = {g: "test" if g == test else "validation" if g == validation else "train"
                       for g in groups}
        folds.append({"id": f"holdout_{test}", "groups": assignments,
                      "samples": [{"path": r["path"], "group": r["group"],
                                   "sha256": r["sha256"], "voxel_sha256": r["voxel_sha256"],
                                   "geometry_screen_passed": r["geometry_screen_passed"],
                                   "candidate": r["candidate"], "split": assignments[r["group"]],
                                   **({"gallery_evidence": r["gallery_evidence"]}
                                      if "gallery_evidence" in r else {}),
                                   **({"air_window": r["air_window"]} if "air_window" in r else {})}
                                  for r in records]})
    result = {"schema": "gan-cave-splits-v1", "audit_id": audit["audit_id"],
              "unit_of_independence": "cave", "folds": folds,
              "data_status": "screen_passed" if all(r["geometry_screen_passed"] for r in records)
                             else "blocked_insufficient_interior_geometry",
              "seed_policy": "arbitrary inference seeds; fixed validation seeds; never split by noise"}
    result["splits_id"] = canonical_hash(result)
    return result


def verify_splits(splits: dict, root: str | Path, fold_id: str) -> list[dict]:
    """Check integrity, group isolation, paths and file identity before data access."""
    payload = {k: v for k, v in splits.items() if k != "splits_id"}
    if canonical_hash(payload) != splits.get("splits_id"):
        raise ValueError("Partition manifest fingerprint mismatch")
    fold = next((f for f in splits["folds"] if f["id"] == fold_id), None)
    if fold is None:
        raise ValueError(f"Unknown fold {fold_id}")
    root = Path(root).resolve()
    group_splits, voxel_splits, paths = {}, {}, set()
    for row in fold["samples"]:
        if row["split"] not in ("train", "validation", "test"):
            raise ValueError("Invalid split")
        for mapping, key in ((group_splits, row["group"]), (voxel_splits, row["voxel_sha256"])):
            if key in mapping and mapping[key] != row["split"]:
                raise ValueError("Leakage across partitions")
            mapping[key] = row["split"]
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root) or path in paths:
            raise ValueError("Unsafe or duplicate reference path")
        paths.add(path)
        if sha256_file(path) != row["sha256"]:
            raise ValueError(f"Changed reference file: {row['path']}")
        data, metadata, key = read_reference(path)
        if key != "data" or voxel_hash(gallery_training_air(data, row)) != row["voxel_sha256"]:
            raise ValueError("Reference voxel identity mismatch")
        if "gallery_evidence" in row:
            evidence = row["gallery_evidence"]
            if not isinstance(evidence, dict) or set(evidence) != set(GALLERY_EVIDENCE) or not row.get("candidate"):
                raise ValueError("Invalid gallery evidence")
            for name in GALLERY_EVIDENCE:
                artifact = (path.parent / name).resolve()
                if not artifact.is_relative_to(root) or sha256_file(artifact) != evidence[name]:
                    raise ValueError(f"Changed gallery evidence: {row['path']} ({name})")
            group = metadata.get("config", {}).get("cave")
        else:
            group = cave_group(metadata.get("source_path", row["path"]))
        if group != row["group"]:
            raise ValueError("Cave group disagrees with source provenance")
    if set(group_splits.values()) != {"train", "validation", "test"}:
        raise ValueError("All three partitions must be nonempty")
    return fold["samples"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/processed/references")
    parser.add_argument("--origins", default="docs/auditoria/origem_nuvens.csv")
    parser.add_argument("--output", default="docs/auditoria/gan")
    args = parser.parse_args(argv)
    audit = audit_references(args.root, args.origins)
    try:
        splits = make_splits(audit)
    except ValueError as error:
        # Still deliver an audit when the inventory cannot support a split.
        # Replace stale partitions with a visibly blocked manifest.
        splits = {"schema": "gan-cave-splits-v1", "audit_id": audit["audit_id"],
                  "unit_of_independence": "cave", "folds": [],
                  "data_status": "blocked_insufficient_independent_candidates",
                  "reason": str(error)}
        splits["splits_id"] = canonical_hash(splits)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("reference_audit.json", audit), ("splits.json", splits)):
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                             allow_nan=False) + "\n", encoding="utf-8")
    print(f"Audited {len(audit['records'])} files; {len(splits['folds'])} cave holdouts. No training.")


if __name__ == "__main__":
    main()
