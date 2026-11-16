"""Offline smoke tests for the progressive v3/v4 website and menu extraction."""
import ast
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

class GuideReleaseTests(unittest.TestCase):
    def test_discovered_menu_sources_do_not_regress(self):
        import json
        data=json.loads((ROOT/"data/menu-discovery.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data.get("restaurants",{})),60,
            "Menu source registry unexpectedly shrank below 60 entries")
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        self.assertIn("discoveredByName",html)
        self.assertIn("Visa meny (PDF)",html)
        self.assertIn("Visa menybild",html)
    def test_approved_photo_survives_daily_refresh(self):
        source=(ROOT/"scripts/update_photos.py").read_text(encoding="utf-8")
        self.assertIn("approved_ids",source)
        self.assertIn("Special:FilePath/",source)
    def test_web_assets_connected(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        self.assertIn('assets/guide-v3.js',html)
        self.assertIn('assets/guide-v3.css',html)
        self.assertTrue((ROOT/"assets/guide-v3.js").is_file())
        self.assertTrue((ROOT/"restaurant-portal.html").is_file())
    def test_menu_highlights_have_valid_source_and_prices(self):
        import json
        from urllib.parse import urlsplit
        entries=json.loads((ROOT/"data/featured-menu-highlights.json").read_text(encoding="utf-8"))["entries"]
        self.assertGreaterEqual(len(entries),3)
        for entry in entries:
            self.assertEqual(urlsplit(entry["url"]).scheme,"https")
            self.assertTrue(entry["dishes"])
            for dish in entry["dishes"]:
                self.assertEqual(len(dish),2)
                self.assertIn("€",dish[1])
    def test_map_and_search_recovery_controls(self):
        js=(ROOT/"assets/guide-v3.js").read_text(encoding="utf-8")
        for token in ("Rensa filter","empty-results","Visa restaurang i listan","if(!window.L)"):
            self.assertIn(token,js)
    def test_portal_requires_review(self):
        portal=(ROOT/"restaurant-portal.html").read_text(encoding="utf-8")
        self.assertIn("issues/new?",portal)
        self.assertIn("manuell granskning",portal)
        self.assertNotIn("api.github.com",portal)
    def test_pdf_extractor_syntax(self):
        source=(ROOT/"scripts/extract_pdf_menus.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("MAX_DOWNLOAD_BYTES=8_000_000",source)
        self.assertIn("source_type",source)
    def test_photo_pipeline_is_licensed_and_bounded(self):
        source=(ROOT/"scripts/update_photos.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("LicenseShortName",source)
        self.assertIn("license_allowed",source)
        self.assertIn("iiurlwidth",source)
        self.assertTrue((ROOT/"data/restaurant-photos.json").exists())
    def test_approved_photo_identity(self):
        import json
        approved=json.loads((ROOT/"data/approved-restaurant-photos.json").read_text(encoding="utf-8"))["approved"]
        restaurants={r["id"]:r["name"] for r in json.loads((ROOT/"data/restaurants.json").read_text(encoding="utf-8"))["items"]}
        for photo in approved:
            self.assertEqual(restaurants.get(photo["restaurant_id"]),photo["restaurant_name"])
            self.assertTrue(photo["commons_file"].startswith("File:"))
    def test_area_map_visible_and_filter(self):
        js=(ROOT/"assets/guide-v3.js").read_text(encoding="utf-8")
        self.assertIn('mapBox.hidden=false',js)
        self.assertIn('area.addEventListener("change"',js)
        self.assertIn('&&inArea(r)',js)
        for name in ("centro","balcon","burriana","torrecilla","playazo","capistrano"):
            self.assertIn(name,js)
    def test_photo_license_restrictions(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location("photo_module", ROOT/"scripts/update_photos.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for allowed in ("CC BY 4.0","CC BY-SA 4.0","CC0 1.0","Public domain"):
            self.assertTrue(module.license_allowed(allowed),allowed)
        for denied in ("CC BY-NC 4.0","CC BY-ND 4.0","CC BY-NC-SA 4.0","All rights reserved",""):
            self.assertFalse(module.license_allowed(denied),denied)
    def test_photo_candidate_review_not_auto_published(self):
        script=(ROOT/"scripts/discover_photo_candidates.py").read_text(encoding="utf-8")
        ast.parse(script)
        self.assertIn("needs_manual_identity_and_license_review",script)
        self.assertIn("checked>=12",script)
    def test_map_has_attribution_and_no_paid_api(self):
        js=(ROOT/"assets/guide-v3.js").read_text(encoding="utf-8")
        self.assertIn("openstreetmap.org/copyright",js)
        self.assertIn("withinPrice",js)
        self.assertNotIn("maps.googleapis.com",js)

if __name__=="__main__":
    unittest.main()
