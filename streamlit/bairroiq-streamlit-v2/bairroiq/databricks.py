"""Provedor do Atlas Sampa/BairroIQ a partir do Consumer V2 Delta auditado.

Mantém o acesso SQL, OAuth e o contrato DataProvider da integração original.
Somente leitura: não cria tabelas, não altera ACLs nem permite publicação.
A prévia de snapshots não homologados requer opt-in explícito E ambiente privado
com permissões apropriadas; a variável por si só não é autorização de acesso.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from bairroiq.consumer_v2 import REQUIRED_COLUMNS, SNAPSHOT, validate_frame

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_DEFAULT_TABLE = "workspace.gold.bairroiq_frontend_v2"
_CONTRACT_VERSION = "frontend_v2.0.0"
_EXPECTED_SQL_SHA256 = "6eb594ea533fb033a392b6b70dede47731f008284ceb80f6be7bf1d988e7e7db"
_AUDIT_COLUMNS = (
    "versao_contrato", "payload_sha256", "sql_sha256", "materializado_em_utc",
)
_NUMERIC = {
    "latitude", "longitude", "formal_jobs_score", "safety_score",
    "mobility_score", "green_leisure_score", "public_services_score",
    "densidade_hab_km2", "robberies_per_1000",
}
_HISTORY_COLUMNS = [
    "neighborhood", "year", "formal_jobs_score", "lighting_led", "safety_score",
]


def _qualified_table(table_name: str) -> str:
    parts = table_name.split(".")
    if not 1 <= len(parts) <= 3 or any(
        not _IDENTIFIER.fullmatch(part) for part in parts
    ):
        raise ValueError(
            "O nome da tabela deve usar identificadores SQL simples, "
            "como workspace.gold.bairroiq_frontend_v2."
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
        """Configura o SQL Warehouse sem quebrar o app.yaml ou secrets local."""
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


def _payload_sha256(df: pd.DataFrame) -> str:
    """Mesmo algoritmo determinístico da materialização aprovada no Databricks."""
    rows: list[list[object]] = []
    for _, row in df.sort_values("cd_dist").iterrows():
        values: list[object] = []
        for column in REQUIRED_COLUMNS:
            value = row[column]
            if column == "cd_dist":
                values.append(int(value))
            elif column in _NUMERIC:
                values.append(format(float(value), ".17g"))
            elif column == "publicacao_autorizada":
                values.append(bool(value))
            else:
                values.append(str(value))
        rows.append(values)
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _verify_audited_result(raw: pd.DataFrame, *, internal_preview: bool) -> pd.DataFrame:
    """Valida 16 campos físicos e quatro metadados antes de expor ao Streamlit."""
    missing = set(_AUDIT_COLUMNS).difference(raw.columns)
    if missing:
        raise ValueError(f"A tabela Delta V2 não contém auditoria: {sorted(missing)}")

    for col in _AUDIT_COLUMNS:
        if raw[col].isna().any() or raw[col].nunique() != 1:
            raise ValueError(f"Auditoria incompleta ou não uniforme: {col}")

    version = str(raw["versao_contrato"].iloc[0])
    if version != _CONTRACT_VERSION:
        raise ValueError(f"Versão de contrato não reconhecida: {version}")

    sql_sha = str(raw["sql_sha256"].iloc[0])
    if sql_sha != _EXPECTED_SQL_SHA256:
        raise ValueError("Hash SQL não corresponde à consulta V2 materializada")

    expected_payload = str(raw["payload_sha256"].iloc[0])
    if not _SHA256.fullmatch(expected_payload):
        raise ValueError("Hash SHA256 de auditoria malformado")

    metrics = validate_frame(raw, internal_preview=internal_preview)
    calculated_payload = _payload_sha256(metrics)
    if calculated_payload != expected_payload:
        raise ValueError("Hash do conteúdo divergente: snapshot alterado após a auditoria")

    return metrics


class DatabricksDataProvider:
    """Consulta exclusivamente a tabela V2 física, sem recomputar percentis."""

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
        """Busca uma fotografia física V2 e confere o conteúdo contra seu hash.

        Por padrão usa somente dados homologados.
        BAIRROIQ_INTERNAL_PREVIEW=true apenas permite a consulta à fotografia
        candidata quando a aplicação inteira tem acesso privado autorizado.
        """
        internal_preview = (
            os.getenv("BAIRROIQ_INTERNAL_PREVIEW", "false").strip().lower()
            == "true"
        )
        gate = "" if internal_preview else "AND publicacao_autorizada IS TRUE"
        query = f"""
            SELECT
                snapshot_id, cd_dist, neighborhood, latitude, longitude,
                formal_jobs_score, safety_score, mobility_score,
                green_leisure_score, public_services_score,
                densidade_hab_km2, robberies_per_1000, perfil_id,
                cluster, tipo_territorio, publicacao_autorizada,
                versao_contrato, payload_sha256, sql_sha256, materializado_em_utc
            FROM {self._config.metrics_table}
            WHERE snapshot_id = '{SNAPSHOT}'
              {gate}
            ORDER BY cd_dist
        """
        raw = self._read_query(query)
        if raw.empty:
            raise ValueError(
                "Consumer V2 físico sem registros acessíveis. O snapshot é interno "
                "e não homologado; confira identidade, permissões e liberação "
                "para prévia estritamente privada."
            )

        metrics = _verify_audited_result(raw, internal_preview=internal_preview)
        # Aliases usados pela interface existente; sem recalcular a segurança.
        metrics["district_code"] = metrics["cd_dist"]
        metrics["robbery_index"] = metrics["robberies_per_1000"]
        return metrics

    def load_history(self) -> pd.DataFrame:
        """Não transforma snapshot em histórico anual fictício."""
        return pd.DataFrame(columns=_HISTORY_COLUMNS)
