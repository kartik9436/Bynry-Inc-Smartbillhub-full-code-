/* work-map.js — <work-map>: Leaflet + Esri street tiles for open work orders.
   Filters above; pin click → job card → Open details. */
(function () {
  var WOS = [
    { id:'WO-4821', type:'Disconnect · non-pay', premise:'1408 Elm St', pr:'High', tech:'D. Ortiz', due:'Today 14:00', status:'En route', ll:[30.2452,-97.7651] },
    { id:'WO-4822', type:'Meter exchange', premise:'221 Oak Ave', pr:'Normal', tech:'D. Ortiz', due:'Today 15:30', status:'Scheduled', ll:[30.2521,-97.7712] },
    { id:'WO-4823', type:'Leak investigation', premise:'77 Cedar Ct', pr:'High', tech:'Unassigned', due:'Today 17:00', status:'Queued', ll:[30.2782,-97.7081] },
    { id:'WO-4824', type:'Reconnect', premise:'903 Birch Ln', pr:'Urgent', tech:'M. Chen', due:'Today 12:00', status:'On site', ll:[30.2841,-97.7152] },
    { id:'WO-4825', type:'Read verification', premise:'14 Pine Row', pr:'Low', tech:'Unassigned', due:'Aug 18', status:'Queued', ll:[30.2262,-97.7422] },
    { id:'WO-4826', type:'Move-in activation', premise:'1408 Elm St · Unit C', pr:'Normal', tech:'R. Patel', due:'Aug 18', status:'Scheduled', ll:[30.2447,-97.7645] },
    { id:'WO-4827', type:'Backflow inspection', premise:'500 Commerce Pk', pr:'Normal', tech:'R. Patel', due:'Aug 19', status:'Scheduled', ll:[30.2192,-97.7261] },
    { id:'WO-4828', type:'Main repair', premise:'Elm St & 3rd', pr:'Urgent', tech:'Crew B', due:'Today', status:'On site', ll:[30.2492,-97.7622] },
    { id:'WO-4830', type:'Meter exchange', premise:'88 Willow', pr:'Normal', tech:'Unassigned', due:'Aug 19', status:'Queued', ll:[30.2911,-97.7021] },
    { id:'WO-4831', type:'Backflow test', premise:'500 Commerce Pk', pr:'Normal', tech:'Unassigned', due:'Aug 20', status:'Queued', ll:[30.2188,-97.7266] },
  ];
  var LCSS='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', LJS='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  function loadLeaflet(cb){ if(window.L) return cb();
    if(!document.querySelector('link[href="'+LCSS+'"]')){var l=document.createElement('link');l.rel='stylesheet';l.href=LCSS;document.head.appendChild(l);}
    var sc=document.querySelector('script[data-leaflet]');
    if(sc){ sc.addEventListener('load',cb); return; }
    sc=document.createElement('script'); sc.src=LJS; sc.setAttribute('data-leaflet','1'); sc.onload=cb; document.head.appendChild(sc); }
  var SEL='min-height:32px;padding:4px 26px 4px 8px;font-size:12px;border:1px solid rgba(32,30,29,.4);background:#eae9e9;font-family:inherit';
  class WorkMap extends HTMLElement {
    connectedCallback(){
      if(this.__done) return; this.__done=true;
      var el=this;
      el.innerHTML='<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">'
        +'<input data-f="q" placeholder="Search WO #, premise…" style="min-height:32px;padding:4px 10px;font-size:12px;border:1px solid rgba(32,30,29,.4);background:#eae9e9;font-family:inherit;width:200px">'
        +'<select data-f="type" style="'+SEL+'"><option value="">Type · all</option><option>Disconnect</option><option>Reconnect</option><option>Meter exchange</option><option>Leak</option><option>Backflow</option><option>Read verification</option><option>Move-in</option><option>Main repair</option></select>'
        +'<select data-f="status" style="'+SEL+'"><option value="">Status · all</option><option>Queued</option><option>Scheduled</option><option>En route</option><option>On site</option></select>'
        +'<select data-f="pr" style="'+SEL+'"><option value="">Priority · all</option><option>Urgent</option><option>High</option><option>Normal</option><option>Low</option></select>'
        +'<select data-f="tech" style="'+SEL+'"><option value="">Technician · all</option><option>Unassigned</option><option>D. Ortiz</option><option>M. Chen</option><option>R. Patel</option><option>Crew B</option></select>'
        +'<span data-count style="font-size:12px;opacity:.7;margin-left:auto"></span></div>'
        +'<div data-map style="height:520px;border:1px solid rgba(32,30,29,.4)"></div>'
        +'<div style="display:flex;gap:18px;font-size:11px;margin-top:8px;opacity:.85">'
        +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#201e1d;margin-right:5px"></span>Assigned &amp; scheduled</span>'
        +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ec3013;margin-right:5px"></span>Urgent / active now</span>'
        +'<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #ec3013;margin-right:5px"></span>Unassigned</span></div>';
      loadLeaflet(function(){
        var map=L.map(el.querySelector('[data-map]'),{scrollWheelZoom:true}).setView([30.256,-97.737],13);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',{attribution:'Tiles © Esri'}).addTo(map);
        var layer=L.layerGroup().addTo(map);
        function draw(){
          var q=(el.querySelector('[data-f=q]').value||'').toLowerCase();
          var ty=el.querySelector('[data-f=type]').value, st=el.querySelector('[data-f=status]').value;
          var pr=el.querySelector('[data-f=pr]').value, te=el.querySelector('[data-f=tech]').value;
          layer.clearLayers(); var n=0;
          WOS.forEach(function(w){
            if(q&&(w.id+w.type+w.premise+w.tech).toLowerCase().indexOf(q)<0) return;
            if(ty&&w.type.toLowerCase().indexOf(ty.toLowerCase())<0) return;
            if(st&&w.status!==st) return;
            if(pr&&w.pr!==pr) return;
            if(te&&w.tech!==te) return;
            n++;
            var un=w.tech==='Unassigned', hot=w.pr==='Urgent'||w.status==='On site'||w.status==='En route';
            var m=L.circleMarker(w.ll,{radius:8,color:'#ec3013',weight:un?3:2,fillColor:hot?'#ec3013':'#201e1d',fillOpacity:un?0:0.9,opacity:(un||hot)?1:0, fill:!un});
            if(!un&&!hot) m.setStyle({color:'#201e1d',opacity:1});
            m.addTo(layer);
            m.bindPopup('<div style="font-family:Archivo,sans-serif;min-width:200px">'
              +'<div style="font-weight:800;font-size:14px">'+w.id+' <span style="font-weight:400;font-size:11px;opacity:.7">'+w.pr+'</span></div>'
              +'<div style="font-size:12px;margin:4px 0">'+w.type+'</div>'
              +'<div style="font-size:11px;opacity:.75">'+w.premise+' · due '+w.due+'</div>'
              +'<div style="font-size:11px;margin:3px 0">'+w.status+' · '+w.tech+'</div>'
              +'<button onclick="window.__sbOpenWO&&window.__sbOpenWO(\''+w.id+'\')" style="margin-top:6px;width:100%;padding:6px;background:#ec3013;color:#f3f2f2;border:0;font-family:Archivo,sans-serif;font-weight:800;font-size:12px;cursor:pointer">Open details →</button></div>');
          });
          el.querySelector('[data-count]').textContent='Showing '+n+' of '+WOS.length+' open orders';
        }
        el.querySelectorAll('[data-f]').forEach(function(c){ c.addEventListener('input',draw); c.addEventListener('change',draw); });
        draw();
        setTimeout(function(){ map.invalidateSize(); },300);
      });
    }
  }
  if(!customElements.get('work-map')) customElements.define('work-map', WorkMap);
})();
