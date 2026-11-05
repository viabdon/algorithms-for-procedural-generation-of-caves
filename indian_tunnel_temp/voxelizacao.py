"""
    Voxeliza a superfície do Indian Tunnel (NASA) numa grade cúbica (depth, height, width).

    O .f32 é uma nuvem de pontos da superfície do tubo de lava: 7 float32 por
    ponto (x, y, z, NIR, R, G, B), lidos aos lotes por memmap. Igual ao
    Elaphes, cada voxel com algum ponto vira superfície (1); o vazio da
    caverna só sai depois, na inundação.

    Etapas:
    1. Limites globais da nuvem inteira, gravados em data/params para não
       reler os 3 GB a cada rodada.
    2. Giro (x, y, z) -> (x, z, -y): aqui o z é a vertical (15 m de extensão,
       contra 76 e 170 m), e a normalização manda o 2º eixo para o height.
       Assim a altura fica no height como no Elaphes, e o giro é uma rotação
       de 90° em torno do x (sem espelhar a caverna).
    3. Normalização com escala única e centralizada (a mesma do Elaphes) e
       marcação dos voxels.
    4. Só a maior componente (vizinhança de 26) fica: o resto é ponto solto
       longe do túnel, como o outlier que foi zerado à mão no Elaphes.

    uv run python indian_tunnel_temp/voxelizacao.py [lado]
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.ndimage import label

from cavegen.core.normalization import normalize_xyz_to_zyx_indices
from cavegen.core.voxelization import voxelize_surface_zyx
from cavegen.datastream.bounds import calculate_xyz_bounds
from cavegen.datastream.f32 import count_f32_points, iter_f32_xyz
from cavegen.datastream.surface_io import save_surface_npz

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
PASTA_NPZ = PASTA / "npz"
PASTA_PLOTS = PASTA / "plots"

F32 = RAIZ / "data" / "raw" / "nasa" / "indian_tunnel.f32"
LIMITES = RAIZ / "data" / "params" / "indian_tunnel_xyz_bounds.json"

LADO_PADRAO = 64
LOTE = 4_000_000

def girar(xyz: np.ndarray) -> np.ndarray:
    """
        (x, y, z) -> (x, z, -y): leva a vertical (z) para o eixo que vira height.
        xyz: array (n, 3) nos eixos da nuvem.
    """
    return np.stack([xyz[:, 0], xyz[:, 2], -xyz[:, 1]], axis=1)

def limites_girados(minimo: np.ndarray, maximo: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
        Limites depois do giro: o -y troca mínimo e máximo de lugar.
        minimo, maximo: limites (x, y, z) da nuvem.
    """
    return (np.array([minimo[0], minimo[2], -maximo[1]], dtype=np.float32),
            np.array([maximo[0], maximo[2], -minimo[1]], dtype=np.float32))

def sha256(caminho: Path) -> str:
    """
        Hash do arquivo inteiro, para o JSON dizer de qual nuvem saíram os limites.
        caminho: arquivo lido aos pedaços.
    """
    h = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while bloco := arquivo.read(1 << 24):
            h.update(bloco)
    return h.hexdigest()

def carregar_limites() -> tuple[np.ndarray, np.ndarray]:
    """
        Limites (x, y, z) da nuvem: lê o JSON, ou calcula e grava na primeira vez.
        O JSON segue o formato do elaphes_xyz_bounds.json.
    """
    if LIMITES.exists():
        dados = json.loads(LIMITES.read_text(encoding="utf-8"))
        return (np.array(dados["min_xyz"], dtype=np.float32),
                np.array(dados["max_xyz"], dtype=np.float32))

    inicio = perf_counter()
    minimo, maximo = calculate_xyz_bounds(iter_f32_xyz(F32, LOTE))
    segundos = perf_counter() - inicio
    dados = {
        "dataset": "NASA Indian Tunnel",
        "source": {
            "path": F32.relative_to(RAIZ).as_posix(),
            "original_name": "IndianTunnel_full_1x.f32",
            "format": "f32 (x, y, z, nir, r, g, b)",
            "sha256": sha256(F32),
            "size_bytes": F32.stat().st_size,
            "vertex_count": count_f32_points(F32),
        },
        "calculation": {
            "function": "cavegen.datastream.bounds.calculate_xyz_bounds",
            "iterator": "cavegen.datastream.f32.iter_f32_xyz",
            "batch_size": LOTE,
            "coordinate_dtype": "float32",
            "elapsed_seconds": round(segundos, 6),
            "completed_on": date.today().isoformat(),
        },
        "min_xyz": [round(float(v), 6) for v in minimo],
        "max_xyz": [round(float(v), 6) for v in maximo],
        "representation": "surface_point_cloud",
        "normalization_note": ("These bounds apply to scanned surface coordinates. "
                               "They do not define a void volume. z is the vertical axis."),
    }
    LIMITES.write_text(json.dumps(dados, indent=2) + "\n", encoding="utf-8")
    return minimo, maximo

def voxelizar(lado: int, minimo: np.ndarray, maximo: np.ndarray) -> np.ndarray:
    """
        Grade lado³ com 1 onde algum ponto da nuvem cai.
        lado: lado da grade.
        minimo, maximo: limites (x, y, z) da nuvem.
    """
    minimo_g, maximo_g = limites_girados(minimo, maximo)
    forma = (lado, lado, lado)
    lotes = (normalize_xyz_to_zyx_indices(girar(lote), minimo_g, maximo_g, forma)
             for lote in iter_f32_xyz(F32, LOTE))
    return voxelize_surface_zyx(lotes, forma)

def maior_componente(superficie: np.ndarray) -> tuple[np.ndarray, int]:
    """
        Devolve (só a maior componente, quantos voxels saíram).
        superficie: grade booleana da superfície.
    """
    rotulos, quantidade = label(superficie, structure=np.ones((3, 3, 3)))
    if quantidade <= 1:
        return superficie, 0
    tamanhos = np.bincount(rotulos.ravel())[1:]
    limpa = rotulos == int(np.argmax(tamanhos)) + 1
    return limpa, int(superficie.sum() - limpa.sum())

def caminho_superficie(lado: int) -> Path:
    """
        Arquivo da superfície voxelizada.
        lado: lado da grade.
    """
    return PASTA_NPZ / f"indian_tunnel_surface_{lado}.npz"

def main():
    lado = int(sys.argv[1]) if len(sys.argv) > 1 else LADO_PADRAO
    PASTA_NPZ.mkdir(exist_ok=True)

    minimo, maximo = carregar_limites()
    inicio = perf_counter()
    superficie, removidos = maior_componente(voxelizar(lado, minimo, maximo))

    saida = caminho_superficie(lado)
    save_surface_npz(superficie, saida, {
        "kind": "surface_voxels",
        "semantic": "true_means_observed_surface",
        "source_f32": F32.relative_to(RAIZ).as_posix(),
        "bounds_path": LIMITES.relative_to(RAIZ).as_posix(),
        "min_xyz": minimo.tolist(),
        "max_xyz": maximo.tolist(),
        "volume_shape_zyx": [lado] * 3,
        "normalization": {
            "source_coordinate_order": "XYZ",
            "rotation": "(x, y, z) -> (x, z, -y), z vertical vira height",
            "grid_index_order": "ZYX",
            "shared_scale_preserves_proportions": True,
            "symmetric_padding": True,
        },
        "largest_component_only": True,
        "removed_voxels": removidos,
    })

    ocupados = np.nonzero(superficie)
    faixas = [f"{int(eixo.min())}-{int(eixo.max())}" for eixo in ocupados]
    print(f"superfície: {int(superficie.sum())} voxels ({removidos} soltos removidos), "
          f"faixas depth/height/width {faixas}, {perf_counter() - inicio:.1f} s -> {saida.name}")

if __name__ == "__main__":
    main()
