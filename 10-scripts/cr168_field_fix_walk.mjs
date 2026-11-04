// ── Trace ──────────────────────────────────────────────
// Change:  CR-168-BRC10 §F.8, lane FIELD-FIX — the field app at 390 px, used
//          by the technician ALONE (nothing sent through the API beforehand):
//          tick safety, tick the tasks, take each required photo ON its task
//          row, record the reading, close; then the office accepts at 1440
//          (ruling 18 — the office never completes a job).
// Defects: DEF-WRK-9619 · 9625 · 9636 · 9620 (a move-in job on its meter)
// ───────────────────────────────────────────────────────
/**
 *   BASE=http://127.0.0.1:5193 ORDER_NO=WO-0051 TECH_PASSWORD=… OFFICE_PASSWORD=… \
 *     PHOTO=/path/to/a.jpg OUT=08-qa/work-2026-10-04/flows/fixed \
 *     node 10-scripts/cr168_field_fix_walk.mjs
 *
 * What would make it pass wrongly: a close the server refused still navigates
 * back (ClosePane treats a send failure as offline) — so the walk reads the
 * refusal line, and the office half re-reads the order's state from the page.
 */
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5193";
const TENANT = process.env.TENANT ?? "brazosbend";
const ORDER_NO = process.env.ORDER_NO ?? "WO-0051";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/flows/fixed";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: EXE });

async function shot(page, name) {
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const text = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, " ").slice(0, 220);
  console.log(`=== ${name}.png ${statSync(file).size} bytes ${page.url().replace(BASE, "")}\n    ${text}`);
}

// ── THE TECHNICIAN, 390 x 844 ────────────────────────────────────────────
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const p = await phone.newPage();
await p.goto(`${BASE}/${TENANT}/work/mobile/signin`, { waitUntil: "networkidle" });
await p.fill("#signin-email", process.env.TECH_EMAIL ?? "r.patel@sample.test");
await p.fill("#signin-password", process.env.TECH_PASSWORD);
await p.click('button[type="submit"]');
await p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
await p.waitForTimeout(1500);
await shot(p, "01-field-today");
await p.getByText(ORDER_NO).first().click();
await p.waitForTimeout(1500);
await shot(p, "02-field-job-before");

// DEF-WRK-9636 — tick every safety row, then every task, on the screen.
for (const box of await p.locator("[data-safety-id] input[type=checkbox]").all()) {
  if (!(await box.isChecked())) {
    await box.click();
    await p.waitForTimeout(1200);
  }
}
for (const box of await p.locator("[data-task-id] label:not([data-task-camera]) input[type=checkbox]").all()) {
  if (!(await box.isChecked()) && (await box.isEnabled())) {
    await box.click();
    await p.waitForTimeout(1200);
  }
}
// DEF-WRK-9619 — each required photograph is taken ON its task row.
const cameras = p.locator("[data-task-camera] input[type=file]");
const n = await cameras.count();
for (let i = 0; i < n; i += 1) {
  await cameras.nth(i).setInputFiles(process.env.PHOTO);
  await p.waitForTimeout(2500);
}
console.log(`    task cameras used: ${n}`);
await shot(p, "03-field-job-ticked-and-photographed");

const jobUrl = p.url().replace(/\/$/, "");
await p.goto(`${jobUrl}/readings`, { waitUntil: "networkidle" });
await p.waitForTimeout(800);
for (const input of await p.locator("[data-reading-id] input[inputmode=decimal]").all()) {
  await input.fill(process.env.READING ?? "4120");
  await input.blur();
  await p.waitForTimeout(1200);
}
await shot(p, "04-field-readings");

await p.goto(`${jobUrl}/close`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
await p.locator('input[name="outcome"]').first().check();
await p.waitForTimeout(300);
const blocked = await p.locator('[data-testid="close-blocked"]').allInnerTexts();
const commit = p.locator('section[data-screen="WRK-23"] button').last();
console.log(`    still needed: ${JSON.stringify(blocked)} · close enabled: ${await commit.isEnabled()}`);
await shot(p, "05-field-close-ready");
await commit.click();
await p.waitForTimeout(3000);
console.log(`    refusal drawn: ${JSON.stringify(await p.locator('[data-testid="close-refusal"]').allInnerTexts())}`);
await shot(p, "06-field-after-close");

// ── THE OFFICE, 1440 ─────────────────────────────────────────────────────
const desk = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const d = await desk.newPage();
await d.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await d.fill("#signin-email", process.env.OFFICE_EMAIL ?? "dana@brazosbendutilities.com");
await d.fill("#signin-password", process.env.OFFICE_PASSWORD);
await d.click('button[type="submit"]');
await d.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
await d.goto(`${BASE}/${TENANT}/work/orders/${ORDER_NO}`, { waitUntil: "networkidle" });
await d.waitForTimeout(2000);
await shot(d, "07-office-order-before-accept");
await d.locator('[data-action="accept"]').click();
await d.waitForTimeout(800);
await shot(d, "08-office-accept-confirm");
await d.getByRole("button", { name: /accept/i }).last().click();
await d.waitForTimeout(3000);
await d.reload({ waitUntil: "networkidle" });
await d.waitForTimeout(1500);
await shot(d, "09-office-order-accepted");
await browser.close();
