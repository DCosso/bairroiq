"""Agregações verificáveis para a comparação territorial do Consumer V2.

O K-Means foi treinado antes da publicação do Consumer V2. Este módulo não
reexecuta clustering, não cria históricos e não trata códigos P01..P09 como
uma escala de qualidade. O gráfico de médias usa *o ranking personalizado*
para caracterizar grupos existentes, não para afirmar que um grupo é melhor.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

import pandas as pd

from bairroiq.ux_labels import nome_perfil

V2_INDICATORS: Mapping[str, str] = {
    "Empregos formais": "formal_jobs_score",
    "Segurança": "safety_score",
    "Mobilidade": "mobility_score",
    "Verde e lazer": "green_leisure_score",
    "Serviços públicos": "public_services_score",
}

V2_WEIGHT_DIMENSIONS: Mapping[str, tuple[str, str]] = {
    "trees": ("Verde e lazer", "green_leisure_score"),
    "safety": ("Segurança", "safety_score"),
    "mobility": ("Mobilidade", "mobility_score"),
    "infrastructure": ("Serviços públicos", "public_services_score"),
}

V2_REQUIRED = frozenset(
    {
        "neighborhood",
        "priority_score",
        "cluster",
        "perfil_id",
        "densidade_hab_km2",
        "robberies_per_1000",
        *V2_INDICATORS.values(),
    }
)


def is_real_v2(frame: pd.DataFrame) -> bool:
    """Não confunde dataset candidato incompleto com dados demonstrativos."""
    markers = {"cluster", "perfil_id", "snapshot_id", "public_services_score"}
    if not markers.intersection(frame.columns):
        return False
    missing = V2_REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError("Consumer V2 incompleto na comparação: " + ", ".join(sorted(missing)))
    return True


def cluster_code(label: str) -> str:
    """Retorna o código categórico apenas para os rótulos existentes P01–P09."""
    match = re.match(r"^(P\d{2})(?:\s*[—-]\s*.+)?$", str(label).strip())
    if not match:
        raise ValueError(f"Rótulo de cluster K-Means inválido: {label!r}")
    return match.group(1)


def build_cluster_comparison(
    all_scored: pd.DataFrame,
    selected_names: Sequence[str],
) -> pd.DataFrame:
    """Resumo dos *nove* grupos reais usando o mesmo score do cenário.

    O score é calculado em `bairroiq.scoring`, não aqui. Agrupar por cluster e
    `perfil_id` evita criar categorias novas e preserva sua proveniência.
    """
    if not is_real_v2(all_scored):
        raise ValueError("A comparação de clusters exige o Consumer V2 real.")
    if all_scored["neighborhood"].duplicated().any():
        raise ValueError("Consumer V2 contém distritos duplicados.")
    if all_scored[list(V2_REQUIRED)].isna().any().any():
        raise ValueError("Consumer V2 contém valor obrigatório nulo.")

    labels = all_scored[["cluster", "perfil_id"]].drop_duplicates()
    if labels["cluster"].duplicated().any() or labels["perfil_id"].duplicated().any():
        raise ValueError("Mapeamento cluster/perfil_id não é biunívoco.")
    summary = (
        all_scored.groupby(["cluster", "perfil_id"], as_index=False)
        .agg(
            distritos_no_perfil=("neighborhood", "nunique"),
            aderencia_media=("priority_score", "mean"),
        )
    )
    summary["codigo"] = summary["cluster"].map(cluster_code)
    if summary["codigo"].duplicated().any():
        raise ValueError("Códigos de cluster duplicados.")
    # Este contrato candidato do BairroIQ contém nove perfis K-Means.
    expected_codes = {f"P{i:02d}" for i in range(1, 10)}
    if set(summary["codigo"]) != expected_codes:
        raise ValueError("Esperados nove perfis P01–P09 no Consumer V2.")
    if int(summary["distritos_no_perfil"].sum()) != len(all_scored):
        raise ValueError("Distribuição por cluster não reconcilia com distritos.")
    selected = all_scored[all_scored["neighborhood"].isin(selected_names)]
    selected_codes = set(selected["cluster"].map(cluster_code))
    summary["grupo_selecionado"] = summary["codigo"].isin(selected_codes)
    summary["destaque"] = summary["grupo_selecionado"].map(
        {True: "Com distrito selecionado", False: "Outros perfis"}
    )
    return summary.sort_values("codigo", kind="stable").reset_index(drop=True)


def selected_cluster_descriptions(
    all_scored: pd.DataFrame,
    selected_names: Sequence[str],
) -> list[str]:
    if not is_real_v2(all_scored):
        return []
    matched = all_scored[all_scored["neighborhood"].isin(selected_names)]
    lookup = {
        str(row["neighborhood"]): f'{row["neighborhood"]}: {nome_perfil(row["cluster"])}'
        for _, row in matched.iterrows()
    }
    return [lookup[name] for name in selected_names if name in lookup]
