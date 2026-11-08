# Databricks | BairroIQ | Materialização auditável do Consumer V2
# Arquivo Python COMPLETO, execute em um notebook Python no Databricks.
#
# Uso:
# 1) Primeiro execute com MATERIALIZAR = False (dry-run sem escrita).
# 2) Confira os resultados e restrição de acesso.
# 3) Só após aprovação humana, troque para True e execute novamente.
#
# Nunca muda a Gold original, dados de origem, grants ou flags de publicação.
# Snapshot candidato: uso estritamente interno e autorizado.
# O app público NÃO deve consumir os dados enquanto publicacao_autorizada=false.
#
# Materialização idempotente por conteúdo: o snapshot existente é verificado
# integralmente; divergências geram falha em vez de sobrescrita.
# Requer um único operador por vez. Não é proteção WORM/ACL do Unity Catalog.
from __future__ import annotations

import hashlib
import json
import math

import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType, BooleanType
)

TARGET_TABLE = "workspace.gold.bairroiq_frontend_v2"
SOURCE_TABLE = "workspace.gold.bairroiq_frontend_v1"
SNAPSHOT = (
    "v3.0.0-candidato|"
    "726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b"
)
CONTRACT_VERSION = "frontend_v2.0.0"
MATERIALIZAR = False   # MANTENHA FALSE NO PRIMEIRO TESTE
EXPECTED_COUNTS = {
    "kmeans-k09-p01": 9,
    "kmeans-k09-p02": 7,
    "kmeans-k09-p03": 6,
    "kmeans-k09-p04": 22,
    "kmeans-k09-p05": 7,
    "kmeans-k09-p06": 8,
    "kmeans-k09-p07": 12,
    "kmeans-k09-p08": 19,
    "kmeans-k09-p09": 6,
}
DATA_COLUMNS = (
    "snapshot_id", "cd_dist", "neighborhood", "latitude", "longitude",
    "formal_jobs_score", "safety_score", "mobility_score",
    "green_leisure_score", "public_services_score", "densidade_hab_km2",
    "robberies_per_1000", "perfil_id", "cluster",
    "tipo_territorio", "publicacao_autorizada",
)
NUMERIC_SCORES = (
    "formal_jobs_score", "safety_score", "mobility_score",
    "green_leisure_score", "public_services_score",
)
NUMERIC_QUANTITIES = ("densidade_hab_km2", "robberies_per_1000")
NUMERIC_COORDS = ("latitude", "longitude")
AUDIT_COLUMNS = (
    "versao_contrato", "payload_sha256", "sql_sha256", "materializado_em_utc",
)

# SQL literalmente igual ao adaptador V2 que passou na validação de 96 distritos.
SQL_V2 = r"""
-- BairroIQ | Adaptador para o Streamlit da Lais | V2 - 2026-11-08
-- Somente leitura. Nao cria tabelas, views, grants ou arquivos.
-- Seis dimensoes: empregos, seguranca relativa, mobilidade,
-- verde/lazer, servicos publicos e densidade populacional.
-- Roubos e perfil K-Means sao informacoes complementares.
-- Atenção: publicacao_autorizada=false, uso interno nao-publicavel.
WITH consumer AS (
    SELECT
        snapshot_id,
        cd_dist,
        distrito,
        latitude,
        longitude,
        perfil_id,
        cluster,
        empregos,
        roubos,
        seguranca,
        mobilidade,
        tipo_territorio,
        publicacao_autorizada
    FROM workspace.gold.bairroiq_frontend_v1
    WHERE snapshot_id = 'v3.0.0-candidato|726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b'
),
extras_raw AS (
    SELECT
        f.snapshot_id,
        f.CD_DIST AS cd_dist,
        MAX(CASE WHEN i.indicador_id = 'pracas' THEN f.valor_numerico END) AS pracas_por_10mil,
        MAX(CASE WHEN i.indicador_id = 'corredores_verdes' THEN f.valor_numerico END) AS corredores_por_10mil,
        MAX(CASE WHEN i.indicador_id = 'escolas' THEN f.valor_numerico END) AS escolas_por_10mil,
        MAX(CASE WHEN i.indicador_id = 'ubs' THEN f.valor_numerico END) AS ubs_por_10mil,
        MAX(CASE WHEN i.indicador_id = 'densidade' THEN f.valor_numerico END) AS densidade_hab_km2,
        COUNT(*) AS contagem_indicadores_extra,
        COUNT(DISTINCT i.indicador_id) AS indicadores_extra_distintos
    FROM workspace.gold.bairroiq_fato_distrito_indicador AS f
    INNER JOIN workspace.gold.bairroiq_dim_indicador AS i
        ON f.snapshot_id = i.snapshot_id
       AND f.indicador_sk = i.indicador_sk
    WHERE f.snapshot_id = 'v3.0.0-candidato|726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b'
      AND i.indicador_id IN ('pracas','corredores_verdes','escolas','ubs','densidade')
    GROUP BY f.snapshot_id, f.CD_DIST
),
extras_percentis AS (
    SELECT
        snapshot_id,
        cd_dist,
        pracas_por_10mil,
        corredores_por_10mil,
        escolas_por_10mil,
        ubs_por_10mil,
        densidade_hab_km2,
        contagem_indicadores_extra,
        indicadores_extra_distintos,
        100.0 * PERCENT_RANK() OVER (ORDER BY pracas_por_10mil) AS pr_pracas,
        100.0 * PERCENT_RANK() OVER (ORDER BY corredores_por_10mil) AS pr_corredores,
        100.0 * PERCENT_RANK() OVER (ORDER BY escolas_por_10mil) AS pr_escolas,
        100.0 * PERCENT_RANK() OVER (ORDER BY ubs_por_10mil) AS pr_ubs
    FROM extras_raw
)
SELECT
    c.snapshot_id,
    c.cd_dist,
    c.distrito AS neighborhood,
    c.latitude,
    c.longitude,
    c.empregos AS formal_jobs_score,
    c.seguranca AS safety_score,
    c.mobilidade AS mobility_score,
    ROUND((e.pr_pracas + e.pr_corredores) / 2.0, 1) AS green_leisure_score,
    ROUND((e.pr_escolas + e.pr_ubs) / 2.0, 1) AS public_services_score,
    e.densidade_hab_km2,
    c.roubos AS robberies_per_1000,
    c.perfil_id,
    c.cluster,
    c.tipo_territorio,
    c.publicacao_autorizada,
    e.contagem_indicadores_extra,
    e.indicadores_extra_distintos
FROM consumer AS c
LEFT JOIN extras_percentis AS e
    ON c.snapshot_id = e.snapshot_id
   AND c.cd_dist = e.cd_dist
ORDER BY c.cd_dist
"""


def _validate(source: pd.DataFrame) -> pd.DataFrame:
    """Validação integral do snapshot antes de qualquer gravação."""
    needed = set(DATA_COLUMNS) | {
        "contagem_indicadores_extra", "indicadores_extra_distintos"
    }
    missing = needed - set(source.columns)
    if missing:
        raise ValueError(f"Colunas ausentes na consulta: {sorted(missing)}")
    if len(source) != 96:
        raise ValueError(f"Esperados 96 distritos; obtidos {len(source)}")
    if source[list(needed)].isna().any().any():
        raise ValueError("Há valores nulos em colunas obrigatórias")
    if source["snapshot_id"].nunique() != 1 or not source["snapshot_id"].eq(SNAPSHOT).all():
        raise ValueError("O snapshot não coincide com o snapshot validado")
    if source["cd_dist"].nunique() != 96 or source["neighborhood"].nunique() != 96:
        raise ValueError("Distritos duplicados ou faltando")
    if set(source["tipo_territorio"]) != {"DISTRITO_IBGE"}:
        raise ValueError("A granularidade deve ser DISTRITO_IBGE")
    if not source["publicacao_autorizada"].eq(False).all():
        raise ValueError("A fonte inesperadamente não está inteiramente não-publicável")
    if source["perfil_id"].value_counts().to_dict() != EXPECTED_COUNTS:
        raise ValueError("A distribuição dos nove perfis mudou")
    if source["cluster"].nunique() != 9:
        raise ValueError("Era esperado exatamente um nome para cada perfil")
    if (source.groupby("perfil_id")["cluster"].nunique() != 1).any():
        raise ValueError("Mesmo perfil associado a múltiplos rótulos")
    for field in ("contagem_indicadores_extra", "indicadores_extra_distintos"):
        if not pd.to_numeric(source[field], errors="raise").eq(5).all():
            raise ValueError(f"Indicadores extras incompletos ou duplicados: {field}")

    checked = source.loc[:, list(DATA_COLUMNS)].copy()
    checked["cd_dist"] = pd.to_numeric(checked["cd_dist"], errors="raise").astype("int64")
    for field in NUMERIC_SCORES + NUMERIC_QUANTITIES + NUMERIC_COORDS:
        checked[field] = pd.to_numeric(checked[field], errors="raise").astype("float64")
        if not checked[field].map(math.isfinite).all():
            raise ValueError(f"Valores não finitos: {field}")
    for field in NUMERIC_SCORES:
        if not checked[field].between(0, 100).all():
            raise ValueError(f"Índice fora da escala 0..100: {field}")
    for field in NUMERIC_QUANTITIES:
        if not checked[field].ge(0).all():
            raise ValueError(f"Taxa ou quantidade negativa: {field}")
    if not checked.latitude.between(-24, -23).all() or not checked.longitude.between(-47, -46).all():
        raise ValueError("Centroide fora de SP")
    return checked.sort_values("cd_dist").reset_index(drop=True)


def _payload_hash(df: pd.DataFrame) -> str:
    """Hash determinístico de todas as 16 colunas de negócio, por código distrital."""
    if list(df.columns) != list(DATA_COLUMNS):
        raise ValueError("Colunas de negócio diferentes do contrato previsto")
    rows = []
    for _, r in df.sort_values("cd_dist").iterrows():
        row = []
        for col in DATA_COLUMNS:
            if col == "cd_dist":
                row.append(int(r[col]))
            elif col in NUMERIC_SCORES + NUMERIC_QUANTITIES + NUMERIC_COORDS:
                row.append(format(float(r[col]), ".17g"))
            elif col == "publicacao_autorizada":
                row.append(bool(r[col]))
            else:
                row.append(str(r[col]))
        rows.append(row)
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prepared_spark(checked: pd.DataFrame):
    """Congela exatamente os 96 registros que passaram na validação Python.

    Isto evita consultar novamente a fonte entre a auditoria e a gravação.
    """
    type_by_field = {
        "snapshot_id": StringType(),
        "cd_dist": LongType(),
        "neighborhood": StringType(),
        "latitude": DoubleType(),
        "longitude": DoubleType(),
        "formal_jobs_score": DoubleType(),
        "safety_score": DoubleType(),
        "mobility_score": DoubleType(),
        "green_leisure_score": DoubleType(),
        "public_services_score": DoubleType(),
        "densidade_hab_km2": DoubleType(),
        "robberies_per_1000": DoubleType(),
        "perfil_id": StringType(),
        "cluster": StringType(),
        "tipo_territorio": StringType(),
        "publicacao_autorizada": BooleanType(),
    }
    schema = StructType([
        StructField(field, type_by_field[field], nullable=False)
        for field in DATA_COLUMNS
    ])
    typed_records = []
    for record in checked.to_dict(orient="records"):
        row = []
        for field in DATA_COLUMNS:
            value = record[field]
            if field == "cd_dist":
                row.append(int(value))
            elif field in NUMERIC_COORDS + NUMERIC_SCORES + NUMERIC_QUANTITIES:
                row.append(float(value))
            elif field == "publicacao_autorizada":
                row.append(bool(value))
            else:
                row.append(str(value))
        typed_records.append(tuple(row))
    return spark.createDataFrame(typed_records, schema=schema)


def _assert_existing(existing, expected, payload_sha: str, sql_sha: str) -> None:
    """Não reutiliza uma tabela adulterada, parcial ou de outro snapshot."""
    expected_signature = [(f.name, f.dataType.simpleString()) for f in expected.schema.fields]
    existing_signature = [(f.name, f.dataType.simpleString()) for f in existing.schema.fields]
    if existing_signature != expected_signature:
        raise RuntimeError(
            "Schema da tabela V2 diferente do contrato. "
            f"Esperado={expected_signature}; Encontrado={existing_signature}"
        )
    count = existing.count()
    if count == 0:
        return
    if count != 96:
        raise RuntimeError(f"Tabela existente parcial/inválida: {count} linhas")
    pd_existing = existing.select(*DATA_COLUMNS).toPandas()
    # Verifica também os campos de auditoria sem usar a tabela como fonte da verdade.
    m = existing.select(*AUDIT_COLUMNS).distinct().collect()
    if len(m) != 1:
        raise RuntimeError("Metadados de auditoria não são únicos")
    row = m[0]
    if (row["versao_contrato"] != CONTRACT_VERSION or
        row["payload_sha256"] != payload_sha or
        row["sql_sha256"] != sql_sha or
        row["materializado_em_utc"] is None):
        raise RuntimeError("Metadados de auditoria divergentes")
    if not pd_existing["snapshot_id"].eq(SNAPSHOT).all():
        raise RuntimeError("A tabela tem outro snapshot")
    verified = _validate_existing_payload(pd_existing)
    if _payload_hash(verified) != payload_sha:
        raise RuntimeError("Dados materiais da tabela divergem da consulta atual")


def _validate_existing_payload(df: pd.DataFrame) -> pd.DataFrame:
    """Valida a leitura física das 16 colunas antes de calcular checksum."""
    if len(df) != 96 or df["cd_dist"].nunique() != 96 or df["neighborhood"].nunique() != 96:
        raise RuntimeError("Tabela física não contém exatamente 96 distritos únicos")
    if df[list(DATA_COLUMNS)].isna().any().any():
        raise RuntimeError("Tabela física tem campos nulos")
    if df["perfil_id"].value_counts().to_dict() != EXPECTED_COUNTS:
        raise RuntimeError("Clusters físicos divergem da distribuição oficial candidata")
    if not df["publicacao_autorizada"].eq(False).all():
        raise RuntimeError("Flag de publicação física inesperada")
    return df.loc[:, list(DATA_COLUMNS)].sort_values("cd_dist").reset_index(drop=True)


# ---------------------- Execução do notebook ----------------------
if not hasattr(spark, "sql"):
    raise RuntimeError("Execute este arquivo em um notebook Python do Databricks")

print("BAIRROIQ | CONSUMER V2 | PRÉ-VALIDAÇÃO")
print("Destino:", TARGET_TABLE)
print("Somente leitura:", not MATERIALIZAR)

# Consulta V2 congelada, a mesma do notebook validado anteriormente.
raw = spark.sql(SQL_V2)
checked = _validate(raw.toPandas())
payload_sha = _payload_hash(checked)
sql_sha = hashlib.sha256(SQL_V2.strip().encode("utf-8")).hexdigest()

# Retém 16 colunas de negócio no contrato, adiciona 4 de auditoria.
base = _prepared_spark(checked)
expected = (
    base.withColumn("versao_contrato", F.lit(CONTRACT_VERSION))
        .withColumn("payload_sha256", F.lit(payload_sha))
        .withColumn("sql_sha256", F.lit(sql_sha))
        .withColumn("materializado_em_utc", F.current_timestamp())
)

print("Distritos:", len(checked))
print("Clusters:", checked.perfil_id.nunique())
print("Nulos:", int(checked.isna().sum().sum()))
print("Status dos dados: INTERNO_NAO_PUBLICAVEL")
print("Contrato:", CONTRACT_VERSION)
print("SHA256 dados:", payload_sha)
print("SHA256 consulta:", sql_sha)

exists = spark.catalog.tableExists(TARGET_TABLE)
if exists:
    table = spark.table(TARGET_TABLE)
    _assert_existing(table, expected, payload_sha, sql_sha)
    count = table.count()
    print("Tabela existente:", count, "linhas; integridade verificada")
else:
    print("Tabela V2 ainda não existe. A primeira materialização criará uma Delta gerenciada.")

if not MATERIALIZAR:
    print("BAIRROIQ_FRONTEND_V2_PREFLIGHT_APROVADO_SEM_ESCRITA")
else:
    # Controle humano: jamais modificar outras tabelas ou autorizações.
    if exists and count == 96:
        print("BAIRROIQ_FRONTEND_V2_JA_MATERIALIZADO_E_CONFERIDO")
    else:
        expected.write.format("delta").mode("append").saveAsTable(TARGET_TABLE)
        written = spark.table(TARGET_TABLE)
        _assert_existing(written, expected, payload_sha, sql_sha)
        print("BAIRROIQ_FRONTEND_V2_MATERIALIZADO_E_AUDITADO")
        print("Linhas gravadas:", written.count())
    try:
        hist = spark.sql(f"DESCRIBE HISTORY {TARGET_TABLE}").select("version", "timestamp", "operation").limit(1)
        display(hist)
    except Exception as exc:
        print("Histórico Delta não exibido (auditoria em tabela permanece válida):", type(exc).__name__)

print("Atenção: tabela interna; acesso e publicação ainda exigem homologação.")
