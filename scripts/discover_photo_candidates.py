"""Find nearby Commons photo candidates for manual restaurant identity review.
Proximity alone is NOT proof that a photo depicts a restaurant.
No candidate is published on the restaurant cards automatically.
"""
import datetime
import json
import pathlib
import re
import urllib.parse
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]/"data"
API="https://commons.wikimedia.org/w/api.php"
HEADERS={"User-Agent":"NerjaFoodGuide/4.0 (community guide; geosearch review candidates)"}

def candidates_for(r):
    try:
        lat=float(r["lat"]); lon=float(r["lon"])
        if not (36.70<lat<36.81 and -3.94<lon< -3.80):return []
    except (KeyError,ValueError,TypeError):return []
    params=urllib.parse.urlencode({
        "action":"query","format":"json","list":"geosearch",
        "gscoord":f"{lat}|{lon}","gsradius":70,
        "gsnamespace":6,"gsprimary":"all","gslimit":12
    })
    req=urllib.request.Request(API+"?"+params,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=7) as response:
        rows=json.load(response).get("query",{}).get("geosearch",[])
    name=str(r["name"]).casefold()
    words=[w for w in re.findall(r"[a-záéíóúñü]{4,}",name) if w not in
           {"restaurante","restaurant","cafeteria","cafetería","bar","cafe","café","nerja","the","del","de","los","las"}]
    result=[]
    for row in rows:
        title=str(row.get("title",""))
        if not title.startswith("File:"):continue
        matches=[w for w in words if w in title.casefold()]
        if not matches:continue
        result.append({"title":title,"source":"https://commons.wikimedia.org/wiki/"+urllib.parse.quote(title.replace(" ","_"),safe=":/"),
                       "distance_m":round(float(row.get("dist",9999)),1),"matched_words":matches,
                       "status":"needs_manual_identity_and_license_review"})
    return result[:5]

def main():
    restaurants=json.loads((ROOT/"restaurants.json").read_text(encoding="utf-8")).get("items",[])
    photos=json.loads((ROOT/"restaurant-photos.json").read_text(encoding="utf-8")).get("photos",{})
    pending={}
    checked=0
    for r in restaurants:
        if r["id"] in photos:continue
        if checked>=12:break
        checked+=1
        try:
            options=candidates_for(r)
            if options:pending[r["id"]]={"name":r["name"],"candidates":options}
        except (OSError,ValueError,KeyError) as exc:
            print("Geosearch unavailable for",r["id"],str(exc)[:100])
    (ROOT/"photo-review-candidates.json").write_text(json.dumps({
        "generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "warning":"Candidates are NOT approved photographs; manually verify subject, rights and attribution.",
        "restaurants":pending
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Restaurants with unverified candidate photos:",len(pending))

if __name__=="__main__":main()
