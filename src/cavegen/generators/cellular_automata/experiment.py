"""Run one CA configuration and print the numbers the experiment doc asks for.

Example (single line; PowerShell has no backslash continuation)::

    uv run python -m cavegen.generators.cellular_automata.experiment --seed-id 2 --border adaptive --ratio 0.5 --iterations 5 --save
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cavegen.generators.cellular_automata.borders import BorderMode
from cavegen.generators.cellular_automata.generator import (
    CellularAutomataParameters,
    generate_cellular_automata,
)
from cavegen.generators.cellular_automata.seeds import PROJECT_ROOT, load_seed
from cavegen.io.voxel_io import save_volume_npz
from cavegen.metrics.connectivity import connected_components, largest_component_ratio


def _report(label: str, volume) -> None:
    data = volume.data
    _, components = connected_components(data, connectivity=6)
    print(
        f"| {label:8s} | open_ratio={volume.fill_ratio:.4f} "
        f"| largest_component_ratio={largest_component_ratio(data):.4f} "
        f"| componentes={components} |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one cellular automata experiment.")
    parser.add_argument("--seed-id", type=int, default=1, help="1=40%%, 2=50%%, 3=60%% de uns.")
    parser.add_argument(
        "--border",
        default=BorderMode.OUTSIDE_SOLID.value,
        choices=[mode.value for mode in BorderMode],
    )
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--threshold", type=int, default=13, help="Limiar absoluto (modos outside_*).")
    parser.add_argument("--ratio", type=float, default=0.5, help="Fracao de vizinhos (modo adaptive).")
    parser.add_argument("--save", action="store_true", help="Grava o volume final em results/volumes.")
    args = parser.parse_args()

    params = CellularAutomataParameters(
        seed_id=args.seed_id,
        iterations=args.iterations,
        border_mode=BorderMode(args.border),
        threshold_open_neighbors=args.threshold,
        threshold_open_ratio=args.ratio,
    )

    initial = load_seed(params.seed_id)
    final = generate_cellular_automata(params, initial=initial)

    print(f"\nseed_{params.seed_id:03d}  shape={initial.shape}  seed={initial.metadata.get('seed')}")
    print(f"border={params.border_mode.value}  iterations={params.iterations}  "
          f"T={params.threshold_open_neighbors}  pct={params.threshold_open_ratio}")
    _report("Inicial", initial)
    _report("Final", final)
    history = " -> ".join(f"{value:.3f}" for value in final.metadata["open_ratio_history"])
    print(f"open_ratio por iteracao: {history}")

    if args.save:
        name = (f"ca_seed{params.seed_id:03d}_{params.border_mode.value}"
                f"_it{params.iterations}_t{params.threshold_open_neighbors}.npz")
        path = Path(PROJECT_ROOT) / "results" / "volumes" / name
        save_volume_npz(final, path)
        print(f"salvo em: {path}")


if __name__ == "__main__":
    main()
