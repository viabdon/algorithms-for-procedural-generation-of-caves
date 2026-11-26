"""Audit a selection of voxelized galleries for an explicit GAN proxy run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation

from cavegen.core.volume import Volume3D
from cavegen.datastream.gallery_reports import audit_flood_fill
from cavegen.metrics import evaluate_structure
from cavegen.training.reference_data import (
    GALLERY_EVIDENCE, canonical_hash, make_splits, read_reference, sha256_file, voxel_hash,
)


def _check_air(path: Path, data: np.ndarray, metadata: dict) -> list[str]:
    surface, surface_meta, key = read_reference(path.with_name("surface.npz"))
    if key != "surface_voxels" or surface.shape != data.shape or surface_meta != metadata:
        raise ValueError(f"Gallery surface does not match its interior: {path}")
    with np.load(path.with_name("masks.npz"), allow_pickle=False) as masks:
        caps = masks["caps"]
        repair = masks["repair"]
        auxiliary = masks.get("auxiliary_caps", np.zeros_like(data))
    if (caps.shape != (2, *data.shape) or repair.shape != data.shape or auxiliary.shape != data.shape
            or any(mask.dtype != bool for mask in (caps, repair, auxiliary))):
        raise ValueError(f"Gallery masks do not match the boolean interior: {path}")
    seed = metadata.get("seed_zyx")
    if (not isinstance(seed, list) or len(seed) != 3
            or any(type(i) is not int or not 0 <= i < n for i, n in zip(seed, data.shape))):
        raise ValueError(f"Invalid gallery seed: {path}")

    checks = audit_flood_fill(
        surface, caps, repair, tuple(seed), data, auxiliary=auxiliary,
        expected_original="exterior" if repair.any() or auxiliary.any() else "interior",
    )
    issues = [row["check"] for row in checks if row["passed"] is False]
    adjacent = binary_dilation(data)
    if not all((adjacent & cap).any() for cap in caps):
        issues.append("interior_does_not_reach_both_caps")
    return issues


def audit_gallery_references(
    root: str | Path, plans: list[str], *, resolution: int, voxel_size: float,
) -> dict:
    """Verify save artifacts and retain members of one native grid and scale."""
    if resolution <= 0 or not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError("Resolution and voxel size must be positive")
    root = Path(root).resolve()
    records = []
    seen: set[tuple[str, str, str]] = set()
    seen_hashes: set[str] = set()
    for name in sorted(plans):
        plan = (root / name).resolve()
        if not plan.is_relative_to(root) or not plan.is_dir():
            raise ValueError(f"Invalid gallery plan directory: {name}")
        paths = sorted(plan.glob("*/*/interior.npz"))
        if not paths:
            raise ValueError(f"No galleries saved in plan directory: {name}")
        for path in paths:
            if any(not (path.parent / artifact).resolve().is_relative_to(root)
                   for artifact in (*GALLERY_EVIDENCE, path.name)):
                raise ValueError(f"Gallery evidence is outside the reference root: {path}")
            data, metadata, key = read_reference(path)
            config = metadata.get("config", {})
            identity = tuple(config.get(k) for k in ("cave", "survey", "crop_id"))
            if (key != "data" or any(not isinstance(value, str) or not value for value in identity)
                    or config["crop_id"] != path.parents[1].name or config.get("plan_id") != plan.name):
                raise ValueError(f"Invalid gallery provenance: {path}")
            if identity in seen:
                raise ValueError(f"Multiple versions of the same gallery: {identity}")
            seen.add(identity)

            issues = _check_air(path, data, metadata)
            metrics = evaluate_structure(Volume3D(data))
            if data.shape != (resolution,) * 3:
                issues.append("incompatible_native_shape")
            if config.get("voxel_size") != voxel_size:
                issues.append("incompatible_voxel_size")
            if metrics.largest_component_voxels < 64 or (metrics.distance_max or 0) < 2:
                issues.append("insufficient_resolved_interior_geometry")
            digest = voxel_hash(data)
            if not issues and digest in seen_hashes:
                raise ValueError(f"Duplicate gallery air grid: {path}")
            if not issues:
                seen_hashes.add(digest)
            records.append({
                "path": path.relative_to(root).as_posix(), "group": identity[0],
                "sha256": sha256_file(path), "voxel_sha256": digest,
                "gallery_evidence": {filename: sha256_file(path.with_name(filename))
                                     for filename in GALLERY_EVIDENCE},
                "candidate": True, "eligible_proxy": not issues,
                "geometry_screen_passed": not issues, "issues": issues,
                "shape_zyx": list(data.shape), "voxel_size": config.get("voxel_size"),
                "crop_id": identity[2], "structure": metrics.to_record(),
                "repair_voxels": metadata.get("repair_voxels"),
                "auxiliary_cap_voxels": metadata.get("auxiliary_cap_voxels"),
                "review_status": metadata.get("status"),
            })
    if not records:
        raise ValueError("Select at least one saved gallery plan")
    result = {
        "schema": "gan-gallery-reference-audit-v1", "records": records, "plans": sorted(plans),
        "resolution": resolution, "voxel_size": voxel_size,
        "interpretation": "audited candidate air awaiting geometric review",
    }
    result["audit_id"] = canonical_hash(result)
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/processed/reference_sections"))
    parser.add_argument("--plans", nargs="+", required=True, help="Plan directories relative to root")
    parser.add_argument("--resolution", type=int, required=True)
    parser.add_argument("--voxel-size", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Choose a new output directory for the gallery proxy audit")
    audit = audit_gallery_references(args.root, args.plans, resolution=args.resolution, voxel_size=args.voxel_size)
    args.output.mkdir(parents=True)
    (args.output / "reference_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    try:
        groups = {row["group"] for row in audit["records"]}
        accepted = {row["group"] for row in audit["records"] if row["eligible_proxy"]}
        missing = sorted(groups - accepted)
        if missing:
            raise ValueError(f"No eligible crop for: {', '.join(missing)}")
        splits = make_splits(audit)
    except ValueError as error:
        parser.exit(1, f"Gallery audit saved. {error}\n")
    splits["data_status"] = "gallery_proxy_pending_review"
    splits.pop("splits_id")
    splits["splits_id"] = canonical_hash(splits)
    (args.output / "splits.json").write_text(
        json.dumps(splits, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"Audited {len(audit['records'])} galleries. Proxy manifest saved for {len(splits['folds'])} holdouts.")


if __name__ == "__main__":
    main()
