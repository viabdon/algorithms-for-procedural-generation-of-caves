"""Triage unsuccessful crops and batch the measured junction searches by source."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import numpy as np

from cavegen.datastream.centreline import CentrelineIndex, passages_from_graph, read_graph
from cavegen.datastream.gallery_junctions import CONTEXT, MAX_STATION, PADDING, save_junction, solve_junction
from cavegen.datastream.point_cloud import iter_point_cloud_xyz

OUTCOMES = {
    "missing_contour", "invalid_cap", "seed_blocked", "ambiguous_passage", "patch_budget_exceeded",
    "escape_path_without_supported_voxels", "patch_disconnects_a_probe_seed", "independent_check_failed",
}
DEFAULT_ROOT = Path("data/processed/experiments/juncoes_auto")


@dataclass(frozen=True)
class Context:
    source: Path
    graph: Path
    origin: tuple
    voxel_size: float

    @property
    def key(self):
        return hashlib.sha256(repr(self).encode()).hexdigest()[:12]


def _context(path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    proposal = cfg.get("proposal", {})
    start, end = proposal["cut_stations"]
    branch = cfg["branch"].removeprefix("passagem_")
    diagnostic = cfg.get("leak_diagnostics", {})
    manifest = path.parent.parent / "plan.json"
    plan = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    origin = tuple(cfg["source_origin_xyz"])
    if plan and tuple(plan["source_origin_xyz"]) != origin:
        raise ValueError("Origem do recorte diverge da origem do plano.")
    source = diagnostic.get("raw_source")
    graph = diagnostic.get("centreline")
    source = path.parent / source if source else manifest.parent / plan["source"]
    graph = path.parent / graph if graph else manifest.parent / plan["centreline"]
    return Context(source.expanduser().resolve(), graph.expanduser().resolve(), origin,
                   float(cfg["voxel_size"])), int(branch) - 1, float(start), float(end)


def _nodes(lines):
    incident = defaultdict(list)
    for branch, line in enumerate(lines):
        for tip, is_junction in enumerate(line.junctions):
            if is_junction:
                incident[tuple(line.xyz[0 if tip == 0 else -1])].append((branch, tip))
    return dict(sorted(incident.items()))


def _near_junctions(lines, branch, start, end, size):
    line = lines[branch]
    length = line.stations[-1]
    if not 0 <= start <= end <= length + size * 1e-6:
        raise ValueError("Estações do recorte fora do ramo.")
    return [tuple(line.xyz[index]) for index, distance, junction in
            zip((0, -1), (start, length - end), line.junctions)
            if junction and distance <= MAX_STATION * size]


def _fingerprint(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_dev


def _gather(context, targets, stage, progress):
    files = {point: stage / f"{index}.f64" for index, point in enumerate(targets)}
    reach = (MAX_STATION + CONTEXT + PADDING) * context.voxel_size
    lows = {point: np.array(point) - reach for point in targets}
    highs = {point: np.array(point) + reach for point in targets}
    read = 0
    before = _fingerprint(context.source)
    for batch in iter_point_cloud_xyz(context.source, 131072, origin_xyz=np.asarray(context.origin)):
        if not len(batch):
            continue
        read += len(batch)
        if read // 1_000_000 != (read - len(batch)) // 1_000_000:
            progress(f"{context.source.name}: {read:,} pontos lidos")
        lo, hi = batch.min(axis=0), batch.max(axis=0)
        for point, path in files.items():
            if np.any((hi < lows[point]) | (lo > highs[point])):
                continue
            kept = batch[np.all((batch >= lows[point]) & (batch <= highs[point]), axis=1)]
            if len(kept):
                with path.open("ab") as stream:
                    kept.astype("<f8", copy=False).tofile(stream)
    if before != _fingerprint(context.source):
        raise ValueError("A nuvem original mudou durante a leitura.")
    return files


def attempt_failed_crops(cases, output=None, progress=print, *, recenter_axes=False):
    """Process (config_path, failure_outcome) pairs without duplicating a junction."""
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        output = DEFAULT_ROOT / f"{stamp}-{uuid4().hex[:8]}"
    output = Path(output)
    groups = defaultdict(list)
    rows = []
    for path, outcome in cases:
        path = Path(path)
        row = {"config": str(path), "falha_anterior": outcome, "juncoes": []}
        rows.append(row)
        if outcome not in OUTCOMES:
            row["resultado"] = "falha_fora_da_triagem"
            continue
        try:
            context, branch, start, end = _context(path)
            groups[context].append((row, branch, start, end))
        except (OSError, ValueError, KeyError, TypeError) as error:
            row.update(resultado="sem_contexto_do_plano", motivo=str(error))

    output.mkdir(parents=True, exist_ok=False)
    results = {"recortes": rows, "juncoes": {}}

    def checkpoint():
        tmp = output / ".resultados.json.tmp"
        tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(output / "resultados.json")

    checkpoint()
    for context, group in groups.items():
        try:
            vertices, edges = read_graph(context.graph)
            lines = passages_from_graph(vertices - np.asarray(context.origin), edges)
        except (OSError, ValueError) as error:
            for row, *_ in group:
                row.update(resultado="grafo_indisponivel", motivo=str(error))
            checkpoint()
            continue
        incident = _nodes(lines)
        names = {point: f"{context.key}/juncao_{i:03}" for i, point in enumerate(incident, 1)}
        targets = set()
        for row, branch, start, end in group:
            try:
                if not 0 <= branch < len(lines):
                    raise ValueError("Ramo fora do grafo.")
                near = _near_junctions(lines, branch, start, end, context.voxel_size)
                targets.update(near)
                row.update(juncoes=[names[p] for p in near],
                           resultado="aguardando_juncao" if near else "sem_juncao_proxima")
            except ValueError as error:
                row.update(resultado="ramo_invalido", motivo=str(error))
        checkpoint()
        if not targets:
            continue
        progress(f"{context.source.name}: {len(targets)} junções únicas após triagem")
        try:
            with TemporaryDirectory(dir=output) as temp:
                files = _gather(context, sorted(targets), Path(temp), progress)
                index = CentrelineIndex(lines, context.voxel_size / 2)
                for i, point in enumerate(sorted(targets), 1):
                    name = names[point]
                    progress(f"[{i}/{len(targets)}] {name}")
                    file = files[point]
                    if file.is_file():
                        points = np.memmap(file, mode="r", dtype="<f8").reshape(-1, 3)
                        record, volume = solve_junction(
                            points, lines, index, np.asarray(point), incident[point], context.voxel_size,
                            recenter_axes=recenter_axes,
                        )
                    else:
                        record, volume = {"resultado": "sem_pontos"}, None
                    record.update(no_xyz=(np.asarray(context.origin) + point).tolist(),
                                  source=str(context.source), centreline=str(context.graph),
                                  voxel_size=context.voxel_size)
                    if volume is not None:
                        destination = output / name
                        destination.parent.mkdir(exist_ok=True)
                        save_junction(destination, record, volume, np.asarray(context.origin),
                                      context.source, context.graph, context.voxel_size)
                        record["volume"] = name
                    results["juncoes"][name] = record
                    progress(f"{name}: {record['resultado']}")
                    checkpoint()
        except OSError as error:
            for row, *_ in group:
                if row["resultado"] == "aguardando_juncao":
                    row.update(resultado="fonte_indisponivel", motivo=str(error))
            checkpoint()
        for row, *_ in group:
            if row["resultado"] == "aguardando_juncao":
                sealed = any(results["juncoes"][name]["resultado"] == "volume_salvo" for name in row["juncoes"])
                row["resultado"] = "volume_de_juncao_salvo" if sealed else "juncao_sem_volume"
        checkpoint()
    progress(f"Relatório de junções: {output / 'resultados.json'}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="JSON com registros config e falha_anterior")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--recenter-axes", action="store_true", help="Testar recentramento local após falha.")
    args = parser.parse_args()
    rows = json.loads(args.inventory.read_text(encoding="utf-8"))
    attempt_failed_crops(((r["config"], r["falha_anterior"]) for r in rows), args.output,
                         progress=lambda message: print(message, flush=True), recenter_axes=args.recenter_axes)


if __name__ == "__main__":
    main()
