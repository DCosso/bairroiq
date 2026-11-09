"""Testes offline do coletor SSP-SP; não acessam rede nem Databricks."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PIPELINE = Path(__file__).resolve().parents[1] / "barrioiq_pipeline"
sys.path.insert(0, str(PIPELINE))

from atlas_sampa.ssp.collector import (
    apply_collection, check_remote, save_version, source_url,
)
from atlas_sampa.ssp.excel_reader import HEADERS, validate_excel

OPENPYXL_AVAILABLE = importlib.util.find_spec("openpyxl") is not None


class FakeResponse(io.BytesIO):
    status = 200

    def __init__(self, data: bytes, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        super().__init__(data)
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "ETag": '"fixture123"',
            "Last-Modified": "Sun, 08 Nov 2026 23:00:00 GMT",
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class URLTests(unittest.TestCase):
    def test_url_2026(self):
        self.assertEqual(
            source_url(2026),
            "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_2026.xlsx",
        )

    def test_refuse_invalid_year(self):
        with self.assertRaises(ValueError):
            source_url(0)

    def test_check_is_read_only(self):
        mock_head = FakeResponse(b"")
        with patch("atlas_sampa.ssp.collector.urlopen", return_value=mock_head) as requester:
            data = check_remote(2026)
        self.assertEqual(data["etag"], '"fixture123"')
        self.assertFalse(data["publicado"])
        self.assertEqual(requester.call_args.args[0].get_method(), "HEAD")


@unittest.skipUnless(OPENPYXL_AVAILABLE, "openpyxl é instalado no CI dedicado")
class WorkbookTests(unittest.TestCase):
    @staticmethod
    def sample_excel(path: Path, extra=False, invalid_header=False):
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        wb.create_sheet("Campos da Tabela_SPDADOS")
        for sheet_name in ("JAN-JUN_2026", "JUL-DEZ_2026"):
            ws = wb.create_sheet(sheet_name)
            headers = list(HEADERS)
            if invalid_header:
                headers[0] = "OUTRA_COLUNA"
            ws.append(headers)
            record = [None] * 30
            record[4] = "AB1234"
            record[21] = "Furto (art. 155)"
            record[24] = 1 if "JAN" in sheet_name else 7
            record[25] = 2026
            ws.append(record)
            if extra:
                ws.cell(row=2, column=31, value="DADO EXTRA")
        wb.save(path)

    def test_validate_and_count(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.xlsx"
            self.sample_excel(p)
            self.assertEqual(validate_excel(p, 2026), {
                "JAN-JUN_2026": 1,
                "JUL-DEZ_2026": 1,
            })

    def test_extra_column_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.xlsx"
            self.sample_excel(p, extra=True)
            with self.assertRaisesRegex(ValueError, "Colunas extras"):
                validate_excel(p, 2026)

    def test_header_changed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.xlsx"
            self.sample_excel(p, invalid_header=True)
            with self.assertRaisesRegex(ValueError, "Cabeçalho"):
                validate_excel(p, 2026)

    def test_get_and_idempotency(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = root / "raw"
            raw.mkdir()
            fixture = root / "fixture.xlsx"
            self.sample_excel(fixture)
            contents = fixture.read_bytes()
            digest = hashlib.sha256(contents).hexdigest()
            with patch("atlas_sampa.ssp.collector.urlopen", side_effect=lambda *a, **kw: FakeResponse(contents)):
                first = apply_collection(2026, raw=raw)
                second = apply_collection(2026, raw=raw)
            self.assertEqual(first["status"], "NOVA_VERSAO_INGERIDA")
            self.assertEqual(second["status"], "VERSAO_JA_EXISTENTE")
            self.assertEqual(first["sha256"], digest)
            self.assertEqual(first["total_rows"], 2)
            self.assertEqual(len(list((raw / "versions" / "2026").glob("*.xlsx"))), 1)
            self.assertEqual(len(list((raw / "versions" / "2026").glob("*.json"))), 1)

    def test_bad_file_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = root / "raw"
            raw.mkdir()
            with patch("atlas_sampa.ssp.collector.urlopen", side_effect=lambda *a, **kw: FakeResponse(b"not-zip")):
                with self.assertRaisesRegex(RuntimeError, "XLSX/ZIP"):
                    apply_collection(2026, raw=raw)
            self.assertFalse((raw / "versions").exists())

    def test_existing_corruption_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = root / "raw"
            raw.mkdir()
            fixture = root / "f.xlsx"
            self.sample_excel(fixture)
            digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
            target = raw / "versions" / "2026" / f"{digest}.xlsx"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"bad existing file")
            with self.assertRaisesRegex(RuntimeError, "hash divergente"):
                save_version(fixture, raw, 2026, digest, {"JAN-JUN_2026": 1}, {})


if __name__ == "__main__":
    unittest.main()
