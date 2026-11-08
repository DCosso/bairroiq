"""Resguarda a linguagem comercial nas telas para visitantes."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
class CommercialCopyTests(unittest.TestCase):
    def test_pages_compile(self):
        for rel in ["pages/explorar.py", "pages/comparar.py", "pages/perfis.py", "pages/fontes.py"]:
            ast.parse((ROOT/rel).read_text(encoding='utf-8'),filename=rel)
    def test_no_infrastructure_copy_on_sources_page(self):
        src=(ROOT/'pages/fontes.py').read_text(encoding='utf-8')
        for phrase in ('Conexão Databricks','secrets.toml','contrato do adaptador','arquitetura do lake'):
            self.assertNotIn(phrase,src)
    def test_map_initial_and_ranking_use_same_filters(self):
        src=(ROOT/'bairroiq/explore_logic.py').read_text(encoding='utf-8')
        self.assertIn('elegiveis = filter_districts(',src)
        self.assertIn('top10 = elegiveis.head(10).copy()',src)
        self.assertIn('elegiveis.copy() if not selecionados',src)
    def test_no_public_profile_codes_in_ui(self):
        for rel in ('pages/explorar.py','pages/comparar.py','pages/perfis.py'):
            src=(ROOT/rel).read_text(encoding='utf-8')
            self.assertNotIn('f"<p>Identificador:',src)
            self.assertNotIn('Identificador ML',src)

if __name__ == '__main__': unittest.main()
