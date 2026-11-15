"""Extract conservative dish/price pairs from visible official restaurant menu HTML."""
import datetime
import html
from html.parser import HTMLParser
import json
import pathlib
import re
import urllib.parse
import urllib.request
from discover_menus import safe, robots_allowed, OPENER

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data"
PRICE = re.compile(r"(?<!\d)(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?(?!\w)", re.I)
BAD = re.compile(r"\b(cookie|privacy|privacidad|reserv|booking|tel[eé]fono|contact|copyright|iva|total|subtotal)\b", re.I)
MENU_HINT = re.compile(r"menu|men[uú]|carta|food|dish|plato|price|precio|item|product|woocommerce|elementor", re.I)
BLOCKS = {"article", "section", "li", "tr", "p", "h3", "h4"}
SKIP = {"script", "style", "svg", "noscript", "nav", "footer", "header"}

class MenuParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.blocks = []
        self.current = []
        self.skip = 0
        self.texts = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            self.skip += 1
        if tag in BLOCKS:
            self.stack.append((tag, len(self.current)))
        if tag in ("br", "hr") and not self.skip:
            self.current.append("\n")
        if tag == "img" and not self.skip and a.get("alt"):
            self.current.append(" " + a["alt"] + " ")
    def handle_data(self, data):
        if not self.skip and data.strip():
            self.current.append(" " + data.strip() + " ")
    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        if tag in BLOCKS:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    start = self.stack[i][1]
                    content = " ".join("".join(self.current[start:]).split())
                    if content:
                        self.blocks.append(content)
                    del self.stack[i:]
                    break
        if tag in ("div", "td", "span", "h2") and not self.skip:
            self.current.append("\n")

def extract_lines(body):
    parser = MenuParser()
    parser.feed(body)
    candidates = parser.blocks + "".join(parser.current).splitlines()
    found = []
    for candidate in candidates:
        line = " ".join(html.unescape(candidate).split())
        if not 6 <= len(line) <= 180 or BAD.search(line):
            continue
        matches = list(PRICE.finditer(line))
        if len(matches) != 1:
            continue
        m = matches[0]
        # Only allow a short trailing suffix, never silently combine multiple dishes.
        if line[m.end():].strip(" .–—|") or m.start() < 4:
            continue
        name = line[:m.start()].strip(" .:-–—|")
        if not (4 <= len(name) <= 95 and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", name)):
            continue
        if len(name.split()) > 15 or re.search(r"https?://|@|[{}<>]", name):
            continue
        found.append([name, m.group(1).replace(".", ",") + " €"])
    return list({x[0].casefold(): x for x in found}.values())[:100]

def fetch(url, official):
    url = url.split("#")[0]
    if not safe(url) or not robots_allowed(url):
        return []
    if urllib.parse.urlsplit(url).hostname != urllib.parse.urlsplit(official).hostname:
        return []
    req = urllib.request.Request(url, headers={"User-Agent": "NerjaFoodGuide/4.1", "Accept": "text/html"})
    with OPENER.open(req, timeout=8) as response:
        if response.geturl() != url or "text/html" not in response.headers.get("Content-Type", "").lower():
            return []
        data = response.read(300001)
    if len(data) > 300000:
        return []
    return extract_lines(data.decode("utf-8", "replace"))

if __name__ == "__main__":
    discovered = json.loads((ROOT / "menu-discovery.json").read_text(encoding="utf-8")).get("restaurants", {})
    target = ROOT / "html-menus.json"
    results = {}
    for rid, restaurant in discovered.items():
        official = restaurant.get("official_website") or ""
        pages = [x["url"] for x in restaurant.get("links", []) if x.get("kind") == "web" and x.get("status") != "website_only"]
        # Official websites may render the entire menu on the landing page.
        if not pages and official and urllib.parse.urlsplit(official).path not in ("", "/"):
            pages = [official]
        dishes = []
        sources = []
        for url in dict.fromkeys(pages):
            if len(sources) >= 12:
                break
            try:
                found = fetch(url, official)
                if found:
                    dishes.extend(found)
                    sources.append(url)
            except Exception as exc:
                print(restaurant["name"], str(exc)[:100], flush=True)
        # Keep each source page separately: never mix prices from different
        # seasonal/language menus into a single authoritative menu.
        dishes = list({d[0].casefold(): d for d in dishes}.values())[:100]
        if len(dishes) >= 2:
            results[rid] = {"source": sources[0], "sources": sources, "status": "candidate",
                            "method": "html-visible-text", "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "dishes": dishes}
        print(restaurant["name"], len(dishes), "HTML candidates", flush=True)
    # Official menu sources may belong to restaurants absent from OSM.
    curated = json.loads((ROOT / "curated-menus.json").read_text(encoding="utf-8")).get("entries", [])
    for entry in curated:
        url = entry.get("source", "")
        host = urllib.parse.urlsplit(url).hostname or ""
        if not host or host.endswith(("thefork.es", "tripadvisor.es")):
            continue
        key = "curated/" + entry["name"]
        try:
            dishes = fetch(url, url)
            if len(dishes) >= 2:
                results[key] = {"source": url, "status": "candidate", "method": "html-visible-text",
                                "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "dishes": dishes}
            print(entry["name"], len(dishes), "curated-source candidates", flush=True)
        except Exception as exc:
            print(entry["name"], str(exc)[:100], flush=True)
    target.write_text(json.dumps({"restaurants": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
