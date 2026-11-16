/* Progressive enhancement: no paid API, original directory works if map is unavailable. */
(() => {
  "use strict";
  const cards=document.getElementById("cards");
  const filters=document.querySelector(".filters");
  if(!cards||!filters||typeof render!=="function")return;
  const area=document.createElement("select");
  area.id="area";area.setAttribute("aria-label","Välj område i Nerja");
  for(const [value,label] of [["","Alla områden"],["centro","Nerja centrum"],["balcon","Balcón de Europa"],["burriana","Playa Burriana"],["torrecilla","Torrecilla"],["playazo","El Playazo"],["capistrano","Capistrano"]]){
    const option=document.createElement("option");option.value=value;option.textContent=label;area.append(option);
  }
  filters.append(area);
  const reset=document.createElement("button");reset.type="button";reset.className="reset-filters";reset.textContent="Rensa filter";
  filters.append(reset);
  reset.addEventListener("click",()=>{
    document.getElementById("search").value="";
    document.getElementById("type").value="";
    document.getElementById("favorites").value="all";
    area.value="";priceInput.value="";render();
  });
  const toolbar=document.createElement("div");
  toolbar.className="toolbar";
  const toggle=document.createElement("button");
  toggle.type="button";toggle.textContent="🗺️ Visa karta";toggle.setAttribute("aria-pressed","false");
  const priceLabel=document.createElement("label");priceLabel.textContent="Högsta maträttspris (€)";
  const priceInput=document.createElement("input");
  priceInput.type="number";priceInput.min="1";priceInput.max="250";priceInput.step="1";priceInput.placeholder="Alla";priceInput.setAttribute("aria-label","Högsta maträttspris i euro");
  priceLabel.append(priceInput);
  const count=document.createElement("span");count.className="muted";count.setAttribute("aria-live","polite");
  const portal=document.createElement("a");portal.href="restaurant-portal.html";portal.textContent="🏪 Uppdatera restaurang";portal.title="Skicka in en meny för granskning";
  toolbar.append(toggle,portal,priceLabel,count);
  filters.after(toolbar);
  const mapBox=document.createElement("div");mapBox.id="restaurant-map";mapBox.hidden=false;mapBox.setAttribute("aria-label","Karta över restauranger i Nerja");toolbar.after(mapBox);
  let map=null,layer=null,loading=false;
  const zones={
    centro:[36.7472,-3.8763,0.95],
    balcon:[36.7449,-3.8753,0.42],
    burriana:[36.7515,-3.8652,0.9],
    torrecilla:[36.7434,-3.8848,0.75],
    playazo:[36.7451,-3.9017,1.4],
    capistrano:[36.7622,-3.8648,1.5]
  };
  function inArea(r){
    if(!area.value)return true;
    const zone=zones[area.value],lat=Number(r.lat),lon=Number(r.lon);
    if(!Number.isFinite(lat)||!Number.isFinite(lon))return false;
    const dy=(lat-zone[0])*111.2,dx=(lon-zone[1])*88.7;
    return Math.hypot(dx,dy)<=zone[2];
  }
  toggle.setAttribute("aria-pressed","true");
  toggle.textContent="🗺️ Dölj karta";
  let photoCatalog={};
  fetch("data/restaurant-photos.json").then(response=>response.ok?response.json():{photos:{}})
    .then(data=>{photoCatalog=data.photos||{};for(const card of cards.children){
      const restaurant=items.find(r=>r.name===card.querySelector("h2")?.textContent);
      if(restaurant){const frame=card.querySelector(".restaurant-photo");if(frame)frame.remove();addPhoto(card,restaurant)}
    }}).catch(()=>{});

  function dishes(r){
    const d=findCurated(r);
    return [...(d?.dishes||[]),...(autoMenus[d?.name]?.dishes||[]),...(pdfMenus[r.id]?.dishes||[]),...(htmlFor(r)?.dishes||[])];
  }
  function withinPrice(r){
    if(!priceInput.value)return true;
    const cap=Number(priceInput.value);
    if(!Number.isFinite(cap)||cap<=0)return true;
    return dishes(r).some(d=>Array.isArray(d)&&Number(String(d[1]).match(/\d+(?:[,.]\d+)?/)?.[0]?.replace(",", "."))<=cap);
  }
  function selected(){
    const q=document.getElementById("search").value.toLocaleLowerCase();
    const t=document.getElementById("type").value;
    const mode=document.getElementById("favorites").value;
    return items.filter(r=>searchable(r).includes(q)&&(!t||r.cuisine===t)&&
      (mode==="all"||(mode==="fav"&&fav.has(r.id))||(mode==="menu"&&hasMenu(r))||(mode==="priced"&&hasPrices(r)))&&withinPrice(r)&&inArea(r));
  }

  function photoUrl(r){
    const raw=String(r.image||"").trim();
    if(!raw)return null;
    if(raw.startsWith("https://")){
      try{const u=new URL(raw);return ["upload.wikimedia.org","commons.wikimedia.org"].includes(u.hostname)?u.href:null}catch(e){return null}
    }
    const name=raw.replace(/^File:/i,"").replace(/^Image:/i,"");
    if(!/^[^/?#]{4,160}[.](jpg|jpeg|png|webp)$/i.test(name))return null;
    return "https://commons.wikimedia.org/wiki/Special:FilePath/"+encodeURIComponent(name)+"?width=700";
  }
  function addPhoto(card,r){
    const frame=document.createElement("div");frame.className="restaurant-photo";
    const record=photoCatalog[r.id];
    if((record?.url?.startsWith("https://upload.wikimedia.org/")||record?.url?.startsWith("https://commons.wikimedia.org/wiki/Special:FilePath/"))&&record?.source?.startsWith("https://commons.wikimedia.org/")){
      const img=document.createElement("img");img.src=record.url;img.loading="lazy";img.decoding="async";
      img.alt="Foto kopplat till "+r.name+" enligt OpenStreetMap";
      img.onerror=()=>{frame.replaceChildren();frame.classList.add("photo-fallback");frame.textContent="🍽️"};
      frame.append(img);
      const credit=document.createElement("a");credit.className="photo-credit";credit.href=record.source;
      credit.target="_blank";credit.rel="noopener noreferrer";
      credit.textContent=(record.author||"Se källan")+" · "+(record.license||"Licens");
      credit.title="Upphovsperson och licens på Wikimedia Commons";
      frame.append(credit);
    }else{
      frame.classList.add("photo-fallback");
      frame.textContent=r.amenity==="cafe"?"☕":r.amenity==="fast_food"?"🥙":"🍽️";
      frame.setAttribute("aria-label","Illustration – licensierat restaurangfoto saknas");
    }
    card.prepend(frame);
  }
  function menuScore(r){
    if(dishes(r).length)return 3;
    if(hasMenu(r))return 2;
    if(r.website)return 1;
    return 0;
  }
  function decorate(){
    cards.querySelectorAll(".empty-results").forEach(el=>el.remove());
    const filtered=selected();
    const ids=new Set(filtered.map(r=>r.id));
    for(const card of cards.children){
      const title=card.querySelector("h2")?.textContent;
      const restaurant=items.find(r=>r.name===title);
      if(!restaurant)continue;
      card.hidden=!ids.has(restaurant.id);
      if(card.dataset.enhanced)continue;
      card.dataset.enhanced="1";
      addPhoto(card,restaurant);
      const details=[];
      for(const child of [...card.children]){
        if(child.tagName!=="P")continue;
        const t=child.textContent||"";
        if(/^(Öppettider|Telefon:|Rullstolsanpassning|Tillgängligt enligt OSM:|OSM-uppgifter hämtade:|Adress saknas)/.test(t))details.push(child);
      }
      if(details.length){
        const extra=document.createElement("div");extra.className="secondary-details";
        for(const d of details)extra.append(d);
        const button=document.createElement("button");button.type="button";button.className="details-toggle";
        button.textContent="Mer information ▾";button.setAttribute("aria-expanded","false");
        button.addEventListener("click",()=>{
          const open=card.classList.toggle("details-expanded");
          button.textContent=open?"Mindre information ▴":"Mer information ▾";
          button.setAttribute("aria-expanded",String(open));
        });
        const links=card.querySelector(".links");
        if(links)card.insertBefore(extra,links);else card.append(extra);
        extra.before(button);
      }
      const h=htmlFor(restaurant),p=pdfMenus[restaurant.id],v=sourceFor(restaurant);
      const tag=document.createElement("span");tag.className="source-tag";
      if(h?.dishes?.length||p?.dishes?.length){tag.textContent="Automatiskt avläst · ej verifierat";tag.classList.add("warn")}
      else if(v?.source_type==="official"){tag.textContent="Officiell menykälla"}
      else if(v?.menu){tag.textContent="Extern menykälla · kontrollera";tag.classList.add("warn")}
      else{tag.textContent="Menyuppgifter kan saknas"}
      card.querySelector("h2")?.after(tag);
    }
    const sorted=[...filtered].sort((a,b)=>menuScore(b)-menuScore(a)||a.name.localeCompare(b.name,"sv"));
    const byName=new Map([...cards.children].map(card=>[card.querySelector("h2")?.textContent,card]));
    for(const r of sorted){const card=byName.get(r.name);if(card)cards.append(card)}
    count.textContent=filtered.length+" restauranger · "+filtered.filter(hasMenu).length+" med meny · "+filtered.filter(hasPrices).length+" med maträtter/priser";
    if(!filtered.length){
      const empty=document.createElement("p");empty.className="empty-results";
      empty.textContent="Inga restauranger matchar filtren. Välj ett större område eller rensa filtren.";
      cards.append(empty);
    }
    if(map&&!mapBox.hidden)drawMap(filtered);
  }
  function drawMap(restaurants){
    if(!map||!window.L)return;
    layer.clearLayers();
    const bounds=[];
    for(const r of restaurants){
      const lat=Number(r.lat),lon=Number(r.lon);
      if(!Number.isFinite(lat)||!Number.isFinite(lon)||lat<36||lat>37||lon< -5||lon> -2)continue;
      const marker=L.marker([lat,lon]);
      const wrap=document.createElement("div");
      const strong=document.createElement("strong");strong.textContent=r.name;
      const text=document.createElement("p");text.textContent=r.cuisine||"Restaurang";
      const a=document.createElement("a");a.href="https://www.openstreetmap.org/?mlat="+lat+"&mlon="+lon+"#map=18/"+lat+"/"+lon;
      a.target="_blank";a.rel="noopener noreferrer";a.textContent="Visa i OpenStreetMap";
      const menu=document.createElement("span");menu.textContent=hasMenu(r)?" · Meny finns":" · Meny saknas";
      const show=document.createElement("button");show.type="button";show.textContent="Visa restaurang i listan";
      show.addEventListener("click",()=>{
        const card=[...cards.querySelectorAll(".card")].find(c=>c.querySelector("h2")?.textContent===r.name);
        if(card){card.scrollIntoView({behavior:"smooth",block:"center"});card.classList.add("map-selected");setTimeout(()=>card.classList.remove("map-selected"),2500)}
      });
      wrap.append(strong,text,menu,document.createElement("br"),a,document.createElement("br"),show);
      marker.bindPopup(wrap);marker.addTo(layer);bounds.push([lat,lon]);
    }
    if(bounds.length)map.fitBounds(bounds,{padding:[25,25],maxZoom:15});
    else if(layer)map.setView([36.75,-3.875],13);
  }
  function loadMap(){
    if(map||loading)return;
    loading=true;
    const link=document.createElement("link");link.rel="stylesheet";link.href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";document.head.append(link);
    const script=document.createElement("script");script.src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload=()=>{
      if(!window.L){mapBox.textContent="Kartan kunde inte starta. Använd restauranglistan.";loading=false;return}
      map=L.map(mapBox,{scrollWheelZoom:false}).setView([36.75,-3.875],13);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom:18
      }).addTo(map);
      layer=L.layerGroup().addTo(map);
      setTimeout(()=>{map.invalidateSize();drawMap(selected())},0);
    };
    script.onerror=()=>{mapBox.textContent="Kartan kunde inte laddas. Restaurangerna och deras kartlänkar fungerar fortfarande nedanför.";loading=false};
    document.head.append(script);
  }
  toggle.addEventListener("click",()=>{
    mapBox.hidden=!mapBox.hidden;
    toggle.setAttribute("aria-pressed",String(!mapBox.hidden));
    toggle.textContent=mapBox.hidden?"🗺️ Visa karta":"🗺️ Dölj karta";
    if(!mapBox.hidden){loadMap();if(map){map.invalidateSize();drawMap(selected())}}
  });
  priceInput.addEventListener("input",decorate);
  area.addEventListener("change",()=>{decorate();if(map&&!mapBox.hidden)drawMap(selected())});
  const original=render;
  render=function(){original();decorate()};
  if(items.length)decorate();
  loadMap();
})();
