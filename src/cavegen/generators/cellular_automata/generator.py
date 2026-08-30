"""3D cave generation with a Moore-neighborhood cellular automaton."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.generators.cellular_automata.borders import (
    MAX_NEIGHBORS,
    BorderMode,
    count_open_neighbors,
    neighbor_threshold,
)
from cavegen.generators.cellular_automata.seeds import load_seed


@dataclass(frozen=True)
class CellularAutomataParameters:
    """Everything that defines one run, except the starting grid.

    The starting grid comes from a numbered seed file (see ``seeds.py``), so
    ``seed_id`` also fixes the shape and the initial open ratio.
    """

    seed_id: int = 1
    iterations: int = 5
    border_mode: BorderMode = BorderMode.OUTSIDE_SOLID
    threshold_open_neighbors: int = 13
    threshold_open_ratio: float = 0.5
    seeds_dir: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "border_mode", BorderMode(self.border_mode))

        if self.iterations < 0:
            raise ValueError("iterations must be non-negative.")
        if not 0 <= self.threshold_open_neighbors <= MAX_NEIGHBORS:
            raise ValueError(f"threshold_open_neighbors must be between 0 and {MAX_NEIGHBORS}.")
        if not 0.0 <= self.threshold_open_ratio <= 1.0:
            raise ValueError("threshold_open_ratio must be between 0 and 1.")

    def describe(self) -> dict:
        data = asdict(self)
        data["border_mode"] = self.border_mode.value
        data["seeds_dir"] = str(self.seeds_dir) if self.seeds_dir else None
        return data


def generate_cellular_automata(
    params: CellularAutomataParameters | None = None,
    initial: Volume3D | None = None,
) -> Volume3D:
    """Run the automaton and return the final volume.

    Rule: a voxel is open at step ``t+1`` when at least ``threshold`` of its 26
    neighbors are open at step ``t``. The threshold is a constant for the
    ``OUTSIDE_*`` border modes and a per-voxel array for ``ADAPTIVE``. The
    voxel's own state is not part of the rule.
    """
    params = params or CellularAutomataParameters()
    initial = initial if initial is not None else load_seed(params.seed_id, params.seeds_dir)

    volume = np.array(initial.data, dtype=bool)
    threshold = neighbor_threshold(
        volume.shape,
        params.border_mode,
        params.threshold_open_neighbors,
        params.threshold_open_ratio,
    )

    open_ratio_history = [float(volume.mean())]
    for _ in range(params.iterations):
        volume = count_open_neighbors(volume, params.border_mode) >= threshold
        open_ratio_history.append(float(volume.mean()))

    return Volume3D(
        volume,
        metadata={
            "algorithm": "cellular_automata",
            **params.describe(),
            "seed": initial.metadata.get("seed"),
            "initial_open_ratio": open_ratio_history[0],
            "final_open_ratio": open_ratio_history[-1],
            "open_ratio_history": open_ratio_history,
        },
    )


@dataclass
class CellularAutomataGenerator:
    """Reusable generator, so benchmarks can hold a configured instance."""

    params: CellularAutomataParameters = field(default_factory=CellularAutomataParameters)

    def generate(self, initial: Volume3D | None = None) -> Volume3D:
        return generate_cellular_automata(self.params, initial=initial)
