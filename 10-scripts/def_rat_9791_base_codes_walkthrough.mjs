// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-9791 (plan edit listed other utilities' codes) ·
//           DEF-RAT-9798 / 9799 / 9800 (PO rulings 2026-10-06: an every-class
//           and a one-class base code coexist; the clash is warned on step 1;
//           "One per customer class.")
// ───────────────────────────────────────────────────────
// A System Admin's walk in Chromium at 1440, on a database where TWO utilities
// each hold BASE-SOL and AFTER-HRS and the app connects as a superuser — so row
// security is bypassed exactly as in the production leak:
//   1. Edit plan › Solar shows ONE base code (BASE-SOL), never "Several base codes".
//   2. New charge code, step 1: Base charge · Solar · BASE-SOL-RES · All classes
//      → "BASE-SOL already covers Every class." under Customer class, Continue off.
//   3. Customer class Residential → the warning goes, Continue on; $10.00; the
//      Residential solar base is created beside every-class BASE-SOL.
//
//   BASE=http://127.0.0.1:<spa> TENANT=<slug> PLAN=<plan id> SHOTS=<dir> \
//   EMAIL=<admin email> PASSWORD=<pw> E2E_CHROMIUM_EXECUTABLE=<chrome> \
//   node 10-scripts/def_rat_9791_base_codes_walkthrough.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(`${REPO}/07-frontend/package.json`);
const { chromium } = require("playwright");

const BASE = process.env.BASE;
const TENANT = process.env.TENANT;
const PLAN = process.env.PLAN;
const SHOTS = process.env.SHOTS ?? `${REPO}/08-qa/screens/def-rat-9791-2026-10-06`;
mkdirSync(SHOTS, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);
const shot = async (name) => {
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
};

await page.goto(`${BASE}/${TENANT}/signin`);
await page.fill("#signin-email", process.env.EMAIL);
await page.fill("#signin-password", process.env.PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
  page.getByRole("button", { name: /^Sign in/ }).click(),
]);

// ── 1 · Edit plan › Solar ───────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${PLAN}/edit`);
await page.getByText("Solar pilot Plan").first().waitFor();
await page.waitForTimeout(2500);
await shot("01-plan-edit-details");
await page.getByRole("button", { name: /^Continue/ }).click();
await page.waitForTimeout(2500);
const text1 = await page.locator("body").innerText();
await shot("01b-plan-edit-services-solar-one-base-code");
check("plan edit shows no 'Several base codes'", !text1.includes("Several base codes"));
const solarCodes = (text1.match(/BASE-SOL\b(?!-)/g) ?? []).length;
check("plan edit names BASE-SOL, never twenty times", solarCodes >= 1 && solarCodes <= 3, `${solarCodes} mention(s)`);

// ── 2 · New charge code, step 1, the clash ─────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/new`);
await page.locator("#cc-kind").waitFor();
await page.selectOption("#cc-kind", "base");
const help = await page.locator("body").innerText();
check("help line reads One per customer class.", help.includes("One per customer class."));
await page.selectOption("#cc-service", "solar");
await page.locator("#cc-code").click();
await page.getByRole("option", { name: /^BASE-SOL-RES ·/ }).click();
const warning = page.getByText("BASE-SOL already covers Every class.");
await warning.waitFor();
const cont = page.getByRole("button", { name: /^Continue/ });
check("step 1 warns under Customer class", await warning.isVisible());
check("Continue is blocked while the clash stands", await cont.isDisabled());
await shot("02-charge-code-step1-clash-warning");

// ── 3 · Residential → no clash → create at $10.00 ──────────────────────────
await page.selectOption("#cc-class", "residential");
await page.waitForTimeout(800);
check("the warning goes for Residential", (await page.getByText(/already covers/).count()) === 0);
check("Continue is on", await cont.isEnabled());
// One amount for every size — Ann Arbor's Residential solar base at $10.00.
if (await page.locator("#cc-priced-by").count()) await page.selectOption("#cc-priced-by", "one");
await shot("03-charge-code-step1-residential-no-clash");
await cont.click();
await page.waitForTimeout(1500);
await shot("04a-charge-code-step2");
const amount = page.locator("table input[type=text], table input:not([type])").first();
await amount.fill("10.00");
await shot("04-charge-code-step2-ten-dollars");
await page.getByRole("button", { name: /^Continue/ }).click();
await page.getByLabel(/^Effective from/).fill("2026-10-06");
await page.getByRole("button", { name: /^Create charge code/ }).click();
await page.waitForTimeout(2500);
const done = await page.locator("body").innerText();
check("Residential solar base saved beside BASE-SOL", !/Failed|already covers/.test(done), done.slice(0, 160).replace(/\n/g, " "));
await shot("05-charge-code-residential-solar-saved");

// ── 4 · Rate schedules: live schedules naming no base code are listed ──────
await page.goto(`${BASE}/${TENANT}/plans-rates/rates`);
await page.waitForTimeout(3000);
const listed = await page.locator("[data-base-to-choose-notice]").count();
const rows = await page.locator("[data-base-to-choose]").count();
check("Rate schedules lists the schedules to name a base code", listed === 1 || rows === 0, `notice ${listed}, rows ${rows}`);
await shot("06-rate-schedules-choose-a-base-code");

writeFileSync(`${SHOTS}/results.json`, JSON.stringify(results, null, 1));
await browser.close();
process.exit(results.every((r) => r.ok) ? 0 : 1);
