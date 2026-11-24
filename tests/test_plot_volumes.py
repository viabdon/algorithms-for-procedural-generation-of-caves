"""Visualização dos arquivos de volume usados pelo benchmark."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.datastream.voxel_io import save_volume_npz
from cavegen.tools.plot_volumes import figura_do_volume, main


class PlotVolumesTests(unittest.TestCase):
    def test_voxel_zyx_is_displayed_in_xyz_coordinates(self):
        data = np.zeros((3, 4, 5), dtype=bool)
        data[1, 2, 3] = True
        cloud = figura_do_volume(Volume3D(data), "volume").data[0]
        self.assertEqual(list(zip(cloud.x, cloud.y, cloud.z)), [(3, 2, 1)])

    def test_cli_writes_html_for_a_solid_volume(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "solid.npz"
            save_volume_npz(Volume3D(np.zeros((2, 3, 4), dtype=bool)), path)
            main([str(path)])
            self.assertIn("Plotly.newPlot", path.with_suffix(".html").read_text())
