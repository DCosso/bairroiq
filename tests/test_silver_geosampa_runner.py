
"""Testes da Silver GeoSampa; sem Spark real ou acesso a Databricks."""

from copy import deepcopy
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
import sys

from barrioiq_pipeline import silver_geosampa_runner as runner


ACCENTED = [
    ("AGUA RASA", "Água Rasa"),
    ("BELEM", "Belém"),
    ("BRAS", "Brás"),
    ("SAO MATEUS", "São Mateus"),
    ("SE", "Sé"),
]


def data():
    geo = []
    ibge = []
    for i in range(96):
        short, official = (
            ACCENTED[i] if i < len(ACCENTED)
            else (f"DISTRITO {i + 1}", f"Distrito {i + 1}")
        )
        row = {
            "nm_distrit": short,
            **{feature: i for feature in runner.FEATURE_COLUMNS},
            "_rescued_data": None,
        }
        geo.append(row)
        ibge.append({
            "CD_DIST": 355030801 + i,
            "NM_DIST": official,
            "CD_MUN": 3550308,
        })
    return geo, ibge


class FakeFrame:
    def __init__(self, records, columns=None):
        self.records = records
        self.columns = (
            runner.OUTPUT_COLUMNS if columns is None else columns
        )

    def count(self):
        return len(self.records)

    def collect(self):
        return deepcopy(self.records)


class FakeSpark:
    def __init__(self, geo, ibge, target=None):
        self.geo = geo
        self.ibge = ibge
        self.target = target
        self.queries = []
        self.created = 0
        self.catalog = SimpleNamespace(
            tableExists=lambda name: (
                name == runner.TARGET and self.target is not None
            ),
        )

    def sql(self, query):
        self.queries.append(query)
        if query.startswith("DESCRIBE HISTORY"):
            version = 7 if runner.SOURCE_GEOSAMPA in query else 3
            return SimpleNamespace(
                first=lambda: {"version": version}
            )
        if query.startswith("SELECT "):
            if runner.SOURCE_GEOSAMPA in query:
                return FakeFrame(self.geo)
            if runner.SOURCE_IBGE in query:
                return FakeFrame(self.ibge)
        raise AssertionError(f"Unexpected SQL statement: {query}")

    def table(self, name):
        if name != runner.TARGET or self.target is None:
            raise AssertionError(f"Unexpected table: {name}")
        return FakeFrame(self.target)

    def createDataFrame(self, *args, **kwargs):
        self.created += 1
        raise AssertionError("Writing is forbidden in read-only tests")


def cli_fake(spark, args):
    pyspark = ModuleType("pyspark")
    sql = ModuleType("pyspark.sql")
    sql.SparkSession = SimpleNamespace(
        builder=SimpleNamespace(getOrCreate=lambda: spark)
    )
    pyspark.sql = sql
    with patch.dict(sys.modules, {"pyspark": pyspark, "pyspark.sql": sql}):
        with patch.object(runner, "emit") as emit:
            runner.main(args)
    return [call.args[0] for call in emit.call_args_list]


class TestNormalization(TestCase):
    def test_normalization_removes_accents(self):
        self.assertEqual(runner.normalize_name(" Água   Rasa "), "AGUA RASA")
        self.assertEqual(runner.normalize_name("A\u0301gua Rasa"), "AGUA RASA")
        self.assertEqual(runner.normalize_name(" São Mateus "), "SAO MATEUS")

    def test_unicode_empty(self):
        self.assertIsNone(runner.normalize_name(None))
        self.assertIsNone(runner.normalize_name(" \t "))

    def test_unicode_does_not_guess_different_districts(self):
        self.assertNotEqual(
            runner.normalize_name("Vila Maria"),
            runner.normalize_name("Vila Mariana"),
        )


class TestQuality(TestCase):
    def test_96_rows_exactly_match(self):
        geo, ibge = data()
        rows, report = runner.build_rows(geo, ibge, 7, 3)
        self.assertEqual(len(rows), 96)
        self.assertEqual(report["correspondencias_validas"], 96)
        self.assertEqual(report["distritos_com_indicadores_nulos"], 0)
        self.assertEqual(report["total_qtd_metro"], sum(range(96)))
        self.assertEqual(rows[0]["NM_DIST"], "Água Rasa")
        self.assertEqual(rows[0]["CD_DIST"], 355030801)
        self.assertEqual(rows[0]["versao_silver_ibge"], 3)

    def test_reject_95_districts(self):
        geo, ibge = data()
        with self.assertRaisesRegex(runner.DataQualityError, "esperados 96"):
            runner.build_rows(geo[:-1], ibge, 7, 3)

    def test_reject_duplicate_geosampa_key(self):
        geo, ibge = data()
        geo[1]["nm_distrit"] = "ÁGUA RASA"
        with self.assertRaisesRegex(runner.DataQualityError, "duplicada"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_duplicate_ibge_code(self):
        geo, ibge = data()
        ibge[2]["CD_DIST"] = ibge[1]["CD_DIST"]
        with self.assertRaisesRegex(runner.DataQualityError, "CD_DIST duplicado"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_unknown_district(self):
        geo, ibge = data()
        geo[0]["nm_distrit"] = "Distrito inexistente"
        with self.assertRaisesRegex(runner.DataQualityError, "nao reconciliados"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_wrong_municipality(self):
        geo, ibge = data()
        ibge[0]["CD_MUN"] = 1111111
        with self.assertRaisesRegex(runner.DataQualityError, "municipio"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_invalid_district_code(self):
        geo, ibge = data()
        ibge[0]["CD_DIST"] = 123
        with self.assertRaisesRegex(runner.DataQualityError, "CD_DIST invalido"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_negative_feature(self):
        geo, ibge = data()
        geo[0]["qtd_metro"] = -1
        with self.assertRaisesRegex(runner.DataQualityError, "negativo"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_float_feature(self):
        geo, ibge = data()
        geo[0]["qtd_onibus"] = 3.5
        with self.assertRaisesRegex(runner.DataQualityError, "nao e inteiro"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_missing_column(self):
        geo, ibge = data()
        del geo[0]["qtd_trem"]
        with self.assertRaisesRegex(runner.DataQualityError, "coluna ausente"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_reject_rescued_data(self):
        geo, ibge = data()
        geo[0]["_rescued_data"] = '{"unexpected":"field"}'
        with self.assertRaisesRegex(runner.DataQualityError, "rescued_data"):
            runner.build_rows(geo, ibge, 7, 3)

    def test_nulls_are_preserved_not_zeroed(self):
        geo, ibge = data()
        geo[0]["qtd_ubs"] = None
        rows, report = runner.build_rows(geo, ibge, 7, 3)
        self.assertIsNone(rows[0]["qtd_ubs"])
        self.assertEqual(rows[0]["qtd_indicadores_nulos"], 1)
        self.assertEqual(report["nulos_por_indicador"], {"qtd_ubs": 1})

    def test_schema_has_42_original_features(self):
        self.assertEqual(len(runner.FEATURE_COLUMNS), 42)
        self.assertIn("qtd_ensino_infatil_publico", runner.FEATURE_COLUMNS)
        self.assertEqual(len(set(runner.FEATURE_COLUMNS)), 42)


class TestCheckExecution(TestCase):
    def test_check_never_writes(self):
        geo, ibge = data()
        spark = FakeSpark(geo, ibge)
        events = cli_fake(spark, ["--check"])
        self.assertIn("GEOSAMPA_SILVER_CHECK_SUCCESS", events)
        self.assertEqual(spark.created, 0)
        self.assertEqual(len(spark.queries), 4)
        self.assertTrue(all(
            q.startswith("DESCRIBE HISTORY") or q.startswith("SELECT ")
            for q in spark.queries
        ))

    def test_target_equal(self):
        geo, ibge = data()
        rows, _ = runner.build_rows(geo, ibge, 7, 3)
        spark = FakeSpark(geo, ibge, target=rows)
        self.assertTrue(runner.compare_target(spark, rows))

    def test_target_different(self):
        geo, ibge = data()
        rows, _ = runner.build_rows(geo, ibge, 7, 3)
        changed = deepcopy(rows)
        changed[0]["qtd_metro"] += 1
        spark = FakeSpark(geo, ibge, target=changed)
        self.assertFalse(runner.compare_target(spark, rows))

    def test_target_wrong_schema_blocks(self):
        geo, ibge = data()
        rows, _ = runner.build_rows(geo, ibge, 7, 3)
        spark = FakeSpark(geo, ibge, target=rows)
        spark.table = lambda _: FakeFrame(rows, runner.OUTPUT_COLUMNS[:-1])
        with self.assertRaisesRegex(runner.DataQualityError, "schema diferente"):
            runner.compare_target(spark, rows)

    def test_apply_without_confirmation_is_rejected(self):
        with self.assertRaises(SystemExit) as exc:
            runner.main(["--apply"])
        self.assertEqual(exc.exception.code, 2)

    def test_check_with_confirmation_is_rejected(self):
        with self.assertRaises(SystemExit) as exc:
            runner.main(["--check", "--confirm-publish"])
        self.assertEqual(exc.exception.code, 2)

    def test_check_invalid_data_before_any_write(self):
        geo, ibge = data()
        geo[0]["qtd_metro"] = -10
        spark = FakeSpark(geo, ibge)
        with self.assertRaises(runner.DataQualityError):
            cli_fake(spark, ["--check"])
        self.assertEqual(spark.created, 0)


if __name__ == "__main__":
    main(verbosity=2)
