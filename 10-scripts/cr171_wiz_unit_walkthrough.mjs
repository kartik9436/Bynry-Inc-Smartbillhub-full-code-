#!/usr/bin/env node
// CR-171-BRC10 lane MVI-WIZ-UNIT — photograph the move-in's step 1 (Unit) at
// 1440 for the side-by-side with `05-prototype/movein-redesign-2026-10-05/
// images/30–32`, driving the real screen against a booted stack.
//
// Usage:
//   WU_BASE=http://127.0.0.1:5724 WU_UNIT='SCW-U-042' WU_METER='W-5041' \
//   WU_OUT=08-qa/movein-2026-10-05/after/wizard node 10-scripts/cr171_wiz_unit_walkthrough.mjs
//
// Shots: `W30-unit.png` (unit chosen, date, a reading, a field-visit row with
// its Work order, For, Window and Assign to), `W31-unit-meter-details.png`
// (the meter's ▸ opened), `W32-unit-read-below-last.png` (a reading below the
// last one typed, warned inline). Each asserts the drawn landmarks are on the
// page before it is taken, so a blank or half-loaded page fails rather than
// photographs.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.WU_BASE || "http://127.0.0.1:5724";
const T = process.env.WU_TENANT || "brazosbend";
const OUT = process.env.WU_OUT || "08-qa/movein-2026-10-05/after/wizard";
const UNIT = process.env.WU_UNIT || "SCW-U-042";
const METER = process.env.WU_METER || "";
const EMAIL = process.env.WU_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.WU_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.WU_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 2400 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

let failed = 0;
async function shot(name, landmarks) {
  for (const selector of landmarks) {
    await page.waitForSelector(selector, { timeout: 20000 });
  }
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`  ✓ ${name}`);
}

try {
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#mvi_unit");
  // The vacant list is read after the page draws; wait for real options.
  await page.waitForFunction(() => (document.querySelector("#mvi_unit")?.options.length ?? 0) > 1, null, {
    timeout: 30000,
  });
  const value = await page.$eval(
    "#mvi_unit",
    (select, unit) => [...select.options].find((o) => o.textContent.includes(unit))?.value ?? "",
    UNIT,
  );
  if (!value) throw new Error(`unit ${UNIT} is not in the vacant list`);
  await page.selectOption("#mvi_unit", value);
  await page.waitForSelector('[data-unit-card="ready"]');
  await page.waitForSelector('[data-array="move-in-meters"] tbody tr');
  await page.waitForLoadState("networkidle");
  // The move-in date, in the utility's own format (the box accepts typing).
  const dateBox = page.locator("#opened_at");
  if ((await dateBox.inputValue()) === "") {
    await dateBox.fill("10/10/2026");
    await dateBox.press("Tab");
  }
  const meter = METER || (await page.locator("[data-meter-row]").first().getAttribute("data-meter-row"));
  // A field-visit row with a Work order, For, Window and Assign to.
  await page.click('[data-array-action="add-work-order"]');
  const workOrder = page.locator("#move_in-fv-0-workOrder");
  await workOrder.click();
  await page.locator('[role="option"]').first().click();
  await page.selectOption("#move_in-fv-0-for", { index: 1 });
  await page.selectOption("#move_in-fv-0-window", "morning");
  const holders = await page.$$eval("#move_in-fv-0-assignee option", (os) => os.map((o) => o.value));
  if (holders.length > 1) await page.selectOption("#move_in-fv-0-assignee", holders[1]);
  await page.waitForLoadState("networkidle");
  // An opening read ABOVE the last one: no warning.
  const box = page.locator(`#moveIn-open-read-${meter}`);
  const last = await page
    .locator(`[data-meter-row="${meter}"]`)
    .locator("xpath=ancestor::tr")
    .locator("td")
    .nth(5)
    .innerText();
  const lastValue = Number((last.split("\n")[0] || "0").replace(/[^0-9.]/g, "")) || 0;
  await box.fill(String(Math.floor(lastValue) + 7));
  await page.waitForTimeout(800);
  await shot("W30-unit.png", ['[data-unit-card="ready"]', "[data-move-in-date]", '[data-field-visit-layout="panel"]']);

  await page.click(`[data-meter-expand="${meter}"]`);
  await shot("W31-unit-meter-details.png", [`[data-meter-facts="${meter}"]`]);

  await box.fill(String(Math.max(0, Math.floor(lastValue) - 24)));
  await page.waitForSelector(`text=Below the last read.`, { timeout: 10000 });
  await shot("W32-unit-read-below-last.png", [`[data-meter-facts="${meter}"]`]);
} catch (error) {
  failed += 1;
  console.log(`  ✗ ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "W30-unit-FAILED.png"), fullPage: true });
}
await browser.close();
clearTimeout(KILL);
process.exit(failed === 0 ? 0 : 1);
