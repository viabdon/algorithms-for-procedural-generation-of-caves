"""Deterministic structural evaluation, independent of generation/profiling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.metrics.connectivity import connected_components
from cavegen.metrics.morphology import distance_transform_stats
from cavegen.metrics.validation import (
    Connectivity,
    SpacingZYX,
    validate_connectivity,
    validate_spacing,
    validate_volume,
)

STRUCTURAL_SCHEMA_VERSION = "structural-v1"
MetricValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class StructuralMetrics:
    """Immutable summary of one generated cave volume.

    Attributes
    ----------
    total_voxels, open_voxels : int
        Counts for the complete grid and its open subset.
    open_ratio : float
        open_voxels / total_voxels.
    component_count, largest_component_voxels : int
        Number of open components and voxel count of the largest one.
    largest_component_ratio : float
        Largest-component voxels / open voxels; zero if no open voxels exist.
    distance_mean, distance_median, distance_max : float or None
        Unsigned center-to-center distances over open voxels, in spacing
        units (voxels at unit spacing). None for both degenerate cases.
    connectivity : {6, 26}
        Open-space adjacency. Does not affect the Euclidean distance metric.
    is_degenerate : bool
        True precisely for all-solid or all-open volumes.
    degenerate_reason : str or None
        no_open_voxels, no_solid_voxels, or None for mixed volumes.
        Disconnected mixed volumes remain measurable; no penalty is applied.
    shape_zyx, spacing_zyx : tuple
        Dimensions and measurement spacings in ZYX order.
    """

    total_voxels: int
    open_voxels: int
    open_ratio: float
    component_count: int
    largest_component_voxels: int
    largest_component_ratio: float
    distance_mean: float | None
    distance_median: float | None
    distance_max: float | None
    connectivity: Connectivity
    is_degenerate: bool
    degenerate_reason: Literal["no_open_voxels", "no_solid_voxels"] | None
    shape_zyx: tuple[int, int, int]
    spacing_zyx: SpacingZYX

    def to_record(self) -> dict[str, MetricValue]:
        """Return one flat, versioned record ready for a CSV experiment row.

        Returns
        -------
        dict
            Stable scalar columns, including ZYX shape/spacing, exterior
            rule and distance unit. Missing distances remain None (empty
            CSV fields or JSON null); no labels or arrays are serialized.
            Execution identity and timing belong to the experiment runner.
        """
        return {
            "structural_schema_version": STRUCTURAL_SCHEMA_VERSION,
            "axis_order": "ZYX",
            "shape_depth": self.shape_zyx[0],
            "shape_height": self.shape_zyx[1],
            "shape_width": self.shape_zyx[2],
            "spacing_z": self.spacing_zyx[0],
            "spacing_y": self.spacing_zyx[1],
            "spacing_x": self.spacing_zyx[2],
            "distance_unit": "voxel" if self.spacing_zyx == (1.0, 1.0, 1.0) else "spacing_unit",
            "exterior_policy": "solid",
            "distance_reference": "voxel_centers",
            "connectivity": self.connectivity,
            "total_voxels": self.total_voxels,
            "open_voxels": self.open_voxels,
            "open_ratio": self.open_ratio,
            "component_count": self.component_count,
            "largest_component_voxels": self.largest_component_voxels,
            "largest_component_ratio": self.largest_component_ratio,
            "dt_mean": self.distance_mean,
            "dt_median": self.distance_median,
            "dt_max": self.distance_max,
            "is_degenerate": self.is_degenerate,
            "degenerate_reason": self.degenerate_reason,
        }


def evaluate_structure(
    volume: Volume3D,
    *,
    connectivity: Connectivity = 6,
    spacing_zyx: SpacingZYX = (1.0, 1.0, 1.0),
) -> StructuralMetrics:
    """Evaluate one cave without modifying, filtering or saving its voxels.

    Parameters
    ----------
    volume
        Volume3D with nonempty boolean ZYX data, True meaning open space.
        Surface-occupancy grids must not be wrapped as cave volumes. Spacing
        and connectivity are explicit, never inferred from its metadata.
    connectivity
        Face adjacency (6, default) or face/edge/corner adjacency (26).
    spacing_zyx
        Three finite positive measurement spacings in ZYX order.

    Returns
    -------
    StructuralMetrics
        Deterministic, immutable scalars. No random state, clock, penalties,
        largest-component cleanup or hidden resampling is involved. Any
        nonempty 3D shape is accepted; production comparison uses 64 cubed.
    """
    if not isinstance(volume, Volume3D):
        raise TypeError("volume must be a Volume3D; raw arrays belong to individual metrics.")
    data = validate_volume(volume.data)
    connectivity = validate_connectivity(connectivity)
    spacing_zyx = validate_spacing(spacing_zyx)
    labeled, component_count = connected_components(data, connectivity)
    sizes = np.bincount(labeled.ravel())
    largest_size = int(sizes[1:].max()) if component_count else 0
    del labeled, sizes
    open_voxels = int(np.count_nonzero(data))
    reason = None
    if open_voxels == 0:
        reason = "no_open_voxels"
    elif open_voxels == data.size:
        reason = "no_solid_voxels"
    distances = distance_transform_stats(data, spacing_zyx=spacing_zyx)
    return StructuralMetrics(
        total_voxels=int(data.size),
        open_voxels=open_voxels,
        open_ratio=float(open_voxels / data.size),
        component_count=component_count,
        largest_component_voxels=largest_size,
        largest_component_ratio=float(largest_size / open_voxels) if open_voxels else 0.0,
        distance_mean=distances["dt_mean"],
        distance_median=distances["dt_median"],
        distance_max=distances["dt_max"],
        connectivity=connectivity,
        is_degenerate=reason is not None,
        degenerate_reason=reason,
        shape_zyx=volume.shape,
        spacing_zyx=spacing_zyx,
    )
