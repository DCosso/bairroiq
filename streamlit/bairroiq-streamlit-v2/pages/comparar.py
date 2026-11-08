from __future__ import annotations

from html import escape

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from bairroiq.map_data import (
    DistrictMapService,
)
from bairroiq.provider import load_history, load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import (
    SCENARIO_DEFAULTS,
    render_header,
    theme_palette,
)


_METRIC_OPTIONS = {
    "Empregos": "formal_jobs_score",
    "Segurança": "safety_score",
    "Iluminação LED": "lighting_led",
    "Arborização": "trees_score",
    "Mobilidade": "mobility_score",
    "Custo de vida": "affordability_score",
}
_HISTORY_METRICS = {
    "Empregos": "formal_jobs_score",
    "Iluminação LED": "lighting_led",
    "Segurança": "safety_score",
}
_COLORS = ["#2d8a6e", "#356ae6", "#d96b43", "#8a58b5", "#c59b35"]
district_map_service = DistrictMapService()


def _sync_map_selection() -> None:
    selected = st.session_state["comparison-neighborhoods-widget"]
    st.session_state["selected-neighborhoods"] = selected
    st.session_state["comparison_neighborhoods"] = selected


render_header("compare")
st.markdown(
    """
    <style>
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-summary-"] {
        height: 74px !important;
        min-height: 74px !important;
    }
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-summary-"] [data-testid="stMetric"] {
        height: 60px !important;
    }
    body:has(.st-key-comparison-map) .st-key-comparison-summary-panel {
        height: 620px !important;
        min-height: 620px !important;
        box-sizing: border-box !important;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-panel [class*="st-key-comparison-summary-"] {
        height: 112px !important;
        min-height: 112px !important;
        box-sizing: border-box !important;
        border: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-panel [class*="st-key-comparison-summary-"] [data-testid="stMetric"] {
        height: 94px !important;
        box-sizing: border-box !important;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-2 [data-testid="stMetric"] > div {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) auto;
        grid-template-rows: auto auto;
        align-items: center;
        column-gap: 0.35rem;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-2 [data-testid="stMetricLabel"] {
        grid-column: 1 / -1;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-2 [data-testid="stMetricValue"] {
        width: auto !important;
        min-height: 0 !important;
        white-space: nowrap !important;
        font-size: clamp(0.9rem, 1.15vw, 1.15rem) !important;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-2 [data-testid="stMetric"] > div > div:last-child {
        width: auto !important;
        margin: 0 !important;
        justify-self: end;
        white-space: nowrap;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-4 [data-testid="stMetric"] > div {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) auto;
        grid-template-rows: auto auto;
        align-items: center;
        column-gap: 0.35rem;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-4 [data-testid="stMetricLabel"] {
        grid-column: 1 / -1;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-4 [data-testid="stMetricValue"] {
        width: auto !important;
        min-height: 0 !important;
        white-space: nowrap !important;
        font-size: clamp(0.9rem, 1.15vw, 1.15rem) !important;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-4 [data-testid="stMetric"] > div > div:last-child {
        width: auto !important;
        margin: 0 !important;
        justify-self: end;
        white-space: nowrap;
    }
    body:has(.st-key-comparison-map) .st-key-comparison-map-card {
        height: 620px !important;
        min-height: 620px !important;
        box-sizing: border-box !important;
    }
    body:has(.st-key-comparison-map) .st-key-comparison-ranking-card {
        height: 620px !important;
        min-height: 620px !important;
        box-sizing: border-box !important;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-map-card [data-testid="stPlotlyChart"],
    body:has(.st-key-comparison-map)
      .st-key-comparison-map-card [data-testid="stPlotlyChart"] > div,
    body:has(.st-key-comparison-map)
      .st-key-comparison-map-card [data-testid="stPlotlyChart"] .plot-container,
    body:has(.st-key-comparison-map)
      .st-key-comparison-map-card [data-testid="stPlotlyChart"] .svg-container {
        height: 500px !important;
    }
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-chart-"] {
        height: 420px !important;
        box-sizing: border-box !important;
    }
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"],
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"] > div,
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"] .plot-container,
    body:has(.st-key-comparison-map)
      [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"] .svg-container {
        height: 340px !important;
    }
    body:has(.st-key-comparison-map) .section-heading {
        margin: 0.55rem 0 0.35rem !important;
    }
    body:has(.st-key-comparison-map) .duel-card {
        height: auto !important;
        min-height: 0 !important;
        padding: 0.55rem 0.75rem !important;
        margin-bottom: 0.75rem !important;
    }
    body:has(.st-key-comparison-map) .duel-card h4 {
        margin-bottom: 0.3rem !important;
    }
    body:has(.st-key-comparison-map) .duel-card .duel-item {
        margin-top: 0.25rem !important;
    }
    body:has(.st-key-comparison-map) .duel-card .duel-opportunity {
        margin-top: 0.35rem !important;
        padding-top: 0.35rem !important;
    }
    body:has(.st-key-comparison-map) [data-testid="stExpander"] summary {
        border: 1px solid var(--line) !important;
        border-radius: 8px !important;
        background: var(--surface) !important;
        color: var(--ink) !important;
    }
    body:has(.st-key-comparison-map) [data-testid="stExpander"] details {
        border: 0 !important;
        background: transparent !important;
    }
    body:has(.st-key-comparison-map) [data-testid="stExpanderDetails"] {
        border: 1px solid var(--line) !important;
        border-radius: 10px !important;
        margin-top: 0.4rem !important;
        background: var(--surface) !important;
    }
    body:has(.st-key-comparison-map) [data-testid="stExpander"] summary * {
        color: var(--ink) !important;
    }
    @media (max-width: 900px) {
        body:has(.st-key-comparison-map) .st-key-comparison-summary-panel,
        body:has(.st-key-comparison-map) .st-key-comparison-ranking-card,
        body:has(.st-key-comparison-map) .st-key-comparison-map-card {
            height: auto !important;
            min-height: 0 !important;
        }
        body:has(.st-key-comparison-map)
          [class*="st-key-comparison-chart-"] {
            height: auto !important;
        }
        body:has(.st-key-comparison-map)
          [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"],
        body:has(.st-key-comparison-map)
          [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"] > div,
        body:has(.st-key-comparison-map)
          [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"] .plot-container,
        body:has(.st-key-comparison-map)
          [class*="st-key-comparison-chart-"] [data-testid="stPlotlyChart"] .svg-container {
            height: 320px !important;
        }
        body:has(.st-key-comparison-map)
          .st-key-comparison-summary-panel [class*="st-key-comparison-summary-"] {
            height: 74px !important;
            min-height: 74px !important;
        }
        body:has(.st-key-comparison-map)
          .st-key-comparison-summary-panel [class*="st-key-comparison-summary-"] [data-testid="stMetric"] {
            height: 60px !important;
        }
        body:has(.st-key-comparison-map)
          .st-key-comparison-map-card [data-testid="stPlotlyChart"],
        body:has(.st-key-comparison-map)
          .st-key-comparison-map-card [data-testid="stPlotlyChart"] > div,
        body:has(.st-key-comparison-map)
          .st-key-comparison-map-card [data-testid="stPlotlyChart"] .plot-container,
        body:has(.st-key-comparison-map)
          .st-key-comparison-map-card [data-testid="stPlotlyChart"] .svg-container {
            height: 320px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Analytics / Comparação")
st.caption(
    "Explore o ranking, compare indicadores e acompanhe a evolução dos bairros selecionados."
)

palette = theme_palette()
metrics = load_metrics()
history = load_history()
all_neighborhoods = metrics["neighborhood"].tolist()

if "comparison-neighborhoods-widget" not in st.session_state:
    st.session_state["comparison-neighborhoods-widget"] = st.session_state.get(
        "comparison_neighborhoods",
        st.session_state.get("selected-neighborhoods", all_neighborhoods[:3]),
    )
st.session_state["comparison-neighborhoods-widget"] = [
    name
    for name in st.session_state["comparison-neighborhoods-widget"]
    if name in all_neighborhoods
]

selection_col, focus_col = st.columns([1.35, 1], gap="large")
with selection_col:
    selected = st.multiselect(
        "Regiões da análise",
        options=all_neighborhoods,
        key="comparison-neighborhoods-widget",
        on_change=_sync_map_selection,
        placeholder="Selecione até cinco bairros",
    )
with focus_col:
    focus_mode = st.radio(
        "Foco da análise",
        options=["Visão geral", "Oportunidades", "Tendências"],
        horizontal=True,
        key="comparison-focus-mode",
    )

if len(selected) < 2:
    st.info("Selecione pelo menos dois bairros para visualizar a comparação completa.")
    st.stop()

for key, default in SCENARIO_DEFAULTS.items():
    st.session_state.setdefault(f"scenario-value-{key}", default)
weights = {
    key: int(st.session_state[f"scenario-value-{key}"])
    for key in SCENARIO_DEFAULTS
}
score_weights = weights if sum(weights.values()) else SCENARIO_DEFAULTS
scored = SCENARIO_SCORER.score_neighborhoods(metrics, score_weights)
comparison = scored[scored["neighborhood"].isin(selected)].copy()
ranking = district_map_service.selected_district_ranking(scored, selected)
history_comparison = history[history["neighborhood"].isin(selected)].copy()

dimensions = dict(_METRIC_OPTIONS)
if focus_mode == "Oportunidades":
    dimensions = {"Empregos": _METRIC_OPTIONS["Empregos"]}
elif focus_mode == "Tendências":
    dimensions = {
        "Empregos": "formal_jobs_score",
        "Iluminação LED": "lighting_led",
        "Segurança": "safety_score",
    }

leader = comparison.sort_values("priority_score", ascending=False).iloc[0]
average_score = comparison["priority_score"].mean()
scenario_dimensions = {
    "trees": ("Arborização", "trees_score"),
    "safety": ("Segurança", "safety_score"),
    "mobility": ("Mobilidade", "mobility_score"),
    "infrastructure": ("Infraestrutura e serviços", "lighting_led"),
    "jobs": ("Empregos e oportunidades", "formal_jobs_score"),
    "budget": ("Custo de vida", "affordability_score"),
}
active_dimensions = [
    (key, *scenario_dimensions[key])
    for key, weight in weights.items()
    if weight > 0
    and key in scenario_dimensions
    and pd.to_numeric(comparison[scenario_dimensions[key][1]], errors="coerce")
    .notna()
    .any()
]
active_priority = max(
    ((key, weights[key]) for key, _, _ in active_dimensions),
    key=lambda item: item[1],
    default=None,
)
priority_labels = {
    key: label for key, (label, _) in scenario_dimensions.items()
}
ranked_comparison = comparison.sort_values(
    "priority_score",
    ascending=False,
).drop_duplicates(subset=["neighborhood"]).reset_index(drop=True)

st.markdown('<div class="section-heading">Diferenciais do duelo</div>', unsafe_allow_html=True)
if ranked_comparison.empty:
    st.info("Selecione pelo menos um bairro para visualizar os diferenciais.")
else:
    duel_columns = st.columns(min(3, len(ranked_comparison)), gap="small")
    for rank, (_, row) in enumerate(ranked_comparison.iterrows(), start=1):
        valid_metrics = [
            (label, column, float(row[column]))
            for label, column in _METRIC_OPTIONS.items()
            if column in row and pd.notna(row[column])
        ]
        strongest = sorted(valid_metrics, key=lambda item: item[2], reverse=True)[:2]
        weakest = min(valid_metrics, key=lambda item: item[2], default=None)
        row_dimensions = [
            dimension
            for dimension in active_dimensions
            if pd.notna(row[dimension[2]])
        ]

        if active_priority and row_dimensions:
            weakest_priority = min(
                row_dimensions,
                key=lambda item: float(row[item[2]]),
            )
            priority_html = (
                '<div class="duel-item"><strong>Prioridade principal:</strong> '
                f'{escape(priority_labels[active_priority[0]])} '
                f'({active_priority[1]}%)</div>'
                '<div class="duel-item duel-opportunity">'
                '<strong>Maior oportunidade:</strong> '
                f'{escape(weakest_priority[1])} '
                f'({float(row[weakest_priority[2]]):.1f}/100)</div>'
            )
        elif weakest:
            priority_html = (
                '<div class="duel-item duel-opportunity">'
                '<strong>Oportunidade:</strong> '
                f'{escape(weakest[0])} ({weakest[2]:.1f}/100)</div>'
            )
        else:
            priority_html = (
                '<div class="duel-item duel-opportunity">'
                "Dados insuficientes para esta análise.</div>"
            )

        highlights = " · ".join(
            f"{escape(label)} {score:.1f}"
            for label, _, score in strongest
        ) or "Dados insuficientes"
        neighborhood_name = escape(str(row["neighborhood"]))
        priority_score = (
            float(row["priority_score"])
            if pd.notna(row["priority_score"])
            else 0.0
        )
        card_html = (
            '<div class="duel-card">'
            f"<h4>#{rank} {neighborhood_name}</h4>"
            f'<div class="duel-score">{priority_score:.1f}/100</div>'
            '<div class="duel-label">Aderência ao cenário</div>'
            f'<div class="duel-item"><strong>Destaques:</strong> {highlights}</div>'
            f"{priority_html}"
            "</div>"
        )
        with duel_columns[(rank - 1) % len(duel_columns)]:
            st.markdown(card_html, unsafe_allow_html=True)

summary_metrics = (
    ("Bairros analisados", len(comparison), None),
    ("Líder do cenário", str(leader["neighborhood"]), f'{leader["priority_score"]:.1f}/100'),
    ("Média de aderência", f"{average_score:.1f}/100", None),
    (
        "Prioridade principal",
        priority_labels[active_priority[0]] if active_priority else "Nenhuma",
        f"{active_priority[1]}%" if active_priority else None,
    ),
)
st.markdown('<div class="section-heading">Resumo por indicador</div>', unsafe_allow_html=True)
table_data = comparison[["neighborhood", *dimensions.values(), "priority_score"]].copy()
table_data.columns = [
    "Bairro",
    *dimensions.keys(),
    "Aderência",
]
table_palette = theme_palette()
is_light_theme = st.session_state.get("bairroiq-theme", "dark") == "light"
table_background = "#ffffff" if is_light_theme else table_palette["paper"]
table_line = "#000000" if is_light_theme else table_palette["line"]
styled_table = (
    table_data.sort_values("Aderência", ascending=False)
    .style.format(
        {
            name: "{:.1f}%"
            for name in [*dimensions.keys(), "Aderência"]
        }
    )
    .set_table_styles(
        [
            {
                "selector": "table",
                "props": [
                    ("width", "100%"),
                    ("border-collapse", "collapse"),
                    ("border", f"1px solid {table_line}"),
                    ("background-color", table_background),
                    ("color", table_palette["ink"]),
                ],
            },
            {
                "selector": "th, td",
                "props": [
                    ("border", f"1px solid {table_line}"),
                    ("background-color", table_background),
                    ("color", table_palette["ink"]),
                    ("padding", "0.5rem"),
                ],
            },
        ]
    )
)
st.table(
    styled_table,
    width="stretch",
    hide_index=True,
)

search = st.session_state.get("map-search", "")
quick_filters = st.session_state.get("map-quick-filters", [])
visible = district_map_service.filter_districts(
    scored, selected, search, quick_filters
)
map_visible, missing_map_boundaries = (
    district_map_service.restrict_to_mapped_districts(visible)
)
summary_column, map_column, ranking_column = st.columns(
    [0.9, 1.55, 0.9],
    gap="medium",
)

with summary_column:
    with st.container(key="comparison-summary-panel", border=True):
        st.markdown(
            '<div class="section-heading">Resumo da análise</div>',
            unsafe_allow_html=True,
        )
        for index, (label, value, detail) in enumerate(summary_metrics, start=1):
            with st.container(key=f"comparison-summary-{index}", border=True):
                st.metric(label, value, detail)

with map_column:
    with st.container(key="comparison-map-card", border=True):
        st.markdown('<div class="section-heading">Mapa por pontuação</div>', unsafe_allow_html=True)
        map_figure = district_map_service.build_map(
            map_visible,
            theme=st.session_state.get("bairroiq-theme", "light"),
        )
        st.plotly_chart(
            map_figure,
            key="comparison-map",
            width="stretch",
            height=500,
            config={"displayModeBar": False, "scrollZoom": True},
        )
        if missing_map_boundaries:
            st.caption(
                "Sem limites geográficos no mapa para: "
                f"{', '.join(missing_map_boundaries)}."
            )
        if (
            "illustrative_boundary" in visible.columns
            and visible["illustrative_boundary"].any()
        ):
            st.caption("Os limites de alguns bairros demonstrativos são ilustrativos.")

with ranking_column:
    with st.container(key="comparison-ranking-card", border=True):
        st.markdown('<div class="section-heading">Top 10 do cenário</div>', unsafe_allow_html=True)
        top10_ranking = scored.head(10)
        st.caption("Melhores bairros de acordo com suas prioridades selecionadas")
        for position, row in enumerate(
            top10_ranking.sort_values("priority_score", ascending=False).to_dict(
                orient="records"
            ),
            start=1,
        ):
            st.markdown(
                f'<div class="ranking-row"><span>#{position} '
                f'{escape(str(row["neighborhood"]))}</span><strong>'
                f'{row["priority_score"]:.1f}</strong></div>',
                unsafe_allow_html=True,
            )
        if top10_ranking.empty:
            st.info("Infelizmente não conseguimos localizar dados para as seleções solicitadas.")
        st.caption("Pontuação personalizada de 0 a 100")

comparison_chart_data = comparison.melt(
    id_vars="neighborhood",
    value_vars=list(dimensions.values()),
    var_name="metric",
    value_name="score",
)
metric_labels = {column: label for label, column in dimensions.items()}
comparison_chart_data["metric"] = comparison_chart_data["metric"].map(metric_labels)

with st.expander("Gráficos comparativos · 3 gráficos disponíveis", expanded=False):
    highlight_column, trend_metric_column = st.columns(2, gap="small")
    with highlight_column:
        highlighted_neighborhood = st.selectbox(
            "Destacar bairro nos gráficos",
            options=["Nenhum", *selected],
            key="comparison-highlight-neighborhood",
        )
    has_highlight = highlighted_neighborhood != "Nenhum"
    with trend_metric_column:
        trend_metric = st.selectbox(
            "Indicador ao longo do tempo",
            options=list(_HISTORY_METRICS),
            index=1 if focus_mode == "Tendências" else 0,
        )
    trend_column_name = _HISTORY_METRICS[trend_metric]
    bar_column, radar_column, trend_column = st.columns(3, gap="small")

    with bar_column:
        with st.container(key="comparison-chart-indicators", border=True):
            st.markdown("#### Indicadores dos bairros")
            bar_figure = px.bar(
                comparison_chart_data,
                x="metric",
                y="score",
                color="neighborhood",
                barmode="group",
                color_discrete_sequence=_COLORS,
                labels={"metric": "Indicador", "score": "Nota (0–100)", "neighborhood": "Bairro"},
            )
            bar_figure.update_layout(
                height=340,
                margin={"r": 12, "t": 12, "l": 8, "b": 80},
                paper_bgcolor=palette["surface"],
                plot_bgcolor=palette["surface"],
                font={"color": palette["ink"], "size": 11},
                xaxis={
                    "tickangle": -20,
                    "gridcolor": palette["line"],
                    "tickfont": {"color": palette["ink"]},
                    "title_font": {"color": palette["ink"]},
                    "automargin": True,
                },
                yaxis={
                    "range": [0, 100],
                    "gridcolor": palette["line"],
                    "tickfont": {"color": palette["ink"]},
                    "title_font": {"color": palette["ink"]},
                },
                legend={
                    "orientation": "h",
                    "y": -0.32,
                    "font": {"color": palette["ink"], "size": 11},
                },
            )
            if has_highlight:
                for trace in bar_figure.data:
                    trace.marker.opacity = (
                        1 if trace.name == highlighted_neighborhood else 0.18
                    )
            st.plotly_chart(bar_figure, width="stretch", config={"displayModeBar": False})

    with radar_column:
        with st.container(key="comparison-chart-profile", border=True):
            st.markdown("#### Perfil por dimensão")
            if comparison.empty:
                st.info("Selecione pelo menos um bairro para ver o perfil por dimensão.")
            else:
                radar = go.Figure()
                for _, row in comparison.iterrows():
                    radar.add_trace(
                        go.Scatterpolar(
                            r=[row[column] for column in dimensions.values()],
                            theta=list(dimensions),
                            fill="toself",
                            name=row["neighborhood"],
                            opacity=(
                                0.58
                                if not has_highlight
                                else (
                                    0.85
                                    if row["neighborhood"] == highlighted_neighborhood
                                    else 0.12
                                )
                            ),
                            line={
                                "width": (
                                    4
                                    if row["neighborhood"] == highlighted_neighborhood
                                    else 2
                                )
                            },
                        )
                    )
                radar.update_layout(
                    polar={
                        "radialaxis": {
                            "visible": True,
                            "range": [0, 100],
                            "gridcolor": palette["line"],
                            "linecolor": palette["muted"],
                            "tickfont": {"color": palette["ink"]},
                        },
                        "angularaxis": {
                            "gridcolor": palette["line"],
                            "linecolor": palette["muted"],
                            "tickfont": {"color": palette["ink"]},
                        },
                        "bgcolor": palette["surface"],
                    },
                    height=340,
                    margin={"r": 35, "t": 20, "l": 35, "b": 60},
                    paper_bgcolor=palette["surface"],
                    plot_bgcolor=palette["surface"],
                    font={"color": palette["ink"], "size": 11},
                    colorway=_COLORS,
                    legend={
                        "orientation": "h",
                        "y": -0.2,
                        "font": {"color": palette["ink"], "size": 11},
                    },
                )
                st.plotly_chart(radar, width="stretch", config={"displayModeBar": False})

    with trend_column:
        with st.container(key="comparison-chart-trend", border=True):
            st.markdown("#### Evolução temporal")
            if comparison.empty:
                st.info("Selecione pelo menos um bairro para ver a evolução temporal.")
            elif history_comparison.empty:
                st.info(
                    "A tabela publicada contém apenas o snapshot atual. Para mostrar "
                    "a evolução, conecte uma fonte com registros por ano."
                )
            else:
                trend = px.line(
                    history_comparison,
                    x="year",
                    y=trend_column_name,
                    color="neighborhood",
                    markers=True,
                    color_discrete_sequence=_COLORS,
                    labels={
                        "year": "Ano",
                        trend_column_name: "Índice (0–100)",
                        "neighborhood": "Bairro",
                    },
                )
                trend.update_layout(
                    height=340,
                    margin={"r": 8, "t": 12, "l": 8, "b": 12},
                    paper_bgcolor=palette["surface"],
                    plot_bgcolor=palette["surface"],
                    font={"color": palette["ink"], "size": 10},
                    xaxis={
                        "gridcolor": palette["line"],
                        "linecolor": palette["muted"],
                        "tickfont": {"color": palette["ink"], "size": 11},
                        "title_font": {"color": palette["ink"], "size": 11},
                        "automargin": True,
                    },
                    yaxis={
                        "range": [0, 100],
                        "gridcolor": palette["line"],
                        "linecolor": palette["muted"],
                        "tickfont": {"color": palette["ink"], "size": 11},
                        "title_font": {"color": palette["ink"], "size": 11},
                    },
                    legend={
                        "orientation": "h",
                        "y": -0.25,
                        "font": {"color": palette["ink"], "size": 11},
                    },
                )
                if has_highlight:
                    for trace in trend.data:
                        is_highlighted = trace.name == highlighted_neighborhood
                        trace.opacity = 1 if is_highlighted else 0.18
                        trace.line.width = 3.5 if is_highlighted else 1.5
                        trace.marker.size = 8 if is_highlighted else 4
                st.plotly_chart(trend, width="stretch", config={"displayModeBar": False})

st.markdown(
    '<div class="source-note">Protótipo com dados demonstrativos. '
    "Conecte o Observa Sampa pelo adaptador Databricks para substituir esta amostra.</div>",
    unsafe_allow_html=True,
)
