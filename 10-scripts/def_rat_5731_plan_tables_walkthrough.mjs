// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-RAT-5731 — steps 4, 5 and 6 of the plan wizard stated one
//           collection TWICE (a catalogue pane beside an "On this plan" pane)
//           and offered the BASE code for adding.
//           DEF-RAT-5724 — a GL account had no readable form on those screens.
//           DEF-RAT-5739 — the wizard's copy against B14 rule 33's caps.
// Rules:    B14 rule 31 (no database id is ever the visible value of a field) ·
//           rule 33 (text capped by what it is for) · BR-SHL-033 · BR-RAT-088
//           (the charge code owns the amount) · BR-RAT-113 (a carried tax is
//           add-only) · OQ-322 (CLOSED 2026-10-03: an unbind now ends the
//           enrolments the day before, so no × is refused any more)
//           · CLAUDE.md hard-won law 6 — NO GATE IN THIS REPO READS RENDERED
//           OUTPUT, so this is the only instrument that can see any of it.
// ───────────────────────────────────────────────────────
/**
 * Walk the three rebuilt steps in a real browser and read what is DRAWN.
 *
 *     BASE=http://127.0.0.1:8123 node 10-scripts/def_rat_5731_plan_tables_walkthrough.mjs
 *
 * ⚠ **29 vitest cases and a clean `tsc` pass on this change already.** Not one
 * of them can see a locale key that renders blank, a column that lays out as a
 * sliver, a picker whose options never arrive from the server, or a control
 * that is present and dead — which is hard-won law 2, the defect class this
 * repo keeps paying for.
 *
 * ⚠⚠ **THIS SCRIPT HAS NOT BEEN RUN PAST SIGN-IN, AND SAYING SO IS THE POINT
 * (hard-won law 1 — a script claiming a guarantee it has not given is a
 * comment, not a proof).** On 2026-09-18 the environment was: SPA served by
 * vite on `:8123`, Django on `:8600`, Chromium at
 * `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`. The app boots, the
 * wizard route mounts, `POST /auth/session` answers with the correct refusal
 * envelope — and **no working credential exists.**
 *
 * ⚠ **THAT WAS TRUE WHEN WRITTEN AND IS FALSE NOW — AMENDED 2026-09-19.**
 * `dana@brazosbendutilities.com` / `S3cure!passw0rd` on tenant `brazosbend`
 * WORKS. The coordinating session reseeded the hash and the membership on
 * 2026-09-19 and signed in with it, and two walks have since run green on it.
 *
 * The paragraph this replaces was accurate: the database was rebuilt on
 * 2026-09-17, the hash stopped matching, and the lane that found it verified
 * with `check_password` against the stored `password_hash` rather than
 * inferring from a failed login — which is the right discipline and is why the
 * finding was trustworthy. It then said, correctly at the time, **"this blocks
 * EVERY lane's law-6 walk, not one lane's"**.
 *
 * ⚠ **AND THAT SENTENCE IS EXACTLY WHY THIS AMENDMENT MATTERS MORE THAN THE
 * CREDENTIAL.** A note saying *no walk is possible* discourages the one check
 * that finds what no test can — and it outlived the condition by two days,
 * during which lanes read it and did not look. A stale blocker is worse than a
 * stale fact: a wrong fact misleads a reader, a wrong blocker stops them being
 * one. **If the database is rebuilt again this note goes stale the same way, so
 * CHECK THE CREDENTIAL RATHER THAN THIS PARAGRAPH** — `check_password` against
 * `password_hash` takes one command and settles it.
 *
 * To restore it after a rebuild: set `password_hash` with `make_password`,
 * clear `must_change_password`, and give the user an ACTIVE `TenantMembership`
 * carrying the `system_admin` role — the membership is the half that is easy to
 * forget, and without it sign-in succeeds and every screen is empty.
 *
 * **To run it, supply a working credential and nothing else changes:**
 *
 *     PASSWORD='…' CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/def_rat_5731_plan_tables_walkthrough.mjs
 *
 * ⚠ **AND `PLAYWRIGHT_BROWSERS_PATH` IS NOT ENOUGH ON THIS MACHINE** — the
 * bundled playwright wants `chromium_headless_shell-1234` and what is installed
 * is `chromium-1194`, so the launch fails with *"Executable doesn't exist"* and
 * an invitation to run `npx playwright install`, which fails through the proxy.
 * `CHROME_PATH` is the way past it and every script here already supports it.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8123";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/-home-user-SMARTBillHub/da7d6dea-a84b-56ee-b035-57684ffe93fb/scratchpad/shots";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail(`PAGE ERROR: ${e.message}`));

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

// ── Reach step 4 through the front door, the way a clerk does ──────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "domcontentloaded" });
await page.locator("#plan-name").waitFor({ timeout: 30000 });
await page.fill("#plan-name", "DEF-RAT-5731 walkthrough");
await page.fill("#plan-code", `D5731-${Date.now().toString().slice(-6)}`);
await page.selectOption("#plan-customer-class", { index: 1 }).catch(() => {});
await continueOn();

// step 2 — tick the first service the utility has switched ON
const ELEVEN = ["electric","water","gas","sewer","trash","storm_water","solar","broadband","thermal_heat","battery","fire"];
for (const code of ELEVEN) {
  const el = page.locator(`#plan-service-${code}`);
  if (await el.count() && !(await el.isDisabled().catch(() => true))) {
    await el.check({ force: true }).catch(() => {});
    note(`   ticked service: ${code}`);
    break;
  }
}
await page.waitForTimeout(400);
await continueOn();          // → step 3 schedules
await continueOn();          // → step 4 charges
await page.waitForTimeout(800);

// ══════════════════════════════════════════════════════════════════════════
note("\n4 · Charges — ONE table, the picker in its add row");
await page.screenshot({ path: `${SHOTS}/step4-charges.png`, fullPage: true });

const hasTable = await page.locator('[data-editable-table="plan-charges"]').count();
hasTable ? ok("the EditableTable is mounted") : fail("no plan-charges table on screen");

const panels = await page.locator("[data-panel]").count();
note(`   panels drawn: ${panels}  (was 3 — base + catalogue + "On this plan")`);
panels <= 1 ? ok("the side panel is GONE") : fail(`${panels} panels — a pane survived`);

for (const dead of ["#plan-charge-search", "#plan-tax-search", "#plan-discount-search"]) {
  (await page.locator(dead).count()) === 0 ? ok(`${dead} is gone`) : fail(`${dead} still drawn`);
}

const picker = page.locator("#plan-charge-pick");
(await picker.count()) ? ok("the picker is drawn") : fail("no charge picker");

// THE OPTIONS COME FROM THE SERVER — a picker with none is law 2's dead control.
const opts = await page.locator("#plan-charge-pick option").allInnerTexts().catch(() => []);
const real = opts.filter((o) => o.trim() && !/^choose/i.test(o.trim()));
note(`   picker offers ${real.length} code(s): ${real.slice(0, 6).join(" | ")}${real.length > 6 ? " …" : ""}`);
real.length ? ok("the picker is fed by the server") : fail("the picker offers NOTHING — dead control");
real.some((o) => /^BASE-/i.test(o.trim())) ? fail("a BASE code is offered") : ok("no BASE-* code is offered");

// ADD one, and read the row that appears.
if (real.length) {
  await page.selectOption("#plan-charge-pick", { index: 1 });
  await page.getByRole("button", { name: "+ Add" }).first().click();
  await page.waitForTimeout(600);
  const rows = await page.locator('[data-editable-table="plan-charges"] tbody tr').count();
  rows === 1 ? ok("pressing Add appended exactly one row") : fail(`Add produced ${rows} rows`);
  await page.screenshot({ path: `${SHOTS}/step4-row-added.png`, fullPage: true });

  const cells = await page.locator('[data-editable-table="plan-charges"] tbody tr td').allInnerTexts();
  note(`   row cells: ${cells.map((c) => JSON.stringify(c.trim())).join(" · ")}`);

  const headers = await page.locator('[data-editable-table="plan-charges"] thead th').allInnerTexts();
  note(`   columns: ${headers.map((h) => h.trim()).filter(Boolean).join(" | ")}`);

  // the recurrence dropdown is ON THE ROW
  const sel = await page.locator('[data-editable-table="plan-charges"] tbody tr select').count();
  sel === 1 ? ok("one-time v recurring is a dropdown ON the row") : fail(`${sel} row selects`);
  if (sel) {
    const choices = await page.locator('[data-editable-table="plan-charges"] tbody tr select option').allInnerTexts();
    note(`   it offers: ${choices.map((c) => c.trim()).join(" · ")}`);
  }

  // B14 rule 31 — no uuid anywhere a person can read it
  const visible = await page.locator("body").innerText();
  const uuid = visible.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
  uuid ? fail(`a uuid is VISIBLE on step 4: ${uuid[0]}`) : ok("no uuid is visible (B14 rule 31)");

  // and the × removes it
  await page.locator('[data-remove-row="1"]').first().click();
  await page.waitForTimeout(500);
  const after = await page.locator('[data-editable-table="plan-charges"] tbody tr').count();
  after === 0 ? ok("the × removed the row") : fail(`× left ${after} row(s)`);
  // put it back so later steps have something to carry
  await page.selectOption("#plan-charge-pick", { index: 1 });
  await page.getByRole("button", { name: "+ Add" }).first().click();
  await page.waitForTimeout(400);
}

// ══════════════════════════════════════════════════════════════════════════
await continueOn();
await page.waitForTimeout(800);
note("\n5 · Taxes — the same shape");
await page.screenshot({ path: `${SHOTS}/step5-taxes.png`, fullPage: true });
(await page.locator('[data-editable-table="plan-taxes"]').count())
  ? ok("the taxes table is mounted") : fail("no plan-taxes table");
const taxOpts = await page.locator("#plan-tax-pick option").allInnerTexts().catch(() => []);
const taxReal = taxOpts.filter((o) => o.trim() && !/^choose/i.test(o.trim()));
note(`   picker offers ${taxReal.length}: ${taxReal.slice(0, 6).join(" | ")}`);
if (taxReal.length === 0) {
  note("   ⚠ this tenant has no tax authorities — DEF-444, a provisioning gap, not this screen");
} else {
  await page.selectOption("#plan-tax-pick", { index: 1 });
  await page.getByRole("button", { name: "+ Add" }).first().click();
  await page.waitForTimeout(600);
  const headers = await page.locator('[data-editable-table="plan-taxes"] thead th').allInnerTexts();
  note(`   columns: ${headers.map((h) => h.trim()).filter(Boolean).join(" | ")}`);
  const cells = await page.locator('[data-editable-table="plan-taxes"] tbody tr td').allInnerTexts();
  note(`   rows: ${cells.map((c) => JSON.stringify(c.trim())).join(" · ")}`);
  const blocked = await page.locator("[data-remove-blocked]").count();
  note(`   rows whose × is refused (BR-RAT-113 carried taxes): ${blocked}`);
  await page.screenshot({ path: `${SHOTS}/step5-bound.png`, fullPage: true });
}

// ══════════════════════════════════════════════════════════════════════════
await continueOn();
await page.waitForTimeout(800);
note("\n6 · Discounts — the same shape");
await page.screenshot({ path: `${SHOTS}/step6-discounts.png`, fullPage: true });
(await page.locator('[data-editable-table="plan-discounts"]').count())
  ? ok("the discounts table is mounted") : fail("no plan-discounts table");
const disOpts = await page.locator("#plan-discount-pick option").allInnerTexts().catch(() => []);
const disReal = disOpts.filter((o) => o.trim() && !/^choose/i.test(o.trim()));
note(`   picker offers ${disReal.length}: ${disReal.slice(0, 6).join(" | ")}`);
if (disReal.length) {
  await page.selectOption("#plan-discount-pick", { index: 1 });
  await page.getByRole("button", { name: "+ Add" }).first().click();
  await page.waitForTimeout(600);
  const headers = await page.locator('[data-editable-table="plan-discounts"] thead th').allInnerTexts();
  note(`   columns: ${headers.map((h) => h.trim()).filter(Boolean).join(" | ")}`);
  const cells = await page.locator('[data-editable-table="plan-discounts"] tbody tr td').allInnerTexts();
  note(`   row: ${cells.map((c) => JSON.stringify(c.trim())).join(" · ")}`);
  const dates = await page.locator('[data-editable-table="plan-discounts"] tbody tr input[type="date"]').count();
  dates === 2 ? ok("both availability dates are real date pickers") : fail(`${dates} date inputs, expected 2`);
  const blocked = await page.locator("[data-remove-blocked]").count();
  note(`   rows whose × is refused (OQ-322 CLOSED 2026-10-03 — expect 0): ${blocked}`);
  await page.screenshot({ path: `${SHOTS}/step6-bound.png`, fullPage: true });
}

// ── Billing terms still on this step ───────────────────────────────────────
(await page.locator("#plan-budget-billing").count()) ? ok("budget billing is still here")
  : fail("budget billing vanished");
(await page.locator("#plan-minimum-bill").count()) ? ok("minimum bill is still here")
  : fail("minimum bill vanished");

note("\n────────────────────────────────────────────");
if (problems.length === 0) {
  note("NO PROBLEMS FOUND in the three rebuilt steps.");
} else {
  note(`${problems.length} PROBLEM(S):`);
  for (const p of problems) note("  · " + p);
}
note(`screenshots in ${SHOTS}`);
await browser.close();
process.exit(problems.length ? 1 : 0);
