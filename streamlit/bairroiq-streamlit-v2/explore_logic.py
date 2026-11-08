"""Regras da tela Explorar: filtros consistentes e mapa completo sem seleção.

Este módulo usa somente as pontuações e os distritos fornecidos pelo app.
Nenhuma classificação territorial é recalculada aqui.
"""
from __future__ import annotations

from collections.abc import Callable
import pandas as pd
from bairroiq.map_data import filter_districts


def calcular_exploracao(
    pontuados: pd.DataFrame,
    selecionados: list[str],
    busca: str,
    filtros: list[str],
    zona: str | None = None,
    identificar_zona: Callable | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Retorna elegíveis, Top 10 e mapa, na ordem do cenário personalizado.

    Nenhum distrito selecionado significa *todos* os distritos elegíveis.
    Quando uma seleção existe, o mapa apresenta somente a interseção com
    busca, filtros e zona; o Top 10 sempre considera TODOS os elegíveis.
    """
    elegiveis = filter_districts(
        pontuados, pontuados["neighborhood"].astype(str).tolist(),
        busca, filtros,
    )
    if zona:
        if identificar_zona is None:
            raise ValueError("Identificação da zona não configurada")
        elegiveis = elegiveis.copy()
        elegiveis["zone"] = elegiveis.apply(identificar_zona, axis=1)
        elegiveis = elegiveis[elegiveis["zone"] == zona].copy()
    elegiveis = elegiveis.sort_values("priority_score", ascending=False, kind="stable")
    top10 = elegiveis.head(10).copy()
    mapa = (
        elegiveis.copy() if not selecionados else
        elegiveis[elegiveis["neighborhood"].isin(selecionados)].copy()
    )
    return elegiveis, top10, mapa
