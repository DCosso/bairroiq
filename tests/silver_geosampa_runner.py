"""BairroIQ | Silver GeoSampa por distrito (96 distritos de Sao Paulo).

Faz a correspondencia entre nomes GeoSampa e nomes oficiais IBGE usando
normalizacao Unicode NFKD, sem correspondencia aproximada (fuzzy).

Uso no Databricks Serverless:
    python silver_geosampa_runner.py --check
    python silver_geosampa_runner.py --apply --confirm-publish

O modo --check e estritamente somente leitura: nao cria tabelas, nao grava
logs Delta, nao altera arquivos nem executa DDL. A publicacao exige dupla
confirmacao, validacao completa e versoes estaveis das duas fontes.

Nao confundir quantidade de pontos de infraestrutura GeoSampa com qualidade
ou frequencia do servico; nem imputar zeros onde a fonte apresenta NULL.
"""

import argparse
from collections import Counter
import json
import re
import unicodedata


SOURCE_GEOSAMPA = "workspace.bronze.geo_sampa"
SOURCE_IBGE = "workspace.silver.ibge_agregados_basicos_v2"
TARGET = "workspace.silver.geosampa_equipamentos_distrito"
EXPECTED_DISTRICTS = 96

# Nomes exatos definidos no DDL Bronze existente. Inclui a grafia original
# "qtd_ensino_infatil_publico", que nao deve ser corrigida sem migracao.
FEATURE_COLUMNS = [
    "qtd_bibliotecas",
    "qtd_espacos",
    "qtd_museus",
    "qtd_teatros_cinemas",
    "qtd_ensino_tecnico_publico",
    "qtd_ensino_infatil_publico",
    "qtd_escolas_privadas",
    "qtd_escolas_publicas",
    "qtd_sistema_s",
    "qtd_ceu",
    "qtd_centro_esportivo",
    "qtd_clubes",
    "qtd_clubes_comunidade",
    "qtd_estadios",
    "qtd_corredor_verde",
    "qtd_praca_largo",
    "qtd_ambulatorios",
    "qtd_hospitais",
    "qtd_saude_mental",
    "qtd_ubs",
    "qtd_urgencia_emergencia",
    "qtd_bicicletario",
    "qtd_metro",
    "qtd_trem",
    "qtd_onibus",
    "qtd_terminal_onibus",
    "qtd_bombeiros",
    "qtd_guarda_civil",
    "qtd_policia_civil",
    "qtd_policia_militar",
    "qtd_defesa_civil",
    "qtd_agencia_funeraria",
    "qtd_velorio",
    "qtd_cemiterio",
    "qtd_consulados",
    "qtd_correios",
    "qtd_feira_livre",
    "qtd_mercado_municipal",
    "qtd_eletropaulo",
    "qtd_sabesp",
    "qtd_poupatempo",
    "qtd_sacoloes",
]

GEO_COLUMNS = ["nm_distrit", *FEATURE_COLUMNS, "_rescued_data"]
IBGE_COLUMNS = ["CD_DIST", "NM_DIST", "CD_MUN"]
OUTPUT_COLUMNS = [
    "CD_DIST",
    "NM_DIST",
    "nm_distrit_geosampa",
    *FEATURE_COLUMNS,
    "qtd_indicadores_nulos",
    "cobertura_indicadores_pct",
    "fonte",
    "versao_bronze_geosampa",
    "versao_silver_ibge",
]


class DataQualityError(ValueError):
    """Dados que nao podem ser publicados com seguranca."""


def emit(event, **details):
    print(json.dumps(
        {"event": event, **details},
        ensure_ascii=False,
        default=str,
        sort_keys=True,
    ), flush=True)


def normalize_name(value):
    """Chave somente para igualdade, sem aproximacao ou geocodificacao."""
    if not isinstance(value, str):
        return None
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char for char in decomposed
        if not unicodedata.combining(char)
    )
    key = re.sub(r"\s+", " ", without_accents).strip().upper()
    return key or None


def row_dict(row):
    """Aceita Spark Row e dicionarios nos testes isolados."""
    return row.asDict(recursive=True) if hasattr(row, "asDict") else dict(row)


def require_96(rows, source):
    if len(rows) != EXPECTED_DISTRICTS:
        raise DataQualityError(
            f"{source}: esperados {EXPECTED_DISTRICTS} registros; "
            f"recebidos {len(rows)}"
        )


def index_names(rows, name_column, source):
    """Impede que dois registros diferentes representem a mesma chave."""
    require_96(rows, source)
    indexed = {}
    for raw in rows:
        row = row_dict(raw)
        name = row.get(name_column)
        key = normalize_name(name)
        if key is None:
            raise DataQualityError(f"{source}: nome de distrito vazio")
        if key in indexed:
            raise DataQualityError(
                f"{source}: chave territorial duplicada: {key!r}"
            )
        indexed[key] = row
    return indexed


def validate_ibge(indexed):
    codes = set()
    for key, row in indexed.items():
        value = row.get("CD_DIST")
        code = str(value).strip() if value is not None else ""
        if not re.fullmatch(r"3550308\d{2}", code):
            raise DataQualityError(
                f"IBGE: CD_DIST invalido para {key}: {code!r}"
            )
        if code in codes:
            raise DataQualityError(f"IBGE: CD_DIST duplicado: {code}")
        codes.add(code)
        if str(row.get("CD_MUN", "")).strip() != "3550308":
            raise DataQualityError(
                f"IBGE: municipio diferente de Sao Paulo para {code}"
            )


def build_rows(geo_rows, ibge_rows, geo_version, ibge_version):
    """Valida e retorna o dataset Silver pronto, mas nao escreve nada."""
    geosampa = index_names(geo_rows, "nm_distrit", "GeoSampa")
    ibge = index_names(ibge_rows, "NM_DIST", "IBGE")
    validate_ibge(ibge)

    missing_ibge = sorted(set(geosampa) - set(ibge))
    missing_geosampa = sorted(set(ibge) - set(geosampa))
    if missing_ibge or missing_geosampa:
        raise DataQualityError(
            "Nomes nao reconciliados apos NFKD. "
            f"Somente GeoSampa: {missing_ibge}; "
            f"somente IBGE: {missing_geosampa}"
        )

    result = []
    nulls_per_column = Counter()
    for key in sorted(geosampa):
        source = geosampa[key]
        reference = ibge[key]
        rescued = source.get("_rescued_data")
        if rescued is not None and str(rescued).strip():
            raise DataQualityError(
                f"GeoSampa {key}: _rescued_data preenchido"
            )

        values = {}
        missing = 0
        for column in FEATURE_COLUMNS:
            if column not in source:
                raise DataQualityError(f"GeoSampa: coluna ausente: {column}")
            value = source[column]
            if value is None:
                missing += 1
                nulls_per_column[column] += 1
            elif isinstance(value, bool) or not isinstance(value, int):
                raise DataQualityError(
                    f"GeoSampa {key}: {column} nao e inteiro: {value!r}"
                )
            elif value < 0:
                raise DataQualityError(
                    f"GeoSampa {key}: {column} negativo: {value}"
                )
            values[column] = value

        result.append({
            "CD_DIST": int(reference["CD_DIST"]),
            "NM_DIST": reference["NM_DIST"].strip(),
            "nm_distrit_geosampa": source["nm_distrit"].strip(),
            **values,
            "qtd_indicadores_nulos": missing,
            "cobertura_indicadores_pct": round(
                100.0 * (len(FEATURE_COLUMNS) - missing)
                / len(FEATURE_COLUMNS),
                4,
            ),
            "fonte": "GeoSampa",
            "versao_bronze_geosampa": int(geo_version),
            "versao_silver_ibge": int(ibge_version),
        })

    if len({r["CD_DIST"] for r in result}) != EXPECTED_DISTRICTS:
        raise DataQualityError("Resultado: codigos IBGE nao unicos")
    if any(set(r) != set(OUTPUT_COLUMNS) for r in result):
        raise DataQualityError("Resultado: colunas inesperadas")

    metrics = {
        "total_distritos": len(result),
        "correspondencias_validas": len(result),
        "indicadores_por_distrito": len(FEATURE_COLUMNS),
        "distritos_com_indicadores_nulos": sum(
            r["qtd_indicadores_nulos"] > 0 for r in result
        ),
        "nulos_por_indicador": dict(sorted(nulls_per_column.items())),
        "total_qtd_metro": sum(r["qtd_metro"] or 0 for r in result),
        "total_qtd_trem": sum(r["qtd_trem"] or 0 for r in result),
        "total_qtd_onibus": sum(r["qtd_onibus"] or 0 for r in result),
        "total_qtd_terminal_onibus": sum(
            r["qtd_terminal_onibus"] or 0 for r in result
        ),
        "total_qtd_bicicletario": sum(
            r["qtd_bicicletario"] or 0 for r in result
        ),
    }
    return result, metrics


def delta_version(spark, source):
    row = spark.sql(f"DESCRIBE HISTORY {source} LIMIT 1").first()
    if row is None or row["version"] is None:
        raise RuntimeError(f"Historico Delta indisponivel: {source}")
    return int(row["version"])


def load_snapshot(spark, source, version, columns):
    projection = ", ".join(
        f"`{column}`" for column in columns
    )
    query = (
        f"SELECT {projection} FROM {source} "
        f"VERSION AS OF {int(version)}"
    )
    return [row_dict(r) for r in spark.sql(query).collect()]


def result_counter(rows):
    return Counter(
        tuple(r[column] for column in OUTPUT_COLUMNS)
        for r in (row_dict(row) for row in rows)
    )


def compare_target(spark, proposed):
    if not spark.catalog.tableExists(TARGET):
        return False
    existing = spark.table(TARGET)
    if existing.columns != OUTPUT_COLUMNS:
        raise DataQualityError(
            "Silver existente possui schema diferente; "
            "alteracao bloqueada"
        )
    if existing.count() != len(proposed):
        return False
    return result_counter(existing.collect()) == result_counter(proposed)


def make_dataframe(spark, rows):
    from pyspark.sql.types import (
        StructType, StructField, IntegerType,
        StringType, DoubleType, LongType,
    )
    schema = StructType([
        StructField("CD_DIST", IntegerType(), False),
        StructField("NM_DIST", StringType(), False),
        StructField("nm_distrit_geosampa", StringType(), False),
        *[
            StructField(name, IntegerType(), True)
            for name in FEATURE_COLUMNS
        ],
        StructField("qtd_indicadores_nulos", IntegerType(), False),
        StructField("cobertura_indicadores_pct", DoubleType(), False),
        StructField("fonte", StringType(), False),
        StructField("versao_bronze_geosampa", LongType(), False),
        StructField("versao_silver_ibge", LongType(), False),
    ])
    return spark.createDataFrame(rows, schema=schema)


def execute(spark, apply=False):
    """Fonte versionada + reconciliacao integral antes de qualquer escrita."""
    geo_version = delta_version(spark, SOURCE_GEOSAMPA)
    ibge_version = delta_version(spark, SOURCE_IBGE)
    geo_rows = load_snapshot(
        spark, SOURCE_GEOSAMPA, geo_version, GEO_COLUMNS
    )
    ibge_rows = load_snapshot(
        spark, SOURCE_IBGE, ibge_version, IBGE_COLUMNS
    )

    result, metrics = build_rows(
        geo_rows, ibge_rows, geo_version, ibge_version
    )
    identical = compare_target(spark, result)
    emit(
        "GEOSAMPA_SILVER_VALIDATED",
        **metrics,
        source_geosampa_version=geo_version,
        source_ibge_version=ibge_version,
        identical_to_target=identical,
    )

    if not apply:
        emit("GEOSAMPA_SILVER_CHECK_SUCCESS", changed_tables=False)
        return result

    if identical:
        emit("GEOSAMPA_SILVER_UNCHANGED", changed_tables=False)
        return result

    # Evita publicar uma fotografia obsoleta das fontes.
    if (
        delta_version(spark, SOURCE_GEOSAMPA) != geo_version
        or delta_version(spark, SOURCE_IBGE) != ibge_version
    ):
        raise RuntimeError("Fontes Delta mudaram durante a validacao")

    # Unica escrita autorizada, apenas com --apply --confirm-publish.
    (
        make_dataframe(spark, result)
        .write.format("delta")
        .mode("overwrite")
        .saveAsTable(TARGET)
    )
    if not compare_target(spark, result):
        raise RuntimeError("Silver publicada nao corresponde ao resultado")
    emit(
        "GEOSAMPA_SILVER_APPLY_SUCCESS",
        target=TARGET,
        total_distritos=len(result),
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-publish", action="store_true")
    args = parser.parse_args(argv)

    if args.apply != args.confirm_publish:
        parser.error(
            "Publicacao exige --apply --confirm-publish; "
            "--check nao aceita --confirm-publish"
        )

    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    execute(spark, apply=args.apply)


if __name__ == "__main__":
    main()
