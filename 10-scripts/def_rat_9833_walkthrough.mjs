#!/usr/bin/env node
// DEF-RAT-9833 (lane AUTO-PAPERLESS, 2026-10-06) — the account door for Autopay and Paperless,
// walked in a browser at 1440 as Marcus Lee (System Admin — Plans & Rates is read-only to a Billing Clerk, unchanged) on the CR-171 matrix world, after M3.
//
// PO D2 (b), verbatim: "clark can add it later also on account"; ruling 4 (read as (b)):
// "when clark make it on or adds it you ahve to set it up so that next billing cycle pick it".
//
//   1. Municipal account (automatic, no person may add it) draws NO + Enroll an account.
//   2. Autopay (automatic, paired with the Autopay setting) DOES draw + Enroll an account.
//   3. + Enroll an account → Harold's account → Enroll: Harold appears on Autopay's Accounts tab;
//      his Autopay setting is then On (read back from the database by the caller).
//
// Usage: W_BASE=http://127.0.0.1:5833 W_OUT=<folder> W_AUTOPAY=<id> W_MUNICIPAL=<id>
//        W_ACCOUNT_NO=AC-2026-00057 node 10-scripts/def_rat_9833_walkthrough.mjs
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.W_BASE ?? "http://127.0.0.1:5833";
const TENANT = process.env.W_TENANT ?? "mvimatrix";
const OUT = process.env.W_OUT ?? "/tmp/walk";
const AUTOPAY = process.env.W_AUTOPAY;
const MUNICIPAL = process.env.W_MUNICIPAL;
const ACCOUNT_NO = process.env.W_ACCOUNT_NO;
const PASSWORD = "S3cure!passw0rd"; // the matrix world's lane fixture credential
mkdirSync(OUT, { recursive: true });
let fails = 0;
const check = (ok, name, detail = "") => {
  if (!ok) fails += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
};

async function signIn(context, email) {
  const page = await context.newPage();
  page.setDefaultTimeout(25000);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  return page;
}
async function accountsTab(page, id) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${id}?tab=accounts`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-discount-accounts]");
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
}

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const clerk = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await signIn(clerk, "marcus@cedarford.example");

await accountsTab(page, MUNICIPAL);
check((await page.locator("[data-discount-enroll]").count()) === 0, "Municipal account draws no + Enroll an account");
await page.screenshot({ path: join(OUT, "1-municipal-accounts-no-enroll.png"), fullPage: true });

await accountsTab(page, AUTOPAY);
const enroll = page.locator("[data-discount-enroll]");
check((await enroll.count()) === 1, "Autopay draws + Enroll an account (DEF-RAT-9833)");
check(!(await page.locator("[data-discount-accounts]").innerText()).includes(ACCOUNT_NO), `${ACCOUNT_NO} is not on Autopay yet`);
await page.screenshot({ path: join(OUT, "2-autopay-accounts-enroll.png"), fullPage: true });

await enroll.click();
const dialog = page.getByRole("dialog");
await dialog.waitFor();
await dialog.locator("#account").fill(ACCOUNT_NO.slice(-5));
const option = dialog.getByText(ACCOUNT_NO, { exact: false }).first();
await option.waitFor({ timeout: 15000 });
await option.click();
await page.waitForTimeout(300);
await page.screenshot({ path: join(OUT, "3-enroll-dialog.png"), fullPage: true });
await dialog.getByRole("button", { name: /Enroll/ }).last().click();
await dialog.waitFor({ state: "detached", timeout: 15000 }).catch(() => undefined);
await page.waitForLoadState("networkidle").catch(() => undefined);
await page.waitForTimeout(800);
const after = await page.locator("[data-discount-accounts]").innerText();
check(after.includes(ACCOUNT_NO), `${ACCOUNT_NO} now listed on Autopay's Accounts tab`);
await page.screenshot({ path: join(OUT, "4-autopay-accounts-enrolled.png"), fullPage: true });

await browser.close();
console.log(`  ${fails === 0 ? "ALL PASS" : fails + " FAIL"}`);
process.exit(fails === 0 ? 0 : 1);
