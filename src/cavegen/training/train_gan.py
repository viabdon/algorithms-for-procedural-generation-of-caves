from __future__ import annotations

import argparse
import json
from pathlib import Path

from cavegen.training.gan_training import TrainingConfig, preflight, train


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GAN preflight; training requires --train")
    parser.add_argument("--root", default="data/processed/references")
    parser.add_argument("--splits", default="docs/auditoria/gan/splits.json")
    parser.add_argument("--config", default="configs/gan/occupancy64.json")
    parser.add_argument("--fold", default="holdout_indian_tunnel")
    parser.add_argument("--output", default="models/checkpoints/gan_occupancy64")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    config = TrainingConfig.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))
    if args.train:
        train(args.root, splits, args.fold, config, args.output, resume=args.resume)
    else:
        print(json.dumps(preflight(args.root, splits, args.fold, config), indent=2))
        print("Preflight only; no training. Use --train only after validating reference geometry.")


if __name__ == "__main__":
    main()
