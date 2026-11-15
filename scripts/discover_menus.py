"""Discover official menu pages, PDFs and menu images. Links remain unverified."""
import json,pathlib,urllib.parse,urllib.request,html.parser,re,datetime,ipaddress,socket
root=pathlib.Path(__file__).resolve().parents[1]/"data"
class Parser(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.text=[]
 def handle_data(self,data):
  if data.strip():self.text.append(data.strip())
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=="a" and a.get("href"):self.links.append((a["href"],a.get("title","")+" "+a.get("aria-label","")))
  if tag=="img" and a.get("src") and re.search(r"menu|men[uú]|carta",a.get("src","")+" "+a.get("alt",""),re.I):self.links.append((a["src"],a.get("alt","")))
def safe(u):
 try:
  p=urllib.parse.urlsplit(u)
  if p.scheme!="https" or not p.hostname or p.username or p.password or p.port not in (None,443):return False
  return all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(p.hostname,443))
 except Exception:return False
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
opener=urllib.request.build_opener(NoRedirect)
data=json.loads((root/"restaurants.json").read_text());out={}
for r in data["items"]:
 links=[];website=r.get("website");menu=r.get("menu")
 if menu and safe(menu):links.append(dict(url=menu,kind="pdf" if urllib.parse.urlsplit(menu).path.lower().endswith(".pdf") else "web",status="published",source="OpenStreetMap menu tag"))
 if website and safe(website):
  try:
   req=urllib.request.Request(website,headers={"User-Agent":"NerjaFoodGuide/3.4","Accept":"text/html"})
   with opener.open(req,timeout=8) as resp:
    final=resp.geturl()
    if not safe(final) or urllib.parse.urlsplit(final).hostname!=urllib.parse.urlsplit(website).hostname:continue
    if "text/html" not in resp.headers.get("Content-Type",""):continue
    body=resp.read(200001)
    if len(body)>200000:continue
   p=Parser();p.feed(body.decode("utf-8","replace"))
   for href,label in p.links:
    u=urllib.parse.urljoin(final,href)
    if not safe(u) or urllib.parse.urlsplit(u).hostname!=urllib.parse.urlsplit(final).hostname:continue
    if not re.search(r"menu|men[uú]|carta|speisekarte|pdf",u+" "+label,re.I):continue
    path=urllib.parse.urlsplit(u).path.lower()
    kind="pdf" if path.endswith(".pdf") else ("image" if re.search(r"\.(?:jpe?g|png|webp)$",path,re.I) else "web")
    links.append(dict(url=u,kind=kind,status="candidate",source=final))
    if len(links)>=16:break
   # Also retain the official site as a useful fallback when no menu was found.
   if not links:links.append(dict(url=final,kind="website",status="website_only",source=final))
  except Exception as e:print("Skipped",r["name"],str(e)[:80],flush=True)
 if links:
  unique=list({x["url"]:x for x in links}.values())
  out[r["id"]]=dict(name=r["name"],official_website=website,links=unique)
(root/"menu-discovery.json").write_text(json.dumps(dict(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),note="Unverified links to original restaurant websites.",restaurants=out),ensure_ascii=False,indent=2)+chr(10))
print("Menu links for",len(out),"places")
