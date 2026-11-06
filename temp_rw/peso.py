"""
    Transforma um resultado voxelizado do experimento em peso do CA.

    Usa as mesmas funções do SDF do Elaphes e do RW do pacote (sdf_temp/sdf.py):
    binariza a borda, mede a distância euclidiana exata até ela e volta com o
    sinal (interno positivo, externo negativo, borda 0). Depois entrega o npz ao
    importar_sdf do CA, que grava o peso e, se pedido, comprime com o logaritmo.

    Como no RW do pacote, aqui o interno é o miolo do túnel, o vazio de verdade
    da caverna, e não a espessura da parede, como no Elaphes.

    uv run python temp_rw/peso.py <resultado> [escala_log]
"""
import sys
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.pesos import PESOS_DIR, importar_sdf, load_peso_info
from results import RESULTS_DIR, load_result

# As funções do SDF ficam no sdf_temp; o inundacao.py de lá precisa estar no caminho também.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sdf_temp"))
from sdf import CONVENCAO, INTERNO, aplicar_sinal, binarizar_borda, distancia_ate_borda

PASTA_NPZ = Path(__file__).resolve().parent / "npz"

def calcular_sdf(classificacao: np.ndarray) -> np.ndarray:
    """
        SDF de uma grade classificada: interno positivo, externo negativo, borda 0.
        classificacao: matriz com 0 fora, 1 borda e 2 interno.
    """
    borda = binarizar_borda(classificacao)
    return aplicar_sinal(distancia_ate_borda(borda), classificacao == INTERNO)

def gravar_sdf(result_id: int, directory: Path = RESULTS_DIR, saida: Path = PASTA_NPZ) -> Path:
    """
        Calcula o SDF de um resultado e grava no formato que importar_sdf lê.
        result_id: número do resultado do experimento.
        directory: pasta dos resultados do experimento.
        saida: pasta onde o npz do SDF é gravado.
    """
    dados = load_result(result_id, directory)
    destino = Path(saida) / f"result_{result_id:03d}_sdf.npz"
    destino.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destino,
        sdf=calcular_sdf(dados["classificacao"]),
        convencao=CONVENCAO,
        seed=dados["seed"],
        result_id=result_id,
    )
    return destino

def gerar_peso(result_id: int, escala_log: float | None = None, directory: Path = RESULTS_DIR,
               saida: Path = PASTA_NPZ, pesos: Path = PESOS_DIR) -> Path:
    """
        Do resultado ao peso do CA, e devolve o caminho do peso gravado.
        result_id: número do resultado do experimento.
        escala_log: escala do logaritmo; None usa o SDF sem transformar.
        directory: pasta dos resultados do experimento.
        saida: pasta onde o npz do SDF é gravado.
        pesos: pasta dos pesos do CA.
    """
    return importar_sdf(gravar_sdf(result_id, directory, saida), pesos, escala_log=escala_log)

def main():
    if len(sys.argv) < 2:
        raise SystemExit("informe o numero do resultado, ex: python temp_rw/peso.py 1 2")

    escala_log = float(sys.argv[2]) if len(sys.argv) > 2 else None
    destino = gerar_peso(int(sys.argv[1]), escala_log)
    info = load_peso_info(int(destino.stem[-3:]))
    print(f"peso gravado: {destino}")
    print(f"origem: {info['origem']}, formato {info['shape']}, escala do log: {info['escala_log']}")

if __name__ == "__main__":
    main()
