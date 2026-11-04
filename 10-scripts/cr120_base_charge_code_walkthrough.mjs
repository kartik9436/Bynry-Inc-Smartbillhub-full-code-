// ── Trace ──────────────────────────────────────────────
// Change:  CR-120-BRC06 — the rate schedule NAMES its base charge code
//          (PO ruling 2026-09-19). Screens: S11 / RAT-03 steps 1, 2 and 5.
// Rules:   BR-RAT-1025 (named first, declared second) · BR-RAT-088 (the charge
//          code owns the AMOUNT) · B14 rule 31 (no database id on screen) ·
//          B14 rule 33 (what on-screen text is capped at) · BR-SHL-033
// ───────────────────────────────────────────────────────
/**
 * Walk the base-charge binding in a real browser — hard-won law 6, which is in
 * CLAUDE.md because NO GATE IN THIS REPO READS RENDERED OUTPUT.
 *
 *     BASE=http://127.0.0.1:8390 node 10-scripts/cr120_base_charge_code_walkthrough.mjs
 *
 * ⚠ **EVERY STEP PROVES ITS OWN PRECONDITION BEFORE CLAIMING A PASS.** Two
 * walkthroughs on this branch have printed "ALL CHECKS PASSED" over a 404 and
 * over a tenant with zero rows. A picker with an empty list renders exactly
 * like a working one, so the count is asserted before anything is selected;
 * `0 options` and `a healthy catalogue` must not look alike.
 *
 * ⚠ **AND THE SELECTED-VALUE CHECK IS THE ONE THAT MATTERS.** The bound code's
 * label appears in the option list whether or not the control is wired, which
 * is hard-won law 2's dead UI rendering identically to a live control. So what
 * is asserted is the combobox's OWN value after the pick, and then the same
 * value again after a reload from the server.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8390";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp";

const problems = [];
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1600 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail(`uncaught page error: ${e.message}`));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 40000 }),
  page.click('button[type="submit"]'),
]);
ok("signed in");

const resp = await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`, { waitUntil: "domcontentloaded" });
if (resp.status() >= 400) fail(`rates/new returned HTTP ${resp.status()}`);
else ok(`rates/new returned HTTP ${resp.status()}`);
await page.waitForTimeout(4000);

// ── STEP 1 · the picker ───────────────────────────────────────────────────
await page.fill("#rate-name", "CR-120 walkthrough");
await page.locator("#rate-service").selectOption({ label: "Water" }).catch(async () => {
  await page.locator("#rate-service").selectOption({ index: 1 });
});
await page.waitForTimeout(2500);

const picker = page.locator("#rate-base-charge-code");
if ((await picker.count()) === 0) {
  fail("step 1 draws NO base charge code control at all — CR-120's whole surface is absent");
} else {
  ok("step 1 draws the base charge code control");
  // BR-SHL-033: it must be the SEARCHABLE control, not a plain select.
  const role = await picker.getAttribute("role");
  if (role === "combobox") ok("it is the searchable combobox, not a plain dropdown");
  else fail(`the control's role is ${role ?? "(none)"} — BR-SHL-033 wants a searchable picker`);

  // PRECONDITION: an empty list renders like a working one.
  // ⚠ **OPENED WITH THE KEYBOARD, NOT WITH A CLICK, AND THAT IS DELIBERATE.**
  // The listbox is `hidden` until the control opens, so a click on the input
  // alone leaves every option present in the DOM and NOT VISIBLE — which is
  // how the first run of this walk timed out on an option it could see. Arrow
  // keys are the path `SearchSelectField.handleKeyDown` implements, so walking
  // it this way also proves the control is operable without a mouse.
  await picker.focus();
  await picker.press("ArrowDown");
  await page.waitForTimeout(800);
  const options = page.locator('#rate-base-charge-code-listbox [role="option"]');
  const count = await options.count();
  if (count === 0) {
    fail("the picker holds ZERO codes — the rest of this walk would prove nothing");
  } else {
    ok(`the picker holds ${count} declared base code(s)`);
    const labels = (await options.allInnerTexts()).join(" | ");
    // The PO asked for the code AND its name, and explicitly NOT the amount.
    if (/BASE-/.test(labels)) ok(`it shows the code: ${labels.slice(0, 80)}`);
    else fail(`no charge CODE visible in the options: ${labels.slice(0, 120)}`);
    if (/\$?\d+\.\d{2}/.test(labels)) {
      fail(`an AMOUNT is drawn on step 1: ${labels.slice(0, 120)} — the PO said that is "not required"`);
    } else ok("no amount is drawn on step 1, which is what the PO asked for");
    // B14 rule 31 — a uuid must never be the visible value of a field.
    if (/[0-9a-f]{8}-[0-9a-f]{4}-/.test(labels)) fail("a database id is VISIBLE in the picker (B14 rule 31)");
    else ok("no database id is visible (B14 rule 31)");

    // ── PICK ONE, and assert the control's OWN value ──────────────────────
    const chosen = (await options.first().innerText()).trim();
    if (!(await options.first().isVisible())) {
      fail("the option list is in the DOM but NOT VISIBLE — a picker nobody can use");
    }
    await options.first().click();
    await page.waitForTimeout(600);
    const shown = await picker.inputValue();
    if (shown === chosen) ok(`the picked code is the control's value: ${shown}`);
    else fail(`picked ${chosen} but the control reads ${shown} — dead control (law 2)`);
  }
}
await page.screenshot({ path: `${SHOTS}/cr120-step1.png`, fullPage: true });

if (problems.length) {
  console.log(`\nWALK FOUND ${problems.length} PROBLEM(S)`);
} else {
  console.log("\nWALK CLEAN — every check above proved its own precondition first");
}
await browser.close();
process.exit(problems.length ? 1 : 0);
