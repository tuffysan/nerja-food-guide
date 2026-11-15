"""Generate transparent menu coverage report from the committed datasets."""
import datetime
import json
import pathlib

root = pathlib.Path(__file__).resolve().parents[1] / "data"
def load(name, default):
    path = root / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

places = load("restaurants.json", {"items": []}).get("items", [])
discovery = load("menu-discovery.json", {"restaurants": {}}).get("restaurants", {})
pdf = load("pdf-menus.json", {"restaurants": {}}).get("restaurants", {})
html = load("html-menus.json", {"restaurants": {}}).get("restaurants", {})
auto = load("auto-menus.json", {"restaurants": {}}).get("restaurants", {})
curated = load("curated-menus.json", {"entries": []}).get("entries", [])
sourced = load("verified-source-menus.json", {"entries": []}).get("entries", [])
verified = load("verified-menu-sources.json", {"entries": []}).get("entries", [])

with_menu = set()
with_prices = set()
for p in places:
    pid = p["id"]
    if p.get("menu") or any(x.get("kind") != "website" for x in discovery.get(pid, {}).get("links", [])):
        with_menu.add(pid)
    if pdf.get(pid, {}).get("dishes") or html.get(pid, {}).get("dishes"):
        with_menu.add(pid)
        with_prices.add(pid)
    for c in curated:
        if any(m.casefold() in p["name"].casefold() for m in c.get("match", [])):
            if c.get("dishes") or auto.get(c["name"], {}).get("dishes"):
                with_menu.add(pid)
                with_prices.add(pid)
            break

report = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "osm_restaurants": len(places),
    "restaurants_with_menu_links_or_dishes": len(with_menu),
    "restaurants_with_dish_prices": len(with_prices),
    "curated_entries": len(curated),
    "official_source_menu_entries": len(sourced),
    "official_source_dish_entries": sum(len(x.get("dishes", [])) for x in sourced),
    "researched_official_menu_sources": len(verified),
    "curated_entries_with_menu_source": sum(bool(c.get("source")) for c in curated),
    "curated_entries_with_prices": sum(bool(c.get("dishes") or html.get("curated/" + c["name"], {}).get("dishes") or auto.get(c["name"], {}).get("dishes")) for c in curated),
    "curated_entries_with_source": sum(bool(c.get("source")) for c in curated),
    "curated_only_menu_candidates": sum(bool(discovery.get("curated/" + c.get("name", ""), {}).get("links")) for c in curated),
    "all_discovery_entries_including_curated": len(discovery),
    "discovered_link_entries": len(discovery),
    "automated_html_menu_entries": sum(bool(x.get("dishes")) for x in html.values()),
    "automated_pdf_menu_entries": sum(bool(x.get("dishes")) for x in pdf.values()),
    "automated_structured_menu_entries": sum(bool(x.get("dishes")) for x in auto.values()),
    "note": "Discovered menu links and OCR price candidates are not human verified. OSM coverage counts exclude independently researched restaurants not matched to OSM and unmatched curated-only restaurants."
}
(root / "coverage-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
