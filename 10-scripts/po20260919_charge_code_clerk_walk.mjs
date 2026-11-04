// ── THE PO's CHARGE-CODE WALK, 2026-09-19 ─────────────────────────────────
// PO, verbatim: *"Also run end to end walk for CHrge codes - wehave so many
// charge codes - hence your walk will be multiple walks - all rules are set
// for charge codes - based on services, based on customer class - if charge
// code value are changed are they passing details to plans"*, and *"walk
// ahould check plasna dn rates work end to end - clark dont have any
// frictions to perform his job, overall user experience is good"*.
//
// WHAT IT FOUND, filed 2026-09-19 — it reported 9 pass / 8 fail:
//   DEF-RAT-5819  the review step reads back the STORED price, not the typed one
//   DEF-RAT-5820  a penalty + auto-apply code saves with no warning; R4 refuses it
//   DEF-RAT-5821  customer class is on no list column and on no Applicability tab
//   DEF-RAT-5822  a plan's class chip renders a raw UUID, and the narrowing stops
//   DEF-RAT-5824  the charge edit asks no change-or-correction and shows no date
//   DEF-RAT-4650  (already open) the PLANS CARRYING IT tile against its own table
// Two more came out of the same walk and were not assertable from a browser:
//   DEF-RAT-5823  rating/0039 restored account_type ids that resolve to nothing
//   DEF-RAT-5825  Refundable's help points at the plan deposits block, deleted
//                 by PO ruling 2026-09-08
//
// ⚠ **EXTENDED 2026-09-19 BY THE LANE THAT FIXED FIVE OF THEM** — 5819, 5820,
// 5821, 5824 and 5825. What moved, and one of them is a correction rather than
// an addition:
//   · scenario 2b is NEW — the detail sub-line's `version in force` claim.
//   · scenario 4 gains 5825, read out of the collapsed disclosure it hides in.
//   · scenario 5 is REWRITTEN to ask whether the contradiction can be AUTHORED
//     rather than whether a warning string is in the DOM, and it now covers the
//     route in that no tick can close: ticked lawfully on `recurring`, then the
//     type changed. It clicks with `force` on purpose — see the case.
//   · ⚠ **scenario 6's first case ASSERTED THE WRONG REMEDY AND IS CORRECTED.**
//     It demanded the rate schedule's `Fix an error` question of a screen whose
//     defect is that it is NOT VERSIONED; passing it would have meant inventing
//     versioning to satisfy a test. `OQ-RAT-12408` is where versioning goes.
// What is deliberately UNCHANGED: 5822's and 4650's cases, which belong to
// other lanes and are expected to stay red here.
//
// ⚠ **IT DOES NOT PRICE A BILL, AND THAT IS THE PO's OWN NARROWING.** An
// earlier plan for this walk ended every scenario at a priced bill; the PO
// struck that row — *"this is not required"*. So this asks what a CLERK can
// see and do, and every assertion is about a screen.
//
// ⚠ **IT REFUSES A STALE BUILD.** Copied from
// `plan_wizard_seven_walkthrough.mjs`, which was written after a walk against
// a `dist/` 26 hours old reported three landed fixes as ABSENT. Nothing in
// the page says how old it is and `tsc`, the suites and every gate are green
// either way, because none of them look at `dist/`.
//
// ⚠ **THE SELECTORS ARE NOT THE PLANS TABLE's.** A charge-code row opens
// through `a[data-inlinelink]`; the PLANS table opens through
// `button.rating-link`. The charge picker on plan step 4 is a combobox
// (`#plan-charge-pick`) whose candidates are `#plan-charge-pick-listbox li`,
// and the customer-class picker on charge step 2 only keeps its list open
// once you type into it. Each of those cost a run to find.
//
// ⚠ **IT SEEDS TWO PROBE CODES AND PURGES THEM.** On the seeded
// `brazosbend`, EVERY non-base charge code is service-NULL and class-NULL, so
// neither narrowing rule can exclude a single row — the rules cannot be
// walked at all without a code that they can remove. Both probes are
// `one_time` with `auto_apply = false`, so `rides_a_periodic_bill` is false
// for each and neither can reach a bill or raise a refusal.
//
//   CHG_WALK_BASE     default http://127.0.0.1:8712
//   CHG_WALK_TENANT   default brazosbend
//   CHG_WALK_EMAIL    default dana@brazosbendutilities.com
//   CHG_WALK_PASSWORD default S3cure!passw0rd
//   CHG_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser here, so the path is passed explicitly — never run
//      `playwright install` in this container.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.CHG_WALK_BASE || "http://127.0.0.1:8712";
const T = process.env.CHG_WALK_TENANT || "brazosbend";
const EMAIL = process.env.CHG_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.CHG_WALK_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CHG_WALK_CHROME
  || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync("07-frontend/dist/index.html").mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
    `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
    `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}

// ⚠ **EVERY LINE IS PRINTED AS IT IS DECIDED, NOT ONLY AT THE END.** This
// walk used to collect `R` and print it after scenario 8, so ONE bad selector
// anywhere threw and took every earlier result with it — which is what
// happened on the first run after the fixes: scenarios 1 to 4 had all been
// decided and none of them was ever seen. A walk whose output survives only
// the happy path is a walk you cannot debug.
const R = [];
const say = (line) => { R.push(line); console.log(line); };
// ⚠ **THE DETAIL IS THE FAILURE'S EXPLANATION, SO IT IS PRINTED ONLY ON A
// FAILURE.** Printed on both, scenario 1 read `PASS · the list has a CUSTOMER
// CLASS column · it does not` — a line that says the opposite of its own
// verdict. CLAUDE.md law 7, habit 3: *a check's output must distinguish pass
// from fail to a READER*, not merely to an exit code. A measurement worth
// having on a PASS goes through `note` and says so.
const ok = (n, c, d = "") => { say(`${c ? "PASS" : "FAIL"} · ${n}${c || !d ? "" : " · " + d}`); };
const note = (n) => say(`NOTE · ${n}`);

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage();
const body = async () => (await p.evaluate(() => document.body.innerText)).split("System Admin")[1] ?? "";
const cont = async () => {
  await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
  await p.waitForTimeout(1600);
};

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// ── 1 · THE LIST · can a clerk SEE either narrowing rule? ──────────────────
await p.goto(`${BASE}/${T}/plans-rates/charge-codes`, { waitUntil: "networkidle" });
await p.waitForTimeout(2200);
const headers = await p.evaluate(() =>
  [...document.querySelectorAll("table thead th")].map((e) => e.textContent.trim().toUpperCase()));
ok("1 · the list has a SERVICE column", headers.includes("SERVICE"), headers.join("/"));
note(`1 · the columns a clerk actually sees: ${headers.join(" · ")}`);
ok("1 · the list has a CUSTOMER CLASS column",
  headers.some((h) => h.includes("CLASS")),
  "DEF-RAT-5821 — it does not, so class scoping is invisible on the list");

// ── 2 · THE DETAIL · the Applicability tab, on a class-scoped code ─────────
await p.locator("table tbody tr a[data-inlinelink]").filter({ hasText: /^BASE-E$/ }).first().click();
await p.waitForTimeout(2400);
const codeUrl = p.url();
await p.locator("button,a").filter({ hasText: /^Applicability$/ }).first().click();
await p.waitForTimeout(1600);
const applic = await body();
ok("2 · Applicability names the SERVICE", /APPLIES TO[\s\S]{0,40}Electric/i.test(applic));
ok("2 · Applicability names the CUSTOMER CLASS",
  /residential/i.test(applic.slice(applic.indexOf("APPLICABILITY"))),
  "DEF-RAT-5821 — BASE-E is residential-only and the tab never says so");

// ── 2b · THE SUB-LINE THAT CLAIMED A VERSION THE OBJECT HAS NOT ──────────
// `charges` has no `effective_from`, no `effective_to` and no version table —
// the Audit tab says so in its own words — and the header sub-line read *"…
// references the version in force, so an issued bill never changes."* This is
// `DEF-RAT-5711`'s mirror: that row corrected the identical false promise on
// the rate-schedule review two days earlier and never reached this object.
//
// ⚠ TWO HALVES, AND THE SECOND IS WHAT STOPS THIS PASSING WRONGLY. `not
// .toContain` alone is green on a page that failed to load, on a tab that
// rendered nothing, and on a sub-line somebody simply deleted. So it asserts
// the OLD claim is gone AND the honest sentence is in its place.
const headText = await body();
ok("2b · the charge-code header claims no version it does not have",
  !/version in force/i.test(headText) && /holds one price/i.test(headText),
  "DEF-RAT-5824 — a charge code holds ONE price and is never versioned");

// ── 3 · THE TWO ROUTES · the tile against the table beneath it ────────────
await p.locator("button,a").filter({ hasText: /^Plans$/ }).first().click();
await p.waitForTimeout(1800);
const plansTab = await body();
const tile = plansTab.match(/PLANS CARRYING IT\s*\n\s*(\d+|—)/)?.[1] ?? "?";
const listed = (plansTab.match(/the plan does not name it/g) || []).length;
ok("3 · the PLANS CARRYING IT tile agrees with the table under it",
  !(tile === "0" && listed > 0),
  `DEF-RAT-4650 (open) — tile reads ${tile} while the table lists ${listed} plans`);

// ── 4 · THE FIVE TYPES · what does step 2 ask for each? ───────────────────
const asked = {};
for (const type of ["recurring", "one_time", "refundable", "penalty", "adjustment"]) {
  await p.goto(`${BASE}/${T}/plans-rates/charge-codes/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1300);
  await p.fill("#charge-code", "WALKPROBE");
  await p.fill("#charge-name", "probe");
  await p.selectOption("#charge-type", type);
  await cont();
  const more = p.locator("button,summary").filter({ hasText: /More about this step/ });
  for (let i = 0, n = await more.count(); i < n; i++) {
    try { await more.nth(i).click(); await p.waitForTimeout(200); } catch { /* collapsed */ }
  }
  await p.waitForTimeout(500);
  const txt = await body();
  asked[type] = {
    raw: txt,
    autoApply: /Apply automatically/.test(txt),
    extra: (txt.match(/How often it is charged|Part-period charging|What raises it|Deposit terms/g) || []),
  };
}
ok("4 · all five types still OFFER apply automatically",
  Object.values(asked).every((a) => a.autoApply),
  "BR-SHL-025 — a control that may not be used is present and disabled, never removed");
ok("4 · REFUNDABLE no longer sends the clerk to the plan for deposit terms",
  !/Deposit rules live on the plan/i.test(asked.refundable.raw),
  "DEF-RAT-5825 — the PO deleted the plan wizard's deposits block on 2026-09-08");
note(`4 · what each type adds, behind the collapsed disclosure: ${
  Object.entries(asked).map(([k, v]) => `${k}=[${v.extra.join(",") || "nothing"}]`).join(" ")}`);

// ── 5 · THE CONTRADICTION A CLERK COULD SAVE ─────────────────────────────
// `resolution.rides_a_periodic_bill` RAISES `ChargeCodeRecurrenceConflict`
// for `auto_apply && charge_type !== "recurring"` — so a Penalty code with
// the flag on REFUSES the bill of every account its customer class reaches.
//
// ⚠ **THE ASSERTIONS ASK WHETHER THE STATE CAN BE AUTHORED, NOT WHETHER A
// WARNING STRING IS SOMEWHERE IN THE DOM.** A sentence a clerk can click past
// is the state this defect was already in: the ENGINE's refusal existed the
// whole time and simply arrived weeks later, at a bill run. So scenario 5a
// clicks the tick and asserts it did NOT go on, and 5c reaches step 3 and
// asserts it is still step 2.
await p.goto(`${BASE}/${T}/plans-rates/charge-codes/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(1300);
await p.fill("#charge-code", "WALKPROBE");
await p.fill("#charge-name", "probe");
await p.selectOption("#charge-type", "penalty");
await cont();
await p.locator("#charge-amount").fill("99.00");
const beforeTick = await body();
// ⚠ **THE LABEL, NOT THE INPUT.** `CheckboxField` renders the `<input>` as
// `peer sr-only` — visually hidden — and draws a `<span>` as the tick, so
// Playwright times out on the input with *"<html> intercepts pointer events"*
// and the case dies rather than deciding anything. The label is what a person
// clicks, and `htmlFor` is what carries the click to the box.
//
// `force`, because the point of the fix is that the box is DISABLED: an
// ordinary click would be refused by the driver and the case would pass for
// the wrong reason — the strongest false pass available here.
await p.locator('label[for="charge-auto-apply"]').click({ force: true }).catch(() => undefined);
await p.waitForTimeout(700);
ok("5a · APPLY AUTOMATICALLY cannot be ticked on a PENALTY",
  (await p.locator("#charge-auto-apply").isChecked()) === false
    && (await p.locator("#charge-auto-apply").isDisabled()),
  "DEF-RAT-5820 — R4 refuses this pair, so the screen must not let it be authored");
// ⚠ **THIS CASE WAS A BEFORE/AFTER COMPARISON AND IT COULD NOT FIRE.** Written
// against the OLD screen, where ticking the box was the event and nothing
// changed; on the fixed screen the reason is drawn the moment the step opens,
// because the type is already Penalty — so before and after are identical and
// the case failed over a screen that was doing the right thing. Caught by
// reading the line rather than the exit code. It asks the question that
// actually matters now: is the reason ON THE STEP, and is it absent where the
// tick is lawful — the second half being what stops a sentence printed on
// every type passing this.
const afterTick = await body();
void beforeTick;
ok("5b · and the screen SAYS why, where the tick is",
  /Only recurring codes apply automatically/i.test(afterTick),
  "DEF-RAT-5820 — a disabled control with no reason is BR-SHL-025 unmet");

// 5c · the one route INTO the contradiction: tick it on Recurring, then go
// back and change the type. The tick was lawful when it was made, so nothing
// could have stopped it there — this is also the shape of a row STORED before
// the fix, which is why Continue has to hold rather than the tick alone.
await p.goto(`${BASE}/${T}/plans-rates/charge-codes/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(1300);
await p.fill("#charge-code", "WALKPROBE");
await p.fill("#charge-name", "probe");
await p.selectOption("#charge-type", "recurring");
await cont();
await p.locator("#charge-amount").fill("99.00");
await p.locator('label[for="charge-auto-apply"]').click();
await p.waitForTimeout(500);
ok("5c · APPLY AUTOMATICALLY ticks freely on a RECURRING code",
  (await p.locator("#charge-auto-apply").isChecked())
    && !/Only recurring codes apply automatically/i.test(await body()),
  "the fix must not take the flag away from the one type that may carry it");
await p.locator('button[data-wizard-step="1"]').first().click();
await p.waitForTimeout(900);
await p.selectOption("#charge-type", "penalty");
await cont();                                       // back to step 2
await cont();                                       // and this one must NOT move
const held = await body();
ok("5d · Continue is REFUSED while the code contradicts itself",
  /STEP 2 OF 3/i.test(held) && !/STEP 3 OF 3/i.test(held),
  "DEF-RAT-5820 — POST /charges answered 201 on exactly this pair");

// 5e · and on a lawful code the review NAMES the flag, so it cannot be saved
// unseen. Step 3 listed ten facts and this was not one of them.
await p.goto(`${BASE}/${T}/plans-rates/charge-codes/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(1300);
await p.fill("#charge-code", "WALKPROBE");
await p.fill("#charge-name", "probe");
await p.selectOption("#charge-type", "recurring");
await cont();
await p.locator("#charge-amount").fill("99.00");
await p.locator('label[for="charge-auto-apply"]').click();
await p.waitForTimeout(500);
await cont();
const review = await body();
ok("5e · the review step says WHEN IT APPLIES",
  /WHEN IT APPLIES\s*\n\s*Every bill/i.test(review),
  "DEF-RAT-5820 — the flag that decides whether it rides every bill was absent from the review");

// ── 6 · A VALUE CHANGE · does the review show what the clerk just typed? ──
await p.goto(`${BASE}/${T}/plans-rates/charge-codes`, { waitUntil: "networkidle" });
await p.waitForTimeout(1800);
await p.locator("table tbody tr a[data-inlinelink]").filter({ hasText: /^PAPER$/ }).first().click();
await p.waitForTimeout(2200);
await p.locator("button,a").filter({ hasText: /^Edit$/ }).first().click();
await p.waitForTimeout(2400);
// ⚠ **THIS CASE ASSERTED THE WRONG REMEDY AND IS CORRECTED (2026-09-19).** It
// read `/Fix an error/i` — the rate schedule's `Change the rate / Fix an
// error` question — over `DEF-RAT-5824`, whose whole finding is that a charge
// code is NOT VERSIONED. Building that question here would have invented
// versioning to satisfy a test, which is `OQ-RAT-12408` and is the PO's to
// size. **The honest fix is to stop claiming otherwise**, so what the edit
// door owes a clerk is the FACT: this change is live on the next bill.
ok("6 · the charge-code edit says what saving does",
  /prices the next bill/i.test(await body()),
  "DEF-RAT-5824 — the edit asked nothing and the only sentence on the subject implied a version");
await cont();
const stored = await p.locator("#charge-amount").inputValue();
const typed = (Number(stored) + 1.25).toFixed(2);
await p.locator("#charge-amount").fill(typed);
await cont();
const rv = await body();
const shown = rv.match(/\nAMOUNT\n([\d.,]+)/)?.[1] ?? "?";
ok("6 · the review reads back the amount the clerk just typed",
  shown === typed,
  `DEF-RAT-5819 — typed ${typed}, review shows ${shown} (the STORED value)`);
// leave without saving
await p.locator("button,a").filter({ hasText: /^Cancel$/ }).first().click();
await p.waitForTimeout(1200);

// ── 7 · THE TWO NARROWING RULES, on the plan's charge picker ─────────────
// Needs the two probe codes; `seed_probes.py` makes and purges them.
for (const customerClass of ["", "Residential"]) {
  await p.goto(`${BASE}/${T}/plans-rates/plans/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2000);
  await p.fill("#plan-name", "Walk probe plan");
  await p.fill("#plan-code", "WALKPLAN");
  if (customerClass) {
    await p.locator("select").first().selectOption({ label: customerClass });
    await p.waitForTimeout(500);
  }
  await cont();                                       // 2 · services
  await p.locator("select").first().selectOption({ label: "Water" });
  await p.waitForTimeout(600);
  await cont();                                       // 3 · rate schedules
  await p.locator("select").first().selectOption({ index: 1 });
  await p.waitForTimeout(700);
  await cont();                                       // 4 · charges
  const offered = await p.evaluate(() =>
    [...document.querySelectorAll("#plan-charge-pick-listbox li")].map((e) => e.textContent.trim()));
  const has = (c) => offered.some((x) => x.startsWith(c));
  const who = customerClass || "no class";
  ok(`7 · [${who}] an ELECTRIC-scoped code is kept off a WATER-only plan`,
    !has("WALK-ELEC"), `it is offered; the service rule removed nothing`);
  note(`7 · [${who}] the picker offered ${offered.length} codes`);
  ok(`7 · [${who}] no is_base code is offered (BR-RAT-088)`, !has("BASE-"));
  if (customerClass === "") {
    ok("7 · [no class] a COMMERCIAL-only code IS offered when the plan names no class",
      has("WALK-COMM"), "empty plan class = no class narrowing");
  } else {
    ok(`7 · [${who}] a COMMERCIAL-only code is kept off a RESIDENTIAL plan`,
      !has("WALK-COMM"));
  }
  const baseLine = (await body()).match(/MONTHLY BASE[\s\S]{0,60}/)?.[0]?.replace(/\s+/g, " ");
  if (customerClass === "") note(`7 · the base reaches the plan by its own route: ${baseLine}`);
}

// ── 8 · THE STORED CLASS THAT RESOLVES TO NOTHING ────────────────────────
// `rating/0039` restored three plans' classes from `plan_versions.snapshot`,
// whose `account_type_id` values no longer exist in `account_types`.
await p.goto(`${BASE}/${T}/plans-rates/plans`, { waitUntil: "networkidle" });
await p.waitForTimeout(2000);
await p.locator("table tbody tr").filter({ hasText: "Sample — Residential" }).first()
  .locator("button.rating-link, a[data-inlinelink]").first().click();
await p.waitForTimeout(2200);
await p.goto(`${p.url()}/edit`, { waitUntil: "networkidle" });
await p.waitForTimeout(2800);
const rawUuid = await p.evaluate(() =>
  document.body.innerText.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)?.[0] ?? null);
ok("8 · no database id is the visible value of a field (B14 rule 31)",
  rawUuid === null,
  rawUuid ? `DEF-RAT-5822 — the customer-class chip renders ${rawUuid}` : "");

await b.close();
const failed = R.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${R.filter((r) => r.startsWith("PASS")).length} pass · ${failed} fail · ` +
  `${R.filter((r) => r.startsWith("NOTE")).length} notes`);
process.exit(failed > 0 ? 1 : 0);
