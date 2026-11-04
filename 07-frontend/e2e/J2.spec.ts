// ── Trace ──────────────────────────────────────────────
// Journey:  J2 — read-to-cash, the money journey
//           (08-qa/01-e2e/journeys/J2-read-to-cash.md, tier 1)
// Story:    US-MET-001/002 (premises + units, S14/S15) · US-AST-002 ·
//           US-MET-006 (asset assignment, S49/S53) · US-RAT-001..003 +
//           the unit plan assignment (S9 · S15) · US-CUS-003/004 (+US-CUS-006
//           snapshot, US-CUS-007 deposit — S18) · US-MET-010..013 (read
//           import, S28) · US-MET-011 (validation, S25/S29) · US-RAT-012/013
//           (rating 🔒) · US-BIL-005 (issue, S31) · US-PAY-001 · US-CUS-012
//           (record payment, S33/S22) · US-LED-001 (posting 🔒, S36)
//           Screens: S14 · S15 · S49 · S9 · S18 · S25 · S28 · S31 · S30 ·
//           S30 detail · S33 · S36
// Rules:    BR-MET-036 (occupancy is DERIVED, never typed) · BR-AST-028 /
//           BR-MET-006 (one asset per enabled service, UoM explicit) ·
//           BR-RAT-030 (only a PUBLISHED plan may be put on a unit) ·
//           BR-CUS-010/011 (the unit's current plan assignment) · BR-MET-040
//           (activation needs the unit to carry a plan) · BR-CUS-014 sc.1
//           (the account's plan-version snapshot) · BR-CUS-029
//           (account_plan_assignments) · BR-MET-059 / B2 r8 (one read row per
//           channel) · BR-MET-049 (the plan-required channel set) · B4.4 /
//           BR-RAT-003 (round per line, half-up, 2 dp, at finalization) ·
//           BR-BIL-058 (nothing issues without a recorded release) ·
//           BR-BIL-024 (the due date derives at issue) · BR-BIL-004 / hard
//           rule 4 (an issued bill is never restated) · BR-PAY-010 (the
//           allocation order) · BR-PAY-021 (posting date ≠ clearing date) ·
//           CLAUDE.md rule 5 (balanced pairs, posting service only) ·
//           BR-SHL-023 (ONE money formatting path — 2 dp at display, 4 on the
//           wire) · BR-SHL-025 (a control that cannot be honoured renders
//           disabled WITH its reason)
// Expected: `moneyTriple("tou", "first", "full")` — the A×D×E dataset row for
//           this journey's combination: the account opens on the tenant's
//           published TOU plan (Residential Standard), so its first cycle is a
//           FIRST bill, and the journey pays it in full. Every money figure
//           below is READ from 08-qa/01-e2e/expected/money-triples.csv at run
//           time, never typed here.
// Impacts:  e2e/support/census.ts (writes the run receipt gate G12 reads) ·
//           10-scripts/gates/g12_journeys.py (this file ACTIVATES J2, so G12
//           now demands a fresh green receipt for it at wave close)
// ───────────────────────────────────────────────────────
//
// THE FIRST RUN OF THE JOURNEY THIS PRODUCT EXISTS TO PERFORM.
//
// J2 is tier 1 and it had never executed. Until 2026-08-15 it was not even
// eligible: the file carried no frontmatter, so the wiring index computed
// `stories: 0` and the money journey was invisible to the activation machinery
// rather than merely blocked (DEF-102). With the frontmatter added it reads
// story-ready on 15 stories, and this spec is what turns "story-ready" into a
// measured statement about whether a human can actually walk it.
//
// WHAT THIS SPEC IS FOR, said plainly: 2,400 backend tests and 1,042 frontend
// tests check the PARTS. Nothing had ever checked the CHAIN. A journey spec is
// not a better unit test — it is the only artefact that can discover that two
// correct halves do not meet, and its most valuable outcome is a RED at the
// seam, not a green.
//
// SERIAL, and the reason is the subject. A journey is a chain: step 4 needs
// what step 3 left in the database, step 8 needs what step 5 committed. When a
// step cannot be performed the honest report is "the journey stopped HERE",
// not eleven failures with one cause. Playwright's serial mode gives exactly
// that — the failing step is named and everything downstream records as
// skipped, which is a true statement about a journey that did not reach them.
// (W4-payment-write.spec.ts sets the same precedent for the same reason.)
//
// ── DELIVERY IS OUT OF THIS RELEASE, AND STEP 9 SAYS SO ────────────────────
// PO ruling 2026-08-15, carried into the journey file's own step 9: *issuing a
// bill does NOT mean the customer receives one*. No provider adapter exists on
// any channel, print included. **J2 therefore ENDS AT A RENDERED DOCUMENT.**
// Step 9 below asserts that the issued bill renders as a document and asserts
// NOTHING about dispatch; a delivery surface reporting the adapter absent is
// correct output under that ruling, never a failure.
//
// ── WHERE THE FIXTURE STOPS AND THIS JOURNEY STARTS ───────────────────────
// `08-qa/01-e2e/stack/seed_e2e_fixture.py` mints ONE account and ONE issued
// bill by calling the billing engine directly, so that W3/W4 have a money
// figure to render and to pay. That bill did NOT come from a meter read and it
// was NOT issued through S31 — the fixture says so itself. This journey
// deliberately uses NONE of it: it takes a vacant seeded unit (U-00101-B), a
// spare seeded meter (M-5099) and the tenant's own published plans, and walks
// the chain from there through the SCREENS. A journey that asserted the
// fixture's bill would be re-testing the seeder.
//
// ── THE ONE OPEN POINT IN THIS FILE, STATED RATHER THAN HIDDEN ────────────
// `moneyTriple` is the expectation source the activation contract names
// (e2e/README.md §Journey activation), and it is used below. It is ALSO known
// — W3-money-render.spec.ts recorded it first — that the 245-row dataset's
// inputs are not the fixture tenant's ratified rate configuration: the dataset
// prices against four tax authorities and Brazos Bend has two. So the first
// thing steps 7–10 will report, if the chain is ever unblocked far enough to
// reach them, is that mismatch. That is a REPORT to route to the PO (which
// figure is the tenant's, and which is the dataset's), not a defect in this
// spec, and it is written here in advance so nobody has to rediscover it.
import { expect, test } from "@playwright/test";

import { signIn, tenant } from "./support/app";
import { skipUnlessAppServer } from "./support/app";
import { journey } from "./support/journey";
import { moneyTriple } from "./support/expected";

// The A×D×E row for this journey's combination. Read, never retyped.
const J2_MONEY = moneyTriple("tou", "first", "full");

// en-US + USD is what MoneyCell renders with (DEFAULT_MONEY_LOCALE) until the
// tenant Regional feed lands. The DIGITS come from the dataset; only the
// symbol is here. BR-SHL-023: 2 dp on screen, 4 on the wire.
function asRendered(figure: string): string {
  return `$${figure}`;
}

// ── The world this journey walks ──────────────────────────────────────────
// All three are `manage.py seed_demo`'s own rows, chosen because each is the
// UNCLAIMED one of its kind: the vacant unit nothing occupies, the spare meter
// nothing reads, and the published plan the tenant's residential customers are
// meant to be on. Overridable so the journey can drive another seeded tenant.
const UNIT_NO = process.env.J2_UNIT_NO ?? "U-00101-B";
// The unit's human LABEL, which is what the asset pickers show ("Unit B") —
// S15 lists the unit ID and the label in separate columns and the two pickers
// this journey drives do not agree on which they render.
const UNIT_LABEL = process.env.J2_UNIT_LABEL ?? "Unit B";
const METER_NO = process.env.J2_METER_NO ?? "M-5099";
const PLAN_NAME = process.env.J2_PLAN_NAME ?? "Residential Standard";
const CUSTOMER_NAME = "J2 Read-to-cash Customer";

// BR-TEN-043 in a test: every business moment is a PARAMETER, never a clock
// read, so a run on any day walks the same journey. June is the service
// period, July is when it is billed and paid — the same month shape the
// fixture bill and every T3M ride use.
const SERVICE_FROM = "2026-06-01";
const SERVICE_TO = "2026-06-30";
const BILL_DATE = "2026-07-01";
const READ_VALUE = "684"; // kWh on the meter at period end
const PAY_POSTED_AT = "2026-07-18";
const PAY_CLEARED_AT = "2026-07-20";

journey("J2", "read-to-cash — premises → reads → bill → cash → books", () => {
  test.describe.configure({ mode: "serial" });
  skipUnlessAppServer(test);

  // ── STEP 1 ───────────────────────────────────────────────────────────────
  // Handoff contract: "unit exists, occupancy derived (BR-MET-036)".
  test("step 1 · US-MET-001/002 — the unit exists on S15 and its occupancy is DERIVED", async ({
    page,
  }) => {
    await signIn(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Premises", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/premises$`));
    await page.getByRole("tab", { name: "Units" }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/premises/units$`));

    const row = page.getByRole("row").filter({ hasText: UNIT_NO });
    await expect(row).toHaveCount(1);
    // BR-MET-036: occupancy is DERIVED from whether an account holds the unit.
    // The unit this journey takes must start Vacant — an occupied one would
    // mean the journey is walking somebody else's tenancy.
    await expect(row).toContainText("Vacant");
  });

  // ── STEP 2 ───────────────────────────────────────────────────────────────
  // Handoff contract: "asset active on unit, UoM explicit, register digits set".
  test("step 2 · US-AST-002/US-MET-006 — the meter goes onto the unit with an explicit UoM", async ({
    page,
  }) => {
    await signIn(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Assets", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/assets$`));

    const meter = page.getByRole("row").filter({ hasText: METER_NO });
    await expect(meter).toHaveCount(1);
    // S53. ONE modal, TWO labels: a spare in inventory offers "Assign" and a
    // meter already on a unit offers "Reassign" (the modal's own heading says
    // "Reassign" either way). Both are accepted here because this journey
    // WRITES, so a re-run against a database it already changed must still be
    // able to perform the step a human performs.
    await meter.getByRole("button", { name: /^(Assign|Reassign)$/ }).click();

    const form = page.getByRole("dialog");
    await expect(form).toBeVisible();
    // BR-SHL-033's searchable control. The option is picked BY ITS LABEL, not
    // by index: IS-3 debounces the query 300 ms, so the listbox opens on the
    // first keystroke still showing every option, and a `.first()` here would
    // click whichever unit happened to sort first. That is not hypothetical —
    // it is what the first run of this journey did, putting the meter on
    // Unit A. Naming the option makes the click the one a human makes.
    await form.locator("#unit_id").fill(UNIT_LABEL);
    const option = form.locator("li[role=option]").filter({ hasText: UNIT_LABEL });
    await expect(option).toHaveCount(1);
    await option.click();
    await form.locator("#effective_date").fill(SERVICE_FROM);
    await form.getByRole("button", { name: /Reassign/ }).click();

    // The handoff contract, read off the registry the way a clerk reads it.
    await page.goto(`/${tenant()}/assets`);
    const assigned = page.getByRole("row").filter({ hasText: METER_NO });
    await expect(assigned).toContainText("Installed/Active");
    // "UoM explicit" (CLAUDE.md rule 3 — consumption is never unit-less).
    await expect(assigned).toContainText("kWh");
    // The unit the meter now serves, so the chain into step 3 is visible.
    await expect(assigned).toContainText(UNIT_LABEL);

    // NOT ASSERTED HERE, and named rather than skipped quietly: the third
    // clause of this step's handoff contract is "register digits set".
    // `assets.register_digits` exists server-side with a default of 9
    // (BR-AST-015) and NO screen in this product renders or collects it, so a
    // browser cannot see it. Reported with this run.
  });

  // ── STEP 3 ───────────────────────────────────────────────────────────────
  // Handoff contract: "rate_plan published; unit_plan_assignments current row
  // (BR-CUS-010/011)".
  test("step 3 · US-RAT-001..003 — a published plan, and the unit carries it", async ({ page }) => {
    await signIn(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Plans & Rates", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/plans-rates$`));

    // BR-RAT-030: only a PUBLISHED plan may be put on a unit, so the journey
    // reads the status off S9 before it tries.
    const plan = page.getByRole("row").filter({ hasText: PLAN_NAME });
    await expect(plan).toHaveCount(1);
    await expect(plan).toContainText("Published");

    // The assignment itself is S15's row action.
    await page.goto(`/${tenant()}/premises/units`);
    const row = page.getByRole("row").filter({ hasText: UNIT_NO });
    await row.getByRole("button", { name: "Assign plan", exact: true }).click();

    const form = page.getByRole("dialog");
    await expect(form).toBeVisible();
    // The PLAN this unit bills on — the same published plan S9 just showed.
    // BR-CUS-010/011 make this row the thing an account then derives from, so
    // the journey names the plan rather than taking whatever is first.
    await form.locator("#tariff_id").fill(PLAN_NAME);
    await expect(form.locator("li[role=option]").filter({ hasText: PLAN_NAME })).toHaveCount(1);
    await form.locator("li[role=option]").filter({ hasText: PLAN_NAME }).click();
    await form.locator("#effective_from").fill(SERVICE_FROM);
    await form.getByRole("button", { name: "Assign plan", exact: true }).click();

    // The current row exists ⇒ the modal closed on a 201 rather than staying
    // open with a refusal. A dialog still on screen IS the refusal.
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  // ── STEP 4 ───────────────────────────────────────────────────────────────
  // Handoff contract: "account active, plan version snapshot saved
  // (account_plan_assignments, BR-CUS-014 sc.1), deposit rule applied
  // (plan_deposit_rules fixed $)".
  test("step 4 · US-CUS-003/004/006/007 — the account is active on the unit, with its snapshot", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/accounts/new`);

    // S18 step 1 — the customer.
    await page.locator("#full_name").fill(CUSTOMER_NAME);
    await page.getByRole("button", { name: "Continue" }).click();

    // S18 step 2 — the unit. Only VACANT units are offered, so this is also
    // step 1's BR-MET-036 derivation read back from another screen.
    await page.locator("#unit_id").fill(UNIT_NO);
    const option = page.locator("li[role=option]").filter({ hasText: UNIT_NO });
    await expect(option).toHaveCount(1);
    await option.click();
    // BR-MET-006: the meter step 2 assigned is what this unit is billed on.
    await expect(page.locator("main")).toContainText(METER_NO);
    await page.locator("#opened_at").fill(SERVICE_FROM);

    // Steps 3–5 (plan · billing prefs · deposit) then the review.
    for (let i = 0; i < 4; i++) {
      await page.getByRole("button", { name: "Continue" }).click();
    }
    await page.getByRole("button", { name: /Create & activate/ }).click();

    // ── the handoff contract, read off S21 ────────────────────────────────
    await expect(page.getByRole("row").filter({ hasText: CUSTOMER_NAME })).toHaveCount(1);
    const account = page.getByRole("row").filter({ hasText: CUSTOMER_NAME });
    await expect(account).toContainText("Active");
    await account.getByRole("link").first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/accounts/`));

    // BR-CUS-014 sc.1 / BR-CUS-029: the plan VERSION the account was opened on
    // is snapshotted, and it is what step 7 prices from. The screen must name
    // the plan this account bills on.
    await expect(page.locator("main")).toContainText(PLAN_NAME);
    // US-CUS-007: the deposit rule the plan carries (plan_deposit_rules, fixed
    // $) is applied at activation — the dataset's first-bill row carries it as
    // "deposit 150.00 + CONN 25.00 non-taxable (BR-BIL-012)".
    await expect(page.locator("main")).toContainText("Deposit");
  });

  // ── STEP 5 ───────────────────────────────────────────────────────────────
  // Handoff contract: "committed meter_reads, one row per `channel`
  // (total/tou_*/export/demand per BR-MET-059, B2 r8), plan-required channel
  // set complete (BR-MET-049), status ok/estimated".
  test("step 5 · US-MET-010..013 — the period's reads are imported and committed", async ({
    page,
  }) => {
    await signIn(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Reads", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/reads$`));

    // S28 — the import wizard. This is the ONLY way a human puts a reading
    // into this product: BR-CUS-021 refuses `initial_reads` on the account
    // create and BR-CUS-021 refuses `final_reads` on the move-out, both
    // because reads commit through metering's own append-only path (B1).
    const upload = page.getByRole("button", { name: /Upload reads/ });
    await expect(upload).toBeEnabled();
    await upload.click();

    const wizard = page.getByRole("dialog");
    await expect(wizard).toBeVisible();
    await wizard.locator("#read-import-text").fill(`${METER_NO},${SERVICE_TO},${READ_VALUE}`);
    await wizard.getByRole("button", { name: /Commit|Post|Import/ }).click();

    // BR-MET-059 / B2 r8: one committed row per channel, and BR-MET-049's
    // plan-required set complete — a missing channel is never billed as zero.
    await page.goto(`/${tenant()}/reads`);
    await page.getByRole("tab", { name: "All reads" }).click();
    const read = page.getByRole("row").filter({ hasText: METER_NO });
    await expect(read).toHaveCount(1);
    await expect(read).toContainText(READ_VALUE);
  });

  // ── STEP 6 ───────────────────────────────────────────────────────────────
  // Handoff contract: "flags resolved or estimated per BR-MET rules".
  test("step 6 · US-MET-011 — nothing on this meter is left flagged", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/reads`);

    // S25's Needs-attention tab is the clerk's own gate before a bill run:
    // a flagged reading that reaches rating prices a guess.
    await expect(page.locator("main")).toContainText("Flagged");
    const flagged = page.locator(".kpi").filter({ hasText: "Flagged" });
    await expect(flagged).toContainText("0");
  });

  // ── STEP 7 ───────────────────────────────────────────────────────────────
  // Handoff contract: "priced lines per B4 CONFIRMED math
  // (GT-1/2/5/10/11/13/15), priced from the account snapshot as of service
  // date (BR-CUS-014 sc.6)".
  test("step 7 · US-RAT-012/013 🔒 — the run prices the period from the account's snapshot", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing/run`);

    // S31 step 1 — the cycle, the period and the bill date. BR-BIL-025: the
    // bill date is what picks the prices, so it is typed and never guessed.
    await page.locator("#brun-cycle").selectOption({ index: 1 });
    await page.locator("#brun-period-start").fill(SERVICE_FROM);
    await page.locator("#brun-period-end").fill(SERVICE_TO);
    await page.locator("#brun-bill-date").fill(BILL_DATE);
    // The service checkbox is a styled control — the input is visually hidden
    // and the LABEL is what a human clicks (BR-SHL-017's field kit).
    await page.locator("label[for=brun-service-electric]").click();
    await page.getByRole("button", { name: /Start this run/ }).click();

    // Step 2 — what the run found. The account step 4 created must be READY,
    // not carried in the "cannot be billed yet" set: a chain that silently
    // drops its own customer has not been walked.
    await expect(page.locator("main")).toContainText(CUSTOMER_NAME);
    const ready = page.locator(".kpi").filter({ hasText: "Ready to bill" });
    await expect(ready).toContainText("1");
  });

  // ── STEP 8 ───────────────────────────────────────────────────────────────
  // Handoff contract: "invoice status=issued, immutable, taxable flags set,
  // due_date set".
  test("step 8 · US-BIL-005 — the run issues an immutable bill with a due date", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing/run`);

    // BR-BIL-058: the five phase-5 confirmations are recorded before anything
    // issues. A run that could issue without them is the rule this journey is
    // here to prove holds.
    for (const confirmation of [
      "I confirm this run meets our compliance checks.",
      "I have seen how many customers can be emailed.",
      "I have seen how many customers have agreed to texts.",
      "I have seen how many customers are on automatic payment.",
      "I confirm these bills are ready to send.",
    ]) {
      await page.getByText(confirmation).click();
    }
    await page.getByRole("button", { name: /Send all now/ }).click();

    // The issued bill on S30, with the money the dataset carries.
    await page.goto(`/${tenant()}/billing`);
    const bill = page.getByRole("row").filter({ hasText: CUSTOMER_NAME });
    await expect(bill).toHaveCount(1);
    await expect(bill).toContainText("Issued");
    await expect(bill.locator(".cell-money-amount")).toHaveText(asRendered(J2_MONEY.total));
    // BR-BIL-024: the due date DERIVES at issue from the cycle's terms. It is
    // asserted as PRESENT rather than as a date, because which date it is is
    // the cycle's arithmetic and not this journey's claim.
    await expect(bill).not.toContainText("—");
  });

  // ── STEP 9 ───────────────────────────────────────────────────────────────
  // Handoff contract, RE-SCOPED IN PLACE by PO ruling 2026-08-15: "bill
  // rendered per A19". Delivery is OUT of this release — no provider adapter
  // exists on any channel, print included — so this journey ENDS AT A RENDERED
  // DOCUMENT and asserts nothing about dispatch.
  test("step 9 · A19 — the issued bill renders as a document (delivery is OUT)", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing`);

    const bill = page.getByRole("row").filter({ hasText: CUSTOMER_NAME });
    await bill.getByRole("link").first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/bills/`));

    // S30 detail opens on Document — the A19 summary box the customer reads.
    // BR-BIL-035: the amount due is the balance-forward figure, and it is the
    // one number a customer phoning in is asking for.
    const summary = page.locator("main");
    await expect(summary).toContainText("Amount due");
    await expect(summary).toContainText(asRendered(J2_MONEY.total));

    // The SAVED COPY is what "rendered document" means (BR-BIL-030): the bill
    // as it was issued, re-openable months later. This is the end of the
    // journey under the 2026-08-15 ruling.
    await expect(page.getByRole("button", { name: "Print bill" })).toBeEnabled();

    // The priced lines behind it, at the dataset's signed figures.
    await page.getByRole("tab", { name: "Charges" }).click();
    const lines = page.locator("table.met-table").filter({ has: page.locator("tfoot") });
    const footer = lines.locator("tfoot tr");
    await expect(footer.nth(0).locator(".cell-money-amount")).toHaveText(
      asRendered(J2_MONEY.taxable),
    );
    await expect(footer.nth(1).locator(".cell-money-amount")).toHaveText(asRendered(J2_MONEY.tax));
    await expect(footer.nth(2).locator(".cell-money-amount")).toHaveText(asRendered(J2_MONEY.total));
  });

  // ── STEP 10 ──────────────────────────────────────────────────────────────
  // Handoff contract: "payment cleared, allocations rows per BR-PAY-010 order".
  test("step 10 · US-PAY-001/US-CUS-012 — the payment clears and meets the bill", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/payments/record`);

    await page.getByRole("button", { name: "Record payment", exact: true }).first().click();
    const form = page.getByRole("dialog");
    await expect(form).toBeVisible();

    // ⚠ ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`) — type and choose on the
    // same element; the matches are `role="option"` rows in its panel.
    await form.locator("#account_id").fill(CUSTOMER_NAME);
    await form.getByRole("option", { name: new RegExp(CUSTOMER_NAME) }).first().click();
    // The dataset's `paid` for this combination — the whole bill, in full.
    await form.locator("#amount").fill(J2_MONEY.paid);
    // BR-PAY-021: BOTH dates, because billing judges lateness by one of them
    // and the books post on the other.
    await form.locator("#posted_at").fill(PAY_POSTED_AT);
    await form.locator("#cleared_at").fill(PAY_CLEARED_AT);
    await form.locator("#method").selectOption({ index: 1 });
    await form.getByRole("button", { name: "Record payment", exact: true }).click();

    const result = page.locator(".pay-result");
    await expect(result).toBeVisible();
    await expect(result.locator(".cell-money-amount").first()).toHaveText(
      asRendered(J2_MONEY.paid),
    );
    // BR-PAY-010's allocation order, read as its OUTCOME: a full payment meets
    // the bill, so nothing is left outstanding and nothing is carried as credit.
    await expect(result).toContainText(asRendered(J2_MONEY.outstanding));
    await expect(result).toContainText(asRendered(J2_MONEY.credit));

    // Hard rule 4 / BR-BIL-004: the money moving does not restate the bill.
    await page.goto(`/${tenant()}/billing`);
    const bill = page.getByRole("row").filter({ hasText: CUSTOMER_NAME });
    await expect(bill.locator(".cell-money-amount")).toHaveText(asRendered(J2_MONEY.total));
  });

  // ── STEP 11 ──────────────────────────────────────────────────────────────
  // Handoff contract: "balanced journal pair via posting service ONLY".
  test("step 11 · US-LED-001 🔒 — the books carry a balanced pair for the money", async ({
    page,
  }) => {
    await signIn(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Finance", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/finance$`));

    // CLAUDE.md rule 5: the ledger only ever moves in balanced pairs, and only
    // the posting service writes them. S36 is where a human sees that hold —
    // the revenue this journey billed and the cash it collected, on one screen.
    const finance = page.locator("main");
    await expect(finance).toContainText(asRendered(J2_MONEY.total));
    await expect(finance).toContainText(asRendered(J2_MONEY.paid));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: J2 activation (08-qa/01-e2e/journeys/J2-read-to-cash.md) / PO ruling
//   2026-08-15 ("issuing a bill does NOT mean the customer receives one" —
//   delivery OUT, J2 ends at a rendered document) / DEF-102 (J2 carried no
//   frontmatter and was invisible to the activation machinery)
// generated: 2026-08-15 by the J2 journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e`✔ · playwright against a live stack booted by
//   08-qa/01-e2e/stack/boot_stack.sh on its own database (sbh_j2_lane) and its
//   own ports (8010/8090) · run_gates.py --wave-close — tail quoted in the lane
//   report. NOTE: `npm run lint` lints `src` only, so it does not cover this
//   file — stated, not claimed.
// FIRST RUN, 2026-08-15 — WHAT IT FOUND. Recorded here rather than only in a
//   lane report, because the next agent reads the repo and not the chat
//   (CLAUDE.md law 10). Steps 1 and 2 PASS. The journey stops at step 3, and
//   four further walls were located by hand afterwards, each independent of the
//   first — so unblocking step 3 alone does not complete the money path:
//
//   * STEP 3 — the wall the run stops on. S15's "Assign plan" modal fills its
//     picker from `GET /rate-schedules` (`getUnitPlanOptions`, api/endpoints.ts)
//     while `POST /units/{id}/plan-assignments` resolves the id against
//     `rate_plans` (`_apply_unit_plan` → `seams.plan_ref`; the PO's 2026-08-11
//     ruling moved the target from tariff to PLAN and the picker never moved).
//     EVERY option the screen offers is refused:
//         422 {"code":"VAL-005","message_key":"metering.plan.tariff_unknown",
//              "field_errors":[{"field":"tariff_id",…}]}
//     rendered as "That plan wasn't found." The endpoint is FINE — posting a
//     `rate_plans` id by hand answers 201 and writes the current row. So a
//     human cannot put a unit on a plan anywhere in this product, and
//     BR-MET-040 then blocks every account activation behind it.
//   * STEP 4 — reachable only with step 3 bypassed, and its handoff contract is
//     unmeetable by design-in-absence: S18 step 3 states "No plan recorded
//     (BR-CUS-029)" and step 5 "Nothing will be recorded (BR-CUS-023)".
//     `account_plan_assignments` HAS NO TABLE in the migrated schema, so the
//     plan-version snapshot BR-CUS-014 sc.1 requires — the thing step 7 is
//     supposed to price from — does not exist.
//   * STEP 5 — S28 is not built. S25's "↑ Upload reads" renders DISABLED with
//     its reason (BR-SHL-025, correctly): "The upload wizard is not built in
//     this release. The endpoints behind it are already served — the screen is
//     not." `meter_reads` is EMPTY on a fully seeded stack and no screen can
//     add a row, so no bill in this product has ever come from a reading.
//   * STEP 8 — S31 cannot issue. Its step 5 says "Your sign-off cannot be
//     recorded yet … Rule BR-BIL-058 · table bill_run_releases — no endpoint is
//     contracted", and its step 6 "Rule BR-BIL-051 · POST /billing/runs/{id}/issue".
//     Neither route is in `apps/billing/api.py` urlpatterns. A run reaches
//     draft and stops.
//   * STEP 9 — the re-scoped end of this journey is itself unreachable, and the
//     screen contradicts itself about why: the Document tab says "Locked copy
//     saved: Yes" beside "The saved copy exists but cannot be opened yet
//     (BR-BIL-030)", while "Print bill" is disabled with "No saved copy was
//     recorded for this bill, so there is nothing to print." Same bill, same
//     screen, opposite statements. "Total due" also prints "—" (BR-BIL-035
//     balance-forward is not stamped into `bill_payload`; OQ-117).
//   * STEP 11 — S36 Finance can never load. The screen requests
//     `GET /finance/revenue-ar?f.from=…&f.to=…` (the `f.<name>` grammar
//     api/endpoints.ts records as this lane's own PROPOSAL) and the endpoint
//     takes bare `from`/`to`:
//         422 {"code":"VAL-001","message_key":"ledger.report.period_required",
//              "field_errors":[{"field":"from",…}]}
//     rendered as "The finance figures could not be loaded".
//
// exceptions:
//   (1) THIS JOURNEY DOES NOT COMPLETE, and the spec is deliberately NOT
//       trimmed to the part that does. Serial mode names the step it stopped
//       at; the steps below it record as skipped, which is the true statement
//       about a chain that never reached them. Nothing here was weakened to
//       make a step pass.
//   (2) the money assertions read `moneyTriple("tou","first","full")` because
//       the activation contract names that source. The fixture tenant's
//       ratified rate configuration is known NOT to reproduce the dataset's
//       inputs (W3-money-render.spec.ts recorded the same for `flat`), so if
//       the chain is unblocked as far as step 7 the first thing it reports is
//       that mismatch — a question for the PO, not a defect in this file.
//   (3) step 2's third handoff clause, "register digits set", is NOT asserted:
//       `assets.register_digits` is stored server-side with a default of 9 and
//       NO screen renders or collects it, so a browser cannot see it. Named at
//       the step rather than dropped.
//   (4) the bill's due DATE is asserted as present, not as a value: BR-BIL-024
//       derives it from the cycle's own terms, and pinning a date here would
//       make this spec a second opinion on the cycle's arithmetic.
//   (5) step 9 asserts NOTHING about delivery, per the PO ruling of
//       2026-08-15 carried in the journey file's own step 9.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
