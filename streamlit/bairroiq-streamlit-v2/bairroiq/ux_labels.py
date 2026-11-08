"""Nomes de perfis territoriais para apresentação, sem códigos internos.

A origem de verdade permanece no Consumer V2. Os identificadores P01...P09
continuam na tabela Delta e nos contratos ML; não são exibidos na interface.
"""
from __future__ import annotations

import re

# Nomes comerciais validados contra o snapshot de 96 distritos do Consumer V2.
_NOMES = {
    "P01": "Mais Praças, Vida Urbana",
    "P02": "Praças em Regiões Menos Densas",
    "P03": "Áreas Pouco Povoadas",
    "P04": "Menos Roubos e Furtos",
    "P05": "Transporte Coletivo em Destaque",
    "P06": "Muitos Moradores por Km²",
    "P07": "Empregos em Destaque",
    "P08": "Mais Moradores, Menos Transporte",
    "P09": "Escolas e UBS por Habitante",
}
_PADRAO = re.compile(r"^(P0[1-9])\s*(?:[—–.\-:]\s*)?(.*)$", re.IGNORECASE)


def nome_perfil(valor: object) -> str:
    """Converte 'P02 — Praças...' para 'Praças...' na camada de UX.

    Aceita o código isolado apenas para manter robustez visual; nunca modifica
    os campos de cluster/perfil_id persistidos ou os testes de integridade.
    """
    bruto = str(valor).strip()
    achado = _PADRAO.fullmatch(bruto)
    if not achado:
        return bruto
    codigo = achado.group(1).upper()
    descr = achado.group(2).strip()
    return descr or _NOMES[codigo]
