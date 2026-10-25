"""Garante o contrato do peso somado à contagem de vizinhos do CA.

O peso (o SDF, por exemplo) entra posição por posição na contagem, antes da
comparação com a sensibilidade. O CA sem peso é o baseline da comparação
CA x CA+SDF, então o primeiro contrato é que ele não muda: sem peso e com peso
zero o resultado tem de ser o mesmo do autômato básico, bit a bit.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.generator import (
    BorderTreatment,
    aplicar_peso,
    cellular_automata,
    iterate,
    neighbor_counts,
)
from cavegen.generators.cellular_automata.pesos import (
    importar_sdf,
    load_peso_info,
    load_peso_matrix,
    used_peso_ids,
)


def matriz_aleatoria(formato: tuple[int, int, int], seed: int) -> np.ndarray:
    """Matriz binária reprodutível com cerca de metade das células vivas."""
    return np.random.default_rng(seed).integers(0, 2, size=formato)


class PesoTests(unittest.TestCase):
    def test_peso_zero_reproduz_o_ca_basico(self) -> None:
        inicial = matriz_aleatoria((9, 10, 11), seed=1)
        zeros = np.zeros(inicial.shape, dtype=np.float32)

        for borda in (BorderTreatment.ZEROS, BorderTreatment.ONES):
            basico, historico_basico = cellular_automata(inicial, 14, borda, 4)
            com_peso, historico_peso = cellular_automata(inicial, 14, borda, 4, peso=zeros)
            np.testing.assert_array_equal(com_peso, basico)
            np.testing.assert_array_equal(historico_peso, historico_basico)

    def test_passo_compara_a_contagem_somada_ao_peso(self) -> None:
        matriz = matriz_aleatoria((8, 8, 8), seed=2)
        peso = np.random.default_rng(3).uniform(-5, 2, size=matriz.shape).astype(np.float32)
        esperado = (neighbor_counts(matriz, BorderTreatment.ZEROS) + peso >= 12).astype(int)

        np.testing.assert_array_equal(iterate(matriz, 12, BorderTreatment.ZEROS, peso), esperado)

    def test_peso_negativo_impede_a_celula_de_virar_1(self) -> None:
        # Tudo vivo: cada célula do miolo tem os 27 vizinhos, mais que a sensibilidade.
        matriz = np.ones((5, 5, 5), dtype=int)
        peso = np.zeros(matriz.shape, dtype=np.float32)
        peso[2, 2, 2] = -27

        saida = iterate(matriz, 14, BorderTreatment.ONES, peso)

        self.assertEqual(saida[2, 2, 2], 0)
        self.assertEqual(int(saida.sum()), matriz.size - 1)

    def test_peso_positivo_faz_a_celula_virar_1_sem_vizinhos(self) -> None:
        matriz = np.zeros((5, 5, 5), dtype=int)
        peso = np.zeros(matriz.shape, dtype=np.float32)
        peso[2, 2, 2] = 14

        saida = iterate(matriz, 14, BorderTreatment.ZEROS, peso)

        self.assertEqual(saida[2, 2, 2], 1)
        self.assertEqual(int(saida.sum()), 1)

    def test_peso_com_formato_diferente_falha(self) -> None:
        vizinhos = np.zeros((4, 4, 4), dtype=np.int16)

        with self.assertRaises(ValueError):
            aplicar_peso(vizinhos, np.zeros((4, 4, 5), dtype=np.float32))


class ArmazenamentoDePesoTests(unittest.TestCase):
    def test_importar_sdf_copia_a_matriz_e_anota_a_origem(self) -> None:
        sdf = np.random.default_rng(4).uniform(-10, 2, size=(4, 5, 6)).astype(np.float32)

        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "campo_sdf.npz"
            np.savez_compressed(origem, sdf=sdf, convencao="interno positivo")
            destino_pesos = Path(pasta) / "pesos"

            primeiro = importar_sdf(origem, destino_pesos)
            segundo = importar_sdf(origem, destino_pesos)

            self.assertEqual((primeiro.name, segundo.name), ("peso_001.npz", "peso_002.npz"))
            self.assertEqual(used_peso_ids(destino_pesos), {1, 2})
            np.testing.assert_array_equal(load_peso_matrix(1, destino_pesos), sdf)

            info = load_peso_info(1, destino_pesos)
            self.assertEqual(info["shape"], (4, 5, 6))
            self.assertEqual(info["convencao"], "interno positivo")
            self.assertTrue(info["origem"].endswith("campo_sdf.npz"))


if __name__ == "__main__":
    unittest.main()
