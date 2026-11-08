from __future__ import annotations

import streamlit as st

from bairroiq.map_data import (
    DistrictMapService,
)
from bairroiq.provider import load_metrics
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, SCENARIO_LABELS, render_header

render_header("personalize")

st.markdown("""
<style>
[data-testid="stAppViewBlockContainer"] { max-width: 1500px; padding: 4px 16px 16px !important; }
[data-testid="stAppViewContainer"] { overflow-x: hidden !important; overflow-y: auto !important; }
[data-testid="stMainBlockContainer"] {
  height: auto !important;
  min-height: calc(100dvh - 20px) !important;
  max-height: none !important;
  overflow: visible !important;
}
[data-testid="stHorizontalBlock"]:has(.st-key-startup-map) {
  align-items: flex-start !important;
  gap: 8px !important;
}
[data-testid="stHorizontalBlock"]:has(.st-key-startup-map) > [data-testid="stColumn"]:nth-child(1) {
  flex: 0 0 calc(75% - 4px) !important;
  width: calc(75% - 4px) !important;
  max-width: calc(75% - 4px) !important;
}
[data-testid="stHorizontalBlock"]:has(.st-key-startup-map) > [data-testid="stColumn"]:nth-child(2) {
  flex: 0 0 calc(25% - 4px) !important;
  width: calc(25% - 4px) !important;
  max-width: calc(25% - 4px) !important;
}

.st-key-startup-map {
  height: clamp(340px, 52dvh, 460px) !important;
  min-height: clamp(340px, 52dvh, 460px) !important;
  max-height: clamp(340px, 52dvh, 460px) !important;
  padding: 0 !important;
  overflow: hidden !important;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-sizing: border-box;
}
.st-key-startup-map > div,
.st-key-startup-map [data-testid="stPlotlyChart"],
.st-key-startup-map [data-testid="stPlotlyChart"] > div,
.st-key-startup-map .plot-container,
.st-key-startup-map .svg-container {
  height: clamp(338px, calc(52dvh - 2px), 458px) !important;
  min-height: 0 !important;
  max-height: clamp(338px, calc(52dvh - 2px), 458px) !important;
}
.st-key-startup-panel {
  height: calc(100dvh - 90px) !important;
  min-height: calc(100dvh - 90px) !important;
  max-height: calc(100dvh - 90px) !important;
  position: static !important;
  padding: 10px !important;
  overflow-y: hidden !important;
  overflow-x: hidden !important;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  box-sizing: border-box;
}
.st-key-startup-panel h3 { margin: 0 0 6px !important; font-size: 18px !important; }
.st-key-startup-panel h4 { margin: 0 0 5px !important; font-size: 14px !important; }
.st-key-startup-panel [data-testid="stVerticalBlock"] { gap: 0 !important; }
.st-key-startup-panel [data-testid="stVerticalBlockBorderWrapper"] {
  padding: 8px 10px !important;
  border-color: var(--line) !important;
  background: var(--navy) !important;
}
.st-key-startup-objectives,
.st-key-startup-budget,
.st-key-startup-priorities {
  width: 100% !important;
  min-width: 0 !important;
  box-sizing: border-box !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  background: var(--surface) !important;
  padding: 10px 12px !important;
}
.st-key-startup-priorities [data-testid="stSlider"] [role="group"] div[style*="left:"] {
  background: #ed5a00 !important;
  border: 2px solid #ed5a00 !important;
  border-radius: 50% !important;
  box-shadow: none !important;
  filter: none !important;
}
.st-key-startup-panel [data-testid="stVerticalBlock"]:has(.stSlider) > [data-testid="stElementContainer"]:nth-child(even) {
  margin-top: 0 !important;
}
.st-key-startup-panel > [data-testid="stLayoutWrapper"]:has(.stSlider) {
  flex: 1 1 auto !important;
  min-height: 0 !important;
}
.st-key-startup-panel > [data-testid="stLayoutWrapper"]:has(.stSlider) > [data-testid="stVerticalBlock"] {
  justify-content: space-between !important;
}
.st-key-startup-panel .stButton button {
  height: 36px !important;
  min-height: 36px !important;
  padding: 0 8px !important;
  font-size: 13px !important;
}
.st-key-startup-panel [data-testid="stSlider"] { margin: 0 !important; }
.st-key-startup-panel [data-testid="stWidgetLabel"],
.st-key-startup-panel [data-testid="stCaptionContainer"],
.st-key-startup-panel input {
  font-size: 13px !important;
}
.st-key-startup-panel [data-testid="stSlider"] [data-testid="stThumbValue"] {
  font-size: 13px !important;
}
.st-key-startup-objectives button[kind="primary"] {
  border: 1px solid var(--rust) !important;
  background: var(--rust) !important;
  color: #fff !important;
}
.st-key-startup-objectives [data-testid="stLayoutWrapper"]:has(> [data-testid="stHorizontalBlock"]) {
  margin-bottom: 8px !important;
}
.st-key-startup-objectives button[kind="primary"] p {
  color: #fff !important;
  font-weight: 700 !important;
}
.st-key-startup-actions {
  position: static !important;
  width: 100% !important;
  z-index: 10 !important;
  margin-top: auto !important;
  padding-top: 8px !important;
  background: var(--surface) !important;
  transform: none !important;
}

body:has(.st-key-startup-map) .section-heading {
  height: 32px !important;
  margin: 0 !important;
  line-height: 32px !important;
  font-weight: 700 !important;
  font-size: 20px !important;
}
:root {
  --startup-map-height: clamp(340px, 52dvh, 460px);
  --startup-zone-height: max(210px, calc(100dvh - 138px - var(--startup-map-height)));
}
[data-testid="stHorizontalBlock"]:has(.st-key-zone-card-norte) {
  width: 100% !important;
  height: var(--startup-zone-height) !important;
  align-items: stretch !important;
  gap: 8px !important;
  overflow: visible !important;
}
[data-testid="stHorizontalBlock"]:has(.st-key-zone-card-norte) > [data-testid="stColumn"] {
  flex: 1 1 0 !important;
  width: 20% !important;
  min-width: 0 !important;
  height: var(--startup-zone-height) !important;
}
.st-key-zone-card-norte,
.st-key-zone-card-sul,
.st-key-zone-card-leste,
.st-key-zone-card-oeste,
.st-key-zone-card-centro {
  width: 100% !important;
  height: var(--startup-zone-height) !important;
  min-height: var(--startup-zone-height) !important;
  max-height: var(--startup-zone-height) !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 0 !important;
  padding: 10px !important;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  box-sizing: border-box;
  color: var(--ink) !important;
}
.st-key-zone-card-norte > div,
.st-key-zone-card-sul > div,
.st-key-zone-card-leste > div,
.st-key-zone-card-oeste > div,
.st-key-zone-card-centro > div {
  width: 100% !important;
  min-height: 0 !important;
}
.st-key-zone-card-norte > [data-testid="stElementContainer"]:first-child,
.st-key-zone-card-sul > [data-testid="stElementContainer"]:first-child,
.st-key-zone-card-leste > [data-testid="stElementContainer"]:first-child,
.st-key-zone-card-oeste > [data-testid="stElementContainer"]:first-child,
.st-key-zone-card-centro > [data-testid="stElementContainer"]:first-child {
  flex: 1 1 auto !important;
  min-height: 0 !important;
  display: flex !important;
}
.st-key-zone-card-norte > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"],
.st-key-zone-card-sul > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"],
.st-key-zone-card-leste > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"],
.st-key-zone-card-oeste > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"],
.st-key-zone-card-centro > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] {
  width: 100% !important;
  height: 100% !important;
  flex: 1 1 auto !important;
  display: flex !important;
}
.st-key-zone-card-norte > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] > div,
.st-key-zone-card-sul > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] > div,
.st-key-zone-card-leste > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] > div,
.st-key-zone-card-oeste > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] > div,
.st-key-zone-card-centro > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] > div,
.st-key-zone-card-norte > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdownContainer"],
.st-key-zone-card-sul > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdownContainer"],
.st-key-zone-card-leste > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdownContainer"],
.st-key-zone-card-oeste > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdownContainer"],
.st-key-zone-card-centro > [data-testid="stElementContainer"]:first-child [data-testid="stMarkdownContainer"] {
  width: 100% !important;
  height: 100% !important;
  min-height: 0 !important;
  flex: 1 1 auto !important;
  display: flex !important;
  flex-direction: column !important;
}
.zone-card-content {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
}
.zone-card-title {
  height: 26px !important;
  flex: none;
  margin: 0 0 5px !important;
  line-height: 26px !important;
  font-size: 16px !important;
  font-weight: 700;
}
.zone-rankings {
  min-height: 0;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  justify-content: flex-start;
  gap: 8px;
}
.ranking-row {
  width: 100%;
  min-height: 40px !important;
  flex: none;
  padding: 0 8px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 4px !important;
  overflow: hidden !important;
  white-space: nowrap !important;
  border-radius: 6px;
  background: var(--navy);
  border: 1px solid var(--line);
}
.ranking-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
}
.ranking-row strong {
  flex: none;
  font-size: 14px;
}
.zone-empty {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px;
  color: var(--muted);
  text-align: center;
}
.zone-empty svg {
  width: 52px;
  height: 52px;
  color: #8b95a7;
}
.zone-empty p {
  max-width: 240px;
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
}
.st-key-zone-card-norte .stButton,
.st-key-zone-card-sul .stButton,
.st-key-zone-card-leste .stButton,
.st-key-zone-card-oeste .stButton,
.st-key-zone-card-centro .stButton { margin-top: auto !important; }
.st-key-zone-card-norte .stButton button,
.st-key-zone-card-sul .stButton button,
.st-key-zone-card-leste .stButton button,
.st-key-zone-card-oeste .stButton button,
.st-key-zone-card-centro .stButton button {
  min-height: 36px !important;
  height: 36px !important;
  font-size: 13px !important;
}

@media (max-width: 900px) {
  [data-testid="stAppViewBlockContainer"] { padding: 4px 8px 12px !important; }
  :root { --startup-map-height: 252px; }
  .st-key-startup-map { height: 252px !important; min-height: 252px !important; max-height: 252px !important; }
  .st-key-startup-map > div,
  .st-key-startup-map [data-testid="stPlotlyChart"],
  .st-key-startup-map [data-testid="stPlotlyChart"] > div,
  .st-key-startup-map .plot-container,
  .st-key-startup-map .svg-container { height: 250px !important; }
  .st-key-startup-panel { height: calc(100dvh - 90px) !important; min-height: 300px !important; max-height: calc(100dvh - 90px) !important; overflow-y: hidden !important; }
  .st-key-zone-card-norte,
  .st-key-zone-card-sul,
  .st-key-zone-card-leste,
  .st-key-zone-card-oeste,
  .st-key-zone-card-centro { height: var(--startup-zone-height) !important; min-height: var(--startup-zone-height) !important; max-height: var(--startup-zone-height) !important; }
}
.scenario-intro { display: none; }
</style>
""", unsafe_allow_html=True)

metrics = load_metrics()
district_map_service = DistrictMapService()
neighborhoods = metrics["neighborhood"].tolist()
if "personalize-objective-value" not in st.session_state:
    st.session_state["personalize-objective-value"] = "Morar"
if "selected-neighborhoods" not in st.session_state:
    st.session_state["selected-neighborhoods"] = []

# Valores são preferências ilustrativas, não probabilidades nem predições.
objective_profiles = {
    "Morar": {"trees": 85, "safety": 90, "mobility": 65, "infrastructure": 80},
    "Trabalhar": {"trees": 45, "safety": 65, "mobility": 100, "infrastructure": 65},
    "Investir": {"trees": 60, "safety": 60, "mobility": 80, "infrastructure": 80},
    "Negócios": {"trees": 50, "safety": 65, "mobility": 85, "infrastructure": 85},
}


def select_objective(name: str) -> None:
    st.session_state["personalize-objective-value"] = name
    for key, value in objective_profiles[name].items():
        st.session_state[f"scenario-value-{key}"] = value
        st.session_state[f"start-priority-{key}"] = value


def reset_scenario() -> None:
    for key, value in SCENARIO_DEFAULTS.items():
        st.session_state[f"scenario-value-{key}"] = value
        st.session_state[f"start-priority-{key}"] = value
    st.session_state["personalize-objective-value"] = "Morar"


def sync_priority(key: str) -> None:
    st.session_state[f"scenario-value-{key}"] = int(
        st.session_state[f"start-priority-{key}"]
    )


map_column, panel_column = st.columns([3.75, 1.0], gap="small")

with map_column:
    with st.container(key="startup-map", border=True):
        weights = {key: int(st.session_state.get(f"scenario-value-{key}", default)) for key, default in SCENARIO_DEFAULTS.items()}
        scored = SCENARIO_SCORER.score_neighborhoods(metrics, weights)
        # O cenário V2 deriva exclusivamente dos quatro pesos visíveis.
        # Botões de objetivos definem presets, sem bônus ocultos de 30%.
        preview = scored.copy()
        preview["personalization_score"] = preview["priority_score"]
        preview = preview.sort_values(
            "personalization_score",
            ascending=False,
        )
        map_preview, missing_boundaries = (
            district_map_service.restrict_to_mapped_districts(preview)
        )
        figure = district_map_service.build_map(
            map_preview,
            theme=st.session_state.get("bairroiq-theme", "light"),
            selectable=True,
        )
        st.plotly_chart(figure, width="stretch", height=460, config={"displayModeBar": False})
        if missing_boundaries:
            st.caption(
                "O mapa não tem limites cadastrados para: "
                f"{', '.join(missing_boundaries)}."
            )
        if preview.empty:
            st.info("Infelizmente não conseguimos localizar dados para as seleções solicitadas.")

    st.markdown('<div class="section-heading">Distritos por zona</div>', unsafe_allow_html=True)
    preview["zone"] = preview.apply(
        district_map_service.zone_for_neighborhood, axis=1
    )
    zone_columns = st.columns(5, gap="small")
    for index, zone_name in enumerate(("Norte", "Sul", "Leste", "Oeste", "Centro")):
        zone_rows = preview[preview["zone"] == zone_name].head(3)
        with zone_columns[index]:
            with st.container(
                key=f"zone-card-{zone_name.lower()}",
                border=True,
            ):
                if zone_rows.empty:
                    zone_content = (
                        f"<div class='zone-card-content'>"
                        f"<div class='zone-card-title'>{zone_name}</div>"
                        "<div class='zone-empty'>"
                        "<svg viewBox='0 0 64 64' fill='none' aria-label='Rosto triste'>"
                        "<circle cx='32' cy='32' r='25' stroke='currentColor' stroke-width='3'/>"
                        "<circle cx='23' cy='25' r='2.5' fill='currentColor'/>"
                        "<circle cx='41' cy='25' r='2.5' fill='currentColor'/>"
                        "<path d='M21 45c2.5-6 7-9 11-9s8.5 3 11 9' "
                        "stroke='currentColor' stroke-width='3' stroke-linecap='round'/>"
                        "</svg>"
                        "<p>Infelizmente não conseguimos localizar dados para as seleções solicitadas.</p>"
                        "</div></div>"
                    )
                else:
                    ranking_rows = "".join(
                        f"<div class='ranking-row'><span>#{rank} {row['neighborhood']}</span>"
                        f"<strong>{row['personalization_score']:.1f}</strong></div>"
                        for rank, row in enumerate(
                            zone_rows.to_dict(orient="records"),
                            start=1,
                        )
                    )
                    zone_content = (
                        f"<div class='zone-card-content'>"
                        f"<div class='zone-card-title'>{zone_name}</div>"
                        f"<div class='zone-rankings'>{ranking_rows}</div>"
                        "</div>"
                    )
                st.markdown(zone_content, unsafe_allow_html=True)
                if st.button(
                    "Explorar zona",
                    key=f"explore-zone-{zone_name}",
                    width="stretch",
                    disabled=zone_rows.empty,
                ):
                    st.session_state["selected-zone"] = zone_name
                    st.session_state["selected-neighborhoods"] = zone_rows[
                        "neighborhood"
                    ].tolist() if not zone_rows.empty else []
                    st.session_state["comparison_neighborhoods"] = st.session_state[
                        "selected-neighborhoods"
                    ][:5]
                    st.session_state["comparison-neighborhoods-widget"] = st.session_state[
                        "selected-neighborhoods"
                    ][:5]
                    st.switch_page("pages/explorar.py")

with panel_column:
    with st.container(key="startup-panel"):
        st.markdown("### Monte seu cenário")

        with st.container(key="startup-objectives", border=True):
            st.markdown("#### Objetivo")
            objectives = [("⌂", "Morar"), ("▣", "Trabalhar"), ("↗", "Investir"), ("▤", "Negócios")]
            for row in range(2):
                objective_columns = st.columns(2, gap="small")
                for column, (icon, name) in zip(objective_columns, objectives[row * 2:(row + 1) * 2]):
                    with column:
                        active = st.session_state["personalize-objective-value"] == name
                        st.button(
                            f"{icon}  {name}",
                            key=f"start-objective-{name}",
                            type="primary" if active else "secondary",
                            width="stretch",
                            on_click=select_objective,
                            args=(name,),
                        )

        with st.container(key="startup-budget", border=True):
            st.markdown("#### Informações complementares")
            st.caption(
                "Empregos formais e densidade populacional são exibidos "
                "nas análises dos distritos, sem interferir no ranking. "
                "Ainda não há dados de custo de vida validados."
            )

        with st.container(key="startup-priorities", border=True):
            st.markdown("#### Minhas prioridades")
            priorities = {}
            for key, label in SCENARIO_LABELS.items():
                widget_key = f"start-priority-{key}"
                value = int(
                    st.session_state.get(
                        widget_key,
                        st.session_state.get(
                            f"scenario-value-{key}",
                            SCENARIO_DEFAULTS[key],
                        ),
                    )
                )
                st.markdown(f'<div style="display:flex;justify-content:space-between;font-size:14px;line-height:1.2;margin:5px 0 -4px"><span>{label}</span><strong>{value}</strong></div>', unsafe_allow_html=True)
                priority_value = st.slider(
                    label,
                    0,
                    100,
                    value,
                    1,
                    key=widget_key,
                    label_visibility="collapsed",
                    on_change=sync_priority,
                    args=(key,),
                )
                priorities[key] = int(priority_value)

        with st.container(key="startup-actions"):
            apply_column, reset_column = st.columns(2, gap="small")
            with apply_column:
                if st.button("Aplicar filtros", type="primary", width="stretch", disabled=sum(priorities.values()) == 0):
                    st.session_state["comparison_neighborhoods"] = scored.head(10)["neighborhood"].tolist()[:5]
                    st.session_state["comparison-neighborhoods-widget"] = scored.head(10)["neighborhood"].tolist()[:5]
                    st.session_state["selected-neighborhoods"] = []
                    st.session_state.pop("map-priority-selection-initialized", None)
                    st.session_state["selected-zone"] = None
                    st.session_state["personalize-complete"] = True
                    st.switch_page("pages/explorar.py")
            with reset_column:
                st.button(
                    "Restaurar padrão",
                    width="stretch",
                    on_click=reset_scenario,
                )
