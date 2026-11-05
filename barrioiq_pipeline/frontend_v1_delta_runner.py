"""BairroIQ | Materialização interna Delta do consumidor v1 (96 distritos).

check(spark): inspeção read-only e hash do conteúdo candidato.
apply_snapshot(...): escrita manual SOMENTE após confirmação + hash + snapshot.

Não altera nenhuma Gold de origem, não publica endpoints, não concede GRANT.
Um único escritor por snapshot é obrigatório: não há bloqueio distribuído.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent
CONSUMER_SCRIPT = ROOT / "frontend_v1_runner.py"
TARGET = "workspace.gold.bairroiq_frontend_v1"
SNAPSHOT_ID = (
    "v3.0.0-candidato|"
    "726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b"
)
STATUS = "PREVIA_DIMENSIONAL_NAO_PUBLICAVEL"
CONFIRMATION = "MATERIALIZAR_FRONTEND_V1_INTERNO_SEM_PUBLICACAO"
EXPECTED_ROWS = 96

# A tabela física usa NOMES TÉCNICOS. Os seis rótulos visuais são contrato do
# frontend_v1_runner e não devem substituir nomes físicos por nomes com acento.
SCHEMA = (
    ("snapshot_id", "string"),
    ("cd_dist", "long"),
    ("distrito", "string"),
    ("latitude", "double"),
    ("longitude", "double"),
    ("perfil_id", "string"),
    ("cluster", "string"),
    ("empregos", "double"),
    ("roubos", "double"),
    ("seguranca", "double"),
    ("mobilidade", "double"),
    ("tipo_territorio", "string"),
    ("publicacao_autorizada", "boolean"),
)
FIELDS = tuple(c for c, _ in SCHEMA)
VISUAL = ("Distrito", "Empregos", "Roubos", "Segurança", "Mobilidade", "Cluster")


class ConsumerDeltaError(ValueError):
    """Bloqueio estrito de uma operação de consumo."""


def require(value: Any, message: str) -> None:
    if not bool(value):
        raise ConsumerDeltaError("BAIRROIQ_FRONTEND_DELTA_V1_BLOCKED: " + message)


def _native(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item") and callable(value.item):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if not isinstance(value, (str, dict, list)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def _cast(value: Any, typ: str) -> Any:
    value = _native(value)
    require(value is not None, f"NULL não permitido ({typ})")
    if typ == "string":
        require(isinstance(value, str) and bool(value.strip()), "String vazia/inválida")
        return value
    if typ == "boolean":
        require(isinstance(value, bool), "Booleano inválido")
        return value
    if typ == "long":
        require(isinstance(value, (int, float)) and not isinstance(value, bool),
                "Inteiro inválido")
        require(math.isfinite(float(value)) and int(value) == float(value),
                "Inteiro fracionário/infinito")
        return int(value)
    if typ == "double":
        require(isinstance(value, (int, float)) and not isinstance(value, bool),
                "Double inválido")
        result = float(value)
        require(math.isfinite(result), "Double não finito")
        return result
    raise AssertionError(f"Tipo não reconhecido: {typ}")


def _row(record: dict[str, Any]) -> dict[str, Any]:
    require(set(record) == set(FIELDS), "Campos físicos desconhecidos ou ausentes")
    return {field: _cast(record[field], typ) for field, typ in SCHEMA}


def content_hash(rows: list[dict[str, Any]]) -> str:
    """SHA256 canônico, independente da ordem; doubles preservam bits IEEE-754."""
    require(len(rows) == EXPECTED_ROWS, "Quantidade incorreta para hash")
    normal = [_row(row) for row in rows]
    keys = [(x["snapshot_id"], x["cd_dist"]) for x in normal]
    require(len(set(keys)) == EXPECTED_ROWS, "Chave duplicada no hash")
    canonical = [
        [float(item[field]).hex() if typ == "double" else item[field]
         for field, typ in SCHEMA]
        for item in sorted(normal, key=lambda x: (x["snapshot_id"], x["cd_dist"]))
    ]
    payload = json.dumps(canonical, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Valida integralmente a saída do consumidor; não depende de Spark."""
    require(isinstance(result, dict), "Saída do consumidor não é objeto")
    summary = result.get("resumo")
    visual = result.get("visual")
    tech = result.get("tecnico")
    require(isinstance(summary, dict), "Resumo inválido")
    require(isinstance(visual, pd.DataFrame) and isinstance(tech, pd.DataFrame),
            "DataFrames visual/técnico ausentes")
    require(summary.get("snapshot_id") == SNAPSHOT_ID
            and summary.get("status") == STATUS,
            "Snapshot/status de origem diferente do congelado")
    require(summary.get("distritos") == EXPECTED_ROWS
            and summary.get("clusters") == 9
            and summary.get("colunas_visuais") == 6,
            "Resumo de cardinalidade divergente")
    require(summary.get("publicacao_autorizada") is False
            and summary.get("escrita_executada") is False
            and summary.get("alteracoes_gold") == "NENHUMA",
            "Consumidor indica publicação ou modificação prévia")
    require(list(visual.columns) == list(VISUAL) and len(visual) == EXPECTED_ROWS,
            "Contrato visual divergente")
    require(list(tech.columns) == list(FIELDS) and len(tech) == EXPECTED_ROWS,
            "Contrato técnico divergente")
    require(visual[list(VISUAL)].notna().all().all(), "NULL visual inesperado")
    require(visual["Distrito"].nunique() == EXPECTED_ROWS
            and visual["Cluster"].nunique() == 9, "Chaves/categorias visuais inválidas")
    for visual_field, tech_field in (
        ("Distrito", "distrito"), ("Empregos", "empregos"),
        ("Roubos", "roubos"), ("Segurança", "seguranca"),
        ("Mobilidade", "mobilidade"), ("Cluster", "cluster"),
    ):
        # Igualdade exata, inclusive ordem: evita salvar um visual diferente do técnico.
        require(visual[visual_field].tolist() == tech[tech_field].tolist(),
                f"Visual/técnico não correspondem: {visual_field}")
    require(tech["cd_dist"].nunique() == EXPECTED_ROWS
            and tech["perfil_id"].nunique() == 9,
            "Distritos/perfis técnicos duplicados ou ausentes")

    records = [
        _row(dict(zip(FIELDS, values)))
        for values in tech[list(FIELDS)].itertuples(index=False, name=None)
    ]
    codes = [r["cd_dist"] for r in records]
    require(len(set(codes)) == EXPECTED_ROWS, "Código distrital duplicado")
    require(all(r["snapshot_id"] == SNAPSHOT_ID for r in records),
            "Mistura de snapshots")
    require(all(r["tipo_territorio"] == "DISTRITO_IBGE"
                and r["publicacao_autorizada"] is False for r in records),
            "Território/publicação não autorizados")
    require(all(-24 <= r["latitude"] <= -23 and -47 <= r["longitude"] <= -46
                for r in records), "Coordenadas fora do município de SP")
    require(all(0 <= r[k] <= 100 for r in records
                for k in ("empregos", "seguranca", "mobilidade")),
            "Índice relativo fora de 0-100")
    require(all(r["roubos"] >= 0 for r in records), "Taxa de roubos negativa")
    require(all(r["perfil_id"].startswith("kmeans-k09-p")
                and r["perfil_id"][-2:].isdigit()
                and 1 <= int(r["perfil_id"][-2:]) <= 9
                and r["cluster"].startswith("P" + r["perfil_id"][-2:] + " — ")
                for r in records), "Perfil/cluster inconsistente")
    return {"snapshot_id": SNAPSHOT_ID, "rows": records,
            "rows_expected": EXPECTED_ROWS, "payload_sha256": content_hash(records)}


def _load_consumer(spark: Any) -> dict[str, Any]:
    require(CONSUMER_SCRIPT.is_file(), f"Arquivo ausente no Bundle: {CONSUMER_SCRIPT}")
    spec = importlib.util.spec_from_file_location(
        "bairroiq_consumer_frozen_for_delta_v1", str(CONSUMER_SCRIPT))
    require(spec is not None and spec.loader is not None, "Módulo de consumo inválido")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(tuple(module.VISUAL_COLUMNS) == VISUAL
            and tuple(module.TECH_COLUMNS) == FIELDS,
            "Contrato frontend alterado sem atualizar o materializador")
    return module.run_from_spark(spark)


def _schema_spark():
    from pyspark.sql.types import (StructType, StructField, StringType,
                                   LongType, DoubleType, BooleanType)
    types = {"string": StringType, "long": LongType,
             "double": DoubleType, "boolean": BooleanType}
    return StructType([StructField(name, types[typ](), True)
                       for name, typ in SCHEMA])


def _validate_existing_table(spark: Any) -> None:
    frame = spark.table(TARGET)
    schema = [(f.name, f.dataType.typeName()) for f in frame.schema]
    require(schema == list(SCHEMA), f"Schema Delta divergente: {schema}")
    detail = spark.sql(f"DESCRIBE DETAIL {TARGET}").first().asDict()
    require(str(detail.get("format", "")).lower() == "delta",
            "Destino existente não está em Delta")


def _load_existing_rows(spark: Any) -> list[dict[str, Any]]:
    # Limit >=97 detecta tabelas com linhas extras sem transportar todo o lake.
    collected = spark.table(TARGET).limit(EXPECTED_ROWS + 1).collect()
    require(len(collected) <= EXPECTED_ROWS,
            "Tabela com mais de 96 registros; operação interrompida")
    return [_row(x.asDict(recursive=True)) for x in collected]


def inspect(spark: Any, prepared: dict[str, Any]) -> dict[str, Any]:
    """Somente leitura, detecta partial writes e conteúdo divergente."""
    exists = bool(spark.catalog.tableExists(TARGET))
    actual = []
    if exists:
        _validate_existing_table(spark)
        actual = _load_existing_rows(spark)
        require(all(r["snapshot_id"] == SNAPSHOT_ID for r in actual),
                "Outro snapshot encontrado na tabela v1")
        require(len(actual) in (0, EXPECTED_ROWS),
                "Tabela física parcialmente materializada")
        if actual:
            require(content_hash(actual) == prepared["payload_sha256"],
                    "Conteúdo existente diverge do snapshot esperado")
    return {
        "target": TARGET,
        "snapshot_id": prepared["snapshot_id"],
        "payload_sha256": prepared["payload_sha256"],
        "expected_rows": EXPECTED_ROWS,
        "table_exists": exists,
        "rows_in_snapshot": len(actual),
        "action_if_applied": "KEEP_VERIFIED" if actual else "APPEND_SNAPSHOT",
        "will_write_on_check": False,
        "publicacao_autorizada": False,
    }


def check(spark: Any) -> dict[str, Any]:
    """Prévia/read-only. Não cria, altera nem substitui dados."""
    return inspect(spark, prepare_payload(_load_consumer(spark)))


def _write_one(spark: Any, prepared: dict[str, Any], exists_before: bool) -> None:
    require(bool(spark.catalog.tableExists(TARGET)) == exists_before,
            "Existência do destino mudou após o preflight")
    if exists_before:
        _validate_existing_table(spark)
        require(len(_load_existing_rows(spark)) == 0,
                "Destino recebeu registros após o preflight")
    dataframe = spark.createDataFrame(prepared["rows"], schema=_schema_spark())
    # Sem overwrite. No Databricks Serverless, append é compatível.
    dataframe.write.format("delta").mode("append").saveAsTable(TARGET)


def apply_snapshot(spark: Any, *, confirmation: str,
                   expected_snapshot_id: str, expected_payload_sha256: str) -> dict[str, Any]:
    """Escrita manual. Não chamar em CI/CD, Jobs ou inicialização automática.

    Somente um operador deve executar a materialização por snapshot.
    O hash do check é obrigatório, evitando aprovar conteúdo diferente.
    """
    require(confirmation == CONFIRMATION, "Token de confirmação incorreto")
    require(expected_snapshot_id == SNAPSHOT_ID, "Snapshot confirmado divergente")
    require(isinstance(expected_payload_sha256, str)
            and len(expected_payload_sha256) == 64,
            "SHA256 esperado inválido")
    prepared = prepare_payload(_load_consumer(spark))
    require(prepared["payload_sha256"] == expected_payload_sha256,
            "Hash do payload mudou desde a auditoria")
    before = inspect(spark, prepared)
    if before["rows_in_snapshot"] == EXPECTED_ROWS:
        return {"action": "ALREADY_MATERIALIZED_AND_VERIFIED",
                "before": before, "after": before, "published": False}
    _write_one(spark, prepared, exists_before=before["table_exists"])
    after = inspect(spark, prepared)
    require(after["rows_in_snapshot"] == EXPECTED_ROWS,
            "Pós-escrita não retornou 96 registros")
    return {"action": "MATERIALIZED_INTERNAL_FRONTEND_V1",
            "before": before, "after": after, "published": False}
