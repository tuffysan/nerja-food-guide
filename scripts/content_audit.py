"""Regenerate honest restaurant content audit from current free source data."""
import datetime,json,pathlib,unicodedata,re
root=pathlib.Path(__file__).resolve().parents[1]/"data"
def load(name):return json.loads((root/name).read_text(encoding="utf-8"))
def norm(s):return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFD",str(s or "").lower()).encode("ascii","ignore").decode())
restaurants=load("restaurants.json").get("items",[])
cur=load("curated-menus.json").get("entries",[])
sourced=load("verified-source-menus.json").get("entries",[])
sources=load("verified-menu-sources.json").get("entries",[])
photos=load("restaurant-photos.json").get("photos",{})
by_menu={norm(e["name"]):e for e in cur}
by_menu.update({norm(e["name"]):e for e in sourced if e.get("dishes")})
by_source={norm(e["name"]):e for e in sources}
rows=[]
for r in restaurants:
 n=norm(r.get("name"));e=by_menu.get(n,{});v=by_source.get(n,{})
 dishes=e.get("dishes") or []
 menu=e.get("source") or v.get("menu") or r.get("menu")
 rows.append({"id":r["id"],"name":r["name"],"menu_status":"dishes_and_prices" if dishes else "menu_link" if menu else "not_found","dish_count":len(dishes),"photo_status":"licensed_photo" if r["id"] in photos else "not_found","address_status":"available" if r.get("address") not in (None,"","Adress saknas") else "not_found","website_status":"available" if r.get("website") or v.get("website") else "not_found","source_url":menu})
stats={"total":len(rows),"with_dishes":sum(x["dish_count"]>0 for x in rows),"with_menu_link_or_dishes":sum(x["menu_status"]!="not_found" for x in rows),"with_photo":sum(x["photo_status"]=="licensed_photo" for x in rows),"missing_menu":sum(x["menu_status"]=="not_found" for x in rows),"missing_photo":sum(x["photo_status"]=="not_found" for x in rows)}
result={"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"scope":"OpenStreetMap restaurant records only; additional curated listings may exist","note":"No menu/photo is fabricated. Status is evidence coverage, not proof a restaurant lacks a menu.", "stats":stats,"restaurants":rows}
(root/"content-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(stats)
