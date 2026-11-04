// ── Trace ──────────────────────────────────────────────
// Defects: DEF-REP-6899 (a Download CSV that fails in silence) · DEF-REP-6900
//          (raw i18n keys on screen) · DEF-REP-6901 (raw database column names
//          as headings) · DEF-REP-6902 (six decimals on a money footer under a
//          two-decimal tile) · DEF-REP-6903 (six decimals on a quantity, raw
//          vocabulary codes in a cell) · DEF-REP-6891 (a pager counting FACTS
//          over a table drawing GROUP rows).
// Rules:   CLAUDE.md hard rule 2 (money 4 / percent 6, BOTH DISPLAY 2) · hard
//          rule 3 (a quantity always with its unit) · hard-won law 2's mirror
//          (a live screen behind a dead control) · hard-won law 6 (no gate
//          looks at rendered output) · hard-won law 7 clause 3 (a check's
//          output must distinguish pass from fail TO A READER) and clause 5
//          (a NUMBER beside every bucket, so a blind spot cannot read as an
//          empty one) · B14 rule 31 (no database id on screen).
// ───────────────────────────────────────────────────────
//
// OPEN EVERY REPORT AND COUNT WHAT A CLERK CAN SEE THAT THEY SHOULD NOT.
//
// Five counts, each of which names its own offenders rather than printing a
// total: a total alone reads identically whether the screens are clean or the
// selector stopped matching. `rep_6898_refusal_walk.mjs` is the shape; this
// one asks a different question of the same forty-six.
//
// USAGE:  BASE=http://127.0.0.1:8086 OUT=/tmp/walkfix node rep_walkfix_display_walk.mjs
const { existsSync, readdirSync, mkdirSync, writeFileSync, readFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8086";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/rep-walkfix";
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);

// The forty-six are READ FROM THE SEED, never typed here — a literal list is
// the count that rots the day a forty-seventh is seeded (law 7 clause 5).
const SEED = new URL("../06-backend/apps/reports/migrations/0003_seed_catalogue.py", import.meta.url);
const CATALOGUE = [
  ...readFileSync(SEED, "utf8").matchAll(
    /^\s*\("R\d+",\s*"([a-z0-9_]+)",\s*"([^"]*)",\s*"[^"]*",\s*"[^"]*",\s*"([a-z_]+)"/gm,
  ),
].map(([, key, name, dataset]) => ({ key, name, dataset }));
if (CATALOGUE.length !== 46) {
  throw new Error(`read ${CATALOGUE.length} definitions from the seed, expected 46`);
}
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — PLAYWRIGHT_BROWSERS_PATH is not set and /opt/pw-browsers has none");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...p) => console.log(...p);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL} against ${BASE}`);

const walk = ONLY.length ? CATALOGUE.filter((r) => ONLY.includes(r.key)) : CATALOGUE;
const results = [];
for (const row of walk) {
  const segment = row.key.replace(/_/g, "-");
  await page.goto(`${BASE}/${TENANT}/reports/${segment}`, { waitUntil: "networkidle" });
  // ⚠ **1.6s AND NOT 0.7s.** At 0.7 the account census and the close pack
  // reported ZERO rows and ZERO tiles on a run where both served perfectly —
  // a check timing out reads exactly like a clean screen, which is law 7's
  // fifth shape wearing a stopwatch.
  await page.waitForTimeout(1600);
  const seen = await page.evaluate(() => {
    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");
    const cellText = (el) => (el.textContent ?? "").trim();
    const heads = [...document.querySelectorAll("table thead th")].map(cellText);
    const bodyCells = [...document.querySelectorAll("table tbody td")].map(cellText);
    const footCells = [...document.querySelectorAll("table tfoot td, tr.fin-total-row td")].map(cellText);
    // ⚠ **A HEADING IS MATCHED AS THE DOM HOLDS IT, NOT AS THE SCREEN DRAWS
    // IT.** The table's `th` carries `text-transform: uppercase`, so a clerk
    // reads `PREMISES_NO` and `textContent` is `premises_no`. A first draft of
    // this file tested for CAPITALS and reported **zero raw headings over
    // fifty-five of them** — hard-won law 7's *structurally incapable of
    // failing*, found by dumping what the DOM actually held.
    const RAW_HEAD = /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/;
    // More than two decimal places in a figure that IS the whole cell — hard
    // rule 2. ⚠ Anchored on purpose: unanchored, it matches the shell's own
    // version badge (`v2.377.7`) on every screen in the product and reports
    // one false offender per report, for ever.
    const OVER_SCALE = /^-?[\d,]+\.\d{3,}$/;
    // A bare stored vocabulary code standing alone in a cell.
    const RAW_CODE = /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/;
    return {
      rows: document.querySelectorAll("table tbody tr").length,
      rawHeads: heads.filter((h) => RAW_HEAD.test(h)),
      // ⚠ **READ PER ELEMENT, NEVER OFF ONE BODY BLOB — THIS CHECK WAS BLIND
      // TO THE ONLY OFFENDER IT HAD.** `document.body.textContent` joins
      // sibling elements with NOTHING between them, so the service order's
      // subhead reads `2026-09-30cells.basis.raised` in one string, and a
      // `\b` anchor cannot match between `0` and `c` — both are word
      // characters. It reported **0 raw keys over a live one**, truthfully,
      // about a string it could not see the start of: hard-won law 7's fifth
      // shape, found by photographing the screen the check had just passed.
      rawKeys: [...document.querySelectorAll("main *")]
        .filter((el) => el.children.length === 0)
        .map(cellText)
        .filter((one) => /^(?:cells|reports)\.[a-z0-9_]+(?:\.[a-z0-9_]+)+$/.test(one))
        .filter((v, i, a) => a.indexOf(v) === i),
      overScaleCells: bodyCells.filter((c) => OVER_SCALE.test(c)).slice(0, 6),
      overScaleFoot: footCells.filter((c) => OVER_SCALE.test(c)),
      overScaleTiles: [...document.querySelectorAll("[data-kpi] .v, [data-kpi] .d")]
        .map(cellText)
        .filter((c) => OVER_SCALE.test(c)),
      rawCodeCells: bodyCells.filter((c) => RAW_CODE.test(c)).filter((v, i, a) => a.indexOf(v) === i).slice(0, 6),
      rawTiles: [...document.querySelectorAll("[data-kpi] .k")]
        .map(cellText)
        .filter((h) => RAW_HEAD.test(h) || (h === h.toLowerCase() && /^[a-z]+$/.test(h))),
      download: document.querySelectorAll('[data-testid="download-csv"], button[aria-label*="Download"], button[title*="Download"]').length,
      pager: (text.match(/\b\d+[–-]\d+ of \d+\b/) ?? [])[0] ?? null,
    };
  });
  results.push({ ...row, ...seen });
  const flags = [
    seen.rawHeads.length ? `heads:${seen.rawHeads.length}` : "",
    seen.rawKeys.length ? `keys:${seen.rawKeys.length}` : "",
    seen.overScaleCells.length || seen.overScaleFoot.length || seen.overScaleTiles.length
      ? `6dp:${seen.overScaleTiles.length}` : "",
    seen.rawCodeCells.length ? `codes:${seen.rawCodeCells.length}` : "",
  ].filter(Boolean).join(" ");
  say(`${row.key.padEnd(26)} ${String(seen.rows).padStart(3)} row(s)  ${flags}`);
}

const sum = (f) => results.reduce((n, r) => n + f(r).length, 0);
const any = (f) => results.filter((r) => f(r).length > 0).length;
say("");
say(`walked ${results.length} of ${CATALOGUE.length} reports at 1440`);
say(`DEF-REP-6901  raw column-name headings : ${sum((r) => r.rawHeads)} on ${any((r) => r.rawHeads)} report(s)`);
say(`DEF-REP-6901  raw KPI tile labels       : ${sum((r) => r.rawTiles)} on ${any((r) => r.rawTiles)} report(s)`);
say(`DEF-REP-6900  raw i18n keys on screen   : ${sum((r) => r.rawKeys)} on ${any((r) => r.rawKeys)} report(s)`);
say(`DEF-REP-6902  >2dp figures anywhere     : ${sum((r) => r.overScaleTiles)} on ${any((r) => r.overScaleTiles)} report(s)`);
say(`DEF-REP-6902  >2dp in the FOOTER total  : ${sum((r) => r.overScaleFoot)} on ${any((r) => r.overScaleFoot)} report(s)`);
say(`DEF-REP-6903  raw vocabulary codes      : ${sum((r) => r.rawCodeCells)} on ${any((r) => r.rawCodeCells)} report(s)`);
writeFileSync(`${OUT}/walk-results.json`, JSON.stringify(results, null, 2));
say(`wrote ${OUT}/walk-results.json`);
await browser.close();
