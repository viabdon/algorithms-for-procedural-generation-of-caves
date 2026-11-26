"""Prepare a synthetic gallery through the same JSON and menu used locally."""

import csv
import json

import laspy
import numpy as np
import pytest

from cavegen.core.surface_filling import INTERIOR, classify_surface_by_flood_fill
from cavegen.datastream.crop_preview import ply_header
from cavegen.datastream.gallery_crop import prepare_crop, process_crop
from cavegen.datastream.gallery_reports import find_report, replay_checks
from cavegen.datastream.menu import main
from cavegen.datastream.surface_io import load_surface_npz
from cavegen.datastream.voxel_io import load_volume_npz


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


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
    reports = first.destination / "relatorio_volume"
    assert read_rows(reports / "summary.csv")[0]["outcome"] == "sealed_without_repair"
    assert find_report(first.destination) == reports / "summary.csv"
    assert replay_checks(first.destination).parent == reports
    assert not (reports / "bins.csv").exists()
    checks = {row["check"]: row for row in read_rows(reports / "checks.csv")}
    assert checks["outside_fill_final"]["result"] == "interior"
    assert checks["remove_initial_cap"]["result"] == checks["remove_final_cap"]["result"] == "exterior"
    with np.load(first.destination / "masks.npz") as masks:
        assert masks["caps"].shape == (2, *wall.shape)

    spec.update(crop_id="other_batch", batch_size=1000)
    path.write_text(json.dumps(spec))
    second = prepare_crop(path, repository=tmp_path)
    assert process_crop(second)["counts"] == record["counts"]
    np.testing.assert_array_equal(load_volume_npz(second.destination / "interior.npz").data, air.data)
    with pytest.raises(FileExistsError):
        process_crop(first)


def test_small_lateral_gap_is_repaired_without_mutating_observations(gallery, tmp_path):
    path, spec, source, wall = gallery
    # A long enough test gallery has both sealed and leaking overlapping probes.
    wall = np.zeros((18, *wall.shape[1:]), dtype=bool)
    wall[2:16, (3, 6), 2:8] = True
    wall[2:16, 3:7, (2, 7)] = True
    missing = (8, 3, 4)
    wall[missing] = False
    spec.update(shape_zyx=[18, 10, 10], selection_max_xyz=[9, 9, 17], seed_xyz=[4.5, 4.5, 8.5])
    spec["sections"][1]["point_xyz"][2] = 15.5
    path.write_text(json.dumps(spec))
    np.savetxt(source, np.argwhere(wall)[:, ::-1] + 0.5)
    crop = prepare_crop(path, repository=tmp_path)
    record = process_crop(crop)

    surface, _ = load_surface_npz(crop.destination / "surface.npz")
    np.testing.assert_array_equal(surface, wall)
    air = load_volume_npz(crop.destination / "interior.npz").data
    with np.load(crop.destination / "masks.npz") as masks:
        np.testing.assert_array_equal(np.argwhere(masks["repair"]), [missing])
        assert not (air & (wall | masks["caps"].any(axis=0) | masks["repair"])).any()
        rerun = classify_surface_by_flood_fill(wall | masks["caps"].any(axis=0) | masks["repair"])
        assert rerun[crop.seed_zyx] == INTERIOR
    assert record["repair_voxels"] == 1
    reports = crop.destination / "relatorio_volume"
    summary = read_rows(reports / "summary.csv")[0]
    assert summary["outcome"] == "repaired"
    assert summary["raw_comparison"] == "source_not_in_plan"
    probes = read_rows(reports / "probes.csv")
    assert (probes[0]["probe"], probes[0]["outcome"]) == ("full_end_planes", "leaking")
    assert any(trial["stage"] == "refine" for trial in probes)
    assert any(trial["outcome"] == "sealed" for trial in probes)
    paths = read_rows(reports / "paths.csv")
    assert any(tuple(int(row[axis]) for axis in "zyx") == missing for row in paths)
    checks = {row["check"]: row for row in read_rows(reports / "checks.csv")}
    assert checks["outside_fill_without_repair"]["result"] == "exterior"
    assert checks["outside_fill_final"]["result"] == "interior"
    ablation = checks["remove_repair_voxel"]
    assert tuple(int(ablation[axis]) for axis in "zyx") == missing
    assert (ablation["result"], ablation["passed"]) == ("exterior", "True")
    replay = {row["check"]: row for row in read_rows(replay_checks(crop.destination))}
    assert replay["remove_repair_voxel"] == ablation
    assert replay["candidate_air_component"]["result"] == "match"


def test_large_lateral_opening_is_reported_without_an_interior(gallery, tmp_path, monkeypatch, capsys):
    path, _, source, wall = gallery
    wall[3:7, 3, 3:7] = False
    np.savetxt(source, np.argwhere(wall)[:, ::-1] + 0.5)
    crop = prepare_crop(path, repository=tmp_path)
    with pytest.raises(ValueError, match="exterior"):
        process_crop(crop)
    assert not crop.destination.exists()
    reports = crop.destination.with_name("10x10x10_sem_volume")
    (attempt,) = reports.iterdir()
    assert find_report(crop.destination) == find_report(reports) == attempt / "summary.csv"
    summary = read_rows(attempt / "summary.csv")[0]
    assert summary["outcome"] == "escape_path_without_supported_voxels"
    assert not any(row["published"] == "True" for row in read_rows(attempt / "bins.csv"))

    answers = iter(["2", "4", str(crop.destination), "0", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    main()
    html = attempt / "vazamento.html"
    assert str(html) in capsys.readouterr().out
    assert "Caminho de fuga" in html.read_text(encoding="utf-8")


def test_cap_gap_runs_double_cap_probe(gallery, tmp_path):
    path, spec, _, _ = gallery
    spec["sections"][0]["polygon_uv"] = [[0, 2], [6, 2], [6, 4], [0, 4]]
    path.write_text(json.dumps(spec))
    crop = prepare_crop(path, repository=tmp_path)
    with pytest.raises(ValueError, match="exterior"):
        process_crop(crop)
    (attempt,) = crop.destination.with_name("10x10x10_sem_volume").iterdir()
    probes = read_rows(attempt / "probes.csv")
    assert (probes[0]["probe"], probes[0]["outcome"]) == ("full_end_planes", "sealed")
    assert sum(row["probe"] == "double_cap" for row in probes) == 48


def test_blocked_seed_reports_failed_precondition(gallery, tmp_path):
    path, spec, _, _ = gallery
    spec["seed_xyz"] = [4.5, 3.5, 4.5]
    path.write_text(json.dumps(spec))
    crop = prepare_crop(path, repository=tmp_path)
    with pytest.raises(ValueError, match="semente caiu na barreira"):
        process_crop(crop)
    (attempt,) = crop.destination.with_name("10x10x10_sem_volume").iterdir()
    assert read_rows(attempt / "summary.csv")[0]["outcome"] == "seed_blocked"
    assert read_rows(attempt / "checks.csv")[-1]["passed"] == "False"
    assert not crop.destination.exists()


def test_compare_bins_with_georeferenced_original(gallery, tmp_path):
    _, spec, _, wall = gallery
    missing = [4, 3, 4]
    offset = np.array([943844.0, 6561936.0, 1044.0])
    raw_xyz = np.argwhere(wall)[:, ::-1] + 0.5 + offset
    raw = tmp_path / "original.las"
    header = laspy.LasHeader(point_format=2, version="1.2")
    header.scales = [0.001] * 3
    header.offsets = offset
    las = laspy.LasData(header)
    las.xyz = np.vstack((raw_xyz, np.array(missing)[::-1] + 0.6 + offset))
    las.write(raw)
    spec.update(
        source="cloud.ply", source_origin_xyz=offset.tolist(), branch="passagem_001",
        proposal={"cut_stations": [0, 5]},
        leak_diagnostics={"raw_source": str(raw)},
    )
    for section in spec["sections"]:
        point = np.array(section["point_xyz"])
        shift = np.array([2.5, 1.5, 0])
        section["point_xyz"] = (point + shift).tolist()
        section["polygon_uv"] = (
            np.array(section["polygon_uv"]) - [2.5, section["inward_normal_xyz"][2] * 1.5]
        ).tolist()
    graph = tmp_path / "axis.npz"
    np.savez(
        graph, nodes_xyz=np.array([s["point_xyz"] for s in spec["sections"]]) + offset,
        edges=np.array([[0, 1]]),
    )
    source = tmp_path / "plan/gallery/cloud.ply"
    source.parent.mkdir(parents=True)
    (source.parent.parent / "plan.json").write_text(json.dumps({
        "source_origin_xyz": offset.tolist(), "source": "old_missing.las",
        "centreline": str(graph), "crops": [{"crop_id": "gallery"}],
    }))
    path = source.with_name("crop.json")
    path.write_text(json.dumps(spec))
    wall[4, 3, 4] = False
    xyz = np.argwhere(wall)[:, ::-1] + 0.5
    source.write_bytes(ply_header(len(xyz)) + xyz.astype("<f8").tobytes())
    crop = prepare_crop(path, repository=tmp_path)
    record = process_crop(crop)
    reports = crop.destination / "relatorio_volume"
    summary = read_rows(reports / "summary.csv")[0]
    assert record["repair_voxels"] == 1
    assert summary["axis_source"] == "plan_centreline"
    assert summary["raw_comparison"] == "compared"
    (cell,) = (row for row in read_rows(reports / "bins.csv") if row["published"] == "True")
    assert [int(cell[axis]) for axis in "zyx"] == missing
    assert (cell["crop_points"], cell["raw_points"], cell["raw_points_in_selection"]) == ("0", "2", "2")
    assert cell["support"] == "original_points"


def test_menu_previews_and_requires_explicit_confirmation(gallery, tmp_path, monkeypatch, capsys):
    path, _, _, _ = gallery
    monkeypatch.chdir(tmp_path)
    crop = prepare_crop(path)
    answers = iter(["2", "2", f'"{path}"', "3", "1", str(path), "", "0", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    main()
    assert "Partição: train" in capsys.readouterr().out
    assert not crop.destination.exists()

    answers = iter(["2", "3", "1", str(path), "PROCESSAR", "0", "0"])
    main()
    assert "Ar candidato: 32 m³ | Reparo local: 0 voxels | Tampas sintéticas: 0 voxels" in capsys.readouterr().out
    assert (crop.destination / "run.json").exists()

    answers = iter(["2", "4", str(crop.destination), "0", "0"])
    main()
    output = crop.destination / "fatias.html"
    volume = crop.destination / "volume.html"
    menu_output = capsys.readouterr().out
    assert str(output) in menu_output
    assert str(volume) in menu_output
    call = output.read_text(encoding="utf-8").rsplit("Plotly.newPlot(", 1)[1]
    decoder = json.JSONDecoder()
    traces, _ = decoder.raw_decode(call.split(",", 1)[1].lstrip())
    assert [trace["type"] for trace in traces] == ["heatmap"] * 3
    assert [trace["xaxis"] for trace in traces] == ["x", "x2", "x3"]
    assert all(trace["customdata"][4][4] == "Ar candidato" for trace in traces)

    call = volume.read_text(encoding="utf-8").rsplit("Plotly.newPlot(", 1)[1]
    traces, _ = decoder.raw_decode(call.split(",", 1)[1].lstrip())
    assert [trace["type"] for trace in traces] == ["scatter3d"] * 3
    assert [trace["name"] for trace in traces] == ["Superfície observada", "Ar candidato", "Tampas"]
    assert [trace["visible"] for trace in traces] == [True, True, "legendonly"]


def test_menu_voxelizes_subfolders_with_progress_per_crop(gallery, tmp_path, monkeypatch, capsys):
    _, spec, source, _ = gallery
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "plano revisado"
    for name in ("ramo_001_003", "ramo_001_002", "ramo_001_001"):
        folder = root / name
        folder.mkdir(parents=True)
        config = folder / "crop.json"
        if name.endswith("002"):
            config.write_text("{")
        else:
            config.write_text(json.dumps(dict(spec, crop_id=name, source=str(source), plan_id="revisado")))
    manifest = root / "plan.json"
    manifest.write_text("{}")
    results = tmp_path / "data/processed/reference_sections/cave/survey/pilot/revisado"

    answers = iter(["2", "3", "2", str(root), "", "0", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    main()
    assert not results.exists()
    assert "3 recortes encontrados" in capsys.readouterr().out

    answers = iter(["2", "3", "2", str(root), "PROCESSAR", "0", "0"])
    main()
    output = capsys.readouterr().out
    assert output.index("[1/3 ramo_001_001] Voxelizando") < output.index("[3/3 ramo_001_003] Voxelizando")
    for label in ("[1/3 ramo_001_001]", "[3/3 ramo_001_003]"):
        assert f"{label} Pontos lidos: 40" in output
        assert f"{label} Pontos lidos: 100 | Retidos: 96" in output
    assert "[2/3 ramo_001_002] Não foi possível concluir:" in output
    assert "2 volumes salvos, 0 pulados, 1 sem volume" in output
    for name in ("ramo_001_001", "ramo_001_003"):
        assert (results / name / "10x10x10/interior.npz").exists()

    answers = iter(["2", "3", "2", str(manifest), "PROCESSAR", "0", "0"])
    main()
    output = capsys.readouterr().out
    assert "[1/3 ramo_001_001] Pulado: Já existe uma execução" in output
    assert "0 volumes salvos, 2 pulados, 1 sem volume" in output


def test_auxiliary_caps_preserve_measured_surface_and_replay(gallery, tmp_path):
    path, spec, source, wall = gallery
    wall[3:6, 3, 3:6] = False
    np.savetxt(source, np.argwhere(wall)[:, ::-1] + 0.5)
    spec["seed_xyz"] = [5.5, 5.5, 5.5]
    spec["auxiliary_cap_radius_voxels"] = 4
    path.write_text(json.dumps(spec))
    crop = prepare_crop(path, repository=tmp_path)
    record = process_crop(crop)
    assert record["repair_voxels"] == 0
    assert record["auxiliary_cap_voxels"] > 0
    np.testing.assert_array_equal(load_surface_npz(crop.destination / "surface.npz")[0], wall)
    with np.load(crop.destination / "masks.npz") as masks:
        assert masks["auxiliary_caps"].sum() == record["auxiliary_cap_voxels"]
    checks = {row["check"]: row for row in read_rows(replay_checks(crop.destination))}
    assert checks["remove_auxiliary_caps"]["result"] == "exterior"
    assert checks["candidate_air_component"]["result"] == "match"


@pytest.mark.parametrize("suffix", [".diagnostics", "_tentativas_sem_volume"])
def test_find_reports_in_legacy_folders(tmp_path, suffix):
    volume = tmp_path / "64x64x64"
    history = tmp_path / f"64x64x64{suffix}"
    attempt = history / "20260101T000000Z-failed"
    attempt.mkdir(parents=True)
    failure = attempt / "summary.csv"
    failure.touch()
    assert find_report(volume) == find_report(history) == failure

    reports = volume / "diagnostics"
    reports.mkdir(parents=True)
    success = reports / "summary.csv"
    success.touch()
    assert find_report(volume) == success
