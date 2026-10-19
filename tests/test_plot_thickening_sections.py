"""Public output of the static thickening comparison plot."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import matplotlib
matplotlib.use("Agg")
import numpy as np
import trimesh

from plots.plot_thickening_sections import plot_sections


class ThickeningPlotTests(unittest.TestCase):
    def test_draws_measured_points_and_mesh_section(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sample.npz"
            np.savez_compressed(sample, points_xyz=np.array([
                [0.4, -0.2, 0.0], [0.5, 0.2, 0.1], [0.6, 0.0, -0.1]
            ]))
            mesh_path = root / "cube.obj"
            trimesh.creation.box(extents=(1, 1, 1)).export(mesh_path)
            output = root / "sections.png"
            result = plot_sections(sample, [("cubo", mesh_path)], output,
                                   x_positions=(0,), slice_thickness=1)
            self.assertEqual(result, output)
            self.assertGreater(output.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
