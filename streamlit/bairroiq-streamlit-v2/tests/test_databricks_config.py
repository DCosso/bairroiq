import unittest
from unittest.mock import patch

import pandas as pd

from bairroiq.databricks import DatabricksConfig, DatabricksDataProvider


class DatabricksConfigTests(unittest.TestCase):
    def test_config_uses_app_warehouse_resource_and_default_table(self) -> None:
        config = DatabricksConfig.from_sources(
            environ={
                "DATABRICKS_HOST": "https://workspace.example.com",
                "DATABRICKS_WAREHOUSE_ID": "warehouse-123",
            }
        )

        self.assertEqual(config.server_hostname, "workspace.example.com")
        self.assertEqual(
            config.http_path, "/sql/1.0/warehouses/warehouse-123"
        )
        self.assertEqual(
            config.metrics_table,
            "`workspace`.`gold`.`bairroiq_frontend_v1`",
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

        self.assertEqual(
            config.metrics_table, "`analytics`.`frontend`"
        )
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

    def test_query_maps_available_metrics_and_marks_missing_ones(self) -> None:
        columns = [
            "snapshot_id",
            "district_code",
            "neighborhood",
            "latitude",
            "longitude",
            "perfil_id",
            "cluster",
            "tipo_territorio",
            "formal_jobs_score",
            "robbery_index",
            "safety_score",
            "mobility_score",
            "lighting_led",
            "trees_score",
            "affordability_score",
        ]
        values = (
            "2026-10-01",
            1,
            "Sé",
            -23.55,
            -46.63,
            "perfil-1",
            "central",
            "denso",
            80.0,
            2.0,
            85.0,
            75.0,
            None,
            None,
            None,
        )

        class Cursor:
            description = [(column,) for column in columns]

            def execute(self, query: str) -> None:
                self.query = query

            def fetchall(self) -> list[tuple]:
                return [values]

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

        class Connection:
            def cursor(self) -> Cursor:
                return Cursor()

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

        provider = DatabricksDataProvider(
            DatabricksConfig(
                "workspace.example.com",
                "/sql/1.0/warehouses/demo",
                "`workspace`.`gold`.`bairroiq_frontend_v1`",
            )
        )
        with patch.object(provider, "_connect", return_value=Connection()):
            metrics = provider.load_metrics()

        self.assertEqual(metrics.loc[0, "neighborhood"], "Sé")
        self.assertEqual(metrics.loc[0, "safety_score"], 85.0)
        self.assertTrue(
            pd.isna(metrics.loc[0, "affordability_score"])
        )

    def test_empty_published_snapshot_is_reported(self) -> None:
        class Cursor:
            description = [("neighborhood",)]

            def execute(self, _query: str) -> None:
                return None

            def fetchall(self) -> list[tuple]:
                return []

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

        class Connection:
            def cursor(self) -> Cursor:
                return Cursor()

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

        provider = DatabricksDataProvider(
            DatabricksConfig("workspace.example.com", "path", "`workspace`.`gold`.`table`")
        )
        with patch.object(provider, "_connect", return_value=Connection()):
            with self.assertRaisesRegex(ValueError, "publicacao_autorizada"):
                provider.load_metrics()

    def test_oauth_connection_uses_the_app_service_principal(self) -> None:
        from databricks import sql
        from databricks.sdk.core import Config

        provider = DatabricksDataProvider(
            DatabricksConfig("workspace.example.com", "path", "`workspace`.`gold`.`table`")
        )
        with (
            patch.object(sql, "connect", return_value=None) as connect,
            patch.object(Config, "__init__", return_value=None) as config_init,
            patch.object(Config, "authenticate", create=True, new_callable=unittest.mock.PropertyMock),
        ):
            provider._connect()

        config_init.assert_called_once_with()
        self.assertTrue(callable(connect.call_args.kwargs["credentials_provider"]))
        self.assertNotIn("access_token", connect.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
