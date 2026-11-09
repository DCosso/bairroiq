"""Reader/contract guard for the SSP monthly Excel, including first-half years.

Verifies all nonempty rows and extra columns without materializing the workbook.
A future second-semester sheet may be absent or empty before publication.
"""
from __future__ import annotations

from pathlib import Path

HEADERS = (
    "NOME_DEPARTAMENTO", "NOME_SECCIONAL", "NOME_DELEGACIA", "NOME_MUNICIPIO",
    "NUM_BO", "ANO_BO", "DATA_REGISTRO", "DATA_OCORRENCIA_BO",
    "HORA_OCORRENCIA_BO", "DESC_PERIODO", "DESCR_TIPOLOCAL",
    "DESCR_SUBTIPOLOCAL", "BAIRRO", "LOGRADOURO", "NUMERO_LOGRADOURO",
    "LATITUDE", "LONGITUDE", "NOME_DELEGACIA_CIRCUNSCRICAO",
    "NOME_DEPARTAMENTO_CIRCUNSCRICAO", "NOME_SECCIONAL_CIRCUNSCRICAO",
    "NOME_MUNICIPIO_CIRCUNSCRICAO", "RUBRICA", "DESCR_CONDUTA",
    "NATUREZA_APURADA", "MES_ESTATISTICA", "ANO_ESTATISTICA",
    "CMD", "BTL", "CIA", "COD IBGE",
)


def validate_excel(path: str | Path, year: int) -> dict[str, int]:
    from openpyxl import load_workbook

    if not 2020 <= year <= 2100:
        raise ValueError("Ano fora da faixa suportada")
    first_sheet, second_sheet = f"JAN-JUN_{year}", f"JUL-DEZ_{year}"
    wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    try:
        if first_sheet not in wb.sheetnames:
            raise ValueError(f"Aba esperada ausente: {first_sheet}")
        result: dict[str, int] = {}
        for sheet in (first_sheet, second_sheet):
            if sheet not in wb.sheetnames:
                result[sheet] = 0
                continue
            ws = wb[sheet]
            first = next(ws.iter_rows(min_row=1, max_row=1, max_col=30, values_only=True))
            if tuple(first) != HEADERS:
                raise ValueError(f"Cabeçalho de 30 colunas divergente: {sheet}")
            rows, max_col = 0, max(ws.max_column or 30, 30)
            for row_number, values in enumerate(ws.iter_rows(min_row=2, max_col=max_col, values_only=True), start=2):
                fields, extras = values[:30], values[30:]
                if any(x is not None and str(x).strip() for x in extras):
                    raise ValueError(f"Colunas extras preenchidas em {sheet}, linha {row_number}")
                if all(x is None or (isinstance(x, str) and not x.strip()) for x in fields):
                    continue
                rows += 1
            if sheet == first_sheet and rows == 0:
                raise ValueError(f"Aba de dados vazia: {sheet}")
            result[sheet] = rows
        return result
    finally:
        wb.close()
