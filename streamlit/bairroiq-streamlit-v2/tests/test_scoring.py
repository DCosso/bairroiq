import unittest

from bairroiq.provider import DataProviderFactory
from bairroiq.sample_data import SampleDataProvider
from bairroiq.scoring import ScenarioScoringService


class ScoreNeighborhoodsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = ScenarioScoringService()

    def test_sample_data_has_ten_neighborhoods_with_history(self) -> None:
        provider = SampleDataProvider()

        self.assertEqual(len(provider.load_metrics()), 10)
        history = provider.load_history()
        self.assertEqual(history["neighborhood"].nunique(), 10)

    def test_provider_factory_selects_sample_data(self) -> None:
        self.assertIsInstance(
            DataProviderFactory.create("sample"), SampleDataProvider
        )
        with self.assertRaisesRegex(ValueError, "BAIRROIQ_DATA_PROVIDER"):
            DataProviderFactory.create("unknown")

    def test_custom_priorities_change_the_ranking(self) -> None:
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
            self.scorer.score_neighborhoods(
                metrics, {"trees": 0, "safety": 0, "mobility": 0, "budget": 0}
            )

    def test_missing_indicators_are_excluded_and_published_safety_is_used(self) -> None:
        metrics = SampleDataProvider().load_metrics().head(2).copy()
        metrics["lighting_led"] = float("nan")
        metrics["trees_score"] = float("nan")
        metrics["affordability_score"] = float("nan")
        metrics["safety_score"] = [91.0, 92.0]
        weights = {
            "safety": 25,
            "mobility": 20,
            "infrastructure": 20,
            "jobs": 15,
            "budget": 20,
        }

        scored = self.scorer.score_neighborhoods(metrics, weights)

        self.assertEqual(
            scored.set_index("neighborhood")["safety_score"].to_dict(),
            {"Vila Mariana": 91.0, "Pinheiros": 92.0},
        )
        self.assertTrue(scored["priority_score"].notna().all())

    def test_scenario_insight_updates_priority_and_recommendation(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        selected = ["Vila Mariana", "Perdizes"]
        greenery_weights = {"trees": 100, "safety": 0, "mobility": 0, "budget": 0}
        safety_weights = {"trees": 0, "safety": 100, "mobility": 0, "budget": 0}

        greenery = self.scorer.build_scenario_insight(
            self.scorer.score_neighborhoods(metrics, greenery_weights),
            greenery_weights,
            selected,
        )
        safety = self.scorer.build_scenario_insight(
            self.scorer.score_neighborhoods(metrics, safety_weights),
            safety_weights,
            selected,
        )

        self.assertEqual(greenery.dominant_priority, "Arborização")
        self.assertEqual(greenery.recommended_name, "Vila Mariana")
        self.assertEqual(safety.dominant_priority, "Segurança")
        self.assertEqual(safety.recommended_name, "Perdizes")
        self.assertNotEqual(greenery.leader_name, safety.leader_name)

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


if __name__ == "__main__":
    unittest.main()
