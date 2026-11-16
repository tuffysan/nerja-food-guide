"""Offline redirect safety regression tests."""
import pathlib
import sys
import unittest
from unittest.mock import patch
from urllib.request import Request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from discover_menus import SafeRedirect

class RedirectTests(unittest.TestCase):
    def test_cross_host_rejected(self):
        with patch("discover_menus.safe",return_value=True):
            self.assertIsNone(SafeRedirect().redirect_request(Request("https://restaurant.example/menu"),None,302,"Found",{},"https://elsewhere.example/menu"))
    def test_private_destination_rejected(self):
        with patch("discover_menus.safe",return_value=False):
            self.assertIsNone(SafeRedirect().redirect_request(Request("https://restaurant.example/menu"),None,301,"Moved",{},"https://restaurant.example/internal"))
    def test_same_host_allowed_if_robots_allow(self):
        with patch("discover_menus.safe",return_value=True),patch("discover_menus.robots_allowed",return_value=True):
            req=SafeRedirect().redirect_request(Request("https://restaurant.example/menu"),None,301,"Moved",{},"/carta/")
            self.assertEqual(req.full_url,"https://restaurant.example/carta/")
if __name__=="__main__":
    unittest.main()
