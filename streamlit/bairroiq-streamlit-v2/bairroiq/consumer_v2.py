"""Adaptador de leitura do snapshot BairroIQ V2 para o Streamlit integrado.

- Apenas leitura: não cria VIEW, tabela, grant, CSV, nem muda a Gold.
- Um snapshot imutável (96 distritos) e nove perfis exploratórios.
- Verde/lazer = percentis de praças e corredores verdes; NÃO é arborização.
- Serviços = percentis de escolas e UBS; NÃO é custo de vida.
- Densidade em habitantes/km², NÃO é nota de qualidade.
- Preview interno requer opt-in explícito no conector e ambiente restrito.
"""
from __future__ import annotations

import math
import re

import pandas as pd

SNAPSHOT = (
    "v3.0.0-candidato|"
    "726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b"
)
REQUIRED_COLUMNS = (
    "snapshot_id", "cd_dist", "neighborhood", "latitude", "longitude",
    "formal_jobs_score", "safety_score", "mobility_score",
    "green_leisure_score", "public_services_score", "densidade_hab_km2",
    "robberies_per_1000", "perfil_id", "cluster", "tipo_territorio",
    "publicacao_autorizada",
)
_SCORE_COLUMNS = (
    "formal_jobs_score", "safety_score", "mobility_score",
    "green_leisure_score", "public_services_score",
)
_QUANTITIES = ("densidade_hab_km2", "robberies_per_1000")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_SQL = "WITH consumer AS (\n    SELECT\n        snapshot_id,\n        cd_dist,\n        distrito,\n        latitude,\n        longitude,\n        perfil_id,\n        cluster,\n        empregos,\n        roubos,\n        seguranca,\n        mobilidade,\n        tipo_territorio,\n        publicacao_autorizada\n    FROM {table}\n    WHERE snapshot_id = '{snapshot}'\n      {gate}\n),\nextras_raw AS (\n    SELECT\n        f.snapshot_id,\n        f.CD_DIST AS cd_dist,\n        MAX(CASE WHEN i.indicador_id = 'pracas' THEN f.valor_numerico END) AS pracas_por_10mil,\n        MAX(CASE WHEN i.indicador_id = 'corredores_verdes' THEN f.valor_numerico END) AS corredores_por_10mil,\n        MAX(CASE WHEN i.indicador_id = 'escolas' THEN f.valor_numerico END) AS escolas_por_10mil,\n        MAX(CASE WHEN i.indicador_id = 'ubs' THEN f.valor_numerico END) AS ubs_por_10mil,\n        MAX(CASE WHEN i.indicador_id = 'densidade' THEN f.valor_numerico END) AS densidade_hab_km2,\n        COUNT(*) AS contagem_indicadores_extra,\n        COUNT(DISTINCT i.indicador_id) AS indicadores_extra_distintos\n    FROM workspace.gold.bairroiq_fato_distrito_indicador AS f\n    INNER JOIN workspace.gold.bairroiq_dim_indicador AS i\n        ON f.snapshot_id = i.snapshot_id\n       AND f.indicador_sk = i.indicador_sk\n    WHERE f.snapshot_id = '{snapshot}'\n      AND i.indicador_id IN ('pracas','corredores_verdes','escolas','ubs','densidade')\n    GROUP BY f.snapshot_id, f.CD_DIST\n),\nextras_percentis AS (\n    SELECT\n        snapshot_id,\n        cd_dist,\n        pracas_por_10mil,\n        corredores_por_10mil,\n        escolas_por_10mil,\n        ubs_por_10mil,\n        densidade_hab_km2,\n        contagem_indicadores_extra,\n        indicadores_extra_distintos,\n        100.0 * PERCENT_RANK() OVER (ORDER BY pracas_por_10mil) AS pr_pracas,\n        100.0 * PERCENT_RANK() OVER (ORDER BY corredores_por_10mil) AS pr_corredores,\n        100.0 * PERCENT_RANK() OVER (ORDER BY escolas_por_10mil) AS pr_escolas,\n        100.0 * PERCENT_RANK() OVER (ORDER BY ubs_por_10mil) AS pr_ubs\n    FROM extras_raw\n)\nSELECT\n    c.snapshot_id,\n    c.cd_dist,\n    c.distrito AS neighborhood,\n    c.latitude,\n    c.longitude,\n    c.empregos AS formal_jobs_score,\n    c.seguranca AS safety_score,\n    c.mobilidade AS mobility_score,\n    ROUND((e.pr_pracas + e.pr_corredores) / 2.0, 1) AS green_leisure_score,\n    ROUND((e.pr_escolas + e.pr_ubs) / 2.0, 1) AS public_services_score,\n    e.densidade_hab_km2,\n    c.roubos AS robberies_per_1000,\n    c.perfil_id,\n    c.cluster,\n    c.tipo_territorio,\n    c.publicacao_autorizada,\n    e.contagem_indicadores_extra,\n    e.indicadores_extra_distintos\nFROM consumer AS c\nLEFT JOIN extras_percentis AS e\n    ON c.snapshot_id = e.snapshot_id\n   AND c.cd_dist = e.cd_dist\nORDER BY c.cd_dist\n"


def build_query(metrics_table: str = "workspace.gold.bairroiq_frontend_v1",
                *, internal_preview: bool = False) -> str:
    """Constrói SQL somente de leitura; jamais muda publicacao_autorizada.

    Sem internal_preview, somente os dados efetivamente homologados podem ser
    consumidos. internal_preview=True é só para execução privada/autorizada,
    NUNCA para um app público.
    """
    parts = metrics_table.split(".")
    if len(parts) != 3 or any(not _IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError("Esperada tabela SQL catalog.schema.table validada")
    table = ".".join(f"`{part}`" for part in parts)
    gate = "" if internal_preview else "AND publicacao_autorizada IS TRUE"
    return _SQL.format(table=table, snapshot=SNAPSHOT, gate=gate)


def validate_frame(raw: pd.DataFrame, *, internal_preview: bool = False) -> pd.DataFrame:
    """Verifica invariantes do snapshot e devolve 16 colunas reais sem nulos."""
    missing = set(REQUIRED_COLUMNS).difference(raw.columns)
    if missing:
        raise ValueError(f"Faltam colunas do contrato V2: {sorted(missing)}")
    if len(raw) != 96:
        raise ValueError(f"Esperados 96 distritos, recebidos {len(raw)}")
    df = raw.copy()
    if df[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Nulos no contrato V2")
    if df["snapshot_id"].nunique() != 1 or not df["snapshot_id"].eq(SNAPSHOT).all():
        raise ValueError("Snapshot inesperado")
    if df["cd_dist"].duplicated().any() or df["neighborhood"].duplicated().any():
        raise ValueError("Distrito duplicado")
    if not df["tipo_territorio"].eq("DISTRITO_IBGE").all():
        raise ValueError("Mistura de distritos e bairros")
    publication = df["publicacao_autorizada"]
    if not publication.map(lambda x: isinstance(x, bool)).all():
        raise ValueError("Flag de publicação deve ser booleana")
    if not internal_preview and not publication.all():
        raise PermissionError("Snapshot não homologado para publicação")
    for field in (*_SCORE_COLUMNS, *_QUANTITIES, "latitude", "longitude"):
        df[field] = pd.to_numeric(df[field], errors="coerce")
        if df[field].isna().any() or not df[field].map(math.isfinite).all():
            raise ValueError(f"Indicador não numérico ou não finito: {field}")
    for field in _SCORE_COLUMNS:
        if not df[field].between(0, 100).all():
            raise ValueError(f"Score fora de 0-100: {field}")
    for field in _QUANTITIES:
        if (df[field] < 0).any():
            raise ValueError(f"Quantidade/taxa negativa: {field}")
    if not (df["latitude"].between(-24, -23).all() and
            df["longitude"].between(-47, -46).all()):
        raise ValueError("Centroides fora de São Paulo")
    if df["perfil_id"].nunique() != 9 or not df["perfil_id"].astype(str).str.fullmatch(r"kmeans-k09-p0[1-9]").all():
        raise ValueError("K-Means: eram esperados nove perfis P01-P09")
    # Contagens calculadas dentro da query de validação, se presentes
    for c in ("contagem_indicadores_extra", "indicadores_extra_distintos"):
        if c in df and not pd.to_numeric(df[c],errors="coerce").eq(5).all():
            raise ValueError(f"Fato distrital incompleto: {c}")
    return df.loc[:, list(REQUIRED_COLUMNS)].sort_values("neighborhood").reset_index(drop=True)
