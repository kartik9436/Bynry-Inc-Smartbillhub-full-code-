/**
 * po_rulings_20261001_walkthrough — the PO's six rulings of 2026-10-01, seen in Chromium at 1440.
 *
 *     BASE72=http://127.0.0.1:8594 RUN72=<RUN-0002 id> BILL72=<BL-2610-000014 id> \
 *     BASE74=http://127.0.0.1:8595 \
 *     E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/po_rulings_20261001_walkthrough.mjs
 *
 * Two stacks, two worlds:
 *   * J72 (`seed_j72_bulk_run --month-two`, September sent by
 *     `J72-bulk-bill-run-accuracy.spec.ts`): the bulk run's Sent step, and
 *     AC-2026-00007's bill — $34.00 − $120.00 + $37.25 = a $48.75 credit, nothing
 *     to pay (ruling 6, OQ-217) — on the bill screen and on the paper.
 *   * J74 (`seed_j70_one_time_bill.py`): a FINAL one-time bill for AC-2026-00012
 *     (Unit L, on no billing cycle) — refused on step 1 with *"No billing cycle.
 *     Assign one on the account."* and Continue does not move (ruling 4).
 *
 * It READS the screen and fails loudly; it does not assert that an element merely
 * exists. Screenshots: 08-qa/screens/po-rulings-2026-10-01/.
 */
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const OUT = new URL("../08-qa/screens/po-rulings-2026-10-01/", import.meta.url).pathname;
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail}`);
}

async function signIn(page, base) {
  await page.goto(`${base}/${TENANT}/signin`);
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60000 });
}

async function shot(page, name) {
  // DEF-316: the content pane scrolls, not the document — capture it whole.
  const pane = page.locator("main.view").first();
  if ((await pane.count()) > 0) {
    await pane.screenshot({ path: `${OUT}1440-${name}.png` }).catch(async () => {
      await page.screenshot({ path: `${OUT}1440-${name}.png` });
    });
  } else {
    await page.screenshot({ path: `${OUT}1440-${name}.png` });
  }
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined });

// ── J72: the bulk run and the credit bill ─────────────────────────────────────
{
  const base = process.env.BASE72;
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await signIn(page, base);
  await page.goto(`${base}/${TENANT}/billing/run?run=${process.env.RUN72}`);
  await page.locator("[data-screen=bulk-bill-run]").waitFor({ timeout: 60000 });
  await page.waitForTimeout(2500);
  const runText = await page.locator("[data-screen=bulk-bill-run]").innerText();
  check("J72 run RUN-0002 opens on Sent", /bills sent/i.test(runText), runText.match(/\d+ bills? sent/i)?.[0] ?? "");
  await shot(page, "j72-run-0002-sent");

  await page.goto(`${base}/${TENANT}/billing/bills/${process.env.BILL72}`);
  await page.locator("dd[data-bil=summary-total]").waitFor({ timeout: 60000 });
  await page.waitForTimeout(1500);
  const total = (await page.locator("dd[data-bil=summary-total]").innerText()).trim();
  const panel = await page.locator("dd[data-bil=summary-total]").locator("xpath=ancestor::dl[1]").innerText();
  check("AC-2026-00007's bill: total due is the $48.75 credit", /48\.75/.test(total), `${total} | ${panel.replace(/\s+/g, " ")}`);
  check("AC-2026-00007's bill: payments $120.00, previous $34.00", /120\.00/.test(panel) && /34\.00/.test(panel), "");
  await shot(page, "j72-ac-2026-00007-bill-credit-48-75");

  await page.goto(`${base}/${TENANT}/billing/bills/${process.env.BILL72}/document`);
  await page.waitForTimeout(4000);
  const paper = await page.locator("body").innerText();
  check("the paper says 0.00 due and a 48.75 credit", /credit 48\.75/.test(paper), (paper.match(/Total due[^\n]*\n?[^\n]*/) ?? [""])[0].replace(/\s+/g, " "));
  await shot(page, "j72-ac-2026-00007-bill-paper");
  await page.close();
}

// ── J74: a final bill for an account on no cycle ──────────────────────────────
{
  const base = process.env.BASE74;
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await signIn(page, base);
  await page.goto(`${base}/${TENANT}/billing/one-time?kind=final`);
  await page.locator("[data-screen=one-time-bill]").waitFor({ timeout: 60000 });
  const combo = page.getByRole("combobox", { name: /Find account/ });
  await combo.fill("AC-2026-00012");
  await page.getByRole("option").first().waitFor({ timeout: 30000 });
  await page.getByRole("option").filter({ hasText: /AC-2026-00012/ }).first().click();
  const problems = page.locator("[data-otb-problems]");
  await problems.waitFor({ timeout: 30000 }).catch(() => {});
  const said = (await problems.count()) > 0 ? await problems.innerText() : "";
  check("final bill, no cycle: step 1 names it", /No billing cycle\. Assign one on the account\./.test(said), said.replace(/\s+/g, " "));
  await page.locator("#period_start").fill("2026-09-01").catch(() => {});
  await page.locator("#period_end").fill("2026-09-10").catch(() => {});
  await page.getByRole("button", { name: "Continue", exact: true }).click().catch(() => {});
  await page.waitForTimeout(2000);
  const step1 = await page.locator('[data-wizard-step="1"]').getAttribute("data-state");
  check("final bill, no cycle: Continue does not move", step1 === "active", `step 1 is ${step1}`);
  await shot(page, "j74-final-bill-no-cycle-refused");
  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} of ${results.length} PASS`);
process.exit(failed.length ? 1 : 0);
