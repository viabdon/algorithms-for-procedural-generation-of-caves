"""Public reference audit, partition integrity and Colab packaging contracts."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from cavegen.core.surface_filling import INTERIOR, classify_surface_by_flood_fill
from cavegen.core.volume import Volume3D
from cavegen.datastream.surface_io import save_surface_npz
from cavegen.datastream.voxel_io import save_volume_npz
from cavegen.training.reference_data import (
    CANDIDATE_SEMANTIC, audit_references, canonical_hash, make_splits,
    read_reference, verify_splits,
)


def write_caves(root: Path, resolution: int = 16) -> dict:
    for i, name in enumerate(("Archamps", "CascadeDeMotiers", "IndianTunnel", "MarkovSpodmol")):
        directory = root / name / f"{resolution}x{resolution}x{resolution}"
        surface = np.zeros((resolution,) * 3, dtype=bool)
        upper = 8 + i
        surface[2:upper, 2:upper, 2:upper] = True
        surface[3:upper-1, 3:upper-1, 3:upper-1] = False
        metadata = {"kind": "surface_voxels", "semantic": "true_means_observed_surface",
                    "source_path": f"/{name}.las", "min_xyz": [0, 0, 0],
                    "max_xyz": [1, 1, 1], "volume_shape_zyx": [resolution] * 3}
        save_surface_npz(surface, directory / "surface.npz", metadata)
        air = classify_surface_by_flood_fill(surface) == INTERIOR
        save_volume_npz(Volume3D(air, {**metadata, "kind": "candidate_cave_void",
                         "semantic": CANDIDATE_SEMANTIC}), directory / "interior.npz")
    return audit_references(root)


def rehash(splits: dict) -> dict:
    splits["splits_id"] = canonical_hash({k: v for k, v in splits.items() if k != "splits_id"})
    return splits


def test_audit_distinguishes_air_and_surfaces_and_reproduces_filling(tmp_path):
    audit = write_caves(tmp_path)
    assert len(audit["records"]) == 8
    air = [r for r in audit["records"] if r["candidate"]]
    assert len(air) == 4
    assert all(r["flood_fill_reproduced"] and r["eligible_proxy"] for r in air)
    assert all(not r["eligible_proxy"] for r in audit["records"] if not r["candidate"])
    assert audit == audit_references(tmp_path)
    assert len({r["sha256"] for r in air}) == 4


def test_every_cave_held_out_once_and_rotations_are_not_new_groups(tmp_path):
    audit = write_caves(tmp_path)
    splits = make_splits(audit)
    held_out = []
    for fold in splits["folds"]:
        samples = verify_splits(splits, tmp_path, fold["id"])
        assert [r["split"] for r in samples].count("train") == 2
        held_out += [r["group"] for r in samples if r["split"] == "test"]
    assert len(held_out) == len(set(held_out)) == 4


def test_split_rejects_tampering_leakage_and_changed_files(tmp_path):
    splits = make_splits(write_caves(tmp_path))
    fold = splits["folds"][0]
    altered = copy.deepcopy(splits)
    altered["folds"][0]["samples"][0]["split"] = "train"
    with pytest.raises(ValueError, match="fingerprint"):
        verify_splits(altered, tmp_path, fold["id"])
    altered = copy.deepcopy(splits)
    altered["folds"][0]["samples"].append({**fold["samples"][0], "split": "train"})
    with pytest.raises(ValueError, match="Leakage"):
        verify_splits(rehash(altered), tmp_path, fold["id"])
    path = tmp_path / fold["samples"][0]["path"]
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Changed reference"):
        verify_splits(splits, tmp_path, fold["id"])


def test_split_rejects_escape_paths_and_insufficient_groups(tmp_path):
    audit = write_caves(tmp_path)
    splits = make_splits(audit)
    splits["folds"][0]["samples"][0]["path"] = "../../outside.npz"
    with pytest.raises(ValueError, match="Unsafe"):
        verify_splits(rehash(splits), tmp_path, splits["folds"][0]["id"])
    audit["records"] = [r for r in audit["records"] if r["group"] == "archamps"]
    with pytest.raises(ValueError, match="three independent"):
        make_splits(audit)


@pytest.mark.parametrize("invalid", [np.ones((3, 3)), np.full((3, 3, 3), 0.1),
                                     np.full((3, 3, 3), np.nan)])
def test_read_reference_never_silently_converts_probabilities(tmp_path, invalid):
    path = tmp_path / "invalid.npz"
    np.savez(path, data=invalid, metadata=json.dumps({}))
    with pytest.raises(ValueError, match="binary"):
        read_reference(path)


def test_duplicate_air_cannot_inflate_dataset(tmp_path):
    write_caves(tmp_path)
    source = next(tmp_path.rglob("interior.npz"))
    destination = source.with_name("copy.npz")
    destination.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="Duplicate air"):
        audit_references(tmp_path)


def test_sparse_air_is_reported_as_blocked(tmp_path):
    audit = write_caves(tmp_path)
    for index, path in enumerate(sorted(tmp_path.rglob("interior.npz"))):
        data, metadata, _ = read_reference(path)
        data[:] = False
        data[4 + index, 4, 4] = True
        save_volume_npz(Volume3D(data, metadata), path)
    # The one-voxel interiors are not consistent with their surfaces either.
    result = audit_references(tmp_path)
    assert all(not r["geometry_screen_passed"] for r in result["records"] if r["candidate"])


def test_colab_bundle_contains_audited_inputs_and_no_raw_clouds(tmp_path):
    import zipfile
    from cavegen.training.prepare_colab import build_bundle

    repository = tmp_path / "repo"
    audit = write_caves(repository / "data/processed/references")
    files = {"README.md": "test", "pyproject.toml": "test", "src/cavegen/__init__.py": "",
             "docs/plano-redes-neurais.md": "plan", "docs/auditoria/origem_nuvens.csv": "test",
             "docs/plano-reconstrucao-secoes.md": "reconstruction plan",
             "docs/planejamento-recortes-voxelizacao.md": "crop bounds plan",
             "docs/resumo-gargalo-gan.md": "plain language summary",
             "docs/preparacao-volumes.md": "preparation guide",
             "data/processed/README.md": "data layout",
             "docs/auditoria/gan/splits.json": json.dumps(make_splits(audit)),
             "data/raw/private.las": "must not be included"}
    for name, content in files.items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    bundle = build_bundle(repository, tmp_path / "bundle.zip")
    with zipfile.ZipFile(bundle) as archive:
        assert "bundle_manifest.json" in archive.namelist()
        assert "docs/planejamento-recortes-voxelizacao.md" in archive.namelist()
        assert "docs/plano-reconstrucao-secoes.md" in archive.namelist()
        assert "docs/resumo-gargalo-gan.md" in archive.namelist()
        assert not any(name.startswith("data/raw") for name in archive.namelist())
        manifest = json.loads(archive.read("bundle_manifest.json"))
        import hashlib
        assert all(hashlib.sha256(archive.read(name)).hexdigest() == digest
                   for name, digest in manifest.items())


def test_audit_cli_still_emits_report_when_splits_are_impossible(tmp_path):
    from cavegen.training.reference_data import main

    root = tmp_path / "references"
    write_caves(root)
    for path in root.rglob("interior.npz"):
        data, metadata, _ = read_reference(path)
        data[:] = False
        save_volume_npz(Volume3D(data, metadata), path)
    origins = tmp_path / "origin.csv"
    origins.write_text("arquivo_relativo\n", encoding="utf-8")
    output = tmp_path / "audit"
    main(["--root", str(root), "--origins", str(origins), "--output", str(output)])
    assert len(json.loads((output / "reference_audit.json").read_text())["records"]) == 8
    assert json.loads((output / "splits.json").read_text())["folds"] == []
