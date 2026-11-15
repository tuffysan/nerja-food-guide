import json,urllib.request,urllib.parse,pathlib,datetime,sys
root=pathlib.Path(__file__).resolve().parents[1]
query='[out:json][timeout:60];(nwr["amenity"~"^(restaurant|cafe|fast_food)$"](36.72,-3.91,36.79,-3.83););out center;'
for endpoint in ['https://overpass.private.coffee/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
 try:
  req=urllib.request.Request(endpoint,data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'NerjaFoodGuide/3.0 (public open-source directory)','Content-Type':'application/x-www-form-urlencoded'})
  with urllib.request.urlopen(req,timeout=90) as response: data=json.load(response)
  rows=[]
  for e in data['elements']:
   t=e.get('tags',{});c=e.get('center',{});name=t.get('name') or t.get('name:es')
   if not name: continue
   rows.append(dict(id=str(e['type'])+'/'+str(e['id']),name=name,cuisine=t.get('cuisine','Ej angivet').replace(';',', '),address=' '.join(filter(None,[t.get('addr:street'),t.get('addr:housenumber')])) or 'Adress saknas',website=t.get('website') or t.get('contact:website'),menu=t.get('website:menu') or t.get('menu:website') or t.get('contact:menu'),hours=t.get('opening_hours'),lat=e.get('lat',c.get('lat')),lon=e.get('lon',c.get('lon'))))
  if len(rows)<10: raise ValueError('Dataset unexpectedly small')
  rows.sort(key=lambda x:x['name'].casefold())
  (root/'data/restaurants.json').write_text(json.dumps(dict(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source='OpenStreetMap contributors via Overpass',count=len(rows),items=rows),ensure_ascii=False,indent=2)+'\n')
  print('Updated',len(rows),'places');break
 except Exception as exc:
  print(endpoint,exc,file=sys.stderr)
else: sys.exit(1)
