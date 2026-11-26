"""Save and preview the XYZ-only binary PLY used by automatic gallery crops."""

import json
from pathlib import Path

import numpy as np

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


def _preview_crops(source: Path) -> tuple[list[tuple[str, Path]], Path | None]:
    manifest = preview_manifest(source)
    if manifest is None:
        return [(source.parent.name, source)], None
    plan = json.loads(manifest.read_text(encoding="utf-8"))
    crops = []
    for record in plan["crops"]:
        name = record["crop_id"]
        if not name or Path(name).name != name or name in (".", ".."):
            raise ValueError("Identificador de recorte inválido no manifesto.")
        if record["retained_points"] > 0:
            crops.append((name, manifest.parent / name / "cloud.ply"))
    if not crops:
        raise ValueError("O plano não tem recortes com pontos para visualizar.")
    return crops, manifest


def _cap_outlines(source: Path):
    config = source.with_name("crop.json")
    if not config.is_file():
        return
    sections = json.loads(config.read_text(encoding="utf-8")).get("sections", [])
    for position, spec in zip(("inicial", "final"), sections):
        if not spec.get("polygon_uv"):
            continue
        section = parse_section(spec, np.zeros(3))
        vertices = section.point + section.polygon.vertices @ section.uv_basis.T
        yield position, vertices


def _write_preview(
    crops: list[tuple[str, Path]], output: Path, title: str, max_points: int, *, group: bool
) -> Path:
    import plotly.graph_objects as go
    from plotly.colors import qualitative

    if max_points < len(crops):
        raise ValueError("O limite de pontos deve permitir pelo menos um ponto por recorte.")

    figure = go.Figure()
    shown = total = 0
    per_crop, extra = divmod(max_points, len(crops))
    palette = qualitative.Dark24
    cap_traces = []
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
        for position, outline in _cap_outlines(path):
            cap_traces.append(len(figure.data))
            figure.add_trace(go.Scatter3d(
                x=outline[:, 0], y=outline[:, 1], z=outline[:, 2],
                mode="lines", line=dict(color="#E66100" if position == "inicial" else "#5E3C99", width=6),
                name=f"Tampa {position} · {name}", visible="legendonly",
                hovertemplate="%{fullData.name}<br>X %{x:.2f}<br>Y %{y:.2f}<br>Z %{z:.2f}<extra></extra>",
            ))
    figure.update_layout(
        title=f"{title} · {len(crops)} recorte(s) · {shown:,} de {total:,} pontos",
        showlegend=group or bool(cap_traces),
        scene=dict(aspectmode="data", xaxis_title="X local", yaxis_title="Y local", zaxis_title="Z local"),
    )
    if cap_traces:
        figure.update_layout(updatemenus=[dict(
            type="buttons", direction="right", x=0, y=1.06, showactive=False,
            buttons=[
                dict(label="Mostrar tampas", method="restyle", args=[{"visible": True}, cap_traces]),
                dict(label="Ocultar tampas", method="restyle", args=[{"visible": "legendonly"}, cap_traces]),
            ],
        )])
    with output.open("x", encoding="utf-8") as stream:
        stream.write(figure.to_html(full_html=True, include_plotlyjs=True))
    return output


def write_crop_preview(source: Path, output: Path, *, max_points: int = 60_000) -> Path:
    """Plot all nonempty crops in a plan, or plot a standalone PLY."""
    crops, manifest = _preview_crops(source)
    title = manifest.parent.name if manifest else crops[0][0]
    return _write_preview(crops, output, title, max_points, group=manifest is not None)


def write_individual_crop_previews(source: Path, *, max_points: int = 60_000) -> list[Path]:
    """Plot a separate HTML next to each PLY without replacing existing previews."""
    crops, _ = _preview_crops(source)
    outputs = [path.with_name(CROP_PREVIEW_NAME) for _, path in crops]
    for output in outputs:
        if output.exists():
            raise FileExistsError(f"Já existe uma prévia individual em {output}.")
    return [
        _write_preview([(name, path)], output, name, max_points, group=False)
        for (name, path), output in zip(crops, outputs)
    ]
