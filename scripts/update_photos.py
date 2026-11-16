"""Resolve only explicitly linked OSM/Wikimedia Commons restaurant photos.
No image search by restaurant name: that could misidentify venues.
All license information is preserved and displayed with the photo.
"""
import datetime
import html
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data"
INPUT = ROOT / "restaurants.json"
OUTPUT = ROOT / "restaurant-photos.json"
API = "https://commons.wikimedia.org/w/api.php"
AGENT = "NerjaFoodGuide/4.0 (noncommercial community restaurant guide; Wikimedia metadata)"
ALLOWED_LICENSES = {"CC0", "CC-BY", "CC-BY-SA", "PUBLIC DOMAIN", "PD", "PDM"}

def title_from_tag(tag):
    tag = str(tag or "").strip()
    if not tag:
        return None
    if tag.startswith("https://"):
        parsed = urllib.parse.urlsplit(tag)
        if parsed.hostname == "commons.wikimedia.org" and parsed.path.startswith("/wiki/File:"):
            tag = urllib.parse.unquote(parsed.path.split("/wiki/", 1)[1])
        elif parsed.hostname == "upload.wikimedia.org":
            tag = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
        else:
            return None
    tag = re.sub(r"^(?:File:|Image:)", "", tag, flags=re.I).replace("_", " ")
    if not re.fullmatch(r"[^/?#<>]{4,180}[.](?:jpe?g|png|webp)", tag, flags=re.I):
        return None
    return "File:" + tag

def clean(value):
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    return " ".join(html.unescape(value).split())[:180]

def license_allowed(license_name):
    """Accept only known free licenses, never NC/ND restrictions."""
    value = str(license_name or "").upper().strip().replace(" ", "-")
    if any(part in value for part in ("-NC", "-ND", "NONCOMMERCIAL", "NODERIVATIVES")):
        return False
    return bool(re.fullmatch(
        r"(?:CC0(?:-1[.]0)?|CC-BY(?:-SA)?(?:-[1-4][.]0)?|"
        r"PD(?:-[A-Z0-9.-]+)?|PDM|PUBLIC-DOMAIN)", value
    ))

def request_metadata(titles):
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
        "iiurlwidth": "700", "titles": "|".join(titles),
    })
    req = urllib.request.Request(API + "?" + params, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=22) as response:
        if response.status != 200:
            raise RuntimeError("Wikimedia metadata unavailable")
        return json.load(response)["query"]["pages"]


def wikidata_image_titles(restaurants):
    """Wikidata P18 photos linked by explicit OSM Q-ID; never fuzzy-match names."""
    identifiers = {}
    for restaurant in restaurants:
        qid = str(restaurant.get("wikidata") or "").strip()
        if re.fullmatch(r"Q[1-9][0-9]{0,11}", qid) and not title_from_tag(restaurant.get("image")):
            identifiers.setdefault(qid, []).append(restaurant["id"])
    result = {}
    for offset in range(0, min(len(identifiers), 150), 25):
        batch = list(identifiers)[offset:offset + 25]
        params = urllib.parse.urlencode({
            "action": "wbgetentities", "format": "json", "ids": "|".join(batch),
            "props": "claims"
        })
        try:
            req = urllib.request.Request("https://www.wikidata.org/w/api.php?" + params,
                headers={"User-Agent": AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as response:
                entities = json.load(response).get("entities", {})
            for qid in batch:
                claims = entities.get(qid, {}).get("claims", {}).get("P18", [])
                for claim in claims[:1]:
                    name = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                    title = title_from_tag(name)
                    if title:
                        result.setdefault(title, []).extend(identifiers[qid])
        except (OSError, ValueError, KeyError) as exc:
            print("Wikidata photo lookup unavailable:", str(exc)[:120])
        time.sleep(0.3)
    return result

def build():
    restaurants = json.loads(INPUT.read_text(encoding="utf-8")).get("items", [])
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")).get("photos", {}) if OUTPUT.exists() else {}
    titles = {}
    for restaurant in restaurants:
        title = title_from_tag(restaurant.get("image"))
        if title:
            titles.setdefault(title, []).append(restaurant["id"])
    for title, ids in wikidata_image_titles(restaurants).items():
        titles.setdefault(title, []).extend(ids)
    approvals_file = ROOT / "approved-restaurant-photos.json"
    if approvals_file.exists():
        approved = json.loads(approvals_file.read_text(encoding="utf-8")).get("approved", [])
        restaurant_names = {r["id"]: r["name"] for r in restaurants}
        for entry in approved:
            rid = entry.get("restaurant_id")
            title = title_from_tag(entry.get("commons_file"))
            if title and rid in restaurant_names and restaurant_names[rid] == entry.get("restaurant_name"):
                titles.setdefault(title, []).append(rid)
    result = {}
    errors = 0
    for offset in range(0, len(titles), 10):
        batch = list(titles)[offset:offset + 10]
        try:
            pages = request_metadata(batch)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            errors += 1
            print("Photo metadata unavailable:", str(exc)[:120])
            continue
        for page in pages:
            title = page.get("title")
            info = (page.get("imageinfo") or [None])[0]
            if not info or info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
                continue
            meta = info.get("extmetadata") or {}
            value = lambda key: clean((meta.get(key) or {}).get("value"))
            license_name = value("LicenseShortName")
            if not license_allowed(license_name) or value("NonFree").lower() == "true":
                continue
            url = info.get("thumburl") or info.get("url")
            source = info.get("descriptionurl")
            license_url = value("LicenseUrl")
            if not url or not source or not url.startswith("https://upload.wikimedia.org/") or not source.startswith("https://commons.wikimedia.org/"):
                continue
            if license_url and not license_url.startswith("https://"):
                continue
            for rid in titles.get(title, []):
                result[rid] = {
                    "url": url, "source": source, "author": value("Artist") or value("Credit") or "Se källan",
                    "license": license_name, "license_url": license_url,
                    "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
        time.sleep(0.3)
    # Keep reviewed and attributed photos even when Commons metadata is unavailable.
    approved_ids = set()
    if approvals_file.exists():
        for entry in approved:
            rid = entry.get("restaurant_id")
            if rid in restaurant_names and restaurant_names[rid] == entry.get("restaurant_name"):
                approved_ids.add(rid)
    associated_ids = {key for values in titles.values() for key in values}
    for rid, old in previous.items():
        if rid not in result and rid in associated_ids and (errors or rid in approved_ids):
            if old.get("source", "").startswith("https://commons.wikimedia.org/") and old.get("license") and old.get("author"):
                result[rid] = old
    # Reviewed photos can be served by Commons FilePath without a successful API lookup.
    if approvals_file.exists():
        for entry in approved:
            rid = entry.get("restaurant_id")
            title = title_from_tag(entry.get("commons_file"))
            if rid not in approved_ids or rid in result or not title:
                continue
            if not entry.get("author") or not license_allowed(entry.get("license")):
                continue
            filename = title.split(":", 1)[1].replace(" ", "_")
            result[rid] = {
                "url": "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename) + "?width=700",
                "source": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe=":/()"),
                "author": entry["author"], "license": entry["license"],
                "license_url": entry.get("license_url", ""),
                "checked_at": entry.get("reviewed_at", ""),
            }
    OUTPUT.write_text(json.dumps({"photos": result, "photo_count": len(result), "metadata_errors": errors},
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Licensed restaurant photos:", len(result), "metadata errors:", errors)

if __name__ == "__main__":
    build()
