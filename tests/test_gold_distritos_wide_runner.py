
"""
BairroIQ | Gold Distritos Wide v3
Testes unitarios de contratos e atualizacao Delta.

Execucao local, na raiz do repositorio:

python -m unittest discover \
    -s tests \
    -p "test_gold_distritos_wide_runner.py" \
    -v

Nao requer PySpark.
Nao acessa Databricks.
Nao modifica tabelas.
"""

import unittest
from collections import Counter
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from barrioiq_pipeline import (
    gold_distritos_wide_runner as runner
)


# ============================================================
# 1. FIXTURES E SIMULADORES
# ============================================================

class FakeType:

    def __init__(self, name):
        self.name = name

    def simpleString(self):
        return self.name


class FakeFrame:

    def __init__(self, rows, columns=None):

        self.rows = list(rows)

        if columns is None:
            columns = [
                ("CD_DIST", "bigint"),
                ("valor", "double"),
            ]

        self.columns_spec = list(columns)

        self.columns = [
            name
            for name, _ in self.columns_spec
        ]

        self.schema = [
            SimpleNamespace(
                name=name,
                dataType=FakeType(dtype),
            )
            for name, dtype in self.columns_spec
        ]

        self.created_views = []

    def count(self):
        return len(self.rows)

    def limit(self, quantity):
        return FakeFrame(
            self.rows[:quantity],
            self.columns_spec,
        )

    def exceptAll(self, other):

        difference = (
            Counter(self.rows)
            - Counter(other.rows)
        )

        return FakeFrame(
            list(difference.elements()),
            self.columns_spec,
        )

    def createOrReplaceTempView(self, name):
        self.created_views.append(name)


class FakeSQLResult:

    def __init__(self, table_format="delta"):
        self.table_format = table_format

    def select(self, *columns):
        return self

    def first(self):
        return {
            "format": self.table_format
        }

    def collect(self):
        return []


def fake_spark(current=None, exists=True):

    return SimpleNamespace(
        catalog=SimpleNamespace(
            tableExists=Mock(
                return_value=exists
            ),
            dropTempView=Mock(),
        ),
        table=Mock(
            return_value=current
        ),
        sql=Mock(),
    )


def fake_summary():

    return {
        "distritos": 96,
        "colunas_totais": 252,
        "atributos_numericos": 249,
        "imoveis": {
            "bairros_aprovados": 93,
            "estoque_mapeado": 28085,
        },
        "observasampa_referencia": {},
        "observasampa_colunas": {},
        "ssp_colunas": {},
    }


STATUS_DIFFERENT = {
    "exists": True,
    "schema_equal": True,
    "identical": False,
}

STATUS_IDENTICAL = {
    "exists": True,
    "schema_equal": True,
    "identical": True,
}


# ============================================================
# 2. CONTRATOS DE ARQUITETURA
# ============================================================

class TestArchitecture(unittest.TestCase):

    def test_target(self):

        self.assertEqual(
            runner.TARGET,
            "workspace.gold.distritos_wide",
        )

    def test_district_count(self):

        self.assertEqual(
            runner.EXPECTED_DISTRICTS,
            96,
        )

    def test_sources(self):

        sources = [
            runner.IBGE,
            runner.GEO,
            runner.OBS,
            runner.SSP,
            runner.IMOVEIS,
            runner.DEPARA,
        ]

        self.assertEqual(
            len(sources),
            6,
        )

        self.assertEqual(
            len(set(sources)),
            6,
        )

        for source in sources:
            self.assertTrue(
                source.startswith(
                    "workspace.silver."
                )
            )

    def test_real_estate_fields(self):

        expected = (
            "imv_venda_estoque",
            "imv_aluguel_estoque",
            "imv_venda_novos",
            "imv_aluguel_novos",
            "imv_bairros_mapeados",
            "imv_metodo_localizacao",
        )

        self.assertEqual(
            runner.IMOVEIS_FEATURES,
            expected,
        )

    def test_no_temporal_real_estate_fields(self):

        prohibited = {
            "imv_mes_referencia",
            "imv_atualizado_em",
            "mes",
            "mes_referencia",
        }

        self.assertFalse(
            prohibited.intersection(
                runner.IMOVEIS_FEATURES
            )
        )

    def test_location_method(self):

        self.assertEqual(
            runner.METODO_IMOVEIS,
            "PROXY_OSM_HOMOLOGADO",
        )


# ============================================================
# 3. FUNCOES AUXILIARES
# ============================================================

class TestHelpers(unittest.TestCase):

    def test_require_accepts_true(self):

        self.assertIsNone(
            runner.require(
                True,
                "erro",
            )
        )

    def test_require_rejects_false(self):

        with self.assertRaises(
            runner.ContractError
        ):
            runner.require(
                False,
                "Contrato invalido",
            )

    def test_slug_deterministic(self):

        first = runner.slug(
            "População total",
            "obs",
        )

        second = runner.slug(
            "População total",
            "obs",
        )

        self.assertEqual(
            first,
            second,
        )

    def test_slug_accents(self):

        value = runner.slug(
            "População total",
            "obs",
        )

        self.assertTrue(
            value.startswith(
                "obs_populacao_total_"
            )
        )

    def test_slug_collision_protection(self):

        first = runner.slug(
            "Saúde",
            "obs",
        )

        second = runner.slug(
            "Saude",
            "obs",
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_slug_rejects_empty(self):

        with self.assertRaises(
            runner.ContractError
        ):
            runner.slug(
                "",
                "obs",
            )

    def test_ssp_partial_month(self):

        start, end = runner.month_window(
            date(2026, 11, 4)
        )

        self.assertEqual(
            start,
            date(2025, 11, 1),
        )

        self.assertEqual(
            end,
            date(2026, 10, 31),
        )

    def test_ssp_complete_month(self):

        start, end = runner.month_window(
            date(2026, 10, 31)
        )

        self.assertEqual(
            start,
            date(2025, 11, 1),
        )

        self.assertEqual(
            end,
            date(2026, 10, 31),
        )

    def test_missing_columns(self):

        frame = SimpleNamespace(
            columns=["CD_DIST"]
        )

        with self.assertRaises(
            runner.ContractError
        ):
            runner.require_columns(
                frame,
                [
                    "CD_DIST",
                    "NM_DIST",
                ],
                "Gold",
            )

    def test_same_schema(self):

        first = FakeFrame(
            [(1, 10.0)]
        )

        second = FakeFrame(
            [(2, 20.0)]
        )

        self.assertTrue(
            runner.same_schema(
                first,
                second,
            )
        )

    def test_different_schema(self):

        first = FakeFrame(
            [(1, 10.0)]
        )

        second = FakeFrame(
            [(1, 10)],
            [
                ("CD_DIST", "bigint"),
                ("valor", "bigint"),
            ],
        )

        self.assertFalse(
            runner.same_schema(
                first,
                second,
            )
        )

    def test_source_versions_unchanged(self):

        versions = {
            runner.IBGE: 3,
            runner.IMOVEIS: 8,
        }

        with patch.object(
            runner,
            "delta_version",
            side_effect=lambda spark, table: versions[table],
        ):

            result = runner.source_versions_unchanged(
                object(),
                versions,
            )

        self.assertTrue(result)

    def test_source_versions_changed(self):

        versions = {
            runner.IBGE: 3,
            runner.IMOVEIS: 8,
        }

        current = {
            runner.IBGE: 3,
            runner.IMOVEIS: 9,
        }

        with patch.object(
            runner,
            "delta_version",
            side_effect=lambda spark, table: current[table],
        ):

            result = runner.source_versions_unchanged(
                object(),
                versions,
            )

        self.assertFalse(result)

    def test_exact_codes_checks_both_directions(self):

        proposed = object()
        current = object()

        with (
            patch.object(
                runner,
                "check_districts",
            ) as check,
            patch.object(
                runner,
                "assert_same_codes",
            ) as compare,
        ):

            runner.assert_exact_codes(
                proposed,
                current,
            )

        self.assertEqual(
            check.call_count,
            2,
        )

        self.assertEqual(
            compare.call_count,
            2,
        )


# ============================================================
# 4. COMPARACAO DE SNAPSHOTS
# ============================================================

class TestGoldComparison(unittest.TestCase):

    def test_missing_target(self):

        proposed = FakeFrame([
            (1, 10.0)
        ])

        status = runner.target_status(
            fake_spark(
                exists=False
            ),
            proposed,
        )

        self.assertFalse(
            status["exists"]
        )

        self.assertFalse(
            status["identical"]
        )

    def test_identical_target(self):

        current = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        proposed = FakeFrame([
            (2, 20.0),
            (1, 10.0),
        ])

        status = runner.target_status(
            fake_spark(current),
            proposed,
        )

        self.assertTrue(
            status["schema_equal"]
        )

        self.assertTrue(
            status["identical"]
        )

    def test_value_difference(self):

        current = FakeFrame([
            (1, 10.0),
        ])

        proposed = FakeFrame([
            (1, 11.0),
        ])

        status = runner.target_status(
            fake_spark(current),
            proposed,
        )

        self.assertFalse(
            status["identical"]
        )

    def test_schema_difference(self):

        current = FakeFrame([
            (1, 10.0),
        ])

        proposed = FakeFrame(
            [(1, 10)],
            [
                ("CD_DIST", "bigint"),
                ("valor", "bigint"),
            ],
        )

        status = runner.target_status(
            fake_spark(current),
            proposed,
        )

        self.assertFalse(
            status["schema_equal"]
        )

    def test_missing_records(self):

        current = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        proposed = FakeFrame([
            (1, 10.0),
        ])

        status = runner.target_status(
            fake_spark(current),
            proposed,
        )

        self.assertFalse(
            status["identical"]
        )

    def test_duplicate_records(self):

        current = FakeFrame([
            (1, 10.0),
            (1, 10.0),
        ])

        proposed = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        status = runner.target_status(
            fake_spark(current),
            proposed,
        )

        self.assertFalse(
            status["identical"]
        )


# ============================================================
# 5. MODOS DE EXECUCAO
# ============================================================

class TestExecutionModes(unittest.TestCase):

    def setUp(self):

        self.spark = fake_spark(
            exists=True
        )

        self.proposed = object()
        self.summary = fake_summary()

    def run_execute(
        self,
        apply=False,
        update=False,
        status=None,
    ):

        if status is None:
            status = STATUS_DIFFERENT

        with (
            patch.object(
                runner,
                "delta_version",
                return_value=1,
            ),
            patch.object(
                runner,
                "build",
                return_value=(
                    self.proposed,
                    self.summary,
                ),
            ),
            patch.object(
                runner,
                "target_status",
                return_value=status,
            ),
            patch.object(
                runner,
                "source_versions_unchanged",
                return_value=True,
            ),
            patch.object(
                runner,
                "update_target",
                return_value={
                    "changed": True,
                    "version_before": 1,
                    "version_after": 2,
                },
            ) as mocked_update,
            patch.object(
                runner,
                "emit",
            ) as mocked_emit,
        ):

            result = runner.execute(
                self.spark,
                apply=apply,
                update=update,
            )

        return result, mocked_update, mocked_emit

    def test_check_is_read_only(self):

        result, mocked_update, events = (
            self.run_execute()
        )

        self.assertEqual(
            result["distritos"],
            96,
        )

        mocked_update.assert_not_called()
        self.spark.sql.assert_not_called()

        names = [
            call.args[0]
            for call in events.call_args_list
        ]

        self.assertIn(
            "GOLD_DISTRICTS_CHECK_SUCCESS",
            names,
        )

    def test_apply_rejects_existing_divergent_gold(self):

        with self.assertRaises(
            runner.ContractError
        ):
            self.run_execute(
                apply=True,
            )

        self.spark.sql.assert_not_called()

    def test_apply_identical_is_idempotent(self):

        result, mocked_update, events = (
            self.run_execute(
                apply=True,
                status=STATUS_IDENTICAL,
            )
        )

        self.assertEqual(
            result["distritos"],
            96,
        )

        mocked_update.assert_not_called()
        self.spark.sql.assert_not_called()

    def test_update_routes_to_protected_engine(self):

        result, mocked_update, events = (
            self.run_execute(
                update=True,
            )
        )

        self.assertEqual(
            result["distritos"],
            96,
        )

        mocked_update.assert_called_once()

        self.spark.sql.assert_not_called()

        names = [
            call.args[0]
            for call in events.call_args_list
        ]

        self.assertIn(
            "GOLD_UPDATE_RESULT",
            names,
        )

    def test_rejects_apply_and_update_together(self):

        with self.assertRaises(
            runner.ContractError
        ):
            runner.execute(
                self.spark,
                apply=True,
                update=True,
            )

        self.spark.sql.assert_not_called()

    def test_update_identical_does_not_publish(self):

        result, mocked_update, events = (
            self.run_execute(
                update=True,
                status=STATUS_IDENTICAL,
            )
        )

        mocked_update.assert_not_called()
        self.spark.sql.assert_not_called()

        self.assertEqual(
            result["distritos"],
            96,
        )


# ============================================================
# 6. MECANISMO DELTA UPDATE
# ============================================================

class TestDeltaUpdate(unittest.TestCase):

    def setUp(self):

        # Dados pequenos e sinteticos.
        # A integridade real dos 96 distritos ja foi
        # validada no Databricks.

        self.current = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        self.proposed = FakeFrame([
            (1, 11.0),
            (2, 22.0),
        ])

        self.spark = fake_spark(
            self.current,
            exists=True,
        )

        self.versions = {
            runner.IBGE: 3,
            runner.IMOVEIS: 8,
        }

        self.table_format = "delta"
        self.fail_merge = False
        self.sql_calls = []

        def execute_sql(statement):

            self.sql_calls.append(statement)

            if (
                self.fail_merge
                and statement.strip().upper().startswith(
                    "MERGE INTO"
                )
            ):
                raise RuntimeError(
                    "Falha simulada no MERGE"
                )

            return FakeSQLResult(
                self.table_format
            )

        self.spark.sql.side_effect = execute_sql

    def invoke_update(
        self,
        statuses=None,
        target_versions=None,
        source_checks=None,
    ):

        if statuses is None:
            statuses = [
                STATUS_DIFFERENT,
                STATUS_IDENTICAL,
            ]

        if target_versions is None:
            target_versions = [
                7, 7, 7, 8
            ]

        if source_checks is None:
            source_checks = [
                True, True
            ]

        self.codes_mock = Mock()

        self.version_mock = Mock(
            side_effect=target_versions
        )

        self.source_mock = Mock(
            side_effect=source_checks
        )

        self.status_mock = Mock(
            side_effect=statuses
        )

        with (
            patch.object(
                runner,
                "assert_exact_codes",
                self.codes_mock,
            ),
            patch.object(
                runner,
                "delta_version",
                self.version_mock,
            ),
            patch.object(
                runner,
                "source_versions_unchanged",
                self.source_mock,
            ),
            patch.object(
                runner,
                "target_status",
                self.status_mock,
            ),
            patch.object(
                runner,
                "emit",
            ) as self.emit_mock,
        ):

            return runner.update_target(
                self.spark,
                self.proposed,
                self.versions,
            )

    def merge_statements(self):

        return [
            statement
            for statement in self.sql_calls
            if statement.strip().upper().startswith(
                "MERGE INTO"
            )
        ]

    # --------------------------------------------------------
    # 6.1. CENARIO DE SUCESSO
    # --------------------------------------------------------

    def test_successful_update(self):

        result = self.invoke_update()

        self.assertTrue(
            result["changed"]
        )

        self.assertEqual(
            result["version_before"],
            7,
        )

        self.assertEqual(
            result["version_after"],
            8,
        )

        self.assertEqual(
            len(self.merge_statements()),
            1,
        )

        self.assertEqual(
            self.codes_mock.call_count,
            2,
        )

        self.assertEqual(
            self.status_mock.call_count,
            2,
        )

        self.assertEqual(
            self.source_mock.call_count,
            2,
        )

    def test_merge_only_updates_matching_districts(self):

        self.invoke_update()

        merge = self.merge_statements()[0]

        self.assertIn(
            f"MERGE INTO {runner.TARGET}",
            merge,
        )

        self.assertIn(
            "ON t.CD_DIST = s.CD_DIST",
            merge,
        )

        self.assertIn(
            "WHEN MATCHED",
            merge,
        )

        self.assertIn(
            "UPDATE SET",
            merge,
        )

        self.assertIn(
            "t.`valor` = s.`valor`",
            merge,
        )

        self.assertNotIn(
            "WHEN NOT MATCHED",
            merge.upper(),
        )

        self.assertNotIn(
            "DELETE",
            merge.upper(),
        )

        self.assertNotIn(
            "INSERT",
            merge.upper(),
        )

    def test_temporary_view_is_removed_after_success(self):

        self.invoke_update()

        self.assertEqual(
            len(self.proposed.created_views),
            1,
        )

        view = self.proposed.created_views[0]

        self.assertTrue(
            view.startswith(
                "bairroiq_gold_update_"
            )
        )

        self.spark.catalog.dropTempView.assert_called_once_with(
            view
        )

    # --------------------------------------------------------
    # 6.2. IDEMPOTENCIA
    # --------------------------------------------------------

    def test_identical_snapshot_does_not_merge(self):

        result = self.invoke_update(
            statuses=[
                STATUS_IDENTICAL
            ],
            target_versions=[
                7, 7
            ],
            source_checks=[
                True
            ],
        )

        self.assertFalse(
            result["changed"]
        )

        self.assertEqual(
            result["version_before"],
            7,
        )

        self.assertEqual(
            result["version_after"],
            7,
        )

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

        self.assertEqual(
            self.proposed.created_views,
            [],
        )

    # --------------------------------------------------------
    # 6.3. PROTECOES DE CONTRATO
    # --------------------------------------------------------

    def test_rejects_missing_target(self):

        self.spark.catalog.tableExists.return_value = False

        with self.assertRaises(
            runner.ContractError
        ):
            self.invoke_update()

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

    def test_rejects_different_schema(self):

        self.proposed = FakeFrame(
            [
                (1, 11),
                (2, 22),
            ],
            [
                ("CD_DIST", "bigint"),
                ("valor", "bigint"),
            ],
        )

        with self.assertRaisesRegex(
            runner.ContractError,
            "schema diferente",
        ):
            self.invoke_update()

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

    def test_rejects_non_delta_target(self):

        self.table_format = "parquet"

        with self.assertRaisesRegex(
            runner.ContractError,
            "Delta Lake",
        ):
            self.invoke_update()

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

    # --------------------------------------------------------
    # 6.4. CONTROLE DE VERSOES
    # --------------------------------------------------------

    def test_rejects_changed_source(self):

        with self.assertRaisesRegex(
            runner.ContractError,
            "Fonte Silver mudou",
        ):
            self.invoke_update(
                target_versions=[7],
                source_checks=[False],
            )

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

    def test_rejects_target_version_change(self):

        with self.assertRaisesRegex(
            runner.ContractError,
            "Gold mudou",
        ):
            self.invoke_update(
                target_versions=[
                    7, 8
                ],
                source_checks=[
                    True
                ],
            )

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

    def test_rejects_source_change_before_merge(self):

        with self.assertRaisesRegex(
            runner.ContractError,
            "Fonte Silver mudou",
        ):
            self.invoke_update(
                target_versions=[
                    7, 7
                ],
                source_checks=[
                    True, False
                ],
            )

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

        self.spark.catalog.dropTempView.assert_called_once()

    def test_rejects_target_change_before_merge(self):

        with self.assertRaisesRegex(
            runner.ContractError,
            "Gold mudou",
        ):
            self.invoke_update(
                target_versions=[
                    7, 7, 8
                ],
                source_checks=[
                    True, True
                ],
            )

        self.assertEqual(
            len(self.merge_statements()),
            0,
        )

        self.spark.catalog.dropTempView.assert_called_once()

    # --------------------------------------------------------
    # 6.5. FALHAS E AUDITORIA
    # --------------------------------------------------------

    def test_merge_failure_cleans_temporary_view(self):

        self.fail_merge = True

        with self.assertRaisesRegex(
            RuntimeError,
            "Falha simulada no MERGE",
        ):
            self.invoke_update(
                target_versions=[
                    7, 7, 7
                ],
                statuses=[
                    STATUS_DIFFERENT
                ],
            )

        self.assertEqual(
            len(self.merge_statements()),
            1,
        )

        self.spark.catalog.dropTempView.assert_called_once()

    def test_rejects_failed_post_publication_audit(self):

        with self.assertRaisesRegex(
            runner.ContractError,
            "diverge da proposta",
        ):
            self.invoke_update(
                target_versions=[
                    7, 7, 7
                ],
                statuses=[
                    STATUS_DIFFERENT,
                    STATUS_DIFFERENT,
                ],
            )

        # A gravacao foi tentada, mas a auditoria
        # rejeitou o resultado. Exige verificacao
        # manual antes de qualquer reexecucao.

        self.assertEqual(
            len(self.merge_statements()),
            1,
        )

        self.spark.catalog.dropTempView.assert_called_once()

    def test_rejects_unchanged_delta_version_after_merge(self):

        with self.assertRaisesRegex(
            runner.ContractError,
            "nova versao Delta",
        ):
            self.invoke_update(
                target_versions=[
                    7, 7, 7, 7
                ],
            )

        self.assertEqual(
            len(self.merge_statements()),
            1,
        )

    def test_exact_codes_are_checked_before_and_after(self):

        self.invoke_update()

        self.assertEqual(
            self.codes_mock.call_count,
            2,
        )

    def test_target_compared_before_and_after(self):

        self.invoke_update()

        self.assertEqual(
            self.status_mock.call_count,
            2,
        )


# ============================================================
# 7. EXECUCAO
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
