"""Reevaluate an existing cave archive without regenerating its geometry."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from cavegen.benchmark.records import (
    append_experiment_record,
    create_experiment_context,
    make_experiment_record,
)
from cavegen.datastream.voxel_io import load_volume_npz
from cavegen.metrics.structural import MetricValue
from cavegen.metrics.validation import Connectivity, SpacingZYX


def evaluate_archive(
    volume_path: str | Path,
    out_csv: str | Path,
    *,
    connectivity: Connectivity = 6,
    spacing_zyx: SpacingZYX = (1.0, 1.0, 1.0),
) -> dict[str, MetricValue]:
    """Append structural measurements of one Volume3D NPZ to the central CSV.

    Parameters
    ----------
    volume_path
        Generated open-space archive using the data/metadata volume format.
        Observed-surface NPZ files are rejected; no point clouds are read.
    out_csv
        Same sequential CSV destination used by the generation runner.
    connectivity, spacing_zyx
        Explicit ZYX measurement settings, validated by evaluate_structure.

    Returns
    -------
    dict
        Saved record tagged structural_evaluation with generation time/RSS
        absent. Source bytes are preserved and no new volume is generated.

    Raises
    ------
    ValueError
        If the source is not a supported cave-volume archive.
    """
    source = Path(volume_path)
    try:
        volume = load_volume_npz(source)
    except OSError as error:
        raise OSError(f"{source}: {error.strerror or error}") from error
    except (KeyError, TypeError, ValueError, BadZipFile) as error:
        raise ValueError(f"{source}: expected a Volume3D NPZ with data, not surface_voxels.") from error
    if not isinstance(volume.metadata, dict):
        raise ValueError(f"{source}: volume metadata must be a JSON object.")
    row = make_experiment_record(
        volume,
        context=create_experiment_context("structural_reevaluation", "existing_volume"),
        algorithm=str(volume.metadata.get("algorithm", "unknown")),
        seed=volume.metadata.get("seed"),
        volume_path=source,
        parameters=volume.metadata,
        variant="structural_evaluation",
        connectivity=connectivity,
        spacing_zyx=spacing_zyx,
    )
    append_experiment_record(out_csv, row)
    return row
