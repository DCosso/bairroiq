from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from bairroiq.map_data import DISTRICT_FILTERS
from bairroiq.provider import load_metrics


BRAND_LOGO_PATH = Path(__file__).with_name("assets") / "atlas-sampa-logo.png"

_THEME_PALETTES = {
    "light": {
        "ink": "#111827",
        "muted": "#64748b",
        "rust": "#356a9a",
        "paper": "#fefefa",
        "surface": "#fefefa",
        "subtle": "#fefefa",
        "line": "#5f7f9e",
        "navy": "#fefefa",
        "topbar_ink": "#111827",
        "button_bg": "#fefefa",
        "color_scheme": "light",
        "grid_cell": "#fefefa",
        "grid_header": "#fefefa",
        "grid_text": "#111827",
        "grid_text_muted": "#64748b",
        "grid_selection": "#fefefa",
    },
    "dark": {
        "ink": "#f8fafc",
        "muted": "#cbd5e1",
        "rust": "#ff9b4a",
        "paper": "#0b1220",
        "surface": "#0b1220",
        "subtle": "#0b1220",
        "line": "#334155",
        "navy": "#0b1220",
        "topbar_ink": "#f8fafc",
        "button_bg": "#0b1220",
        "color_scheme": "dark",
        "grid_cell": "#0b1220",
        "grid_header": "#0b1220",
        "grid_text": "#f8fafc",
        "grid_text_muted": "#cbd5e1",
        "grid_selection": "#0b1220",
    },
}

# As quatro prioridades afetam exclusivamente o ranking personalizado.
# Empregos e densidade são indicadores descritivos; não têm peso implícito.
SCENARIO_DEFAULTS = {
    "trees": 25,
    "safety": 25,
    "mobility": 25,
    "infrastructure": 25,
}
SCENARIO_LABELS = {
    "trees": "Verde e lazer",
    "safety": "Segurança",
    "mobility": "Mobilidade",
    "infrastructure": "Serviços públicos",
}
SEARCH_SUGGESTIONS = (
    "Praças em Regiões Menos Densas",
    "Áreas Pouco Povoadas",
    "Mais Praças, Vida Urbana",
    "Menos Roubos e Furtos",
    "Transporte Coletivo em Destaque",
    "Muitos Moradores por Km²",
    "Empregos em Destaque",
    "Mais Moradores, Menos Transporte",
    "Escolas e UBS por Habitante",
)


def theme_palette() -> dict[str, str]:
    mode = st.session_state.get("bairroiq-theme", "dark")
    return _THEME_PALETTES[mode]


def _toggle_theme() -> None:
    current = st.session_state.get("bairroiq-theme", "dark")
    st.session_state["bairroiq-theme"] = "dark" if current == "light" else "light"


def _sync_comparison_selection() -> None:
    selected = st.session_state["selected-neighborhoods"]
    st.session_state["comparison_neighborhoods"] = selected[:5]
    st.session_state["comparison-neighborhoods-widget"] = selected[:5]


def _apply_search_suggestion() -> None:
    suggestion = st.session_state.get("map-search-suggestion")
    if suggestion:
        st.session_state["map-search"] = suggestion



def _ensure_neighborhood_selection(neighborhoods: list[str]) -> None:
    defaults = [name for name in ("Vila Mariana", "Pinheiros") if name in neighborhoods]
    if "selected-neighborhoods" not in st.session_state:
        st.session_state["selected-neighborhoods"] = defaults or neighborhoods[:2]
    st.session_state["selected-neighborhoods"] = [
        name for name in st.session_state["selected-neighborhoods"]
        if name in neighborhoods
    ]


def _save_scenario_weight(key: str) -> None:
    st.session_state[f"scenario-value-{key}"] = int(
        st.session_state[f"scenario-{key}"]
    )


def render_scenario_builder() -> dict[str, int]:
    weights: dict[str, int] = {}
    for key, label in SCENARIO_LABELS.items():
        widget_key = f"scenario-{key}"
        persisted_key = f"scenario-value-{key}"
        if persisted_key not in st.session_state:
            st.session_state[persisted_key] = SCENARIO_DEFAULTS[key]
        st.session_state[widget_key] = int(st.session_state[persisted_key])
        value = int(st.session_state[widget_key])
        with st.container(key=f"scenario-control-{key}"):
            st.markdown(
                f'<div class="scenario-slider-label">{label}</div>',
                unsafe_allow_html=True,
            )
            value_position = 7 + value * 0.86
            st.markdown(
                '<div class="scenario-slider-values">'
                '<span class="scenario-slider-min">0</span>'
                f'<span class="scenario-slider-current" style="left: {value_position:.1f}%">'
                f'{value}</span>'
                '<span class="scenario-slider-max">100</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.slider(
                label=f"Controle de prioridade: {label}",
                min_value=0,
                max_value=100,
                step=1,
                key=widget_key,
                format="%d",
                label_visibility="collapsed",
                on_change=_save_scenario_weight,
                args=(key,),
            )
        weights[key] = int(st.session_state[widget_key])
    return weights


def apply_theme() -> None:
    palette = theme_palette()
    st.markdown(
        f"""
        <style>
        :root {{
            color-scheme: {palette["color_scheme"]};
            --ink: {palette["ink"]};
            --muted: {palette["muted"]};
            --rust: {palette["rust"]};
            --paper: {palette["paper"]};
            --surface: {palette["surface"]};
            --subtle: {palette["subtle"]};
            --line: {palette["line"]};
            --navy: {palette["navy"]};
            --topbar-ink: {palette["topbar_ink"]};
            --button-bg: {palette["button_bg"]};
            --primary-color: {palette["rust"]};
            --background-color: {palette["paper"]};
            --secondary-background-color: {palette["surface"]};
            --text-color: {palette["ink"]};
            --gdg-bg-cell: {palette["grid_cell"]};
            --gdg-bg-cell-medium: {palette["grid_header"]};
            --gdg-bg-header: {palette["grid_header"]};
            --gdg-bg-header-hovered: {palette["subtle"]};
            --gdg-bg-header-has-focus: {palette["grid_header"]};
            --gdg-text-dark: {palette["grid_text"]};
            --gdg-text-medium: {palette["grid_text_muted"]};
            --gdg-text-light: {palette["grid_text_muted"]};
            --gdg-border-color: {palette["line"]};
            --gdg-accent-color: {palette["rust"]};
            --gdg-accent-light: {palette["grid_selection"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        .stApp {
            background: var(--paper);
            color: var(--ink);
            font-family: "Inter", "Segoe UI", sans-serif;
            box-shadow: inset 0 0 0 1px var(--line);
        }
        .stApp p,
        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp label,
        .stApp button,
        .stApp input,
        .stApp textarea,
        .stApp select,
        .stApp a {
            font-family: "Inter", "Segoe UI", sans-serif !important;
        }
        .stApp .brand,
        .stApp .brand-caption { font-family: Georgia, "Times New Roman", serif !important; }
        [data-testid="stHeader"],
        [data-testid="stNavigation"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        footer { display: none !important; }
        #MainMenu { visibility: hidden !important; }
        [data-testid="stMainBlockContainer"] {
            max-width: none;
            padding: 0 1rem 1rem;
        }
        h1, h2, h3 {
            letter-spacing: -0.025em;
            font-family: Georgia, "Times New Roman", serif !important;
        }
        h1 { font-size: clamp(1.8rem, 3vw, 2.5rem) !important; line-height: 1.15; }
        h2 { font-size: 1.55rem !important; line-height: 1.25; }
        h3 { font-size: 1.15rem !important; line-height: 1.3; }
        [data-testid="stMarkdownContainer"] p { line-height: 1.5; }
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],
        [data-testid="stCaptionContainer"],
        [data-testid="stRadio"],
        [data-testid="stCheckbox"] { color: var(--ink); }
        [data-testid="stAlert"] {
            border-color: var(--line);
            background: var(--subtle);
            color: var(--ink);
        }
        [data-testid="stAlert"] p { color: var(--ink); }
        [role="tooltip"] [data-testid="stTooltipContent"] {
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22) !important;
        }
        [role="tooltip"] [data-testid="stTooltipContent"] * {
            background: transparent !important;
            color: var(--ink) !important;
        }
        [data-testid="stLinkButton"] a {
            border-color: var(--rust) !important;
            background: var(--rust) !important;
            color: #fff !important;
        }
        [data-testid="stLinkButton"] a p { color: #fff !important; }
        [data-baseweb="select"] > div,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {
            border-color: var(--line) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"],
        [data-testid="stMultiSelect"] [data-baseweb="select"],
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        [data-testid="stSelectbox"] [data-baseweb="select"] [role="combobox"],
        [data-testid="stMultiSelect"] [data-baseweb="select"] [role="combobox"],
        [data-testid="stSelectbox"] [data-baseweb="select"] input,
        [data-testid="stMultiSelect"] [data-baseweb="select"] input {
            border-color: var(--line) !important;
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="value-container"],
        [data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="value-container"],
        [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="input"],
        [data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="input"] {
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--ink) !important;
        }
        [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"],
        [data-testid="stMultiSelect"] .react-aria-ComboBox > [role="group"] {
            border: 1px solid var(--line) !important;
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        [data-testid="stSelectbox"] input[role="combobox"],
        [data-testid="stMultiSelect"] input[role="combobox"] {
            background: transparent !important;
            color: var(--ink) !important;
        }
        [data-testid="stSelectbox"] input[role="combobox"]::placeholder,
        [data-testid="stMultiSelect"] input[role="combobox"]::placeholder {
            color: var(--muted) !important;
            opacity: 1;
        }
        [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"]:has(input:focus),
        [data-testid="stMultiSelect"] .react-aria-ComboBox > [role="group"]:has(input:focus) {
            border-color: var(--rust) !important;
            box-shadow: 0 0 0 1px var(--rust) !important;
        }
        [data-testid="stMultiSelect"] [data-tag] {
            border: 1px solid var(--line) !important;
            background: var(--subtle) !important;
            color: var(--ink) !important;
        }
        [data-testid="stMultiSelect"] [data-tag] > span,
        [data-testid="stMultiSelect"] [data-tag] button {
            background: transparent !important;
            color: var(--ink) !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] *,
        [data-testid="stMultiSelect"] [data-baseweb="select"] * {
            background-color: var(--surface) !important;
            color: var(--ink) !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within,
        [data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within {
            border-color: var(--rust) !important;
            box-shadow: 0 0 0 1px var(--rust) !important;
        }
        [data-baseweb="popover"],
        [role="listbox"],
        [role="dialog"]:has([data-testid="stMultiSelect"]) {
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        [data-baseweb="menu"] { background: var(--surface) !important; }
        [data-baseweb="menu"] *,
        [data-baseweb="popover"] *,
        [role="listbox"] * {
            color: var(--ink) !important;
        }
        [data-baseweb="popover"]:has([role="listbox"]),
        [data-baseweb="menu"],
        [role="listbox"] {
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16) !important;
        }
        [data-baseweb="menu"] ul,
        [data-baseweb="menu"] li,
        [role="listbox"] ul,
        [role="listbox"] li,
        [role="listbox"] > div {
            background: var(--surface) !important;
            background-color: var(--surface) !important;
        }
        [role="listbox"] [role="option"] {
            background: var(--surface) !important;
            color: var(--ink) !important;
            border-radius: 6px !important;
            margin: 2px 4px !important;
        }
        [role="listbox"] [role="option"][aria-selected="true"],
        [role="listbox"] [role="option"][data-focused="true"] {
            background: var(--subtle) !important;
        }
        .st-key-explore-toolbar [data-testid="stPopover"] button {
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        .st-key-explore-toolbar [data-testid="stPopover"] button p,
        .st-key-explore-toolbar [data-testid="stPopover"] button svg {
            color: var(--ink) !important;
            fill: var(--ink) !important;
        }
        [role="dialog"]:has([data-testid="stMultiSelect"]) {
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16) !important;
        }
        [role="dialog"]:has([data-testid="stMultiSelect"]) *,
        [role="dialog"]:has([data-testid="stMultiSelect"]) *::placeholder {
            border-color: var(--line) !important;
            color: var(--ink) !important;
        }
        [role="dialog"]:has([data-testid="stMultiSelect"]) [data-testid="stMultiSelect"] [data-baseweb="select"],
        [role="dialog"]:has([data-testid="stMultiSelect"]) [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        [role="dialog"]:has([data-testid="stMultiSelect"]) [data-testid="stMultiSelect"] [data-baseweb="value-container"],
        [role="dialog"]:has([data-testid="stMultiSelect"]) [data-testid="stMultiSelect"] [data-baseweb="input"] {
            background: var(--surface) !important;
            background-color: var(--surface) !important;
        }
        [role="dialog"]:has([data-testid="stMultiSelect"]) [data-testid="stMultiSelect"] [data-tag] {
            border: 1px solid var(--line) !important;
            background: var(--subtle) !important;
            background-color: var(--subtle) !important;
        }
        [role="dialog"]:has([data-testid="stMultiSelect"]) [data-testid="stMultiSelect"] [data-tag] * {
            background: transparent !important;
            color: var(--ink) !important;
        }
        [data-baseweb="popover"]:has([role="listbox"]),
        [data-baseweb="popover"]:has([role="listbox"]) *,
        [data-baseweb="menu"]:has([role="option"]),
        [data-baseweb="menu"]:has([role="option"]) *,
        [role="listbox"],
        [role="listbox"] * {
            border-color: var(--line) !important;
            background-color: var(--surface) !important;
            color: var(--ink) !important;
        }
        [role="listbox"] [role="option"][aria-selected="true"],
        [role="listbox"] [role="option"][data-focused="true"],
        [role="listbox"] [role="option"]:hover {
            background: var(--subtle) !important;
            background-color: var(--subtle) !important;
        }
        [data-baseweb="tag"] {
            border-color: var(--line) !important;
            background: var(--subtle) !important;
            color: var(--ink) !important;
        }
        [data-baseweb="tag"] span { color: var(--ink) !important; }
        [data-baseweb="input"],
        [data-baseweb="input"] > div {
            background: var(--surface) !important;
        }
        .st-key-startup-budget [data-testid="stNumberInput"] [data-baseweb="input"],
        .st-key-startup-budget [data-testid="stNumberInput"] [data-baseweb="input"] > div,
        .st-key-startup-budget [data-testid="stNumberInput"] input,
        .st-key-startup-budget [data-testid="stNumberInput"] button {
            border: 0 !important;
            background: #fff !important;
            color: #111827 !important;
            box-shadow: none !important;
        }
        .st-key-startup-budget [data-testid="stNumberInput"] input::placeholder {
            color: #64748b !important;
            opacity: 1 !important;
        }
        .st-key-startup-budget [data-testid="stNumberInputContainer"] {
            border: 1px solid #000 !important;
            border-radius: 8px !important;
            background: #fff !important;
        }
        .st-key-startup-budget,
        .st-key-startup-objectives {
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            background: var(--surface) !important;
        }
        .st-key-startup-budget {
            padding: 0.6rem 0.75rem !important;
        }
        .st-key-comparison-summary-panel,
        .st-key-comparison-map-card,
        .st-key-comparison-ranking-card,
        .st-key-comparison-chart-indicators,
        .st-key-comparison-chart-profile,
        .st-key-comparison-chart-trend,
        .st-key-source-card-observa,
        .st-key-source-card-boundaries,
        .st-key-source-card-scoring {
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
            background: var(--surface) !important;
        }
        .st-key-source-card-observa,
        .st-key-source-card-boundaries,
        .st-key-source-card-scoring {
            height: 260px !important;
            min-height: 260px !important;
            box-sizing: border-box !important;
            display: flex !important;
            flex-direction: column !important;
            padding-bottom: 12px !important;
        }
        .st-key-source-card-observa [data-testid="stLinkButton"],
        .st-key-source-card-boundaries [data-testid="stLinkButton"] {
            margin-top: auto !important;
            margin-bottom: 0 !important;
        }
        .st-key-source-card-observa [data-testid="stLinkButton"] a,
        .st-key-source-card-boundaries [data-testid="stLinkButton"] a {
            transform: none !important;
        }
        .st-key-source-card-observa > div,
        .st-key-source-card-boundaries > div,
        .st-key-source-card-scoring > div {
            height: 100% !important;
            min-height: 0 !important;
            display: flex !important;
            flex-direction: column !important;
        }
        .st-key-startup-map [data-testid="stPlotlyChart"],
        .st-key-comparison-map-card [data-testid="stPlotlyChart"],
        .st-key-comparison-chart-indicators [data-testid="stPlotlyChart"],
        .st-key-comparison-chart-profile [data-testid="stPlotlyChart"],
        .st-key-comparison-chart-trend [data-testid="stPlotlyChart"] {
            border: 0 !important;
            border-radius: 0 !important;
        }
        [data-testid="stExpander"] {
            border-color: var(--line) !important;
            background: var(--surface);
        }
        div[data-testid="stMetric"] {
            padding: 0.8rem 1rem;
            border: 1px solid var(--line);
            border-radius: 14px;
            background: var(--surface);
            overflow-wrap: anywhere;
        }
        [data-testid="stDataFrame"],
        [data-testid="stDataFrame"] > div,
        [data-testid="stDataFrame"] [role="grid"] {
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            border-color: var(--line) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        [data-testid="stDataFrame"] {
            --gdg-bg-cell: var(--surface);
            --gdg-bg-cell-medium: var(--subtle);
            --gdg-bg-header: var(--subtle);
            --gdg-bg-header-hovered: var(--line);
            --gdg-bg-header-has-focus: var(--subtle);
            --gdg-text-dark: var(--ink);
            --gdg-text-medium: var(--muted);
            --gdg-text-light: var(--muted);
            --gdg-border-color: var(--line);
            --gdg-accent-color: var(--rust);
            --gdg-accent-light: var(--subtle);
        }
        div[data-testid="stMetricLabel"] { color: var(--muted); }
        div[data-testid="stMetricValue"] { color: var(--ink); }
        div[data-testid="stPlotlyChart"] {
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 14px;
            background: var(--surface);
        }
        .source-note { color: var(--muted); font-size: 0.8rem; }

        [data-testid="stVerticalBlockBorderWrapper"],
        .profile-card,
        div[data-testid="stMetric"] {
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08) !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] *:not(button):not(button *),
        .profile-card *,
        div[data-testid="stMetric"] * {
            color: var(--ink) !important;
        }
        .st-key-topbar {
            position: sticky;
            top: 0;
            z-index: 50;
            margin: -1rem 0 0;
            padding: 0.15rem 1rem 0;
            box-sizing: border-box;
            background: var(--navy);
            color: var(--topbar-ink);
        }
        .st-key-topbar-main {
            padding-right: 1rem;
            padding-bottom: 0.45rem;
            border-bottom: 1px solid var(--line);
        }
        .st-key-topbar .brand {
            justify-content: center;
            min-height: 2.5rem;
            width: 100%;
        }
        .st-key-topbar .brand-name {
            color: #ed5a00 !important;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: 0.01em;
        }
        .st-key-topbar .brand-name span {
            color: #ed5a00 !important;
        }
        .st-key-topbar [data-testid="stHorizontalBlock"] {
            align-items: top;
            flex-wrap: nowrap !important;
            gap: 0.5rem;
        }
        .st-key-topbar [data-testid="stColumn"] { min-width: 0 !important; }
        .st-key-topbar .brand {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            min-height: 2.5rem;
            width: 100%;
            box-sizing: border-box;
            color: var(--topbar-ink) !important;
            white-space: nowrap;
        }
        .st-key-topbar .brand-name {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.15rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .st-key-topbar .brand-name span { color: var(--topbar-ink); }
        .st-key-topbar .brand-caption {
            color: var(--topbar-ink);
            font-family: Georgia, "Times New Roman", serif;
            font-size: 0.86rem;
            font-weight: 500;
        }
        .st-key-topbar [class*="st-key-nav-"] {
            display: flex;
            min-height: 2rem;
            box-sizing: border-box;
            align-items: center;
            justify-content: center;
            padding: 0.1rem 0 0.2rem;
            text-align: center;
        }
        .st-key-topbar [class*="st-key-nav-"][class*="-active"] {
            transform: none;
            align-self: center;
            border-bottom: 0;
        }
        .st-key-topbar [class*="st-key-nav-"][class*="-active"] a {
            background: var(--surface);
            border-color: var(--line) !important;
        }
        .st-key-topbar [class*="st-key-nav-"]:not([class*="-active"]):hover {
            transform: translateY(-1px);
        }
        .st-key-topbar [class*="st-key-nav-"] a {
            display: flex !important;
            width: 100% !important;
            height: 2rem !important;
            min-height: 2rem !important;
            box-sizing: border-box !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0.28rem 0.7rem !important;
            border: 1px solid transparent !important;
            border-radius: 999px !important;
            color: var(--topbar-ink) !important;
            font-family: "Inter", "Segoe UI", sans-serif;
            font-size: 0.8rem;
            font-weight: 600;
            line-height: 1.2;
            text-decoration: none;
            white-space: nowrap;
        }
        .st-key-topbar [class*="st-key-nav-"] a p {
            margin: 0;
            color: var(--topbar-ink) !important;
            font-family: "Inter", "Segoe UI", sans-serif;
            font-size: 0.8rem !important;
            font-weight: 600;
            line-height: 1.2;
            text-decoration: none;
        }
        .st-key-topbar .st-key-topbar-main [data-testid="stHorizontalBlock"] {
            align-items: center;
        }
        .st-key-topbar [data-testid="stButton"] button {
            min-width: 2.25rem;
            min-height: 1.8rem;
            padding: 0.2rem;
            border: 1px solid var(--line);
            background: transparent;
            color: var(--topbar-ink) !important;
            font-size: 1rem;
        }
        .st-key-topbar [data-testid="stButton"] button p { color: var(--topbar-ink) !important; }

        .st-key-explore-toolbar {
            margin: 0;
            padding: 0 1rem 0 0;
            min-height: 2.75rem;
            display: flex;
            align-items: center;
            background: var(--navy);
            border-bottom: 0;
        }
        .st-key-explore-toolbar > div,
        .st-key-explore-toolbar [data-testid="stHorizontalBlock"] {
            width: 100%;
        }
        .st-key-explore-toolbar [data-testid="stHorizontalBlock"] {
            align-items: center;
            flex-wrap: nowrap !important;
            gap: 0.6rem;
        }
        .st-key-explore-toolbar [data-testid="stColumn"] { min-width: 0 !important; }
        .st-key-explore-toolbar [data-testid="stTextInput"],
        .st-key-explore-toolbar [data-testid="stTextInput"] > div,
        .st-key-explore-toolbar [data-testid="stTextInput"] label {
            height: 2.25rem;
            margin: 0 !important;
            padding: 0 !important;
        }
        .st-key-explore-toolbar [data-testid="stTextInput"] label { display: none !important; }
        .st-key-explore-toolbar [data-testid="stTextInput"] [data-baseweb="input"] {
            height: 2.25rem;
            margin: 0;
            border: 1px solid var(--line) !important;
            border-radius: 6px !important;
            background: var(--paper) !important;
            box-shadow: none !important;
            outline: none !important;
        }
        .st-key-explore-toolbar [data-testid="stTextInput"] [data-baseweb="input"] > div {
            border: 0 !important;
            box-shadow: none !important;
        }
        .st-key-explore-toolbar [data-testid="stTextInput"] input {
            height: 2.25rem;
            min-height: 2.25rem;
            border: 0 !important;
            border-radius: 5px;
            background: transparent !important;
            color: var(--ink);
            font-size: 0.8rem;
            box-shadow: none !important;
            outline: none !important;
        }
        .st-key-explore-toolbar [data-testid="stTextInput"] input::placeholder {
            color: var(--muted);
            opacity: 1;
        }
        .st-key-explore-toolbar [data-testid="stTextInput"] input,
        .st-key-explore-toolbar [data-testid="stTextInput"] [data-baseweb="input"] {
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        .st-key-explore-toolbar button[data-testid="stBaseButton-secondary"] {
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        .st-key-explore-toolbar [data-testid="stPopover"] button {
            min-height: 2rem;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            color: var(--ink) !important;
            font-size: 0.76rem;
            white-space: nowrap;
        }
        .st-key-explore-toolbar [data-testid="stPopover"] button p {
            color: var(--ink) !important;
        }
        [data-testid="stButton"] button:not(.st-key-toggle-theme) {
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
            background: var(--button-bg) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        [data-testid="stButton"] button:not(.st-key-toggle-theme) p {
            color: var(--ink) !important;
        }
        [data-testid="stButton"] button[kind="primary"] {
            border-color: var(--rust) !important;
            background: var(--rust) !important;
            color: #ffffff !important;
        }
        [data-testid="stButton"] button[kind="primary"] p {
            color: #ffffff !important;
        }
        [data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {
            border-color: var(--rust) !important;
            background: var(--rust) !important;
        }
        [data-testid="stCheckbox"] [data-selected="true"] > div:first-of-type {
            border-color: var(--rust) !important;
            background: var(--rust) !important;
        }

        .st-key-map-stage {
            position: relative;
            isolation: isolate;
            flex: none !important;
            height: calc(100dvh - 150px) !important;
            min-height: 0 !important;
            width: calc(100vw - 2rem);
            margin-left: 0;
            overflow: hidden;
            box-sizing: border-box;
            border: 1px solid var(--line);
            border-radius: 12px;
            background: var(--surface);
        }
        .st-key-map-stage [data-testid="stPlotlyChart"] {
            position: absolute !important;
            z-index: 0;
            inset: 1px;
            width: auto;
            height: calc(100dvh - 152px) !important;
            min-height: 0;
            max-height: calc(100dvh - 152px);
            border: 0;
            border-radius: 11px;
            background: var(--paper);
        }
        .st-key-map-stage [data-testid="stPlotlyChart"] > div,
        .st-key-map-stage [data-testid="stPlotlyChart"] iframe,
        .st-key-map-stage [data-testid="stPlotlyChart"] .js-plotly-plot,
        .st-key-map-stage [data-testid="stPlotlyChart"] .plot-container,
        .st-key-map-stage [data-testid="stPlotlyChart"] .svg-container {
            width: 100% !important;
            height: 100% !important;
            min-height: 0 !important;
        }
        .st-key-map-stage .st-key-scenario-panel,
        .st-key-map-stage .st-key-district-popup,
        .st-key-map-stage .st-key-ranking-panel,
        .st-key-scenario-dashboard {
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08) !important;
        }
        .st-key-map-stage .st-key-scenario-panel *,
        .st-key-map-stage .st-key-district-popup *,
        .st-key-map-stage .st-key-ranking-panel *,
        .st-key-scenario-dashboard * {
            color: var(--ink);
        }
        .st-key-map-stage .st-key-scenario-panel,
        .st-key-map-stage .st-key-district-popup {
            height: 112px;
            min-height: 112px;
            box-sizing: border-box;
        }
        [class*="st-key-comparison-summary-"] {
            height: 128px;
            min-height: 128px;
            padding: 0.8rem;
            box-sizing: border-box;
        }
        [class*="st-key-comparison-summary-"] [data-testid="stMetric"] {
            height: 112px;
            margin: 0;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
        [class*="st-key-comparison-summary-"] [data-testid="stMetric"] {
            width: 100%;
            overflow: visible !important;
        }
        [class*="st-key-comparison-summary-"] [data-testid="stMetricLabel"],
        [class*="st-key-comparison-summary-"] [data-testid="stMetricValue"] {
            width: 100%;
            max-width: none;
            white-space: normal;
            overflow: visible !important;
            text-overflow: clip;
            overflow-wrap: anywhere;
        }
        [class*="st-key-comparison-summary-"] [data-testid="stMetricValue"] {
            min-height: 42px;
            font-size: clamp(0.95rem, 1.35vw, 1.35rem) !important;
        }
        .st-key-comparison-map-card,
        .st-key-comparison-ranking-card {
            height: min(450px, 56dvh);
            padding: 0.65rem 0.75rem;
            box-sizing: border-box;
        }
        .st-key-scenario-dashboard {
            height: fit-content;
            align-self: flex-start;
            padding: 0.75rem 0.75rem 0.4rem;
            box-sizing: border-box;
            gap: 0 !important;
        }
        .st-key-comparison-map-card .section-heading,
        .st-key-comparison-ranking-card .section-heading,
        .st-key-scenario-dashboard .section-heading {
            height: 32px;
            margin: 0 0 0.55rem;
            display: flex;
            align-items: center;
            line-height: 32px;
        }
        .st-key-comparison-map-card,
        .st-key-comparison-ranking-card {
            box-sizing: border-box;
            overflow: hidden;
        }
        .st-key-comparison-map-card [data-testid="stPlotlyChart"] {
            height: clamp(180px, 45dvh, 390px) !important;
        }
        .st-key-comparison-map-card [data-testid="stPlotlyChart"] > div,
        .st-key-comparison-map-card [data-testid="stPlotlyChart"] .plot-container,
        .st-key-comparison-map-card [data-testid="stPlotlyChart"] .svg-container {
            height: clamp(180px, 45dvh, 390px) !important;
        }
        .st-key-comparison-ranking-card {
            overflow-y: auto;
        }
        .duel-card {
            min-height: 220px;
            height: 100%;
        }
        .st-key-map-stage .st-key-ranking-panel {
            position: absolute !important;
            z-index: 5;
            box-sizing: border-box;
            max-width: calc(100% - 1rem);
            overflow-wrap: anywhere;
        }
        .st-key-map-stage .st-key-scenario-panel [data-testid="stMarkdownContainer"],
        .st-key-map-stage .st-key-scenario-panel [data-testid="stCaptionContainer"],
        .st-key-scenario-dashboard [data-testid="stMarkdownContainer"],
        .st-key-scenario-dashboard [data-testid="stCaptionContainer"],
        .st-key-map-stage .st-key-district-popup [data-testid="stMarkdownContainer"],
        .st-key-map-stage .st-key-ranking-panel [data-testid="stMarkdownContainer"],
        .st-key-map-stage .st-key-ranking-panel [data-testid="stCaptionContainer"] {
            margin-bottom: 0 !important;
        }
        .st-key-map-stage .st-key-scenario-panel {
            position: absolute !important;
            z-index: 10;
            bottom: 8px;
            left: 8px;
            width: clamp(220px, 24vw, 320px);
            height: fit-content;
            max-height: none;
            padding: 0.75rem 0.75rem 0.4rem;
            gap: 0 !important;
            overflow: visible;
            opacity: 1 !important;
            background: var(--surface) !important;
            background-image: none !important;
            backdrop-filter: none !important;
        }
        .st-key-map-stage .st-key-scenario-panel > div,
        .st-key-map-stage .st-key-scenario-panel [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface) !important;
            opacity: 1 !important;
        }
        .st-key-map-stage .st-key-ranking-panel {
            right: 8px;
            bottom: 8px;
            width: clamp(220px, 22vw, 300px);
            max-height: calc(100% - 1rem);
            padding: 0.65rem 0.75rem 0.55rem;
            gap: 0 !important;
            overflow-y: auto;
        }
        .st-key-map-stage .st-key-district-popup [data-testid="stButton"] button {
            border: 1px solid var(--line) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        .st-key-map-stage .st-key-district-popup [data-testid="stButton"] button p {
            color: var(--ink) !important;
        }
        .st-key-map-stage .st-key-district-popup {
            position: absolute !important;
            z-index: 12;
            top: 12%;
            left: 50%;
            width: clamp(320px, 38vw, 460px);
            height: auto;
            min-height: 0;
            max-height: calc(100% - 1.5rem);
            box-sizing: border-box;
            padding: 0.65rem 0.9rem;
            overflow-y: auto;
            transform: translateX(-50%);
            gap: 0 !important;
        }
        .st-key-map-stage .st-key-district-popup [data-testid="stButton"] {
            margin-top: 0.55rem !important;
        }
        .st-key-map-stage .st-key-district-popup [data-testid="stButton"] button:last-child {
            min-height: 36px;
            margin-top: 0;
            border: 1px solid var(--line);
            background: var(--surface);
            color: var(--ink) !important;
        }
        .st-key-map-stage .st-key-district-popup .st-key-close-district-details button {
            border: 1px solid var(--line) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
        }
        .st-key-map-stage .st-key-district-popup .st-key-close-district-details button p {
            border: 0 !important;
            background: transparent !important;
            color: var(--ink) !important;
        }
        .st-key-scenario-dashboard {
            padding: 0.75rem 0.75rem 0.4rem;
            border: 1px solid var(--line);
            border-radius: 12px;
            background: var(--surface);
        }
        .st-key-scenario-dashboard h3 {
            margin: 0 0 0.3rem;
            font-size: 0.95rem;
            line-height: 1.3;
            white-space: nowrap;
            overflow-wrap: normal;
        }
        .st-key-scenario-dashboard [data-testid="stCaptionContainer"] p {
            margin: 0;
            font-size: 0.72rem;
        }
        .st-key-scenario-dashboard .scenario-slider-label {
            height: 16px;
            margin: 0 0 0.05rem;
            font-size: 0.78rem;
            line-height: 16px;
        }
        .st-key-scenario-dashboard [data-testid="stSlider"] {
            height: 23px !important;
            min-height: 23px;
            margin: -0.28rem 0 0.05rem !important;
        }
        .st-key-scenario-dashboard [data-testid="stSlider"] [data-baseweb="slider"] {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }
        .st-key-scenario-dashboard [class*="st-key-scenario-control-"] {
            overflow: visible;
            margin-bottom: 0.1rem;
            gap: 0 !important;
        }
        .profile-card {
            display: flex;
            width: 100%;
            min-height: 150px;
            margin-bottom: 0.75rem;
            box-sizing: border-box;
            flex-direction: column;
            justify-content: center;
            padding: 0.9rem;
            border: 1px solid var(--line);
            border-radius: 14px;
            background: var(--surface);
            overflow-wrap: anywhere;
        }
        .st-key-profiles-grid {
            margin-bottom: 1.25rem;
        }
        .st-key-profiles-grid [data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }
        .st-key-profiles-grid [data-testid="stColumn"] {
            min-width: 0;
        }
        .profile-card strong { color: var(--rust); }
        .st-key-map-stage .st-key-scenario-panel h3,
        .st-key-map-stage .st-key-district-popup h3,
        .st-key-map-stage .st-key-ranking-panel h3 {
            margin: 0 0 0.3rem;
            font-size: 0.95rem;
            line-height: 1.3;
            white-space: nowrap;
            overflow-wrap: normal;
        }
        .scenario-slider-label {
            height: 16px;
            margin: 0 0 0.05rem;
            color: var(--ink);
            font-size: 0.78rem;
            font-weight: 600;
            line-height: 16px;
        }
        .st-key-map-stage .st-key-scenario-panel [data-testid="stSlider"] {
            height: 23px !important;
            min-height: 23px;
            margin: -0.28rem 0 0.05rem !important;
            overflow: visible;
        }
        .st-key-map-stage .st-key-scenario-panel [class*="st-key-scenario-control-"] {
            overflow: visible;
            margin-bottom: 0.1rem;
            gap: 0 !important;
        }
        .scenario-slider-values {
            position: relative;
            height: 11px;
            margin-bottom: -11px;
            color: var(--muted);
            font-size: 0.62rem;
            line-height: 11px;
            pointer-events: none;
        }
        .scenario-slider-current {
            position: absolute;
            transform: translateX(-50%);
            color: var(--ink);
            font-weight: 600;
        }
        .scenario-slider-min { position: absolute; left: 0; }
        .scenario-slider-max { position: absolute; right: 0; }
        [data-testid="stSliderTickBar"],
        [data-testid="stSliderMinMaxValue"] {
            display: none !important;
        }
        [data-testid="stSliderThumbValue"] {
            display: none !important;
            font-size: 0.62rem !important;
        }
        [data-testid="stSlider"]:hover [data-testid="stSliderThumbValue"],
        [data-testid="stSlider"]:focus-within [data-testid="stSliderThumbValue"] {
            display: flex !important;
        }
        .st-key-map-stage .st-key-scenario-panel
        [class*="st-key-scenario-control-"]:has(
            [data-testid="stSlider"]:hover,
            [data-testid="stSlider"]:focus-within
        )
        .scenario-slider-current,
        .st-key-scenario-dashboard
        [class*="st-key-scenario-control-"]:has(
            [data-testid="stSlider"]:hover,
            [data-testid="stSlider"]:focus-within
        )
        .scenario-slider-current {
            visibility: hidden;
        }
        [data-testid="stSlider"] *,
        [data-testid="stSlider"] *::before,
        [data-testid="stSlider"] *::after {
            transition-duration: 0s !important;
        }
        [data-testid="stSlider"] [role="slider"] { display: block !important; }
        [data-testid="stSlider"] [role="group"] > div > div:first-child {
            filter: hue-rotate(25deg) saturate(1.1);
        }
        [data-testid="stSlider"] [role="group"] > div > div[style*="position: absolute"] {
            background: var(--rust) !important;
            border-color: var(--rust) !important;
        }
        [data-testid="stSlider"] [role="progressbar"] { background: var(--rust) !important; }
        .st-key-map-stage .st-key-scenario-panel [data-rac][role="group"] {
            height: 21px !important;
        }
        .st-key-map-stage .st-key-scenario-panel [data-testid="stSlider"]
        [data-rac][data-orientation="horizontal"] > div[data-rac][data-orientation="horizontal"] {
            height: 21px !important;
        }
        .st-key-map-stage .st-key-scenario-panel [data-testid="stSlider"] [data-testid="stWidgetLabel"] {
            display: none !important;
        }
        .st-key-map-stage .st-key-scenario-panel [data-testid="stSlider"] {
            overflow: visible;
        }
        .st-key-map-stage .st-key-scenario-panel [data-testid="stCaptionContainer"] p {
            margin: 0;
            font-size: 0.72rem;
        }
        .st-key-map-stage .district-metrics {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.35rem 0.6rem;
            margin: 0.45rem 0 0.65rem;
            font-size: 0.75rem;
        }
        .st-key-map-stage .district-metrics span {
            display: flex;
            justify-content: space-between;
            gap: 0.3rem;
            border-bottom: 1px solid var(--line);
            color: var(--muted);
        }
        .st-key-map-stage .district-metrics strong { color: var(--ink); }
        .st-key-map-stage .st-key-ranking-panel [data-testid="stCheckbox"] {
            min-height: 30px;
            margin: -0.2rem 0 !important;
        }
        .st-key-map-stage .st-key-ranking-panel [data-testid="stCheckbox"] p {
            font-size: 0.78rem;
            overflow-wrap: anywhere;
        }
        .st-key-map-stage .st-key-ranking-panel .st-key-ranking-compare-button button {
            background: var(--rust) !important;
            border-color: var(--rust) !important;
            color: #ffffff !important;
        }
        .st-key-map-stage .st-key-ranking-panel .st-key-ranking-compare-button button p {
            color: #ffffff !important;
        }
        .st-key-map-stage .st-key-district-popup [data-testid="stButton"] button,
        .st-key-map-stage .st-key-ranking-panel [data-testid="stButton"] button {
            box-sizing: border-box;
            width: 100%;
            min-width: 0;
            min-height: 2rem;
            padding: 0.35rem 0.5rem;
            border: 0;
            background: var(--rust);
            color: white !important;
            font-size: 0.76rem;
            line-height: 1.25;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .st-key-map-stage .st-key-district-popup [data-testid="stButton"] button p,
        .st-key-map-stage .st-key-ranking-panel [data-testid="stButton"] button p {
            color: white !important;
        }
        .st-key-map-stage .st-key-district-popup .st-key-close-district-details button,
        .st-key-map-stage .st-key-district-popup .st-key-close-district-details button p {
            color: var(--ink) !important;
        }
        .st-key-map-stage .st-key-ranking-panel [data-testid="stButton"] button {
            min-height: 1.85rem;
            padding: 0.15rem;
        }
        .ranking-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            margin: 0.25rem 0;
            padding: 0.55rem 0.6rem;
            border: 1px solid var(--line);
            border-radius: 9px;
            background: var(--surface);
            color: var(--ink);
            font-size: 0.84rem;
        }
        .ranking-row strong { color: var(--rust); }
        .scenario-recommendation,
        .duel-card {
            border: 1px solid var(--line);
            border-radius: 12px;
            background: var(--surface);
            color: var(--ink);
        }
        .scenario-recommendation {
            margin-top: 0.55rem;
            padding: 0.65rem 0.75rem;
        }
        .scenario-recommendation strong { color: var(--rust); }
        .scenario-recommendation p,
        .duel-card p { margin: 0.2rem 0; }
        .duel-card {
            height: 100%;
            padding: 0.85rem 1rem;
            border-top: 3px solid var(--rust);
        }
        .duel-card h4 {
            margin: 0 0 0.55rem;
            color: var(--ink);
            font-size: 1rem;
        }
        .duel-card .duel-score {
            color: var(--rust);
            font-size: 1.2rem;
            font-weight: 750;
        }
        .duel-card .duel-label { color: var(--muted); font-size: 0.78rem; }
        .duel-card .duel-item { margin-top: 0.4rem; font-size: 0.83rem; }
        .duel-card .duel-opportunity {
            margin-top: 0.65rem;
            padding-top: 0.55rem;
            border-top: 1px solid var(--line);
        }
        .section-heading {
            margin: 1rem 0 0.55rem;
            color: var(--ink);
            font-size: 1.25rem;
            font-weight: 700;
        }
        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] { padding: 0 0.75rem 0.75rem; }
            h1 { font-size: clamp(1.6rem, 7vw, 2rem) !important; }
            h2 { font-size: 1.35rem !important; }
            .st-key-source-card-observa,
            .st-key-source-card-boundaries,
            .st-key-source-card-scoring {
                height: auto !important;
                min-height: 186px !important;
            }
            .st-key-topbar {
                margin: -1rem 0 0;
                padding: 0.15rem 0.5rem 0;
            }
            .st-key-topbar-main { padding-right: 0.5rem; }
            .st-key-topbar [data-testid="stHorizontalBlock"] { gap: 0.15rem; }
            .st-key-topbar .st-key-topbar-main > div > [data-testid="stHorizontalBlock"] {
                display: grid;
                grid-template-columns: minmax(0, 1fr) 4.5rem;
                gap: 0.1rem 0.25rem;
            }
            .st-key-topbar .st-key-topbar-main > div > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]:nth-child(1) { grid-column: 1; grid-row: 1; }
            .st-key-topbar .st-key-topbar-main > div > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]:nth-child(2) { grid-column: 1 / -1; grid-row: 2; }
            .st-key-topbar .st-key-topbar-main > div > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]:nth-child(3) {
                grid-column: 2;
                grid-row: 1;
                width: 4.5rem !important;
                max-width: none !important;
                flex: none !important;
            }
            .st-key-topbar .brand {
                gap: 0.2rem;
                min-height: 1.9rem;
                padding-left: 0.5rem;
            }
            .st-key-topbar .st-key-topbar-main > div > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]:nth-child(2) {
                width: calc(100vw - 2.5rem) !important;
                max-width: none !important;
                flex: none !important;
            }
            .st-key-topbar .brand-name { font-size: 1rem; }
            .st-key-topbar .brand-caption { font-size: 0.72rem; }
            .st-key-topbar [data-testid="stHorizontalBlock"] { gap: 0.15rem; }
            .st-key-topbar [class*="st-key-nav-"] { min-height: 2rem; padding: 0.1rem 0; }
            .st-key-topbar [class*="st-key-nav-"] a,
            .st-key-topbar [class*="st-key-nav-"] a p { font-size: 0.58rem !important; }
            .st-key-topbar [class*="st-key-nav-"] a {
                white-space: normal;
                overflow-wrap: anywhere;
                text-align: center;
            }
            .st-key-explore-toolbar {
                min-height: 34px;
                height: 34px;
                padding: 0 0.5rem 0 0;
                overflow: visible;
            }
            .st-key-explore-toolbar [data-testid="stHorizontalBlock"] { gap: 0.15rem; }
            .st-key-explore-toolbar [data-testid="stColumn"]:nth-child(1) {
                flex: 3.7 1 0% !important;
            }
            .st-key-explore-toolbar [data-testid="stColumn"]:nth-child(2) {
                flex: 2.5 1 0% !important;
            }
            .st-key-explore-toolbar [data-testid="stColumn"]:nth-child(3) {
                flex: 2.5 1 0% !important;
            }
            .st-key-explore-toolbar [data-testid="stTextInput"],
            .st-key-explore-toolbar [data-testid="stTextInput"] > div,
            .st-key-explore-toolbar [data-testid="stTextInput"] [data-baseweb="input"],
            .st-key-explore-toolbar [data-testid="stTextInput"] input {
                height: 1.4rem;
                min-height: 1.4rem;
                margin: 0;
            }
            .st-key-explore-toolbar [data-testid="stTextInput"] input {
                padding: 0 0.2rem;
                font-size: 0.65rem;
            }
            .st-key-explore-toolbar [data-testid="stPopover"] button {
                min-height: 1.4rem;
                padding: 0 0.08rem;
                font-size: 0.48rem;
            }
            .st-key-explore-toolbar [data-testid="stPopover"] button p {
                font-size: 0.48rem !important;
            }
            .st-key-map-stage {
                height: calc(100dvh - 120px) !important;
                min-height: 0 !important;
                width: calc(100vw - 1rem);
                margin-left: -0.25rem;
            }
            .st-key-map-stage [data-testid="stPlotlyChart"] {
                height: calc(100dvh - 122px) !important;
                min-height: 0;
                max-height: calc(100dvh - 122px);
            }
            .st-key-map-stage .st-key-scenario-panel {
                width: clamp(180px, 34vw, 240px);
                max-height: none;
                padding: 0.4rem 0.5rem;
            }
            .st-key-map-stage .st-key-ranking-panel {
                width: clamp(150px, 29vw, 190px);
                max-height: 64%;
                padding: 0.4rem 0.5rem;
            }
            .st-key-map-stage .st-key-scenario-panel h3,
            .st-key-map-stage .st-key-district-popup h3,
            .st-key-map-stage .st-key-ranking-panel h3 {
                font-size: 0.78rem;
            }
            .scenario-slider-label {
                height: 16px;
                margin-bottom: 0.4rem;
                font-size: 0.67rem;
                line-height: 16px;
            }
            .scenario-slider-label strong {
                min-width: 42px;
                font-size: 0.62rem;
            }
            .st-key-map-stage .st-key-scenario-panel [data-testid="stSlider"] {
                height: 23px !important;
                min-height: 23px;
                margin: -0.22rem 0 0.05rem !important;
            }
            .st-key-map-stage .st-key-scenario-panel [data-testid="stSlider"] [data-testid="stWidgetLabel"] p,
            .st-key-map-stage .st-key-ranking-panel [data-testid="stCheckbox"] p {
                font-size: 0.67rem;
            }
            .st-key-map-stage .st-key-ranking-panel [data-testid="stCheckbox"] {
                min-height: 28px;
                margin: -0.15rem 0 !important;
            }
            .st-key-map-stage .st-key-district-popup {
                top: 1%;
                width: clamp(280px, 72vw, 420px);
                max-height: calc(100% - 1rem);
                padding: 0.45rem 0.6rem;
            }
            .st-key-map-stage .district-metrics {
                gap: 0.2rem 0.45rem;
                margin: 0.3rem 0 0.4rem;
                font-size: 0.61rem;
            }
            .st-key-map-stage .st-key-scenario-panel h3,
            .st-key-map-stage .st-key-ranking-panel h3 { font-size: 0.72rem; }
            .st-key-map-stage .st-key-district-popup [data-testid="stButton"] button,
            .st-key-map-stage .st-key-ranking-panel [data-testid="stButton"] button {
                min-height: 1.7rem;
                padding: 0.25rem 0.3rem;
                font-size: 0.62rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(active_page: str) -> None:
    apply_theme()
    with st.container(key="topbar"):
        with st.container(key="topbar-main"):
            brand, navigation, actions = st.columns([2.2, 4.2, 0.7], gap="small")
            with brand:
                st.markdown(
                    '<div class="brand"><div class="brand-name">'
                    "Atlas Sampa"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
            with navigation:
                nav_personalize, nav_explore, nav_compare, nav_profiles, nav_sources = st.columns(5, gap="small")
                pages = (
                    (nav_personalize, "personalize", "pages/iniciar.py", "Personalizar"),
                    (nav_explore, "explore", "pages/explorar.py", "Explorar / Mapa"),
                    (nav_compare, "compare", "pages/comparar.py", "Comparar regiões"),
                    (nav_profiles, "profiles", "pages/perfis.py", "Perfis Urbanos"),
                    (nav_sources, "sources", "pages/fontes.py", "Fontes"),
                )
                for column, page_id, page_path, label in pages:
                    with column:
                        key = f"nav-{page_id}-active" if active_page == page_id else f"nav-{page_id}"
                        with st.container(key=key):
                            st.page_link(page_path, label=label)
            with actions:
                mode = st.session_state.get("bairroiq-theme", "dark")
                st.button(
                    "☀" if mode == "dark" else "☾",
                    key="toggle-theme",
                    help="Alternar entre tema claro e escuro",
                    on_click=_toggle_theme,
                    width="stretch",
                )

        if active_page not in {"sources", "personalize"}:
            neighborhoods = load_metrics()["neighborhood"].tolist()
            _ensure_neighborhood_selection(neighborhoods)
            if "comparison-neighborhoods-widget" not in st.session_state:
                st.session_state["comparison-neighborhoods-widget"] = (
                    st.session_state["comparison_neighborhoods"]
                    if "comparison_neighborhoods" in st.session_state
                    else st.session_state["selected-neighborhoods"]
                )

            with st.container(key="explore-toolbar"):
                search, neighborhood_filter, data_filter = st.columns(
                    [5, 1.6, 1.5], gap="small"
                )
                search.selectbox(
                    "Busca inteligente",
                    options=SEARCH_SUGGESTIONS,
                    index=None,
                    placeholder="Selecione uma busca...",
                    label_visibility="collapsed",
                    key="map-search-suggestion",
                    on_change=_apply_search_suggestion,
                )
                with neighborhood_filter:
                    with st.popover("Quick Bairros ▾", width="stretch"):
                        st.multiselect(
                            "Distritos para analisar",
                            options=neighborhoods,
                            key="selected-neighborhoods",
                            placeholder="Selecione os bairros",
                            on_change=_sync_comparison_selection,
                        )
                with data_filter:
                    with st.popover("Quick Filtros ▾", width="stretch"):
                        st.multiselect(
                            "Indicadores mínimos",
                            options=list(DISTRICT_FILTERS),
                            placeholder="Todos os indicadores",
                            key="map-quick-filters",
                        )

    if os.getenv("BAIRROIQ_DATA_PROVIDER", "sample").strip().lower() == "databricks":
        metrics = load_metrics()
        required = {
            "Verde e lazer": "green_leisure_score",
            "Segurança": "safety_score",
            "Mobilidade": "mobility_score",
            "Serviços públicos": "public_services_score",
        }
        missing = [
            label for label, column in required.items()
            if column not in metrics.columns or metrics[column].isna().any()
        ]
        if missing:
            st.error(
                "A fonte auditada V2 não atende ao contrato visual: "
                + ", ".join(missing)
            )
            st.stop()
        st.caption(
            "Consumer V2: comparação territorial entre distritos. "
            "Esta fotografia não representa uma série histórica."
        )
