"""Compatibilidade entre o seletor superior e a página Comparar (0 a 10)."""
from __future__ import annotations
from collections.abc import Sequence


def reconcile_selection(
    header_names: Sequence[str] | None,
    page_names: Sequence[str] | None,
    eligible_names: Sequence[str],
    max_items: int = 10,
) -> list[str]:
    """Recupera itens cortados no callback legado somente quando seguro.

    A sincronização antiga copiava no máximo cinco itens da barra superior.
    Se a seleção da página é exatamente o prefixo da barra, a barra é a
    origem autoritativa. Caso contrário, preserva a seleção explícita da página.
    Em qualquer caso remove nomes inelegíveis ou duplicados e limita a dez.
    """
    header = list(dict.fromkeys(header_names or []))
    page = list(dict.fromkeys(page_names or []))
    if header and len(header) > len(page) and page == header[: len(page)]:
        result = header
    else:
        result = page
    eligible = set(eligible_names)
    return [name for name in result if name in eligible][:max_items]
