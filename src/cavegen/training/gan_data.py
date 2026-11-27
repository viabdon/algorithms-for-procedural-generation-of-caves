"""Explicit occupancy/TSDF representations and integrity-checked partition loading."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
import torch
from torch.utils.data import Dataset

from cavegen.training.gan_models import ModelConfig
from cavegen.core.volume import Volume3D
from cavegen.metrics import evaluate_structure
from cavegen.training.reference_data import (
    CANDIDATE_SEMANTIC, VALID_SEMANTIC, gallery_training_air, read_reference, verify_splits,
)


def encode_volume(data: np.ndarray, config: ModelConfig) -> np.ndarray:
    """TSDF has no zero-valued air centers: sign recovers every input voxel.

    Outside the grid is solid. Distances are center-to-center in voxel units;
    this is a discrete signed distance surrogate, not a continuous surface SDF.
    """
    if data.dtype != np.bool_ or data.shape != (config.resolution,) * 3:
        raise ValueError("Expected boolean air at configured model resolution")
    if config.representation == "occupancy":
        return data.astype(np.float32)
    if not data.any():
        return np.full(data.shape, -1, dtype=np.float32)
    padded = np.pad(data, 1, constant_values=False)
    inside = distance_transform_edt(padded)[1:-1, 1:-1, 1:-1]
    outside = distance_transform_edt(~data)
    return (np.clip(inside - outside, -config.sdf_tau, config.sdf_tau)
            / config.sdf_tau).astype(np.float32)


def decode_volume(field: np.ndarray, config: ModelConfig, threshold: float = 0.5) -> np.ndarray:
    if field.shape != (config.resolution,) * 3 or not np.isfinite(field).all():
        raise ValueError("Invalid generated field")
    if not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("Occupancy threshold must be finite and inside (0,1)")
    return field >= threshold if config.representation == "occupancy" else field > 0


class ReferenceDataset(Dataset):
    """Only the requested cave partition is materialized; no on-load augmentation."""

    def __init__(self, root: str | Path, splits: dict, fold: str, split: str,
                 config: ModelConfig, *, allow_candidate_proxy: bool = False) -> None:
        if split not in ("train", "validation", "test"):
            raise ValueError("Unknown partition")
        rows = verify_splits(splits, root, fold)
        self.rows = [row for row in rows if row["split"] == split]
        self.arrays, self.tensors = [], []
        for row in self.rows:
            data, metadata, key = read_reference(Path(root) / row["path"])
            semantic = CANDIDATE_SEMANTIC if "gallery_evidence" in row else metadata.get("semantic")
            if key != "data" or semantic not in (CANDIDATE_SEMANTIC, VALID_SEMANTIC):
                raise ValueError("Observed surfaces cannot be GAN air references")
            if semantic == CANDIDATE_SEMANTIC and not allow_candidate_proxy:
                raise ValueError("Candidate flood-fill air: explicitly enable the proxy experiment")
            data = gallery_training_air(data, row)
            metrics = evaluate_structure(Volume3D(data))
            if metrics.largest_component_voxels < 64 or (metrics.distance_max or 0) < 2:
                raise ValueError(f"Insufficient resolved cave interior: {row['path']}; "
                                 "need largest component >=64 voxels and EDT max >=2 voxels")
            self.arrays.append(data)
            self.tensors.append(torch.from_numpy(encode_volume(data, config)[None]))
        if not self.tensors:
            raise ValueError("Empty requested partition")

    def __len__(self) -> int:
        return len(self.tensors)

    def __getitem__(self, index: int) -> torch.Tensor:
        return self.tensors[index].clone()
