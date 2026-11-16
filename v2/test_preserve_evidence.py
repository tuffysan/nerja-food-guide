import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "v2" / "preserve_evidence.py"
spec = importlib.util.spec_from_file_location("preserve_evidence", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class EvidenceTests(unittest.TestCase):
    def test_keeps_previous_menu_when_crawler_returns_none(self):
        old={"restaurants":{"node/1":{"name":"A","links":[{"url":"https://a.example/menu","status":"published"}]}}}
        new={"restaurants":{"node/1":{"name":"A","links":[]}}}
        result=mod.merge_discovery(old,new)
        self.assertEqual(len(result["restaurants"]["node/1"]["links"]),1)

    def test_merges_without_duplicate_urls(self):
        link={"url":"https://a.example/menu"}
        old={"restaurants":{"node/1":{"links":[link]}}}
        new={"restaurants":{"node/1":{"links":[link,{"url":"https://a.example/carta"}]}}}
        self.assertEqual(len(mod.merge_discovery(old,new)["restaurants"]["node/1"]["links"]),2)

    def test_preserves_old_photo(self):
        old={"photos":{"node/1":{"url":"https://commons.wikimedia.org/a.jpg","license":"CC BY-SA 2.0"}}}
        self.assertEqual(mod.merge_photos(old,{"photos":{}})["photo_count"],1)

    def test_rejects_non_https_candidate(self):
        self.assertFalse(mod.acceptable_url("http://localhost/menu"))
        self.assertFalse(mod.acceptable_url("javascript:alert(1)"))

if __name__=="__main__":
    unittest.main()
