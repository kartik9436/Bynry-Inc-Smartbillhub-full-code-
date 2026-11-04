// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-8735, 8736, 8738, 8739, 8740, 8741, 8742 — the PO's beta
//           screenshots of RAT-03 (edit "Sample — Battery capacity", v2.418.9).
// Rules:    12-governance/22-product-maintenance-process.md §0 and §4 · law 6.
// ───────────────────────────────────────────────────────
// Walks a battery edit, a water edit and a NEW battery schedule through all five
// steps at 1440 and writes, per step, a screenshot, the visible text and a
// fields/sentences count (`<PREFIX>-measure.json`).
//
//   BASE=http://127.0.0.1:<spa> SHOTS=<dir> PREFIX=before|after \
//   [NEWSHAPE=1  step 2 is the table array with + Add row (after the fix)] \
//   [OPEN_BASE=1 also shoot step 1 with the base charge code opened] \
//   E2E_CHROMIUM_EXECUTABLE=<chrome> node 10-scripts/def_rat_8735_rate_schedule_wizard_walk.mjs
//
// Needs a PRIVATE database: tenant `brazosbend` from seed_demo, battery switched
// on (PUT /settings/services/battery {"enabled": true}) and
// `manage.py load_sample_data --tenant brazosbend`. It creates schedules.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8938";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS;
const PREFIX = process.env.PREFIX ?? "before";
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: Number(process.env.VH ?? 2000) } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("    console: " + m.text()); });
await page.goto(`${BASE}/${TENANT}/signin`);
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
  page.click('button[type="submit"]'),
]);
const api = (p) => `${BASE}/api/${TENANT}${p}`;
const list = (await (await ctx.request.get(api("/rate-schedules?per=200"))).json()).results;
const byName = (re) => list.find((c) => re.test(c.name));

const report = {};
async function measure(label) {
  // What the clerk reads inside the wizard frame: fields (labelled controls) and
  // sentences (text nodes ending in a full stop, outside controls).
  return await page.evaluate(() => {
    const root = document.querySelector(".rating-wizard") ?? document.body;
    const fields = root.querySelectorAll(
      "input:not([type=hidden]), select, textarea, [role=combobox]",
    );
    const visible = [...fields].filter((el) => el.offsetParent !== null);
    const text = root.innerText;
    const sentences = text
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => /[.!?…]$/.test(s) && s.split(/\s+/).length >= 3);
    return { fields: new Set(visible.map((el) => el.id || el.getAttribute("aria-label") || el.name)).size, sentences, text };
  });
}
async function shot(scn, n, label) {
  const path = `${SHOTS}/${PREFIX}-${scn}-${n}-${label}.png`;
  await page.screenshot({ path, fullPage: true });
  const m = await measure(label);
  report[`${scn}-${n}-${label}`] = { fields: m.fields, sentences: m.sentences.length, sentenceText: m.sentences };
  writeFileSync(`${SHOTS}/${PREFIX}-${scn}-${n}-${label}.txt`, m.text);
  console.log(`  ${scn} step ${n} ${label}: ${m.fields} fields · ${m.sentences.length} sentences`);
}
async function cont() {
  await page.getByRole("button", { name: /^Continue/ }).click();
  await page.waitForTimeout(1200);
}

async function walk(scn, url, chooseChange) {
  console.log(`== ${scn}`);
  await page.goto(url);
  await page.waitForSelector(".rating-wizard", { timeout: 60000 });
  await page.waitForTimeout(2500);
  if (chooseChange) {
    const change = page.getByLabel("Change the rate");
    if (await change.count()) await change.check();
  }
  await shot(scn, 1, "basics");
  if (process.env.OPEN_BASE === "1") {
    await page.locator("#rate-base-charge-code").click();
    await page.waitForTimeout(500);
    await shot(scn, 1, "basics-open");
    await page.keyboard.press("Escape");
  }
  await cont();
  await shot(scn, 2, "sizes");
  await cont();
  await shot(scn, 3, "structure");
  await cont();
  await page.waitForTimeout(2500);
  await shot(scn, 4, "effective");
  await cont();
  await page.waitForTimeout(1500);
  await shot(scn, 5, "review");
}

const bat = byName(/Sample — Battery capacity/);
const water = byName(/Sample — Residential water \(inclining tiers\)/);
await walk("battery-edit", `${BASE}/${TENANT}/plans-rates/rates/${bat.id}/edit`, true);
await walk("water-edit", `${BASE}/${TENANT}/plans-rates/rates/${water.id}/edit`, true);

// New schedule: battery, with two sizes added on step 2 (5 kW then 30 kW, one
// minimum blank) so the read-back order and the blank are both exercised.
console.log("== battery-new");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`);
await page.waitForSelector(".rating-wizard", { timeout: 60000 });
await page.waitForTimeout(2000);
await page.fill("#rate-name", `Walk ${PREFIX} ${Date.now() % 100000} battery`);
await page.selectOption("#rate-service", "battery");
await page.waitForTimeout(800);
await shot("battery-new", 1, "basics");
await cont();
if (process.env.NEWSHAPE === "1") {
  for (const [code, min] of [["BAT-30", "12.50"], ["BAT-5", ""]]) {
    await page.locator('[data-array-action="add-size"], button:has-text("Add row")').first().click();
    const sel = page.locator('select[data-cell="size"]').last();
    await sel.selectOption(code);
    if (min) await page.locator('input[id^="size-minimum"]').last().fill(min);
  }
} else {
  for (const [code, min] of [["BAT-30", "12.50"], ["BAT-5", ""]]) {
    await page.selectOption("#size-pick", code);
    if (min) await page.fill("#size-pick-minimum", min);
    await page.getByRole("button", { name: /Add size/ }).click();
  }
}
await shot("battery-new", 2, "sizes");
await cont();
const price = page.locator('input[id^="tier-price"], input[id*="unit_price"], input[id*="price"]').first();
if (await price.count()) await price.fill("3.25");
await shot("battery-new", 3, "structure");
await cont();
await page.waitForTimeout(1500);
await shot("battery-new", 4, "effective");
await cont();
await page.waitForTimeout(1500);
await shot("battery-new", 5, "review");

writeFileSync(`${SHOTS}/${PREFIX}-measure.json`, JSON.stringify(report, null, 2));
await browser.close();
