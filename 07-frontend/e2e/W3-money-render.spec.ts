// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-001 (sign in, S3) · US-SHL-001 (shell nav, BR-SHL-001) ·
//           US-BIL-025 (GET /invoices — the S30 list) · US-BIL-026
//           (GET /invoices/{id} — the S30 detail)
//           Screens: S3 · shell-chrome · S30 · S30 detail
// Rules:    BR-SHL-023 (ONE money formatting path, 2 dp at display) ·
//           BR-BIL-010 (each line carries the GL stamped at issue) ·
//           BR-BIL-011 (bill anatomy — lines, taxes, total) · BR-RAT-003 /
//           B4.4 (round per line, half-up, 2 dp, at finalization) · BR-RAT-005
//           / B4.2 (tax base = usage + base)
// Golden:   GT-1 — B5 ❄️ FROZEN, finance-signed 2026-08-08. **Every figure
//           asserted below is READ FROM `04-docs/02-decisions/05-golden-tests.md`
//           at run time** (`goldenCalc("GT-1")`), never typed here. A finance
//           re-sign under HUMAN-GUIDE §6 moves this spec in the same commit.
// Tests:    this file. Its fixture is `08-qa/01-e2e/stack/seed_e2e_fixture.py`,
//           which prices the same bill THROUGH THE REAL ENGINE.
// Impacts:  .github/workflows/qa.yml (runs it) · e2e/support/census.ts (counts
//           its assertions, and fails the run when it executed none)
// ───────────────────────────────────────────────────────
//
// THE FIRST BROWSER-TO-DATABASE MONEY PROOF IN THIS REPO.
//
// PO ruling, 2026-08-11, verbatim: **"we ahve to prove against human clicking"**
// (12-governance/02-decision-log.md). The state it answered, measured: 1,651
// backend tests drive the real cross-module chain against a real database; 875
// frontend tests run against MOCKED responses; and NOTHING exercised a browser
// against a live server. So the frozen money was known to reproduce through the
// engine and to land correctly in the database, and **nothing proved that the
// human staring at the screen sees those same numbers**.
//
// This spec closes that one gap for one bill, front to back:
//
//     browser → real S3 sign-in → session cookie → /api/{tenant}/invoices
//             → Postgres → JSON → React → RENDERED TEXT → assertion
//
// and the assertion compares that rendered text to GT-1 as B5 states it.
//
// WHAT IT IS NOT. It is not a catalog journey: the 304 files in
// `08-qa/01-e2e/journeys/` activate through the wiring index when their last
// story is built (e2e/README.md), and nothing here activates one. J07 and
// T3M-001 both need reads, payments and deposit rules that do not exist yet;
// claiming either ID would be the same false comfort DEF-057 is about. This is
// the narrowest ride that reaches a ❄️ FROZEN figure, and it is named for what
// it is.
//
// WHY GT-1 AND NOT A money-triples.csv ROW. The 245-row dataset's `flat` shape
// prices 700 kWh at $0.11 against FOUR tax authorities; the fixture utility's
// ratified configuration has neither that schedule nor those authorities, so
// reproducing 97.41 would mean inventing rates. GT-1's tax — *"8.25 % on
// (usage+base)"* — IS Brazos Bend's own seeded pair (Texas State 6.25 % + Local
// 2.00 %), and under B4.4's per-line rounding the pair lands on GT-1's signed
// $8.30 exactly. The seeder's `_tax_rules` docstring works that through.
import { expect, test } from "@playwright/test";

import { bootApp, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";
import { goldenCalc } from "./support/expected";

// GT-1's worked line, as B5 writes it (05-golden-tests.md):
//   "684×0.12 = 82.08; +18.50 = 100.58; tax 8.2979 → 8.30; **total 108.88**"
// Read, never retyped. The four steps are named here so a mis-parse is a
// NAMING error in this file and not a silent wrong number in an assertion.
const GT1 = goldenCalc("GT-1");
const [GT1_USAGE, GT1_SUBTOTAL, GT1_TAX, GT1_TOTAL] = GT1.steps;

// en-US + USD is what MoneyCell renders with (DEFAULT_MONEY_LOCALE) until the
// tenant Regional feed lands. The DIGITS come from B5; only the symbol is here.
function asRendered(figure: string): string {
  return `$${figure}`;
}

// The account `08-qa/01-e2e/stack/seed_e2e_fixture.py` bills. It identifies the
// row without pinning the bill NUMBER, which the tenant's own series allocates
// and which therefore differs between a fresh database and a re-seeded one.
function fixtureAccountNo(): string {
  return process.env.E2E_ACCOUNT_NO ?? "E2E-10001";
}

// A tenant slug the fixture never provisions — used to prove the SCREEN is
// scoped, not just the API. `apps.tenancy.selectors.RESERVED_SUBDOMAINS`
// refuses to mint anything named after a platform path, and this is not one of
// those either, so it is simply a tenant that does not exist.
const OTHER_TENANT = "not-brazosbend";

test.describe("W3 money render — a human sees the figure finance signed", { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);

  test("the B5 fixture this spec asserts against is the one it says it is", () => {
    // Not ceremony: `goldenCalc` parses a FROZEN document, and a parser that
    // silently mis-aligned would make every assertion below compare the right
    // rendered text to the wrong signed figure. So the parse is checked against
    // GT-1's own two internal statements before anything is rendered.
    expect(GT1.heading).toContain("GT-1");
    expect(GT1.steps).toHaveLength(4);
    // B5 marks the headline with `**total N**`; it must be the last step too.
    expect(GT1_TOTAL).toBe(GT1.total);
    // "Input: Electric flat $0.12/kWh, base $18.50, usage 684 kWh, tax 8.25% …"
    expect(GT1.input).toContain("684");
    expect(GT1.input).toContain("18.50");
  });

  test("signs in, clicks Billing, and the list's TOTAL is GT-1's frozen total", async ({
    page,
  }) => {
    await signIn(page);

    // A human clicking, not a URL typed: the sidebar item is what a clerk uses,
    // and a nav item that navigates nowhere is exactly the "built is not wired"
    // class (hard-won law 2) that no mocked test can see.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Billing", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing$`));

    const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() });
    await expect(row).toHaveCount(1);
    // TOTAL is the row's only money column (S30: bill # · cycle · account ·
    // customer · issue date · due date · TOTAL · status).
    await expect(row.locator(".cell-money-amount")).toHaveText(asRendered(GT1_TOTAL));
  });

  test("opens the bill and every GT-1 figure renders at its signed value", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing`);

    const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() });
    // The bill number is the row's first link (the account number is the
    // second); clicking it is how a clerk opens a bill.
    await row.getByRole("link").first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/bills/`));

    // S30 detail opens on Document; the priced lines are the Charges tab.
    await page.getByRole("tab", { name: "Charges" }).click();

    const lines = page.locator("table.met-table").filter({ has: page.locator("tfoot") });
    const usageRow = lines.getByRole("row").filter({ hasText: "electric usage" });
    // Two money cells on a usage row — unit price, then amount (BR-BIL-011).
    await expect(usageRow.locator(".cell-money-amount").last()).toHaveText(
      asRendered(GT1_USAGE),
    );

    // The three footer rows, in the order BillDetailPage writes them.
    const footer = lines.locator("tfoot tr");
    await expect(footer).toHaveCount(3);
    await expect(footer.nth(0)).toContainText("Subtotal");
    await expect(footer.nth(0).locator(".cell-money-amount")).toHaveText(
      asRendered(GT1_SUBTOTAL),
    );
    await expect(footer.nth(1)).toContainText("Tax");
    await expect(footer.nth(1).locator(".cell-money-amount")).toHaveText(asRendered(GT1_TAX));
    await expect(footer.nth(2)).toContainText("Total");
    await expect(footer.nth(2).locator(".cell-money-amount")).toHaveText(asRendered(GT1_TOTAL));
  });

  test("a tenant that does not own the bill cannot see it on the screen", async ({ page }) => {
    // CLAUDE.md rule 1, read from the BROWSER. That a cross-tenant read is a
    // 404 rather than a 403 is asserted at API level (BR-TEN-003,
    // 06-backend/tests/test_us_bil_025_026_bills_read.py). What no API test can
    // see is what the SCREEN then does with that answer — and a list that
    // rendered another tenant's row would be the worst defect this product
    // could ship. So the same list is opened under a tenant segment that does
    // NOT own the bill, and the fixture row must not be there.
    //
    // The slug is deliberately one the fixture never provisions: an
    // unprovisioned tenant and a real-but-other tenant reach the same screen
    // through the same 404, which is the point of HR-1's "reads as absent".
    await signIn(page);
    await bootApp(page);
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/dashboard$`));

    await page.goto(`/${OTHER_TENANT}/billing`);
    await expect(page.getByRole("row").filter({ hasText: fixtureAccountNo() })).toHaveCount(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking")
// generated: 2026-08-11 by the E2E bring-up lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e`✔ (this directory's FIRST typecheck — see
//   tsconfig.e2e.json) · tsc --noEmit✔ · `npm run lint`✔ (BUT it lints `src`
//   only, so it does not cover this file — stated, not claimed) · vitest 890
//   passed / 183 todo✔ · vite build✔
//   run_gates 18 PASS · 0 FAIL · 1 SKIP✔ · playwright 10 passed, 22 app-server
//   assertions, against the live stack
// red-proof (law 7): a SECOND account was seeded with a bill the engine priced
//   from 683 kWh instead of GT-1's 684 — a real bill, in the real database,
//   reached through the real API — and this spec failed on it, verbatim:
//     Expected: "$108.88"   Received: "$108.75"
//     Expected: "$82.08"    Received: "$81.96"
//   The bill was ISSUED and therefore immutable, so the restore was to drop and
//   re-seed the fixture database rather than to edit a row; the clean re-boot
//   is quoted in the lane report.
// exceptions: not a catalog journey — see the header. The bill's NUMBER is not
//   asserted (the tenant series allocates it); the ACCOUNT number is the row key.
//   The cross-tenant case asserts an ABSENCE (`toHaveCount(0)`), which a page
//   that failed to render at all would also satisfy — the positive half of that
//   pair is the API-level 404 test in
//   06-backend/tests/test_us_bil_025_026_bills_read.py, and this is deliberately
//   the weaker screen-side companion rather than a claim to replace it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
