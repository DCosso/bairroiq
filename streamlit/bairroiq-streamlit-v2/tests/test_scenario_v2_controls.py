"""Garantias estáticas do passo 6B: não altera layout nem agrega scores ocultos."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
UI = BASE / "bairroiq" / "ui.py"
START = BASE / "pages" / "iniciar.py"

class TestScenarioV2Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = UI.read_text(encoding="utf-8")
        cls.start = START.read_text(encoding="utf-8")
        ast.parse(cls.ui)
        ast.parse(cls.start)

    def test_four_priorities_and_no_budget_priority(self):
        tree = ast.parse(self.ui)
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"SCENARIO_DEFAULTS", "SCENARIO_LABELS"}:
                        values[target.id] = ast.literal_eval(node.value)
        expected = {"trees", "safety", "mobility", "infrastructure"}
        self.assertEqual(set(values["SCENARIO_DEFAULTS"]), expected)
        self.assertEqual(set(values["SCENARIO_LABELS"]), expected)
        self.assertEqual(values["SCENARIO_LABELS"]["trees"], "Verde e lazer")
        self.assertEqual(values["SCENARIO_LABELS"]["infrastructure"], "Serviços públicos")

    def test_no_unvalidated_budget_control(self):
        self.assertNotIn('st.number_input(', self.start)
        self.assertNotIn('affordability_threshold(', self.start)
        self.assertNotIn('"affordability_score"', self.start)

    def test_no_hidden_objective_score(self):
        self.assertIn('preview["personalization_score"] = preview["priority_score"]', self.start)
        self.assertNotIn('preview["priority_score"] * 0.7', self.start)

    def test_original_layout_preserved(self):
        for marker in ('key="startup-map"','key="startup-panel"','key="startup-objectives"',
                       'key="startup-priorities"','key="startup-budget"','st.plotly_chart('):
            self.assertIn(marker, self.start)

if __name__ == "__main__":
    unittest.main()
