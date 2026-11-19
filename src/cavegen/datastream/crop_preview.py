"""Save and preview the XYZ-only binary PLY used by automatic gallery crops."""

from pathlib import Path

import numpy as np

from cavegen.datastream.ply import read_ply_header
from cavegen.datastream.ply_types import PlyProperty

XYZ_PROPERTIES = tuple(PlyProperty(name, "double") for name in ("x", "y", "z"))


def ply_header(count: int) -> bytes:
    # Fixed-width count lets extraction write batches before the final count is known.
    return (
        f"ply\nformat binary_little_endian 1.0\nelement vertex {count:020d}\n"
        "property double x\nproperty double y\nproperty double z\nend_header\n"
    ).encode("ascii")


def write_crop_preview(source: Path, output: Path, *, max_points: int = 60_000) -> Path:
    """Make a standalone interactive HTML with uniformly spaced PLY rows."""
    import plotly.graph_objects as go

    if max_points < 1:
        raise ValueError("Informe um limite de pontos positivo.")
    header = read_ply_header(source)
    if not header.vertex_count:
        raise ValueError("A nuvem do recorte está vazia.")
    if header.format != "binary_little_endian" or header.vertex_properties != XYZ_PROPERTIES:
        raise ValueError("Escolha o PLY XYZ binário gerado pelo planejador.")
    points = np.memmap(
        source, mode="r", dtype="<f8", offset=header.data_offset, shape=(header.vertex_count, 3)
    )
    rows = np.linspace(0, len(points) - 1, min(len(points), max_points), dtype=np.intp)
    xyz = points[rows]
    figure = go.Figure(go.Scatter3d(
        x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2], mode="markers",
        marker=dict(size=2, opacity=0.65, color=xyz[:, 2], colorscale="Viridis"),
        name="Superfície observada",
    ))
    figure.update_layout(
        title=f"{source.parent.name} · {len(xyz):,} de {len(points):,} pontos",
        scene=dict(aspectmode="data", xaxis_title="X local", yaxis_title="Y local", zaxis_title="Z local"),
    )
    with output.open("x", encoding="utf-8") as stream:
        stream.write(figure.to_html(full_html=True, include_plotlyjs=True))
    return output
