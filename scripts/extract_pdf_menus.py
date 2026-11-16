"""OCR public restaurant menu PDFs and menu images with free local Tesseract.
Candidate prices are unverified. No downloaded media is committed.
"""
import io,json,re,pathlib,urllib.request,urllib.parse,datetime,ipaddress,socket,subprocess,tempfile,time
from pypdf import PdfReader
from discover_menus import robots_allowed, OPENER, safe, same_host
root=pathlib.Path(__file__).resolve().parents[1]/"data"
restaurants=json.loads((root/"restaurants.json").read_text())["items"]
discovery=json.loads((root/"menu-discovery.json").read_text()).get("restaurants",{})
target=root/"pdf-menus.json"

def allowed(url,base):
 try:
  p=urllib.parse.urlsplit(url);b=urllib.parse.urlsplit(base)
  if p.scheme!="https" or p.hostname!=b.hostname or p.port not in (None,443) or p.username or p.password:return False
  for result in socket.getaddrinfo(p.hostname,443):
   if not ipaddress.ip_address(result[4][0]).is_global:return False
  return True
 except Exception:return False
opener=OPENER
MAX_DOWNLOAD_BYTES=8_000_000
pattern=re.compile(r"^(.{4,95}?)\s+(?:[.·•-]\s*){0,8}(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?\s*$",re.I)
def plausible(name):
 name=name.strip()
 words=name.split()
 return (len(words)>=2 and len(name)>=9 and len(name)<=85 and len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]",name))>=7 and not re.search(r"[<>|{}\\] |https?://|www\.|\d{4}",name,re.I) and not any(len(w)>24 for w in words))
price_only=re.compile(r"^(?:€\s*)?(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?$",re.I)
def adjacent_pairs(text):
 lines=[" ".join(x.split()) for x in text.splitlines()]
 found=[]
 for i in range(len(lines)-1):
  name=lines[i].strip(" .·-")
  m=price_only.fullmatch(lines[i+1])
  if m and plausible(name) and not re.search(r"\b(total|iva|vat|telefono|phone|descuento|subtotal|desde|from)\b",name,re.I):
   amount=float(m[1].replace(",","."))
   if 0.5<=amount<=250:
    found.append([name,m[1].replace(".",",")+" €"])
 return found
def pairs_from(text):
 pairs=[]
 for line in text.splitlines():
  m=pattern.match(" ".join(line.strip().split()))
  if m and plausible(m[1]) and not re.search(r"\b(total|iva|vat|telefono|phone|descuento)\b",m[1],re.I):
   pairs.append([m[1].strip(" .-"),m[2].replace(".",",")+" €"])
 return list({x[0].casefold():x for x in pairs+adjacent_pairs(text)}.values())[:80]
def ocr(image):
 texts=[]
 for mode in ("11","6"):
  try:
   result=subprocess.run(["tesseract","stdin","stdout","-l","spa+eng","--psm",mode],input=image,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=18,check=True)
   texts.append(result.stdout.decode("utf-8","replace"))
  except (subprocess.TimeoutExpired,subprocess.CalledProcessError):
   continue
 return "\n".join(texts)
def read_pdf(data):
 reader=PdfReader(io.BytesIO(data),strict=False)
 if len(reader.pages)>25:return []
 text="\n".join((p.extract_text() or "") for p in reader.pages[:10])
 if len(pairs_from(text))>=3:return pairs_from(text)
 with tempfile.TemporaryDirectory() as directory:
  pdf=pathlib.Path(directory)/"menu.pdf";pdf.write_bytes(data)
  # OCR first two pages only; bounded processing cost on shared GitHub runners.
  proc=subprocess.run(["pdftoppm","-f","1","-l","3","-scale-to","1400","-png",str(pdf),str(pathlib.Path(directory)/"page")],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=35,check=True)
  for page in sorted(pathlib.Path(directory).glob("page-*.png")):
   if page.stat().st_size<3_000_000:text+="\n"+ocr(page.read_bytes())
 return pairs_from(text)
previous=json.loads(target.read_text(encoding="utf-8")).get("restaurants",{}) if target.exists() else {}
out={}
diagnostics={"attempted":0,"fresh":0,"failures":[],"stale":0}
# Include curated and researched PDFs even if a venue has no OSM ID or website.
extra=[]
curated=json.loads((root/"curated-menus.json").read_text(encoding="utf-8")).get("entries",[])
verified=json.loads((root/"verified-menu-sources.json").read_text(encoding="utf-8")).get("entries",[])
for entry in curated:
 url=entry.get("source","")
 if urllib.parse.urlsplit(url).path.lower().endswith(".pdf"):
  extra.append({"id":"curated/"+entry["name"],"name":entry["name"],"website":url,"extra_url":url,"source_type":"third_party" if any(h in urllib.parse.urlsplit(url).hostname.lower() for h in ("carta.menu","menuweb.menu","thefork","restaurantguru")) else "unverified"})
for entry in verified:
 url=entry.get("menu","")
 if urllib.parse.urlsplit(url).path.lower().endswith(".pdf"):
  extra.append({"id":"verified/"+entry["name"],"name":entry["name"],"website":url,"extra_url":url,"source_type":entry.get("source_type","unverified")})
deadline=time.monotonic()+420
for r in restaurants+extra:
 if time.monotonic()>deadline:break
 site=r.get("website")
 if not site or not urllib.parse.urlsplit(site).scheme=="https":continue
 links=discovery.get(r["id"],{}).get("links",[])
 if r.get("extra_url"):
  links=[{"url":r["extra_url"],"kind":"pdf"}]+links
 candidates=[x for x in links if x.get("kind") in ("pdf","image") and allowed(x.get("url",""),site)]
 for candidate in candidates[:12]:
  url=candidate["url"]
  try:
   diagnostics["attempted"]+=1
   if not safe(url) or not robots_allowed(url):continue
   req=urllib.request.Request(url,headers={"User-Agent":"NerjaFoodGuide/3.4","Accept":"application/pdf,image/*"})
   with opener.open(req,timeout=10) as response:
    if not same_host(response.geturl(),url) or not safe(response.geturl()):continue
    content_type=response.headers.get("Content-Type","").lower()
    data=response.read(MAX_DOWNLOAD_BYTES+1)
   if len(data)>MAX_DOWNLOAD_BYTES:
    diagnostics["failures"].append({"restaurant":r["name"],"url":url,"reason":"File exceeds 8 MB limit"})
    continue
   if data.startswith(b"%PDF"):pairs=read_pdf(data)
   elif content_type.startswith("image/") and (data.startswith(b"\x89PNG") or data.startswith(b"RIFF") or data.startswith(b"\xff\xd8\xff")):
    pairs=pairs_from(ocr(data))
   else:
    diagnostics["failures"].append({"restaurant":r["name"],"url":url,"reason":"Unsupported content type"})
    continue
   if len(pairs)>=2:
    out[r["id"]]={"source":url,"status":"candidate","source_type":r.get("source_type","official_site" if not r.get("extra_url") else "unverified"),"method":"pdf-text-or-local-ocr","checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"dishes":pairs}
    diagnostics["fresh"]+=1
    print(r["name"],len(pairs),"unverified menu candidates",flush=True)
    break
   diagnostics["failures"].append({"restaurant":r["name"],"url":url,"reason":"No confident dish/price pairs"})
  except Exception as e:
   diagnostics["failures"].append({"restaurant":r["name"],"url":url,"reason":str(e)[:160]})
   print("OCR skipped",r["name"],str(e)[:100],flush=True)

for key, old in previous.items():
 if key not in out:
  out[key]=dict(old,status="stale_candidate",stale_reason="No fresh PDF extraction")
  diagnostics["stale"]+=1
target.write_text(json.dumps({"restaurants":out},ensure_ascii=False,indent=2)+"\n")
(root/"pdf-menu-diagnostics.json").write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+"\n")
