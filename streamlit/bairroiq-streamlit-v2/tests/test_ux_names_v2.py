"""Testes sem side effects: códigos ML não aparecem na interface."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from bairroiq.ux_labels import nome_perfil

ROOT = Path(__file__).resolve().parents[1]

class TestUserFacingLabels(unittest.TestCase):
    def test_all_nine_commercial_names(self):
        expected = [
            "Mais Praças, Vida Urbana", "Praças em Regiões Menos Densas",
            "Áreas Pouco Povoadas", "Menos Roubos e Furtos",
            "Transporte Coletivo em Destaque", "Muitos Moradores por Km²",
            "Empregos em Destaque", "Mais Moradores, Menos Transporte",
            "Escolas e UBS por Habitante",
        ]
        for i, name in enumerate(expected, start=1):
            code = f"P{i:02d}"
            self.assertEqual(nome_perfil(f"{code} — {name}"), name)
            self.assertEqual(nome_perfil(f"{code}. {name}"), name)
            self.assertEqual(nome_perfil(code), name)

    def test_no_codes_in_ux_templates(self):
        pages = {
            'pages/explorar.py': ['escape(nome_perfil(focus["cluster"]))'],
            'pages/perfis.py': ['escape(nome_perfil(row["cluster"]))'],
            'pages/comparar.py': ['escape(nome_perfil(row["cluster"]))',
                                  '"ticktext": nomes_perfis'],
            'bairroiq/map_data.py': ['"nome_perfil_publico"'],
            'bairroiq/comparison_v2.py': ['nome_perfil(row["cluster"])'],
        }
        for p, required in pages.items():
            source = (ROOT / p).read_text(encoding='utf-8')
            ast.parse(source)
            for token in required:
                self.assertIn(token, source, p)

    def test_original_integrity_kept(self):
        source = (ROOT / 'bairroiq/comparison_v2.py').read_text(encoding='utf-8')
        self.assertIn('summary["codigo"] = summary["cluster"].map(cluster_code)', source)
        self.assertIn('expected_codes = {f"P{i:02d}" for i in range(1, 10)}', source)

if __name__ == '__main__':
    unittest.main()
