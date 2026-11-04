// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-127 (2026-08-15, CRITICAL) — *"NO SURFACE IN THE PRODUCT CAN
//           TELL A CUSTOMER WHAT THEY OWE — the account reads $0.00 and 'Awaits
//           billing' while the ledger holds an issued, unpaid $108.88."*
//           Screens: S17 (accounts list + header) · S30 (the bill)
// Rules:    BR-CUS-015 (`accounts.balance` is a CACHE; the ledger is the source
//           of truth) · BR-REP-002 (read-models over journal-line dimensions,
//           never a side-maintained number) · BR-BIL-035 (the balance-forward
//           block is STAMPED at issue) · BR-SHL-023 (ONE money formatting path)
// Golden:   GT-1 — B5 ❄️ FROZEN, finance-signed 2026-08-08. Every figure below
//           is READ from `04-docs/02-decisions/05-golden-tests.md` at run time
//           (`goldenCalc("GT-1")`), never typed here.
// Tests:    the backend half is
//           06-backend/tests/test_def_127_one_account_one_figure.py, which asks
//           the same question of seven server surfaces at once.
// Impacts:  its fixture is `08-qa/01-e2e/stack/seed_e2e_fixture.py` — the SAME
//           account `E2E-10001` and the SAME bill DEF-127 was measured on.
// ───────────────────────────────────────────────────────
//
// DEF-127 WAS FOUND BY LOOKING AT A SCREEN, AND ONLY A SCREEN CAN PROVE IT
// FIXED (hard-won law 6). The backend check next door proves seven server
// surfaces state one figure. It cannot see what a clerk reads, and what a clerk
// read was: **Balance $0.00 · Awaits billing** beside an account holding an
// issued, unpaid 108.88, with **Outstanding $0.00** in the header above it and
// an em-dash where the bill's TOTAL DUE belongs.
//
// So this drives the two screens the defect names, on the booted stack, and
// asserts the FIGURE A HUMAN SEES — three times, in the three places that
// disagreed.
import { expect, test } from "@playwright/test";

import { signIn, tenant, skipUnlessAppServer } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";
import { goldenCalc } from "./support/expected";

// GT-1's frozen total, read from B5 rather than typed: "684×0.12 = 82.08;
// +18.50 = 100.58; tax 8.2979 → 8.30; **total 108.88**". It is the figure the
// fixture bills and the figure DEF-127 was measured on.
const GT1_TOTAL = goldenCalc("GT-1").total;

// en-US + USD is what MoneyCell renders with until the tenant Regional feed
// lands (DEFAULT_MONEY_LOCALE). The DIGITS come from B5; only the symbol here.
const OWED = `$${GT1_TOTAL}`;

// The account `08-qa/01-e2e/stack/seed_e2e_fixture.py` bills — DEF-127's own.
function fixtureAccountNo(): string {
  return process.env.E2E_ACCOUNT_NO ?? "E2E-10001";
}

test.describe(
  "DEF-127 — a clerk can see what this customer owes",
  { tag: APP_SERVER_TAG },
  () => {
    skipUnlessAppServer(test);

    test("the accounts row shows the balance and the date it was billed", async ({ page }) => {
      await signIn(page);

      // A human clicking, not a URL typed.
      const nav = page.getByRole("navigation", { name: "Main navigation" });
      await nav.getByRole("link", { name: "Accounts", exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/${tenant()}/accounts$`));

      const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() });
      await expect(row).toHaveCount(1);

      // THE CELL THE DEFECT WAS MEASURED ON. It read $0.00.
      await expect(row.locator(".cell-money-amount")).toHaveText(OWED);

      // And the cell beside it read "Awaits billing" about an account whose
      // bill had issued on 1 July — the seam resolved the wrong module
      // attribute, so nothing ever answered the last-bill read.
      await expect(row).not.toContainText("Awaits billing");
    });

    test("the header KPI is not $0.00 while the books hold a debt", async ({ page }) => {
      await signIn(page);
      await page.goto(`/${tenant()}/accounts`);

      const rollup = page.locator(".page-header-rollup");
      await expect(rollup).toContainText("Outstanding");

      // The header is a TENANT total across every seeded account, so it is not
      // GT-1's figure and must not be asserted as one — what DEF-127 makes
      // assertable is that it is not ZERO while an account owes money, and that
      // it is at least what that one account owes. A stricter equality here
      // would be a claim about the whole fixture cohort, which other lanes'
      // seeders legitimately change.
      const outstanding = await rollup
        .locator(".cus-rollup-item", { hasText: "Outstanding" })
        .locator(".cell-money-amount")
        .innerText();
      const shown = Number(outstanding.replace(/[^0-9.]/g, ""));
      expect(shown).toBeGreaterThanOrEqual(Number(GT1_TOTAL));
    });

    test("the bill prints its TOTAL DUE instead of an em-dash", async ({ page }) => {
      await signIn(page);
      await page.goto(`/${tenant()}/billing`);

      const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() });
      await row.getByRole("link").first().click();
      await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/bills/`));

      // A19 §1.3's summary box — the largest number on a utility bill, and the
      // one this product could not print. BR-BIL-035 stamps it at issue; the
      // read model had never opened the stamp.
      //
      // ⚠ THE LOCATOR IS THE `[data-bil="summary-total"]` <dd> AND NOTHING LOOSER, and
      // that is a finding rather than a preference. The first draft of this test
      // read `.cell-money-amount` LAST inside the box — which, on a bill whose
      // total due renders as an em-dash, resolves to CURRENT CHARGES instead and
      // matches $108.88. It passed against the defect. A check aimed at the row
      // beside the one that is broken is not a check (law 7 caught it).
      const summary = page.locator('dl[data-bil="summary"]');
      await expect(summary).toContainText("Total due");
      const totalDue = summary.locator('dd[data-bil="summary-total"]');
      await expect(totalDue.locator(".cell-money-amount")).toHaveText(OWED);

      // The four figures FOOT on the page a customer receives:
      // previous balance − payments received + current charges = total due.
      // This account has no earlier bill, so the two middle lines are 0.00 —
      // and 0.00 here is a STAMPED figure, not an absence rendered as one, which
      // is why the awaiting marker must be nowhere in the box.
      await expect(summary).toContainText("Previous balance");
      await expect(summary).toContainText("Current charges");
      await expect(summary).not.toContainText("Not available");
    });
  },
);

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-127 (12-governance/10-defect-log.csv)
// generated: 2026-08-16 by the balance lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: `npm run typecheck:e2e`✔ · run against the live stack booted by
//   08-qa/01-e2e/stack/boot_stack.sh; the rendered figures are quoted in the
//   lane report
// red-proof (law 7): run against the stack BEFORE the fix, the same three
//   assertions failed on the rendered text — the row read "$0.00", the cell
//   beside it read "Awaits billing", and the summary box had no money cell for
//   Total due at all. The API responses behind each are quoted in the lane
//   report (balance 0.000000 · last_bill_at null · total_due null).
// exceptions: the header assertion is a LOWER BOUND, not an equality — the
//   roll-up is a tenant total and `seed_journey_fixture.py` adds cohorts to the
//   same tenant, so pinning it would make this spec fail whenever another lane
//   seeds an account. The equality is asserted where it IS sound: on a tenant of
//   one account, in 06-backend/tests/test_def_127_one_account_one_figure.py
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
