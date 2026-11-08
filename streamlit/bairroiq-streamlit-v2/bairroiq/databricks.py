from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEFAULT_TABLE = "workspace.gold.bairroiq_frontend_v1"
_HISTORY_COLUMNS = [
    "neighborhood",
    "year",
    "formal_jobs_score",
    "lighting_led",
    "safety_score",
]


def _qualified_table(table_name: str) -> str:
    parts = table_name.split(".")
    if not 1 <= len(parts) <= 3 or any(
        not _IDENTIFIER.fullmatch(part) for part in parts
    ):
        raise ValueError(
            "O nome da tabela deve usar identificadores SQL simples, "
            "como workspace.gold.bairroiq_frontend_v1."
        )
    return ".".join(f"`{part}`" for part in parts)


@dataclass(frozen=True)
class DatabricksConfig:
    server_hostname: str
    http_path: str
    metrics_table: str
    access_token: str | None = None

    @classmethod
    def from_sources(
        cls,
        secrets: Mapping[str, Any] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> DatabricksConfig:
        """Lê a configuração do app ou secrets locais para desenvolvimento."""
        environment = os.environ if environ is None else environ
        secret_values: Mapping[str, Any] = {}
        if secrets is not None:
            section = secrets.get("databricks", secrets)
            if isinstance(section, Mapping):
                secret_values = section

        def setting(
            env_names: tuple[str, ...],
            secret_name: str | None = None,
            default: str | None = None,
        ) -> str | None:
            for name in env_names:
                value = environment.get(name)
                if value:
                    return value.strip()
            if secret_name:
                value = secret_values.get(secret_name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return default

        host = setting(("DATABRICKS_HOST", "DATABRICKS_SERVER_HOSTNAME",), "server_hostname")
        warehouse_id = setting(("DATABRICKS_WAREHOUSE_ID",), "warehouse_id")
        http_path = setting(("DATABRICKS_HTTP_PATH",), "http_path")
        if not http_path and warehouse_id:
            http_path = f"/sql/1.0/warehouses/{warehouse_id}"

        if not host or not http_path:
            raise ValueError(
                "Falta conectar o app ao Databricks SQL Warehouse. No Databricks Apps, "
                "adicione o recurso SQL Warehouse com a chave 'sql-warehouse' e "
                "permissão 'Can use'. Para rodar localmente, informe host e http_path "
                "em .streamlit/secrets.toml."
            )

        table_name = setting(
            ("DATABRICKS_METRICS_TABLE",),
            "metrics_table",
            _DEFAULT_TABLE,
        )
        access_token = setting(("DATABRICKS_ACCESS_TOKEN",), "access_token")
        return cls(
            server_hostname=host.removeprefix("https://").removeprefix("http://"),
            http_path=http_path,
            metrics_table=_qualified_table(table_name or _DEFAULT_TABLE),
            access_token=access_token,
        )


class DatabricksDataProvider:
    """Consulta a tabela publicada e traduz seus nomes para o contrato do app.

    A autenticação em Databricks Apps usa a identidade do próprio app (OAuth).
    Um token pessoal é aceito apenas para compatibilidade com desenvolvimento local.
    """

    def __init__(self, config: DatabricksConfig) -> None:
        self._config = config

    def _connect(self) -> Any:
        try:
            from databricks import sql
        except ImportError as exc:
            raise RuntimeError(
                "Conector Databricks ausente. Instale as dependências do projeto."
            ) from exc

        connection_options: dict[str, Any] = {
            "server_hostname": self._config.server_hostname,
            "http_path": self._config.http_path,
        }
        if self._config.access_token:
            connection_options["access_token"] = self._config.access_token
        else:
            try:
                from databricks.sdk.core import Config
            except ImportError as exc:
                raise RuntimeError(
                    "SDK Databricks ausente. Instale as dependências do projeto."
                ) from exc
            workspace_config = Config()
            connection_options["credentials_provider"] = (
                lambda: workspace_config.authenticate
            )
        return sql.connect(**connection_options)

    def _read_query(self, query: str) -> pd.DataFrame:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [column[0] for column in cursor.description]
                return pd.DataFrame(cursor.fetchall(), columns=columns)

    def load_metrics(self) -> pd.DataFrame:
        """Busca apenas dados autorizados do snapshot mais recente.

        O MAX(snapshot_id) considera a ordenação textual. Para representar
        recência, os IDs precisam ser ordenáveis (por exemplo, timestamp ISO).
        """
        query = f"""
            WITH ultimo_snapshot_publicado AS (
                SELECT MAX(snapshot_id) AS snapshot_id
                FROM {self._config.metrics_table}
                WHERE publicacao_autorizada IS TRUE
            )
            SELECT
                fonte.snapshot_id,
                fonte.cd_dist AS district_code,
                fonte.distrito AS neighborhood,
                fonte.latitude,
                fonte.longitude,
                fonte.perfil_id,
                fonte.cluster,
                fonte.tipo_territorio,
                fonte.empregos AS formal_jobs_score,
                fonte.roubos AS robbery_index,
                fonte.seguranca AS safety_score,
                fonte.mobilidade AS mobility_score,
                CAST(NULL AS DOUBLE) AS lighting_led,
                CAST(NULL AS DOUBLE) AS trees_score,
                CAST(NULL AS DOUBLE) AS affordability_score
            FROM {self._config.metrics_table} AS fonte
            INNER JOIN ultimo_snapshot_publicado AS snapshot
                ON fonte.snapshot_id = snapshot.snapshot_id
            WHERE fonte.publicacao_autorizada IS TRUE
            ORDER BY fonte.distrito
        """
        metrics = self._read_query(query)
        if metrics.empty:
            raise ValueError(
                "A tabela não retornou bairros publicados. Confira se há linhas com "
                "publicacao_autorizada = true e snapshot_id preenchido."
            )
        if metrics["neighborhood"].isna().any():
            raise ValueError(
                "Há registros publicados sem distrito (coluna distrito). "
                "Corrija a tabela antes de disponibilizar o mapa."
            )
        duplicated = metrics.loc[
            metrics["neighborhood"].duplicated(keep=False), "neighborhood"
        ].unique()
        if len(duplicated):
            names = ", ".join(sorted(map(str, duplicated)))
            raise ValueError(
                "Há mais de uma linha publicada para o mesmo distrito no snapshot "
                f"mais recente: {names}. Garanta uma linha por distrito."
            )
        return metrics

    def load_history(self) -> pd.DataFrame:
        """Não inventa uma série temporal a partir de snapshots sem data."""
        return pd.DataFrame(columns=_HISTORY_COLUMNS)
