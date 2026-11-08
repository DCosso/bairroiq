"""Busca e filtros recalculam o Top 10; seleção vazia mostra o mapa todo."""
from __future__ import annotations
import ast
import unittest
from pathlib import Path
import pandas as pd
from bairroiq.explore_logic import calcular_exploracao

BASE = Path(__file__).resolve().parents[1]

class ExploreFiltersTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame([
            {"neighborhood": f"Distrito {i:03d}", "priority_score": float(100-i),
             "safety_score": float(i), "formal_jobs_score": float(i),
             "mobility_score": float(i), "green_leisure_score": float(i),
             "public_services_score": float(i), "densidade_hab_km2": 1000.,
             "robberies_per_1000": 1., "cluster": "P01 — Mais Praças, Vida Urbana"}
            for i in range(96)
        ])
    def test_no_selection_shows_every_district(self):
        eligible, top10, map_df = calcular_exploracao(self.data, [], "", [])
        self.assertEqual(len(eligible),96)
        self.assertEqual(len(map_df),96)
        self.assertEqual(len(top10),10)
    def test_filter_changes_top_ten_and_map(self):
        _a, top10, shown = calcular_exploracao(self.data, [], "", ["Segurança"])
        self.assertEqual(len(shown),21)
        self.assertEqual(top10.iloc[0].neighborhood, "Distrito 075")
        self.assertNotIn("Distrito 000", top10.neighborhood.tolist())
    def test_selection_limits_map_not_top_ten(self):
        _a, top10, shown = calcular_exploracao(self.data,["Distrito 078"],"",["Segurança"])
        self.assertEqual(len(shown),1)
        self.assertEqual(len(top10),10)
    def test_zone_filters_both_rank_and_map(self):
        zones=lambda row: "Norte" if int(row.neighborhood[-3:])%2==0 else "Sul"
        _a,top10,shown=calcular_exploracao(self.data,[],"",[],zona="Norte",identificar_zona=zones)
        self.assertEqual(len(shown),48)
        self.assertEqual(top10.iloc[0].neighborhood,"Distrito 000")
    def test_explore_page_uses_shared_rule(self):
        text=(BASE/'pages/explorar.py').read_text(encoding='utf-8')
        ast.parse(text)
        self.assertIn('calcular_exploracao(',text)
        self.assertNotIn('st.session_state[_SELECTION_KEY] = initial_scored',text)

if __name__ == '__main__': unittest.main()
