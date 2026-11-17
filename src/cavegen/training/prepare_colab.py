"""Bundle code and small voxel artifacts for a private Colab upload, without training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

from cavegen.training.reference_data import sha256_file, verify_splits


def build_bundle(repository: str | Path, output: str | Path) -> Path:
    repository, output = Path(repository).resolve(), Path(output).resolve()
    splits = json.loads((repository / "docs/auditoria/gan/splits.json").read_text(encoding="utf-8"))
    for fold in splits["folds"]:
        verify_splits(splits, repository / "data/processed/references", fold["id"])
    selected = {repository / name for name in ("pyproject.toml", "README.md")}
    for directory in ("src", "configs/gan", "docs/auditoria/gan", "notebooks/colab",
                      "data/processed/references"):
        selected.update(p for p in (repository / directory).rglob("*") if p.is_file()
                        and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".zip"))
    selected.update(repository / path for path in ("docs/plano-redes-neurais.md",
                                                   "docs/plano-reconstrucao-secoes.md",
                                                   "docs/planejamento-recortes-voxelizacao.md",
                                                   "docs/resumo-gargalo-gan.md",
                                                   "docs/preparacao-volumes.md",
                                                   "data/processed/README.md",
                                                   "docs/auditoria/origem_nuvens.csv"))
    if output in selected:
        raise ValueError("Bundle must not include itself")
    if output.exists():
        raise FileExistsError(output)
    manifest = {p.relative_to(repository).as_posix(): sha256_file(p) for p in sorted(selected)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(selected):
            archive.write(path, path.relative_to(repository).as_posix())
        archive.writestr("bundle_manifest.json", json.dumps(manifest, indent=2) + "\n")
    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=".")
    parser.add_argument("--output", default="data/processed/gan_colab_bundle.zip")
    args = parser.parse_args(argv)
    print(build_bundle(args.repository, args.output))


if __name__ == "__main__":
    main()
