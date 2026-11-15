"""Menu Discovery Engine 2.0: catalog external leads and decode public QR images.

No paid APIs. External directory pages are link-only and never scraped for prices.
"""
import datetime
import json
import pathlib
import subprocess
import tempfile
import urllib.parse
import urllib.request

from discover_menus import OPENER, Parser, robots_allowed, safe, same_host

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data"
MAX_IMAGES_PER_SITE = 8
MAX_BYTES = 1_000_000


def source_links(entries):
    """Keep provenance; do not turn third-party listings into official menus."""
    result = {}
    for entry in entries:
        url = entry.get("menu", "")
        if not url or not safe(url):
            continue
        key = "researched/" + entry["name"]
        result[key] = {
            "name": entry["name"],
            "official_website": entry.get("website", "") if entry.get("source_type") == "official" else "",
            "links": [{
                "url": url,
                "kind": "pdf" if urllib.parse.urlsplit(url).path.lower().endswith(".pdf") else "web",
                "status": "published" if entry.get("source_type") == "official" else "external_unverified",
                "source": "verified-menu-sources.json",
                "source_type": entry.get("source_type", "unverified_lead"),
                "note": entry.get("note", "")
            }]
        }
    return result


def qr_candidates(site):
    """Inspect only menu/QR-related images on an allowed official homepage."""
    if not safe(site) or not robots_allowed(site):
        return [], 0
    request = urllib.request.Request(site, headers={"User-Agent": "NerjaFoodGuide/4.2"})
    with OPENER.open(request, timeout=7) as response:
        if response.geturl() != site or "text/html" not in response.headers.get("Content-Type", "").lower():
            return [], 0
        body = response.read(250001)
    if len(body) > 250000:
        return [], 0
    parser = Parser()
    parser.feed(body.decode("utf-8", "replace"))
    images = []
    for href, label in parser.links:
        url = urllib.parse.urljoin(site, href).split("#")[0]
        if ("qr" in (href + " " + label).lower() or "codigo" in (href + " " + label).lower()) and urllib.parse.urlsplit(url).path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            if same_host(url, site) and safe(url) and robots_allowed(url):
                images.append(url)
    links = []
    for url in dict.fromkeys(images[:MAX_IMAGES_PER_SITE]):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "NerjaFoodGuide/4.2"})
            with OPENER.open(request, timeout=7) as response:
                if response.geturl() != url or not response.headers.get("Content-Type", "").lower().startswith("image/"):
                    continue
                image = response.read(MAX_BYTES + 1)
            if len(image) > MAX_BYTES:
                continue
            with tempfile.NamedTemporaryFile(suffix=".png") as file:
                file.write(image)
                file.flush()
                decoded = subprocess.run(["zbarimg", "--quiet", "--raw", file.name], capture_output=True, text=True, timeout=8, check=False)
            for line in decoded.stdout.splitlines():
                target = line.strip().split("#")[0]
                # Only same-host HTTPS targets are automatically promoted.
                if safe(target) and same_host(target, site) and robots_allowed(target):
                    links.append({"url": target, "kind": "web", "status": "qr_candidate", "source": url, "source_type": "official_site_qr"})
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return list({x["url"]: x for x in links}.values()), len(images[:MAX_IMAGES_PER_SITE])


def augment(discovered, researched, qr_lookup=None):
    qr_lookup = qr_lookup or (lambda site: ([], 0))
    output = dict(discovered)
    stats = {"external_leads": 0, "official_leads": 0, "qr_images_checked": 0, "qr_links": 0, "errors": []}
    for key, record in source_links(researched).items():
        existing = output.get(key)
        if existing:
            urls = {x["url"]: x for x in existing.get("links", [])}
            for link in record["links"]:
                urls.setdefault(link["url"], link)
            record["links"] = list(urls.values())
        output[key] = record
        if record["links"][0]["source_type"] == "official":
            stats["official_leads"] += 1
        else:
            stats["external_leads"] += 1
    for key, record in list(output.items()):
        site = record.get("official_website", "")
        if not site or not safe(site) or record.get("qr_scanned"):
            continue
        try:
            links, checked = qr_lookup(site)
            stats["qr_images_checked"] += checked
            existing = {x["url"]: x for x in record.get("links", [])}
            for link in links:
                if link["url"] not in existing:
                    existing[link["url"]] = link
                    stats["qr_links"] += 1
            record["links"] = list(existing.values())
        except Exception as error:
            stats["errors"].append({"restaurant": record.get("name", key), "reason": str(error)[:160]})
    return output, stats


def main():
    path = ROOT / "menu-discovery.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    researched = json.loads((ROOT / "verified-menu-sources.json").read_text(encoding="utf-8")).get("entries", [])
    output, stats = augment(data.get("restaurants", {}), researched, qr_candidates)
    data["restaurants"] = output
    data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data["note"] = "Official and third-party sources are labeled separately. QR links are candidates, not verified menus."
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats["generated_at"] = data["updated_at"]
    stats["total_sources"] = len(output)
    (ROOT / "menu-discovery-diagnostics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
