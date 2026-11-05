"""Testes sintéticos do materializador; nenhum Spark/Databricks real é chamado."""
from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "barrioiq_pipeline" / "frontend_v1_delta_runner.py"
spec = importlib.util.spec_from_file_location("bairroiq_frontend_v1_delta_test", MODULE)
delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delta)


def synthetic_result():
    rows = []
    for i in range(96):
        pid = f"kmeans-k09-p{(i % 9) + 1:02d}"
        rows.append({
            "snapshot_id": delta.SNAPSHOT_ID, "cd_dist": 355030801+i,
            "distrito": f"Distrito Fictício {i:02d}",
            "latitude": -23.75 + i / 1000, "longitude": -46.85 + i / 1000,
            "perfil_id": pid, "cluster": f"P{(i%9)+1:02d} — Perfil sintético {(i%9)+1:02d}",
            "empregos": round(i * 100 / 95, 1),
            "roubos": round(0.1 + i / 20, 2),
            "seguranca": round(100 - i * 100 / 95, 1),
            "mobilidade": round((i % 17) * 100 / 16, 1),
            "tipo_territorio": "DISTRITO_IBGE", "publicacao_autorizada": False,
        })
    technical = pd.DataFrame(rows)[list(delta.FIELDS)]
    visual = technical.rename(columns={
        "distrito": "Distrito", "empregos": "Empregos", "roubos": "Roubos",
        "seguranca": "Segurança", "mobilidade": "Mobilidade", "cluster": "Cluster",
    })[list(delta.VISUAL)]
    return {"visual": visual, "tecnico": technical,
            "resumo": {"snapshot_id": delta.SNAPSHOT_ID, "status": delta.STATUS,
                        "distritos": 96, "clusters": 9, "colunas_visuais": 6,
                        "publicacao_autorizada": False, "escrita_executada": False,
                        "alteracoes_gold": "NENHUMA"}}


class FakeWriter:
    def __init__(self, spark, rows):
        self.spark = spark
        self.rows = rows
    def format(self, typ):
        assert typ == "delta"
        return self
    def mode(self, name):
        assert name == "append"
        return self
    def saveAsTable(self, name):
        assert name == delta.TARGET
        self.spark.saved.extend(copy.deepcopy(self.rows))
        self.spark.operations.append(name)


class FakeSpark:
    def __init__(self):
        self.saved = []
        self.created = False
        self.operations = []
        self.catalog = self
    def tableExists(self, name):
        assert name == delta.TARGET
        return self.created
    def createDataFrame(self, rows, schema):
        self.created = True
        return type("FakeDataFrame", (), {"write": FakeWriter(self, rows)})()


class TestFrontendDelta(unittest.TestCase):
    def setUp(self):
        self.result = synthetic_result()
        self.payload = delta.prepare_payload(self.result)

    def test_contract_exact_six_thirteen_columns(self):
        self.assertEqual(len(delta.SCHEMA), 13)
        self.assertEqual(len(delta.VISUAL), 6)
        self.assertEqual(self.payload["rows_expected"], 96)
        self.assertEqual(len(self.payload["rows"]), 96)

    def test_hash_stable_against_row_order(self):
        direct = self.payload["payload_sha256"]
        backwards = delta.content_hash(list(reversed(self.payload["rows"])))
        self.assertEqual(direct, backwards)

    def test_hash_changes_if_a_value_changes(self):
        changed = copy.deepcopy(self.payload["rows"])
        changed[0]["roubos"] = changed[0]["roubos"] + 0.01
        self.assertNotEqual(self.payload["payload_sha256"], delta.content_hash(changed))

    def test_reject_wrong_snapshot(self):
        self.result["resumo"]["snapshot_id"] = "outro"
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Snapshot/status"):
            delta.prepare_payload(self.result)

    def test_reject_public_summary(self):
        self.result["resumo"]["publicacao_autorizada"] = True
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "publicação"):
            delta.prepare_payload(self.result)

    def test_reject_public_row(self):
        self.result["tecnico"].loc[0, "publicacao_autorizada"] = True
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Visual/técnico|Território/publicação"):
            delta.prepare_payload(self.result)

    def test_reject_duplicated_district(self):
        self.result["tecnico"].loc[0, "cd_dist"] = self.result["tecnico"].loc[1, "cd_dist"]
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "duplicados"):
            delta.prepare_payload(self.result)

    def test_reject_mixed_snapshot(self):
        self.result["tecnico"].loc[0, "snapshot_id"] = "diferente"
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Mistura"):
            delta.prepare_payload(self.result)

    def test_reject_visual_mismatch(self):
        self.result["visual"].loc[0, "Roubos"] += 0.2
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Visual/técnico"):
            delta.prepare_payload(self.result)

    def test_reject_led_column(self):
        self.result["visual"]["Iluminação LED"] = 100
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Contrato visual"):
            delta.prepare_payload(self.result)

    def test_reject_out_of_range(self):
        self.result["tecnico"].loc[0, "mobilidade"] = 101
        self.result["visual"].loc[0, "Mobilidade"] = 101
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "fora de 0-100"):
            delta.prepare_payload(self.result)

    def test_reject_negative_robbery_rate(self):
        self.result["tecnico"].loc[0, "roubos"] = -1
        self.result["visual"].loc[0, "Roubos"] = -1
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "negativa"):
            delta.prepare_payload(self.result)

    def test_reject_invalid_coordinates(self):
        self.result["tecnico"].loc[0, "latitude"] = -15.0
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Coordenadas"):
            delta.prepare_payload(self.result)

    def test_reject_invalid_cluster_assignment(self):
        mask = self.result["tecnico"]["perfil_id"].eq("kmeans-k09-p01")
        self.result["tecnico"].loc[mask, "cluster"] = "P09 — Erro"
        self.result["visual"].loc[mask, "Cluster"] = "P09 — Erro"
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "Perfil/cluster"):
            delta.prepare_payload(self.result)

    def test_reject_nulled_metric(self):
        self.result["tecnico"].loc[0, "empregos"] = None
        self.result["visual"].loc[0, "Empregos"] = None
        with self.assertRaisesRegex(delta.ConsumerDeltaError, "NULL"):
            delta.prepare_payload(self.result)

    def test_inspect_absent_is_readonly(self):
        fake = FakeSpark()
        plan = delta.inspect(fake, self.payload)
        self.assertEqual(plan["rows_in_snapshot"], 0)
        self.assertEqual(plan["action_if_applied"], "APPEND_SNAPSHOT")
        self.assertFalse(plan["will_write_on_check"])
        self.assertEqual(fake.operations, [])

    def test_check_never_writes(self):
        fake = FakeSpark()
        with patch.object(delta, "_load_consumer", return_value=self.result):
            plan = delta.check(fake)
        self.assertFalse(plan["will_write_on_check"])
        self.assertEqual(fake.operations, [])
        self.assertEqual(plan["payload_sha256"], self.payload["payload_sha256"])

    def test_existing_identical_is_verified(self):
        fake = FakeSpark()
        fake.created = True
        fake.saved = copy.deepcopy(self.payload["rows"])
        with patch.object(delta, "_validate_existing_table"), \
             patch.object(delta, "_load_existing_rows", side_effect=lambda sp: sp.saved):
            plan = delta.inspect(fake, self.payload)
        self.assertEqual(plan["action_if_applied"], "KEEP_VERIFIED")
        self.assertEqual(plan["rows_in_snapshot"], 96)

    def test_existing_divergent_blocks(self):
        fake = FakeSpark()
        fake.created = True
        fake.saved = copy.deepcopy(self.payload["rows"])
        fake.saved[0]["roubos"] = 6000
        with patch.object(delta, "_validate_existing_table"), \
             patch.object(delta, "_load_existing_rows", side_effect=lambda sp: sp.saved):
            with self.assertRaisesRegex(delta.ConsumerDeltaError, "Conteúdo existente"):
                delta.inspect(fake, self.payload)

    def test_existing_partial_blocks(self):
        fake = FakeSpark()
        fake.created = True
        fake.saved = copy.deepcopy(self.payload["rows"][:60])
        with patch.object(delta, "_validate_existing_table"), \
             patch.object(delta, "_load_existing_rows", side_effect=lambda sp: sp.saved):
            with self.assertRaisesRegex(delta.ConsumerDeltaError, "parcialmente"):
                delta.inspect(fake, self.payload)

    def test_existing_foreign_snapshot_blocks(self):
        fake = FakeSpark()
        fake.created = True
        fake.saved = copy.deepcopy(self.payload["rows"])
        fake.saved[0]["snapshot_id"] = "outra-versao"
        with patch.object(delta, "_validate_existing_table"), \
             patch.object(delta, "_load_existing_rows", side_effect=lambda sp: sp.saved):
            with self.assertRaisesRegex(delta.ConsumerDeltaError, "Outro snapshot"):
                delta.inspect(fake, self.payload)

    def test_wrong_confirmation_blocks_before_io(self):
        fake = FakeSpark()
        with patch.object(delta, "_load_consumer", side_effect=AssertionError("não deve ler")):
            with self.assertRaisesRegex(delta.ConsumerDeltaError, "confirmação"):
                delta.apply_snapshot(fake, confirmation="SIM", expected_snapshot_id=delta.SNAPSHOT_ID,
                                     expected_payload_sha256=self.payload["payload_sha256"])
        self.assertEqual(fake.operations, [])

    def test_wrong_payload_hash_blocks_before_write(self):
        fake = FakeSpark()
        with patch.object(delta, "_load_consumer", return_value=self.result):
            with self.assertRaisesRegex(delta.ConsumerDeltaError, "Hash do payload"):
                delta.apply_snapshot(fake, confirmation=delta.CONFIRMATION,
                                     expected_snapshot_id=delta.SNAPSHOT_ID,
                                     expected_payload_sha256="b" * 64)
        self.assertEqual(fake.operations, [])

    def test_materialize_then_idempotent(self):
        fake = FakeSpark()
        with patch.object(delta, "_load_consumer", return_value=self.result), \
             patch.object(delta, "_validate_existing_table"), \
             patch.object(delta, "_load_existing_rows", side_effect=lambda sp: sp.saved), \
             patch.object(delta, "_schema_spark", return_value="fake-schema"):
            first = delta.apply_snapshot(fake, confirmation=delta.CONFIRMATION,
                                         expected_snapshot_id=delta.SNAPSHOT_ID,
                                         expected_payload_sha256=self.payload["payload_sha256"])
            self.assertEqual(first["action"], "MATERIALIZED_INTERNAL_FRONTEND_V1")
            self.assertFalse(first["published"])
            self.assertEqual(len(fake.saved), 96)
            second = delta.apply_snapshot(fake, confirmation=delta.CONFIRMATION,
                                          expected_snapshot_id=delta.SNAPSHOT_ID,
                                          expected_payload_sha256=self.payload["payload_sha256"])
            self.assertEqual(second["action"], "ALREADY_MATERIALIZED_AND_VERIFIED")
            self.assertEqual(fake.operations, [delta.TARGET])

    def test_no_forbidden_write_modes_or_automated_apply(self):
        source = MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "GRANT " not in source.upper() and "DROP TABLE" not in source.upper()
        assert 'mode("overwrite")' not in source
        fn = {x.name: x for x in tree.body if isinstance(x, ast.FunctionDef)}
        for name in ("check", "inspect"):
            self.assertFalse(any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {"_write_one", "apply_snapshot"}
                for node in ast.walk(fn[name])
            ))


if __name__ == "__main__":
    unittest.main()
