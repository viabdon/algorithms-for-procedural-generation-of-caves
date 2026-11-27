"""Interactive, reproducible point-cloud voxelization and optional flood fill."""

from pathlib import Path
import json
import shlex
import subprocess
import sys
from typing import TYPE_CHECKING

from cavegen.datastream.run_reference_voxelization import main as voxelize

if TYPE_CHECKING:
    from cavegen.datastream.gallery_crop import GalleryCrop


def _ask(prompt: str, default: str = "") -> str:
    answer = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return answer or default


def _path(value: str) -> Path:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return Path(value).expanduser().absolute()


def _short_path(path: Path) -> str:
    path = path.absolute()
    cwd = Path.cwd()
    return str(path.relative_to(cwd) if path.is_relative_to(cwd) else path)


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
        print("Escolha " + ", ".join(choices) + ".")


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
        print("Use dimensões positivas, como 64 ou 32 64 64.")
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
    arguments = ["--input", _short_path(source), "--shape", *map(str, shape),
                 "--batch-size", str(batch), "--progress-every", str(progress),
                 "--output", _short_path(output_folder / "surface.npz")]
    if bounds is not None:
        arguments += ["--bounds", _short_path(bounds)]
    if fill:
        arguments += ["--interior-output", _short_path(output_folder / "interior.npz")]
    # Interactive runs never silently replace an earlier preparation.
    protected = ["surface.npz", "surface.bounds.json", "surface.run.json", "surface.log",
                 "surface.pid", "surface.command.json"] + (["interior.npz"] if fill else [])
    if any((output_folder / name).exists() for name in protected):
        raise ValueError("A pasta contém saídas anteriores; escolha outra pasta para esta execução.")
    return arguments, output_folder


def _print_crop_summary(crop: "GalleryCrop") -> None:
    print(f"Nuvem: {_short_path(crop.source)} | Partição: {crop.partition}")
    print(f"Domínio XYZ: {crop.extent_xyz} {crop.config['units']}")
    print(f"Pasta do volume: {_short_path(crop.destination)}")


def _voxelizar_recorte(crop: "GalleryCrop", prefix: str = "") -> None:
    from cavegen.datastream.gallery_crop import process_crop

    record = process_crop(
        crop, progress=lambda count: print(f"{prefix}Pontos lidos: {count:,}", flush=True),
        diagnostic_progress=lambda message: print(f"{prefix}{message}", flush=True),
    )
    counts = record["counts"]
    print(f"{prefix}Pontos lidos: {counts['read']:,} | Retidos: {counts['retained']:,}")
    print(
        f"{prefix}Ar candidato: {record['candidate_volume']:.3g} {crop.config['units']}³"
        f" | Reparo local: {record['repair_voxels']} voxels"
        f" | Tampas sintéticas: {record['auxiliary_cap_voxels']} voxels"
    )
    print(f"{prefix}Relatório do volume: {_short_path(crop.destination / record['diagnostics'])}")


def _voxelizar_conjunto(path: Path) -> None:
    from cavegen.datastream.gallery_crop import CropGeometryError, prepare_crop
    from cavegen.datastream.junction_fallback import OUTCOMES, attempt_failed_crops

    root = path.parent if path.name == "plan.json" and path.is_file() else path
    if not root.is_dir():
        raise ValueError("Informe uma pasta de recortes ou o plan.json correspondente.")
    configs = sorted(config for config in root.glob("*/crop.json") if config.is_file())
    if not configs:
        raise ValueError(f"Nenhum crop.json encontrado nas subpastas de {root}.")

    total = len(configs)
    print(f"{total} recortes encontrados em {_short_path(root)}.")
    if _ask("Digite PROCESSAR para confirmar o conjunto") != "PROCESSAR":
        return

    completed = skipped = failed = 0
    pending = []
    for index, config in enumerate(configs, start=1):
        prefix = f"[{index}/{total} {config.parent.name}] "
        try:
            crop = prepare_crop(config)
            prefix = f"[{index}/{total} {crop.config['crop_id']}] "
            print(f"{prefix}Voxelizando", flush=True)
            _voxelizar_recorte(crop, prefix)
            completed += 1
        except FileExistsError as error:
            skipped += 1
            print(f"{prefix}Pulado: {error}", flush=True)
        except (OSError, ValueError, TypeError, KeyError) as error:
            failed += 1
            print(f"{prefix}Não foi possível concluir: {error}", flush=True)
            if isinstance(error, CropGeometryError) and error.outcome in OUTCOMES:
                pending.append((config, error.outcome))
    print(f"Lote: {completed} volumes salvos, {skipped} pulados, {failed} sem volume.")
    if pending:
        print(f"Triagem de junções para {len(pending)} recortes sem volume.", flush=True)
        attempt_failed_crops(pending, progress=lambda message: print(message, flush=True))


def _crop_menu() -> None:
    from cavegen.datastream.gallery_crop import CROP_FORMATS, CropGeometryError, inspect_crop, prepare_crop
    from cavegen.datastream.crop_planner import default_plan_destination, propose_crops, read_plan_config
    from cavegen.datastream.crop_preview import (
        CROP_PREVIEW_NAME,
        PLAN_PREVIEW_NAME,
        preview_manifest,
        write_crop_preview,
        write_individual_crop_previews,
    )
    from cavegen.datastream.gallery_leak_preview import write_leak_preview
    from cavegen.datastream.gallery_reports import PREVIEW_FILE, find_report

    template = "configs/crops/gallery.template.json"
    while True:
        print("\nRecortes por galeria")
        print("1. Listar nuvens brutas")
        print("2. Conferir JSON do recorte")
        print("3. Voxelizar recortes")
        print("4. Inspecionar volume ou vazamento")
        print("5. Extrair recortes pela linha central")
        print("6. Visualizar recortes e tampas")
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
                        print(_short_path(source))
            elif choice == "4":
                selection = _ask("Pasta do volume, histórico de tentativas ou summary.csv (Enter para cancelar)")
                if selection:
                    path = _path(selection)
                    report = find_report(path)
                    if (path / "interior.npz").is_file():
                        slices, volume = inspect_crop(path)
                        print(f"Fatias: {_short_path(slices)}")
                        print(f"Volume 3D: {_short_path(volume)}", flush=True)
                    elif report is None:
                        raise FileNotFoundError(f"Não há resultado nem diagnóstico em {path}.")
                    if report is not None:
                        print(f"Relatório: {_short_path(report)}", flush=True)
                        if report.suffix == ".json" or report.with_name(PREVIEW_FILE).is_file():
                            print(f"Vazamento: {_short_path(write_leak_preview(report))}", flush=True)
            elif choice == "5":
                plan = _ask("JSON do planejamento (modelo em configs/crops/plan.template.json; Enter para cancelar)")
                if not plan:
                    continue
                path = _path(plan)
                spec = read_plan_config(path)
                line = _ask("Arquivo de linha central (Enter usa o JSON ou calcula se vazio)")
                target = _path(_ask("Pasta nova para o plano", str(default_plan_destination(spec))))
                if not line and not spec["centreline"]:
                    print("A linha central será estimada em CPU. O resultado ficará em revisão.")
                manifest = propose_crops(
                    path, target, centreline=_path(line) if line else None,
                    progress=lambda phase, count: print(f"{phase}: {count:,} pontos lidos", flush=True),
                )
                flagged = sum(bool(crop["review_reasons"]) for crop in manifest["crops"])
                print(f"Propostos {manifest['proposed']} de {manifest['requested']}. Com alertas: {flagged}.")
                print(f"Plano gerado: {_short_path(target / 'plan.json')}")
            elif choice == "6":
                print("1. Recortes juntos")
                print("2. Um HTML por recorte")
                print("0. Voltar")
                mode = _choice("Opção", "1", ("0", "1", "2"))
                if mode == "0":
                    continue
                path = _ask("Pasta do plano, plan.json ou PLY de um recorte (Enter para cancelar)")
                if not path:
                    continue
                source = _path(path)
                if mode == "2":
                    for output in write_individual_crop_previews(source):
                        print(f"Prévia: {_short_path(output)}")
                else:
                    manifest = preview_manifest(source)
                    default = (
                        manifest.with_name(PLAN_PREVIEW_NAME) if manifest
                        else source.with_name(CROP_PREVIEW_NAME)
                    )
                    output = _path(_ask("Arquivo HTML", _short_path(default)))
                    print(f"Prévia: {_short_path(write_crop_preview(source, output))}")
            elif choice == "3":
                print("1. Um recorte (crop.json)")
                print("2. Recortes em lote (pasta ou plan.json)")
                print("0. Voltar")
                mode = _choice("Opção", "0", ("0", "1", "2"))
                if mode == "1":
                    path = _ask(f"JSON do recorte (modelo em {template}; Enter para cancelar)")
                    if path:
                        from cavegen.datastream.junction_fallback import OUTCOMES, attempt_failed_crops

                        config = _path(path)
                        confirmed = False
                        try:
                            crop = prepare_crop(config)
                            _print_crop_summary(crop)
                            confirmed = _ask("Digite PROCESSAR para confirmar") == "PROCESSAR"
                            if confirmed:
                                _voxelizar_recorte(crop)
                        except CropGeometryError as error:
                            if error.outcome not in OUTCOMES:
                                raise
                            print(f"Recorte sem volume: {error}")
                            if confirmed or _ask("Digite PROCESSAR para testar a junção") == "PROCESSAR":
                                attempt_failed_crops([(config, error.outcome)],
                                                     progress=lambda message: print(message, flush=True))
                elif mode == "2":
                    path = _ask("Pasta dos recortes ou plan.json (Enter para cancelar)")
                    if path:
                        _voxelizar_conjunto(_path(path))
            else:
                path = _ask(f"JSON do recorte (modelo em {template}; Enter para cancelar)")
                if not path:
                    continue
                crop = prepare_crop(_path(path))
                print(json.dumps(crop.config, indent=2, ensure_ascii=False))
                _print_crop_summary(crop)
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(f"Não foi possível concluir: {error}")
        except KeyboardInterrupt:
            print("\nOperação cancelada.")


def main() -> None:
    """Ask for a source and parameters, then run or detach the same CLI pipeline."""
    try:
        while True:
            print("\nDatastream — preparação de nuvens e recortes")
            print("1. Voxelizar nuvem inteira")
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
                mode = _choice("Execução (1 primeiro plano, 2 segundo plano, 0 cancelar)",
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
                    print("Acompanhar: tail -f " + shlex.quote(_short_path(log_path)))
                    print("O processo continua após fechar o menu e o terminal (Linux).")
            except (OSError, ValueError) as error:
                print(f"Não foi possível concluir: {error}")
    except (EOFError, KeyboardInterrupt):
        print("\nMenu encerrado.")
