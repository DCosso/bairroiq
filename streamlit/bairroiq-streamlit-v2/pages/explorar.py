from __future__ import annotations

import pandas as pd
import streamlit as st

from bairroiq.map_data import (
    DistrictMapService,
)
from bairroiq.provider import load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import (
    SCENARIO_DEFAULTS,
    render_header,
)


_SELECTION_KEY = "selected-neighborhoods"
district_map_service = DistrictMapService()


def _format_indicator(value: float) -> str:
    return f"{value:.1f}" if pd.notna(value) else "Indisponível"


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
    selected = st.session_state.get(_SELECTION_KEY, [])
    if selected:
        st.session_state["comparison_neighborhoods"] = selected
        st.session_state["comparison-neighborhoods-widget"] = selected


metrics = load_metrics()
neighborhood_names = metrics["neighborhood"].tolist()
if not neighborhood_names:
    st.error("A base não contém bairros para exibir.")
    st.stop()

if "map-priority-selection-initialized" not in st.session_state:
    if not st.session_state.get(_SELECTION_KEY) and not st.session_state.get(
        "selected-zone"
    ):
        initial_weights = {
            key: int(st.session_state.get(f"scenario-value-{key}", default))
            for key, default in SCENARIO_DEFAULTS.items()
        }
        initial_weights = (
            initial_weights
            if sum(initial_weights.values())
            else SCENARIO_DEFAULTS
        )
        initial_scored = SCENARIO_SCORER.score_neighborhoods(
            metrics, initial_weights
        )
        st.session_state[_SELECTION_KEY] = initial_scored["neighborhood"].tolist()
    st.session_state["map-priority-selection-initialized"] = True

render_header("explore")
st.session_state["neighborhood-options"] = neighborhood_names

for weight, default in SCENARIO_DEFAULTS.items():
    widget_key = f"scenario-{weight}"
    persisted_key = f"scenario-value-{weight}"
    if persisted_key not in st.session_state:
        st.session_state[persisted_key] = int(
            st.session_state.get(widget_key, default)
        )
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
    all_scored = SCENARIO_SCORER.score_neighborhoods(
        metrics, weights_for_score
    )
    scored = all_scored
    selected_names = st.session_state[_SELECTION_KEY]
    for name in neighborhood_names:
        checkbox_key = f"district-checkbox-{name}"
        if st.session_state.get(checkbox_key) != (name in selected_names):
            st.session_state[checkbox_key] = name in selected_names

    selected_zone = st.session_state.get("selected-zone")
    if selected_zone:
        scored["zone"] = scored.apply(
            district_map_service.zone_for_neighborhood, axis=1
        )
        scored = scored[scored["zone"] == selected_zone].copy()
    top10_ranking = scored.head(10)
    top10_names = top10_ranking["neighborhood"].tolist()
    st.session_state["top10-neighborhoods"] = top10_names
    selected_ranking = district_map_service.selected_district_ranking(
        all_scored,
        st.session_state.get(_SELECTION_KEY, []),
    )
    selected_ranking = selected_ranking[
        ~selected_ranking["neighborhood"].isin(top10_names)
    ]
    ranking_rows = [
        *top10_ranking.to_dict(orient="records"),
        *selected_ranking.to_dict(orient="records"),
    ]
    if selected_zone and selected_names:
        selected_names = [
            name for name in selected_names if name in top10_names
        ]
    elif selected_zone:
        selected_names = top10_names
    visible = district_map_service.filter_districts(
        scored, selected_names, search, quick_filters
    )
    map_visible, missing_boundaries = (
        district_map_service.restrict_to_mapped_districts(visible)
    )
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
    if active_detail not in selected_names:
        active_detail = None
        st.session_state["active-district-detail"] = None

    with st.container(key="map-stage"):
        map_generation = int(
            st.session_state.get("neighborhood-map-generation", 0)
        )
        previous_map_key = f"neighborhood-map-{map_generation - 1}"
        if map_generation and previous_map_key in st.session_state:
            del st.session_state[previous_map_key]

        map_state = st.plotly_chart(
            figure,
            key=f"neighborhood-map-{map_generation}",
            width="stretch",
            height="stretch",
            config={"displayModeBar": False, "scrollZoom": True},
            on_select="rerun",
            selection_mode="points",
        )
        if (
            "illustrative_boundary" in map_visible.columns
            and map_visible["illustrative_boundary"].any()
        ):
            st.caption("Os limites de alguns bairros demonstrativos são ilustrativos.")
        if missing_boundaries:
            st.warning(
                "O mapa não tem limites cadastrados para: "
                f"{', '.join(missing_boundaries)}. Eles continuam disponíveis "
                "nas listas e nos cálculos."
            )
        selected_points = map_state.selection.points
        clicked_district = district_map_service.district_from_selection(
            selected_points, visible_names
        )
        if clicked_district:
            st.session_state["active-district-detail"] = (
                district_map_service.toggle_district_detail(
                active_detail, clicked_district
                )
            )
            st.session_state["neighborhood-map-generation"] = map_generation + 1
            st.rerun()

        active_detail = st.session_state.get("active-district-detail")
        if active_detail not in selected_names:
            active_detail = None
            st.session_state["active-district-detail"] = None
        focus_name = active_detail or (
            visible_names or selected_names or neighborhood_names
        )[0]
        focus = scored.loc[scored["neighborhood"] == focus_name].iloc[0]

        if active_detail:
            with st.container(key="district-popup"):
                st.markdown(f"### {active_detail} ({focus['priority_score']:.1f})")
                st.markdown(
                    '<div class="district-metrics">'
                    f'<span>Empregos <strong>{_format_indicator(focus["formal_jobs_score"])}</strong></span>'
                    f'<span>Segurança <strong>{_format_indicator(focus["safety_score"])}</strong></span>'
                    f'<span>LED <strong>{_format_indicator(focus["lighting_led"])}</strong></span>'
                    f'<span>Arborização <strong>{_format_indicator(focus["trees_score"])}</strong></span>'
                    f'<span>Mobilidade <strong>{_format_indicator(focus["mobility_score"])}</strong></span>'
                    f'<span>Orçamento <strong>{_format_indicator(focus["affordability_score"])}</strong></span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                if scenario_insight.dominant_priority:
                    st.markdown(
                        '<div class="scenario-recommendation">'
                        f'<div class="duel-label">Sugestão · {scenario_insight.dominant_priority} '
                        f'({scenario_insight.dominant_weight}/100)</div>'
                        f'<p>Reforce {scenario_insight.dominant_priority.lower()} em '
                        f'<strong>{scenario_insight.recommended_name}</strong> '
                        f'({scenario_insight.recommended_score:.1f}/100).</p>'
                        f'<p>{scenario_insight.leader_name} lidera o cenário com '
                        f'{scenario_insight.leader_score:.1f}/100.</p>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("Ajuste uma prioridade para receber uma sugestão.")
                st.button(
                    "Fechar",
                    key="close-district-details",
                    width="stretch",
                    on_click=_close_district_details,
                )
        with st.container(key="ranking-panel", border=True):
            st.markdown("### Melhores Distritos")
            st.caption("Top 10 do cenário e distritos selecionados")
            if not ranking_rows:
                st.caption("Infelizmente não conseguimos localizar dados para as seleções solicitadas.")
            else:
                for rank, row in enumerate(
                    ranking_rows, start=1
                ):
                    name = str(row["neighborhood"])
                    st.checkbox(
                        f"#{rank} {name} · {row['priority_score']:.1f}/100",
                        key=f"district-checkbox-{name}",
                        on_change=_update_selection,
                        args=(name,),
                    )
            with st.container(key="ranking-compare-button"):
                if st.button(
                    "Comparar",
                    key="open-comparison",
                    type="primary",
                    width="stretch",
                    disabled=not bool(st.session_state.get(_SELECTION_KEY, [])),
                ):
                    _open_comparison()
                    st.switch_page("pages/comparar.py")
            st.caption("Clique em um bairro no mapa para ver sua análise.")


render_map_explorer()
