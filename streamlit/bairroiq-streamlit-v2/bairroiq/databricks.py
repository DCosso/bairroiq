"""Provedor SQL Databricks do Streamlit integrado ao BairroIQ.

Lê o Consumer V2 usando o módulo existente bairroiq.consumer_v2.
Nenhuma função deste arquivo escreve dados, altera grants ou homologa snapshots.

Dados candidatos somente podem ser consultados para prévia interna por meio
 de BAIRROIQ_INTERNAL_PREVIEW=true em um ambiente efetivamente privado, cujo
acesso seja controlado no Databricks Apps e no Unity Catalog. A variável de
ambiente NÃO substitui controles de acesso.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from bairroiq.consumer_v2 import build_query, validate_frame

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
        """Mantém a configuração usada pela versão integrada da Laís."""
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

        host = setting(
            ("DATABRICKS_HOST", "DATABRICKS_SERVER_HOSTNAME"),
            "server_hostname",
        )
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
    """Consulta o snapshot V2 e traduz os campos para o Streamlit.

    O OAuth da identidade do aplicativo permanece o padrão do Databricks Apps.
    O token pessoal continua restrito ao desenvolvimento local.
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
        """Busca, valida e entrega indicadores reais do Consumer V2.

        Modo padrão: consulta somente linhas homologadas.
        Modo de prévia: BAIRROIQ_INTERNAL_PREVIEW=true, exclusivamente com
        acesso privado e previamente autorizado aos usuários do aplicativo.
        """
        internal_preview = (
            os.getenv("BAIRROIQ_INTERNAL_PREVIEW", "false").strip().lower()
            == "true"
        )

        # DatabricksConfig guarda a tabela já validada e com crases. O módulo
        # consumer_v2 normaliza e valida novamente seu identificador SQL.
        metrics_table = self._config.metrics_table.replace("`", "")
        query = build_query(
            metrics_table=metrics_table,
            internal_preview=internal_preview,
        )
        raw = self._read_query(query)
        if raw.empty:
            raise ValueError(
                "Consulta V2 sem registros. Confira o snapshot, as permissões "
                "e publicacao_autorizada. Prévia não homologada somente em "
                "ambiente privado e com BAIRROIQ_INTERNAL_PREVIEW=true."
            )

        metrics = validate_frame(raw, internal_preview=internal_preview)

        # Dois aliases conservam os pontos de entrada do frontend atual.
        # robbery_index mantém a taxa real de roubos por mil habitantes;
        # NÃO é uma pontuação de segurança nem deve ser multiplicado por 10.
        metrics["district_code"] = metrics["cd_dist"]
        metrics["robbery_index"] = metrics["robberies_per_1000"]
        return metrics

    def load_history(self) -> pd.DataFrame:
        """Não inventa série histórica a partir de um único snapshot."""
        return pd.DataFrame(columns=_HISTORY_COLUMNS)
