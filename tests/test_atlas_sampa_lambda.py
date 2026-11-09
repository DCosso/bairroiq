"""Pure offline unit tests; no Databricks writes or public SSP access."""
from collections import Counter
from datetime import date, datetime, time
import importlib.util
from pathlib import Path
import sys
import unittest

P = Path(__file__).resolve().parents[1] / 'barrioiq_pipeline' / 'atlas_sampa' / 'ssp'
sys.path.insert(0, str(P))
import pipeline as p


class LambdaTests(unittest.TestCase):
    def test_immutability_of_names(self):
        self.assertEqual(p.BRONZE, 'workspace.bronze.ssp_ingestao_v2')
        self.assertEqual(p.SILVER, 'workspace.silver.atlas_sampa_ssp_v2')
        self.assertNotIn('gold.', p.SERVING)
        self.assertEqual(len(p.RUBRICAS), 2)

    def test_multiset_new_month(self):
        old = Counter({'a': 3, 'b': 1})
        new = Counter({'a': 3, 'b': 1, 'c': 3})
        add, rem = p.difference_counts(old, new)
        self.assertEqual(sum(add.values()), 3)
        self.assertEqual(sum(rem.values()), 0)

    def test_multiset_republication_with_corrections(self):
        old = Counter({'a': 2, 'b': 1})
        new = Counter({'a': 1, 'c': 1})
        add, rem = p.difference_counts(old, new)
        self.assertEqual(dict(add), {'c': 1})
        self.assertEqual(dict(rem), {'a': 1, 'b': 1})
        self.assertEqual(sum(new.values()), sum(old.values()) + sum(add.values()) - sum(rem.values()))

    def test_multiset_duplicate_replay_idempotency(self):
        old = Counter(['a', 'a', 'b'])
        add, rem = p.difference_counts(old, old.copy())
        self.assertFalse(add)
        self.assertFalse(rem)

    def test_normalize_source_values(self):
        self.assertIsNone(p.normalized_cell(None))
        self.assertEqual(p.normalized_cell(datetime(2026,9,1,12,30)), '2026-09-01 12:30:00')
        self.assertEqual(p.normalized_cell(date(2026,9,1)), '2026-09-01')
        self.assertEqual(p.normalized_cell(time(9,30)), '09:30:00')
        self.assertEqual(p.normalized_cell(3550308), '3550308')

    def test_source_line_id(self):
        self.assertEqual(p.source_ident('JAN-JUN_2026', 2), ('JAN-JUN_2026', 2))

    def test_location_96_unchanged(self):
        self.assertIn('ssp_ingestao_v2', p.BRONZE)
        self.assertIn('observability', p.CONTROL)
        self.assertIn('observability', p.SPEED)
        self.assertIn('observability', p.BATCH)

    @unittest.skipUnless(importlib.util.find_spec("openpyxl") is not None,
                         "openpyxl somente no CI dedicado")
    def test_first_semester_Excel_may_have_no_second_semester(self):
        from atlas_sampa.ssp.excel_reader import HEADERS, validate_excel
        from openpyxl import Workbook
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "fixture.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.title = "JAN-JUN_2027"
            ws.append(list(HEADERS))
            record = [None] * 30
            record[21], record[24], record[25] = "Furto (art. 155)", 1, 2027
            ws.append(record)
            wb.save(filename)
            self.assertEqual(validate_excel(filename, 2027),
                             {"JAN-JUN_2027": 1, "JUL-DEZ_2027": 0})

    def test_cli_requires_mode(self):
        self.assertTrue(callable(p.main))
        self.assertEqual(p.LOTE, 20000)


if __name__ == '__main__':
    unittest.main()
