from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MobileScreenshotFixContract(unittest.TestCase):
    def test_five_navigation_links_are_visible_without_horizontal_scroll(self):
        css = (ROOT / "bairroiq/assets/mobile.css").read_text(encoding="utf-8")
        self.assertIn('grid-template-columns: repeat(3, minmax(0, 1fr))', css)
        self.assertIn('min-height: 44px !important', css)

    def test_source_cards_stack_vertically(self):
        css = (ROOT / "bairroiq/assets/mobile.css").read_text(encoding="utf-8")
        self.assertIn('body:has(.st-key-source-card-observa)', css)
        self.assertIn('flex-direction: column !important', css)

    def test_public_snapshot_is_not_labeled_as_demo(self):
        sources = (ROOT / "pages/fontes.py").read_text(encoding="utf-8")
        self.assertIn('== "sample"', sources)
        self.assertNotIn('!= "databricks"', sources)


if __name__ == "__main__":
    unittest.main()
