"""Offline tests for restaurant menu anchor discovery."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from discover_menus import Parser, STRONG


class MenuAnchorTests(unittest.TestCase):
    def test_visible_link_text(self):
        parser = Parser()
        parser.feed('<a href="/download?id=17">Carta de comida</a>')
        self.assertTrue(any(href == "/download?id=17" and STRONG.search(label)
                            for href, label in parser.links))

    def test_accessible_link_text(self):
        parser = Parser()
        parser.feed('<a href="/file.pdf" aria-label="Ver menú">Abrir</a>')
        self.assertTrue(any(STRONG.search(label) for _, label in parser.links))

    def test_qr_image_candidate(self):
        parser = Parser()
        parser.feed('<img src="/uploads/qr-menu.png" alt="Código QR">')
        self.assertTrue(any("qr-menu" in href for href, _ in parser.links))


if __name__ == "__main__":
    unittest.main()
