import json,pathlib,urllib.parse,urllib.request,html.parser,re,datetime
root=pathlib.Path(__file__).resolve().parents[1]/'data'
class Parser(html.parser.HTMLParser):
 def __init__(self): super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'):self.links.append((a['href'],a.get('title','')))
def safe(u):
 try:
  p=urllib.parse.urlsplit(u)
  return p.scheme in ('http','https') and p.hostname and not p.username and not p.password and p.port in (None,80,443) and not p.hostname.endswith(('.local','.internal','.localhost'))
 except: return False
data=json.loads((root/'restaurants.json').read_text());out={}
for r in data['items']:
 links=[];website=r.get('website');menu=r.get('menu')
 if menu and safe(menu):links.append(dict(url=menu,kind='web',status='published',source='OpenStreetMap menu tag'))
 if website and safe(website) and not links:
  try:
   req=urllib.request.Request(website,headers={'User-Agent':'NerjaFoodGuide/3.0','Accept':'text/html'})
   with urllib.request.urlopen(req,timeout=8) as resp:
    final=resp.geturl()
    if not safe(final) or urllib.parse.urlsplit(final).hostname!=urllib.parse.urlsplit(website).hostname:continue
    if 'text/html' not in resp.headers.get('Content-Type',''):continue
    body=resp.read(200001)
    if len(body)>200000:continue
   p=Parser();p.feed(body.decode('utf-8','replace'))
   for href,label in p.links:
    u=urllib.parse.urljoin(final,href)
    if safe(u) and urllib.parse.urlsplit(u).hostname==urllib.parse.urlsplit(final).hostname and re.search(r'menu|men[uú]|carta|speisekarte|pdf',u+' '+label,re.I):
     links.append(dict(url=u,kind='pdf' if urllib.parse.urlsplit(u).path.lower().endswith('.pdf') else 'web',status='candidate',source=final))
    if len(links)>=8:break
  except Exception as e: print('Skipped',r['name'],str(e)[:80])
 if links:out[r['id']]=dict(name=r['name'],official_website=website,links=links)
(root/'menu-discovery.json').write_text(json.dumps(dict(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),note='Menu candidates are not verified. Links point to original websites.',restaurants=out),ensure_ascii=False,indent=2)+'\n')
print('Menu links for',len(out),'places')
