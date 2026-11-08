"""Validação offline do contrato de comparação por K-Means do Consumer V2."""
from __future__ import annotations

import unittest

import pandas as pd

from bairroiq.comparison_v2 import (
    V2_INDICATORS,
    V2_WEIGHT_DIMENSIONS,
    build_cluster_comparison,
    cluster_code,
    is_real_v2,
    selected_cluster_descriptions,
)


def make_frame() -> pd.DataFrame:
    data = []
    for number in range(1, 10):
        code = f"P{number:02d}"
        for suffix in range(2):
            data.append(
                {
                    "neighborhood": f"Distrito {code} {suffix}",
                    "cluster": f"{code} — Perfil de teste {number}",
                    "perfil_id": f"kmeans-k09-p{number:02d}",
                    "priority_score": 40.0 + number + suffix,
                    "formal_jobs_score": 35.0 + number,
                    "safety_score": 45.0 + number,
                    "mobility_score": 50.0 + number,
                    "green_leisure_score": 55.0 + number,
                    "public_services_score": 60.0 + number,
                    "densidade_hab_km2": 12000.0 + number,
                    "robberies_per_1000": 4.5 + number / 10.0,
                }
            )
    return pd.DataFrame(data)


class ComparisonContractTests(unittest.TestCase):
    def setUp(self):
        self.frame = make_frame()

    def test_indicators_and_rank_dimensions(self):
        self.assertEqual(len(V2_INDICATORS), 5)
        self.assertEqual(set(V2_WEIGHT_DIMENSIONS), {"trees", "safety", "mobility", "infrastructure"})
        self.assertNotIn("formal_jobs_score", [v[1] for v in V2_WEIGHT_DIMENSIONS.values()])
        self.assertNotIn("densidade_hab_km2", [v[1] for v in V2_WEIGHT_DIMENSIONS.values()])

    def test_detects_real_contract(self):
        self.assertTrue(is_real_v2(self.frame))
        self.assertFalse(is_real_v2(pd.DataFrame({"neighborhood": ["A"]})))

    def test_rejects_incomplete_real_contract(self):
        with self.assertRaisesRegex(ValueError, "incompleto"):
            is_real_v2(self.frame.drop(columns=["green_leisure_score"]))

    def test_nine_groups_and_district_totals(self):
        result = build_cluster_comparison(self.frame, ["Distrito P04 0", "Distrito P09 1"])
        self.assertEqual(result["codigo"].tolist(), [f"P{i:02d}" for i in range(1, 10)])
        self.assertEqual(int(result["distritos_no_perfil"].sum()), 18)
        self.assertEqual(set(result[result["grupo_selecionado"]]["codigo"]), {"P04", "P09"})
        self.assertAlmostEqual(result.loc[result["codigo"] == "P04", "aderencia_media"].iloc[0], 44.5)

    def test_cluster_codes_are_categories(self):
        self.assertEqual(cluster_code("P03 — Áreas Pouco Povoadas"), "P03")
        with self.assertRaises(ValueError):
            cluster_code("perfil novo")

    def test_no_duplicate_district(self):
        data = pd.concat([self.frame, self.frame.iloc[:1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicados"):
            build_cluster_comparison(data, [])

    def test_no_ambiguous_cluster_to_profile(self):
        data = self.frame.copy()
        data.loc[0, "perfil_id"] = "kmeans-k09-p99"
        with self.assertRaisesRegex(ValueError, "biunívoco"):
            build_cluster_comparison(data, [])

    def test_selected_names_follow_user_order(self):
        selected = ["Distrito P09 1", "Distrito P04 0"]
        labels = selected_cluster_descriptions(self.frame, selected)
        self.assertTrue(labels[0].startswith(selected[0]))
        self.assertTrue(labels[1].startswith(selected[1]))


if __name__ == "__main__":
    unittest.main()
