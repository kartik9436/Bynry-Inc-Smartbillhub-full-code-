/**
 * walk_late_fee_2026_10_17 — the bill run applies the late fee (DEF-BIL-10200,
 * DEF-BIL-10201), walked in Chromium at 1440.
 *
 *     WEB=http://127.0.0.1:<spa> OUT=05-prototype/walk-late-fee-2026-10-17 \
 *       node 10-scripts/walk_late_fee_2026_10_17.mjs
 *
 * World (set up on a PRIVATE copy of the dev database): cycle LF-WALK, June 2026,
 * bill date 1 Jul, due 21 days; four electric accounts, each with one ISSUED May
 * bill due 10 Jun (grace 5 calendar days → runs out after 15 Jun):
 *   LF-A  plan on LATE (1.5%, min $5)  $100.00, money arrived 20 Jun  → $5.00
 *   LF-B  plan on LATE                 $24.99 unpaid                  → nothing (under $25.00)
 *   LF-C  plan on LATEFLAT (Flat $10)  $900.00 unpaid                 → $10.00
 *   LF-D  plan on LATE                 $542.10 unpaid (GT-8)          → $8.13, WAIVED here
 * Steps: Scope → Check (the Late fee due pane: count, total, each row) → waive
 * LF-D on its own row → Price → Sign off → Send → read each bill's lines.
 * It READS the screen and fails loudly.
 */
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8109";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-late-fee-2026-10-17";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const results = [];
mkdirSync(OUT, { recursive: true });

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
}

async function shot(page, name) {
  const pane = page.locator("main.view").first();
  const path = `${OUT}/1440-${name}.png`;
  if ((await pane.count()) > 0) await pane.screenshot({ path }).catch(async () => page.screenshot({ path }));
  else await page.screenshot({ path });
}

async function onStep(page, label, timeout = 30000) {
  try {
    await page.locator("[data-wizard=rail] [aria-current=step]").filter({ hasText: label }).waitFor({ timeout });
    return true;
  } catch {
    return false;
  }
}

async function openTag(page, code) {
  const row = page.locator(`[data-tag=${code}]`).first();
  await row.waitFor({ timeout: 30000 });
  await row.click();
  await page.locator(`[data-tag-pane=${code}]`).waitFor({ timeout: 15000 });
  return page.locator(`[data-tag-pane=${code}]`);
}

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));
try {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);

  // ── Scope ───────────────────────────────────────────────────────────────
  await page.goto(`${WEB}/${T}/billing/run`);
  await page.locator("[data-screen=bulk-bill-run]").waitFor({ timeout: 30000 });
  await page.locator("#label").fill("June 2026 · late fees");
  const cycle = page.locator("#cycle_id");
  const option = cycle.locator("option").filter({ hasText: /LF-WALK/ });
  await option.first().waitFor({ state: "attached", timeout: 20000 });
  await cycle.selectOption({ value: (await option.first().getAttribute("value")) ?? "" });
  await page.locator("#period_start").fill("2026-06-01");
  await page.locator("#period_end").fill("2026-06-30");
  await page.locator("#bill_date").fill("2026-07-01");
  await page.locator("#due_days").fill("21");
  const template = page.locator("#template_id");
  await template.locator("option").nth(1).waitFor({ state: "attached", timeout: 20000 });
  await template.selectOption({ index: 1 });
  await page.waitForTimeout(1800);
  await page.getByRole("button", { name: "Start checking", exact: true }).click();
  await page.locator("[data-check-results]").waitFor({ timeout: 180000 });
  await shot(page, "01-check-results");

  // ── Check: the Late fee due pane ────────────────────────────────────────
  let pane = await openTag(page, "late_fee");
  await pane.locator("[data-late-fee-total]").waitFor({ timeout: 30000 });
  let total = (await pane.locator("[data-late-fee-total]").innerText()).trim();
  check("the pane states count and total", total === "3 accounts · late fees $23.13", total);
  const text = (await pane.innerText()).replace(/\s+/g, " ");
  check("LF-A: $5.00 on $100.00 (paid after grace)", /LF-A.*\$5\.00 on \$100\.00 overdue/.test(text), "");
  check("LF-C: flat $10.00 on $900.00", /LF-C.*\$10\.00 on \$900\.00 overdue/.test(text), "");
  check("LF-D: GT-8 $8.13 on $542.10", /LF-D.*\$8\.13 on \$542\.10 overdue/.test(text), "");
  check("LF-B ($24.99) is not listed", !text.includes("LF-B"), "");
  check("no Waive for the whole tag", (await pane.getByRole("radio", { name: "Waive" }).count()) === 0, "");
  check("the pane says waive one at a time", text.includes("Waive one account at a time."), "");
  await shot(page, "02-late-fee-pane");

  // ── Waive LF-D on its own row ───────────────────────────────────────────
  const decideD = pane.getByRole("combobox", { name: "Decide for LF-D" });
  check("LF-D's row reads Apply before any answer", (await decideD.inputValue()) === "apply", await decideD.inputValue());
  await decideD.selectOption({ value: "waive" });
  await page.waitForTimeout(3500);
  pane = await openTag(page, "late_fee");
  total = (await pane.locator("[data-late-fee-total]").innerText()).trim();
  check("after waiving LF-D: 2 accounts · $15.00", total === "2 accounts · late fees $15.00", total);
  await shot(page, "03-after-waive");

  // ── Price → Sign off → Send ─────────────────────────────────────────────
  const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
  await price.waitFor({ timeout: 30000 });
  check("Price offered for all four accounts", /Price 4 accounts/.test(await price.innerText()), await price.innerText());
  await price.click();
  check("Calculate opens Sign off", await onStep(page, "Sign off", 240000), page.url());
  const runId = new URL(page.url()).searchParams.get("run");
  await shot(page, "04-sign-off");
  const confirmations = page.getByRole("group", { name: "Sign off" });
  for (const name of [
    "Bills follow our rules and rates",
    "Email customers have agreed to e-bills",
    "SMS customers have agreed to texts",
    "Autopay customers charged on due date",
    "I checked the totals",
  ]) {
    const box = confirmations.getByRole("checkbox", { name });
    if ((await box.count()) > 0) await box.check();
  }
  const actions = page.locator("[data-wizard=actions]");
  await actions.getByRole("button", { name: "Sign off", exact: true }).click();
  check("Sign off opens Send", await onStep(page, "Send", 60000), "");
  const sendRegion = page.getByRole("region", { name: "Send" });
  const confirm = sendRegion.getByRole("checkbox", { name: "I checked the totals" });
  if ((await confirm.count()) > 0) await confirm.check();
  await actions.getByRole("button", { name: /^Send \d+ bills?$/ }).click();
  await page.locator("[data-sent-card]").waitFor({ timeout: 180000 });
  await shot(page, "05-sent");

  // ── The bills, and each one's Late fee line ─────────────────────────────
  const api = `${WEB}/api/${T}`;
  const bills = await page.evaluate(async ([api, runId]) => {
    const r = await fetch(`${api}/invoices?f.bill_run_id=${runId}&per=200`, { credentials: "include" });
    return (await r.json()).results ?? [];
  }, [api, runId]);
  check("four bills issued", bills.length === 4, String(bills.length));
  const expected = { "LF-A": "5.00", "LF-B": null, "LF-C": "10.00", "LF-D": null };
  for (const [no, fee] of Object.entries(expected)) {
    const bill = bills.find((b) => (b.account_no ?? b.account?.account_no) === no);
    if (!bill) {
      check(`${no}: billed`, false, "no bill");
      continue;
    }
    await page.goto(`${WEB}/${T}/billing/bills/${bill.id}?tab=lines`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    const body = (await page.locator("main").first().innerText()).replace(/\s+/g, " ");
    // The fee line is the code's own name: LATE "Late payment fee", LATEFLAT "Late fee (flat)".
    const line = body.match(/(Late payment fee|Late fee \(flat\))[^$]*\$([0-9.,]+)/);
    if (fee === null) check(`${no}: no late fee line`, line === null, line ? line[0] : "none");
    else check(`${no}: late fee line $${fee}`, line !== null && line[2] === fee, line ? line[0] : body.slice(0, 200));
    await page.locator("text=/Late payment fee|Late fee \\(flat\\)/").first().scrollIntoViewIfNeeded().catch(() => {});
    await shot(page, `06-bill-${no}`);
  }
  console.log(`RUN ${runId}`);
} catch (error) {
  check("walk completed", false, String(error).split("\n")[0]);
  await shot(page, "99-failure").catch(() => {});
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed ? 1 : 0);
