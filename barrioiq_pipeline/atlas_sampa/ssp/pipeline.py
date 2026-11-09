"""Atlas Sampa | SSP-SP monthly Lambda pilot (independent read-model).

--check: HTTP HEAD only; no writes.
--run: ingest versioned source, guarded Bronze V2, 96-district Silver,
       Batch + Speed diff and reconciled Serving; publish pointer last.

Does not update historical BairroIQ Bronze/Silver/Gold or frontend.
The output is a private demonstration read-model, not a production crime feed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time, timezone
import hashlib
import json
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo

# Databricks Bundle syncs this folder as a self-contained bundle. Provide the
# package context that the already-versioned collector uses for relative imports.
HERE = Path(__file__).resolve().parent
if "atlas_sampa.ssp" not in sys.modules:
    parent = sys.modules.setdefault("atlas_sampa", types.ModuleType("atlas_sampa"))
    parent.__path__ = [str(HERE.parent)]
    child = types.ModuleType("atlas_sampa.ssp")
    child.__path__ = [str(HERE)]
    sys.modules["atlas_sampa.ssp"] = child

from atlas_sampa.ssp.collector import (  # noqa: E402
    RAW_DEFAULT, apply_collection, check_remote, save_version, _file_sha256,
)
from atlas_sampa.ssp.excel_reader import HEADERS, validate_excel  # noqa: E402

RAW = RAW_DEFAULT
LEGACY_FILE = RAW / "SPDadosCriminais_2026.xlsx"
SHP = Path("/Volumes/workspace/bronze/raw/ibge/malha_distritos_2022/shapefile/SP_distritos_CD2022.shp")
BRONZE = "workspace.bronze.ssp_ingestao_v2"
BRONZE_STAGE = "workspace.bronze.atlas_sampa_ssp_stage_v2"
SILVER = "workspace.silver.atlas_sampa_ssp_v2"
BATCH = "workspace.observability.atlas_sampa_ssp_batch_v1"
SPEED = "workspace.observability.atlas_sampa_ssp_speed_v1"
SERVING = "workspace.observability.atlas_sampa_ssp_serving_v1"
CONTROL = "workspace.observability.atlas_sampa_ssp_publication_v1"
LOTE = 20000
RUBRICAS = {"Furto (art. 155)": "FURTO", "Roubo (art. 157)": "ROUBO"}


def emit(event: str, **details) -> None:
    # Never log BO identifiers, addresses or row-level information.
    print(json.dumps({"event": event, **details}, ensure_ascii=False, default=str, sort_keys=True), flush=True)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def normalized_cell(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    return str(value)


def source_ident(sheet: str, row_number: int):
    return sheet, int(row_number)


def difference_counts(previous: Counter, current: Counter) -> tuple[Counter, Counter]:
    """Multiset diff: handles duplicate rows and corrections without BO key guesses."""
    added = current - previous
    removed = previous - current
    return added, removed


def validate_bronze_contract(spark):
    require(spark.catalog.tableExists(BRONZE), f"Bronze paralela inexistente: {BRONZE}")
    schema = spark.table(BRONZE).schema
    cols = [f.name for f in schema]
    metadata = {"_rescued_data", "source_sha256", "source_sheet", "source_row", "ingested_at_utc"}
    originals = [c for c in cols if c not in metadata]
    require(len(cols) == 35 and len(originals) == 30, "Bronze V2 exige 35 campos, com 30 originais")
    require(tuple(c.replace("_", " ") if c == "COD_IBGE" else c for c in originals) == HEADERS,
            "Ordem de colunas da Bronze V2 difere do Excel")
    for name in originals + ["_rescued_data", "source_sha256", "source_sheet"]:
        require(schema[name].dataType.simpleString() == "string", f"Campo nao STRING: {name}")
    require(schema["source_row"].dataType.simpleString() in ("bigint", "long"), "source_row nao BIGINT")
    require(schema["ingested_at_utc"].dataType.simpleString() == "timestamp", "ingested_at_utc nao TIMESTAMP")
    return schema, cols, originals


def _existing_rows(spark, table: str, sha: str) -> int:
    from pyspark.sql import functions as F
    if not spark.catalog.tableExists(table):
        return 0
    return spark.table(table).filter(F.col("source_sha256") == sha).count()


def stage_bronze(spark, year: int, sha: str, filename: Path, expected_rows: int) -> None:
    """Reads XLSX in bounded Python batches. Only stages the requested version."""
    from openpyxl import load_workbook
    from pyspark.sql import functions as F
    schema, cols, originals = validate_bronze_contract(spark)
    already = _existing_rows(spark, BRONZE, sha)
    if already:
        require(already == expected_rows, "Bronze possui snapshot parcial: requer correcao manual")
        df = spark.table(BRONZE).filter(F.col("source_sha256") == sha)
        distinct = df.select("source_sheet", "source_row").distinct().count()
        require(distinct == already, "Bronze: chaves de origem repetidas")
        emit("BRONZE_REUSED", sha256=sha, rows=already)
        return

    wb = load_workbook(str(filename), read_only=True, data_only=True)
    total, first = 0, True
    ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        for sheet in (f"JAN-JUN_{year}", f"JUL-DEZ_{year}"):
            if sheet not in wb.sheetnames:
                emit("EXCEL_SHEET_NOT_PUBLISHED", sheet=sheet)
                continue
            ws = wb[sheet]
            header = tuple(next(ws.iter_rows(min_row=1, max_row=1, max_col=30, values_only=True)))
            require(header == HEADERS, f"Cabecalho alterado: {sheet}")
            buffer, count = [], 0
            for row_number, fields in enumerate(ws.iter_rows(min_row=2, max_col=30, values_only=True), start=2):
                if all(value is None or (isinstance(value, str) and not value.strip()) for value in fields):
                    continue
                record = dict(zip(originals, (normalized_cell(value) for value in fields)))
                record.update({"_rescued_data": None, "source_sha256": sha,
                               "source_sheet": sheet, "source_row": row_number,
                               "ingested_at_utc": ingested_at})
                buffer.append(tuple(record[col] for col in cols))
                if len(buffer) >= LOTE:
                    frame = spark.createDataFrame(buffer, schema=schema)
                    frame.write.format("delta").mode("overwrite" if first else "append").saveAsTable(BRONZE_STAGE)
                    first = False
                    count += len(buffer)
                    buffer.clear()
            if buffer:
                frame = spark.createDataFrame(buffer, schema=schema)
                frame.write.format("delta").mode("overwrite" if first else "append").saveAsTable(BRONZE_STAGE)
                first = False
                count += len(buffer)
            total += count
            emit("EXCEL_SHEET_STAGED", sheet=sheet, rows=count)
    finally:
        wb.close()
    require(total == expected_rows, f"Excel conteve {total} registros, esperados {expected_rows}")
    stage = spark.table(BRONZE_STAGE)
    require(stage.count() == expected_rows, "Stage: contagem diverge")
    require(stage.select("source_sheet", "source_row").distinct().count() == expected_rows, "Stage duplicou linha")
    require(stage.filter(F.col("source_sha256") != sha).limit(1).count() == 0, "Stage hash divergente")
    require(stage.filter(F.col("RUBRICA").isNull() | (F.trim("RUBRICA") == "")).limit(1).count() == 0,
            "Stage com RUBRICA ausente: bloquear publicacao")
    # The source hash is version identity, not a row identity. This MERGE is
    # idempotent WITHIN a version; Silver/Speed handle changes BETWEEN versions.
    spark.sql(f"""MERGE INTO {BRONZE} AS t USING {BRONZE_STAGE} AS s
        ON t.source_sha256 = s.source_sha256
        AND t.source_sheet = s.source_sheet AND t.source_row = s.source_row
        WHEN NOT MATCHED THEN INSERT *""")
    require(_existing_rows(spark, BRONZE, sha) == expected_rows, "Bronze merge incompleto")
    emit("BRONZE_VERSION_VALIDATED", sha256=sha, rows=expected_rows)


def districts_shape():
    import geopandas as gpd
    shp = gpd.read_file(SHP)
    require(shp.crs is not None, "Malha sem CRS")
    needed = {"CD_MUN", "CD_DIST", "NM_DIST", "geometry"}
    require(needed.issubset(shp.columns), "Malha distrital com contrato inesperado")
    result = shp[shp["CD_MUN"].astype(str).str.strip() == "3550308"].copy()
    result["CD_DIST"] = result["CD_DIST"].astype(str).str.strip()
    result["NM_DIST"] = result["NM_DIST"].astype(str).str.strip()
    require(len(result) == 96 and result["CD_DIST"].nunique() == 96, "Malha sem 96 distritos")
    require(result.geometry.notna().all() and result.geometry.is_valid.all(), "Geometria distrital invalida")
    result = result.to_crs("EPSG:4674")
    return result[["CD_DIST", "NM_DIST", "geometry"]]


def derive_silver(spark, sha: str, year: int, districts) -> None:
    """Maps SSP city robberies/thefts to the same 96 official districts, in chunks."""
    from pyspark.sql import functions as F, types as T
    import geopandas as gpd
    import pandas as pd

    bronze = spark.table(BRONZE).filter(F.col("source_sha256") == sha)
    originals = [c for c in bronze.columns if c not in
                 {"_rescued_data", "source_sha256", "source_sheet", "source_row", "ingested_at_utc"}]
    fingerprint = F.sha2(F.to_json(F.array(*[F.col(c) for c in originals])), 256)
    relevant = (
        bronze.filter((F.trim("COD_IBGE") == "3550308") & F.col("RUBRICA").isin(*RUBRICAS))
        .select(
            "source_sheet", "source_row", fingerprint.alias("record_sha256"),
            F.col("RUBRICA"),
            F.expr("try_cast(LATITUDE as double)").alias("latitude_num"),
            F.expr("try_cast(LONGITUDE as double)").alias("longitude_num"),
            F.expr("try_cast(ANO_ESTATISTICA as int)").alias("ano"),
            F.expr("try_cast(MES_ESTATISTICA as int)").alias("mes"),
        )
        .filter(
            (F.col("ano") == year) & F.col("mes").between(1, 12)
            & F.col("latitude_num").between(-90.0, 90.0)
            & F.col("longitude_num").between(-180.0, 180.0)
            & ~((F.col("latitude_num") == 0) & (F.col("longitude_num") == 0))
        )
    )
    source_rows = relevant.count()
    require(source_rows > 0, "Nao ha registros SSP georreferenciaveis para o municipio")
    existing = _existing_rows(spark, SILVER, sha)
    if existing:
        require(existing == source_rows, "Silver parcial: existem linhas faltantes, bloquear reprocessamento")
        saved = spark.table(SILVER).filter(F.col("source_sha256") == sha)
        require(saved.select("source_sheet", "source_row").distinct().count() == source_rows,
                "Silver com chave repetida: bloquear reprocessamento")
        require(saved.filter(F.col("CD_DIST").isNotNull()).select("CD_DIST").distinct().count() == 96,
                "Silver incompleta em cobertura distrital")
        emit("SILVER_VERSION_REUSED", sha256=sha, rows=source_rows)
        return

    schema = T.StructType([
        T.StructField("source_sha256", T.StringType(), False),
        T.StructField("record_sha256", T.StringType(), False),
        T.StructField("source_sheet", T.StringType(), False),
        T.StructField("source_row", T.LongType(), False),
        T.StructField("ano", T.IntegerType(), False),
        T.StructField("mes", T.IntegerType(), False),
        T.StructField("tipo", T.StringType(), False),
        T.StructField("CD_DIST", T.LongType(), True),
        T.StructField("NM_DIST", T.StringType(), True),
    ])
    buf, inserted = [], 0
    # The actual driver-side spatial join is bounded by chunk size. Never
    # collect the entire statewide publication into Python memory.
    def flush(rows):
        nonlocal inserted
        if not rows:
            return
        pdf = pd.DataFrame(rows, columns=["source_sheet", "source_row", "record_sha256",
                                           "RUBRICA", "latitude_num", "longitude_num", "ano", "mes"])
        pts = gpd.GeoDataFrame(pdf, geometry=gpd.points_from_xy(pdf.longitude_num, pdf.latitude_num), crs="EPSG:4674")
        joined = gpd.sjoin(pts, districts, how="left", predicate="within")
        require(len(joined) == len(pdf), "Spatial join duplicou ocorrencias: abortar")
        output = []
        for row in joined.to_dict("records"):
            code = row.get("CD_DIST")
            name = row.get("NM_DIST")
            output.append((
                sha, str(row["record_sha256"]), str(row["source_sheet"]), int(row["source_row"]),
                int(row["ano"]), int(row["mes"]), RUBRICAS[str(row["RUBRICA"])],
                int(code) if pd.notna(code) else None,
                str(name) if pd.notna(name) else None,
            ))
        df = spark.createDataFrame(output, schema=schema)
        df.write.format("delta").mode("append" if spark.catalog.tableExists(SILVER) else "overwrite").saveAsTable(SILVER)
        inserted += len(output)

    for item in relevant.toLocalIterator():
        buf.append((item["source_sheet"], item["source_row"], item["record_sha256"], item["RUBRICA"],
                    item["latitude_num"], item["longitude_num"], item["ano"], item["mes"]))
        if len(buf) >= 10000:
            flush(buf)
            buf.clear()
    flush(buf)
    require(inserted == source_rows, "Silver: cardinalidade apos georreferenciamento difere")
    df = spark.table(SILVER).filter(F.col("source_sha256") == sha)
    require(df.count() == source_rows, "Silver: cardinalidade fisica difere")
    require(df.select("source_sheet", "source_row").distinct().count() == source_rows,
            "Silver duplicou chave da linha de origem")
    matched = df.filter(F.col("CD_DIST").isNotNull()).count()
    districts_count = df.filter(F.col("CD_DIST").isNotNull()).select("CD_DIST").distinct().count()
    require(districts_count == 96, "Silver nao encontrou ocorrencias nos 96 distritos")
    emit("SILVER_VERSION_VALIDATED", sha256=sha, candidates=source_rows, assigned=matched,
         not_assigned=source_rows - matched, districts=districts_count)


def monthly_batch(spark, sha: str, districts):
    from pyspark.sql import functions as F
    silver = spark.table(SILVER).filter(F.col("source_sha256") == sha)
    matched = silver.filter(F.col("CD_DIST").isNotNull())
    periods = silver.select("ano", "mes").distinct()
    district_info = [(int(row.CD_DIST), str(row.NM_DIST)) for row in districts.itertuples()]
    district_df = spark.createDataFrame(district_info, "CD_DIST LONG, NM_DIST STRING")
    kinds_df = spark.createDataFrame([(t,) for t in RUBRICAS.values()], "tipo STRING")
    domain = periods.crossJoin(district_df).crossJoin(kinds_df)
    actual = matched.groupBy("ano", "mes", "CD_DIST", "tipo").agg(F.count("*").alias("quantidade"))
    batch = (domain.join(actual, ["ano", "mes", "CD_DIST", "tipo"], "left")
             .fillna({"quantidade": 0}).withColumn("source_sha256", F.lit(sha))
             .select("source_sha256", "ano", "mes", "CD_DIST", "NM_DIST", "tipo", "quantidade"))
    count = batch.count()
    require(count == periods.count() * 96 * 2, "Batch incompleto: grade mes x distrito x tipo")
    if _existing_rows(spark, BATCH, sha):
        saved = spark.table(BATCH).filter(F.col("source_sha256") == sha)
        require(saved.count() == count, "Batch preexistente com contagem inesperada")
        diff = saved.select("ano", "mes", "CD_DIST", "tipo", "quantidade").exceptAll(
            batch.select("ano", "mes", "CD_DIST", "tipo", "quantidade"))
        require(diff.limit(1).count() == 0, "Batch preexistente diverge: abortar")
    else:
        batch.write.format("delta").mode("append" if spark.catalog.tableExists(BATCH) else "overwrite").saveAsTable(BATCH)
    return batch


def speed_diff(spark, previous_sha: str | None, current_sha: str):
    """Multiset diff by full-row hash, preserving duplicates and corrections."""
    from pyspark.sql import functions as F
    keys = ["record_sha256", "ano", "mes", "CD_DIST", "tipo"]
    source = spark.table(SILVER).filter(F.col("CD_DIST").isNotNull())
    now = source.filter(F.col("source_sha256") == current_sha).groupBy(*keys).agg(F.count("*").alias("current_n"))
    if previous_sha is None:
        old = now.limit(0).withColumnRenamed("current_n", "previous_n")
    else:
        old = source.filter(F.col("source_sha256") == previous_sha).groupBy(*keys).agg(F.count("*").alias("previous_n"))
    full = now.join(old, keys, "full_outer").fillna({"current_n": 0, "previous_n": 0})
    deltas = (full.withColumn("delta", F.col("current_n") - F.col("previous_n"))
              .withColumn("adicionados", F.greatest(F.col("delta"), F.lit(0)))
              .withColumn("removidos", F.greatest(-F.col("delta"), F.lit(0))))
    group = (deltas.groupBy("ano", "mes", "CD_DIST", "tipo")
             .agg(F.sum("delta").alias("delta"), F.sum("adicionados").alias("adicionados"),
                  F.sum("removidos").alias("removidos"))
             .withColumn("source_sha256", F.lit(current_sha))
             .withColumn("previous_sha256", F.lit(previous_sha).cast("string")))
    return group.select("source_sha256", "previous_sha256", "ano", "mes", "CD_DIST", "tipo",
                        "delta", "adicionados", "removidos")


def reconciled_serving(spark, current_sha: str, previous_sha: str | None, batch, speed):
    from pyspark.sql import functions as F
    keys = ["ano", "mes", "CD_DIST", "tipo"]
    if previous_sha is None:
        old = batch.limit(0).select(*keys, F.col("quantidade").alias("anterior"))
    else:
        old = (spark.table(BATCH).filter(F.col("source_sha256") == previous_sha)
               .select(*keys, F.col("quantidade").alias("anterior")))
    expected = (old.join(speed.select(*keys, "delta"), keys, "full_outer")
                .fillna({"anterior": 0, "delta": 0})
                .withColumn("calculado", F.col("anterior") + F.col("delta")))
    actual = batch.select(*keys, "quantidade")
    diff = (expected.join(actual, keys, "full_outer")
            .fillna({"calculado": 0, "quantidade": 0})
            .filter(F.col("calculado") != F.col("quantidade")))
    require(diff.limit(1).count() == 0, "FALHA: batch anterior + speed != batch atual")
    require(batch.filter(F.col("quantidade") < 0).limit(1).count() == 0, "Batch negativo")
    return batch


def save_snapshot(spark, table: str, sha: str, frame):
    from pyspark.sql import functions as F
    if _existing_rows(spark, table, sha):
        current = spark.table(table).filter(F.col("source_sha256") == sha)
        require(current.count() == frame.count(), f"Tabela parcial ou divergente: {table}")
        cols = frame.columns
        require(current.select(*cols).exceptAll(frame.select(*cols)).limit(1).count() == 0,
                f"Tabela existente diverge: {table}")
        return
    frame.write.format("delta").mode("append" if spark.catalog.tableExists(table) else "overwrite").saveAsTable(table)
    require(_existing_rows(spark, table, sha) == frame.count(), f"Persistencia falhou: {table}")


def control_current(spark, year: int) -> str | None:
    from pyspark.sql import functions as F
    if not spark.catalog.tableExists(CONTROL):
        return None
    rows = spark.table(CONTROL).filter(F.col("ano") == year).select("source_sha256").collect()
    require(len(rows) <= 1, "Controle contem multiplas versoes atuais")
    return rows[0][0] if rows else None


def publish_control(spark, year: int, sha: str) -> None:
    from pyspark.sql import types as T
    schema = T.StructType([
        T.StructField("ano", T.IntegerType(), False),
        T.StructField("source_sha256", T.StringType(), False),
        T.StructField("publicado_em_utc", T.TimestampType(), False),
    ])
    df = spark.createDataFrame([(year, sha, datetime.now(timezone.utc).replace(tzinfo=None))], schema)
    if not spark.catalog.tableExists(CONTROL):
        df.write.format("delta").mode("overwrite").saveAsTable(CONTROL)
    else:
        df.createOrReplaceTempView("atlas_sampa_control_update")
        spark.sql(f"""MERGE INTO {CONTROL} AS t
          USING atlas_sampa_control_update AS s ON t.ano = s.ano
          WHEN MATCHED THEN UPDATE SET t.source_sha256 = s.source_sha256,
             t.publicado_em_utc = s.publicado_em_utc
          WHEN NOT MATCHED THEN INSERT *""")
    require(control_current(spark, year) == sha, "Ponteiro de publicacao nao conferiu")


def process_version(spark, year: int, sha: str, path: Path, expected_rows: int, districts) -> dict:
    previous = control_current(spark, year)
    if previous == sha:
        emit("SNAPSHOT_ALREADY_PUBLISHED", year=year, sha256=sha)
        return {"sha256": sha, "status": "SEM_ALTERACAO"}
    # Fail closed: never overwrite an older publication just because another
    # run started in parallel. Job max_concurrent_runs=1 is mandatory.
    stage_bronze(spark, year, sha, path, expected_rows)
    derive_silver(spark, sha, year, districts)
    batch = monthly_batch(spark, sha, districts)
    speed = speed_diff(spark, previous, sha)
    save_snapshot(spark, SPEED, sha, speed)
    reconciled = reconciled_serving(spark, sha, previous, batch, speed)
    save_snapshot(spark, SERVING, sha, reconciled)
    from pyspark.sql import functions as F
    summary = speed.agg(F.sum("adicionados").alias("added"),
                        F.sum("removidos").alias("removed")).first()
    additions = int(summary["added"] or 0)
    removed = int(summary["removed"] or 0)
    publish_control(spark, year, sha)  # Last write: private serving publication.
    emit("PRIVATE_SERVING_PUBLISHED", year=year, sha256=sha, previous_sha256=previous,
         added_spatial=additions, removed_spatial=removed, serving_rows=reconciled.count(),
         existing_gold_unchanged=True, frontend_unchanged=True)
    return {"status": "PRIVATE_SERVING_PUBLISHED", "sha256": sha,
            "previous_sha256": previous, "added_spatial": additions, "removed_spatial": removed}


def run_pipeline(year: int, bootstrap_legacy: bool = False) -> dict:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    validate_bronze_contract(spark)
    result = apply_collection(year, raw=RAW)
    sha = result["sha256"]
    path = Path(result["arquivo"])
    count = int(result["total_rows"])
    # Reusing same source must NOT skip an incompletely published snapshot.
    current = control_current(spark, year)
    if current == sha:
        emit("UP_TO_DATE", year=year, sha256=sha, published=True)
        return {"status": "UP_TO_DATE", "sha256": sha}
    districts = districts_shape()
    # Optional one-off bootstrap with the preserved October 2026 Excel.
    # This demonstrates the real +82,092 statewide source change, but the
    # serving values are spatially filtered to São Paulo and 2 crime rubrics.
    if bootstrap_legacy and year == 2026 and current is None and LEGACY_FILE.exists():
        old_sha = _file_sha256(LEGACY_FILE)
        if old_sha != sha:
            sheets = validate_excel(LEGACY_FILE, year)
            old = save_version(LEGACY_FILE, RAW, year, old_sha, sheets,
                               {"ETag": None, "Last-Modified": None})
            emit("BOOTSTRAP_LEGACY", sha256=old_sha, rows=sum(sheets.values()))
            process_version(spark, year, old_sha, Path(old["arquivo"]), sum(sheets.values()), districts)
    return process_version(spark, year, sha, path, count, districts)


def main():
    parser = argparse.ArgumentParser(description="Atlas Sampa SSP Lambda monthly")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="HTTP HEAD only: no writes")
    modes.add_argument("--run", action="store_true", help="Run isolated Bronze/Silver/Lambda private serving")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--bootstrap-legacy", action="store_true", help="Once: October-2026 legacy file as baseline")
    args = parser.parse_args()
    now_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))
    # January still checks the previous publication year; February onward
    # targets the current-year file. Missing source is a visible Job failure.
    year = args.year or (now_sp.year - 1 if now_sp.month == 1 else now_sp.year)
    require(2020 <= year <= 2100, "Ano invalido")
    if args.check:
        emit("SOURCE_CHECK", **check_remote(year))
    else:
        emit("RUN_STARTED", year=year, bootstrap_legacy=args.bootstrap_legacy)
        emit("RUN_FINISHED", **run_pipeline(year, bootstrap_legacy=args.bootstrap_legacy))


if __name__ == "__main__":
    main()
