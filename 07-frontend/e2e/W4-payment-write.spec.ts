// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-001 (sign in, S3) · US-SHL-001 (shell nav, BR-SHL-001) ·
//           US-PAY-004 (S33 Record payments — the list and its money columns) ·
//           US-PAY-001 (the S22/S35 Record modal — the WRITE) · US-BIL-026
//           (GET /invoices/{id} — the S30 detail this re-reads afterwards)
//           Screens: S3 · shell-chrome · S33 · S30 detail
// Rules:    BR-PAY-021 (posting date ≠ clearing date — BOTH collected, BOTH
//           rendered) · BR-PAY-022 (the single-entry field set) · BR-PAY-028
//           (one submit token per opened form) · BR-PAY-012 (purpose `bill`) ·
//           BR-BIL-004 / hard rule 4 (an ISSUED bill is never restated — the
//           money moving does not touch it) · BR-SHL-023 (ONE money formatting
//           path, 2 dp at display) · BR-SHL-025 (a control that cannot be
//           honoured renders disabled WITH its reason)
// Golden:   GT-1 — B5 ❄️ FROZEN, finance-signed 2026-08-08. The amount this
//           spec TYPES INTO THE FORM and every figure it asserts are read from
//           `04-docs/02-decisions/05-golden-tests.md` at run time
//           (`goldenCalc("GT-1")`), never typed here.
// Tests:    this file. Its fixture is `08-qa/01-e2e/stack/seed_e2e_fixture.py`
//           (one account, one engine-priced ISSUED bill).
// Impacts:  .github/workflows/qa.yml (runs it) · e2e/support/census.ts (counts
//           its assertions and writes the run receipt gate G12 reads)
// ───────────────────────────────────────────────────────
//
// THE FIRST BROWSER-DRIVEN **WRITE** IN THIS REPO.
//
// `W3-money-render.spec.ts` proved that a human SEES the figure finance signed.
// It is entirely a READ: sign in, click, assert. Nothing in this repo had ever
// driven the product to CHANGE anything — and the payments write path is the
// exact place where "built is not wired" (hard-won law 2) bit hardest this week:
// the service could record a payment, allocate it across open bills and post it
// to the books, under nineteen passing tests, while `apps/payments/api.py` was a
// one-line docstring and **no human being could record a payment at all**.
//
// So this spec types into the S33/S22 form the way a clerk does — account,
// amount, BOTH BR-PAY-021 dates, method — clicks Record payment, and asserts
// what comes back.
//
// WHAT IT IS NOT, and this matters more than what it is:
//
//   **It is NOT a catalog journey and claims no journey ID.** The steps it
//   performs are step 2 of the T3M money-triple rides ("payment outcome: full")
//   and step 3 of J07 ("payment by check, posting and clearing dates entered"),
//   but neither journey is ACTIVATED by it. J07 needs a move-in wizard, a
//   prorated first bill, a deposit position and a month-2 cycle run; T3M-001
//   needs a flat fixture priced at 97.41 against four tax authorities this
//   tenant does not have, and its steps 3–4 need a late-fee assessment surface
//   and ledger tie-outs that no endpoint serves. A spec claiming an ID it can
//   only half-perform is precisely the false comfort DEF-057 is about, and
//   `07-frontend/e2e/README.md` records that refusal as the standard. Gate G12
//   now enforces it mechanically.
//
// WHY THE ASSERTIONS ARE THE ONES THEY ARE — the repeatability problem, stated:
// a WRITE spec changes the world it asserts against, and this stack's database
// survives between runs (`boot_stack.sh` is idempotent; it does not drop). Run
// one records a payment that MEETS the fixture bill; run two records a second
// payment that meets nothing and is carried as credit. So every assertion below
// is one that holds on EVERY run — the amount received, the row's own money and
// its two dates, and the issued bill's immutability — and the allocation
// outcome, which legitimately differs between the first run and the rest, is
// deliberately NOT asserted. An assertion that had to be told which run it was
// on would be a test of the fixture, not of the product.
import { expect, test } from "@playwright/test";

import { signIn, tenant } from "./support/app";
import { skipUnlessAppServer } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";
import { goldenCalc } from "./support/expected";

const GT1 = goldenCalc("GT-1");
const [GT1_USAGE, GT1_SUBTOTAL, GT1_TAX, GT1_TOTAL] = GT1.steps;

// en-US + USD is what MoneyCell renders with (DEFAULT_MONEY_LOCALE) until the
// tenant Regional feed lands. The DIGITS come from B5; only the symbol is here.
function asRendered(figure: string): string {
  return `$${figure}`;
}

function fixtureAccountNo(): string {
  return process.env.E2E_ACCOUNT_NO ?? "E2E-10001";
}

// BR-TEN-043 in a test: the dates a clerk types are PARAMETERS, never a clock
// read, so a run on any day writes the same two dates. They are the fixture
// bill's own month — issued 2026-07-01, due 21 days later (BR-BIL-024) — so the
// payment is on time by POSTING date and clears two days later, which is the
// BR-PAY-021 shape J07 step 3 and every T3M ride describe.
const POSTED_AT = "2026-07-18";
const CLEARED_AT = "2026-07-20";

test.describe("W4 payment write — a clerk records money against the frozen bill", { tag: APP_SERVER_TAG }, () => {
  // SERIAL, and the reason is the subject: the second test asserts what the
  // first one WROTE. Playwright's default is one worker per file but the order
  // is not otherwise guaranteed across a sharded run, and a "does the row
  // render" test that happened to run before the row existed would fail for a
  // reason that has nothing to do with the product. Serial also means a failed
  // write SKIPS the read rather than reporting two defects for one cause.
  test.describe.configure({ mode: "serial" });
  skipUnlessAppServer(test);

  test("records a payment through the real S33 form for GT-1's signed total", async ({ page }) => {
    await signIn(page);

    // A human clicking: sidebar → Payments → the Record payments tab. The page
    // lands on Summary (BR-SHL-001 maps /payments there), so the tab is a real
    // click and not a URL typed.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Payments", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/payments$`));
    await page.getByRole("tab", { name: "Record payments" }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/payments/record$`));

    // `.first()` is the PAGE HEADER's action. The screen legitimately renders a
    // second button with the same label — the empty-state CTA, which a tenant
    // with no payments yet sees under the table (US-PAY-004's A18 §3 empty
    // state) — so a strict locator resolves to two and the header one is the
    // control a clerk with a list in front of them clicks.
    await page.getByRole("button", { name: "Record payment", exact: true }).first().click();
    const form = page.getByRole("dialog");
    await expect(form).toBeVisible();

    // IS-3: the account picker searches SERVER-side and needs two characters.
    // The wait is on the OPTION, not a sleep: the select renders empty until
    // `GET /accounts?q=…` answers, and a picker that never fills is itself the
    // failure (BR-CUS-053's capability row) rather than a slow test.
    // ⚠ **ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`)** — the `#account_query`
    // box and its `#account_id` select are one combobox; the matches are
    // `role="option"` rows in its panel, so the choice is a CLICK.
    await form.locator("#account_id").fill(fixtureAccountNo());
    // `name` is null on the fixture account, so `accountPickerLabel` renders the
    // account number alone — the label a clerk reads.
    await form.getByRole("option", { name: fixtureAccountNo(), exact: true }).click();

    // THE FROZEN FIGURE IS TYPED IN, not asserted out: the clerk is paying the
    // bill finance signed, so the amount comes from B5 at run time.
    await form.locator("#amount").fill(GT1_TOTAL);
    await form.locator("#posted_at").fill(POSTED_AT);
    await form.locator("#cleared_at").fill(CLEARED_AT);
    // BR-PAY-026: the method list is the tenant's own, served with the list
    // response. Whichever methods this tenant has, the second option is a real
    // one — index 0 is the placeholder.
    await form.locator("#method").selectOption({ index: 1 });

    await form.getByRole("button", { name: "Record payment", exact: true }).click();

    // ── the result panel (US-PAY-001 §5) ──────────────────────────────────
    const result = page.locator(".pay-result");
    await expect(result).toBeVisible();
    // "Received" is the first money figure on the panel, and it is the one that
    // is the same on every run: it is what was TAKEN, before allocation.
    await expect(result.locator(".cell-money-amount").first()).toHaveText(asRendered(GT1_TOTAL));
    // The ledger sentence is asserted as PRESENT, not as a particular one: a
    // payment with a clearing date posts, one without does not, and this spec
    // gives a clearing date — but which sentence renders is the SERVER's answer
    // about its own books, and asserting the text would restate a rule this
    // screen only reports (BR-PAY-021).
    await expect(result.locator(".pay-result-ledger")).not.toBeEmpty();
  });

  test("the recorded payment renders on S33 with BOTH BR-PAY-021 dates", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/payments/record`);

    // The row this spec's first test wrote. `.first()` rather than a count:
    // re-running the suite against a stack that was not re-seeded legitimately
    // adds another, and a count assertion would be a claim about how many times
    // someone has run the tests.
    const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() }).first();
    await expect(row).toBeVisible();
    await expect(row.locator(".cell-money-amount").first()).toHaveText(asRendered(GT1_TOTAL));
    // The POSTING date is on the default column set — it is the date billing
    // judges lateness by (BR-PAY-021), so it is the one a clerk sees first.
    await expect(row).toContainText("07/18/2026");
    // The "Applied to" cell is deliberately NOT asserted, and this is the run
    // that proved why: a first run against a fresh fixture renders the bill
    // number (`BL-2606-000001`), and the second run's payment — which meets a
    // bill already settled — renders "Met no bill" and sorts ABOVE it on the
    // default posting-date-desc order. Both are correct product behaviour, so an
    // assertion on that cell would be an assertion about how many times the
    // suite has been run. Verbatim from the run that caught it:
    //   Expected substring: "BL-"
    //   Received string:    "PY-260718-0002…Met no bill$108.88Cleared"

    // ── the CLEARING date takes a click, and that is the finding ──────────
    // BR-PAY-021 is this module's cardinal rule and the screen's own docstring
    // says "both collected, both columns" — but `cleared_at` ships
    // `defaultVisible: false` (the IS-5 available set), so the S33 ledger opens
    // showing ONE of the two dates. That is a deliberate design choice and not
    // a defect; it is asserted HERE, by driving the column chooser exactly as a
    // clerk would, because a spec that quietly asserted only the visible date
    // would have hidden the fact that the other one takes a click to see.
    // Reported to the PO batch, 2026-08-11, rather than changed from this lane.
    await page.getByRole("group").filter({ hasText: "⋮" }).first().click();
    await page.getByRole("checkbox", { name: "Cleared", exact: true }).check();
    await expect(row).toContainText("07/20/2026");
  });

  test("the issued bill is not restated by the money that met it", async ({ page }) => {
    // Hard rule 4 / BR-BIL-004, read from the BROWSER. The immutability trigger
    // is proved on a live Postgres by the billing suite; what no database test
    // can see is what the SCREEN shows afterwards. A bill whose rendered total
    // changed when a payment arrived would be the same defect class as a
    // restated invoice, and would be invisible to every check in this repo.
    await signIn(page);
    await page.goto(`/${tenant()}/billing`);

    const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() });
    await row.getByRole("link").first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/bills/`));
    await page.getByRole("tab", { name: "Charges" }).click();

    const lines = page.locator("table.met-table").filter({ has: page.locator("tfoot") });
    const usageRow = lines.getByRole("row").filter({ hasText: "electric usage" });
    await expect(usageRow.locator(".cell-money-amount").last()).toHaveText(asRendered(GT1_USAGE));

    const footer = lines.locator("tfoot tr");
    await expect(footer.nth(0).locator(".cell-money-amount")).toHaveText(asRendered(GT1_SUBTOTAL));
    await expect(footer.nth(1).locator(".cell-money-amount")).toHaveText(asRendered(GT1_TAX));
    await expect(footer.nth(2).locator(".cell-money-amount")).toHaveText(asRendered(GT1_TOTAL));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking")
// generated: 2026-08-11 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e`✔ · tsc --noEmit✔ · `npm run lint`✔ (BUT it
//   lints `src` only, so it does not cover this file — stated, not claimed) ·
//   vitest✔ · vite build✔ · run_gates✔ · playwright against the live stack —
//   counts in the lane report
// red-proof (law 7): the amount TYPED INTO THE FORM was mutated from GT-1's
//   frozen total to one cent less (`fill("108.87")`) and the suite re-run
//   against the live stack. Verbatim:
//     Error: expect(locator).toHaveText(expected) failed
//     Locator:  locator('.pay-result').locator('.cell-money-amount').first()
//     Expected: "$108.88"
//     Received: "$108.87"
//   The panel rendered exactly what the server took, which is what proves the
//   assertion reads the RENDERED write and not a constant. Reverted; green
//   (3 passed). The mutation left a real $108.87 payment in the fixture
//   database — append-only per hard rule 4, so it is NOT deleted, and the S33
//   assertions use `.first()` precisely because such rows accumulate.
//   A second red was found rather than staged, and is quoted at its assertion:
//   the "Applied to" cell reads `BL-2606-000001` on a first run and "Met no
//   bill" on later ones.
// exceptions: (1) NOT a catalog journey — see the header for why J07 and
//   T3M-001 both stay unactivated · (2) the ALLOCATION outcome (applied vs
//   carried-as-credit) is deliberately unasserted: it differs legitimately
//   between the first run against a fresh fixture and later ones · (3) the
//   payment METHOD is picked by index, not by name: BR-PAY-026 makes the list
//   the tenant's own and naming one here would hard-code a fixture's reference
//   data · (4) the two dates are asserted in MM/DD/YYYY because that is the
//   seeded tenant's Regional format; a tenant on another format renders another
//   string, which is the ONE formatter working (BR-SHL-034)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
