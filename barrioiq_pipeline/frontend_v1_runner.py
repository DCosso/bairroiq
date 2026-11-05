"""BairroIQ | Contrato do frontend v1, apenas leitura.

96 distritos oficiais, oito colunas visuais e metadados técnicos.
Os índices de empregos, mobilidade e ocorrências são relativos ao universo
fixo de 96 distritos; não representam qualidade de vida ou risco individual.

Nenhuma tabela/view/arquivo é criada por este módulo. O runner valida o
snapshot Delta existente antes de combinar a Gold original para obter LED.
"""
from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd

BASE = Path(__file__).resolve().parent
DELTA_RUNNER = BASE / "star_schema_v1_delta_runner.py"
CATALOG = "workspace"
SCHEMA = "gold"
SNAPSHOT = (
    "v3.0.0-candidato|"
    "726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b"
)
STATUS = "PREVIA_DIMENSIONAL_NAO_PUBLICAVEL"
LED_GOLD_FIELD = "obs_porcentagem_de_lampadas_led_na_iluminacao_p_a1e1d34b"
METRICS = ("empregos", "roubos", "furtos", "metro", "onibus", "trem")
ALL_METRICS = (
    "empregos", "roubos", "furtos", "metro", "onibus", "trem",
    "pracas", "corredores_verdes", "escolas", "ubs", "densidade",
)
SOURCE_TABLES = {
    "dim_snapshot": "bairroiq_dim_snapshot",
    "dim_distrito": "bairroiq_dim_distrito",
    "dim_perfil": "bairroiq_dim_perfil",
    "dim_indicador": "bairroiq_dim_indicador",
    "fato_distrito_indicador": "bairroiq_fato_distrito_indicador",
    "fato_distrito_perfil": "bairroiq_fato_distrito_perfil",
    "fato_prioridade_ocorrencias": "bairroiq_fato_prioridade_ocorrencias",
}
COUNTS = {
    "dim_snapshot": 1, "dim_distrito": 96, "dim_perfil": 9,
    "dim_indicador": 11, "fato_distrito_indicador": 1056,
    "fato_distrito_perfil": 96, "fato_prioridade_ocorrencias": 96,
}
VISUAL_COLUMNS = (
    "Distrito", "Empregos", "Roubos", "Segurança",
    "Iluminação LED", "Arborização", "Mobilidade", "Cluster",
)
TECH_COLUMNS = (
    "snapshot_id", "cd_dist", "distrito", "latitude", "longitude",
    "perfil_id", "cluster", "empregos", "roubos", "seguranca",
    "iluminacao_led", "arborizacao", "mobilidade", "tipo_territorio",
    "publicacao_autorizada",
)
METADATA = {
    "Empregos": {
        "unidade": "percentil relativo 0–100",
        "fonte": "ObservaSampa, empregos formais (2021)",
        "definicao": "Posição relativa do total de vínculos formais, não vagas disponíveis.",
    },
    "Roubos": {
        "unidade": "registros por 1.000 habitantes, janela 12 meses",
        "fonte": "SSP-SP / Gold",
        "definicao": "Taxa administrativa de roubos (art. 157); não é risco individual.",
    },
    "Segurança": {
        "unidade": "índice relativo 0–100",
        "fonte": "SSP-SP / prioridade de ocorrências v1",
        "definicao": "100 menos índice médio dos percentis de roubos e furtos; não mede segurança geral.",
    },
    "Iluminação LED": {
        "unidade": "porcentagem (%)",
        "fonte": "ObservaSampa / Gold",
        "definicao": "Percentual de lâmpadas LED na iluminação pública; período não uniformizado.",
    },
    "Arborização": {
        "unidade": "não definida",
        "fonte": "pendente",
        "definicao": "NULL até homologação de indicador específico de arborização.",
    },
    "Mobilidade": {
        "unidade": "índice relativo 0–100",
        "fonte": "GeoSampa / Gold",
        "definicao": "Média dos percentis de equipamentos de metrô, ônibus e trem por 10 mil hab.; não é tempo de viagem.",
    },
    "Cluster": {
        "unidade": "categoria",
        "fonte": "BairroIQ K-Means v3 candidato",
        "definicao": "Grupo estatístico provisório, não ranking nem recomendação automática.",
    },
}


class FrontendContractError(ValueError):
    pass


def require(ok: bool, msg: str) -> None:
    if not bool(ok):
        raise FrontendContractError("BAIRROIQ_FRONTEND_V1_BLOCKED: " + msg)


def columns(df: pd.DataFrame, required: tuple[str, ...], name: str) -> None:
    require(isinstance(df, pd.DataFrame), f"{name}: não é DataFrame")
    missing = set(required) - set(df.columns)
    require(not missing, f"{name}: faltam colunas {sorted(missing)}")


def unique(df: pd.DataFrame, keys: tuple[str, ...], count: int, name: str) -> None:
    require(len(df) == count, f"{name}: esperados {count}, obtidos {len(df)}")
    require(df[list(keys)].notna().all().all(), f"{name}: chave nula")
    require(not df.duplicated(list(keys)).any(), f"{name}: chave duplicada")


def numeric(df: pd.DataFrame, fields: tuple[str, ...], name: str,
            *, nonnegative: bool = True) -> pd.DataFrame:
    out = df.copy()
    for field in fields:
        out[field] = pd.to_numeric(out[field], errors="coerce")
        require(out[field].notna().all(), f"{name}.{field}: nulo ou inválido")
        require(out[field].map(lambda x: math.isfinite(float(x))).all(),
                f"{name}.{field}: valor não finito")
        if nonnegative:
            require(out[field].ge(0).all(), f"{name}.{field}: negativo")
    return out


def round_like_spark(value: Any, digits: int) -> float:
    """ROUND_HALF_UP como Spark F.round, evitando round half-even do pandas."""
    quant = Decimal("1").scaleb(-digits)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def inverse_priority(value: Any) -> float:
    """Preserva arredondamento de 100 - índice de ocorrências."""
    return round_like_spark(Decimal("100") - Decimal(str(value)), 1)


def percentile_rank(series: pd.Series) -> pd.Series:
    """Mesmo cálculo que Spark percent_rank(): (rank_min-1)/(n-1)*100."""
    require(len(series) > 1 and series.notna().all(), "Percentil com entrada inválida")
    return ((series.rank(method="min", ascending=True) - 1) * 100 / (len(series) - 1))


def build_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Transformação pura testável localmente; NÃO contém operações Spark/write."""
    require(set(frames) == set(SOURCE_TABLES) | {"gold_led"},
            "Conjunto de fontes inesperado")
    for name, count in COUNTS.items():
        columns(frames[name], ("snapshot_id",), name)
        require(frames[name]["snapshot_id"].eq(SNAPSHOT).all(),
                f"{name}: snapshot errado")
        require(len(frames[name]) == count, f"{name}: cardinalidade inesperada")

    s = frames["dim_snapshot"]
    unique(s, ("snapshot_id",), 1, "dim_snapshot")
    columns(s, ("status", "disponivel_publicamente", "sha256_gold", "catalogo_versao"), "dim_snapshot")
    require(s.iloc[0]["status"] == STATUS and s.iloc[0]["disponivel_publicamente"] == False,
            "Snapshot público ou status inesperado")
    require(s.iloc[0]["sha256_gold"] == SNAPSHOT.split("|", 1)[1]
            and s.iloc[0]["catalogo_versao"] == "v3.0.0-candidato",
            "Metadados de versão/hash divergentes")

    d = frames["dim_distrito"]
    columns(d, ("CD_DIST", "NM_DIST", "latitude", "longitude"), "dim_distrito")
    unique(d, ("snapshot_id", "CD_DIST"), 96, "dim_distrito")
    require(d["NM_DIST"].notna().all() and d["NM_DIST"].astype(str).str.strip().ne("").all(),
            "Distrito sem nome")
    d = numeric(d, ("CD_DIST", "latitude", "longitude"), "dim_distrito", nonnegative=False)
    require(d["latitude"].between(-24, -23).all() and d["longitude"].between(-47, -46).all(),
            "Coordenadas fora de SP")

    p = frames["dim_perfil"]
    columns(p, ("perfil_sk", "perfil_id", "nome_exibicao_proposto", "disponivel_publicamente"), "dim_perfil")
    unique(p, ("snapshot_id", "perfil_sk"), 9, "dim_perfil")
    require(p["perfil_id"].nunique() == 9, "Não há nove clusters")
    require(p["disponivel_publicamente"].eq(False).all(), "Há perfis públicos")
    require(p["nome_exibicao_proposto"].notna().all()
            and p["nome_exibicao_proposto"].astype(str).str.strip().ne("").all(),
            "Nome de cluster vazio")
    require(p["perfil_id"].astype(str).str.fullmatch(r"kmeans-k09-p\d{2}").all(),
            "Identificação de cluster inesperada")

    fp = frames["fato_distrito_perfil"]
    columns(fp, ("CD_DIST", "perfil_sk"), "fato_distrito_perfil")
    unique(fp, ("snapshot_id", "CD_DIST"), 96, "fato_distrito_perfil")

    o = frames["fato_prioridade_ocorrencias"]
    columns(o, ("CD_DIST", "indice_ordenacao_ocorrencias"), "fato_prioridade_ocorrencias")
    unique(o, ("snapshot_id", "CD_DIST"), 96, "fato_prioridade_ocorrencias")
    o = numeric(o, ("indice_ordenacao_ocorrencias",), "fato_prioridade_ocorrencias")
    require(o["indice_ordenacao_ocorrencias"].between(0, 100).all(), "Índice de ocorrências fora de 0–100")

    i = frames["dim_indicador"]
    columns(i, ("indicador_sk", "indicador_id"), "dim_indicador")
    unique(i, ("snapshot_id", "indicador_sk"), 11, "dim_indicador")
    require(set(i["indicador_id"]) == set(ALL_METRICS), "Catálogo de indicadores mudou")
    fi = frames["fato_distrito_indicador"]
    columns(fi, ("CD_DIST", "indicador_sk", "valor_numerico"), "fato_distrito_indicador")
    unique(fi, ("snapshot_id", "CD_DIST", "indicador_sk"), 1056, "fato_distrito_indicador")
    fi = numeric(fi, ("valor_numerico",), "fato_distrito_indicador")
    li = fi.merge(i[["snapshot_id", "indicador_sk", "indicador_id"]],
                  on=["snapshot_id", "indicador_sk"], how="inner", validate="many_to_one")
    require(len(li) == 1056, "Fato perdeu indicadores no join")
    require(not li.duplicated(["CD_DIST", "indicador_id"]).any(), "Fato tem indicadores duplicados")
    pivot = li.loc[li["indicador_id"].isin(METRICS)].pivot(
        index=["snapshot_id", "CD_DIST"], columns="indicador_id", values="valor_numerico"
    ).reset_index()
    require(len(pivot) == 96 and set(METRICS).issubset(pivot.columns),
            "Pivot de indicadores incompleto")
    pivot.columns.name = None
    pivot = numeric(pivot, METRICS, "pivot")

    led = frames["gold_led"]
    columns(led, ("CD_DIST", "led_pct"), "gold_led")
    unique(led, ("CD_DIST",), 96, "gold_led")
    led = numeric(led, ("led_pct",), "gold_led")
    require(led.led_pct.between(0, 100).all(), "LED fora de 0–100")

    base = (d.merge(pivot, on=["snapshot_id", "CD_DIST"], how="inner", validate="one_to_one")
            .merge(fp[["snapshot_id", "CD_DIST", "perfil_sk"]],
                   on=["snapshot_id", "CD_DIST"], how="inner", validate="one_to_one")
            .merge(p[["snapshot_id", "perfil_sk", "perfil_id", "nome_exibicao_proposto"]],
                   on=["snapshot_id", "perfil_sk"], how="inner", validate="many_to_one")
            .merge(o[["snapshot_id", "CD_DIST", "indice_ordenacao_ocorrencias"]],
                   on=["snapshot_id", "CD_DIST"], how="inner", validate="one_to_one")
            .merge(led, on="CD_DIST", how="inner", validate="one_to_one"))
    require(len(base) == 96 and base.CD_DIST.nunique() == 96, "Join territorial perdeu ou duplicou distritos")
    require(base.perfil_id.nunique() == 9, "Distribuição perdeu clusters")
    code = base.perfil_id.str.extract(r"(p\d{2})$")[0].str.upper()
    require(code.notna().all(), "Código do cluster inválido")

    tech = pd.DataFrame({
        "snapshot_id": base.snapshot_id,
        "cd_dist": base.CD_DIST.astype("int64"),
        "distrito": base.NM_DIST,
        "latitude": base.latitude.astype(float),
        "longitude": base.longitude.astype(float),
        "perfil_id": base.perfil_id,
        "cluster": code + " — " + base.nome_exibicao_proposto,
        "empregos": percentile_rank(base.empregos).map(lambda v: round_like_spark(v, 1)),
        "roubos": base.roubos.map(lambda v: round_like_spark(Decimal(str(v)) / 100, 2)),
        "seguranca": base.indice_ordenacao_ocorrencias.map(inverse_priority),
        "iluminacao_led": base.led_pct.map(lambda v: round_like_spark(v, 1)),
        "arborizacao": pd.Series([None] * len(base), index=base.index, dtype="object"),
        "mobilidade": ((percentile_rank(base.metro) + percentile_rank(base.onibus)
                        + percentile_rank(base.trem)) / 3).map(lambda v: round_like_spark(v, 1)),
        "tipo_territorio": "DISTRITO_IBGE",
        "publicacao_autorizada": False,
    })[list(TECH_COLUMNS)].sort_values("distrito").reset_index(drop=True)
    require(tech.cd_dist.nunique() == 96 and tech.cluster.nunique() == 9,
            "Chaves/cluster inválidos")
    for field in ("empregos", "seguranca", "mobilidade", "iluminacao_led"):
        require(tech[field].notna().all() and tech[field].between(0, 100).all(),
                f"{field}: fora de 0–100")
    require(tech.roubos.notna().all() and tech.roubos.ge(0).all(), "Roubos inválidos")
    require(tech.arborizacao.isna().all() and tech.publicacao_autorizada.eq(False).all(),
            "Arborização inventada ou publicação autorizada")
    visual = tech.rename(columns={
        "distrito": "Distrito", "empregos": "Empregos", "roubos": "Roubos",
        "seguranca": "Segurança", "iluminacao_led": "Iluminação LED",
        "arborizacao": "Arborização", "mobilidade": "Mobilidade", "cluster": "Cluster",
    })[list(VISUAL_COLUMNS)]
    require(len(visual) == 96 and list(visual.columns) == list(VISUAL_COLUMNS),
            "Formato visual errado")
    return {
        "visual": visual,
        "tecnico": tech,
        "metadados": METADATA,
        "resumo": {
            "status": STATUS, "snapshot_id": SNAPSHOT, "distritos": len(visual),
            "clusters": tech.cluster.nunique(), "indicadores_led_preenchidos": int(tech.iluminacao_led.notna().sum()),
            "arborizacao_valores_preenchidos": int(tech.arborizacao.notna().sum()),
            "publicacao_autorizada": False, "alteracoes_gold": "NENHUMA",
            "escrita_executada": False,
            "nota": "Distrito = distrito administrativo oficial do IBGE; escalas diferentes entre colunas",
            "led_origem": f"{CATALOG}.{SCHEMA}.distritos_wide:{LED_GOLD_FIELD}",
            "led_versao_dado": "live_da_gold; nao incluída no hash dos 11 indicadores ML; fixar versão antes da materialização",
        },
    }


def run_from_spark(spark_session: Any) -> dict[str, Any]:
    """Lê dados reais de forma limitada e valida os sete snapshots antes do consumo."""
    require(DELTA_RUNNER.is_file(), f"Delta runner ausente: {DELTA_RUNNER}")
    spec = importlib.util.spec_from_file_location("bairroiq_delta_read_only_for_frontend", str(DELTA_RUNNER))
    require(spec is not None and spec.loader is not None, "Runner Delta não importável")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plan = mod.check(spark_session)  # Read-only: valida Gold e os 7 Delta.
    require(plan.get("will_write_on_check") is False
            and plan.get("publicacao_gold_autorizada") is False
            and plan.get("snapshot_id") == SNAPSHOT, "Preflight Delta inválido")
    require(all(plan["tables"][name]["rows_in_snapshot"] == COUNTS[name]
                and plan["tables"][name]["action_if_applied"] == "KEEP_VERIFIED"
                for name in COUNTS), "Alguma relação Delta ainda não está reconciliada")

    from pyspark.sql import functions as F
    frames = {}
    for entity, table in SOURCE_TABLES.items():
        frames[entity] = (spark_session.table(f"{CATALOG}.{SCHEMA}.{table}")
                          .where(F.col("snapshot_id") == SNAPSHOT).toPandas())
    frames["gold_led"] = (spark_session.table(f"{CATALOG}.{SCHEMA}.distritos_wide")
                           .select("CD_DIST", F.col(LED_GOLD_FIELD).cast("double").alias("led_pct"))
                           .toPandas())
    return build_from_frames(frames)
