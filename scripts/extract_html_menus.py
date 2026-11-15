"""Conservative extraction of dish/price candidates from official HTML menu pages."""
import datetime
import html
from html.parser import HTMLParser
import json
import pathlib
import re
import urllib.parse
from discover_menus import safe, robots_allowed, OPENER
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data"
PRICE = re.compile(r"(?<!\d)(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?\s*$", re.I)
BAD = re.compile(r"\b(cookie|privacy|privacidad|reserv|booking|tel[eé]fono|contact|copyright|iva|total)\b", re.I)

class TextLines(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg", "noscript"):
            self.skip += 1
        if tag in ("p", "li", "div", "h2", "h3", "h4", "tr", "br"):
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "noscript"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "li", "div", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

def extract_lines(body):
    parser = TextLines()
    parser.feed(body)
    text = html.unescape("".join(parser.parts))
    out = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if not (6 <= len(line) <= 135) or BAD.search(line):
            continue
        match = PRICE.search(line)
        if not match:
            continue
        name = line[:match.start()].strip(" .:-–—|")
        if not (4 <= len(name) <= 95) or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", name):
            continue
        out.append([name, match.group(1).replace(".", ",") + " €"])
    return list({p[0].casefold(): p for p in out}.values())[:100]

def fetch(url, official):
    if not safe(url) or not robots_allowed(url):
        return []
    if urllib.parse.urlsplit(url).hostname != urllib.parse.urlsplit(official).hostname:
        return []
    request = urllib.request.Request(url, headers={"User-Agent": "NerjaFoodGuide/4.0", "Accept": "text/html"})
    with OPENER.open(request, timeout=8) as response:
        if response.geturl() != url or "text/html" not in response.headers.get("Content-Type", "").lower():
            return []
        data = response.read(300001)
    if len(data) > 300000:
        return []
    return extract_lines(data.decode("utf-8", "replace"))

if __name__ == "__main__":
    discovered = json.loads((ROOT / "menu-discovery.json").read_text(encoding="utf-8")).get("restaurants", {})
    target = ROOT / "html-menus.json"
    previous = json.loads(target.read_text(encoding="utf-8")).get("restaurants", {}) if target.exists() else {}
    results = {}
    for rid, restaurant in discovered.items():
        official = restaurant.get("official_website") or ""
        pages = [x["url"] for x in restaurant.get("links", []) if x.get("kind") == "web" and x.get("status") != "website_only"]
        dishes = []
        source = ""
        for url in pages[:10]:
            try:
                found = fetch(url.split("#")[0], official)
                if found:
                    dishes.extend(found)
                    source = url
            except Exception as exc:
                print(restaurant["name"], str(exc)[:100], flush=True)
        dishes = list({d[0].casefold(): d for d in dishes}.values())[:100]
        if len(dishes) >= 2:
            results[rid] = {"source": source, "status": "candidate", "method": "html-text", "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "dishes": dishes}
        elif rid in previous:
            results[rid] = previous[rid]
        print(restaurant["name"], len(dishes), "HTML candidates", flush=True)
    target.write_text(json.dumps({"restaurants": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
