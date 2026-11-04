#!/usr/bin/env node
// Walk — reading gaps C, B and Enter opening read (Accounts lane), 2026-10-17.
// DEF-CUS-10165 (Move-in step 1 read date) · DEF-CUS-10166 (Mark as cut
// closing reading + date + Fetch) · DEF-CUS-10167 (Enter opening read date +
// Fetch). Decision log "WHERE A USER ENTERS A METER READING".
//
// Usage (a PRIVATE database copy — this COMMITS a move-in, a cut and an
// opening read):
//   WR_BASE=http://127.0.0.1:8103 node 10-scripts/walk_reading_gaps_accounts_2026_10_17.mjs
//
// Env: WR_UNIT (move-in unit label substring), WR_CASE (disconnect case),
// WR_MOVE (a committed move-in waiting on a read), WR_ASSETS (JSON map of
// meter number -> asset id, for the read-history screenshots).
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.WR_BASE || "http://127.0.0.1:8103";
const T = "brazosbend";
const OUT = process.env.WR_OUT || "05-prototype/walk-reading-gaps-accounts-2026-10-17";
const UNIT = process.env.WR_UNIT || "U-00318-101";
const CASE = process.env.WR_CASE || "DSC-26-0002";
const MOVE = process.env.WR_MOVE || "MVI-26-0022";
const ASSETS = JSON.parse(process.env.WR_ASSETS || "{}");
// WR_SKIP=C,B re-runs only what is left after a section already COMMITTED
// (its read-history shots are still taken from WR_ASSETS).
const SKIP = (process.env.WR_SKIP || "").split(",");

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
const shot = async (name, target = page, scrollTo = null) => {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
  // The app frame scrolls inside its own container, so a full-page shot is the
  // viewport: bring the part under test into view first.
  if (scrollTo) await page.locator(scrollTo).first().scrollIntoViewIfNeeded();
  await target.screenshot({ path: join(OUT, name), ...(target === page ? { fullPage: true } : {}) });
  console.log(`  shot ${name}`);
};
const settle = async () => {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(700);
};
async function typeDate(selector, value) {
  await page.fill(selector, "");
  await page.fill(selector, value);
  await page.keyboard.press("Tab");
  await page.waitForTimeout(300);
}
async function fetchSaid(meter, scope = page) {
  const box = scope.locator(`[data-fetch-reading="${meter}"]`);
  await box.getByRole("button").click();
  const said = box.locator("[data-fetch-reading-state]");
  await said.waitFor({ timeout: 15000 }).catch(() => undefined);
  return ((await said.textContent().catch(() => "")) ?? "").trim();
}
async function readHistory(meter, name) {
  if (!ASSETS[meter]) return;
  await page.goto(`${BASE}/${T}/assets/${ASSETS[meter]}?tab=reads`, { waitUntil: "domcontentloaded" });
  await settle();
  await shot(name);
}

await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

try {
  // ── C · Move-in step 1 — a read date per meter ────────────────────────────
  if (SKIP.includes("C")) {
    await readHistory("M-7301", "C5-read-history-opening-read-dated-10-12.png");
  } else {
  console.log("C · Move-in step 1");
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#mvi_unit option:nth-child(2)", { state: "attached" });
  const options = await page.$$eval("#mvi_unit option", (ns) => ns.map((o) => ({ value: o.value, label: o.textContent.trim() })));
  const unit = options.find((o) => o.label.includes(UNIT));
  check(`vacant unit ${UNIT} offered`, unit !== undefined);
  await page.selectOption("#mvi_unit", unit.value);
  await settle();
  await typeDate("#opened_at", "10/15/2026");
  await settle();
  const meter = await page.locator("[data-opening-read]").first().getAttribute("data-opening-read");
  const dateSel = `#moveIn-open-read-${meter}-date`;
  check("Read date opens on the move-in date", (await page.inputValue(dateSel)) === "10/15/2026", await page.inputValue(dateSel));
  check("no Estimate control on move-in", (await page.getByLabel(/Estimate/).count()) === 0);
  await page.fill(`#moveIn-open-read-${meter}-value`, "9150");
  await typeDate(dateSel, "10/30/2026");
  check("a date after today is refused", (await page.getByText("Read date is after today.").count()) > 0);
  await shot("C1-move-in-future-read-date-refused.png", page, '[data-array="move-in-meters"]');
  await typeDate(dateSel, "07/15/2026");
  check("a date before the last reading is refused", (await page.getByText("Earlier than the last reading.").count()) > 0);
  await shot("C2-move-in-before-last-refused.png", page, '[data-array="move-in-meters"]');
  await typeDate(dateSel, "10/12/2026");
  check("an earlier lawful date (before the move-in day) is accepted", (await page.locator(`[data-meter-reading-date="${meter}"]`).getAttribute("data-read-date-problem")) === "");
  const fetchText = await fetchSaid(meter);
  console.log(`  · Fetch ${meter}: ${fetchText}`);
  check("Fetch answers honestly with no reading", /connected|not connected|No reading/i.test(fetchText), fetchText);
  await shot("C3-move-in-read-date-10-12-and-fetch.png", page, '[data-array="move-in-meters"]');
  if (process.env.WR_STEP1_ONLY) throw new Error("WR_STEP1_ONLY: step 1 walked, nothing committed");
  await settle();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="2"][data-state="active"]');
  await page.getByLabel(/Full name/).fill("Mensah, Kofi");
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.getByLabel(/^Phone/).fill("512-555-0188");
  await settle();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="3"][data-state="active"]');
  const addToBill = page.locator('[data-segmented="move-in-payment"] [data-segment="add_to_bill"]');
  if ((await addToBill.count()) > 0) await addToBill.click();
  await settle();
  await page.getByRole("button", { name: "Continue" }).click();
  // DEF-CUS-9761 — the Billing step can hold its first early press while it
  // is still reading its own facts; press again once settled.
  await page.waitForSelector('[data-wizard-step="4"][data-state="active"]', { timeout: 5000 }).catch(async () => {
    await settle();
    await page.getByRole("button", { name: "Continue" }).click();
  });
  await page.waitForSelector('[data-wizard-step="4"][data-state="active"]', { timeout: 8000 }).catch(async () => {
    const said = await page.locator('[role="alert"], .field-error, [data-field-error]').allInnerTexts();
    console.log(`  · step 3 held: ${JSON.stringify(said).slice(0, 600)}`);
    const invalid = await page.$$eval('[aria-invalid="true"]', (ns) => ns.map((n) => `${n.id}|${n.getAttribute("name")}`));
    const errs = await page.$$eval('[id$="-error"]', (ns) => ns.map((n) => `${n.id}: ${n.textContent}`));
    console.log(`  · invalid: ${JSON.stringify(invalid)} errors: ${JSON.stringify(errs).slice(0, 800)}`);
    console.log((await page.locator("main").innerText()).slice(0, 3000));
    throw new Error("step 3 did not continue");
  });
  await settle();
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 40000 });
  await shot("C4-move-in-completed.png");
  await readHistory(meter, "C5-read-history-opening-read-dated-10-12.png");
  }

  // ── B · Disconnect → Mark as cut ─────────────────────────────────────────
  if (SKIP.includes("B")) {
    await page.goto(`${BASE}/${T}/disconnects/${CASE}`, { waitUntil: "domcontentloaded" });
    await settle();
    await shot("B3-case-after-cut.png");
    for (const no of ["E-5002", "W-5002"]) await readHistory(no, `B4-read-history-${no}.png`);
  } else {
  console.log("B · Mark as cut");
  await page.goto(`${BASE}/${T}/disconnects/${CASE}`, { waitUntil: "domcontentloaded" });
  await settle();
  await page.getByRole("button", { name: "Mark as cut" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  const rows = await dialog.locator("[data-closing-read]").evaluateAll((ns) => ns.map((n) => n.getAttribute("data-closing-read")));
  check("one closing reading row per meter on the cut services", rows.length > 0, rows.join(", "));
  check("no Estimate in Mark as cut", (await dialog.getByLabel(/Estimate/).count()) === 0);
  const cutFetch = await fetchSaid(rows[0], dialog);
  console.log(`  · Fetch ${rows[0]}: ${cutFetch}`);
  check("Fetch on Mark as cut answers honestly", cutFetch !== "", cutFetch);
  // Required: press with nothing typed.
  await dialog.getByRole("button", { name: /Mark as cut/ }).click();
  await page.waitForTimeout(600);
  check("a missing closing reading holds the cut", (await dialog.getByText("Enter the reading.").count()) > 0);
  await shot("B1-mark-as-cut-required-and-fetch.png");
  const values = { "E-5002": "5810", "W-5002": "1124" };
  for (const no of rows) {
    await page.fill(`#disconnect-cut-read-${no}-value`, values[no] ?? "1");
  }
  await typeDate(`#disconnect-cut-read-${rows.find((no) => no.startsWith("E-")) ?? rows[0]}-date`, "10/12/2026");
  await shot("B2-mark-as-cut-readings-typed.png");
  await dialog.getByRole("button", { name: /Mark as cut/ }).click();
  await dialog.waitFor({ state: "detached", timeout: 40000 });
  await settle();
  await shot("B3-case-after-cut.png");
  for (const no of rows) await readHistory(no, `B4-read-history-${no}.png`);
  }

  // ── Move record → Enter opening read ─────────────────────────────────────
  console.log("Move record · Enter opening read");
  await page.goto(`${BASE}/${T}/moves/${MOVE}`, { waitUntil: "domcontentloaded" });
  await settle();
  await page.getByTestId("move-action-enterOpeningRead").click();
  const modal = page.getByRole("dialog");
  await modal.waitFor();
  await settle();
  const unread = await modal.locator("[data-meter-reading-entry]").evaluateAll((ns) => ns.map((n) => n.getAttribute("data-meter-reading-entry")));
  check("Enter opening read lists the unread meters", unread.length > 0, unread.join(", "));
  const no = unread[0];
  check("its Read date opens on the move-in date", (await page.inputValue(`#read-${no}-date`)) === "10/14/2026", await page.inputValue(`#read-${no}-date`));
  const moveFetch = await fetchSaid(no, modal);
  console.log(`  · Fetch ${no}: ${moveFetch}`);
  await page.fill(`#read-${no}-value`, "6520");
  await typeDate(`#read-${no}-date`, "10/30/2026");
  await modal.getByRole("button", { name: /Save reads/ }).click();
  await page.waitForTimeout(600);
  check("a future date does not save", (await modal.getByText("Read date is after today.").count()) > 0);
  await shot("M1-opening-read-future-refused.png");
  await typeDate(`#read-${no}-date`, "10/15/2026");
  await shot("M2-opening-read-dated-10-15.png");
  await modal.getByRole("button", { name: /Save reads/ }).click();
  await modal.waitFor({ state: "detached", timeout: 40000 });
  await settle();
  await shot("M3-move-record-after-save.png");
  await readHistory(no, `M4-read-history-${no}.png`);
} catch (error) {
  failed += 1;
  console.log(`  FAIL  ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "FAILED.png"), fullPage: true }).catch(() => undefined);
}
await browser.close();
console.log(failed === 0 ? "WALK PASSED" : `WALK: ${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
