"""Evaluate a frozen checkpoint on arbitrary inference seeds and a reserved cave."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from cavegen.core.volume import Volume3D
from cavegen.datastream.voxel_io import save_volume_npz
from cavegen.generators.gan_3d import GAN3DGenerator
from cavegen.training.gan_data import ReferenceDataset, decode_volume, encode_volume
from cavegen.training.gan_evaluation import compare_distributions
from cavegen.training.gan_models import latent_for_seed
from cavegen.training.reference_data import canonical_hash


def evaluation_seeds(start: int = 0, count: int = 256, explicit: list[int] | None = None) -> list[int]:
    seeds = list(explicit) if explicit is not None else list(range(start, start + count))
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Evaluation requires nonempty, distinct seeds")
    for seed in seeds:
        latent_for_seed(seed, 1)
    return seeds


def evaluate_checkpoint(checkpoint: str | Path, root: str | Path, splits: dict,
                        seeds: list[int], output: str | Path, *, device: str = "cpu") -> dict:
    seeds = evaluation_seeds(explicit=seeds)
    generator = GAN3DGenerator(checkpoint, device=device)
    if generator.training_step < 1:
        raise ValueError("Cannot report untrained weights as a GAN experiment")
    if generator.provenance["splits_id"] != splits["splits_id"]:
        raise ValueError("Checkpoint and evaluation partitions differ")
    fold = generator.provenance["fold"]
    # The checkpoint records whether candidate air was explicitly permitted.
    import torch
    checkpoint_data = torch.load(checkpoint, map_location="cpu", weights_only=True)
    allow_candidate = checkpoint_data["config"]["allow_candidate_proxy"]
    datasets = {part: ReferenceDataset(root, splits, fold, part, generator.config,
                                       allow_candidate_proxy=allow_candidate)
                for part in ("train", "test")}
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Evaluation output must be a new directory")
    output.mkdir(parents=True, exist_ok=True)
    generated, field_errors, timings = [], [], []
    for seed in seeds:
        start = time.perf_counter()
        field = generator.generate_field(seed)
        timings.append(time.perf_counter() - start)
        air = decode_volume(field, generator.config, generator.threshold)
        generated.append(air)
        metadata = {"algorithm": "gan_" + generator.config.representation,
            "axis_order": "ZYX", "semantic": "true_means_cave_air", "seed": seed,
            "checkpoint_sha256": generator.checkpoint_sha256, "threshold": generator.threshold,
            "model_config": generator.config.to_dict(), "provenance": generator.provenance,
            "backend": device, "postprocessing": "none"}
        save_volume_npz(Volume3D(air, metadata), output / f"seed_{seed}.npz")
        np.savez_compressed(output / f"seed_{seed}.field.npz", field=field,
                            metadata=json.dumps({**metadata, "semantic": "continuous_generated_field"}))
        if generator.config.representation == "sdf":
            recoded = encode_volume(air, generator.config)
            field_errors.append(float(np.abs(recoded - field).mean()))
    result = compare_distributions(generated, datasets["test"].arrays, datasets["train"].arrays)
    # Same sample count as GAN; copying is an explicit control, not a learned method.
    copy_control = [datasets["train"].arrays[i % len(datasets["train"])] for i in range(len(seeds))]
    copy_report = compare_distributions(copy_control, datasets["test"].arrays, datasets["train"].arrays)
    solid_report = compare_distributions([np.zeros_like(generated[0]) for _ in seeds],
                                         datasets["test"].arrays, datasets["train"].arrays)
    val_start = checkpoint_data["config"]["validation_seed_start"]
    val_end = val_start + checkpoint_data["config"]["validation_count"]
    result.update(checkpoint_sha256=generator.checkpoint_sha256, provenance=generator.provenance,
                  seeds=seeds, seeds_id=canonical_hash(seeds), threshold=generator.threshold,
                  validation_seed_overlap=[s for s in seeds if val_start <= s < val_end],
                  inference_seconds_per_seed=timings, backend=device,
                  sdf_reencoding_mae_per_sample=field_errors,
                  copy_control=copy_report, all_solid_control=solid_report)
    (output / "evaluation.json").write_text(json.dumps(result, indent=2, allow_nan=False)
                                            + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--root", default="data/processed/references")
    parser.add_argument("--splits", default="docs/auditoria/gan/splits.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--count", type=int, default=256)
    parser.add_argument("--seeds", nargs="+", type=int)
    args = parser.parse_args(argv)
    seeds = evaluation_seeds(args.seed_start, args.count, args.seeds)
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))
    report = evaluate_checkpoint(args.checkpoint, args.root, splits, seeds, args.output,
                                 device=args.device)
    print(json.dumps({k: report[k] for k in ("generated_count", "degenerate_fraction",
          "duplicate_fraction", "selection_score")}, indent=2))


if __name__ == "__main__":
    main()
