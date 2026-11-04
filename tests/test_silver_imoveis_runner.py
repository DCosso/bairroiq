
"""BairroIQ | Testes locais da Silver Imoveis v1 (sem Databricks).

Execucao no repo:
    python -m unittest discover -s tests -p 'test_silver_imoveis_runner.py' -v
"""

from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from barrioiq_pipeline import silver_imoveis_runner as runner


class Fixtures:
    @staticmethod
    def row(**overrides):
        base = {
            "mes": date(2026, 10, 1),
            "bairro": "Aclimacao",
            "transacao": "venda",
            "mediana_m2": 8000,
            "p25_m2": 6500,
            "p75_m2": 10500,
            "anuncios_ativos_media_dia": 10,
            "novos_anuncios": 0,
            "dias_no_mercado_medio": 35,
            "_rescued_data": None,
        }
        base.update(overrides)
        return base

    @staticmethod
    def bronze_baseline():
        # 29.612 chaves unicas, 1.626 bairros,
        # 14 meses e 2 modalidades.
        months = [
            date(
                2025 + (8 + i) // 12,
                (8 + i) % 12 + 1,
                1,
            )
            for i in range(14)
        ]

        rows = []

        for i in range(runner.BASELINE_ROWS):
            bairro_id = i % runner.BASELINE_BAIRROS

            month_id = (
                (i // runner.BASELINE_BAIRROS)
                % len(months)
            )

            modalidade = (
                "venda"
                if i // (
                    runner.BASELINE_BAIRROS * 14
                ) == 0
                else "aluguel"
            )

            row = Fixtures.row(
                mes=months[month_id],
                bairro=f"Bairro {bairro_id:04d}",
                transacao=modalidade,
            )

            if i < 3240:
                row.update(
                    mediana_m2=None,
                    p25_m2=None,
                    p75_m2=None,
                    anuncios_ativos_media_dia=1,
                    dias_no_mercado_medio=None,
                )

            rows.append(row)

        return rows


class TestContract(unittest.TestCase):

    def test_tables_and_columns(self):
        self.assertEqual(
            runner.SOURCE,
            "workspace.bronze.imoveis",
        )
        self.assertEqual(
            runner.TARGET,
            "workspace.silver.imoveis_bairro_mensal",
        )
        self.assertEqual(
            len(runner.SOURCE_COLUMNS),
            10,
        )
        self.assertEqual(
            len(runner.OUTPUT_COLUMNS),
            12,
        )
        self.assertEqual(
            len(set(runner.OUTPUT_COLUMNS)),
            12,
        )
        self.assertNotIn(
            "CD_DIST",
            runner.OUTPUT_COLUMNS,
        )

    def test_normalizes_accents_without_changing_original(self):
        row = Fixtures.row(
            bairro="  Vila  São   José  "
        )

        actual = runner.transform_record(row, 9)

        self.assertEqual(
            actual["bairro"],
            row["bairro"],
        )
        self.assertEqual(
            actual["bairro_normalizado"],
            "VILA SAO JOSE",
        )
        self.assertEqual(
            actual["transacao"],
            "venda",
        )
        self.assertEqual(
            actual["versao_bronze_imoveis"],
            9,
        )

    def test_valid_prices(self):
        actual = runner.transform_record(
            Fixtures.row(),
            2,
        )
        self.assertEqual(
            actual["status_preco"],
            "PRECO_VALIDO",
        )
        self.assertEqual(
            (
                actual["p25_m2"],
                actual["mediana_m2"],
                actual["p75_m2"],
            ),
            (6500, 8000, 10500),
        )

    def test_equal_percentiles_are_legal(self):
        actual = runner.transform_record(
            Fixtures.row(
                p25_m2=8000,
                mediana_m2=8000,
                p75_m2=8000,
            ),
            1,
        )
        self.assertEqual(
            actual["status_preco"],
            "PRECO_VALIDO",
        )

    def test_three_null_prices_are_preserved(self):
        row = Fixtures.row(
            p25_m2=None,
            mediana_m2=None,
            p75_m2=None,
            anuncios_ativos_media_dia=2,
            novos_anuncios=0,
            dias_no_mercado_medio=None,
        )

        actual = runner.transform_record(row, 1)

        self.assertEqual(
            actual["status_preco"],
            "TRES_PRECOS_NULOS",
        )
        self.assertIsNone(
            actual["mediana_m2"]
        )
        self.assertIsNone(
            actual["p25_m2"]
        )
        self.assertIsNone(
            actual["p75_m2"]
        )
        self.assertEqual(
            actual["anuncios_ativos_media_dia"],
            2,
        )
        self.assertIsNone(
            actual["dias_no_mercado_medio"]
        )

    def test_reject_partial_null_prices(self):
        with self.assertRaisesRegex(
            runner.ContractError,
            "parcialmente",
        ):
            runner.transform_record(
                Fixtures.row(p25_m2=None),
                1,
            )

    def test_reject_zero_or_negative_prices(self):
        for val in (0, -1):
            with self.subTest(price=val):
                with self.assertRaises(
                    runner.ContractError
                ):
                    runner.transform_record(
                        Fixtures.row(
                            mediana_m2=val
                        ),
                        1,
                    )

    def test_reject_inverted_percentiles(self):
        with self.assertRaisesRegex(
            runner.ContractError,
            "incoerentes",
        ):
            runner.transform_record(
                Fixtures.row(
                    p25_m2=9000
                ),
                1,
            )

    def test_reject_invalid_bairro(self):
        for value in (
            None,
            "",
            "   ",
            "\ufffd",
        ):
            with self.subTest(value=value):
                with self.assertRaises(
                    runner.ContractError
                ):
                    runner.transform_record(
                        Fixtures.row(
                            bairro=value
                        ),
                        1,
                    )

    def test_reject_invalid_month(self):
        for value in (
            None,
            "2026-10-01",
            date(2026, 10, 2),
        ):
            with self.subTest(value=value):
                with self.assertRaises(
                    runner.ContractError
                ):
                    runner.transform_record(
                        Fixtures.row(
                            mes=value
                        ),
                        1,
                    )

    def test_reject_unknown_transaction(self):
        for value in (
            None,
            "",
            "Venda",
            "locacao",
        ):
            with self.subTest(value=value):
                with self.assertRaises(
                    runner.ContractError
                ):
                    runner.transform_record(
                        Fixtures.row(
                            transacao=value
                        ),
                        1,
                    )

    def test_reject_invalid_volume(self):
        for field in (
            "anuncios_ativos_media_dia",
            "novos_anuncios",
        ):
            for value in (
                None,
                -1,
                True,
                1.1,
            ):
                with self.subTest(
                    field=field,
                    value=value,
                ):
                    with self.assertRaises(
                        runner.ContractError
                    ):
                        runner.transform_record(
                            Fixtures.row(
                                **{field: value}
                            ),
                            1,
                        )

    def test_reject_invalid_days_in_market(self):
        for value in (
            -1,
            True,
            2.2,
        ):
            with self.subTest(value=value):
                with self.assertRaises(
                    runner.ContractError
                ):
                    runner.transform_record(
                        Fixtures.row(
                            dias_no_mercado_medio=value
                        ),
                        1,
                    )

    def test_reject_rescued_data(self):
        with self.assertRaisesRegex(
            runner.ContractError,
            "_rescued_data",
        ):
            runner.transform_record(
                Fixtures.row(
                    _rescued_data='{"corrupt": 1}'
                ),
                1,
            )

    def test_duplicate_business_key_rejected(self):
        row = Fixtures.row()

        with self.assertRaisesRegex(
            runner.ContractError,
            "duplicada",
        ):
            runner.validate_records(
                [row, dict(row)],
                1,
            )

    def test_missing_coverage_rejected(self):
        with self.assertRaisesRegex(
            runner.ContractError,
            "Perda de linhas",
        ):
            runner.validate_records(
                [Fixtures.row()],
                1,
            )

    def test_empty_bronze_rejected(self):
        with self.assertRaisesRegex(
            runner.ContractError,
            "vazia",
        ):
            runner.validate_records(
                [],
                1,
            )

    def test_baseline_and_preservation(self):
        rows = Fixtures.bronze_baseline()

        actual, summary = runner.validate_records(
            rows,
            14,
        )

        self.assertEqual(
            summary["rows"],
            29612,
        )
        self.assertEqual(
            summary["bairros_origem"],
            1626,
        )
        self.assertEqual(
            summary["meses"],
            14,
        )
        self.assertEqual(
            summary["tres_precos_nulos"],
            3240,
        )
        self.assertEqual(
            summary["precos_validos"],
            26372,
        )
        self.assertEqual(
            summary["primeiro_mes"],
            "2025-09-01",
        )
        self.assertEqual(
            summary["ultimo_mes"],
            "2026-10-01",
        )
        self.assertEqual(
            len(actual),
            len(rows),
        )


class TestSnapshot(unittest.TestCase):

    def test_delta_version(self):
        spark = SimpleNamespace(
            sql=Mock(
                return_value=SimpleNamespace(
                    first=lambda: {
                        "version": 12
                    }
                )
            )
        )

        self.assertEqual(
            runner.delta_version(
                spark,
                runner.SOURCE,
            ),
            12,
        )

        spark.sql.assert_called_once_with(
            f"DESCRIBE HISTORY {runner.SOURCE} LIMIT 1"
        )

    def test_snapshot_requires_real_columns(self):
        spark = SimpleNamespace(
            table=Mock(
                return_value=SimpleNamespace(
                    columns=["mes"]
                )
            ),
            sql=Mock(),
        )

        with self.assertRaisesRegex(
            runner.ContractError,
            "Colunas ausentes",
        ):
            runner.load_snapshot(
                spark,
                3,
            )

        spark.sql.assert_not_called()

    def test_snapshot_uses_fixed_delta_version(self):
        df = SimpleNamespace(
            limit=Mock(
                return_value=SimpleNamespace(
                    collect=lambda: []
                )
            )
        )

        spark = SimpleNamespace(
            table=Mock(
                return_value=SimpleNamespace(
                    columns=runner.SOURCE_COLUMNS
                )
            ),
            sql=Mock(
                return_value=df
            ),
        )

        self.assertEqual(
            runner.load_snapshot(
                spark,
                8,
            ),
            [],
        )

        sql = spark.sql.call_args.args[0]

        self.assertIn(
            "VERSION AS OF 8",
            sql,
        )
        self.assertIn(
            runner.SOURCE,
            sql,
        )

        df.limit.assert_called_once_with(
            runner.MAX_ROWS + 1
        )

    def test_bounded_collect_rejects_overflow(self):
        spark = SimpleNamespace(
            table=Mock(
                return_value=SimpleNamespace(
                    columns=runner.SOURCE_COLUMNS
                )
            ),
            sql=Mock(
                return_value=SimpleNamespace(
                    limit=lambda n: SimpleNamespace(
                        collect=lambda: [
                            {},
                            {},
                            {},
                            {},
                        ]
                    )
                )
            ),
        )

        with patch.object(
            runner,
            "MAX_ROWS",
            3,
        ):
            with self.assertRaisesRegex(
                runner.ContractError,
                "memoria",
            ):
                runner.load_snapshot(
                    spark,
                    1,
                )


class TestExecution(unittest.TestCase):

    def setUp(self):
        self.expected = {
            "rows": 29612,
            "bairros_origem": 1626,
            "meses": 14,
            "precos_validos": 26372,
            "tres_precos_nulos": 3240,
        }

        self.df = Mock()

        self.spark = SimpleNamespace(
            catalog=SimpleNamespace(
                tableExists=Mock(
                    return_value=False
                ),
                dropTempView=Mock(),
            ),
            sql=Mock(
                return_value=SimpleNamespace(
                    collect=Mock(
                        return_value=[]
                    )
                )
            ),
        )

    def do_execute(
        self,
        apply=False,
        target_exists=False,
        equal=False,
        versions=(7, 7, 7),
    ):
        self.spark.catalog.tableExists.return_value = (
            target_exists
        )

        with (
            patch.object(
                runner,
                "delta_version",
                side_effect=list(versions),
            ),
            patch.object(
                runner,
                "load_snapshot",
                return_value=[Fixtures.row()],
            ),
            patch.object(
                runner,
                "validate_records",
                return_value=(
                    [Fixtures.row()],
                    self.expected,
                ),
            ),
            patch.object(
                runner,
                "output_dataframe",
                return_value=self.df,
            ),
            patch.object(
                runner,
                "equal_target",
                return_value=equal,
            ),
            patch.object(
                runner,
                "emit",
            ) as emitted,
        ):
            result = runner.execute(
                self.spark,
                apply=apply,
            )

        return result, emitted

    def test_check_never_writes(self):
        result, emitted = self.do_execute()

        self.assertEqual(
            result,
            self.expected,
        )

        self.spark.sql.assert_not_called()

        self.df.createOrReplaceTempView.assert_not_called()

        self.spark.catalog.dropTempView.assert_not_called()

        self.assertEqual(
            emitted.call_args.args[0],
            "IMOVEIS_SILVER_CHECK_SUCCESS",
        )
        self.assertEqual(
            emitted.call_args.kwargs[
                "changed_tables"
            ],
            False,
        )

    def test_check_on_existing_divergent_target_does_not_write(self):
        result, emitted = self.do_execute(
            target_exists=True,
            equal=False,
        )

        self.assertEqual(
            result,
            self.expected,
        )

        self.spark.sql.assert_not_called()

        self.assertEqual(
            emitted.call_args.args[0],
            "IMOVEIS_SILVER_CHECK_SUCCESS",
        )

    def test_apply_identical_target_does_not_write(self):
        result, emitted = self.do_execute(
            apply=True,
            target_exists=True,
            equal=True,
        )

        self.assertEqual(
            result,
            self.expected,
        )

        self.spark.sql.assert_not_called()

        self.assertEqual(
            emitted.call_args.args[0],
            "IMOVEIS_SILVER_UNCHANGED",
        )

    def test_apply_rejects_existing_divergent_target(self):
        self.spark.catalog.tableExists.return_value = True

        with (
            patch.object(
                runner,
                "delta_version",
                side_effect=[7, 7],
            ),
            patch.object(
                runner,
                "load_snapshot",
                return_value=[Fixtures.row()],
            ),
            patch.object(
                runner,
                "validate_records",
                return_value=(
                    [Fixtures.row()],
                    self.expected,
                ),
            ),
            patch.object(
                runner,
                "output_dataframe",
                return_value=self.df,
            ),
            patch.object(
                runner,
                "equal_target",
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(
                runner.ContractError,
                "publicacao bloqueada",
            ):
                runner.execute(
                    self.spark,
                    apply=True,
                )

        self.spark.sql.assert_not_called()

    def test_check_rejects_changed_source_snapshot(self):
        with (
            patch.object(
                runner,
                "delta_version",
                side_effect=[7, 8],
            ),
            patch.object(
                runner,
                "load_snapshot",
                return_value=[Fixtures.row()],
            ),
            patch.object(
                runner,
                "validate_records",
                return_value=(
                    [Fixtures.row()],
                    self.expected,
                ),
            ),
            patch.object(
                runner,
                "output_dataframe",
                return_value=self.df,
            ),
            patch.object(
                runner,
                "equal_target",
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(
                runner.ContractError,
                "Bronze mudou",
            ):
                runner.execute(
                    self.spark,
                    apply=False,
                )

        self.spark.sql.assert_not_called()

    def test_apply_new_target_creates_once_and_verifies(self):
        with (
            patch.object(
                runner,
                "delta_version",
                side_effect=[7, 7, 7],
            ),
            patch.object(
                runner,
                "load_snapshot",
                return_value=[Fixtures.row()],
            ),
            patch.object(
                runner,
                "validate_records",
                return_value=(
                    [Fixtures.row()],
                    self.expected,
                ),
            ),
            patch.object(
                runner,
                "output_dataframe",
                return_value=self.df,
            ),
            patch.object(
                runner,
                "equal_target",
                side_effect=[False, True],
            ),
            patch.object(
                runner,
                "emit",
            ) as emitted,
        ):
            runner.execute(
                self.spark,
                apply=True,
            )

        self.spark.sql.assert_called_once()

        sql = self.spark.sql.call_args.args[0]

        self.assertTrue(
            sql.startswith(
                f"CREATE TABLE IF NOT EXISTS {runner.TARGET}"
            )
        )
        self.assertNotIn(
            "REPLACE TABLE",
            sql,
        )

        self.df.createOrReplaceTempView.assert_called_once()

        self.spark.catalog.dropTempView.assert_called_once()

        self.assertEqual(
            emitted.call_args.args[0],
            "IMOVEIS_SILVER_APPLY_SUCCESS",
        )

    def test_apply_rejects_failed_publication_verification(self):
        with (
            patch.object(
                runner,
                "delta_version",
                side_effect=[7, 7, 7],
            ),
            patch.object(
                runner,
                "load_snapshot",
                return_value=[Fixtures.row()],
            ),
            patch.object(
                runner,
                "validate_records",
                return_value=(
                    [Fixtures.row()],
                    self.expected,
                ),
            ),
            patch.object(
                runner,
                "output_dataframe",
                return_value=self.df,
            ),
            patch.object(
                runner,
                "equal_target",
                side_effect=[False, False],
            ),
        ):
            with self.assertRaisesRegex(
                runner.ContractError,
                "nao coincide",
            ):
                runner.execute(
                    self.spark,
                    apply=True,
                )

        self.spark.catalog.dropTempView.assert_called_once()


class TestCli(unittest.TestCase):

    def test_apply_requires_explicit_confirmation(self):
        with (
            self.assertRaises(SystemExit) as caught,
            patch("sys.stderr"),
        ):
            runner.main(["--apply"])

        self.assertEqual(
            caught.exception.code,
            2,
        )

    def test_check_rejects_confirmation(self):
        with (
            self.assertRaises(SystemExit) as caught,
            patch("sys.stderr"),
        ):
            runner.main([
                "--check",
                "--confirm-publish",
            ])

        self.assertEqual(
            caught.exception.code,
            2,
        )

    def test_mutual_exclusion(self):
        with (
            self.assertRaises(SystemExit) as caught,
            patch("sys.stderr"),
        ):
            runner.main([
                "--check",
                "--apply",
                "--confirm-publish",
            ])

        self.assertEqual(
            caught.exception.code,
            2,
        )

    def test_requires_mode(self):
        with (
            self.assertRaises(SystemExit) as caught,
            patch("sys.stderr"),
        ):
            runner.main([])

        self.assertEqual(
            caught.exception.code,
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
