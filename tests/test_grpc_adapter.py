"""Test lossless raw-byte serialization of boolean voxel volumes."""

from __future__ import annotations

import unittest

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.datastream.grpc_adapter import raw_bytes_to_volume, volume_to_raw_bytes


class GrpcAdapterTests(unittest.TestCase):
    """Verify byte serialization preserves a volume's shape and values."""

    def test_round_trips_a_non_byte_aligned_volume(self) -> None:
        """Preserve all voxels when bit packing leaves unused trailing bits."""
        source = Volume3D(
            np.array(
                [[[True, False, True], [False, True, False]], [[False, True, True], [True, False, False]]]
            )
        )

        shape, payload = volume_to_raw_bytes(source)
        restored = raw_bytes_to_volume(shape, payload)

        self.assertEqual(shape, source.shape)
        np.testing.assert_array_equal(restored.data, source.data)
        self.assertEqual(restored.metadata, {"source": "grpc_payload"})


if __name__ == "__main__":
    unittest.main()
