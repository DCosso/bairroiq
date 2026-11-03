"""BairroIQ | Validacao reproduzivel da Silver SSP por distrito.

Execucao local sem argumentos: verifica o contrato do executor, sem Spark.
Execucao no Databricks com --check: refaz a associacao espacial em
memoria e compara todas as oito colunas, com multiplicidade de linhas,
contra a tabela existente. Nao grava tabelas nem arquivos.

Dependencias para --check no Databricks: geopandas==1.1.1, pandas, numpy,
PySpark e acesso ao Shapefile do IBGE no Unity Catalog Volume.
"""

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path


# ============================================================
# 1. CONTRATO DO EXECUTOR
# ============================================================

SOURCE = "workspace.silver.ssp_ocorrencias"
TARGET = "workspace.silver.ssp_ocorrencias_distrito"
DISTRICT_REFERENCE = "workspace.silver.ibge_agregados_basicos_v2"

SHAPEFILE = Path(
    "/Volumes/workspace/bronze/raw/ibge/"
    "malha_distritos_2022/shapefile/SP_distritos_CD2022.shp"
)

MUNICIPALITY = "3550308"
CRS = "EPSG:4674"
EXPECTED_DISTRICTS = 96
STATUS = "CONVERTIDA"

OUTPUT_COLUMNS = [
    "numero_bo",
    "data_ocorrencia",
    "rubrica",
    "bairro_normalizado",
    "latitude",
    "longitude",
    "CD_DIST",
    "NM_DIST",
]

SOURCE_COLUMNS = OUTPUT_COLUMNS[:6]
SHAPE_COMPONENTS = (".shp", ".shx", ".dbf", ".prj")


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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_contract():
    """Verificacoes estaticas que funcionam sem Databricks."""
    require(len(OUTPUT_COLUMNS) == 8, "Contrato: esperadas 8 colunas")
    require(len(set(OUTPUT_COLUMNS)) == 8, "Colunas duplicadas")
    require(len(set(SOURCE_COLUMNS)) == 6, "Origem inesperada")
    require(SOURCE != TARGET, "Origem e destino nao podem coincidir")
    require(EXPECTED_DISTRICTS == 96, "Quantidade distrital inesperada")
    require(SHAPEFILE.suffix.lower() == ".shp", "Malha nao e SHP")
    emit("SSP_STATIC_VALIDATION_SUCCESS", read_only=True)


def delta_version(spark, table):
    """Captura a versao Delta para consulta consistente."""
    history = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()
    require(history is not None, f"Historico Delta ausente: {table}")
    return int(history["version"])


def hash_shapefile():
    """Calcula a identidade dos quatro componentes obrigatorios do SHP."""
    sha = hashlib.sha256()
    for suffix in SHAPE_COMPONENTS:
        part = SHAPEFILE.with_suffix(suffix)
        require(part.is_file(), f"Arquivo da malha ausente: {part}")
        sha.update(suffix.encode("ascii"))
        with part.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
    return sha.hexdigest()


def load_districts(gpd, spark, ibge_version):
    """Carrega os poligonos e confirma a correspondencia com IBGE Silver."""
    source = gpd.read_file(SHAPEFILE)
    require(source.crs is not None, "Shapefile nao possui CRS")

    necessary = {"CD_MUN", "CD_DIST", "NM_DIST", "geometry"}
    require(
        necessary.issubset(source.columns),
        f"Colunas ausentes na malha: {sorted(necessary - set(source.columns))}",
    )

    selected = source.loc[
        source["CD_MUN"]
        .astype("string")
        .str.strip()
        .eq(MUNICIPALITY)
        .fillna(False)
    ].copy()

    selected["CD_DIST"] = selected["CD_DIST"].astype("string").str.strip()
    selected["NM_DIST"] = selected["NM_DIST"].astype("string").str.strip()

    require(len(selected) == EXPECTED_DISTRICTS, "Quantidade incorreta de distritos")
    require(selected["CD_DIST"].notna().all(), "Distrito sem codigo")
    require(selected["CD_DIST"].ne("").all(), "Distrito com codigo vazio")
    require(selected["NM_DIST"].notna().all(), "Distrito sem nome")
    require(selected["NM_DIST"].ne("").all(), "Distrito com nome vazio")
    require(
        selected["CD_DIST"].nunique() == EXPECTED_DISTRICTS,
        "Codigos distritais nao sao unicos",
    )
    require(selected.geometry.notna().all(), "Geometrias distritais nulas")
    require(not selected.geometry.is_empty.any(), "Geometrias vazias")
    require(selected.geometry.is_valid.all(), "Geometrias invalidas")

    selected = selected.to_crs(CRS)

    ibge_rows = spark.sql(
        f"SELECT CD_DIST FROM {DISTRICT_REFERENCE} "
        f"VERSION AS OF {ibge_version}"
    ).collect()
    ibge_codes = {str(r["CD_DIST"]).strip() for r in ibge_rows if r["CD_DIST"] is not None}
    shape_codes = set(selected["CD_DIST"].tolist())

    require(len(ibge_rows) == EXPECTED_DISTRICTS, "Silver IBGE nao possui 96 linhas")
    require(ibge_codes == shape_codes, "Codigos da malha diferem da Silver IBGE")

    emit(
        "MALHA_VALIDATED",
        districts=len(selected),
        crs=str(selected.crs),
        polygons_valid=True,
        ibge_codes_match=True,
    )
    return selected[["CD_DIST", "NM_DIST", "geometry"]]


def load_source(spark, source_version):
    """Reproduz exatamente o filtro usado na transformacao da Aline."""
    from pyspark.sql import functions as F

    df = spark.sql(f"SELECT * FROM {SOURCE} VERSION AS OF {source_version}")
    needed = set(SOURCE_COLUMNS) | {"status_coordenada"}
    require(needed.issubset(df.columns), f"Origem sem campos: {sorted(needed - set(df.columns))}")

    filtered = (
        df.filter(
            (F.col("status_coordenada") == F.lit(STATUS))
            & F.col("latitude").isNotNull()
            & F.col("longitude").isNotNull()
        )
        .select(*SOURCE_COLUMNS)
    )

    # Este recorte foi validado anteriormente com 255.707 registros.
    # Nao fixar esse numero para permitir detectar mudancas nas fontes.
    pdf = filtered.toPandas()
    require(not pdf.empty, "Origem sem ocorrencias com coordenadas CONVERTIDA")
    emit("SOURCE_LOADED", rows=len(pdf), source_version=source_version)
    return pdf


def build_spatial_result(gpd, pd, np, source_pdf, districts):
    """Reproduz o point-in-polygon; nao descarta pontos sem distrito."""
    lat = pd.to_numeric(source_pdf["latitude"], errors="coerce")
    lon = pd.to_numeric(source_pdf["longitude"], errors="coerce")

    finite = np.isfinite(lat.to_numpy(dtype="float64")) & np.isfinite(lon.to_numpy(dtype="float64"))
    require(bool(finite.all()), "Origem com coordenadas nao numericas ou infinitas")
    require(bool(lat.between(-90, 90).all()), "Latitude fora da faixa global")
    require(bool(lon.between(-180, 180).all()), "Longitude fora da faixa global")
    require(not bool(((lat == 0) & (lon == 0)).any()), "Origem contem ponto (0,0)")

    points_pdf = source_pdf.copy()
    points_pdf["_row_id"] = np.arange(len(points_pdf), dtype=np.int64)

    points = gpd.GeoDataFrame(
        points_pdf,
        geometry=gpd.points_from_xy(lon, lat),
        crs=CRS,
    )
    require(points.crs == districts.crs, "CRS divergente entre pontos e malha")

    joined = gpd.sjoin(points, districts, how="left", predicate="within")

    require(len(joined) == len(points), "Spatial join alterou a cardinalidade")
    require(
        joined["_row_id"].nunique() == len(points),
        "Spatial join perdeu ou duplicou identificadores de linha",
    )

    assigned = int(joined["CD_DIST"].notna().sum())
    unassigned = int(joined["CD_DIST"].isna().sum())
    unique_districts = int(joined["CD_DIST"].nunique())

    require(assigned + unassigned == len(points), "Contagem espacial inconsistente")
    require(unique_districts == EXPECTED_DISTRICTS, "Nem todos os 96 distritos tiveram ocorrencias")
    require(
        bool(joined.loc[joined["CD_DIST"].notna(), "NM_DIST"].notna().all()),
        "Ocorrencia com distrito sem nome",
    )

    result = pd.DataFrame(joined[OUTPUT_COLUMNS].copy())
    emit(
        "SPATIAL_CARDINALITY_VALIDATED",
        rows=len(result),
        matched=assigned,
        unmatched=unassigned,
        districts=unique_districts,
        percentage=round(assigned * 100.0 / len(result), 4),
    )
    return result


def canonical_value(value):
    """Normaliza representacoes Python sem arredondar numeros ou limpar texto."""
    import numpy as np
    import pandas as pd
    from decimal import Decimal

    if value is None:
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)):
            return None
        require(math.isfinite(float(value)), "Numero infinito encontrado")
        return ["number", float(value).hex()]
    if isinstance(value, (bool, np.bool_)):
        return ["bool", bool(value)]
    if isinstance(value, (int, np.integer)):
        return ["integer", int(value)]
    if isinstance(value, Decimal):
        if value.is_nan():
            return None
        return ["decimal", str(value)]
    if isinstance(value, (date, datetime, pd.Timestamp, np.datetime64)):
        return ["datetime", pd.Timestamp(value).isoformat()]
    if isinstance(value, str):
        return ["text", value]
    raise TypeError(f"Tipo nao previsto na comparacao: {type(value).__name__}")


def row_multiset(df):
    """Compara registros completos e preserva multiplicidade de duplicados.

    Cada linha e representada por SHA-256 de JSON canonico. Isso evita
    depender de uma chave unica, que nao foi comprovada nessa fonte.
    """
    require(set(OUTPUT_COLUMNS).issubset(df.columns), "Colunas ausentes na comparacao")
    result = Counter()
    for row in df[OUTPUT_COLUMNS].itertuples(index=False, name=None):
        encoded = json.dumps(
            [canonical_value(value) for value in row],
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        result[hashlib.sha256(encoded).hexdigest()] += 1
    return result


def compare_target(spark, pd, proposed, target_version):
    """Compara todas as oito colunas, nao so totais por distrito."""
    current = spark.sql(
        f"SELECT * FROM {TARGET} VERSION AS OF {target_version}"
    )
    require(
        set(current.columns) == set(OUTPUT_COLUMNS),
        f"Schema da Silver distrital diverge: {current.columns}",
    )
    existing = current.select(*OUTPUT_COLUMNS).toPandas()
    require(
        len(existing) == len(proposed),
        f"Quantidade divergente: atual={len(existing)}, nova={len(proposed)}",
    )

    expected = row_multiset(existing)
    calculated = row_multiset(proposed)
    missing = expected - calculated
    unexpected = calculated - expected

    differing_old = sum(missing.values())
    differing_new = sum(unexpected.values())

    emit(
        "ROWSET_COMPARISON",
        target_version=target_version,
        rows_existing=len(existing),
        rows_reproduced=len(proposed),
        old_rows_without_match=differing_old,
        new_rows_without_match=differing_new,
    )
    require(
        differing_old == 0 and differing_new == 0,
        "A Silver SSP nao e identica registro a registro; publicacao bloqueada",
    )
    emit("SSP_ROWSET_MATCH", rows=len(proposed), all_eight_columns=True)


def run_check():
    """Executa as validacoes com dados reais, somente leitura."""
    try:
        import geopandas as gpd
        import numpy as np
        import pandas as pd
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "Dependencia ausente no ambiente Databricks. "
            "Instale geopandas==1.1.1 (e dependencias) no ambiente "
            "antes de usar --check."
        ) from exc

    spark = SparkSession.builder.getOrCreate()

    source_version = delta_version(spark, SOURCE)
    target_version = delta_version(spark, TARGET)
    ibge_version = delta_version(spark, DISTRICT_REFERENCE)
    shape_sha = hash_shapefile()

    emit(
        "INPUT_SNAPSHOTS",
        source_version=source_version,
        target_version=target_version,
        ibge_version=ibge_version,
        shapefile_sha256=shape_sha,
    )

    districts = load_districts(gpd, spark, ibge_version)
    source_pdf = load_source(spark, source_version)
    proposed = build_spatial_result(gpd, pd, np, source_pdf, districts)
    compare_target(spark, pd, proposed, target_version)

    # Detectar alteracoes concorrentes; o resultado foi calculado sobre
    # versoes fixas, mas a verificacao da Silver atual exige atualidade.
    require(
        delta_version(spark, SOURCE) == source_version,
        "Origem SSP mudou durante a validacao",
    )
    require(
        delta_version(spark, TARGET) == target_version,
        "Silver SSP distrital mudou durante a validacao",
    )
    require(
        delta_version(spark, DISTRICT_REFERENCE) == ibge_version,
        "Silver IBGE mudou durante a validacao",
    )
    require(hash_shapefile() == shape_sha, "Malha SHP mudou durante a validacao")

    emit(
        "SSP_SPATIAL_CHECK_SUCCESS",
        changed_tables=False,
        changed_files=False,
        source_version=source_version,
        target_version=target_version,
        rows=len(proposed),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Reproduz e compara a Silver SSP usando Spark (somente leitura)",
    )
    args = parser.parse_args()
    verify_contract()
    if args.check:
        run_check()


if __name__ == "__main__":
    main()
