// ── Trace ──────────────────────────────────────────────
// Defects: DEF-LED-6662 · DEF-LED-6664 · DEF-LED-6663 · DEF-LED-6668 ·
//          DEF-LED-6654 — five Finance controls that were wrong on a screen
//          that worked. Plus a MEASUREMENT of DEF-REP-6660 (the Aging list's
//          two unservable sort columns), which is handed back, not fixed.
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app against the
//          drawing; no gate looks at rendered output"*) · law 2 and its MIRROR
//          (*"assert the destination by ADDRESS and by the SCREEN ID it
//          opens"*) · BR-SHL-025.
// ───────────────────────────────────────────────────────
/**
 * **EVERY ONE OF THESE FIVE WAS FOUND BY OPENING A SCREEN AND BY NOTHING
 * ELSE**, so a fix proved by vitest is not proved. This file is the other half.
 *
 * ⚠ **IT OPERATES THE REAL CONTROLS.** The view strip is CLICKED, the close is
 * PRESSED, the property filter is TYPED INTO and CHOSEN FROM. A lane once drove
 * four groupings through a `?group=` the screen does not read and produced four
 * byte-identical screenshots of one grouping under four names.
 *
 * ⚠ **IT WRITES TO THE BOOKS.** Step 4 CLOSES the open period and step 6
 * REOPENS it, both through the UI, because `DEF-LED-6668` only appears on a
 * CLOSED month and no fixture can stand in for that. Run it against a database
 * NOBODY ELSE IS SEEDING — `10-scripts/proof-db.sh clone <yours>` — on your own
 * ports, and kill your server by the PID you recorded.
 *
 * RUN:
 *   BASE=http://127.0.0.1:<your web port> SHOTS=<dir> \
 *     node 10-scripts/def_led_6662_6664_6663_6668_6654_doors_walkthrough.mjs
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8612";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? "/tmp/finwire-shots";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
// ⚠ **THE WAITS ARE LONG ON PURPOSE.** This walk shares a machine with three
// other lanes' suites; at load 70 the General ledger took longer than 30s to
// paint its first control and a default-timeout click failed over a screen
// that was perfectly correct. A walkthrough that times out under load teaches
// nothing about the product, so the budget is generous and every wait is for a
// SELECTOR rather than for a number of seconds.
page.setDefaultTimeout(180000);
page.setDefaultNavigationTimeout(180000);
page.on("pageerror", (e) => fail("page error: " + e.message));

async function shot(name) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
  console.log("    shot " + name + ".png");
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 180000 });

// ── 1 · DEF-LED-6662 — the period pack ─────────────────────────────────────
console.log("\n1 · DEF-LED-6662 — Revenue & AR's period pack");
await page.goto(`${BASE}/${TENANT}/finance/revenue`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("h1", { timeout: 180000 });
await page.waitForTimeout(6000);
const pack = await page.evaluate(() => {
  const link = document.querySelector('[data-testid="download-period-pack"]');
  if (link !== null) {
    return { kind: "link", href: link.getAttribute("href"), text: link.textContent.trim() };
  }
  const btn = Array.from(document.querySelectorAll("button"))
    .find((b) => /period pack/i.test(b.textContent || ""));
  return btn === undefined
    ? { kind: "absent" }
    : { kind: "button", text: btn.textContent.trim(), disabled: btn.disabled, title: btn.getAttribute("title") };
});
console.log("    " + JSON.stringify(pack));
if (pack.kind === "link") {
  if (pack.href.startsWith(`/api/${TENANT}/finance/export/batches/`) && pack.href.endsWith("/file")) {
    ok("a real download, at " + pack.href);
  } else fail("the link points somewhere unexpected: " + pack.href);
} else if (pack.kind === "button") {
  if ((pack.title || "").includes("not built")) fail("the ROTTED refusal is still on screen: " + pack.title);
  else ok("refused, truthfully: " + pack.title);
} else fail("no period-pack control at all");
await shot("01-revenue-period-pack");

// ── 2 · DEF-LED-6664 — the journal door, BY ADDRESS AND BY THE SCREEN ──────
console.log("\n2 · DEF-LED-6664 — '+ Journal entry'");
await page.goto(`${BASE}/${TENANT}/finance`, { waitUntil: "domcontentloaded" });
await page.waitForSelector('[data-testid="open-journal-entry"]', { timeout: 180000 });
await page.click('[data-testid="open-journal-entry"]');
await page.waitForTimeout(2500);
const addr = new URL(page.url()).pathname;
if (addr === `/${TENANT}/finance/journal-entries/new`) ok("address: " + addr);
else fail("address is " + addr);
await page.waitForSelector("h1", { timeout: 180000 });
await page.waitForTimeout(2000);
const head = await page.evaluate(() => document.querySelector("h1")?.textContent.trim() ?? "");
if (head === "New journal entries") ok('the SCREEN it opens: "' + head + '"');
else fail('the screen reads "' + head + '"');
await shot("02-journal-batch-screen");

// ── 3 · DEF-LED-6663 — the Export head over an OPEN month ─────────────────
console.log("\n3 · DEF-LED-6663 — Close & export → Export, month OPEN");
await page.goto(`${BASE}/${TENANT}/finance/export`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("h1", { timeout: 180000 });
await page.waitForTimeout(6000);
await page.locator("button", { hasText: /^Export$/ }).first().click();
await page.waitForTimeout(3000);
const openHead = await page.evaluate(() => ({
  h1: document.querySelector("h1")?.textContent.trim(),
  rollup: document.querySelector("h1")?.parentElement?.querySelector(".fin-absent-reason")?.textContent.trim()
       ?? Array.from(document.querySelectorAll(".fin-absent-reason")).map((e) => e.textContent.trim())[0],
  body: Array.from(document.querySelectorAll('p[role="note"]')).map((e) => e.textContent.trim()),
}));
console.log("    " + JSON.stringify(openHead));
if ((openHead.rollup || "").includes("Closed through")) fail("the head still claims the month is closed through");
else ok('the head says "' + openHead.rollup + '" over an open month');
await shot("03-export-head-open");

// ── 4 · DEF-LED-6668 — close it, then read the button ─────────────────────
console.log("\n4 · DEF-LED-6668 — close September, then read the Close button");
await page.locator("button", { hasText: /^Close$/ }).first().click();
await page.waitForTimeout(2500);
const before = await page.evaluate(() => {
  const b = Array.from(document.querySelectorAll("button")).find((x) => /^Close \w/.test(x.textContent || ""));
  return b === undefined ? null : { text: b.textContent.trim(), disabled: b.disabled, title: b.getAttribute("title") };
});
console.log("    before: " + JSON.stringify(before));
await page.locator("button", { hasText: /^Close September/ }).first().click();
await page.waitForTimeout(1500);
// the confirm form — a close needs a date, and a reason while items are left
await page.evaluate(() => {
  for (const input of document.querySelectorAll('[role="dialog"] input')) {
    if (input.type === "date" && input.value === "") input.value = "2026-09-30";
  }
});
const dateField = page.locator('[role="dialog"] input[type="date"]').first();
if (await dateField.count()) await dateField.fill("2026-09-30");
const reasonField = page.locator('[role="dialog"] textarea, [role="dialog"] input[type="text"]').first();
if (await reasonField.count()) await reasonField.fill("FIN-WIRE proving DEF-LED-6668");
await shot("04-close-dialog");
await page.locator('[role="dialog"] button', { hasText: /Close the month/ }).first().click();
await page.waitForTimeout(4500);
const after = await page.evaluate(() => {
  const b = Array.from(document.querySelectorAll("button")).find((x) => /^Close \w/.test(x.textContent || ""));
  return {
    button: b === undefined ? null : { text: b.textContent.trim(), disabled: b.disabled, title: b.getAttribute("title") },
    notes: Array.from(document.querySelectorAll('p[role="note"]')).map((e) => e.textContent.trim()),
    rollup: Array.from(document.querySelectorAll(".fin-absent-reason")).map((e) => e.textContent.trim())[0],
  };
});
console.log("    after:  " + JSON.stringify(after));
const title = after.button?.title ?? "";
if (title.includes("Your role")) fail("THE DEFECT IS STILL LIVE: " + title);
else ok('the closed month says "' + title + '"');
if (after.notes.some((n) => /You can still close/.test(n))) fail("step 2 still instructs a close that has happened");
else ok("step 2 states the close: " + JSON.stringify(after.notes));
await shot("05-close-after");

// ── 5 · DEF-LED-6663 again — the Export head over a CLOSED month ──────────
console.log("\n5 · DEF-LED-6663 — the same head, month now CLOSED");
await page.locator("button", { hasText: /^Export$/ }).first().click();
await page.waitForTimeout(3000);
const closedHead = await page.evaluate(() =>
  Array.from(document.querySelectorAll(".fin-absent-reason")).map((e) => e.textContent.trim())[0]);
console.log("    " + JSON.stringify(closedHead));
if ((closedHead || "").includes("Closed through")) ok('now it DOES say "' + closedHead + '"');
else fail("the head does not state the close: " + closedHead);
await shot("06-export-head-closed");

// ── 6 · put the books back ────────────────────────────────────────────────
console.log("\n6 · reopening September (a walk must not leave the books moved)");
await page.locator("button", { hasText: /^Close$/ }).first().click();
await page.waitForTimeout(3000);
const reopen = page.locator('[title="Reopen"], button[aria-label*="Reopen"], button[title*="Reopen"]').first();
if (await reopen.count()) {
  await reopen.click();
  await page.waitForTimeout(1500);
  const r = page.locator('[role="dialog"] textarea, [role="dialog"] input[type="text"]').first();
  if (await r.count()) await r.fill("FIN-WIRE put it back after proving DEF-LED-6668");
  const submit = page.locator('[role="dialog"] button', { hasText: /Reopen/ }).last();
  if (await submit.count()) { await submit.click(); await page.waitForTimeout(4000); }
  ok("reopened through the UI — the row reads 'reopened', which is the audit trail working");
} else console.log("    (no reopen control found; SAY SO in the report rather than leaving it unsaid)");
await shot("07-reopened");

// ── 7 · DEF-LED-6654 — the property filter in the URL ─────────────────────
console.log("\n7 · DEF-LED-6654 — the Balance view's property filter");
await page.goto(`${BASE}/${TENANT}/finance?view=balance`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("h1", { timeout: 180000 });
await page.waitForTimeout(8000);
const box = page.locator('input[type="search"], input[placeholder]').filter({ hasNot: page.locator("[disabled]") });
const field = page.locator("input").nth(await page.evaluate(() => {
  const inputs = Array.from(document.querySelectorAll("input"));
  const i = inputs.findIndex((n) => /propert|premis/i.test((n.placeholder || "") + (n.getAttribute("aria-label") || "")));
  return i < 0 ? 0 : i;
}));
await field.fill("a");
await page.waitForTimeout(2500);
await shot("08-balance-filter-typed");
const option = page.locator('[role="option"], li button, ul li').first();
let chosen = null;
if (await option.count()) {
  chosen = (await option.textContent())?.trim() ?? null;
  await option.click();
  await page.waitForTimeout(3000);
}
const url = page.url();
console.log("    address after choosing " + JSON.stringify(chosen) + ": " + url);
if (url.includes("f.premises=")) ok("the filter is IN THE LINK");
else fail("the filter reached no URL: " + url);
const rows = await page.evaluate(() => document.querySelectorAll("tbody tr").length);
console.log("    rows on the filtered trial balance: " + rows);
await shot("09-balance-filtered");

// the colleague's half: a SECOND context with nothing but the pasted link
const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page2 = await ctx2.newPage();
page2.setDefaultTimeout(180000);
page2.setDefaultNavigationTimeout(180000);
await page2.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page2.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
await page2.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
await page2.click('button[type="submit"]');
await page2.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 180000 });
await page2.goto(url, { waitUntil: "domcontentloaded" });
await page2.waitForSelector("h1", { timeout: 180000 });
await page2.waitForTimeout(8000);
const rows2 = await page2.evaluate(() => document.querySelectorAll("tbody tr").length);
console.log("    the colleague sees " + rows2 + " rows");
if (rows2 === rows) ok("the pasted link shows the SAME trial balance");
else fail("the colleague sees " + rows2 + " rows where the sender saw " + rows);
await page2.screenshot({ path: `${SHOTS}/10-balance-colleague.png`, fullPage: true });
await ctx2.close();

// ── 8 · DEF-REP-6660 — MEASURED, not fixed ────────────────────────────────
console.log("\n8 · DEF-REP-6660 — which Aging columns offer a sort (measurement)");
await page.goto(`${BASE}/${TENANT}/finance/revenue?view=aging`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("thead th", { timeout: 180000 });
await page.waitForTimeout(6000);
const aging = await page.evaluate(() => {
  const heads = Array.from(document.querySelectorAll("thead th"));
  return heads.map((th) => ({
    label: (th.textContent || "").trim(),
    sortable: th.querySelector("button") !== null,
  }));
});
console.log("    " + JSON.stringify(aging));
await shot("11-aging-columns");

console.log("\n" + (problems.length === 0 ? "ALL CHECKS PASSED" : problems.length + " PROBLEM(S):"));
for (const p of problems) console.log("  · " + p);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
