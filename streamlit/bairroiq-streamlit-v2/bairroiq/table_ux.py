"""Tabelas acessíveis, responsivas e independentes do renderer de grids."""
from __future__ import annotations

from html import escape
from collections.abc import Mapping

import pandas as pd
import streamlit as st


def render_responsive_table(
    frame: pd.DataFrame,
    *,
    precision: int = 1,
    column_precision: Mapping[str, int] | None = None,
    label: str = "Tabela de dados",
) -> None:
    """Renderiza HTML seguro. Nunca usa CSS de tabela branca no modo escuro."""
    overrides = column_precision or {}
    headings = "".join(f'<th scope="col">{escape(str(c))}</th>' for c in frame.columns)
    rows: list[str] = []
    for values in frame.itertuples(index=False, name=None):
        cells = []
        for column, value in zip(frame.columns, values):
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if pd.isna(value):
                display = "Indisponível"
            elif numeric:
                display = f"{float(value):,.{overrides.get(str(column), precision)}f}"
            else:
                display = str(value)
            cells.append(
                f'<td class="{"num" if numeric else "label"}">{escape(display)}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    html = (
        '<div class="atlas-data-table-wrap" role="region" aria-label="'
        + escape(label, quote=True)
        + '" tabindex="0"><table class="atlas-data-table"><thead><tr>'
        + headings + '</tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
