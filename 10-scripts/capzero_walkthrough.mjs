/**
 * capzero_walkthrough — "a $0.00 capacity line is left off the bill" (PO 2026-10-17,
 * DEF-RAT-10210), walked in Chromium at 1440 after `capzero_walk_prep.py`.
 *
 *   1. A bulk run for September on CAP0-SOLAR: Check → Price → Sign off → Send.
 *   2. Each bill's Charges tab, its document and its PDF text: the flat-fee
 *      account (solar 6 kW + battery 10 kW at $0/kW, BASE-SOL/BASE-BAT $25.00)
 *      shows two $25.00 lines, tax $2.00, total $52.00, and no "$0.00" line;
 *      Municipal Solar shows 6 kW × $4.00 = $24.00, $10.00, tax $1.36, $35.36.
 *   3. The customer portal's bill page and printed bill for both.
 *
 *     BASE=http://127.0.0.1:8110 E2E_CHROMIUM_EXECUTABLE=… node 10-scripts/capzero_walkthrough.mjs
 *
 * It READS the screen and fails loudly. Screenshots: OUT (default
 * 05-prototype/walk-capacity-zero-line-2026-10-17/).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const OUT = process.env.OUT ?? new URL("../05-prototype/walk-capacity-zero-line-2026-10-17/", import.meta.url).pathname;
const BASE = process.env.BASE ?? "http://127.0.0.1:8110";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const PORTAL_PASSWORD = "Sunfield-2026!";
const RUN_ID = process.env.RUN_ID ?? "";
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
}

async function shot(page, name, full = true) {
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage: full });
}

async function onStep(page, label, timeout = 30000) {
  try {
    await page.locator("[data-wizard=rail] [aria-current=step]").filter({ hasText: label }).waitFor({ timeout });
    return true;
  } catch {
    return false;
  }
}

const flat = (s) => s.replace(/\s+/g, " ");

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const api = `${BASE}/api/${TENANT}`;
const facts = {};
try {
  await page.goto(`${BASE}/${TENANT}/signin`);
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60000 });

  let runId = RUN_ID;
  if (!runId) {
    // ── 1. Scope: September on CAP0-SOLAR ────────────────────────────────────
    await page.goto(`${BASE}/${TENANT}/billing/run`);
    await page.locator("[data-screen=bulk-bill-run]").waitFor({ timeout: 30000 });
    await page.locator("#label").fill("September 2026 · solar $0 walk");
    const cycle = page.locator("#cycle_id");
    const option = cycle.locator("option").filter({ hasText: /CAP0-SOLAR/ });
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
    await shot(page, "01-run-scope");
    await page.getByRole("button", { name: "Start checking", exact: true }).click();
    await page.locator("[data-check-results]").waitFor({ timeout: 180000 });
    await shot(page, "02-run-check");
    const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
    await price.waitFor({ timeout: 30000 });
    check("Check offers to price both accounts", /Price 2 accounts/.test(await price.innerText()), await price.innerText());
    await price.click();
    check("Price opens Sign off", await onStep(page, "Sign off", 240000), page.url());
    runId = new URL(page.url()).searchParams.get("run");
    await shot(page, "03-run-signoff");
    const signoffText = flat(await page.locator("main").innerText());
    facts.signoff = signoffText.slice(0, 1500);
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
    await shot(page, "04-run-send");
    await sendRegion.getByRole("checkbox", { name: "I checked the totals" }).check();
    await actions.getByRole("button", { name: /^Send \d+ bills?$/ }).click();
    await page.locator("[data-sent-card]").waitFor({ timeout: 180000 });
    await shot(page, "05-run-sent");
  }
  facts.runId = runId;

  // ── 2. The bills, by the database's own answer ─────────────────────────
  const bills = await page.evaluate(async ([api, runId]) => {
    const r = await fetch(`${api}/invoices?f.bill_run_id=${runId}&per=200`, { credentials: "include" });
    return (await r.json()).results ?? [];
  }, [api, runId]);
  const byName = (re) => bills.find((b) => re.test(JSON.stringify(b)));
  const flatBill = byName(/Rosa Delgado|CAP0-FLAT/);
  const muniBill = byName(/Hal Brenner|CAP0-MUNI/);
  check("flat-fee bill total $52.00", flatBill && Number(flatBill.total) === 52, JSON.stringify(flatBill?.total));
  check("Municipal Solar bill total $35.36", muniBill && Number(muniBill.total) === 35.36, JSON.stringify(muniBill?.total));

  for (const [bill, tag, expectIn] of [
    [flatBill, "flat", ["25.00", "2.00", "52.00"]],
    [muniBill, "muni", ["24.00", "10.00", "1.36", "35.36"]],
  ]) {
    if (!bill) continue;
    const detail = await page.evaluate(async ([api, id]) => {
      const r = await fetch(`${api}/invoices/${id}`, { credentials: "include" });
      return await r.json();
    }, [api, bill.id]);
    const lines = (detail.lines ?? []).map((l) => ({
      kind: l.kind, description: l.description, quantity: l.quantity, unit: l.unit,
      unit_price: l.unit_price, amount: l.amount,
    }));
    facts[`${tag}_lines`] = lines;
    const zero = lines.filter((l) => l.kind !== "tax" && Number(l.amount) === 0);
    check(`${tag}: no stored $0.00 charge line`, zero.length === 0, JSON.stringify(zero));

    await page.goto(`${BASE}/${TENANT}/billing/bills/${bill.id}?tab=lines`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    const text = flat(await page.locator("main").innerText());
    facts[`${tag}_detail_text`] = text.slice(0, 2500);
    check(`${tag}: bill detail shows ${expectIn.join(", ")}`, expectIn.every((e) => text.includes(e)), "");
    check(`${tag}: bill detail has no "× $0.00" capacity row`, !/×\s*\$0\.00/.test(text) && !/@ \$?0\.00/.test(text), "");
    await shot(page, `1${tag === "flat" ? 0 : 5}-${tag}-bill-detail-charges`);
    await page.evaluate(() => {
      const el = [...document.querySelectorAll("h2,h3,h4,p,div,span")].find(
        (n) => n.childElementCount === 0 && /^every charge$/i.test((n.textContent ?? "").trim()),
      );
      el?.scrollIntoView({ block: "start" });
    });
    await shot(page, `1${tag === "flat" ? 2 : 7}-${tag}-bill-detail-every-charge`, false);

    await page.goto(`${BASE}/${TENANT}/billing/bills/${bill.id}/document`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2500);
    await shot(page, `1${tag === "flat" ? 1 : 6}-${tag}-bill-document`);
    await page.mouse.move(840, 650);
    await page.mouse.wheel(0, 650);
    await shot(page, `1${tag === "flat" ? 3 : 8}-${tag}-bill-document-charges`, false);

    const pdf = await page.evaluate(async ([api, id]) => {
      const r = await fetch(`${api}/invoices/${id}/document.pdf`, { credentials: "include" });
      const buf = new Uint8Array(await r.arrayBuffer());
      let s = "";
      for (const b of buf) s += String.fromCharCode(b);
      return { status: r.status, type: r.headers.get("content-type"), b64: btoa(s) };
    }, [api, bill.id]);
    if (pdf.status === 200) writeFileSync(`${OUT}${tag}-bill.pdf`, Buffer.from(pdf.b64, "base64"));
    check(`${tag}: PDF served`, pdf.status === 200, `${pdf.status} ${pdf.type}`);
    facts[`${tag}_number`] = detail.invoice_no ?? detail.number ?? bill.invoice_no ?? bill.number;
  }

  // ── 3. The customer portal ─────────────────────────────────────────────
  for (const [tag, email] of [["flat", "cap0-flat@example.com"], ["muni", "cap0-muni@example.com"]]) {
    const number = facts[`${tag}_number`];
    if (!number) continue;
    const portal = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const p = await portal.newPage();
    const r = await p.request.post(`${api}/portal/auth/sign-in`, { data: { email, password: PORTAL_PASSWORD } });
    check(`${tag}: portal sign-in`, r.ok(), String(r.status()));
    await p.goto(`${BASE}/${TENANT}/portal/bills/${encodeURIComponent(number)}`);
    await p.waitForLoadState("networkidle");
    await p.waitForTimeout(2000);
    const text = flat(await p.locator("body").innerText());
    facts[`${tag}_portal_text`] = text.slice(0, 2500);
    check(`${tag}: portal bill has no "× $0.00" row`, !/×\s*\$0\.00/.test(text) && !/@ \$?0\.00/.test(text), "");
    await p.screenshot({ path: `${OUT}2${tag === "flat" ? 0 : 5}-${tag}-portal-bill.png`, fullPage: true });
    await p.goto(`${BASE}/${TENANT}/portal/bills/${encodeURIComponent(number)}/document`);
    await p.waitForLoadState("networkidle");
    await p.waitForTimeout(2500);
    await p.screenshot({ path: `${OUT}2${tag === "flat" ? 1 : 6}-${tag}-portal-printed-bill.png`, fullPage: true });
    await portal.close();
  }
} catch (error) {
  check("walk completed", false, String(error).split("\n")[0]);
  await shot(page, "99-failure").catch(() => {});
} finally {
  writeFileSync(`${OUT}walk-facts.json`, JSON.stringify(facts, null, 2));
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed ? 1 : 0);
