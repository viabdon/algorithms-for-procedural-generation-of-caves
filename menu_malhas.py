"""Menu de texto e comandos curtos para revisar normais e malhas diagnósticas.

Execute ``.venv/bin/python menu_malhas.py`` para o menu interativo ou
``.venv/bin/python menu_malhas.py --help`` para comandos diretos.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from cavegen.meshing.normal_orientation import (
    apply_manual_corrections,
    compare_cosine_thresholds,
    load_orientation,
    prepare,
    reason_names,
)
from cavegen.meshing.poisson import run_oriented_sample


ROOT = Path(__file__).resolve().parent
SAMPLE = "data/processed/elaphes_gallery_roi_x12_45.npz"
GRAPH = "data/processed/elaphes_centreline_roi_x12_45_pruned_exploratory.npz"
ORIENTATION = "data/processed/elaphes_centreline_normals_review.npz"
LINE_FIGURE = "results/figures/03_linha_central/elaphes_centreline_roi_x12_45_pruned_interactive.html"
NORMAL_FIGURE = "results/figures/04_orientacao_normais/elaphes_centreline_normals_review.html"
THICK_SAMPLE = "data/processed/elaphes_gallery_roi_x12_35_dense2m_bins.npz"
RAW_OCCUPANCY = "data/processed/elaphes_gallery_roi_x12_35_raw_occupancy_010.npz"
RAW_PLY = "/run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply"


def path(value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else ROOT / candidate


def new_output(destination: Path, *, review: bool = False) -> None:
    companions = [destination]
    if review:
        companions += [destination.with_suffix(".json"), destination.with_suffix(".uncertain.csv"),
                       destination.with_suffix(".references.template.json")]
    else:
        companions.append(destination.with_suffix(destination.suffix + ".json"))
    existing = next((item for item in companions if item.exists()), None)
    if existing is not None:
        raise ValueError(f"saída já existe: {existing}; escolha outro nome")


def suggest_output(name: str, *, review: bool = False) -> str:
    destination = path(name)
    for number in range(1, 1000):
        candidate = (destination if number == 1 else
                     destination.with_name(f"{destination.stem}_{number:02d}{destination.suffix}"))
        try:
            new_output(candidate, review=review)
        except ValueError:
            continue
        return str(candidate.relative_to(ROOT)) if candidate.is_relative_to(ROOT) else str(candidate)
    raise ValueError(f"não há nome livre para {destination}")


def inspect_file(source: Path, index: int | None = None) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"arquivo não encontrado: {source}")
    print(f"Arquivo: {source}\nTamanho: {source.stat().st_size:,} bytes")
    suffix = source.suffix.lower()
    if suffix == ".npz":
        with np.load(source, allow_pickle=False) as archive:
            keys = set(archive.files)
            for key in sorted(keys):
                array = archive[key]
                print(f"  {key}: forma={array.shape}, tipo={array.dtype}")
            if {"uncertain_mask", "review_sha256"} <= keys:
                reviewed = load_orientation(source)
                print(f"Pontos: {len(reviewed['points_xyz'])}; incertos: "
                      f"{len(reviewed['uncertain_indices'])}; decisões manuais: "
                      f"{np.count_nonzero(reviewed['manual_mask'])}")
                if "automatic_sign" in reviewed:
                    signs = reviewed["automatic_sign"]
                    print(f"Limiar |cos|: {float(reviewed['cosine_threshold']):.2f}; "
                          f"keep propostos: {np.count_nonzero(signs == 1)}; "
                          f"flip propostos: {np.count_nonzero(signs == -1)}")
                print(f"Hash da amostra: {reviewed['point_sha256']}")
                if index is not None:
                    if not 0 <= index < len(reviewed["points_xyz"]):
                        raise ValueError("índice de ponto fora do intervalo")
                    print(f"Ponto {index}: XYZ={reviewed['points_xyz'][index].tolist()}; "
                          f"normal={reviewed['oriented_normals_xyz'][index].tolist()}; "
                          f"ramos={reviewed['candidate_branches'][index].tolist()}; "
                          f"incerto={bool(reviewed['uncertain_mask'][index])}; "
                          f"motivos={reason_names(int(reviewed['reason_bits'][index]))}")
                    if "candidate_cosines" in reviewed:
                        print(f"  cossenos={reviewed['candidate_cosines'][index].tolist()}; "
                              f"arestas={reviewed['candidate_edges'][index].tolist()}; "
                              f"proposta={int(reviewed['automatic_sign'][index])}")
            elif index is not None:
                key = "nodes_xyz" if "nodes_xyz" in keys else "points_xyz"
                if key not in keys or not 0 <= index < len(archive[key]):
                    raise ValueError("índice fora do intervalo ou NPZ sem nós/pontos XYZ")
                print(f"{key}[{index}]={archive[key][index].tolist()}")
                if key == "nodes_xyz" and "edges" in keys:
                    edges = archive["edges"]
                    neighbors = edges[(edges == index).any(axis=1)]
                    print(f"Arestas incidentes: {neighbors.tolist()}")
    elif suffix == ".json":
        print(json.dumps(json.loads(source.read_text(encoding="utf-8")),
                         indent=2, ensure_ascii=False))
    elif suffix == ".csv":
        with source.open(encoding="utf-8", newline="") as stream:
            first = stream.readline()
            if not first.startswith("# review_sha256="):
                stream.seek(0)
            reader = csv.DictReader(stream)
            total = 0
            decisions = {"keep": 0, "flip": 0}
            for row in reader:
                total += 1
                action = (row.get("action") or "").strip().lower()
                if action in decisions:
                    decisions[action] += 1
        print(f"Linhas: {total}; keep: {decisions['keep']}; flip: {decisions['flip']}")
    elif suffix == ".obj":
        metadata = source.with_suffix(".obj.json")
        if metadata.is_file():
            inspect_file(metadata)
        else:
            print("Sem JSON de métricas associado.")
    elif suffix == ".html":
        print("Visualização HTML; abra o caminho acima no navegador para inspecionar.")
    else:
        raise ValueError("formatos aceitos: .npz, .json, .csv, .obj e .html")


def list_files(kind: str) -> None:
    directories = {
        "dados": ROOT / "data/processed",
        "malhas": ROOT / "results/meshes",
        "figuras": ROOT / "results/figures",
    }
    for name, directory in directories.items():
        if kind not in {"todos", name}:
            continue
        files = sorted(item for item in directory.rglob("*") if item.is_file()
                       and item.name not in {".gitkeep", "README.md"})
        print(f"{name} ({len(files)}):")
        for item in files:
            print(f"  {item.relative_to(ROOT)}  ({item.stat().st_size:,} bytes)")


def execute(args: argparse.Namespace) -> int:
    if args.command == "testar":
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests",
                   "-p", args.padrao, "-v"]
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    if args.command == "listar":
        list_files(args.tipo)
    elif args.command == "inspecionar":
        inspect_file(path(args.arquivo), args.indice)
    elif args.command == "preparar":
        output = path(args.saida or suggest_output(ORIENTATION, review=True))
        new_output(output, review=True)
        result = prepare(path(args.amostra), path(args.grafo), output,
                         reference_path=path(args.referencias) if args.referencias else None)
        print(f"Revisão: {output}\nIncertos: {result['uncertain_count']}\n"
              f"CSV: {result['uncertain_csv']}\nTemplate: {result['reference_template']}")
    elif args.command == "plotar":
        from plots.plot_elaphes import main as plot_main

        output = path(args.saida or suggest_output(
            NORMAL_FIGURE if args.orientacao else LINE_FIGURE))
        new_output(output)
        command = ["line", "--cloud", str(path(args.amostra)), "--graph", str(path(args.grafo)),
                   "--output", str(output)]
        if args.orientacao:
            command += ["--orientation", str(path(args.orientacao)), "--highlight-uncertain",
                        "--show-manual", "--show-normals", "--max-normal-arrows", str(args.setas)]
        plot_main(command)
    elif args.command == "aplicar":
        source = path(args.orientacao)
        output = path(args.saida)
        new_output(output, review=True)
        correction = path(args.csv) if args.csv else source.with_suffix(".uncertain.csv")
        result = apply_manual_corrections(source, correction, output)
        print(f"Revisão corrigida: {output}\nIncertos restantes: {result['uncertain_count']}")
    elif args.command == "cossenos":
        prefix = path(args.prefixo or "data/processed/elaphes_centreline_cosine")
        result = compare_cosine_thresholds(path(args.orientacao), path(args.grafo), prefix)
        for report in result["thresholds"]:
            print(f"|cos| ≥ {report['cosine_threshold']:.2f}: "
                  f"keep={report['automatic_keep_count']}, flip={report['automatic_flip_count']}, "
                  f"incertos={report['uncertain_count']} -> {report['orientation_path']}")
        print(f"Resumo: {prefix.with_name(prefix.name + '_summary.json')}")
    elif args.command == "malha":
        output = path(args.saida)
        new_output(output)
        result = run_oriented_sample(
            path(args.orientacao), output, depth=args.profundidade, threads=args.threads,
            normal_source=args.modo,
            require_resolved=args.modo == "reviewed" and not args.permitir_incertos,
        )
        print(f"Malha diagnóstica: {output}\nNormais: {result['normal_source']}\n"
              f"Pontos: {result['sampled_vertices']}; sentidos incertos: "
              f"{result['normal_sign_uncertain_count']}\n"
              f"Faces: {result['mesh_triangles']}; bordas: {result['mesh_boundary_edges']}")
    elif args.command == "amostrar-roi":
        from cavegen.meshing.morphological_thickening import sample_measured_roi

        result = sample_measured_roi(
            path(args.ply), path(args.saida), max_bins=args.max_bins,
        )
        print(f"Amostra medida: {result['sample_path']}\n"
              f"Pontos no recorte: {result['roi_source_count']:,}; "
              f"representantes: {result['sampled_points']:,}")
    elif args.command == "espessar":
        from cavegen.meshing.morphological_thickening import run_experiment

        result = run_experiment(
            path(args.amostra), path(args.prefixo), voxel_size=args.voxel,
            radii_voxels=tuple(args.raios), depth=args.profundidade,
            threads=args.threads, probe_graph_path=path(args.grafo) if args.grafo else None,
        )
        print(f"Comparação diagnóstica: {path(args.prefixo).with_name(path(args.prefixo).name + '_summary.json')}\n"
              f"Pontos medidos: {result['measured_points']:,}")
    elif args.command == "voxelizar-roi":
        from cavegen.meshing.morphological_thickening import voxelize_raw_roi

        result = voxelize_raw_roi(
            path(args.ply), path(args.saida), voxel_size=args.voxel,
        )
        print(f"Ocupação bruta: {result['occupancy_path']}\n"
              f"Pontos no recorte: {result['roi_source_count']:,}; "
              f"voxels ocupados: {result['occupied_voxels']:,}")
    elif args.command == "espessar-bruto":
        from cavegen.meshing.morphological_thickening import run_raw_occupancy_experiment

        result = run_raw_occupancy_experiment(
            path(args.ocupacao), path(args.amostra), path(args.prefixo),
            radii_voxels=tuple(args.raios), depth=args.profundidade,
            threads=args.threads, probe_graph_path=path(args.grafo) if args.grafo else None,
        )
        print(f"Comparação diagnóstica: {path(args.prefixo).with_name(path(args.prefixo).name + '_summary.json')}\n"
              f"Pontos brutos no recorte: {result['raw_roi_points']:,}")
    return 0


def parser_for_menu() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    testing = commands.add_parser("testar", help="executar testes automatizados")
    testing.add_argument("--padrao", default="test_*.py", help="ex.: test_normal_orientation.py")
    listing = commands.add_parser("listar", help="listar artefatos locais")
    listing.add_argument("--tipo", choices=("todos", "dados", "malhas", "figuras"), default="todos")
    inspection = commands.add_parser("inspecionar", help="ver conteúdo e métricas de um arquivo")
    inspection.add_argument("arquivo")
    inspection.add_argument("--indice", type=int, help="índice exato de ponto ou nó em um NPZ")
    preparation = commands.add_parser("preparar", help="preparar normais e CSV de revisão")
    preparation.add_argument("--amostra", default=SAMPLE)
    preparation.add_argument("--grafo", default=GRAPH)
    preparation.add_argument("--referencias", help="JSON de nós validados em cortes")
    preparation.add_argument("--saida", help="novo NPZ; padrão: próximo nome livre")
    plotting = commands.add_parser("plotar", help="salvar HTML da linha e da revisão")
    plotting.add_argument("--amostra", default=SAMPLE)
    plotting.add_argument("--grafo", default=GRAPH)
    plotting.add_argument("--orientacao", help="NPZ da revisão; omita para ver só a linha")
    plotting.add_argument("--saida", help="novo HTML; padrão: próximo nome livre")
    plotting.add_argument("--setas", type=int, default=120)
    correction = commands.add_parser("aplicar", help="aplicar keep/flip do CSV")
    correction.add_argument("--orientacao", required=True)
    correction.add_argument("--csv", help="padrão: CSV associado ao NPZ")
    correction.add_argument("--saida", required=True)
    cosine = commands.add_parser("cossenos", help="comparar limiares 0,50/0,75/0,94 na mesma amostra")
    cosine.add_argument("--orientacao", default=ORIENTATION, help="NPZ com normais base fixas")
    cosine.add_argument("--grafo", default=GRAPH)
    cosine.add_argument("--prefixo", help="prefixo dos NPZ e JSON; não sobrescreve saídas")
    meshing = commands.add_parser("malha", help="gerar Poisson de uma revisão fixa")
    meshing.add_argument("--orientacao", required=True)
    meshing.add_argument("--saida", required=True)
    meshing.add_argument("--modo", choices=("baseline", "reviewed"), default="reviewed",
                         help="baseline=normais Open3D originais; reviewed=normais revisadas")
    meshing.add_argument("--profundidade", type=int, default=8)
    meshing.add_argument("--threads", type=int, default=1)
    meshing.add_argument("--permitir-incertos", action="store_true",
                         help="permitir malha revisada diagnóstica ainda com sentidos incertos")
    roi = commands.add_parser("amostrar-roi", help="amostrar pontos medidos do PLY no recorte X [12,35]")
    roi.add_argument("--ply", default=RAW_PLY)
    roi.add_argument("--saida", default=THICK_SAMPLE)
    roi.add_argument("--max-bins", type=int, default=2_000_000)
    thickening = commands.add_parser("espessar", help="comparar Poisson direto e dilatação morfológica")
    thickening.add_argument("--amostra", default=THICK_SAMPLE)
    thickening.add_argument("--prefixo", default="results/meshes/elaphes_thickening_dense2m")
    thickening.add_argument("--voxel", type=float, default=0.25)
    thickening.add_argument("--raios", type=int, nargs="+", default=[1, 2])
    thickening.add_argument("--grafo",
                            help="nós visuais como sonda diagnóstica, não referência interior validada")
    thickening.add_argument("--profundidade", type=int, default=8)
    thickening.add_argument("--threads", type=int, default=1)
    raw_roi = commands.add_parser("voxelizar-roi", help="voxelizar todos os pontos brutos do recorte")
    raw_roi.add_argument("--ply", default=RAW_PLY)
    raw_roi.add_argument("--saida", default=RAW_OCCUPANCY)
    raw_roi.add_argument("--voxel", type=float, default=0.1)
    raw_thickening = commands.add_parser("espessar-bruto", help="comparar Poisson com dilatação da ocupação bruta")
    raw_thickening.add_argument("--ocupacao", default=RAW_OCCUPANCY)
    raw_thickening.add_argument("--amostra", default=THICK_SAMPLE,
                               help="amostra medida para checagem de distância (não é holdout)")
    raw_thickening.add_argument("--prefixo", default="results/meshes/elaphes_thickening_raw_010")
    raw_thickening.add_argument("--raios", type=int, nargs="+", default=[0, 1, 2])
    raw_thickening.add_argument("--grafo", help="nós ainda não validados para sonda diagnóstica")
    raw_thickening.add_argument("--profundidade", type=int, default=8)
    raw_thickening.add_argument("--threads", type=int, default=1)
    return parser


def _ask(label: str, default: str = "") -> str:
    answer = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def interactive() -> int:
    menu = ("\n1 Testar  2 Listar  3 Inspecionar  4 Preparar revisão\n"
            "5 Plotar  6 Aplicar CSV  7 Gerar malha Poisson  8 Comparar cossenos\n"
            "9 Amostrar PLY no recorte  10 Comparar espessamento\n"
            "11 Voxelizar PLY bruto  12 Comparar espessamento bruto  0 Sair")
    while True:
        try:
            print(menu)
            choice = input("Escolha: ").strip()
            if choice == "0":
                return 0
            commands = {
                "1": lambda: ["testar", "--padrao", _ask("Padrão", "test_*.py")],
                "2": lambda: ["listar", "--tipo", _ask("Tipo (todos/dados/malhas/figuras)", "todos")],
                "3": lambda: ["inspecionar", _ask("Arquivo")],
                "4": lambda: ["preparar", "--amostra", _ask("Amostra", SAMPLE),
                              "--grafo", _ask("Grafo", GRAPH), "--saida",
                              _ask("Saída", suggest_output(ORIENTATION, review=True))],
                "5": lambda: ["plotar", "--amostra", _ask("Amostra", SAMPLE),
                              "--grafo", _ask("Grafo", GRAPH)],
                "6": lambda: ["aplicar", "--orientacao", _ask("NPZ da revisão", ORIENTATION),
                              "--saida", _ask("Novo NPZ de revisão", suggest_output(
                                  "data/processed/elaphes_centreline_normals_corrected.npz", review=True))],
                "7": lambda: ["malha", "--orientacao", _ask("NPZ da revisão", ORIENTATION),
                              "--modo", _ask("Normais (baseline/reviewed)", "reviewed"),
                              "--saida", _ask("Novo OBJ", suggest_output(
                                  "results/meshes/elaphes_normals_diagnostic.obj")), "--profundidade",
                              _ask("Profundidade Poisson", "8")],
                "8": lambda: ["cossenos", "--orientacao", _ask("NPZ base", ORIENTATION),
                              "--grafo", _ask("Grafo", GRAPH), "--prefixo",
                              _ask("Prefixo dos resultados", "data/processed/elaphes_centreline_cosine")],
                "9": lambda: ["amostrar-roi", "--ply", _ask("PLY bruto", RAW_PLY),
                              "--saida", _ask("Novo NPZ", THICK_SAMPLE),
                              "--max-bins", _ask("Limite de bins", "2000000")],
                "10": lambda: ["espessar", "--amostra", _ask("Amostra densa", THICK_SAMPLE),
                               "--prefixo", _ask("Prefixo novo das malhas",
                                                "results/meshes/elaphes_thickening_dense2m"),
                               "--voxel", _ask("Tamanho do voxel", "0.25"),
                               "--raios", *_ask("Raios em voxels, separados por espaço", "1 2").split()],
                "11": lambda: ["voxelizar-roi", "--ply", _ask("PLY bruto", RAW_PLY),
                               "--saida", _ask("Novo NPZ de ocupação", RAW_OCCUPANCY),
                               "--voxel", _ask("Tamanho do voxel", "0.1")],
                "12": lambda: ["espessar-bruto", "--ocupacao", _ask("Ocupação bruta", RAW_OCCUPANCY),
                               "--amostra", _ask("Amostra medida para checagem", THICK_SAMPLE),
                               "--prefixo", _ask("Prefixo novo das malhas",
                                                "results/meshes/elaphes_thickening_raw_010"),
                               "--raios", *_ask("Raios em voxels, separados por espaço", "0 1 2").split()],
            }
            if choice not in commands:
                print("Escolha inválida.")
                continue
            argv = commands[choice]()
            if choice == "3":
                index = _ask("Índice de ponto/nó (vazio = resumo)")
                if index:
                    argv += ["--indice", index]
            if choice in {"4", "5"}:
                option = _ask("JSON de referências" if choice == "4" else "NPZ de orientação (- = só linha)",
                              ORIENTATION if choice == "5" and path(ORIENTATION).exists() else "")
                if option and option != "-":
                    argv += ["--referencias" if choice == "4" else "--orientacao", option]
            if choice == "5":
                default_figure = NORMAL_FIGURE if "--orientacao" in argv else LINE_FIGURE
                argv += ["--saida", _ask("HTML", suggest_output(default_figure))]
            if choice == "7" and argv[argv.index("--modo") + 1] == "reviewed":
                if _ask("Permitir sentidos incertos? (s/N)", "N").lower() == "s":
                    argv.append("--permitir-incertos")
            if choice in {"10", "12"}:
                graph = _ask("Grafo opcional para sonda visual (- = nenhum)",
                             GRAPH if path(GRAPH).exists() else "")
                if graph and graph != "-":
                    argv += ["--grafo", graph]
            try:
                main(argv)
            except SystemExit:
                # argparse already displayed the invalid option; keep the menu open.
                continue
        except (EOFError, KeyboardInterrupt):
            print()
            return 0


def main(argv: list[str] | None = None) -> int:
    arguments = parser_for_menu().parse_args(argv)
    if arguments.command is None:
        return interactive()
    try:
        return execute(arguments)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
