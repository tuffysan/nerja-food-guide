/* Progressive enhancement: no paid API, original directory works if map is unavailable. */
(() => {
  "use strict";
  const cards=document.getElementById("cards");
  const filters=document.querySelector(".filters");
  if(!cards||!filters||typeof render!=="function")return;
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
  const mapBox=document.createElement("div");mapBox.id="restaurant-map";mapBox.hidden=true;mapBox.setAttribute("aria-label","Karta över restauranger i Nerja");toolbar.after(mapBox);
  let map=null,layer=null,loading=false;
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
      (mode==="all"||(mode==="fav"&&fav.has(r.id))||(mode==="menu"&&hasMenu(r))||(mode==="priced"&&hasPrices(r)))&&withinPrice(r));
  }
  function decorate(){
    const filtered=selected();
    const ids=new Set(filtered.map(r=>r.id));
    for(const card of cards.children){
      const title=card.querySelector("h2")?.textContent;
      const restaurant=items.find(r=>r.name===title);
      if(!restaurant)continue;
      card.hidden=!ids.has(restaurant.id);
      if(card.dataset.enhanced)return;
      card.dataset.enhanced="1";
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
    count.textContent=filtered.length+" restauranger";
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
      wrap.append(strong,text,a);marker.bindPopup(wrap);marker.addTo(layer);bounds.push([lat,lon]);
    }
    if(bounds.length)map.fitBounds(bounds,{padding:[25,25],maxZoom:15});
  }
  function loadMap(){
    if(map||loading)return;
    loading=true;
    const link=document.createElement("link");link.rel="stylesheet";link.href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";document.head.append(link);
    const script=document.createElement("script");script.src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload=()=>{
      map=L.map(mapBox,{scrollWheelZoom:false}).setView([36.75,-3.875],13);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom:18
      }).addTo(map);
      layer=L.layerGroup().addTo(map);
      setTimeout(()=>{map.invalidateSize();drawMap(selected())},0);
    };
    script.onerror=()=>{mapBox.textContent="Kartan kunde inte laddas. Använd kartlänkarna på restaurangkorten.";loading=false};
    document.head.append(script);
  }
  toggle.addEventListener("click",()=>{
    mapBox.hidden=!mapBox.hidden;
    toggle.setAttribute("aria-pressed",String(!mapBox.hidden));
    toggle.textContent=mapBox.hidden?"🗺️ Visa karta":"🗺️ Dölj karta";
    if(!mapBox.hidden){loadMap();if(map){map.invalidateSize();drawMap(selected())}}
  });
  priceInput.addEventListener("input",decorate);
  const original=render;
  render=function(){original();decorate()};
  if(items.length)decorate();
})();
