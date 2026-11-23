"""Show local voxel bins, an escape route and sampled points from a leak report."""

from pathlib import Path
import csv
import json

import numpy as np

from cavegen.datastream.gallery_reports import PREVIEW_FILE


def write_leak_preview(report_path: Path) -> Path:
    """Export local orthogonal slices with individually toggleable evidence layers."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if report_path.suffix == ".json":
        report = json.loads(report_path.read_text(encoding="utf-8"))
        focus = report["focus"]
        output = report_path.with_suffix(".html")
    else:
        with report_path.open(encoding="utf-8", newline="") as stream:
            report = next(csv.DictReader(stream))
        with np.load(report_path.with_name(PREVIEW_FILE), allow_pickle=False) as arrays:
            focus = dict(arrays)
        output = report_path.with_name("leak_diagnostics.html")
    center = np.array(focus["voxel_zyx"])
    lower = np.array(focus["min_zyx"])
    surface = np.asarray(focus["surface"])
    classes = np.zeros(surface.shape, dtype=np.uint8)
    classes[surface] = 1
    classes[np.asarray(focus["caps"])] = 2
    classes[np.asarray(focus["repair"])] = 3
    labels = np.array(["Bin livre", "Superfície observada", "Tampa definitiva", "Reparo local"])
    colors = ["#202B39", "#DDE6EC", "#EA580C", "#A855F7"]
    colorscale = [(edge / len(colors), color) for i, color in enumerate(colors) for edge in (i, i + 1)]

    planes = [(0, 2, 1), (1, 2, 0), (2, 1, 0)]
    figure = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.09,
        subplot_titles=[f"{'ZYX'[a]} = {center[a]}" for a, _, _ in planes],
    )
    escape = np.argwhere(focus["escape"]) + lower
    evidence = (
        ("Caminho de fuga", escape, "#3ED6FF", "x"),
        ("Pontos do recorte", np.asarray(focus["crop_sample_zyx"]).reshape(-1, 3), "#14B8A6", "circle"),
        ("Pontos da nuvem original", np.asarray(focus["raw_sample_zyx"]).reshape(-1, 3), "#EAB308", "circle-open"),
    )
    for column, (axis, x_axis, y_axis) in enumerate(planes, 1):
        z = classes.take(center[axis] - lower[axis], axis=axis)
        x = lower[x_axis] + np.arange(z.shape[1])
        y = lower[y_axis] + np.arange(z.shape[0])
        figure.add_trace(go.Heatmap(
            x=x, y=y, z=z, customdata=labels[z], coloraxis="coloraxis",
            hovertemplate="%{customdata}<extra></extra>",
        ), row=1, col=column)
        for name, points, color, symbol in evidence:
            if not len(points):
                continue
            selected = points[np.floor(points[:, axis] + 0.5) == center[axis]]
            figure.add_trace(go.Scatter(
                x=selected[:, x_axis], y=selected[:, y_axis],
                mode="markers", marker=dict(color=color, symbol=symbol, size=6),
                name=name, legendgroup=name, showlegend=column == 1,
                visible=True if name == "Caminho de fuga" else "legendonly",
            ), row=1, col=column)
        figure.update_xaxes(
            title_text=f"{'ZYX'[x_axis]} (voxel)", constrain="domain", row=1, col=column,
        )
        figure.update_yaxes(
            title_text=f"{'ZYX'[y_axis]} (voxel)", scaleanchor="x" if column == 1 else f"x{column}",
            scaleratio=1, constrain="domain", row=1, col=column,
        )
    figure.update_layout(
        title=f"{report['crop_id']} · vizinhança do voxel ZYX {center.tolist()}",
        template="plotly_white", height=500, legend=dict(orientation="h", y=-0.2),
        coloraxis=dict(
            cmin=-0.5, cmax=3.5, colorscale=colorscale,
            colorbar=dict(tickvals=list(range(len(labels))), ticktext=labels.tolist()),
        ),
    )
    figure.write_html(output, include_plotlyjs=True)
    return output
