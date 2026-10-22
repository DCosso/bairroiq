# Databricks notebook source
"""BarrioIQ - smoke test de qualidade PySpark e auditoria em Delta Lake.

Executar com Run all no Databricks (Spark Serverless).
A tabela workspace.observability.data_quality_runs deve existir previamente.
"""

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
# 1. Dados sinteticos (nao representam dados reais do IBGE)

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

bronze = spark.createDataFrame(input_rows, schema=input_schema)

# COMMAND ----------
# 2. Perfil Bronze: diagnosticar sem descartar o dado bruto

valid_key = (
    F.col("codigo_area").isNotNull()
    & (F.trim(F.col("codigo_area")) != "")
)

bronze_total = bronze.count()
bronze_missing = bronze.filter(~valid_key).count()
bronze_with_key = bronze.filter(valid_key)
bronze_duplicates = (
    bronze_with_key.count()
    - bronze_with_key.select("codigo_area").distinct().count()
)

assert bronze_total == 5, "Quantidade Bronze inesperada"
assert bronze_missing == 1, "Quantidade de chaves ausentes inesperada"
assert bronze_duplicates == 1, "Quantidade de chaves duplicadas inesperada"

print(
    f"BRONZE: registros={bronze_total}, "
    f"chaves_ausentes={bronze_missing}, "
    f"chaves_duplicadas={bronze_duplicates}"
)

# COMMAND ----------
# 3. Silver: para este smoke test, remover apenas linhas exatamente iguais
# e chaves ausentes. Duplicidades conflitantes continuam visiveis e falham.

silver = bronze.filter(valid_key).dropDuplicates()


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

    invalid_count = df.filter(invalid_condition).count()
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
assert silver_total == 3, "Quantidade Silver inesperada"
print(f"SILVER: registros_validos={silver_total}")

# COMMAND ----------
# 4. Teste negativo: a validacao deve rejeitar populacao negativa

invalid_silver = spark.createDataFrame(
    [("999", "Teste", -10, 2000.0)],
    schema=input_schema,
)

try:
    validate_silver(invalid_silver)
except ValueError:
    print("DQ_NEGATIVE_TEST_PASSED")
else:
    raise AssertionError("A validacao aceitou populacao negativa")

# COMMAND ----------
# 5. Gold: agregar por distrito e conferir reconciliacao de totais

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

assert gold_summary["areas"] == silver_total, "Areas Silver e Gold diferem"
assert gold_population == silver_population, "Populacao Silver e Gold difere"
assert gold_districts == 2, "Quantidade de distritos inesperada"
assert gold_population == 450, "Populacao agregada inesperada"

gold.orderBy("distrito").show(truncate=False)
print(f"GOLD: distritos={gold_districts}, populacao={gold_population}")

# COMMAND ----------
# 6. Auditoria persistente. A tabela Delta ja foi criada via SQL versionado.
# Não recriar nem sobrescrever a tabela neste notebook.

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

# Interromper com erro claro se a tabela nao estiver acessivel.
try:
    spark.table(AUDIT_TABLE).schema
except Exception as exc:
    raise RuntimeError(
        f"AUDIT_TABLE_UNAVAILABLE: {AUDIT_TABLE}. "
        "Confira o catalogo, o schema e as permissoes no Unity Catalog."
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
    "duration_seconds": float(time.perf_counter() - STARTED_AT),
    "error_message": None,
}

audit_df = spark.createDataFrame([record], schema=audit_schema)

print(f"AUDIT_WRITE_START table={AUDIT_TABLE} run_id={RUN_ID}")
(
    audit_df.write
    .format("delta")
    .mode("append")
    .saveAsTable(AUDIT_TABLE)
)

# Verificacao de leitura apos escrita: nao emitir sucesso sem persistencia.
readback = (
    spark.table(AUDIT_TABLE)
    .filter(F.col("run_id") == RUN_ID)
    .count()
)
if readback != 1:
    raise RuntimeError(
        f"AUDIT_READBACK_FAILED: run_id={RUN_ID}, linhas={readback}. "
        "A gravacao nao foi confirmada na tabela Delta."
    )

print("AUDIT_WRITE_SUCCESS")
print("AUDIT_READBACK_SUCCESS")
print(f"Run ID: {RUN_ID}")
print(f"Tabela: {AUDIT_TABLE}")

# COMMAND ----------
# 7. Emitir metricas e sucesso somente depois da confirmacao da auditoria

metrics = {
    "event": "barrioiq_data_quality",
    "run_id": RUN_ID,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
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

print(json.dumps(metrics, indent=2, ensure_ascii=False))
print("JOB_BARRIOIQ_DQ_SUCCESS")
