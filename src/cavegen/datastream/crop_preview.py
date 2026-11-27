"""Save and preview the XYZ-only binary PLY used by automatic gallery crops."""

import json
from pathlib import Path

import numpy as np

from cavegen.datastream.centreline import Passage, passages_from_graph, read_graph
from cavegen.datastream.gallery_crop import parse_section
from cavegen.datastream.ply import read_ply_header
from cavegen.datastream.ply_types import PlyProperty

XYZ_PROPERTIES = tuple(PlyProperty(name, "double") for name in ("x", "y", "z"))
PLAN_PREVIEW_NAME = "recortes.html"
CROP_PREVIEW_NAME = "recorte.html"


def ply_header(count: int) -> bytes:
    # Fixed-width count lets extraction write batches before the final count is known.
    return (
        f"ply\nformat binary_little_endian 1.0\nelement vertex {count:020d}\n"
        "property double x\nproperty double y\nproperty double z\nend_header\n"
    ).encode("ascii")


def preview_manifest(source: Path) -> Path | None:
    """Find the plan for a directory, its manifest, or one of its PLYs."""
    if source.is_dir():
        return source / "plan.json"
    if source.name == "plan.json":
        return source
    manifest = source.parent.parent / "plan.json"
    if source.name == "cloud.ply" and manifest.is_file():
        return manifest
    return None


def _sample_ply(source: Path, count: int) -> tuple[np.ndarray, int]:
    header = read_ply_header(source)
    if not header.vertex_count:
        raise ValueError("A nuvem do recorte está vazia.")
    if header.format != "binary_little_endian" or header.vertex_properties != XYZ_PROPERTIES:
        raise ValueError("Escolha o PLY XYZ binário gerado pelo planejador.")
    points = np.memmap(
        source, mode="r", dtype="<f8", offset=header.data_offset, shape=(header.vertex_count, 3)
    )
    rows = np.linspace(0, len(points) - 1, min(len(points), count), dtype=np.intp)
    return points[rows], len(points)


def _preview_crops(source: Path, *, single_ply: bool = False):
    manifest = preview_manifest(source)
    if manifest is None:
        return [(source.parent.name, source)], None, {}
    plan = json.loads(manifest.read_text(encoding="utf-8"))
    if single_ply and source.suffix.lower() == ".ply":
        return [(source.parent.name, source)], manifest, plan
    crops = []
    for record in plan["crops"]:
        name = record["crop_id"]
        if not name or Path(name).name != name or name in (".", ".."):
            raise ValueError("Identificador de recorte inválido no manifesto.")
        if record["retained_points"] > 0:
            crops.append((name, manifest.parent / name / "cloud.ply"))
    if not crops:
        raise ValueError("O plano não tem recortes com pontos para visualizar.")
    return crops, manifest, plan


def _crop_config(source: Path) -> dict:
    config = source.with_name("crop.json")
    return json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}


def _outline(spec: dict) -> np.ndarray:
    section = parse_section(spec, np.zeros(3))
    return section.point + section.polygon.vertices @ section.uv_basis.T


def _plan_passages(manifest: Path | None, plan: dict) -> list[Passage]:
    if manifest is None or not plan.get("centreline") or "source_origin_xyz" not in plan:
        return []
    graph = manifest.parent / Path(plan["centreline"]).expanduser()
    try:
        nodes, edges = read_graph(graph)
        return passages_from_graph(nodes - np.asarray(plan["source_origin_xyz"]), edges)
    except (OSError, ValueError, KeyError):
        # Older previews can still open when their graph is on an unavailable drive.
        return []


def _crop_axis(passages: list[Passage], branch: int, stations: list[float]) -> np.ndarray | None:
    if not stations or not 1 <= branch <= len(passages):
        return None
    start, end = stations
    line = passages[branch - 1]
    if not 0 <= start < end <= line.stations[-1] + 1e-6:
        return None
    inside = line.stations[(line.stations > start) & (line.stations < end)]
    return line.at(np.r_[start, inside, end])


def _candidate_traces(figure, passages, reviews):
    import plotly.graph_objects as go

    indices = []
    for has_outline, name, mode in (
        (True, "Contornos candidatos", "lines"),
        (False, "Estações testadas", "markers"),
    ):
        points, labels = [], []
        for review in reviews:
            branch = review["passage"]
            for trial in review["trials"]:
                section = trial.get("section")
                station = trial["station"]
                if bool(section) != has_outline:
                    continue
                if section and review["outcome"] in ("moved", "refit") and station == review["selected_station"]:
                    continue  # Already drawn as a planned cap.
                if section:
                    rim = _outline(section)
                    xyz = [*rim, rim[0], [None, None, None]]
                elif 1 <= branch <= len(passages):
                    xyz = [passages[branch - 1].at(station)]
                else:
                    continue
                status = "contorno completo" if trial["connected_complete"] else "contorno incompleto"
                if not trial["spacing_ok"]:
                    status += " · espaçamento insuficiente"
                label = (
                    f"Ramo {branch:03d} · corte {review['cut']} · {station:.2f} m<br>"
                    f"{trial['connected_bins_supported']}/16 setores · {status}"
                )
                points.extend(xyz)
                labels.extend([label] * len(xyz))
        if points:
            x, y, z = zip(*points)
            indices.append(len(figure.data))
            figure.add_trace(go.Scatter3d(
                x=x, y=y, z=z, text=labels, name=name, mode=mode, visible="legendonly",
                line=dict(color="#8E44AD", dash="dash", width=4),
                marker=dict(color="#8E44AD", size=4, symbol="diamond"),
                hovertemplate="%{text}<extra></extra>",
            ))
    return indices


def _write_preview(
    crops: list[tuple[str, Path]], output: Path, title: str, max_points: int, *, group: bool,
    passages: list[Passage], reviews: list[dict],
) -> Path:
    import plotly.graph_objects as go
    from plotly.colors import qualitative

    if max_points < len(crops):
        raise ValueError("O limite de pontos deve permitir pelo menos um ponto por recorte.")

    figure = go.Figure()
    shown = total = 0
    per_crop, extra = divmod(max_points, len(crops))
    palette = qualitative.Dark24
    cap_traces, axis_traces = [], []
    selected_cuts = set()
    for index, (name, path) in enumerate(crops):
        xyz, available = _sample_ply(path, per_crop + (index < extra))
        shown += len(xyz)
        total += available
        marker = dict(size=2, opacity=0.65, color=palette[index % len(palette)])
        if not group:
            marker.update(color=xyz[:, 2], colorscale="Viridis")
        figure.add_trace(go.Scatter3d(
            x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2], mode="markers",
            marker=marker, name=name,
            hovertemplate="%{fullData.name}<br>X %{x:.2f}<br>Y %{y:.2f}<br>Z %{z:.2f}<extra></extra>",
        ))
        config = _crop_config(path)
        branch = config.get("branch", "").removeprefix("passagem_")
        stations = config.get("proposal", {}).get("cut_stations")
        if branch.isdecimal() and stations:
            branch = int(branch)
            selected_cuts.update((branch, station) for station in stations)
            axis = _crop_axis(passages, branch, stations)
            if axis is not None:
                axis_traces.append(len(figure.data))
                figure.add_trace(go.Scatter3d(
                    x=axis[:, 0], y=axis[:, 1], z=axis[:, 2], mode="lines",
                    name=f"Linha central · {name}", visible="legendonly",
                    line=dict(color="#252934", width=6),
                ))
        for position, spec in zip(("inicial", "final"), config.get("sections", [])):
            if not spec.get("polygon_uv"):
                continue
            outline = _outline(spec)
            cap_traces.append(len(figure.data))
            figure.add_trace(go.Scatter3d(
                x=outline[:, 0], y=outline[:, 1], z=outline[:, 2],
                mode="lines", line=dict(color="#E66100" if position == "inicial" else "#5E3C99", width=6),
                name=f"Tampa {position} · {name}", visible="legendonly",
                hovertemplate="%{fullData.name}<br>X %{x:.2f}<br>Y %{y:.2f}<br>Z %{z:.2f}<extra></extra>",
            ))
    candidate_traces = _candidate_traces(
        figure, passages,
        [review for review in reviews if (review["passage"], review["selected_station"]) in selected_cuts],
    )
    buttons = [
        dict(label=f"{action} {label}", method="restyle", args=[{"visible": visible}, indices])
        for label, indices in (
            ("tampas", cap_traces), ("linha central", axis_traces), ("candidatas", candidate_traces),
        )
        if indices
        for action, visible in (("Mostrar", True), ("Ocultar", "legendonly"))
    ]
    figure.update_layout(
        title=f"{title} · {len(crops)} recorte(s) · {shown:,} de {total:,} pontos",
        showlegend=group or bool(buttons),
        scene=dict(aspectmode="data", xaxis_title="X local", yaxis_title="Y local", zaxis_title="Z local"),
    )
    if buttons:
        figure.update_layout(
            margin=dict(l=176),
            updatemenus=[dict(
                type="buttons", direction="down", x=0, xanchor="right", y=1, yanchor="top",
                pad=dict(r=12), showactive=False, buttons=buttons,
            )],
        )
    with output.open("x", encoding="utf-8") as stream:
        stream.write(figure.to_html(full_html=True, include_plotlyjs=True))
    return output


def write_crop_preview(source: Path, output: Path, *, max_points: int = 60_000) -> Path:
    """Plot all nonempty crops in a plan, or plot a standalone PLY."""
    crops, manifest, plan = _preview_crops(source)
    title = manifest.parent.name if manifest else crops[0][0]
    return _write_preview(
        crops, output, title, max_points, group=manifest is not None,
        passages=_plan_passages(manifest, plan), reviews=plan.get("section_reviews", []),
    )


def write_individual_crop_previews(source: Path, *, max_points: int = 60_000) -> list[Path]:
    """Plot a separate HTML next to each PLY without replacing existing previews."""
    crops, manifest, plan = _preview_crops(source, single_ply=True)
    outputs = [path.with_name(CROP_PREVIEW_NAME) for _, path in crops]
    for output in outputs:
        if output.exists():
            raise FileExistsError(f"Já existe uma prévia individual em {output}.")
    passages = _plan_passages(manifest, plan)
    return [
        _write_preview([(name, path)], output, name, max_points, group=False,
                       passages=passages, reviews=plan.get("section_reviews", []))
        for (name, path), output in zip(crops, outputs)
    ]
