"""Testes offline do conector Databricks para o contrato Consumer V2.

Os dados são sintéticos: não requer credenciais ou consulta ao Databricks.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import pandas as pd

from bairroiq.consumer_v2 import SNAPSHOT
from bairroiq.databricks import DatabricksConfig, DatabricksDataProvider


def _fixture(*, authorized: bool = False) -> pd.DataFrame:
    """Simula exatamente 96 distritos e nove perfis válidos."""
    rows = []
    for index in range(96):
        profile_number = index % 9 + 1
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
            "perfil_id": f"kmeans-k09-p{profile_number:02d}",
            "cluster": f"P{profile_number:02d} — Perfil Sintético",
            "tipo_territorio": "DISTRITO_IBGE",
            "publicacao_autorizada": authorized,
            "contagem_indicadores_extra": 5,
            "indicadores_extra_distintos": 5,
        })
    return pd.DataFrame(rows)


class DatabricksConfigTests(unittest.TestCase):
    def test_config_uses_app_warehouse_resource_and_default_table(self) -> None:
        config = DatabricksConfig.from_sources(
            environ={
                "DATABRICKS_HOST": "https://workspace.example.com",
                "DATABRICKS_WAREHOUSE_ID": "warehouse-123",
            }
        )
        self.assertEqual(config.server_hostname, "workspace.example.com")
        self.assertEqual(config.http_path, "/sql/1.0/warehouses/warehouse-123")
        self.assertEqual(
            config.metrics_table, "`workspace`.`gold`.`bairroiq_frontend_v1`"
        )
        self.assertIsNone(config.access_token)

    def test_config_supports_local_secrets_and_table_override(self) -> None:
        config = DatabricksConfig.from_sources(
            {
                "databricks": {
                    "server_hostname": "workspace.example.com",
                    "http_path": "/sql/1.0/warehouses/demo",
                    "access_token": "local-test-token",
                    "metrics_table": "analytics.frontend",
                }
            },
            environ={},
        )
        self.assertEqual(config.metrics_table, "`analytics`.`frontend`")
        self.assertEqual(config.access_token, "local-test-token")

    def test_table_names_reject_sql_fragments(self) -> None:
        with self.assertRaisesRegex(ValueError, "identificadores SQL"):
            DatabricksConfig.from_sources(
                environ={
                    "DATABRICKS_HOST": "workspace.example.com",
                    "DATABRICKS_WAREHOUSE_ID": "demo",
                    "DATABRICKS_METRICS_TABLE": "metrics; DROP TABLE users",
                }
            )


class DatabricksDataProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = DatabricksDataProvider(
            DatabricksConfig(
                "workspace.example.com",
                "/sql/1.0/warehouses/demo",
                "`workspace`.`gold`.`bairroiq_frontend_v1`",
            )
        )

    def test_published_data_uses_real_indicators(self) -> None:
        raw = _fixture(authorized=True)
        captured = {}

        def read(query: str) -> pd.DataFrame:
            captured["query"] = query
            return raw.copy()

        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", side_effect=read):
                metrics = self.provider.load_metrics()
        self.assertEqual(len(metrics), 96)
        self.assertEqual(metrics["perfil_id"].nunique(), 9)
        self.assertEqual(metrics["green_leisure_score"].iloc[0], 60.0)
        self.assertEqual(metrics["public_services_score"].iloc[0], 55.0)
        self.assertEqual(metrics["robbery_index"].iloc[0], 2.5)
        self.assertTrue(metrics["district_code"].equals(metrics["cd_dist"]))
        self.assertFalse(metrics.isna().any().any())
        self.assertIn("AND publicacao_autorizada IS TRUE", captured["query"])
        self.assertNotIn("CAST(NULL", captured["query"])

    def test_internal_preview_requires_explicit_opt_in(self) -> None:
        raw = _fixture(authorized=False)
        captured = {}

        def read(query: str) -> pd.DataFrame:
            captured["query"] = query
            return raw.copy()

        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "true"}):
            with patch.object(self.provider, "_read_query", side_effect=read):
                metrics = self.provider.load_metrics()
        self.assertEqual(len(metrics), 96)
        self.assertFalse(metrics["publicacao_autorizada"].any())
        self.assertNotIn("AND publicacao_autorizada IS TRUE", captured["query"])

    def test_unpublished_data_blocked_by_default(self) -> None:
        raw = _fixture(authorized=False)
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", return_value=raw):
                with self.assertRaises(PermissionError):
                    self.provider.load_metrics()

    def test_empty_published_snapshot_is_reported(self) -> None:
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", return_value=pd.DataFrame()):
                with self.assertRaisesRegex(ValueError, "publicacao_autorizada"):
                    self.provider.load_metrics()

    def test_invalid_data_are_rejected(self) -> None:
        raw = _fixture(authorized=True)
        raw.loc[0, "safety_score"] = 150.0
        with patch.dict(os.environ, {"BAIRROIQ_INTERNAL_PREVIEW": "false"}):
            with patch.object(self.provider, "_read_query", return_value=raw):
                with self.assertRaisesRegex(ValueError, "0-100"):
                    self.provider.load_metrics()

    def test_history_is_empty_without_actual_time_series(self) -> None:
        history = self.provider.load_history()
        self.assertEqual(len(history), 0)
        self.assertIn("year", history.columns)

    def test_oauth_connection_uses_app_service_principal_if_sdk_available(self) -> None:
        try:
            from databricks import sql
            from databricks.sdk.core import Config
        except ImportError:
            self.skipTest("O SDK Databricks não está instalado neste ambiente")
        with (
            patch.object(sql, "connect", return_value=None) as connect,
            patch.object(Config, "__init__", return_value=None) as config_init,
            patch.object(
                Config, "authenticate", create=True,
                new_callable=unittest.mock.PropertyMock,
            ),
        ):
            self.provider._connect()
        config_init.assert_called_once_with()
        self.assertTrue(callable(connect.call_args.kwargs["credentials_provider"]))
        self.assertNotIn("access_token", connect.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
