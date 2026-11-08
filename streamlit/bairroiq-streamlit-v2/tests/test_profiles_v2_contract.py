"""A página de estilos usa as atribuições reais, com nomes acessíveis."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest
PAGE=Path(__file__).resolve().parents[1]/"pages/perfis.py"
class TestProfilesV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=PAGE.read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.content)
    def test_v2_indicators(self):
        for field in ('formal_jobs_score','safety_score','mobility_score',
                      'green_leisure_score','public_services_score'):
            self.assertIn(field,self.content)
    def test_real_groups_preserved_but_codes_hidden(self):
        self.assertIn('nome_perfil(row["cluster"])',self.content)
        self.assertIn('metrics["perfil_id"].nunique()',self.content)
        self.assertNotIn('f"<p>Identificador:',self.content)
        self.assertNotIn('f"<p>Perfil territorial K-Means:',self.content)
    def test_density_is_descriptive(self):
        self.assertIn('row["densidade_hab_km2"]',self.content)
        self.assertNotIn('"Densidade populacional": "densidade_hab_km2"',self.content)
    def test_keep_layout(self):
        for key in ('key="profiles-grid"','key="profiles-chart"','class="profile-card"'):
            self.assertIn(key,self.content)
        self.assertIn('SCENARIO_SCORER.score_neighborhoods',self.content)
if __name__=='__main__':unittest.main()
