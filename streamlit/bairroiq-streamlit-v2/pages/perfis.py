from __future__ import annotations

from html import escape

import plotly.express as px
import streamlit as st
import pandas as pd

from bairroiq.provider import load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, render_header, theme_palette


render_header("profiles")
st.title("Perfis Urbanos")
st.caption("Identifique os indicadores que mais caracterizam cada região selecionada.")

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
    st.info("Selecione bairros em Quick Bairros para visualizar os perfis.")
    st.stop()

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
    if profiles[column].notna().any()
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
                    f'<p>Vocação predominante: {escape(leading_dimension[0])}</p>'
                    f'<p>Indicador de destaque: '
                    f'{row[leading_dimension[1]]:.1f}/100</p>'
                )
            else:
                leading_summary = (
                    "<p>Vocação predominante: Sem dados</p>"
                    "<p>Indicador de destaque: indisponível</p>"
                )
            st.markdown(
                f'<div class="profile-card"><strong>{escape(str(row["neighborhood"]))}</strong>'
                f'{leading_summary}'
                f'<p>Pontuação personalizada: {row["priority_score"]:.1f}/100</p></div>',
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
    labels={"indicator": "Dimensão", "score": "Nota (0–100)", "neighborhood": "Bairro"},
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
