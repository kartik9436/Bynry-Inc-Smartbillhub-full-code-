/* table-tools.js — makes every .lt list table functional:
   search, one "Filter ▾" dropdown (filter values + column show/hide + ↑↓ reorder),
   applied-filter chips, header sorting, and a live pagination footer.
   Survives re-renders via a MutationObserver that re-applies saved state. */
(function () {
  var STATES = new Map();
  var pop = null;

  function tKey(tbl) {
    var ths = tbl.tHead ? [].map.call(tbl.tHead.rows[0].cells, function (c) { return c.textContent.trim(); }).join('|') : '';
    var all = document.querySelectorAll('table.lt');
    var idx = [].indexOf.call(all, tbl);
    return ths + '#' + idx;
  }
  function getState(tbl) {
    var k = tKey(tbl);
    if (!STATES.has(k)) {
      var n = tbl.tHead ? tbl.tHead.rows[0].cells.length : 0;
      STATES.set(k, { order: Array.apply(null, Array(n)).map(function (_, i) { return i; }), hidden: {}, filters: {}, search: '', sort: null, pageSize: 50 });
    }
    return STATES.get(k);
  }
  function allRows(tbl) {
    var out = [];
    for (var i = 0; i < tbl.tBodies.length; i++) out = out.concat([].slice.call(tbl.tBodies[i].rows));
    return out;
  }
  function curPos(st, oi) { return st.order.indexOf(oi); }
  function cellVal(c) { return (c ? c.textContent : '').trim(); }
  function numVal(t) { var x = parseFloat(t.replace(/[$,%×]/g, '').replace(/,/g, '')); return isNaN(x) ? null : x; }

  function moveCol(tbl, from, to) {
    if (to < 0) return;
    var rows = [tbl.tHead.rows[0]].concat(allRows(tbl));
    if (to >= rows[0].cells.length) return;
    rows.forEach(function (r) {
      if (!r.cells[from] || !r.cells[to]) return;
      var c = r.cells[from];
      if (to < from) r.insertBefore(c, r.cells[to]);
      else r.insertBefore(c, r.cells[to].nextSibling);
    });
  }
  function applyOrder(tbl, st) {
    for (var p = 0; p < st.order.length; p++) {
      var rows0 = tbl.tHead.rows[0];
      var cur = -1;
      for (var c = 0; c < rows0.cells.length; c++) if (+rows0.cells[c].getAttribute('data-oi') === st.order[p]) { cur = c; break; }
      if (cur >= 0 && cur !== p) moveCol(tbl, cur, p);
    }
  }
  function applyHidden(tbl, st) {
    var head = tbl.tHead.rows[0];
    for (var p = 0; p < head.cells.length; p++) {
      var oi = +head.cells[p].getAttribute('data-oi');
      var hide = !!st.hidden[oi];
      head.cells[p].style.display = hide ? 'none' : '';
      allRows(tbl).forEach(function (r) { if (r.cells[p]) r.cells[p].style.display = hide ? 'none' : ''; });
    }
  }
  function applySort(tbl, st) {
    if (!st.sort) return;
    var p = curPos(st, st.sort.oi);
    if (p < 0) return;
    var body = tbl.tBodies[0];
    var rows = [].slice.call(body.rows);
    rows.sort(function (a, b) {
      var ta = cellVal(a.cells[p]), tb = cellVal(b.cells[p]);
      var na = numVal(ta), nb = numVal(tb);
      var r = (na !== null && nb !== null) ? na - nb : ta.localeCompare(tb);
      return st.sort.dir === 'asc' ? r : -r;
    });
    rows.forEach(function (r) { body.appendChild(r); });
    [].forEach.call(tbl.tHead.rows[0].cells, function (c) { c.removeAttribute('data-dir'); });
    tbl.tHead.rows[0].cells[p] && tbl.tHead.rows[0].cells[p].setAttribute('data-dir', st.sort.dir);
  }
  function applyVisibility(tbl, st) {
    var rows = allRows(tbl);
    var shown = 0, total = 0;
    rows.forEach(function (r) {
      var ok = true;
      if (st.search) ok = r.textContent.toLowerCase().indexOf(st.search.toLowerCase()) >= 0;
      if (ok) Object.keys(st.filters).forEach(function (oi) {
        var set = st.filters[oi];
        if (set && set.length) {
          var p = curPos(st, +oi);
          if (set.indexOf(cellVal(r.cells[p])) < 0) ok = false;
        }
      });
      total++;
      if (ok && shown < st.pageSize) { r.style.display = ''; shown++; }
      else if (ok) { r.style.display = 'none'; shown++; }
      else r.style.display = 'none';
    });
    var matched = rows.filter(function (r) {
      var ok = true;
      if (st.search) ok = r.textContent.toLowerCase().indexOf(st.search.toLowerCase()) >= 0;
      if (ok) Object.keys(st.filters).forEach(function (oi) {
        var set = st.filters[oi];
        if (set && set.length) { var p = curPos(st, +oi); if (set.indexOf(cellVal(r.cells[p])) < 0) ok = false; }
      });
      return ok;
    }).length;
    var pg = tbl.nextElementSibling;
    if (pg && pg.classList.contains('pgbar')) {
      var label = pg.querySelector('span');
      if (label) label.textContent = 'Showing 1–' + Math.min(matched, st.pageSize) + ' of ' + matched + (matched !== total ? ' (filtered from ' + total + ')' : '');
      var pageInfo = pg.querySelector('.pgnav span');
      if (pageInfo) pageInfo.textContent = 'Page 1 of ' + Math.max(1, Math.ceil(matched / st.pageSize));
    }
  }
  function applyAll(tbl, st) { applyOrder(tbl, st); applyHidden(tbl, st); applySort(tbl, st); applyVisibility(tbl, st); renderChips(tbl, st); }

  function findToolbar(tbl) {
    var n = tbl.previousElementSibling;
    for (var i = 0; i < 6 && n; i++) { if (n.classList && n.classList.contains('toolbar')) return n; n = n.previousElementSibling; }
    var p = tbl.parentElement;
    if (p) { n = p.previousElementSibling; for (i = 0; i < 6 && n; i++) { if (n.classList && n.classList.contains('toolbar')) return n; n = n.previousElementSibling; } }
    return null;
  }
  function renderChips(tbl, st) {
    var bar = tbl.__fbar;
    if (!bar) return;
    [].slice.call(bar.querySelectorAll('.tt-chip')).forEach(function (c) { c.remove(); });
    var allChip = bar.querySelector('.fchip');
    var any = false;
    Object.keys(st.filters).forEach(function (oi) {
      (st.filters[oi] || []).forEach(function (v) {
        any = true;
        var chip = document.createElement('span');
        chip.className = 'fchip tt-chip';
        chip.innerHTML = tbl.__cols[oi] + ': ' + v + ' <span class="x">×</span>';
        chip.onclick = function () { st.filters[oi] = st.filters[oi].filter(function (x) { return x !== v; }); applyAll(tbl, st); };
        bar.insertBefore(chip, bar.querySelector('.tt-filter-btn'));
      });
    });
    if (allChip) allChip.classList.toggle('active', !any && !st.search);
  }
  function closePop() { if (pop) { pop.remove(); pop = null; } }
  document.addEventListener('click', function (e) { if (pop && !pop.contains(e.target) && !(e.target.closest && e.target.closest('.tt-filter-btn'))) closePop(); }, true);

  function openPop(btn, tbl, st, mode) {
    closePop();
    pop = document.createElement('div');
    pop.className = 'tt-pop';
    var r = btn.getBoundingClientRect();
    pop.style.cssText = 'position:fixed;top:' + (r.bottom + 6) + 'px;left:' + Math.max(8, Math.min(r.left, innerWidth - 340)) + 'px;z-index:9999;width:320px;max-height:70vh;overflow:auto;background:var(--color-bg,#f3f2f2);border:2px solid #201e1d;box-shadow:0 12px 32px rgba(45,43,43,.22);padding:14px;font-size:12px';
    var head = tbl.tHead.rows[0];
    if (mode === 'filters') {
    var h1 = document.createElement('div'); h1.className = 'tt-h'; h1.textContent = 'FILTER BY'; pop.appendChild(h1);
    var rows = allRows(tbl);
    var anyFilter = false;
    for (var p = 0; p < head.cells.length; p++) {
      (function (p, oi) {
      if (st.hidden[oi]) return;
      var vals = {};
      rows.forEach(function (row) { var v = cellVal(row.cells[p]); if (v && v.length < 28) vals[v] = 1; });
      var keys = Object.keys(vals);
      if (keys.length < 2 || keys.length > 8) return;
      anyFilter = true;
      var g = document.createElement('div'); g.className = 'tt-g';
      var gt = document.createElement('div'); gt.className = 'tt-gt'; gt.textContent = tbl.__cols[oi]; g.appendChild(gt);
      keys.forEach(function (v) {
        var lb = document.createElement('label'); lb.className = 'tt-row';
        var cb = document.createElement('input'); cb.type = 'checkbox';
        cb.checked = (st.filters[oi] || []).indexOf(v) >= 0;
        cb.onchange = function () {
          st.filters[oi] = st.filters[oi] || [];
          if (cb.checked) st.filters[oi].push(v); else st.filters[oi] = st.filters[oi].filter(function (x) { return x !== v; });
          applyAll(tbl, st);
        };
        lb.appendChild(cb); lb.appendChild(document.createTextNode(' ' + v));
        g.appendChild(lb);
      });
      pop.appendChild(g);
      })(p, +head.cells[p].getAttribute('data-oi'));
    } if (!anyFilter) { var none = document.createElement('div'); none.style.cssText = 'opacity:.6;padding:4px 0 10px'; none.textContent = 'No filterable columns on this table.'; pop.appendChild(none); }
    }
    if (mode === 'columns') {
    var h2 = document.createElement('div'); h2.className = 'tt-h'; h2.textContent = 'COLUMNS · show / hide · ↑↓ reorder'; pop.appendChild(h2);
    st.order.forEach(function (oi, p2) {
      var rw = document.createElement('div'); rw.className = 'tt-row tt-col';
      var cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = !st.hidden[oi];
      cb.onchange = function () { st.hidden[oi] = !cb.checked; applyAll(tbl, st); };
      var nm = document.createElement('span'); nm.style.flex = '1'; nm.textContent = tbl.__cols[oi] || '(actions)';
      var up = document.createElement('button'); up.className = 'tt-ud'; up.textContent = '↑'; up.title = 'Move up';
      var dn = document.createElement('button'); dn.className = 'tt-ud'; dn.textContent = '↓'; dn.title = 'Move down';
      up.onclick = function () { if (p2 > 0) { moveCol(tbl, p2, p2 - 1); var t = st.order[p2 - 1]; st.order[p2 - 1] = st.order[p2]; st.order[p2] = t; openPop(btn, tbl, st, mode); applyVisibility(tbl, st); } };
      dn.onclick = function () { if (p2 < st.order.length - 1) { moveCol(tbl, p2, p2 + 1); var t = st.order[p2 + 1]; st.order[p2 + 1] = st.order[p2]; st.order[p2] = t; openPop(btn, tbl, st, mode); applyVisibility(tbl, st); } };
      rw.appendChild(cb); rw.appendChild(nm); rw.appendChild(up); rw.appendChild(dn);
      pop.appendChild(rw);
    });
    }
    var reset = document.createElement('button'); reset.className = 'tt-reset'; reset.textContent = 'Reset table';
    reset.onclick = function () { STATES.delete(tKey(tbl)); location.hash = location.hash; closePop(); window.__ttEnhanceSoon(); };
    pop.appendChild(reset);
    document.body.appendChild(pop);
  }

  function enhance(tbl) {
    if (tbl.__enh || !tbl.tHead || !tbl.tBodies.length) return;
    tbl.__enh = true;
    var st = getState(tbl);
    var head = tbl.tHead.rows[0];
    if (st.order.length !== head.cells.length) { st.order = Array.apply(null, Array(head.cells.length)).map(function (_, i) { return i; }); st.hidden = {}; st.filters = {}; }
    tbl.__cols = {};
    var pre = (tbl.tHead.getAttribute('data-hidecols') || '').split(',').filter(Boolean);
    for (var i = 0; i < head.cells.length; i++) {
      head.cells[i].setAttribute('data-oi', i);
      tbl.__cols[i] = head.cells[i].textContent.trim() || '(actions)';
      if (pre.length && !tbl.__preApplied && pre.indexOf(tbl.__cols[i]) >= 0 && st.hidden[i] === undefined) st.hidden[i] = true;
      (function (cell) {
        cell.addEventListener('click', function () {
          var oi = +cell.getAttribute('data-oi');
          if (st.sort && st.sort.oi === oi) { if (st.sort.dir === 'asc') st.sort.dir = 'desc'; else st.sort = null; }
          else st.sort = { oi: oi, dir: 'asc' };
          if (!st.sort) { [].forEach.call(head.cells, function (c) { c.removeAttribute('data-dir'); }); } 
          applySort(tbl, st); applyVisibility(tbl, st);
        });
      })(head.cells[i]);
    }
    var toolbar = findToolbar(tbl);
    if (toolbar) {
      var search = toolbar.querySelector('input.input');
      if (search) { search.value = st.search; search.addEventListener('input', function () { st.search = search.value; applyAll(tbl, st); }); }
      var bar = toolbar.querySelector('.fbar') || toolbar;
      tbl.__fbar = bar;
      var fbtn = null, cbtn = null;
      [].slice.call(bar.querySelectorAll('button')).forEach(function (b) { if (/\+ Filter/.test(b.textContent)) fbtn = b; if (/^Choose columns/.test(b.title || '')) cbtn = b; });
      if (fbtn) {
        fbtn.classList.add('tt-filter-btn');
        fbtn.textContent = '+ Filter ▾';
        fbtn.addEventListener('click', function (e) { e.stopPropagation(); if (pop) closePop(); else openPop(fbtn, tbl, st, 'filters'); });
      }
      if (cbtn) {
        cbtn.classList.add('tt-filter-btn');
        cbtn.addEventListener('click', function (e) { e.stopPropagation(); if (pop) closePop(); else openPop(cbtn, tbl, st, 'columns'); });
      }
      var allChip = bar.querySelector('.fchip');
      if (allChip) allChip.addEventListener('click', function () { st.filters = {}; st.search = ''; if (search) search.value = ''; applyAll(tbl, st); });
    }
    var pg = tbl.nextElementSibling;
    if (pg && pg.classList.contains('pgbar')) {
      var sel = pg.querySelector('select');
      if (sel) { sel.value = String(st.pageSize); sel.addEventListener('change', function () { st.pageSize = +sel.value; applyVisibility(tbl, st); }); }
    }
    applyAll(tbl, st);
  }

  var timer = null;
  function enhanceAll() { [].slice.call(document.querySelectorAll('table.lt')).forEach(enhance); }
  window.__ttEnhanceSoon = function () { clearTimeout(timer); timer = setTimeout(enhanceAll, 250); };
  var css = document.createElement('style');
  css.textContent = '.tt-pop .tt-h{font-family:var(--font-heading);font-weight:800;font-size:10px;letter-spacing:.08em;margin:10px 0 6px;border-bottom:2px solid #201e1d;padding-bottom:4px}.tt-pop .tt-h:first-child{margin-top:0}.tt-pop .tt-gt{font-weight:700;margin:6px 0 2px;opacity:.75}.tt-pop .tt-row{display:flex;align-items:center;gap:8px;padding:3px 0;cursor:pointer}.tt-pop .tt-ud{border:1px solid rgba(32,30,29,.4);background:transparent;cursor:pointer;width:22px;height:22px;font-size:11px}.tt-pop .tt-ud:hover{background:rgba(32,30,29,.08)}.tt-pop .tt-reset{margin-top:12px;width:100%;border:1px solid rgba(32,30,29,.4);background:transparent;padding:6px;cursor:pointer;font-family:var(--font-heading);font-weight:800;font-size:11px}.lt thead th[data-dir="asc"]::after{content:" ▲" !important;opacity:1 !important}.lt thead th[data-dir="desc"]::after{content:" ▼" !important;opacity:1 !important}';
  document.head.appendChild(css);
  new MutationObserver(function () { window.__ttEnhanceSoon(); }).observe(document.body, { childList: true, subtree: true });
  window.__ttEnhanceSoon();
})();
