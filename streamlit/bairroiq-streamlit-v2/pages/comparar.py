"""Comparação de 1 a 10 distritos, com fallback Top 10 do cenário filtrado.

Todos os gráficos utilizam os distritos elegíveis dos filtros ativos.
Os Perfis de Distrito são metadados do Consumer, não são recalculados aqui.
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
from bairroiq.ranking_ux import ranking_filtrado, selecionar_comparacao, top10_filtrado
from bairroiq.table_ux import render_responsive_table
from bairroiq.selection_ux import reconcile_selection
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, render_header, theme_palette
from bairroiq.ux_labels import nome_perfil

_COLORS = ["#218f75", "#2d6ddd", "#db784c", "#9060c2", "#d39a37", "#3a879f",
           "#cd5273", "#827bcd", "#879e37", "#c1794f"]
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


def _sync_map_selection() -> None:
    chosen = list(st.session_state.get("comparison-neighborhoods-widget", []))[:10]
    st.session_state["selected-neighborhoods"] = chosen
    st.session_state["comparison_neighborhoods"] = chosen


def _clear_comparison() -> None:
    st.session_state["comparison-neighborhoods-widget"] = []
    st.session_state["selected-neighborhoods"] = []
    st.session_state["comparison_neighborhoods"] = []
    st.session_state.pop("comparison-highlight-neighborhood", None)


def _summary_card(title: str, value: object, detail: str = "") -> None:
    st.markdown(
        '<div class="comparison-stat">'
        f'<div class="comparison-stat-label">{escape(str(title))}</div>'
        f'<div class="comparison-stat-value">{escape(str(value))}</div>'
        + (f'<div class="comparison-stat-detail">{escape(str(detail))}</div>' if detail else '')
        + '</div>',
        unsafe_allow_html=True,
    )


render_header("compare")
st.markdown("""
<style>
/* Contraste e toque adequados em desktop e smartphone, só na comparação. */
body:has(.st-key-comparison-map-card) .stButton > button {
  background: #184977 !important; color: #fff !important;
  border: 1px solid #417fac !important; border-radius: 10px !important;
  min-height: 44px !important; padding: .58rem .9rem !important;
  font-size: .97rem !important; font-weight: 750 !important;
  opacity: 1 !important; box-shadow: none !important;
}
body:has(.st-key-comparison-map-card) .stButton > button p,
body:has(.st-key-comparison-map-card) .stButton > button span { color: #fff !important; }
body:has(.st-key-comparison-map-card) .stButton > button:hover {
  background: #276caa !important; border-color: #91c4eb !important;
}
body:has(.st-key-comparison-map-card) [data-testid="stRadio"] [role="radiogroup"] label,
body:has(.st-key-comparison-map-card) [data-testid="stRadio"] [role="radiogroup"] label p {
  color: var(--ink) !important; opacity: 1 !important;
  font-size: .95rem !important; font-weight: 600 !important;
}
body:has(.st-key-comparison-map-card) [data-testid="stMultiSelect"] [data-baseweb="tag"],
body:has(.st-key-comparison-map-card) [data-testid="stMultiSelect"] [data-tag] {
  background-color: #235c90 !important; color: #fff !important;
  border: 1px solid #528bb9 !important; border-radius: 8px !important;
}
body:has(.st-key-comparison-map-card) [data-testid="stMultiSelect"] [data-baseweb="tag"] *,
body:has(.st-key-comparison-map-card) [data-testid="stMultiSelect"] [data-tag] * { color: #fff !important; }
body:has(.st-key-comparison-map-card) [data-testid="stExpander"] summary {
  color: var(--ink) !important; font-weight: 700 !important;
  background: var(--surface) !important;
}
body:has(.st-key-comparison-map-card) .comparison-stat {
  padding: .9rem; min-height: 110px; margin-bottom: .6rem;
  border: 1px solid var(--line); background: var(--surface);
  border-radius: 12px; color: var(--ink); overflow-wrap: anywhere;
}
body:has(.st-key-comparison-map-card) .comparison-stat-label { font-size: .9rem; color: var(--muted); }
body:has(.st-key-comparison-map-card) .comparison-stat-value {
  font-size: clamp(1.08rem, 1.55vw, 1.48rem);
  font-weight: 800; line-height: 1.35; color: var(--ink);
}
body:has(.st-key-comparison-map-card) .comparison-stat-detail {
  font-size: .89rem; font-weight: 650; line-height: 1.35; color: var(--ink);
  background: transparent !important; padding-top: .3rem;
}
body:has(.st-key-comparison-map-card) .comparison-district-card {
  border: 1px solid var(--line); border-radius: 11px;
  padding: .8rem; margin: .45rem 0; background: var(--surface);
  color: var(--ink); min-height: 158px; overflow-wrap: anywhere;
}
body:has(.st-key-comparison-map-card) .comparison-district-card h4 {
  font-size: 1.01rem; color: var(--ink); margin: 0 0 .4rem;
}
body:has(.st-key-comparison-map-card) .comparison-district-card .district-score {
  font-size: 1.35rem; font-weight: 800; color: var(--ink);
}
body:has(.st-key-comparison-map-card) .comparison-district-card p {
  font-size: .86rem; line-height: 1.35; margin: .26rem 0; color: var(--ink);
}
body:has(.st-key-comparison-map-card) .comparison-top-row {
  display: flex; justify-content: space-between; gap: .7rem;
  border-bottom: 1px solid var(--line); padding: .35rem 0;
  font-size: .92rem; color: var(--ink);
}
body:has(.st-key-comparison-map-card) .comparison-top-row b { white-space: nowrap; }
@media (max-width: 900px) {
  body:has(.st-key-comparison-map-card) .comparison-stat { min-height: 0; }
  body:has(.st-key-comparison-map-card) .comparison-district-card { min-height: 0; }
  body:has(.st-key-comparison-map-card) [class*="st-key-comparison-chart-"] { min-height: 0 !important; height: auto !important; }
  body:has(.st-key-comparison-map-card) .st-key-comparison-map-card { min-height: 0 !important; height: auto !important; }
}
</style>
""", unsafe_allow_html=True)

st.title("Compare seus distritos")
st.caption("Compare entre 1 e 10 distritos. Sem seleção, exibimos os dez com maior aderência aos filtros atuais.")

metrics = load_metrics()
if metrics.empty:
    st.info("Não há distritos disponíveis para comparar.")
    st.stop()
for key, default in SCENARIO_DEFAULTS.items():
    st.session_state.setdefault(f"scenario-value-{key}", default)
weights = {key: int(st.session_state[f"scenario-value-{key}"]) for key in SCENARIO_DEFAULTS}
score_weights = weights if sum(weights.values()) else SCENARIO_DEFAULTS
scored = SCENARIO_SCORER.score_neighborhoods(metrics, score_weights)
real_v2 = is_real_v2(scored)
palette = theme_palette()
district_map_service = DistrictMapService()
st.session_state.pop("selected-zone", None)  # Filtro de zona descontinuado.

# Busca e interesses do cabeçalho também restringem o Top 10 desta página.
eligible = ranking_filtrado(
    scored,
    busca=st.session_state.get("map-search", ""),
    filtros=st.session_state.get("map-quick-filters", []),
    perfil=st.session_state.get("home-profile-filter", "Todos os perfis"),
)
if eligible.empty:
    st.info("Nenhum distrito atende aos filtros selecionados. Volte à tela Explorar e revise a busca ou os interesses.")
    st.stop()

options = eligible["neighborhood"].astype(str).tolist()
if "comparison-neighborhoods-widget" not in st.session_state:
    st.session_state["comparison-neighborhoods-widget"] = list(
        st.session_state.get("comparison_neighborhoods", st.session_state.get("selected-neighborhoods", []))
    )
# A barra superior da versão anterior sincronizava apenas cinco nomes.
# Se ela foi a origem da seleção, restauramos até dez antes de montar o widget.
# Não restaura nomes fora do conjunto elegível pelos filtros ativos.
header_selection = st.session_state.get("selected-neighborhoods", [])
widget_selection = st.session_state.get("comparison-neighborhoods-widget", [])
st.session_state["comparison-neighborhoods-widget"] = reconcile_selection(
    header_selection, widget_selection, options, max_items=10,
)

selection_col, focus_col = st.columns([1.4, 1], gap="large")
with selection_col:
    chosen = st.multiselect(
        "Distritos da análise", options=options, key="comparison-neighborhoods-widget",
        max_selections=10, on_change=_sync_map_selection,
        placeholder="Selecione até 10 distritos (vazio = Top 10)",
    )
with focus_col:
    valid_focus_modes = ["Visão geral", "Empregos formais", "Perfis de Distrito"]
    if st.session_state.get("comparison-focus-mode") not in (*valid_focus_modes, None):
        st.session_state["comparison-focus-mode"] = "Visão geral"
    focus_mode = st.radio(
        "Foco da análise", options=valid_focus_modes, horizontal=True,
        key="comparison-focus-mode",
    )

comparison, automatic_top10 = selecionar_comparacao(eligible, chosen)
selected = comparison["neighborhood"].astype(str).tolist()
if comparison.empty:
    st.info("Não há distritos elegíveis para a comparação atual.")
    st.stop()
if automatic_top10:
    st.info(f"Nenhum distrito selecionado. Exibindo o Top {len(comparison)} do cenário filtrado.")
else:
    st.caption(f"Comparando {len(comparison)} distrito(s) selecionado(s).")
st.button("Limpar seleção e mostrar Top 10", key="comparison-clear-selection", on_click=_clear_comparison)

if real_v2:
    metric_options = dict(V2_INDICATORS)
    priority_options = dict(V2_WEIGHT_DIMENSIONS)
    # Valida a identidade original dos nove perfis a partir de dados completos.
    cluster_summary = build_cluster_comparison(scored, selected)
    # Dados exibidos no gráfico também devem respeitar busca e interesses.
    stats = eligible.groupby(["cluster", "perfil_id"], as_index=False).agg(
        distritos_no_perfil=("neighborhood", "nunique"),
        aderencia_media=("priority_score", "mean"),
    )
    cluster_summary = (
        cluster_summary.drop(columns=["distritos_no_perfil", "aderencia_media"])
        .merge(stats, on=["cluster", "perfil_id"], how="inner")
        .sort_values("codigo", kind="stable")
    )
    st.caption("Aderência às suas prioridades de verde e lazer, segurança, mobilidade e serviços públicos.")
else:
    metric_options = {label: column for label, column in _SAMPLE_INDICATORS.items()
                      if column in comparison.columns}
    priority_options = _SAMPLE_PRIORITIES
    cluster_summary = None
    st.warning("Você está conhecendo uma versão de demonstração.")

if focus_mode == "Empregos formais":
    dimensions = {"Empregos formais": "formal_jobs_score"}
else:
    dimensions = metric_options
radar_dimensions = metric_options

leader = comparison.iloc[0]
average_score = float(comparison["priority_score"].mean())
active = [
    (key, label, col)
    for key, (label, col) in priority_options.items()
    if weights.get(key, 0) > 0 and col in comparison.columns
    and pd.to_numeric(comparison[col], errors="coerce").notna().any()
]
priority = max(active, key=lambda x: weights[x[0]], default=None)

st.markdown("### Destaques dos distritos")
for offset in range(0, len(comparison), 3):
    cols = st.columns(3, gap="medium")
    for column, (_, row) in zip(cols, comparison.iloc[offset:offset + 3].iterrows()):
        name = escape(str(row["neighborhood"]))
        score = float(row["priority_score"])
        valid = [(title, float(row[field])) for title, field in metric_options.items()
                 if field in row and pd.notna(row[field])]
        strengths = sorted(valid, key=lambda pair: pair[1], reverse=True)[:2]
        strengths_copy = ", ".join(f"{escape(label)} ({value:.0f})" for label, value in strengths)
        profile_copy = (
            f'<p><b>Perfil de Distrito:</b> {escape(nome_perfil(row["cluster"]))}</p>'
            if real_v2 else ""
        )
        with column:
            st.markdown(
                '<div class="comparison-district-card">'
                f'<h4>{name}</h4>'
                f'<div class="district-score">{score:.1f}/100</div>'
                '<p>Aderência ao cenário</p>'
                f'<p><b>Destaques:</b> {strengths_copy or "Sem dados disponíveis"}</p>'
                f'{profile_copy}</div>',
                unsafe_allow_html=True,
            )

st.markdown("### Resumo da análise")
summary_col, map_col, top_col = st.columns([0.9, 1.65, 1.0], gap="medium")
with summary_col:
    with st.container(key="comparison-summary-panel", border=True):
        _summary_card("Distritos analisados", len(comparison))
        _summary_card("Líder do cenário", str(leader["neighborhood"]),
                      f'{float(leader["priority_score"]):.1f}/100')
        _summary_card("Média de aderência", f"{average_score:.1f}/100")
        _summary_card("Prioridade principal", priority[1] if priority else "Nenhuma",
                      f"Peso {weights[priority[0]]}" if priority else "")
with map_col:
    with st.container(key="comparison-map-card", border=True):
        st.markdown("#### Mapa dos distritos comparados")
        mapped, missing = district_map_service.restrict_to_mapped_districts(comparison)
        fig = district_map_service.build_map(
            mapped, theme=st.session_state.get("bairroiq-theme", "dark")
        )
        st.plotly_chart(fig, key="comparison-map", width="stretch", height=460,
                        config={"displayModeBar": False, "scrollZoom": True})
        if missing:
            st.caption("Sem limites no mapa: " + ", ".join(missing))
with top_col:
    with st.container(key="comparison-ranking-card", border=True):
        st.markdown("#### Top 10 do cenário")
        st.caption("Após busca, filtros de interesse e prioridades")
        for index, row in enumerate(top10_filtrado(eligible).to_dict("records"), start=1):
            st.markdown(
                '<div class="comparison-top-row">'
                f'<span>#{index} {escape(str(row["neighborhood"]))}</span>'
                f'<b>{float(row["priority_score"]):.1f}</b>'
                '</div>', unsafe_allow_html=True,
            )

st.markdown("### Resumo por indicador")
cols = ["neighborhood", *dimensions.values(), "priority_score"]
table = comparison.loc[:, cols].copy()
table.columns = ["Distrito", *dimensions.keys(), "Aderência"]
render_responsive_table(table, precision=1, label="Resumo por indicador")

if real_v2:
    with st.expander("Mais detalhes sobre os distritos", expanded=False):
        descriptive = comparison[["neighborhood", "cluster", "densidade_hab_km2", "robberies_per_1000"]].copy()
        descriptive.columns = ["Distrito", "Perfil de Distrito", "Densidade (hab./km²)", "Roubos por 1.000 hab."]
        descriptive["Perfil de Distrito"] = descriptive["Perfil de Distrito"].map(nome_perfil)
        render_responsive_table(
            descriptive, precision=1,
            column_precision={"Densidade (hab./km²)": 0, "Roubos por 1.000 hab.": 2},
            label="Detalhes territoriais",
        )

with st.expander("Gráficos: indicadores, comparações e Perfis de Distrito", expanded=False):
    st.session_state.setdefault("comparison-highlight-neighborhood", "Nenhum")
    highlight_options = ["Nenhum", *selected]
    if st.session_state["comparison-highlight-neighborhood"] not in highlight_options:
        st.session_state["comparison-highlight-neighborhood"] = "Nenhum"
    highlight = st.selectbox(
        "Destacar distrito nos gráficos", options=highlight_options,
        key="comparison-highlight-neighborhood",
    )
    bar_col, radar_col, profile_col = st.columns(3, gap="medium")
    with bar_col:
        with st.container(key="comparison-chart-indicators", border=True):
            st.markdown("#### Indicadores")
            if dimensions:
                melted = comparison.melt(
                    id_vars="neighborhood", value_vars=list(dimensions.values()),
                    var_name="indicator", value_name="score",
                )
                label_map = {v: k for k, v in dimensions.items()}
                melted["indicator"] = melted["indicator"].map(label_map)
                chart = px.bar(
                    melted, x="indicator", y="score", color="neighborhood",
                    barmode="group", color_discrete_sequence=_COLORS,
                    labels={"indicator": "Indicador", "score": "Índice (0–100)",
                            "neighborhood": "Distrito"},
                )
                chart.update_layout(
                    height=410, margin={"l": 16, "r": 16, "t": 12, "b": 105},
                    paper_bgcolor=palette["surface"], plot_bgcolor=palette["surface"],
                    font={"color": palette["ink"], "size": 11},
                    xaxis={"tickangle": -30, "automargin": True},
                    yaxis={"range": [0, 100], "gridcolor": palette["line"]},
                    legend={"orientation": "h", "y": -0.45, "font": {"size": 10}},
                )
                if highlight != "Nenhum":
                    for trace in chart.data:
                        trace.marker.opacity = 1 if trace.name == highlight else 0.18
                st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
            else:
                st.info("Sem indicadores disponíveis.")
    with radar_col:
        with st.container(key="comparison-chart-profile", border=True):
            st.markdown("#### Perfil por dimensão")
            radar = go.Figure()
            for _, row in comparison.iterrows():
                focus = highlight == "Nenhum" or str(row["neighborhood"]) == highlight
                radar.add_trace(go.Scatterpolar(
                    r=[float(row[field]) for field in radar_dimensions.values()],
                    theta=list(radar_dimensions.keys()), fill="toself",
                    name=str(row["neighborhood"]),
                    opacity=0.5 if highlight == "Nenhum" else (0.85 if focus else 0.12),
                    line={"width": 3 if focus and highlight != "Nenhum" else 1.7},
                ))
            radar.update_layout(
                polar={"radialaxis": {"visible": True, "range": [0, 100], "gridcolor": palette["line"]},
                       "angularaxis": {"gridcolor": palette["line"]}, "bgcolor": palette["surface"]},
                height=410, margin={"l": 35, "r": 35, "t": 12, "b": 95},
                paper_bgcolor=palette["surface"], font={"color": palette["ink"], "size": 11},
                colorway=_COLORS,
                legend={"orientation": "h", "y": -0.25, "font": {"size": 10}},
            )
            st.plotly_chart(radar, width="stretch", config={"displayModeBar": False})
    with profile_col:
        with st.container(key="comparison-chart-cluster", border=True):
            st.markdown("#### Perfis de Distrito")
            if not real_v2 or cluster_summary is None or cluster_summary.empty:
                st.info("Perfis disponíveis apenas para o conjunto territorial validado.")
            else:
                nomes_perfis = cluster_summary["cluster"].map(nome_perfil).tolist()
                chart = px.bar(
                    cluster_summary, x="codigo", y="aderencia_media", color="destaque",
                    category_orders={"codigo": cluster_summary["codigo"].tolist()},
                    color_discrete_map={
                        "Com distrito selecionado": "#218f75",
                        "Outros perfis": "#8b96a7",
                    },
                    custom_data=["cluster", "distritos_no_perfil"],
                    labels={"codigo": "Perfil de Distrito", "aderencia_media": "Aderência média (0–100)"},
                )
                chart.update_traces(
                    customdata=cluster_summary[["distritos_no_perfil"]].to_numpy(),
                    hovertemplate="Distritos elegíveis no perfil: %{customdata[0]}<br>Aderência média: %{y:.1f}/100<extra></extra>",
                )
                chart.update_layout(
                    height=410, margin={"l": 10, "r": 12, "t": 12, "b": 155},
                    paper_bgcolor=palette["surface"], plot_bgcolor=palette["surface"],
                    font={"color": palette["ink"], "size": 11},
                    xaxis={"type": "category", "tickangle": -45, "tickmode": "array",
                           "tickvals": cluster_summary["codigo"].tolist(),
                           "ticktext": nomes_perfis, "tickfont": {"size": 9}, "automargin": True},
                    yaxis={"range": [0, 100], "gridcolor": palette["line"]},
                    legend={"orientation": "h", "y": -0.35, "font": {"size": 10}},
                )
                st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
    if real_v2:
        st.caption("**Perfis de Distrito analisados:** " + " · ".join(
            selected_cluster_descriptions(scored, selected)
        ))
        st.caption("Aderência representa afinidade com preferências, não qualidade absoluta de vida.")

st.caption("Saiba mais sobre indicadores e limitações na página Fontes.")
