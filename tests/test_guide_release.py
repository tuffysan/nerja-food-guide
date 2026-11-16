"""Offline smoke tests for the progressive v3/v4 website and menu extraction."""
import ast
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

class GuideReleaseTests(unittest.TestCase):
    def test_web_assets_connected(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        self.assertIn('assets/guide-v3.js',html)
        self.assertIn('assets/guide-v3.css',html)
        self.assertTrue((ROOT/"assets/guide-v3.js").is_file())
        self.assertTrue((ROOT/"restaurant-portal.html").is_file())
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
