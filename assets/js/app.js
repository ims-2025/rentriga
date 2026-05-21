/* ============================================================
   RentRiga — App logic
   ============================================================ */

(function(){
  const $  = (s,r=document)=>r.querySelector(s);
  const $$ = (s,r=document)=>Array.from(r.querySelectorAll(s));

  /* ---------- Helpers ---------- */
  function fmtPrice(l){
    const lang = window.RR_getLang();
    const nf = new Intl.NumberFormat(lang === "en" ? "en-GB" : (lang === "ru" ? "ru-RU" : "lv-LV"));
    const p = nf.format(l.price);
    let unit = window.RR_t("lst.month");
    if(l.priceUnit === "per_night") unit = window.RR_t("lst.night");
    if(l.priceUnit === "per_m2")    unit = window.RR_t("lst.m2");
    return `€${p}<small>${unit}</small>`;
  }
  function titleFor(l){
    const lang = window.RR_getLang();
    if(lang === "lv" && l.titleLv) return l.titleLv;
    if(lang === "ru" && l.titleRu) return l.titleRu;
    return l.title;
  }
  function badgeFor(l){
    const out = [];
    if(l.premium) out.push(`<span class="badge accent">${({en:"Premium",lv:"Premium",ru:"Премиум"})[window.RR_getLang()]}</span>`);
    if(l.verified) out.push(`<span class="badge good">✓ ${({en:"Verified",lv:"Pārbaudīts",ru:"Проверено"})[window.RR_getLang()]}</span>`);
    if(l.isNew) out.push(`<span class="badge dark">${({en:"New",lv:"Jauns",ru:"Новое"})[window.RR_getLang()]}</span>`);
    return out.join("");
  }
  function featsFor(l){
    const lang = window.RR_getLang();
    const parts = [];
    if(l.rooms) parts.push(`<span>◧ ${l.rooms} ${({en:"rooms",lv:"ist.",ru:"комн."})[lang]}</span>`);
    if(l.area)  parts.push(`<span>⬜ ${l.area} m²</span>`);
    if(l.floor) parts.push(`<span>↥ ${l.floor}</span>`);
    if(l.plot)  parts.push(`<span>▦ ${l.plot} m²</span>`);
    return parts.join("");
  }
  function cardHtml(l){
    return `
      <a class="listing" href="listing.html?id=${l.id}">
        <div class="listing-img">
          <img loading="lazy" src="${l.img}" alt="${escapeHtml(l.title)}">
          <div class="listing-badges">${badgeFor(l)}</div>
          <button class="fav" aria-label="Save" onclick="event.preventDefault();this.classList.toggle('is-fav')">♥</button>
        </div>
        <div class="listing-body">
          <div class="listing-price">${fmtPrice(l)}</div>
          <div class="listing-title">${escapeHtml(titleFor(l))}</div>
          <div class="listing-location">📍 ${escapeHtml(l.street)}, ${escapeHtml(l.district)}</div>
          <div class="listing-feats">${featsFor(l)}</div>
          <div class="listing-foot">
            <span class="source-tag">${escapeHtml(l.source)}</span>
            <span>ID ${l.id}</span>
          </div>
        </div>
      </a>`;
  }
  function escapeHtml(s){
    return String(s||"").replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  /* ---------- Common: header, language ---------- */
  function initHeader(){
    $$(".lang-switch button").forEach(b=>{
      b.addEventListener("click", ()=> window.RR_setLang(b.dataset.lang));
    });
    document.documentElement.setAttribute("lang", window.RR_getLang());
  }

  /* ---------- Homepage ---------- */
  function initHome(){
    if(!$(".js-home")) return;

    /* stats */
    const s = window.RR_STATS;
    $$(".js-stat-listings").forEach(e=> e.textContent = s.total);
    $$(".js-stat-sources").forEach(e=> e.textContent = s.sources);
    $$(".js-stat-districts").forEach(e=> e.textContent = s.districts);

    /* district datalist */
    const dl = $("#districtList");
    if(dl){
      dl.innerHTML = window.RR_DISTRICTS.map(d=>`<option value="${d}">`).join("");
    }

    /* featured grid */
    const featured = window.RR_LISTINGS
      .filter(l => l.premium || l.verified)
      .slice(0,6);
    $("#featuredGrid").innerHTML = featured.map(cardHtml).join("");

    /* search submit -> listings page with query */
    $("#heroSearch").addEventListener("submit", e=>{
      e.preventDefault();
      const params = new URLSearchParams();
      const where = $("#fWhere").value.trim();
      const type  = $("#fType").value;
      const rooms = $("#fRooms").value;
      const price = $("#fPrice").value;
      if(where) params.set("q", where);
      if(type)  params.set("type", type);
      if(rooms) params.set("rooms", rooms);
      if(price) params.set("maxPrice", price);
      const tab = $(".search-tabs .active");
      if(tab && tab.dataset.tab) params.set("type", tab.dataset.tab);
      location.href = "listings.html?" + params.toString();
    });

    /* tab toggling */
    $$(".search-tabs button").forEach(b=>{
      b.addEventListener("click", ()=>{
        $$(".search-tabs button").forEach(x=>x.classList.remove("active"));
        b.classList.add("active");
      });
    });
  }

  /* ---------- Listings page ---------- */
  let LS_STATE = {
    q:"", type:"", rooms:"", maxPrice:"", minPrice:"", minArea:"", maxArea:"",
    districts: new Set(), amenities: new Set(), sources: new Set(),
    sort:"new", view:"grid", page:1, perPage:9
  };

  function readQuery(){
    const u = new URLSearchParams(location.search);
    if(u.get("q"))         LS_STATE.q = u.get("q");
    if(u.get("type"))      LS_STATE.type = u.get("type");
    if(u.get("rooms"))     LS_STATE.rooms = u.get("rooms");
    if(u.get("maxPrice"))  LS_STATE.maxPrice = u.get("maxPrice");
    if(u.get("district"))  LS_STATE.districts.add(u.get("district"));
  }

  function filterListings(){
    let arr = window.RR_LISTINGS.slice();
    if(LS_STATE.type)   arr = arr.filter(l=> l.type === LS_STATE.type);
    if(LS_STATE.q){
      const q = LS_STATE.q.toLowerCase();
      arr = arr.filter(l =>
        (l.title + " " + (l.titleLv||"") + " " + (l.titleRu||"") + " " + l.street + " " + l.district).toLowerCase().includes(q)
      );
    }
    if(LS_STATE.rooms){
      const r = parseInt(LS_STATE.rooms,10);
      arr = arr.filter(l => l.rooms && (r >= 4 ? l.rooms >= 4 : l.rooms === r));
    }
    if(LS_STATE.minPrice) arr = arr.filter(l=> l.price >= parseFloat(LS_STATE.minPrice));
    if(LS_STATE.maxPrice) arr = arr.filter(l=> l.price <= parseFloat(LS_STATE.maxPrice));
    if(LS_STATE.minArea)  arr = arr.filter(l=> (l.area||0) >= parseFloat(LS_STATE.minArea));
    if(LS_STATE.maxArea)  arr = arr.filter(l=> (l.area||0) <= parseFloat(LS_STATE.maxArea));
    if(LS_STATE.districts.size) arr = arr.filter(l=> LS_STATE.districts.has(l.district));
    if(LS_STATE.amenities.size){
      arr = arr.filter(l => Array.from(LS_STATE.amenities).every(a => (l.amenities||[]).includes(a)));
    }
    if(LS_STATE.sources.size) arr = arr.filter(l=> LS_STATE.sources.has(l.source));

    /* sort */
    if(LS_STATE.sort === "lowhi") arr.sort((a,b)=> a.price-b.price);
    else if(LS_STATE.sort === "hilo") arr.sort((a,b)=> b.price-a.price);
    else if(LS_STATE.sort === "m2") arr.sort((a,b)=> (b.area||0)-(a.area||0));
    else /* newest */ arr.sort((a,b)=> (b.isNew?1:0) - (a.isNew?1:0));

    return arr;
  }

  function renderListings(){
    if(!$(".js-listings")) return;
    const arr = filterListings();
    $("#resCount").innerHTML = `<b>${arr.length}</b> ${window.RR_t("lst.results")}`;

    /* pagination */
    const total = arr.length;
    const pages = Math.max(1, Math.ceil(total / LS_STATE.perPage));
    if(LS_STATE.page > pages) LS_STATE.page = 1;
    const start = (LS_STATE.page-1) * LS_STATE.perPage;
    const slice = arr.slice(start, start + LS_STATE.perPage);

    const grid = $("#resultsGrid");
    grid.classList.toggle("list-view", LS_STATE.view === "list");
    grid.classList.remove("cols-2");
    if(LS_STATE.view === "map") grid.classList.add("cols-2");
    grid.innerHTML = slice.map(cardHtml).join("") || `<div class="muted" style="padding:40px 0">No listings match your filters.</div>`;

    /* pager */
    const pager = $("#pager");
    if(pages <= 1){ pager.innerHTML = ""; }
    else {
      const items = [];
      for(let i=1;i<=pages;i++){
        items.push(`<button class="${i===LS_STATE.page?'active':''}" onclick="window.RR_gotoPage(${i})">${i}</button>`);
      }
      pager.innerHTML = items.join("");
    }

    /* map */
    if(LS_STATE.view === "map"){
      renderMap(arr);
    }
  }

  function renderMap(arr){
    const mp = $("#mapPane");
    if(!mp) return;
    mp.style.display = "block";
    /* Render a stylized SVG map of Riga with pins. No external API needed. */
    const w = mp.clientWidth || 600, h = 520;
    const lats = arr.map(l=>l.lat).filter(Boolean);
    const lngs = arr.map(l=>l.lng).filter(Boolean);
    const minLat = Math.min(...lats, 56.86), maxLat = Math.max(...lats, 57.05);
    const minLng = Math.min(...lngs, 23.98), maxLng = Math.max(...lngs, 24.30);
    const X = lng => ((lng - minLng)/(maxLng-minLng)) * (w-60) + 30;
    const Y = lat => h - 30 - ((lat - minLat)/(maxLat-minLat)) * (h-60);

    const pins = arr.map(l => {
      if(!l.lat) return "";
      const x = X(l.lng), y = Y(l.lat);
      return `
        <g transform="translate(${x},${y})" class="pin" style="cursor:pointer" onclick="location.href='listing.html?id=${l.id}'">
          <circle r="18" fill="#fff" stroke="#0d6b6b" stroke-width="2"></circle>
          <text y="4" text-anchor="middle" font-size="10" font-weight="700" fill="#0d6b6b">€${Math.round(l.price)}</text>
        </g>`;
    }).join("");

    mp.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background:linear-gradient(135deg,#e3eaf2,#cfd8e3)">
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(11,18,32,.06)" stroke-width="1"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)"/>
        <!-- River Daugava abstract -->
        <path d="M 0 ${h*0.7} Q ${w*0.3} ${h*0.5} ${w*0.5} ${h*0.6} T ${w} ${h*0.55}" stroke="#9ec5e0" stroke-width="36" fill="none" opacity=".55" stroke-linecap="round"/>
        <path d="M 0 ${h*0.7} Q ${w*0.3} ${h*0.5} ${w*0.5} ${h*0.6} T ${w} ${h*0.55}" stroke="#cfe1ee" stroke-width="22" fill="none" opacity=".9" stroke-linecap="round"/>
        <!-- Centre marker -->
        <text x="${w*0.5}" y="${h*0.35}" font-family="Inter" font-size="14" font-weight="700" fill="#0b1220" text-anchor="middle" opacity=".5">RIGA</text>
        ${pins}
      </svg>`;
  }

  function buildFilterUi(){
    /* District chips */
    const dWrap = $("#fDistricts");
    if(dWrap){
      dWrap.innerHTML = window.RR_DISTRICTS.map(d=>
        `<button type="button" class="chip" data-d="${d}">${d}</button>`
      ).join("");
      dWrap.addEventListener("click", e=>{
        if(e.target.matches(".chip")){
          const d = e.target.dataset.d;
          e.target.classList.toggle("active");
          if(LS_STATE.districts.has(d)) LS_STATE.districts.delete(d);
          else LS_STATE.districts.add(d);
          LS_STATE.page = 1; renderListings();
        }
      });
    }
    /* Amenities */
    const amWrap = $("#fAmenities");
    if(amWrap){
      const AM = ["furnished","balcony","parking","elevator","ac","internet","pets_ok","sauna","gym","fireplace","garden","terrace","historic"];
      amWrap.innerHTML = AM.map(a=>`
        <label class="check"><input type="checkbox" data-a="${a}"><span data-t="am.${a}">${a}</span></label>
      `).join("");
      amWrap.addEventListener("change", e=>{
        if(e.target.matches("input[type=checkbox]")){
          const a = e.target.dataset.a;
          if(e.target.checked) LS_STATE.amenities.add(a);
          else LS_STATE.amenities.delete(a);
          LS_STATE.page = 1; renderListings();
        }
      });
    }
    /* Source list */
    const sWrap = $("#fSources");
    if(sWrap){
      const used = Array.from(new Set(window.RR_LISTINGS.map(l=>l.source))).sort();
      sWrap.innerHTML = used.map(s=>`
        <label class="check"><input type="checkbox" data-s="${s}"><span>${s}</span></label>
      `).join("");
      sWrap.addEventListener("change", e=>{
        if(e.target.matches("input[type=checkbox]")){
          const s = e.target.dataset.s;
          if(e.target.checked) LS_STATE.sources.add(s);
          else LS_STATE.sources.delete(s);
          LS_STATE.page = 1; renderListings();
        }
      });
    }
    /* Type chips */
    const tWrap = $("#fTypeChips");
    if(tWrap){
      tWrap.addEventListener("click", e=>{
        if(e.target.matches(".chip")){
          $$(".chip", tWrap).forEach(c=>c.classList.remove("active"));
          e.target.classList.add("active");
          LS_STATE.type = e.target.dataset.type || "";
          LS_STATE.page = 1; renderListings();
        }
      });
      /* Pre-select from query */
      if(LS_STATE.type){
        const m = $(`.chip[data-type="${LS_STATE.type}"]`, tWrap);
        if(m){ $$(".chip", tWrap).forEach(c=>c.classList.remove("active")); m.classList.add("active"); }
      }
    }
    /* Room chips */
    const rWrap = $("#fRoomChips");
    if(rWrap){
      rWrap.addEventListener("click", e=>{
        if(e.target.matches(".chip")){
          const isActive = e.target.classList.contains("active");
          $$(".chip", rWrap).forEach(c=>c.classList.remove("active"));
          if(!isActive){ e.target.classList.add("active"); LS_STATE.rooms = e.target.dataset.r; }
          else LS_STATE.rooms = "";
          LS_STATE.page = 1; renderListings();
        }
      });
    }
    /* Price/Area inputs */
    ["minPrice","maxPrice","minArea","maxArea"].forEach(id=>{
      const el = $("#"+id);
      if(el){ el.addEventListener("input", ()=>{ LS_STATE[id] = el.value; LS_STATE.page = 1; renderListings(); }); }
    });
    /* Quick-bar type select mirrors chips */
    const tSel = $("#fTypeSel");
    if(tSel){
      tSel.value = LS_STATE.type || "";
      tSel.addEventListener("change", ()=>{
        LS_STATE.type = tSel.value;
        $$("#fTypeChips .chip").forEach(c=>c.classList.remove("active"));
        const m = $(`#fTypeChips .chip[data-type="${tSel.value}"]`);
        if(m) m.classList.add("active");
        LS_STATE.page = 1; renderListings();
      });
    }
    /* Search input */
    const q = $("#fQ");
    if(q){
      q.value = LS_STATE.q;
      q.addEventListener("input", ()=>{ LS_STATE.q = q.value; LS_STATE.page = 1; renderListings(); });
    }
    /* Sort */
    const so = $("#fSort");
    if(so) so.addEventListener("change", ()=>{ LS_STATE.sort = so.value; renderListings(); });
    /* View toggle */
    $$(".view-toggle button").forEach(b=>{
      b.addEventListener("click", ()=>{
        $$(".view-toggle button").forEach(x=>x.classList.remove("active"));
        b.classList.add("active");
        LS_STATE.view = b.dataset.v;
        $("#mapPane").style.display = LS_STATE.view === "map" ? "block" : "none";
        renderListings();
      });
    });
    /* Clear */
    const clr = $("#fClear");
    if(clr) clr.addEventListener("click", ()=>{
      LS_STATE = {q:"",type:"",rooms:"",maxPrice:"",minPrice:"",minArea:"",maxArea:"",
                 districts:new Set(),amenities:new Set(),sources:new Set(),
                 sort:"new",view:LS_STATE.view,page:1,perPage:9};
      $$(".chip.active").forEach(c=>c.classList.remove("active"));
      $$("#fAmenities input,#fSources input").forEach(c=>c.checked=false);
      ["#fQ","#minPrice","#maxPrice","#minArea","#maxArea"].forEach(s=>{const e=$(s);if(e)e.value="";});
      renderListings();
    });
  }

  window.RR_gotoPage = function(n){ LS_STATE.page = n; renderListings(); window.scrollTo({top:0,behavior:"smooth"}); };

  function initListingsPage(){
    if(!$(".js-listings")) return;
    readQuery();
    buildFilterUi();
    renderListings();
  }

  /* ---------- Listing detail ---------- */
  function initDetail(){
    if(!$(".js-detail")) return;
    const id = new URLSearchParams(location.search).get("id") || window.RR_LISTINGS[0].id;
    const L = window.RR_LISTINGS.find(x => x.id === id) || window.RR_LISTINGS[0];
    if(!L) return;

    document.title = `${L.title} — RentRiga`;

    /* Inject JSON-LD for SEO */
    const ld = {
      "@context":"https://schema.org",
      "@type":"Apartment",
      "name": L.title,
      "description": L.desc,
      "image": L.gallery || [L.img],
      "address":{"@type":"PostalAddress","streetAddress":L.street,"addressLocality":"Rīga","addressCountry":"LV"},
      "numberOfRooms": L.rooms,
      "floorSize":{"@type":"QuantitativeValue","value":L.area,"unitCode":"MTK"},
      "offers":{"@type":"Offer","price":L.price,"priceCurrency":L.currency || "EUR"}
    };
    const s = document.createElement("script");
    s.type = "application/ld+json"; s.textContent = JSON.stringify(ld);
    document.head.appendChild(s);

    /* Gallery */
    const g = L.gallery || [L.img,L.img,L.img,L.img,L.img];
    $("#galleryHost").innerHTML = `
      <div class="g g1"><img src="${g[0]||L.img}" alt=""></div>
      <div class="g"><img src="${g[1]||L.img}" alt=""></div>
      <div class="g"><img src="${g[2]||L.img}" alt=""></div>
      <div class="g"><img src="${g[3]||L.img}" alt=""></div>
      <div class="g"><img src="${g[4]||L.img}" alt="">
        <span class="more">+ ${Math.max(0,g.length-4)} more</span>
      </div>`;

    /* Header info */
    $("#dTitle").textContent = titleFor(L);
    $("#dCrumb").textContent = titleFor(L);
    $("#dLoc").textContent   = `${L.street}, ${L.district}, Rīga`;
    $("#dBadges").innerHTML  = badgeFor(L);
    $("#dPrice").innerHTML   = fmtPrice(L);
    $("#dPrice2").innerHTML  = fmtPrice(L);
    $("#dDesc").textContent  = L.desc;

    /* Key/value block */
    const kvs = [
      ["Rooms / Istabas / Комнат",  L.rooms || "—"],
      ["Area / Platība / Площадь",  L.area ? L.area + " m²" : "—"],
      ["Floor / Stāvs / Этаж",      L.floor || "—"],
      ["Year / Gads / Год",         L.year || "—"],
      ["Plot / Zeme / Участок",     L.plot ? L.plot + " m²" : "—"],
      ["District / Rajons / Район", L.district]
    ];
    $("#dKvs").innerHTML = kvs.map(([k,v])=>`<div class="kv"><small>${k}</small><b>${v}</b></div>`).join("");

    /* Amenities */
    $("#dAm").innerHTML = (L.amenities||[]).map(a=>
      `<span data-t="am.${a}">${window.RR_t("am."+a)}</span>`
    ).join("") || `<span class="muted">No amenities listed.</span>`;

    /* Source attribution */
    $("#dSourceName").textContent = L.source;
    $("#dSourceLink").href = L.sourceUrl;
    $("#dSourceLink2").href = L.sourceUrl;

    /* Mini-map */
    if(L.lat && $("#dMap")){
      const w = 700, h = 280;
      $("#dMap").innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"
             style="background:linear-gradient(135deg,#e3eaf2,#cfd8e3);border-radius:14px">
          <defs><pattern id="g2" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(11,18,32,.06)" stroke-width="1"/></pattern></defs>
          <rect width="100%" height="100%" fill="url(#g2)"/>
          <path d="M 0 ${h*0.7} Q ${w*0.3} ${h*0.5} ${w*0.5} ${h*0.6} T ${w} ${h*0.55}"
                stroke="#9ec5e0" stroke-width="40" fill="none" opacity=".55" stroke-linecap="round"/>
          <g transform="translate(${w/2},${h/2})">
            <circle r="22" fill="#0d6b6b" stroke="#fff" stroke-width="3"/>
            <text y="5" text-anchor="middle" font-size="14" font-weight="800" fill="#fff">📍</text>
          </g>
          <text x="${w/2}" y="${h/2+50}" text-anchor="middle" font-family="Inter" font-size="13" fill="#1f2a44">
            ${escapeHtml(L.street)}, ${escapeHtml(L.district)}
          </text>
        </svg>`;
    }

    /* Similar */
    const similar = window.RR_LISTINGS
      .filter(x => x.id !== L.id && x.type === L.type)
      .slice(0,3);
    $("#dSimilar").innerHTML = similar.map(cardHtml).join("");

    /* Contact form */
    $("#dForm").addEventListener("submit", e=>{
      e.preventDefault();
      $("#dForm").innerHTML = `<div style="padding:30px 10px;text-align:center;color:#0c6a44">
        <div style="font-size:34px">✓</div>
        <p style="font-weight:600">Enquiry sent. ${escapeHtml(L.source)} will reply to your email.</p></div>`;
    });
  }

  /* ---------- Re-render on language change ----------
     Only re-render data-driven views; don't rebuild UI that owns user state
     (filter chips/checkboxes) — i18n already updated their static labels. */
  window.RR_renderAll = function(){
    if($(".js-home")){
      const s = window.RR_STATS;
      $$(".js-stat-listings").forEach(e=> e.textContent = s.total);
      $$(".js-stat-sources").forEach(e=> e.textContent = s.sources);
      $$(".js-stat-districts").forEach(e=> e.textContent = s.districts);
      const fg = $("#featuredGrid");
      if(fg){
        const featured = window.RR_LISTINGS.filter(l => l.premium || l.verified).slice(0,6);
        fg.innerHTML = featured.map(cardHtml).join("");
      }
    }
    if($(".js-listings")) renderListings();
    if($(".js-detail")) {
      /* For detail page, re-render the dynamic text bits without re-injecting JSON-LD */
      const id = new URLSearchParams(location.search).get("id") || window.RR_LISTINGS[0].id;
      const L = window.RR_LISTINGS.find(x => x.id === id) || window.RR_LISTINGS[0];
      if(L){
        $("#dTitle").textContent = titleFor(L);
        $("#dCrumb").textContent = titleFor(L);
        $("#dPrice").innerHTML = fmtPrice(L);
        $("#dPrice2").innerHTML = fmtPrice(L);
        $("#dAm").innerHTML = (L.amenities||[]).map(a=>
          `<span>${window.RR_t("am."+a)}</span>`
        ).join("");
        /* re-render similar */
        const similar = window.RR_LISTINGS.filter(x => x.id !== L.id && x.type === L.type).slice(0,3);
        $("#dSimilar").innerHTML = similar.map(cardHtml).join("");
      }
    }
  };

  /* ---------- Boot ---------- */
  document.addEventListener("DOMContentLoaded", ()=>{
    initHeader();
    window.RR_applyI18n();
    initHome();
    initListingsPage();
    initDetail();
  });
})();
