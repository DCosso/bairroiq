
"""
BairroIQ | Testes do executor Silver IBGE.

Testes unitarios sem Databricks ou PySpark real.
Nenhuma tabela e criada, alterada ou excluida.

Execucao:
    python -m unittest discover -s tests -v
"""

from collections import Counter
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
import sys
import tempfile

from barrioiq_pipeline import silver_ibge_runner as runner


# ============================================================
# 1. DADOS SINTETICOS
# ============================================================

def make_rows(total=96):
    rows = []

    for i in range(total):
        rows.append({
            "CD_DIST": str(355030800 + i),
            "NM_DIST": f"Distrito {i + 1}",
            "CD_MUN": "3550308",
            "NM_MUN": "São Paulo",
            "area_km2": Decimal("2.50"),
            "total_pessoas": 1000,
            "total_domicilios": 400,
            "total_domicilios_particulares": 390,
            "total_domicilios_coletivos": 10,
            "media_moradores_domicilios_ocupados":
                Decimal("2.50"),
            "percentual_domicilios_ocupados_imputados":
                Decimal("3.50"),
            "total_domicilios_particulares_ocupados": 300,
            "total_domicilios_uso_ocasional": 50,
            "total_domicilios_permanentes_vagos": 40,
        })

    return rows


# ============================================================
# 2. SIMULADORES DE SPARK
# ============================================================

class FakeDataFrame:

    def __init__(self, rows, columns=None):
        self.rows = rows
        self.columns = list(
            columns if columns is not None
            else runner.COLUMNS
        )

    def collect(self):
        return list(self.rows)

    def count(self):
        return len(self.rows)

    def select(self, *columns):
        return FakeDataFrame(
            [
                {column: row[column] for column in columns}
                for row in self.rows
            ],
            list(columns),
        )


class FakeSpark:

    def __init__(self, rows, target_rows=None):
        self.rows = rows
        self.target_rows = target_rows
        self.queries = []

        self.catalog = SimpleNamespace(
            tableExists=lambda name: (
                name == runner.TARGET
                and self.target_rows is not None
            )
        )

    def sql(self, query):
        self.queries.append(query)

        if query.startswith("DESCRIBE HISTORY"):
            return SimpleNamespace(
                first=lambda: {"version": 7}
            )

        if query.lstrip().upper().startswith("SELECT"):
            return FakeDataFrame(self.rows)

        raise AssertionError(
            f"Escrita SQL nao esperada no teste: {query}"
        )

    def table(self, name):
        if name != runner.TARGET:
            raise AssertionError(
                f"Tabela inesperada: {name}"
            )

        if self.target_rows is None:
            raise AssertionError(
                "Tabela destino nao configurada"
            )

        return FakeDataFrame(self.target_rows)


def run_cli_with_fake_spark(spark, arguments):
    """Executa a CLI com Spark simulado."""

    pyspark_module = ModuleType("pyspark")
    sql_module = ModuleType("pyspark.sql")

    sql_module.SparkSession = SimpleNamespace(
        builder=SimpleNamespace(
            getOrCreate=lambda: spark
        )
    )

    pyspark_module.sql = sql_module

    with (
        patch.dict(
            sys.modules,
            {
                "pyspark": pyspark_module,
                "pyspark.sql": sql_module,
            },
        ),
        patch.object(
            sys,
            "argv",
            ["silver_ibge_runner.py", *arguments],
        ),
        patch.object(runner, "emit") as mocked_emit,
    ):
        runner.main()

    return [
        call.args[0]
        for call in mocked_emit.call_args_list
    ]


# ============================================================
# 3. TESTES DE CONTRATO SQL
# ============================================================

class TestSilverRunnerSQL(TestCase):

    def test_01_load_valid_sql(self):
        projection, digest = runner.load_select()

        self.assertTrue(
            projection.upper().startswith("SELECT")
        )

        self.assertEqual(len(digest), 64)

        self.assertNotIn(
            "CREATE OR REPLACE",
            projection.upper(),
        )

    def test_02_reject_wrong_target(self):
        original = runner.SQL_FILE.read_text(
            encoding="utf-8"
        )

        invalid = original.replace(
            runner.TARGET,
            "workspace.gold.ibge_agregados_basicos_v2",
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.sql"
            path.write_text(
                invalid,
                encoding="utf-8",
            )

            with patch.object(runner, "SQL_FILE", path):
                with self.assertRaises(ValueError):
                    runner.load_select()

    def test_03_reject_multiple_statements(self):
        original = runner.SQL_FILE.read_text(
            encoding="utf-8"
        )

        invalid = (
            original
            + "\nDROP TABLE workspace.silver.exemplo;\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.sql"
            path.write_text(
                invalid,
                encoding="utf-8",
            )

            with patch.object(runner, "SQL_FILE", path):
                with self.assertRaises(ValueError):
                    runner.load_select()

    def test_04_snapshot_version(self):
        spark = FakeSpark(make_rows())

        self.assertEqual(
            runner.snapshot(spark),
            7,
        )

        self.assertTrue(
            spark.queries[0].startswith(
                "DESCRIBE HISTORY"
            )
        )

    def test_05_build_select(self):
        query = runner.build_select(
            "SELECT CD_DIST",
            7,
        )

        self.assertIn(
            "VERSION AS OF 7",
            query,
        )

        self.assertIn(
            "CD_MUN = '3550308'",
            query,
        )


# ============================================================
# 4. TESTES DE QUALIDADE DOS DADOS
# ============================================================

class TestSilverRunnerQuality(TestCase):

    def test_06_accept_96_valid_districts(self):
        rows = make_rows()

        result = runner.validate(
            FakeDataFrame(rows)
        )

        self.assertEqual(len(result), 96)

    def test_07_reject_missing_district(self):
        rows = make_rows(95)

        with self.assertRaisesRegex(
            ValueError,
            "Esperados 96 distritos",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_08_reject_duplicate_district(self):
        rows = make_rows()

        rows[1]["CD_DIST"] = rows[0]["CD_DIST"]

        with self.assertRaisesRegex(
            ValueError,
            "duplicado",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_09_reject_null_population(self):
        rows = make_rows()

        rows[0]["total_pessoas"] = None

        with self.assertRaisesRegex(
            ValueError,
            "colunas nulas",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_10_reject_negative_quantity(self):
        rows = make_rows()

        rows[0]["total_domicilios_coletivos"] = -1

        with self.assertRaisesRegex(
            ValueError,
            "quantidade negativa",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_11_reject_total_mismatch(self):
        rows = make_rows()

        rows[0]["total_domicilios"] = 401

        with self.assertRaisesRegex(
            ValueError,
            "nao reconciliado",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_12_reject_household_mismatch(self):
        rows = make_rows()

        rows[0]["total_domicilios_uso_ocasional"] = 51

        with self.assertRaisesRegex(
            ValueError,
            "nao reconciliados",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_13_reject_invalid_percentage(self):
        rows = make_rows()

        rows[0][
            "percentual_domicilios_ocupados_imputados"
        ] = Decimal("120")

        with self.assertRaisesRegex(
            ValueError,
            "percentual imputado",
        ):
            runner.validate(FakeDataFrame(rows))

    def test_14_reject_unexpected_schema(self):
        rows = make_rows()

        columns = runner.COLUMNS[:-1]

        with self.assertRaisesRegex(
            ValueError,
            "Colunas inesperadas",
        ):
            runner.validate(
                FakeDataFrame(rows, columns)
            )

    def test_15_reject_wrong_municipality(self):
        rows = make_rows()

        rows[0]["CD_MUN"] = "9999999"

        with self.assertRaisesRegex(
            ValueError,
            "identificacao territorial invalida",
        ):
            runner.validate(FakeDataFrame(rows))


# ============================================================
# 5. TESTES DE COMPARACAO COM A SILVER
# ============================================================

class TestSilverRunnerComparison(TestCase):

    def test_16_detect_identical_target(self):
        rows = make_rows()

        spark = FakeSpark(
            rows=rows,
            target_rows=[dict(row) for row in rows],
        )

        self.assertTrue(
            runner.same_as_target(spark, rows)
        )

    def test_17_detect_changed_target(self):
        rows = make_rows()

        old = [
            dict(row)
            for row in rows
        ]

        old[0]["total_pessoas"] = 999

        spark = FakeSpark(
            rows=rows,
            target_rows=old,
        )

        self.assertFalse(
            runner.same_as_target(spark, rows)
        )

    def test_18_detect_missing_target(self):
        rows = make_rows()

        spark = FakeSpark(
            rows=rows,
            target_rows=None,
        )

        self.assertFalse(
            runner.same_as_target(spark, rows)
        )


# ============================================================
# 6. TESTES DE SEGURANCA DA EXECUCAO
# ============================================================

class TestSilverRunnerExecution(TestCase):

    def test_19_check_mode_never_writes(self):
        rows = make_rows()

        spark = FakeSpark(
            rows=rows,
            target_rows=make_rows(),
        )

        events = run_cli_with_fake_spark(
            spark,
            ["--check"],
        )

        self.assertIn(
            "CHECK_SUCCESS",
            events,
        )

        self.assertEqual(
            len(spark.queries),
            2,
        )

        self.assertFalse(
            any(
                "CREATE OR REPLACE TABLE" in query
                for query in spark.queries
            )
        )

    def test_20_apply_requires_confirmation(self):
        with patch.object(
            sys,
            "argv",
            [
                "silver_ibge_runner.py",
                "--apply",
            ],
        ):
            with self.assertRaises(SystemExit) as error:
                runner.main()

        self.assertEqual(
            error.exception.code,
            2,
        )

    def test_21_identical_data_skips_publish(self):
        rows = make_rows()

        spark = FakeSpark(
            rows=rows,
            target_rows=make_rows(),
        )

        events = run_cli_with_fake_spark(
            spark,
            [
                "--apply",
                "--confirm-publish",
            ],
        )

        self.assertIn(
            "UNCHANGED",
            events,
        )

        self.assertEqual(
            len(spark.queries),
            2,
        )

    def test_22_invalid_data_blocks_publish(self):
        rows = make_rows()

        rows[0]["total_pessoas"] = None

        spark = FakeSpark(
            rows=rows,
            target_rows=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Falha de qualidade",
        ):
            run_cli_with_fake_spark(
                spark,
                [
                    "--apply",
                    "--confirm-publish",
                ],
            )

        self.assertEqual(
            len(spark.queries),
            2,
        )


if __name__ == "__main__":
    main(verbosity=2)
