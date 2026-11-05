"""BairroIQ: prioridade por roubos/furtos e nome condicional P04 (dados sinteticos)."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PRIORITY_SCRIPT = BASE / "barrioiq_pipeline" / "prioridade_roubos_furtos_v1.py"
spec = importlib.util.spec_from_file_location("bairroiq_priority_test", str(PRIORITY_SCRIPT))
priority = importlib.util.module_from_spec(spec)
spec.loader.exec_module(priority)

# Fixtures e configuracao deliberadamente artificiais da mesma suite v3.
from test_ml_catalogo_perfis_v3 import fixture, config_for_fixture, NONEXISTENT_REFERENCE


def synthetic_audit_frame():
    codes = list(range(355030801, 355030897))
    return pd.DataFrame({
        "CD_DIST": codes,
        "NM_DIST": [f"D{i}" for i in range(96)],
        "roubos": [10.] * 22 + [100.] * 74,
        "furtos": [20.] * 22 + [200.] * 74,
    })


class TestCrimeAudit(unittest.TestCase):
    def test_p04_both_rates_really_below(self):
        data = synthetic_audit_frame()
        result = priority.audit_p04(data, data.CD_DIST.iloc[:22].tolist())
        self.assertTrue(result["condicao_editorial_atendida"])
        self.assertFalse(result["nome_homologado"])
        self.assertEqual(result["distritos_ambos_abaixo_mediana_96"], 22)

    def test_p04_reject_when_one_rate_high(self):
        data = synthetic_audit_frame()
        data.loc[:21, "furtos"] = 300.
        result = priority.audit_p04(data, data.CD_DIST.iloc[:22].tolist())
        self.assertFalse(result["condicao_editorial_atendida"])

    def test_p04_reject_when_disjoint_below_medians(self):
        data = synthetic_audit_frame()
        data.loc[:10, "furtos"] = 300.
        data.loc[11:21, "roubos"] = 300.
        result = priority.audit_p04(data, data.CD_DIST.iloc[:22].tolist())
        self.assertFalse(result["condicao_editorial_atendida"])
        self.assertEqual(result["distritos_ambos_abaixo_mediana_96"], 0)

    def test_p04_reject_invalid_data(self):
        data = synthetic_audit_frame()
        data.loc[0, "roubos"] = np.nan
        with self.assertRaisesRegex(ValueError, "nulas"):
            priority.audit_p04(data, data.CD_DIST.iloc[:22].tolist())
        data = synthetic_audit_frame()
        data.loc[0, "furtos"] = -1
        with self.assertRaisesRegex(ValueError, "negativas"):
            priority.audit_p04(data, data.CD_DIST.iloc[:22].tolist())

    def test_reject_partial_or_duplicate_districts(self):
        data = synthetic_audit_frame()
        with self.assertRaisesRegex(ValueError, "96 distritos"):
            priority.audit_p04(data.iloc[:-1], data.CD_DIST.iloc[:22].tolist())
        data.loc[1, "CD_DIST"] = data.loc[0, "CD_DIST"]
        with self.assertRaisesRegex(ValueError, "repetido"):
            priority.audit_p04(data, data.CD_DIST.iloc[:22].tolist())


class TestPriorityPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()
        cls.config = config_for_fixture(cls.raw)
        cls.results = priority.build_priority(
            cls.raw, config=cls.config, reference=NONEXISTENT_REFERENCE
        )

    def test_ranks_every_district_exactly_once(self):
        frame = self.results["distritos_priorizados"]
        self.assertEqual(len(frame), 96)
        self.assertEqual(frame.CD_DIST.nunique(), 96)
        self.assertEqual(sorted(frame.posicao_relativa_entre_96), list(range(1, 97)))
        self.assertEqual(frame.perfil_id.nunique(), 9)
        self.assertTrue(frame.roubos.notna().all() and frame.furtos.notna().all())

    def test_rank_direction_low_rates_first(self):
        data = self.results["distritos_priorizados"]
        low = data.iloc[0]
        self.assertTrue((data.indice_ordenacao_ocorrencias.diff().dropna() >= -1e-9).all())
        self.assertEqual(int(low.posicao_relativa_entre_96), 1)
        self.assertGreaterEqual(low.roubos, 0)
        self.assertGreaterEqual(low.furtos, 0)

    def test_independent_profile_filter_preserves_global_ranking(self):
        result = self.results
        pid = result["catalogo"].perfil_id.iloc[0]
        filtered = priority.filter_priority(result, perfil_id=pid, limit=None)
        original = result["distritos_priorizados"]
        self.assertEqual(len(filtered), int((original.perfil_id == pid).sum()))
        self.assertTrue(filtered.perfil_id.eq(pid).all())
        orig_positions = original.set_index("CD_DIST").posicao_relativa_entre_96
        for _, item in filtered.iterrows():
            self.assertEqual(item.posicao_relativa_entre_96, orig_positions[item.CD_DIST])
        self.assertTrue(priority.filter_priority(result, limit=5).shape[0] == 5)

    def test_unknown_profile_blocks(self):
        with self.assertRaisesRegex(ValueError, "Perfil desconhecido"):
            priority.filter_priority(self.results, perfil_id="inexistente")
        with self.assertRaisesRegex(ValueError, "Limite invalido"):
            priority.filter_priority(self.results, limit=0)

    def test_no_auto_publication(self):
        self.assertFalse(self.results["resumo"]["publicacao_gold_autorizada"])
        self.assertEqual(self.results["resumo"]["status"], priority.STATUS)
        self.assertEqual(self.results["resumo"]["alteracoes_gold"], "NENHUMA")
        self.assertTrue(self.results["catalogo"].nome_validado_para_publicacao.eq(False).all())
        self.assertTrue(self.results["distritos_priorizados"].status_prioridade.eq(priority.STATUS).all())
        self.assertNotIn("nota_seguranca", self.results["distritos_priorizados"].columns)

    def test_determinism(self):
        result = priority.build_priority(
            self.raw.sample(frac=1, random_state=10), config=self.config,
            reference=NONEXISTENT_REFERENCE
        )
        pd.testing.assert_frame_equal(
            result["distritos_priorizados"], self.results["distritos_priorizados"]
        )

    def test_config_name_alternate_is_conditional(self):
        # Nome comercial nunca pode ser aprovado somente pela existencia no JSON.
        cat = self.results["catalogo"]
        p04 = cat.loc[cat.perfil_id == priority.P04_ID].iloc[0]
        audit = self.results["auditoria_p04"]
        if audit["condicao_editorial_atendida"]:
            self.assertEqual(p04.nome_exibicao_proposto, "Menos Roubos e Furtos")
        else:
            self.assertNotEqual(p04.nome_exibicao_proposto, "Menos Roubos e Furtos")
        self.assertFalse(p04.nome_validado_para_publicacao)

    def test_hash_guard(self):
        changed = self.raw.copy()
        changed.loc[0, "furtos"] += 5
        with self.assertRaisesRegex(ValueError, "Hash da Gold mudou"):
            priority.build_priority(changed, config=self.config,
                                    reference=NONEXISTENT_REFERENCE)

    def test_local_export_only(self):
        with tempfile.TemporaryDirectory() as directory:
            priority.export(self.results, directory)
            names = sorted(x.name for x in Path(directory).iterdir())
            self.assertEqual(names, sorted([
                "catalogo_com_prioridade_ocorrencias.csv",
                "distritos_prioridade_ocorrencias.csv",
                "auditoria_nome_p04.json",
                "resumo_prioridade_ocorrencias.json",
            ]))
            obj = json.loads((Path(directory) / "auditoria_nome_p04.json").read_text(encoding="utf-8"))
            self.assertIn("condicao_editorial_atendida", obj)


if __name__ == "__main__":
    unittest.main()
