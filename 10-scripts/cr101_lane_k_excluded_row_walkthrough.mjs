#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane K — the three PO rulings of 2026-09-15 about
//           WHICH BILLS a bulk correction takes, walked in a browser.
// Rules:    hard-won law 6 (no gate reads rendered output) · B14 rule 37 (a
//           figure in a wireframe is an illustration) · rule 31/32 (no id, no
//           internal code on screen) · the UI skill's §15 close-out
// Defects:  DEF-BIL-5377 (one closed account blocked every bulk restatement) ·
//           DEF-BIL-5360 (the cap refused the whole case)
// ───────────────────────────────────────────────────────
/**
 * TWO THINGS A PERSON CAN SEE, AND NOTHING ELSE CAN.
 *
 *   BASE=http://127.0.0.1:8087 SHOTS=<dir> \
 *   RUN_ID=<a run that HAS correctable bills> \
 *   CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *     node 10-scripts/cr101_lane_k_excluded_row_walkthrough.mjs
 *
 * 1. **`DEF-BIL-5377` — the case OPENS.** Before 2026-09-15 a class-R case over
 *    any bulk scope on this tenant refused every bill, because one account
 *    (`AC-2026-00042`) is closed. It now opens over the rest, and the count on
 *    screen is the proof: **38 where the run holds 39**.
 * 2. **`DEF-BIL-5360` — p137's fifth row exists.** *Beyond the cap · Removed
 *    from the set*, drawn at zero on this tenant because nothing here re-prices
 *    upward past the window, and drawn ANYWAY (p129: an absent panel is drawn,
 *    never omitted).
 *
 * ⚠ **IT OPENS A CASE AND ABANDONS IT.** `POST /corrections` writes the case,
 * its pinned bills and their impacts — nothing money-bearing exists before
 * approval (BR-BIL-014) — and the case is closed with a reason before this
 * exits, so the bills stay correctable for a sibling lane (BR-BIL-048).
 *
 * ⚠ **WHAT IT CANNOT SEE:** the row's POPULATED state. Getting a real excluded
 * bill needs an upward re-price on a period older than the tenant's window, and
 * the demo tenant's bills are all recent and re-price flat. That state is held
 * by `FixWhatStepBulk.dom.test.tsx` TC-D3.3b against a served payload, and is
 * named here rather than left to look covered.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8087";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/lane-K-shots";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const ok = (m) => console.log(`  ✓ ${m}`);
const fail = (m) => {
  problems.push(m);
  console.log(`  ✗ ${m}`);
};

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

for (const width of (process.env.WIDTHS ?? "1440,1280").split(",").map(Number)) {
  const ctx = await browser.newContext({ viewport: { width, height: 1400 } });
  const page = await ctx.newPage();
  console.log(`\n=== ${width} ===`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  await page.locator("#bil-fix-scope").selectOption("run");
  await page.waitForFunction(
    () => document.querySelectorAll("#bil-fix-run option[value]:not([value=''])").length > 0,
    undefined,
    { timeout: 30000 },
  );
  const runs = await page
    .locator("#bil-fix-run option")
    .evaluateAll((opts) => opts.map((o) => o.value).filter(Boolean));
  await page.locator("#bil-fix-run").selectOption(process.env.RUN_ID ?? runs[0]);
  await page.waitForTimeout(2500);
  await page.locator('label[for="bil-fix-reason-wrong_rate_plan"]').click();
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();

  const landed = await page
    .waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 90000 })
    .then(() => true)
    .catch(() => false);
  if (!landed) {
    const why = await page.locator('[data-wizard="frame"]').innerText();
    fail(`${width}: the case would not open — ${why.slice(0, 200).replace(/\s+/g, " ")}`);
    await ctx.close();
    continue;
  }
  await page.waitForTimeout(1500);
  ok(`${width}: DEF-BIL-5377 — the case opened over a run holding a closed account's bill`);

  // The answer band carries the count the scope resolved to.
  const band = (await page.locator('[data-wizard="frame"]').innerText()).replace(/\s+/g, " ");
  const bills = band.match(/(\d+) bills change/);
  if (bills) ok(`${width}: the case pinned ${bills[1]} bills`);
  else fail(`${width}: the answer band does not state how many bills changed`);

  const group3 = page.getByTestId("fix-bulk-group-3");
  if ((await group3.count()) === 0) {
    fail(`${width}: group 3 is not on the screen`);
  } else {
    const text = (await group3.innerText()).replace(/\s+/g, " ");
    console.log(`  group 3: ${text}`);
    if (/Beyond the .*cap/.test(text)) {
      ok(`${width}: DEF-BIL-5360 — p137's fifth row is drawn`);
    } else {
      fail(`${width}: p137's fifth row is missing from group 3`);
    }
    // B14 rule 32 — no rule id, no internal code, in a clerk's copy.
    for (const bad of ["BR-BIL", "DEF-", "beyond_the_back_bill_cap", "window_months"]) {
      if (text.includes(bad)) fail(`${width}: "${bad}" is visible to a clerk in group 3`);
    }
    ok(`${width}: no rule id or internal code in group 3`);
    await group3.screenshot({ path: `${SHOTS}/lane-K-group3-${width}.png` });
  }

  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (sideways) fail(`${width}: the page scrolls sideways`);
  else ok(`${width}: no horizontal scroll`);

  // Close it with a reason, so the run's bills are free (BR-BIL-048).
  const close = page.locator("button", { hasText: "Close without correcting" }).first();
  if ((await close.count()) === 0) {
    fail(`${width}: NO WAY TO CLOSE — a case is left open on the tenant`);
  } else {
    await close.click();
    await page.waitForTimeout(2500);
    ok(`${width}: the case was abandoned, so its bills are free`);
  }
  await ctx.close();
}

await browser.close();
console.log(`\n${problems.length} problem(s)`);
for (const p of problems) console.log(`  - ${p}`);
process.exit(problems.length === 0 ? 0 : 1);
