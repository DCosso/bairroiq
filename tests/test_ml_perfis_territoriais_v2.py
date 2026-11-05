"""Testes sem Spark nem acesso ao workspace; apenas dados sintéticos de teste."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

import numpy as np
import pandas as pd

PATH = Path(__file__).resolve().parents[1] / "barrioiq_pipeline" / "ml_perfis_territoriais_v2.py"
spec = importlib.util.spec_from_file_location("ml_perfis_v2", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    rng = np.random.default_rng(42)
    n = 96
    districts = pd.DataFrame({
        "CD_DIST": np.arange(355030801, 355030801 + n, dtype=int),
        "NM_DIST": [f"Distrito {i}" for i in range(n)],
        "latitude": -23.65 + rng.random(n) * .35,
        "longitude": -46.85 + rng.random(n) * .5,
    })
    latent = np.repeat(np.arange(8), 12)  # somente teste de contrato, nao e dado real
    for i, name in enumerate(module.SOURCE_FIELDS):
        if name == "empregos":
            districts[name] = 2500 + 1200 * latent + rng.uniform(1, 500, n)
        elif name == "densidade":
            districts[name] = 250 + 1000 * latent + rng.uniform(1, 500, n)
        else:
            districts[name] = np.maximum(.01, 1 + latent * .4 + rng.random(n) * (i + 1))
    return districts


class TestContract(unittest.TestCase):
    def test_valid_and_sorted(self):
        x = fixture().sample(frac=1, random_state=10)
        out = module.validate_and_prepare(x, reference=Path("/nonexistent/ibge.json"))
        self.assertEqual(len(out), 96)
        self.assertTrue(out.CD_DIST.is_monotonic_increasing)

    def test_missing_column(self):
        with self.assertRaisesRegex(ValueError, "Colunas ausentes"):
            module.validate_and_prepare(fixture().drop(columns="ubs"))

    def test_duplicate_district(self):
        x = fixture(); x.loc[1, "CD_DIST"] = x.loc[0, "CD_DIST"]
        with self.assertRaisesRegex(ValueError, "duplicado"):
            module.validate_and_prepare(x)

    def test_nan_rejected(self):
        x = fixture(); x.loc[0, "roubos"] = np.nan
        with self.assertRaisesRegex(ValueError, "nulos"):
            module.validate_and_prepare(x)

    def test_negative_rejected(self):
        x = fixture(); x.loc[0, "pracas"] = -2
        with self.assertRaisesRegex(ValueError, "negativos"):
            module.validate_and_prepare(x)

    def test_no_missing_imbge_name_guesses(self):
        x = fixture(); x.loc[0, "NM_DIST"] = "S\ufffde"
        with self.assertRaisesRegex(ValueError, "corrompidos"):
            module.validate_and_prepare(x, reference=Path("/nonexistent/ibge.json"))


class TestMethods(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = module.validate_and_prepare(fixture(), reference=Path("/nonexistent/ibge.json"))
        cls.X, cls.axes = module.features(cls.data)

    def test_six_axes(self):
        self.assertEqual(self.X.shape, (96, 6))
        self.assertEqual(tuple(self.axes.columns), module.AXES)

    def test_both_reproducible(self):
        for method in module.METHODS:
            a = module.predict(method, self.X, 8)
            b = module.predict(method, self.X, 8)
            np.testing.assert_array_equal(a, b)

    def test_ablation(self):
        for axis in module.AXES:
            x, _ = module.features(self.data, without_axis=axis)
            self.assertEqual(x.shape, (96, 5))

    def test_invalid_axis(self):
        with self.assertRaisesRegex(ValueError, "Eixo desconhecido"):
            module.features(self.data, without_axis="custo_de_vida")

    def test_invalid_method(self):
        with self.assertRaisesRegex(ValueError, "Metodo invalido"):
            module.predict("dbscan", self.X, 8)

    def test_stable_ids(self):
        lab = module.predict("ward", self.X, 8)
        a = module.stable_ids(lab, self.data)
        b = module.stable_ids(lab + 20, self.data)
        np.testing.assert_array_equal(a, b)

    def test_explanations_are_provisional(self):
        lab = module.predict("kmeans", self.X, 9)
        profiles, assignments = module.explain_profiles(self.data, self.X, lab, "kmeans", 9)
        self.assertEqual(len(profiles), 9)
        self.assertEqual(len(assignments), 96)
        self.assertTrue(profiles.perfil_nome_provisorio.str.len().gt(0).all())
        self.assertTrue(profiles.status.eq("EXPLORATORIO_NAO_HOMOLOGADO").all())
        self.assertEqual(assignments.CD_DIST.nunique(), 96)


class TestExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = module.compare(fixture(), repetitions=2, reference=Path("/nonexistent/ibge.json"))

    def test_all_k_combinations(self):
        self.assertEqual(len(self.results["metricas"]), 22)
        self.assertEqual(set(self.results["metricas"].k), set(range(2, 13)))

    def test_all_explanations_and_assignments(self):
        self.assertEqual(len(self.results["atribuicoes"]), 96 * 3 * 2)
        self.assertEqual(self.results["perfis"].groupby(["metodo", "k"]).size().to_dict(),
                         {(m, k): k for m in module.METHODS for k in module.PRODUCT_K})

    def test_no_automatic_approval(self):
        summary = self.results["resumo"]
        self.assertEqual(summary["alteracoes_gold"], "NENHUMA")
        self.assertEqual(summary["status"], "EXPLORATORIO_NAO_HOMOLOGADO")
        self.assertTrue(all("status_publicacao" in i for i in summary["variacoes"]))

    def test_robustness_is_recorded(self):
        self.assertEqual(len(self.results["resumo"]["variacoes"]), 6)
        for entry in self.results["resumo"]["variacoes"]:
            self.assertEqual(entry["estabilidade"]["reamostragens"], 2)
            self.assertEqual(set(entry["sensibilidade_ari"]), set(module.AXES))

    def test_export(self):
        with tempfile.TemporaryDirectory() as directory:
            module.export(self.results, directory)
            for name in ("metricas_v2.csv", "perfis_v2.csv", "distritos_perfis_v2.csv", "resumo_v2.json"):
                self.assertTrue((Path(directory) / name).is_file())
            self.assertEqual(json.loads((Path(directory) / "resumo_v2.json").read_text())["distritos"], 96)


if __name__ == "__main__":
    unittest.main()
