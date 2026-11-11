"""Contratos de regressão: seleção 0-10, mapa alto e tabelas com contraste."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest
from bairroiq.selection_ux import reconcile_selection

BASE = Path(__file__).resolve().parents[1]

class UxV4Fixes(unittest.TestCase):
    def test_selection_recovers_truncated_header(self):
        header=[f"Distrito {i}" for i in range(8)]
        self.assertEqual(reconcile_selection(header,header[:5],header),header)
        self.assertEqual(len(reconcile_selection(header[:10],header[:5],header)),8)
    def test_page_selection_keeps_manual_choice(self):
        header=[f"Distrito {i}" for i in range(10)]
        page=["Distrito 9","Distrito 7"]
        self.assertEqual(reconcile_selection(header,page,header),page)
    def test_selection_clears_when_empty(self):
        self.assertEqual(reconcile_selection([],[],["A"]),[])
    def test_selection_respects_limit_filters_and_dedup(self):
        full=[f"D{i}" for i in range(13)]
        self.assertEqual(reconcile_selection(full,full[:5],full),full[:10])
        self.assertEqual(reconcile_selection(full,full[:5],full[3:]),full[3:13])
    def test_frontend_contract(self):
        app=(BASE/'app.py').read_text(encoding='utf-8')
        home=(BASE/'pages/iniciar.py').read_text(encoding='utf-8')
        compare=(BASE/'pages/comparar.py').read_text(encoding='utf-8')
        for name,source in [('app',app),('home',home),('compare',compare)]:
            ast.parse(source,filename=name)
        self.assertIn('reconcile_selection(', app)
        self.assertIn('reconcile_selection(', compare)
        self.assertIn('max_selections=10',compare)
        self.assertIn('"### Perfis de Distrito"',home)
        self.assertNotIn('"### Top 10 do cenário"',home)
        self.assertIn('height="stretch"',home)
        self.assertIn('render_responsive_table(',compare)
    def test_css_table_and_map_scoped(self):
        css=(BASE/'bairroiq/assets/ajustes_v4.css').read_text(encoding='utf-8')
        self.assertIn('min-width: 901px',css)
        self.assertIn('--atlas-home-height',css)
        self.assertIn('.atlas-data-table',css)
        self.assertIn('[data-testid="stTable"]',css)

if __name__=='__main__':unittest.main()
