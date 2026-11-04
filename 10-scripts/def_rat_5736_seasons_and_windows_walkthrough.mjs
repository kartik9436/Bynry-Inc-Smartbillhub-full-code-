// ── Trace ──────────────────────────────────────────────
// Defects: DEF-RAT-5736 (two unrelated panels + a per-window Season dropdown) ·
//          DEF-RAT-5733 (a season boundary typed as four free numeric boxes) ·
//          DEF-RAT-5734 (step 2 pre-listed every size class) ·
//          DEF-RAT-5735 (the rate wizard's text against B14 rule 33)
// Question: OQ-RAT-12410, CLOSED by the PO's approval of this design 2026-09-18
// Rules:   B14 rule 33 · rule 32 c3 · rule 8 / BR-SHL-033 · BR-RAT-033/034 ·
//          BR-RAT-067
// ───────────────────────────────────────────────────────
/**
 * Walk the redrawn step 2 and step 3 in a real browser — hard-won law 6.
 *
 *     BASE=http://127.0.0.1:8390 node 10-scripts/def_rat_5736_seasons_and_windows_walkthrough.mjs
 *
 * ⚠ **IT ASSERTS THE DATA EXISTS AND THE CALL SUCCEEDED BEFORE CLAIMING A PASS.**
 * One walkthrough on this branch printed "ALL CHECKS PASSED" over a 404 and
 * another printed "WALK CLEAN" over a tenant with zero rows, so every step here
 * proves its own precondition first.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8390";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp";

const problems = [];
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1500 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
ok("signed in");

const resp = await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`, { waitUntil: "domcontentloaded" });
if (resp.status() >= 400) { fail(`rates/new returned HTTP ${resp.status()}`); }
else ok(`rates/new returned HTTP ${resp.status()}`);
await page.waitForTimeout(3000);

// ── step 1 ────────────────────────────────────────────────────────────────
await page.fill("#rate-name", "DEF-RAT-5736 walkthrough");
await page.locator("#rate-service").selectOption({ index: 1 });
await page.waitForTimeout(1500);
const uomCount = await page.locator("#rate-uom option").count();
if (uomCount <= 1) fail("the unit picker is EMPTY — the walk would prove nothing");
else ok(`unit picker holds ${uomCount - 1} unit(s)`);
await page.locator("#rate-uom").selectOption({ index: 1 });
await page.waitForTimeout(500);
await page.locator('button:has-text("Continue")').first().click();
await page.waitForTimeout(1500);

// ── step 2 · DEF-RAT-5734 ────────────────────────────────────────────────
console.log("\nSTEP 2 — pick, price, then Add");
const offered = await page.locator("#size-pick option").count();
if (offered <= 1) fail("the size picker is EMPTY — nothing to add, so nothing is proved");
else ok(`the picker offers ${offered - 1} size(s)`);
const preListedRows = await page.locator('[data-editable-table="rate-schedule-sizes"] tbody tr').count();
if (preListedRows !== 0) fail(`${preListedRows} row(s) are pre-listed — nothing should be until Add`);
else ok("no rows are pre-listed");
const emptyText = await page.locator("[data-editable-empty]").innerText();
ok(`the empty table says: ${JSON.stringify(emptyText)}`);
await page.screenshot({ path: `${SHOTS}/after-02-step2-picker.png`, fullPage: true });

await page.locator("#size-pick").selectOption({ index: 1 });
await page.fill("#size-pick-minimum", "18.00");
await page.locator('button:has-text("Add size")').first().click();
await page.waitForTimeout(700);
const rowsNow = await page.locator('[data-editable-table="rate-schedule-sizes"] tbody tr').count();
if (rowsNow !== 1) fail(`Add produced ${rowsNow} row(s), expected 1`);
else ok("Add produced exactly one row");
if (await page.locator('[data-move="up"]').count() > 0) fail("a reorder control is drawn on a collection with no order");
else ok("no reorder handle, no up, no down");
// ⚠ **THE FIRST VERSION OF THIS CHECK COUNTED THE DOM AND FAILED ON A CORRECT
// FIX.** `label:has-text()` matches an `sr-only` label perfectly well, and an
// sr-only label is the POINT — the name is announced and not drawn. So ask the
// browser what the reader sees: the label must EXIST (a screen reader still
// needs it) and must NOT be visible. This is B14 rule 31's own lesson one
// component over — read what is rendered, never the markup.
const rowLabel = page.locator('label:has-text("Minimum rate for")');
const labelCount = await rowLabel.count();
if (labelCount !== 1) fail(`the accessible per-row name is missing (${labelCount} found)`);
else ok("the accessible per-row name is present");
const drawn = await rowLabel.first().evaluate((el) => {
  const box = el.getBoundingClientRect();
  return box.left >= 0 && box.top >= 0 && box.width > 1 && box.height > 1;
});
if (drawn) fail("the per-row label is still DRAWN beside its own column header");
else ok("the per-row label is announced, not drawn");
const attributions = await page.locator("text=Read-only · from").count();
if (attributions > 1) fail(`the attribution is repeated ${attributions} times`);
else ok(`the attribution appears ${attributions} time(s)`);
await page.screenshot({ path: `${SHOTS}/after-03-step2-added.png`, fullPage: true });

// ── step 3 · DEF-RAT-5736 / 5733 ─────────────────────────────────────────
console.log("\nSTEP 3 — seasons and their windows");
await page.locator('button:has-text("Continue")').first().click();
await page.waitForTimeout(1500);
await page.locator("#rate-model").selectOption("time_of_use");
await page.waitForTimeout(1200);

const headings = (await page.locator("h3").allTextContents()).map((s) => s.trim()).filter(Boolean);
ok(`panel headings: ${JSON.stringify(headings)}`);
if (headings.includes("Seasons") || headings.includes("Time-of-use windows"))
  fail("the two old panels are still drawn");
else ok("ONE panel, not two");

await page.locator('button:has-text("Add season")').first().click();
await page.waitForTimeout(500);
await page.fill("#season-label-0", "Summer");
await page.locator("#season-start-0-month").selectOption("4");
await page.waitForTimeout(300);
const aprilDays = await page.locator("#season-start-0-day option").count();
if (aprilDays - 1 !== 30) fail(`April offers ${aprilDays - 1} days, expected 30`);
else ok("April offers exactly 30 days — 31 April is unselectable");
await page.locator("#season-start-0-day").selectOption("1");
await page.locator("#season-end-0-month").selectOption("9");
await page.locator("#season-end-0-day").selectOption("30");
await page.waitForTimeout(600);
const echo = await page.locator('[data-season-range="s0"]').innerText().catch(() => "");
if (echo.trim() !== "1 Apr – 30 Sep") fail(`the range echoed ${JSON.stringify(echo)}`);
else ok(`the range echoes back: ${JSON.stringify(echo.trim())}`);

const feb = await page.locator("#season-end-0-month").selectOption("2").then(() => page.waitForTimeout(300))
  .then(() => page.locator("#season-end-0-day option").count());
if (feb - 1 !== 28) fail(`February offers ${feb - 1} days, expected 28 (the server's 2001 reference year)`);
else ok("February offers 28 days — the server's own non-leap reference year");
await page.locator("#season-end-0-month").selectOption("9");
await page.locator("#season-end-0-day").selectOption("30");
await page.waitForTimeout(400);

const issue = await page.locator("[data-season-issue]").innerText().catch(() => "");
if (issue === "") fail("one season covering half the year raised NO coverage message");
else ok(`the gap is named while typing: ${JSON.stringify(issue.trim())}`);

await page.locator('[data-add-window="s0"]').click();
await page.waitForTimeout(600);
if (await page.locator("#window-season-0").count() > 0) fail("the window still carries a Season dropdown");
else ok("the window has NO Season dropdown");
const insideSeason = await page.locator('[data-season="s0"] #window-label-0').count();
if (insideSeason !== 1) fail("the window is not nested inside its season");
else ok("the window renders inside its season");
await page.screenshot({ path: `${SHOTS}/after-04-step3-tou.png`, fullPage: true });

await page.locator('button:has-text("Add season")').first().click();
await page.waitForTimeout(400);
await page.fill("#season-label-1", "Winter");
await page.locator("#season-start-1-month").selectOption("10");
await page.locator("#season-start-1-day").selectOption("1");
await page.locator("#season-end-1-month").selectOption("3");
await page.locator("#season-end-1-day").selectOption("31");
await page.waitForTimeout(700);
const settled = await page.locator("[data-season-issue]").count();
if (settled !== 0) fail("two seasons tiling the year still report a coverage problem");
else ok("two seasons tiling the year report nothing");
await page.locator('[data-add-window="s1"]').click();
await page.waitForTimeout(500);
await page.screenshot({ path: `${SHOTS}/after-05-step3-two-seasons.png`, fullPage: true });

// ── the seasonal mode ────────────────────────────────────────────────────
console.log("\nSTEP 3 — the same panel, seasonal mode");
await page.locator("#rate-model").selectOption("seasonal");
await page.waitForTimeout(1200);
const seasonalHeads = (await page.locator("h3").allTextContents()).map((s) => s.trim()).filter(Boolean);
ok(`panel headings: ${JSON.stringify(seasonalHeads)}`);
if (await page.locator('[data-add-window="s0"]').count() > 0) fail("seasonal mode still draws a windows block");
else ok("seasonal mode draws no windows");
if (await page.locator("#season-price-0").count() !== 1) fail("seasonal mode has no per-season price");
else ok("seasonal mode carries a price per season");
await page.screenshot({ path: `${SHOTS}/after-06-step3-seasonal.png`, fullPage: true });

console.log(problems.length === 0 ? "\nWALK CLEAN — every precondition asserted" : `\n${problems.length} PROBLEM(S)`);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
