import json, urllib.request, urllib.parse, pathlib, datetime, sys, time, random
root = pathlib.Path(__file__).resolve().parents[1]
destination = root / "data/restaurants.json"
# Smaller geographic cells reduce load on public Overpass servers.
cells = [(36.720,-3.910,36.755,-3.870),(36.720,-3.870,36.755,-3.830),(36.755,-3.910,36.790,-3.870),(36.755,-3.870,36.790,-3.830)]
endpoints = [
 "https://overpass-api.de/api/interpreter",
 "https://overpass.kumi.systems/api/interpreter",
 "https://overpass.private.coffee/api/interpreter",
 "https://overpass.nchc.org.tw/api/interpreter"
]
def fetch(box):
 s,w,n,e=box
 query=f'[out:json][timeout:35];nwr["amenity"~"^(restaurant|cafe|fast_food)$"]({s},{w},{n},{e});out center;'
 payload=urllib.parse.urlencode({"data":query}).encode()
 for attempt in range(6):
  endpoint=endpoints[attempt%len(endpoints)]
  try:
   req=urllib.request.Request(endpoint,data=payload,headers={"User-Agent":"NerjaFoodGuide/3.1 (OpenStreetMap attribution; daily cache)","Content-Type":"application/x-www-form-urlencoded"})
   with urllib.request.urlopen(req,timeout=48) as response:
    data=json.load(response)
   if not isinstance(data.get("elements"),list):raise ValueError("Missing elements")
   print("Fetched",len(data["elements"]),"elements from",endpoint,flush=True)
   return data["elements"]
  except Exception as exc:
   print("Attempt",attempt+1,endpoint,repr(exc),file=sys.stderr,flush=True)
   time.sleep(min(3+attempt*2,12)+random.random())
 raise RuntimeError("No Overpass endpoint succeeded for cell "+str(box))
try:
 elements=[]
 for box in cells:elements.extend(fetch(box))
 dedup={}
 for e in elements:
  tags=e.get("tags",{});center=e.get("center",{})
  name=tags.get("name") or tags.get("name:es")
  if not name:continue
  key=str(e["type"])+"/"+str(e["id"])
  dedup[key]=dict(id=key,name=name,cuisine=tags.get("cuisine","Ej angivet").replace(";",", "),address=" ".join(filter(None,[tags.get("addr:street"),tags.get("addr:housenumber")])) or "Adress saknas",website=tags.get("website") or tags.get("contact:website"),menu=tags.get("website:menu") or tags.get("menu:website") or tags.get("contact:menu"),hours=tags.get("opening_hours"),phone=tags.get("phone") or tags.get("contact:phone"),description=tags.get("description") or tags.get("description:en"),diet=tags.get("diet:vegetarian"),wheelchair=tags.get("wheelchair"),lat=e.get("lat",center.get("lat")),lon=e.get("lon",center.get("lon")))
 rows=sorted(dedup.values(),key=lambda x:x["name"].casefold())
 if len(rows)<10:raise ValueError("Unexpectedly small dataset: "+str(len(rows)))
 destination.write_text(json.dumps(dict(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source="OpenStreetMap contributors via Overpass",count=len(rows),items=rows),ensure_ascii=False,indent=2)+"\n")
 print("Updated",len(rows),"places")
except Exception as exc:
 print("Refresh failed; previous data preserved:",repr(exc),file=sys.stderr)
 try:
  cached=json.loads(destination.read_text(encoding="utf-8"))
  rows=cached.get("items",[])
  if len(rows)<10:raise ValueError("Cached restaurant directory is missing or too small")
  print("Using",len(rows),"cached restaurants; continuing menu updates",flush=True)
 except Exception as cache_error:
  print("No usable fallback restaurant directory:",repr(cache_error),file=sys.stderr)
  sys.exit(1)
