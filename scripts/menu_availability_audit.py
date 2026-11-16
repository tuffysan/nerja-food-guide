"""Audit restaurant menu sources without confusing links with verified menus."""
import json
from pathlib import Path
from urllib.parse import urlsplit
import unicodedata
import re

ROOT = Path(__file__).resolve().parents[1] / "data"

def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def key(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in value if not unicodedata.combining(c)))

def is_menu_link(link):
    url = str(link.get("url") or "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or link.get("kind") == "website":
        return False
    return bool(re.search(r"menu|carta|speisekarte|food|drink|bebida|\.pdf$|\.jpe?g$|\.png$|\.webp$", (parsed.path + "#" + parsed.fragment).lower())) or link.get("status") == "published"

def build():
    osm = read("restaurants.json")["items"]
    discovered = read("menu-discovery.json")["restaurants"]
    verified = read("verified-menu-sources.json")["entries"]
    curated = read("curated-menus.json")["entries"]
    sourced = read("verified-source-menus.json")["entries"]
    names = {}
    for entry in osm + curated + sourced + verified:
        n = key(entry.get("name"))
        if n:
            names.setdefault(n, {"name": entry["name"], "links": set(), "dishes": 0, "official": False})
            names[n]["dishes"] = max(names[n]["dishes"], len(entry.get("dishes") or []))
    for entry in verified:
        n = key(entry["name"])
        url = entry.get("menu", "")
        if url.startswith("https://") and re.search(r"menu|carta|\.pdf$", urlsplit(url).path.lower()):
            names[n]["links"].add(url)
            names[n]["official"] |= entry.get("source_type") == "official"
    for entry in discovered.values():
        n = key(entry.get("name"))
        if not n:
            continue
        names.setdefault(n, {"name": entry["name"], "links": set(), "dishes": 0, "official": False})
        for link in entry.get("links", []):
            if is_menu_link(link):
                names[n]["links"].add(link["url"])
    found = sorted(({"name": v["name"], "menu_links": len(v["links"]), "has_dishes": bool(v["dishes"]), "official": v["official"]} for v in names.values() if v["links"] or v["dishes"]), key=lambda x:x["name"].casefold())
    report = {"restaurants_with_menu_evidence": len(found), "restaurants_with_menu_links": sum(bool(x["menu_links"]) for x in found), "restaurants_with_dish_entries": sum(x["has_dishes"] for x in found), "restaurants_with_official_menu_link": sum(x["official"] for x in found), "total_menu_urls": sum(x["menu_links"] for x in found), "note": "Evidence counts, NOT verified working links. A website without a menu-specific URL is excluded. Photos counted separately.", "restaurants": found}
    (ROOT / "menu-availability-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Menu evidence for", len(found), "distinct normalized restaurant names")

if __name__ == "__main__":
    build()
