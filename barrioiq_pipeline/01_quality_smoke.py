
# Databricks notebook source

import json
from datetime import datetime, timezone
import time
from uuid import uuid4
from pyspark.sql.types import TimestampType

dq_run_id = str(uuid4())
dq_started_at = time.perf_counter()

from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    DoubleType,
)


# COMMAND ----------

# 1. DADOS SINTETICOS

schema = StructType([
    StructField("codigo_area", StringType(), True),
    StructField("distrito", StringType(), True),
    StructField("populacao", LongType(), True),
    StructField("renda_media", DoubleType(), True),
])

dados = [
    ("001", "Centro", 100, 3000.0),
    ("002", "Centro", 200, 4000.0),
    ("003", "Norte", 150, 2500.0),
    ("002", "Centro", 200, 4000.0),
    (None, "Sul", 80, 2000.0),
]

bronze = spark.createDataFrame(dados, schema)

# COMMAND ----------

# 2. PERFIL DE QUALIDADE BRONZE

chave_valida = (
    F.col("codigo_area").isNotNull()
    & (F.trim(F.col("codigo_area")) != "")
)

bronze_total = bronze.count()
bronze_nulos = bronze.filter(~chave_valida).count()

bronze_com_chave = bronze.filter(chave_valida)

bronze_duplicados = (
    bronze_com_chave.count()
    - bronze_com_chave.select("codigo_area").distinct().count()
)

print("BRONZE:")
print("Registros:", bronze_total)
print("Chaves ausentes:", bronze_nulos)
print("Chaves duplicadas:", bronze_duplicados)

assert bronze_total == 5
assert bronze_nulos == 1
assert bronze_duplicados == 1

# COMMAND ----------

# 3. TRATAMENTO SINTETICO PARA SILVER

silver = (
    bronze
    .filter(chave_valida)
    .dropDuplicates(["codigo_area"])
)

def validate_silver(df):
    invalidos = df.filter(
        F.col("codigo_area").isNull()
        | (F.trim("codigo_area") == "")
        | F.col("distrito").isNull()
        | (F.trim("distrito") == "")
        | F.col("populacao").isNull()
        | (F.col("populacao") < 0)
        | F.col("renda_media").isNull()
        | F.isnan("renda_media")
        | (F.col("renda_media") < 0)
    ).count()

    duplicados = (
        df.groupBy("codigo_area")
        .count()
        .filter(F.col("count") > 1)
        .count()
    )

    if invalidos or duplicados:
        raise ValueError(
            f"DATA_QUALITY_FAILED: "
            f"invalidos={invalidos}, "
            f"duplicados={duplicados}"
        )

    return df.count()

silver_total = validate_silver(silver)

assert silver_total == 3

print("SILVER:")
print("Registros aprovados:", silver_total)

# COMMAND ----------

# 4. TESTE NEGATIVO: DADOS RUINS DEVEM FALHAR

silver_invalida = spark.createDataFrame(
    [("999", "Teste", -10, 2000.0)],
    schema
)

try:
    validate_silver(silver_invalida)
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
    F.sum("populacao").alias("populacao_total")
)

gold_totais = gold.agg(
    F.sum("total_areas").alias("areas"),
    F.sum("populacao_total").alias("populacao")
).first()

silver_populacao = silver.agg(
    F.sum("populacao").alias("total")
).first()["total"]

assert gold_totais["areas"] == silver_total
assert gold_totais["populacao"] == silver_populacao

print("GOLD:")
gold.show(truncate=False)

# COMMAND ----------

# 6. METRICAS E LOG ESTRUTURADO

metricas = {
    "event": "barrioiq_data_quality",
    "timestamp_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "status": "SUCCESS",
    "bronze_records": bronze_total,
    "bronze_missing_keys": bronze_nulos,
    "bronze_duplicate_keys": bronze_duplicados,
    "silver_records": silver_total,
    "gold_districts": gold.count(),
    "silver_population": silver_populacao,
    "gold_population": gold_totais["populacao"],
}

print(json.dumps(
    metricas,
    indent=2,
    ensure_ascii=False
))


# COMMAND ----------

# 7. AUDITORIA PERSISTENTE NO UNITY CATALOG

tabela_auditoria = (
    "workspace.observability.data_quality_runs"
)

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

registro = {
    "run_id": dq_run_id,
    "executed_at": datetime.now(timezone.utc),
    "pipeline": "barrioiq_quality_smoke",
    "status": "SUCCESS",
    "bronze_records": bronze_total,
    "bronze_missing_keys": bronze_nulos,
    "bronze_duplicate_keys": bronze_duplicados,
    "silver_records": silver_total,
    "gold_districts": gold.count(),
    "silver_population": int(silver_populacao),
    "gold_population": int(gold_totais["populacao"]),
    "duration_seconds": float(
        time.perf_counter() - dq_started_at
    ),
    "error_message": None,
}

df_auditoria = spark.createDataFrame(
    [registro],
    schema=audit_schema
)

# Adiciona uma linha sem sobrescrever o historico
(
    df_auditoria.write
    .format("delta")
    .mode("append")
    .saveAsTable(tabela_auditoria)
)

print("AUDIT_WRITE_SUCCESS")
print("Run ID:", dq_run_id)
print("Tabela:", tabela_auditoria)
print("JOB_BARRIOIQ_DQ_SUCCESS")

