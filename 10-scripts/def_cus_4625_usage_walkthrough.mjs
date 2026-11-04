// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-4621 (the axis caption printed `{{low}} to {{high}}
//          {{unit}}`) · DEF-CUS-4622 (the unread-months caption, and its test
//          pinned it) · DEF-CUS-4623 (a parked gate finding reached the PO's
//          screen as a raw key) · DEF-CUS-4624 (the chart's aria-label, which
//          only markup can check) · DEF-CUS-4625 (the portal panel refused
//          over a portal that shipped) · DEF-CUS-4626 (the water figure beside
//          four electric ones)
// Rules:   CLAUDE.md hard-won law 6 — NO GATE IN THIS REPO READS RENDERED
//          OUTPUT, which is why the Product Owner found all four of these and
//          no check did · PO standing rule: *"everything should be executed
//          based on actual code … ensure you do web walkthorugh before you
//          sign off"* · B14 rule 32 (a description budget) · rule 33 (a
//          refusal caps at five or six words)
// ───────────────────────────────────────────────────────
/**
 * Open an account's Usage tab in a real browser and read the six lines back.
 *
 *     DATABASE_URL=… python3.12 manage.py runserver 127.0.0.1:8077 --noreload
 *     cd 07-frontend && ./node_modules/.bin/vite build
 *     PORT=4477 API_PROXY_TARGET=http://127.0.0.1:8077 \
 *       STATIC_DIR=/home/user/wt-usage/07-frontend/dist node server.mjs
 *     BASE=http://127.0.0.1:4477 SHOTS=… node 10-scripts/def_cus_4625_usage_walkthrough.mjs
 *
 * ⚠ **REBUILD THE BUNDLE FIRST AND CHECK THE HASH.** `server.mjs` serves
 * whatever is in `dist/` and never notices it is stale; on 2026-09-05 a server
 * started hours earlier served six screens that read as "never built". This
 * script prints the `index-*.js` the page actually loaded so the reader can
 * compare it with the one just built.
 *
 * ⚠ **AND `STATIC_DIR` IS PASSED EXPLICITLY**, because `server.mjs` resolves
 * `dist/` from its OWN directory: a lane in a worktree that runs the shared
 * checkout's `server.mjs` serves the SHARED checkout's bundle, however
 * carefully it just built its own.
 *
 * WHAT IT ASSERTS, AND WHY EACH ONE IS HERE RATHER THAN IN A VITEST FILE
 * ---------------------------------------------------------------------
 * Every check below could be written against `renderToStaticMarkup`, and most
 * of them ARE, in `AccountUsageTab.test.tsx`. They are here as well because
 * the vitest suite was GREEN through all six defects: it renders the component
 * with a hand-written payload, and four of the six are faults in what the
 * REAL server sends or in copy that only resolves against the real catalogue.
 * This walks the actual product, over the actual database, and reads what a
 * clerk reads.
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire("/home/user/wt-usage/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4477";
const TENANT = process.env.TENANT ?? "pine-hill";
const EMAIL = process.env.EMAIL ?? "sarah@pinehillwp.test";
const PASSWORD = process.env.PASSWORD ?? "Pin3Hill!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "";
const SHOTS = process.env.SHOTS ?? "/tmp/usage-shots";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(e.message.slice(0, 160)));
page.on("response", (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) {
    jsErrors.push(`${r.status()} ${r.url().replace(BASE, "")}`);
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
const bundle = await page.evaluate(() =>
  [...document.querySelectorAll("script[src]")].map((s) => s.getAttribute("src")).join(" "),
);
console.log(`bundle served: ${bundle}`);
await page.locator("#signin-password").waitFor({ timeout: 30000 });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
console.log(`signed in — ${page.url()}`);

await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=usage`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(3500);
const usageTab = page.getByRole("tab", { name: /usage/i }).or(page.locator("a,button").filter({ hasText: /^Usage$/ }));
if (await usageTab.count()) {
  await usageTab.first().click().catch(() => {});
  await page.waitForTimeout(2500);
}
await page.screenshot({ path: `${SHOTS}/usage-after.png`, fullPage: true });
const text = (await page.locator("body").innerText()).trim();
writeFileSync(`${SHOTS}/usage-after.txt`, text);

// ── 1 · NO PLACEHOLDER AND NO RAW KEY ANYWHERE ─────────────────────────────
// The whole page, not the parts a person happens to look at. `{{` covers the
// two captions the PO photographed; the key shape covers the KPI tile.
const html = await page.content();
if (html.includes("{{")) {
  fail(`a raw placeholder is still on screen: ${html.match(/.{0,60}\{\{.{0,40}/)?.[0]}`);
} else ok("no `{{` anywhere in the rendered page");
const rawKey = text.match(/\bcustomers\.account\.[a-z][A-Za-z0-9.]+/);
if (rawKey) fail(`a raw translation key is on screen: ${rawKey[0]}`);
else ok("no raw `customers.account.*` key is rendered as a value");

// ── 2 · THE AXIS CAPTION STATES THE WINDOW ─────────────────────────────────
const axis = text.match(/\b(\d{4}-\d{2}) to (\d{4}-\d{2})\b/);
if (axis) ok(`axis caption reads the window: "${axis[0]}"`);
else fail("no `YYYY-MM to YYYY-MM` window caption found under the chart");

// ── 3 · THE CHART'S ACCESSIBLE NAME CARRIES ITS UNIT ───────────────────────
// Nobody can SEE this one — it is read aloud. A screenshot cannot check it.
// ⚠ NOT `[role="img"]` unqualified — the FIRST one on this page is the
// tenant's logo, and pointing a check at the wrong element is law 7's
// *looking at the wrong thing*. This walkthrough's own first run did exactly
// that and reported the logo's alt text as the chart's failure.
const aria = await page
  .locator('[role="img"][aria-label*="usage in"]')
  .first()
  .getAttribute("aria-label")
  .catch(() => null);
if (aria && !aria.includes("{{") && /usage in \S+/.test(aria)) {
  ok(`chart aria-label resolves: "${aria}"`);
} else fail(`chart aria-label is wrong: ${JSON.stringify(aria)}`);

// ── 4 · THE READ-OUTS ARE BODY TEXT, NOT KPI TILES ─────────────────────────
const readouts = page.locator('[data-testid="usage-readouts"]');
if (await readouts.count()) {
  const size = await readouts.locator("span").nth(1).evaluate((el) => getComputedStyle(el).fontSize);
  const body = await page.locator("body").evaluate((el) => getComputedStyle(el).fontSize);
  ok(`read-out row present; value ${size} against body ${body}`);
  if (parseFloat(size) > parseFloat(body) * 1.4) {
    fail(`the read-out value is ${size} — still far larger than the ${body} it summarises`);
  }
  if (await page.locator(".kpi-grid").count()) {
    fail("a `.kpi-grid` is still on this screen — the shared KPI component is back");
  } else ok("no `.kpi-grid` on this screen; KPIStrip is untouched elsewhere");
} else fail("no read-out row found");

// ── 5 · THE SERVICE PICKER, AND ONE TREND AT A TIME ────────────────────────
const picker = page.locator("#usage-service");
if (await picker.count()) {
  const options = await picker.locator("option").allTextContents();
  const charts = await page.locator("h3").filter({ hasText: /per month/ }).count();
  ok(`picker offers ${options.length}: ${options.join(" · ")}; ${charts} chart drawn`);
  if (charts !== 1) fail(`expected ONE chart on open, found ${charts}`);

  // Switch service and confirm the chart, the unit and the read-outs move.
  const before = await page.locator("h3").filter({ hasText: /per month/ }).first().innerText();
  const second = (await picker.locator("option").nth(1).getAttribute("value")) ?? "";
  await picker.selectOption(second);
  await page.waitForTimeout(1500);
  const after = await page.locator("h3").filter({ hasText: /per month/ }).first().innerText();
  if (before === after) fail(`choosing "${second}" did not change the chart (still "${after}")`);
  else ok(`picker switches the chart: "${before}" → "${after}"`);
  await page.screenshot({ path: `${SHOTS}/usage-after-second-service.png`, fullPage: true });
  writeFileSync(`${SHOTS}/usage-after-second-service.txt`, (await page.locator("body").innerText()).trim());
} else {
  ok("no picker — this account takes one service, so it is not asked to choose");
}

// ── 6 · THE PORTAL PANEL SAYS WHAT THE DATA SAYS ───────────────────────────
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
const overview = (await page.locator("body").innerText()).trim();
writeFileSync(`${SHOTS}/portal-panel-after.txt`, overview);
await page.screenshot({ path: `${SHOTS}/portal-panel-after.png`, fullPage: true });
if (overview.includes("out of scope for this version")) {
  fail("the portal panel STILL says the portal is out of scope");
} else ok("the `out of scope for this version` sentence is gone");
if (overview.includes("never built")) fail("the panel still claims columns were never built");
else ok("the `columns that were never built` claim is gone");
for (const want of ["Portal access", "Last sign-in", "Paperless", "Bills are always printed"]) {
  if (overview.includes(want)) ok(`portal panel states "${want}"`);
  else fail(`portal panel is missing "${want}"`);
}

if (jsErrors.length) {
  console.log("\nJS errors / failed API calls:");
  for (const e of [...new Set(jsErrors)].slice(0, 8)) console.log("  " + e);
}
console.log(`\nshots + text in ${SHOTS}`);
console.log(problems.length ? `\n${problems.length} PROBLEM(S)` : "\nall checks passed");
await browser.close();
process.exit(problems.length ? 1 : 0);
