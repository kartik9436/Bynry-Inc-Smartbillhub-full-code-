// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6715 — Finance > General ledger > Chart is five tables where
//          the PO asked for one ("i will have 1 table only and i will use
//          columns to manage rest of the table").
// Drawing: 05-prototype/07 Finance Blueprint.pdf p024 (1·3 Chart, the drawn end
//          state) and p025 (its notes, filter criteria and components), read as
//          IMAGES (B14 rule 42).
// Rules:   CLAUDE.md hard-won law 6 — no gate looks at rendered output ·
//          hard-won law 2's MIRROR — a real absence that stops being visible
//          because the thing that showed it was tidied away.
// ───────────────────────────────────────────────────────
/**
 * WALK THE CHART TAB AND SAY WHAT IS ON IT.
 *
 * ⚠ **THE GUARD CASE COMES FIRST, AND IT IS THE POINT OF THIS FILE.**
 * An absence assertion over a blank page is the easiest false pass in this
 * repository to write: the one route-level rendered-output check could not
 * reach any Finance screen's BODY — with reads disabled the page never gets
 * past *"Set the fiscal year start to see the current period"* — so five of its
 * six "this panel is absent" assertions were passing over a blank page.
 *
 * So **nothing below is believed until `bodyRendered` passes**: the accounts
 * table must be on screen with real rows in it. If it is not, every absence
 * check is reported as UNPROVEN rather than as a pass.
 *
 * RUN, against a database nobody else is seeding and on your own ports:
 *   BASE=http://127.0.0.1:5844 SHOTS=<dir> node 10-scripts/def_led_6715_chart_one_table_walkthrough.mjs
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:5844";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/chart-shots";
const LABEL = process.env.LABEL ?? "after";

mkdirSync(SHOTS, { recursive: true });
const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail("page error: " + e.message));

async function shot(name) {
  writeFileSync(`${SHOTS}/${LABEL}-${name}.png`, await page.screenshot({ fullPage: true }));
  console.log(`    shot ${LABEL}-${name}.png`);
}

console.log("\n── sign in ────");
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
ok("signed in");

console.log("\n── Finance > General ledger > Chart ────");
await page.goto(`${BASE}/${TENANT}/finance?view=chart`, { waitUntil: "domcontentloaded" });

// ══ THE GUARD CASE ══════════════════════════════════════════════════════
// Prove the BODY rendered before believing any absence below it.
let bodyRendered = false;
try {
  await page.waitForSelector("table tbody tr td", { timeout: 40000 });
  const rows = await page.locator("table tbody tr").count();
  const head = (await page.locator("h3").allInnerTexts()).join(" | ");
  if (rows >= 5 && /account/i.test(head)) {
    bodyRendered = true;
    ok(`GUARD: the chart body rendered — ${rows} table rows, panel headings: ${head}`);
  } else {
    fail(`GUARD: body did not render as a chart (rows=${rows}, headings="${head}") — every absence below is UNPROVEN`);
  }
} catch {
  fail("GUARD: no table row appeared in 40s — every absence below is UNPROVEN");
}
await shot("chart");

// ══ WHAT SECTIONS ARE ON THE SCREEN ═════════════════════════════════════
const headings = await page.locator("main h3").allInnerTexts();
console.log("  panel headings on screen: " + JSON.stringify(headings));
const columns = await page.locator("table thead th").allInnerTexts();
console.log("  first table columns: " + JSON.stringify(columns.slice(0, 12)));
const tables = await page.locator("main table").count();
console.log(`  tables on screen: ${tables}`);

if (bodyRendered) {
  if (tables === 1) ok("ONE table on the Chart tab");
  else fail(`${tables} tables on the Chart tab — the PO asked for one`);
  for (const gone of ["Where each service's revenue goes", "Tax authorities",
                      "Codes your accounting package knows", "What each kind of money lands in"]) {
    const seen = await page.getByText(gone, { exact: false }).count();
    if (seen === 0) ok(`panel gone: ${gone}`);
    else fail(`panel STILL PRESENT: ${gone}`);
  }
}

// ══ THE WARNING THAT MUST SURVIVE THE DELETION ══════════════════════════
// Four GL roles have no live account. That is a real operational state, and an
// unfilled role has no row, so a column cannot carry it. It must be reachable
// as a FILTER and countable without opening one.
//
// This comment used to say "BR-LED-796 refuses a posting that needs one".
// Measured 2026-09-25: it does not. selectors.gl_account_for_designation
// returns None for an unfilled role and raises only on an unrecognised
// designation NAME; BR-LED-796 is one caller's worked case. Which is why this
// walkthrough checks the count and the filter in a real browser rather than
// trusting that something downstream would shout.
if (bodyRendered) {
  const badge = page.locator('[data-testid="coa-unfilled-roles-count"]');
  if ((await badge.count()) > 0) {
    ok(`the unfilled-role count is on screen: ${(await badge.first().innerText()).trim()}`);
  } else {
    fail("no unfilled-role count on screen — the roles panel's warning has been tidied away");
  }
  const filter = page.locator('[data-testid="coa-role-filter"]');
  if ((await filter.count()) > 0) {
    const values = await filter.locator("option").allInnerTexts();
    console.log("  Role filter values: " + JSON.stringify(values));
    // OPERATE THE CONTROL, never the URL.
    await filter.selectOption("needs-account");
    // ⚠ **WAIT FOR THE ROW, NOT FOR A CLOCK (`DEF-GOV-6646`, one screen over).**
    // The first run of this file slept 1,200ms and then counted rows: the panel
    // was still a loading skeleton, it reported ZERO roles over a working
    // screen, and the screenshot beside it is a page of grey bars. A wait on a
    // number of milliseconds is a measurement of how fast the machine is.
    await page
      .waitForSelector("table tbody tr td", { timeout: 20000 })
      .catch(() => undefined);
    const shown = await page.locator("table tbody tr").allInnerTexts();
    console.log(`  rows under "needs an account": ${shown.length}`);
    console.log("  " + JSON.stringify(shown.slice(0, 8)));
    if (shown.length > 0 && !shown.join(" ").includes("_")) {
      ok(`the filter lists ${shown.length} role(s) needing an account, by their human names`);
    } else {
      fail(`the filter listed ${shown.length} rows and/or showed a raw code`);
    }
    await shot("chart-needs-account");
    await filter.selectOption("");
    await page.waitForSelector("table tbody tr td", { timeout: 20000 }).catch(() => undefined);
  } else {
    fail("no Role filter on the Chart tab");
  }
}

// ══ THE OTHER CONTROLS, THROUGH THE REAL UI ═════════════════════════════
if (bodyRendered) {
  const search = page.locator('.fin-params input').first();
  if ((await search.count()) > 0) {
    const before = await page.locator("table tbody tr").count();
    await search.fill("cash");
    // ⚠ **WAIT FOR THE COUNT TO CHANGE, NOT FOR A ROW TO EXIST.** The second
    // run of this file waited on `rows > 0`, which was ALREADY TRUE of the 130
    // rows still on screen from before the search — so it counted the old list
    // and reported the search broken over a search that works. A condition
    // that is true before the act is not a wait; it is the third variant of
    // the same fault in one file, and it is the reason every wait here now
    // names the thing the act CHANGES.
    await page.waitForFunction(
      (was) => {
        const rows = document.querySelectorAll("table tbody tr").length;
        return rows > 0 && rows !== was;
      },
      before,
      { timeout: 20000 },
    ).catch(() => undefined);
    const n = await page.locator("table tbody tr").count();
    console.log(`  (was ${before} rows before the search)`);
    console.log(`  search "cash" -> ${n} rows`);
    (n > 0 && n < 100) ? ok("search narrows the one table") : fail(`search returned ${n} rows`);
    await search.fill("");
    await page.waitForTimeout(1000);
  }
  // ⚠ **IT IS A `<summary>` WITH AN `aria-label`, NOT A BUTTON WITH THE WORD
  // ON IT.** The first run of this file looked for text and reported the
  // control absent over a control that is on the screen — law 7's *looking at
  // the wrong thing*, in the probe rather than in the product. The kit draws
  // `ColumnChooser` as an icon disclosure; what a person finds it by is its
  // accessible name.
  const chooser = page.getByLabel("Show or hide columns");
  if ((await chooser.count()) > 0) {
    ok("the shared ColumnChooser is on the screen");
    await chooser.first().click();
    const items = await page.locator("details[open] label").allInnerTexts();
    console.log("  column menu: " + JSON.stringify(items));
    const nine = ["Code", "Name", "Type", "Role in the books", "Category",
                  "QuickBooks ref", "Xero ref", "Status", "Actions"];
    const missing = nine.filter((label) => !items.some((item) => item.includes(label)));
    if (missing.length === 0) ok("all NINE columns are offered by the menu");
    else fail("columns missing from the menu: " + missing.join(", "));
  } else {
    fail("no Columns control on the screen");
  }
}

console.log("\n── result ────");
if (problems.length === 0) console.log("  no problems");
else problems.forEach((p) => console.log("  ✗ " + p));
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
