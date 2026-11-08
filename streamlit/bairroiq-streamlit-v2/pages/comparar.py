"""Comparação territorial do BairroIQ / Atlas Sampa.

Consumer V2: comparação transversal de distritos, mapas oficiais e perfis
K-Means existentes. Não utiliza séries temporais fictícias nem reexecuta ML.
O layout conserva a estrutura de cartões, mapa, ranking, radar e gráficos
comparativos desenvolvida originalmente para o frontend Streamlit.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from bairroiq.comparison_v2 import (
    V2_INDICATORS,
    V2_WEIGHT_DIMENSIONS,
    build_cluster_comparison,
    is_real_v2,
    selected_cluster_descriptions,
)
from bairroiq.map_data import DistrictMapService
from bairroiq.provider import load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, render_header, theme_palette


_COLORS = ["#2d8a6e", "#356ae6", "#d96b43", "#8a58b5", "#c59b35"]
# Compatibilidade visual com o modo de demonstração, nunca com o Consumer V2.
_SAMPLE_INDICATORS = {
    "Empregos (demonstração)": "formal_jobs_score",
    "Segurança (demonstração)": "safety_score",
    "Iluminação (demonstração)": "lighting_led",
    "Arborização (demonstração)": "trees_score",
    "Mobilidade (demonstração)": "mobility_score",
    "Custo (demonstração)": "affordability_score",
}
_SAMPLE_PRIORITIES = {
    "trees": ("Arborização", "trees_score"),
    "safety": ("Segurança", "safety_score"),
    "mobility": ("Mobilidade", "mobility_score"),
    "infrastructure": ("Infraestrutura e serviços", "lighting_led"),
}

district_map_service = DistrictMapService()


def _sync_map_selection() -> None:
    selected = list(st.session_state["comparison-neighborhoods-widget"][:5])
    st.session_state["selected-neighborhoods"] = selected
    st.session_state["comparison_neighborhoods"] = selected


def _score_display(value: object) -> str:
    if pd.isna(value):
        return "indisponível"
    return f"{float(value):.1f}"


def _numeric_style(column: str) -> str:
    return "{:.1f}" if column != "Aderência" else "{:.1f}"


render_header("compare")
st.markdown(
    """
    <style>
    /* Mantém o desenho de três colunas da página original da Laís. */
    body:has(.st-key-comparison-map) .st-key-comparison-summary-panel,
    body:has(.st-key-comparison-map) .st-key-comparison-ranking-card,
    body:has(.st-key-comparison-map) .st-key-comparison-map-card {
        min-height: 620px; box-sizing: border-box;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-panel [class*="st-key-comparison-summary-"] {
        min-height: 110px; box-sizing: border-box; margin-bottom: 0.35rem;
    }
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-2 [data-testid="stMetricValue"],
    body:has(.st-key-comparison-map)
      .st-key-comparison-summary-4 [data-testid="stMetricValue"] {
        font-size: clamp(0.85rem, 1.1vw, 1.1rem) !important;
        white-space: normal !important;
    }
    body:has(.st-key-comparison-map) .st-key-comparison-map-card
      [data-testid="stPlotlyChart"] {
        min-height: 500px;
    }
    body:has(.st-key-comparison-map) [class*="st-key-comparison-chart-"] {
        min-height: 420px; box-sizing: border-box;
    }
    body:has(.st-key-comparison-map) .section-heading {
        margin: 0.55rem 0 0.35rem !important;
    }
    body:has(.st-key-comparison-map) .duel-card {
        padding: 0.55rem 0.75rem !important;
        margin-bottom: 0.75rem !important;
        min-height: 155px;
    }
    body:has(.st-key-comparison-map) .duel-card .duel-item {
        margin-top: 0.25rem !important;
    }
    body:has(.st-key-comparison-map) [data-testid="stExpander"] summary {
        border: 1px solid var(--line) !important;
        border-radius: 8px !important;
        background: var(--surface) !important;
        color: var(--ink) !important;
    }
    @media (max-width: 900px) {
        body:has(.st-key-comparison-map) .st-key-comparison-summary-panel,
        body:has(.st-key-comparison-map) .st-key-comparison-ranking-card,
        body:has(.st-key-comparison-map) .st-key-comparison-map-card,
        body:has(.st-key-comparison-map) [class*="st-key-comparison-chart-"] {
            min-height: 0 !important;
            height: auto !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Analytics / Comparação")
st.caption(
    "Compare distritos, indicadores territoriais e perfis do K-Means "
    "do snapshot selecionado. Não há série histórica nessa fonte."
)

palette = theme_palette()
metrics = load_metrics()
all_neighborhoods = metrics["neighborhood"].astype(str).tolist()
if len(all_neighborhoods) < 2:
    st.info("São necessários ao menos dois distritos para uma comparação.")
    st.stop()

if "comparison-neighborhoods-widget" not in st.session_state:
    st.session_state["comparison-neighborhoods-widget"] = st.session_state.get(
        "comparison_neighborhoods",
        st.session_state.get("selected-neighborhoods", all_neighborhoods[:3]),
    )
# Valores herdados de outras telas podem conter mais de cinco distritos.
st.session_state["comparison-neighborhoods-widget"] = [
    name
    for name in st.session_state["comparison-neighborhoods-widget"]
    if name in all_neighborhoods
][:5]

selection_col, focus_col = st.columns([1.35, 1], gap="large")
with selection_col:
    selected = st.multiselect(
        "Distritos da análise",
        options=all_neighborhoods,
        key="comparison-neighborhoods-widget",
        max_selections=5,
        on_change=_sync_map_selection,
        placeholder="Selecione de dois a cinco distritos",
    )
with focus_col:
    valid_focus_modes = ["Visão geral", "Empregos formais", "Perfis ML"]
    if st.session_state.get("comparison-focus-mode") not in (*valid_focus_modes, None):
        st.session_state["comparison-focus-mode"] = "Visão geral"
    focus_mode = st.radio(
        "Foco da análise",
        options=valid_focus_modes,
        horizontal=True,
        key="comparison-focus-mode",
    )

if len(selected) < 2:
    st.info("Selecione pelo menos dois distritos para visualizar a comparação completa.")
    st.stop()

for key, default in SCENARIO_DEFAULTS.items():
    st.session_state.setdefault(f"scenario-value-{key}", default)
weights = {
    key: int(st.session_state[f"scenario-value-{key}"])
    for key in SCENARIO_DEFAULTS
}
score_weights = weights if sum(weights.values()) else SCENARIO_DEFAULTS
scored = SCENARIO_SCORER.score_neighborhoods(metrics, score_weights)
real_v2 = is_real_v2(scored)
comparison = scored[scored["neighborhood"].isin(selected)].copy()
comparison = comparison.sort_values("priority_score", ascending=False, kind="stable")

if real_v2:
    metric_options = dict(V2_INDICATORS)
    priority_options = dict(V2_WEIGHT_DIMENSIONS)
    cluster_summary = build_cluster_comparison(scored, selected)
    radar_dimensions = metric_options
    if focus_mode == "Empregos formais":
        dimensions = {"Empregos formais": "formal_jobs_score"}
    else:
        dimensions = metric_options
    st.caption(
        "Empregos formais, densidade e roubos são informações descritivas. "
        "Somente Verde e lazer, Segurança, Mobilidade e Serviços públicos "
        "entram na aderência personalizada."
    )
else:
    # O modo sample permanece identificado; seus dados nunca são apresentados
    # como K-Means, indicadores oficiais ou histórico factual.
    metric_options = {
        label: field for label, field in _SAMPLE_INDICATORS.items()
        if field in scored.columns
    }
    priority_options = _SAMPLE_PRIORITIES
    dimensions = (
        {"Empregos (demonstração)": "formal_jobs_score"}
        if focus_mode == "Empregos formais" else metric_options
    )
    cluster_summary = None
    radar_dimensions = metric_options
    st.warning("Modo demonstrativo: conecte o Consumer V2 para comparar clusters reais.")

leader = comparison.iloc[0]
average_score = float(comparison["priority_score"].mean())
active_dimensions = [
    (key, label, column)
    for key, (label, column) in priority_options.items()
    if float(weights.get(key, 0)) > 0
    and column in comparison.columns
    and pd.to_numeric(comparison[column], errors="coerce").notna().any()
]
active_priority = max(
    ((key, weights[key]) for key, _label, _column in active_dimensions),
    key=lambda item: item[1], default=None,
)
priority_labels = {key: label for key, (label, _col) in priority_options.items()}

st.markdown('<div class="section-heading">Diferenciais do duelo</div>', unsafe_allow_html=True)
duel_columns = st.columns(min(3, len(comparison)), gap="small")
for position, (_, row) in enumerate(comparison.iterrows(), start=1):
    observed = [
        (label, column, float(row[column]))
        for label, column in metric_options.items()
        if column in row and pd.notna(row[column])
    ]
    strongest = sorted(observed, key=lambda item: item[2], reverse=True)[:2]
    valid_priorities = [
        (key, label, column) for key, label, column in active_dimensions
        if pd.notna(row[column])
    ]
    weakest = (
        min(valid_priorities, key=lambda item: float(row[item[2]]))
        if valid_priorities else None
    )
    highlights = " · ".join(
        f"{escape(label)} {value:.1f}" for label, _column, value in strongest
    ) or "Dados insuficientes"
    if weakest:
        insight = (
            f'<div class="duel-item"><strong>Prioridade principal:</strong> '
            f'{escape(priority_labels[active_priority[0]])} '
            f'(peso {active_priority[1]})</div>'
            f'<div class="duel-item duel-opportunity"><strong>Menor índice entre suas '
            f'prioridades:</strong> {escape(weakest[1])} '
            f'({_score_display(row[weakest[2]])}/100)</div>'
        )
    else:
        insight = '<div class="duel-item">Nenhuma prioridade ativa.</div>'
    profile_html = (
        f'<div class="duel-item"><strong>Perfil K-Means:</strong> '
        f'{escape(str(row["cluster"]))}</div>'
        f'<div class="duel-item"><small>{escape(str(row["perfil_id"]))}</small></div>'
        if real_v2 else ""
    )
    card_html = (
        '<div class="duel-card">'
        f'<h4>#{position} {escape(str(row["neighborhood"]))}</h4>'
        f'<div class="duel-score">{float(row["priority_score"]):.1f}/100</div>'
        '<div class="duel-label">Aderência ao cenário</div>'
        f'<div class="duel-item"><strong>Destaques:</strong> {highlights}</div>'
        f'{profile_html}{insight}</div>'
    )
    with duel_columns[(position - 1) % len(duel_columns)]:
        st.markdown(card_html, unsafe_allow_html=True)

summary_metrics = (
    ("Distritos analisados", len(comparison), None),
    ("Líder do cenário", str(leader["neighborhood"]), f'{leader["priority_score"]:.1f}/100'),
    ("Média de aderência", f"{average_score:.1f}/100", None),
    (
        "Prioridade principal",
        priority_labels[active_priority[0]] if active_priority else "Nenhuma",
        f"Peso {active_priority[1]}" if active_priority else None,
    ),
)
st.markdown('<div class="section-heading">Resumo por indicador</div>', unsafe_allow_html=True)
table_columns = ["neighborhood", *dimensions.values(), "priority_score"]
table_data = comparison[table_columns].copy()
table_data.columns = ["Distrito", *dimensions.keys(), "Aderência"]
table_palette = theme_palette()
light_theme = st.session_state.get("bairroiq-theme", "dark") == "light"
table_background = "#ffffff" if light_theme else table_palette["paper"]
table_line = "#000000" if light_theme else table_palette["line"]
styled_table = (
    table_data.sort_values("Aderência", ascending=False)
    .style.format({name: _numeric_style(name) for name in [*dimensions.keys(), "Aderência"]})
    .set_table_styles([
        {"selector": "table", "props": [
            ("width", "100%"), ("border-collapse", "collapse"),
            ("border", f"1px solid {table_line}"),
            ("background-color", table_background), ("color", table_palette["ink"]),
        ]},
        {"selector": "th, td", "props": [
            ("border", f"1px solid {table_line}"),
            ("background-color", table_background), ("color", table_palette["ink"]),
            ("padding", "0.5rem"),
        ]},
    ])
)
st.table(styled_table, width="stretch", hide_index=True)

if real_v2:
    with st.expander("Perfis K-Means e indicadores descritivos", expanded=False):
        descriptive = comparison[[
            "neighborhood", "cluster", "perfil_id", "densidade_hab_km2",
            "robberies_per_1000",
        ]].rename(columns={
            "neighborhood": "Distrito", "cluster": "Perfil territorial",
            "perfil_id": "Identificador ML", "densidade_hab_km2": "Habitantes por km²",
            "robberies_per_1000": "Roubos por 1.000 habitantes",
        })
        st.dataframe(
            descriptive,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Habitantes por km²": st.column_config.NumberColumn(format="%.0f"),
                "Roubos por 1.000 habitantes": st.column_config.NumberColumn(format="%.2f"),
            },
        )

# Uma comparação deve sempre mostrar todos os distritos selecionados,
# mesmo que existam filtros antigos guardados na página Explorar.
visible = district_map_service.filter_districts(scored, selected, "", [])
map_visible, missing_map_boundaries = district_map_service.restrict_to_mapped_districts(visible)
summary_column, map_column, ranking_column = st.columns([0.9, 1.55, 0.9], gap="medium")
with summary_column:
    with st.container(key="comparison-summary-panel", border=True):
        st.markdown('<div class="section-heading">Resumo da análise</div>', unsafe_allow_html=True)
        for index, (label, value, detail) in enumerate(summary_metrics, start=1):
            with st.container(key=f"comparison-summary-{index}", border=True):
                st.metric(label, value, detail)
with map_column:
    with st.container(key="comparison-map-card", border=True):
        st.markdown('<div class="section-heading">Mapa por pontuação</div>', unsafe_allow_html=True)
        figure = district_map_service.build_map(
            map_visible, theme=st.session_state.get("bairroiq-theme", "light")
        )
        st.plotly_chart(
            figure, key="comparison-map", width="stretch", height=500,
            config={"displayModeBar": False, "scrollZoom": True},
        )
        if missing_map_boundaries:
            st.caption("Sem limites cadastrados para: " + ", ".join(missing_map_boundaries))
        if "illustrative_boundary" in visible and visible["illustrative_boundary"].any():
            st.caption("Os limites de distritos demonstrativos são ilustrativos.")
with ranking_column:
    with st.container(key="comparison-ranking-card", border=True):
        st.markdown('<div class="section-heading">Top 10 do cenário</div>', unsafe_allow_html=True)
        st.caption("Distritos com maior aderência às quatro prioridades")
        for position, row in enumerate(scored.head(10).to_dict("records"), start=1):
            st.markdown(
                f'<div class="ranking-row"><span>#{position} '
                f'{escape(str(row["neighborhood"]))}</span><strong>'
                f'{row["priority_score"]:.1f}</strong></div>',
                unsafe_allow_html=True,
            )
        st.caption("Aderência personalizada, de 0 a 100")

chart_data = comparison.melt(
    id_vars="neighborhood", value_vars=list(dimensions.values()),
    var_name="metric", value_name="score",
)
metric_labels = {field: name for name, field in dimensions.items()}
chart_data["metric"] = chart_data["metric"].map(metric_labels)

with st.expander("Gráficos comparativos · indicadores, radar e clusters ML", expanded=False):
    highlighted = st.selectbox(
        "Destacar distrito nos gráficos", options=["Nenhum", *selected],
        key="comparison-highlight-neighborhood",
    )
    has_highlight = highlighted != "Nenhum"
    bar_column, radar_column, cluster_column = st.columns(3, gap="small")

    with bar_column:
        with st.container(key="comparison-chart-indicators", border=True):
            st.markdown("#### Indicadores dos distritos")
            bars = px.bar(
                chart_data, x="metric", y="score", color="neighborhood",
                barmode="group", color_discrete_sequence=_COLORS,
                labels={"metric": "Indicador", "score": "Índice (0–100)", "neighborhood": "Distrito"},
            )
            bars.update_layout(
                height=340, margin={"r": 12, "t": 12, "l": 8, "b": 82},
                paper_bgcolor=palette["surface"], plot_bgcolor=palette["surface"],
                font={"color": palette["ink"], "size": 11},
                xaxis={"tickangle": -25, "automargin": True},
                yaxis={"range": [0, 100], "gridcolor": palette["line"]},
                legend={"orientation": "h", "y": -0.36, "font": {"size": 11}},
            )
            if has_highlight:
                for trace in bars.data:
                    trace.marker.opacity = 1 if trace.name == highlighted else 0.18
            st.plotly_chart(bars, width="stretch", config={"displayModeBar": False})

    with radar_column:
        with st.container(key="comparison-chart-profile", border=True):
            st.markdown("#### Perfil por dimensão")
            radar = go.Figure()
            for _, row in comparison.iterrows():
                is_focus = not has_highlight or row["neighborhood"] == highlighted
                radar.add_trace(go.Scatterpolar(
                    r=[row[field] for field in radar_dimensions.values()],
                    theta=list(radar_dimensions), fill="toself",
                    name=str(row["neighborhood"]),
                    opacity=0.58 if not has_highlight else (0.85 if is_focus else 0.12),
                    line={"width": 4 if has_highlight and is_focus else 2},
                ))
            radar.update_layout(
                polar={
                    "radialaxis": {"visible": True, "range": [0, 100],
                                   "gridcolor": palette["line"]},
                    "angularaxis": {"gridcolor": palette["line"]},
                    "bgcolor": palette["surface"],
                },
                height=340, margin={"r": 35, "t": 20, "l": 35, "b": 60},
                paper_bgcolor=palette["surface"], plot_bgcolor=palette["surface"],
                font={"color": palette["ink"], "size": 11}, colorway=_COLORS,
                legend={"orientation": "h", "y": -0.2, "font": {"size": 11}},
            )
            st.plotly_chart(radar, width="stretch", config={"displayModeBar": False})

    with cluster_column:
        with st.container(key="comparison-chart-cluster", border=True):
            st.markdown("#### Perfis territoriais K-Means")
            if not real_v2 or cluster_summary is None:
                st.info("Os perfis reais do K-Means só estão disponíveis no Consumer V2.")
            else:
                # P01...P09 são categorias, nunca valores numéricos/ranking.
                clusters_plot = px.bar(
                    cluster_summary,
                    x="codigo", y="aderencia_media", color="destaque",
                    category_orders={"codigo": cluster_summary["codigo"].tolist()},
                    color_discrete_map={
                        "Com distrito selecionado": "#2d8a6e",
                        "Outros perfis": "#8b96a7",
                    },
                    custom_data=["cluster", "perfil_id", "distritos_no_perfil"],
                    labels={"codigo": "Perfil K-Means", "aderencia_media": "Aderência média (0–100)",
                            "destaque": "Seleção"},
                )
                clusters_plot.update_traces(hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Identificador: %{customdata[1]}<br>"
                    "Distritos no perfil: %{customdata[2]}<br>"
                    "Aderência média ao cenário: %{y:.1f}/100"
                    "<extra></extra>"
                ))
                clusters_plot.update_layout(
                    height=340, margin={"r": 10, "t": 12, "l": 8, "b": 82},
                    paper_bgcolor=palette["surface"], plot_bgcolor=palette["surface"],
                    font={"color": palette["ink"], "size": 11},
                    xaxis={"type": "category", "tickangle": -30},
                    yaxis={"range": [0, 100], "gridcolor": palette["line"]},
                    legend={"orientation": "h", "y": -0.35, "font": {"size": 10}},
                )
                st.plotly_chart(
                    clusters_plot, width="stretch", config={"displayModeBar": False}
                )

    if real_v2:
        st.caption("**Perfis dos distritos selecionados:** " + " · ".join(
            selected_cluster_descriptions(scored, selected)
        ))
        st.caption(
            "As barras indicam a aderência média ao cenário atual dos distritos "
            "de cada perfil. Não são notas do K-Means nem uma hierarquia entre clusters. "
            "Os perfis são classificações exploratórias do snapshot candidato."
        )

if real_v2:
    st.caption(
        "Fonte: Consumer V2 do BairroIQ; classificação territorial exploratória "
        "K-Means. Snapshot candidato, sem autorização de publicação pública."
    )
else:
    st.caption("Ambiente demonstrativo: os dados exibidos não são indicadores reais da cidade.")
