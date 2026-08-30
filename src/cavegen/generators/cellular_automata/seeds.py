"""Sequential seed volumes used as the starting point of every CA experiment.

The research uses a fixed shape, so a seed is stored as the initial boolean
grid itself (``data/seeds/seed_001.npz`` ...). What separates one seed from the
next is the initial fraction of open voxels: 40%, 50% and 60%.

Each file is a ``Volume3D`` npz, so the parameters that produced it travel
inside the file's metadata.

Regenerate them with::

    uv run python -m cavegen.generators.cellular_automata.seeds
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from cavegen.core.seed import numpy_rng
from cavegen.core.volume import Volume3D
from cavegen.io.voxel_io import load_volume_npz, save_volume_npz

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SEEDS_DIR = PROJECT_ROOT / "data" / "seeds"

DEFAULT_SHAPE: tuple[int, int, int] = (64, 64, 64)
DEFAULT_OPEN_RATIOS: tuple[float, ...] = (0.40, 0.50, 0.60)
MASTER_SEED = 20260827


def seed_path(seed_id: int, directory: str | Path | None = None) -> Path:
    return Path(directory or SEEDS_DIR) / f"seed_{seed_id:03d}.npz"


def derive_seeds(count: int, master_seed: int = MASTER_SEED) -> list[int]:
    """Independent, reproducible integer seeds derived from one master seed."""
    children = np.random.SeedSequence(master_seed).spawn(count)
    return [int(child.generate_state(1, dtype=np.uint32)[0]) for child in children]


def build_seed_volume(
    open_ratio: float,
    seed: int,
    seed_id: int,
    shape: tuple[int, int, int] = DEFAULT_SHAPE,
) -> Volume3D:
    if not 0.0 <= open_ratio <= 1.0:
        raise ValueError("open_ratio must be between 0 and 1.")
    data = numpy_rng(seed).random(shape) < open_ratio
    return Volume3D(
        data,
        metadata={
            "kind": "ca_seed",
            "seed_id": seed_id,
            "seed": seed,
            "shape": list(shape),
            "target_open_ratio": open_ratio,
            "actual_open_ratio": float(data.mean()),
        },
    )


def generate_seed_files(
    shape: tuple[int, int, int] = DEFAULT_SHAPE,
    open_ratios: tuple[float, ...] = DEFAULT_OPEN_RATIOS,
    directory: str | Path | None = None,
    master_seed: int = MASTER_SEED,
    overwrite: bool = False,
) -> list[Path]:
    """Write one npz per open ratio, numbered sequentially from 1."""
    directory = Path(directory or SEEDS_DIR)
    seeds = derive_seeds(len(open_ratios), master_seed)

    written: list[Path] = []
    for index, (open_ratio, seed) in enumerate(zip(open_ratios, seeds), start=1):
        path = seed_path(index, directory)
        if path.exists() and not overwrite:
            raise FileExistsError(f"{path} already exists. Pass overwrite=True to replace it.")
        save_volume_npz(build_seed_volume(open_ratio, seed, index, shape), path)
        written.append(path)
    return written


def load_seed(seed_id: int, directory: str | Path | None = None) -> Volume3D:
    path = seed_path(seed_id, directory)
    if not path.exists():
        raise FileNotFoundError(
            f"Seed {seed_id} not found at {path}. "
            "Run `python -m cavegen.generators.cellular_automata.seeds` to create it."
        )
    return load_volume_npz(path)


def list_seeds(directory: str | Path | None = None) -> list[Path]:
    return sorted(Path(directory or SEEDS_DIR).glob("seed_*.npz"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the base CA seed volumes.")
    parser.add_argument("--out", default=None, help="Output directory (default: data/seeds).")
    parser.add_argument("--master-seed", type=int, default=MASTER_SEED)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    for path in generate_seed_files(
        directory=args.out, master_seed=args.master_seed, overwrite=args.overwrite
    ):
        volume = load_volume_npz(path)
        print(f"{path.name}  shape={volume.shape}  open_ratio={volume.fill_ratio:.4f}")


if __name__ == "__main__":
    main()
