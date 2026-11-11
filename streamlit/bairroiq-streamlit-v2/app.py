from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from bairroiq.ui import BRAND_LOGO_PATH

st.set_page_config(
    page_title="Atlas Sampa",
    page_icon=str(BRAND_LOGO_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)

provider = os.getenv("BAIRROIQ_DATA_PROVIDER", "sample").strip().lower()
if provider == "sample":
    st.warning(
        "AMBIENTE DEMONSTRATIVO: os dados exibidos são fictícios e não "
        "representam os indicadores reais dos 96 distritos de São Paulo."
    )

pages = [
    st.Page(
        "pages/iniciar.py",
        title="Personalizar cenário",
        icon="⚙️",
        default=True,
        url_path="iniciar",
    ),
    st.Page(
        "pages/explorar.py",
        title="Explorar / Mapa",
        icon="🗺️",
        url_path="explorar",
    ),
    st.Page(
        "pages/comparar.py",
        title="Comparar regiões",
        icon="📊",
        url_path="comparar",
    ),
    st.Page(
        "pages/perfis.py",
        title="Perfis Urbanos",
        icon="🏘️",
        url_path="perfis",
    ),
    st.Page(
        "pages/fontes.py",
        title="Fontes",
        icon="📚",
        url_path="fontes",
    ),
]
navigation = st.navigation(pages, position="hidden")
st.session_state.setdefault("bairroiq-theme", "dark")
# Os comparativos por zonas foram descontinuados.
# Limpa sessões antigas antes de renderizar Explorar.
st.session_state.pop("selected-zone", None)
# Se o usuário limpou a busca sugerida, não retenha filtro anterior oculto.
if "map-search-suggestion" in st.session_state and not st.session_state["map-search-suggestion"]:
    st.session_state["map-search"] = ""
navigation.run()

# Aplica somente regras responsivas apos executar a pagina selecionada.
# Isso mantem intactos os layouts desktop definidos no CSS atual.
_mobile_css = Path(__file__).resolve().parent / "bairroiq" / "assets" / "mobile.css"
if _mobile_css.is_file():
    st.markdown(
        "<style>" + _mobile_css.read_text(encoding="utf-8") + "</style>",
        unsafe_allow_html=True,
    )

# Correcoes de legibilidade e responsividade desta versao.
_ux_css = Path(__file__).resolve().parent / "bairroiq" / "assets" / "perfis_v3.css"
if _ux_css.is_file():
    st.markdown(
        "<style>" + _ux_css.read_text(encoding="utf-8") + "</style>",
        unsafe_allow_html=True,
    )
