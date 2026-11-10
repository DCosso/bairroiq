
"""Smoke check offline da camada mobile, sem precisar de Databricks/Streamlit."""
from __future__ import annotations

from pathlib import Path
import unittest


APP_DIR = Path(__file__).resolve().parents[1]
CSS_PATH = APP_DIR / "bairroiq" / "assets" / "mobile.css"


class MobileLayoutContractTests(unittest.TestCase):
    def test_css_is_scoped_to_mobile(self):
        css = CSS_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "@media screen and (max-width: 850px)", css
        )
        self.assertIn(
            "@media screen and (max-width: 700px)", css
        )
        self.assertIn(
            "@media screen and (max-width: 480px)", css
        )

        # Todos os estilos devem permanecer nas regras mobile.
        self.assertEqual(css.count("@media screen"), 3)

    def test_mobile_targets_all_critical_components(self):
        css = CSS_PATH.read_text(encoding="utf-8")

        for selector in (
            ".st-key-topbar",
            ".st-key-explore-toolbar",
            ".st-key-startup-map",
            ".st-key-startup-panel",
            ".st-key-zone-card-norte",
            ".st-key-map-stage",
            ".st-key-ranking-panel",
            ".st-key-district-popup",
            ".st-key-comparison-map",
            ".st-key-profiles-grid",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)

    def test_app_loads_mobile_css_after_navigation(self):
        source = (APP_DIR / "app.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('"mobile.css"', source)
        self.assertGreater(
            source.index("_mobile_css ="),
            source.index("navigation.run()"),
        )
        self.assertIn("unsafe_allow_html=True", source)


if __name__ == "__main__":
    unittest.main()
