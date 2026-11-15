"""Merge manually researched official menu URLs into discovery results without paid APIs."""
import datetime
import json
import pathlib
import unicodedata
import re
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data"
def norm(name):
    text = unicodedata.normalize("NFD", name.casefold())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)))
def kind(url):
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return "image"
    return "web"

restaurants = json.loads((ROOT / "restaurants.json").read_text(encoding="utf-8")).get("items", [])
verified = json.loads((ROOT / "verified-menu-sources.json").read_text(encoding="utf-8")).get("entries", [])
target = ROOT / "menu-discovery.json"
data = json.loads(target.read_text(encoding="utf-8"))
out = data.setdefault("restaurants", {})
for entry in verified:
    name, site, menu = entry["name"], entry["website"], entry["menu"]
    if any(urllib.parse.urlsplit(u).scheme != "https" for u in (site, menu)):
        continue
    match = next((r for r in restaurants if norm(r["name"]) == norm(name)), None)
    rid = match["id"] if match else "verified/" + norm(name)
    record = out.setdefault(rid, {"name": name, "official_website": site, "links": []})
    if not record.get("official_website"):
        record["official_website"] = site
    if not any(x.get("url") == menu for x in record["links"]):
        record["links"].append({"url": menu, "kind": kind(menu), "status": "published",
                                "source": "researched official restaurant website"})
data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Added", len(verified), "official menu sources", flush=True)
