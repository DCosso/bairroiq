"""Validação estrita, em streaming, do Excel SSP-SP.

Não faz transformação, deduplicação ou escrita no Lakehouse.
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
    """Confere planilha e percorre registros, sem materializar DataFrame.

    Retorna contagens reais de linhas não vazias de cada aba. Não presume que
    max_row implica uma ocorrência válida. Falha para campos extras preenchidos.
    """
    from openpyxl import load_workbook

    if not 2020 <= year <= 2100:
        raise ValueError("Ano fora da faixa suportada")

    expected_sheets = (f"JAN-JUN_{year}", f"JUL-DEZ_{year}")
    workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
    try:
        result: dict[str, int] = {}
        for sheet_name in expected_sheets:
            if sheet_name not in workbook.sheetnames:
                raise ValueError(f"Aba esperada ausente: {sheet_name}")
            ws = workbook[sheet_name]
            first = next(ws.iter_rows(min_row=1, max_row=1, max_col=30, values_only=True))
            if tuple(first) != HEADERS:
                raise ValueError(f"Cabeçalho de 30 colunas divergente: {sheet_name}")

            rows = 0
            max_col = max(ws.max_column or 30, 30)
            for row_number, values in enumerate(
                ws.iter_rows(min_row=2, max_col=max_col, values_only=True), start=2
            ):
                fields = values[:30]
                extras = values[30:]
                if any(x is not None and str(x).strip() for x in extras):
                    raise ValueError(
                        f"Colunas extras preenchidas em {sheet_name}, linha {row_number}"
                    )
                if all(x is None or (isinstance(x, str) and not x.strip()) for x in fields):
                    continue
                rows += 1
            if rows == 0:
                raise ValueError(f"Aba de dados vazia: {sheet_name}")
            result[sheet_name] = rows
        return result
    finally:
        workbook.close()
