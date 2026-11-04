#!/usr/bin/env node
// CR-185-BRC10 D4 — the Owner summary, walked in a browser.
// Opens the report with no owner (the viewer asks for one), finds the owner by
// one of their master accounts, reads the rows and the grand total, and checks
// that Print and Download are both offered. Prints PASS/FAIL per check.
// Env: BASE, TENANT, OUT, EMAIL, PASSWORD, FROM, TO, FIND, CHROME.
import { mkdirSync } from "node:fs";

const pw = await import(
  process.env.PW ?? "/home/user/SMARTBillHub/07-frontend/node_modules/playwright/index.mjs"
);
const chromium = pw.chromium ?? pw.default.chromium;
const BASE = process.env.BASE ?? "http://127.0.0.1:8089";
const T = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "05-prototype/owner-summary-balance-transfer-2026-10-14";
const FROM = process.env.FROM ?? "2026-10-01";
const TO = process.env.TO ?? "2026-10-31";
const FIND = process.env.FIND ?? "Mill Pond";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(60000);
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
const shot = async (name) => {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/${name}`, fullPage: true });
  console.log(`  shot ${name}`);
};

try {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

  await page.goto(`${BASE}/${T}/reports?q=Owner`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  check("the library lists Owner summary", (await page.getByText("Owner summary").count()) > 0);
  await shot("D4-1-library.png");

  await page.goto(`${BASE}/${T}/reports/owner_summary?f.from=${FROM}&f.to=${TO}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("#report-requires-subject_id");
  check("with no owner, the viewer asks for one", true);
  await shot("D4-2-asks-for-owner.png");

  await page.fill("#report-requires-subject_id", FIND);
  const option = page.getByRole("option").first();
  await option.waitFor();
  const label = await option.innerText();
  check("the finder offers the owner's master account", /AC-/.test(label), label);
  await option.click();
  await page.waitForFunction(() => location.search.includes("subject_id="));
  await page.waitForSelector("table tbody tr");
  await page.waitForTimeout(1500);
  const text = await page.innerText("body");
  check("a row per property", /301 Mill Pond Ln/.test(text) && /88 Pine Vista/.test(text));
  check("the grand total is $85.00", /\$85\.00/.test(text));
  check("empty units $15.00 and common areas $70.00 in the totals", /\$15\.00/.test(text) && /\$70\.00/.test(text));
  check("the owner is named in the head", /Mill Pond Apartments LP/.test(text));
  check("no database id on screen", !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(text));
  check("Print is offered", (await page.locator('[data-report-print="button"]').count()) === 1);
  check("Download is offered", (await page.locator('[data-download="button"]').count()) === 1);
  await shot("D4-3-maple-style-owner.png");
  await page.emulateMedia({ media: "print" });
  await shot("D4-4-print-view.png");
  await page.emulateMedia({ media: "screen" });
} catch (error) {
  failed += 1;
  console.log(`  FAIL  ${String(error).slice(0, 400)}`);
  await shot("D4-FAILED.png").catch(() => undefined);
} finally {
  await browser.close();
  console.log(failed === 0 ? "ALL PASS" : `${failed} FAILED`);
  process.exit(failed === 0 ? 0 : 1);
}
