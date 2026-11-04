// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9521 (lane DEP-PICK) — a size-priced deposit with no meter
//          fitted: the clerk picks the size on the Deposit step. PO 2026-10-04,
//          verbatim: *"(c) Let the clerk pick the size on the Deposit step."*
// Data:    10-scripts/dep_pick_walk_prep.py (DEP-SIZE 5/8" $150.00 · 2"
//          $600.00 on SCW-RES; SCW-U-207 has a 5/8" meter; SCW-U-355 none)
// Run:     BASE=http://127.0.0.1:5401 OUT=08-qa/plans-2026-10-03/deposit-pick \
//          node 10-scripts/dep_pick_walk.mjs
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
const OUT = process.env.OUT ?? "/tmp/dep-pick";
const TODAY = process.env.TODAY ?? "2026-10-04";
const STAGES = (process.env.STAGES ?? "pick,meter,movein").split(",");
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

if (STAGES.includes("pick")) {
  // The ruling's worked case: SCW-U-355, no meter fitted.
  await toDeposit("SCW-U-355", "Rosa Pemberton");
  await deposit("no meter, nothing picked");
  // Continue is held until a size is picked.
  await shot("01-no-meter-pick-a-size", "New account · Deposit · no meter fitted: Meter size offered, nothing picked");
  await page.locator("#deposit_size_class").selectOption("W-2");
  await page.waitForTimeout(500);
  await deposit("2\" picked");
  await shot("02-no-meter-2in-picked-600", "New account · Deposit · 2\" picked → $600.00");
  await page.locator("label:has(#deposit_take_now)").click();
  await page.locator("#deposit_method_code").selectOption("cash");
  await page.fill("#deposit_posted_at", TODAY);
  await page.fill("#deposit_cleared_at", TODAY).catch(() => {});
  await shot("03-no-meter-2in-taken-today", "New account · Deposit · $600.00 taken today in cash");
  await cont();
  await shot("04-review-2in-600", "New account · Review · Meter size 2\", $600.00");
  const answer = page.waitForResponse(
    (r) => r.url().endsWith(`/api/${TENANT}/accounts`) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await page.locator('button[data-variant="primary"]').last().click();
  const response = await answer;
  const body = await response.json().catch(() => ({}));
  say(`POST accounts → ${response.status()} ${JSON.stringify({ id: body.id, account_no: body.account_no, deposit: body.deposit }).slice(0, 800)}`);
  await page.waitForTimeout(2000);
  await shot("05-created-2in-600", "New account created · $600.00 deposit taken");
}

if (STAGES.includes("meter")) {
  // A 5/8" meter fitted: the amount follows it, no picker.
  await toDeposit("SCW-U-207", "Lone Star Bakery");
  await deposit("5/8\" meter fitted");
  await shot("06-meter-58-150-no-picker", "New account · Deposit · 5/8\" meter fitted → $150.00, no picker");
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

if (STAGES.includes("movein")) {
  // The same Deposit step on Move-in (S19 standalone), a vacant unit with no meter.
  await page.goto(`${BASE}/${TENANT}/move-ins/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await dump("move-in step 1");
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
  await dump("move-in step 4");
  await page.fill("#opened_at", TODAY);
  await cont(); // → Account preferences
  await cont(); // → Deposit
  await page.locator('[data-deposit-plan="pending"]').waitFor({ state: "detached", timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(800);
  await deposit("move-in, no meter");
  await shot("07-move-in-no-meter-pick-a-size", "Move-in · Deposit · no meter fitted: Meter size offered");
  await page.locator("#deposit_size_class").selectOption("W-2");
  await page.waitForTimeout(500);
  await deposit("move-in, 2\" picked");
  await shot("08-move-in-2in-picked-600", "Move-in · Deposit · 2\" picked → $600.00");
}

await browser.close();
