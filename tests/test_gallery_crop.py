"""Prepare a synthetic gallery through the same JSON and menu used locally."""

import json

import numpy as np
import pytest

from cavegen.datastream.gallery_crop import prepare_crop, process_crop
from cavegen.datastream.menu import main
from cavegen.datastream.surface_io import load_surface_npz
from cavegen.datastream.voxel_io import load_volume_npz


@pytest.fixture
def gallery(tmp_path):
    split_path = tmp_path / "docs/auditoria/gan/splits.json"
    split_path.parent.mkdir(parents=True)
    split_path.write_text(json.dumps({"folds": [{"id": "pilot", "groups": {"cave": "train"}}]}))

    wall = np.zeros((10, 10, 10), dtype=bool)
    wall[2:8, (3, 6), 2:8] = True
    wall[2:8, 3:7, (2, 7)] = True
    xyz = np.argwhere(wall)[:, ::-1] + 0.5
    extras = [[1, 4, 1.5], [4, 4, 8.5], [9, 4, 4.5], [0, 4, 4.5]]
    source = tmp_path / "cloud with spaces.xyz"
    np.savetxt(source, np.vstack((xyz, extras)))
    config_path = tmp_path / "crop.json"
    spec = {
        "cave": "cave",
        "survey": "survey",
        "fold": "pilot",
        "crop_id": "gallery",
        "branch": "main",
        "source": source.name,
        "units": "m",
        "origin_xyz": [0, 0, 0],
        "selection_min_xyz": [1, 1, 1],
        "selection_max_xyz": [9, 9, 9],
        "shape_zyx": [10, 10, 10],
        "voxel_size": 1,
        "batch_size": 7,
        "progress_every": 40,
        "sections": [
            {
                "point_xyz": [2, 3, 2.5],
                "inward_normal_xyz": [0, 0, 1],
                "u_xyz": [1, 0, 1],
                "polygon_uv": [[0, 0], [6, 0], [6, 4], [0, 4]],
            },
            {
                "point_xyz": [2, 3, 7.5],
                "inward_normal_xyz": [0, 0, -1],
                "u_xyz": [1, 0, 1],
                "polygon_uv": [[0, 0], [0, -4], [6, -4], [6, 0]],
            },
        ],
        "seed_xyz": [4.5, 4.5, 4.5],
    }
    config_path.write_text(json.dumps(spec))
    return config_path, spec, source, wall


def test_crop_outputs_and_selection_are_independent_of_batch_size(gallery, tmp_path):
    path, spec, _, wall = gallery
    first = prepare_crop(path, repository=tmp_path)
    milestones = []
    record = process_crop(first, progress=milestones.append)
    assert milestones == [40, 80]
    expected_air = np.zeros_like(wall)
    expected_air[3:7, 4:6, 3:7] = True

    surface, _ = load_surface_npz(first.destination / "surface.npz")
    np.testing.assert_array_equal(surface, wall)
    air = load_volume_npz(first.destination / "interior.npz")
    np.testing.assert_array_equal(air.data, expected_air)
    assert record["counts"] == {"read": 100, "candidate": 98, "retained": 96, "outside_grid": 0}
    assert record["candidate_volume"] == 32
    assert record["partition"] == "train"
    assert record["status"] == "pending_review"
    assert json.loads((first.destination / "run.json").read_text()) == record
    with np.load(first.destination / "masks.npz") as masks:
        assert masks["caps"].shape == (2, *wall.shape)

    spec.update(crop_id="other_batch", batch_size=1000)
    path.write_text(json.dumps(spec))
    second = prepare_crop(path, repository=tmp_path)
    assert process_crop(second)["counts"] == record["counts"]
    np.testing.assert_array_equal(load_volume_npz(second.destination / "interior.npz").data, air.data)
    with pytest.raises(FileExistsError):
        process_crop(first)


def test_lateral_leak_produces_no_outputs(gallery, tmp_path):
    path, _, source, wall = gallery
    wall[4, 3, 4] = False
    np.savetxt(source, np.argwhere(wall)[:, ::-1] + 0.5)
    crop = prepare_crop(path, repository=tmp_path)
    with pytest.raises(ValueError, match="exterior"):
        process_crop(crop)
    assert not crop.destination.exists()


def test_menu_previews_and_requires_explicit_confirmation(gallery, tmp_path, monkeypatch, capsys):
    path, _, _, _ = gallery
    monkeypatch.chdir(tmp_path)
    crop = prepare_crop(path)
    answers = iter(["2", "2", f'"{path}"', "3", str(path), "", "0", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    main()
    assert "Partição: train" in capsys.readouterr().out
    assert not crop.destination.exists()

    answers = iter(["2", "3", str(path), "PROCESSAR", "0", "0"])
    main()
    assert "Ar candidato: 32 m³" in capsys.readouterr().out
    assert (crop.destination / "run.json").exists()
