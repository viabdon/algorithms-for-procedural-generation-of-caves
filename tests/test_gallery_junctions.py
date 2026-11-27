"""Exercise measured junctions through the same fallback used by the menu."""

import csv
import json

import numpy as np
import pytest
from scipy.ndimage import binary_dilation

from cavegen.datastream.gallery_reports import replay_checks
from cavegen.datastream.junction_fallback import attempt_failed_crops


@pytest.mark.parametrize("arms,leak", [(3, False), (4, False), (3, True)])
def test_junction_fallback_deduplicates_and_checks_all_incident_caps(tmp_path, arms, leak, monkeypatch):
    monkeypatch.setattr("cavegen.datastream.gallery_junctions.POINT_BATCH", 1000)
    theta = np.arange(arms) * (2 * np.pi / arms)
    directions = np.column_stack((np.cos(theta), np.sin(theta), np.zeros(arms)))
    joint = np.array([30.5, 30.5, 8.5])
    n = 61
    z, y, x = np.indices((17, n, n))
    xyz = np.stack((x, y, z), axis=-1) + .5
    rel = xyz - joint
    air = np.zeros(x.shape, dtype=bool)
    for direction in directions:
        depth = np.clip(rel @ direction, 0, 22)
        air |= (np.linalg.norm(rel - depth[..., None] * direction, axis=-1) < 3.6)
    wall = binary_dilation(air) & ~air
    if leak:
        wall[(z >= 12) & (abs(x - 30) <= 3) & (abs(y - 30) <= 3)] = False
    source = tmp_path / "raw.xyz"
    np.savetxt(source, xyz[wall])
    graph = tmp_path / "graph.npz"
    np.savez(graph, nodes_xyz=np.vstack((joint, joint + 22 * directions)),
             edges=np.column_stack((np.zeros(arms, dtype=int), np.arange(1, arms + 1))))
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "plan.json").write_text(json.dumps({
        "source": str(source), "centreline": str(graph), "source_origin_xyz": [0, 0, 0],
    }))
    configs = []
    for branch in (1, 2):
        config = plan / str(branch) / "crop.json"
        config.parent.mkdir()
        config.write_text(json.dumps({
            "source_origin_xyz": [0, 0, 0], "voxel_size": 1, "branch": f"passagem_{branch:03}",
            "proposal": {"cut_stations": [2, 13]},
        }))
        configs.append(config)
    base = tmp_path / "result"
    result = attempt_failed_crops(((cfg, "missing_contour") for cfg in configs), base)
    name, = result["juncoes"]
    assert all(r["juncoes"] == [name] for r in result["recortes"])
    record = result["juncoes"][name]
    if leak:
        assert record["resultado"] == "sem_fechamento"
        assert any(t.get("planos_completos") == "leaking" for t in record["tentativas"])
        assert not (base / name / "interior.npz").exists()
    else:
        assert record["resultado"] == "volume_salvo"
        assert len(record["tampas"]) == arms
        with replay_checks(base / name).open(encoding="utf-8") as stream:
            checks = {row["check"]: row for row in csv.DictReader(stream)}
        assert checks["candidate_air_component"]["result"] == "match"
        assert all(checks[f"air_reaches_cap_{i}"]["passed"] == "True" for i in range(1, arms + 1))
        assert all(checks[f"branch_{i}_axis_in_air"]["passed"] == "True" for i in range(1, arms + 1))


def test_oblique_cap_matches_voxel_centres_and_finite_intersection():
    from cavegen.datastream.gallery_crop import parse_section
    from cavegen.tools.planar_caps import polygons_intersect, raster_cap_voxels

    shape = (11, 12, 13)
    info = {
        "point_xyz": [6., 5., 5.], "inward_normal_xyz": [1., -1., .5], "u_xyz": [1., 1., 0.],
        "polygon_uv": [[-3, -2], [3, -2], [3, 2], [-3, 2]],
    }
    cap = parse_section(info, np.zeros(3))
    voxel = np.indices(shape).reshape(3, -1).T
    relative = voxel[:, ::-1] + .5 - cap.point
    near = abs(relative @ cap.normal) <= abs(cap.normal).sum() / 2 + 1e-8
    inside = cap.polygon.contains_points(relative @ cap.uv_basis, radius=1e-8)
    np.testing.assert_array_equal(raster_cap_voxels(cap, 1., 1e-8, shape), voxel[near & inside])
    crossing = parse_section({**info, "inward_normal_xyz": [0., 0., 1.]}, np.zeros(3))
    separate = parse_section({**info, "point_xyz": [15., 5., 5.],
                              "inward_normal_xyz": [0., 0., 1.]}, np.zeros(3))
    assert polygons_intersect(cap, crossing, 1e-8)
    assert not polygons_intersect(cap, separate, 1e-8)


def test_unbranched_crop_never_reads_original_source(tmp_path):
    graph = tmp_path / "line.npz"
    np.savez(graph, nodes_xyz=[[0., 0., 0.], [0., 0., 20.]], edges=[[0, 1]])
    path = tmp_path / "crop" / "crop.json"
    path.parent.mkdir()
    path.write_text(json.dumps({
        "source_origin_xyz": [0, 0, 0], "branch": "passagem_001", "voxel_size": 1.,
        "proposal": {"cut_stations": [2., 12.]},
        "leak_diagnostics": {"raw_source": "ausente.xyz", "centreline": str(graph)},
    }))
    result = attempt_failed_crops([(path, "missing_contour"), (path, "sealed")], tmp_path / "out")
    assert [row["resultado"] for row in result["recortes"]] == [
        "sem_juncao_proxima", "falha_fora_da_triagem",
    ]
    assert result["juncoes"] == {}


def test_axis_audit_detects_exit_and_reentry_even_when_endpoint_is_inside():
    from cavegen.datastream.gallery_reports import audit_junction_axes, junction_axis_checks

    air = np.zeros((9, 9, 9), dtype=bool)
    air[3:6, 3:6, 3:6] = True
    wall = binary_dilation(air) & ~air
    caps = np.zeros((3, *air.shape), dtype=bool)
    cells = [[4, 4, x] for x in [4, 3, 2, 1, 2, 3, 4]]
    axes = [{"ramo": 19, "voxels_zyx": cells, "distancias_m": list(range(len(cells)))}]
    evidence = audit_junction_axes(wall, caps, air, axes)
    assert evidence[0]["desvios"] == [
        {"estado": "parede", "de_m": 2, "ate_m": 2},
        {"estado": "exterior", "de_m": 3, "ate_m": 3},
        {"estado": "parede", "de_m": 4, "ate_m": 4},
    ]
    assert junction_axis_checks(evidence)[0]["passed"] is False


@pytest.mark.parametrize("length,expected_mode,expected", [
    (.949, "ramo_curto", [.629, .48]),
    (.60, "sem_estacao", []),
    (1.60, "padrao", [1.28]),
])
def test_short_branch_search_only_opens_when_default_stations_are_missing(length, expected_mode, expected):
    from cavegen.datastream.gallery_junctions import _branch_stations

    mode, stations = _branch_stations(length, .16)
    assert mode == expected_mode
    np.testing.assert_allclose(stations, expected)
    assert (stations <= length - .32 + 1e-12).all()
