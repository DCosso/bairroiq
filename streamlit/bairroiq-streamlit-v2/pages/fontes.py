"""Explicacoes simples para quem deseja conhecer os distritos da cidade."""
from __future__ import annotations

import os
import streamlit as st
from bairroiq.ui import render_header

render_header("sources")
st.title("Sobre as informações")
st.write(
    "O Atlas Sampa reúne informações públicas para ajudar você a conhecer "
    "os distritos de São Paulo e encontrar regiões que combinam com suas escolhas."
)

# O modo public_snapshot disponibiliza dados reais, agregados e aprovados.
# Somente o provider sample exibe dados ilustrativos.
if os.getenv("BAIRROIQ_DATA_PROVIDER", "sample").strip().lower() == "sample":
    st.info("Você está vendo informações de demonstração, não resultados da cidade.")

cards = st.columns(3, gap="medium")
with cards[0]:
    with st.container(key="source-card-observa", border=True):
        st.markdown("### Como é a região?")
        st.write(
            "Conheça características como acesso ao transporte, serviços públicos, "
            "empregos e espaços de lazer. Essas informações ajudam a comparar opções "
            "segundo o que é importante para você."
        )
        st.link_button("Conhecer ObservaSampa", "https://observasampa.prefeitura.sp.gov.br/", width="stretch")
with cards[1]:
    with st.container(key="source-card-boundaries", border=True):
        st.markdown("### Onde fica cada distrito?")
        st.write(
            "Os contornos do mapa representam os limites reais dos distritos "
            "da cidade de São Paulo, conforme dados da Prefeitura."
        )
        st.link_button("Conhecer GeoSampa", "https://geosampa.prefeitura.sp.gov.br/", width="stretch")
with cards[2]:
    with st.container(key="source-card-scoring", border=True):
        st.markdown("### O que significa a nota?")
        st.write(
            "A nota de 0 a 100 mostra o quanto um distrito combina com suas prioridades. "
            "Mude suas preferências e o resultado também muda. "
            "Não é uma nota absoluta de qualidade de vida."
        )

with st.expander("Como interpretar os estilos de região?"):
    st.write(
        "Distritos com características parecidas são apresentados com nomes como "
        "'Mais Praças, Vida Urbana' e 'Transporte Coletivo em Destaque'. "
        "Eles ajudam a descobrir regiões semelhantes, mas não indicam "
        "que uma região seja melhor que outra."
    )
with st.expander("Outras informações importantes"):
    st.write(
        "As informações vêm de diferentes fontes e períodos. Uma nota alta em "
        "um aspecto não garante as mesmas condições em todas as ruas do distrito. "
        "Custos de moradia não estão incluídos na nota personalizada. "
        "Considere visitar a região e consultar fontes adicionais antes de decidir."
    )
    st.write(
        "Além das fontes da Prefeitura, o projeto utiliza estatísticas públicas "
        "do IBGE e da Secretaria da Segurança Pública de São Paulo."
    )
