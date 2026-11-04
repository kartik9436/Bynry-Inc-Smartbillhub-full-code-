#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-081 — sewer is a percentage of the water VOLUME, priced on a
//           sewer rate schedule of its own. PO 2026-09-07: *"we ahve to apply
//           this method - Way 2 … a percentage of the gallons"*; the six ❄️
//           frozen figures re-signed 2026-09-08: *"C — factor 90%, rate $5.00
//           → $36.00, which is what a real sewer customer actually pays"*.
// Screens:  S31/S30 → bill detail → the sewer line a customer is charged ·
//           S11 → Plans & Rates → the sewer schedule's factor and rate
// Rules:    BR-RAT-1015 · CLAUDE.md hard-won law 6 (no gate reads rendered
//           output — diff the RUNNING app) · hard rule 3 (a quantity always
//           carries its unit) · 13-change-process.md's CLOSURE BAR (PO
//           2026-08-18: *"CR is not closed until we have confirm user is able
//           to perform tasks using screen/broswer/UI"*) · PO's standing rule,
//           2026-09-07: *"everything should be executed based on actual code …
//           ensure you do web walkthorugh before you sign off"*
// ───────────────────────────────────────────────────────
/**
 * READ A SEWER LINE OFF A REAL BILL, IN A REAL BROWSER.
 *
 *     DATABASE_URL=postgres://... python3.12 10-scripts/cr081_seed_sewer_utility.py
 *     BASE=http://127.0.0.1:8080 TENANT=cr081-sewer \
 *       node 10-scripts/cr081_sewer_walkthrough.mjs
 *
 * ⚠ **IT DOES NOT ASSERT THAT A LINE EXISTS — IT READS THE RENDERED TEXT, AND
 * THE THREE THINGS IT LOOKS FOR ARE THE THREE `CR-081` ADDED.** Before this
 * change the sewer line carried NO quantity and NO unit on purpose (*"this line
 * prices DOLLARS, not a metered volume"*), so a screen that renders the amount
 * and drops the other two would look exactly like the old, correct bill —
 * every backend case green, every gate green, and the customer unable to check
 * the figure. That is the failure this file exists to see.
 *
 *   1. the sewer line is on the rendered document at all;
 *   2. it carries a QUANTITY and a UNIT — and the unit is WATER's, because the
 *      quantity is borrowed from the water meter (hard rule 3);
 *   3. the quantity really is 90% of the water line's own quantity on the SAME
 *      bill, and the money really is that quantity times the rate. **Checked
 *      as arithmetic against the neighbouring line, not against a constant** —
 *      a hardcoded 7.2 would pass on a bill whose water line said anything.
 *
 * ⚠ **AND IT ASSERTS THE OLD SENTENCE IS GONE.** *"% of water usage charges"*
 * on a line that now prices a volume is a bill that explains itself wrongly.
 */
import { createRequire } from "node:module";
const require = createRequire(process.env.NODE_MODULES_FROM ?? "/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "cr081-sewer";
const EMAIL = process.env.EMAIL ?? `owner@${TENANT}.test`;
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/cr081";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);
const num = (v) => Number(String(v ?? "0"));

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

// ── 1 · FIND A BILL WITH BOTH A WATER AND A SEWER USAGE LINE ───────────────
note("\n1 · Billing → Bills → a bill carrying water AND sewer");
const list = await (await page.request.get(`${BASE}/api/${TENANT}/invoices?page_size=100`)).json();
const invoices = list.results ?? list.items ?? [];
note(`    ${invoices.length} bill(s) on this utility`);

let found = null;
for (const inv of invoices) {
  const detail = await (await page.request.get(`${BASE}/api/${TENANT}/invoices/${inv.id}`)).json();
  const lines = detail.lines ?? [];
  const svc = (l) => l.service_code ?? l.service ?? "";
  const sewer = lines.filter((l) => svc(l) === "sewer" && (l.kind ?? "") === "usage");
  const water = lines.filter((l) => svc(l) === "water" && (l.kind ?? "") === "usage");
  if (sewer.length && water.length) { found = { id: inv.id, number: inv.number ?? inv.id, sewer, water }; break; }
}

if (!found) {
  fail("no bill on this utility carries both a water and a sewer usage line — nothing to read");
} else {
  ok(`bill ${found.number} carries ${found.water.length} water line(s) and ${found.sewer.length} sewer line(s)`);

  // ── 2 · THE ARITHMETIC, AGAINST THE NEIGHBOURING LINE ────────────────────
  note("\n2 · the arithmetic, checked against the water line on the SAME bill");
  const waterQty = found.water.reduce((a, l) => a + num(l.quantity), 0);
  const sewerQty = found.sewer.reduce((a, l) => a + num(l.quantity), 0);
  const sewerAmt = found.sewer.reduce((a, l) => a + num(l.amount), 0);
  const rate = num(found.sewer[0].unit_price);
  // ⚠ THE KEY IS `unit`. `billing.selectors.invoice_line_row` serialises
  // `"unit": line.unit` — `invoice_lines` names the column `unit` while
  // `tariff_versions` names its own `uom`, and the first draft of this file read
  // `uom ?? unit_of_measure` and got `undefined` for BOTH lines. It then
  // reported *"the sewer line carries no unit"* against a screen that plainly
  // rendered `7.2 kgal`: a check looking at the wrong thing (law 7).
  const unitOf = (l) => l.unit ?? l.uom ?? l.unit_of_measure ?? "";
  const waterUnit = unitOf(found.water[0]);
  const sewerUnit = unitOf(found.sewer[0]);
  note(`    water  ${waterQty} ${waterUnit}`);
  note(`    sewer  ${sewerQty} ${sewerUnit} @ $${rate} = $${sewerAmt.toFixed(2)}`);

  if (!sewerQty) fail("the sewer line carries NO quantity — CR-081's whole point, and hard rule 3");
  else ok("the sewer line carries a quantity");
  if (!sewerUnit) fail("the sewer line carries no unit — hard rule 3, never assume one");
  else if (sewerUnit !== waterUnit) fail(`sewer bills in ${sewerUnit} and water meters in ${waterUnit} — the unit must be BORROWED from the basis`);
  else ok(`the sewer line bills in \`${sewerUnit}\`, the unit water is metered in`);

  const expectedQty = waterQty * 0.9;
  if (Math.abs(sewerQty - expectedQty) > 0.0001) {
    fail(`the sewer quantity is ${sewerQty} and 90% of the bill's own ${waterQty} ${waterUnit} is ${expectedQty}`);
  } else ok(`the sewer quantity IS 90% of this bill's water: ${waterQty} → ${sewerQty} ${waterUnit}`);

  const expectedAmt = Math.round(sewerQty * rate * 100) / 100;
  if (Math.abs(sewerAmt - expectedAmt) > 0.005) {
    fail(`the sewer amount is $${sewerAmt.toFixed(2)} and ${sewerQty} × $${rate} is $${expectedAmt.toFixed(2)}`);
  } else ok(`the money IS the quantity times the rate: $${sewerAmt.toFixed(2)}`);

  // ── 3 · THE RENDERED DOCUMENT — the half no gate can see ─────────────────
  note("\n3 · the bill on the SCREEN (hard-won law 6)");
  await page.goto(`${BASE}/${TENANT}/billing/bills/${found.id}?tab=lines`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  const billText = await page.evaluate(() => document.body.innerText);
  const shown = billText.split("\n").filter((l) => /sewer/i.test(l));
  note("    the sewer line(s), as rendered:");
  for (const l of shown) note(`      ${l}`);

  if (!shown.length) {
    fail("the API serves a sewer line and the SCREEN renders none (hard-won law 2 — built is not wired)");
  } else {
    const text = shown.join(" ");
    ok("the sewer line is on the rendered bill");
    // ⚠ **GUARDED, BECAUSE THE UNGUARDED FORM WAS A FALSE PASS.** With
    // `sewerUnit` empty the regex is `\b\b`, which matches ANY text — so the
    // run printed *"the rendered line shows its unit ``"* as a TICK on the same
    // pass where it had just failed for having no unit at all. Two checks
    // reading the same empty string disagreed, and the reassuring one was the
    // lie. CLAUDE.md law 7's second habit: ask what would make this check pass
    // WRONGLY, not only what makes it fail.
    if (!sewerUnit) {
      fail("cannot check the rendered unit: the API served none, so any assertion here would pass on an empty string");
    } else if (new RegExp(`\\b${sewerUnit}\\b`, "i").test(text)) {
      ok(`the rendered line shows its unit \`${sewerUnit}\``);
    } else {
      fail(`the rendered line shows no unit — the API says ${sewerUnit} and the screen does not`);
    }
    if (new RegExp(String(sewerQty).replace(".", "\\.")).test(text)) ok(`the rendered line shows its quantity ${sewerQty}`);
    else fail(`the rendered line does not show the quantity ${sewerQty}`);
    if (/usage charges/i.test(text)) fail("the line still says `% of water usage charges` — it prices a VOLUME now");
    else ok("the old `% of water usage charges` wording is gone");
    if (/volume/i.test(text)) ok("the line says where its quantity came from (`% of water volume`)");
    else note("    (the line does not name its basis in words — check the description wording)");
  }
  await page.screenshot({ path: `${SHOTS}/bill-sewer-line.png`, fullPage: true });
  note(`    screenshot → ${SHOTS}/bill-sewer-line.png`);
}

// ── 4 · THE SCHEDULE A CLERK CONFIGURES ────────────────────────────────────
note("\n4 · Plans & Rates → the sewer schedule");
await page.goto(`${BASE}/${TENANT}/rates/schedules`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const schedText = await page.evaluate(() => document.body.innerText);
if (/sewer/i.test(schedText)) ok("the sewer schedule is listed");
else fail("no sewer schedule on the Plans & Rates screen");
await page.screenshot({ path: `${SHOTS}/rates-sewer-schedule.png`, fullPage: true });
note(`    screenshot → ${SHOTS}/rates-sewer-schedule.png`);

// ── verdict ────────────────────────────────────────────────────────────────
console.log("");
if (problems.length) {
  console.log(`cr081 walkthrough: ${problems.length} problem(s)`);
  for (const p of problems) console.log("  - " + p);
} else {
  console.log("cr081 walkthrough: clean");
}
await browser.close();
process.exit(problems.length ? 1 : 0);
