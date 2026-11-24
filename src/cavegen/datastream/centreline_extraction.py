"""Adapt point-cloud origins and NPZ output to the shared centreline estimator."""

from collections.abc import Iterable
from pathlib import Path

import numpy as np

from cavegen.datastream.las import read_las_metadata
from cavegen.tools.centreline import ExtractionSettings, estimate_centreline


def source_anchor(source: Path) -> np.ndarray:
    """Use the stored LAS offset so sub-metre geometry stays near the origin."""
    if source.suffix.lower() == ".las":
        return np.asarray(read_las_metadata(source)["offsets_xyz"], dtype=np.float64)
    return np.zeros(3, dtype=np.float64)


def generate_centreline(
    batches: Iterable[np.ndarray], source_offset: np.ndarray, output: Path, settings: ExtractionSettings
) -> dict:
    """Save an estimated graph in original XYZ and return its provenance."""
    nodes, edges, provenance = estimate_centreline(batches, settings, source_offset=source_offset)
    with output.open("xb") as stream:
        np.savez_compressed(stream, nodes_xyz=nodes, edges=edges)
    return provenance
