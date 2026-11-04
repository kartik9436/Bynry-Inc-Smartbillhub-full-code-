// ── Trace ──────────────────────────────────────────────
// Ask:      Portal accessibility, Group A (contrast, F-01 and F-09) — decision
//           log 2026-10-23, "the new colours confirmed". The tester's working
//           rule: *"list every similar place before changing anything"*.
// Results:  08-qa/a11y-portal-2026-10/group-a-inventory.md
// ───────────────────────────────────────────────────────
/**
 * portal_contrast_scan — READ-ONLY. Measures colour contrast on every
 * customer-portal page, and lists every grey in the code the portal mounts.
 * It changes no product file and no colour; the "approved colours" pass is a
 * stylesheet injected into the browser and nothing else.
 *
 * TWO MODES
 *
 *   node 10-scripts/a11y/portal_contrast_scan.mjs --code  [--json out.json]
 *       Static inventory. Walks the import graph from src/portal (so shared
 *       components the portal mounts are included, and staff-only files are
 *       not), and lists every text-/border-/placeholder-/fill-/stroke-/ring-/
 *       outline-/divide-/bg-neutral-300..600, every var(--color-neutral-*) in
 *       CSS and the four hard-coded hexes, classified by use, with the ratio
 *       today and after the approved colours.
 *
 *   node 10-scripts/a11y/portal_contrast_scan.mjs [--simulate] [--brand=#hex]
 *        [--langs=en,es] [--auth=out,in] [--states] [--out=<dir>]
 *        [--only=/bills,/bills/:number] [--json=<file>]
 *       --only takes ROUTE patterns as `portalRoutes.tsx` spells them.
 *       --out writes a full-page screenshot per page; --json the results
 *       (default ./portal-contrast-<base|sim>[-<brand>].json).
 *       Browser scan with axe-core's `color-contrast` rule on every route in
 *       `portalRoutes.tsx`, plus the checks axe does not make: placeholder
 *       text, field borders (3:1), the keyboard focus ring (3:1), chart text
 *       in SVG, meaningful icons (3:1), and the brand colour on its fills.
 *       --states adds hover, focus, expanded/pressed/selected and the errors
 *       an EMPTY submit draws. --simulate injects the approved colours.
 *
 * SET-UP (fake data only — the Pine Hill / Oak Ridge portal fixture):
 *
 *     createdb sbh_<lane>; DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \
 *       python manage.py migrate && python manage.py seed_portal_demo
 *     DATABASE_URL=… ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8099 --noreload
 *     # ⚠ `--mode walk`, NOT a bare build: a bare build is `production` and
 *     # bakes in the PRODUCTION API origin, so every page draws "We could not
 *     # open this page" and scans clean. Any mode with no `.env.<mode>` serves
 *     # the API from the same origin.
 *     cd 07-frontend && npx vite build --mode walk && \
 *       STATIC_DIR=$PWD/dist PORT=4299 API_PROXY_TARGET=http://127.0.0.1:8099 node server.mjs
 *     npm install --prefix <scratch> --no-save axe-core@4.10.3      # PINNED
 *     AXE_PATH=<scratch>/node_modules/axe-core/axe.min.js \
 *       PORTAL_LOGIN=<seeded login> node 10-scripts/a11y/portal_contrast_scan.mjs --states
 *
 *   The seeded login is in `portal_credential` (on 2026-10-23 it was
 *   `alvarez0@example.invalid`, password `Sample-Portal-2026!` — fake). A
 *   full run (53 pages × 2 × 2) takes about 25 minutes; --states about 30
 *   minutes in English. ⚠ `seed_portal_demo` stopped part-way on 2026-10-23
 *   (VAL-001 base_charge_code_required in seed_priced_addresses), after the
 *   bills were planted and before the usage readings, so the usage chart
 *   draws nothing on that fixture.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY (hard-won law 7):
 *   * a signed-in pass that is really signed out — every screen draws "you're
 *     signed out" and scans clean. The run prints the signed-in check and
 *     REFUSES to continue when the sign-in did not take.
 *   * a Spanish pass that is still English — the language is set through the
 *     app's own i18n handle and `i18n.language` is read back per page.
 *   * a page that never rendered — every page records its `data-screen` id
 *     and word count; a blank page is listed, not counted as clean.
 *   * axe's own blind spots — `incomplete` nodes (gradients, overlaps) are
 *     COUNTED and printed beside the violations, never dropped; placeholder
 *     text and SVG text are measured by this script because axe skips them.
 *   * `networkidle` — the portal holds a connection open; never wait for it.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const FRONTEND = join(REPO, "07-frontend");
const SRC = join(FRONTEND, "src");
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, v] = a.replace(/^--/, "").split("=");
    return [k, v ?? true];
  }),
);

// ── colour maths (WCAG 2.1 relative luminance) ────────────────────────────
function hexToRgb(h) {
  h = h.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
function lum([r, g, b]) {
  const f = (c) => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
export function ratio(a, b) {
  const [x, y] = [lum(hexToRgb(a)), lum(hexToRgb(b))].sort((p, q) => q - p);
  return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100;
}

//: The greys AS THE TREE HOLDS THEM, read from tokens.css — never a copy typed
//: here, or a re-run after the colour change would report the old ratios as
//: "today" (hard-won law 12's shape for pointers). The values before the
//: Group A change were 300 #d7d3d3 · 400 #bab6b6 · 500 #9b9797 · 600 #7d7979.
const TOKENS = readFileSync(join(SRC, "styles/tokens.css"), "utf8");
const GREY = Object.fromEntries(
  ["300", "400", "500", "600"].map((n) => [n, (TOKENS.match(new RegExp(`--color-neutral-${n}:\\s*(#[0-9a-fA-F]{6})`)) || [])[1]]),
);
if (Object.values(GREY).some((v) => !v)) throw new Error("could not read --color-neutral-300..600 from tokens.css — the shape moved");
const APPROVED = { text600: "#6b6767", text500: "#6b6767", fieldBorder: "#8c8888" };
const WHITE = "#ffffff";
const BG = "#f3f2f2";

// ══════════════════════════════════════════════════════════════════════════
// MODE 1 — the code inventory
// ══════════════════════════════════════════════════════════════════════════
function portalClosure() {
  const files = new Set();
  const walk = (d) => {
    for (const n of readdirSync(d)) {
      const p = join(d, n);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(tsx?|css)$/.test(n) && !/\.test\.|\.spec\./.test(n)) files.add(p);
    }
  };
  walk(join(SRC, "portal"));
  const queue = [...files];
  const tryResolve = (base) => {
    for (const ext of ["", ".tsx", ".ts", "/index.tsx", "/index.ts"]) {
      const p = base + ext;
      if (existsSync(p) && statSync(p).isFile()) return p;
    }
    return null;
  };
  // ⚠ FOLLOW ONLY WHAT IS MOUNTED. A plain import closure pulls in the staff
  // app: `regional.tsx` imports one helper from `ShellWithSession`, which
  // imports `AppShell`, and the closure then "finds" staff greys that never
  // render in the portal. So an import is followed out of `src/portal` only
  // when it brings in a capitalised name that the importing file renders as
  // JSX (`<Name`), or a stylesheet. Inside `src/portal` everything counts.
  const mounts = (text, clause) => {
    if (!clause) return true; // side-effect import (CSS)
    if (/^\s*type\b/.test(clause)) return false;
    const names = clause
      .replace(/[{}]/g, " ")
      .split(",")
      .map((s) => s.trim().replace(/^type\s+/, "").split(/\s+as\s+/).pop().trim())
      .filter(Boolean);
    return names.some((n) => /^[A-Z][A-Za-z0-9_]*$/.test(n) && new RegExp(`<${n}[\\s/>.]`).test(text));
  };
  while (queue.length) {
    const f = queue.pop();
    if (f.endsWith(".css")) continue;
    const text = readFileSync(f, "utf8");
    for (const m of text.matchAll(/^import\s+(?:([^;"']*?)\s+from\s+)?["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']/gm)) {
      let spec = m[2] ?? m[3];
      const insidePortal = f.startsWith(join(SRC, "portal"));
      if (!m[3] && !spec.endsWith(".css") && !mounts(text, m[1]) && !(insidePortal && spec.startsWith("."))) continue;
      let base;
      if (spec.startsWith("@/")) base = join(SRC, spec.slice(2));
      else if (spec.startsWith(".")) base = resolve(dirname(f), spec);
      else continue;
      const hit = tryResolve(base);
      if (hit && hit.startsWith(SRC) && !/\.test\.|\.spec\./.test(hit) && !files.has(hit)) {
        files.add(hit);
        queue.push(hit);
      }
    }
  }
  // The app-wide stylesheets are mounted on every portal page too.
  for (const css of ["styles/global.css", "styles/tokens.css", "styles/tailwind.css"]) files.add(join(SRC, css));
  return [...files].sort();
}

const CLASS_RE =
  /(?<![\w\-[])((?:[a-z0-9\-[\]&>*:]+:)*)(text|border(?:-[trblxyse])?|placeholder|fill|stroke|ring(?:-offset)?|outline|divide(?:-[xy])?|bg|decoration|caret|accent)-neutral-(300|400|500|600)(?:\/(\d+))?(?![\w-])/g;
const VAR_RE = /var\(--color-neutral-(300|400|500|600)\)/g;
const HEX_RE = /#(7d7979|7f7d7d|9b9797|d7d3d3)\b/gi;

function isComment(line) {
  const t = line.trim();
  return t.startsWith("//") || t.startsWith("*") || t.startsWith("/*") || t.startsWith("{/*");
}

function blend(fg, alphaPct, bg) {
  const a = alphaPct / 100;
  const [f, b] = [hexToRgb(fg), hexToRgb(bg)];
  return "#" + f.map((c, i) => Math.round(c * a + b[i] * (1 - a)).toString(16).padStart(2, "0")).join("");
}

//: Hand rulings where the line alone cannot say what a grey is FOR — each one
//: read in the source on 2026-10-23. Keyed by file and a snippet of the line,
//: never by line number, so an edit above it does not move the ruling.
const OVERRIDES = [
  ["portal/components/primitives.tsx", "w-full min-h-9 border border-neutral-300", "border", "input or select border"],
  ["portal/components/primitives.tsx", "shrink-0 border border-neutral-300 bg-[white] px-3 text-base font-semibold text-accent", "border", "control border (button joined to a field)"],
  ["portal/components/primitives.tsx", "\"border border-accent\" : \"border border-neutral-300\"", "border", "input or select border"],
  ["portal/components/primitives.tsx", "border border-neutral-300 bg-[white] px-3 py-2 text-body text-neutral-900", "border", "input or select border"],
  ["portal/components/primitives.tsx", "future: \"border-neutral-300 text-neutral-300\"", "border", "step marker (future step)"],
  ["portal/components/primitives.tsx", "border border-neutral-300 bg-neutral-100 px-3 text-body text-neutral-500", "*", "disabled"],
  ["portal/components/primitives.tsx", "now ? \"border-accent text-accent\" : \"border-neutral-300\"", "border", "step marker"],
  ["portal/components/primitives.tsx", "h-3 min-w-0 bg-neutral-300", "bg", "chart mark (non-text)"],
  ["portal/components/primitives.tsx", "items-end gap-[2px] border-b border-neutral-300", "border", "chart baseline"],
  ["portal/shell/GuestLanguage.tsx", "h-9 border border-neutral-300", "border", "input or select border"],
  ["portal/shell/PortalShell.tsx", "h-9 max-w-[280px] border border-neutral-300", "border", "input or select border"],
  ["portal/guest/ApplyForService.tsx", "border border-neutral-300 p-3", "border", "divider"],
  ["components/StatusPill.tsx", "bg-neutral-400 text-neutral-900", "bg", "fill (non-text)"],
  //: an ERRAND CARD the utility has switched off (`aria-disabled` article) —
  //: kept grey-500 by the colour lane as an inactive component; WCAG 1.4.3
  //: exempts inactive UI, and whether a whole card counts is the tester's call
  ["portal/components/primitives.tsx", "off ? \"text-lead font-bold text-neutral-500\"", "text", "disabled (switched-off card)"],
  ["portal/components/primitives.tsx", "off ? \"text-body leading-relaxed text-neutral-500\"", "text", "disabled (switched-off card)"],
  //: a sentence INSIDE a JSX comment that quotes an old class list
  ["portal/guest/HelpPage.tsx", "`border border-neutral-300 px-3 py-1", "*", "comment"],
];

function classify(prop, variants, line, near, file) {
  const v = variants || "";
  for (const [f, snip, p, use] of OVERRIDES)
    if (file.endsWith(f) && line.includes(snip) && (p === "*" || prop.startsWith(p))) return use;
  if (/disabled|aria-disabled/.test(v)) return "disabled";
  if (prop === "placeholder" || /placeholder/.test(v)) return "placeholder text";
  if (/^(ring|outline)/.test(prop)) return /focus/.test(v) ? "focus ring" : "outline";
  if (/^divide/.test(prop)) return "divider";
  // ⚠ NARROW CONTEXT: this line and two either side (an opening tag spans
  // lines). A wider window called every sentence in Usage.tsx a chart label.
  const chart = /data-money-(month|value|compare|legend)|data-month-label|<figcaption|data-usage-bar|role="img"/.test(near) && !/-empty/.test(line);
  const icon = /<svg|aria-hidden|Icon\b/.test(line);
  const field = /<input|<select|<textarea/.test(near);
  if (prop === "fill" || prop === "stroke") return chart ? "chart label or legend" : "icon that carries meaning";
  if (/^border/.test(prop)) return field ? "input or select border" : "divider";
  if (prop === "bg") return chart ? "chart mark (non-text)" : "fill (non-text)";
  if (prop === "text") {
    if (chart) return "chart label or legend";
    if (icon) return "icon that carries meaning";
    return "text";
  }
  return "other";
}

function afterColour(use, step, current) {
  if (use === "input or select border") return APPROVED.fieldBorder;
  if (["text", "placeholder text", "chart label or legend"].includes(use) && (step === "600" || step === "500"))
    return APPROVED.text600;
  if (step === "600") return APPROVED.text600; // the token itself moves, every use goes with it
  return current;
}

function required(use) {
  if (use.startsWith("disabled")) return "exempt";
  if (["divider", "fill (non-text)", "outline", "step marker", "chart baseline"].includes(use)) return "none";
  if (["text", "placeholder text"].includes(use)) return 4.5;
  if (use === "chart label or legend") return 4.5;
  return 3;
}

function codeInventory() {
  const files = portalClosure();
  const rows = [];
  for (const f of files) {
    const lines = readFileSync(f, "utf8").split("\n");
    const rel = relative(REPO, f);
    const isTokenFile = /styles\/(tokens|tailwind)\.css$/.test(f);
    lines.forEach((line, i) => {
      if (isComment(line)) return;
      const ctx = lines.slice(Math.max(0, i - 4), i + 4).join("\n");
      for (const m of line.matchAll(CLASS_RE)) {
        const [, variants, prop, step, alpha] = m;
        const use0 = classify(prop.replace(/-[trblxyse]$/, ""), variants, line, lines.slice(Math.max(0, i - 2), i + 3).join("\n"), f);
        if (use0 === "comment") continue;
        // the switched-off card line carries BOTH states; only its grey-500 half is the off state
        const use = use0.startsWith("disabled (switched") && step !== "500" ? "text" : use0;
        const base = GREY[step];
        const now = alpha ? blend(base, Number(alpha), WHITE) : base;
        let after = afterColour(use, step, base);
        if (alpha) after = blend(after, Number(alpha), WHITE);
        rows.push({ file: `${rel}:${i + 1}`, cls: m[0], use, now, after, req: required(use),
          nowW: ratio(now, WHITE), nowBg: ratio(now, BG), afterW: ratio(after, WHITE), afterBg: ratio(after, BG) });
      }
      if (/\.css$/.test(f) && !isTokenFile)
        for (const m of line.matchAll(VAR_RE)) {
          const prop = (line.match(/^\s*([a-z-]+)\s*:/) || [])[1] || "?";
          const use = /color$/.test(prop) && !/border|outline/.test(prop) ? "text" : /border/.test(prop) ? "divider" : "other";
          const base = GREY[m[1]];
          const after = afterColour(use, m[1], base);
          rows.push({ file: `${rel}:${i + 1}`, cls: `${prop}: ${m[0]}`, use, now: base, after, req: required(use),
            nowW: ratio(base, WHITE), nowBg: ratio(base, BG), afterW: ratio(after, WHITE), afterBg: ratio(after, BG) });
        }
      if (!isTokenFile)
        for (const m of line.matchAll(HEX_RE))
          rows.push({ file: `${rel}:${i + 1}`, cls: m[0], use: "hard-coded hex", now: m[0].toLowerCase(), after: m[0].toLowerCase(),
            req: "?", nowW: ratio(m[0], WHITE), nowBg: ratio(m[0], BG), afterW: ratio(m[0], WHITE), afterBg: ratio(m[0], BG) });
    });
  }
  return { files: files.map((f) => relative(REPO, f)), rows };
}

// ══════════════════════════════════════════════════════════════════════════
// MODE 2 — the browser scan
// ══════════════════════════════════════════════════════════════════════════

/** In-page helpers, injected once per document. */
const PAGE_HELPERS = () => {
  // ⚠ TWO SHAPES. Chrome reports a `color-mix()` result — the brand hover
  // steps, the chooser card's tint — as `color(srgb 0.9 0.2 0.1 / 0.06)`, not
  // `rgb()`. A parser that reads only `rgb()` returns null there and the first
  // version of this file threw on six signed-in pages because of it.
  const parse = (s) => {
    if (!s) return null;
    let m = s.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    m = s.match(/color\(srgb\s+([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
      return { r: p[0] * 255, g: p[1] * 255, b: p[2] * 255, a: p.length > 3 ? p[3] : 1 };
    }
    return null;
  };
  const hex = (c) => (c ? "#" + [c.r, c.g, c.b].map((x) => Math.round(x).toString(16).padStart(2, "0")).join("") : null);
  const over = (top, bot) => ({
    r: top.r * top.a + bot.r * (1 - top.a),
    g: top.g * top.a + bot.g * (1 - top.a),
    b: top.b * top.a + bot.b * (1 - top.a),
    a: 1,
  });
  const L = (c) => {
    const f = (x) => ((x /= 255) <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    if (!a || !b) return null;
    const [x, y] = [L(a), L(b)].sort((p, q) => q - p);
    return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100;
  };
  /** The colour actually painted behind `el` (alpha-composited up the tree). */
  const bgOf = (el) => {
    const stack = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0) {
        stack.push(c);
        if (c.a >= 1) break;
      }
    }
    let acc = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) acc = over(stack[i], acc);
    return acc;
  };
  const sel = (el) => {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && parts.length < 4; n = n.parentElement) {
      let s = n.tagName.toLowerCase();
      const ds = [...n.attributes].find((a) => a.name.startsWith("data-") && a.name !== "data-state");
      if (ds) s += `[${ds.name}${ds.value ? `="${ds.value.slice(0, 30)}"` : ""}]`;
      else if (n.parentElement) {
        const sib = [...n.parentElement.children].filter((c) => c.tagName === n.tagName);
        if (sib.length > 1) s += `:nth-of-type(${sib.indexOf(n) + 1})`;
      }
      parts.unshift(s);
    }
    return parts.join(" > ");
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && Number(cs.opacity) > 0;
  };
  /** The colour class that is responsible for `el`'s text colour. */
  const colourClass = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cls = (n.getAttribute("class") || "").split(/\s+/).filter((c) => /(^|:)text-(neutral|accent|danger|success|warning|info|text|\[)/.test(c));
      if (cls.length) return cls.join(" ");
    }
    return "(inherited from body)";
  };
  const disabled = (el) => el.closest("[disabled], [aria-disabled='true'], fieldset[disabled]") !== null;
  window.__a11y = { parse, hex, ratio, bgOf, sel, visible, colourClass, disabled };
};

/** Measurements axe does not make. Runs in the page. */
const EXTRA_CHECKS = () => {
  const { parse, hex, ratio, bgOf, sel, visible, disabled } = window.__a11y;
  const out = [];
  const root = document.querySelector("main") ? document.body : document.body;
  // 1 · placeholder text (axe skips ::placeholder) — 4.5:1
  for (const el of root.querySelectorAll("input[placeholder], textarea[placeholder]")) {
    if (!visible(el) || !el.getAttribute("placeholder")) continue;
    const c = parse(getComputedStyle(el, "::placeholder").color);
    if (!c) continue;
    const bg = bgOf(el);
    const r = ratio(c, bg);
    out.push({ kind: "placeholder", selector: sel(el), fg: hex(c), bg: hex(bg), ratio: r, need: 4.5, exempt: disabled(el),
      text: el.getAttribute("placeholder").slice(0, 40), cls: (el.getAttribute("class") || "").match(/placeholder:\S+/g)?.join(" ") || "(default)" });
  }
  // 2 · field borders (WCAG 1.4.11) — 3:1 against the colour beside the edge
  for (const el of root.querySelectorAll("input:not([type=hidden]), select, textarea")) {
    const box = ["checkbox", "radio"].includes(el.type) ? el : el;
    if (!visible(box)) continue;
    const cs = getComputedStyle(box);
    if (cs.borderTopStyle === "none" || parseFloat(cs.borderTopWidth) === 0) {
      if (["checkbox", "radio"].includes(el.type)) {
        // native control: drawn by the UA — record the accent-color it uses
        out.push({ kind: "native control", selector: sel(el), fg: cs.accentColor, bg: hex(bgOf(el.parentElement)), ratio: null, need: 3,
          exempt: disabled(el), text: el.type, cls: "(browser-drawn)" });
      }
      continue;
    }
    const c = parse(cs.borderTopColor);
    const outside = bgOf(box.parentElement);
    const inside = bgOf(box);
    const r = c ? Math.min(ratio(c, outside), ratio(c, inside)) : null;
    out.push({ kind: "field border", selector: sel(el), fg: hex(c), bg: hex(outside), bgInside: hex(inside), ratio: r, need: 3, exempt: disabled(el),
      text: el.tagName.toLowerCase() + (el.type ? `[${el.type}]` : ""), cls: (box.getAttribute("class") || "").match(/border-\S+/g)?.join(" ") || "" });
  }
  // 3 · text inside SVG (chart axis labels and legends) — axe does not read it
  for (const t of root.querySelectorAll("svg text, svg tspan")) {
    if (!visible(t) || !t.textContent.trim()) continue;
    const cs = getComputedStyle(t);
    const c = parse(cs.fill) || parse(cs.color);
    if (!c) continue;
    const bg = bgOf(t.closest("svg").parentElement);
    const size = parseFloat(cs.fontSize);
    const bold = Number(cs.fontWeight) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    out.push({ kind: "svg text", selector: sel(t), fg: hex(c), bg: hex(bg), ratio: ratio(c, bg), need, exempt: false,
      text: t.textContent.trim().slice(0, 30), cls: t.getAttribute("class") || "" });
  }
  // 4 · meaningful icons — an svg that is NOT aria-hidden, or the only
  //     content of a control (an icon-only button/link). 3:1.
  for (const s of root.querySelectorAll("svg")) {
    if (!visible(s)) continue;
    const control = s.closest("button, a, [role=button]");
    const iconOnly = control && !control.textContent.trim();
    // ⚠ An icon-only row action hides its SVG (`aria-hidden`) and names the
    // CONTROL instead — the icon is still the only thing a sighted person
    // sees, so it still needs 3:1. The first version skipped every hidden
    // SVG and found no icons at all on a page of eight icon buttons.
    if (s.closest("[aria-hidden='true']") && !iconOnly) continue;
    const labelled = s.getAttribute("role") === "img" || s.getAttribute("aria-label") || s.querySelector("title");
    if (!iconOnly && !labelled) continue;
    if (s.querySelector("text")) continue; // a chart, handled above
    const cs = getComputedStyle(s);
    const c = parse(cs.color);
    const stroke = parse(cs.stroke);
    const fill = parse(cs.fill);
    const paint = (stroke && stroke.a > 0 ? stroke : null) || (fill && fill.a > 0 ? fill : null) || c;
    const bg = bgOf(s.parentElement);
    out.push({ kind: "icon", selector: sel(s), fg: hex(paint), bg: hex(bg), ratio: ratio(paint, bg), need: 3, exempt: control ? disabled(control) : false,
      text: (control?.getAttribute("aria-label") || s.getAttribute("aria-label") || "").slice(0, 40), cls: (s.getAttribute("class") || "") });
  }
  // 5 · chart marks — bars in the usage chart (non-text, 3:1 against the plot)
  for (const b of root.querySelectorAll("[data-usage-bar], [data-chart] [data-bar], svg rect[data-bar]")) {
    if (!visible(b)) continue;
    const c = parse(getComputedStyle(b).backgroundColor) || parse(getComputedStyle(b).fill);
    if (!c || c.a === 0) continue;
    const bg = bgOf(b.parentElement);
    out.push({ kind: "chart mark", selector: sel(b), fg: hex(c), bg: hex(bg), ratio: ratio(c, bg), need: 3, exempt: false, text: "", cls: b.getAttribute("class") || "" });
  }
  // 6 · the brand colour where it FILLS — white (or other) text on accent
  const accent = getComputedStyle(document.querySelector("[style*='--color-accent']") || document.documentElement)
    .getPropertyValue("--color-accent").trim();
  for (const el of root.querySelectorAll("button, a, [role=button], span, div")) {
    if (!visible(el)) continue;
    const cls = el.getAttribute("class") || "";
    if (!/(^|\s)(hover:)?bg-accent(\s|$)|bg-accent-(600|700)|text-accent(\s|$)|border-accent/.test(cls)) continue;
    if (!el.textContent.trim()) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color);
    const bg = bgOf(el);
    out.push({ kind: /bg-accent/.test(cls) ? "brand fill" : "brand text", selector: sel(el), fg: hex(fg), bg: hex(bg), ratio: ratio(fg, bg),
      need: parseFloat(cs.fontSize) >= 24 || (Number(cs.fontWeight) >= 700 && parseFloat(cs.fontSize) >= 18.66) ? 3 : 4.5,
      exempt: disabled(el), text: el.textContent.trim().slice(0, 30), cls: cls.match(/\S*accent\S*/g)?.join(" ") || "", accent });
  }
  return out;
};

/** The focus indicator of document.activeElement, against what is behind it. */
const FOCUS_RING = () => {
  const { parse, hex, ratio, bgOf, sel, visible } = window.__a11y;
  const el = document.activeElement;
  if (!el || el === document.body || !visible(el)) return null;
  const cs = getComputedStyle(el);
  const res = { selector: sel(el), tag: el.tagName.toLowerCase(), text: (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 30) };
  const behind = bgOf(el.parentElement);
  const own = bgOf(el);
  res.bg = hex(behind);
  res.ownBg = hex(own);
  if (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0) {
    const c = parse(cs.outlineColor);
    res.indicator = "outline";
    res.fg = hex(c);
    res.width = cs.outlineWidth;
    res.offset = cs.outlineOffset;
    // With a positive offset the ring sits on what is BEHIND the control;
    // with none it touches the control's own fill too.
    res.ratio = parseFloat(cs.outlineOffset) > 0 ? ratio(c, behind) : Math.min(ratio(c, behind), ratio(c, own));
  } else if (cs.boxShadow && cs.boxShadow !== "none") {
    const colours = [...cs.boxShadow.matchAll(/rgba?\([^)]+\)|color\(srgb[^)]+\)/g)].map((m) => parse(m[0])).filter((c) => c && c.a > 0);
    if (colours.length) {
      const best = colours.map((c) => ({ c, r: ratio(c, behind) })).sort((a, b) => b.r - a.r)[0];
      res.indicator = "box-shadow";
      res.fg = hex(best.c);
      res.ratio = best.r;
    }
  }
  if (!res.indicator) {
    // Focus may be drawn on an ancestor via :has(:focus-visible) — the chooser card.
    const card = el.closest(".chooser-option, label");
    if (card) {
      const ccs = getComputedStyle(card);
      if (ccs.outlineStyle !== "none" && parseFloat(ccs.outlineWidth) > 0) {
        const c = parse(ccs.outlineColor);
        res.indicator = "outline on ancestor";
        res.fg = hex(c);
        res.ratio = ratio(c, bgOf(card.parentElement));
      }
    }
  }
  if (!res.indicator) res.indicator = "NONE";
  return res;
};

/** The approved colours, simulated: CSS rules rewritten in place, in memory. */
const SIMULATE = (approved) => {
  const touch = (rules) => {
    for (const r of rules) {
      if (r.cssRules) touch(r.cssRules);
      if (!r.selectorText || !r.style) continue;
      const s = r.selectorText;
      // grey-500 used AS TEXT (incl. its placeholder variant) → the new grey-600
      if (/text-neutral-500/.test(s) && r.style.getPropertyValue("color")) r.style.setProperty("color", approved.text500, "important");
    }
  };
  for (const sh of document.styleSheets) {
    try {
      touch(sh.cssRules);
    } catch {
      /* cross-origin sheet — none expected */
    }
  }
  const st = document.createElement("style");
  st.setAttribute("data-a11y-simulation", "");
  // the token itself moves: every use of grey-600 goes with it
  st.textContent = `:root, :host, [style] { --color-neutral-600: ${approved.text600} !important; }`;
  document.head.appendChild(st);
  // field and select borders: a NEW token, used only by inputs and selects —
  // so only a field whose border is today the grey-300 hairline moves.
  const fields = () => {
    for (const el of document.querySelectorAll("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea")) {
      const c = getComputedStyle(el).borderTopColor;
      if (c === "rgb(215, 211, 211)") el.style.setProperty("border-color", approved.fieldBorder, "important");
    }
  };
  fields();
  if (!window.__a11ySimObserver) {
    window.__a11ySimObserver = new MutationObserver(fields);
    window.__a11ySimObserver.observe(document.body, { childList: true, subtree: true });
  }
};

async function browserScan() {
  const require = createRequire(join(FRONTEND, "package.json"));
  const { chromium } = require("playwright");
  const BASE = process.env.BASE ?? "http://127.0.0.1:4299";
  const TENANT = process.env.PORTAL_TENANT ?? "pine-hill";
  const LOGIN = process.env.PORTAL_LOGIN;
  const PASSWORD = process.env.PORTAL_PASSWORD ?? "Sample-Portal-2026!";
  const AXE = process.env.AXE_PATH;
  const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const OUT = args.out ? resolve(String(args.out)) : null;
  const LANGS = String(args.langs ?? "en,es").split(",");
  const AUTHS = String(args.auth ?? "out,in").split(",");
  const STATES = !!args.states;
  const SIM = !!args.simulate;
  const BRAND = args.brand ? String(args.brand) : null;
  if (!AXE || !existsSync(AXE)) throw new Error("AXE_PATH must name axe.min.js (npm install --no-save axe-core@4.10.3)");
  if (AUTHS.includes("in") && !LOGIN) throw new Error("PORTAL_LOGIN is required for the signed-in pass");
  const axeVersion = (readFileSync(AXE, "utf8").match(/axe v([\d.]+)/) || [])[1] ?? "?";
  if (OUT) mkdirSync(OUT, { recursive: true });

  // ── every route the router mounts, not only the register ────────────────
  const routes = [...readFileSync(join(SRC, "portal/routing/portalRoutes.tsx"), "utf8").matchAll(/\{\s*path:\s*"([^"]*)",\s*element:\s*<(\w+)/g)].map(
    ([, path, el]) => ({ path, element: el }),
  );
  const register = [...readFileSync(join(SRC, "portal/routing/screenIds.ts"), "utf8").matchAll(/\{\s*path:\s*"([^"]*)",\s*id:\s*"(CWP-\d+)"/g)].map(
    ([, path, id]) => ({ path, id }),
  );
  const idOf = (p) => register.find((r) => r.path === p)?.id ?? "(unregistered)";

  const launch = () => chromium.launch(existsSync(CHROME) ? { executablePath: CHROME } : {});
  let browser = await launch();
  const rel = (p) => `/${TENANT}/portal` + (p === "/" ? "" : p);

  // discover the references a :param needs, through the API the screens read
  const ctx0 = await browser.newContext();
  const api = ctx0.request;
  const params = {};
  if (LOGIN) {
    const s = await api.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, { data: { email: LOGIN, password: PASSWORD } });
    if (!s.ok()) throw new Error(`sign-in refused: ${s.status()} ${(await s.text()).slice(0, 200)}`);
    const first = async (path, key, pick) => {
      const r = await api.get(`${BASE}/api/${TENANT}/portal${path}`);
      const b = r.ok() ? await r.json().catch(() => null) : null;
      const list = b?.[key];
      return Array.isArray(list) && list.length ? pick(list[0]) : null;
    };
    params.number = await first("/bills", "bills", (b) => b.number);
    params.reference = await first("/requests", "requests", (r) => r.reference ?? r.number);
  }
  const g = await api.get(`${BASE}/api/${TENANT}/portal/public/help`);
  params.helpSlug = g.ok() ? (await g.json())?.answers?.[0]?.slug : null;
  const c = await api.get(`${BASE}/api/${TENANT}/portal/public/service-centres`);
  params.centreSlug = c.ok() ? (await c.json())?.centres?.[0]?.slug : null;
  await ctx0.close();

  const pages = [];
  const skipped = [];
  for (const r of routes) {
    let p = r.path;
    if (p.includes(":draft")) {
      skipped.push({ ...r, why: "a draft link is minted by the form, not typed" });
      continue;
    }
    if (p.includes(":number")) p = params.number ? p.replace(":number", params.number) : null;
    else if (p.includes(":reference")) p = params.reference ? p.replace(":reference", params.reference) : null;
    else if (p.includes(":slug")) p = p.startsWith("/help") ? (params.helpSlug ? p.replace(":slug", params.helpSlug) : null) : params.centreSlug ? p.replace(":slug", params.centreSlug) : null;
    if (!p) {
      skipped.push({ ...r, why: "no reference on this login" });
      continue;
    }
    if (args.only && !String(args.only).split(",").includes(r.path)) continue;
    pages.push({ route: r.path, path: p, id: idOf(r.path), element: r.element });
  }

  const results = { meta: { axeVersion, base: BASE, tenant: TENANT, simulate: SIM, brand: BRAND, langs: LANGS, auths: AUTHS, states: STATES,
    at: new Date().toISOString(), routes: routes.length, register: register.length, scanned: pages.length, skipped }, runs: [] };

  // ⚠ THE BROWSER CAN DIE UNDER US. On 2026-10-23 the whole Chromium went away
  // mid-run twice (another process on the machine), and a walk that throws
  // there reports nothing. So a session is something this script can REOPEN:
  // relaunch, new context, re-sign-in, and retry the page once.
  async function openSession(auth, tries = 3) {
    try {
      return await openSessionOnce(auth);
    } catch (e) {
      if (tries <= 1) throw e;
      await new Promise((r) => setTimeout(r, 5000));
      await browser.close().catch(() => {});
      browser = await launch();
      return openSession(auth, tries - 1);
    }
  }
  async function openSessionOnce(auth) {
    if (!browser.isConnected()) browser = await launch();
    // `bypassCSP`: the server's `script-src 'self'` refuses axe as an inline
    // script and the simulation as an inline style. Bypassing it in the TEST
    // browser changes nothing the product serves.
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true });
    const page = await context.newPage();
    page.on("dialog", (d) => d.dismiss().catch(() => {}));
    if (BRAND) {
      await context.route("**/api/**", async (route) => {
        const resp = await route.fetch();
        const ct = resp.headers()["content-type"] || "";
        if (!ct.includes("json")) return route.fulfill({ response: resp });
        const body = await resp.text();
        route.fulfill({ response: resp, body: body.replace(/"brand_primary_hex":\s*"#?[0-9A-Fa-f]{6}"/g, `"brand_primary_hex": "${BRAND}"`) });
      });
    }
    if (auth === "in") {
      const s = await page.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, { data: { email: LOGIN, password: PASSWORD } });
      if (!s.ok()) throw new Error(`sign-in refused in browser context: ${s.status()}`);
    }
    return { context, page };
  }

  for (const auth of AUTHS) {
    let { context, page } = await openSession(auth);
    for (const lang of LANGS) {
      for (let attempt = 0, i = 0; i < pages.length; ) {
       const pg = pages[i];
       const run = { auth, lang, ...pg, states: {} };
       try {
        const t0 = Date.now();
        const load = async () => {
          await page.goto(BASE + rel(pg.path), { waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => {});
          await page.waitForSelector("[data-screen], main", { timeout: 4000 }).catch(() => {});
          await page.waitForTimeout(900);
          await page.evaluate(PAGE_HELPERS);
          if (lang !== "en")
            await page.evaluate(async (l) => {
              await window.__SMARTBILLHUB_I18N__?.changeLanguage(l);
            }, lang);
          await page.waitForTimeout(lang !== "en" ? 700 : 100);
          if (SIM) await page.evaluate(SIMULATE, APPROVED);
        };
        const axe = async (contextSel) => {
          await page.evaluate(PAGE_HELPERS);
          if (SIM) await page.evaluate(SIMULATE, APPROVED);
          const hasAxe = await page.evaluate(() => typeof window.axe !== "undefined");
          if (!hasAxe) await page.addScriptTag({ path: AXE });
          return page.evaluate(async (cs) => {
            const ctxNode = cs ? document.querySelector(cs) : document;
            if (!ctxNode) return { violations: [], incomplete: [] };
            const r = await window.axe.run(ctxNode, { runOnly: { type: "rule", values: ["color-contrast"] }, resultTypes: ["violations", "incomplete"] });
            const map = (n) => {
              const d = n.any?.[0]?.data ?? {};
              let el = null;
              try {
                el = document.querySelector(n.target[0]);
              } catch {}
              return {
                selector: n.target.join(" "),
                html: n.html.slice(0, 160),
                text: (el?.textContent || "").trim().replace(/\s+/g, " ").slice(0, 50),
                fg: d.fgColor, bg: d.bgColor, ratio: d.contrastRatio, need: d.expectedContrastRatio,
                fontSize: d.fontSize, fontWeight: d.fontWeight,
                colourClass: el ? window.__a11y.colourClass(el) : "?",
                reason: n.any?.[0]?.message?.slice(0, 90),
              };
            };
            return {
              violations: (r.violations[0]?.nodes ?? []).map(map),
              incomplete: (r.incomplete[0]?.nodes ?? []).map(map),
            };
          }, contextSel ?? null);
        };

        await load();
        //: ⚠ `$eval`, not `getAttribute`: getAttribute WAITS 30s for a missing
        //: element, and every signed-out page has none — 40s a page.
        run.screen = await page.$eval("[data-screen]", (e) => e.getAttribute("data-screen")).catch(() => null);
        run.words = (await page.locator("body").innerText().catch(() => "")).split(/\s+/).filter(Boolean).length;
        run.language = await page.evaluate(() => window.__SMARTBILLHUB_I18N__?.language ?? document.documentElement.lang);
        run.signedOutText = /signed out|sesión cerrada|no ha iniciado/i.test(await page.locator("body").innerText().catch(() => ""));
        run.finalUrl = page.url().replace(BASE, "");
        //: the shape a mis-built bundle produces on EVERY page — counted, and
        //: the run refuses below when most pages show it (law 7)
        run.couldNotOpen = /couldn't reach|could not reach|no pudimos conectar/i.test(await page.locator("body").innerText().catch(() => ""));
        run.states.default = await axe();
        run.extras = await page.evaluate(EXTRA_CHECKS);
        run.disabledCount = await page.evaluate(() => document.querySelectorAll("[disabled], [aria-disabled='true']").length);
        if (OUT) await page.screenshot({ path: join(OUT, `${auth}-${lang}${SIM ? "-sim" : ""}-${pg.path.replace(/[^a-z0-9]+/gi, "_") || "root"}.png`), fullPage: true }).catch(() => {});

        // ── states ────────────────────────────────────────────────────────
        if (STATES) {
          // expanders, pressed toggles, tabs, radios, <details>: open/select each, then scan
          const toggles = await page.$$eval(
            "main [aria-expanded='false'], main [aria-pressed], main [role=tab], main summary, main input[type=radio], main input[type=checkbox]",
            (n) => n.filter((e) => window.__a11y.visible(e) || e.type === "radio" || e.type === "checkbox").slice(0, 12).map((e) => window.__a11y.sel(e)),
          ).catch(() => []);
          const sel = [];
          for (const t of toggles) {
            try {
              await page.locator(t).first().click({ timeout: 1500, force: true });
              await page.waitForTimeout(250);
            } catch {}
          }
          if (toggles.length) {
            if (new URL(page.url()).pathname === new URL(BASE + rel(pg.path)).pathname) {
              const r = await axe();
              sel.push(...r.violations);
              run.states.selected = { violations: sel, incomplete: r.incomplete, toggled: toggles.length };
              run.extrasSelected = await page.evaluate(EXTRA_CHECKS);
            }
            await load();
          }

          // hover (EN only — colour does not depend on language)
          if (lang === "en") {
            const hov = await page.$$eval("main a[href], main button, header a[href], header button, footer a[href]",
              (n) => n.filter((e) => window.__a11y.visible(e) && !window.__a11y.disabled(e)).slice(0, 25).map((e) => window.__a11y.sel(e))).catch(() => []);
            const hv = [];
            for (const h of hov) {
              try {
                await page.locator(h).first().hover({ timeout: 1000 });
                await page.waitForTimeout(120);
                const r = await axe(h);
                for (const v of r.violations) hv.push({ ...v, trigger: h });
              } catch {}
            }
            run.states.hover = { violations: hv, probed: hov.length };
            await page.mouse.move(0, 0);

            // focus: Tab through the page; measure every focus indicator
            await load();
            const rings = [];
            const fv = [];
            await page.locator("body").click({ position: { x: 1, y: 1 } }).catch(() => {});
            for (let i = 0; i < 40; i++) {
              await page.keyboard.press("Tab");
              await page.waitForTimeout(60);
              const r = await page.evaluate(FOCUS_RING);
              if (!r) continue;
              if (rings.some((x) => x.selector === r.selector)) break;
              rings.push(r);
              const a = await axe(r.selector).catch(() => ({ violations: [] }));
              for (const v of a.violations) fv.push({ ...v, trigger: r.selector });
            }
            run.focus = rings;
            run.states.focus = { violations: fv, probed: rings.length };
            if (new URL(page.url()).pathname !== new URL(BASE + rel(pg.path)).pathname) await load();
          }

          // errors: press the page's primary button with nothing filled in
          await load();
          // The button that SENDS the form: a real submit first, then the
          // primary-variant button nearest a field. ⚠ Never a segmented
          // control or a tab — the first version pressed "All" on a filter
          // bar on eight pages and called that an error state.
          const primary = await page.$$eval("main button:not([disabled])", (n) => {
            const ok = n.filter((b) => window.__a11y.visible(b) && !b.closest("[data-segmented-control], [role=tablist], [role=radiogroup]") && !["tab", "radio"].includes(b.getAttribute("role")));
            const submit = ok.filter((b) => b.type === "submit");
            const prim = ok.filter((b) => b.getAttribute("data-variant") === "primary" && b.closest("form, section, [data-twocol-main]")?.querySelector("input, select, textarea"));
            return [...submit, ...prim].slice(0, 2).map((b) => window.__a11y.sel(b));
          }).catch(() => []);
          if (primary.length && (await page.$("main input, main select, main textarea"))) {
            const before = page.url();
            try {
              await page.locator(primary[0]).first().click({ timeout: 1500 });
              await page.waitForTimeout(800);
            } catch {}
            if (page.url() === before) {
              const r = await axe();
              run.states.error = { violations: r.violations, incomplete: r.incomplete, pressed: primary[0],
                alerts: await page.$$eval("[role=alert], [aria-invalid='true']", (n) => n.length).catch(() => 0) };
              run.extrasError = await page.evaluate(EXTRA_CHECKS);
            } else run.states.error = { navigated: page.url().replace(BASE, ""), violations: [] };
          }
        }
        const d = run.states.default;
        console.log(`${auth.padEnd(3)} ${lang} ${(run.screen ?? "—").padEnd(9)} ${String(d.violations.length).padStart(3)} fail ${String(d.incomplete.length).padStart(3)} review ${String(Math.round((Date.now() - t0) / 1000)).padStart(3)}s  ${pg.path}${run.words < 25 ? "  ⚠ NEARLY EMPTY" : ""}${run.language !== lang ? `  ⚠ LANGUAGE ${run.language}` : ""}`);
       } catch (e) {
        // A crashed tab is recorded and the walk goes on — never a silent gap.
        run.error = String(e.message ?? e).slice(0, 200);
        run.states.default ??= { violations: [], incomplete: [] };
        console.log(`${auth} ${lang} ERROR ${pg.path}: ${run.error}`);
        if (page.isClosed() || !browser.isConnected() || /crash/i.test(run.error)) {
          await context.close().catch(() => {});
          ({ context, page } = await openSession(auth));
          if (attempt === 0) {
            attempt = 1;
            continue; // retry this page once on a fresh session
          }
        }
       }
        results.runs.push(run);
        attempt = 0;
        i++;
      }
    }
    const broken = results.runs.filter((r) => r.auth === auth && r.couldNotOpen).length;
    if (broken > pages.length / 2) throw new Error(`${broken} pages drew "We couldn't reach …" — the bundle cannot reach the API; refusing to report`);
    if (auth === "in") {
      const home = results.runs.filter((r) => r.auth === "in" && r.path === "/home")[0];
      if (home?.signedOutText) throw new Error("the signed-in pass is signed out — refusing to report it");
    }
    await context.close().catch(() => {});
  }
  await browser.close().catch(() => {});
  return results;
}

// ── main ─────────────────────────────────────────────────────────────────
if (args.code) {
  const inv = codeInventory();
  const target = args.json ? resolve(String(args.json)) : null;
  if (target) writeFileSync(target, JSON.stringify(inv, null, 1));
  const byUse = {};
  for (const r of inv.rows) byUse[r.use] = (byUse[r.use] ?? 0) + 1;
  console.log(`files in the portal's import closure: ${inv.files.length}`);
  console.log(`uses found: ${inv.rows.length}`, byUse);
  if (!target) for (const r of inv.rows) console.log(`${r.file}\t${r.cls}\t${r.use}\t${r.nowW}\t${r.afterW}`);
} else {
  const res = await browserScan();
  const target = resolve(String(args.json ?? `portal-contrast-${res.meta.simulate ? "sim" : "base"}${res.meta.brand ? "-" + res.meta.brand.slice(1) : ""}.json`));
  writeFileSync(target, JSON.stringify(res, null, 1));
  const n = res.runs.reduce((a, r) => a + r.states.default.violations.length, 0);
  console.log(`\naxe ${res.meta.axeVersion} · ${res.meta.scanned} pages × ${res.meta.auths.length} × ${res.meta.langs.length} · ${n} failing nodes in the default state · written ${target}`);
  for (const s of res.meta.skipped) console.log(`  NOT SCANNED ${s.path} — ${s.why}`);
  // The tester's three figures, recomputed per pass: failing elements, how
  // many are one colour, and the worst pair.
  for (const auth of res.meta.auths)
    for (const lang of res.meta.langs) {
      const runs = res.runs.filter((r) => r.auth === auth && r.lang === lang);
      const nodes = runs.flatMap((r) => r.states.default.violations.map((v) => ({ ...v, path: r.path })));
      const failingPages = runs.filter((r) => r.states.default.violations.length).length;
      const byFg = {};
      for (const v of nodes) byFg[v.fg] = (byFg[v.fg] ?? 0) + 1;
      const worst = nodes.sort((a, b) => a.ratio - b.ratio)[0];
      const review = runs.reduce((a, r) => a + r.states.default.incomplete.length, 0);
      console.log(`signed ${auth} · ${lang}: ${nodes.length} failing elements on ${failingPages} of ${runs.length} pages · ${review} for review · by colour ${JSON.stringify(byFg)}` +
        (worst ? ` · worst ${worst.fg} on ${worst.bg} at ${worst.ratio}:1 (${worst.path})` : ""));
    }
}
