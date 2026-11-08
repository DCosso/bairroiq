"""Explorar / Mapa do BairroIQ.

Mantém os painéis, checkboxes e eventos da interface da Laís.
No Consumer V2, exibe indicadores reais sobre 96 polígonos distritais oficiais;
para malhas parciais, há opção de pontos nos centroides.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from bairroiq.map_data import DistrictMapService
from bairroiq.explore_logic import calcular_exploracao
from bairroiq.ux_labels import nome_perfil
from bairroiq.provider import load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, render_header


_SELECTION_KEY = "selected-neighborhoods"
district_map_service = DistrictMapService()


def _format_indicator(value: float, *, decimals: int = 1) -> str:
    if pd.isna(value):
        return "Indisponível"
    return f"{float(value):,.{decimals}f}"


def _close_district_details() -> None:
    st.session_state["active-district-detail"] = None


def _update_selection(neighborhood: str) -> None:
    selected = set(st.session_state.get(_SELECTION_KEY, []))
    checkbox_key = f"district-checkbox-{neighborhood}"
    if st.session_state[checkbox_key]:
        selected.add(neighborhood)
    else:
        selected.discard(neighborhood)
    st.session_state[_SELECTION_KEY] = [
        name for name in st.session_state["neighborhood-options"] if name in selected
    ]
    st.session_state["comparison_neighborhoods"] = st.session_state[_SELECTION_KEY][:5]
    st.session_state["comparison-neighborhoods-widget"] = st.session_state[
        _SELECTION_KEY
    ][:5]


def _open_comparison() -> None:
    selected = st.session_state.get(_SELECTION_KEY, [])[:5]
    if selected:
        st.session_state["comparison_neighborhoods"] = selected
        st.session_state["comparison-neighborhoods-widget"] = selected


metrics = load_metrics()
neighborhood_names = metrics["neighborhood"].tolist()
if not neighborhood_names:
    st.error("A base não contém distritos para exibir.")
    st.stop()

is_real_v2 = {
    "green_leisure_score", "public_services_score", "densidade_hab_km2",
    "robberies_per_1000", "perfil_id", "cluster",
}.issubset(metrics.columns)

# Uma seleção vazia é intencional: significa ver todos os distritos.
if "map-priority-selection-initialized" not in st.session_state:
    st.session_state["map-priority-selection-initialized"] = True

render_header("explore")
st.session_state["neighborhood-options"] = neighborhood_names

for weight, default in SCENARIO_DEFAULTS.items():
    widget_key = f"scenario-{weight}"
    persisted_key = f"scenario-value-{weight}"
    if persisted_key not in st.session_state:
        st.session_state[persisted_key] = int(st.session_state.get(widget_key, default))
    st.session_state[widget_key] = int(st.session_state[persisted_key])


@st.fragment
def render_map_explorer() -> None:
    search = st.session_state.get("map-search", "")
    quick_filters = st.session_state.get("map-quick-filters", [])
    weights = {
        name: int(st.session_state[f"scenario-{name}"])
        for name in SCENARIO_DEFAULTS
    }
    weights_for_score = weights if sum(weights.values()) else SCENARIO_DEFAULTS
    all_scored = SCENARIO_SCORER.score_neighborhoods(metrics, weights_for_score)
    selected_names = st.session_state[_SELECTION_KEY]
    for name in neighborhood_names:
        checkbox_key = f"district-checkbox-{name}"
        if st.session_state.get(checkbox_key) != (name in selected_names):
            st.session_state[checkbox_key] = name in selected_names

    # O Top 10, as opções do mapa e os resultados da busca precisam usar
    # exatamente os mesmos filtros. A seleção de distritos só restringe o mapa.
    scored, top10_ranking, visible = calcular_exploracao(
        all_scored, selected_names, search, quick_filters,
        zona=st.session_state.get("selected-zone"),
        identificar_zona=district_map_service.zone_for_neighborhood,
    )
    if scored.empty:
        st.info("Nenhum distrito combina com esses filtros. Tente retirar um deles.")
        return
    if visible.empty:
        st.info(
            "Os distritos escolhidos não atendem aos filtros atuais. "
            "Você pode limpar a seleção para ver todas as opções disponíveis."
        )
        return
    top10_names = top10_ranking["neighborhood"].tolist()
    st.session_state["top10-neighborhoods"] = top10_names
    selected_ranking = district_map_service.selected_district_ranking(
        scored, selected_names
    )
    selected_ranking = selected_ranking[
        ~selected_ranking["neighborhood"].isin(top10_names)
    ]
    ranking_rows = [
        *top10_ranking.to_dict(orient="records"),
        *selected_ranking.to_dict(orient="records"),
    ]
    map_visible, missing_boundaries = district_map_service.restrict_to_mapped_districts(visible)
    figure = district_map_service.build_map(
        map_visible,
        theme=st.session_state.get("bairroiq-theme", "light"),
        selectable=True,
    )
    scenario_insight = SCENARIO_SCORER.build_scenario_insight(
        scored, weights, selected_names
    )

    visible_names = visible["neighborhood"].tolist()
    active_detail = st.session_state.get("active-district-detail")
    if active_detail not in visible_names:
        active_detail = None
        st.session_state["active-district-detail"] = None

    with st.container(key="map-stage"):
        map_generation = int(st.session_state.get("neighborhood-map-generation", 0))
        previous_map_key = f"neighborhood-map-{map_generation - 1}"
        if map_generation and previous_map_key in st.session_state:
            del st.session_state[previous_map_key]

        map_state = st.plotly_chart(
            figure,
            key=f"neighborhood-map-{map_generation}",
            width="stretch", height="stretch",
            config={"displayModeBar": False, "scrollZoom": True},
            on_select="rerun", selection_mode="points",
        )
        if not is_real_v2 and "illustrative_boundary" in map_visible.columns and map_visible["illustrative_boundary"].any():
            st.caption("Algumas regiões de exemplo estão representadas de forma ilustrativa.")
        if missing_boundaries:
            st.warning(
                "Não foi possível mostrar no mapa: "
                f"{', '.join(missing_boundaries)}. Eles continuam disponíveis "
                "nas outras opções de consulta."
            )

        selected_points = map_state.selection.points
        clicked_district = district_map_service.district_from_selection(
            selected_points, visible_names
        )
        if clicked_district:
            st.session_state["active-district-detail"] = district_map_service.toggle_district_detail(
                active_detail, clicked_district
            )
            st.session_state["neighborhood-map-generation"] = map_generation + 1
            st.rerun()

        active_detail = st.session_state.get("active-district-detail")
        if active_detail not in visible_names:
            active_detail = None
            st.session_state["active-district-detail"] = None
        fallback_names = visible_names or selected_names or scored["neighborhood"].tolist()
        focus_name = active_detail or fallback_names[0]
        focus = scored.loc[scored["neighborhood"] == focus_name].iloc[0]

        if active_detail:
            with st.container(key="district-popup"):
                st.markdown(f"### {escape(active_detail)} ({focus['priority_score']:.1f})")
                if is_real_v2:
                    metrics_html = (
                        f'<span>Empregos <strong>{_format_indicator(focus["formal_jobs_score"])}</strong></span>'
                        f'<span>Segurança <strong>{_format_indicator(focus["safety_score"])}</strong></span>'
                        f'<span>Verde e lazer <strong>{_format_indicator(focus["green_leisure_score"])}</strong></span>'
                        f'<span>Mobilidade <strong>{_format_indicator(focus["mobility_score"])}</strong></span>'
                        f'<span>Serviços públicos <strong>{_format_indicator(focus["public_services_score"])}</strong></span>'
                        f'<span>Densidade <strong>{_format_indicator(focus["densidade_hab_km2"], decimals=0)} hab./km²</strong></span>'
                        f'<span>Roubos <strong>{_format_indicator(focus["robberies_per_1000"], decimals=2)} /1.000 hab.</strong></span>'
                        f'<span>Estilo da região <strong>{escape(nome_perfil(focus["cluster"]))}</strong></span>'
                    )
                else:
                    metrics_html = (
                        f'<span>Empregos <strong>{_format_indicator(focus["formal_jobs_score"])}</strong></span>'
                        f'<span>Segurança <strong>{_format_indicator(focus["safety_score"])}</strong></span>'
                        f'<span>LED <strong>{_format_indicator(focus["lighting_led"])}</strong></span>'
                        f'<span>Arborização <strong>{_format_indicator(focus["trees_score"])}</strong></span>'
                        f'<span>Mobilidade <strong>{_format_indicator(focus["mobility_score"])}</strong></span>'
                        f'<span>Orçamento <strong>{_format_indicator(focus["affordability_score"])}</strong></span>'
                    )
                st.markdown(
                    '<div class="district-metrics">' + metrics_html + '</div>',
                    unsafe_allow_html=True,
                )
                if scenario_insight.dominant_priority:
                    st.markdown(
                        '<div class="scenario-recommendation">'
                        f'<div class="duel-label">Sugestão · {escape(scenario_insight.dominant_priority)} '
                        f'({scenario_insight.dominant_weight}/100)</div>'
                        f'<p>Reforce {escape(scenario_insight.dominant_priority.lower())} em '
                        f'<strong>{escape(str(scenario_insight.recommended_name))}</strong> '
                        f'({scenario_insight.recommended_score:.1f}/100).</p>'
                        f'<p>{escape(scenario_insight.leader_name)} lidera o cenário com '
                        f'{scenario_insight.leader_score:.1f}/100.</p>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("Ajuste uma prioridade para receber uma sugestão.")
                st.button(
                    "Fechar", key="close-district-details", width="stretch",
                    on_click=_close_district_details,
                )
        with st.container(key="ranking-panel", border=True):
            st.markdown("### Distritos que combinam com você")
            st.caption("As melhores combinações com suas preferências e suas escolhas")
            if not ranking_rows:
                st.caption("Nenhum distrito encontrado para as seleções solicitadas.")
            else:
                for rank, row in enumerate(ranking_rows, start=1):
                    name = str(row["neighborhood"])
                    st.checkbox(
                        f"#{rank} {name} · {row['priority_score']:.1f}/100",
                        key=f"district-checkbox-{name}",
                        on_change=_update_selection, args=(name,),
                    )
            with st.container(key="ranking-compare-button"):
                if st.button(
                    "Comparar", key="open-comparison", type="primary",
                    width="stretch",
                    disabled=not bool(st.session_state.get(_SELECTION_KEY, [])),
                ):
                    _open_comparison()
                    st.switch_page("pages/comparar.py")
            st.caption("Clique no mapa para conhecer cada distrito.")


render_map_explorer()
