"""BairroIQ | Gold distritos_wide v1.

Uma linha por distrito oficial de Sao Paulo. Preserva os indicadores disponiveis
na Silver com o valor mais recente valido de cada indicador ObservaSampa.
SSP: janela dos 12 meses completos mais recentes presentes na fonte.
Nao cruza bairros imobiliarios com distritos sem mapeamento territorial validado.

O resultado e uma WIDE TABLE para consulta/exploracao. A selecao final de
features, imputacao e escalonamento para ML pertencem ao pipeline de ML.

Execucao em Databricks Serverless:
    python gold_distritos_wide_runner.py --check
    python gold_distritos_wide_runner.py --apply --confirm-publish

--check nao altera tabelas nem arquivos.
--apply apenas CRIA a tabela se ela nao existir. Nunca substitui dados
existentes divergentes. Nao ha agendamento automatico.
"""

import argparse
import calendar
from datetime import date, timedelta
import hashlib
import json
import re
import unicodedata
from uuid import uuid4

IBGE = "workspace.silver.ibge_agregados_basicos_v2"
GEO = "workspace.silver.geosampa_equipamentos_distrito"
OBS = "workspace.silver.observasampa_indicadores_distrito"
SSP = "workspace.silver.ssp_ocorrencias_distrito"
TARGET = "workspace.gold.distritos_wide"
EXPECTED_DISTRICTS = 96

IBGE_MEASURES = (
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
)

# Apenas rubricas que possuem volume expressivo no diagnostico historico.
# Sao usadas para gerar taxas auxiliares; todas as demais rubricas
# continuam presentes como contagens, sem entrar automaticamente no ML.
SSP_RATE_RUBRICAS = (
    "Furto (art. 155)",
    "Roubo (art. 157)",
    "Lesão corporal (art. 129)",
    "tráfico drogas (Art.33, caput)",
)


class ContractError(ValueError):
    """Dados ou schema fora do contrato esperado."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def emit(event, **data):
    print(json.dumps({"event": event, **data}, ensure_ascii=False,
                     default=str, sort_keys=True), flush=True)


def slug(value, prefix):
    """Nome de coluna deterministico, sem colisoes por truncamento."""
    require(isinstance(value, str) and value.strip(),
            f"Nome de feature invalido: {value!r}")
    text = "".join(c for c in unicodedata.normalize("NFKD", value)
                   if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    require(bool(text), f"Nome de feature sem letras/numeros: {value!r}")
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{text[:43].rstrip('_')}_{suffix}"


def month_window(latest):
    """12 meses completos, sem extrapolar alem da data da Silver SSP."""
    require(isinstance(latest, date), "SSP sem data de ocorrencia valida")
    end_day = calendar.monthrange(latest.year, latest.month)[1]
    last = date(latest.year, latest.month, end_day)
    if latest < last:
        last = latest.replace(day=1) - timedelta(days=1)
    require(last.year >= 2000, "Periodo SSP inesperado")
    month_index = last.year * 12 + last.month - 1 - 11
    first = date(month_index // 12, month_index % 12 + 1, 1)
    return first, last


def delta_version(spark, table):
    row = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()
    require(row is not None and row["version"] is not None,
            f"Historico Delta nao encontrado: {table}")
    return int(row["version"])


def load_snapshot(spark, table, version):
    return spark.sql(f"SELECT * FROM {table} VERSION AS OF {int(version)}")


def require_columns(frame, columns, label):
    missing = set(columns) - set(frame.columns)
    require(not missing, f"{label}: colunas ausentes {sorted(missing)}")


def check_districts(frame, label):
    from pyspark.sql import functions as F
    stats = frame.agg(
        F.count("*").alias("n"),
        F.countDistinct("CD_DIST").alias("n_dist"),
        F.sum(F.when(F.col("CD_DIST").isNull(), 1).otherwise(0))
         .alias("nulls"),
    ).first()
    require(stats["n"] == EXPECTED_DISTRICTS
            and stats["n_dist"] == EXPECTED_DISTRICTS
            and stats["nulls"] == 0,
            f"{label}: esperadas 96 linhas com codigos unicos; "
            f"obtido={stats.asDict()}")


def assert_same_codes(frame, base, label):
    # Evita perda silenciosa de distritos durante joins.
    extra = frame.select("CD_DIST").distinct().join(
        base.select("CD_DIST"), "CD_DIST", "left_anti"
    ).limit(1).count()
    require(extra == 0, f"{label}: codigo territorial fora da referencia IBGE")


def build(spark, versions):
    from pyspark.sql import functions as F

    # 1. Referencia oficial: exatamente 96 distritos IBGE.
    ibge = load_snapshot(spark, IBGE, versions[IBGE])
    require_columns(ibge,
                    ["CD_DIST", "NM_DIST", "CD_MUN", *IBGE_MEASURES],
                    "IBGE")
    ibge = ibge.filter(F.col("CD_MUN").cast("string") == "3550308")
    base = ibge.select(
        F.col("CD_DIST").cast("long").alias("CD_DIST"),
        F.col("NM_DIST"),
        *[F.col(c).cast("double").alias(f"ibge_{c}")
          for c in IBGE_MEASURES],
    )
    check_districts(base, "IBGE")
    require(base.filter(F.col("NM_DIST").isNull()).limit(1).count() == 0,
            "IBGE: nome de distrito nulo")

    # 2. GeoSampa: 42 medidas numericas, ja no grao distrital.
    geo = load_snapshot(spark, GEO, versions[GEO])
    require_columns(geo, ["CD_DIST"], "GeoSampa")
    geo_features = sorted(
        c for c in geo.columns
        if c.startswith("qtd_") and c != "qtd_indicadores_nulos"
    )
    require(len(geo_features) == 42,
            f"GeoSampa: esperados 42 indicadores, obtidos {len(geo_features)}")
    geo = geo.select(
        F.col("CD_DIST").cast("long").alias("CD_DIST"),
        *[F.col(c).cast("double").alias(f"geo_{c}")
          for c in geo_features],
    )
    check_districts(geo, "GeoSampa")
    assert_same_codes(geo, base, "GeoSampa")

    # 3. ObservaSampa: ultimo ANO valido por indicador na cidade,
    # uniforme entre distritos. Onde nao existe observacao naquele
    # ano, a celula da wide fica NULL (sem backfill implicito).
    obs = load_snapshot(spark, OBS, versions[OBS])
    require_columns(obs,
                    ["CD_DIST", "indicador", "ano", "valor_numerico",
                     "status_valor"], "ObservaSampa")
    obs = obs.withColumn("CD_DIST", F.col("CD_DIST").cast("long"))
    assert_same_codes(obs.filter(F.col("CD_DIST").isNotNull()),
                      base, "ObservaSampa")
    require(obs.filter(F.col("indicador").isNull()
                       | F.col("ano").isNull()
                       | F.col("CD_DIST").isNull()).limit(1).count() == 0,
            "ObservaSampa: chave incompleta")
    duplicated = (obs.groupBy("CD_DIST", "indicador", "ano")
                  .count().filter(F.col("count") > 1).limit(1).count())
    require(duplicated == 0,
            "ObservaSampa: duplicidade distrito+indicador+ano")
    valid = obs.filter(
        (F.col("status_valor") == "OK")
        & F.col("valor_numerico").isNotNull()
    )
    years = valid.groupBy("indicador").agg(F.max("ano").alias("ano_ref"))
    recent = (valid.join(years, "indicador", "inner")
              .filter(F.col("ano") == F.col("ano_ref")))
    obs_stats = (recent.groupBy("indicador", "ano_ref")
                 .agg(F.countDistinct("CD_DIST").alias("coverage"))
                 .orderBy("indicador").collect())
    require(len(obs_stats) >= 1, "ObservaSampa sem indicadores validos")
    indicators = [r["indicador"] for r in obs_stats]
    obs_names = {name: slug(name, "obs") for name in indicators}
    require(len(set(obs_names.values())) == len(obs_names),
            "ObservaSampa: colunas geradas colidem")
    obs_pivot = (recent.withColumn(
        "valor_numerico", F.col("valor_numerico").cast("double"))
        .groupBy("CD_DIST").pivot("indicador", indicators)
        .agg(F.max("valor_numerico")))
    for name, field in obs_names.items():
        obs_pivot = obs_pivot.withColumnRenamed(name, field)

    # 4. SSP: contagem de REGISTROS por rubrica em 12 meses completos,
    # nao contagem de crimes confirmados nem soma de todo o historico.
    ssp = load_snapshot(spark, SSP, versions[SSP])
    require_columns(ssp,
                    ["CD_DIST", "rubrica", "data_ocorrencia"], "SSP")
    require(ssp.filter(F.col("rubrica").isNull()
                       | F.col("data_ocorrencia").isNull())
            .limit(1).count() == 0,
            "SSP: rubrica/data nula")
    latest = ssp.agg(F.max(F.to_date("data_ocorrencia")).alias("m")).first()["m"]
    first_day, last_day = month_window(latest)
    rubricas = sorted(r["rubrica"] for r in ssp.select("rubrica").distinct().collect())
    require(rubricas, "SSP: nenhuma rubrica identificada")
    ssp_names = {name: slug(name, "ssp_registros_12m") for name in rubricas}
    require(len(set(ssp_names.values())) == len(ssp_names),
            "SSP: nomes de rubricas geram colunas duplicadas")
    ssp_window = (ssp.withColumn("CD_DIST", F.col("CD_DIST").cast("long"))
                  .filter(F.to_date("data_ocorrencia").between(first_day, last_day)))
    unlocated = ssp_window.filter(F.col("CD_DIST").isNull()).count()
    located = ssp_window.filter(F.col("CD_DIST").isNotNull())
    assert_same_codes(located, base, "SSP")
    ssp_counts = (located.groupBy("CD_DIST", "rubrica").count())
    ssp_pivot = (ssp_counts.groupBy("CD_DIST")
                 .pivot("rubrica", rubricas).agg(F.max("count")))
    for rubric, field in ssp_names.items():
        ssp_pivot = ssp_pivot.withColumnRenamed(rubric, field)

    # 5. LEFT JOIN exclusivo por CD_DIST: jamais multiplica 96 linhas.
    result = (base.join(geo, "CD_DIST", "left")
              .join(obs_pivot, "CD_DIST", "left")
              .join(ssp_pivot, "CD_DIST", "left"))
    # Ausencia de registro SSP em uma rubrica na janela = zero registros;
    # para ObservaSampa, ausencia permanece NULL.
    result = result.fillna(0, subset=list(ssp_names.values()))

    # Taxas explicitamente ligadas a um denominador populacional.
    # Usa a ultima Populacao total do ObservaSampa (2024 no diagnostico),
    # sem combinar populações distritais de anos distintos.
    require("População total" in obs_names,
            "ObservaSampa: indicador Populacao total ausente")
    pop_col = F.col(obs_names["População total"])
    require(result.filter(pop_col.isNull() | (pop_col <= 0))
            .limit(1).count() == 0,
            "Populacao ObservaSampa ausente/zero em algum distrito")
    result = result.withColumn(
        "densidade_habitantes_km2",
        F.when(F.col("ibge_area_km2") > 0,
               F.col("ibge_total_pessoas") / F.col("ibge_area_km2"))
    )
    for geo_field in geo_features:
        col = f"geo_{geo_field}"
        result = result.withColumn(
            f"{col}_por_10mil_hab",
            F.col(col) * F.lit(10000.0) / pop_col,
        )
    for rubric in SSP_RATE_RUBRICAS:
        require(rubric in ssp_names,
                f"Rubrica SSP esperada ausente: {rubric}")
        col = ssp_names[rubric]
        result = result.withColumn(
            f"{col}_por_100mil_hab",
            F.col(col) * F.lit(100000.0) / pop_col,
        )

    check_districts(result, "Gold proposta")
    feature_cols = [c for c in result.columns if c not in ("CD_DIST", "NM_DIST")]
    require(len(feature_cols) == len(set(feature_cols)),
            "Gold: nomes de colunas repetidos")
    # A tabela fica numerica (exceto NM_DIST), pronta para um pipeline de
    # feature selection/normalizacao; nao treinar com TODOS os atributos.
    non_numeric = [f.name for f in result.schema
                   if f.name in feature_cols
                   and f.dataType.typeName() not in ("double", "float", "long", "integer",
                                                    "decimal", "short", "byte")]
    require(not non_numeric, f"Gold: features nao numericas {non_numeric}")

    coverage = result.agg(*[
        F.sum(F.when(F.col(c).isNotNull(), 1).otherwise(0)).alias(c)
        for c in feature_cols
    ]).first().asDict()
    complete = sum(n == 96 for n in coverage.values())
    sparse = sorted([(c, n) for c, n in coverage.items() if n < 86],
                    key=lambda x: (x[1], x[0]))
    summary = {
        "distritos": 96,
        "colunas_totais": len(result.columns),
        "atributos_numericos": len(feature_cols),
        "atributos_com_cobertura_total": complete,
        "atributos_com_menos_86_distritos": sparse,
        "observasampa_indicadores": len(indicators),
        "observasampa_referencia": {str(r["indicador"]): int(r["ano_ref"])
                                       for r in obs_stats},
        "ssp_rubricas": len(rubricas),
        "ssp_inicio_janela": str(first_day),
        "ssp_fim_janela": str(last_day),
        "ssp_sem_distrito_na_janela": unlocated,
        "silver_delta_versions": versions,
        "observasampa_colunas": obs_names,
        "ssp_colunas": ssp_names,
    }
    return result, summary


def equal_target(spark, proposed):
    if not spark.catalog.tableExists(TARGET):
        return False
    current = spark.table(TARGET)
    old_schema = [(f.name, f.dataType.simpleString()) for f in current.schema]
    new_schema = [(f.name, f.dataType.simpleString()) for f in proposed.schema]
    require(old_schema == new_schema,
            "Gold existente com schema divergente; publicacao bloqueada")
    if current.count() != proposed.count():
        return False
    return (current.exceptAll(proposed).limit(1).count() == 0
            and proposed.exceptAll(current).limit(1).count() == 0)


def execute(spark, apply=False):
    sources = (IBGE, GEO, OBS, SSP)
    for table in sources:
        require(spark.catalog.tableExists(table), f"Silver ausente: {table}")
    versions = {table: delta_version(spark, table) for table in sources}
    proposed, summary = build(spark, versions)
    identical = equal_target(spark, proposed)
    # Protecao contra mudanca de dados durante a leitura.
    require(all(delta_version(spark, tbl) == version
                for tbl, version in versions.items()),
            "Uma fonte Silver mudou durante a validacao")
    emit("GOLD_DISTRICTS_VALIDATED",
         summary={k: v for k, v in summary.items()
                  if k not in ("observasampa_referencia", "observasampa_colunas",
                               "ssp_colunas")},
         target_exists=spark.catalog.tableExists(TARGET),
         identical_to_target=identical)
    # Mapeamento dos indicadores/anos impresso apenas em logs de validacao,
    # para posterior materializacao de catalogo de metadados.
    emit("GOLD_FEATURE_MAPPING",
         observasampa_referencia=summary["observasampa_referencia"],
         observasampa_colunas=summary["observasampa_colunas"],
         ssp_colunas=summary["ssp_colunas"])
    if not apply:
        emit("GOLD_DISTRICTS_CHECK_SUCCESS",
             changed_tables=False, changed_files=False)
        return summary
    if identical:
        emit("GOLD_DISTRICTS_UNCHANGED", changed_tables=False)
        return summary
    require(not spark.catalog.tableExists(TARGET),
            "Gold existente com dados diferentes: substituicao bloqueada")
    require(all(delta_version(spark, tbl) == version
                for tbl, version in versions.items()),
            "Uma fonte Silver mudou antes da publicacao")
    view = "bairroiq_gold_publish_" + uuid4().hex
    proposed.createOrReplaceTempView(view)
    try:
        spark.sql(f"CREATE TABLE IF NOT EXISTS {TARGET} "
                  f"USING DELTA AS SELECT * FROM {view}").collect()
    finally:
        spark.catalog.dropTempView(view)
    require(equal_target(spark, proposed),
            "Gold publicada difere da transformacao validada")
    emit("GOLD_DISTRICTS_APPLY_SUCCESS", target=TARGET,
         distritos=96, atributos_numericos=summary["atributos_numericos"])
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-publish", action="store_true")
    args = parser.parse_args(argv)
    if args.apply != args.confirm_publish:
        parser.error("Publicacao exige --apply --confirm-publish; "
                     "--check e somente leitura")
    from pyspark.sql import SparkSession
    execute(SparkSession.builder.getOrCreate(), apply=args.apply)


if __name__ == "__main__":
    main()
