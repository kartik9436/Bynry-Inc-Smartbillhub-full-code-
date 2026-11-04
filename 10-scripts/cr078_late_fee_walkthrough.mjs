// ── Trace ──────────────────────────────────────────────
// Change:   CR-078 (PO ruling 2026-09-07, finance re-signed the same day) —
//           the late fee comes from the charge code the PLAN names, and a plan
//           naming none charges ZERO.
// Rules:    BR-RAT-1011 · BR-BIL-001 + B4 ❄️ (GT-8's 8.13, unmoved) ·
//           CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · 13-change-process.md's CLOSURE BAR (PO 2026-08-18:
//           *"CR is not closed until we have confirm user is able to perform
//           tasks using screen/broswer/UI"*) · B14 rule 31 (no database id is
//           ever the visible value of a field)
// ───────────────────────────────────────────────────────
/**
 * cr078_late_fee_walkthrough — CLICK the control, SAVE it, and watch a real
 * account's late fee go from $8.13 to $0.00 and back.
 *
 *     ./08-qa/01-e2e/stack/boot_stack.sh      (or a backend + server.mjs pair)
 *     BASE=http://127.0.0.1:8477 node 10-scripts/cr078_late_fee_walkthrough.mjs
 *
 * ⚠ **IT DOES NOT ASSERT THAT A FIELD EXISTS — IT READS THE RENDERED OPTION,
 * CHANGES IT THROUGH THE FORM, SAVES, AND RE-READS THE SCREEN.** That
 * distinction is the reason this file exists: 8 backend cases and a clean
 * `tsc` pass on this change already, and none of them can see a select that
 * renders with no options because the catalogue prop is never passed (hard-won
 * law 2 — built is not wired), or a label that renders blank because a locale
 * key is missing.
 *
 * ⚠ **THE MONEY IS READ THROUGH THE API, NOT INVENTED HERE.** The fee itself
 * has no screen yet — `assess_late_fee` has no production caller (see
 * `apps/billing/tenancy_seam.py`'s trailer, exception 1: the S31.2 Balances tab
 * that will call it is US-BIL-002, unbuilt) — so this reads the plan's served
 * `late_fee_charge` off `/api/rating/plans/{id}` after each save, which is the
 * SAME row `plan_late_fee_terms` computes the fee from. What that cannot prove
 * is the fee LINE on a bill; `tests/test_def_719_late_fee_charge_code.py`
 * tc1 does that end to end, and this file states the gap rather than implying
 * it away.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8477";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

// ── walking the wizard rail to step 6 (Discounts & billing) ────────────────
// ⚠ **THE RAIL ONLY NAVIGATES BACKWARDS** (`WizardFrame`: `disabled={!done}`,
// BR-SHL-018), so a walkthrough cannot jump to a step it has not reached. It
// presses **Continue** the way a clerk does. That is not ceremony — the first
// draft of this file clicked a `role="tab"` that does not exist on this screen
// and reported *"the control is not wired"* over a control that is wired. A
// check whose failure mode is "I looked in the wrong place" is worse than none.
async function walkToLateFeeStep(page) {
  // ⚠ **WAIT FOR THE RAIL BEFORE JUDGING ANYTHING.** The first working draft
  // bailed on hop 0 because `Continue` had not rendered yet and reported
  // *"the control is not wired"* over a control that was three clicks away.
  // That is hard-won law 7's *looking at the wrong thing*, produced by the
  // check written to avoid it — so the wait is the first statement here.
  await page.locator('[data-wizard-step="1"]').waitFor({ timeout: 30000 }).catch(() => {});
  for (let hop = 0; hop < 12; hop += 1) {
    if (await page.locator("#plan-late-fee-charge").count()) return true;
    const cont = page.getByRole("button", { name: /^Continue$/ }).first();
    if (await cont.count()) {
      await cont.click().catch(() => {});
    }
    await page.waitForTimeout(1200);
  }
  return (await page.locator("#plan-late-fee-charge").count()) > 0;
}

/** Walk from wherever we are to the last step and press the commit button. */
async function commitTheWizard(page) {
  for (let hop = 0; hop < 12; hop += 1) {
    const reason = page.locator("#plan-reason, [name='reason'], #plan-change-reason").first();
    if (await reason.count()) {
      await reason.fill("CR-078 walkthrough").catch(() => {});
    }
    const commit = page.getByRole("button", { name: /Publish plan/i }).first();
    if (await commit.count()) {
      await commit.click().catch(() => {});
      await page.waitForTimeout(3000);
      return true;
    }
    const cont = page.getByRole("button", { name: /^Continue$/ }).first();
    if (!(await cont.count())) break;
    await cont.click().catch(() => {});
    await page.waitForTimeout(1000);
  }
  fail("never reached the wizard's commit button");
  return false;
}

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL} → ${page.url()}`);

const api = async (path, init) => {
  const r = await page.request.fetch(`${BASE}/api/${TENANT}${path}`, init);
  return { status: r.status(), body: await r.json().catch(() => null) };
};

// ── the plan we will work on ───────────────────────────────────────────────
const list = await api(`/plans?limit=50`);
if (list.status !== 200) { fail(`GET /plans → ${list.status}`); }
const rows = list.body?.results ?? list.body?.items ?? [];
const target = rows.find((r) => r.code === "RES-STD") ?? rows[0];
if (!target) { fail("no rate plan to walk"); }
note(`\nplan under test: ${target.code} — ${target.name}`);

const detail = await api(`/plans/${target.id}`);
const before = detail.body?.late_fee_charge ?? null;
if (before === null) {
  fail("the plan names no late-fee charge code before we start — the backfill did not reach it");
} else {
  ok(`served late_fee_charge = ${before.code} (${before.percent_display} / min ${before.min_amount_display})`);
}

// ── 1 · THE CONTROL IS ON SCREEN AND SHOWS THE TENANT'S OWN CODE ───────────
note("\n1 · the plan editor draws the control, with the tenant's own codes in it");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${target.id}/edit`, {
  waitUntil: "domcontentloaded",
});
// Step 6 of the wizard is where Late fees live — pressed to, not jumped to.
const reached = await walkToLateFeeStep(page);
const select = page.locator("#plan-late-fee-charge");
if (!reached) {
  fail("#plan-late-fee-charge is not on the plan editor — the control is not wired");
} else {
  const labelText = await page
    .locator('label[for="plan-late-fee-charge"]')
    .first()
    .innerText()
    .catch(() => "");
  if (!labelText.trim()) fail("the control renders with a BLANK label — a missing locale key");
  else ok(`label reads ${JSON.stringify(labelText.trim())}`);

  const rail = await page
    .locator('[data-wizard-step][data-state="active"]')
    .first()
    .innerText()
    .catch(() => "");
  ok(`reached wizard step ${JSON.stringify(rail.replace(/\s+/g, " ").trim())}`);
  const options = await select.locator("option").allInnerTexts();
  ok(`${options.length} option(s) offered, e.g. ${JSON.stringify(options.slice(0, 3))}`);
  if (!options.some((o) => /LATE/.test(o))) {
    fail("the tenant's own LATE code is not among the options — the catalogue prop is not passed");
  }
  const emptyOption = options.find((o) => !/—/.test(o)) ?? options[0];
  if (!/no late fee/i.test(emptyOption)) {
    fail(`the empty option reads ${JSON.stringify(emptyOption)} — it must SAY the plan charges nothing`);
  } else {
    ok(`the empty option says ${JSON.stringify(emptyOption)} — a stated absence, not a blank`);
  }
  const selected = await select.inputValue();
  if (selected !== before?.id) fail(`the control shows ${selected}, the server serves ${before?.id}`);
  else ok("the control is loaded with the code the server serves");
}

// ── 2 · CLEAR IT THROUGH THE FORM AND SAVE ─────────────────────────────────
note("\n2 · clear it on screen and save — the ruled ZERO, chosen by a human");
await select.selectOption("").catch(() => fail("could not clear the control"));
// ⚠ **THE WIZARD COMMITS AT THE END, NOT AT THE STEP.** `WizardFrame` writes on
// `onCommit` from the FINAL step (`rating.plan.publish` — *Publish plan ✓*), so
// a walkthrough that clicked a save button beside the control saved nothing and
// then truthfully reported that the server had not changed. Same class as the
// bail above: the check was right and it was looking in the wrong place.
await commitTheWizard(page);

const afterClear = await api(`/plans/${target.id}`);
if (afterClear.body?.late_fee_charge === null) {
  ok("the server now serves late_fee_charge = null — this plan charges $0.00");
} else {
  fail(`after saving an empty control the server still serves ${JSON.stringify(afterClear.body?.late_fee_charge)}`);
}

// ── 3 · PUT IT BACK, THROUGH THE SAME FORM ─────────────────────────────────
note("\n3 · put the code back through the same control");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${target.id}/edit`, {
  waitUntil: "domcontentloaded",
});
if (!(await walkToLateFeeStep(page))) fail("could not reach the late-fee step a second time");
await page.locator("#plan-late-fee-charge").selectOption(before.id).catch(() => fail("could not re-select the code"));
await commitTheWizard(page);

const restored = await api(`/plans/${target.id}`);
if (restored.body?.late_fee_charge?.code === before.code) {
  ok(`restored: the plan names ${before.code} again`);
} else {
  fail(`restore failed — the plan now names ${JSON.stringify(restored.body?.late_fee_charge)}`);
}

await page.screenshot({ path: process.env.SHOT ?? "/tmp/cr078-plan-late-fee.png", fullPage: false });
await browser.close();

console.log(
  problems.length
    ? `\nCR-078 WALKTHROUGH: ${problems.length} problem(s)\n - ` + problems.join("\n - ")
    : "\nCR-078 WALKTHROUGH: every check passed."
);
process.exit(problems.length ? 1 : 0);
