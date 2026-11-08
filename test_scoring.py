"""Testes do ranking demonstrativo e dos quatro indicadores reais V2."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from bairroiq.sample_data import SampleDataProvider
from bairroiq.scoring import ScenarioScoringService


class ScoreNeighborhoodsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = ScenarioScoringService()

    def test_sample_data_has_ten_neighborhoods_with_history(self) -> None:
        provider = SampleDataProvider()
        self.assertEqual(len(provider.load_metrics()), 10)
        self.assertEqual(provider.load_history()["neighborhood"].nunique(), 10)

    def test_provider_factory_selects_sample_data(self) -> None:
        # Testa a fábrica quando Streamlit está disponível, sem exigir
        # SDK/servidor Databricks no teste unitário.
        try:
            from bairroiq.provider import DataProviderFactory
        except ImportError as exc:
            self.skipTest(f"Streamlit indisponível no ambiente do teste: {exc}")
        self.assertIsInstance(
            DataProviderFactory.create("sample"), SampleDataProvider
        )
        with self.assertRaisesRegex(ValueError, "BAIRROIQ_DATA_PROVIDER"):
            DataProviderFactory.create("unknown")

    def test_custom_priorities_change_sample_ranking(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        greenery = self.scorer.score_neighborhoods(
            metrics, {"trees": 100, "safety": 0, "mobility": 0, "budget": 0}
        )
        affordability = self.scorer.score_neighborhoods(
            metrics, {"trees": 0, "safety": 0, "mobility": 0, "budget": 100}
        )
        self.assertEqual(greenery.iloc[0]["neighborhood"], "Perdizes")
        self.assertEqual(affordability.iloc[0]["neighborhood"], "Sé")

    def test_zero_weights_are_rejected(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        with self.assertRaisesRegex(ValueError, "ao menos uma prioridade"):
            self.scorer.score_neighborhoods(metrics, {"trees": 0, "safety": 0})

    def test_sample_fallback_uses_precomputed_safety(self) -> None:
        metrics = SampleDataProvider().load_metrics().head(2).copy()
        metrics["lighting_led"] = float("nan")
        metrics["trees_score"] = float("nan")
        metrics["affordability_score"] = float("nan")
        metrics["safety_score"] = [91.0, 92.0]
        weights = {"safety": 25, "mobility": 20, "infrastructure": 20, "jobs": 15, "budget": 20}
        scored = self.scorer.score_neighborhoods(metrics, weights)
        self.assertEqual(
            scored.set_index("neighborhood")["safety_score"].to_dict(),
            {"Vila Mariana": 91.0, "Pinheiros": 92.0},
        )
        self.assertTrue(scored["priority_score"].notna().all())

    def test_scenario_insight_updates_priority_and_recommendation(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        selected = ["Vila Mariana", "Perdizes"]
        green_weights = {"trees": 100, "safety": 0, "mobility": 0, "budget": 0}
        safety_weights = {"trees": 0, "safety": 100, "mobility": 0, "budget": 0}
        green = self.scorer.build_scenario_insight(
            self.scorer.score_neighborhoods(metrics, green_weights), green_weights,
            selected,
        )
        safety = self.scorer.build_scenario_insight(
            self.scorer.score_neighborhoods(metrics, safety_weights), safety_weights,
            selected,
        )
        self.assertEqual(green.dominant_priority, "Arborização")
        self.assertEqual(green.recommended_name, "Vila Mariana")
        self.assertEqual(safety.dominant_priority, "Segurança")
        self.assertEqual(safety.recommended_name, "Perdizes")
        self.assertNotEqual(green.leader_name, safety.leader_name)

    def test_scenario_insight_explains_when_all_priorities_are_disabled(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        weights = {"trees": 0, "safety": 0, "mobility": 0, "budget": 0}
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )
        insight = self.scorer.build_scenario_insight(scored, weights)
        self.assertIsNone(insight.dominant_priority)
        self.assertIsNone(insight.recommended_name)
        self.assertGreaterEqual(insight.leader_score, 0)

    @staticmethod
    def real_fixture() -> pd.DataFrame:
        return pd.DataFrame({
            "snapshot_id": ["snapshot", "snapshot"],
            "neighborhood": ["Distrito A", "Distrito B"],
            "latitude": [-23.55, -23.57],
            "longitude": [-46.64, -46.65],
            "formal_jobs_score": [88.0, 10.0],
            "safety_score": [60.0, 90.0],
            "mobility_score": [50.0, 70.0],
            "green_leisure_score": [100.0, 10.0],
            "public_services_score": [80.0, 20.0],
            "densidade_hab_km2": [5000.0, 22000.0],
            "robberies_per_1000": [15.0, 1.0],
            "perfil_id": ["kmeans-k09-p01", "kmeans-k09-p02"],
            "cluster": ["P01 — Perfil A", "P02 — Perfil B"],
        })

    def test_real_consumer_uses_four_distinct_priorities(self) -> None:
        frame = self.real_fixture()
        weights = {"trees": 50, "safety": 0, "mobility": 0,
                   "infrastructure": 50, "jobs": 100, "budget": 100}
        out = self.scorer.score_neighborhoods(frame, weights)
        self.assertEqual(out["neighborhood"].tolist(), ["Distrito A", "Distrito B"])
        # Empregos e orçamento não entram na pontuação V2.
        self.assertAlmostEqual(out.loc[0, "priority_score"], 90.0)
        self.assertAlmostEqual(out.loc[1, "priority_score"], 15.0)
        self.assertEqual(out.set_index("neighborhood").loc["Distrito A", "safety_score"], 60.0)

    def test_real_ranking_is_not_recomputed_from_robberies(self) -> None:
        frame = self.real_fixture()
        out = self.scorer.score_neighborhoods(frame, {"safety": 100})
        self.assertEqual(out.iloc[0]["neighborhood"], "Distrito B")
        self.assertEqual(out.iloc[0]["safety_score"], 90.0)

    def test_real_rejects_missing_or_null_scores(self) -> None:
        frame = self.real_fixture()
        with self.assertRaisesRegex(ValueError, "Consumer V2 sem indicadores"):
            self.scorer.score_neighborhoods(
                frame.drop(columns="green_leisure_score"), {"safety": 100}
            )
        frame.loc[0, "public_services_score"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Indicador V2 nulo"):
            self.scorer.score_neighborhoods(frame, {"safety": 100})

    def test_real_dominant_priority_is_green_leisure(self) -> None:
        frame = self.real_fixture()
        weights = {"trees": 80, "safety": 20, "mobility": 0, "infrastructure": 0}
        out = self.scorer.score_neighborhoods(frame, weights)
        insight = self.scorer.build_scenario_insight(out, weights)
        self.assertEqual(insight.dominant_priority, "Verde e lazer")
        self.assertEqual(insight.dominant_weight, 80)


if __name__ == "__main__":
    unittest.main()
