#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane J — blueprint **screen 28** (Print bills),
//           p147–p150, walked in a browser at both staff widths.
//           Closes `DEF-BIL-5354`.
// Rules:    hard-won law 6 (diff the running app against the drawing — no gate
//           in this repo reads rendered output) · B14 rules 31, 32, 33, 41, 42 ·
//           NFR-3 (the total comes from the database) · CLAUDE.md hard rule 2
//           (money DISPLAYS at two decimals)
// ───────────────────────────────────────────────────────
/**
 * WALK PRINT BILLS AT 1440 AND 1280, READ IT, AND CAPTURE IT.
 *
 *   BASE=http://127.0.0.1:8087 SHOTS=<dir> node 10-scripts/cr101_print_bills_walkthrough.mjs
 *
 * ⚠ **IT NEVER PRESSES `Generate the print set`.** Generating writes an archive
 * and holds a worker for as long as the bills take; this pass reads the screen a
 * clerk reads BEFORE that button, which is the half `DEF-BIL-5354` is about. The
 * button is counted, its state is read, and it is left alone.
 *
 * ⚠ **WHAT IT CANNOT DO, STATED:** it cannot tell you the screen looks like the
 * drawing. It reads presence, order, words and arithmetic; the comparison with
 * p148–p149 is a person putting the capture beside the page.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8087";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/print-bills";
mkdirSync(SHOTS, { recursive: true });

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const INTERNAL = /\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/;
const FOUR_DP = /\d\.\d{4}\b/;

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
}

async function noSidewaysScroll(page, label) {
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (wide) fail(`${label}: the page scrolls sideways`);
  else ok(`${label}: no horizontal scroll`);
}

async function readScreen(page, label) {
  const text = await page.locator("main").innerText();
  note(`\n── ${label} · the screen as a clerk reads it ────────────────────`);
  note(text.replace(/\n{3,}/g, "\n\n"));
  note("────────────────────────────────────────────────────────────────\n");

  // ── the four tiles, and their arithmetic ─────────────────────────────
  const tiles = await page.locator(".kpi").evaluateAll((els) =>
    els.map((el) => ({
      label: el.querySelector(".k")?.textContent?.trim() ?? "",
      value: el.querySelector(".v")?.textContent?.trim() ?? "",
      detail: el.querySelector(".d")?.textContent?.trim() ?? "",
    })),
  );
  note(`  tiles: ${JSON.stringify(tiles)}`);
  if (tiles.length === 4) ok("four tiles, as drawn");
  else fail(`${tiles.length} tiles on screen, not four`);
  const number = (raw) => Number(String(raw).replace(/[^0-9]/g, ""));
  if (tiles.length === 4) {
    const printing = number(tiles[0].value);
    const held = number(tiles[1].value);
    const inPeriod = number(tiles[3].value);
    if (printing + held === inPeriod) ok(`the counts add up — ${printing} + ${held} = ${inPeriod}`);
    else fail(`the counts do NOT add up: ${printing} + ${held} ≠ ${inPeriod}`);
  }

  // ── group 1, the form ────────────────────────────────────────────────
  for (const [what, selector] of [
    ["scope", "[data-print-scope]"],
    ["cycle", "[data-print-cycle]"],
    ["issued from", "[data-print-issued-from]"],
    ["issued to", "[data-print-issued-to]"],
    ["bill run", "[data-print-run]"],
  ]) {
    if (await page.locator(selector).count()) ok(`group 1 offers the ${what} control`);
    else fail(`group 1 has no ${what} control`);
  }
  const facts = await page
    .locator("[data-print-fact]")
    .evaluateAll((els) => els.map((el) => el.innerText.replace(/\n/g, " · ")));
  note(`  facts: ${JSON.stringify(facts)}`);

  // ── group 2, the table ───────────────────────────────────────────────
  const headers = await page.locator("table thead th").allInnerTexts();
  note(`  columns: ${JSON.stringify(headers.map((h) => h.trim()))}`);
  const rows = await page.locator("table tbody tr").count();
  if (rows > 0) ok(`${rows} bill(s) listed`);
  else fail("group 2 lists no bills at all");
  const footer = await page.locator("main").innerText();
  const showing = footer.match(/\b1\s*[–-]\s*\d+\s+of\s+\d+/);
  if (showing) ok(`the pager states the whole population — "${showing[0]}"`);
  else note("  (no 'showing 1–N of M' line matched; the pager may word it differently)");

  const door = page.locator("[data-print-held-door]");
  if (await door.count()) ok(`the held-back door reads — "${(await door.innerText()).trim()}"`);
  else fail("no held-back door");

  // ── the laws that bite on this screen ────────────────────────────────
  if (UUID.test(text)) fail("a database id is visible on the screen");
  else ok("no database id on screen (B14 rule 31)");
  const internal = text.match(INTERNAL);
  if (internal) fail(`an internal id is visible — ${internal[0]}`);
  else ok("no rule, question or defect id on screen (B14 rule 32)");
  const money = text.match(FOUR_DP);
  if (money) fail(`money is drawn to four decimals — ${money[0]}`);
  else ok("money displays at two decimals (hard rule 2)");
  for (const code of ["address_incomplete", "no_bill_number", "unsafe_bill_number"]) {
    if (text.includes(code)) fail(`a hold reason CODE reached the clerk — ${code}`);
  }

  // ── the primary, read and NOT pressed ────────────────────────────────
  const primary = page.locator("button", { hasText: /Generate the print set/ }).first();
  if (await primary.count()) {
    const disabled = await primary.isDisabled();
    const reason = (await primary.getAttribute("title")) ?? "";
    ok(`the primary reads "Generate the print set" · disabled=${disabled} · reason="${reason}"`);
  } else fail("no 'Generate the print set' control");

  await noSidewaysScroll(page, label);
}

async function walk(width, height, tag) {
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  page.on("pageerror", (e) => fail(`page error: ${e.message}`));
  await signIn(page);
  await page.goto(`${BASE}/${TENANT}/billing/print`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-print-scope]", { timeout: 60000 });
  await page.waitForSelector("table tbody tr", { timeout: 60000 }).catch(() => {});
  // ⚠ **WAIT FOR THE TILES, AND THE REASON IS MEASURED.** `GET /billing/
  // print-sets` also asks whether a worker would run the job (`would_run` →
  // `dispatch_is_ready`), and on a stack with no broker that probe takes
  // **6.048 s** — measured on this machine 2026-09-15 — against 0.026 s for the
  // whole four-count forecast beside it. A 700 ms wait captured four empty
  // tiles and would have published a screenshot of the wrong screen.
  await page.waitForSelector(".kpi .v", { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(700);
  await readScreen(page, `${width}px`);
  await page.screenshot({ path: `${SHOTS}/print-bills-${tag}-full.png`, fullPage: true });

  // The held-back door, pressed — it narrows this table and offers the way back.
  const door = page.locator("[data-print-held-door]");
  if (await door.count()) {
    await door.click();
    await page.waitForTimeout(1500);
    const after = (await door.innerText()).trim();
    note(`  after pressing the door, it reads — "${after}"`);
    const rows = await page.locator("table tbody tr").count();
    note(`  held-only rows: ${rows}`);
    await page.screenshot({ path: `${SHOTS}/print-bills-${tag}-held-only.png`, fullPage: true });
    await door.click();
    await page.waitForTimeout(700);
  }

  // A cycle scope, which is the drawing's own default scope.
  const scope = page.locator("[data-print-scope]");
  await scope.selectOption("cycle");
  await page.waitForTimeout(600);
  const cycle = page.locator("[data-print-cycle]");
  const options = await cycle.locator("option").allInnerTexts();
  note(`  cycle options: ${JSON.stringify(options.slice(0, 6))}`);
  if (options.length > 1) {
    await cycle.selectOption({ index: 1 });
    // The preview is re-asked for the new scope, so the broker probe is paid
    // again — see the note above.
    await page.waitForTimeout(9000);
    const tiles = await page.locator(".kpi .v").allInnerTexts();
    note(`  tiles for that cycle: ${JSON.stringify(tiles)}`);
    await page.screenshot({ path: `${SHOTS}/print-bills-${tag}-cycle.png`, fullPage: true });
  }
  await context.close();
}

/**
 * THE HELD STATE, SEEDED THE WAY A CLERK WOULD AND PUT BACK AFTERWARDS.
 *
 * ⚠ **THE DEMO TENANT HOLDS NO HELD BILL, AND THAT IS ITSELF INFORMATION:**
 * all 79 printable bills have a complete mailing address, so the drawn
 * *"8 held back, each with a reason"* has no real row to stand on. Rather than
 * writing one behind the product's back, this takes a mailing address the way
 * the product lets a clerk take it — `PATCH /accounts/{id}/mailing-address`,
 * the route the account screen posts to — clears the CITY, reads the screen,
 * and **puts the city back**. `BR-NOT-029` (b) names city, state and postal
 * code as the three that hold a bill.
 */
async function walkHeld(width, height, tag) {
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  await signIn(page);

  const listed = await page.request.fetch(
    `${BASE}/api/${TENANT}/billing/print-sets/bills?page=1&per=1`,
  );
  const first = (await listed.json()).results[0];
  if (!first) {
    fail("no bill to seed a held state from");
    await context.close();
    return;
  }
  const account = first.account_id;
  const before = await page.request.fetch(`${BASE}/api/${TENANT}/accounts/${account}`);
  const held = await before.json().catch(() => ({}));
  const city = held?.mailing_address?.city ?? held?.addresses?.[0]?.city ?? "San Antonio";
  note(`\n── seeding a held bill on ${first.account_no} (city was "${city}") ──`);

  const cleared = await page.request.fetch(
    `${BASE}/api/${TENANT}/accounts/${account}/mailing-address`,
    { method: "PATCH", data: { city: "" } },
  );
  note(`  clearing the city answered ${cleared.status()}`);
  if (cleared.status() >= 400) {
    note(`  ${(await cleared.text()).slice(0, 200)}`);
  }

  await page.goto(`${BASE}/${TENANT}/billing/print`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".kpi .v", { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(800);
  const tiles = await page.locator(".kpi .v").allInnerTexts();
  note(`  tiles with one bill held: ${JSON.stringify(tiles)}`);
  const door = page.locator("[data-print-held-door]");
  note(`  the door now reads — "${(await door.innerText()).trim()}"`);
  await door.click();
  await page.waitForTimeout(1500);
  const rows = await page.locator("table tbody tr").allInnerTexts();
  note(`  held row: ${JSON.stringify(rows.slice(0, 2))}`);
  await page.screenshot({ path: `${SHOTS}/print-bills-${tag}-held-state.png`, fullPage: true });

  // ⚠ PUT IT BACK. A walk that leaves the demo tenant changed is a walk that
  // reports on a world the next lane cannot reproduce.
  const restored = await page.request.fetch(
    `${BASE}/api/${TENANT}/accounts/${account}/mailing-address`,
    { method: "PATCH", data: { city } },
  );
  note(`  putting the city back answered ${restored.status()}`);
  await context.close();
}

await walk(1440, 1000, "1440");
await walk(1280, 900, "1280");
if (process.env.SEED_HELD === "1") {
  await walkHeld(1440, 1000, "1440");
}
await browser.close();

note(`\nshots in ${SHOTS}`);
if (problems.length) {
  note(`\n${problems.length} problem(s):`);
  for (const one of problems) note("  · " + one);
  process.exit(1);
}
note("\nno problems found by this walk — the comparison with p148–p149 is a person's");
