"""BairroIQ: validação e aplicação dos cinco DDLs Bronze.

Sem argumentos: valida os arquivos, sem acessar o Spark.
Com --apply: aplica os DDLs e persiste auditoria no Databricks.

Executar como arquivo Python em uma spark_python_task.
"""

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SQL_DIR = Path(__file__).resolve().parent / "sql" / "bronze"
AUDIT_TABLE = "workspace.observability.bronze_ddl_runs"

EXPECTED = {
    "001_geo_sampa.sql": "workspace.bronze.geo_sampa",
    "002_ibge.sql": "workspace.bronze.ibge_agregados_basico_distritos",
    "003_imoveis.sql": "workspace.bronze.imoveis",
    "004_observa_sampa.sql": "workspace.bronze.observa_sampa",
    "005_ssp.sql": "workspace.bronze.dados_criminais_unificado_ssp",
}

AUDIT_SCHEMA = """
    run_id STRING,
    event_id STRING,
    event_at TIMESTAMP,
    filename STRING,
    table_name STRING,
    sql_sha256 STRING,
    status STRING,
    existed_before BOOLEAN,
    duration_seconds DOUBLE,
    error_message STRING
"""

# Gramática restrita aos tipos e opções presentes nos cinco DDLs.
# Mudanças futuras na sintaxe devem passar por revisão do executor.
IDENTIFIER = r"(?:[A-Za-z_][A-Za-z0-9_]*|`[^`\r\n]+`)"
COLUMN = (
    rf"{IDENTIFIER}\s+"
    r"(?:INT|DATE|STRING(?:\s+COLLATE\s+UTF8_BINARY)?)"
)
COLUMNS = rf"{COLUMN}(?:\s*,\s*{COLUMN})*"
COMMENT = r"(?:\s+COMMENT\s+'(?:[^']|'')*')?"


def emit(**event):
    """Mantém evidência nos logs, inclusive se a auditoria falhar."""
    print(json.dumps(event, ensure_ascii=False, default=str), flush=True)


def validate_files(sql_dir):
    """Valida o conjunto inteiro e mantém os SQLs validados em memória."""
    if not sql_dir.is_dir():
        raise ValueError(f"Diretório SQL não encontrado: {sql_dir}")

    actual = {path.name for path in sql_dir.glob("*.sql")}
    expected = set(EXPECTED)

    if actual != expected:
        raise ValueError(
            f"Arquivos ausentes: {sorted(expected - actual)}; "
            f"arquivos extras: {sorted(actual - expected)}"
        )

    validated = []

    for filename, table in EXPECTED.items():
        raw = (sql_dir / filename).read_bytes()
        text = raw.decode("utf-8-sig")

        # Remove apenas comentários que ocupam uma linha completa.
        statement = re.sub(
            r"(?m)^[ \t]*--[^\r\n]*$",
            "",
            text,
        ).strip()

        # Uma única instrução, sem CTAS, LOCATION, substituição,
        # alterações de tabela ou comandos de escrita de dados.
        pattern = (
            rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+"
            rf"{re.escape(table)}\s*"
            rf"\(\s*{COLUMNS}\s*\)\s+"
            rf"USING\s+DELTA"
            rf"{COMMENT}"
            rf"\s+CLUSTER\s+BY\s+AUTO\s*;"
        )

        if not re.fullmatch(pattern, statement, flags=re.IGNORECASE):
            raise ValueError(
                f"{filename}: DDL fora do formato permitido. "
                "Revise o arquivo; nenhuma DDL Bronze foi executada."
            )

        validated.append({
            "filename": filename,
            "table": table,
            "sql": statement,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })

    return validated


def write_audit(
    spark,
    run_id,
    item,
    status,
    existed_before=None,
    duration_seconds=0.0,
    error_message=None,
):
    record = {
        "run_id": run_id,
        "event_id": str(uuid4()),
        "event_at": datetime.now(timezone.utc),
        "filename": item["filename"],
        "table_name": item["table"],
        "sql_sha256": item["sha256"],
        "status": status,
        "existed_before": existed_before,
        "duration_seconds": float(duration_seconds),
        "error_message": error_message,
    }

    emit(**record)

    # A tabela de auditoria precisa ter sido criada previamente
    # por apply_files. Aqui só acrescentamos eventos.
    (
        spark.createDataFrame([record], schema=AUDIT_SCHEMA)
        .write
        .format("delta")
        .mode("append")
        .saveAsTable(AUDIT_TABLE)
    )


def apply_files(spark, validated, run_id):
    # O schema observability já é provisionado pelo Terraform.
    # Esta tabela é independente da auditoria de Data Quality.
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} "
        f"({AUDIT_SCHEMA}) USING DELTA"
    ).collect()

    # Verifica acesso e estrutura antes de aplicar qualquer DDL Bronze.
    spark.table(AUDIT_TABLE).select(
        "run_id",
        "event_id",
        "event_at",
        "filename",
        "table_name",
        "sql_sha256",
        "status",
        "existed_before",
        "duration_seconds",
        "error_message",
    ).limit(0).collect()

    for item in validated:
        started = time.perf_counter()
        existed_before = None

        try:
            existed_before = spark.catalog.tableExists(item["table"])

            # Se este registro falhar, a DDL não será executada.
            write_audit(
                spark,
                run_id,
                item,
                "STARTED",
                existed_before=existed_before,
            )

            spark.sql(item["sql"]).collect()

            if not spark.catalog.tableExists(item["table"]):
                raise RuntimeError(
                    f"Tabela não encontrada após a DDL: {item['table']}"
                )

            # Confirma que o objeto resultante é uma tabela Delta.
            detail = spark.sql(
                f"DESCRIBE DETAIL {item['table']}"
            ).first()

            if detail is None or str(detail["format"]).lower() != "delta":
                raise RuntimeError(
                    f"O objeto não é uma tabela Delta: {item['table']}"
                )

            write_audit(
                spark,
                run_id,
                item,
                "SUCCESS",
                existed_before=existed_before,
                duration_seconds=time.perf_counter() - started,
            )

        except Exception as exc:
            try:
                write_audit(
                    spark,
                    run_id,
                    item,
                    "FAILED",
                    existed_before=existed_before,
                    duration_seconds=time.perf_counter() - started,
                    error_message=str(exc)[:8000],
                )
            except Exception as audit_exc:
                emit(
                    event="AUDIT_WRITE_FAILED",
                    run_id=run_id,
                    filename=item["filename"],
                    original_error=str(exc),
                    audit_error=str(audit_exc),
                )

            # Interrompe o Job e preserva a causa original.
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar DDLs e gravar auditoria usando Spark.",
    )
    args = parser.parse_args()

    run_id = str(uuid4())
    started = time.perf_counter()

    try:
        validated = validate_files(SQL_DIR)

        for item in validated:
            emit(
                event="DDL_VALIDATED",
                run_id=run_id,
                filename=item["filename"],
                table_name=item["table"],
                sql_sha256=item["sha256"],
            )

        if not args.apply:
            emit(
                event="VALIDATION_SUCCESS",
                run_id=run_id,
                files=len(validated),
                applied=False,
            )
            return

        # Import tardio permite validar no CI sem instalar PySpark.
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        apply_files(spark, validated, run_id)

        emit(
            event="BRONZE_DDL_SUCCESS",
            run_id=run_id,
            files=len(validated),
            applied=True,
            duration_seconds=time.perf_counter() - started,
        )

    except Exception as exc:
        emit(
            event="BRONZE_DDL_FAILED",
            run_id=run_id,
            duration_seconds=time.perf_counter() - started,
            error_message=str(exc),
        )
        raise


if __name__ == "__main__":
    main()
