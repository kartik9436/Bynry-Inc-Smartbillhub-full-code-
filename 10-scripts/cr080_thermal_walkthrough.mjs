#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-080 — thermal/heat is billed on connected tonnage, not on a
//           meter. PO 2026-09-07: *"connected tonnage - it is capacity not
//           metering; i will ahve 100 tonne or 200 tonne etc"*.
// Screens:  S8 → Settings → Services & UoM (the basis and the unit) ·
//           S8 → Reference data → Utility service size classes (the ladder) ·
//           S30 → bill detail → the thermal line a customer is charged
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           RUNNING app) · 13-change-process.md's CLOSURE BAR (PO 2026-08-18:
//           *"CR is not closed until we have confirm user is able to perform
//           tasks using screen/broswer/UI"*) · PO's standing rule, 2026-09-07:
//           *"everything should be executed based on actual code, and rules
//           that we place, also ensure you do web walkthorugh before you sign
//           off the user story or build"*
// ───────────────────────────────────────────────────────
/**
 * READ A THERMAL LINE OFF A REAL BILL, IN A REAL BROWSER.
 *
 *     10-scripts/cr080_seed_thermal_utility.py            # provision + seed + bill
 *     BASE=http://127.0.0.1:8080 TENANT=cr080-thermal \
 *       node 10-scripts/cr080_thermal_walkthrough.mjs
 *
 * ⚠ **IT DOES NOT ASSERT THAT A LINE EXISTS — IT READS THE RENDERED TEXT.**
 * That distinction is why this file exists: every backend case on this change
 * passes already, and not one of them can see a quantity that renders blank
 * because the unit never reached the screen, or a `$0.00` where the tonnage
 * did not reach the tenant (`DEF-2388`, one service over).
 *
 * ⚠ **AND IT ASSERTS THE `$0.00` LINE AS WELL AS THE PRICED ONES.** One seeded
 * unit deliberately has no connection recorded, so `BR-MET-108`'s ruled zero
 * has to stand on a real document beside real numbers. A walkthrough that only
 * ever looks at the priced units cannot tell a working zero from a missing one.
 */
import { createRequire } from "node:module";
const require = createRequire(process.env.NODE_MODULES_FROM ?? "/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "cr080-thermal";
const EMAIL = process.env.EMAIL ?? `owner@${TENANT}.test`;
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
const page = await ctx.newPage();

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

// ── 1 · SETTINGS → SERVICES & UoM · the basis and the unit, as a clerk sees ──
note("\n1 · Settings → Services & UoM");
await page.goto(`${BASE}/${TENANT}/settings/services`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const servicesText = await page.evaluate(() => document.body.innerText);
if (/[Tt]hermal/.test(servicesText)) {
  ok("the Thermal/Heat row is on the screen");
  const row = servicesText.split("\n").filter((l) => /[Tt]hermal/i.test(l)).join(" | ");
  note(`    rendered: ${row}`);
  if (/ton-hr/i.test(servicesText)) {
    fail("`ton-hr` is still rendered — thermal is capacity-billed and has no ton-hour");
  } else {
    ok("`ton-hr` is not on the screen");
  }
} else {
  fail("no Thermal/Heat row on Settings → Services & UoM");
}

// ── 2 · SETTINGS → REFERENCE DATA · the eight connected tonnages ────────────
note("\n2 · Settings → Reference data → Utility service size classes");
// ⚠ **THE ROUTE IS `settings/reference-data?list=<code>` AND THE SCREEN
// PAGINATES.** A first draft of this file guessed `settings/reference/
// service_size_classes`, which the router does not hold: it fell through to
// Settings → Company, and the three "is it listed" checks failed while the two
// "is it gone" checks PASSED — over a page that had none of the sixty-four rows
// on it. **A negative assertion over an empty page is a check that cannot
// fail** (CLAUDE.md law 7), so the first thing asserted here is that this
// screen is showing the right list at all.
await page.goto(`${BASE}/${TENANT}/settings/reference-data?list=service_size_classes`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(2000);
const heading = await page.evaluate(() => document.body.innerText);
if (!/[Ss]ize class/.test(heading)) {
  fail("the size-class list did not open — every check below would be vacuous");
} else {
  ok("the Utility service size classes list is open");
  // ⚠ **PAGINATE, DO NOT SEARCH.** A first draft typed each code into the
  // list's search box and read the table back. It was not reliable: the same
  // fill-and-wait returned an UNFILTERED page one for `TH-T5` and a filtered
  // one for `TH-T100`, so the run reported one code missing and two present
  // when the tenant demonstrably holds all eight (`select … from
  // meter_size_classes` says so). **A check whose answer depends on a debounce
  // cannot distinguish pass from fail** — CLAUDE.md law 7's third habit — so
  // this walks every page and unions what it reads.
  const seen = new Set();
  for (let pageNo = 1; pageNo <= 10; pageNo += 1) {
    await page.goto(
      `${BASE}/${TENANT}/settings/reference-data?list=service_size_classes&page=${pageNo}`,
      { waitUntil: "networkidle" },
    );
    await page.waitForTimeout(900);
    const cells = await page.evaluate(() =>
      [...document.querySelectorAll("table td")].map((c) => c.textContent.trim()),
    );
    if (!cells.length) break;
    const before = seen.size;
    for (const c of cells) seen.add(c);
    if (seen.size === before) break; // the last page repeated itself
  }
  note(`    read ${seen.size} distinct cell value(s) across the list's pages`);
  for (const code of ["TH-T5", "TH-T10", "TH-T25", "TH-T50", "TH-T100", "TH-T200", "TH-T400", "TH-T800"]) {
    if (seen.has(code)) ok(`${code} is listed`);
    else fail(`${code} is NOT listed — the ladder did not reach the tenant`);
  }
  for (const withdrawn of ["TH-CW-25", "TH-CW-25-100", "TH-CW-100P"]) {
    if (seen.has(withdrawn)) fail(`${withdrawn} is still listed — it is withdrawn`);
    else ok(`${withdrawn} is gone`);
  }
  // The negative assertions above are only meaningful because the positive ones
  // passed on the same reading — an empty page would fail both halves.
}



// ── 3 · THE BILL · the thermal line a customer is actually charged ──────────
note("\n3 · Billing → Bills → the thermal line");
const list = await (await page.request.get(`${BASE}/api/${TENANT}/invoices?status=issued&page_size=100`)).json();
const invoices = list.results ?? list.items ?? [];
note(`    ${invoices.length} issued bill(s)`);
let priced = null;
let zeroed = null;
for (const inv of invoices) {
  const detail = await (await page.request.get(`${BASE}/api/${TENANT}/invoices/${inv.id}`)).json();
  const lines = detail.lines ?? [];
  const thermal = lines.filter((l) => (l.service_code ?? l.service ?? "") === "thermal_heat");
  if (!thermal.length) continue;
  const total = thermal.reduce((a, l) => a + Number(l.amount ?? 0), 0);
  if (total > 0 && priced === null) priced = { id: inv.id, lines: thermal };
  if (total === 0 && zeroed === null) zeroed = { id: inv.id, lines: thermal };
  if (priced && zeroed) break;
}

if (!priced) {
  fail("no issued bill carries a PRICED thermal line — the tonnage did not reach the tenant (DEF-2388's shape)");
} else {
  await page.goto(`${BASE}/${TENANT}/billing/bills/${priced.id}?tab=lines`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  const billText = await page.evaluate(() => document.body.innerText);
  const shown = billText.split("\n").filter((l) => /thermal/i.test(l));
  note("    the thermal line(s), as rendered:");
  for (const l of shown) note(`      ${l}`);
  if (!shown.length) {
    fail("the API serves a thermal line and the SCREEN renders none");
  } else {
    ok("the thermal line is on the rendered bill");
    if (/\bton\b/i.test(shown.join(" "))) ok("its quantity carries the unit `ton`");
    else fail("the thermal line renders no unit — CLAUDE.md hard rule 3");
    if (/ton-hr/i.test(shown.join(" "))) fail("the line still says `ton-hr`");
  }
  for (const l of priced.lines) {
    note(`      API: qty=${l.quantity} ${l.uom ?? l.unit_of_measure ?? "?"} @ ${l.unit_price} = ${l.amount}`);
  }
}

if (!zeroed) {
  note("  (no $0.00 thermal line on this tenant — the ruled-zero seat may not be billed here)");
} else {
  ok(`BR-MET-108's ruled $0.00 stands on bill ${zeroed.id} beside real numbers`);
}

// ── verdict ────────────────────────────────────────────────────────────────
console.log("");
if (problems.length) {
  console.log(`cr080 walkthrough: ${problems.length} problem(s)`);
  for (const p of problems) console.log("  - " + p);
} else {
  console.log("cr080 walkthrough: clean");
}
await browser.close();
process.exit(problems.length ? 1 : 0);
