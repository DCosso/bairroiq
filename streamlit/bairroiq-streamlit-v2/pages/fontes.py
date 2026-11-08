from __future__ import annotations

import os

import streamlit as st

from bairroiq.ui import render_header


render_header("sources")
st.title("Fontes e metodologia")
st.caption("Transparência sobre os dados e os cálculos apresentados no Atlas Sampa.")

provider = os.getenv("BAIRROIQ_DATA_PROVIDER", "sample").strip().lower()
if provider == "databricks":
    st.success("Fonte de indicadores: provedor Databricks configurado.")
else:
    st.info("Fonte de indicadores atual: dados demonstrativos locais do protótipo.")

source_columns = st.columns(3, gap="medium")
with source_columns[0]:
    with st.container(key="source-card-observa", border=True):
        st.markdown("### Observa Sampa")
        st.write(
            "O contrato do adaptador contempla indicadores de emprego formal, "
            "segurança, iluminação, arborização, mobilidade e custo de vida."
        )
        st.link_button(
            "Acessar Observa Sampa",
            "https://observasampa.prefeitura.sp.gov.br/",
            width="stretch",
        )
with source_columns[1]:
    with st.container(key="source-card-boundaries", border=True):
        st.markdown("### Limites geográficos")
        st.write(
            "Os polígonos distritais do protótipo foram derivados de dados do GeoSampa "
            "e permitem exibir áreas selecionadas no mapa."
        )
        st.link_button(
            "Acessar GeoSampa",
            "https://geosampa.prefeitura.sp.gov.br/",
            width="stretch",
        )
with source_columns[2]:
    with st.container(key="source-card-scoring", border=True):
        st.markdown("### Pontuação")
        st.write(
            "A pontuação personalizada combina as prioridades de arborização, "
            "segurança, mobilidade e custo de vida. Segurança é calculada a partir "
            "do índice de roubos."
        )

st.markdown("### Conexão Databricks")
st.write(
    "A integração fica isolada em `bairroiq/databricks.py`. Configure o provedor, "
    "as tabelas e os secrets locais conforme as instruções do README do projeto. "
    "Credenciais nunca devem ser adicionadas ao código."
)
st.markdown(
    '<div class="source-note">Dados e pontuações deste protótipo não devem ser '
    "interpretados como estatística oficial até que a conexão com as fontes seja ativada.</div>",
    unsafe_allow_html=True,
)
