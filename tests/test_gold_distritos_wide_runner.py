
"""
BairroIQ | Testes unitarios Gold Distritos Wide v2

Executar na raiz do repositorio:

python -m unittest discover \
    -s tests \
    -p "test_gold_distritos_wide_runner.py" \
    -v

Nao requer PySpark nem conexao com Databricks.
Nao modifica tabelas ou arquivos externos.
"""

import unittest
from collections import Counter
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from barrioiq_pipeline import gold_distritos_wide_runner as runner


# ============================================================
# 1. SIMULADORES LOCAIS
# ============================================================

class FakeType:

    def __init__(self, value):
        self.value = value

    def simpleString(self):
        return self.value


class FakeFrame:

    def __init__(self, rows, columns=None):
        self.rows = list(rows)

        if columns is None:
            columns = [
                ("CD_DIST", "bigint"),
                ("valor", "double"),
            ]

        self.columns_spec = columns

        self.schema = [
            SimpleNamespace(
                name=name,
                dataType=FakeType(dtype),
            )
            for name, dtype in columns
        ]

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


def fake_spark(current=None, exists=True):

    return SimpleNamespace(
        catalog=SimpleNamespace(
            tableExists=Mock(
                return_value=exists
            )
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


# ============================================================
# 2. CONTRATOS DE ARQUITETURA
# ============================================================

class TestArchitecture(unittest.TestCase):

    def test_target_is_existing_wide(self):
        self.assertEqual(
            runner.TARGET,
            "workspace.gold.distritos_wide",
        )

    def test_expected_districts(self):
        self.assertEqual(
            runner.EXPECTED_DISTRICTS,
            96,
        )

    def test_all_six_sources_are_defined(self):

        sources = [
            runner.IBGE,
            runner.GEO,
            runner.OBS,
            runner.SSP,
            runner.IMOVEIS,
            runner.DEPARA,
        ]

        self.assertEqual(len(sources), 6)
        self.assertEqual(len(set(sources)), 6)

        for source in sources:
            self.assertTrue(
                source.startswith("workspace.silver.")
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

    def test_no_temporal_fields(self):

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

    def test_require_accepts_valid_condition(self):
        self.assertIsNone(
            runner.require(True, "erro")
        )

    def test_require_rejects_invalid_condition(self):

        with self.assertRaises(
            runner.ContractError
        ):
            runner.require(
                False,
                "Contrato invalido",
            )

    def test_slug_is_deterministic(self):

        first = runner.slug(
            "População total",
            "obs",
        )

        second = runner.slug(
            "População total",
            "obs",
        )

        self.assertEqual(first, second)
        self.assertTrue(
            first.startswith("obs_populacao_total_")
        )

    def test_slug_avoids_collision(self):

        a = runner.slug("Saúde", "obs")
        b = runner.slug("Saude", "obs")

        self.assertNotEqual(a, b)

    def test_slug_rejects_empty_name(self):

        with self.assertRaises(
            runner.ContractError
        ):
            runner.slug("", "obs")

    def test_ssp_window_partial_month(self):

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

    def test_ssp_window_complete_month(self):

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

    def test_missing_columns_are_rejected(self):

        frame = SimpleNamespace(
            columns=["CD_DIST"]
        )

        with self.assertRaises(
            runner.ContractError
        ):
            runner.require_columns(
                frame,
                ["CD_DIST", "NM_DIST"],
                "Gold",
            )


# ============================================================
# 4. COMPARACAO DA GOLD
# ============================================================

class TestGoldComparison(unittest.TestCase):

    def test_missing_target(self):

        proposed = FakeFrame([(1, 10.0)])

        status = runner.target_status(
            fake_spark(exists=False),
            proposed,
        )

        self.assertFalse(status["exists"])
        self.assertFalse(status["identical"])

    def test_identical_target(self):

        original = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        proposed = FakeFrame([
            (2, 20.0),
            (1, 10.0),
        ])

        status = runner.target_status(
            fake_spark(original),
            proposed,
        )

        self.assertTrue(status["exists"])
        self.assertTrue(status["schema_equal"])
        self.assertTrue(status["identical"])

    def test_detects_value_difference(self):

        original = FakeFrame([
            (1, 10.0),
        ])

        proposed = FakeFrame([
            (1, 11.0),
        ])

        status = runner.target_status(
            fake_spark(original),
            proposed,
        )

        self.assertFalse(status["identical"])

    def test_detects_schema_difference(self):

        original = FakeFrame(
            [(1, 10.0)],
            [
                ("CD_DIST", "bigint"),
                ("valor", "double"),
            ],
        )

        proposed = FakeFrame(
            [(1, 10)],
            [
                ("CD_DIST", "bigint"),
                ("valor", "bigint"),
            ],
        )

        status = runner.target_status(
            fake_spark(original),
            proposed,
        )

        self.assertFalse(status["schema_equal"])
        self.assertFalse(status["identical"])

    def test_detects_missing_rows(self):

        original = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        proposed = FakeFrame([
            (1, 10.0),
        ])

        status = runner.target_status(
            fake_spark(original),
            proposed,
        )

        self.assertFalse(status["identical"])

    def test_detects_duplicate_rows(self):

        original = FakeFrame([
            (1, 10.0),
            (1, 10.0),
        ])

        proposed = FakeFrame([
            (1, 10.0),
            (2, 20.0),
        ])

        status = runner.target_status(
            fake_spark(original),
            proposed,
        )

        self.assertFalse(status["identical"])


# ============================================================
# 5. SEGURANCA DE PUBLICACAO
# ============================================================

class TestPublicationSafety(unittest.TestCase):

    def setUp(self):

        self.spark = fake_spark(
            exists=True
        )

        self.proposed = object()
        self.summary = fake_summary()

    def run_mocked(self, apply, target_status):

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
                return_value=target_status,
            ),
            patch.object(
                runner,
                "emit",
            ) as mock_emit,
        ):

            result = runner.execute(
                self.spark,
                apply=apply,
            )

            return result, mock_emit

    def test_check_does_not_publish(self):

        status = {
            "exists": True,
            "schema_equal": True,
            "identical": False,
        }

        result, events = self.run_mocked(
            apply=False,
            target_status=status,
        )

        self.assertEqual(
            result["distritos"],
            96,
        )

        self.spark.sql.assert_not_called()

        event_names = [
            call.args[0]
            for call in events.call_args_list
        ]

        self.assertIn(
            "GOLD_DISTRICTS_CHECK_SUCCESS",
            event_names,
        )

    def test_apply_rejects_divergent_existing_gold(self):

        status = {
            "exists": True,
            "schema_equal": True,
            "identical": False,
        }

        with self.assertRaises(
            runner.ContractError
        ):
            self.run_mocked(
                apply=True,
                target_status=status,
            )

        self.spark.sql.assert_not_called()

    def test_apply_identical_is_idempotent(self):

        status = {
            "exists": True,
            "schema_equal": True,
            "identical": True,
        }

        result, events = self.run_mocked(
            apply=True,
            target_status=status,
        )

        self.assertEqual(
            result["distritos"],
            96,
        )

        self.spark.sql.assert_not_called()

        event_names = [
            call.args[0]
            for call in events.call_args_list
        ]

        self.assertIn(
            "GOLD_DISTRICTS_UNCHANGED",
            event_names,
        )


# ============================================================
# 6. EXECUCAO
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
