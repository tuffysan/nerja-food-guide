"""Extract candidate dish/price pairs from official restaurant PDF menus.
Candidate data is never presented as verified. PDF bytes are processed in memory.
"""
import io,json,re,pathlib,urllib.request,urllib.parse,datetime,ipaddress,socket
from pypdf import PdfReader
root=pathlib.Path(__file__).resolve().parents[1]/"data"
restaurants=json.loads((root/"restaurants.json").read_text())["items"]
discovery=json.loads((root/"menu-discovery.json").read_text()).get("restaurants",{})
target=root/"pdf-menus.json"
previous=json.loads(target.read_text()).get("restaurants",{}) if target.exists() else {}
def allowed(url,base):
 try:
  p=urllib.parse.urlsplit(url);b=urllib.parse.urlsplit(base)
  if p.scheme!="https" or p.hostname!=b.hostname or p.port not in (None,443):return False
  for result in socket.getaddrinfo(p.hostname,443):
   addr=ipaddress.ip_address(result[4][0])
   if not addr.is_global:return False
  return True
 except Exception:return False
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
opener=urllib.request.build_opener(NoRedirect)
pattern=re.compile(r"^(.{4,95}?)\s+(?:[.·•-]\s*){0,8}(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?\s*$",re.I)
out={}
for r in restaurants:
 site=r.get("website")
 if not site:continue
 links=discovery.get(r["id"],{}).get("links",[])
 candidates=[x["url"] for x in links if x.get("kind")=="pdf" and allowed(x.get("url",""),site)]
 for url in candidates[:2]:
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"NerjaFoodGuide/3.3","Accept":"application/pdf"})
   with opener.open(req,timeout=12) as response:
    if "pdf" not in response.headers.get("Content-Type","").lower() and not url.lower().split("?")[0].endswith(".pdf"):continue
    data=response.read(2_500_001)
   if len(data)>2_500_000 or not data.startswith(b"%PDF"):continue
   reader=PdfReader(io.BytesIO(data),strict=False)
   if len(reader.pages)>15:continue
   pairs=[]
   for page in reader.pages:
    text=page.extract_text() or ""
    for line in text.splitlines():
     m=pattern.match(" ".join(line.strip().split()))
     if m and not re.search(r"\b(total|iva|vat|telefono|phone|descuento)\b",m[1],re.I):
      pairs.append([m[1].strip(" .-"),m[2].replace(".",",")+" €"])
   pairs=list({x[0].casefold():x for x in pairs}.values())[:80]
   if len(pairs)>=3:
    out[r["id"]]={"source":url,"status":"candidate","checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"dishes":pairs}
    print(r["name"],len(pairs),"PDF candidate items",flush=True)
    break
  except Exception as e:print("PDF skipped",r["name"],str(e)[:100],flush=True)
 if r["id"] not in out and r["id"] in previous:out[r["id"]]=previous[r["id"]]
target.write_text(json.dumps({"restaurants":out},ensure_ascii=False,indent=2)+"\n")
