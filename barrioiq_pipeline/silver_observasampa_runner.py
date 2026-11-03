
"""BairroIQ | Silver ObservaSampa - indicadores distritais de Sao Paulo.

Preserva todos os indicadores e anos da Bronze, sem projetar
empregos de 2021 para 2026 ou misturar granularidades.

Fonte: workspace.bronze.observa_sampa
Referencia: workspace.silver.geosampa_equipamentos_distrito
Destino: workspace.silver.observasampa_indicadores_distrito

Uso:
    python silver_observasampa_runner.py --check
    python silver_observasampa_runner.py --apply --confirm-publish

--check: somente leitura, nenhuma tabela modificada.
--apply: cria a tabela apenas se ela ainda nao existir.
          Nunca substitui automaticamente dados divergentes.
"""

import argparse
from decimal import Decimal, InvalidOperation
import json
import re
import unicodedata


SOURCE = "workspace.bronze.observa_sampa"
REFERENCE = "workspace.silver.geosampa_equipamentos_distrito"
TARGET = "workspace.silver.observasampa_indicadores_distrito"

EXPECTED_DISTRICTS = 96

NUMERIC_PATTERN = r"^[+-]?[0-9]+([.,][0-9]{1,8})?$"
# ObservaSampa utiliza virgula como separador decimal.
# Pontos com tres casas permanecem ambiguos.
AMBIGUOUS_PATTERN = r"^[+-]?[0-9]{1,3}\.[0-9]{3}$"

OUTPUT_COLUMNS = [
    "CD_DIST",
    "NM_DIST",
    "regiao_origem",
    "indicador",
    "ano",
    "resultado_texto",
    "valor_numerico",
    "status_valor",
    "fonte",
    "versao_bronze_observasampa",
    "versao_silver_geosampa",
]


class ContractError(ValueError):
    """Contrato de dados nao atendido."""


def emit(event, **details):
    print(
        json.dumps(
            {"event": event, **details},
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        ),
        flush=True,
    )


def normalizar(nome):
    if not isinstance(nome, str):
        return None

    sem_acentos = "".join(
        c
        for c in unicodedata.normalize("NFKD", nome)
        if not unicodedata.combining(c)
    )

    chave = re.sub(
        r"\s+", " ", sem_acentos
    ).strip().upper()

    if not chave or "\ufffd" in chave:
        return None

    return chave


def nome_distrito(regiao):
    if not isinstance(regiao, str):
        return None

    match = re.fullmatch(
        r"\s*(.*?)\s*\(\s*distrito\s*\)\s*",
        regiao,
        re.IGNORECASE,
    )

    return match.group(1).strip() if match else None


def build_reference(district_rows, region_names):
    """Associa os 96 territorios sem correspondencia aproximada."""

    by_key = {}
    codes = set()

    rows = list(district_rows)
    regions = list(region_names)

    if (
        len(rows) != EXPECTED_DISTRICTS
        or len(regions) != EXPECTED_DISTRICTS
    ):
        raise ContractError(
            "Referencia e regioes devem ter 96 distritos"
        )

    for raw in rows:
        row = (
            raw.asDict()
            if hasattr(raw, "asDict")
            else dict(raw)
        )

        name = row.get("NM_DIST")
        key = normalizar(name)
        code = row.get("CD_DIST")

        if (
            not key
            or code is None
            or key in by_key
            or int(code) in codes
        ):
            raise ContractError(
                f"Referencia territorial invalida: {name!r}"
            )

        codes.add(int(code))
        by_key[key] = (int(code), name)

    mapping = []
    names_seen = set()

    for raw in regions:
        regiao = (
            raw["regiao"]
            if isinstance(raw, dict)
            or hasattr(raw, "__getitem__")
            else str(raw)
        )

        key = normalizar(nome_distrito(regiao))

        if not key or key in names_seen:
            raise ContractError(
                f"Regiao nao distrital/duplicada: {regiao!r}"
            )

        names_seen.add(key)

        if key not in by_key:
            raise ContractError(
                f"Distrito sem correspondencia: {regiao!r}"
            )

        code, official = by_key[key]
        mapping.append((regiao, code, official))

    if names_seen != set(by_key):
        raise ContractError(
            "Nem todos os distritos foram encontrados"
        )

    return mapping


def parse_numeric(text):
    """Validador local do contrato numerico.

    Nao presume que 1.234 ou 1,234 sejam milhar ou decimal.
    Esses formatos sao ambiguos e exigem revisao.
    """

    if text is None or not str(text).strip():
        return None, "VAZIO"

    value = str(text).strip()

    if re.fullmatch(AMBIGUOUS_PATTERN, value):
        return None, "AMBIGUO"

    if not re.fullmatch(NUMERIC_PATTERN, value):
        return None, "FORMATO_INVALIDO"

    try:
        result = Decimal(
            value.replace(",", ".")
        )
    except InvalidOperation:
        return None, "FORMATO_INVALIDO"

    integer_digits = max(
        len(result.as_tuple().digits)
        + result.as_tuple().exponent,
        0,
    )

    if integer_digits > 20:
        return None, "TIPAGEM_INVALIDA"

    return result, "OK"


def version(spark, table):
    row = spark.sql(
        f"DESCRIBE HISTORY {table} LIMIT 1"
    ).first()

    if row is None or row["version"] is None:
        raise ContractError(
            f"Versao Delta nao encontrada: {table}"
        )

    return int(row["version"])


def build(spark, source_version, ref_version):
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        StructType,
        StructField,
        StringType,
        IntegerType,
    )

    required = {
        "Nome",
        "Região",
        "Período",
        "Resultado",
        "_rescued_data",
    }

    missing = required - set(
        spark.table(SOURCE).columns
    )

    if missing:
        raise ContractError(
            f"Colunas Bronze ausentes: {sorted(missing)}"
        )

    # Snapshot imutavel da Bronze.
    raw = spark.sql(
        "SELECT "
        "TRIM(Nome) AS indicador, "
        "TRIM(`Região`) AS regiao, "
        "`Período` AS ano, "
        "TRIM(Resultado) AS resultado_texto, "
        "_rescued_data "
        f"FROM {SOURCE} VERSION AS OF {source_version}"
    )

    # Somente distritos. As demais granularidades
    # permanecem preservadas na Bronze.
    district = raw.filter(
        F.col("regiao").rlike(
            r"(?i)\(\s*distrito\s*\)\s*$"
        )
    )

    region_rows = (
        district
        .select("regiao")
        .distinct()
        .collect()
    )

    reference_rows = spark.sql(
        "SELECT CD_DIST, NM_DIST "
        f"FROM {REFERENCE} VERSION AS OF {ref_version}"
    ).collect()

    mapping = build_reference(
        reference_rows,
        region_rows,
    )

    schema = StructType([
        StructField(
            "regiao", StringType(), False
        ),
        StructField(
            "CD_DIST", IntegerType(), False
        ),
        StructField(
            "NM_DIST", StringType(), False
        ),
    ])

    depara = spark.createDataFrame(
        mapping,
        schema=schema,
    )

    joined = district.join(
        F.broadcast(depara),
        "regiao",
        "left",
    )

    # Converte somente numeros sem ambiguidade.
    normalized = joined.withColumn(
        "valor_numerico",
        F.when(
            F.col("resultado_texto").rlike(
                NUMERIC_PATTERN
            )
            & ~F.col("resultado_texto").rlike(
                AMBIGUOUS_PATTERN
            ),
            F.expr(
                "TRY_CAST("
                "REPLACE(resultado_texto, ',', '.') "
                "AS DECIMAL(28, 8))"
            ),
        ).otherwise(
            F.lit(None).cast("decimal(28,8)")
        ),
    ).withColumn(
        "status_valor",
        F.when(
            F.col("resultado_texto").isNull()
            | (F.length("resultado_texto") == 0),
            "VAZIO",
        )
        .when(
            F.col("resultado_texto").rlike(
                AMBIGUOUS_PATTERN
            ),
            "AMBIGUO",
        )
        .when(
            ~F.col("resultado_texto").rlike(
                NUMERIC_PATTERN
            ),
            "FORMATO_INVALIDO",
        )
        .when(
            F.col("valor_numerico").isNull(),
            "TIPAGEM_INVALIDA",
        )
        .otherwise("OK"),
    )

    proposed = normalized.select(
        "CD_DIST",
        "NM_DIST",
        F.col("regiao").alias("regiao_origem"),
        "indicador",
        "ano",
        "resultado_texto",
        "valor_numerico",
        "status_valor",
        F.lit("ObservaSampa").alias("fonte"),
        F.lit(
            int(source_version)
        ).cast("long").alias(
            "versao_bronze_observasampa"
        ),
        F.lit(
            int(ref_version)
        ).cast("long").alias(
            "versao_silver_geosampa"
        ),
    )

    # Qualidade dos identificadores e dos dados brutos.
    invalid_input = joined.filter(
        F.col("indicador").isNull()
        | (F.length("indicador") == 0)
        | F.col("ano").isNull()
        | (F.col("ano") < 1900)
        | (F.col("ano") > 2100)
        | F.col("CD_DIST").isNull()
        | (
            F.col("_rescued_data").isNotNull()
            & (
                F.length(
                    F.trim("_rescued_data")
                ) > 0
            )
        )
    ).limit(1).count()

    if invalid_input:
        raise ContractError(
            "Indicador, ano, distrito "
            "ou _rescued_data invalido"
        )

    # Chave unica: distrito + indicador + ano.
    duplicates = (
        proposed
        .groupBy(
            "CD_DIST",
            "indicador",
            "ano",
        )
        .count()
        .filter(
            F.col("count") > 1
        )
        .limit(5)
        .collect()
    )

    if duplicates:
        raise ContractError(
            f"Chaves distritais duplicadas: {duplicates}"
        )

    summary = proposed.agg(
        F.count("*").alias("rows"),
        F.countDistinct(
            "CD_DIST"
        ).alias("districts"),
        F.countDistinct(
            "indicador"
        ).alias("indicators"),
        F.min("ano").alias("min_year"),
        F.max("ano").alias("max_year"),
        F.sum(
            F.when(
                F.col("status_valor") != "OK",
                1,
            ).otherwise(0)
        ).alias("invalid_values"),
    ).first().asDict()

    if (
        not summary["rows"]
        or summary["districts"] != 96
    ):
        raise ContractError(
            f"Cardinalidade territorial invalida: {summary}"
        )

    # Nenhuma conversao ambigua pode ser publicada.
    if summary["invalid_values"]:
        examples = (
            proposed
            .filter(
                F.col("status_valor") != "OK"
            )
            .select(
                "indicador",
                "ano",
                "resultado_texto",
                "status_valor",
            )
            .limit(12)
            .collect()
        )

        raise ContractError(
            "Resultados nao numericos/ambiguos: "
            f"{examples}"
        )

    return proposed, summary


def equal_target(spark, proposed):
    if not spark.catalog.tableExists(TARGET):
        return False

    old = spark.table(TARGET)

    schema_old = [
        (
            f.name,
            f.dataType.simpleString(),
        )
        for f in old.schema
    ]

    schema_new = [
        (
            f.name,
            f.dataType.simpleString(),
        )
        for f in proposed.schema
    ]

    if schema_old != schema_new:
        raise ContractError(
            "Schema da Silver existente difere; "
            "substituicao bloqueada"
        )

    if old.count() != proposed.count():
        return False

    return (
        not old.exceptAll(
            proposed
        ).limit(1).count()
        and not proposed.exceptAll(
            old
        ).limit(1).count()
    )


def execute(spark, apply=False):
    source_version = version(
        spark, SOURCE
    )

    reference_version = version(
        spark, REFERENCE
    )

    proposed, summary = build(
        spark,
        source_version,
        reference_version,
    )

    identical = equal_target(
        spark,
        proposed,
    )

    emit(
        "OBSERVASAMPA_SILVER_VALIDATED",
        **summary,
        source_version=source_version,
        reference_version=reference_version,
        identical_to_target=identical,
    )

    if not apply:
        emit(
            "OBSERVASAMPA_SILVER_CHECK_SUCCESS",
            changed_tables=False,
        )
        return summary

    if identical:
        emit(
            "OBSERVASAMPA_SILVER_UNCHANGED",
            changed_tables=False,
        )
        return summary

    if spark.catalog.tableExists(TARGET):
        raise ContractError(
            "Silver existente tem dados divergentes; "
            "publicacao bloqueada"
        )

    if (
        version(spark, SOURCE) != source_version
        or version(
            spark, REFERENCE
        ) != reference_version
    ):
        raise ContractError(
            "Fontes Delta mudaram durante a validacao"
        )

    # Somente cria a tabela quando ela nao existe.
    proposed.write.format(
        "delta"
    ).mode(
        "errorifexists"
    ).saveAsTable(TARGET)

    if not equal_target(spark, proposed):
        raise ContractError(
            "Tabela criada nao corresponde "
            "ao resultado validado"
        )

    emit(
        "OBSERVASAMPA_SILVER_APPLY_SUCCESS",
        target=TARGET,
        **summary,
    )

    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--check", action="store_true"
    )

    mode.add_argument(
        "--apply", action="store_true"
    )

    parser.add_argument(
        "--confirm-publish",
        action="store_true",
    )

    args = parser.parse_args(argv)

    if args.apply != args.confirm_publish:
        parser.error(
            "Publicacao exige "
            "--apply --confirm-publish; "
            "--check e somente leitura"
        )

    from pyspark.sql import SparkSession

    execute(
        SparkSession.builder.getOrCreate(),
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
