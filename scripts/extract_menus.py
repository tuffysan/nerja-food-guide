"""Conservative daily extraction of structured menu data from known official websites.
Only schema.org MenuItem with an explicit price is accepted; never infer prices.
"""
import json, pathlib, urllib.request, urllib.parse, html.parser, datetime, re
root=pathlib.Path(__file__).resolve().parents[1]
source=json.loads((root/"data/curated-menus.json").read_text())
target=root/"data/auto-menus.json"
previous=json.loads(target.read_text()) if target.exists() else {"restaurants":{}}
class Scripts(html.parser.HTMLParser):
 def __init__(self): super().__init__();self.in_json=False;self.parts=[];self.scripts=[]
 def handle_starttag(self,tag,attrs):
  if tag=="script":
   self.in_json="ld+json" in dict(attrs).get("type","").lower();self.parts=[]
 def handle_data(self,data):
  if self.in_json:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=="script" and self.in_json:
   self.scripts.append("".join(self.parts));self.in_json=False
def walk(obj):
 if isinstance(obj,list):
  for x in obj:yield from walk(x)
 elif isinstance(obj,dict):
  yield obj
  for v in obj.values():yield from walk(v)
def extract(url):
 p=urllib.parse.urlsplit(url)
 if p.scheme!="https" or not p.hostname:return []
 req=urllib.request.Request(url,headers={"User-Agent":"NerjaFoodGuide/3.2 (daily structured-menu reader)","Accept":"text/html"})
 with urllib.request.urlopen(req,timeout=12) as response:
  if urllib.parse.urlsplit(response.geturl()).hostname!=p.hostname:return []
  if "text/html" not in response.headers.get("Content-Type",""):return []
  body=response.read(350001)
 if len(body)>350000:return []
 parser=Scripts();parser.feed(body.decode("utf-8","replace"))
 found=[]
 for raw in parser.scripts:
  try: doc=json.loads(raw)
  except (ValueError,TypeError):continue
  for item in walk(doc):
   typ=item.get("@type",[])
   if isinstance(typ,str):typ=[typ]
   if not any(str(t).split("/")[-1]=="MenuItem" for t in typ):continue
   name=item.get("name")
   offer=item.get("offers",{})
   if isinstance(offer,list):offer=next((x for x in offer if isinstance(x,dict) and x.get("price") is not None),{})
   if not isinstance(offer,dict):continue
   price=offer.get("price")
   currency=offer.get("priceCurrency","EUR")
   if isinstance(name,str) and len(name)<130 and isinstance(price,(str,int,float)) and re.fullmatch(r"[0-9]{1,4}(?:[.,][0-9]{1,2})?",str(price)) and currency=="EUR":
    found.append([name,str(price).replace(".",",")+" €"])
 return list({x[0].casefold():x for x in found}.values())[:80]
out={}
for entry in source["entries"]:
 url=entry["source"]
 host=urllib.parse.urlsplit(url).hostname or ""
 # Only visit the restaurant's own site, never aggregators or arbitrary discovered links.
 if host.endswith("thefork.es"):continue
 try:
  dishes=extract(url)
  if dishes:out[entry["name"]]={"source":url,"dishes":dishes,"checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
  elif entry["name"] in previous.get("restaurants",{}):out[entry["name"]]=previous["restaurants"][entry["name"]]
  print(entry["name"],len(dishes),"structured items",flush=True)
 except Exception as exc:
  print(entry["name"],"not refreshed:",str(exc)[:120],flush=True)
  if entry["name"] in previous.get("restaurants",{}):out[entry["name"]]=previous["restaurants"][entry["name"]]
target.write_text(json.dumps({"restaurants":out},ensure_ascii=False,indent=2)+"\n")
