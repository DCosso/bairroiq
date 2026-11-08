"""Testes sintéticos do Consumer físico auditado e conector Databricks.

Rodar com: python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import pandas as pd

from bairroiq.consumer_v2 import SNAPSHOT
from bairroiq.databricks import (
    DatabricksConfig,
    DatabricksDataProvider,
    _EXPECTED_SQL_SHA256,
    _payload_sha256,
)


DISTRIBUTION = (9, 7, 6, 22, 7, 8, 12, 19, 6)


def fixture(*, authorized: bool = False) -> pd.DataFrame:
    rows = []
    for p, quantity in enumerate(DISTRIBUTION, start=1):
        for _ in range(quantity):
            index = len(rows)
            rows.append({
                "snapshot_id": SNAPSHOT,
                "cd_dist": 355030801 + index,
                "neighborhood": f"Distrito Sintético {index + 1:02d}",
                "latitude": -23.5 - index / 1000,
                "longitude": -46.5 - index / 1000,
                "formal_jobs_score": float(index),
                "safety_score": 50.0,
                "mobility_score": 70.0,
                "green_leisure_score": 60.0,
                "public_services_score": 55.0,
                "densidade_hab_km2": 1500.0 + index,
                "robberies_per_1000": 2.5,
                "perfil_id": f"kmeans-k09-p{p:02d}",
                "cluster": f"P{p:02d} — Perfil Sintético",
                "tipo_territorio": "DISTRITO_IBGE",
                "publicacao_autorizada": authorized,
            })
    df = pd.DataFrame(rows)
    df["versao_contrato"] = "frontend_v2.0.0"
    df["payload_sha256"] = _payload_sha256(df)
    df["sql_sha256"] = _EXPECTED_SQL_SHA256
    df["materializado_em_utc"] = pd.Timestamp("2026-11-08T16:00:00Z")
    return df


class DatabricksConfigTests(unittest.TestCase):
    def test_default_table_is_the_new_physical_consumer(self):
        c = DatabricksConfig.from_sources(environ={
            "DATABRICKS_HOST": "https://workspace.example.com",
            "DATABRICKS_WAREHOUSE_ID": "warehouse-123",
        })
        self.assertEqual(c.metrics_table, "`workspace`.`gold`.`bairroiq_frontend_v2`")
        self.assertEqual(c.server_hostname, "workspace.example.com")
        self.assertEqual(c.http_path, "/sql/1.0/warehouses/warehouse-123")
        self.assertIsNone(c.access_token)

    def test_secrets_and_table_override_still_work(self):
        c = DatabricksConfig.from_sources({
            "databricks": {
                "server_hostname": "workspace.example.com",
                "http_path": "/sql/1.0/warehouses/demo",
                "access_token": "local-test-token",
                "metrics_table": "analytics.frontend",
            }
        }, environ={})
        self.assertEqual(c.metrics_table, "`analytics`.`frontend`")
        self.assertEqual(c.access_token, "local-test-token")

    def test_rejects_sql_injection_table(self):
        with self.assertRaisesRegex(ValueError, "identificadores SQL"):
            DatabricksConfig.from_sources(environ={
                "DATABRICKS_HOST": "workspace.example.com",
                "DATABRICKS_WAREHOUSE_ID": "demo",
                "DATABRICKS_METRICS_TABLE": "metrics; DROP TABLE users",
            })


class DatabricksDataProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = DatabricksDataProvider(DatabricksConfig(
            "workspace.example.com", "/sql/1.0/warehouses/demo",
            "`workspace`.`gold`.`bairroiq_frontend_v2`",
        ))

    def test_private_authorized_preview_reads_audited_v2(self):
        raw = fixture(authorized=False)
        captured = {}

        def read(query):
            captured["query"] = query
            return raw.copy()

        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "true"}):
            with patch.object(self.provider, "_read_query", side_effect=read):
                metrics = self.provider.load_metrics()
        self.assertEqual(len(metrics), 96)
        self.assertEqual(metrics["perfil_id"].nunique(), 9)
        self.assertFalse(metrics.isna().any().any())
        self.assertEqual(metrics.iloc[0]["green_leisure_score"], 60.0)
        self.assertEqual(metrics.iloc[0]["public_services_score"], 55.0)
        self.assertEqual(metrics.iloc[0]["robbery_index"], 2.5)
        self.assertTrue(metrics["district_code"].equals(metrics["cd_dist"]))
        self.assertIn("`workspace`.`gold`.`bairroiq_frontend_v2`", captured["query"])
        self.assertNotIn("bairroiq_fato_distrito_indicador", captured["query"])
        self.assertNotIn("AND publicacao_autorizada IS TRUE", captured["query"])

    def test_published_mode_requires_publication_flag(self):
        raw = fixture(authorized=True)
        captured = {}

        def read(query):
            captured["query"] = query
            return raw.copy()

        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", side_effect=read):
                metrics = self.provider.load_metrics()
        self.assertEqual(len(metrics), 96)
        self.assertIn("AND publicacao_autorizada IS TRUE", captured["query"])

    def test_unpublished_data_blocked_by_default(self):
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", return_value=fixture()):
                with self.assertRaises(PermissionError):
                    self.provider.load_metrics()

    def test_empty_table_result_raises(self):
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", return_value=pd.DataFrame()):
                with self.assertRaisesRegex(ValueError, "sem registros acessíveis"):
                    self.provider.load_metrics()

    def test_detects_payload_tampering(self):
        raw = fixture()
        raw.loc[0, "mobility_score"] = 30.0
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "true"}):
            with patch.object(self.provider, "_read_query", return_value=raw):
                with self.assertRaisesRegex(ValueError, "Hash do conteúdo divergente"):
                    self.provider.load_metrics()

    def test_detects_sql_hash_tampering(self):
        raw = fixture()
        raw["sql_sha256"] = "0" * 64
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "true"}):
            with patch.object(self.provider, "_read_query", return_value=raw):
                with self.assertRaisesRegex(ValueError, "Hash SQL"):
                    self.provider.load_metrics()

    def test_detects_audit_row_divergence(self):
        raw = fixture()
        raw.loc[0, "versao_contrato"] = "v2.0.1"
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "true"}):
            with patch.object(self.provider, "_read_query", return_value=raw):
                with self.assertRaisesRegex(ValueError, "Auditoria incompleta"):
                    self.provider.load_metrics()

    def test_detects_missing_metrics(self):
        raw = fixture().drop(columns=["green_leisure_score"])
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "true"}):
            with patch.object(self.provider, "_read_query", return_value=raw):
                with self.assertRaisesRegex(ValueError, "Faltam colunas"):
                    self.provider.load_metrics()

    def test_does_not_synthesize_history(self):
        h = self.provider.load_history()
        self.assertEqual(len(h), 0)
        self.assertIn("year", h.columns)

    def test_oauth_connection_uses_service_principal_when_sdk_available(self):
        try:
            from databricks import sql
            from databricks.sdk.core import Config
        except ImportError:
            self.skipTest("SDK Databricks não instalado neste ambiente")
        with (
            patch.object(sql, "connect", return_value=None) as connect,
            patch.object(Config, "__init__", return_value=None) as cinit,
            patch.object(
                Config, "authenticate", create=True,
                new_callable=unittest.mock.PropertyMock,
            ),
        ):
            self.provider._connect()
        cinit.assert_called_once_with()
        self.assertTrue(callable(connect.call_args.kwargs["credentials_provider"]))
        self.assertNotIn("access_token", connect.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
