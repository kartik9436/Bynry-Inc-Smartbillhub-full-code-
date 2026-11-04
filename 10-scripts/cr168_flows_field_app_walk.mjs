// ── Trace ──────────────────────────────────────────────
// Change:  CR-168-BRC10 lane FLOW-MEASURE (§F) — the PO's question "when the
//          technician app is not available how will you complete technician
//          work for the time being?" answered by DOING it: the field app the
//          product already ships at /{tenant}/work/mobile, in a phone-size
//          Chromium window, signed in as the assigned technician (never the
//          office — ruling 18), closing one job a flow raised.
// Rules:   BR-WRK-041 (the phone closes; nothing activates there) ·
//          BR-MET-110 (the office accepts) · ruling 18.
// ───────────────────────────────────────────────────────
/**
 *   BASE=http://127.0.0.1:5601 ORDER_NO=WO-0046 EMAIL=r.patel@sample.test \
 *     PASSWORD=... OUT=08-qa/work-2026-10-04/flows node 10-scripts/cr168_flows_field_app_walk.mjs
 *
 * The job's safety rows, tasks and readings are expected to be already sent
 * from the handset's queue (the lane sends them through the same field sync
 * API the phone uses, as the technician); this walk photographs Today, the
 * job, the close pane, presses Close with outcome "Passed", and photographs
 * Today again. ⚠ What would make it pass wrongly: a close the server refused
 * still navigates back (ClosePane treats a send failure as *offline*) — so the
 * walk prints the refusal line if one is drawn and the caller re-reads the
 * order's state from the server afterwards.
 */
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5601";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "r.patel@sample.test";
const PASSWORD = process.env.PASSWORD;
const ORDER_NO = process.env.ORDER_NO ?? "WO-0046";
const OUT = process.env.OUT ?? "/tmp/cr168-flows";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const shot = async (name) => {
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const text = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, " ").slice(0, 260);
  console.log(`=== ${name}.png ${statSync(file).size} bytes ${page.url().replace(BASE, "")}\n    ${text}`);
};

await page.goto(`${BASE}/${TENANT}/work/mobile/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
await page.waitForTimeout(1500);
await shot(`20-field-app-today-before-${ORDER_NO}`);

await page.getByText(ORDER_NO).first().click();
await page.waitForTimeout(1500);
await shot(`21-field-app-job-${ORDER_NO}`);

const jobUrl = page.url().replace(/\/$/, "");
// The template asks for photographs; the technician takes them in the
// Photographs pane (PHOTO is any small image file on disk, e.g. a test card).
for (let i = 0; i < Number(process.env.PHOTOS ?? 0); i += 1) {
  await page.goto(jobUrl + "/photos", { waitUntil: "networkidle" });
  await page.locator('input[type="file"]').setInputFiles(process.env.PHOTO);
  await page.waitForTimeout(2500);
}
if (Number(process.env.PHOTOS ?? 0) > 0) await shot(`21b-field-app-photos-${ORDER_NO}`);
await page.goto(jobUrl + "/close", { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.locator('input[name="outcome"]').first().check();
await page.waitForTimeout(300);
await shot(`22-field-app-close-${ORDER_NO}`);
const commit = page.locator('section[data-screen="WRK-23"] button').last();
console.log(`    close button enabled: ${await commit.isEnabled()}`);
await commit.click();
await page.waitForTimeout(2500);
const refusal = await page.locator('[data-testid="close-refusal"]').allInnerTexts();
console.log(`    refusal drawn: ${JSON.stringify(refusal)}`);
await shot(`23-field-app-after-close-${ORDER_NO}`);
await browser.close();
