
"""BairroIQ | GeoSampa -> Silver por distrito de Sao Paulo.

Le a Bronze GeoSampa (42 indicadores), a Silver IBGE (somente codigos) e
os nomes oficiais do DBF da malha distrital do IBGE, sem GeoPandas.

    python silver_geosampa_runner.py --check
    python silver_geosampa_runner.py --apply --confirm-publish

--check e somente leitura. --apply exige confirmacao explicita; nao use antes
que o codigo esteja versionado, testado e o check real tenha passado.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata


SOURCE_GEOSAMPA = "workspace.bronze.geo_sampa"
SOURCE_IBGE = "workspace.silver.ibge_agregados_basicos_v2"
TARGET = "workspace.silver.geosampa_equipamentos_distrito"
DBF_PATH = Path(
    "/Volumes/workspace/bronze/raw/ibge/"
    "malha_distritos_2022/shapefile/SP_distritos_CD2022.dbf"
)
EXPECTED_DISTRICTS = 96

# Manter os nomes do contrato Bronze, inclusive o typo 'infatil'.
# Na tabela carregada, 'qtd_pupatempo' sera lido como 'qtd_poupatempo'.
FEATURE_COLUMNS = [
    "qtd_bibliotecas", "qtd_espacos", "qtd_museus",
    "qtd_teatros_cinemas", "qtd_ensino_tecnico_publico",
    "qtd_ensino_infatil_publico", "qtd_escolas_privadas",
    "qtd_escolas_publicas", "qtd_sistema_s", "qtd_ceu",
    "qtd_centro_esportivo", "qtd_clubes", "qtd_clubes_comunidade",
    "qtd_estadios", "qtd_corredor_verde", "qtd_praca_largo",
    "qtd_ambulatorios", "qtd_hospitais", "qtd_saude_mental",
    "qtd_ubs", "qtd_urgencia_emergencia", "qtd_bicicletario",
    "qtd_metro", "qtd_trem", "qtd_onibus", "qtd_terminal_onibus",
    "qtd_bombeiros", "qtd_guarda_civil", "qtd_policia_civil",
    "qtd_policia_militar", "qtd_defesa_civil", "qtd_agencia_funeraria",
    "qtd_velorio", "qtd_cemiterio", "qtd_consulados",
    "qtd_correios", "qtd_feira_livre", "qtd_mercado_municipal",
    "qtd_eletropaulo", "qtd_sabesp", "qtd_poupatempo", "qtd_sacoloes",
]
IBGE_COLUMNS = ["CD_DIST", "NM_DIST", "CD_MUN"]
OUTPUT_COLUMNS = [
    "CD_DIST", "NM_DIST", "nm_distrit_geosampa",
    *FEATURE_COLUMNS, "qtd_indicadores_nulos",
    "cobertura_indicadores_pct", "fonte",
    "versao_bronze_geosampa", "versao_silver_ibge",
]


class DataQualityError(ValueError):
    """Entrada invalida ou referencia territorial inconsistente."""


def emit(event, **data):
    print(json.dumps({ "event": event, **data }, ensure_ascii=False,
                     sort_keys=True, default=str), flush=True)


def normalize_name(value):
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip().upper() or None


def compatible_ibge_name(silver_name, official_name):
    """U+FFFD pode representar somente uma letra desconhecida, nao um nome livre."""
    a, b = normalize_name(silver_name), normalize_name(official_name)
    return bool(a and b and len(a) == len(b) and all(
        x == y or x == "\ufffd" for x, y in zip(a, b)
    ))


def row_dict(row):
    return row.asDict(recursive=True) if hasattr(row, "asDict") else dict(row)


def validate_ibge(rows):
    if len(rows) != EXPECTED_DISTRICTS:
        raise DataQualityError(f"Silver IBGE: esperadas 96 linhas; {len(rows)}")
    by_code = {}
    for raw in rows:
        row = row_dict(raw)
        code = str(row.get("CD_DIST") or "").strip()
        if not re.fullmatch(r"3550308\d{2}", code):
            raise DataQualityError(f"CD_DIST invalido: {code!r}")
        if str(row.get("CD_MUN") or "").strip() != "3550308":
            raise DataQualityError(f"Municipio IBGE invalido: {code}")
        if code in by_code:
            raise DataQualityError(f"CD_DIST duplicado: {code}")
        if not normalize_name(row.get("NM_DIST")):
            raise DataQualityError(f"NM_DIST vazio: {code}")
        by_code[code] = row
    return by_code


def read_official_dbf(path, municipal_codes):
    """Le somente CD_DIST/NM_DIST do DBF estadual e filtra os 96 codigos.

    Na fonte verificada os nomes estao codificados em UTF-8. Qualquer alteracao
    de codificacao bloqueia a validacao, em vez de aceitar texto corrompido.
    """
    content = Path(path).read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    if len(content) < 33:
        raise DataQualityError("DBF incompleto")
    record_count = int.from_bytes(content[4:8], "little")
    header_len = int.from_bytes(content[8:10], "little")
    record_len = int.from_bytes(content[10:12], "little")
    if (header_len < 33 or header_len > len(content) or record_len <= 1
            or len(content) < header_len + record_len * record_count):
        raise DataQualityError("Cabecalho/comprimento DBF invalido")

    fields = {}
    pos = 32
    offset = 1
    found_terminator = False
    while pos < header_len:
        if content[pos] == 0x0D:
            found_terminator = True
            break
        if pos + 32 > header_len:
            raise DataQualityError("Descritor DBF truncado")
        field = content[pos:pos + 32]
        name = field[:11].split(b"\x00", 1)[0].decode("ascii")
        length = field[16]
        if not name or length == 0 or name in fields:
            raise DataQualityError("Campos DBF invalidos/duplicados")
        fields[name] = (offset, length)
        offset += length
        pos += 32
    if not found_terminator or offset > record_len:
        raise DataQualityError("Estrutura DBF invalida")
    if not {"CD_DIST", "NM_DIST"}.issubset(fields):
        raise DataQualityError("DBF sem CD_DIST ou NM_DIST")

    result = {}
    for n in range(record_count):
        start = header_len + n * record_len
        record = content[start:start + record_len]
        if record[0:1] == b"*":
            continue  # registro excluido no DBF
        if record[0:1] != b" ":
            raise DataQualityError(f"Registro DBF invalido: {n}")
        off_code, len_code = fields["CD_DIST"]
        code = record[off_code:off_code + len_code].strip(b" \x00").decode("ascii")
        if code not in municipal_codes:
            continue
        off_name, len_name = fields["NM_DIST"]
        name = record[off_name:off_name + len_name].strip(b" \x00").decode("utf-8")
        if not normalize_name(name) or "\ufffd" in name:
            raise DataQualityError(f"Nome oficial invalido: {code}")
        if code in result:
            raise DataQualityError(f"Codigo duplicado no DBF: {code}")
        result[code] = name
    if set(result) != set(municipal_codes) or len(result) != EXPECTED_DISTRICTS:
        raise DataQualityError(
            "DBF nao cobre exatamente os 96 codigos da Silver IBGE"
        )
    return result, {"registros_dbf_estadual": record_count, "dbf_sha256": sha256}


def bronze_projection(spark):
    """Detecta a grafia real sem renomear nem alterar a tabela Bronze."""
    available = set(spark.table(SOURCE_GEOSAMPA).columns)
    required = {"nm_distrit", "_rescued_data", *FEATURE_COLUMNS} - {"qtd_poupatempo"}
    missing = required - available
    if missing:
        raise DataQualityError(f"Colunas Bronze ausentes: {sorted(missing)}")
    canonical = "qtd_poupatempo" in available
    legacy = "qtd_pupatempo" in available
    if canonical == legacy:
        raise DataQualityError(
            "Contrato Poupatempo ambiguo: deve existir apenas uma grafia"
        )
    cols = ["nm_distrit", *FEATURE_COLUMNS, "_rescued_data"]
    projection = [
        "`qtd_pupatempo` AS `qtd_poupatempo`"
        if col == "qtd_poupatempo" and legacy else f"`{col}`"
        for col in cols
    ]
    return ", ".join(projection), legacy


def delta_version(spark, name):
    row = spark.sql(f"DESCRIBE HISTORY {name} LIMIT 1").first()
    if row is None or row["version"] is None:
        raise RuntimeError(f"Delta history indisponivel: {name}")
    return int(row["version"])


def load_snapshot(spark, table, version, projection):
    return [row_dict(row) for row in spark.sql(
        f"SELECT {projection} FROM {table} VERSION AS OF {int(version)}"
    ).collect()]


def build_rows(geo_rows, ibge_rows, official_names, geo_version, ibge_version):
    """Cruzamento 1:1 com bloqueio de ambiguidades e dados negativos."""
    ibge = validate_ibge(ibge_rows)
    if set(official_names) != set(ibge):
        raise DataQualityError("Codigos DBF e Silver IBGE diferentes")

    official_by_key = {}
    corrupted = 0
    for code, official_name in official_names.items():
        if not compatible_ibge_name(ibge[code]["NM_DIST"], official_name):
            raise DataQualityError(
                f"Nome IBGE incompativel com DBF: {code}: "
                f"{ibge[code]['NM_DIST']!r} != {official_name!r}"
            )
        corrupted += "\ufffd" in ibge[code]["NM_DIST"]
        key = normalize_name(official_name)
        if key in official_by_key:
            raise DataQualityError(f"Nome duplicado no DBF: {key}")
        official_by_key[key] = (code, official_name)

    if len(geo_rows) != EXPECTED_DISTRICTS:
        raise DataQualityError(f"GeoSampa: esperados 96 registros; {len(geo_rows)}")
    geo_by_key = {}
    for raw in geo_rows:
        row = row_dict(raw)
        key = normalize_name(row.get("nm_distrit"))
        if not key or key in geo_by_key:
            raise DataQualityError(f"Nome GeoSampa ausente/duplicado: {key!r}")
        geo_by_key[key] = row

    if set(geo_by_key) != set(official_by_key):
        raise DataQualityError(
            "Nomes nao reconciliados. "
            f"Somente GeoSampa: {sorted(set(geo_by_key) - set(official_by_key))}; "
            f"Somente IBGE: {sorted(set(official_by_key) - set(geo_by_key))}"
        )

    result = []
    nulls_per_feature = Counter()
    for key in sorted(official_by_key):
        code, official_name = official_by_key[key]
        source = geo_by_key[key]
        if source.get("_rescued_data") is not None and str(source["_rescued_data"]).strip():
            raise DataQualityError(f"_rescued_data preenchido: {key}")
        metrics = {}
        for feature in FEATURE_COLUMNS:
            if feature not in source:
                raise DataQualityError(f"Coluna ausente no registro: {feature}")
            value = source[feature]
            if value is None:
                nulls_per_feature[feature] += 1
            elif isinstance(value, bool) or not isinstance(value, int):
                raise DataQualityError(f"Valor nao inteiro: {key}, {feature}={value!r}")
            elif value < 0:
                raise DataQualityError(f"Valor negativo: {key}, {feature}={value}")
            metrics[feature] = value
        null_count = sum(metrics[col] is None for col in FEATURE_COLUMNS)
        result.append({
            "CD_DIST": int(code), "NM_DIST": official_name,
            "nm_distrit_geosampa": source["nm_distrit"].strip(),
            **metrics,
            "qtd_indicadores_nulos": null_count,
            "cobertura_indicadores_pct": round(
                100 * (len(FEATURE_COLUMNS) - null_count) / len(FEATURE_COLUMNS), 4
            ),
            "fonte": "GeoSampa",
            "versao_bronze_geosampa": int(geo_version),
            "versao_silver_ibge": int(ibge_version),
        })
    if len(result) != EXPECTED_DISTRICTS or any(
        list(row) != OUTPUT_COLUMNS for row in result
    ):
        raise DataQualityError("Resultado Silver inesperado")
    report = {
        "total_distritos": len(result),
        "correspondencias_validas": len(result),
        "indicadores_por_distrito": len(FEATURE_COLUMNS),
        "nomes_ibge_corrompidos": corrupted,
        "distritos_com_indicadores_nulos": sum(
            row["qtd_indicadores_nulos"] > 0 for row in result
        ),
        "nulos_por_indicador": dict(sorted(nulls_per_feature.items())),
        "total_qtd_metro": sum(row["qtd_metro"] or 0 for row in result),
        "total_qtd_trem": sum(row["qtd_trem"] or 0 for row in result),
        "total_qtd_onibus": sum(row["qtd_onibus"] or 0 for row in result),
        "total_qtd_terminal_onibus": sum(
            row["qtd_terminal_onibus"] or 0 for row in result
        ),
        "total_qtd_bicicletario": sum(
            row["qtd_bicicletario"] or 0 for row in result
        ),
    }
    return result, report


def row_counter(rows):
    return Counter(tuple(row_dict(r)[c] for c in OUTPUT_COLUMNS) for r in rows)


def compare_target(spark, proposed):
    if not spark.catalog.tableExists(TARGET):
        return False
    actual = spark.table(TARGET)
    if actual.columns != OUTPUT_COLUMNS:
        raise DataQualityError("Schema da Silver existente diverge; publicacao bloqueada")
    if actual.count() != len(proposed):
        return False
    return row_counter(actual.collect()) == row_counter(proposed)


def make_dataframe(spark, rows):
    from pyspark.sql.types import (
        StructType, StructField, IntegerType, LongType, StringType, DoubleType
    )
    schema = StructType([
        StructField("CD_DIST", IntegerType(), False),
        StructField("NM_DIST", StringType(), False),
        StructField("nm_distrit_geosampa", StringType(), False),
        *[StructField(name, IntegerType(), True) for name in FEATURE_COLUMNS],
        StructField("qtd_indicadores_nulos", IntegerType(), False),
        StructField("cobertura_indicadores_pct", DoubleType(), False),
        StructField("fonte", StringType(), False),
        StructField("versao_bronze_geosampa", LongType(), False),
        StructField("versao_silver_ibge", LongType(), False),
    ])
    return spark.createDataFrame(rows, schema=schema)


def execute(spark, apply=False, dbf_path=None):
    if dbf_path is None:
        dbf_path = DBF_PATH
    geo_version = delta_version(spark, SOURCE_GEOSAMPA)
    ibge_version = delta_version(spark, SOURCE_IBGE)
    geo_projection, alias_used = bronze_projection(spark)
    geo_rows = load_snapshot(spark, SOURCE_GEOSAMPA, geo_version, geo_projection)
    ibge_rows = load_snapshot(
        spark, SOURCE_IBGE, ibge_version, ", ".join(f"`{c}`" for c in IBGE_COLUMNS)
    )
    ibge_codes = set(validate_ibge(ibge_rows))
    official_names, dbf_info = read_official_dbf(dbf_path, ibge_codes)
    proposed, report = build_rows(
        geo_rows, ibge_rows, official_names, geo_version, ibge_version
    )
    identical = compare_target(spark, proposed)
    emit(
        "GEOSAMPA_SILVER_VALIDATED", **report, **dbf_info,
        source_geosampa_version=geo_version,
        source_ibge_version=ibge_version,
        legacy_poupatempo_alias=alias_used,
        identical_to_target=identical,
    )
    if not apply:
        emit("GEOSAMPA_SILVER_CHECK_SUCCESS", changed_tables=False, changed_files=False)
        return proposed
    if identical:
        emit("GEOSAMPA_SILVER_UNCHANGED", changed_tables=False)
        return proposed
    if (delta_version(spark, SOURCE_GEOSAMPA) != geo_version
            or delta_version(spark, SOURCE_IBGE) != ibge_version):
        raise RuntimeError("Fonte Delta mudou durante a validacao; publicacao bloqueada")
    if hashlib.sha256(Path(dbf_path).read_bytes()).hexdigest() != dbf_info["dbf_sha256"]:
        raise RuntimeError("DBF oficial mudou durante a validacao; publicacao bloqueada")
    make_dataframe(spark, proposed).write.format("delta").mode("overwrite").saveAsTable(TARGET)
    if not compare_target(spark, proposed):
        raise RuntimeError("Tabela publicada diverge do resultado validado")
    emit("GEOSAMPA_SILVER_APPLY_SUCCESS", target=TARGET, total_distritos=len(proposed))
    return proposed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-publish", action="store_true")
    args = parser.parse_args(argv)
    if args.apply != args.confirm_publish:
        parser.error("Publicacao exige --apply --confirm-publish, nunca --check")
    from pyspark.sql import SparkSession
    execute(SparkSession.builder.getOrCreate(), apply=args.apply)


if __name__ == "__main__":
    main()
