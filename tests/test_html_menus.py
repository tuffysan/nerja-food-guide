"""Offline regression tests for HTML menu extraction (no external APIs)."""
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from extract_html_menus import extract_lines

class HTMLMenuTests(unittest.TestCase):
    def test_separate_elements(self):
        body = '<section><article><h3>Gambas al Pil Pil</h3><span>12,50 €</span></article><article><h3>Paella de Marisco</h3><span>18.00 €</span></article></section>'
        dishes = extract_lines(body)
        self.assertIn(["Gambas al Pil Pil", "12,50 €"], dishes)
        self.assertIn(["Paella de Marisco", "18,00 €"], dishes)
    def test_skip_navigation_and_contact(self):
        body = '<nav><p>Contact 12,50 €</p></nav><main><p>Pollo al ajillo 13,50 €</p></main>'
        self.assertEqual(extract_lines(body), [["Pollo al ajillo", "13,50 €"]])
    def test_reject_ambiguous_multiple_prices(self):
        self.assertEqual(extract_lines("<p>Tapas 5,00 € / 9,00 €</p>"), [])

if __name__ == "__main__":
    unittest.main()
