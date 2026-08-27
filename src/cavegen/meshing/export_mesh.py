from __future__ import annotations

import argparse
from pathlib import Path

import trimesh

from cavegen.datastream.voxel_io import load_volume_npz
from cavegen.meshing.marching_cubes import volume_to_mesh


def export_obj(input_path: str | Path, output_path: str | Path) -> None:
    volume = load_volume_npz(input_path)
    verts, faces, _, _ = volume_to_mesh(volume.data)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a .npz voxel volume to a mesh file.")
    parser.add_argument("--input", required=True, help="Input .npz volume path.")
    parser.add_argument("--output", required=True, help="Output mesh path, e.g. .obj or .glb.")
    args = parser.parse_args()
    export_obj(args.input, args.output)


if __name__ == "__main__":
    main()
