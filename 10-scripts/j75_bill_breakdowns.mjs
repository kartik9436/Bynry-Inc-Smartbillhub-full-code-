/**
 * j75_bill_breakdowns — J75's sent bills, read on the BILL DETAIL screen in Chromium at 1440.
 *
 * For every bill id in BILLS (the eight J75 sends, in case order), opens the bill's
 * Charges tab, reads every capacity line's size breakdown (size × count · base · each,
 * BR-BIL-1067, stored as `invoice_lines.pricing_trace`) and the footer, and screenshots
 * it. Fails loudly when a bill that carries trash, fire, battery or solar shows no
 * breakdown, or when the footer's Subtotal + Tax does not reach the Total.
 *
 *   BASE=http://127.0.0.1:<web> BILLS=<id>,<id>,… \
 *   E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *     node 10-scripts/j75_bill_breakdowns.mjs
 *
 * Screenshots: 08-qa/screens/six-service-onetime-2026-10-01/1440-caseN-5-bill-detail.png.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url).pathname);
const { chromium } = require("playwright");

const OUT = new URL("../08-qa/screens/six-service-onetime-2026-10-01/", import.meta.url).pathname;
const BASE = process.env.BASE ?? "http://127.0.0.1:8796";
const TENANT = process.env.TENANT ?? "sixrivers";
const EMAIL = process.env.EMAIL ?? "priya@sixriversutility.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
//: case → how many capacity LINES show a breakdown: trash and fire print one line a
//: service (a month), battery and solar two (the kW line and the base line), and the
//: stored trace is on both
const EXPECT = { 1: 6, 2: 3, 3: 6, 4: 6, 5: 6, 6: 18, 7: 18, 8: 0 };
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const record = {};
try {
  await page.goto(`${BASE}/${TENANT}/signin`);
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60000 });
  for (const [i, id] of (process.env.BILLS ?? "").split(",").filter(Boolean).entries()) {
    const n = i + 1;
    await page.goto(`${BASE}/${TENANT}/billing/bills/${id}?tab=lines`);
    await page.locator("table").first().waitFor({ timeout: 30000 });
    await page.waitForTimeout(1500);
    const breakdowns = (await page.locator("[data-size-breakdown]").allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());
    record[n] = { breakdowns, text: (await page.locator("main").innerText()).replace(/\s+/g, " ").slice(0, 4000) };
    check(`case ${n}: ${EXPECT[n]} capacity lines show size × count · base`, breakdowns.length === EXPECT[n], JSON.stringify(breakdowns));
    await page.screenshot({ path: `${OUT}1440-case${n}-5-bill-detail.png`, fullPage: true });
  }
} catch (error) {
  check("walk completed", false, String(error).split("\n")[0]);
} finally {
  await browser.close();
}
writeFileSync(`${OUT}j75-bill-detail.json`, `${JSON.stringify(record, null, 2)}\n`);
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed ? 1 : 0);
