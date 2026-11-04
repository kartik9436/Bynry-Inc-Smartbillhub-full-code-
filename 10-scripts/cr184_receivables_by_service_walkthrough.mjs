#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-184-BRC10 — WALK receivables by service in a real browser
//          against a running stack. It VERIFIES; it writes one report
//          definition (the builder's own Save as) and nothing else.
// Rules:   B14 rule 31 (no database id or code on screen) · hard rule 2
//          (money at 2 on screen) · hard-won laws 2, 6, 7
// ───────────────────────────────────────────────────────
//
// 01 the catalogue — the card under Receivables
// 02 the library report at the default as-of date
// 03 the library report as at 2027-01-31 (bills now over 90 days)
// 04 the builder — Receivables chosen, columns ticked, Save as
// 05 the saved custom report, filtered to Water, as at 2027-01-31
// 06 Finance → Who owes you, as at the same date, unfiltered and Water
//
// Usage (stack already running; nothing is started or stopped here):
//   BASE=http://127.0.0.1:8088 node 10-scripts/cr184_receivables_by_service_walkthrough.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const { chromium } = await import(
  process.env.PLAYWRIGHT ?? "/home/user/SMARTBillHub/07-frontend/node_modules/playwright/index.mjs"
);

const BASE = process.env.BASE ?? "http://127.0.0.1:8088";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium";
const OUT = process.env.OUT ?? new URL("../05-prototype/receivables-by-service-2026-10-14/", import.meta.url).pathname;
const WIDTH = Number(process.env.WIDTH ?? 1440);
const LATER = process.env.AS_OF ?? "2027-01-31";
mkdirSync(OUT, { recursive: true });

const results = [];
const texts = {};
function check(name, pass, detail) {
  console.log(`${pass ? "PASS" : "FAIL"} ${name}${detail === undefined ? "" : ` — ${detail}`}`);
  results.push({ name, pass, detail });
}
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: WIDTH, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(30000);

async function settle(ms = 1200) {
  await page.waitForTimeout(ms);
  await page.waitForLoadState("networkidle");
}
async function shot(name) {
  const need = await page.evaluate(() =>
    Math.max(...[...document.querySelectorAll("*")].map((el) => el.scrollHeight), 900),
  );
  await page.setViewportSize({ width: WIDTH, height: Math.min(need + 80, 8000) });
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  await page.setViewportSize({ width: WIDTH, height: 1000 });
  console.log(`   shot ${name}.png`);
}
const viewText = async () => page.locator("main").first().innerText();
function noIds(where, text) {
  const hit = text.match(UUID);
  check(`B14 rule 31 — no database id (${where})`, hit === null, hit?.[0]);
}

await page.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle", timeout: 400000 });
page.setDefaultTimeout(120000);
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

// 01 · catalogue
await page.goto(`${BASE}/${T}/reports`, { waitUntil: "networkidle" });
await settle();
const catalogue = await viewText();
check("card in the catalogue under Receivables · Arrears", /ARREARS\s*\n\s*Receivables over 90 days by service/.test(catalogue));
await shot("01-catalogue");

// 02 · library report, default date
await page.goto(`${BASE}/${T}/reports/receivables-over-90-by-service`, { waitUntil: "networkidle" });
await settle(2500);
texts.library_default = await viewText();
check("library report renders rows", /Electric|Water/.test(texts.library_default));
check("class rows in words", /Taxes/.test(texts.library_default) && !/\btaxes\b/.test(texts.library_default));
check("foot difference stated", texts.library_default.includes("Rows do not match the books"));
noIds("library", texts.library_default);
await shot("02-library-default");

// 03 · library report, later date
await page.goto(`${BASE}/${T}/reports/receivables-over-90-by-service?f.to=${LATER}`, { waitUntil: "networkidle" });
await settle(2500);
texts.library_later = await viewText();
await shot("03-library-later");

// 04 · the builder
await page.goto(`${BASE}/${T}/reports/custom/new`, { waitUntil: "networkidle" });
await settle(2000);
const chooser = page.locator("#report-edit-dataset");
await chooser.selectOption("receivables");
await settle(1500);
for (const label of ["Account number", "Account", "Service", "Charge type", "Over 90 days", "Total"]) {
  const box = page.locator(`input[type="checkbox"][aria-label="${label}"]`).first();
  if ((await box.count()) > 0 && !(await box.isChecked())) await box.check();
}
await settle(800);
texts.builder = await viewText();
check("builder offers Receivables", texts.builder.includes("Receivables"));
await shot("04-builder");
let keySeg = process.env.KEY_SEGMENT ?? "receivables-over-90-days-by-service";
if (process.env.SAVE !== "0") {
  await page.getByRole("button", { name: "Save as" }).click();
  await page.locator("input#name").fill("Receivables over 90 days by service");
  await settle(500);
  await shot("04b-save-as");
  const groupSelect = page.locator("select#group");
  if ((await groupSelect.count()) > 0) {
    await groupSelect.selectOption({ label: "Receivables" }).catch(() => undefined);
    await settle(500);
  }
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await settle(3000);
  const saved = page.url();
  check("Save as left the blank builder", !saved.endsWith("/custom/new"), saved);

  const seg = new URL(saved).pathname.split("/").filter(Boolean);
  keySeg = seg[seg.indexOf("reports") + 1];
}

// 05 · the saved custom report, as at the later date and filtered to Water
await page.goto(`${BASE}/${T}/reports/${keySeg}?f.to=${LATER}`, { waitUntil: "networkidle" });
await settle(2500);
texts.custom_later = await viewText();
await shot("05-custom-later");
await page.goto(`${BASE}/${T}/reports/${keySeg}?f.to=${LATER}&f.service=water`, { waitUntil: "networkidle" });
await settle(2500);
texts.custom_water = await viewText();
await shot("05b-custom-water");

// 06 · Finance → Who owes you
await page.goto(`${BASE}/${T}/finance/revenue?view=aging`, { waitUntil: "networkidle" });
await settle(2500);
texts.aging = await viewText();
await shot("06-who-owes-you");
await page.goto(`${BASE}/${T}/finance/revenue?view=aging&f.service=water`, { waitUntil: "networkidle" });
await settle(2500);
texts.aging_water = await viewText();
await shot("06b-who-owes-you-water");

writeFileSync(join(OUT, "walk-results.json"), JSON.stringify({ results, texts }, null, 2));
await browser.close();
