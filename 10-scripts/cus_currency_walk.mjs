// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-5114 (lane CUS-CURRENCY) — the tenant's currency had no
//          front-end reader, so New account and a Move-in into a VACANT unit
//          read "Currency not known here" where the deposit is $600.00.
// Data:    10-scripts/dep_pick_walk_prep.py (DEP-SIZE 5/8" $150.00 · 2"
//          $600.00 on SCW-RES; SCW-U-355 has no meter)
// Run:     BASE=http://127.0.0.1:5501 OUT=08-qa/cus-currency-2026-10-04 \
//          node 10-scripts/cus_currency_walk.mjs
// Checks:  each step prints whether "$600.00" and "Currency not known here"
//          are on the page — a FAIL line names the one that is wrong.
// ───────────────────────────────────────────────────────
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5401";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cus-currency";
const TODAY = process.env.TODAY ?? "2026-10-04";
const STAGES = (process.env.STAGES ?? "newaccount,movein").split(",");
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
  if (/\/(accounts|move-ins)/.test(url) && (response.request().method() !== "GET" || /deposit-standard/.test(url))) {
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
const cont = async () => {
  await page.locator("button", { hasText: /^Continue/ }).first().click();
  await page.waitForTimeout(1500);
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

async function toDeposit(unitNo, name) {
  await page.goto(`${BASE}/${TENANT}/accounts/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator("#account_type").selectOption("residential");
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

async function deposit(stage) {
  const amount = await page.locator("#deposit_amount").inputValue().catch(() => null);
  const sizes = await page
    .locator("#deposit_size_class option")
    .evaluateAll((os) => os.map((o) => `${o.value}=${o.textContent}`))
    .catch(() => []);
  say(`${stage}: amount box ${JSON.stringify(amount)} · size options ${JSON.stringify(sizes)}`);
}

async function dump(label) {
  const fields = await page.evaluate(() =>
    [...document.querySelectorAll("main input, main select, main button")].map(
      (e) => `${e.tagName}#${e.id}[${e.getAttribute("name") ?? ""}]:${(e.textContent || "").trim().slice(0, 24)}`,
    ),
  );
  say(`${label}: ${(await page.locator("main").innerText()).replace(/\s+/g, " ").slice(0, 300)}`);
  say(`${label} fields: ${JSON.stringify(fields)}`);
}


let failures = 0;
async function check(label) {
  const text = await page.locator("main").innerText();
  const money = text.includes("$600.00");
  const absent = text.includes("Currency not known here");
  const ok = money && !absent;
  if (!ok) failures += 1;
  say(`${ok ? "PASS" : "FAIL"} ${label}: "$600.00" ${money ? "shown" : "MISSING"} · "Currency not known here" ${absent ? "SHOWN" : "absent"}`);
}

if (STAGES.includes("newaccount")) {
  await toDeposit("SCW-U-355", "Rosa Pemberton");
  await page.locator("#deposit_size_class").selectOption("W-2");
  await page.waitForTimeout(500);
  await page.locator("label:has(#deposit_take_now)").click();
  await page.locator("#deposit_method_code").selectOption("cash");
  await page.fill("#deposit_posted_at", TODAY);
  await page.fill("#deposit_cleared_at", TODAY).catch(() => {});
  await page.waitForTimeout(500);
  await check("New account · Deposit · taken today");
  await shot("01-new-account-deposit-total-600", "New account · Deposit · 2\" picked, taken today → What is paid today $600.00");
  await cont();
  await check("New account · Review");
  await shot("02-new-account-review-600", "New account · Review · Deposit $600.00");
}

if (STAGES.includes("movein")) {
  await page.goto(`${BASE}/${TENANT}/move-ins/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const unitLabel = await page.locator("#mvi_unit option", { hasText: process.env.MI_UNIT ?? "SCW-U-206" }).first().textContent();
  await page.locator("#mvi_unit").selectOption({ label: unitLabel });
  await page.waitForTimeout(2000);
  await cont(); // → Which services
  await cont(); // → Customer
  await page.locator("#account_type").waitFor();
  await page.locator("#account_type").selectOption("residential");
  await page.fill("#full_name", "Ana Ruiz");
  await page.fill("#email", "walk.movein@example.com");
  await page.fill("#phone", "(281) 555-0188");
  await page.locator('label:has(input[name="customer_kind"][value="person"])').click();
  await cont(); // → Start & read
  await page.fill("#opened_at", TODAY);
  await cont(); // → Account preferences
  await cont(); // → Deposit
  await page.locator('[data-deposit-plan="pending"]').waitFor({ state: "detached", timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(800);
  await page.locator("#deposit_size_class").selectOption("W-2").catch(() => say("move-in: no size picker on this unit"));
  await page.waitForTimeout(500);
  await page.locator("label:has(#deposit_take_now)").click();
  await page.locator("#deposit_method_code").selectOption("cash");
  await page.fill("#deposit_posted_at", TODAY);
  await page.fill("#deposit_cleared_at", TODAY).catch(() => {});
  await page.waitForTimeout(500);
  await check("Move-in (vacant unit) · Deposit · taken today");
  await shot("03-move-in-vacant-deposit-total-600", "Move-in into a vacant unit · Deposit · taken today → $600.00");
  await cont();
  await check("Move-in (vacant unit) · Review");
  await shot("04-move-in-vacant-review-600", "Move-in into a vacant unit · Review · Deposit $600.00");
}

await browser.close();
say(failures === 0 ? "WALK PASS" : `WALK FAIL (${failures})`);
process.exit(failures === 0 ? 0 : 1);
