/**
 * capbase_walkthrough — the capacity-base ruling (BR-BIL-1067), walked in Chromium at 1440.
 *
 *   MODE=bill  BILLS=<invoice id>,… — open each bill's Charges tab and read the size ×
 *              count × base under its capacity line (the J74 interim bill, J74 world).
 *   MODE=bulk  — a September bulk run on J72-RIVERSIDE after `capbase_walk_prep.py`:
 *              Check shows the "Size base $0.00" warning for CAP-WALK-B and bills it,
 *              Sign off's warnings note and Send's count carry it, Send issues both trash
 *              bills, and each bill's line shows its breakdown.
 *
 *     BASE=http://127.0.0.1:<web> E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       MODE=bulk node 10-scripts/capbase_walkthrough.mjs
 *
 * It READS the screen and fails loudly. Screenshots: 08-qa/screens/capacity-base-2026-10-01/.
 */
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const OUT = new URL("../08-qa/screens/capacity-base-2026-10-01/", import.meta.url).pathname;
const BASE = process.env.BASE ?? "http://127.0.0.1:8814";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const MODE = process.env.MODE ?? "bulk";
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
}

async function shot(page, name, full = true) {
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}1440-${name}.png`, fullPage: full });
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

async function readBill(page, id, name, expect) {
  await page.goto(`${BASE}/${TENANT}/billing/bills/${id}?tab=lines`);
  const breakdown = page.locator("[data-size-breakdown]").first();
  await breakdown.waitFor({ timeout: 30000 });
  const text = (await page.locator("[data-size-breakdown]").allInnerTexts()).join(" | ").replace(/\s+/g, " ");
  check(`${name}: the line shows size × count · base`, expect.every((e) => text.includes(e)), text);
  await breakdown.scrollIntoViewIfNeeded();
  await shot(page, name);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
try {
  await page.goto(`${BASE}/${TENANT}/signin`);
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60000 });

  if (MODE === "bill") {
    for (const [i, id] of (process.env.BILLS ?? "").split(",").filter(Boolean).entries()) {
      await readBill(page, id, `0${2 + i}-j74-interim-bill-detail`, ["Trash 96-gallon cart × 1", "base $3.00", "$15.00 each"]);
    }
  } else {
    // ── Scope: September on J72-RIVERSIDE ──────────────────────────────────
    await page.goto(`${BASE}/${TENANT}/billing/run`);
    await page.locator("[data-screen=bulk-bill-run]").waitFor({ timeout: 30000 });
    await page.locator("#label").fill("September 2026 · capacity base");
    const cycle = page.locator("#cycle_id");
    const option = cycle.locator("option").filter({ hasText: /J72-RIVERSIDE/ });
    await option.first().waitFor({ state: "attached", timeout: 20000 });
    await cycle.selectOption({ value: (await option.first().getAttribute("value")) ?? "" });
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await page.locator("#bill_date").fill("2026-10-01");
    await page.locator("#due_days").fill("21");
    const template = page.locator("#template_id");
    await template.locator("option").nth(1).waitFor({ state: "attached", timeout: 20000 });
    await template.selectOption({ index: 1 });
    await page.waitForTimeout(1800);
    await page.getByRole("button", { name: "Start checking", exact: true }).click();
    await page.locator("[data-check-results]").waitFor({ timeout: 180000 });
    await shot(page, "10-bulk-check-results");

    // ── Check: the warning tag, its account, its sentence ──────────────────
    const tagRow = page.locator("[data-tag=base_size_not_priced]").first();
    const tagText = (await tagRow.innerText()).replace(/\s+/g, " ");
    check("Check lists the warning tag 'Size base $0.00'", /Size base \$0\.00/.test(tagText), tagText);
    const pane = await openTag(page, "base_size_not_priced");
    await pane.locator("[data-row-account='AC-2026-00013']").first().waitFor({ timeout: 30000 });
    const paneText = (await pane.innerText()).replace(/\s+/g, " ");
    check("the tag holds CAP-WALK-B's account", paneText.includes("AC-2026-00013"), paneText.slice(0, 300));
    check("the row says which code and size", /BASE-T has no price for CART-35/.test(paneText), paneText.slice(0, 400));
    await shot(page, "11-bulk-check-size-base-tag");

    // The J72 world's own missing reading takes the estimate J72's spec records
    // (U5 · DEF-BIL-8551) — otherwise it is left undecided, which is not this walk's subject.
    if ((await page.locator("[data-tag=missing_read]").count()) > 0) {
      const nr = await openTag(page, "missing_read");
      const decide = nr.getByRole("combobox", { name: "Decide for AC-2026-00003" });
      if ((await decide.count()) > 0) {
        await decide.selectOption({ value: "estimate" });
        const box = nr.locator("[data-estimate-box]");
        await box.waitFor({ timeout: 15000 });
        const usage = box.getByLabel("Usage");
        if ((await usage.inputValue()) === "") await usage.fill("7");
        const unit = box.getByLabel("Unit");
        if ((await unit.inputValue()) === "") await unit.fill("kgal");
        await box.getByRole("button", { name: "Record this estimate" }).click();
        await nr.locator("[data-estimate-recorded]").waitFor({ timeout: 20000 });
      }
    }
    // The J72 world's own overlap row takes its one lawful answer (as J72's spec does).
    const overlap = page.getByRole("combobox", { name: "Decide for AC-2026-00010" });
    if ((await page.locator("[data-tag=gap_or_overlap]").count()) > 0) {
      await openTag(page, "gap_or_overlap");
      if ((await overlap.count()) > 0) await overlap.selectOption({ label: "Look into it" }).catch(() => {});
      await page.waitForTimeout(2500);
    }
    const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
    await price.waitFor({ timeout: 30000 });
    const priceText = await price.innerText();
    await price.click();
    check("Price was offered", true, priceText);
    check("Calculate opens Sign off", await onStep(page, "Sign off", 240000), page.url());
    const runId = new URL(page.url()).searchParams.get("run");

    // ── Sign off: the warnings note carries the tag ────────────────────────
    const note = page.locator("[data-signoff-warnings]");
    await note.waitFor({ timeout: 30000 });
    const noteText = (await note.innerText()).replace(/\s+/g, " ");
    check("Sign off's warnings note names 'Size base $0.00'", /Size base \$0\.00/.test(noteText), noteText);
    await note.scrollIntoViewIfNeeded();
    await shot(page, "12-bulk-signoff-warnings");
    const confirmations = page.getByRole("group", { name: "Sign off" });
    for (const name of [
      "Bills follow our rules and rates",
      "Email customers have agreed to e-bills",
      "SMS customers have agreed to texts",
      "Autopay customers charged on due date",
      "I checked the totals",
    ]) {
      await confirmations.getByRole("checkbox", { name }).check();
    }
    const actions = page.locator("[data-wizard=actions]");
    await actions.getByRole("button", { name: "Sign off", exact: true }).click();
    check("Sign off opens Send", await onStep(page, "Send", 60000), "");
    const sendRegion = page.getByRole("region", { name: "Send" });
    const sendText = (await sendRegion.innerText()).replace(/\s+/g, " ");
    check("Send counts the warning", /Warnings\s*[1-9]/.test(sendText), sendText.slice(0, 400));
    await shot(page, "13-bulk-send-warnings");
    await sendRegion.getByRole("checkbox", { name: "I checked the totals" }).check();
    await actions.getByRole("button", { name: /^Send \d+ bills?$/ }).click();
    await page.locator("[data-sent-card]").waitFor({ timeout: 180000 });
    await shot(page, "14-bulk-sent");

    // ── The two trash bills, read off the database's own answer ───────────
    const api = `${BASE}/api/${TENANT}`;
    const bills = await page.evaluate(async ([api, runId]) => {
      const r = await fetch(`${api}/invoices?f.bill_run_id=${runId}&per=200`, { credentials: "include" });
      return (await r.json()).results ?? [];
    }, [api, runId]);
    const byAccount = (no) => bills.find((b) => (b.account_no ?? b.account?.account_no) === no);
    const a = byAccount("AC-2026-00012");
    const b = byAccount("AC-2026-00013");
    check("CAP-WALK-A billed $36.00", a && Number(a.total) === 36, JSON.stringify(a?.total));
    check("CAP-WALK-B billed $33.00 (CART-35's base at $0.00)", b && Number(b.total) === 33, JSON.stringify(b?.total));
    if (a) await readBill(page, a.id, "15-bulk-bill-A-breakdown", ["Trash 96-gallon cart × 2", "base $3.00", "$15.00 each"]);
    if (b) await readBill(page, b.id, "16-bulk-bill-B-breakdown", ["Trash 96-gallon cart × 1 · base $3.00 · $15.00 each", "Trash 35-gallon cart × 1 · no base price · $15.00 each"]);
  }
} catch (error) {
  check("walk completed", false, String(error).split("\n")[0]);
  await shot(page, "99-failure").catch(() => {});
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed ? 1 : 0);
