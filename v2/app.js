"use strict";
const DATA="../data/";
const $=id=>document.getElementById(id);
const norm=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]/g,"");
const validUrl=u=>{try{const x=new URL(u);return x.protocol==="https:"&&!!x.hostname}catch{return false}};
const menuUrl=u=>{if(!validUrl(u))return false;const x=new URL(u);return /(?:menu|men[uú]|carta|speisekarte|food|drink|bebida|\.pdf$)/i.test(decodeURIComponent(x.pathname+x.hash))};
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let restaurants=[];
async function load(name){const res=await fetch(DATA+name,{cache:"no-store"});if(!res.ok)throw Error(name+" "+res.status);return res.json()}
function merge(rest,discovery,verified,curated,photos){
 const byName=new Map(),byId=new Map();
 for(const r of rest.items||[]){const item={...r,menus:[],dishes:[],photo:photos.photos?.[r.id]||null};byId.set(r.id,item);const key=norm(r.name);if(!byName.has(key))byName.set(key,item)}
 const find=(name,id)=>byId.get(id)||byName.get(norm(name));
 const add=(r,url,status,source)=>{if(!r||!menuUrl(url))return;if(!r.menus.some(m=>m.url===url))r.menus.push({url,status,source})};
 for(const [id,d] of Object.entries(discovery.restaurants||{})){const r=find(d.name,id);for(const m of d.links||[])add(r,m.url,m.status==="published"?"source":"candidate",m.source||"Discovery")}
 for(const v of verified.entries||[])add(find(v.name),v.menu,v.source_type==="official"?"source":"candidate","Researched source");
 for(const v of curated.entries||[]){const r=find(v.name);if(!r)continue;add(r,v.source,"candidate","Curated");r.dishes=(v.dishes||[]).map(x=>Array.isArray(x)?{name:x[0],price:x[1]||""}:x).filter(x=>x.name)}
 for(const r of byId.values()){add(r,r.menu,"source","OpenStreetMap");r.menus.sort((a,b)=>Number(b.status==="source")-Number(a.status==="source"))}
 return [...byId.values()];
}
function card(r){
 const photo=r.photo&&validUrl(r.photo.url)?'<img class="photo" loading="lazy" src="'+esc(r.photo.url)+'" alt="Foto kopplat till '+esc(r.name)+'">':'<div class="placeholder" aria-hidden="true">🍽️</div>';
 const menus=r.menus.slice(0,3).map(m=>'<a href="'+esc(m.url)+'" target="_blank" rel="noopener noreferrer">Visa '+(m.url.toLowerCase().includes(".pdf")?"PDF-meny":"menykälla")+' ↗</a>').join("");
 const map=Number.isFinite(+r.lat)&&Number.isFinite(+r.lon)?'<a href="https://www.openstreetmap.org/?mlat='+encodeURIComponent(r.lat)+'&mlon='+encodeURIComponent(r.lon)+'#map=18/'+encodeURIComponent(r.lat)+'/'+encodeURIComponent(r.lon)+'" target="_blank" rel="noopener noreferrer">Karta ↗</a>':"";
 const site=validUrl(r.website)?'<a href="'+esc(r.website)+'" target="_blank" rel="noopener noreferrer">Webbplats ↗</a>':"";
 const license=r.photo?'<p class="attribution">Foto: '+esc(r.photo.author||"okänd")+' · '+esc(r.photo.license||"")+' <a href="'+esc(r.photo.source||"#")+'" target="_blank" rel="noopener noreferrer">Källa</a></p>':"";
 return '<article class="card">'+photo+'<div class="body"><h2>'+esc(r.name)+'</h2><p class="meta">'+esc(r.cuisine&&r.cuisine!=="Ej angivet"?r.cuisine:"Restaurang")+'</p><p class="meta">'+esc(r.address&&r.address!=="Adress saknas"?r.address:"Nerja")+'</p>'+(r.menus.length?'<span class="tag good">Menykälla: '+r.menus.length+'</span>':'<span class="tag">Meny saknas</span>')+(r.dishes.length?'<span class="tag">'+r.dishes.length+' registrerade rätter</span>':"")+'<div class="links">'+menus+site+map+'</div>'+license+'</div></article>';
}
function render(){
 const q=norm($("search").value),onlyMenu=$("onlyMenu").checked,onlyPhoto=$("onlyPhoto").checked;
 const items=restaurants.filter(r=>(!q||norm([r.name,r.cuisine,r.address].join(" ")).includes(q))&&(!onlyMenu||r.menus.length||r.dishes.length)&&(!onlyPhoto||r.photo));
 items.sort($("sort").value==="menu"?(a,b)=>(b.menus.length+b.dishes.length)-(a.menus.length+a.dishes.length)||a.name.localeCompare(b.name,"sv"):(a,b)=>a.name.localeCompare(b.name,"sv"));
 $("summary").textContent=items.length+" av "+restaurants.length+" restauranger · "+restaurants.filter(r=>r.menus.length||r.dishes.length).length+" med menyunderlag · "+restaurants.filter(r=>r.photo).length+" med licensierad bild";
 $("cards").innerHTML=items.map(card).join("");$("empty").hidden=items.length>0;
}
async function init(){try{const [r,d,v,c,p]=await Promise.all(["restaurants.json","menu-discovery.json","verified-menu-sources.json","curated-menus.json","restaurant-photos.json"].map(load));restaurants=merge(r,d,v,c,p);render()}catch(e){$("summary").textContent="Kunde inte ladda restaurangdata. Försök igen senare.";console.error(e)}}
["search","onlyMenu","onlyPhoto","sort"].forEach(id=>$(id).addEventListener("input",render));init();