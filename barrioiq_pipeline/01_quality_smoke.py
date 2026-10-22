
# Databricks notebook source
"""BarrioIQ - Data Quality com PySpark e auditoria Delta."""

import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

AUDIT_TABLE = "workspace.observability.data_quality_runs"
RUN_ID = str(uuid4())
STARTED_AT = time.perf_counter()

print(f"BARRIOIQ_DQ_START run_id={RUN_ID}")

# COMMAND ----------
# 1. DADOS SINTETICOS

input_schema = StructType([
    StructField("codigo_area", StringType(), True),
    StructField("distrito", StringType(), True),
    StructField("populacao", LongType(), True),
    StructField("renda_media", DoubleType(), True),
])

input_rows = [
    ("001", "Centro", 100, 3000.0),
    ("002", "Centro", 200, 4000.0),
    ("003", "Norte", 150, 2500.0),
    ("002", "Centro", 200, 4000.0),
    (None, "Sul", 80, 2000.0),
]

bronze = spark.createDataFrame(
    input_rows,
    schema=input_schema
)

# COMMAND ----------
# 2. QUALIDADE BRONZE

valid_key = (
    F.col("codigo_area").isNotNull()
    & (F.trim(F.col("codigo_area")) != "")
)

bronze_total = bronze.count()

bronze_missing = bronze.filter(
    ~valid_key
).count()

bronze_with_key = bronze.filter(valid_key)

bronze_duplicates = (
    bronze_with_key.count()
    - bronze_with_key
        .select("codigo_area")
        .distinct()
        .count()
)

assert bronze_total == 5
assert bronze_missing == 1
assert bronze_duplicates == 1

print(
    f"BRONZE: registros={bronze_total}, "
    f"chaves_ausentes={bronze_missing}, "
    f"chaves_duplicadas={bronze_duplicates}"
)

# COMMAND ----------
# 3. TRATAMENTO E VALIDACAO SILVER

# Remove apenas duplicatas identicas.
# Chaves conflitantes continuam sujeitas a validacao.
silver = (
    bronze
    .filter(valid_key)
    .dropDuplicates()
)


def validate_silver(df):
    invalid_condition = (
        F.col("codigo_area").isNull()
        | (F.trim(F.col("codigo_area")) == "")
        | F.col("distrito").isNull()
        | (F.trim(F.col("distrito")) == "")
        | F.col("populacao").isNull()
        | (F.col("populacao") < 0)
        | F.col("renda_media").isNull()
        | F.isnan(F.col("renda_media"))
        | (F.col("renda_media") < 0)
    )

    invalid_count = df.filter(
        invalid_condition
    ).count()

    duplicated_keys = (
        df.groupBy("codigo_area")
        .count()
        .filter(F.col("count") > 1)
        .count()
    )

    if invalid_count or duplicated_keys:
        raise ValueError(
            "DATA_QUALITY_FAILED: "
            f"registros_invalidos={invalid_count}, "
            f"chaves_duplicadas={duplicated_keys}"
        )

    return df.count()


silver_total = validate_silver(silver)

assert silver_total == 3

print(f"SILVER: registros_validos={silver_total}")

# COMMAND ----------
# 4. TESTE NEGATIVO DE QUALIDADE

invalid_silver = spark.createDataFrame(
    [("999", "Teste", -10, 2000.0)],
    schema=input_schema,
)

try:
    validate_silver(invalid_silver)

except ValueError:
    print("DQ_NEGATIVE_TEST_PASSED")

else:
    raise AssertionError(
        "A validacao aceitou populacao negativa"
    )

# COMMAND ----------
# 5. AGREGACAO GOLD

gold = silver.groupBy("distrito").agg(
    F.count("*").alias("total_areas"),
    F.sum("populacao").alias("populacao_total"),
)

gold_summary = gold.agg(
    F.sum("total_areas").alias("areas"),
    F.sum("populacao_total").alias("populacao"),
).first()

silver_population = silver.agg(
    F.sum("populacao").alias("total")
).first()["total"]

gold_districts = gold.count()
gold_population = gold_summary["populacao"]

assert gold_summary["areas"] == silver_total
assert gold_population == silver_population
assert gold_districts == 2
assert gold_population == 450

gold.orderBy("distrito").show(truncate=False)

print(
    f"GOLD: distritos={gold_districts}, "
    f"populacao={gold_population}"
)

# COMMAND ----------
# 6. AUDITORIA PERSISTENTE NO DELTA LAKE

audit_schema = StructType([
    StructField("run_id", StringType(), False),
    StructField("executed_at", TimestampType(), False),
    StructField("pipeline", StringType(), False),
    StructField("status", StringType(), False),
    StructField("bronze_records", LongType(), True),
    StructField("bronze_missing_keys", LongType(), True),
    StructField("bronze_duplicate_keys", LongType(), True),
    StructField("silver_records", LongType(), True),
    StructField("gold_districts", LongType(), True),
    StructField("silver_population", LongType(), True),
    StructField("gold_population", LongType(), True),
    StructField("duration_seconds", DoubleType(), True),
    StructField("error_message", StringType(), True),
])

# Confere a acessibilidade da tabela existente.
try:
    spark.table(AUDIT_TABLE).schema

except Exception as exc:
    raise RuntimeError(
        f"AUDIT_TABLE_UNAVAILABLE: {AUDIT_TABLE}. "
        "Confira catalogo, schema e permissoes."
    ) from exc

record = {
    "run_id": RUN_ID,
    "executed_at": datetime.now(timezone.utc),
    "pipeline": "barrioiq_quality_smoke",
    "status": "SUCCESS",

    "bronze_records": int(bronze_total),
    "bronze_missing_keys": int(bronze_missing),
    "bronze_duplicate_keys": int(bronze_duplicates),

    "silver_records": int(silver_total),
    "gold_districts": int(gold_districts),

    "silver_population": int(silver_population),
    "gold_population": int(gold_population),

    "duration_seconds": float(
        time.perf_counter() - STARTED_AT
    ),

    "error_message": None,
}

audit_df = spark.createDataFrame(
    [record],
    schema=audit_schema
)

print(
    f"AUDIT_WRITE_START "
    f"table={AUDIT_TABLE} "
    f"run_id={RUN_ID}"
)

# Acrescenta uma linha ao historico existente.
# Nao recria nem sobrescreve a tabela.
(
    audit_df.write
    .format("delta")
    .mode("append")
    .saveAsTable(AUDIT_TABLE)
)

# COMMAND ----------
# 7. CONFERIR SE A LINHA FOI GRAVADA

readback = (
    spark.table(AUDIT_TABLE)
    .filter(F.col("run_id") == RUN_ID)
    .count()
)

if readback != 1:
    raise RuntimeError(
        f"AUDIT_READBACK_FAILED: "
        f"run_id={RUN_ID}, "
        f"linhas_encontradas={readback}"
    )

print("AUDIT_WRITE_SUCCESS")
print("AUDIT_READBACK_SUCCESS")
print(f"Run ID: {RUN_ID}")
print(f"Tabela: {AUDIT_TABLE}")

# COMMAND ----------
# 8. LOG ESTRUTURADO FINAL

metrics = {
    "event": "barrioiq_data_quality",
    "run_id": RUN_ID,
    "timestamp_utc": datetime.now(
        timezone.utc
    ).isoformat(),

    "status": "SUCCESS",
    "audit_persisted": True,

    "bronze_records": bronze_total,
    "bronze_missing_keys": bronze_missing,
    "bronze_duplicate_keys": bronze_duplicates,

    "silver_records": silver_total,
    "gold_districts": gold_districts,

    "silver_population": int(silver_population),
    "gold_population": int(gold_population),

    "duration_seconds": record["duration_seconds"],
}

print(json.dumps(
    metrics,
    indent=2,
    ensure_ascii=False
))

print("JOB_BARRIOIQ_DQ_SUCCESS")
