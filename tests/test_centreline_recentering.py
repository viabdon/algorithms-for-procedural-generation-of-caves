import numpy as np
from scipy.ndimage import binary_dilation

from cavegen.datastream.centreline import Passage
from cavegen.datastream.centreline_recentering import _crossings, recenter_passage


def _fixture():
    z, y, x = np.indices((21, 35, 56))
    air = ((y - 15)**2 + (z - 10)**2 < 3.6**2) & (x >= 1) & (x <= 54)
    shell = binary_dilation(air) & ~air
    cells = np.argwhere(shell)
    return cells[:, ::-1] + .5, set(map(tuple, cells))


def _passage(vertices):
    xyz = np.asarray(vertices, dtype=float)
    stations = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xyz, axis=0), axis=1))]
    return Passage(xyz, stations, (True, False))


def test_recentering_rejoins_original_anchors_without_crossing_the_wall():
    points, wall = _fixture()
    original = _passage([[4.5, 15.5, 10.5], [13.5, 15.5, 10.5], [20.5, 20.5, 10.5],
                         [29.5, 20.5, 10.5], [36.5, 15.5, 10.5], [46.5, 15.5, 10.5]])
    adjusted, report = recenter_passage(original, 0, points, wall, 1.)
    assert report["resultado"] == "eixo_recentrado"
    assert report["voxels_de_parede_antes"] > 0
    assert not _crossings(adjusted.xyz, wall, 1.)
    np.testing.assert_array_equal(adjusted.xyz[[0, -1]], original.xyz[[0, -1]])
    assert adjusted.junctions == original.junctions


def test_recentering_keeps_original_when_terminal_anchor_is_missing():
    points, wall = _fixture()
    original = _passage([[4.5, 15.5, 10.5], [20.5, 15.5, 10.5], [35.5, 22.5, 10.5]])
    adjusted, report = recenter_passage(original, 0, points, wall, 1.)
    assert adjusted is original
    assert report["resultado"] == "sem_duas_ancoras"
    assert report["ancora_antes"] and not report["ancora_depois"]
