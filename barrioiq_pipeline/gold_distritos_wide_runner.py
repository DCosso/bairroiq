
"""
BairroIQ | Gold Distritos Wide v3

Fontes:
    IBGE, GeoSampa, ObservaSampa, SSP e Imoveis.

Destino:
    workspace.gold.distritos_wide

Granularidade:
    Exatamente uma linha por distrito oficial de Sao Paulo.

Politica:
    - Estado mais recente disponivel.
    - Nenhuma coluna de data na Gold.
    - Ausencias imobiliarias permanecem NULL.
    - Somente associacoes territoriais aprovadas.
    - Nenhuma media de medianas imobiliarias.
    - Nenhum historico analitico na Gold.

Execucao:
    --check
        Validacao somente leitura.

    --apply --confirm-publish
        Criacao inicial, se o destino nao existir.

    --update --confirm-publish
        Atualizacao controlada do destino existente.

O modo --update:
    - Requer Delta Lake.
    - Exige exatamente 96 distritos.
    - Exige schema identico.
    - Exige codigos territoriais identicos.
    - Confere versoes das fontes.
    - Executa MERGE por CD_DIST.
    - Compara integralmente o resultado publicado.

Nenhuma operacao de publicacao e automatica.
"""

import argparse
import calendar
from datetime import date, timedelta
import hashlib
import json
import re
import unicodedata
from uuid import uuid4


# ============================================================
# 1. CONFIGURACAO
# ============================================================

IBGE = "workspace.silver.ibge_agregados_basicos_v2"
GEO = "workspace.silver.geosampa_equipamentos_distrito"
OBS = "workspace.silver.observasampa_indicadores_distrito"
SSP = "workspace.silver.ssp_ocorrencias_distrito"
IMOVEIS = "workspace.silver.imoveis_bairro_mensal"
DEPARA = "workspace.silver.imoveis_bairro_distrito_candidatos"

TARGET = "workspace.gold.distritos_wide"

EXPECTED_DISTRICTS = 96
METODO_IMOVEIS = "PROXY_OSM_HOMOLOGADO"

IMOVEIS_FEATURES = (
    "imv_venda_estoque",
    "imv_aluguel_estoque",
    "imv_venda_novos",
    "imv_aluguel_novos",
    "imv_bairros_mapeados",
    "imv_metodo_localizacao",
)

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

SSP_RATE_RUBRICAS = (
    "Furto (art. 155)",
    "Roubo (art. 157)",
    "Lesão corporal (art. 129)",
    "tráfico drogas (Art.33, caput)",
)


# ============================================================
# 2. FUNCOES DE CONTROLE
# ============================================================

class ContractError(ValueError):
    """Violacao de contrato de dados."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def emit(event, **data):
    print(
        json.dumps(
            {"event": event, **data},
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        ),
        flush=True,
    )


def slug(value, prefix):
    require(
        isinstance(value, str) and bool(value.strip()),
        f"Nome de feature invalido: {value!r}",
    )

    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text.lower(),
    ).strip("_")

    require(
        bool(text),
        f"Nome de feature invalido: {value!r}",
    )

    suffix = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:8]

    return (
        f"{prefix}_"
        f"{text[:43].rstrip('_')}_"
        f"{suffix}"
    )


def month_window(latest):
    require(
        isinstance(latest, date),
        "SSP sem data valida",
    )

    last_day = calendar.monthrange(
        latest.year,
        latest.month,
    )[1]

    last = date(
        latest.year,
        latest.month,
        last_day,
    )

    if latest < last:
        last = latest.replace(
            day=1
        ) - timedelta(days=1)

    require(
        last.year >= 2000,
        "Periodo SSP inesperado",
    )

    month_index = (
        last.year * 12
        + last.month
        - 1
        - 11
    )

    first = date(
        month_index // 12,
        month_index % 12 + 1,
        1,
    )

    return first, last


def delta_version(spark, table):
    row = spark.sql(
        f"DESCRIBE HISTORY {table} LIMIT 1"
    ).first()

    require(
        row is not None and row["version"] is not None,
        f"Historico Delta indisponivel: {table}",
    )

    return int(row["version"])


def load_snapshot(spark, table, version):
    return spark.sql(
        f"SELECT * FROM {table} "
        f"VERSION AS OF {int(version)}"
    )


def require_columns(frame, columns, label):
    missing = set(columns) - set(frame.columns)

    require(
        not missing,
        f"{label}: colunas ausentes {sorted(missing)}",
    )


def check_districts(frame, label):
    from pyspark.sql import functions as F

    stats = frame.agg(
        F.count("*").alias("linhas"),
        F.countDistinct("CD_DIST").alias("distritos"),
        F.sum(
            F.when(
                F.col("CD_DIST").isNull(), 1
            ).otherwise(0)
        ).alias("nulos"),
    ).first()

    require(
        stats["linhas"] == EXPECTED_DISTRICTS
        and stats["distritos"] == EXPECTED_DISTRICTS
        and stats["nulos"] == 0,
        f"{label}: distritos invalidos: {stats.asDict()}",
    )


def assert_same_codes(frame, reference, label):
    extra = (
        frame.select("CD_DIST").distinct()
        .join(
            reference.select("CD_DIST"),
            "CD_DIST",
            "left_anti",
        )
        .limit(1)
        .count()
    )

    require(
        extra == 0,
        f"{label}: codigo territorial desconhecido",
    )


def total(frame, field):
    from pyspark.sql import functions as F

    value = frame.agg(
        F.sum(field).alias("total")
    ).first()["total"]

    return value if value is not None else 0


def source_versions_unchanged(spark, versions):
    return all(
        delta_version(spark, table) == version
        for table, version in versions.items()
    )


def same_schema(left, right):
    def signature(frame):
        return [
            (
                field.name,
                field.dataType.simpleString(),
            )
            for field in frame.schema
        ]

    return signature(left) == signature(right)


def assert_exact_codes(proposed, current):
    check_districts(proposed, "Gold proposta")
    check_districts(current, "Gold existente")

    assert_same_codes(
        proposed,
        current,
        "Proposta versus existente",
    )

    assert_same_codes(
        current,
        proposed,
        "Existente versus proposta",
    )


# ============================================================
# 3. INTEGRACAO IMOBILIARIA
# ============================================================

def build_imoveis(spark, versions, base):
    from pyspark.sql import functions as F

    imoveis = load_snapshot(
        spark, IMOVEIS, versions[IMOVEIS]
    )

    require_columns(
        imoveis,
        [
            "mes",
            "bairro_normalizado",
            "transacao",
            "anuncios_ativos_media_dia",
            "novos_anuncios",
        ],
        "Imoveis",
    )

    mes_recente = imoveis.agg(
        F.max("mes").alias("mes")
    ).first()["mes"]

    require(
        mes_recente is not None,
        "Imoveis: nenhum mes disponivel",
    )

    fonte = (
        imoveis
        .filter(
            F.col("mes") == F.lit(mes_recente)
        )
        .withColumn(
            "_bairro",
            F.upper(
                F.trim(
                    F.col("bairro_normalizado")
                    .cast("string")
                )
            ),
        )
        .withColumn(
            "_tipo",
            F.lower(
                F.trim(
                    F.col("transacao").cast("string")
                )
            ),
        )
    )

    require(
        fonte.count() > 0,
        "Imoveis: mes mais recente vazio",
    )

    invalidos = fonte.filter(
        F.col("_bairro").isNull()
        | (F.col("_bairro") == "")
        | ~F.col("_tipo").isin("venda", "aluguel")
        | F.col("anuncios_ativos_media_dia").isNull()
        | (F.col("anuncios_ativos_media_dia") < 0)
        | F.col("novos_anuncios").isNull()
        | (F.col("novos_anuncios") < 0)
    ).count()

    require(
        invalidos == 0,
        f"Imoveis: {invalidos} registros invalidos",
    )

    tipos = {
        row["_tipo"]
        for row in fonte.select("_tipo").distinct().collect()
    }

    require(
        tipos == {"venda", "aluguel"},
        f"Imoveis: modalidades inesperadas {tipos}",
    )

    duplicados = (
        fonte
        .groupBy("mes", "_bairro", "_tipo")
        .count()
        .filter(F.col("count") > 1)
        .limit(1)
        .count()
    )

    require(
        duplicados == 0,
        "Imoveis: duplicidade na chave mensal",
    )

    # De/para aprovado, usando a aprovacao mais recente.

    depara = load_snapshot(
        spark, DEPARA, versions[DEPARA]
    )

    require_columns(
        depara,
        [
            "bairro_normalizado",
            "mes_referencia",
            "CD_DIST_aprovado",
            "justificativa_aprovacao",
        ],
        "De/para",
    )

    aprovados = (
        depara
        .filter(
            F.col("CD_DIST_aprovado").isNotNull()
        )
        .select(
            F.upper(
                F.trim(
                    F.col("bairro_normalizado")
                    .cast("string")
                )
            ).alias("_bairro"),

            F.to_date(
                "mes_referencia"
            ).alias("_mes_aprovacao"),

            F.col("CD_DIST_aprovado")
            .cast("long")
            .alias("CD_DIST"),

            F.col("justificativa_aprovacao")
            .alias("_justificativa"),
        )
    )

    require(
        aprovados.count() > 0,
        "De/para: nenhuma aprovacao encontrada",
    )

    invalidos_aprovacao = aprovados.filter(
        F.col("_bairro").isNull()
        | (F.col("_bairro") == "")
        | F.col("_mes_aprovacao").isNull()
        | F.col("CD_DIST").isNull()
        | F.col("_justificativa").isNull()
        | (F.trim("_justificativa") == "")
    ).count()

    require(
        invalidos_aprovacao == 0,
        "De/para: aprovacoes incompletas",
    )

    ultimas = (
        aprovados
        .groupBy("_bairro")
        .agg(
            F.max("_mes_aprovacao")
            .alias("_mes_aprovacao")
        )
    )

    mapa = aprovados.join(
        ultimas,
        ["_bairro", "_mes_aprovacao"],
        "inner",
    )

    require(
        mapa.groupBy("_bairro")
        .count()
        .filter(F.col("count") > 1)
        .limit(1)
        .count() == 0,
        "De/para: aprovacao recente duplicada",
    )

    assert_same_codes(
        mapa, base, "De/para"
    )

    integrada = fonte.join(
        mapa.select("_bairro", "CD_DIST"),
        "_bairro",
        "left",
    )

    require(
        integrada.count() == fonte.count(),
        "Imoveis: JOIN alterou quantidade de linhas",
    )

    mapeados = integrada.filter(
        F.col("CD_DIST").isNotNull()
    )

    require(
        mapeados.count() > 0,
        "Imoveis: nenhuma associacao homologada",
    )

    agregado = (
        mapeados
        .groupBy("CD_DIST")
        .agg(
            F.sum(
                F.when(
                    F.col("_tipo") == "venda",
                    F.col("anuncios_ativos_media_dia"),
                )
            ).cast("long").alias(
                "imv_venda_estoque"
            ),

            F.sum(
                F.when(
                    F.col("_tipo") == "aluguel",
                    F.col("anuncios_ativos_media_dia"),
                )
            ).cast("long").alias(
                "imv_aluguel_estoque"
            ),

            F.sum(
                F.when(
                    F.col("_tipo") == "venda",
                    F.col("novos_anuncios"),
                )
            ).cast("long").alias(
                "imv_venda_novos"
            ),

            F.sum(
                F.when(
                    F.col("_tipo") == "aluguel",
                    F.col("novos_anuncios"),
                )
            ).cast("long").alias(
                "imv_aluguel_novos"
            ),

            F.countDistinct("_bairro")
            .cast("long").alias(
                "imv_bairros_mapeados"
            ),
        )
        .withColumn(
            "imv_metodo_localizacao",
            F.lit(METODO_IMOVEIS),
        )
    )

    estoque_mapeado = total(
        mapeados,
        "anuncios_ativos_media_dia",
    )

    require(
        total(agregado, "imv_venda_estoque")
        + total(agregado, "imv_aluguel_estoque")
        == estoque_mapeado,
        "Imoveis: estoque nao reconciliado",
    )

    novos_mapeados = total(
        mapeados,
        "novos_anuncios",
    )

    require(
        total(agregado, "imv_venda_novos")
        + total(agregado, "imv_aluguel_novos")
        == novos_mapeados,
        "Imoveis: novos anuncios nao reconciliados",
    )

    estoque_total = total(
        fonte,
        "anuncios_ativos_media_dia",
    )

    cobertura = (
        100.0 * estoque_mapeado / estoque_total
        if estoque_total > 0
        else 0.0
    )

    summary = {
        "mes_fonte": str(mes_recente),
        "bairros_aprovados": mapa.count(),
        "bairros_mapeados": (
            mapeados
            .select("_bairro")
            .distinct()
            .count()
        ),
        "distritos_com_imoveis": agregado.count(),
        "estoque_total": estoque_total,
        "estoque_mapeado": estoque_mapeado,
        "cobertura_percentual": round(cobertura, 2),
        "novos_anuncios_mapeados": novos_mapeados,
        "metodo_localizacao": METODO_IMOVEIS,
    }

    return agregado, summary


# ============================================================
# 4. CONSTRUIR SNAPSHOT GOLD
# ============================================================

def build(spark, versions):
    from pyspark.sql import functions as F

    # --------------------------------------------------------
    # 4.1. IBGE
    # --------------------------------------------------------

    ibge = load_snapshot(
        spark, IBGE, versions[IBGE]
    )

    require_columns(
        ibge,
        [
            "CD_DIST", "NM_DIST", "CD_MUN",
            *IBGE_MEASURES,
        ],
        "IBGE",
    )

    ibge = ibge.filter(
        F.col("CD_MUN").cast("string") == "3550308"
    )

    base = ibge.select(
        F.col("CD_DIST")
        .cast("long").alias("CD_DIST"),
        F.col("NM_DIST"),
        *[
            F.col(c).cast("double").alias(f"ibge_{c}")
            for c in IBGE_MEASURES
        ],
    )

    check_districts(base, "IBGE")

    require(
        base.filter(
            F.col("NM_DIST").isNull()
        ).limit(1).count() == 0,
        "IBGE: nome de distrito nulo",
    )

    # --------------------------------------------------------
    # 4.2. GEOSAMPA
    # --------------------------------------------------------

    geo = load_snapshot(
        spark, GEO, versions[GEO]
    )

    require_columns(
        geo, ["CD_DIST"], "GeoSampa"
    )

    geo_features = sorted(
        c for c in geo.columns
        if c.startswith("qtd_")
        and c != "qtd_indicadores_nulos"
    )

    require(
        len(geo_features) == 42,
        "GeoSampa: quantidade inesperada de indicadores",
    )

    geo = geo.select(
        F.col("CD_DIST")
        .cast("long").alias("CD_DIST"),
        *[
            F.col(c).cast("double").alias(f"geo_{c}")
            for c in geo_features
        ],
    )

    check_districts(geo, "GeoSampa")
    assert_same_codes(geo, base, "GeoSampa")

    # --------------------------------------------------------
    # 4.3. OBSERVASAMPA
    # --------------------------------------------------------

    obs = load_snapshot(
        spark, OBS, versions[OBS]
    )

    require_columns(
        obs,
        [
            "CD_DIST", "indicador", "ano",
            "valor_numerico", "status_valor",
        ],
        "ObservaSampa",
    )

    obs = obs.withColumn(
        "CD_DIST",
        F.col("CD_DIST").cast("long"),
    )

    require(
        obs.filter(
            F.col("CD_DIST").isNull()
            | F.col("indicador").isNull()
            | F.col("ano").isNull()
        ).limit(1).count() == 0,
        "ObservaSampa: chave incompleta",
    )

    assert_same_codes(
        obs, base, "ObservaSampa"
    )

    require(
        obs.groupBy(
            "CD_DIST", "indicador", "ano"
        ).count()
        .filter(F.col("count") > 1)
        .limit(1).count() == 0,
        "ObservaSampa: chave duplicada",
    )

    valid = obs.filter(
        (F.col("status_valor") == "OK")
        & F.col("valor_numerico").isNotNull()
    )

    years = valid.groupBy("indicador").agg(
        F.max("ano").alias("ano_ref")
    )

    recent = (
        valid.join(years, "indicador", "inner")
        .filter(F.col("ano") == F.col("ano_ref"))
    )

    obs_stats = (
        recent
        .groupBy("indicador", "ano_ref")
        .agg(
            F.countDistinct("CD_DIST")
            .alias("coverage")
        )
        .orderBy("indicador")
        .collect()
    )

    require(
        len(obs_stats) >= 1,
        "ObservaSampa sem indicadores validos",
    )

    indicators = [
        row["indicador"] for row in obs_stats
    ]

    obs_names = {
        name: slug(name, "obs")
        for name in indicators
    }

    require(
        len(set(obs_names.values())) == len(obs_names),
        "ObservaSampa: colunas duplicadas",
    )

    obs_pivot = (
        recent
        .withColumn(
            "valor_numerico",
            F.col("valor_numerico").cast("double"),
        )
        .groupBy("CD_DIST")
        .pivot("indicador", indicators)
        .agg(F.max("valor_numerico"))
    )

    for name, field in obs_names.items():
        obs_pivot = obs_pivot.withColumnRenamed(
            name, field
        )

    # --------------------------------------------------------
    # 4.4. SSP
    # --------------------------------------------------------

    ssp = load_snapshot(
        spark, SSP, versions[SSP]
    )

    require_columns(
        ssp,
        ["CD_DIST", "rubrica", "data_ocorrencia"],
        "SSP",
    )

    require(
        ssp.filter(
            F.col("rubrica").isNull()
            | F.col("data_ocorrencia").isNull()
        ).limit(1).count() == 0,
        "SSP: rubrica/data nula",
    )

    latest = ssp.agg(
        F.max(
            F.to_date("data_ocorrencia")
        ).alias("m")
    ).first()["m"]

    first_day, last_day = month_window(latest)

    rubricas = sorted(
        row["rubrica"]
        for row in ssp.select(
            "rubrica"
        ).distinct().collect()
    )

    require(
        bool(rubricas),
        "SSP: nenhuma rubrica encontrada",
    )

    ssp_names = {
        name: slug(name, "ssp_registros_12m")
        for name in rubricas
    }

    require(
        len(set(ssp_names.values())) == len(ssp_names),
        "SSP: colunas duplicadas",
    )

    ssp_window = (
        ssp
        .withColumn(
            "CD_DIST",
            F.col("CD_DIST").cast("long"),
        )
        .filter(
            F.to_date("data_ocorrencia").between(
                first_day, last_day
            )
        )
    )

    unlocated = ssp_window.filter(
        F.col("CD_DIST").isNull()
    ).count()

    located = ssp_window.filter(
        F.col("CD_DIST").isNotNull()
    )

    assert_same_codes(
        located, base, "SSP"
    )

    ssp_counts = (
        located
        .groupBy("CD_DIST", "rubrica")
        .count()
    )

    ssp_pivot = (
        ssp_counts
        .groupBy("CD_DIST")
        .pivot("rubrica", rubricas)
        .agg(F.max("count"))
    )

    for rubric, field in ssp_names.items():
        ssp_pivot = ssp_pivot.withColumnRenamed(
            rubric, field
        )

    # --------------------------------------------------------
    # 4.5. JUNCAO DAS FONTES TERRITORIAIS
    # --------------------------------------------------------

    result = (
        base
        .join(geo, "CD_DIST", "left")
        .join(obs_pivot, "CD_DIST", "left")
        .join(ssp_pivot, "CD_DIST", "left")
    )

    result = result.fillna(
        0,
        subset=list(ssp_names.values()),
    )

    # --------------------------------------------------------
    # 4.6. FEATURES NORMALIZADAS
    # --------------------------------------------------------

    require(
        "População total" in obs_names,
        "ObservaSampa: populacao ausente",
    )

    pop_col = F.col(
        obs_names["População total"]
    )

    require(
        result.filter(
            pop_col.isNull()
            | (pop_col <= 0)
        ).limit(1).count() == 0,
        "Populacao invalida para normalizacao",
    )

    result = result.withColumn(
        "densidade_habitantes_km2",
        F.when(
            F.col("ibge_area_km2") > 0,
            F.col("ibge_total_pessoas")
            / F.col("ibge_area_km2"),
        ),
    )

    for geo_field in geo_features:
        col = f"geo_{geo_field}"

        result = result.withColumn(
            f"{col}_por_10mil_hab",
            F.col(col)
            * F.lit(10000.0)
            / pop_col,
        )

    for rubric in SSP_RATE_RUBRICAS:
        require(
            rubric in ssp_names,
            f"SSP: rubrica ausente {rubric}",
        )

        col = ssp_names[rubric]

        result = result.withColumn(
            f"{col}_por_100mil_hab",
            F.col(col)
            * F.lit(100000.0)
            / pop_col,
        )

    # --------------------------------------------------------
    # 4.7. IMOVEIS HOMOLOGADOS
    # --------------------------------------------------------

    imoveis_gold, imoveis_summary = build_imoveis(
        spark, versions, base
    )

    result = result.join(
        imoveis_gold,
        "CD_DIST",
        "left",
    )

    check_districts(
        result,
        "Gold com imoveis",
    )

    # --------------------------------------------------------
    # 4.8. CONTRATO FINAL
    # --------------------------------------------------------

    feature_cols = [
        c for c in result.columns
        if c not in ("CD_DIST", "NM_DIST")
    ]

    require(
        len(result.columns) == len(set(result.columns)),
        "Gold: nomes de colunas duplicados",
    )

    non_numeric = [
        field.name
        for field in result.schema
        if (
            field.name in feature_cols
            and field.name != "imv_metodo_localizacao"
            and field.dataType.typeName() not in (
                "double", "float", "long",
                "integer", "decimal", "short", "byte"
            )
        )
    ]

    require(
        not non_numeric,
        f"Gold: features nao numericas {non_numeric}",
    )

    require(
        tuple(result.columns[-6:]) == IMOVEIS_FEATURES,
        "Gold: ordem das colunas imobiliarias invalida",
    )

    prohibited = {
        "imv_mes_referencia",
        "imv_atualizado_em",
        "mes",
        "mes_referencia",
    }

    require(
        not set(result.columns).intersection(prohibited),
        "Gold: coluna temporal proibida",
    )

    coverage = result.agg(
        *[
            F.sum(
                F.when(
                    F.col(c).isNotNull(), 1
                ).otherwise(0)
            ).alias(c)
            for c in feature_cols
        ]
    ).first().asDict()

    complete = sum(
        n == EXPECTED_DISTRICTS
        for n in coverage.values()
    )

    sparse = sorted(
        [
            (c, n)
            for c, n in coverage.items()
            if n < 86
        ],
        key=lambda x: (x[1], x[0]),
    )

    summary = {
        "distritos": EXPECTED_DISTRICTS,
        "colunas_totais": len(result.columns),
        "atributos_numericos": len(feature_cols) - 1,
        "atributos_com_cobertura_total": complete,
        "atributos_com_menos_86_distritos": sparse,
        "observasampa_indicadores": len(indicators),
        "observasampa_referencia": {
            str(r["indicador"]): int(r["ano_ref"])
            for r in obs_stats
        },
        "ssp_rubricas": len(rubricas),
        "ssp_inicio_janela": str(first_day),
        "ssp_fim_janela": str(last_day),
        "ssp_sem_distrito_na_janela": unlocated,
        "silver_delta_versions": versions,
        "observasampa_colunas": obs_names,
        "ssp_colunas": ssp_names,
        "imoveis": imoveis_summary,
    }

    return result, summary


# ============================================================
# 5. COMPARAR PROPOSTA COM DESTINO
# ============================================================

def target_status(spark, proposed):
    if not spark.catalog.tableExists(TARGET):
        return {
            "exists": False,
            "schema_equal": False,
            "identical": False,
        }

    current = spark.table(TARGET)

    schema_equal = same_schema(
        current, proposed
    )

    if not schema_equal:
        return {
            "exists": True,
            "schema_equal": False,
            "identical": False,
        }

    if current.count() != proposed.count():
        return {
            "exists": True,
            "schema_equal": True,
            "identical": False,
        }

    identical = (
        current.exceptAll(
            proposed
        ).limit(1).count() == 0
        and proposed.exceptAll(
            current
        ).limit(1).count() == 0
    )

    return {
        "exists": True,
        "schema_equal": True,
        "identical": identical,
    }


# ============================================================
# 6. ATUALIZAR GOLD EXISTENTE
# ============================================================

def update_target(spark, proposed, versions):
    """
    Publicacao Delta controlada.

    Nao cria, exclui nem renomeia distritos.
    Nao altera schema.
    Atualiza todos os atributos quando o snapshot muda.

    A transacao MERGE e atomica no Delta.
    A verificacao de versao anterior reduz risco de
    concorrencia, mas nao substitui o controle
    transacional do Delta Lake.
    """

    require(
        spark.catalog.tableExists(TARGET),
        "Gold ausente: --update exige tabela existente",
    )

    # Contrato da tabela existente.

    current = spark.table(TARGET)

    require(
        same_schema(current, proposed),
        "Gold existente possui schema diferente. "
        "Atualizacao bloqueada.",
    )

    assert_exact_codes(
        proposed, current
    )

    detail = spark.sql(
        f"DESCRIBE DETAIL {TARGET}"
    ).select("format").first()

    require(
        detail is not None
        and detail["format"].lower() == "delta",
        "Gold existente nao esta em Delta Lake",
    )

    # Capturar versao antes das ultimas verificacoes.

    target_version = delta_version(
        spark, TARGET
    )

    require(
        source_versions_unchanged(spark, versions),
        "Fonte Silver mudou antes da publicacao",
    )

    require(
        delta_version(spark, TARGET) == target_version,
        "Gold mudou durante a preparacao",
    )

    # Conferir novamente se a proposta ja esta publicada.

    status = target_status(
        spark, proposed
    )

    require(
        status["schema_equal"],
        "Schema Gold alterado durante a preparacao",
    )

    if status["identical"]:
        emit(
            "GOLD_DISTRICTS_UNCHANGED",
            target=TARGET,
            changed_tables=False,
        )
        return {
            "changed": False,
            "version_before": target_version,
            "version_after": target_version,
        }

    # Montar um MERGE estrito:
    # chave CD_DIST, sem inserts e sem deletes.
    # Todos os atributos devem existir em ambas as tabelas.

    fields = [
        c for c in proposed.columns
        if c != "CD_DIST"
    ]

    require(
        fields,
        "Gold proposta nao possui atributos",
    )

    assignments = ",\n        ".join(
        f"t.`{c}` = s.`{c}`"
        for c in fields
    )

    view = (
        "bairroiq_gold_update_"
        + uuid4().hex
    )

    proposed.createOrReplaceTempView(
        view
    )

    try:
        require(
            source_versions_unchanged(spark, versions),
            "Fonte Silver mudou antes do MERGE",
        )

        require(
            delta_version(spark, TARGET) == target_version,
            "Gold mudou antes do MERGE",
        )

        sql = f"""
        MERGE INTO {TARGET} AS t
        USING {view} AS s

        ON t.CD_DIST = s.CD_DIST

        WHEN MATCHED
        THEN UPDATE SET
            {assignments}
        """

        spark.sql(sql).collect()

    finally:
        spark.catalog.dropTempView(view)

    # Auditoria integral apos a publicacao.

    final_status = target_status(
        spark, proposed
    )

    require(
        final_status["schema_equal"]
        and final_status["identical"],
        "Gold publicada diverge da proposta validada. "
        "Verificar transacao Delta antes de reexecutar.",
    )

    final = spark.table(TARGET)

    assert_exact_codes(
        proposed, final
    )

    version_after = delta_version(
        spark, TARGET
    )

    require(
        version_after > target_version,
        "MERGE nao gerou nova versao Delta",
    )

    emit(
        "GOLD_DISTRICTS_UPDATE_SUCCESS",
        target=TARGET,
        districts=EXPECTED_DISTRICTS,
        columns=len(proposed.columns),
        version_before=target_version,
        version_after=version_after,
        identical_after_update=True,
    )

    return {
        "changed": True,
        "version_before": target_version,
        "version_after": version_after,
    }


# ============================================================
# 7. EXECUCAO
# ============================================================

def execute(spark, apply=False, update=False):

    require(
        not (apply and update),
        "Nao e permitido aplicar e atualizar simultaneamente",
    )

    sources = (
        IBGE,
        GEO,
        OBS,
        SSP,
        IMOVEIS,
        DEPARA,
    )

    for table in sources:
        require(
            spark.catalog.tableExists(table),
            f"Fonte ausente: {table}",
        )

    versions = {
        table: delta_version(spark, table)
        for table in sources
    }

    proposed, summary = build(
        spark, versions
    )

    status = target_status(
        spark, proposed
    )

    require(
        source_versions_unchanged(spark, versions),
        "Uma fonte Silver mudou durante a validacao",
    )

    emit(
        "GOLD_DISTRICTS_VALIDATED",
        distritos=summary["distritos"],
        colunas=summary["colunas_totais"],
        atributos_numericos=summary["atributos_numericos"],
        imoveis=summary["imoveis"],
        target_status=status,
    )

    emit(
        "GOLD_FEATURE_MAPPING",
        observasampa_referencia=summary[
            "observasampa_referencia"
        ],
        observasampa_colunas=summary[
            "observasampa_colunas"
        ],
        ssp_colunas=summary[
            "ssp_colunas"
        ],
    )

    # --------------------------------------------------------
    # 7.1. MODO CHECK
    # --------------------------------------------------------

    if not apply and not update:
        emit(
            "GOLD_DISTRICTS_CHECK_SUCCESS",
            changed_tables=False,
            changed_files=False,
            target_identical=status["identical"],
        )

        return summary

    # --------------------------------------------------------
    # 7.2. SEM ALTERACOES
    # --------------------------------------------------------

    if status["identical"]:
        emit(
            "GOLD_DISTRICTS_UNCHANGED",
            changed_tables=False,
        )

        return summary

    # --------------------------------------------------------
    # 7.3. MODO UPDATE
    # --------------------------------------------------------

    if update:
        require(
            status["exists"],
            "Gold inexistente: --update bloqueado",
        )

        require(
            status["schema_equal"],
            "Gold com schema divergente. "
            "Atualizacao bloqueada.",
        )

        update_result = update_target(
            spark,
            proposed,
            versions,
        )

        emit(
            "GOLD_UPDATE_RESULT",
            **update_result,
        )

        return summary

    # --------------------------------------------------------
    # 7.4. MODO APPLY (CRIACAO INICIAL)
    # --------------------------------------------------------

    require(
        not status["exists"],
        "Gold existente com dados diferentes: "
        "criacao bloqueada. "
        "Use --update somente apos validacao.",
    )

    require(
        source_versions_unchanged(spark, versions),
        "Fonte Silver mudou antes da publicacao",
    )

    view = (
        "bairroiq_gold_publish_"
        + uuid4().hex
    )

    proposed.createOrReplaceTempView(
        view
    )

    try:
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {TARGET} "
            f"USING DELTA AS "
            f"SELECT * FROM {view}"
        ).collect()

    finally:
        spark.catalog.dropTempView(view)

    final_status = target_status(
        spark, proposed
    )

    require(
        final_status["identical"],
        "Gold publicada diverge da proposta validada",
    )

    emit(
        "GOLD_DISTRICTS_APPLY_SUCCESS",
        target=TARGET,
        distritos=EXPECTED_DISTRICTS,
        colunas=summary["colunas_totais"],
        imoveis=summary["imoveis"],
    )

    return summary


# ============================================================
# 8. INTERFACE DE LINHA DE COMANDO
# ============================================================

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
        help="Validar sem publicar",
    )

    mode.add_argument(
        "--apply",
        action="store_true",
        help="Criar Gold inexistente",
    )

    mode.add_argument(
        "--update",
        action="store_true",
        help="Atualizar Gold existente",
    )

    parser.add_argument(
        "--confirm-publish",
        action="store_true",
        help="Confirmacao obrigatoria de escrita",
    )

    args = parser.parse_args(argv)

    publish = args.apply or args.update

    if publish != args.confirm_publish:
        parser.error(
            "Publicacao exige --confirm-publish. "
            "--check nao aceita confirmacao. "
            "Use --apply ou --update, nunca ambos."
        )

    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder
        .getOrCreate()
    )

    execute(
        spark,
        apply=args.apply,
        update=args.update,
    )


if __name__ == "__main__":
    main()
