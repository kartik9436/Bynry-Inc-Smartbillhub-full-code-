// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5717 — the tier contiguity refusal threw away the number the
//          server already sends, and only fired on the LAST step.
// Rules:   BR-RAT-032 (CONFIRMED, PO R5-5 — contiguous, half-open boundaries:
//          tier 1 is 0 up to but NOT including 100) · B14 rule 33 (two
//          sentences of six beat one of twelve) · the Plans & Rates blueprint
//          p047 (*"checked here, where the numbers are typed … the message
//          names the two tiers and the two numbers"*)
// ───────────────────────────────────────────────────────
/**
 * Type the PO's own ladder — 0–100 then 101–300 — and read what the screen says.
 *
 *     BASE=http://127.0.0.1:8380 node 10-scripts/def_rat_5717_tier_gap_walkthrough.mjs
 *
 * PO, in the beta, verbatim: *"in tied rates - if tier 1 start from 0 to 100 and
 * tier 2 start from 101 to 300 ; then it give error - tier 2 should start from
 * 100"*.
 *
 * ⚠ **THE PRODUCT WAS RIGHT AND THE MESSAGE WAS AT FAULT**, so this asserts the
 * WORDS and not the refusal. A walkthrough that only checked *"an error
 * appears"* would have passed on the day this was reported.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8380";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL}`);

// ── a NEW schedule, so nothing live is touched ────────────────────────────
note("\n1 · a new tiered water schedule");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
await page.fill("#rate-name", "Tier gap walkthrough");
await page.waitForTimeout(300);
const serviceSel = page.locator("#rate-service");
if (await serviceSel.count()) await serviceSel.selectOption({ index: 1 }).catch(() => {});
await page.waitForTimeout(600);
const uomSel = page.locator("#rate-uom");
if (await uomSel.count()) await uomSel.selectOption({ index: 1 }).catch(() => {});
await page.waitForTimeout(400);
for (let step = 0; step < 2; step += 1) {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (await cont.count()) { await cont.click().catch(() => {}); await page.waitForTimeout(900); }
}
await page.screenshot({ path: `${SHOTS}/rat5717_1_rates_step.png`, fullPage: true });

// ── 2 · the PO's ladder ───────────────────────────────────────────────────
note("\n2 · type 0-100 then 101-300, exactly as reported");
const structure = page.locator("#rate-model");
if (await structure.count()) {
  await structure.selectOption("tiered").catch(() => {});
  await page.waitForTimeout(800);
}
const set = async (id, value) => {
  const f = page.locator(`#${id}`);
  if (await f.count()) { await f.fill(value); await page.waitForTimeout(200); }
};
await set("tier-from-0", "0");
await set("tier-to-0", "100");
await set("tier-price-0", "3.20");

const add = page.getByRole("button", { name: /Add (a )?tier/i }).first();
if (await add.count()) {
  await add.click();
  await page.waitForTimeout(700);
  // 3.b — the new block should already start where the one above ends.
  const prefilled = await page.locator("#tier-from-1").inputValue().catch(() => "");
  if (prefilled === "100") {
    ok(`the new block starts where the one above ends (pre-filled "${prefilled}")`);
  } else {
    fail(`the new block's From came out "${prefilled}" — it should pre-fill 100`);
  }
} else {
  fail("no Add tier control");
}

await set("tier-from-1", "101");
await set("tier-to-1", "300");
await set("tier-price-1", "4.80");
await page.waitForTimeout(600);
await page.screenshot({ path: `${SHOTS}/rat5717_2_gap.png`, fullPage: true });

// ── 3 · the message, on THIS step, naming the number ──────────────────────
note("\n3 · what the screen says — the whole defect");
const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (/Start tier 2 at 100/.test(body)) {
  ok('it says "Start tier 2 at 100." — the PO\'s own ask, answered');
} else {
  fail("the screen does not say which tier or which number");
}
if (/Tier 1 ends there/.test(body)) {
  ok('and "Tier 1 ends there." — both tiers named (blueprint p047)');
} else {
  fail("the message does not name the tier above");
}
// ⚠ AND IT MUST BE HERE, not four steps away.
const onThisStep = await page
  .locator('text=/Start tier 2 at 100/')
  .first()
  .isVisible()
  .catch(() => false);
if (onThisStep) {
  ok("it is visible on the step where the numbers are typed");
} else {
  fail("the message is not on this step — it is still a last-step refusal");
}
// The old sentence must be gone, or two messages say the same thing two ways.
if (/no gap: each tier starts where the one before it ends/.test(body)) {
  fail("the OLD general sentence is still on screen beside the new one");
} else {
  ok("the old general sentence is gone");
}

// ── 4 · fix it, and the message must go ───────────────────────────────────
note("\n4 · type 100 and it clears");
await set("tier-from-1", "100");
await page.waitForTimeout(700);
await page.screenshot({ path: `${SHOTS}/rat5717_3_fixed.png`, fullPage: true });
const after = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (!/Start tier 2 at/.test(after)) {
  ok("the message clears when the ladder runs on");
} else {
  fail("the message stays after the gap is closed — it would read as noise");
}

console.log(
  problems.length === 0
    ? "\nALL CHECKS PASSED"
    : `\n${problems.length} PROBLEM(S):\n - ${problems.join("\n - ")}`,
);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
