/**
 * Walk the eight charge-code fixes of lane CHARGE-CODE-FIVE IN A REAL BROWSER,
 * at 1440, and photograph each.
 *
 *     BASE=http://127.0.0.1:5835 TENANT=mvimatrix EMAIL=marcus@cedarford.example \
 *       APP_FEE_ID=<uuid> RE_READ_ID=<uuid> OUT=08-qa/charge-codes-2026-10-06 \
 *       node 10-scripts/def_rat_9803_charge_code_eight_fixes_walkthrough.mjs
 *
 * Defects: DEF-RAT-9803 (Kind into + Filter) · 9804 (locked fields readable) ·
 * 9805 (one-time never automatic) · 9806 (Edit's Code is the dropdown, locked) ·
 * 9807 (Entered-when-used default; PO 2026-10-06 option (a)) · 9811 / 9812
 * (late-fee hints) · 9813 (recurring + automatic warning).
 *
 * It asserts what a person sees (innerText, computed colour) — jsdom loads no
 * stylesheet, so "full-strength text" can only be checked here.
 */
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url).pathname);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:5835";
const TENANT = process.env.TENANT ?? "mvimatrix";
const EMAIL = process.env.EMAIL ?? "marcus@cedarford.example";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const APP_FEE_ID = process.env.APP_FEE_ID;
const RE_READ_ID = process.env.RE_READ_ID;
const OUT = process.env.OUT ?? "08-qa/charge-codes-2026-10-06";
mkdirSync(OUT, { recursive: true });

let failures = 0;
const ok = (m) => console.log(`PASS ${m}`);
const bad = (m) => {
  failures += 1;
  console.log(`FAIL ${m}`);
};
const check = (cond, m) => (cond ? ok(m) : bad(m));

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

// ── 1 · DEF-RAT-9803 ──────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes`, { waitUntil: "networkidle" });
await page.locator("tbody tr").first().waitFor({ timeout: 30000 });
check((await page.locator("[data-kind-chips]").count()) === 0, "1 · no Kind chip row beside the search box");
await shot("1a-list-toolbar");
await page.locator("details > summary", { hasText: "Filter" }).first().click();
const kindLabels = await page.locator("details fieldset", { has: page.locator("legend", { hasText: /^Kind$/ }) }).locator("label").allInnerTexts();
check(kindLabels.length === 3 && kindLabels.every((l) => / · \d+$/.test(l)), `1 · the panel offers Kind with counts: ${kindLabels.join(" | ")}`);
await shot("1b-filter-dropdown");
await page.getByLabel(/^Base · \d+$/).check();
await page.waitForTimeout(1200);
check(/Kind: Base/.test(await page.locator("body").innerText()), "1 · applied as a removable chip 'Kind: Base'");
check(new URL(page.url()).searchParams.get("f.kind") === "base", "1 · f.kind=base stays in the URL");
await page.keyboard.press("Escape");
await shot("1c-kind-base-chip");

// ── 2 + 4 · DEF-RAT-9804, 9806 — Edit APP-FEE step 1 ──────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${APP_FEE_ID}/edit`, { waitUntil: "networkidle" });
await page.locator("#cc-code").waitFor({ timeout: 30000 });
for (const id of ["cc-kind", "cc-service", "cc-part-month", "cc-code"]) {
  const box = page.locator(`#${id}`);
  const locked = (await box.getAttribute("data-locked")) !== null;
  const value = await box.inputValue().catch(() => "");
  const style = await box.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { color: cs.color, opacity: cs.opacity };
  });
  check(locked && value !== "" && style.opacity === "1", `2 · ${id} locked, reads "${value}" at full strength (colour ${style.color}, opacity ${style.opacity})`);
}
check((await page.locator("#cc-code").getAttribute("role")) === "combobox", "4 · Code is the dropdown control (combobox), locked");
// ── 3 · DEF-RAT-9805 ──
check((await page.locator("#cc-auto").inputValue()) === "No", "3 · Apply automatically reads No, locked, on a one-time code");
await shot("2-edit-app-fee-step1-locked");

// ── 5 · DEF-RAT-9807 — the Pricing step with a default ────────────────────
await page.getByRole("button", { name: /^Continue$/ }).first().click();
await page.locator("#cc-default-amount").waitFor({ timeout: 15000 });
check((await page.locator("#cc-default-amount").inputValue()) === "10.00", "5 · Pricing step shows the default $10.00");
await shot("5a-pricing-default-10");

// ── 5 · the clerk's override — One-time bill, fee kind ────────────────────
await page.goto(`${BASE}/${TENANT}/billing/one-time`, { waitUntil: "networkidle" });
await page.locator('[data-kind="fee"]').first().click();
await page.locator("#charge_code").waitFor({ timeout: 15000 });
const option = await page.locator("#charge_code option", { hasText: "Application processing fee" }).first().getAttribute("value");
await page.selectOption("#charge_code", option);
await page.locator("#entered_amount").waitFor({ timeout: 10000 });
check((await page.locator("#entered_amount").inputValue()) === "10.00", "5 · the clerk's amount starts at $10.00");
await shot("5b-one-time-bill-starts-at-default");
await page.fill("#entered_amount", "25.00");
check((await page.locator("#entered_amount").inputValue()) === "25.00", "5 · the clerk changes it to $25.00");
await shot("5c-one-time-bill-clerk-override-25");

// ── 8 · 9 · 10 — Add: late-fee hints and the every-bill warning ───────────
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/new`, { waitUntil: "networkidle" });
await page.locator("#cc-kind").waitFor({ timeout: 30000 });
await page.selectOption("#cc-kind", "other");
check((await page.locator("#cc-kind-help").innerText()).includes("Late fees: choose Plan charge."), "8 · Other charge hint");
await shot("8-other-late-fee-hint");
await page.selectOption("#cc-kind", "plan");
check((await page.locator("#cc-type-help").innerText()) === "Late fees: choose Penalty.", "9 · Type hint");
await shot("9-type-late-fee-hint");
await page.selectOption("#cc-type", "recurring");
await page.selectOption("#cc-auto", "yes");
const warning = page.locator('[data-warning="bills-everyone"]');
check((await warning.count()) === 1 && (await warning.innerText()).trim() === "Bills every account, every bill.", "10 · recurring + automatic warns");
await shot("10-bills-everyone-warning");
await page.selectOption("#cc-type", "one_time");
check((await page.locator("#cc-auto").inputValue()) === "No" && (await warning.count()) === 0, "3 · switching to one-time locks Apply automatically at No and clears the warning");
await shot("3-one-time-auto-locked-no");

if (RE_READ_ID) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${RE_READ_ID}/edit`, { waitUntil: "networkidle" });
  await page.locator("#cc-code").waitFor({ timeout: 30000 });
  await shot("2b-edit-re-read-step1-locked");
}

await browser.close();
console.log(failures === 0 ? "ALL PASS" : `${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
