"""OCR public restaurant menu PDFs and menu images with free local Tesseract.
Candidate prices are unverified. No downloaded media is committed.
"""
import io,json,re,pathlib,urllib.request,urllib.parse,datetime,ipaddress,socket,subprocess,tempfile,time
from pypdf import PdfReader
root=pathlib.Path(__file__).resolve().parents[1]/"data"
restaurants=json.loads((root/"restaurants.json").read_text())["items"]
discovery=json.loads((root/"menu-discovery.json").read_text()).get("restaurants",{})
target=root/"pdf-menus.json"
previous=json.loads(target.read_text()).get("restaurants",{}) if target.exists() else {}
def allowed(url,base):
 try:
  p=urllib.parse.urlsplit(url);b=urllib.parse.urlsplit(base)
  if p.scheme!="https" or p.hostname!=b.hostname or p.port not in (None,443) or p.username or p.password:return False
  for result in socket.getaddrinfo(p.hostname,443):
   if not ipaddress.ip_address(result[4][0]).is_global:return False
  return True
 except Exception:return False
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
opener=urllib.request.build_opener(NoRedirect)
pattern=re.compile(r"^(.{4,95}?)\s+(?:[.·•-]\s*){0,8}(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?\s*$",re.I)
def plausible(name):
 name=name.strip()
 words=name.split()
 return (len(words)>=2 and len(name)>=9 and len(name)<=85 and len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]",name))>=7 and not re.search(r"[<>|{}\\] |https?://|www\.|\d{4}",name,re.I) and not any(len(w)>24 for w in words))
def pairs_from(text):
 pairs=[]
 for line in text.splitlines():
  m=pattern.match(" ".join(line.strip().split()))
  if m and plausible(m[1]) and not re.search(r"\b(total|iva|vat|telefono|phone|descuento)\b",m[1],re.I):
   pairs.append([m[1].strip(" .-"),m[2].replace(".",",")+" €"])
 return list({x[0].casefold():x for x in pairs}.values())[:80]
def ocr(image):
 return subprocess.run(["tesseract","stdin","stdout","-l","spa+eng","--psm","11"],input=image,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=18,check=True).stdout.decode("utf-8","replace")
def read_pdf(data):
 reader=PdfReader(io.BytesIO(data),strict=False)
 if len(reader.pages)>15:return []
 text="\n".join((p.extract_text() or "") for p in reader.pages[:6])
 if len(pairs_from(text))>=3:return pairs_from(text)
 with tempfile.TemporaryDirectory() as directory:
  pdf=pathlib.Path(directory)/"menu.pdf";pdf.write_bytes(data)
  # OCR first two pages only; bounded processing cost on shared GitHub runners.
  proc=subprocess.run(["pdftoppm","-f","1","-l","2","-scale-to","1400","-png",str(pdf),str(pathlib.Path(directory)/"page")],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=35,check=True)
  for page in sorted(pathlib.Path(directory).glob("page-*.png")):
   if page.stat().st_size<3_000_000:text+="\n"+ocr(page.read_bytes())
 return pairs_from(text)
out={}
deadline=time.monotonic()+420
for r in restaurants:
 if time.monotonic()>deadline:break
 site=r.get("website")
 if not site or not urllib.parse.urlsplit(site).scheme=="https":continue
 links=discovery.get(r["id"],{}).get("links",[])
 candidates=[x for x in links if x.get("kind") in ("pdf","image") and allowed(x.get("url",""),site)]
 for candidate in candidates[:12]:
  url=candidate["url"]
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"NerjaFoodGuide/3.4","Accept":"application/pdf,image/*"})
   with opener.open(req,timeout=10) as response:
    content_type=response.headers.get("Content-Type","").lower()
    data=response.read(2_500_001)
   if len(data)>2_500_000:continue
   if data.startswith(b"%PDF"):pairs=read_pdf(data)
   elif content_type.startswith("image/") and (data.startswith(b"\x89PNG") or data.startswith(b"RIFF") or data.startswith(b"\xff\xd8\xff")):
    pairs=pairs_from(ocr(data))
   else:continue
   if len(pairs)>=3:
    out[r["id"]]={"source":url,"status":"candidate","method":"pdf-text-or-local-ocr","checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"dishes":pairs}
    print(r["name"],len(pairs),"unverified menu candidates",flush=True)
    break
  except Exception as e:print("OCR skipped",r["name"],str(e)[:100],flush=True)
 if r["id"] not in out and r["id"] in previous:out[r["id"]]=previous[r["id"]]
target.write_text(json.dumps({"restaurants":out},ensure_ascii=False,indent=2)+"\n")
