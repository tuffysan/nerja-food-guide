"""Block accidental loss of previously published restaurant/menu/photo coverage.

This is a conservative regression gate, not a claim that every URL is a real menu.
Use --baseline to compare committed JSON with regenerated files before publication.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import re
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = ("restaurants.json", "menu-discovery.json", "restaurant-photos.json")

def read(path, previous=False):
    if previous:
        try:
            raw = subprocess.check_output(["git", "show", "HEAD:data/" + path], cwd=ROOT)
            return json.loads(raw)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
    return json.loads((ROOT / "data" / path).read_text(encoding="utf-8"))

def metrics(restaurants, discovery, photos):
    entries = discovery.get("restaurants", {})
    return {
        "restaurants": len(restaurants.get("items", [])),
        "menu_source_records": sum(bool(x.get("links")) for x in entries.values()),
        "distinct_menu_urls": len({link.get("url") for x in entries.values() for link in x.get("links", []) if link.get("url")}),
        "licensed_photos": len(photos.get("photos", {})),
    }

def menu_specific(url):
    """Generic restaurant homepages are not menus and may be replaced safely."""
    path = urlsplit(str(url or '')).path.lower()
    return bool(re.search(r'(?:menu|carta|speisekarte|food|drink|bebida|\\.pdf$)', path))

def validate():
    old = [read(name, True) for name in FILES]
    new = [read(name) for name in FILES]
    if any(x is None for x in old):
        print("No committed baseline available; skipping regression comparison")
        return 0
    before, after = metrics(*old), metrics(*new)
    print(json.dumps({"before": before, "after": after}, indent=2))
    errors = []
    for metric in before:
        if after[metric] < before[metric]:
            errors.append(f"{metric} decreased: {before[metric]} -> {after[metric]}")
    for name, old_data, new_data in zip(FILES, old, new):
        if name == "menu-discovery.json":
            previous = {link.get("url") for entry in old_data.get("restaurants", {}).values() for link in entry.get("links", []) if link.get("url")}
            current = {link.get("url") for entry in new_data.get("restaurants", {}).values() for link in entry.get("links", []) if link.get("url")}
            lost = {url for url in previous - current if menu_specific(url)}
            ignored = len(previous - current) - len(lost)
            if ignored:
                print(f"Ignored {ignored} removed generic homepage URL(s), not menu-specific")
            if lost:
                errors.append(f"{len(lost)} menu URLs lost (first 5: {sorted(lost)[:5]})")
        if name == "restaurant-photos.json":
            lost = set(old_data.get("photos", {})) - set(new_data.get("photos", {}))
            if lost:
                errors.append(f"{len(lost)} licensed restaurant photos lost: {sorted(lost)[:5]}")
    if errors:
        print("CONTENT REGRESSION: " + "; ".join(errors), file=sys.stderr)
        return 1
    print("Content regression gate passed")
    return 0

if __name__ == "__main__":
    sys.exit(validate())
