"""Smoke test do snapshot publico existente. Nenhum CSV sera modificado."""
from __future__ import annotations

from pathlib import Path
import unittest

import pandas as pd
from bairroiq.ux_labels import nome_perfil
from bairroiq.ranking_ux import resumo_perfis, top10_filtrado, selecionar_comparacao

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "public_consumer_v2.csv"


@unittest.skipUnless(CSV.is_file(), "Snapshot publico deve estar disponivel no repositorio completo")
class SnapshotPerfisV3Tests(unittest.TestCase):
    def test_96_districts_nine_profiles_no_missing_labels(self):
        frame = pd.read_csv(CSV)
        self.assertEqual(len(frame), 96)
        self.assertEqual(frame["cd_dist"].nunique(), 96)
        self.assertEqual(frame["perfil_id"].nunique(), 9)
        self.assertEqual(frame["cluster"].map(nome_perfil).nunique(), 9)
        self.assertFalse(frame["cluster"].map(nome_perfil).isna().any())
        self.assertEqual(len(frame.columns), 15)

    def test_profile_summary_and_top10_on_real_snapshot(self):
        frame = pd.read_csv(CSV)
        frame["priority_score"] = frame[[
            "safety_score", "mobility_score", "green_leisure_score", "public_services_score",
        ]].mean(axis=1)
        frame = frame.sort_values("priority_score", ascending=False, kind="stable")
        result = resumo_perfis(frame)
        self.assertEqual(len(result), 9)
        self.assertEqual(int(result["Distritos"].sum()), 96)
        top = top10_filtrado(frame)
        self.assertEqual(len(top), 10)
        compare, automatic = selecionar_comparacao(frame, [])
        self.assertTrue(automatic)
        self.assertEqual(compare["neighborhood"].tolist(), top["neighborhood"].tolist())


if __name__ == "__main__":
    unittest.main()
