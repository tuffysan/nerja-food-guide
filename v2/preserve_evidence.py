"""V2 evidence-preserving merge: never erase known menu candidates after transient crawl failures.

Run before discovery to snapshot current JSON, and after discovery to merge.
Usage: python v2/preserve_evidence.py snapshot|merge
"""
import json
import pathlib
import sys
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SNAP = ROOT / ".v2-evidence-snapshot.json"
FILES = ("menu-discovery.json", "restaurant-photos.json")

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def acceptable_url(url):
    try:
        u = urlsplit(str(url))
        return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False

def merge_discovery(previous, current):
    output = dict(current)
    entries = dict(current.get("restaurants", {}))
    for rid, old in previous.get("restaurants", {}).items():
        if rid not in entries:
            entries[rid] = old
            continue
        new = dict(entries[rid])
        links = list(new.get("links") or [])
        seen = {item.get("url") for item in links}
        for link in old.get("links", []):
            url = link.get("url")
            if acceptable_url(url) and url not in seen:
                links.append(link)
                seen.add(url)
        new["links"] = links
        entries[rid] = new
    output["restaurants"] = entries
    return output

def merge_photos(previous, current):
    output = dict(current)
    photos = dict(previous.get("photos", {}))
    photos.update(current.get("photos", {}))
    output["photos"] = photos
    output["photo_count"] = len(photos)
    return output

def main(action):
    if action == "snapshot":
        save(SNAP, {name: load(DATA / name) for name in FILES})
        print("Saved existing evidence before crawling")
    elif action == "merge":
        if not SNAP.exists():
            raise SystemExit("Missing pre-discovery snapshot")
        old = load(SNAP)
        current = {name: load(DATA / name) for name in FILES}
        merged = {
            FILES[0]: merge_discovery(old[FILES[0]], current[FILES[0]]),
            FILES[1]: merge_photos(old[FILES[1]], current[FILES[1]]),
        }
        for name, value in merged.items():
            save(DATA / name, value)
        SNAP.unlink()
        print("Merged previous menu/photo evidence without deleting existing records")
    else:
        raise SystemExit("Expected snapshot or merge")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
