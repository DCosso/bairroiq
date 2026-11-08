"""A comparação mantém gráficos, mas mostra nomes comerciais dos grupos."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest
PAGE=Path(__file__).resolve().parents[1]/'pages/comparar.py'
class CompareMlPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=PAGE.read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source)
    def test_groups_are_original_and_labels_commercial(self):
        self.assertIn('build_cluster_comparison(scored, selected)',cls_source := self.source)
        self.assertIn('key="comparison-chart-cluster"',cls_source)
        self.assertIn('"ticktext": nomes_perfis',cls_source)
        self.assertIn('custom_data=["cluster", "distritos_no_perfil"]',cls_source)
        self.assertNotIn('"Identificador ML"',cls_source)
    def test_no_fictitious_history(self):
        for value in ('load_history','history_comparison','Evolução temporal','x="year"'):
            self.assertNotIn(value,self.source)
    def test_layout_survives(self):
        for key in ('key="comparison-summary-panel"','key="comparison-map-card"',
                    'key="comparison-ranking-card"','key="comparison-chart-indicators"',
                    'key="comparison-chart-profile"','key="comparison-map"','"duel-card"'):
            self.assertIn(key,self.source)
    def test_v2_dimensions(self):
        for value in ('metric_options = dict(V2_INDICATORS)',
                      'priority_options = dict(V2_WEIGHT_DIMENSIONS)',
                      'real_v2 = is_real_v2(scored)'):
            self.assertIn(value,self.source)
        self.assertIn('x="codigo", y="aderencia_media"',self.source)
        self.assertIn('max_selections=5',self.source)
if __name__=='__main__':unittest.main()
