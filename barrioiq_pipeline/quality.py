
"""Regras de qualidade do BarrioIQ - testes sintéticos."""

import math
from collections import defaultdict


class DataQualityError(ValueError):
    pass


REQUIRED_FIELDS = (
    "codigo_area",
    "distrito",
    "populacao",
    "renda_media",
)


def profile_bronze(rows):
    """Gera indicadores sem rejeitar dados brutos."""
    rows = list(rows)
    keys = [
        row.get("codigo_area")
        for row in rows
        if row.get("codigo_area") not in (None, "")
    ]

    return {
        "total_records": len(rows),
        "missing_keys": len(rows) - len(keys),
        "duplicate_keys": len(keys) - len(set(keys)),
    }


def validate_silver(rows):
    """Reprova registros inválidos na camada Silver."""
    rows = list(rows)
    seen = set()
    errors = []

    for index, row in enumerate(rows, start=1):
        missing = [
            field for field in REQUIRED_FIELDS
            if row.get(field) in (None, "")
        ]

        if missing:
            errors.append(
                f"Row {index}: missing {missing}"
            )
            continue

        key = row["codigo_area"]

        if key in seen:
            errors.append(f"Row {index}: duplicate key {key}")
        seen.add(key)

        population = row["populacao"]
        income = row["renda_media"]

        if (
            isinstance(population, bool)
            or not isinstance(population, (int, float))
            or not math.isfinite(population)
            or population < 0
            or not float(population).is_integer()
        ):
            errors.append(f"Row {index}: invalid population")

        if (
            isinstance(income, bool)
            or not isinstance(income, (int, float))
            or not math.isfinite(income)
            or income < 0
        ):
            errors.append(f"Row {index}: invalid income")

    if errors:
        raise DataQualityError("; ".join(errors))

    return rows


def summarize_gold(rows):
    """Agrega dados válidos por distrito."""
    rows = validate_silver(rows)
    groups = defaultdict(
        lambda: {"areas": 0, "population": 0}
    )

    for row in rows:
        district = row["distrito"]
        groups[district]["areas"] += 1
        groups[district]["population"] += row["populacao"]

    return dict(groups)
