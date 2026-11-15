"""Offline tests for Menu Discovery Engine 2.0."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from menu_discovery_v2 import augment, source_links


class MenuDiscoveryV2Tests(unittest.TestCase):
    def test_provenance_and_no_prices(self):
        records = [
            {"name": "Origen", "menu": "https://origennerja.com/menu.pdf", "website": "https://origennerja.com/", "source_type": "official"},
            {"name": "Oliva", "menu": "https://restaurantguru.com/Oliva-Nerja/menu", "source_type": "third_party"},
        ]
        sources = source_links(records)
        self.assertEqual(sources["researched/Oliva"]["links"][0]["status"], "external_unverified")
        self.assertEqual(sources["researched/Origen"]["links"][0]["kind"], "pdf")
        self.assertNotIn("dishes", sources["researched/Oliva"])

    def test_qr_deduplicated_and_scoped(self):
        existing = {"node/1": {"name": "Test", "official_website": "https://example.com/", "links": [{"url": "https://example.com/menu", "kind": "web"}]}}
        def qr(site):
            return ([{"url": "https://example.com/menu", "kind": "web", "status": "qr_candidate"},
                     {"url": "https://example.com/carta", "kind": "web", "status": "qr_candidate"}], 2)
        result, stats = augment(existing, [], qr)
        self.assertEqual(len(result["node/1"]["links"]), 2)
        self.assertEqual(stats["qr_links"], 1)
        self.assertEqual(stats["qr_images_checked"], 2)


if __name__ == "__main__":
    unittest.main()
