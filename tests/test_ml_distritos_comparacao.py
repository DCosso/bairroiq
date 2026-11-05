"""Testes do experimento de modelos BairroIQ, sem Spark/Databricks.

Instalar numpy, pandas e scikit-learn. Na raiz do repositorio:
  python -m unittest discover -s tests -p test_ml_distritos_comparacao.py -v
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from barrioiq_pipeline import ml_distritos_comparacao as ml


def fixture():
    rng = np.random.default_rng(2026)
    g = np.repeat([0, 1, 2], [32, 32, 32])
    n = len(g)
    return pd.DataFrame({
        "CD_DIST": np.arange(355030801, 355030801 + n),
        "NM_DIST": [f"Distrito {i:02d}" for i in range(n)],
        "latitude": -23.4 - rng.random(n) * .3,
        "longitude": -46.3 - rng.random(n) * .45,
        "empregos": np.maximum(0, rng.normal(20000 + 50000 * g, 5000)),
        "roubos": np.maximum(0, rng.normal(200 + 300 * g, 50)),
        "corredores_verdes": np.maximum(0, rng.normal(.03 + g*.12, .04)),
        "metro": np.maximum(0, rng.normal(.05 + g*.1, .02)),
        "onibus": np.maximum(0, rng.normal(10 + g*10, 2)),
        "trem": np.maximum(0, rng.normal(.02 + g*.08, .01)),
    })


class TestContract(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def test_valid_input(self):
        validated = ml.validate_data(self.data)
        self.assertEqual((len(validated), validated.CD_DIST.nunique()), (96, 96))
        self.assertEqual(list(validated.columns), list(ml.RAW_COLUMNS))

    def test_missing_field(self):
        with self.assertRaisesRegex(ValueError, "Colunas ausentes"):
            ml.validate_data(self.data.drop(columns="onibus"))

    def test_missing_district(self):
        with self.assertRaisesRegex(ValueError, "Esperados 96"):
            ml.validate_data(self.data.iloc[:-1])

    def test_duplicate_district(self):
        self.data.loc[0, "CD_DIST"] = self.data.loc[1, "CD_DIST"]
        with self.assertRaisesRegex(ValueError, "CD_DIST"):
            ml.validate_data(self.data)

    def test_missing_indicator(self):
        self.data.loc[0, "roubos"] = np.nan
        with self.assertRaisesRegex(ValueError, "nulos"):
            ml.validate_data(self.data)

    def test_negative_indicator(self):
        self.data.loc[0, "metro"] = -1
        with self.assertRaisesRegex(ValueError, "negativos"):
            ml.validate_data(self.data)

    def test_invalid_coordinate(self):
        self.data.loc[0, "longitude"] = -10
        with self.assertRaisesRegex(ValueError, "Coordenadas fora"):
            ml.validate_data(self.data)

    def test_sort_and_hash_independent_of_order(self):
        a = ml.validate_data(self.data)
        b = ml.validate_data(self.data.sample(frac=1, random_state=1))
        self.assertEqual(ml.dataset_fingerprint(a), ml.dataset_fingerprint(b))


class TestMethods(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ml.validate_data(fixture())
        cls.x, cls.axes = ml.prepare_axes(cls.data)

    def test_four_normalized_axes(self):
        self.assertEqual(self.x.shape, (96, 4))
        np.testing.assert_allclose(self.x.mean(axis=0), np.zeros(4), atol=1e-10)
        np.testing.assert_allclose(self.x.std(axis=0), np.ones(4), atol=1e-10)

    def test_log1p_jobs_and_robberies(self):
        self.assertAlmostEqual(self.axes.empregos.iloc[0], np.log1p(self.data.empregos.iloc[0]))
        self.assertAlmostEqual(self.axes.roubos.iloc[0], np.log1p(self.data.roubos.iloc[0]))

    def test_both_algorithms_and_reproducibility(self):
        for method in ml.METHODS:
            a = ml.fit_labels(method, self.x, 3)
            b = ml.fit_labels(method, self.x, 3)
            np.testing.assert_array_equal(a, b)
            self.assertEqual(len(set(a)), 3)

    def test_ablation_three_axes(self):
        x, axes = ml.prepare_axes(self.data, excluded="verde")
        self.assertEqual(x.shape, (96, 3))
        self.assertNotIn("verde", axes)

    def test_rejects_invalid_axis(self):
        with self.assertRaisesRegex(ValueError, "desconhecida"):
            ml.prepare_axes(self.data, excluded="desconhecida")

    def test_stable_ids_invariant_to_permutation_of_labels(self):
        original = ml.fit_labels("kmeans", self.x, 3)
        a = ml.stable_cluster_ids(original, self.data)
        b = ml.stable_cluster_ids((original + 1) % 3, self.data)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(set(a), {1, 2, 3})


class TestExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = ml.compare_models(fixture())

    def test_twenty_two_evaluations_including_ten_clusters(self):
        d = self.result["metricas"]
        self.assertEqual(len(d), 22)
        self.assertEqual(set(d.metodo), {"kmeans", "ward"})
        self.assertEqual(set(d.k), set(range(2, 13)))
        self.assertEqual(ml.TARGET_K, 10)
        self.assertIn("grupos_unitarios", d.columns)

    def test_assignments_complete(self):
        d = self.result["atribuicoes"]
        self.assertEqual(len(d), 96)
        self.assertEqual(d.CD_DIST.nunique(), 96)
        self.assertFalse(d[["kmeans_cluster", "ward_cluster", "kmeans_cluster_k10", "ward_cluster_k10"]].isna().any().any())
        self.assertEqual(d.kmeans_cluster_k10.nunique(), 10)
        self.assertEqual(d.ward_cluster_k10.nunique(), 10)

    def test_stability_and_ablation_documented(self):
        s = self.result["resumo"]
        for method in ml.METHODS:
            m = s["metodos"][method]
            self.assertEqual(m["estabilidade_exploratoria"]["amostras"], 100)
            self.assertEqual(set(m["sensibilidade_exploratoria_ari"]), set(ml.FEATURE_AXES))
            k10 = m["cenario_produto_k10"]
            self.assertEqual(k10["estabilidade_subamostras"]["amostras"], 100)
            self.assertEqual(set(k10["sensibilidade_retirada_dimensoes_ari"]), set(ml.FEATURE_AXES))
            self.assertFalse(k10["aprovado_publicacao"])
        self.assertEqual(s["k_objetivo_produto"], 10)
        self.assertIn("concordancia_k10_ari", s)
        self.assertEqual(s["decisao"], "PENDENTE_REVISAO_DOS_CRITERIOS_DE_NEGOCIO")
        self.assertEqual(s["alteracoes_gold"], "NENHUMA")

    def test_export_isolated_and_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            ml.export_results(self.result, temp)
            self.assertEqual(
                sorted(p.name for p in Path(temp).iterdir()),
                ["distritos_clusters_comparados.csv", "metricas_modelos.csv",
                 "perfis_clusters.csv", "resumo_experimento.json"],
            )
            d = pd.read_csv(Path(temp) / "distritos_clusters_comparados.csv")
            self.assertEqual(len(d), 96)


if __name__ == "__main__":
    unittest.main()
