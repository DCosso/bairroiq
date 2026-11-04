"""BairroIQ | Job de validacao estrita da Gold Distritos Wide v4.

Executa apenas --check. Reconstroi a Gold v4 atraves do runner oficial,
exige identidade completa entre fonte e destino, confere os centroides e
os comentarios no Unity Catalog e falha com exit code != 0 em divergencia.

Nenhum dado, arquivo ou metadado e modificado.

Uso:
    python gold_distritos_wide_v4_strict_check.py --check
"""

import argparse
import importlib.util
from pathlib import Path

RUNNER_FILE = Path(__file__).resolve().with_name(
    "gold_distritos_wide_v4_runner.py"
)
TARGET = "workspace.gold.distritos_wide"
EXPECTED_DISTRICTS = 96
EXPECTED_COLUMNS = 254
EXPECTED_LEGACY_COLUMNS = 252


def require(condition, message):
    if not condition:
        raise RuntimeError(f"BAIRROIQ_GOLD_V4_STRICT_CHECK_FAILED: {message}")


def load_runner():
    require(RUNNER_FILE.is_file(), f"Runner v4 ausente: {RUNNER_FILE}")
    spec = importlib.util.spec_from_file_location(
        "bairroiq_gold_v4_strict_job", str(RUNNER_FILE)
    )
    require(spec is not None and spec.loader is not None,
            "Nao foi possivel carregar runner v4")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.TARGET == TARGET, "Destino do runner diferente")
    return module


def execute(spark):
    runner = load_runner()
    result = runner.execute(
        spark,
        apply=False,
        update=False,
        migrate_coordinates_mode=False,
    )

    status = result["target_status"]
    coordinates = result["coordinates"]
    summary = result["summary"]
    require(status.get("state") == "GEO_IDENTICAL",
            f"Gold nao homologada: {status}")
    require(status.get("identical") is True,
            "Gold difere da reconstrucao v4")
    require(status.get("schema_equal") is True,
            "Schema da Gold difere da reconstrucao")
    require(summary.get("colunas_totais") == EXPECTED_LEGACY_COLUMNS,
            "Nucleo legado nao possui 252 colunas")
    require(coordinates.get("distritos_geolocalizados") == EXPECTED_DISTRICTS,
            "Cobertura geoespacial incompleta")
    require(coordinates.get("metodo") == "CENTROIDE",
            "Metodo geoespacial inesperado")
    require(coordinates.get("crs") == "EPSG:4326",
            "CRS geoespacial inesperado")

    gold = spark.table(TARGET)
    require(gold.count() == EXPECTED_DISTRICTS,
            "Gold nao possui 96 distritos")
    require(len(gold.columns) == EXPECTED_COLUMNS,
            "Gold nao possui 254 colunas")
    require(gold.columns[-2:] == ["latitude", "longitude"],
            "Ordem dos campos de coordenadas incorreta")
    for col in ("latitude", "longitude"):
        require(gold.schema[col].dataType.simpleString() == "double",
                f"Campo {col} nao e DOUBLE")

    from pyspark.sql import functions as F
    require(gold.select("CD_DIST").distinct().count() == EXPECTED_DISTRICTS,
            "CD_DIST nao e unico")
    require(gold.filter(
        F.col("CD_DIST").isNull()
        | F.col("latitude").isNull()
        | F.col("longitude").isNull()
        | F.isnan("latitude")
        | F.isnan("longitude")
        | ~F.col("latitude").between(-24.0, -23.0)
        | ~F.col("longitude").between(-47.0, -46.0)
    ).limit(1).count() == 0, "Coordenadas nulas ou fora da faixa")

    prior_metadata = runner.metadata_snapshot(
        spark, gold.columns[:EXPECTED_LEGACY_COLUMNS]
    )
    require(bool(prior_metadata["table_comment"]),
            "Comentario da tabela ausente")
    runner.ensure_new_column_comments(spark)

    print("=" * 68)
    print("BAIRROIQ | GOLD V4 | CHECK ESTRITO APROVADO")
    print("=" * 68)
    print("Estado: GEO_IDENTICAL")
    print("Distritos: 96/96")
    print("Colunas: 254/254")
    print("Centroides: 96/96")
    print("Schema e dados: IDENTICOS")
    print("Metadados: VALIDADOS")
    print("Alteracoes realizadas: NENHUMA")
    print("BAIRROIQ_GOLD_V4_STRICT_CHECK_SUCCESS")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True,
                        help="Executar somente leitura com falha em divergencias")
    args = parser.parse_args(argv)
    require(args.check, "Use exclusivamente --check")
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    execute(spark)


if __name__ == "__main__":
    main()
