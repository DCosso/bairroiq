
"""BairroIQ | Testes da Silver ObservaSampa sem Spark real.

Execucao:
python -m unittest discover -s tests \
  -p "test_silver_observasampa_runner.py" -v
"""

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from barrioiq_pipeline import silver_observasampa_runner as runner


def fixtures():
    reference = []
    regions = []

    for i in range(96):
        name = (
            "Água Rasa" if i == 0
            else "São Mateus" if i == 1
            else f"Distrito {i:02}"
        )

        reference.append({
            "CD_DIST": 355030801 + i,
            "NM_DIST": name,
        })

        normalized = (
            "Agua Rasa" if i == 0
            else "Sao Mateus" if i == 1
            else name
        )

        regions.append({
            "regiao": f"{normalized} (Distrito)",
        })

    return reference, regions


class TestNormalization(TestCase):

    def test_names_accents(self):
        self.assertEqual(
            runner.normalizar(" São  Mateus "),
            "SAO MATEUS",
        )

        self.assertEqual(
            runner.normalizar("A\u0301gua Rasa"),
            "AGUA RASA",
        )

    def test_invalid_name(self):
        self.assertIsNone(runner.normalizar(None))
        self.assertIsNone(runner.normalizar(" � "))

    def test_district_suffix(self):
        self.assertEqual(
            runner.nome_distrito(
                "Água Rasa (Distrito)"
            ),
            "Água Rasa",
        )

        self.assertEqual(
            runner.nome_distrito(
                " Sao Mateus (distrito) "
            ),
            "Sao Mateus",
        )

        self.assertIsNone(
            runner.nome_distrito(
                "Sao Mateus (Subprefeitura)"
            )
        )

    def test_district_ref_exact(self):
        ref, regions = fixtures()

        mapping = runner.build_reference(
            ref, regions
        )

        self.assertEqual(len(mapping), 96)

        self.assertEqual(
            mapping[0],
            (
                "Agua Rasa (Distrito)",
                355030801,
                "Água Rasa",
            ),
        )

    def test_reject_95_districts(self):
        ref, regions = fixtures()

        with self.assertRaisesRegex(
            runner.ContractError,
            "96 distritos",
        ):
            runner.build_reference(
                ref, regions[:-1]
            )

    def test_reject_duplicate_reference_code(self):
        ref, regions = fixtures()

        ref[1]["CD_DIST"] = ref[0]["CD_DIST"]

        with self.assertRaises(
            runner.ContractError
        ):
            runner.build_reference(
                ref, regions
            )

    def test_reject_duplicate_reference_name(self):
        ref, regions = fixtures()

        ref[1]["NM_DIST"] = ref[0]["NM_DIST"]

        with self.assertRaises(
            runner.ContractError
        ):
            runner.build_reference(
                ref, regions
            )

    def test_reject_duplicate_region(self):
        ref, regions = fixtures()

        regions[1]["regiao"] = (
            "Água Rasa (Distrito)"
        )

        with self.assertRaises(
            runner.ContractError
        ):
            runner.build_reference(
                ref, regions
            )

    def test_reject_unknown_territory(self):
        ref, regions = fixtures()

        regions[0]["regiao"] = (
            "Distrito inventado (Distrito)"
        )

        with self.assertRaisesRegex(
            runner.ContractError,
            "sem correspondencia",
        ):
            runner.build_reference(
                ref, regions
            )

    def test_reject_subprefeitura(self):
        ref, regions = fixtures()

        regions[0]["regiao"] = (
            "Água Rasa (Subprefeitura)"
        )

        with self.assertRaisesRegex(
            runner.ContractError,
            "nao distrital",
        ):
            runner.build_reference(
                ref, regions
            )


class TestValues(TestCase):

    def test_integer_employment_2021(self):
        self.assertEqual(
            runner.parse_numeric("106896"),
            (Decimal("106896"), "OK"),
        )

    def test_decimal_led_2024(self):
        self.assertEqual(
            runner.parse_numeric("92,8119"),
            (Decimal("92.8119"), "OK"),
        )

        self.assertEqual(
            runner.parse_numeric("100"),
            (Decimal("100"), "OK"),
        )

    def test_negative_values_supported(self):
        self.assertEqual(
            runner.parse_numeric("-3,5"),
            (Decimal("-3.5"), "OK"),
        )

    def test_reject_ambiguous_thousands(self):
        self.assertEqual(
            runner.parse_numeric("1.234"),
            (None, "AMBIGUO"),
        )

        self.assertEqual(
            runner.parse_numeric("1,234"),
            (None, "AMBIGUO"),
        )

    def test_reject_mixed_separators(self):
        self.assertEqual(
            runner.parse_numeric("1.234,56"),
            (None, "FORMATO_INVALIDO"),
        )

    def test_empty_and_non_numeric(self):
        self.assertEqual(
            runner.parse_numeric(""),
            (None, "VAZIO"),
        )

        self.assertEqual(
            runner.parse_numeric(None),
            (None, "VAZIO"),
        )

        self.assertEqual(
            runner.parse_numeric("n/d"),
            (None, "FORMATO_INVALIDO"),
        )


class TestSafety(TestCase):

    def test_output_schema_and_sources(self):
        self.assertEqual(
            runner.SOURCE,
            "workspace.bronze.observa_sampa",
        )

        self.assertEqual(
            runner.REFERENCE,
            "workspace.silver.geosampa_equipamentos_distrito",
        )

        self.assertEqual(
            len(set(runner.OUTPUT_COLUMNS)),
            len(runner.OUTPUT_COLUMNS),
        )

        self.assertIn(
            "valor_numerico",
            runner.OUTPUT_COLUMNS,
        )

        self.assertIn(
            "ano",
            runner.OUTPUT_COLUMNS,
        )

    def test_requires_confirmation(self):
        with self.assertRaises(
            SystemExit
        ) as caught:
            runner.main(["--apply"])

        self.assertEqual(
            caught.exception.code, 2
        )

    def test_no_confirm_on_check(self):
        with self.assertRaises(
            SystemExit
        ) as caught:
            runner.main([
                "--check",
                "--confirm-publish",
            ])

        self.assertEqual(
            caught.exception.code, 2
        )

    def test_mutually_exclusive(self):
        with self.assertRaises(
            SystemExit
        ) as caught:
            runner.main([
                "--check",
                "--apply",
                "--confirm-publish",
            ])

        self.assertEqual(
            caught.exception.code, 2
        )

    def test_execute_check_does_not_write(self):

        class DummySpark:
            catalog = SimpleNamespace(
                tableExists=lambda _: False
            )

        expected = {
            "rows": 134567,
            "districts": 96,
            "indicators": 104,
        }

        with (
            patch.object(
                runner,
                "version",
                side_effect=[43, 0],
            ),
            patch.object(
                runner,
                "build",
                return_value=(object(), expected),
            ),
            patch.object(
                runner,
                "emit",
            ) as emit,
        ):
            summary = runner.execute(
                DummySpark(),
                apply=False,
            )

        self.assertEqual(summary, expected)

        self.assertEqual(
            emit.call_args_list[-1].args[0],
            "OBSERVASAMPA_SILVER_CHECK_SUCCESS",
        )

    def test_apply_blocks_existing_different_table(self):

        class DummySpark:
            catalog = SimpleNamespace(
                tableExists=lambda _: True
            )

        expected = {
            "rows": 134567,
            "districts": 96,
            "indicators": 104,
        }

        with (
            patch.object(
                runner,
                "version",
                side_effect=[43, 0],
            ),
            patch.object(
                runner,
                "build",
                return_value=(object(), expected),
            ),
            patch.object(
                runner,
                "equal_target",
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(
                runner.ContractError,
                "divergentes",
            ):
                runner.execute(
                    DummySpark(),
                    apply=True,
                )


if __name__ == "__main__":
    main(verbosity=2)
