"""Find likely menu pages on official restaurant sites, with bounded same-site crawling."""
import datetime
import urllib.error
import html.parser
import ipaddress
import json
import pathlib
import re
import socket
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data"
KEYWORDS = re.compile(r"menu|men[uú]|carta|food|comida|speisekarte|carte|dinner|lunch|tapas|platos|restaurant", re.I)
STRONG = re.compile(r"menu|men[uú]|carta|speisekarte|carte|food-menu|food_menu|entrantes|ensaladas|carnes|pescados|postres|bebidas|starters|desserts|drinks|pizzas|pastas", re.I)
MAX_SITES = 220
MAX_PAGES = 8
MAX_LINKS = 40

class Parser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.in_anchor = False
        self.anchor_href = ""
        self.anchor_label = ""
    def handle_data(self, data):
        if self.in_anchor and data.strip():
            self.links.append((self.anchor_href, self.anchor_label + " " + data.strip()))
    def handle_endtag(self, tag):
        if tag == "a":
            self.in_anchor = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.in_anchor = True
            self.anchor_href = a["href"]
            self.anchor_label = " ".join([a.get("title", ""), a.get("aria-label", "")])
            self.links.append((a["href"], self.anchor_label))
        if tag == "img" and a.get("src") and (STRONG.search(a.get("src", "") + " " + a.get("alt", "")) or re.search(r"qr|codigo|código", a.get("src", "") + " " + a.get("alt", ""), re.I)):
            self.links.append((a["src"], a.get("alt", "")))

def safe(url):
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return False
        return all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(p.hostname, 443))
    except (ValueError, OSError):
        return False

def same_host(url, origin):
    return urllib.parse.urlsplit(url).hostname == urllib.parse.urlsplit(origin).hostname

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)
ROBOTS = {}

def robots_allowed(url):
    p = urllib.parse.urlsplit(url)
    host = p.hostname
    if host not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url("https://" + host + "/robots.txt")
        try:
            # Fail closed if robots.txt is inaccessible.
            req = urllib.request.Request(rp.url, headers={"User-Agent": "NerjaFoodGuide/4.0"})
            with OPENER.open(req, timeout=5) as response:
                raw = response.read(100001)
            if len(raw) > 100000:
                ROBOTS[host] = None
            else:
                rp.parse(raw.decode("utf-8", "replace").splitlines())
                ROBOTS[host] = rp
        except urllib.error.HTTPError as error:
            ROBOTS[host] = True if error.code in (404, 410) else None
        except Exception:
            ROBOTS[host] = None
    return ROBOTS[host] is True or (ROBOTS[host] is not None and ROBOTS[host].can_fetch("NerjaFoodGuide", url))

def fetch_html(url):
    if not safe(url) or not robots_allowed(url):
        return None
    req = urllib.request.Request(url, headers={
        "User-Agent": "NerjaFoodGuide/4.0 (+https://tuffysan.github.io/nerja-food-guide/)",
        "Accept": "text/html"
    })
    with OPENER.open(req, timeout=7) as response:
        if response.geturl() != url or "text/html" not in response.headers.get("Content-Type", "").lower():
            return None
        body = response.read(250001)
    if len(body) > 250000:
        return None
    parser = Parser()
    parser.feed(body.decode("utf-8", "replace"))
    return parser.links

def sitemap_menus(site):
    """Find menu pages in a site's public sitemap without a paid search API."""
    base = urllib.parse.urlsplit(site)
    root = base.scheme + "://" + base.netloc
    queue = [root + "/sitemap.xml", root + "/wp-sitemap.xml"]
    visited = set()
    found = {}
    while queue and len(visited) < 8 and len(found) < MAX_LINKS:
        url = queue.pop(0)
        if url in visited or not same_host(url, site) or not safe(url) or not robots_allowed(url):
            continue
        visited.add(url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NerjaFoodGuide/4.2"})
            with OPENER.open(req, timeout=5) as response:
                if response.geturl() != url:
                    continue
                content = response.read(350001)
            if len(content) > 350000:
                continue
            tree = ET.fromstring(content)
            for element in tree.iter():
                if element.tag.rsplit("}", 1)[-1] != "loc" or not element.text:
                    continue
                target = element.text.strip().split("#")[0]
                if not same_host(target, site) or not safe(target):
                    continue
                if target.lower().endswith(".xml") and len(queue) < 12:
                    queue.append(target)
                elif STRONG.search(urllib.parse.unquote(urllib.parse.urlsplit(target).path)):
                    found[target] = {"url": target, "kind": kind(target), "status": "candidate", "source": url}
        except (OSError, ValueError, ET.ParseError):
            continue
    return list(found.values())

def kind(url):
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if re.search(r"\.(?:png|jpe?g|webp)$", path):
        return "image"
    return "web"

def discover(site):
    queue = [(site, 0)]
    visited = set()
    found = {}
    while queue and len(visited) < MAX_PAGES and len(found) < MAX_LINKS:
        page, depth = queue.pop(0)
        if page in visited:
            continue
        visited.add(page)
        try:
            links = fetch_html(page)
        except Exception:
            continue
        if links is None:
            continue
        for href, label in links:
            target = urllib.parse.urljoin(page, href).split("#")[0]
            if not same_host(target, site) or not safe(target):
                continue
            clue = urllib.parse.unquote(target) + " " + label
            if STRONG.search(clue):
                found[target] = {"url": target, "kind": kind(target), "status": "candidate", "source": page}
            if depth < 3 and kind(target) == "web" and (KEYWORDS.search(clue) or STRONG.search(clue)) and target not in visited and not any(x[0] == target for x in queue):
                queue.append((target, depth + 1))
            if len(found) >= MAX_LINKS:
                break
        time.sleep(0.2)
    for entry in sitemap_menus(site):
        found.setdefault(entry["url"], entry)
    return list(found.values())[:MAX_LINKS]

if __name__ == "__main__":
    data = json.loads((ROOT / "restaurants.json").read_text(encoding="utf-8"))
    out = {}
    seed_path = ROOT / "verified-source-menus.json"
    seeds = json.loads(seed_path.read_text(encoding="utf-8")).get("entries", []) if seed_path.exists() else []
    known_sources = json.loads((ROOT / "verified-source-menus.json").read_text(encoding="utf-8")).get("entries", []) if (ROOT / "verified-source-menus.json").exists() else []
    for restaurant in data.get("items", [])[:MAX_SITES]:
        site = restaurant.get("website", "")
        if not site:
            matched = [x for x in seeds if x.get("source") and (x["name"].casefold() == restaurant["name"].casefold() or any(m.casefold() == restaurant["name"].casefold() for m in x.get("match", [])))]
            if len(matched) == 1:
                site = matched[0]["source"]
        direct = restaurant.get("menu", "")
        for known in known_sources:
            if known.get("name", "").casefold() == restaurant.get("name", "").casefold() and not site:
                site = known.get("source", "")
        links = []
        if direct and safe(direct):
            links.append({"url": direct, "kind": kind(direct), "status": "published", "source": "OpenStreetMap menu tag"})
        if site and safe(site):
            if kind(site) != "web":
                links.append({"url": site, "kind": kind(site), "status": "candidate", "source": "official website"})
            else:
                links.extend(discover(site))
            if not links:
                links.append({"url": site, "kind": "website", "status": "website_only", "source": site})
        if links:
            dedup = {x["url"]: x for x in links}
            out[restaurant["id"]] = {"name": restaurant["name"], "official_website": site, "links": list(dedup.values())}
        print(restaurant.get("name", "?"), len(links), "links", flush=True)
    curated = json.loads((ROOT / "curated-menus.json").read_text(encoding="utf-8")).get("entries", [])
    for entry in curated:
        name = entry.get("name", "")
        source = entry.get("source", "")
        if not source or not safe(source):
            continue
        matched = next((p for p in data.get("items", []) if any(m.casefold() in p.get("name", "").casefold() for m in entry.get("match", []))), None)
        rid = matched["id"] if matched else "curated/" + name
        # Curated sources are editorially supplied; no external search-engine API is required.
        site = source if urllib.parse.urlsplit(source).path in ("", "/") else urllib.parse.urlunsplit((*urllib.parse.urlsplit(source)[:2], "/", "", ""))
        links = [{"url": source, "kind": kind(source), "status": "curated", "source": "curated-menus.json"}]
        if safe(site) and not any(site.endswith(domain) or urllib.parse.urlsplit(site).hostname.endswith(domain) for domain in ("thefork.es", "linktr.ee", "esnerja.com")):
            links.extend(discover(site))
        existing = out.get(rid, {}).get("links", [])
        out[rid] = {"name": name, "official_website": site, "links": list({x["url"]: x for x in existing + links}.values())[:MAX_LINKS]}
    # Seeded sources supplement incomplete OpenStreetMap website coverage.
    seeds_path = ROOT / "verified-menu-sources.json"
    if seeds_path.exists():
        seeds = json.loads(seeds_path.read_text(encoding="utf-8")).get("entries", [])
        for entry in seeds:
            if entry.get("source_type") != "official":
                continue
            name = entry.get("name", "")
            site = entry.get("website", "")
            menu = entry.get("menu", "")
            if not site or not safe(site):
                continue
            key = next((r["id"] for r in data.get("items", []) if r["name"].casefold() == name.casefold()), "verified/" + name)
            links = []
            if menu and safe(menu) and same_host(menu, site):
                links.append({"url": menu, "kind": kind(menu), "status": "published", "source": "Reviewed source list"})
            links.extend(discover(site))
            if links:
                existing = out.get(key, {}).get("links", [])
                out[key] = {"name": name, "official_website": site, "links": list({x["url"]: x for x in existing + links}.values())}
    (ROOT / "menu-discovery.json").write_text(json.dumps({
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": "Discovered candidates are not verified menus. Official-site crawling respects robots.txt.",
        "restaurants": out
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Restaurants with links:", len(out))
