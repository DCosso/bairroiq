"""Perfis Urbanos do Atlas Sampa / BairroIQ.

O Consumer V2 contém classificações já calculadas pelo K-Means.
Esta página apenas exibe perfil_id e cluster e compara indicadores reais;
não reexecuta ML nem confunde o indicador mais alto com o cluster.
Mantém os cards e o gráfico Plotly da implementação original.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from bairroiq.provider import load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, render_header, theme_palette


render_header("profiles")
st.title("Perfis Urbanos")
st.caption("Compare os indicadores que caracterizam os distritos selecionados.")

metrics = load_metrics()
weights = {
    key: int(st.session_state.get(f"scenario-value-{key}", default))
    for key, default in SCENARIO_DEFAULTS.items()
}
scored = SCENARIO_SCORER.score_neighborhoods(
    metrics, weights if sum(weights.values()) else SCENARIO_DEFAULTS
)
selected_names = st.session_state.get(
    "selected-neighborhoods", scored["neighborhood"].tolist()
)
profiles = scored[scored["neighborhood"].isin(selected_names)].copy()

if profiles.empty:
    st.info("Selecione distritos em Quick Bairros para visualizar os perfis.")
    st.stop()

# Os dados reais V2 são identificados pelo contrato, não por uma flag manual.
is_real_v2 = {
    "perfil_id",
    "cluster",
    "green_leisure_score",
    "public_services_score",
    "densidade_hab_km2",
}.issubset(profiles.columns)

if is_real_v2:
    profile_dimensions = {
        "Empregos formais": "formal_jobs_score",
        "Segurança": "safety_score",
        "Mobilidade": "mobility_score",
        "Verde e lazer": "green_leisure_score",
        "Serviços públicos": "public_services_score",
    }
    all_profile_count = metrics["perfil_id"].nunique()
    st.caption(
        f"Perfis territoriais exploratórios do K-Means: "
        f"{all_profile_count} perfis no conjunto de 96 distritos. "
        "Os grupos não constituem classificação oficial de qualidade de vida."
    )
else:
    # Mantém compatibilidade com os dados ilustrativos usados no desenvolvimento.
    profile_dimensions = {
        "Empregos e oportunidades": "formal_jobs_score",
        "Segurança": "safety_score",
        "Iluminação": "lighting_led",
        "Áreas verdes": "trees_score",
        "Mobilidade": "mobility_score",
        "Custo de vida": "affordability_score",
    }

profile_dimensions = {
    label: column
    for label, column in profile_dimensions.items()
    if column in profiles.columns and profiles[column].notna().any()
}
if not profile_dimensions:
    st.info("A tabela conectada ainda não tem indicadores para montar os perfis.")
    st.stop()

palette = theme_palette()
with st.container(key="profiles-grid"):
    columns = st.columns(min(3, len(profiles)), gap="medium")
    for index, (_, row) in enumerate(profiles.iterrows()):
        available_dimensions = [
            item for item in profile_dimensions.items() if pd.notna(row[item[1]])
        ]
        leading_dimension = (
            max(available_dimensions, key=lambda item: row[item[1]])
            if available_dimensions
            else None
        )
        with columns[index % len(columns)]:
            if leading_dimension:
                leading_summary = (
                    f'<p>Indicador de destaque: {escape(leading_dimension[0])}</p>'
                    f'<p>Índice relativo: {float(row[leading_dimension[1]]):.1f}/100</p>'
                )
            else:
                leading_summary = (
                    "<p>Indicador de destaque: sem dados</p>"
                    "<p>Índice relativo: indisponível</p>"
                )

            if is_real_v2:
                cluster_name = escape(str(row["cluster"]))
                profile_code = escape(str(row["perfil_id"]))
                density = float(row["densidade_hab_km2"])
                profile_summary = (
                    f"<p>Perfil territorial K-Means: <strong>{cluster_name}</strong></p>"
                    f"<p>Identificador: {profile_code}</p>"
                    f"<p>Densidade: {density:,.0f} hab./km²</p>"
                )
            else:
                profile_summary = (
                    f"<p>Vocação predominante: "
                    f"{escape(leading_dimension[0]) if leading_dimension else 'Sem dados'}</p>"
                )

            st.markdown(
                f'<div class="profile-card"><strong>{escape(str(row["neighborhood"]))}</strong>'
                f'{profile_summary}'
                f'{leading_summary}'
                f'<p>Pontuação personalizada: {float(row["priority_score"]):.1f}/100</p></div>',
                unsafe_allow_html=True,
            )

chart_data = profiles.melt(
    id_vars="neighborhood",
    value_vars=list(profile_dimensions.values()),
    var_name="indicator",
    value_name="score",
)
labels = {column: label for label, column in profile_dimensions.items()}
chart_data["indicator"] = chart_data["indicator"].map(labels)
figure = px.bar(
    chart_data,
    x="indicator",
    y="score",
    color="neighborhood",
    barmode="group",
    color_discrete_sequence=["#2d8a6e", "#356ae6", "#d96b43", "#8a58b5", "#c59b35"],
    labels={
        "indicator": "Dimensão",
        "score": "Índice relativo (0–100)",
        "neighborhood": "Distrito" if is_real_v2 else "Bairro",
    },
)
figure.update_layout(
    height=560,
    margin={"r": 16, "t": 16, "l": 12, "b": 60},
    paper_bgcolor=palette["surface"],
    plot_bgcolor=palette["surface"],
    font={"color": palette["ink"]},
    yaxis={
        "range": [0, 100],
        "gridcolor": palette["line"],
        "tickfont": {"color": palette["ink"]},
        "title_font": {"color": palette["ink"]},
    },
    xaxis={
        "tickangle": -20,
        "tickfont": {"color": palette["ink"]},
        "title_font": {"color": palette["ink"]},
        "automargin": True,
    },
    legend={"font": {"color": palette["ink"]}},
)
st.plotly_chart(
    figure,
    key="profiles-chart",
    width="stretch",
    height=560,
    config={"displayModeBar": False},
)
