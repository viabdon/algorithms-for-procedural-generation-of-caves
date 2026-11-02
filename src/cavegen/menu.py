"""Interactive terminal entry point for generation and structural experiments."""

from __future__ import annotations

import csv
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile

import yaml

from cavegen.benchmark.run_generation_benchmark import run_configuration
from cavegen.benchmark.structural_evaluation import evaluate_archive
from cavegen.core.config import load_yaml
from cavegen.metrics.structural import MetricValue
from cavegen.metrics.validation import validate_connectivity, validate_spacing

Read = Callable[[str], str]
Write = Callable[[str], None]


@dataclass
class _Session:
    csv_path: Path
    volumes_dir: Path
    read: Read
    write: Write


def _answer(session: _Session, label: str, default: str = "") -> str:
    suffix = f" [Enter = {default}]" if default else ""
    value = session.read(f"{label}{suffix}: ").strip()
    if value == ":voltar":
        raise KeyboardInterrupt
    return value or default


def _integer(
    session: _Session, label: str, default: int, minimum: int, maximum: int | None = None
) -> int:
    while True:
        try:
            value = int(_answer(session, label, str(default)))
            if value < minimum or (maximum is not None and value > maximum):
                raise ValueError
            return value
        except ValueError:
            limit = f" a {maximum}" if maximum is not None else " ou maior"
            session.write(f"Digite um inteiro de {minimum}{limit}.")


def _probability(session: _Session) -> float:
    while True:
        try:
            value = float(_answer(session, "Probabilidade inicial de ar (0 a 1)", "0.45"))
            if not 0 <= value <= 1:
                raise ValueError
            return value
        except ValueError:
            session.write("Digite um número finito de 0 a 1, usando ponto decimal.")


def _path(session: _Session, label: str, default: str = "") -> Path:
    while True:
        value = _answer(session, label, default).strip('"').strip("'")
        if value:
            return Path(value).expanduser()
        session.write("Informe um caminho ou digite :voltar para cancelar.")


def _describe_record(session: _Session, row: dict[str, MetricValue]) -> None:
    session.write(
        f"Salvo: {row['run_id']} | {row['algorithm']} | {row['shape']} | "
        f"abertos={row['open_voxels']} | componentes={row['component_count']}"
    )
    session.write(f"  Volume: {row['volume_path']}")
    session.write(
        f"  Maior componente/ar: {row['largest_component_ratio']} | "
        f"EDT média/mediana/máx: {row['dt_mean']} / {row['dt_median']} / {row['dt_max']} "
        f"({row['distance_unit']})"
    )
    if row["is_degenerate"]:
        session.write(f"  Degenerado: {row['degenerate_reason']}; EDT ausente.")
    session.write(f"  Tabela: {session.csv_path}")


def _generate(session: _Session) -> None:
    session.write("\nGerar um volume 64³ em ZYX e salvar NPZ + métricas no CSV.")
    session.write("1) Random Walk: escava uma caminhada por seis direções.")
    session.write("2) CA básico do main: suaviza ruído pela contagem de 26 vizinhos.")
    choice = _integer(session, "Algoritmo", 1, 1, 2)
    seed = _integer(session, "Seed reprodutível", 0, 0)
    if choice == 1:
        session.write("Passos controlam a duração da caminhada; raio engrossa a escavação.")
        algorithm = "random_walk"
        params = {
            "steps": _integer(session, "Passos", 6000, 1),
            "brush_radius": _integer(session, "Raio do pincel em voxels", 1, 0, 63),
        }
    else:
        session.write("Limiar menor tende a abrir mais ar; a borda permanece sólida.")
        algorithm = "cellular_automata"
        params = {
            "initial_open_probability": _probability(session),
            "iterations": _integer(session, "Iterações (0 mantém a grade inicial)", 5, 0),
            "threshold_open_neighbors": _integer(session, "Limiar de vizinhos abertos", 13, 0, 26),
        }
    config = {
        "experiment_name": "interactive_64",
        "shape": [64, 64, 64],
        "seeds": [seed],
        "algorithms": {algorithm: params},
        "outputs": {"volumes_dir": str(session.volumes_dir)},
    }
    session.write("Gerando e avaliando...")
    run_configuration(config, session.csv_path,
                      on_record=lambda row: _describe_record(session, row))


def _run_yaml(session: _Session) -> None:
    session.write("\nExecutar todas as seeds/algoritmos de uma configuração YAML existente.")
    source = _path(session, "Configuração YAML", "configs/experiments/baseline_64.yaml")
    config = load_yaml(source)
    session.write(f"Grade ZYX: {config.get('shape', [64, 64, 64])}")
    session.write(f"Seeds: {config.get('seeds', [0])}")
    session.write("Os parâmetros e o diretório de volumes seguem o YAML; o CSV é o da sessão.")
    if _answer(session, "Executar esta configuração? (s/n)", "s").lower() != "s":
        session.write("Execução cancelada.")
        return
    run_configuration(config, session.csv_path, config_path=str(source),
                      on_record=lambda row: _describe_record(session, row))


def _recent_records(session: _Session, limit: int) -> list[dict[str, str]]:
    if not session.csv_path.exists() or session.csv_path.stat().st_size == 0:
        return []
    with session.csv_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required = {"run_id", "structural_schema_version", "volume_path", "variant"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{session.csv_path}: cabeçalho incompatível com a tabela central.")
        return list(deque(reader, maxlen=limit))


def _display_rows(session: _Session, rows: list[dict[str, str]]) -> None:
    if not rows:
        session.write("Nenhuma execução registrada nesta tabela.")
    for index, row in enumerate(rows, 1):
        session.write(
            f"{index}) {row.get('algorithm')} | {row.get('variant')} | "
            f"seed={row.get('seed')} | {row.get('shape')} | "
            f"ar={row.get('open_ratio')} | componentes={row.get('component_count')}"
        )
        session.write(f"   run_id={row['run_id']} | NPZ={row['volume_path']}")
        session.write(
            f"   maior/ar={row.get('largest_component_ratio')} | "
            f"EDT média/mediana/máx={row.get('dt_mean') or 'ausente'} / "
            f"{row.get('dt_median') or 'ausente'} / {row.get('dt_max') or 'ausente'} | "
            f"conectividade={row.get('connectivity')} | "
            f"spacing ZYX={row.get('spacing_z')} {row.get('spacing_y')} {row.get('spacing_x')}"
        )


def _evaluate(session: _Session) -> None:
    session.write("\nReavaliar um NPZ de volume gerado (True = ar conhecido).")
    session.write("Grades surface_voxels e point clouds não são entradas desta opção.")
    rows = _recent_records(session, 10)
    _display_rows(session, rows)
    while True:
        raw = _answer(session, "Número da lista ou caminho completo do NPZ")
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            source = Path(rows[int(raw) - 1]["volume_path"])
            break
        if raw:
            source = Path(raw.strip('"').strip("'")).expanduser()
            break
        session.write("Informe o número, caminho ou :voltar.")
    while True:
        connectivity = _integer(session, "Conectividade (6 = faces; 26 = inclui diagonais)", 6, 6, 26)
        try:
            connectivity = validate_connectivity(connectivity)
            break
        except ValueError:
            session.write("As opções permitidas são 6 e 26.")
    while True:
        text = _answer(session, "Spacing Z Y X (três números, ponto decimal)", "1 1 1")
        try:
            spacing = validate_spacing(tuple(float(value) for value in text.split()))
            break
        except (TypeError, ValueError):
            session.write("Spacing requer três números positivos e finitos em ordem ZYX.")
    row = evaluate_archive(source, session.csv_path, connectivity=connectivity, spacing_zyx=spacing)
    _describe_record(session, row)
    session.write("Reavaliação registrada; tempo de geração e RSS ficam ausentes.")


def _list_results(session: _Session) -> None:
    limit = _integer(session, "Quantas linhas recentes mostrar (máximo 1000)", 10, 1, 1000)
    _display_rows(session, _recent_records(session, limit))


def _destinations(session: _Session) -> None:
    csv_path = _path(session, "CSV central da sessão", str(session.csv_path))
    volumes_dir = _path(session, "Pasta dos volumes interativos", str(session.volumes_dir))
    session.csv_path, session.volumes_dir = csv_path, volumes_dir
    session.write("Destinos atualizados nesta sessão; arquivos existentes foram preservados.")


def _help(session: _Session) -> None:
    session.write(
        "\n1: gera um volume 64³ com parâmetros e seed informados; salva NPZ e CSV.\n"
        "2: executa um YAML com várias seeds/algoritmos e acompanha cada linha salva.\n"
        "3: recalcula métricas de um NPZ existente com conectividade/spacing explícitos.\n"
        "4: consulta as últimas linhas sem carregar volumes nem alterar o CSV.\n"
        "5: troca CSV e pasta de geração interativa apenas durante esta sessão.\n"
        "6: mostra esta ajuda. 0: sai do programa.\n"
        "Enter aceita o padrão; :voltar ou Ctrl+C cancela a ação; EOF encerra.\n"
        "Unidades: spacing 1 1 1 usa voxels; outro spacing usa sua unidade declarada.\n"
        "Ausências de EDT nos casos degenerados aparecem como células vazias.\n"
        "Glossário e contratos: docs/metricas-estruturais.md."
    )


def run_menu(
    input_fn: Read = input,
    output_fn: Write = print,
    *,
    csv_path: str | Path = "results/csv/experiments.csv",
    volumes_dir: str | Path = "results/volumes",
) -> None:
    """Run the reusable terminal loop until explicit exit or end of input.

    Parameters
    ----------
    input_fn, output_fn
        Text input/output functions, injectable for terminal-independent tests.
    csv_path, volumes_dir
        Initial session destinations, editable through option 5. Opening the
        menu or consulting results does not create files. Paths are relative
        to the working directory unless explicitly absolute.

    Notes
    -----
    Expected file/input errors return to the menu. Ctrl+C or :voltar cancel
    the current operation; EOF exits cleanly even inside a prompt. Completed
    rows remain saved if a later operation is interrupted.
    """
    session = _Session(Path(csv_path), Path(volumes_dir), input_fn, output_fn)
    actions = {
        "1": ("Gerar e avaliar um volume 64³", _generate),
        "2": ("Executar experimento YAML", _run_yaml),
        "3": ("Avaliar NPZ existente", _evaluate),
        "4": ("Consultar resultados recentes", _list_results),
        "5": ("Alterar destinos da sessão", _destinations),
        "6": ("Ajuda e glossário", _help),
    }
    while True:
        session.write(f"\n=== CaveGen: geração e métricas ===\nCSV: {session.csv_path}")
        for key, (label, _) in actions.items():
            session.write(f"{key}) {label}")
        session.write("0) Sair | Enter aceita padrões | :voltar cancela a ação")
        try:
            choice = _answer(session, "Opção")
            if choice == "0":
                return
            if choice not in actions:
                session.write("Opção inválida. Escolha de 0 a 6.")
                continue
            actions[choice][1](session)
        except EOFError:
            session.write("Entrada encerrada. Saindo.")
            return
        except KeyboardInterrupt:
            session.write("Ação cancelada. Retornando ao menu.")
        except (OSError, ValueError, TypeError, KeyError, BadZipFile, yaml.YAMLError) as error:
            session.write(f"Não foi possível concluir a ação: {error}")


def main() -> None:
    """Open the terminal menu using standard input and output."""
    run_menu()


if __name__ == "__main__":
    main()
