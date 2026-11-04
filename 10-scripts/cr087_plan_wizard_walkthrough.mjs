// ── Trace ──────────────────────────────────────────────
// Change:   CR-087 D1–D4 (PO rulings 2026-09-08) — the plan wizard's steps 1
//           to 7, redrawn. `PRB-15` `PRB-16` `PRB-17` `PRB-18` `PRB-24`
//           `PRB-25` `PRB-26`.
// Rules:    BR-RAT-024 / BR-RAT-100 as amended (the ELEVEN services, the
//           switched-off ones named) · BR-RAT-102 (the surcharge's two gates) ·
//           BR-RAT-1011 / CR-078 (the late fee comes off the charge code) ·
//           CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) and law 2 (built is not wired) ·
//           13-change-process.md's CLOSURE BAR, PO 2026-08-18: *"CR is not
//           closed until we have confirm user is able to perform tasks using
//           screen/broswer/UI"*
// ───────────────────────────────────────────────────────
/**
 * Walk steps 1 to 7 of the plan wizard in a real browser, TYPE 15 into the
 * surcharge box, and PRESS the Add button.
 *
 *     BASE=http://127.0.0.1:8080 node 10-scripts/cr087_plan_wizard_walkthrough.mjs
 *
 * ⚠ **IT READS THE RENDERED SCREEN, NOT THE COMPONENT.** 33 vitest cases and a
 * clean `tsc` pass on this change already, and not one of them can see a locale
 * key that renders blank, a tile grid that lays out as slivers, or a control
 * that is present and dead — which is hard-won law 2, the defect class this
 * repo keeps paying for.
 *
 * ⚠ **THE RAIL ONLY NAVIGATES BACKWARDS** (`WizardFrame`, `BR-SHL-018`), so
 * this presses **Continue** the way a clerk does rather than jumping. A
 * previous walkthrough in this directory recorded the cost of getting that
 * wrong: it clicked a `role="tab"` that does not exist and reported *"the
 * control is not wired"* over a control that was wired.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL} → ${page.url()}`);

async function continueOn() {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (!(await cont.count())) return false;
  await cont.click().catch(() => {});
  await page.waitForTimeout(900);
  return true;
}

// ── STEP 1 · Basics ────────────────────────────────────────────────────────
note("\n1 · Basics (PRB-15) — five blocks of prose became one");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "domcontentloaded" });
await page.locator("#plan-name").waitFor({ timeout: 30000 });
const step1 = await page.locator("body").innerText();
note(`   heading: ${(step1.split("\n").find((l) => l.includes("?")) ?? "").trim()}`);
const oneNote = step1.includes("The name is what customers see on their bills");
oneNote ? ok("the one surviving sentence is on screen") : fail("the step-1 sentence is missing");
if (/where it appears|self-service|move-in Plan step/i.test(step1)) {
  fail("a help paragraph describing WHERE a value appears is still drawn");
} else {
  ok("no help paragraph describing where a value would later appear");
}
await page.fill("#plan-name", "CR-087 walkthrough plan");
await page.fill("#plan-code", `CR087-${Date.now().toString().slice(-6)}`);
const classOptions = await page.locator("#plan-customer-class option").allInnerTexts();
note(`   customer class offers: ${classOptions.join(" · ")}`);
await page.selectOption("#plan-customer-class", { index: 1 }).catch(() => {});
await continueOn();

// ── STEP 2 · Services + the surcharge ──────────────────────────────────────
note("\n2 · Services (PRB-16 / PRB-24) — eleven services and a PERCENTAGE");
await page.locator("#plan-service-electric").waitFor({ timeout: 30000 }).catch(() => {});
const ELEVEN = ["electric","water","gas","sewer","trash","storm_water","solar","broadband","thermal_heat","battery","fire"];
let drawn = 0; const missing = [];
for (const code of ELEVEN) {
  if (await page.locator(`#plan-service-${code}`).count()) drawn += 1; else missing.push(code);
}
drawn === 11 ? ok(`all ELEVEN services are on the screen`) : fail(`only ${drawn}/11 drawn; missing ${missing.join(", ")}`);
const offCodes = [];
for (const code of ELEVEN) {
  const el = page.locator(`#plan-service-${code}`);
  if (await el.count() && await el.isDisabled().catch(() => false)) offCodes.push(code);
}
note(`   switched OFF on this tenant (drawn, greyed, unselectable): ${offCodes.join(", ") || "none"}`);
const step2 = await page.locator("body").innerText();
step2.includes("Not switched on") ? ok('the greyed rows carry the words "Not switched on"')
  : fail("a switched-off service carries no word, only a colour");
/Settings/.test(step2) ? ok("and where to switch one on is said in the list")
  : fail("nothing on screen says where a service is switched on");

// tick a service the utility HAS switched on
for (const code of ELEVEN) {
  const el = page.locator(`#plan-service-${code}`);
  if (await el.count() && !(await el.isDisabled().catch(() => true))) {
    await el.check({ force: true }).catch(() => {});
    note(`   ticked: ${code}`);
    break;
  }
}
await page.waitForTimeout(500);

// THE SURCHARGE — the whole point of D1
note("\n   the outside-city surcharge");
const question = page.locator("#plan-outside-city-charges-more");
(await question.count()) ? ok("it asks a plain question first") : fail("the two-answer question is not drawn");
if (await page.locator("#plan-outside-city-factor").count()) {
  fail("the OLD multiplier box (type 1.15) is still on screen");
} else {
  ok("the old multiplier box is gone");
}
if (await page.locator("#plan-outside-city-percent").count()) {
  fail("the percentage box is drawn before anyone answered yes");
} else {
  ok("the percentage box is collapsed until the answer is yes");
}
await question.selectOption("yes").catch(() => {});
await page.waitForTimeout(600);
const pct = page.locator("#plan-outside-city-percent");
(await pct.count()) ? ok("answering yes reveals the percentage box") : fail("answering yes revealed nothing");
await pct.fill("15").catch(() => {});
await page.waitForTimeout(700);
const readback = await page.locator("body").innerText();
const line = readback.split("\n").find((l) => l.includes("outside the city becomes")) ?? "";
note(`   READ-BACK ON SCREEN: "${line.trim()}"`);
line.includes("$100.00") && line.includes("$115.00")
  ? ok("a $100.00 bill outside the city becomes $115.00 — the CR's own figure")
  : fail(`the read-back does not show $100.00 → $115.00 (saw: "${line.trim()}")`);
await continueOn();

// ── STEP 3 · Rate schedules ────────────────────────────────────────────────
note("\n3 · Rate schedules (PRB-18) — no base column, and refused HERE");
await page.waitForTimeout(900);
const step3 = await page.locator("body").innerText();
// ⚠ **THIS SCANS THE WHOLE STEP, NOT THE TABLE HEADER — AND THAT IS THE POINT.**
// The vitest case asserts the column HEADER's key is absent and passed
// truthfully while two sentences went on promising a base charge in different
// words (`DEF-RAT-4675`). Prose has no id, so the only check that can see it is
// one that reads the rendered step and looks for the WORDS.
if (/base charge/i.test(step3)) {
  const where = step3.split("\n").filter((l) => /base charge/i.test(l)).join(" | ");
  fail(`step 3 still mentions a base charge: "${where}"`);
} else {
  ok("nothing on step 3 mentions a base charge — column and copy both gone");
}
if (/Every service needs a rate schedule/i.test(step3)) {
  ok("an unpriced service is refused on THIS step, named");
} else {
  note("   (no refusal shown — the service picked already has a schedule)");
}
const before3 = page.url();
await continueOn();
await page.waitForTimeout(600);
const sched = page.locator('select[id^="schedule-"]').first();
if (await sched.count()) {
  const opts = await sched.locator("option").allInnerTexts();
  note(`   schedule picker offers: ${opts.slice(0, 3).join(" | ")}${opts.length > 3 ? " …" : ""}`);
  await sched.selectOption({ index: 1 }).catch(() => {});
  await page.waitForTimeout(500);
}
await continueOn();

// ── STEP 4 · Charges — THE ADD BUTTON ──────────────────────────────────────
note("\n4 · Charges (PRB-17) — the Add button, fed by a NARROWED catalogue");
await page.waitForTimeout(900);
const step4 = await page.locator("body").innerText();
const narrowed = step4.split("\n").find((l) => /charge codes this plan can carry/i.test(l)) ?? "";
narrowed ? ok(`the count states its denominator: "${narrowed.trim()}"`)
  : fail("the catalogue count has no denominator on screen");
const addButtons = page.getByRole("button", { name: /^\+ Add$/ });
const addCount = await addButtons.count();
note(`   "+ Add" buttons on the catalogue: ${addCount}`);
if (addCount > 0) {
  const beforeAdd = await page.locator("body").innerText();
  // ⚠ **CASE-INSENSITIVE, AND THE FIRST DRAFT WAS NOT.** `Kicker` carries
  // `uppercase`, and Playwright's `innerText` returns text AS RENDERED — so
  // `/On this plan/` matched nothing, both captures came back `undefined`, and
  // `Number(undefined) > Number(undefined)` is false. The check reported *"the
  // Add button is not wired"* over a button that adds correctly. That is law 7's
  // *looking at the wrong thing*, in the walkthrough written to avoid it, and it
  // failed SAFE only by luck: the same bug with the comparison the other way
  // round would have reported success.
  const onPlanBefore = (beforeAdd.match(/On this plan · (\d+)/i) ?? [])[1];
  await addButtons.first().click().catch(() => {});
  await page.waitForTimeout(800);
  const afterAdd = await page.locator("body").innerText();
  const onPlanAfter = (afterAdd.match(/On this plan · (\d+)/i) ?? [])[1];
  note(`   pressed + Add — "On this plan" went ${onPlanBefore} → ${onPlanAfter}`);
  Number(onPlanAfter) > Number(onPlanBefore)
    ? ok("the Add button actually adds — it is wired, not drawn")
    : fail("pressing + Add changed nothing on screen (built is not wired)");
} else {
  fail("no + Add button on the charges catalogue");
}
await continueOn();

// ── STEP 5 · Taxes ─────────────────────────────────────────────────────────
note("\n5 · Taxes — the authority Add control");
await page.waitForTimeout(900);
const step5 = await page.locator("body").innerText();
/Add|attach/i.test(step5) ? ok("step 5 offers an add/attach control") : fail("step 5 offers no way to add");
await continueOn();

// ── STEP 6 · Discounts & billing ───────────────────────────────────────────
note("\n6 · Discounts & billing (PRB-26) — the late fee and the deposits are GONE");
await page.waitForTimeout(900);
const step6 = await page.locator("body").innerText();
for (const [id, what] of [
  ["#penalty-late-min", "minimum late fee"],
  ["#penalty-late-pct", "late fee percentage"],
  ["#penalty-grace-days", "grace days"],
  ["#penalty-grace-mode", "grace basis"],
  ["#plan-late-fee-charge", "late fee charge-code picker"],
]) {
  (await page.locator(id).count()) ? fail(`the ${what} control is still on step 6`) : ok(`no ${what} control`);
}
(await page.locator('[id^="plan-deposit-"]').count())
  ? fail("a deposit box is still on step 6")
  : ok("no deposit boxes");
/Late fees and deposits are charge codes/i.test(step6)
  ? ok("and the absence is EXPLAINED in one sentence")
  : fail("the two blocks vanished with no sentence saying where they went");
await continueOn();

// ── STEP 7 · Eligibility ───────────────────────────────────────────────────
note("\n7 · Eligibility (PRB-25) — the heading agrees with the fact");
await page.waitForTimeout(900);
const step7 = await page.locator("body").innerText();
/Who this plan is meant for/i.test(step7) ? ok("the heading says who the plan is MEANT FOR")
  : fail("the heading still reads as a permission");
/Nothing here refuses anybody/i.test(step7) ? ok("and one note says nothing here refuses anybody")
  : fail("the refusal fact is not stated");
/When it runs/i.test(step7) ? ok("the dates have their own block — dates are not eligibility")
  : fail("the dates are still buried in the eligibility block");
const thirdTime = (step7.match(/record an intention/gi) ?? []).length;
thirdTime === 0 ? ok("the third statement of the same fact is gone")
  : fail(`the same fact is still stated ${thirdTime} extra time(s)`);
(await page.locator("#plan-effective-from").count()) ? ok("Effective from is on this step")
  : fail("no effective-from date on step 7");

await page.screenshot({ path: "/tmp/cr087-step7.png", fullPage: true }).catch(() => {});
note("\n" + (problems.length === 0
  ? "WALKTHROUGH CLEAN — steps 1 to 7 behave as ruled."
  : `WALKTHROUGH FOUND ${problems.length} PROBLEM(S):\n  - ${problems.join("\n  - ")}`));
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
