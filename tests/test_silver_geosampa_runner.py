
"""BairroIQ | Testes da Silver GeoSampa sem Spark/Databricks reais.

Executar na raiz do repositorio:
    python -m unittest discover -s tests -p 'test_silver_geosampa_runner.py' -v
"""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
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


def sample():
    geo, ibge, official = [], [], {}
    for i in range(96):
        g, name = (
            ACCENTED[i] if i < len(ACCENTED)
            else (f"DISTRITO {i + 1}", f"Distrito {i + 1}")
        )
        code = str(355030801 + i)
        official[code] = name
        geo.append({
            "nm_distrit": g,
            **{feature: i for feature in runner.FEATURE_COLUMNS},
            "_rescued_data": None,
        })
        ibge.append({"CD_DIST": int(code), "NM_DIST": name, "CD_MUN": 3550308})
    return geo, ibge, official


def dbf_bytes(records):
    """Gera DBF minimo valido com campos CD_DIST e NM_DIST."""
    specs = [("CD_DIST", 12), ("NM_DIST", 80)]
    field_count = len(specs)
    head_len = 32 + field_count * 32 + 1
    record_len = 1 + sum(length for _, length in specs)
    head = bytearray(32)
    head[0] = 0x03
    head[4:8] = len(records).to_bytes(4, "little")
    head[8:10] = head_len.to_bytes(2, "little")
    head[10:12] = record_len.to_bytes(2, "little")
    result = bytearray(head)
    for name, length in specs:
        descriptor = bytearray(32)
        encoded = name.encode("ascii")
        descriptor[:len(encoded)] = encoded
        descriptor[11] = ord("C")
        descriptor[16] = length
        result.extend(descriptor)
    result.append(0x0D)
    for code, name in records:
        record = bytearray(b" ")
        for value, (_, length) in zip((code, name), specs):
            encoded = str(value).encode("utf-8")
            if len(encoded) > length:
                raise AssertionError("Valor sintetico longo demais")
            record.extend(encoded.ljust(length, b" "))
        result.extend(record)
    return bytes(result)


def write_test_dbf(path, official, extra=946):
    records = [(code, name) for code, name in official.items()]
    records += [
        (str(355040000 + i), f"Outros {i}") for i in range(extra)
    ]
    Path(path).write_bytes(dbf_bytes(records))


class FakeFrame:
    def __init__(self, rows, columns=None):
        self.rows = rows
        self.columns = list(columns) if columns is not None else list(runner.OUTPUT_COLUMNS)

    def count(self):
        return len(self.rows)

    def collect(self):
        return deepcopy(self.rows)


class FakeSpark:
    def __init__(self, geo, ibge, target=None, legacy=True):
        self.geo, self.ibge, self.target = geo, ibge, target
        self.legacy = legacy
        self.sql_queries = []
        self.write_calls = 0
        self.catalog = SimpleNamespace(
            tableExists=lambda name: name == runner.TARGET and self.target is not None
        )

    def table(self, name):
        if name == runner.SOURCE_GEOSAMPA:
            columns = ["nm_distrit", *runner.FEATURE_COLUMNS, "_rescued_data"]
            if self.legacy:
                columns[columns.index("qtd_poupatempo")] = "qtd_pupatempo"
            return FakeFrame([], columns)
        if name == runner.TARGET and self.target is not None:
            return FakeFrame(self.target)
        raise AssertionError(f"Tabela inesperada: {name}")

    def sql(self, query):
        self.sql_queries.append(query)
        if query.startswith("DESCRIBE HISTORY"):
            version = 43 if runner.SOURCE_GEOSAMPA in query else 0
            return SimpleNamespace(first=lambda: {"version": version})
        if query.startswith("SELECT "):
            if runner.SOURCE_GEOSAMPA in query:
                return FakeFrame(self.geo)
            if runner.SOURCE_IBGE in query:
                return FakeFrame(self.ibge)
        raise AssertionError(f"SQL proibido/desconhecido: {query}")

    def createDataFrame(self, *args, **kwargs):
        self.write_calls += 1
        raise AssertionError("Escrita nao esperada neste teste")


def cli_fake(spark, args):
    pyspark = ModuleType("pyspark")
    pyspark_sql = ModuleType("pyspark.sql")
    pyspark_sql.SparkSession = SimpleNamespace(
        builder=SimpleNamespace(getOrCreate=lambda: spark)
    )
    pyspark.sql = pyspark_sql
    with patch.dict(sys.modules, {"pyspark": pyspark, "pyspark.sql": pyspark_sql}):
        with patch.object(runner, "emit") as mock_emit:
            runner.main(args)
    return [x.args[0] for x in mock_emit.call_args_list]


class TestUnicodeAndReference(TestCase):
    def test_unicode_normalization(self):
        self.assertEqual(runner.normalize_name(" Água  Rasa "), "AGUA RASA")
        self.assertEqual(runner.normalize_name("A\u0301gua Rasa"), "AGUA RASA")
        self.assertIsNone(runner.normalize_name(None))
        self.assertIsNone(runner.normalize_name("  "))

    def test_corrupted_silver_name_can_match_by_code(self):
        self.assertTrue(runner.compatible_ibge_name("�GUA RASA", "Água Rasa"))
        self.assertTrue(runner.compatible_ibge_name("S�O MATEUS", "São Mateus"))
        self.assertFalse(runner.compatible_ibge_name("VILA MARIA", "Vila Mariana"))
        self.assertFalse(runner.compatible_ibge_name("S�O PAULO", "São Mateus"))

    def test_dbf_filters_1042_to_96(self):
        _, _, official = sample()
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            write_test_dbf(path, official)
            actual, meta = runner.read_official_dbf(path, set(official))
        self.assertEqual(actual, official)
        self.assertEqual(meta["registros_dbf_estadual"], 1042)
        self.assertEqual(len(meta["dbf_sha256"]), 64)

    def test_dbf_rejects_missing_municipal_district(self):
        _, _, official = sample()
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            incomplete = dict(official)
            incomplete.pop(next(iter(incomplete)))
            write_test_dbf(path, incomplete)
            with self.assertRaisesRegex(runner.DataQualityError, "96 codigos"):
                runner.read_official_dbf(path, set(official))

    def test_dbf_rejects_duplicate_code(self):
        _, _, official = sample()
        records = list(official.items()) + [next(iter(official.items()))]
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            path.write_bytes(dbf_bytes(records))
            with self.assertRaisesRegex(runner.DataQualityError, "duplicado"):
                runner.read_official_dbf(path, set(official))

    def test_dbf_rejects_invalid_utf8(self):
        _, _, official = sample()
        records = list(official.items())
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            content = dbf_bytes(records)
            content = content.replace("Água Rasa".encode("utf-8"), b"\xff\xfegua Rasa")
            path.write_bytes(content)
            with self.assertRaises(UnicodeError):
                runner.read_official_dbf(path, set(official))

    def test_dbf_rejects_truncated_bytes(self):
        _, _, official = sample()
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            path.write_bytes(dbf_bytes(list(official.items()))[:-20])
            with self.assertRaisesRegex(runner.DataQualityError, "DBF invalido"):
                runner.read_official_dbf(path, set(official))


class TestGeoSampaQuality(TestCase):
    def test_96_all_features(self):
        geo, ibge, official = sample()
        rows, meta = runner.build_rows(geo, ibge, official, 43, 0)
        self.assertEqual(len(rows), 96)
        self.assertEqual(meta["indicadores_por_distrito"], 42)
        self.assertEqual(meta["nomes_ibge_corrompidos"], 0)
        self.assertEqual(rows[0]["NM_DIST"], "Água Rasa")
        self.assertEqual(rows[0]["versao_bronze_geosampa"], 43)
        self.assertEqual(rows[0]["versao_silver_ibge"], 0)
        self.assertEqual(list(rows[0]), runner.OUTPUT_COLUMNS)

    def test_32_corrupted_names_recovered(self):
        geo, ibge, official = sample()
        for row in ibge[:32]:
            row["NM_DIST"] = "�" + row["NM_DIST"][1:]
        # A substituicao e simulada apos a primeira letra; para os demais
        # nomes sinteticos sem acento, o caractere corrompido e o wildcard.
        rows, meta = runner.build_rows(geo, ibge, official, 43, 0)
        self.assertEqual(meta["nomes_ibge_corrompidos"], 32)
        self.assertEqual(rows[0]["NM_DIST"], "Água Rasa")

    def test_reject_95_geo(self):
        geo, ibge, official = sample()
        with self.assertRaisesRegex(runner.DataQualityError, "96 registros"):
            runner.build_rows(geo[:-1], ibge, official, 43, 0)

    def test_reject_geo_duplicate(self):
        geo, ibge, official = sample()
        geo[1]["nm_distrit"] = "Água Rasa"
        with self.assertRaisesRegex(runner.DataQualityError, "duplicado"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_mismatch_even_after_normalization(self):
        geo, ibge, official = sample()
        geo[0]["nm_distrit"] = "Bairro inventado"
        with self.assertRaisesRegex(runner.DataQualityError, "nao reconciliados"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_bad_silver_name(self):
        geo, ibge, official = sample()
        ibge[0]["NM_DIST"] = "Qualquer nome"
        with self.assertRaisesRegex(runner.DataQualityError, "incompativel"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_duplicate_ibge_code(self):
        geo, ibge, official = sample()
        ibge[1]["CD_DIST"] = ibge[0]["CD_DIST"]
        with self.assertRaisesRegex(runner.DataQualityError, "duplicado"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_wrong_ibge_municipality(self):
        geo, ibge, official = sample()
        ibge[0]["CD_MUN"] = 9999999
        with self.assertRaisesRegex(runner.DataQualityError, "Municipio"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_invalid_ibge_code(self):
        geo, ibge, official = sample()
        ibge[0]["CD_DIST"] = 123
        with self.assertRaisesRegex(runner.DataQualityError, "CD_DIST invalido"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_negative_indicator(self):
        geo, ibge, official = sample()
        geo[0]["qtd_metro"] = -1
        with self.assertRaisesRegex(runner.DataQualityError, "negativo"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_float_indicator(self):
        geo, ibge, official = sample()
        geo[0]["qtd_metro"] = 2.5
        with self.assertRaisesRegex(runner.DataQualityError, "nao inteiro"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_missing_indicator(self):
        geo, ibge, official = sample()
        del geo[0]["qtd_metro"]
        with self.assertRaisesRegex(runner.DataQualityError, "Coluna ausente"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_reject_rescued_data(self):
        geo, ibge, official = sample()
        geo[0]["_rescued_data"] = '{"invalid":true}'
        with self.assertRaisesRegex(runner.DataQualityError, "rescued_data"):
            runner.build_rows(geo, ibge, official, 43, 0)

    def test_preserve_null_not_zero(self):
        geo, ibge, official = sample()
        geo[0]["qtd_ubs"] = None
        rows, meta = runner.build_rows(geo, ibge, official, 43, 0)
        self.assertIsNone(rows[0]["qtd_ubs"])
        self.assertEqual(rows[0]["qtd_indicadores_nulos"], 1)
        self.assertEqual(meta["nulos_por_indicador"], {"qtd_ubs": 1})


class TestProjectionAndExecution(TestCase):
    def test_column_alias_legacy(self):
        geo, ibge, _ = sample()
        sql, alias = runner.bronze_projection(FakeSpark(geo, ibge, legacy=True))
        self.assertTrue(alias)
        self.assertIn("`qtd_pupatempo` AS `qtd_poupatempo`", sql)

    def test_column_canonical(self):
        geo, ibge, _ = sample()
        sql, alias = runner.bronze_projection(FakeSpark(geo, ibge, legacy=False))
        self.assertFalse(alias)
        self.assertIn("`qtd_poupatempo`", sql)
        self.assertNotIn("`qtd_pupatempo`", sql)

    def test_missing_alias_rejected(self):
        geo, ibge, _ = sample()
        spark = FakeSpark(geo, ibge)
        spark.table = lambda name: FakeFrame([], ["nm_distrit", *runner.FEATURE_COLUMNS[:-2], "_rescued_data"])
        with self.assertRaises(runner.DataQualityError):
            runner.bronze_projection(spark)

    def test_target_identical_and_changed(self):
        geo, ibge, official = sample()
        rows, _ = runner.build_rows(geo, ibge, official, 43, 0)
        self.assertTrue(runner.compare_target(FakeSpark(geo, ibge, rows), rows))
        changed = deepcopy(rows)
        changed[0]["qtd_metro"] += 3
        self.assertFalse(runner.compare_target(FakeSpark(geo, ibge, changed), rows))

    def test_missing_target_returns_false(self):
        geo, ibge, official = sample()
        rows, _ = runner.build_rows(geo, ibge, official, 43, 0)
        self.assertFalse(runner.compare_target(FakeSpark(geo, ibge), rows))

    def test_target_schema_mismatch_rejected(self):
        geo, ibge, official = sample()
        rows, _ = runner.build_rows(geo, ibge, official, 43, 0)
        spark = FakeSpark(geo, ibge, rows)
        old_table = spark.table
        spark.table = lambda name: (
            FakeFrame(rows, runner.OUTPUT_COLUMNS[:-1])
            if name == runner.TARGET else old_table(name)
        )
        with self.assertRaisesRegex(runner.DataQualityError, "Schema"):
            runner.compare_target(spark, rows)

    def test_real_check_path_never_writes(self):
        geo, ibge, official = sample()
        spark = FakeSpark(geo, ibge)
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            write_test_dbf(path, official)
            with patch.object(runner, "DBF_PATH", path):
                events = cli_fake(spark, ["--check"])
        self.assertIn("GEOSAMPA_SILVER_CHECK_SUCCESS", events)
        self.assertEqual(spark.write_calls, 0)
        self.assertEqual(len(spark.sql_queries), 4)
        self.assertTrue(all(
            q.startswith("SELECT ") or q.startswith("DESCRIBE HISTORY")
            for q in spark.sql_queries
        ))
        self.assertTrue(any("AS `qtd_poupatempo`" in q for q in spark.sql_queries))

    def test_apply_without_confirmation_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            runner.main(["--apply"])
        self.assertEqual(ctx.exception.code, 2)

    def test_check_with_confirmation_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            runner.main(["--check", "--confirm-publish"])
        self.assertEqual(ctx.exception.code, 2)

    def test_apply_and_check_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as ctx:
            runner.main(["--check", "--apply", "--confirm-publish"])
        self.assertEqual(ctx.exception.code, 2)

    def test_check_invalid_data_blocks_without_write(self):
        geo, ibge, official = sample()
        geo[0]["qtd_metro"] = -1
        spark = FakeSpark(geo, ibge)
        with TemporaryDirectory() as d:
            path = Path(d) / "districts.dbf"
            write_test_dbf(path, official)
            with self.assertRaises(runner.DataQualityError):
                runner.execute(spark, apply=False, dbf_path=path)
        self.assertEqual(spark.write_calls, 0)


if __name__ == "__main__":
    main(verbosity=2)
