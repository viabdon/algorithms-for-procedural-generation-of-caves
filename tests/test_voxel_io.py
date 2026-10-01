"""Test persistence of boolean voxel volumes and JSON metadata."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.datastream.voxel_io import load_volume_npz, save_volume_npz


class VoxelIOTests(unittest.TestCase):
    """Verify compressed NPZ volume round-trips and metadata fallback."""

    def test_round_trips_boolean_data_and_metadata(self) -> None:
        """Preserve volume values, shape, and JSON-compatible metadata."""
        volume = Volume3D(
            np.array([[[True, False], [False, True]]]),
            metadata={"source": "synthetic", "resolution": [1, 2, 2]},
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "volume.npz"
            save_volume_npz(volume, path)
            restored = load_volume_npz(path)

        np.testing.assert_array_equal(restored.data, volume.data)
        self.assertEqual(restored.data.dtype, np.bool_)
        self.assertEqual(restored.metadata, volume.metadata)

    def test_uses_empty_metadata_for_invalid_json(self) -> None:
        """Return an empty metadata mapping when a legacy archive has invalid JSON."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid_metadata.npz"
            np.savez_compressed(path, data=np.ones((1, 1, 1), dtype=np.uint8), metadata="not json")
            restored = load_volume_npz(path)

        self.assertTrue(restored.data[0, 0, 0])
        self.assertEqual(restored.metadata, {})


if __name__ == "__main__":
    unittest.main()
