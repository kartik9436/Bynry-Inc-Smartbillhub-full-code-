/* assets-map.js — <asset-map>: real Leaflet basemap (Esri World Street tiles),
   filter bar above the map, marker click → device card → Open details. */
(function () {
  var ASSETS = [
    { id:'M-4021', type:'Meter', role:'Standard', svc:'E', status:'Active', premise:'1408 Elm Street · Unit A', read:'42,864 · Aug 3', ll:[30.2452,-97.7651], wo:'' },
    { id:'M-4022', type:'Meter', role:'Standard', svc:'W', status:'Active', premise:'1408 Elm Street · Unit A', read:'1,204 · Aug 3', ll:[30.2455,-97.7648], wo:'' },
    { id:'M-4204', type:'Meter', role:'Standard', svc:'W', status:'Needs repair', premise:'500 Main Plaza · 200', read:'438,240 · Jul 3', ll:[30.2681,-97.7423], wo:'WO-4204' },
    { id:'M-4310', type:'Meter', role:'Standard', svc:'E', status:'Active', premise:'77 Industrial Way', read:'88,410 · Aug 3', ll:[30.2901,-97.7003], wo:'' },
    { id:'M-4108', type:'Meter', role:'Standard', svc:'E', status:'Idle · vacant', premise:'1408 Elm Street · Unit B', read:'8,412 · Jun 30', ll:[30.2449,-97.7654], wo:'' },
    { id:'M-MASTER-12', type:'Meter', role:'Master · 24 units', svc:'E', status:'Active', premise:'Vega Apts', read:'48,210 kWh · Jul', ll:[30.2603,-97.7602], wo:'' },
    { id:'M-MASTER-08', type:'Meter', role:'Master · 18 units', svc:'W', status:'Active', premise:'2200 Riverside', read:'1,204 kgal · Jul', ll:[30.2582,-97.7101], wo:'' },
    { id:'SM-8801', type:'Sub-meter', role:'Sub → M-MASTER-12', svc:'E', status:'Active', premise:'Vega Apts · Apt 102', read:'2,140 · Aug 3', ll:[30.2605,-97.7598], wo:'' },
    { id:'SM-8803', type:'Sub-meter', role:'Sub → M-MASTER-08', svc:'W', status:'Needs repair', premise:'2200 Riverside · 224', read:'88 · Jul 3', ll:[30.2585,-97.7098], wo:'WO-8803' },
    { id:'BF-3301', type:'Device', role:'Backflow preventer', svc:'W', status:'Test due', premise:'500 Main Plaza · 200', read:'Test overdue Jan 18', ll:[30.2678,-97.7428], wo:'WO-4831' },
    { id:'PV-1180', type:'Device', role:'Solar inverter · net', svc:'E', status:'Active', premise:'901 Hillside Ave', read:'Exported 412 kWh · Jul', ll:[30.2221,-97.7524], wo:'' },
    { id:'PV-1204', type:'Device', role:'Solar inverter · net', svc:'E', status:'Active', premise:'1200 Business Park', read:'Exported 1,884 kWh · Jul', ll:[30.3102,-97.7203], wo:'' },
    { id:'EV-2210', type:'Device', role:'EV charger', svc:'E', status:'Active', premise:'1200 Business Park · 12', read:'—', ll:[30.3098,-97.7208], wo:'' },
    { id:'M-5099', type:'Meter', role:'Standard', svc:'E', status:'Pending install', premise:'1408 Elm Street · Unit C', read:'Install Aug 18', ll:[30.2447,-97.7645], wo:'WO-4834' },
    { id:'M-4110', type:'Meter', role:'Common area', svc:'W', status:'Active', premise:'1408 Elm Street · common', read:'214 · Aug 3', ll:[30.2457,-97.7656], wo:'' },
  ];
  var AREAS = { North:[[30.24,-97.78],[30.28,-97.73]], East:[[30.25,-97.73],[30.30,-97.69]], South:[[30.21,-97.77],[30.25,-97.71]] };
  function areaOf(a) { var la=a.ll[0], ln=a.ll[1]; if (la>=30.28) return 'East'; if (la<30.24) return 'South'; return ln<-97.755?'North':(ln<-97.73?'North':'East'); }
  function attention(st){ return /repair|due|Pending/i.test(st); }

  var LCSS='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', LJS='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  function loadLeaflet(cb){ if(window.L) return cb();
    if(!document.querySelector('link[href="'+LCSS+'"]')){var l=document.createElement('link');l.rel='stylesheet';l.href=LCSS;document.head.appendChild(l);}
    var sc=document.querySelector('script[data-leaflet]');
    if(sc){ sc.addEventListener('load',cb); return; }
    sc=document.createElement('script'); sc.src=LJS; sc.setAttribute('data-leaflet','1'); sc.onload=cb; document.head.appendChild(sc); }

  var SEL='min-height:32px;padding:4px 26px 4px 8px;font-size:12px;border:1px solid rgba(32,30,29,.4);background:#eae9e9;font-family:inherit';
  class AssetMap extends HTMLElement {
    connectedCallback(){
      if(this.__done) return; this.__done=true;
      var el=this;
      el.innerHTML='<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">'
        +'<input data-f="q" placeholder="Search asset #, premise…" style="min-height:32px;padding:4px 10px;font-size:12px;border:1px solid rgba(32,30,29,.4);background:#eae9e9;font-family:inherit;width:220px">'
        +'<select data-f="type" style="'+SEL+'"><option value="">Type · all</option><option>Meter</option><option value="Master">Masters</option><option value="Sub">Sub-meters</option><option>Device</option></select>'
        +'<select data-f="status" style="'+SEL+'"><option value="">Status · all</option><option value="Active">Active</option><option value="attention">Needs attention</option><option value="Pending">Pending / idle</option></select>'
        +'<select data-f="svc" style="'+SEL+'"><option value="">Service · all</option><option value="E">Electric</option><option value="W">Water</option></select>'
        +'<select data-f="area" style="'+SEL+'"><option value="">Area · all</option><option>North</option><option>East</option><option>South</option></select>'
        +'<span data-count style="font-size:12px;opacity:.7;margin-left:auto"></span></div>'
        +'<div data-map style="height:520px;border:1px solid rgba(32,30,29,.4)"></div>'
        +'<div style="display:flex;gap:18px;font-size:11px;margin-top:8px;opacity:.85">'
        +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#201e1d;margin-right:5px"></span>Healthy</span>'
        +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ec3013;margin-right:5px"></span>Needs attention (repair, test due, pending)</span>'
        +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #ec3013;margin-right:5px"></span>Master meter</span></div>';
      loadLeaflet(function(){
        var map=L.map(el.querySelector('[data-map]'),{scrollWheelZoom:true}).setView([30.263,-97.74],13);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',{attribution:'Tiles © Esri'}).addTo(map);
        var layer=L.layerGroup().addTo(map);
        function draw(){
          var q=(el.querySelector('[data-f=q]').value||'').toLowerCase();
          var ty=el.querySelector('[data-f=type]').value, st=el.querySelector('[data-f=status]').value;
          var sv=el.querySelector('[data-f=svc]').value, ar=el.querySelector('[data-f=area]').value;
          layer.clearLayers(); var n=0;
          ASSETS.forEach(function(a){
            if(q && (a.id+a.premise+a.role).toLowerCase().indexOf(q)<0) return;
            if(ty==='Master'&&a.role.indexOf('Master')!==0) return;
            if(ty==='Sub'&&a.type!=='Sub-meter') return;
            if((ty==='Meter'||ty==='Device')&&a.type!==ty) return;
            if(st==='Active'&&a.status!=='Active') return;
            if(st==='attention'&&!attention(a.status)) return;
            if(st==='Pending'&&!/Pending|Idle/i.test(a.status)) return;
            if(sv&&a.svc!==sv) return;
            if(ar&&areaOf(a)!==ar) return;
            n++;
            var isMaster=a.role.indexOf('Master')===0, warn=attention(a.status);
            var m=L.circleMarker(a.ll,{radius:isMaster?10:7,color:warn?'#ec3013':'#201e1d',weight:isMaster?3:2,fillColor:warn?'#ec3013':'#201e1d',fillOpacity:isMaster?0.15:0.9}).addTo(layer);
            m.bindPopup('<div style="font-family:Archivo,sans-serif;min-width:210px">'
              +'<div style="font-weight:800;font-size:14px">'+a.id+' <span style="font-weight:400;font-size:11px;opacity:.7">'+a.role+'</span></div>'
              +'<div style="font-size:12px;margin:4px 0">'+a.premise+'</div>'
              +'<div style="font-size:11px;opacity:.75">Last read · '+a.read+'</div>'
              +'<div style="font-size:11px;margin:3px 0;color:'+(warn?'#ec3013':'#201e1d')+'">'+a.status+(a.wo?' · '+a.wo:'')+'</div>'
              +'<button onclick="window.__sbOpenAsset&&window.__sbOpenAsset(\''+a.id+'\')" style="margin-top:6px;width:100%;padding:6px;background:#ec3013;color:#f3f2f2;border:0;font-family:Archivo,sans-serif;font-weight:800;font-size:12px;cursor:pointer">Open details →</button></div>');
          });
          el.querySelector('[data-count]').textContent='Showing '+n+' of '+ASSETS.length+' assets';
        }
        el.querySelectorAll('[data-f]').forEach(function(c){ c.addEventListener('input',draw); c.addEventListener('change',draw); });
        draw();
        setTimeout(function(){ map.invalidateSize(); },300);
      });
    }
  }
  if(!customElements.get('asset-map')) customElements.define('asset-map', AssetMap);
})();
