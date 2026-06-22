from __future__ import annotations

import numpy as np

from cavegen.core.volume import Volume3D


def volume_to_raw_bytes(volume: Volume3D) -> tuple[tuple[int, int, int], bytes]:
    """Serialize a volume for the future gRPC layer."""
    packed = np.packbits(volume.data.reshape(-1).astype(np.uint8))
    return volume.shape, packed.tobytes()


def raw_bytes_to_volume(shape: tuple[int, int, int], payload: bytes) -> Volume3D:
    total = int(np.prod(shape))
    unpacked = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))[:total]
    return Volume3D(unpacked.reshape(shape).astype(bool), metadata={"source": "grpc_payload"})
