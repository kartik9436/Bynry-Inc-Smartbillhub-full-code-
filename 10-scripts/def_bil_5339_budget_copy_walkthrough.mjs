// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-BIL-5339 · DEF-BIL-5340 — Budget Bills, maintenance under
//           CR-103-BRC03 (12-governance/22-product-maintenance-process.md:
//           REPRODUCE before a line moves, PROVE against the reproduction after)
// Rules:    B14 rule 31 · 32 · 33 · hard-won law 6 (no gate reads rendered
//           output — the running screen is looked at) · staff widths 1440 + 1280
// ───────────────────────────────────────────────────────
/**
 * def_bil_5339_budget_copy_walkthrough — DRIVE the Budget Bills tab and record
 * what a clerk reads on it.
 *
 *     (cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \
 *        python manage.py runserver 127.0.0.1:8000 --noreload &)
 *     (cd 07-frontend && npx vite build && \
 *        API_PROXY_TARGET=http://127.0.0.1:8000 PORT=8080 node server.mjs &)
 *     node 10-scripts/def_bil_5339_budget_copy_walkthrough.mjs --before   # or --after
 *
 * `--before` records the unfixed screen, `--after` the fixed one; the same
 * eight looks are taken in both modes so the two sets of screenshots line up
 * side by side. What it MEASURES, in both modes:
 *
 *   1. every internal reference a clerk can read on the tab — the id grammar
 *      `CLAUDE.md` defines and dotted Python identifiers — read off TEXT NODES
 *      and `title`/`aria-label` attributes, the same question
 *      `07-frontend/src/testSupport/internalReferences.ts` asks in vitest;
 *   2. the heading over the stated absences, and whether it hardcodes a count;
 *   3. what the zero-results state says with no term and with a term for an
 *      account that EXISTS and is NOT enrolled (`ACCOUNT_NO` below), and
 *      whether that state names the set it searched and links to Enrol.
 *
 * `--before` is EXPECTED to print findings — that is the reproduction. `--after`
 * exits non-zero on any.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
/** Exists on the demo tenant and is NOT on budget billing (checked in SQL
 *  under the tenant GUC before this ran). The PO's reproduction used
 *  `AC-2026-00038` on the Ottumwa tenant, which is not in this database. */
const ACCOUNT_NO = process.env.ACCOUNT_NO ?? "A-10432";
const MODE = process.argv.includes("--after") ? "after" : "before";
const SHOTS = process.env.SHOTS ?? `SCRATCH/def-bil-5339/${MODE}`;
mkdirSync(SHOTS, { recursive: true });

const ID = /\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/g;
const DOTTED = /\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+\b/g;
const findings = [];
const note = (m) => console.log(m);
const flag = (m) => {
  findings.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

/** Runs IN the page: every text node and hover/read-aloud attribute under
 *  `[data-tab-panel], main`, one string each — never `textContent` of the
 *  whole, which glues `yet` to `BR-RAT-043` and hides the boundary. */
async function clerkVisibleStrings(page) {
  return page.evaluate(() => {
    const root = document.querySelector("main") ?? document.body;
    const out = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const s = n.textContent.trim();
      if (s) out.push(s);
    }
    for (const el of root.querySelectorAll("[title], [aria-label]")) {
      for (const a of ["title", "aria-label"]) {
        const v = el.getAttribute(a);
        if (v) out.push(v);
      }
    }
    return out;
  });
}

function internalReferences(strings) {
  const hits = [];
  for (const s of strings) {
    for (const m of s.match(ID) ?? []) hits.push({ ref: m, in: s });
    for (const m of s.match(DOTTED) ?? []) {
      if (m.includes("_") || m.split(".").length >= 3) hits.push({ ref: m, in: s });
    }
  }
  return hits;
}

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

for (const width of [1440, 1280]) {
  const ctx = await browser.newContext({ viewport: { width, height: 1100 } });
  const page = await ctx.newPage();
  note(`\n══ ${MODE.toUpperCase()} · ${width}px ══`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("#signin-password").press("Enter");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

  await page.goto(`${BASE}/${TENANT}/billing/budget`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-bil="gaps"], .state-zero, table.data-table', { timeout: 60000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/01-tab-${width}.png`, fullPage: true });

  // ── 1 · the stated-absence heading ──────────────────────────────────────
  const heading = await page.locator(".settings-arrives h3").first().textContent().catch(() => null);
  note(`heading over the stated absences: "${heading}"`);
  if (heading && /\b(one|two|three|four|five|\d+)\b/i.test(heading)) {
    flag(`the heading hardcodes a count: "${heading}"`);
  } else {
    ok("the heading carries no hardcoded count");
  }

  // ── 2 · open the gap list and read everything a clerk can ───────────────
  const gaps = page.locator('[data-bil="gaps"]');
  if ((await gaps.count()) > 0) {
    await gaps.locator("summary").click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${SHOTS}/02-gaps-open-${width}.png`, fullPage: true });
    const items = await gaps.locator("li").allTextContents();
    note(`the gap list holds ${items.length} bullet(s):`);
    for (const item of items) note(`    · ${item.slice(0, 110)}${item.length > 110 ? "…" : ""}`);
  } else {
    note("no gap list rendered (server served none)");
  }
  const strings = await clerkVisibleStrings(page);
  const hits = internalReferences(strings);
  if (hits.length === 0) ok("no rule id, question id or Python identifier is visible on the tab");
  for (const h of hits) flag(`internal reference "${h.ref}" is visible in: "${h.in.slice(0, 90)}…"`);

  // ── 3 · the zero-results state, no term ─────────────────────────────────
  const zeroNoTerm = await page.locator(".state-zero p").first().textContent().catch(() => null);
  note(`zero-results sentence with no term: "${zeroNoTerm}"`);
  if (zeroNoTerm && zeroNoTerm.includes("''")) flag(`the zero state echoes an empty term: "${zeroNoTerm}"`);
  const scopeNoTerm = await page.locator('[data-bil="search-scope"]').first().textContent().catch(() => null);
  if (scopeNoTerm) ok(`scope note under the empty list: "${scopeNoTerm}"`);
  else flag("no scope note under the empty list (which set is this?)");

  // ── 4 · search for an account that exists and is not enrolled ───────────
  // ⚠ THE TAB'S OWN TOOLBAR BOX, BY ITS PLACEHOLDER. `input[type="search"]`
  // matches the shell's global search first, and the first run of this script
  // typed the account number into that instead — every "after" assertion
  // would have passed over a search that never happened.
  const box = page.getByPlaceholder("Search account #, customer or address");
  await box.fill(ACCOUNT_NO);
  await page.waitForTimeout(900);
  await page.waitForSelector(".state-zero, table.data-table", { timeout: 30000 });
  await page.screenshot({ path: `${SHOTS}/03-search-${ACCOUNT_NO}-${width}.png`, fullPage: true });
  const zeroTerm = await page.locator(".state-zero p").first().textContent().catch(() => null);
  note(`zero-results sentence for "${ACCOUNT_NO}": "${zeroTerm}"`);
  const scope = page.locator('[data-bil="search-scope"]').first();
  if ((await scope.count()) > 0) {
    const text = await scope.textContent();
    const href = await scope.locator("a").first().getAttribute("href").catch(() => null);
    ok(`scope note: "${text}" → ${href}`);
    if (!href || !href.endsWith("/billing/budget/enrol")) flag(`the scope note does not point at Enrol (href ${href})`);
  } else {
    flag(`searching "${ACCOUNT_NO}" leaves a clerk with "${zeroTerm}" and no word on which set was searched or where to enrol`);
  }
  await ctx.close();
}

await browser.close();
console.log(`\n${MODE}: ${findings.length} finding(s); screenshots in ${SHOTS}`);
if (MODE === "after" && findings.length > 0) process.exit(1);
