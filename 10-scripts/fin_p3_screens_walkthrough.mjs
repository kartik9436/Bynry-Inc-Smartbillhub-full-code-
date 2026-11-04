// ── Trace ──────────────────────────────────────────────
// Task:    Finance blueprint Phase 3 — `P3.1` the accruals workbench (1·4) ·
//          `P3.2` reopen a period (6·1b) · `P3.3` refund detail (2·5d) ·
//          `P3.4` the GL map save (1·3) · `P3.5` **every door asserted by
//          ADDRESS and by the SCREEN IT OPENS**.
// Drawing: 05-prototype/07 Finance Blueprint.pdf p026–p028 · p046–p047 ·
//          p068 · p072–p073, rendered as IMAGES (B14 rule 42).
// Rules:   CLAUDE.md hard-won law 6 — *"diff the running app against the
//          drawing; no gate looks at rendered output"* · hard-won law 2 and
//          its MIRROR (a live screen behind a dead control).
// ───────────────────────────────────────────────────────
/**
 * **THIS IS THE ONLY CHECK IN THE REPOSITORY THAT READS RENDERED OUTPUT, AND
 * IT IS A PERSON LOOKING AT THE SHOTS IT TAKES.**
 *
 * Every one of Phase 3's four screens is a DOOR onto a backend that was already
 * finished, tested and unreachable. A green suite proves the endpoint exists; a
 * screenshot of the accruals workbench listing real accruals is the difference
 * between that and *a clerk can post the accrual*.
 *
 * ⚠ **IT ASSERTS EACH DOOR BY ADDRESS AND BY THE SCREEN IT OPENS** (`P3.5`).
 * A hold-expiry test once asserted a screen was REGISTERED at one address while
 * the router mounted it at another, and both opened onto *"not built yet"*. So
 * every check below clicks the control a person would click, reads the address
 * bar, AND reads a string only the destination screen renders.
 *
 * RUN:
 *   BASE=http://127.0.0.1:8972 SHOTS=<dir> node 10-scripts/fin_p3_screens_walkthrough.mjs
 *
 * ⚠ **AGAINST A DATABASE NOBODY ELSE IS SEEDING** — `10-scripts/proof-db.sh
 * clone <yours>` — and **on your own ports**. Kill your server by the PID you
 * recorded; matching on a process name kills every lane's.
 *
 * ⚠ **BOOT THROUGH `07-frontend/server.mjs`, NOT `vite`.** That server IS the
 * deployed join, so the walk exercises what a clerk actually gets.
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/finp3-shots";

mkdirSync(SHOTS, { recursive: true });

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail("page error: " + e.message));

/**
 * ⚠ **THE PAGE BODY SCROLLS INSIDE THE SHELL, SO `fullPage` IS NOT ENOUGH.**
 * The app frame is fixed and the content scrolls in its own box, so Playwright's
 * `fullPage` captures the VIEWPORT and nothing below it — the first run of this
 * file photographed the chart's loading skeleton and called it the GL map.
 *
 * ⚠ **AND `fullPage: true` THEREFORE DID NOTHING AT ALL** (`DEF-GOV-6645`). The
 * document IS the window here, so every shot this file wrote came out exactly
 * one screenful — eleven images, every one 1440x1100 — and a screen taller than
 * that lost its lower half with nothing to show it had. **Two shots is the
 * answer rather than one tall one:** a fixed sidebar stretched to a 2,000px
 * canvas photographs as a dark band over white, which looks like a broken
 * screen, and the point of these pictures is to show the PO what a clerk sees.
 * So a screen that scrolls is photographed as the person reads it — the head,
 * then the foot — and the second is named `-lower`.
 *
 * `anchor` is the selector to bring into view first. **The page head stays
 * visible in every shot** (the coordinator's own requirement, and the first
 * thing the PO checks), so a shot with an anchor is taken in TWO parts: the
 * head, then the anchored section, and the anchored one is named `-detail`.
 *
 * ⚠ **A SECOND FILE IS WRITTEN ONLY IF ITS BYTES DIFFER.** When the anchor was
 * already on screen, `-detail` was a byte-identical copy of the shot above it —
 * and a file named *detail* that is not a detail tells a reader something was
 * looked at closely when nothing was. Same for `-lower` on a screen that does
 * not scroll.
 */
async function writeIfNew(name, buffer, twin) {
  if (twin !== undefined && buffer.equals(twin)) {
    console.log(`    (no ${name}.png — it would be a copy of the shot above it)`);
    return false;
  }
  writeFileSync(`${SHOTS}/${name}.png`, buffer);
  console.log(`    shot ${name}.png`);
  return true;
}

/**
 * The box the content actually scrolls in, or null when the screen fits.
 *
 * ⚠ **`> 120px` RATHER THAN `> 0`, AND A DIALOG COUNTS AS THE WHOLE SCREEN.**
 * A first version asked only whether the box could scroll at all, and a page
 * ten pixels taller than the window produced a `-lower` shot that is the shot
 * above it with the head nudged up — eight near-identical pictures for a person
 * to compare by eye. And while a dialog is open, the PAGE behind it scrolls: the
 * dialog is what the shot is of, so a second one of the same dialog over
 * different wallpaper says nothing.
 */
async function scrollBox() {
  return await page.evaluate(() => {
    if (document.querySelector('[role="dialog"]') !== null) return null;
    const boxes = Array.from(document.querySelectorAll("main, main *, body, html")).filter(
      (el) => {
        const style = getComputedStyle(el);
        return /auto|scroll/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 120;
      },
    );
    if (boxes.length === 0) return null;
    const box = boxes[0];
    return { height: box.scrollHeight, visible: box.clientHeight };
  });
}

async function shot(name, anchor) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    for (const el of document.querySelectorAll("main, main *")) {
      if (el.scrollTop > 0) el.scrollTop = 0;
    }
  });
  await page.waitForTimeout(250);
  const head = await page.screenshot({ fullPage: true });
  writeFileSync(`${SHOTS}/${name}.png`, head);
  console.log(`    shot ${name}.png`);

  const box = await scrollBox();
  if (box !== null) {
    await page.evaluate(() => {
      for (const el of document.querySelectorAll("main, main *")) {
        if (el.scrollHeight > el.clientHeight + 4) el.scrollTop = el.scrollHeight;
      }
      window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(400);
    await writeIfNew(`${name}-lower`, await page.screenshot(), head);
    await page.evaluate(() => {
      for (const el of document.querySelectorAll("main, main *")) {
        if (el.scrollTop > 0) el.scrollTop = 0;
      }
      window.scrollTo(0, 0);
    });
    await page.waitForTimeout(250);
  }

  if (anchor !== undefined) {
    const target = page.locator(anchor).first();
    if ((await target.count()) > 0) {
      await target.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
      await writeIfNew(`${name}-detail`, await page.screenshot(), head);
    }
  }
}

console.log("\n── sign in ────────────────────────");
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
ok("signed in");

// ══════════════════════════════════════════════════════════════════════════
// P3.1 · 1·4 ACCRUALS — the workbench over four engines with zero callers
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── P3.1 · 1·4 Accruals workbench ────────");
await page.goto(`${BASE}/${TENANT}/finance?view=accruals`, { waitUntil: "domcontentloaded" });
await page.waitForSelector('[data-testid="accruals-post-all"]', { timeout: 30000 });
// ⚠ **WAIT FOR THE TABLE BODY, NOT FOR THE BUTTON.** `Post all` is in the
// panel head and renders while `DataTable` is still showing its skeleton — so
// a walk that proceeds on the button alone reads the COLUMNS and the *Never*
// cells before there is a table at all, and reports six failures over a
// perfectly correct screen. That happened on the first run of this file, which
// is hard-won law 7's *looking at the wrong thing*: the check was measuring how
// far the render had got.
await page.waitForSelector("table tbody tr", { timeout: 30000 });
// The four engines, by the words the drawing puts in the ENTRY column.
for (const entry of ["Unbilled revenue", "Unpaid costs", "Depreciation", "Bad-debt allowance"]) {
  const seen = await page.getByText(entry, { exact: true }).count();
  if (seen > 0) ok(`ENTRY row present: ${entry}`);
  else fail(`ENTRY row MISSING: ${entry}`);
}
// ⚠ The two columns that stop the $40,000 error.
for (const column of ["Type", "Reverses", "Basis", "Amount", "State"]) {
  const seen = await page.locator("table thead th", { hasText: new RegExp(`^${column}$`) }).count();
  if (seen > 0) ok(`column present: ${column}`);
  else fail(`column MISSING: ${column}`);
}
const neverCells = await page.getByText("Never", { exact: true }).count();
if (neverCells >= 2) ok(`"Never" on ${neverCells} rows — depreciation and the allowance do not reverse`);
else fail(`"Never" on ${neverCells} row(s); the drawing has TWO standard entries`);
await shot("p3-1-accruals-workbench");

// The 👁 opens the engine's lines IN PLACE — p027's Components table.
const previewButtons = page.getByRole("button", { name: "See the lines" });
if ((await previewButtons.count()) > 0) {
  // ⚠ **THE ROW WITH SOMETHING TO POST, NOT THE FIRST ONE.** `.first()` lands on
  // the bad-debt allowance, which is already posted this period, so the panel
  // opens saying *"Nothing to post this period."* — a true answer and a useless
  // picture of a control whose whole job is to show the lines. This picks an
  // engine that has lines, and falls back to the first row if none has.
  const unbilled = page.getByRole("row", { name: /Unbilled revenue/ }).first();
  const onARowWithLines = unbilled.getByRole("button", { name: "See the lines" });
  const target = (await onARowWithLines.count()) > 0 ? onARowWithLines : previewButtons.first();
  await target.click();
  await page.waitForTimeout(800);
  const opened = await page.getByText("the lines", { exact: false }).count();
  if (opened > 0) ok("\u{1F441} opens the engine's lines");
  else fail("\u{1F441} opened nothing");
  await shot("p3-1-accruals-preview");
} else {
  fail("no \u{1F441} preview control on any row");
}

// ══════════════════════════════════════════════════════════════════════════
// P3.4 · 1·3 CHART — the GL map, now saved on one screen
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── P3.4 · 1·3 GL map save ────────────");
await page.goto(`${BASE}/${TENANT}/finance?view=chart`, { waitUntil: "domcontentloaded" });
// The chart is a bounded DataTable and the map sits below it; wait for BOTH,
// or the shot photographs a loading skeleton (which the first run did).
// ⚠ **`table tbody tr` IS NOT THAT WAIT AND IT LOOKED LIKE IT WAS.** This screen
// holds SEVERAL tables, and the roles map below the chart arrives first — so the
// wait was satisfied by a different table while the accounts list was still grey
// bars, and the shot went on photographing the skeleton this line was written to
// prevent. The honest wait is *no skeleton left anywhere on the screen*.
await page.waitForSelector("table tbody tr", { timeout: 30000 });
await page.waitForSelector('[data-testid="gl-map-save"]', { timeout: 30000 });
await page.waitForFunction(() => document.querySelector('[aria-busy="true"]') === null, {
  timeout: 30000,
});
ok("the map carries a Save on the screen that shows it");
const stale = await page.getByText("Settings → Services", { exact: false }).count();
if (stale === 0) ok("the *Settings → Services* sentence is gone");
else fail(`the *Settings → Services* sentence is still on screen (${stale})`);
const saveDisabled = await page.locator('[data-testid="gl-map-save"]').isDisabled();
if (saveDisabled) ok("Save is disabled while nothing has moved");
else fail("Save is live over an unchanged map");
await shot("p3-4-gl-map-save", '[data-testid="gl-map-save"]');

// ══════════════════════════════════════════════════════════════════════════
// P3.2 · 6·1b REOPEN — the door on 6·1's closed months
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── P3.2 · 6·1b Reopen a period ───────");
await page.goto(`${BASE}/${TENANT}/finance/export`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
await shot("p3-2-close-and-export", '[data-testid="reopen-period"], .fin-journal-state');
const reopen = page.getByRole("button", { name: "Reopen" });
if ((await reopen.count()) > 0) {
  await reopen.first().click();
  await page.waitForTimeout(800);
  const dialog = await page.getByText("Entries can be dated back in.", { exact: false }).count();
  if (dialog > 0) ok("↺ opens 6·1b, and the dialog says what happens");
  else fail("↺ opened something that is not 6·1b");
  const reasonField = await page.locator("#reopen-period-reason").count();
  if (reasonField > 0) ok("the reason field is on the dialog");
  else fail("no reason field — BR-LED-006 requires one");
  await shot("p3-2-reopen-a-period");
  await page.keyboard.press("Escape");
} else {
  fail("NO ↺ REOPEN CONTROL on any closed month — the door P3.2 exists to build");
}

// ══════════════════════════════════════════════════════════════════════════
// P3.3 · 2·5d REFUND DETAIL — and P3.5's door, by address AND by screen
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── P3.3 · 2·5d Refund detail ─────────");
// ⚠ **`?view=refunds` — THE QUEUE MOVED INTO A VIEW ON 2026-09-24 (`P2.18`).**
// Revenue & AR became five views the same day this lane was building, so the
// bare address lands on *services* and the queue is not on the page at all.
// A walk that kept the bare address would report "no refund to open" over a
// perfectly good queue — the same *looking at the wrong thing* this file's
// `shot` header records, one screen along.
await page.goto(`${BASE}/${TENANT}/finance/revenue?view=refunds`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(3000);
await shot("p3-3-refunds-queue");
// The DOOR: the refund's reference on 2·5 Refunds.
const queue = page.locator(".pay-writeoff-rows button");
if ((await queue.count()) > 0) {
  await queue.first().click();
  await page.waitForTimeout(2500);
  const url = new URL(page.url());
  // ⚠ P3.5 — the ADDRESS…
  if (/^\/brazosbend\/finance\/refunds\/[^/]+$/.test(url.pathname)) {
    ok(`door resolves to the address: ${url.pathname}`);
  } else {
    fail(`door resolved to ${url.pathname}, not /:tenant/finance/refunds/:id`);
  }
  // …AND the SCREEN it opens, by a string only 2·5d renders.
  const whose = await page.getByText("Whose money", { exact: true }).count();
  if (whose > 0) ok("…and it opens 2·5d (its *Whose money* section)");
  else fail("the address resolved but 2·5d did not render");
  await shot("p3-3-refund-detail");
} else {
  fail("no refund in the queue to open — seed one and re-run");
}

// ══════════════════════════════════════════════════════════════════════════
// 1280 — the laptop minimum. Everything must work here (no clipping).
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── 1280 ───────────────────────");
await page.setViewportSize({ width: 1280, height: 1000 });
// The third member is the ANCHOR — the control this task built, so the 1280 set
// shows it rather than only proving the page does not scroll sideways. The GL
// map editor sits below a 60-row chart, and a shot of the chart at 1280 says
// nothing about the thing `P3.4` added.
for (const [name, path, anchor] of [
  ["p3-1-accruals-workbench-1280", "finance?view=accruals", undefined],
  ["p3-4-gl-map-save-1280", "finance?view=chart", '[data-testid="gl-map-save"]'],
  ["p3-2-close-and-export-1280", "finance/export", undefined],
]) {
  await page.goto(`${BASE}/${TENANT}/${path}`, { waitUntil: "domcontentloaded" });
  // Wait for a real table rather than for the clock — a timeout photographs
  // whatever the render had reached, which is the fault the head of `shot`
  // records.
  await page.waitForSelector("table tbody tr", { timeout: 30000 }).catch(() => undefined);
  await page.waitForTimeout(800);
  // ⚠ **THE SCROLL BOX IS THE SHELL'S MAIN, NOT THE DOCUMENT.** Reading
  // `documentElement.scrollWidth` on a page whose body never scrolls answers a
  // question about the wrong element and can only ever say *no overflow* — a
  // check incapable of failing. This asks every scrollable box on the page.
  const overflow = await page.evaluate(() => {
    const boxes = [document.documentElement, ...document.querySelectorAll("main, [role=main]")];
    return boxes.some((box) => box.scrollWidth > box.clientWidth + 1);
  });
  if (overflow) fail(`${name}: something scrolls sideways at 1280`);
  else ok(`${name}: no horizontal scroll at 1280`);
  await shot(name, anchor);
}

console.log("\n── verdict ───────────────────");
if (problems.length === 0) {
  console.log("  every check passed");
} else {
  console.log(`  ${problems.length} problem(s):`);
  for (const p of problems) console.log("    · " + p);
}
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
