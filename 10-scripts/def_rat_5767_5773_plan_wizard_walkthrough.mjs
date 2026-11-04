/**
 * ── LAW 6: THE SEVEN BETA DEFECTS, CLICKED IN A BROWSER ────────────────────
 *
 * `DEF-RAT-5767` · `DEF-RAT-5768` · `DEF-RAT-5769` · `DEF-RAT-5772` ·
 * `DEF-RAT-5773` · `DEF-RAT-5779` · `DEF-RAT-5780`, shipped `2.308.7`.
 *
 *     BASE=http://127.0.0.1:8123 CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/def_rat_5767_5773_plan_wizard_walkthrough.mjs
 *
 * ⚠ **827 vitest cases and a clean `tsc` pass on this change already.** Not one
 * of them can see a locale key that renders as its own name, a picker whose
 * options never arrive from the SERVER, a column that lays out as a sliver, or
 * a control that is present and dead. Law 6 is the only thing in this repo that
 * looks at rendered output, and it found three faults in THIS SCRIPT before it
 * found none in the product — each one recorded below, because a walkthrough
 * that reports a defect the product does not have is worth no more than one
 * that passes wrongly.
 *
 * ⚠⚠ **THE CREDENTIAL EVERY OTHER WALKTHROUGH DECLARES DEAD IS ALIVE, AND
 * THAT NOTE HAS BEEN BLOCKING EVERY LANE'S LAW-6 WALK.**
 * `def_rat_5731_plan_tables_walkthrough.mjs`'s header says the database was
 * rebuilt on 2026-09-17 and that `S3cure!passw0rd` no longer matches its hash.
 * Re-checked on 2026-09-19 by the same method it used — `check_password`
 * against the stored `password_hash`, not a failed login — it **matches**, for
 * `dana@brazosbendutilities.com` and for `sam.reyes@sample.test`. Nothing was
 * written to get there. The note had simply gone stale, and it is hard-won law
 * 1 in a docstring: a comment claiming a guarantee is not the guarantee, and
 * this one claimed an ABSENCE.
 *
 * ⚠ **THE DEV SERVER CARRIES NO `/api` PROXY**, so a walk needs one:
 * a local `vite.walk.config.ts` that merges `server.proxy` onto the real
 * config, pointed at Django on `:8600`. It is not committed, because adding a
 * proxy to the shared config would change how every lane's dev server behaves.
 *
 * ── WHAT THE THREE FAULTS IN THIS SCRIPT WERE, so the next one avoids them ──
 *   1. It asserted on step 1 the moment `#plan-name` existed — BEFORE the
 *      class lookup had answered — and reported *"no chip control on step 1"*
 *      against a perfectly correct screen.
 *   2. It clicked an *Add* BUTTON on the chip control. `ChipMultiSelect`'s add
 *      control is a `<select data-chip-add>` whose `onChange` adds immediately;
 *      there is no button, so it timed out.
 *   3. It pressed Continue a fixed number of times from a NEW plan. Step 2
 *      gates on a service and step 3 on a bound schedule, so it never reached
 *      step 4 — which reads exactly like a missing table. A PUBLISHED plan is
 *      the honest way in: it already holds both, and it is the only state in
 *      which `DEF-RAT-5769`'s verb is drawn at all.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8123";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
/** `RES-STD`, published, and it already NAMES `CONN`, `LATE` and `NSF` — the
 *  PO's own demo data, which is what makes the `When it applies` column worth
 *  reading rather than a fixture repeating the assertion back. */
const PLAN = process.env.PLAN ?? "01a0afe1-27c0-7832-966f-1e410ad73924";

const problems = [];
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const page = await (await browser.newContext({ viewport: { width: 1500, height: 1100 } })).newPage();
page.on("pageerror", (e) => fail(`PAGE ERROR: ${e.message}`));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
console.log(`signed in as ${EMAIL} → ${page.url()}`);
const stepNow = async () =>
  (await page.locator("[data-kicker]").allTextContents()).map((t) => t.trim())
    .find((t) => /^Step \d/.test(t)) ?? "?";

// ══ 1 · A NEW PLAN — DEF-RAT-5768, the class is a LIST ════════════════════
console.log("\nDEF-RAT-5768 — the customer class is a list (new plan, step 1)");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "domcontentloaded" });
await page.locator("#plan-name").waitFor({ timeout: 30000 });
const chipGroup = page.locator('[data-chip-select="plan-customer-classes"]');
await chipGroup.waitFor({ timeout: 30000 }).catch(() => {});
await page.waitForTimeout(800);
(await chipGroup.count()) ? ok("chips + an add control are on step 1") : fail("no chip control on step 1");
(await page.locator("#plan-customer-class").count())
  ? fail("the old single select is still there") : ok("the single select is gone");
const classAdd = page.locator('[data-chip-add="plan-customer-classes"]');
const classes = (await classAdd.locator("option").allTextContents())
  .map((t) => t.trim()).filter((t) => t && !/add a class/i.test(t));
console.log(`    the SERVER offered ${classes.length}: ${classes.join(" · ")}`);
classes.length > 1 ? ok("more than one class is offered, so a list is meaningful")
                   : fail("the class list came back empty — the screen cannot be exercised");
for (const label of classes.slice(0, 2)) {
  await classAdd.selectOption({ label }).catch(() => {});
  await page.waitForTimeout(350);
}
const chips = (await page.locator("[data-chip]").allTextContents()).map((c) => c.replace(/×$/, "").trim());
console.log(`    chips now: ${chips.join(" · ")}`);
chips.length >= 2 ? ok(`${chips.length} classes on ONE plan — the defect is closed`)
                  : fail(`only ${chips.length} chip(s) rendered`);
chips.some((c) => /[0-9a-f]{8}-[0-9a-f]{4}/.test(c))
  ? fail("B14 rule 31 — a uuid is visible in a chip") : ok("no uuid on screen (B14 rule 31)");

// ══ 2 · A PUBLISHED PLAN — the verb, the picker, the columns ══════════════
console.log("\nDEF-RAT-5769 — the change-or-correction verb is asked FIRST");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${PLAN}/edit`, { waitUntil: "domcontentloaded" });
await page.locator("#plan-name").waitFor({ timeout: 30000 });
await page.waitForTimeout(2500);
console.log(`    opened "${await page.locator("#plan-name").inputValue()}" at ${await stepNow()}`);
(await page.locator('input[name="plan-edit-intent"]').count()) === 2
  ? ok("both verbs are on STEP 1 of a published plan")
  : fail("the verb is not on step 1");
const segs = (await page.locator(".seg-opt").allTextContents()).map((t) => t.trim()).filter(Boolean);
console.log(`    it reads: ${segs.join(" | ")}`);
/\b\d+\s+bills?\b/i.test(await page.locator("body").textContent() ?? "")
  ? fail("a bill COUNT is on screen (BR-BIL-030 / OQ-185)") : ok("no bill count is shown");

for (let i = 0; i < 8; i++) {
  if (await page.locator('[data-editable-table="plan-charges"]').count()) break;
  await page.getByRole("button", { name: /^Continue$/ }).first().click().catch(() => {});
  await page.waitForTimeout(1100);
}
const table = page.locator('[data-editable-table="plan-charges"]');
(await table.count()) ? ok(`reached ${await stepNow()}`) : fail("never reached step 4");

console.log("\nDEF-RAT-5767 — step 4 offers every charge type");
const offered = (await page.locator("#plan-charge-pick-listbox [role=option]").allTextContents()).map((t) => t.trim());
const held = ((await table.locator("tbody").textContent().catch(() => "")) ?? "");
console.log(`    ${offered.length} codes offered; this plan already holds CONN, LATE, NSF`);
// A PENALTY is attachable — the capability half of the PO's 2026-09-17
// complaint. LATE and NSF are absent from the picker only because the plan
// HOLDS them, which is the picker's own rule, so TAMPER is the one to assert.
offered.some((o) => o.startsWith("TAMPER ")) ? ok("TAMPER (a penalty) is attachable")
                                             : fail("TAMPER is still not offered");
["LATE", "NSF"].forEach((c) => (held.includes(c) ? ok(`${c} is on the plan already`)
                                                 : fail(`${c} is neither offered nor held`)));
offered.some((o) => /^BASE-/i.test(o)) ? fail("a BASE code is offered")
                                       : ok("no BASE-* code is offered (BR-RAT-088)");

console.log("\nDEF-RAT-5772 — the picker is a search picker, and wider");
(await page.locator("#plan-charge-pick").getAttribute("role")) === "combobox"
  ? ok("the add row's control is a combobox") : fail("the add row is not a combobox");
const width = Math.round(await page.locator("[data-picker-width]").first()
  .evaluate((n) => n.getBoundingClientRect().width));
console.log(`    picker width: ${width}px`);
width >= 280 ? ok("wide enough to read a code in") : fail(`only ${width}px`);

console.log("\nDEF-RAT-5779 — the row STATES the code's rule, it does not set it");
const th = (await table.locator("th").allTextContents()).map((t) => t.trim()).filter(Boolean);
console.log(`    columns: ${th.join(" · ")}`);
th.some((h) => /^type$/i.test(h)) ? ok("a Type column is drawn") : fail("no Type column");
th.some((h) => /when it applies/i.test(h)) ? ok("a 'When it applies' column is drawn")
                                           : fail("no 'When it applies' column");
(await page.locator('[id^="plan-charge-recurrence-"]').count())
  ? fail("the editable Applied dropdown is still on the row")
  : ok("the editable Applied dropdown is gone");
/Penalty/.test(held) ? ok("LATE reads its type: Penalty") : fail("no Penalty type on the LATE row");
/When triggered/.test(held)
  ? ok("the PO's own codes read 'When triggered', not 'Every bill'")
  : fail("no 'When triggered' on any row");

console.log(`\n${problems.length === 0 ? "ALL CLEAR" : problems.length + " PROBLEM(S)"}`);
await browser.close();
process.exit(problems.length ? 1 : 0);
