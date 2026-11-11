"""Regressão dos filtros compartilhados, seleção opcional e nomes dos perfis."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

import pandas as pd
from bairroiq.ranking_ux import ranking_filtrado, top10_filtrado, selecionar_comparacao, resumo_perfis

ROOT = Path(__file__).resolve().parents[1]


class RankingUxTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame([
            {
                "neighborhood": f"Distrito {i:03d}",
                "priority_score": float(100-i),
                "safety_score": float(i),
                "mobility_score": float(i),
                "green_leisure_score": float(i),
                "public_services_score": float(i),
                "formal_jobs_score": float(i),
                "cluster": (
                    "P01 — Mais Praças, Vida Urbana" if i % 2 == 0
                    else "P04 — Menos Roubos e Furtos"
                ),
                "perfil_id": "kmeans-k09-p01" if i % 2 == 0 else "kmeans-k09-p04",
                "densidade_hab_km2": 15000.0,
                "robberies_per_1000": 1.7,
            }
            for i in range(96)
        ])

    def test_unfiltered_top_ten(self):
        top = top10_filtrado(ranking_filtrado(self.data))
        self.assertEqual(len(top), 10)
        self.assertEqual(top.iloc[0]["neighborhood"], "Distrito 000")

    def test_quick_filter_changes_top_ten(self):
        restricted = ranking_filtrado(self.data, filtros=["Segurança"])
        top = top10_filtrado(restricted)
        self.assertLessEqual(len(top), 10)
        self.assertNotIn("Distrito 000", top["neighborhood"].tolist())

    def test_perfil_filter_changes_top_ten(self):
        restricted = ranking_filtrado(self.data, perfil="Menos Roubos e Furtos")
        self.assertEqual(len(restricted), 48)
        self.assertEqual(restricted.iloc[0]["neighborhood"], "Distrito 001")
        self.assertEqual(len(top10_filtrado(restricted)), 10)

    def test_zero_selected_returns_filtered_top_ten(self):
        eligible = ranking_filtrado(self.data, perfil="Menos Roubos e Furtos")
        result, automatic = selecionar_comparacao(eligible, [])
        self.assertTrue(automatic)
        self.assertEqual(len(result), 10)
        self.assertEqual(result.iloc[0]["neighborhood"], "Distrito 001")

    def test_between_one_and_ten_selected(self):
        eligible = ranking_filtrado(self.data)
        for number in (1, 2, 5, 10):
            selected = eligible.head(number)["neighborhood"].tolist()
            result, automatic = selecionar_comparacao(eligible, selected)
            self.assertFalse(automatic)
            self.assertEqual(len(result), number)
        with self.assertRaisesRegex(ValueError, "até dez"):
            selecionar_comparacao(eligible, eligible.head(11)["neighborhood"].tolist())

    def test_selected_outside_filter_does_not_reappear(self):
        eligible = ranking_filtrado(self.data, perfil="Menos Roubos e Furtos")
        comparison, _ = selecionar_comparacao(eligible, ["Distrito 000", "Distrito 001"])
        self.assertEqual(comparison["neighborhood"].tolist(), ["Distrito 001"])

    def test_profile_summary_uses_commercial_names(self):
        profiles = resumo_perfis(ranking_filtrado(self.data))
        self.assertEqual(set(profiles["Perfil de Distrito"]), {
            "Mais Praças, Vida Urbana", "Menos Roubos e Furtos",
        })
        self.assertEqual(int(profiles["Distritos"].sum()), 96)

    def test_home_no_zone_cards_and_has_profiles(self):
        source = (ROOT / "pages/iniciar.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("### Perfis de Distrito", source)
        self.assertIn("top10_filtrado(filtered)", source)
        self.assertNotIn("Distritos por zona", source)
        self.assertNotIn("zone-card-", source)


if __name__ == "__main__":
    unittest.main()
