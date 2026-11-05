"""Testes offline 100% sintéticos do contrato Frontend v1 do BairroIQ."""
from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "barrioiq_pipeline/frontend_v1_runner.py"
spec = importlib.util.spec_from_file_location("bairroiq_frontend_v1_test", str(FILE))
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)
SID = frontend.SNAPSHOT


def fixture() -> dict[str, pd.DataFrame]:
    codes = np.arange(355030801, 355030897, dtype="int64")
    names = [f"Distrito Teste {i:02d}" for i in range(96)]
    categories = [f"kmeans-k09-p{i:02d}" for i in range(1, 10)]
    distribution = (9, 7, 6, 22, 7, 8, 12, 19, 6)
    assign = sum(([c] * n for c, n in zip(categories, distribution)), [])
    dist = pd.DataFrame({
        "snapshot_id": SID, "CD_DIST": codes, "NM_DIST": names,
        "latitude": np.linspace(-23.8, -23.4, 96),
        "longitude": np.linspace(-46.9, -46.4, 96),
    })
    perfis = pd.DataFrame({
        "snapshot_id": SID,
        "perfil_sk": [f"{SID}|{c}" for c in categories],
        "perfil_id": categories,
        "nome_exibicao_proposto": [f"Perfil sintético {i:02d}" for i in range(1, 10)],
        "disponivel_publicamente": False,
    })
    fp = pd.DataFrame({
        "snapshot_id": SID, "CD_DIST": codes,
        "perfil_sk": [f"{SID}|{c}" for c in assign],
    })
    io = pd.DataFrame({"snapshot_id": SID, "CD_DIST": codes,
                       "indice_ordenacao_ocorrencias": np.linspace(1.0, 99.0, 96)})
    ind = pd.DataFrame({"snapshot_id": SID,
                        "indicador_sk": [f"{SID}|{a}" for a in frontend.ALL_METRICS],
                        "indicador_id": list(frontend.ALL_METRICS)})
    facts = []
    for j, alias in enumerate(frontend.ALL_METRICS):
        for k, cd in enumerate(codes):
            facts.append({"snapshot_id": SID, "CD_DIST": cd,
                          "indicador_sk": f"{SID}|{alias}",
                          "valor_numerico": float(j * 20 + (k // 2) + 1)})
    fi = pd.DataFrame(facts)
    return {
        "dim_snapshot": pd.DataFrame([{
            "snapshot_id": SID, "sha256_gold": SID.split("|", 1)[1],
            "catalogo_versao": "v3.0.0-candidato", "status": frontend.STATUS,
            "disponivel_publicamente": False,
        }]),
        "dim_distrito": dist, "dim_perfil": perfis,
        "dim_indicador": ind, "fato_distrito_indicador": fi,
        "fato_distrito_perfil": fp, "fato_prioridade_ocorrencias": io,
        "gold_led": pd.DataFrame({"CD_DIST": codes, "led_pct": np.linspace(90, 100, 96)}),
    }


class TestFrontendV1(unittest.TestCase):
    def setUp(self):
        self.f = fixture()

    def build(self):
        return frontend.build_from_frames(self.f)

    def test_exact_eight_visual_columns(self):
        out = self.build()
        self.assertEqual(list(out["visual"].columns), list(frontend.VISUAL_COLUMNS))
        self.assertEqual(out["visual"].shape, (96, 8))

    def test_technical_schema_and_types(self):
        out = self.build()
        self.assertEqual(list(out["tecnico"].columns), list(frontend.TECH_COLUMNS))
        self.assertEqual(out["tecnico"].cd_dist.nunique(), 96)

    def test_nine_clusters(self):
        out = self.build()
        self.assertEqual(out["tecnico"].cluster.nunique(), 9)
        self.assertTrue(out["tecnico"].cluster.str.startswith("P0").all())

    def test_no_arborization_fabricated(self):
        out = self.build()
        self.assertTrue(out["visual"]["Arborização"].isna().all())

    def test_no_publication(self):
        out = self.build()
        self.assertTrue(out["tecnico"].publicacao_autorizada.eq(False).all())
        self.assertFalse(out["resumo"]["escrita_executada"])

    def test_led_coverage(self):
        self.assertEqual(self.build()["resumo"]["indicadores_led_preenchidos"], 96)

    def test_empregos_percent_rank_with_ties(self):
        series = pd.Series([5, 5, 8, 10], dtype=float)
        self.assertEqual(frontend.percentile_rank(series).round(2).tolist(), [0.0, 0.0, 66.67, 100.0])

    def test_roubos_unit_is_per_thousand(self):
        out = self.build()["tecnico"]
        self.assertAlmostEqual(float(out.iloc[0].roubos), 0.21, places=2)

    def test_security_is_inverse_not_predictive(self):
        out = self.build()["tecnico"]
        self.assertAlmostEqual(float(out.iloc[0].seguranca), 99.0, places=1)
        self.assertIn("não mede segurança geral", frontend.METADATA["Segurança"]["definicao"])

    def test_spark_round_half_up_for_security_tie(self):
        self.assertEqual(frontend.inverse_priority(1.15), 98.9)
        self.assertEqual(frontend.round_like_spark(1.25, 1), 1.3)

    def test_led_lineage_explicit(self):
        r = self.build()["resumo"]
        self.assertIn("distritos_wide", r["led_origem"])
        self.assertIn("fixar versão", r["led_versao_dado"])

    def test_district_not_real_estate_neighborhood(self):
        self.assertTrue(self.build()["tecnico"].tipo_territorio.eq("DISTRITO_IBGE").all())

    def test_reject_source_snapshot_drift(self):
        self.f["dim_perfil"].loc[0, "snapshot_id"] = "outro"
        with self.assertRaisesRegex(frontend.FrontendContractError, "snapshot errado"):
            self.build()

    def test_reject_public_catalogue(self):
        self.f["dim_snapshot"].loc[0, "disponivel_publicamente"] = True
        with self.assertRaisesRegex(frontend.FrontendContractError, "público"):
            self.build()

    def test_reject_duplicate_gold_led(self):
        self.f["gold_led"].loc[0, "CD_DIST"] = self.f["gold_led"].loc[1, "CD_DIST"]
        with self.assertRaisesRegex(frontend.FrontendContractError, "chave duplicada"):
            self.build()

    def test_reject_bad_led_range(self):
        self.f["gold_led"].loc[0, "led_pct"] = 103.0
        with self.assertRaisesRegex(frontend.FrontendContractError, "LED fora"):
            self.build()

    def test_reject_missing_led(self):
        self.f["gold_led"].loc[0, "led_pct"] = None
        with self.assertRaisesRegex(frontend.FrontendContractError, "nulo"):
            self.build()

    def test_reject_missing_fact(self):
        self.f["fato_distrito_indicador"] = self.f["fato_distrito_indicador"].iloc[:-1]
        with self.assertRaisesRegex(frontend.FrontendContractError, "cardinalidade"):
            self.build()

    def test_reject_bad_profile_fk(self):
        self.f["fato_distrito_perfil"].loc[0, "perfil_sk"] = "inexistente"
        with self.assertRaises(ValueError):
            self.build()

    def test_reject_incorrect_robbery_rates(self):
        fi = self.f["fato_distrito_indicador"]
        fi.loc[fi.indicador_sk.eq(f"{SID}|roubos"), "valor_numerico"] = -1
        with self.assertRaisesRegex(frontend.FrontendContractError, "negativo"):
            self.build()

    def test_no_spark_writes_or_views(self):
        script = ast.parse(FILE.read_text(encoding="utf-8"))
        forbidden = ("saveAsTable", "insertInto", "writeTo", "createOrReplaceTempView", "createOrReplaceGlobalTempView")
        for node in ast.walk(script):
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, forbidden)

    def test_distrito_visual_label_and_technical_field(self):
        result = self.build()
        self.assertEqual(result["visual"].columns[0], "Distrito")
        self.assertIn("distrito", result["tecnico"].columns)
        self.assertNotIn("bairro", result["tecnico"].columns)
        self.assertNotIn("Bairro", result["visual"].columns)
        self.assertEqual(
            result["visual"]["Distrito"].tolist(),
            result["tecnico"]["distrito"].tolist(),
        )

    def test_metadata_covers_all_indicators_except_distrito(self):
        self.assertEqual(set(frontend.METADATA), set(frontend.VISUAL_COLUMNS) - {"Distrito"})


if __name__ == "__main__":
    unittest.main()
