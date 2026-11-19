"""Interactive, reproducible point-cloud voxelization and optional flood fill."""

from pathlib import Path
import json
import shlex
import subprocess
import sys

from cavegen.datastream.run_reference_voxelization import main as voxelize


def _ask(prompt: str, default: str = "") -> str:
    answer = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return answer or default


def _path(value: str) -> Path:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return Path(value).expanduser().absolute()


def _integer(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        try:
            value = int(_ask(prompt, str(default)))
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"Informe um inteiro maior ou igual a {minimum}.")


def _choice(prompt: str, default: str, choices: tuple[str, ...]) -> str:
    while True:
        value = _ask(prompt, default).lower()
        if value in choices:
            return value
        print("Opções: " + ", ".join(choices))


def _prepare() -> tuple[list[str], Path]:
    while True:
        source = _path(_ask("Arquivo da nuvem (.xyz, .ply, .f32 ou .las)"))
        if source.is_file() and source.suffix.lower() in (".xyz", ".ply", ".f32", ".las"):
            break
        print("Escolha um arquivo existente com extensão XYZ, PLY, F32 ou LAS.")
    while True:
        try:
            parts = [int(x) for x in _ask("Grade ZYX (um lado ou três dimensões)", "64").split()]
            shape = parts * 3 if len(parts) == 1 else parts
            if len(shape) == 3 and min(shape) > 0:
                break
        except ValueError:
            pass
        print("Exemplos válidos: 64 ou 32 64 64; dimensões positivas.")
    default_folder = Path("data/processed/references") / source.stem / ("x".join(map(str, shape)))
    output_folder = _path(_ask("Pasta de saída", str(default_folder)))
    while True:
        bounds_text = _ask("JSON de limites existente (Enter para calcular)")
        bounds = _path(bounds_text) if bounds_text else None
        if bounds is None or bounds.is_file():
            break
        print("Arquivo de limites não encontrado.")
    batch = _integer("Pontos por lote", 65536)
    progress = _integer("Intervalo do progresso em pontos (0 desativa)", 1000000, 0)
    fill = _choice("Inferir interior por flood fill? (s/n)", "s", ("s", "n")) == "s"
    arguments = ["--input", str(source), "--shape", *map(str, shape),
                 "--batch-size", str(batch), "--progress-every", str(progress),
                 "--output", str(output_folder / "surface.npz")]
    if bounds is not None:
        arguments += ["--bounds", str(bounds)]
    if fill:
        arguments += ["--interior-output", str(output_folder / "interior.npz")]
    # Interactive runs never silently replace an earlier preparation.
    protected = ["surface.npz", "surface.bounds.json", "surface.run.json", "surface.log",
                 "surface.pid", "surface.command.json"] + (["interior.npz"] if fill else [])
    if any((output_folder / name).exists() for name in protected):
        raise ValueError("A pasta contém saídas anteriores; escolha outra pasta para esta execução.")
    return arguments, output_folder


def _crop_menu() -> None:
    from cavegen.datastream.gallery_crop import CROP_FORMATS, inspect_crop, prepare_crop, process_crop
    from cavegen.datastream.crop_planner import propose_crops
    from cavegen.datastream.crop_preview import write_crop_preview

    template = "configs/crops/gallery.template.json"
    while True:
        print("\nRecortes por galeria")
        print("1. Listar nuvens brutas")
        print("2. Conferir configuração JSON")
        print("3. Processar recorte em CPU")
        print("4. Inspecionar recorte processado")
        print("5. Propor e extrair N recortes pela linha central")
        print("6. Gerar prévia 3D de um PLY recortado")
        print("0. Voltar")
        choice = _choice("Opção", "0", ("0", "1", "2", "3", "4", "5", "6"))
        if choice == "0":
            return
        try:
            if choice == "1":
                root = _path(_ask("Pasta das nuvens", "/run/media/midnavi/Pablo/TCC/DATA/RAW/data"))
                if not root.is_dir():
                    raise FileNotFoundError(f"Pasta das nuvens indisponível: {root}")
                for source in sorted(root.rglob("*")):
                    if (
                        source.suffix.lower() in CROP_FORMATS
                        and "mesh" not in source.relative_to(root).parts
                        and source.is_file()
                    ):
                        print(source)
            elif choice == "4":
                folder = _ask("Pasta da saída do recorte (Enter para cancelar)")
                if folder:
                    inspect_crop(_path(folder))
            elif choice == "5":
                plan = _ask("JSON do planejamento (modelo em configs/crops/plan.template.json; Enter para cancelar)")
                if not plan:
                    continue
                path = _path(plan)
                target = _path(_ask("Pasta nova para os recortes", f"data/processed/crop_plans/{path.stem}"))
                manifest = propose_crops(
                    path, target,
                    progress=lambda phase, count: print(f"{phase}: {count:,} pontos lidos", flush=True),
                )
                flagged = sum(bool(crop["review_reasons"]) for crop in manifest["crops"])
                print(f"Propostos {manifest['proposed']} de {manifest['requested']}. Com alertas: {flagged}.")
                print(f"Plano e nuvens para revisão: {target}")
            elif choice == "6":
                ply = _ask("PLY do recorte (Enter para cancelar)")
                if not ply:
                    continue
                source = _path(ply)
                output = _path(_ask("Arquivo HTML", str(source.with_name("preview.html"))))
                print(f"Prévia para abrir no navegador: {write_crop_preview(source, output)}")
            else:
                path = _ask(f"JSON do recorte (modelo em {template}; Enter para cancelar)")
                if not path:
                    continue
                crop = prepare_crop(_path(path))
                if choice == "2":
                    print(json.dumps(crop.config, indent=2, ensure_ascii=False))
                print(f"Fonte: {crop.source} | Partição: {crop.partition}")
                print(f"Domínio XYZ: {crop.extent_xyz} {crop.config['units']}")
                print(f"Saída: {crop.destination.absolute()}")
                if choice == "3" and _ask("Digite PROCESSAR para confirmar") == "PROCESSAR":
                    record = process_crop(
                        crop, progress=lambda count: print(f"Pontos lidos: {count:,}", flush=True)
                    )
                    print(f"Contagens de seleção: {record['counts']}")
                    print(f"Ar candidato: {record['candidate_volume']:.3g} {crop.config['units']}³")
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(f"Não foi possível concluir: {error}")
        except KeyboardInterrupt:
            print("\nOperação cancelada.")


def main() -> None:
    """Ask for a source and parameters, then run or detach the same CLI pipeline."""
    try:
        while True:
            print("\nPreparação de cavernas — XYZ / PLY / F32 / LAS")
            print("1. Gerar superfície e, opcionalmente, interior candidato da nuvem inteira")
            print("2. Preparar recortes por galeria")
            print("0. Sair")
            choice = _choice("Opção", "1", ("0", "1", "2"))
            if choice == "0":
                return
            if choice == "2":
                _crop_menu()
                continue
            try:
                arguments, folder = _prepare()
                command = [sys.executable, "-u", "-m",
                           "cavegen.datastream.run_reference_voxelization", *arguments]
                print("\nComando equivalente:\n" + shlex.join(command))
                print("A superfície e o interior serão arquivos separados.")
                mode = _choice("Execução: 1 primeiro plano, 2 background, 0 cancelar",
                               "1", ("0", "1", "2"))
                if mode == "0":
                    continue
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "surface.command.json").write_text(json.dumps({
                    "command_argv": command, "command_shell": shlex.join(command),
                    "working_directory": str(Path.cwd()), "execution_mode": mode,
                }, indent=2) + "\n", encoding="utf-8")
                if mode == "1":
                    voxelize(arguments)
                else:
                    folder.mkdir(parents=True, exist_ok=True)
                    log_path = folder / "surface.log"
                    with log_path.open("x", encoding="utf-8") as log:
                        process = subprocess.Popen(
                            command, stdin=subprocess.DEVNULL, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True,
                        )
                    (folder / "surface.pid").write_text(str(process.pid) + "\n", encoding="utf-8")
                    print(f"Processo iniciado: PID {process.pid}")
                    print("Acompanhar: tail -f " + shlex.quote(str(log_path)))
                    print("O processo continua após fechar o menu e o terminal (Linux).")
            except (OSError, ValueError) as error:
                print(f"Não foi possível concluir: {error}")
    except (EOFError, KeyboardInterrupt):
        print("\nMenu encerrado.")
