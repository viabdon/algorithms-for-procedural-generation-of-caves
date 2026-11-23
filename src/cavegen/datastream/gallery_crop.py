"""Voxelize one manually reviewed gallery crop on the CPU."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from matplotlib.path import Path as PolygonPath
import numpy as np
from scipy.ndimage import generate_binary_structure, label

from cavegen.core.surface_filling import INTERIOR, classify_surface_by_flood_fill
from cavegen.core.volume import Volume3D
from cavegen.datastream.point_cloud import iter_point_cloud_xyz
from cavegen.datastream.progress import report_point_progress
from cavegen.datastream.surface_io import load_surface_npz, save_surface_npz
from cavegen.datastream.voxel_io import load_volume_npz, save_volume_npz

CROP_FORMATS = frozenset({".xyz", ".ply", ".f32", ".las"})


@dataclass(frozen=True)
class Section:
    point: np.ndarray
    normal: np.ndarray
    uv_basis: np.ndarray
    polygon: PolygonPath


@dataclass(frozen=True)
class GalleryCrop:
    config: dict
    source: Path
    destination: Path
    partition: str
    origin_xyz: np.ndarray
    shape_zyx: tuple[int, int, int]
    voxel_size: float
    selection_min_local: np.ndarray
    selection_max_local: np.ndarray
    sections: tuple[Section, Section]
    seed_zyx: tuple[int, int, int]

    @property
    def extent_xyz(self) -> np.ndarray:
        return np.asarray(self.shape_zyx[::-1]) * self.voxel_size


def _vector(value, field: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError(f"{field} precisa de três coordenadas finitas.")
    return result


def parse_section(config: dict, origin: np.ndarray) -> Section:
    """Build the plane basis and UV polygon used for caps and their previews."""
    if not isinstance(config, dict):
        raise ValueError("Cada seção deve ser um objeto JSON.")
    point = _vector(config.get("point_xyz"), "point_xyz") - origin
    normal = _vector(config.get("inward_normal_xyz"), "inward_normal_xyz")
    norm = np.linalg.norm(normal)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("A normal do plano deve ser não nula e normalizável.")
    normal = normal / norm

    u = _vector(config.get("u_xyz"), "u_xyz")
    u = u - (u @ normal) * normal
    norm = np.linalg.norm(u)
    if not np.isfinite(norm) or norm <= 1e-12:
        raise ValueError("u_xyz deve definir uma direção no plano.")
    u = u / norm
    # V completa a base ortonormal do plano. A ordem N × U fixa o sinal de V.
    v = np.cross(normal, u)
    uv_basis = np.column_stack((u, v))

    polygon = np.asarray(config.get("polygon_uv"), dtype=np.float64)
    if (
        polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3
        or not np.isfinite(polygon).all()
        or np.linalg.matrix_rank(polygon - polygon[0]) < 2
    ):
        raise ValueError("Informe um polígono UV finito e com área.")
    return Section(point, normal, uv_basis, PolygonPath(np.vstack((polygon, polygon[0])), closed=True))


def prepare_crop(path: Path, *, repository: Path = Path(".")) -> GalleryCrop:
    """Read and validate a crop JSON without reading cloud points."""
    with path.open(encoding="utf-8") as stream:
        spec = json.load(stream)
    if not isinstance(spec, dict):
        raise ValueError("A configuração de recorte deve ser um objeto JSON.")
    for key in ("cave", "survey", "crop_id", "fold"):
        value = spec.get(key)
        if not isinstance(value, str) or not value.strip() or Path(value).name != value or value in (".", ".."):
            raise ValueError(f"Informe {key} como identificador simples.")
    for key in ("source", "units", "branch"):
        value = spec.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Informe {key}.")
    source = (path.parent / Path(spec["source"]).expanduser()).resolve()
    if not source.is_file() or source.suffix.lower() not in CROP_FORMATS:
        raise ValueError(f"Esperado arquivo XYZ, LAS, PLY ou F32 existente: {source}")

    lo = _vector(spec.get("selection_min_xyz"), "selection_min_xyz")
    hi = _vector(spec.get("selection_max_xyz"), "selection_max_xyz")
    origin = _vector(spec.get("origin_xyz"), "origin_xyz")
    shape = spec.get("shape_zyx")
    size = spec.get("voxel_size")
    tolerance = spec.setdefault("plane_tolerance", 1e-8)
    if (
        not isinstance(shape, list) or len(shape) != 3
        or any(type(n) is not int or n < 3 for n in shape)
        or type(size) not in (int, float) or not np.isfinite(size) or size <= 0
        or type(tolerance) not in (int, float) or not 0 <= tolerance < size / 10
        or np.any(lo >= hi)
    ):
        raise ValueError("Revise shape_zyx, voxel_size, plane_tolerance e caixa de seleção.")
    extent = np.asarray(shape[::-1]) * size
    if not np.isfinite(extent).all():
        raise ValueError("O domínio XYZ da grade deve ser finito.")
    batch_size = spec.setdefault("batch_size", 65536)
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size deve ser um inteiro positivo.")
    progress_every = spec.setdefault("progress_every", 1000000)
    if type(progress_every) is not int or progress_every < 0:
        raise ValueError("progress_every deve ser um inteiro não negativo.")

    sections = spec.get("sections")
    if not isinstance(sections, list) or len(sections) != 2:
        raise ValueError("Informe as duas seções revisadas.")
    start, end = (parse_section(section, origin) for section in sections)
    seed = _vector(spec.get("seed_xyz"), "seed_xyz") - origin
    if np.any(seed < lo - origin) or np.any(seed >= hi - origin) or np.any(seed < 0) or np.any(seed >= extent):
        raise ValueError("A semente deve estar dentro da caixa e da grade.")
    if any((seed - section.point) @ section.normal <= tolerance for section in (start, end)):
        raise ValueError("A semente deve estar no lado interno dos dois planos.")

    split_path = repository / "docs/auditoria/gan/splits.json"
    folds = json.loads(split_path.read_text(encoding="utf-8"))["folds"]
    partition = next(
        (fold["groups"].get(spec["cave"]) for fold in folds if fold["id"] == spec["fold"]),
        None,
    )
    if partition not in ("train", "validation", "test"):
        raise ValueError("Caverna ou fold ausente no inventário de partições.")

    resolution = "x".join(map(str, shape))
    destination = repository / "data/processed/reference_sections" / spec["cave"] / spec["survey"]
    if "plan_id" in spec:
        plan_id = spec["plan_id"]
        if (
            not isinstance(plan_id, str) or not plan_id.strip()
            or plan_id in (".", "..") or "/" in plan_id or "\\" in plan_id
        ):
            raise ValueError("Informe plan_id como identificador simples.")
        destination = destination / spec["fold"] / plan_id
    destination = destination / spec["crop_id"] / resolution
    seed_zyx = tuple(int(i) for i in np.floor(seed[::-1] / size))
    return GalleryCrop(
        config=spec,
        source=source,
        destination=destination,
        partition=partition,
        origin_xyz=origin,
        shape_zyx=tuple(shape),
        voxel_size=float(size),
        selection_min_local=lo - origin,
        selection_max_local=hi - origin,
        sections=(start, end),
        seed_zyx=seed_zyx,
    )


def _rasterize_surface(
    crop: GalleryCrop, batches: Iterable[np.ndarray]
) -> tuple[np.ndarray, dict[str, int]]:
    surface = np.zeros(crop.shape_zyx, dtype=bool)
    counts = dict(read=0, candidate=0, retained=0, outside_grid=0)
    lo, hi = crop.selection_min_local, crop.selection_max_local
    extent = crop.extent_xyz
    tolerance = crop.config["plane_tolerance"]
    for xyz in batches:
        counts["read"] += len(xyz)
        candidate = xyz[np.all((xyz >= lo) & (xyz < hi), axis=1)]
        counts["candidate"] += len(candidate)
        for section in crop.sections:
            distance = (candidate - section.point) @ section.normal
            candidate = candidate[distance >= -tolerance]
        counts["retained"] += len(candidate)
        inside = np.all((candidate >= 0) & (candidate < extent), axis=1)
        counts["outside_grid"] += int(np.count_nonzero(~inside))
        indices = np.floor(candidate[inside] / crop.voxel_size).astype(np.intp)
        surface[tuple(indices[:, ::-1].T)] = True
    return surface, counts


def _rasterize_caps(crop: GalleryCrop) -> np.ndarray:
    # Trabalhar por fatia limita a memória das coordenadas temporárias.
    y, x = np.indices(crop.shape_zyx[1:])
    caps = np.zeros((2, *crop.shape_zyx), dtype=bool)
    tolerance = crop.config["plane_tolerance"]
    for z in range(crop.shape_zyx[0]):
        xyz = np.column_stack((x.ravel(), y.ravel(), np.full(x.size, z)))
        centers = (xyz + 0.5) * crop.voxel_size
        for i, section in enumerate(crop.sections):
            relative = centers - section.point
            half_width = crop.voxel_size / 2 * np.abs(section.normal).sum() + tolerance
            near = np.abs(relative @ section.normal) <= half_width
            uv = relative[near] @ section.uv_basis
            caps[i, z].ravel()[near] = section.polygon.contains_points(uv, radius=tolerance)
    return caps


def _infer_air(surface: np.ndarray, caps: np.ndarray, seed_zyx: tuple[int, int, int]) -> np.ndarray:
    barrier = surface | caps.any(axis=0)
    if any(np.take(barrier, (0, -1), axis=axis).any() for axis in range(3)):
        raise ValueError("Parede ou tampa toca a borda da grade. Revise a margem.")
    if any(not (cap & surface).any() for cap in caps):
        raise ValueError("Uma tampa ficou vazia ou sem contato voxelizado com a parede.")
    enclosed = classify_surface_by_flood_fill(barrier) == INTERIOR
    components, _ = label(enclosed, structure=generate_binary_structure(3, 1))
    seed_label = components[seed_zyx]
    if not seed_label:
        raise ValueError("A semente caiu na barreira ou ficou conectada ao exterior.")
    return components == seed_label


def process_crop(crop: GalleryCrop, *, progress: Callable[[int], None] | None = None) -> dict:
    """Stream points, infer candidate air, and publish the four outputs together."""
    target = crop.destination
    if target.exists():
        raise FileExistsError(f"Já existe uma execução em {target}.")
    before = crop.source.stat()
    batches = iter_point_cloud_xyz(crop.source, crop.config["batch_size"], origin_xyz=crop.origin_xyz)
    if progress is not None and crop.config["progress_every"]:
        batches = report_point_progress(batches, crop.config["progress_every"], progress)
    surface, counts = _rasterize_surface(crop, batches)
    after = crop.source.stat()
    if (
        before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev
    ) != (after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev):
        raise ValueError("A fonte mudou durante a leitura.")
    if not surface.any() or counts["outside_grid"]:
        raise ValueError(f"Recorte vazio ou com pontos selecionados fora da grade. Contagens: {counts}")

    caps = _rasterize_caps(crop)
    air = _infer_air(surface, caps, crop.seed_zyx)
    air_voxels = int(air.sum())
    record = {
        "config": crop.config,
        "partition": crop.partition,
        "source_path": str(crop.source),
        "source_size_bytes": before.st_size,
        "source_mtime_ns": before.st_mtime_ns,
        "method": "reviewed_planar_caps_exterior_flood_fill_6",
        "status": "pending_review",
        "counts": counts,
        "axis_order": "ZYX",
        "seed_zyx": list(crop.seed_zyx),
        "surface_voxels": int(surface.sum()),
        "cap_voxels": [int(cap.sum()) for cap in caps],
        "air_voxels": air_voxels,
        "candidate_volume": air_voxels * crop.voxel_size**3,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as staging:
        folder = Path(staging)
        save_surface_npz(surface, folder / "surface.npz", record)
        np.savez_compressed(folder / "masks.npz", caps=caps)
        save_volume_npz(Volume3D(air, metadata=record), folder / "interior.npz")
        (folder / "run.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.rename(folder, target)
    return record


def inspect_crop(folder: Path) -> tuple[Path, Path]:
    """Export Plotly HTMLs for the seed slices and the voxel layers."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    surface, _ = load_surface_npz(folder / "surface.npz")
    interior = load_volume_npz(folder / "interior.npz")
    classes = np.zeros(surface.shape, dtype=np.uint8)
    classes[surface] = 1
    with np.load(folder / "masks.npz", allow_pickle=False) as masks:
        caps = masks["caps"].any(axis=0)
    classes[caps] = 2
    classes[interior.data] = 3

    labels = np.array(["Exterior ou vazio não selecionado", "Parede", "Tampa", "Ar candidato"])
    colors = ["black", "white", "orange", "deepskyblue"]
    colorscale = [
        (edge / len(colors), color)
        for i, color in enumerate(colors)
        for edge in (i, i + 1)
    ]
    seed = interior.metadata["seed_zyx"]
    planes = ("XY", "XZ", "YZ")
    perpendicular_axes = "ZYX"
    figure = make_subplots(
        rows=1, cols=3,
        subplot_titles=[
            f"{plane} · {fixed} = {index}"
            for plane, fixed, index in zip(planes, perpendicular_axes, seed)
        ],
    )
    for axis, (index, (x_axis, y_axis)) in enumerate(zip(seed, planes)):
        column = axis + 1
        voxels = classes.take(index, axis=axis)
        figure.add_trace(go.Heatmap(
            z=voxels, customdata=labels[voxels], coloraxis="coloraxis",
            hovertemplate=f"{x_axis} %{{x}} · {y_axis} %{{y}}<br>%{{customdata}}<extra></extra>",
        ), row=1, col=column)
        figure.update_xaxes(title_text=f"{x_axis} (voxel)", constrain="domain", row=1, col=column)
        figure.update_yaxes(
            title_text=f"{y_axis} (voxel)", scaleanchor="x" if column == 1 else f"x{column}",
            scaleratio=1, constrain="domain", row=1, col=column,
        )
    crop_id = interior.metadata.get("config", {}).get("crop_id", folder.parent.name)
    figure.update_layout(
        title=f"{crop_id} · fatias pela semente",
        template="plotly_white",
        height=450,
        coloraxis=dict(
            cmin=-0.5, cmax=len(labels) - 0.5, colorscale=colorscale,
            colorbar=dict(tickvals=list(range(len(labels))), ticktext=labels.tolist()),
        ),
    )
    slices = folder / "fatias_plotly.html"
    figure.write_html(slices, include_plotlyjs=True)

    spatial = go.Figure()
    layers = [
        ("Superfície observada", surface, "#526478", 0.3, True),
        ("Ar candidato", interior.data, "#0284C7", 0.7, True),
        ("Tampas", caps, "#EA580C", 0.9, "legendonly"),
    ]
    for name, mask, color, opacity, visible in layers:
        z, y, x = mask.nonzero()
        spatial.add_trace(go.Scatter3d(
            x=x, y=y, z=z, mode="markers", name=name, visible=visible,
            marker=dict(size=3, color=color, opacity=opacity),
            hovertemplate=f"{name}<br>X %{{x}} · Y %{{y}} · Z %{{z}}<extra></extra>",
        ))
    spatial.update_layout(
        title=f"{crop_id} · camadas de voxels",
        template="plotly_white",
        legend=dict(title_text="Camadas"),
        scene=dict(
            aspectmode="data",
            xaxis_title="X (voxel)", yaxis_title="Y (voxel)", zaxis_title="Z (voxel)",
        ),
    )
    volume = folder / "volume_plotly.html"
    spatial.write_html(volume, include_plotlyjs=True)
    return slices, volume
