"""Exercise automatic crop planning, point export, and independent preview."""

import json
from pathlib import Path

import numpy as np
import pytest

from cavegen.datastream.centreline import read_graph
from cavegen.datastream.crop_planner import propose_crops
from cavegen.datastream.crop_preview import write_crop_preview
from cavegen.datastream.gallery_crop import prepare_crop, process_crop
from cavegen.datastream.menu import main
from cavegen.datastream.ply import iter_ply_xyz, read_ply_header


def straight_cloud(length, y=0):
    angles = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    station, theta = np.meshgrid(np.linspace(0, length, int(length * 10) + 1), angles)
    return np.column_stack((station.ravel(), y + .8 * np.cos(theta.ravel()), .8 * np.sin(theta.ravel())))


def preview_traces(path):
    call = path.read_text(encoding="utf-8").rsplit("Plotly.newPlot(", 1)[1]
    traces, _ = json.JSONDecoder().raw_decode(call.split(",", 1)[1].lstrip())
    assert all(trace["type"] == "scatter3d" for trace in traces)
    return traces


def setup_plan(tmp_path, points, nodes, *, count=2, source_format="npz"):
    source = tmp_path / "raw cloud.xyz"
    np.savetxt(source, points)
    edges = np.column_stack((np.arange(len(nodes) - 1), np.arange(1, len(nodes))))
    if source_format == "npz":
        graph = tmp_path / "graph.npz"
        np.savez(graph, nodes_xyz=nodes, edges=edges)
    else:
        graph = tmp_path / "scan_nodes_from_LBC.txt"
        np.savetxt(graph, nodes)
        np.savetxt(tmp_path / "scan_links_from_LBC.txt", edges, fmt="%d")
    config = tmp_path / "plan.json"
    config.write_text(json.dumps({
        "source": source.name, "centreline": graph.name, "cave": "pilot",
        "survey": "scan", "fold": "try", "units": "m", "count": count,
        "voxel_size": .25, "batch_size": 1300,
    }))
    return config, source


def test_racine_plan_builds_shared_caps_and_preview_is_a_separate_menu_action(tmp_path, monkeypatch, capsys):
    config, raw = setup_plan(
        tmp_path, straight_cloud(12), [[0, 0, 0], [6, 0, 0], [12, 0, 0]],
        source_format="racine",
    )
    output = tmp_path / "recortes"
    monkeypatch.chdir(tmp_path)
    split = tmp_path / "docs/auditoria/gan/splits.json"
    split.parent.mkdir(parents=True)
    split.write_text(json.dumps({"folds": [{"id": "try", "groups": {"pilot": "train"}}]}))
    answers = iter(["2", "5", str(config), "", str(output), "0", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    main()
    assert "Propostos 2 de 2" in capsys.readouterr().out

    manifest = json.loads((output / "plan.json").read_text())
    folders = [output / crop["crop_id"] for crop in manifest["crops"]]
    first, second = [prepare_crop(folder / "crop.json") for folder in folders]
    assert first.config["sections"][1]["point_xyz"] == second.config["sections"][0]["point_xyz"]
    assert first.config["proposal"]["section_bins_supported"] == [16, 16]
    assert first.config["shape_zyx"] == [64, 64, 64]
    assert first.config["proposal"]["status"] == "pending_review"
    assert manifest["centreline_extraction"] is None
    assert read_ply_header(first.source).vertex_count == manifest["crops"][0]["retained_points"]
    assert not list(output.rglob("*.html"))
    assert not first.destination.exists()

    raw.unlink()
    html = output / "recortes.html"
    answers = iter(["2", "6", "1", str(first.source), "", "0", "0"])
    main()
    assert "Prévia: recortes/recortes.html" in capsys.readouterr().out
    traces = preview_traces(html)
    assert [trace["name"] for trace in traces if trace["mode"] == "markers"] == [
        folder.name for folder in folders
    ]
    caps = [trace for trace in traces if trace["name"].startswith("Tampa ")]
    assert len(caps) == 4
    assert all(cap["visible"] == "legendonly" for cap in caps)
    axes = [trace for trace in traces if trace["name"].startswith("Linha central")]
    assert [trace["name"] for trace in axes] == [f"Linha central · {folder.name}" for folder in folders]
    assert all(axis["visible"] == "legendonly" for axis in axes)
    for label in ("Mostrar tampas", "Mostrar linha central", "Ocultar linha central"):
        assert label in html.read_text(encoding="utf-8")

    answers = iter(["2", "6", "2", str(first.source), "0", "0"])
    main()
    assert capsys.readouterr().out.count("Prévia:") == 1
    assert not (folders[1] / "recorte.html").exists()
    (folders[0] / "recorte.html").unlink()
    answers = iter(["2", "6", "2", str(output / "plan.json"), "0", "0"])
    main()
    assert capsys.readouterr().out.count("Prévia:") == 2
    for folder in folders:
        traces = preview_traces(folder / "recorte.html")
        assert [trace["name"] for trace in traces] == [
            folder.name, f"Linha central · {folder.name}", f"Tampa inicial · {folder.name}", f"Tampa final · {folder.name}"
        ]
    assert process_crop(first)["air_voxels"] > 0


def test_menu_estimates_missing_centreline_and_namespaces_both_outputs(tmp_path, monkeypatch, capsys):
    pytest.importorskip("robust_laplacian")
    monkeypatch.chdir(tmp_path)
    points = straight_cloud(24)
    source = tmp_path / "tunnel.f32"
    np.pad(points, ((0, 0), (0, 4))).astype(np.float32).tofile(source)
    split = tmp_path / "docs/auditoria/gan/splits.json"
    split.parent.mkdir(parents=True)
    split.write_text(json.dumps({"folds": [{"id": "test-fold", "groups": {"indian_tunnel": "train"}}]}))
    config = tmp_path / "pilot-f32.json"
    config.write_text(json.dumps({
        "source": str(source), "cave": "indian_tunnel", "survey": "full_1x",
        "fold": "test-fold", "units": "m", "count": 2, "voxel_size": .25, "batch_size": 1300,
    }))

    answers = iter(["2", "5", str(config), "", "", "0", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    main()
    assert "Propostos 2 de 2" in capsys.readouterr().out
    namespace = tmp_path / "data/processed/crop_plans/indian_tunnel/full_1x/test-fold/pilot-f32"
    manifest = json.loads((namespace / "plan.json").read_text())
    nodes, edges = read_graph(namespace / manifest["centreline"])
    assert len(edges) == len(nodes) - 1
    assert np.ptp(nodes[:, 0]) > 15
    assert np.linalg.norm(nodes[:, 1:], axis=1).max() < .6
    assert manifest["centreline_extraction"]["points_read"] == len(points)
    assert manifest["centreline_extraction"]["status"] == "pending_review"
    for record in manifest["crops"]:
        crop = prepare_crop(namespace / record["crop_id"] / "crop.json")
        assert crop.destination == (
            Path("data/processed/reference_sections/indian_tunnel/full_1x/test-fold/pilot-f32")
            / record["crop_id"] / "64x64x64"
        )
        assert record["retained_points"] > 0
        assert "linha_central_estimada" in record["review_reasons"]


def test_u_shape_uses_station_to_keep_the_opposite_arm_out(tmp_path):
    gap = 2.1
    config, _ = setup_plan(
        tmp_path, np.concatenate((straight_cloud(12), straight_cloud(12, y=gap))),
        [[0, 0, 0], [12, 0, 0], [12, gap, 0], [0, gap, 0]], count=3,
    )
    output = tmp_path / "recortes"
    result = propose_crops(config, output)
    first = result["crops"][0]
    xyz = np.concatenate(list(iter_ply_xyz(output / first["crop_id"] / "cloud.ply", 1000)))
    assert result["proposed"] == 3
    assert xyz[:, 1].max() <= .801
    assert "outra_passagem_ou_retorno_proximo" in first["review_reasons"]
    with pytest.raises(FileExistsError):
        propose_crops(config, output)


def test_incomplete_section_has_no_invented_cap(tmp_path):
    points = straight_cloud(12)
    config, _ = setup_plan(tmp_path, points[points[:, 2] >= 0], [[0, 0, 0], [12, 0, 0]], count=1)
    output = tmp_path / "recortes"
    record = propose_crops(config, output)["crops"][0]
    crop = json.loads((output / record["crop_id"] / "crop.json").read_text())
    assert record["retained_points"] > 0
    assert "tampa_com_cobertura_insuficiente" in record["review_reasons"]
    assert all(section["polygon_uv"] == [] for section in crop["sections"])


def test_reviewed_cuts_reject_a_detached_cluster_and_share_displaced_station(tmp_path):
    station, angle = np.meshgrid(np.linspace(0, .7, 60), np.linspace(1.22, 1.43, 45))
    detached = np.column_stack((station.ravel(), 3 * np.cos(angle.ravel()), 3 * np.sin(angle.ravel())))
    config, _ = setup_plan(
        tmp_path, np.concatenate((straight_cloud(12), detached)), [[0, 0, 0], [12, 0, 0]],
    )
    baseline_folder = tmp_path / "baseline"
    baseline = propose_crops(config, baseline_folder)
    old = json.loads((baseline_folder / baseline["crops"][0]["crop_id"] / "crop.json").read_text())
    assert np.linalg.norm(old["sections"][0]["polygon_uv"], axis=1).max() > 2.5

    spec = json.loads(config.read_text())
    spec["section_overrides"] = [
        {"passage": 1, "cut": 0, "station": .25, "contour": "connected"},
        {"passage": 1, "cut": 1, "station": 6.5},
    ]
    config.write_text(json.dumps(spec))
    reviewed = tmp_path / "reviewed"
    plan = propose_crops(config, reviewed)
    first, second = [
        json.loads((reviewed / record["crop_id"] / "crop.json").read_text())
        for record in plan["crops"]
    ]
    assert np.linalg.norm(first["sections"][0]["polygon_uv"], axis=1).max() < 1.1
    assert first["proposal"]["section_bins_supported"][0] == 16
    assert first["proposal"]["cut_stations"][-1] == second["proposal"]["cut_stations"][0] == 6.5
    assert first["sections"][-1]["point_xyz"] == second["sections"][0]["point_xyz"]
    assert first["sections"][-1]["polygon_uv"] == (
        np.asarray(second["sections"][0]["polygon_uv"])[::-1] * [1, -1]
    ).tolist()


def test_automatic_section_review_compares_the_source_and_updates_both_neighbours(tmp_path):
    points = straight_cloud(12)
    wall = points[(abs(points[:, 0] - 6) > 1.05) | (points[:, 2] <= 0)]
    close_to_axis = points[abs(points[:, 0] - 6) < 0.4] * [1, .1, .1]
    station, angle = np.meshgrid(np.linspace(0, .7, 60), np.linspace(1.22, 1.43, 45))
    detached = np.column_stack((station.ravel(), 3 * np.cos(angle.ravel()), 3 * np.sin(angle.ravel())))
    config, _ = setup_plan(
        tmp_path, np.vstack((wall, close_to_axis, detached)), [[0, 0, 0], [12, 0, 0]],
    )
    baseline = propose_crops(config, tmp_path / "base")
    assert "tampa_com_cobertura_insuficiente" in baseline["crops"][0]["review_reasons"]
    spec = json.loads(config.read_text())
    spec.update(section_search_radius_voxels=8)
    config.write_text(json.dumps(spec))
    output = tmp_path / "auto"
    manifest = propose_crops(config, output)
    first, second = [json.loads((output / c["crop_id"] / "crop.json").read_text())
                     for c in manifest["crops"]]
    begin, shared, end = manifest["section_reviews"]
    assert begin["outcome"] == end["outcome"] == "refit"
    assert np.linalg.norm(first["sections"][0]["polygon_uv"], axis=1).max() < 1.1
    assert shared["outcome"] == "moved"
    original, *other_trials = shared["trials"]
    assert not original["connected_complete"]
    assert sum(original["raw_bins"]) > sum(original["raw_bins_above_min_radius"])
    assert sum(original["filtered_bins"]) > sum(original["filtered_bins_above_min_radius"])
    winner = next(t for t in other_trials if t["station"] == shared["selected_station"])
    assert winner["spacing_ok"] and winner["connected_complete"]
    assert winner["section"] == second["sections"][0]
    assert "section" not in original
    html = write_crop_preview(output / "plan.json", tmp_path / "candidatas.html")
    traces = {trace["name"]: trace for trace in preview_traces(html)}
    assert traces["Contornos candidatos"]["visible"] == "legendonly"
    assert traces["Estações testadas"]["visible"] == "legendonly"
    assert "Mostrar candidatas" in html.read_text(encoding="utf-8")
    assert first["proposal"]["cut_stations"][-1] == second["proposal"]["cut_stations"][0]
    assert first["sections"][-1]["point_xyz"] == second["sections"][0]["point_xyz"]
    np.testing.assert_allclose(first["sections"][-1]["inward_normal_xyz"],
                               -np.array(second["sections"][0]["inward_normal_xyz"]))
    assert read_ply_header(output / first["crop_id"] / "cloud.ply").vertex_count > 0


def test_reviewed_connected_cut_keeps_two_complete_contours_pending(tmp_path):
    inner = straight_cloud(12)
    outer = inner * [1, 3.5, 3.5]
    config, _ = setup_plan(
        tmp_path, np.concatenate((inner, outer)), [[0, 0, 0], [12, 0, 0]], count=1,
    )
    spec = json.loads(config.read_text())
    spec["section_overrides"] = [{"passage": 1, "cut": 0, "station": .25, "contour": "connected"}]
    config.write_text(json.dumps(spec))
    output = tmp_path / "ambiguous"
    record, = propose_crops(config, output)["crops"]
    crop = json.loads((output / record["crop_id"] / "crop.json").read_text())

    assert crop["sections"][0]["polygon_uv"] == []
    assert record["section_bins_supported"][0] == 16
    assert "tampa_com_contornos_concorrentes" in record["review_reasons"]


def test_section_override_cannot_cross_the_next_cut(tmp_path):
    config, _ = setup_plan(tmp_path, straight_cloud(12), [[0, 0, 0], [12, 0, 0]])
    spec = json.loads(config.read_text())
    spec["section_overrides"] = [{"passage": 1, "cut": 0, "station": 7}]
    config.write_text(json.dumps(spec))
    output = tmp_path / "crossed"

    with pytest.raises(ValueError, match="em ordem"):
        propose_crops(config, output)
    assert not output.exists()


def test_plan_targets_shorter_passages_without_renumbering_graph(tmp_path):
    main_gallery = straight_cloud(14)
    side_gallery = straight_cloud(4)[:, [1, 0, 2]] + [6, 0, 0]
    nodes = [[0, 0, 0], [6, 0, 0], [14, 0, 0], [6, 4, 0], [6, 0, 1]]
    config, _ = setup_plan(tmp_path, np.concatenate((main_gallery, side_gallery)), nodes, count=3)
    np.savez(tmp_path / "graph.npz", nodes_xyz=nodes, edges=[[0, 1], [1, 2], [1, 3], [1, 4]])
    spec = json.loads(config.read_text())
    config.write_text(json.dumps(dict(spec, passages=[2, 3])))
    plan = propose_crops(config, tmp_path / "selecionados")
    assert [row["crop_id"] for row in plan["crops"]] == [
        "ramo_002_001", "ramo_002_002", "ramo_003_001",
    ]
    assert all(row["retained_points"] > 0 for row in plan["crops"])

    config.write_text(json.dumps(dict(spec, passages=[3, 4])))
    with pytest.raises(ValueError, match="menos de oito voxels úteis: 4"):
        propose_crops(config, tmp_path / "curto")
