"""Contratos estáticos da página de comparação V3, sem subir Streamlit."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages/comparar.py"


class ComparePageV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PAGE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_up_to_ten_and_automatic_top_ten(self):
        self.assertIn("max_selections=10", self.source)
        self.assertIn("selecionar_comparacao(eligible, chosen)", self.source)
        self.assertIn("top10_filtrado(eligible)", self.source)
        self.assertNotIn("max_selections=5", self.source)
        self.assertNotIn("len(selected) < 2", self.source)

    def test_filters_before_ranking(self):
        self.assertIn("ranking_filtrado(", self.source)
        self.assertIn('st.session_state.get("map-search", "")', self.source)
        self.assertIn('st.session_state.get("map-quick-filters", [])', self.source)
        self.assertIn('options=options', self.source)

    def test_existing_visual_components(self):
        for marker in (
            'key="comparison-summary-panel"', 'key="comparison-map-card"',
            'key="comparison-ranking-card"', 'key="comparison-chart-indicators"',
            'key="comparison-chart-profile"', 'key="comparison-chart-cluster"',
            'key="comparison-map"',
        ):
            self.assertIn(marker, self.source)
        self.assertIn('build_cluster_comparison(scored, selected)', self.source)
        self.assertIn('custom_data=["cluster", "distritos_no_perfil"]', self.source)
        self.assertIn('"ticktext": nomes_perfis', self.source)
        self.assertIn('x="codigo", y="aderencia_media"', self.source)
        self.assertIn('real_v2 = is_real_v2(scored)', self.source)

    def test_no_synthetic_history_or_user_facing_ml(self):
        for marker in ("load_history", "history_comparison", "Evolução temporal", "Identificador ML"):
            self.assertNotIn(marker, self.source)
        self.assertIn("Perfis de Distrito", self.source)

    def test_button_contrast(self):
        self.assertIn('background: #184977 !important', self.source)
        self.assertIn('color: #fff !important', self.source)
        self.assertIn('min-height: 44px !important', self.source)


if __name__ == "__main__":
    unittest.main()
