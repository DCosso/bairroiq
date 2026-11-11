"""Início: cenário personalizado, mapa, Top 10 e Perfis de Distrito.

Não calcula perfis novos. Usa apenas os nomes e indicadores publicados.
Sem agregação por zona geográfica.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from bairroiq.map_data import DistrictMapService
from bairroiq.provider import load_metrics
from bairroiq.ranking_ux import ranking_filtrado, resumo_perfis
from bairroiq.scoring import SCENARIO_SCORER
from bairroiq.ui import SCENARIO_DEFAULTS, SCENARIO_LABELS, render_header
from bairroiq.ux_labels import nome_perfil


OBJECTIVES = {
    "Morar": {"trees": 85, "safety": 90, "mobility": 65, "infrastructure": 80},
    "Trabalhar": {"trees": 45, "safety": 65, "mobility": 100, "infrastructure": 65},
    "Investir": {"trees": 60, "safety": 60, "mobility": 80, "infrastructure": 80},
    "Negócios": {"trees": 50, "safety": 65, "mobility": 85, "infrastructure": 85},
}


def select_objective(name: str) -> None:
    st.session_state["personalize-objective-value"] = name
    for key, value in OBJECTIVES[name].items():
        st.session_state[f"scenario-value-{key}"] = value
        st.session_state[f"start-priority-{key}"] = value


def sync_priority(key: str) -> None:
    st.session_state[f"scenario-value-{key}"] = int(
        st.session_state[f"start-priority-{key}"]
    )


def reset_scenario() -> None:
    for key, value in SCENARIO_DEFAULTS.items():
        st.session_state[f"scenario-value-{key}"] = value
        st.session_state[f"start-priority-{key}"] = value
    st.session_state["personalize-objective-value"] = "Morar"
    st.session_state["home-profile-filter"] = "Todos os perfis"
    st.session_state["home-profile-applied"] = "Todos os perfis"
    st.session_state["map-search"] = ""
    st.session_state["map-search-suggestion"] = None
    st.session_state["map-quick-filters"] = []
    st.session_state.pop("selected-zone", None)


def sync_home_profile() -> None:
    """Mantém o filtro de Perfil de Distrito na navegação subsequente."""
    choice = st.session_state.get("home-profile-filter", "Todos os perfis")
    old = st.session_state.get("home-profile-applied", "Todos os perfis")
    if choice != "Todos os perfis":
        st.session_state["map-search"] = choice
        st.session_state["map-search-suggestion"] = choice
    elif old != "Todos os perfis":
        # Limpa somente a busca associada ao perfil anterior.
        if st.session_state.get("map-search") == old:
            st.session_state["map-search"] = ""
        if st.session_state.get("map-search-suggestion") == old:
            st.session_state["map-search-suggestion"] = None
    st.session_state["home-profile-applied"] = choice


def explore_profile(profile_name: str) -> None:
    # O filtro existente do explorador reconhece exatamente os nomes dos perfis.
    st.session_state["map-search"] = profile_name
    st.session_state["map-search-suggestion"] = profile_name
    st.session_state["map-quick-filters"] = []
    st.session_state["selected-neighborhoods"] = []
    st.session_state["comparison_neighborhoods"] = []
    st.session_state["comparison-neighborhoods-widget"] = []
    st.session_state.pop("selected-zone", None)
    st.switch_page("pages/explorar.py")


render_header("personalize")
st.markdown("""
<style>
/* Escopo da página inicial. Preserva a navegação e demais páginas. */
body:has(.st-key-startup-map) .st-key-startup-map {
  height: auto !important; min-height: 360px !important;
  max-height: none !important; overflow: visible !important;
  padding: .45rem !important;
}
body:has(.st-key-startup-map) .st-key-startup-map > div {
  height: auto !important; max-height: none !important;
}
body:has(.st-key-startup-map) .st-key-startup-panel {
  height: auto !important; min-height: 0 !important;
  max-height: none !important; overflow: visible !important;
}
body:has(.st-key-startup-map) .st-key-startup-panel [data-testid="stVerticalBlock"] {
  height: auto !important; min-height: 0 !important;
}
body:has(.st-key-startup-map) .st-key-startup-panel [data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--line); border-radius: 12px;
}
body:has(.st-key-startup-map) [class*="st-key-district-profile-"] {
  border: 1px solid var(--line) !important;
  background: var(--surface) !important;
  border-radius: 12px !important;
  min-height: 195px; padding: .65rem !important;
}
body:has(.st-key-startup-map) .profile-header { font-size: 1.08rem; line-height: 1.35; font-weight: 750; color: var(--ink); min-height: 2.6em; }
body:has(.st-key-startup-map) .profile-stat { font-size: .9rem; color: var(--muted); margin: .28rem 0; }
body:has(.st-key-startup-map) .profile-score { font-weight: 750; color: var(--ink); }
body:has(.st-key-startup-map) .profile-district { font-size: .89rem; color: var(--ink); margin: .24rem 0; }
body:has(.st-key-startup-map) [class*="st-key-district-profile-"] [data-testid="stButton"] button,
body:has(.st-key-startup-map) .st-key-startup-actions button {
  width: 100% !important; min-height: 44px !important;
  background: #184977 !important; color: #fff !important;
  border: 1px solid #356a9a !important; border-radius: 9px !important;
  font-size: .9rem !important; font-weight: 700 !important;
}
body:has(.st-key-startup-map) [class*="st-key-district-profile-"] [data-testid="stButton"] button p,
body:has(.st-key-startup-map) .st-key-startup-actions button p { color: #fff !important; }
body:has(.st-key-startup-map) [class*="st-key-district-profile-"] button:hover,
body:has(.st-key-startup-map) .st-key-startup-actions button:hover {
  background: #25669e !important; border-color: #98c6ee !important;
}
body:has(.st-key-startup-map) .st-key-startup-panel [data-testid="stSlider"] { margin-bottom: .35rem; }
@media (max-width: 900px) {
  body:has(.st-key-startup-map) [class*="st-key-district-profile-"] { min-height: 0 !important; }
  body:has(.st-key-startup-map) .st-key-startup-map { min-height: 265px !important; }
  body:has(.st-key-startup-map) .st-key-startup-panel { height: auto !important; min-height: 0 !important; max-height: none !important; overflow: visible !important; }
  body:has(.st-key-startup-map) [data-testid="stHorizontalBlock"]:has(.st-key-startup-map) > [data-testid="stColumn"] { width: 100% !important; flex: 1 1 100% !important; }
}
</style>
""", unsafe_allow_html=True)

metrics = load_metrics()
if metrics.empty:
    st.error("Nenhum distrito disponível para análise.")
    st.stop()
st.session_state.setdefault("personalize-objective-value", "Morar")
st.session_state.setdefault("selected-neighborhoods", [])
st.session_state.pop("selected-zone", None)  # Migração da navegação antiga por zonas.

for key, default in SCENARIO_DEFAULTS.items():
    st.session_state.setdefault(f"scenario-value-{key}", default)
    st.session_state.setdefault(f"start-priority-{key}", st.session_state[f"scenario-value-{key}"])
weights = {key: int(st.session_state[f"scenario-value-{key}"]) for key in SCENARIO_DEFAULTS}
score_weights = weights if sum(weights.values()) else SCENARIO_DEFAULTS
scored = SCENARIO_SCORER.score_neighborhoods(metrics, score_weights)
preview = scored.copy()
preview["personalization_score"] = preview["priority_score"]

# Uma única regra de filtros e ranking para o mapa, os cartões e o Top 10.
profile_names = sorted({nome_perfil(v) for v in scored["cluster"].unique()}) if "cluster" in scored else []
profile_options = ["Todos os perfis", *profile_names]
if st.session_state.get("home-profile-filter", "Todos os perfis") not in profile_options:
    st.session_state["home-profile-filter"] = "Todos os perfis"

st.markdown("### Explore São Paulo conforme suas prioridades")
map_column, panel_column = st.columns([3.35, 1.2], gap="medium")
with panel_column:
    with st.container(key="startup-panel", border=True):
        st.markdown("#### Monte seu cenário")
        with st.container(key="startup-objectives", border=True):
            st.markdown("**Objetivo**")
            for duo in (("Morar", "Trabalhar"), ("Investir", "Negócios")):
                a, b = st.columns(2, gap="small")
                for column, name in zip((a, b), duo):
                    with column:
                        st.button(
                            name, key=f"start-objective-{name}",
                            type="primary" if st.session_state["personalize-objective-value"] == name else "secondary",
                            width="stretch", on_click=select_objective, args=(name,),
                        )
        with st.container(key="startup-budget", border=True):
            st.markdown("**Informações complementares**")
            st.caption("Empregos e densidade aparecem nas análises, mas não alteram o ranking. Não há custo de vida validado.")
        with st.container(key="startup-priorities", border=True):
            st.markdown("**Minhas prioridades**")
            for key, label in SCENARIO_LABELS.items():
                st.slider(label, 0, 100, step=1, key=f"start-priority-{key}",
                          on_change=sync_priority, args=(key,))
        with st.container(key="startup-actions"):
            a, b = st.columns(2, gap="small")
            with a:
                if st.button("Aplicar filtros", type="primary", width="stretch", disabled=sum(weights.values()) == 0):
                    st.session_state["selected-neighborhoods"] = []
                    st.session_state["comparison_neighborhoods"] = []
                    st.session_state["comparison-neighborhoods-widget"] = []
                    profile = st.session_state.get("home-profile-filter", "Todos os perfis")
                    if profile != "Todos os perfis":
                        st.session_state["map-search"] = profile
                        st.session_state["map-search-suggestion"] = profile
                    st.session_state.pop("selected-zone", None)
                    st.switch_page("pages/explorar.py")
            with b:
                st.button("Restaurar padrão", on_click=reset_scenario, width="stretch")

with map_column:
    with st.container(key="startup-map", border=True):
        st.selectbox(
            "Filtrar por Perfil de Distrito", options=profile_options,
            key="home-profile-filter", on_change=sync_home_profile,
        )
        filtered = ranking_filtrado(
            preview,
            st.session_state.get("map-search", ""),
            st.session_state.get("map-quick-filters", []),
            st.session_state["home-profile-filter"],
        )
        if filtered.empty:
            st.info("Nenhum distrito atende aos filtros. Experimente limpar a busca ou os interesses na tela Explorar.")
        else:
            map_service = DistrictMapService()
            mapped, missing = map_service.restrict_to_mapped_districts(filtered)
            fig = map_service.build_map(
                mapped, theme=st.session_state.get("bairroiq-theme", "dark"), selectable=True,
            )
            # Altura expansível: o gráfico preenche a área reservada pelo CSS.
            # Desktop e mobile utilizam limites independentes em ajustes_v4.css.
            fig.update_layout(height=None, autosize=True)
            st.plotly_chart(fig, width="stretch", height="stretch", config={"displayModeBar": False})
            if missing:
                st.caption("Sem geometria no mapa: " + ", ".join(missing))

st.markdown("### Perfis de Distrito")
st.caption("Características predominantes dos distritos. Os perfis não são uma classificação de qualidade de vida.")
if not filtered.empty and "cluster" in filtered:
    profiles = resumo_perfis(filtered).reset_index(drop=True)
    for offset in range(0, len(profiles), 3):
        cols = st.columns(3, gap="medium")
        for col, (idx, profile_row) in zip(cols, profiles.iloc[offset:offset + 3].iterrows()):
            profile = str(profile_row["Perfil de Distrito"])
            members = filtered[filtered["cluster"].map(nome_perfil) == profile]
            with col:
                with st.container(key=f"district-profile-{idx}", border=True):
                    st.markdown(f'<div class="profile-header">{escape(profile)}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="profile-stat">{len(members)} distrito(s) · '
                        f'<span class="profile-score">{profile_row["Aderência média"]:.1f}/100</span> de aderência média</div>',
                        unsafe_allow_html=True,
                    )
                    for _, district in members.head(3).iterrows():
                        st.markdown(
                            f'<div class="profile-district">{escape(str(district["neighborhood"]))} · '
                            f'<b>{float(district["priority_score"]):.1f}/100</b></div>',
                            unsafe_allow_html=True,
                        )
                    if st.button("Explorar perfil", key=f"explore-profile-{idx}", width="stretch"):
                        explore_profile(profile)
elif "cluster" not in filtered:
    st.info("Os Perfis de Distrito estão disponíveis no conjunto territorial validado.")
