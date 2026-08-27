from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.datastream.ply import iter_ply_xyz, read_ply_header
from cavegen.datastream.ply_types import PlyHeader


class PlyReaderTests(unittest.TestCase):
    def test_iterates_ascii_vertices_in_batches(self) -> None:
        header = b"""ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nend_header\n"""
        payload = b"1 2 3 10\n4 5 6 20\n7 8 9 30\n"

        with TemporaryDirectory() as directory:
            path = Path(directory) / "points_ascii.ply"
            path.write_bytes(header + payload)
            batches = list(iter_ply_xyz(path, batch_size=2))

        self.assertEqual([batch.shape for batch in batches], [(2, 3), (1, 3)])
        np.testing.assert_array_equal(
            np.vstack(batches),
            np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=np.float32),
        )

    def test_iterates_binary_vertices_with_properties_out_of_xyz_order(self) -> None:
        header = b"""ply\nformat binary_little_endian 1.0\nelement vertex 2\nproperty uchar red\nproperty float z\nproperty float x\nproperty float y\nelement face 0\nproperty list uchar int vertex_indices\nend_header\n"""
        dtype = np.dtype([("red", "u1"), ("z", "<f4"), ("x", "<f4"), ("y", "<f4")])
        vertices = np.array([(10, 3.0, 1.0, 2.0), (20, 6.0, 4.0, 5.0)], dtype=dtype)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "points_binary.ply"
            path.write_bytes(header + vertices.tobytes())
            parsed_header = read_ply_header(path)
            batches = list(iter_ply_xyz(path, batch_size=1))

        self.assertEqual(parsed_header.format, "binary_little_endian")
        self.assertEqual(parsed_header.vertex_count, 2)
        self.assertIsInstance(parsed_header, PlyHeader)
        np.testing.assert_array_equal(
            np.vstack(batches),
            np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32),
        )

    def test_rejects_header_without_xyz_properties(self) -> None:
        content = b"""ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nproperty float y\nend_header\n0 1\n"""

        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing_z.ply"
            path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "missing vertex properties"):
                read_ply_header(path)


if __name__ == "__main__":
    unittest.main()
