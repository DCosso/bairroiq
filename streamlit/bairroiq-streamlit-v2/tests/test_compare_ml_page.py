"""Proteções estáticas para a tela Comparação sem depender do Streamlit."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "pages" / "comparar.py"


class CompareMlPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PAGE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_real_kmeans_cluster_chart(self):
        self.assertIn("build_cluster_comparison(scored, selected)", self.source)
        self.assertIn('key="comparison-chart-cluster"', self.source)
        self.assertIn('"cluster", "perfil_id", "distritos_no_perfil"', self.source)

    def test_no_demo_history_chart_or_loading(self):
        self.assertNotIn("load_history", self.source)
        self.assertNotIn("history_comparison", self.source)
        self.assertNotIn("Evolução temporal", self.source)
        self.assertNotIn('x="year"', self.source)

    def test_original_layout_survives(self):
        for marker in (
            'key="comparison-summary-panel"', 'key="comparison-map-card"',
            'key="comparison-ranking-card"', 'key="comparison-chart-indicators"',
            'key="comparison-chart-profile"', 'key="comparison-map"',
            '"duel-card"',
        ):
            self.assertIn(marker, self.source)

    def test_no_old_indicators_in_v2_flow(self):
        # Os nomes antigos só podem aparecer na compatibilidade ilustrativa.
        self.assertIn('metric_options = dict(V2_INDICATORS)', self.source)
        self.assertIn('priority_options = dict(V2_WEIGHT_DIMENSIONS)', self.source)
        self.assertIn('real_v2 = is_real_v2(scored)', self.source)

    def test_cluster_ids_not_used_as_quantities(self):
        self.assertIn('x="codigo", y="aderencia_media"', self.source)
        self.assertIn('xaxis={"type": "category"', self.source)

    def test_max_five_districts(self):
        self.assertIn('max_selections=5', self.source)


if __name__ == "__main__":
    unittest.main()
