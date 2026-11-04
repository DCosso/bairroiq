"""BairroIQ | Gold Distritos Wide v4 | Georreferenciamento distrital.

Reutiliza a logica de indicadores da v3, sem copiar nem modificar suas regras,
e adiciona latitude/longitude de centroides oficiais versionados no Git.

ARQUIVOS OBRIGATORIOS NA MESMA PASTA:
    gold_distritos_wide_runner.py        (v3, nucleo de indicadores)
    gold_distritos_geo.py                (validacao geoespacial)
    distritos_centroides_ibge_2022.json  (96 centroides IBGE)

EXECUCAO:
    python gold_distritos_wide_v4_runner.py --check
    python gold_distritos_wide_v4_runner.py --migrate-coordinates --confirm-publish
    python gold_distritos_wide_v4_runner.py --update --confirm-publish
    python gold_distritos_wide_v4_runner.py --apply --confirm-publish

CHECK nunca escreve. MIGRATE e a unica opcao permitida para ampliar a Gold
existente de 252 para 254 colunas; preserva 252 campos e seus comentarios.
A evolucao de schema e o MERGE sao duas transacoes Delta distintas; se a
segunda falhar, o modo MIGRATE e reexecutavel apos diagnostico.
"""

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent
CORE_FILE = BASE_DIR / "gold_distritos_wide_runner.py"
GEO_FILE = BASE_DIR / "gold_distritos_geo.py"
GEO_REFERENCE = BASE_DIR / "distritos_centroides_ibge_2022.json"

TARGET = "workspace.gold.distritos_wide"
EXPECTED_DISTRICTS = 96
LEGACY_COLUMNS = 252
GEO_COLUMNS = ("latitude", "longitude")
NEW_COLUMNS = LEGACY_COLUMNS + len(GEO_COLUMNS)

COLUMN_COMMENTS = {
    "latitude": (
        "Latitude WGS84 EPSG:4326 do centroide do poligono oficial "
        "IBGE 2022 do distrito; calculada em EPSG:31983. "
        "Ponto representativo, nao endereco ou concentracao populacional."
    ),
    "longitude": (
        "Longitude WGS84 EPSG:4326 do centroide do poligono oficial "
        "IBGE 2022 do distrito; calculada em EPSG:31983. "
        "Ponto representativo, nao endereco ou concentracao populacional."
    ),
}


class MigrationError(RuntimeError):
    """Estado inconsistente, operacao bloqueada antes de gravar."""


def require(condition, message):
    if not condition:
        raise MigrationError(message)


def emit(event, **details):
    print(json.dumps({"event": event, **details}, ensure_ascii=False,
                     sort_keys=True, default=str), flush=True)


def load_module(name, location):
    require(location.is_file(), f"Arquivo obrigatorio nao encontrado: {location}")
    spec = importlib.util.spec_from_file_location(name, str(location))
    require(spec is not None and spec.loader is not None,
            f"Nao foi possivel carregar {location}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_dependencies():
    """Carrega os dois modulos contiguos (nao depende de PYTHONPATH)."""
    core = load_module("bairroiq_gold_v3_core", CORE_FILE)
    geo = load_module("bairroiq_district_geo", GEO_FILE)
    require(core.TARGET == TARGET, "Destino diferente no runner v3")
    require(core.EXPECTED_DISTRICTS == EXPECTED_DISTRICTS,
            "Granularidade diferente no runner v3")
    require(geo.EXPECTED_TABLE == TARGET and geo.GEO_COLUMNS == GEO_COLUMNS,
            "Contrato diferente no modulo geografico")
    return core, geo


def identical_rows(left, right):
    """Compara linhas e multiplicidades; exige schema e contagem iguais."""
    require(len(left.columns) == len(right.columns), "Colunas diferentes")
    require(left.columns == right.columns, "Ordem dos campos diferente")
    if left.count() != right.count():
        return False
    return (left.exceptAll(right).limit(1).count() == 0
            and right.exceptAll(left).limit(1).count() == 0)


def classify_target(spark, core, base, proposed):
    """Identifica estado sem mutar dados; rejeita qualquer deriva historica."""
    if not spark.catalog.tableExists(TARGET):
        return {"state": "ABSENT", "identical": False, "schema_equal": False}

    current = spark.table(TARGET)
    require(len(current.columns) in (LEGACY_COLUMNS, NEW_COLUMNS),
            f"Gold com quantidade inesperada de colunas: {len(current.columns)}")

    if len(current.columns) == LEGACY_COLUMNS:
        require(core.same_schema(current, base),
                "Schema legado da Gold difere do runner v3")
        core.assert_exact_codes(base, current)
        legacy_equal = identical_rows(current, base)
        return {"state": "LEGACY_IDENTICAL" if legacy_equal else "LEGACY_STALE",
                "identical": False, "schema_equal": False}

    require(core.same_schema(current, proposed),
            "Schema de 254 colunas difere da proposta v4")
    current_legacy = current.select(*base.columns)
    core.assert_exact_codes(base, current_legacy)
    legacy_equal = identical_rows(current_legacy, base)
    equal = legacy_equal and identical_rows(current, proposed)
    state = (
        "GEO_IDENTICAL" if equal else
        "GEO_INCOMPLETE" if legacy_equal else
        "GEO_STALE"
    )
    return {"state": state, "identical": equal, "schema_equal": True}


def metadata_snapshot(spark, original_columns):
    """Audita comentarios e propriedades publicadas, sem usar refreshTable."""
    row = spark.sql(f"DESCRIBE TABLE EXTENDED {TARGET} AS JSON").first()
    require(row is not None, "Metadados da Gold indisponiveis")
    raw = row[0]
    document = json.loads(raw) if isinstance(raw, str) else raw
    require(isinstance(document, dict), "Metadados AS JSON invalidos")

    columns = document.get("columns")
    require(isinstance(columns, list), "DESCRIBE nao retornou colunas")
    by_name = {c.get("name"): c for c in columns if isinstance(c, dict)}
    require(all(col in by_name for col in original_columns),
            "Metadados das 252 colunas originais indisponiveis")
    comments = {col: (by_name[col].get("comment") or "")
                for col in original_columns}
    require(all(comments.values()),
            "Existem colunas originais sem comentario publicado")

    properties = {}
    for item in spark.sql(f"SHOW TBLPROPERTIES {TARGET}").collect():
        key, value = str(item[0]), str(item[1])
        require(key not in properties, f"Propriedade duplicada: {key}")
        properties[key] = value

    return {"comments": comments,
            "table_comment": document.get("comment") or "",
            "properties": properties}


def ensure_metadata_preserved(spark, columns, before):
    after = metadata_snapshot(spark, columns)
    require(after == before,
            "Metadados anteriores mudaram; inspecione a Gold antes de prosseguir")


def ensure_new_column_comments(spark):
    row = spark.sql(f"DESCRIBE TABLE EXTENDED {TARGET} AS JSON").first()
    require(row is not None, "Metadados nao disponiveis")
    doc = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    by_name = {entry["name"]: entry for entry in doc.get("columns", [])}
    for name, expected in COLUMN_COMMENTS.items():
        require(by_name.get(name, {}).get("comment") == expected,
                f"Comentario da coluna {name} ausente ou divergente")


def sources_unchanged(spark, core, versions):
    require(core.source_versions_unchanged(spark, versions),
            "Fonte Silver mudou durante a validacao; operacao interrompida")


def coordinates_reference_unchanged(geo, initial_sha):
    _, sha = geo.load_centroids(GEO_REFERENCE)
    require(sha == initial_sha, "JSON de centroides mudou durante a execucao")


def merge_coordinates(spark, core, proposed):
    """Atualiza somente duas colunas; nao insere nem exclui distritos."""
    temp_view = "bairroiq_geo_merge_" + uuid4().hex
    proposed.select("CD_DIST", *GEO_COLUMNS).createOrReplaceTempView(temp_view)
    try:
        spark.sql(f"""
            MERGE INTO {TARGET} AS t
            USING {temp_view} AS s
            ON t.CD_DIST = s.CD_DIST
            WHEN MATCHED THEN UPDATE SET
                t.latitude = s.latitude,
                t.longitude = s.longitude
        """).collect()
    finally:
        spark.catalog.dropTempView(temp_view)


def migrate_coordinates(spark, core, geo, base, proposed,
                        versions, geo_sha, state):
    """Migra v3 para v4, mantendo colunas/comentarios e sem recriar tabela."""
    require(state["state"] in (
        "LEGACY_IDENTICAL", "GEO_INCOMPLETE", "GEO_IDENTICAL"
    ), "Migracao exige que os 252 campos originais correspondam "
       "integralmente as fontes Silver e que o schema seja valido")

    if state["state"] == "GEO_IDENTICAL":
        emit("GOLD_COORDINATES_UNCHANGED", changed_tables=False,
             target_identical=True)
        return

    original_columns = list(base.columns)
    before = metadata_snapshot(spark, original_columns)
    initial_version = core.delta_version(spark, TARGET)

    sources_unchanged(spark, core, versions)
    coordinates_reference_unchanged(geo, geo_sha)
    require(core.delta_version(spark, TARGET) == initial_version,
            "Tabela Gold mudou depois do diagnostico")

    if state["state"] == "LEGACY_IDENTICAL":
        # Apenas DDL aditiva, em uma unica transacao Delta de metadados.
        # Nao altera os tipos nem os comentarios das 252 colunas antigas.
        ddl = ", ".join(
            f"{name} DOUBLE COMMENT '{COLUMN_COMMENTS[name]}'"
            for name in GEO_COLUMNS
        )
        spark.sql(f"ALTER TABLE {TARGET} ADD COLUMNS ({ddl})").collect()

        require(core.same_schema(spark.table(TARGET), proposed),
                "Schema apos ADD COLUMNS diverge de 254 campos")
        ensure_metadata_preserved(spark, original_columns, before)
        ensure_new_column_comments(spark)
        emit("GOLD_COORDINATES_COLUMNS_ADDED", previous=LEGACY_COLUMNS,
             current=NEW_COLUMNS, changed_tables=True)

    # Se o DDL passou e o MERGE nao, uma segunda execucao volta por aqui.
    sources_unchanged(spark, core, versions)
    coordinates_reference_unchanged(geo, geo_sha)
    require(core.same_schema(spark.table(TARGET), proposed),
            "Schema mudou antes do MERGE geoespacial")
    ensure_metadata_preserved(spark, original_columns, before)
    ensure_new_column_comments(spark)

    # Validacao da parte historica novamente antes da DML.
    current_legacy = spark.table(TARGET).select(*original_columns)
    require(identical_rows(current_legacy, base),
            "Campos anteriores divergem antes do MERGE")

    before_merge = core.delta_version(spark, TARGET)
    merge_coordinates(spark, core, proposed)
    after_merge = core.delta_version(spark, TARGET)

    require(after_merge > before_merge,
            "MERGE geoespacial nao gerou nova versao Delta")
    require(core.target_status(spark, proposed)["identical"],
            "Gold nao ficou identica apos MERGE; verificar historico Delta")
    ensure_metadata_preserved(spark, original_columns, before)
    ensure_new_column_comments(spark)
    require(identical_rows(spark.table(TARGET).select(*original_columns), base),
            "MERGE modificou campos antigos inesperadamente")

    emit("GOLD_COORDINATES_MIGRATION_SUCCESS",
         target=TARGET, districts=EXPECTED_DISTRICTS, columns=NEW_COLUMNS,
         version_before=initial_version, version_after=after_merge,
         old_columns_preserved=True, old_comments_preserved=True,
         target_identical=True)


def apply_initial(spark, core, geo, proposed, versions, geo_sha):
    """CTAS para primeiro deploy quando nao existe uma Gold anterior."""
    require(not spark.catalog.tableExists(TARGET),
            "Gold ja existe; --apply nao sobrescreve dados")
    sources_unchanged(spark, core, versions)
    coordinates_reference_unchanged(geo, geo_sha)

    temp_view = "bairroiq_gold_v4_apply_" + uuid4().hex
    proposed.createOrReplaceTempView(temp_view)
    try:
        spark.sql(f"CREATE TABLE IF NOT EXISTS {TARGET} USING DELTA "
                  f"AS SELECT * FROM {temp_view}").collect()
    finally:
        spark.catalog.dropTempView(temp_view)

    # CTAS nao transfere comentarios da tabela; os dois novos sao publicados.
    for column, comment in COLUMN_COMMENTS.items():
        spark.sql(f"ALTER TABLE {TARGET} ALTER COLUMN {column} "
                  f"COMMENT '{comment}'").collect()

    require(core.target_status(spark, proposed)["identical"],
            "Gold v4 criada, mas nao corresponde ao snapshot")
    ensure_new_column_comments(spark)
    emit("GOLD_DISTRICTS_V4_APPLY_SUCCESS", columns=NEW_COLUMNS,
         districts=EXPECTED_DISTRICTS)


def execute(spark, apply=False, update=False, migrate_coordinates_mode=False):
    """Orquestra a v4; --check e sempre somente leitura."""
    modes = sum(bool(x) for x in (apply, update, migrate_coordinates_mode))
    require(modes <= 1, "Escolha uma unica modalidade de publicacao")

    core, geo = load_dependencies()
    require(GEO_REFERENCE.is_file(),
            f"JSON de centroides ausente: {GEO_REFERENCE}")
    _, geo_sha = geo.load_centroids(GEO_REFERENCE)

    sources = (core.IBGE, core.GEO, core.OBS, core.SSP,
               core.IMOVEIS, core.DEPARA)
    for table in sources:
        require(spark.catalog.tableExists(table), f"Fonte ausente: {table}")
    versions = {table: core.delta_version(spark, table) for table in sources}

    base, summary = core.build(spark, versions)
    require(len(base.columns) == LEGACY_COLUMNS,
            f"Runner v3 retornou {len(base.columns)}, esperado 252")
    proposed, geo_report = geo.attach_coordinates(spark, base, GEO_REFERENCE)
    require(len(proposed.columns) == NEW_COLUMNS,
            "Gold v4 nao possui exatamente 254 colunas")
    require(proposed.columns[-2:] == list(GEO_COLUMNS),
            "Ordem de latitude e longitude inesperada")
    require(proposed.count() == EXPECTED_DISTRICTS,
            "Gold v4 nao possui 96 distritos")

    status = classify_target(spark, core, base, proposed)
    sources_unchanged(spark, core, versions)
    coordinates_reference_unchanged(geo, geo_sha)

    emit("GOLD_DISTRICTS_V4_VALIDATED", districts=EXPECTED_DISTRICTS,
         columns=NEW_COLUMNS, coordinates=geo_report,
         target_status=status, imoveis=summary["imoveis"])

    if modes == 0:
        emit("GOLD_DISTRICTS_CHECK_SUCCESS", changed_tables=False,
             changed_files=False, target_identical=status["identical"],
             migration_required=status["state"] in (
                 "LEGACY_IDENTICAL", "LEGACY_STALE", "GEO_INCOMPLETE"),
             update_required=status["state"] == "GEO_STALE")
        return {"summary": summary, "coordinates": geo_report,
                "target_status": status}

    if migrate_coordinates_mode:
        migrate_coordinates(spark, core, geo, base, proposed,
                            versions, geo_sha, status)
    elif update:
        require(status["state"] in (
                    "GEO_IDENTICAL", "GEO_INCOMPLETE", "GEO_STALE"),
                "--update exige Gold v4 com 254 colunas; "
                "use --migrate-coordinates para migrar da v3")
        if status["identical"]:
            emit("GOLD_DISTRICTS_UNCHANGED", changed_tables=False)
        else:
            core.update_target(spark, proposed, versions)
    else:
        require(status["state"] == "ABSENT",
                "--apply exige que a Gold nao exista")
        apply_initial(spark, core, geo, proposed, versions, geo_sha)

    return {"summary": summary, "coordinates": geo_report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true",
                       help="Validar sem modificar dados nem metadados")
    modes.add_argument("--migrate-coordinates", action="store_true",
                       help="Evoluir Gold existente de 252 para 254 campos")
    modes.add_argument("--update", action="store_true",
                       help="Atualizar Gold v4 com 254 colunas")
    modes.add_argument("--apply", action="store_true",
                       help="Criar Gold inexistente")
    parser.add_argument("--confirm-publish", action="store_true",
                        help="Confirmacao explicita para DDL/DML")
    args = parser.parse_args(argv)
    publishing = args.apply or args.update or args.migrate_coordinates
    if publishing != args.confirm_publish:
        parser.error("Operacoes de escrita exigem --confirm-publish; "
                     "--check nao aceita essa confirmacao")

    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    execute(spark, apply=args.apply, update=args.update,
            migrate_coordinates_mode=args.migrate_coordinates)


if __name__ == "__main__":
    main()
