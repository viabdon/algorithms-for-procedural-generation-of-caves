"""Distributional comparison and copy/collapse diagnostics for unpaired 3D caves."""

from __future__ import annotations

import numpy as np
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance

from cavegen.core.volume import Volume3D
from cavegen.metrics import evaluate_structure
from cavegen.training.reference_data import voxel_hash

FEATURES = ("open_ratio", "component_count", "largest_component_ratio", "dt_mean", "dt_max")
SCALE_FLOORS = np.array([0.01, 1.0, 0.1, 1.0, 1.0])


def describe_volume(data: np.ndarray) -> dict:
    if data.dtype != np.bool_:
        raise ValueError("Metrics require explicitly decoded boolean air")
    return evaluate_structure(Volume3D(data)).to_record()


def pattern_histogram(data: np.ndarray) -> np.ndarray:
    """All 2x2x2 binary patterns, no wrapping, ZYX bit order, no subsampling."""
    if data.dtype != np.bool_ or data.ndim != 3 or min(data.shape) < 2:
        raise ValueError("Pattern histogram requires a boolean grid with sides >=2")
    windows = np.lib.stride_tricks.sliding_window_view(data, (2, 2, 2))
    codes = np.zeros(windows.shape[:3], dtype=np.uint16)
    for bit, coord in enumerate(np.ndindex(2, 2, 2)):
        codes |= windows[..., coord[0], coord[1], coord[2]].astype(np.uint16) << bit
    return np.bincount(codes.ravel(), minlength=256).astype(np.float64)


def compare_distributions(generated: list[np.ndarray], references: list[np.ndarray],
                          train: list[np.ndarray]) -> dict:
    """Selection score uses validation only; scaling uses training references only.

    Undefined EDT in a degenerate volume is set to zero for the score, with
    degeneration reported separately. The scalar is a project heuristic.
    """
    if not generated or not references or not train:
        raise ValueError("Generated, target and training sets must be nonempty")
    shapes = {v.shape for v in generated + references + train}
    if len(shapes) != 1:
        raise ValueError("Comparison requires a common voxel resolution")
    records = [describe_volume(v) for v in generated]
    target_records = [describe_volume(v) for v in references]
    train_records = [describe_volume(v) for v in train]

    def matrix(rows: list[dict]) -> np.ndarray:
        return np.asarray([[r[k] if r[k] is not None else 0 for k in FEATURES]
                           for r in rows], dtype=float)

    g, r, t = matrix(records), matrix(target_records), matrix(train_records)
    scale = np.maximum(t.std(0), SCALE_FLOORS)
    distances = {key: float(wasserstein_distance(g[:, i], r[:, i]) / scale[i])
                 for i, key in enumerate(FEATURES)}
    # Smooth probabilities equally regardless of the number of generated samples.
    # Natural log; JS divergence in [0, ln 2].
    gh = sum((pattern_histogram(v) for v in generated))
    rh = sum((pattern_histogram(v) for v in references))
    gh, rh = gh / gh.sum() + 1e-6, rh / rh.sum() + 1e-6
    js = float(jensenshannon(gh / gh.sum(), rh / rh.sum(), base=np.e) ** 2)
    hashes = [voxel_hash(v) for v in generated]
    train_hashes = {voxel_hash(v) for v in train}
    degenerate_fraction = sum(x["is_degenerate"] for x in records) / len(records)
    nearest = [min(float(np.mean(v != ref)) for ref in train) for v in generated]
    # Deterministic first 64 samples; all unordered pairs. Diagnostic, not a quality score.
    subset = generated[:64]
    pairwise = [float(np.mean(subset[i] != subset[j])) for i in range(len(subset))
                for j in range(i)]
    return {"schema": "gan-evaluation-v1", "generated_count": len(generated),
            "reference_count": len(references), "training_reference_count": len(train),
            "normalized_wasserstein": distances, "scale_from_training": scale.tolist(),
            "pattern_2cube_js_nats": js, "degenerate_fraction": degenerate_fraction,
            "duplicate_fraction": 1 - len(set(hashes)) / len(hashes),
            "exact_training_copy_fraction": sum(h in train_hashes for h in hashes) / len(hashes),
            "nearest_train_hamming_per_sample": nearest,
            "mean_pairwise_hamming_first64": float(np.mean(pairwise)) if pairwise else None,
            "feature_quantiles_05_50_95": {key: np.quantile(g[:, i], [0.05, 0.5, 0.95]).tolist()
                                           for i, key in enumerate(FEATURES)},
            "selection_score": float(np.mean(list(distances.values())) + js + degenerate_fraction),
            "interpretation": "descriptive; seeds are not independent caves; Hamming is axis-sensitive",
            "per_sample": records}
