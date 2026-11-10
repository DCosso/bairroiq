from __future__ import annotations

import os

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
navigation.run()
