#!/usr/bin/env node
// CR-190-BRC10 lane MOVEIN-MSG — Accounts → [account] → Change plan, with
// *Notify the customer* ticked, so `email_plan_change` is queued. The queued
// email is then rendered by `cr190_movein_messages_readback.py --plan-change`.
//
// PRIVATE walk database only (it commits a plan change):
//   CPW_BASE=http://127.0.0.1:8982 CPW_ACCOUNT=<account uuid> CPW_OUT=<dir> \
//     node 10-scripts/cr190_plan_change_walkthrough.mjs
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.CPW_BASE || "http://127.0.0.1:8982";
const T = process.env.CPW_TENANT || "brazosbend";
const ACCOUNT = process.env.CPW_ACCOUNT || "";
const OUT = process.env.CPW_OUT || ".";
const EFFECTIVE = process.env.CPW_EFFECTIVE || "2026-10-31";
const CHROME = process.env.CPW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1600 } })).newPage();
page.setDefaultTimeout(30000);
let failed = 0;
const shot = async (name) => {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`    · ${name}`);
};
const next = async () => {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: /^(Continue|Next)/ }).last().click();
};
try {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", process.env.CPW_EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.CPW_PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.goto(`${BASE}/${T}/accounts/${ACCOUNT}/change-plan`, { waitUntil: "domcontentloaded" });
  const choices = page.getByText(process.env.CPW_PLAN || "Sample — Residential", { exact: true });
  await choices.first().waitFor();
  await choices.first().click();
  await shot("11-plan-chosen.png");
  await next();
  await page.fill("#effective_on", EFFECTIVE);
  await page.keyboard.press("Tab");
  await page.getByRole("button", { name: /Show preview/ }).click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  await next();
  const notify = page.locator("#notify");
  if (!(await notify.isChecked())) await notify.check({ force: true });
  await shot("12-confirm-notify.png");
  await page.getByRole("button", { name: /Confirm/ }).last().click();
  await page.waitForTimeout(3000);
  await shot("13-after-change.png");
  console.log(`    url ${page.url()}`);
} catch (error) {
  failed += 1;
  console.log(`  ✗ walk stopped: ${error.message.split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "19-stopped.png"), fullPage: true }).catch(() => undefined);
} finally {
  await browser.close();
}
console.log(failed === 0 ? "PASS" : `FAIL (${failed})`);
process.exit(failed === 0 ? 0 : 1);
