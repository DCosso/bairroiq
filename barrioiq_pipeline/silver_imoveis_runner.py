
"""BairroIQ | Silver Imoveis v1, granularidade mensal por bairro de origem.

Fonte: workspace.bronze.imoveis
Destino: workspace.silver.imoveis_bairro_mensal

Uso:
    python silver_imoveis_runner.py --check
    python silver_imoveis_runner.py --apply --confirm-publish

--check nunca altera tabelas ou arquivos.
--apply apenas cria o destino se ele ainda nao existir; nao sobrescreve
uma Silver divergente. Nao associa bairros de mercado aos 96 distritos.
"""

import argparse
from collections import Counter
from datetime import date
import json
import re
import unicodedata
from uuid import uuid4

SOURCE = "workspace.bronze.imoveis"
TARGET = "workspace.silver.imoveis_bairro_mensal"

BASELINE_ROWS = 29612
BASELINE_BAIRROS = 1626
BASELINE_MESES = 14

# Protecao de memoria para esta v1 em dados pequenos.
MAX_ROWS = 250000

SOURCE_COLUMNS = [
    "mes",
    "bairro",
    "transacao",
    "mediana_m2",
    "p25_m2",
    "p75_m2",
    "anuncios_ativos_media_dia",
    "novos_anuncios",
    "dias_no_mercado_medio",
    "_rescued_data",
]

OUTPUT_COLUMNS = [
    "mes",
    "bairro",
    "bairro_normalizado",
    "transacao",
    "mediana_m2",
    "p25_m2",
    "p75_m2",
    "anuncios_ativos_media_dia",
    "novos_anuncios",
    "dias_no_mercado_medio",
    "status_preco",
    "versao_bronze_imoveis",
]


class ContractError(ValueError):
    """Violacao de contrato dos dados imobiliarios."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def emit(event, **details):
    print(
        json.dumps(
            {"event": event, **details},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ),
        flush=True,
    )


def normalizar_bairro(value):
    require(
        isinstance(value, str) and bool(value.strip()),
        "Bairro nulo ou em branco",
    )

    normalized = "".join(
        c
        for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )

    normalized = re.sub(
        r"\s+", " ", normalized
    ).strip().upper()

    require(
        bool(normalized) and "\ufffd" not in normalized,
        f"Bairro com nome invalido: {value!r}",
    )

    return normalized


def validate_non_negative(
    value, field, key, nullable=False
):
    if value is None:
        require(
            nullable,
            f"{field} nulo em {key}",
        )
        return

    require(
        type(value) is int and value >= 0,
        f"{field} invalido em {key}: {value!r}",
    )


def transform_record(record, source_version):
    row = (
        record.asDict(recursive=True)
        if hasattr(record, "asDict")
        else dict(record)
    )

    require(
        not row.get("_rescued_data"),
        "_rescued_data nao vazio na Bronze Imoveis",
    )

    mes = row.get("mes")

    require(
        isinstance(mes, date)
        and not isinstance(mes, str),
        f"Mes invalido: {mes!r}",
    )

    require(
        mes.day == 1,
        f"Mes fora do primeiro dia: {mes!r}",
    )

    bairro = row.get("bairro")
    bairro_normalizado = normalizar_bairro(bairro)

    transacao = row.get("transacao")

    require(
        isinstance(transacao, str)
        and transacao in {"venda", "aluguel"},
        f"Transacao nao prevista: {transacao!r}",
    )

    key = (mes, bairro, transacao)

    for field in (
        "anuncios_ativos_media_dia",
        "novos_anuncios",
    ):
        validate_non_negative(
            row.get(field),
            field,
            key,
        )

    validate_non_negative(
        row.get("dias_no_mercado_medio"),
        "dias_no_mercado_medio",
        key,
        nullable=True,
    )

    prices = [
        row.get(f)
        for f in (
            "p25_m2",
            "mediana_m2",
            "p75_m2",
        )
    ]

    if all(value is None for value in prices):
        status = "TRES_PRECOS_NULOS"

    else:
        require(
            all(
                type(value) is int and value > 0
                for value in prices
            ),
            "Precos parcialmente nulos "
            f"ou nao positivos: {key}: {prices}",
        )

        require(
            prices[0] <= prices[1] <= prices[2],
            f"Percentis incoerentes: {key}: {prices}",
        )

        status = "PRECO_VALIDO"

    output = {
        "mes": mes,

        # Preserva o nome original do bairro.
        "bairro": bairro,

        # Chave auxiliar. Nao representa distrito.
        "bairro_normalizado": bairro_normalizado,

        "transacao": transacao,
        "mediana_m2": row.get("mediana_m2"),
        "p25_m2": row.get("p25_m2"),
        "p75_m2": row.get("p75_m2"),

        "anuncios_ativos_media_dia": row.get(
            "anuncios_ativos_media_dia"
        ),

        "novos_anuncios": row.get(
            "novos_anuncios"
        ),

        "dias_no_mercado_medio": row.get(
            "dias_no_mercado_medio"
        ),

        "status_preco": status,
        "versao_bronze_imoveis": source_version,
    }

    return output


def validate_records(records, source_version):
    require(
        records,
        "Bronze Imoveis vazia",
    )

    require(
        len(records) <= MAX_ROWS,
        "Limite de linhas da v1 excedido",
    )

    output = []
    keys = set()
    stats = Counter()

    bairros = set()
    meses = set()
    transacoes = set()

    for record in records:
        data = transform_record(
            record,
            source_version,
        )

        key = (
            data["mes"],
            data["bairro"],
            data["transacao"],
        )

        require(
            key not in keys,
            f"Chave duplicada: {key}",
        )

        keys.add(key)
        output.append(data)

        stats[data["status_preco"]] += 1

        bairros.add(data["bairro"])
        meses.add(data["mes"])
        transacoes.add(data["transacao"])

    # As contagens do diagnostico inicial sao
    # um piso de seguranca, nao um limite superior.
    # O total de precos nulos pode mudar.

    require(
        len(output) >= BASELINE_ROWS,
        "Perda de linhas frente a base inicial: "
        f"{len(output)}",
    )

    require(
        len(bairros) >= BASELINE_BAIRROS,
        f"Cobertura de bairros caiu: {len(bairros)}",
    )

    require(
        len(meses) >= BASELINE_MESES,
        f"Cobertura temporal caiu: {len(meses)}",
    )

    require(
        transacoes == {"venda", "aluguel"},
        "Tipos de transacao inesperados: "
        f"{transacoes}",
    )

    summary = {
        "rows": len(output),
        "bairros_origem": len(bairros),
        "meses": len(meses),
        "primeiro_mes": str(min(meses)),
        "ultimo_mes": str(max(meses)),

        "precos_validos": stats[
            "PRECO_VALIDO"
        ],

        "tres_precos_nulos": stats[
            "TRES_PRECOS_NULOS"
        ],
    }

    return output, summary


def delta_version(spark, table):
    row = spark.sql(
        f"DESCRIBE HISTORY {table} LIMIT 1"
    ).first()

    require(
        row is not None,
        f"Tabela Delta sem historico: {table}",
    )

    return int(row["version"])


def load_snapshot(spark, source_version):
    available = set(
        spark.table(SOURCE).columns
    )

    missing = (
        set(SOURCE_COLUMNS) - available
    )

    require(
        not missing,
        "Colunas ausentes na Bronze: "
        f"{sorted(missing)}",
    )

    selected = ", ".join(
        f"`{name}`"
        for name in SOURCE_COLUMNS
    )

    df = spark.sql(
        f"SELECT {selected} "
        f"FROM {SOURCE} "
        f"VERSION AS OF {source_version}"
    )

    records = df.limit(
        MAX_ROWS + 1
    ).collect()

    require(
        len(records) <= MAX_ROWS,
        "Bronze excede limite de memoria "
        "da v1; revisar arquitetura",
    )

    return records


def output_dataframe(spark, rows):
    from pyspark.sql.types import (
        DateType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
    )

    schema = StructType([
        StructField(
            "mes", DateType(), False
        ),
        StructField(
            "bairro", StringType(), False
        ),
        StructField(
            "bairro_normalizado",
            StringType(),
            False,
        ),
        StructField(
            "transacao", StringType(), False
        ),
        StructField(
            "mediana_m2", IntegerType(), True
        ),
        StructField(
            "p25_m2", IntegerType(), True
        ),
        StructField(
            "p75_m2", IntegerType(), True
        ),
        StructField(
            "anuncios_ativos_media_dia",
            IntegerType(),
            False,
        ),
        StructField(
            "novos_anuncios",
            IntegerType(),
            False,
        ),
        StructField(
            "dias_no_mercado_medio",
            IntegerType(),
            True,
        ),
        StructField(
            "status_preco",
            StringType(),
            False,
        ),
        StructField(
            "versao_bronze_imoveis",
            LongType(),
            False,
        ),
    ])

    data = [
        tuple(
            row[col]
            for col in OUTPUT_COLUMNS
        )
        for row in rows
    ]

    return spark.createDataFrame(
        data,
        schema=schema,
    )


def equal_target(spark, proposed):
    if not spark.catalog.tableExists(TARGET):
        return False

    current = spark.table(TARGET)

    old_schema = [
        (
            f.name,
            f.dataType.simpleString(),
        )
        for f in current.schema
    ]

    new_schema = [
        (
            f.name,
            f.dataType.simpleString(),
        )
        for f in proposed.schema
    ]

    require(
        old_schema == new_schema,
        "Schema Silver existente e diferente; "
        "substituicao bloqueada",
    )

    if current.count() != proposed.count():
        return False

    return (
        current.exceptAll(
            proposed
        ).limit(1).count() == 0

        and proposed.exceptAll(
            current
        ).limit(1).count() == 0
    )


def execute(spark, apply=False):
    source_version = delta_version(
        spark,
        SOURCE,
    )

    records = load_snapshot(
        spark,
        source_version,
    )

    rows, summary = validate_records(
        records,
        source_version,
    )

    proposed = output_dataframe(
        spark,
        rows,
    )

    identical = equal_target(
        spark,
        proposed,
    )

    target_exists = spark.catalog.tableExists(
        TARGET
    )

    # Nao confirma validacao com Bronze mutavel.
    require(
        delta_version(spark, SOURCE)
        == source_version,
        "Bronze mudou durante a validacao; "
        "operacao interrompida",
    )

    emit(
        "IMOVEIS_SILVER_VALIDATED",
        **summary,
        source_version=source_version,
        target_exists=target_exists,
        identical_to_target=identical,
    )

    # Modo somente leitura.
    if not apply:
        emit(
            "IMOVEIS_SILVER_CHECK_SUCCESS",
            changed_tables=False,
            changed_files=False,
        )
        return summary

    # Nao reprocessa dados identicos.
    if identical:
        emit(
            "IMOVEIS_SILVER_UNCHANGED",
            changed_tables=False,
        )
        return summary

    # Nunca sobrescreve Silver divergente.
    require(
        not target_exists,
        "Silver ja existe e diverge; "
        "publicacao bloqueada",
    )

    require(
        delta_version(spark, SOURCE)
        == source_version,
        "Bronze mudou antes da publicacao; "
        "operacao interrompida",
    )

    # Criacao condicional compativel com
    # Databricks Serverless e Unity Catalog.
    temp_view = (
        "bairroiq_imoveis_publish_"
        f"{uuid4().hex}"
    )

    proposed.createOrReplaceTempView(
        temp_view
    )

    try:
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {TARGET} "
            f"USING DELTA AS "
            f"SELECT * FROM {temp_view}"
        ).collect()

    finally:
        spark.catalog.dropTempView(
            temp_view
        )

    require(
        equal_target(spark, proposed),
        "Tabela Silver publicada nao coincide "
        "com os dados validados",
    )

    emit(
        "IMOVEIS_SILVER_APPLY_SUCCESS",
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
        "--check",
        action="store_true",
    )

    mode.add_argument(
        "--apply",
        action="store_true",
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
