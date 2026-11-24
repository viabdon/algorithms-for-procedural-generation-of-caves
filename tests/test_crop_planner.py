"""Exercise automatic crop planning, point export, and independent preview."""

import json
from pathlib import Path

import numpy as np
import pytest

from cavegen.datastream.centreline import read_graph
from cavegen.datastream.crop_planner import propose_crops
from cavegen.datastream.gallery_crop import prepare_crop, process_crop
from cavegen.datastream.menu import main
from cavegen.datastream.ply import iter_ply_xyz, read_ply_header
from cavegen.tools.centreline import ExtractionSettings, estimate_centreline


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
    html = tmp_path / "preview.html"
    answers = iter(["2", "6", "1", str(first.source), str(html), "0", "0"])
    main()
    assert "Prévia para abrir" in capsys.readouterr().out
    traces = preview_traces(html)
    assert [trace["name"] for trace in traces if trace["mode"] == "markers"] == [
        folder.name for folder in folders
    ]
    caps = [trace for trace in traces if trace["mode"] == "lines"]
    assert len(caps) == 4
    assert all(cap["visible"] == "legendonly" for cap in caps)
    assert "Mostrar tampas" in html.read_text(encoding="utf-8")

    answers = iter(["2", "6", "2", str(output / "plan.json"), "0", "0"])
    main()
    assert capsys.readouterr().out.count("Prévia para abrir") == 2
    for folder in folders:
        traces = preview_traces(folder / "preview_individual_tampas.html")
        assert [trace["name"] for trace in traces] == [
            folder.name, f"Tampa inicial · {folder.name}", f"Tampa final · {folder.name}"
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


def test_shared_centreline_recovers_original_xyz_from_local_batches():
    pytest.importorskip("robust_laplacian")
    points = straight_cloud(24)
    offset = np.array([700_000, 9_000_000, 500])
    batches = (points[start:start + 1300] for start in range(0, len(points), 1300))
    nodes, edges, provenance = estimate_centreline(
        batches, ExtractionSettings(), source_offset=offset,
    )
    local_nodes = nodes - offset
    assert np.ptp(local_nodes[:, 0]) > 15
    assert np.linalg.norm(local_nodes[:, 1:], axis=1).max() < .6
    assert len(edges) == len(nodes) - 1
    assert provenance["points_read"] == len(points)


def test_shared_centreline_rejects_invalid_xyz_batches():
    pytest.importorskip("robust_laplacian")
    with pytest.raises(ValueError, match="lote.*XYZ"):
        estimate_centreline([np.zeros((32, 2))], ExtractionSettings())


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
