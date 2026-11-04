// ── THE DEPOSIT STEP TAKES THE PLAN'S FIGURE — WALKED IN A BROWSER ─────────
//
// `DEF-CUS-6369` (the amount is the plan's for the category, no override) ·
// `DEF-CUS-6370` (a waive is kept on the account) · `DEF-CUS-6371`
// (`OQ-CUS-12620` (a): *No* only where the plan asks none) · `DEF-CUS-6372`
// (an Executive cannot reach the waive — pinned, not fixed).
// Run it after any change to `depositCapability.tsx`, `apps/customers/deposit.py`
// or the Deposit tile in `accountDetailHeader.tsx`.
//
// **THE WORKED FIGURE, AND IT IS ASSERTED:** the unit's plan asks Residential
// **$150.00** (and Commercial $400.00, and Industrial nothing). Rosa Pemberton
// is Residential. So the step shows `150.00`, not editable; the answers are
// Take or Waive; taken today it is ONE $150.00 deposit payment with its journal
// pair DR 1010 Undeposited funds / CR 2300 Customer deposit liability; not
// taken it falls on the first bill; a billing clerk's waive is refused in
// words; a System Admin's waive with reason *Hardship* is kept on the account
// and the Deposit tile reads *Waived · $150.00*.
//
// ⚠ **IT NEEDS A PRIVATE DATABASE WITH THE RULES STATED**, because the seed
// states no `plan_deposit_rules` at all: `10-scripts/proof-db.sh clone <label>`,
// then give `Residential Standard` Residential 150.00 + Commercial 400.00
// (Plans & Rates, or `PlanDepositRule` in a shell). It WRITES accounts on the
// three vacant `U-00318-10x` units and does not clean them up — run it on a
// clone and throw the clone away.
//
//   DEP_BASE      default http://127.0.0.1:8632
//   DEP_TENANT    default brazosbend
//   DEP_CLERK     default sam.reyes@sample.test   (a Billing Clerk)
//   DEP_ADMIN     default dana@brazosbendutilities.com (a System Admin)
//   DEP_EXEC      default avery.cole@sample.test  (an Executive)
//   DEP_PASSWORD  default S3cure!passw0rd
//   DEP_DB        the clone's name, for the journal read-back (psql)
//   DEP_SHOTS     default /tmp/claude-0/shots/deposit
//   DEP_CHROME    default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.DEP_BASE || "http://127.0.0.1:8632";
const T = process.env.DEP_TENANT || "brazosbend";
const CLERK = process.env.DEP_CLERK || "sam.reyes@sample.test";
const ADMIN = process.env.DEP_ADMIN || "dana@brazosbendutilities.com";
const EXEC = process.env.DEP_EXEC || "avery.cole@sample.test";
const PASSWORD = process.env.DEP_PASSWORD || "S3cure!passw0rd";
const DB = process.env.DEP_DB || "sbh_clone_deposit";
const SHOTS = process.env.DEP_SHOTS || "/tmp/claude-0/shots/deposit";
const CHROME = process.env.DEP_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const TODAY = "2026-09-23";
mkdirSync(SHOTS, { recursive: true });

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(`${what} ${detail}`);
    console.log(`  ✗ ${what} ${detail}`);
  }
}

function psql(sql) {
  return execSync(
    `psql -h 127.0.0.1 -U smartbillhub -d ${DB} -tA -c "${sql.replace(/"/g, '\\"')}"`,
    { env: { ...process.env, PGPASSWORD: "smartbillhub" } },
  )
    .toString()
    .trim();
}

async function signIn(browser, email) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(40000);
  await p.goto(`${BASE}/${T}/signin`);
  await p.fill("#signin-email", email);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

const cont = async (p) => {
  await p.locator("button", { hasText: /^Continue/ }).first().click();
  await p.waitForTimeout(1500);
};
const back = async (p) => {
  await p.locator("button", { hasText: /^Back/ }).first().click();
  await p.waitForTimeout(1000);
};
const category = (p, code) =>
  p.locator(`label.seg-opt:has(input[name="account_type"][value="${code}"])`).click();

/** New account → Deposit step, as the clerk does it: by pressing Continue. */
async function toDeposit(p, unitNo, name = "Rosa Pemberton") {
  await p.goto(`${BASE}/${T}/accounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await category(p, "residential");
  await p.fill("#full_name", name);
  await p.fill("#email", "rosa.pemberton@example.com");
  await p.fill("#phone", "(281) 555-0199");
  await p.locator('label.seg-opt:has(input[name="customer_kind"][value="person"])').click();
  await cont(p);
  await p.locator("#unit_id").fill(unitNo);
  const option = p.locator('[role="option"]', { hasText: unitNo }).first();
  await option.waitFor({ timeout: 60000 });
  await option.click();
  await p.fill("#opened_at", TODAY);
  await cont(p);
  await cont(p);
  await p.locator('[data-deposit-plan="pending"]').waitFor({ state: "detached", timeout: 30000 }).catch(() => {});
}

/** Press the review step's one primary commit and read the server's answer. */
async function commit(p) {
  const answer = p.waitForResponse(
    (r) => r.url().endsWith(`/api/${T}/accounts`) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await p.locator('button[data-variant="primary"]').last().click();
  const response = await answer;
  return { status: response.status(), body: await response.json().catch(() => ({})) };
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  // ═════════════════════════════════════════════════════════════════════════
  // 1 · A BILLING CLERK SEES THE PLAN'S FIGURE, READ-ONLY, AND TAKE OR WAIVE
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 1 · the step shows the plan's $150.00 (Rosa, Residential) ──");
  const clerk = await signIn(browser, CLERK);
  await toDeposit(clerk, "U-00318-101");
  const amount = clerk.locator("#deposit_amount");
  await amount.waitFor();
  ok("the amount is the plan's 150.00", (await amount.inputValue()) === "150.00", await amount.inputValue());
  ok("the amount cannot be typed", (await amount.getAttribute("readonly")) !== null);
  const answers = await clerk.locator("#deposit_decision option").evaluateAll((os) =>
    os.map((o) => o.value).filter((v) => v !== ""),
  );
  ok("the answers are Take or Waive — no 'No'", JSON.stringify(answers) === '["required","waived"]', JSON.stringify(answers));
  ok("'Why this amount' is gone", (await clerk.locator("#deposit_reason").count()) === 0);
  ok("the credit-tier note is gone", (await clerk.locator('[data-advisory="BR-CUS-058"]').count()) === 0);
  ok(
    "the Due help is the ruled six-word pair",
    ((await clerk.locator("#deposit_due_on-help").textContent()) ?? "").trim() === "Falls on the first bill. Unless taken today.",
  );
  await clerk.screenshot({ path: `${SHOTS}/1-clerk-deposit-residential-150.png`, fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · CHANGE THE CATEGORY — the figure follows the plan's row, or there is none
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 2 · the figure follows the category ──");
  for (let i = 0; i < 3; i += 1) await back(clerk);
  await category(clerk, "commercial");
  for (let i = 0; i < 3; i += 1) await cont(clerk);
  await clerk.waitForFunction(() => document.querySelector("#deposit_amount")?.value === "400.00", null, { timeout: 30000 }).catch(() => {});
  ok("Commercial reads the plan's 400.00", (await clerk.locator("#deposit_amount").inputValue().catch(() => "")) === "400.00");
  await clerk.screenshot({ path: `${SHOTS}/2-clerk-deposit-commercial-400.png`, fullPage: true });
  for (let i = 0; i < 3; i += 1) await back(clerk);
  await category(clerk, "industrial");
  for (let i = 0; i < 3; i += 1) await cont(clerk);
  await clerk.locator('[data-deposit-plan="none"]').waitFor({ timeout: 30000 }).catch(() => {});
  const noneText = (await clerk.locator('[data-deposit-plan="none"]').textContent().catch(() => "")) ?? "";
  ok("Industrial: 'No deposit on this plan.'", noneText.trim() === "No deposit on this plan.", noneText);
  ok("…and nothing can be typed or picked", (await clerk.locator("#deposit_amount, #deposit_decision").count()) === 0);
  await clerk.screenshot({ path: `${SHOTS}/3-clerk-deposit-industrial-none.png`, fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · TAKEN TODAY — one $150.00 deposit payment, DR 1010 / CR 2300
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 3 · taken today ──");
  for (let i = 0; i < 3; i += 1) await back(clerk);
  await category(clerk, "residential");
  for (let i = 0; i < 3; i += 1) await cont(clerk);
  await clerk.locator("#deposit_amount").waitFor();
  await clerk.locator("label:has(#deposit_take_now)").click();
  await clerk.locator("#deposit_method_code").selectOption("cash");
  await clerk.fill("#deposit_posted_at", TODAY);
  await clerk.fill("#deposit_cleared_at", TODAY);
  await clerk.waitForTimeout(600);
  await clerk.screenshot({ path: `${SHOTS}/4-clerk-taken-today.png`, fullPage: true });
  await cont(clerk);
  const taken = await commit(clerk);
  ok("the account opened", taken.status === 201, `status=${taken.status} ${JSON.stringify(taken.body).slice(0, 300)}`);
  ok("the deposit answered is the plan's 150", Number(taken.body?.deposit?.amount) === 150);
  const takenId = taken.body?.id;
  if (takenId) {
    const tenant = psql("select id from tenants where subdomain='" + T + "'");
    const pay = psql(
      `set app.tenant_id='${tenant}'; select id || '|' || amount || '|' || status from payments where account_id='${takenId}' and purpose='deposit'`,
    )
      .split("\n")
      .filter((l) => l.includes("|"));
    ok("ONE deposit payment of 150.00, cleared", pay.length === 1 && pay[0].includes("|150.") && pay[0].endsWith("|cleared"), JSON.stringify(pay));
    const payId = pay[0]?.split("|")[0];
    const legs = psql(
      `set app.tenant_id='${tenant}'; select jl.side || ':' || la.code || ':' || jl.amount from journal_lines jl join journal_entries je on je.id=jl.journal_entry_id join ledger_accounts la on la.id=jl.ledger_account_id where je.source_id='${payId}' order by jl.side`,
    )
      .split("\n")
      .filter((l) => l.includes(":"));
    ok(
      "the books: DR 1010 undeposited / CR 2300 deposit liability, 150.00 each",
      legs.length === 2 && legs.some((l) => /^(DR|debit|D):1010:150\./i.test(l)) && legs.some((l) => /^(CR|credit|C):2300:150\./i.test(l)),
      JSON.stringify(legs),
    );
    const held = psql(`set app.tenant_id='${tenant}'; select deposit_on_file from accounts where id='${takenId}'`).split("\n").pop();
    ok("the register holds 150.00", Number(held) === 150, held);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · NOT TAKEN — it falls on the first bill
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 4 · not taken today ──");
  await toDeposit(clerk, "U-00318-102", "Rosa Pemberton B");
  await clerk.locator("#deposit_amount").waitFor();
  await cont(clerk);
  const later = await commit(clerk);
  ok("the account opened", later.status === 201, `status=${later.status}`);
  ok("it goes with the first bill", (later.body?.deposit?.notes ?? []).includes("deposit_deferred_to_first_bill"));
  if (later.body?.id) {
    const tenant = psql("select id from tenants where subdomain='" + T + "'");
    const row = psql(`set app.tenant_id='${tenant}'; select coalesce(deposit_assessed::text,'') || '|' || (select count(*) from payments where account_id='${later.body.id}' and purpose='deposit') from accounts where id='${later.body.id}'`).split("\n").pop();
    ok("assessed 150.00 and no payment", /^150\.0+\|0$/.test(row ?? ""), row);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · A BILLING CLERK'S WAIVE IS REFUSED IN WORDS
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 5 · a billing clerk may not waive ──");
  await toDeposit(clerk, "U-00318-103", "Rosa Pemberton C");
  await clerk.locator("#deposit_decision").selectOption("waived");
  await clerk.fill("#deposit_waive_reason", "Hardship");
  await clerk.waitForTimeout(500);
  await clerk.screenshot({ path: `${SHOTS}/5-clerk-waive-filled.png`, fullPage: true });
  await cont(clerk);
  const refused = await commit(clerk);
  await clerk.waitForTimeout(1500);
  ok("the server refuses it", refused.status >= 400, `status=${refused.status}`);
  const page = (await clerk.locator("main").textContent()) ?? "";
  ok("…in words, on the screen", page.includes("Only a supervisor may waive this."), page.slice(-400));
  await clerk.screenshot({ path: `${SHOTS}/6-clerk-waive-refused.png`, fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · A SUPERVISOR'S WAIVE IS KEPT ON THE ACCOUNT — Waived · $150.00
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 6 · a System Admin waives for Hardship ──");
  const admin = await signIn(browser, ADMIN);
  await toDeposit(admin, "U-00318-103", "Rosa Pemberton C");
  await admin.locator("#deposit_decision").selectOption("waived");
  await admin.fill("#deposit_waive_reason", "Hardship");
  await cont(admin);
  const waived = await commit(admin);
  ok("the account opened", waived.status === 201, `status=${waived.status} ${JSON.stringify(waived.body).slice(0, 300)}`);
  if (waived.body?.id) {
    const tenant = psql("select id from tenants where subdomain='" + T + "'");
    const row = psql(`set app.tenant_id='${tenant}'; select a.deposit_waived_amount || '|' || a.deposit_waive_reason || '|' || u.full_name || '|' || (a.deposit_waived_at is not null) || '|' || (select count(*) from payments where account_id=a.id) from accounts a join users u on u.id=a.deposit_waived_by where a.id='${waived.body.id}'`).split("\n").pop();
    ok("kept on the account: 150.0000 · Hardship · Dana Whitfield · when · nothing taken", row === "150.0000|Hardship|Dana Whitfield|true|0", row);
    await admin.goto(`${BASE}/${T}/accounts/${waived.body.id}`, { waitUntil: "networkidle" });
    await admin.locator("[data-deposit-waived]").waitFor({ timeout: 30000 }).catch(() => {});
    const tile = ((await admin.locator("[data-deposit-waived]").textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
    ok("the Deposit tile reads 'Waived · $150.00'", tile === "Waived · $150.00", tile);
    const by = ((await admin.locator("[data-deposit-waived-by]").textContent().catch(() => "")) ?? "").trim();
    ok("…with who and why beneath it", by.startsWith("Dana Whitfield · Hardship · "), by);
    await admin.screenshot({ path: `${SHOTS}/7-admin-account-waived-tile.png` });
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · DEF-CUS-6372 — an Executive cannot reach the waive at all
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 7 · an Executive (DEF-CUS-6372, pinned) ──");
  const exec = await signIn(browser, EXEC);
  await exec.goto(`${BASE}/${T}/accounts/new`, { waitUntil: "networkidle" });
  await exec.waitForTimeout(1500);
  const execText = (await exec.locator("main").textContent()) ?? "";
  ok("the door refuses an Executive before any deposit", execText.includes("Your role can view accounts but not change them."));
  await exec.screenshot({ path: `${SHOTS}/8-executive-cannot-open-accounts.png` });
} finally {
  await browser.close();
}

console.log(`\n${pass} passed · ${fail} failed`);
if (fail > 0) {
  for (const f of failures) console.log(`  FAILED: ${f}`);
  process.exit(1);
}
