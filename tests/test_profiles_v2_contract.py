"""Testes estáticos do contrato da página Perfis Urbanos.

Não dependem de credenciais, de acesso ao Databricks ou de Streamlit instalado.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "pages" / "perfis.py"


class TestProfilesV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = PAGE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.content)

    def test_v2_indicators(self) -> None:
        for column in (
            "formal_jobs_score", "safety_score", "mobility_score",
            "green_leisure_score", "public_services_score",
        ):
            self.assertIn(column, self.content)

    def test_cluster_is_read_from_materialized_result(self) -> None:
        self.assertIn('row["cluster"]', self.content)
        self.assertIn('row["perfil_id"]', self.content)
        self.assertIn("K-Means", self.content)

    def test_population_density_is_not_ranked_as_score(self) -> None:
        self.assertIn('row["densidade_hab_km2"]', self.content)
        self.assertNotIn('"Densidade populacional": "densidade_hab_km2"', self.content)

    def test_keeps_original_components(self) -> None:
        self.assertIn('key="profiles-grid"', self.content)
        self.assertIn('key="profiles-chart"', self.content)
        self.assertIn('class="profile-card"', self.content)
        self.assertIn("SCENARIO_SCORER.score_neighborhoods", self.content)


if __name__ == "__main__":
    unittest.main()
