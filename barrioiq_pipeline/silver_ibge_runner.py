
"""BairroIQ | Executor controlado da Silver IBGE.

Sem argumentos: valida o SQL local (sem Spark).
--check: valida a transformacao e compara com a Silver (somente leitura).
--apply --confirm-publish: publica somente apos validacao e auditoria.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4


# ============================================================
# 1. CONFIGURACOES
# ============================================================

SOURCE = "workspace.bronze.ibge_agregados_basico_v2"
TARGET = "workspace.silver.ibge_agregados_basicos_v2"
AUDIT = "workspace.observability.silver_ibge_runs"


# ============================================================
# 2. RESOLUCAO DO CAMINHO DO SCRIPT
# ============================================================

def resolve_script_dir():
    """
    Resolve o diretorio do executor em Python local
    e no Databricks Serverless.

    No Databricks, __file__ pode nao estar definido
    quando o script e executado via exec().

    Usa o nome do arquivo associado ao codigo da funcao
    como alternativa, conforme o executor Bronze.
    """

    filename = (
        globals().get("__file__")
        or resolve_script_dir.__code__.co_filename
    )

    path = Path(filename).resolve()

    if not path.is_file():
        raise RuntimeError(
            f"Arquivo do executor nao encontrado: {path}"
        )

    return path.parent


SQL_FILE = (
    resolve_script_dir()
    / "sql"
    / "silver"
    / "001_ibge_agregados_basicos.sql"
)


COLUMNS = [
    "CD_DIST",
    "NM_DIST",
    "CD_MUN",
    "NM_MUN",
    "area_km2",
    "total_pessoas",
    "total_domicilios",
    "total_domicilios_particulares",
    "total_domicilios_coletivos",
    "media_moradores_domicilios_ocupados",
    "percentual_domicilios_ocupados_imputados",
    "total_domicilios_particulares_ocupados",
    "total_domicilios_uso_ocasional",
    "total_domicilios_permanentes_vagos",
]


# ============================================================
# 3. LOGS E OBSERVABILIDADE
# ============================================================

def emit(event, **details):
    print(
        json.dumps(
            {"event": event, **details},
            default=str,
            ensure_ascii=False,
        ),
        flush=True,
    )


# ============================================================
# 4. CARREGAMENTO DO SQL VERSIONADO
# ============================================================

def load_select():
    """Extrai a transformacao SQL do arquivo versionado."""

    raw = SQL_FILE.read_bytes()
    sql = raw.decode("utf-8-sig")

    sql = re.sub(
        r"(?m)^[ \t]*--[^\r\n]*$",
        "",
        sql,
    ).strip()

    pattern = (
        rf"CREATE\s+OR\s+REPLACE\s+TABLE\s+"
        rf"{re.escape(TARGET)}\s+"
        rf"USING\s+DELTA\s+AS\s+"
        rf"(?P<select>SELECT\s+.*?)\s+"
        rf"FROM\s+{re.escape(SOURCE)}\s+"
        rf"WHERE\s+CD_MUN\s*=\s*'3550308'\s*;"
    )

    match = re.fullmatch(
        pattern,
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match or sql.count(";") != 1:
        raise ValueError(
            "SQL Silver fora do contrato versionado; "
            "nenhuma tabela foi alterada"
        )

    projection = match.group("select")

    forbidden = (
        r"\b("
        r"FROM|JOIN|UNION|EXCEPT|INTERSECT|"
        r"INSERT|UPDATE|DELETE|DROP|TRUNCATE|"
        r"ALTER|MERGE|CREATE|GRANT|REVOKE"
        r")\b"
    )

    if re.search(
        forbidden,
        projection,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            "Instrucao nao autorizada na projecao Silver"
        )

    return projection, hashlib.sha256(raw).hexdigest()


# ============================================================
# 5. CONTROLE DE VERSAO DA BRONZE
# ============================================================

def snapshot(spark):
    """Identifica a versao Delta atual da Bronze."""

    row = spark.sql(
        f"DESCRIBE HISTORY {SOURCE} LIMIT 1"
    ).first()

    if row is None:
        raise RuntimeError(
            "Nao foi possivel identificar a versao da Bronze"
        )

    return int(row["version"])


def build_select(projection, version):
    """Usa a mesma versao da Bronze em toda a execucao."""

    return (
        f"{projection} "
        f"FROM {SOURCE} VERSION AS OF {version} "
        "WHERE CD_MUN = '3550308'"
    )


# ============================================================
# 6. VALIDACAO DE QUALIDADE
# ============================================================

def validate(df):
    """Valida as regras demograficas e territoriais."""

    if df.columns != COLUMNS:
        raise ValueError(
            f"Colunas inesperadas: {df.columns}"
        )

    # A coleta e limitada ao recorte de 96 distritos.
    # Este metodo nao deve ser reutilizado em bases grandes.
    rows = df.collect()

    if len(rows) != 96:
        raise ValueError(
            f"Esperados 96 distritos; recebidos {len(rows)}"
        )

    seen = set()
    errors = []

    nonnegative = [
        "total_pessoas",
        "total_domicilios",
        "total_domicilios_particulares",
        "total_domicilios_coletivos",
        "total_domicilios_particulares_ocupados",
        "total_domicilios_uso_ocasional",
        "total_domicilios_permanentes_vagos",
    ]

    for row in rows:
        code = str(
            row["CD_DIST"] or ""
        ).strip()

        if not code or code in seen:
            errors.append(
                f"codigo ausente ou duplicado: {code!r}"
            )

        seen.add(code)

        if any(
            row[col] is None
            for col in COLUMNS
        ):
            errors.append(
                f"{code}: uma ou mais colunas nulas"
            )
            continue

        if (
            not str(row["NM_DIST"]).strip()
            or str(row["CD_MUN"]).strip() != "3550308"
        ):
            errors.append(
                f"{code}: identificacao territorial invalida"
            )

        if (
            row["area_km2"] <= 0
            or row[
                "media_moradores_domicilios_ocupados"
            ] <= 0
        ):
            errors.append(
                f"{code}: area ou media de moradores invalida"
            )

        if (
            row["total_pessoas"] <= 0
            or row["total_domicilios"] <= 0
        ):
            errors.append(
                f"{code}: populacao ou domicilios nao positivos"
            )

        if any(
            row[col] < 0
            for col in nonnegative
        ):
            errors.append(
                f"{code}: quantidade negativa"
            )

        if row["total_domicilios"] != (
            row["total_domicilios_particulares"]
            + row["total_domicilios_coletivos"]
        ):
            errors.append(
                f"{code}: total de domicilios nao reconciliado"
            )

        if row["total_domicilios_particulares"] != (
            row["total_domicilios_particulares_ocupados"]
            + row["total_domicilios_uso_ocasional"]
            + row["total_domicilios_permanentes_vagos"]
        ):
            errors.append(
                f"{code}: domicilios particulares "
                "nao reconciliados"
            )

        percentage = row[
            "percentual_domicilios_ocupados_imputados"
        ]

        if not 0 <= percentage <= 100:
            errors.append(
                f"{code}: percentual imputado fora do intervalo"
            )

    if errors:
        raise ValueError(
            "Falha de qualidade: "
            + " | ".join(errors[:15])
        )

    return rows


# ============================================================
# 7. COMPARACAO COM A SILVER EXISTENTE
# ============================================================

def same_as_target(spark, proposed):
    """Compara os dados novos com a Silver atual."""

    if not spark.catalog.tableExists(TARGET):
        return False

    existing = spark.table(TARGET)

    if existing.columns != COLUMNS:
        raise ValueError(
            "Schema da Silver existente diverge; "
            "publicacao bloqueada"
        )

    if existing.count() != len(proposed):
        return False

    old = (
        existing
        .select(*COLUMNS)
        .collect()
    )

    def as_tuples(rows):
        return Counter(
            tuple(row[col] for col in COLUMNS)
            for row in rows
        )

    return as_tuples(old) == as_tuples(proposed)


# ============================================================
# 8. AUDITORIA DE PUBLICACAO
# ============================================================

def audit(
    spark,
    run_id,
    event,
    source_version,
    sql_sha256,
    rows,
    error=None,
):
    """Registra eventos da publicacao na camada observability."""

    from pyspark.sql.types import (
        StructType,
        StructField,
        StringType,
        LongType,
        TimestampType,
    )

    schema = StructType([
        StructField("run_id", StringType(), False),
        StructField("event_at", TimestampType(), False),
        StructField("status", StringType(), False),
        StructField("source_version", LongType(), False),
        StructField("sql_sha256", StringType(), False),
        StructField("total_distritos", LongType(), False),
        StructField("error_message", StringType(), True),
    ])

    record = [(
        run_id,
        datetime.now(timezone.utc),
        event,
        source_version,
        sql_sha256,
        rows,
        error,
    )]

    (
        spark.createDataFrame(record, schema)
        .write
        .format("delta")
        .mode("append")
        .saveAsTable(AUDIT)
    )

    emit(
        "AUDIT",
        status=event,
        run_id=run_id,
    )


# ============================================================
# 9. EXECUTOR PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--check",
        action="store_true",
        help="Validacao sem gravacao",
    )

    mode.add_argument(
        "--apply",
        action="store_true",
        help="Publicacao controlada",
    )

    parser.add_argument(
        "--confirm-publish",
        action="store_true",
    )

    args = parser.parse_args()

    if args.apply != args.confirm_publish:
        parser.error(
            "Para publicar, informe "
            "--apply --confirm-publish"
        )

    projection, sql_sha256 = load_select()

    emit(
        "SQL_VALIDATED",
        file=str(SQL_FILE),
        sha256=sql_sha256,
    )

    # Modo padrao: apenas validacao estatica.
    if not (args.check or args.apply):
        return

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()

    # Fixa a versao da origem.
    version = snapshot(spark)

    select = build_select(
        projection,
        version,
    )

    # Valida antes de qualquer publicacao.
    rows = validate(
        spark.sql(select)
    )

    identical = same_as_target(
        spark,
        rows,
    )

    emit(
        "DATA_VALIDATED",
        source_version=version,
        total_distritos=len(rows),
        identical_to_target=identical,
    )

    # CHECK: nunca grava dados ou auditoria.
    if not args.apply:
        emit(
            "CHECK_SUCCESS",
            changed_tables=False,
        )
        return

    # Nao reprocessar dados identicos.
    if identical:
        emit(
            "UNCHANGED",
            message=(
                "Silver existente ja corresponde "
                "ao resultado"
            ),
        )
        return

    # Evita publicar um snapshot desatualizado.
    if snapshot(spark) != version:
        raise RuntimeError(
            "Bronze mudou durante a validacao; "
            "tente novamente"
        )

    run_id = str(uuid4())

    # Prepara auditoria antes da publicacao.
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {AUDIT} ("
        "run_id STRING, "
        "event_at TIMESTAMP, "
        "status STRING, "
        "source_version BIGINT, "
        "sql_sha256 STRING, "
        "total_distritos BIGINT, "
        "error_message STRING"
        ") USING DELTA"
    )

    audit(
        spark,
        run_id,
        "STARTED",
        version,
        sql_sha256,
        len(rows),
    )

    try:
        # Publicacao explicita.
        # Esta instrucao substitui a tabela destino.
        spark.sql(
            f"CREATE OR REPLACE TABLE {TARGET} "
            f"USING DELTA AS {select}"
        ).collect()

        # Confere os dados apos a publicacao.
        if not same_as_target(spark, rows):
            raise RuntimeError(
                "Silver publicada difere "
                "dos dados validados"
            )

        audit(
            spark,
            run_id,
            "SUCCESS",
            version,
            sql_sha256,
            len(rows),
        )

        emit(
            "SILVER_IBGE_SUCCESS",
            target=TARGET,
            source_version=version,
        )

    except Exception as exc:
        try:
            audit(
                spark,
                run_id,
                "FAILED",
                version,
                sql_sha256,
                len(rows),
                str(exc)[:4000],
            )

        except Exception as audit_error:
            emit(
                "AUDIT_FAILED",
                error=str(audit_error),
            )

        raise


if __name__ == "__main__":
    main()
