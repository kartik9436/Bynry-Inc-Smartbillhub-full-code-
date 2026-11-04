#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-179-BRC10 — WALK the Rate Impact report in a real browser against
//          the running stack. It VERIFIES; it changes no product code and writes
//          nothing but one CSV export request (the product's own Download CSV).
// Drawing: 05-prototype/rate-impact-2026-10-12/*.png (compare by eye; the
//          differences are listed in walk/README.md)
// Rules:   B14 rule 31 (no database id is a visible value) · hard rule 2 (money
//          2dp on screen, a unit price up to 4) · hard rule 3 (a quantity
//          carries its unit) · hard-won laws 2, 6, 7
// ───────────────────────────────────────────────────────
//
// WHAT IT DOES, AT EACH WIDTH IN `WIDTHS` (default 1440 and 1280)
//   01 catalogue — the card sits under Billing · Readiness
//   02 the card opened, nothing chosen
//   03 Services Water + Electric, classes Residential + Municipal, 12 months,
//      rows typed: three electric capacities on the version in force, water
//      5/8" on the version in force AND on an older version, and an attempt at
//      a Charge code row (its Item list is recorded, then the row removed).
//   04 Change all prices +5 % → Fill (box values read back)
//   05 Run report → the result; 06 every group expanded
//   07 (1440 only) Download CSV → History, the run's row and its Open in report
//   08 Open in report → the viewer re-opened; the typed rows read back
//
// STEP=walk    the walk above up to and including pressing Download CSV
// STEP=history only 07 + 08 (run it after the export job has run)
// STEP=all     both (default)
//
// Usage (stack already running; nothing is started or stopped here):
//   node 10-scripts/cr179_rate_impact_walkthrough.mjs
//   BASE=http://127.0.0.1:8080 WIDTHS=1440 STEP=history node 10-scripts/cr179_rate_impact_walkthrough.mjs
//
// It prints a PASS/FAIL line per check and writes `walk-results-<STEP>.json` beside
// the screenshots. A FAIL is a finding, not a crash: the walk carries on.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const { chromium } = await import(
  process.env.PLAYWRIGHT ?? "/home/user/SMARTBillHub/07-frontend/node_modules/playwright/index.mjs"
);

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium";
const OUT = process.env.OUT ?? new URL("../05-prototype/rate-impact-2026-10-12/walk/", import.meta.url).pathname;
const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
const STEP = process.env.STEP ?? "all";
mkdirSync(OUT, { recursive: true });

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

// The rows typed — labels as the screen shows them, never ids.
const ROWS = [
  { type: "Rate schedule", item: "Sample — Electric usage", version: "2026-09-20", capacity: "Electric 1φ 100A", base: "13", price: "0.125", min: "" },
  { type: "Rate schedule", item: "Sample — Electric usage", version: "2026-09-20", capacity: "Electric 1φ 200A", base: "13", price: "0.125", min: "" },
  { type: "Rate schedule", item: "Sample — Electric usage", version: "2026-09-20", capacity: "Electric 3φ 400A", base: "13", price: "0.125", min: "" },
  { type: "Rate schedule", item: "Sample — Residential water (inclining tiers)", version: "2026-10-01", capacity: 'Water 5/8"', base: "9", price: "4.5", min: "10" },
  { type: "Rate schedule", item: "Sample — Residential water (inclining tiers)", version: "2026-08-01", capacity: 'Water 5/8"', base: "9", price: "4.5", min: "10" },
];

const results = [];
function check(width, name, pass, detail) {
  const line = `${pass ? "PASS" : "FAIL"} [${width}] ${name}${detail === undefined ? "" : ` — ${detail}`}`;
  console.log(line);
  results.push({ width, name, pass, detail });
}
function note(width, name, detail) {
  console.log(`NOTE [${width}] ${name} — ${detail}`);
  results.push({ width, name, pass: null, detail });
}

const browser = await chromium.launch({ executablePath: CHROME });

async function signIn(width) {
  const context = await browser.newContext({ viewport: { width, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return { context, page };
}

// ⚠ `fullPage` does not capture this app — `.view` scrolls inside a 100vh
// shell — so grow the viewport to the tallest scroller, shoot, put it back.
async function shot(page, width, name) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  const need = await page.evaluate(() =>
    Math.max(...[...document.querySelectorAll("*")].map((el) => el.scrollHeight), 900),
  );
  await page.setViewportSize({ width, height: Math.min(need + 80, 8000) });
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, `${width}-${name}.png`) });
  await page.setViewportSize({ width, height: 1000 });
  console.log(`   shot ${width}-${name}.png`);
}

const settle = async (page, ms = 800) => {
  await page.waitForTimeout(ms);
  await page.waitForLoadState("networkidle");
};
const viewText = async (page) => page.locator(".view").first().innerText();
const sel = (page, label, i) => page.locator(`select[aria-label="${label}"]`).nth(i);
const box = (page, label, i) => page.locator(`input[aria-label="${label}"]`).nth(i);

async function tick(page, buttonId, labels) {
  await page.locator(`#${buttonId}`).click();
  for (const label of labels) {
    await page.locator("label", { hasText: new RegExp(`^${label}$`) }).first().click();
    await page.waitForTimeout(250);
  }
  await page.keyboard.press("Escape");
  await settle(page);
}

function noIds(width, where, text) {
  const hit = text.match(UUID);
  check(width, `B14 rule 31 — no database id on screen (${where})`, hit === null, hit === null ? undefined : `visible: ${hit[0]}`);
}

async function walk(width) {
  const { context, page } = await signIn(width);

  // 01 · the catalogue card
  await page.goto(`${BASE}/${T}/reports`, { waitUntil: "networkidle" });
  await settle(page);
  const catalogue = await viewText(page);
  const billingBlock = catalogue.slice(catalogue.indexOf("BILLING ·"), catalogue.indexOf("RECEIVABLES ·"));
  check(width, "card is in the Billing group", /READINESS\s*\n\s*Rate Impact/.test(billingBlock));
  check(width, "card sits next to Bill Run Readiness", /Bill Run Readiness[\s\S]{0,80}Rate Impact/.test(billingBlock));
  const cardBasis = (billingBlock.match(/Rate Impact\s*\n\s*([^\n]+)/) ?? [])[1];
  check(width, "card basis reads 'Usage months' as drawn", cardBasis === "Usage months", `card says "${cardBasis}"`);
  await shot(page, width, "01-catalogue");

  // 02 · open it
  await page.getByText("Rate Impact", { exact: true }).first().click();
  await settle(page, 1500);
  check(width, "card opens the report", page.url().includes("/reports/rate-impact"), page.url().replace(BASE, ""));
  const head = await viewText(page);
  check(width, "head carries the drawn subtitle 'Proposed rates against billed revenue.'", head.includes("Proposed rates against billed revenue"));
  const headButtons = await page.$$eval(".view button", (n) => n.slice(0, 4).map((b) => b.textContent.trim()));
  check(width, "head offers Export + Run report as drawn (no Schedule)", !headButtons.includes("Schedule"), `head buttons: ${headButtons.join(", ")}`);
  await shot(page, width, "02-opened");

  // 03 · inputs
  await tick(page, "rep-in-services", ["Water", "Electric"]);
  await tick(page, "rep-in-classes", ["Residential", "Municipal"]);
  const classesLabel = (await page.locator("#rep-in-classes").innerText()).trim();
  note(width, "classes picker reads", classesLabel);
  await page.locator("#rep-in-months").selectOption({ label: "12 months" });
  await settle(page);
  const services = (await page.locator("#rep-in-services").innerText()).trim();
  const serviceChoices = await page.locator("#rep-in-services").click().then(async () => {
    const labels = await page.$$eval('input[type="checkbox"]', (n) => n.map((e) => e.closest("label")?.textContent.trim()).filter(Boolean));
    await page.keyboard.press("Escape");
    return labels;
  });
  note(width, "services offered", serviceChoices.join(", "));
  check(width, "a trash or fire schedule can be modelled", serviceChoices.some((s) => /Trash|Fire/.test(s)), "this tenant offers: " + serviceChoices.join(", "));
  check(width, "services chosen", /Electric/.test(services) && /Water/.test(services), services);

  for (const [i, row] of ROWS.entries()) {
    await page.getByRole("button", { name: "+ Add a row" }).click();
    await page.waitForTimeout(250);
    await sel(page, "Type", i).selectOption({ label: row.type });
    await sel(page, "Item", i).selectOption({ label: row.item });
    const versions = await sel(page, "Version", i).locator("option").allTextContents();
    if (i === 0) {
      note(width, "Version choices for Sample — Electric usage", versions.join(" / "));
      check(width, "version defaults to the one in force", (await sel(page, "Version", i).inputValue()) !== "", "version box starts on 'Choose'");
      check(width, "version reads as drawn ('v3 · in force')", versions.some((v) => /in force/i.test(v)), `labels: ${versions.join(" / ")}`);
    }
    await sel(page, "Version", i).selectOption({ label: row.version });
    await sel(page, "Capacity", i).selectOption({ label: row.capacity });
    await box(page, "Base / month", i).fill(row.base);
    await box(page, "Price per unit", i).fill(row.price);
    if (row.min !== "") await box(page, "Minimum", i).fill(row.min);
  }
  const rowsText = await page.locator('[data-otb-panel], table').first().innerText().catch(() => "");
  check(width, "'now' figures shown under each box", /now \$12\.00/.test(rowsText) && /now \$8\.00/.test(rowsText));

  // the charge-code row
  await page.getByRole("button", { name: "+ Add a row" }).click();
  const chargeIndex = ROWS.length;
  await sel(page, "Type", chargeIndex).selectOption({ label: "Charge code" });
  await page.waitForTimeout(300);
  const chargeItems = (await sel(page, "Item", chargeIndex).locator("option").allTextContents()).filter((o) => o !== "Choose");
  check(width, "a charge code can be chosen", chargeItems.length > 0, chargeItems.length === 0 ? "Item list is empty for Charge code" : chargeItems.join(", "));
  await page.getByRole("button", { name: new RegExp(`Remove row — ${chargeIndex + 1}`) }).click();
  await page.waitForTimeout(300);
  await shot(page, width, "03-rows-typed");

  // 04 · change all prices +5 % → Fill
  await page.locator("#rep-in-rows-percent").selectOption({ label: "+5%" });
  await page.getByRole("button", { name: "Fill" }).click();
  await page.waitForTimeout(500);
  const filled = [];
  for (let i = 0; i < ROWS.length; i += 1) {
    filled.push({
      base: await box(page, "Base / month", i).inputValue(),
      price: await box(page, "Price per unit", i).inputValue(),
      min: await box(page, "Minimum", i).inputValue().catch(() => ""),
    });
  }
  note(width, "boxes after +5% Fill", JSON.stringify(filled));
  check(width, "Fill moved base $12.00 → $12.60 (electric) and $8.00 → $8.40 (water)", filled[0].base === "12.60" && filled[3].base === "8.40", `${filled[0].base} / ${filled[3].base}`);
  await shot(page, width, "04-after-fill");

  // 05 · run
  await page.getByRole("button", { name: "Run report" }).click();
  await settle(page, 2500);
  const result = await viewText(page);
  await shot(page, width, "05-result");
  check(width, "grand total row present", /\nTotal\t/.test(result));
  check(width, "'Not worked out' present", result.includes("Not worked out"));
  check(width, "'Proposed figures used' present", result.includes("Proposed figures used"));
  check(width, "Capacity column present", /CAPACITY/.test(result));
  const groupAccounts = result.match(/\n\t*\$\d+\.\d{2}\t/);
  check(width, "group subtotal shows ACCOUNTS as a count, not money", !/1 rows?\n\t*\$\d/.test(result) && !/rows\n\t\t\$\d+\.00/.test(result), groupAccounts ? `group row reads "${groupAccounts[0].trim()}"` : undefined);
  noIds(width, "result", result);

  // 06 · expand every group
  const toggles = page.locator(".view button", { hasText: "▸" });
  const groups = await toggles.count();
  for (let i = 0; i < groups; i += 1) {
    await page.locator(".view button", { hasText: "▸" }).first().click();
    await page.waitForTimeout(300);
  }
  const expanded = await viewText(page);
  check(width, "groups expand", groups > 0 && (await page.locator(".view button", { hasText: "▾" }).count()) >= groups, `${groups} groups`);
  check(width, "usage carries its unit (kWh / kgal)", /\d kWh/.test(expanded) && /\d kgal/.test(expanded));
  const lines = expanded.split("\n").filter((l) => /^\s*(Electric|Water) .*\t/.test(l) || /Residential|Municipal/.test(l));
  note(width, "result lines", lines.slice(0, 20).join(" ¦ "));
  await shot(page, width, "06-expanded");
  noIds(width, "expanded result", expanded);
  writeFileSync(join(OUT, `${width}-result.txt`), expanded);

  if (width === WIDTHS[0] && STEP !== "history") {
    const download = page.locator('button[aria-label="Download CSV"]');
    check(width, "Export (Download CSV) offered", (await download.count()) > 0);
    const posted = page.waitForResponse((r) => r.url().includes("/api/exports") && r.request().method() === "POST");
    await download.first().click();
    const answer = await posted;
    const toast = await page.locator('[role="status"], [role="alert"]').allInnerTexts();
    check(width, "Export accepted", answer.status() === 202, `${answer.status()} · toast: ${toast.join(" | ")}`);
    writeFileSync(join(OUT, "export-job.json"), await answer.text());
  }
  await context.close();
}

async function history(width) {
  const { context, page } = await signIn(width);
  await page.goto(`${BASE}/${T}/reports/history`, { waitUntil: "networkidle" });
  await settle(page, 1500);
  const text = await viewText(page);
  const row = text.split("\n").find((l) => l.includes("Rate Impact"));
  check(width, "History lists the Rate Impact export", row !== undefined, row);
  check(width, "History row is finished, not queued", row !== undefined && !/Queued|Running/.test(row), row);
  noIds(width, "History", text);
  const open = page.locator('a[aria-label="Open in report"]');
  check(width, "History row has 'Open in report'", (await open.count()) > 0);
  await shot(page, width, "07-history");
  if ((await open.count()) === 0) return context.close();
  await open.first().click();
  await settle(page, 2500);
  // The viewer draws the declared inputs only once the run answers.
  await page.locator('select[aria-label="Item"]').first().waitFor({ timeout: 30000 }).catch(() => {});
  await page.getByText("Proposed figures used").first().waitFor({ timeout: 30000 }).catch(() => {});
  const reopened = await viewText(page);
  const values = [];
  const count = await page.locator('select[aria-label="Item"]').count();
  for (let i = 0; i < count; i += 1) {
    values.push({
      item: await sel(page, "Item", i).evaluate((e) => e.selectedOptions[0]?.textContent.trim()),
      version: await sel(page, "Version", i).evaluate((e) => e.selectedOptions[0]?.textContent.trim()),
      capacity: await sel(page, "Capacity", i).evaluate((e) => e.selectedOptions[0]?.textContent.trim()),
      base: await box(page, "Base / month", i).inputValue(),
      price: await box(page, "Price per unit", i).inputValue(),
    });
  }
  note(width, "rows after Open in report", JSON.stringify(values));
  check(width, "Open in report re-opens the typed rows", values.length === ROWS.length && values.every((v, i) => v.item === ROWS[i].item && v.capacity === ROWS[i].capacity), `${values.length} rows back`);
  check(width, "re-opened report shows its result", reopened.includes("Proposed figures used"));
  await shot(page, width, "08-reopened");
  await context.close();
}

for (const width of WIDTHS) {
  if (STEP !== "history") await walk(width);
  if (STEP !== "walk") await history(width);
}
await browser.close();
writeFileSync(join(OUT, `walk-results-${STEP}.json`), JSON.stringify(results, null, 1));
const failed = results.filter((r) => r.pass === false).length;
console.log(`\n${results.filter((r) => r.pass === true).length} pass · ${failed} fail · ${results.filter((r) => r.pass === null).length} notes`);
