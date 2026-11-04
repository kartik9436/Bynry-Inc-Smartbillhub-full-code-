// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 follow-up (lane PLAN-MONEY) — `OQ-RAT-12786` CLOSED
//          2026-10-03, PO verbatim: *"(a) Class or size: the deposit table
//          gets a size column, like charge codes have."* Walked in a real
//          browser at 1440 on PostgreSQL 16, photographed beside images 17,
//          21 and 30 of `05-prototype/plans-2026-10-03/images/`.
// ───────────────────────────────────────────────────────
//
// Expects (CR-167 §15.3):
//   * the API — `manage.py runserver 127.0.0.1:8241` on `sbh_planmoney`
//     (`migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`), plus
//     the refundable code `DEP-SIZE` on water priced 5/8" $150.00 and 2"
//     $600.00 (created through `services.create_charge`, stated in §15.3);
//   * the SPA — `vite build --mode wolocal`, then
//     `PORT=5341 API_PROXY_TARGET=http://127.0.0.1:8241 node 07-frontend/server.mjs`.
//
//   RES=<SCW-RES id> COM=<SCW-COM id> OUT=08-qa/plans-2026-10-03/money \
//     node 10-scripts/cr167_plan_money_walk.mjs
//
// What it does: names DEP-SIZE on SCW-RES and SCW-COM through Edit › *Fix a
// mistake* › Billing (step 4's Deposits table), photographs the step, Review
// and the details Billing tab; then opens Accounts › New account's Deposit step
// on four vacant SCW-RES units given meters by `cr167_plan_money_walk_prep.py`
// — 5/8" (asks $150.00), 2" (asks $600.00), 3/4" (a size the code does not
// price — refused by name) and one with no meter (no size recorded — refused)
// — and commits the 5/8" one with the deposit taken in cash.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5341";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-money";
const RES = process.env.RES;
const COM = process.env.COM;
const STAGES = (process.env.STAGES ?? "res,com,step").split(",");
const TODAY = process.env.TODAY ?? "2026-10-03";
mkdirSync(OUT, { recursive: true });
const say = (line) => console.log(line);

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(40000);
page.on("pageerror", (error) => say(`PAGE ERROR ${error.message}`));
page.on("response", (response) => {
  const url = response.url();
  if (/\/(plans|accounts)/.test(url) && (response.request().method() !== "GET" || /deposit-standard/.test(url))) {
    say(`  ${response.request().method()} ${url.replace(/^.*\/api\//, "")} → ${response.status()}`);
  }
});

async function shot(name, caption) {
  await page.waitForTimeout(700);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);
  const height = await page.evaluate(() => {
    const main = document.querySelector("main");
    const top = main ? main.getBoundingClientRect().top : 0;
    return Math.ceil(Math.max(900, (main ?? document.body).scrollHeight + top + 40));
  });
  await page.setViewportSize({ width: 1440, height });
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`=== ${name}.png — ${caption}`);
}
const click = (name) => page.getByRole("button", { name, exact: true }).click();
async function text(selector) {
  return (await page.locator(selector).first().innerText()).replace(/\s+/g, " ").trim();
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

async function nameDeposit(planId, tag) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${planId}/edit?change=correct&step=3`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("+ Add deposit");
  const select = page.getByRole("combobox", { name: "Deposit", exact: true }).last();
  const options = await select.locator("option").allInnerTexts();
  say(`deposit options: ${JSON.stringify(options)}`);
  const wanted = options.find((o) => o.startsWith("DEP-SIZE"));
  await select.selectOption({ label: wanted });
  const main = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  say(`step-4 deposits: ${main.slice(main.indexOf("Deposits"), main.indexOf("Deposits") + 220)}`);
  await shot(`17-${tag}-step4-deposit-by-size`, `Fix a mistake · Billing · DEP-SIZE named, priced by Size (image 17)`);
  await click("Continue");
  await page.getByText("How it is saved").waitFor();
  await page.getByLabel(/^Reason/).fill("The plan asks a deposit by meter size");
  await shot(`21-${tag}-review-deposit-by-size`, `Fix a mistake · Review (image 21)`);
  await click("Save correction");
  await page.locator("[data-plan-edit-saved]").waitFor();
  say(`saved: ${await text("[data-plan-edit-saved]")}`);
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${planId}?tab=billing`, { waitUntil: "networkidle" });
  await page.locator('[data-plan-section="deposits"]').waitFor();
  say(`details deposits: ${await text('[data-plan-section="deposits"]')}`);
  await shot(`30-${tag}-details-billing-deposit-by-size`, `Details · Billing · Deposits by size (image 30)`);
}

// `photo` re-photographs a plan that already names DEP-SIZE, saving nothing
// (used after DEF-RAT-9503's fix: smallest size first).
async function photo(planId, tag) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${planId}?tab=billing`, { waitUntil: "networkidle" });
  await page.locator('[data-plan-section="deposits"]').waitFor();
  say(`details deposits: ${await text('[data-plan-section="deposits"]')}`);
  await shot(`30-${tag}-details-billing-deposit-by-size`, `Details · Billing · Deposits by size (image 30)`);
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${planId}/edit?change=correct&step=3`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  const main = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  say(`step-4 deposits: ${main.slice(main.indexOf("Deposits"), main.indexOf("Deposits") + 220)}`);
  await shot(`17-${tag}-step4-deposit-by-size`, `Fix a mistake · Billing · DEP-SIZE on the plan, priced by Size (image 17)`);
}
if (STAGES.includes("photo")) {
  await photo(RES, "res");
  await photo(COM, "com");
}
if (STAGES.includes("res")) await nameDeposit(RES, "res");
if (STAGES.includes("com")) await nameDeposit(COM, "com");

const cont = async () => {
  await page.locator("button", { hasText: /^Continue/ }).first().click();
  await page.waitForTimeout(1500);
};
async function toDeposit(unitNo, category, name) {
  await page.goto(`${BASE}/${TENANT}/accounts/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator("#account_type").selectOption(category);
  await page.fill("#full_name", name);
  await page.fill("#email", "walk.deposit@example.com");
  await page.fill("#phone", "(281) 555-0199");
  await page.locator('label:has(input[name="customer_kind"][value="person"])').click();
  await cont();
  await page.locator("#unit_id").fill(unitNo);
  const option = page.locator('[role="option"]', { hasText: unitNo }).first();
  await option.waitFor({ timeout: 60000 });
  await option.click();
  await page.fill("#opened_at", TODAY);
  await cont();
  await cont();
  await page.locator('[data-deposit-plan="pending"]').waitFor({ state: "detached", timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(800);
}

if (STAGES.includes("step")) {
  for (const [unitNo, category, size, name] of [
    ["SCW-U-207", "residential", "58", "Rosa Pemberton"],
    ["SCW-U-351", "residential", "2", "Lone Star Bakery"],
    ["SCW-U-353", "residential", "34", "Ana Ruiz"],
    ["SCW-U-355", "residential", "none", "Ben Ortiz"],
  ]) {
    await toDeposit(unitNo, category, name);
    const amount = await page.locator("#deposit_amount").inputValue().catch(() => null);
    const panel = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    const fact = panel.match(/Deposit[^]*?(No deposit[^.]*\.|This plan[^.]*\.)/)?.[1] ?? null;
    say(`${unitNo} (${size}) ${category}: amount box ${amount} · ${fact ?? ""}`);
    await shot(`deposit-step-${size}-${unitNo}`, `New account · Deposit · ${unitNo}`);
  }
  // End to end: the 5/8" customer, deposit taken in cash.
  await toDeposit("SCW-U-207", "residential", "Rosa Pemberton");
  await page.locator("label:has(#deposit_take_now)").click();
  await page.locator("#deposit_method_code").selectOption("cash");
  await page.fill("#deposit_posted_at", TODAY);
  await page.fill("#deposit_cleared_at", TODAY).catch(() => {});
  await cont();
  await shot("deposit-58-review", "New account · Review with the $150.00 deposit");
  const answer = page.waitForResponse(
    (r) => r.url().endsWith(`/api/${TENANT}/accounts`) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await page.locator('button[data-variant="primary"]').last().click();
  const response = await answer;
  const body = await response.json().catch(() => ({}));
  say(`POST accounts → ${response.status()} ${JSON.stringify({ id: body.id, account_no: body.account_no, deposit: body.deposit }).slice(0, 600)}`);
  await page.waitForTimeout(2000);
  await shot("deposit-58-created", "New account created with the deposit taken");
}

await browser.close();
