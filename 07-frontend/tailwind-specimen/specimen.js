/* ════════════════════════════════════════════════════════════════════════
 * CR-018 Phase 0 — PROOF THAT ALL 76 TOKENS CROSSED, BY RENDERING.
 *
 * Hard-won law 1: a config claiming a value is not the value. So nothing here
 * reads the @theme block. For every token there are two elements:
 *
 *   LEFT   painted by a TAILWIND UTILITY  (bg-accent-700, text-h2, p-4 …)
 *   RIGHT  painted by the LITERAL parsed out of tokens.css source text
 *
 * Both are read back with getComputedStyle, so the browser resolves both sides
 * — color-mix() resolves, em resolves, unitless line-height resolves. A token
 * PASSES only when the two computed values are equal.
 * ════════════════════════════════════════════════════════════════════════ */
import tokensSource from "../src/styles/tokens.css?raw";

/* ── tokens.css, parsed from source ─────────────────────────────────────── */
const LITERAL = {};
{
  const stripped = tokensSource.replace(/\/\*[\s\S]*?\*\//g, "");
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let m;
  while ((m = re.exec(stripped)) !== null) LITERAL[m[1]] = m[2].trim();
}

const C = (token, cls, prop, lit, extra = {}) => ({ token, cls, prop, lit, ...extra });

/* ⚠ THE TWIN GOES THROUGH A CUSTOM PROPERTY, EXACTLY AS THE UTILITY DOES —
 * `--p:<literal>; <prop>: var(--p)`. That is also how the app itself consumes
 * every token today (`background: var(--color-x)`), so both sides take the
 * identical code path. */
const via = (prop) => (v) => `--p:${v};${prop}:var(--p)`;
const pinned = (prop) => (v) => `font-size:15px;--p:${v};${prop}:var(--p)`;
const bgLit = via("background-color");

/* ⚠ AND THE TWO SIDES ARE COMPARED AS NUMBERS, NOT AS STRINGS.
 * Tailwind v4 compiles through Lightning CSS, which RESOLVES a static
 * `color-mix()` at build time: `color-mix(in srgb, #201e1d 40%, transparent)`
 * leaves the compiler as `rgba(32, 30, 29, .4)`, while the twin is resolved by
 * the browser and computes as `color(srgb 0.12549 0.117647 0.113725 / 0.4)`.
 * Same colour, two spellings — and a naive string compare called it a FAIL on
 * --color-divider and all three shadows while every channel matched to the
 * byte. So colours are canonicalised to 8-bit RGBA before comparing, and
 * box-shadow additionally drops Tailwind's four inert ring/inset layers
 * (`rgba(0,0,0,0) 0px 0px 0px 0px`), which carry no paint.
 * The comparison stays a RENDERING comparison — both numbers come out of
 * getComputedStyle in a real browser; only the spelling is normalised. */
function canonColor(t) {
  let m = /^color\(srgb\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)(?:\s*\/\s*([-\d.]+))?\)$/.exec(t);
  if (m) {
    const [r, g, b] = [1, 2, 3].map((i) => Math.round(parseFloat(m[i]) * 255));
    const a = m[4] === undefined ? 1 : parseFloat(m[4]);
    return `rgba(${r},${g},${b},${a.toFixed(3)})`;
  }
  m = /^rgba?\(([^)]*)\)$/.exec(t);
  if (m) {
    const p = m[1].split(/[,\s/]+/).filter(Boolean).map(parseFloat);
    const a = p.length > 3 ? p[3] : 1;
    return `rgba(${Math.round(p[0])},${Math.round(p[1])},${Math.round(p[2])},${a.toFixed(3)})`;
  }
  return t;
}

/** split on top-level commas — `rgb(1, 2, 3)` must stay one piece */
function topSplit(s) {
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

const canonLayer = (layer) =>
  layer.replace(/(color\(srgb[^)]*\)|rgba?\([^)]*\))/g, (t) => canonColor(t)).replace(/\s+/g, " ").trim();

function canon(prop, value) {
  if (value === undefined || value === null) return value;
  if (prop === "boxShadow") {
    return topSplit(value)
      .map(canonLayer)
      .filter((l) => !/^rgba\(0,0,0,0\.000\)( 0px)+$/.test(l))
      .join(" | ");
  }
  return canonLayer(value);
}

/* ── the 76, and how each one is proved ─────────────────────────────────
 * ⚠ EVERY CLASS NAME BELOW IS WRITTEN OUT IN FULL, and that is not a style
 * preference. Tailwind generates only the utilities its scanner can SEE in
 * source. The first draft of this file built them with `bg-${name}` and 55 of
 * the 76 reported FAIL with `rgba(0, 0, 0, 0)` — the theme was correct the
 * whole time and the classes had simply never been generated. That is this
 * page catching the exact failure a Phase 3 lane will hit the first time it
 * interpolates a class name, so it is recorded rather than quietly fixed.
 * ──────────────────────────────────────────────────────────────────── */
const CHECKS = [
  /* ══ 48 colours ══ */
  C("--color-bg", "bg-bg", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-surface", "bg-surface", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-text", "bg-text", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent", "bg-accent", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2", "bg-accent-2", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-divider", "bg-divider", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-100", "bg-neutral-100", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-200", "bg-neutral-200", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-300", "bg-neutral-300", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-400", "bg-neutral-400", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-500", "bg-neutral-500", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-600", "bg-neutral-600", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-700", "bg-neutral-700", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-800", "bg-neutral-800", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-neutral-900", "bg-neutral-900", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-100", "bg-accent-100", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-200", "bg-accent-200", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-300", "bg-accent-300", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-400", "bg-accent-400", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-500", "bg-accent-500", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-600", "bg-accent-600", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-700", "bg-accent-700", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-800", "bg-accent-800", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-900", "bg-accent-900", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-100", "bg-accent-2-100", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-200", "bg-accent-2-200", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-300", "bg-accent-2-300", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-400", "bg-accent-2-400", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-500", "bg-accent-2-500", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-600", "bg-accent-2-600", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-700", "bg-accent-2-700", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-800", "bg-accent-2-800", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-accent-2-900", "bg-accent-2-900", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-success-100", "bg-success-100", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-success-500", "bg-success-500", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-success-700", "bg-success-700", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-warning-100", "bg-warning-100", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-warning-500", "bg-warning-500", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-warning-700", "bg-warning-700", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-danger-100", "bg-danger-100", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-danger-500", "bg-danger-500", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-danger-700", "bg-danger-700", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-service-electric", "bg-service-electric", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-service-water", "bg-service-water", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-service-gas", "bg-service-gas", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-service-sewer", "bg-service-sewer", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-service-trash", "bg-service-trash", "backgroundColor", bgLit, { group: "colour" }),
  C("--color-service-broadband", "bg-service-broadband", "backgroundColor", bgLit, { group: "colour" }),

  /* ══ 2 typefaces ══ */
  C("--font-heading", "font-heading", "fontFamily", via("font-family"), { group: "typeface" }),
  C("--font-body", "font-body", "fontFamily", via("font-family"), { group: "typeface" }),

  /* ══ 9 type-scale sizes ══ */
  C("--text-body", "text-body", "fontSize", via("font-size"), { group: "type scale" }),
  C("--text-h1", "text-h1", "fontSize", via("font-size"), { group: "type scale" }),
  C("--text-h2", "text-h2", "fontSize", via("font-size"), { group: "type scale" }),
  C("--text-h3", "text-h3", "fontSize", via("font-size"), { group: "type scale" }),
  C("--text-h4", "text-h4", "fontSize", via("font-size"), { group: "type scale" }),
  C("--text-h5", "text-h5", "fontSize", via("font-size"), { group: "type scale" }),
  C("--text-h6", "text-h6", "fontSize", via("font-size"), { group: "type scale" }),
  C("--table-font-size", "text-table", "fontSize", via("font-size"), { group: "type scale", note: "derived alias --text-table" }),
  C("--table-header-font-size", "text-table-header", "fontSize", via("font-size"), { group: "type scale", note: "derived alias --text-table-header" }),

  /* ══ 4 rhythm tokens ══
     Both twins are pinned to 15px so a unitless line-height and an em tracking
     resolve against the same font-size on each side. */
  C("--line-height-body", "text-[15px] leading-body", "lineHeight", pinned("line-height"), { group: "rhythm", note: "derived alias --leading-body" }),
  C("--line-height-heading", "text-[15px] leading-heading", "lineHeight", pinned("line-height"), { group: "rhythm", note: "derived alias --leading-heading" }),
  C("--letter-spacing-heading", "text-[15px] tracking-heading", "letterSpacing", pinned("letter-spacing"), { group: "rhythm", note: "derived alias --tracking-heading" }),
  C("--font-heading-weight", "font-extrabold", "fontWeight", via("font-weight"), { group: "rhythm", note: "no key of its own — `font-heading` is taken by the family; proved against Tailwind's own font-extrabold" }),

  /* ══ 6 spacing — Tailwind's --spacing multiplier, no named keys ══ */
  C("--space-1", "p-1", "paddingTop", via("padding-top"), { group: "spacing", note: "Tailwind --spacing multiplier" }),
  C("--space-2", "p-2", "paddingTop", via("padding-top"), { group: "spacing", note: "Tailwind --spacing multiplier" }),
  C("--space-3", "p-3", "paddingTop", via("padding-top"), { group: "spacing", note: "Tailwind --spacing multiplier" }),
  C("--space-4", "p-4", "paddingTop", via("padding-top"), { group: "spacing", note: "Tailwind --spacing multiplier" }),
  C("--space-6", "p-6", "paddingTop", via("padding-top"), { group: "spacing", note: "Tailwind --spacing multiplier" }),
  C("--space-8", "p-8", "paddingTop", via("padding-top"), { group: "spacing", note: "Tailwind --spacing multiplier" }),

  /* ══ 3 radii ══ */
  C("--radius-sm", "rounded-sm", "borderTopLeftRadius", via("border-top-left-radius"), { group: "radius" }),
  C("--radius-md", "rounded-md", "borderTopLeftRadius", via("border-top-left-radius"), { group: "radius" }),
  C("--radius-lg", "rounded-lg", "borderTopLeftRadius", via("border-top-left-radius"), { group: "radius" }),

  /* ══ 3 elevations ══ */
  C("--shadow-sm", "shadow-sm", "boxShadow", via("box-shadow"), { group: "elevation", note: "Tailwind composes shadow-* with four inert ring/inset layers; those carry no paint and are dropped before comparing" }),
  C("--shadow-md", "shadow-md", "boxShadow", via("box-shadow"), { group: "elevation", note: "Tailwind composes shadow-* with four inert ring/inset layers; those carry no paint and are dropped before comparing" }),
  C("--shadow-lg", "shadow-lg", "boxShadow", via("box-shadow"), { group: "elevation", note: "Tailwind composes shadow-* with four inert ring/inset layers; those carry no paint and are dropped before comparing" }),

  /* ══ 1 measure ══ */
  C("--desc-measure", "max-w-measure", "maxWidth", via("max-width"), { group: "measure", note: "derived alias --container-measure" }),
];

/* ── the extra guards: things Tailwind's defaults must NOT be able to do ── */
const NEUTRALISED = [
  { cls: "bg-red-500", prop: "backgroundColor", why: "Tailwind's own palette — B14 never ratified a red-500" },
  { cls: "bg-blue-500", prop: "backgroundColor", why: "ditto" },
  { cls: "text-lg", prop: "fontSize", why: "18px on a table cell breaks B14 rule 20" },
  { cls: "text-base", prop: "fontSize", why: "16px on a button is a third size — B14 rule 5" },
  { cls: "text-xs", prop: "fontSize", why: "ditto" },
  { cls: "font-sans", prop: "fontFamily", why: "not our typeface" },
  { cls: "shadow-2xl", prop: "boxShadow", why: "a fourth elevation the system never ratified" },
];
const RADIUS_ZEROED = [
  "rounded-none", "rounded-xs", "rounded-sm", "rounded-md", "rounded-lg",
  "rounded-xl", "rounded-2xl", "rounded-3xl", "rounded-4xl",
];

/* ── render ─────────────────────────────────────────────────────────────── */
const app = document.getElementById("app");

function probe(cls, prop, inline) {
  const el = document.createElement("div");
  if (cls) el.className = cls;
  if (inline) el.setAttribute("style", inline);
  el.style.position = "absolute";
  el.style.left = "-9999px";
  el.style.width = "40px";
  el.style.height = "20px";
  document.body.appendChild(el);
  const v = getComputedStyle(el)[prop];
  el.remove();
  return v;
}

const results = [];
const byGroup = new Map();
for (const c of CHECKS) {
  const lit = LITERAL[c.token];
  const got = probe(c.cls, c.prop, null);
  const want = lit === undefined ? "«not in tokens.css»" : probe(null, c.prop, c.lit(lit));
  const ok = lit !== undefined && canon(c.prop, got) === canon(c.prop, want);
  const row = { ...c, lit, got, want, ok };
  results.push(row);
  if (!byGroup.has(c.group)) byGroup.set(c.group, []);
  byGroup.get(c.group).push(row);
}
const pass = results.filter((r) => r.ok).length;

const head = document.createElement("header");
head.className = "p-6 bg-surface border-b-2 border-divider";
head.innerHTML = `
  <div class="text-h6 font-heading tracking-[0.08em] uppercase text-accent-700">CR-018 · Phase 0</div>
  <h1 class="text-h2 font-heading">Tailwind theme vs <code>tokens.css</code></h1>
  <p class="text-body max-w-measure">Left of each pair is painted by a Tailwind utility. Right is painted by the
  literal parsed out of <code>tokens.css</code> source. Both are read back with <code>getComputedStyle</code> in
  this browser — nothing here reads the <code>@theme</code> block.</p>
  <p class="text-h4 font-heading">${pass} / ${results.length} tokens crossed with their value intact</p>`;
app.appendChild(head);

for (const [group, rows] of byGroup) {
  const sec = document.createElement("section");
  sec.className = "p-6";
  const h = document.createElement("h2");
  h.className = "text-h4 font-heading mb-3";
  h.textContent = `${group} — ${rows.filter((r) => r.ok).length}/${rows.length}`;
  sec.appendChild(h);

  const tbl = document.createElement("table");
  tbl.className = "w-full text-table border-collapse";
  tbl.innerHTML = `<thead><tr class="text-table-header uppercase tracking-[0.08em] text-left border-b-2 border-divider">
      <th class="p-2">token</th><th class="p-2">utility</th><th class="p-2">theme</th>
      <th class="p-2">tokens.css</th><th class="p-2">computed</th><th class="p-2">=</th></tr></thead>`;
  const tb = document.createElement("tbody");
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = "border-b border-divider";
    tr.setAttribute("data-token", r.token);
    tr.setAttribute("data-ok", String(r.ok));
    const pair =
      r.prop === "backgroundColor"
        ? `<td class="p-2"><span class="${r.cls} inline-block w-16 h-6 border border-divider"></span></td>
           <td class="p-2"><span class="inline-block w-16 h-6 border border-divider" style="background-color:${r.lit ?? "transparent"}"></span></td>`
        : `<td class="p-2"><span class="${r.cls}">Aa&nbsp;1,234.56</span></td>
           <td class="p-2"><code>${r.lit ?? "—"}</code></td>`;
    tr.innerHTML =
      `<td class="p-2"><code>${r.token}</code></td><td class="p-2"><code>${r.cls}</code></td>` +
      pair +
      `<td class="p-2"><code>${r.got}</code></td>
       <td class="p-2 font-heading ${r.ok ? "text-success-700" : "text-danger-700"}">${r.ok ? "PASS" : "FAIL"}</td>`;
    tb.appendChild(tr);
  }
  tbl.appendChild(tb);
  sec.appendChild(tbl);
  app.appendChild(sec);
}

/* ── SECOND PROOF: the variables @theme RE-EMITS ─────────────────────────
 * The tables above prove each UTILITY paints the right value. They do not
 * prove that the raw custom property `@theme` writes into :root still matches
 * tokens.css — two different claims with two different consumers:
 *   · the utility is what Phase 3's markup will use;
 *   · the raw variable is what the 40 existing stylesheets use, at 1,788 sites,
 *     and it is what must still be right the day tokens.css is deleted.
 * ⚠ THIS SECTION EXISTS BECAUSE THE RED PROOF FOUND THE GAP. Sabotaging
 * `--space-4: 16px → 17px` changed NOTHING above: `p-4` comes from Tailwind's
 * `--spacing` multiplier, not from our key, so the utility check walked
 * straight past a token that had drifted by a pixel. Hard-won law 7 — a guard
 * is proved by breaking it first, and this one only half-worked.
 *
 * ⚠ AND IT IS COMPARED BY USE, NOT BY SPELLING. The computed value of a CUSTOM
 * property is an unresolved token stream, so reading `--color-divider` back off
 * :root returns whatever the minifier wrote (`#201e1d66`) against tokens.css's
 * `color-mix(...)`, and `-.015em` against `-0.015em` — identical values, five
 * false FAILs. So each variable is USED, fed into the same real property its
 * utility drives, and the browser resolves both sides before they are read.
 * ──────────────────────────────────────────────────────────────────────── */
const rootRaw = getComputedStyle(document.documentElement);
const kebab = (p) => p.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
const varRows = CHECKS.map((c) => {
  const pin = c.prop === "lineHeight" || c.prop === "letterSpacing" ? "font-size:15px;" : "";
  const emitted = probe(null, c.prop, `${pin}${kebab(c.prop)}:var(${c.token})`);
  const want = LITERAL[c.token] === undefined ? "«not in tokens.css»" : probe(null, c.prop, c.lit(LITERAL[c.token]));
  return {
    token: c.token,
    raw: rootRaw.getPropertyValue(c.token).trim(),
    emitted,
    want,
    ok: LITERAL[c.token] !== undefined && canon(c.prop, emitted) === canon(c.prop, want),
  };
});
const varPass = varRows.filter((r) => r.ok).length;

const varSec = document.createElement("section");
varSec.className = "p-6";
varSec.innerHTML =
  `<h2 class="text-h4 font-heading mb-3">variables re-emitted by <code>@theme</code> — ${varPass}/${varRows.length}</h2>
   <p class="text-body max-w-measure">Every token, read off <code>:root</code> and then <em>used</em>, against the
   literal in <code>tokens.css</code>. This is what keeps the 1,788 existing <code>var(--token)</code> sites alive
   when <code>tokens.css</code> is finally deleted.</p>
   <table class="w-full text-table border-collapse"><thead><tr class="text-table-header uppercase tracking-[0.08em] text-left border-b-2 border-divider">
     <th class="p-2">token</th><th class="p-2">@theme wrote</th><th class="p-2">used → computed</th>
     <th class="p-2">tokens.css → computed</th><th class="p-2">=</th></tr></thead><tbody>` +
  varRows
    .map(
      (r) => `<tr class="border-b border-divider" data-var="${r.token}" data-ok="${r.ok}">
        <td class="p-2"><code>${r.token}</code></td><td class="p-2"><code>${r.raw || "«not emitted»"}</code></td>
        <td class="p-2"><code>${r.emitted}</code></td><td class="p-2"><code>${r.want}</code></td>
        <td class="p-2 font-heading ${r.ok ? "text-success-700" : "text-danger-700"}">${r.ok ? "PASS" : "FAIL"}</td></tr>`,
    )
    .join("") +
  `</tbody></table>`;
app.appendChild(varSec);

/* ── THIRD PROOF: Tailwind's defaults cannot smuggle in a value ─────────── */
const neutRows = [
  ...NEUTRALISED.map((n) => {
    const got = probe(n.cls, n.prop, null);
    const base = probe(null, n.prop, "");
    return { cls: n.cls, why: n.why, got, expect: `inert (= ${base})`, ok: got === base };
  }),
  ...RADIUS_ZEROED.map((c) => ({
    cls: c,
    why: "Modernist is square",
    got: probe(c, "borderTopLeftRadius", null),
    expect: "0px",
    ok: probe(c, "borderTopLeftRadius", null) === "0px",
  })),
  (() => {
    const got = probe("rounded-full", "borderTopLeftRadius", null);
    return {
      cls: "rounded-full",
      why: "LOAD-BEARING — the A12 service dots are circles; must NOT be zeroed",
      got,
      expect: "not 0px",
      ok: got !== "0px",
    };
  })(),
];
const neutPass = neutRows.filter((r) => r.ok).length;

const neut = document.createElement("section");
neut.className = "p-6";
neut.innerHTML =
  `<h2 class="text-h4 font-heading mb-3">defaults neutralised — ${neutPass}/${neutRows.length}</h2>
   <table class="w-full text-table border-collapse"><thead><tr class="text-table-header uppercase tracking-[0.08em] text-left border-b-2 border-divider">
     <th class="p-2">utility</th><th class="p-2">why</th><th class="p-2">expected</th>
     <th class="p-2">computed</th><th class="p-2">=</th></tr></thead><tbody>` +
  neutRows
    .map(
      (r) => `<tr class="border-b border-divider" data-neutralised="${r.cls}" data-ok="${r.ok}">
        <td class="p-2"><code>${r.cls}</code></td><td class="p-2">${r.why}</td>
        <td class="p-2"><code>${r.expect}</code></td><td class="p-2"><code>${r.got}</code></td>
        <td class="p-2 font-heading ${r.ok ? "text-success-700" : "text-danger-700"}">${r.ok ? "PASS" : "FAIL"}</td></tr>`,
    )
    .join("") +
  `</tbody></table>`;
app.appendChild(neut);

/* ── type specimen — the scale rendered, not tabulated ──────────────────── */
const spec = document.createElement("section");
spec.className = "p-6 bg-surface";
spec.innerHTML =
  `<h2 class="text-h4 font-heading mb-3">type specimen — every size, straight from the theme</h2>
   <p class="text-h1 font-heading">H1 · SMARTBillHub · 1,234.567890 kWh</p>
   <p class="text-h2 font-heading">H2 · SMARTBillHub · 1,234.567890 kWh</p>
   <p class="text-h3 font-heading">H3 · SMARTBillHub · 1,234.567890 kWh</p>
   <p class="text-h4 font-heading">H4 · SMARTBillHub · 1,234.567890 kWh</p>
   <p class="text-h5 font-heading">H5 · SMARTBillHub · 1,234.567890 kWh</p>
   <p class="text-h6 font-heading">H6 · SMARTBillHub · 1,234.567890 kWh</p>
   <p class="text-body max-w-measure">text-body · Descriptions cap at 80% of the content width — B14 rule 18 as
   amended (PO 2026-08-16, "make it 80%", "across the app"). This paragraph is capped by
   <code>max-w-measure</code>.</p>
   <p class="text-btn font-heading">text-btn · 14px — B14 rule 5 default tier</p>
   <p class="text-btn-sm font-heading">text-btn-sm · 12px — B14 rule 5 small tier</p>
   <p class="text-table">text-table · 13.5px — B14 rule 20</p>
   <p class="text-table-header uppercase tracking-[0.08em]">text-table-header · 12px</p>
   <p class="font-mono text-table">font-mono · 1234567890 — tokenised from two bare literals</p>
   <p class="text-body"><span class="inline-block w-2 h-2 bg-service-water rounded-full"></span>
   <span class="inline-block w-2 h-2 bg-service-gas rounded-full"></span>
   <span class="inline-block w-2 h-2 bg-service-trash rounded-full"></span>
   service dots — <code>rounded-full</code> survives on purpose while every other radius is 0</p>`;
app.appendChild(spec);

/* the machine-readable verdict verify.mjs reads */
window.__CR018 = {
  total: results.length,
  pass,
  fail: results.filter((r) => !r.ok).map((r) => ({ token: r.token, cls: r.cls, got: r.got, want: r.want, lit: r.lit })),
  vars: { total: varRows.length, pass: varPass, fail: varRows.filter((r) => !r.ok) },
  neutralised: { total: neutRows.length, pass: neutPass, fail: neutRows.filter((r) => !r.ok) },
  tokensInSource: Object.keys(LITERAL).length,
  covered: [...new Set(results.map((r) => r.token))].length,
  uncovered: Object.keys(LITERAL).filter((t) => !results.some((r) => r.token === t)),
};
document.body.setAttribute("data-ready", "1");
