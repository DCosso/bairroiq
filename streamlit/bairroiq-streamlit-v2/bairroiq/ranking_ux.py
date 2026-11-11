"""Regras compartilhadas de ranking e seleção da UI, sem alterar o Consumer.

Os filtros de busca e interesse são os mesmos do explorador existente.
O ranking considera apenas distritos elegíveis em ordem de aderência.
"""
from __future__ import annotations

from collections.abc import Sequence
import pandas as pd

from bairroiq.map_data import filter_districts
from bairroiq.ux_labels import nome_perfil


def ranking_filtrado(
    pontuados: pd.DataFrame,
    busca: str = "",
    filtros: Sequence[str] = (),
    perfil: str | None = None,
) -> pd.DataFrame:
    """Única regra de filtragem dos Top 10 em Iniciar e Comparar.

    A tela Explorar usa a mesma função subjacente `filter_districts`,
    através de `calcular_exploracao`, garantindo semântica equivalente.
    """
    nomes = pontuados["neighborhood"].astype(str).tolist()
    base = filter_districts(pontuados, nomes, busca or "", list(filtros or ()))
    if perfil and perfil != "Todos os perfis" and "cluster" in base.columns:
        base = base[base["cluster"].map(nome_perfil) == perfil].copy()
    return base.sort_values(
        ["priority_score", "neighborhood"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def top10_filtrado(elegiveis: pd.DataFrame) -> pd.DataFrame:
    """Retorna até dez distritos, sempre após aplicar todos os filtros."""
    return elegiveis.head(10).copy()


def selecionar_comparacao(
    elegiveis: pd.DataFrame,
    nomes_selecionados: Sequence[str] | None,
) -> tuple[pd.DataFrame, bool]:
    """Seleção de 1 a 10; lista vazia utiliza Top 10 automaticamente.

    Uma seleção explícita é limitada aos distritos elegíveis pelos filtros.
    Retorna dados na ordem de pontuação e indicador de modo automático.
    """
    selecionados = list(dict.fromkeys(nomes_selecionados or ()))
    if len(selecionados) > 10:
        raise ValueError("É possível selecionar até dez distritos.")
    if not selecionados:
        return top10_filtrado(elegiveis), True
    result = elegiveis[elegiveis["neighborhood"].isin(selecionados)].copy()
    return result, False


def resumo_perfis(elegiveis: pd.DataFrame) -> pd.DataFrame:
    """Perfis existentes no Consumer, sem treinamento ou rótulos técnicos."""
    if "cluster" not in elegiveis.columns:
        return pd.DataFrame(columns=["Perfil de Distrito", "Distritos", "Aderência média"])
    frame = elegiveis.copy()
    frame["Perfil de Distrito"] = frame["cluster"].map(nome_perfil)
    result = frame.groupby("Perfil de Distrito", as_index=False).agg(
        Distritos=("neighborhood", "nunique"),
        **{"Aderência média": ("priority_score", "mean")},
    )
    return result.sort_values("Aderência média", ascending=False, kind="stable")
