"""Confere o SDF de cavegen/tools/sdf e as manipulações dele (limiar e logaritmo).

    uv run python -m unittest tests/test_sdf.py -v
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cavegen.generators.cellular_automata.pesos import (
    importar_sdf,
    load_peso_info,
    load_peso_matrix,
)
from cavegen.sdf.manipulacao import comprimir_log, deslocar_zero, manipular_sdf
from cavegen.tools.sdf.sdf import (
    CORTE_NEGATIVO,
    corte_do_campo,
    gravar_campo,
    nome_do_campo,
    sdf_da_superficie,
)


def caixa_oca() -> np.ndarray:
    """Casca de cubo com 2 voxels de parede e um oco fechado no meio, numa grade 16³."""
    cheio = np.zeros((16, 16, 16), dtype=bool)
    cheio[4:12, 4:12, 4:12] = True
    cheio[6:10, 6:10, 6:10] = False
    return cheio

def gravar_superficie(pasta: Path, cheio: np.ndarray) -> Path:
    """Grava a grade no formato que gravar_campo lê."""
    entrada = pasta / "caixa_16.npz"
    np.savez_compressed(entrada, surface_voxels=cheio.astype(np.uint8),
                        metadata=np.array("caixa de teste"))
    return entrada

class ManipulacaoTests(unittest.TestCase):
    def test_limiar_leva_o_zero_para_o_limiar(self):
        sdf = np.array([-6.0, -4.0, -1.0, 0.0, 2.0], dtype=np.float32)

        campo = deslocar_zero(sdf, -4)

        np.testing.assert_array_equal(campo, [-2.0, 0.0, 3.0, 4.0, 6.0])
        self.assertEqual(campo.dtype, np.float32)

    def test_sem_limiar_e_sem_log_o_campo_e_o_sdf_base(self):
        sdf = np.linspace(-20, 3, 50, dtype=np.float32)

        np.testing.assert_array_equal(manipular_sdf(sdf), sdf)

    def test_ordem_fixa_desloca_e_depois_comprime(self):
        sdf = np.linspace(-20, 3, 47, dtype=np.float32)

        campo = manipular_sdf(sdf, limiar=-4, escala_log=2)

        np.testing.assert_array_equal(campo, comprimir_log(deslocar_zero(sdf, -4), 2))
        # Nessa ordem, o voxel a 4 voxels de fora continua neutro depois do log.
        self.assertEqual(float(manipular_sdf(np.array([-4.0], np.float32), -4, 2)[0]), 0.0)
        # Na ordem inversa o zero sairia do lugar: a ordem faz diferença.
        invertido = deslocar_zero(comprimir_log(sdf, 2), -4)
        self.assertFalse(np.allclose(campo, invertido))

    def test_manipulacao_preserva_a_ordem_dos_voxels(self):
        # Por isso o corte do plot mostra os mesmos voxels com e sem manipulação.
        sdf = np.linspace(-30, 3, 200, dtype=np.float32)
        for limiar, escala in ((0, None), (-4, None), (-4, 2.0), (1.5, 0.5)):
            campo = manipular_sdf(sdf, limiar, escala)
            self.assertTrue(np.all(np.diff(campo) > 0))
            np.testing.assert_array_equal(campo > corte_do_campo(limiar, escala),
                                          sdf > CORTE_NEGATIVO)

    def test_entradas_invalidas(self):
        sdf = np.zeros(3, dtype=np.float32)
        for limiar in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                manipular_sdf(sdf, limiar=limiar)
        for escala in (0.0, -1.0, float("nan")):
            with self.assertRaises(ValueError):
                manipular_sdf(sdf, limiar=-4, escala_log=escala)

    def test_nome_do_campo(self):
        self.assertEqual(nome_do_campo("elaphes_surface_64"), "elaphes_surface_64_sdf")
        self.assertEqual(nome_do_campo("elaphes_surface_64", -4, 2),
                         "elaphes_surface_64_sdf_limiar-4_log2")
        self.assertEqual(nome_do_campo("e", escala_log=0.5), "e_sdf_log0.5")

class GravacaoTests(unittest.TestCase):
    def test_sdf_base_segue_o_contrato_de_sinal(self):
        sdf, borda, interno = sdf_da_superficie(caixa_oca())

        np.testing.assert_array_equal(sdf == 0, borda)
        np.testing.assert_array_equal(sdf > 0, interno)
        np.testing.assert_array_equal(sdf < 0, ~borda & ~interno)

    def test_campo_gravado_guarda_a_manipulacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            entrada = gravar_superficie(pasta, caixa_oca())
            base = gravar_campo(entrada, pasta=pasta / "npz")
            manipulado = gravar_campo(entrada, limiar=-4, escala_log=2, pasta=pasta / "npz")

            with np.load(base) as b, np.load(manipulado) as m:
                self.assertEqual(base.name, "caixa_16_sdf.npz")
                self.assertEqual(manipulado.name, "caixa_16_sdf_limiar-4_log2.npz")
                self.assertEqual(float(b["limiar"]), 0.0)
                self.assertNotIn("escala_log", b.files)
                self.assertEqual((float(m["limiar"]), float(m["escala_log"])), (-4.0, 2.0))
                self.assertIn("d = -4", str(m["convencao"]))
                self.assertIn("comprimido com 2", str(m["convencao"]))
                np.testing.assert_array_equal(m["sdf"], manipular_sdf(b["sdf"], -4, 2))
                np.testing.assert_array_equal(m["borda"], b["borda"])

    def test_ca_importa_o_campo_manipulado_como_peso(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            entrada = gravar_superficie(pasta, caixa_oca())
            campo = gravar_campo(entrada, limiar=-4, pasta=pasta / "npz")
            importar_sdf(campo, pasta / "pesos")

            info = load_peso_info(1, pasta / "pesos")
            matriz = load_peso_matrix(1, pasta / "pesos")
            with np.load(campo) as c:
                esperado = c["sdf"]

        np.testing.assert_array_equal(matriz, esperado)
        self.assertIn("d = -4", info["convencao"])

    def test_parametro_invalido_nao_grava_nada(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            entrada = gravar_superficie(pasta, caixa_oca())
            with self.assertRaises(ValueError):
                gravar_campo(entrada, limiar=float("nan"), pasta=pasta / "npz")
            self.assertFalse((pasta / "npz").exists())

if __name__ == "__main__":
    unittest.main()
