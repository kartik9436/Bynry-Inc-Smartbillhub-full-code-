// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5765 — the plan CORRECTION verb has an engine, an endpoint,
//          a client wrapper and 13 backend cases, and no control a clerk can
//          reach. Hard-won law 2 in the shape that costs most: every layer
//          exists, so every check that reads CODE passes.
// Rules:   BR-RAT-1016 (the three verbs: EDIT · CORRECT · CHANGE) · BR-RAT-037
//          (a CHANGE is a new version) · hard rule 4 (a bill locks at issue) ·
//          B14 rule 32/33 (the copy caps) · B14 rule 31 (no database id shown)
// ───────────────────────────────────────────────────────
/**
 * Walk to a published plan as a clerk and prove the CORRECT verb is reachable
 * and distinguishable from the other two, in a real browser.
 *
 *     BASE=http://127.0.0.1:8391 node 10-scripts/def_rat_5765_correct_plan_door_walkthrough.mjs
 *
 * ⚠ **WHAT THIS DEFECT ACTUALLY WAS, BECAUSE THE ROW UNDERSTATES IT.** The row
 * reads as though nothing had been built. It had: `PlanEditIntentPicker` was on
 * the wizard's REVIEW step (step 8) and correctly wired to
 * `POST /plans/{id}/corrections`. The gap was that the ONLY way to reach it was
 * to press `Edit` and walk eight steps — so from the plan detail, and from the
 * Audit tab that lists the very versions a correction restates, the verb was
 * invisible. A clerk who has just found a wrong figure in version 1 had no way
 * to learn that restating it was even possible.
 *
 * ⚠ **STATE ON THE DAY THIS LANDED (2026-09-19): IT REPRODUCES, IT DOES NOT
 * PASS.** The fix it proves spans two files owned by two lanes —
 * `PlanDetail.tsx` (the door) and `PlanWizard.tsx` (reading `?intent=correct`,
 * carried by the lane holding `DEF-RAT-5769`). The halves cannot ship apart: a
 * door labelled *Fix an error* over a builder that ignores the intent files a
 * version bump, which is worse than no door. **So this script is the executable
 * specification of the whole capability, landed FIRST and deliberately red** —
 * hard-won law 2's *"when you write a hold, write the test that fires when the
 * hold expires"*. It was run to ALL CHECKS PASSED against both halves applied
 * together in a private worktree before being landed in this state, so its
 * green is known to be reachable rather than hoped for.
 *
 * ⚠ **CHECK 4 IS THE ONE THAT MATTERS, AND IT IS THE ONE THE DEFECT ROW NAMES.**
 * Checks 1–3 prove the control is on screen and says the right words. Check 4
 * asserts the REQUEST — that pressing it reaches `POST /plans/{id}/corrections`
 * and that `plans.version` did NOT move — because a rendered button proves
 * nothing about what it calls, and a "correction" that bumped the version would
 * be a plan CHANGE wearing a correction's clothes.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8391";
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
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();

// ⚠ **THE CORRECTION CALL IS WATCHED, AND THAT IS THE POINT OF THE WHOLE
// SCRIPT.** DEF-RAT-5765's own row says it: assert the REQUEST, not the
// rendering. A button that renders and calls `PATCH /plans/{id}` is the defect
// still present, wearing the fix's clothes.
let correctCall = null;
let patchCall = null;
page.on("response", async (r) => {
  const u = new URL(r.url());
  const m = r.request().method();
  if (u.pathname.includes("/plans/")) {
    if (u.pathname.endsWith("/corrections") && m === "POST") {
      let body = ""; try { body = (await r.text()).slice(0, 300); } catch {}
      correctCall = { status: r.status(), body };
    }
    if (m === "PATCH") patchCall = { path: u.pathname, status: r.status() };
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL}`);

// ── 0 · a plan that is PUBLISHED and NOT ALREADY CORRECTED ───────────────
//
// ⚠ **THE SECOND HALF OF THAT HEADING IS WHY THIS SCRIPT IS RE-RUNNABLE.**
// `BR-RAT-1016` lets a filed version be corrected ONCE — a second attempt is
// refused `409 BIZ-STATE rating.plans.already_corrected`, correctly. A first
// draft of this walkthrough took the first published plan every time, passed on
// the first run, and failed on the second against a server that was behaving
// exactly as ruled. A check that only works once is a check that will be read
// as a regression by the next person to run it.
await page.goto(`${BASE}/${TENANT}/plans-rates/plans`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2200);
const rows = page.locator("table tbody tr").filter({ hasText: /Active|Published/i });
const rowCount = await rows.count();
if (rowCount === 0) { fail("no published plan — nothing to correct"); await browser.close(); process.exit(1); }

let planId = "";
let versionBefore = null;
let chosen = "";
for (let i = 0; i < rowCount; i += 1) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1600);
  const candidate = page.locator("table tbody tr").filter({ hasText: /Active|Published/i }).nth(i);
  const label = (await candidate.innerText()).replace(/\s+/g, " ").trim().slice(0, 70);
  await candidate.locator("button.rating-link, a, button").first().click();
  await page.waitForTimeout(2000);
  const id = page.url().split("/plans/")[1]?.split(/[/?#]/)[0] ?? "";
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}?tab=audit`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForTimeout(1800);
  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  if (/This filing was corrected/i.test(text)) {
    note(`    skipping ${label} — its filing has already been corrected`);
    continue;
  }
  planId = id;
  chosen = label;
  const vm = text.match(/\bV(\d+)\b/);
  versionBefore = vm ? vm[1] : null;
  break;
}
if (planId === "") {
  fail("every published plan has already been corrected — seed a fresh one to re-run this");
  await browser.close();
  process.exit(1);
}
note(`\n0 \u00b7 ${chosen}`);
note(`    plan detail: ${BASE}/${TENANT}/plans-rates/plans/${planId}`);
note(`    plan version before: ${versionBefore === null ? "(not found)" : "V" + versionBefore}`);

// ── 1 · the CORRECT verb is on the plan detail, BY NAME ───────────────────
note("\n1 \u00b7 DEF-RAT-5765 \u2014 the correction affordance exists on the plan detail");
const auditTab = page.getByRole("tab", { name: /audit/i });
if (await auditTab.count()) {
  await auditTab.first().click();
  await page.waitForTimeout(1600);
}
await page.screenshot({ path: `${SHOTS}/rat5765_1_audit.png`, fullPage: true });
const door = page.getByRole("link", { name: /Fix an error/i }).first();
if (await door.count()) {
  ok("the Audit tab offers `Fix an error`");
} else {
  fail("NO correction affordance on the plan detail \u2014 the three verbs are indistinguishable");
}
// B14 rule 31 — a database id is never the visible value of a field.
const auditText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (planId && auditText.includes(planId)) fail("B14 rule 31: a database id is on screen");
else ok("no database id on screen (B14 rule 31)");

if (!(await door.count())) {
  note(`\n${"=".repeat(60)}`);
  note(`${problems.length} PROBLEM(S) \u2014 stopping before the request check`);
  problems.forEach((p) => note("  \u2717 " + p));
  await browser.close();
  process.exit(1);
}

// ── 2 · it opens the builder ALREADY CORRECTING ───────────────────────────
note("\n2 \u00b7 the door opens the builder in correction mode, not change mode");
await door.click();
await page.waitForTimeout(3000);
await page.screenshot({ path: `${SHOTS}/rat5765_2_builder.png`, fullPage: true });
if (/intent=correct/.test(page.url())) ok(`the builder opened at ${page.url().split("/edit")[1]}`);
else fail(`the door did not carry the intent: ${page.url()}`);
// ⚠ **THE PICKER IS ON THE REVIEW STEP TODAY.** `PlanEditIntentPicker`'s own
// docstring calls it "the last thing inside Edit". The PO asked on 2026-09-19
// for it on step 1 (`DEF-RAT-5769`, another lane). So this walks forward to
// wherever it is and reads its state — it passes either way, and stops
// immediately once the move lands.
let sawPicker = false;
for (let i = 0; i < 10; i += 1) {
  const chosen = await page.locator('input[name="plan-edit-intent"]:checked').count();
  if (chosen > 0) { sawPicker = true; break; }
  // ⚠ **SCOPED TO THE FOOTER, AND THAT IS NOT TIDINESS.** The step RAIL draws
  // a button per step whose number sits in an `aria-hidden` span, so step 8's
  // accessible name is exactly `Review & activate` — and a rail button beyond
  // the furthest validated step is DISABLED (`BR-SHL-018`). An unscoped
  // `getByRole(...).first()` therefore finds a disabled RAIL button, reports
  // the walk stalled, and blames the product for the selector's mistake. It
  // did, on the first run of this script.
  const next = page.locator('[data-wizard="actions"]').getByRole("button", {
    name: /^(Next|Continue|Review)/i,
  }).last();
  if (!(await next.count()) || !(await next.isEnabled())) break;
  await next.click();
  await page.waitForTimeout(900);
}
if (sawPicker) {
  const value = await page.locator('input[name="plan-edit-intent"]:checked').getAttribute("value");
  if (value === "correct") ok("the builder is CORRECTING, chosen for the clerk by the door");
  else fail(`the builder opened on "${value}" \u2014 a correction would be filed as a version bump`);
  await page.screenshot({ path: `${SHOTS}/rat5765_3_correcting.png`, fullPage: true });
  const pickerText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  // Hard rule 4, and NO FIGURE beside the word bills: nothing on `invoices`
  // points back at a plan (BR-BIL-030) and the only link that exists counts
  // LINES and over-counts a shared tariff (OQ-185).
  if (/Bills already sent keep their prices/i.test(pickerText)) {
    ok("it states what the correction cannot reach (hard rule 4)");
  } else {
    fail("nothing states that issued bills keep their prices");
  }
  if (/\d+\s+bills/i.test(pickerText)) fail("a COUNT is drawn beside the word bills (OQ-185)");
  else ok("no bill count is invented (OQ-185)");
} else {
  fail("the builder never showed the change-vs-correction picker");
}

// ── 3 · THE REQUEST, and the version that must NOT move ───────────────────
note("\n3 \u00b7 the commit reaches POST /plans/{id}/corrections \u2014 the REQUEST, not the render");
// ⚠ **THE REASON IS A PARAMETER OF THE ACT, NOT A FIELD THIS SCRIPT IS BEING
// POLITE ABOUT.** `correct_plan_version` refuses without one — the first run of
// this walkthrough committed with it empty and the server answered
// `422 VAL-001 rating.plans.correction_reason`, correctly. It answers *what was
// recorded wrongly*, which is NOT `BR-RAT-037`'s filing note.
const reasonBox = page.locator("#plan-reason");
if (await reasonBox.count()) {
  await reasonBox.fill("The demand rate was keyed from the wrong tariff sheet.");
  ok("the correction reason is asked for, by its own name");
  await page.waitForTimeout(300);
} else {
  fail("no correction reason field \u2014 the server will refuse this correction");
}
const saveDraft = page.getByRole("button", { name: /Save draft & exit/i }).first();
if (await saveDraft.count()) {
  await saveDraft.click();
  await page.waitForTimeout(3500);
}
await page.screenshot({ path: `${SHOTS}/rat5765_4_after.png`, fullPage: true });
if (correctCall && correctCall.status >= 200 && correctCall.status < 300) {
  ok(`POST /plans/{id}/corrections -> ${correctCall.status}`);
} else if (correctCall) {
  fail(`the corrections endpoint answered ${correctCall.status}: ${correctCall.body}`);
} else {
  fail("NO POST to /plans/{id}/corrections \u2014 the control does not call the correction endpoint");
}
if (patchCall) fail(`it called PATCH ${patchCall.path} \u2014 that is verb 3, a version bump`);
else ok("no PATCH \u2014 this was not filed as a plan change");

// ── 4 · THE RESULT IS VISIBLE, which is the half a render proves nothing about
note("\n4 \u00b7 the plan detail shows the correction, and the version did NOT move");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${planId}?tab=audit`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/rat5765_5_result.png`, fullPage: true });
const after = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (/Correction/i.test(after)) ok("the versions list marks the correction");
else fail("the correction is not visible on the versions list");
if (/This filing was corrected/i.test(after)) ok("the superseded filing says so");
else fail("the corrected filing is not marked");
// ⚠ **THE INVARIANT.** A plan version has no window (`OQ-324` — CLOSED (B) 2026-10-03; it has one now and a correction copies it), so the COUNTER
// is what a correction holds fixed: `version_no` is copied and `plans.version`
// does not move. If it moved, this was a CHANGE wearing a correction's clothes
// and 75 `unit_plan_assignments.plan_version` rows now point at a number the
// plan no longer means (BR-CUS-013).
if (versionBefore !== null) {
  const m = after.match(/\bV(\d+)\b/);
  const versionAfter = m ? m[1] : null;
  if (versionAfter === versionBefore) ok(`the plan is still V${versionAfter} \u2014 the counter held`);
  else fail(`the plan version moved ${versionBefore} \u2192 ${versionAfter} \u2014 that is verb 3`);
}

note(`\n${"=".repeat(60)}`);
if (problems.length === 0) { note("ALL CHECKS PASSED"); }
else { note(`${problems.length} PROBLEM(S):`); problems.forEach((p) => note("  \u2717 " + p)); }
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
