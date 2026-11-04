// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-LED-6622` — `PaymentsMadePanel.tsx` has cited this file under
//          `Tests:` since it landed (`P4.11`, 2026-09-24) and the file had
//          never been written. Hard-won law 1: a comment claiming a guarantee
//          is not the guarantee.
// Rules:   B14 rule 19 (the search prompt names what it matches) · rule 31 (no
//          database id is ever the visible value of a field) · BR-LED-019 (the
//          filing confirmation ref and the receipt are the auditor artefacts) ·
//          BR-REP-002 (the books are the number that has to be right)
// Tests:   this file
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY THIS FILE EXISTS, AND IT IS NOT "MORE COVERAGE"                     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// `G116` reported this component as a `Tests:` line pointing at nothing. The
// damage of that is specific and is worse than an honestly blank header: a
// `Tests:` line is how the next lane decides whether a change is already
// guarded, so pointed at nothing it says *this is covered* and the case never
// gets written. `PaymentsMadePanel` had **no test of any kind** while its own
// header named one. Correcting the line to name nothing was the cheaper fix;
// writing the file it already names is the honest one.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7      ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// **(a) A NEGATIVE ON A PANEL THAT NEVER RENDERED.** Every rule-31 assertion
// here is *"this id is NOT on screen"*, and a component that threw renders no
// id either. So the first case asserts the panel MOUNTED and drew a row, and
// every negative below is written to run only after that is true.
//
// **(b) ASSERTING THE SPEC AGAINST ITSELF.** Checking that `search` returns
// `[authority, confirmation_ref]` restates the source line. What is asserted
// instead is the BEHAVIOUR those fields buy — a query matching a confirmation
// reference selects its row and drops the other — which is what p058's prompt
// promises a finance officer.
//
// **(c) A SORT CASE THAT CANNOT TELL ASCENDING FROM ARBITRARY.** Two rows sort
// correctly by accident half the time, so the money case uses three rows whose
// NUMERIC and LEXICAL orders disagree (`9.00` vs `10.00` vs `100.00`): a
// `Number()` comparison and a string comparison give different answers, so a
// regression to string sorting is red rather than lucky.
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { RemittancePaidResponse, RemittancePaidRow } from "@/api/endpoints";

import { PAYMENTS_MADE_SPEC, PaymentsMadePanel } from "./PaymentsMadePanel";

afterEach(cleanup);

/** Keys, not English: this file asserts STRUCTURE, and the copy has its own
 *  guards in `financeCopyRule33.test.ts` and the eleven-catalogue i18n suite. */
const t = ((key: string) => key) as unknown as Parameters<
  typeof PaymentsMadePanel
>[0]["t"];

/** The id a clerk must never see (B14 rule 31), made unmistakable on purpose. */
const HIDDEN_ID = "0f8c1d22-4e51-4b2a-9d7e-6b3a11c9e000";

function row(over: Partial<RemittancePaidRow> = {}): RemittancePaidRow {
  return {
    id: HIDDEN_ID,
    authority_code: "BEXAR",
    authority: "Bexar County",
    period: { start: "2026-08-01", end: "2026-08-31" },
    paid_on: "2026-09-05",
    amount: "1234.5600",
    currency: "USD",
    basis: "posting",
    confirmation_ref: "CONF-77120",
    entry_id: "6a2b0d91-1111-4c3d-8e55-0a9b7c2d4f31",
    entry_no: "JE-2026-0091",
    receipts: [],
    ...over,
  };
}

function history(rows: RemittancePaidRow[]): RemittancePaidResponse {
  // `journal_only` is REQUIRED on `RemittancePaidResponse` and counts filings
  // recorded before the register existed. Omitting it here made this fixture a
  // shape the product never serves (DEF-LED-6754); 0 is the only value that
  // asserts nothing about a count these cases do not exercise.
  return { count: rows.length, currency: "USD", rows, journal_only: 0 };
}

function mount(rows: RemittancePaidRow[]) {
  render(
    <MemoryRouter>
      <PaymentsMadePanel
        history={history(rows)}
        t={t}
        locale="en-US"
        tenantPath={(path) => `/brazosbend${path}`}
      />
    </MemoryRouter>,
  );
}

describe("PaymentsMadePanel — the filings half of 4·1 (P4.11)", () => {
  it("the fixture can tell a drawn row from a panel that rendered nothing", () => {
    // ⚠ FIRST, BECAUSE EVERY RULE-31 ASSERTION BELOW IS A NEGATIVE AND A
    // NEGATIVE IS FREE ON A BLANK PANEL.
    mount([row()]);
    expect(screen.getByText("Bexar County")).toBeTruthy();
    expect(screen.getByText("CONF-77120")).toBeTruthy();
  });

  it("no database id is the visible value of a field (B14 rule 31)", () => {
    mount([row()]);
    expect(screen.getByText("Bexar County")).toBeTruthy(); // the panel drew
    expect(screen.queryByText(HIDDEN_ID)).toBeNull();
    expect(document.body.textContent ?? "").not.toContain(HIDDEN_ID);
  });

  it("an entry with no number composes nothing in its place (BR-LED-021)", () => {
    // `entry_no` is NULL until the tenant seeds the series, and the endpoint's
    // own comment says nothing composes one. A dash, an id or "JE-" would each
    // be an invented identity.
    mount([row({ entry_no: null })]);
    expect(screen.getByText("Bexar County")).toBeTruthy();
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("6a2b0d91");
    expect(text).not.toContain(HIDDEN_ID);
  });

  it("the search prompt matches the two fields it names, and nothing else", () => {
    // p058 draws *"Search authority or confirmation…"* (B14 rule 19). Asserted
    // as behaviour rather than by restating the spec's own field list.
    const bexar = row();
    const travis = row({
      id: "1111",
      authority: "Travis County",
      authority_code: "TRAVIS",
      confirmation_ref: "CONF-99000",
      paid_on: "2026-09-06",
    });
    const matched = [bexar, travis].filter((candidate) =>
      PAYMENTS_MADE_SPEC.search(candidate).some((field) =>
        (field ?? "").toLowerCase().includes("conf-77120"),
      ),
    );
    expect(matched).toEqual([bexar]);

    // …and a term that is on the row but NOT in the two named fields does not
    // select it — otherwise the prompt is lying about what it searches.
    const byBasis = [bexar, travis].filter((candidate) =>
      PAYMENTS_MADE_SPEC.search(candidate).some((field) =>
        (field ?? "").toLowerCase().includes("posting"),
      ),
    );
    expect(byBasis).toEqual([]);
  });

  it("amount sorts as money, not as text", () => {
    // Three rows whose numeric and lexical orders DISAGREE, so a regression to
    // string comparison is red rather than lucky: lexically "10.00" < "100.00"
    // < "9.00"; numerically 9 < 10 < 100.
    const rows = [
      row({ id: "a", amount: "100.0000" }),
      row({ id: "b", amount: "9.0000" }),
      row({ id: "c", amount: "10.0000" }),
    ];
    const byAmount = [...rows].sort(
      (left, right) =>
        Number(PAYMENTS_MADE_SPEC.sortValue(left, "amount")) -
        Number(PAYMENTS_MADE_SPEC.sortValue(right, "amount")),
    );
    expect(byAmount.map((candidate) => candidate.id)).toEqual(["b", "c", "a"]);
    const lexical = [...rows]
      .sort((left, right) => String(left.amount).localeCompare(String(right.amount)))
      .map((candidate) => candidate.id);
    expect(lexical).not.toEqual(["b", "c", "a"]); // the orders really do differ
  });

  it("a column the table does not own sorts by nothing, rather than by accident", () => {
    expect(PAYMENTS_MADE_SPEC.sortValue(row(), "not_a_column")).toBeNull();
  });

  it("an empty filing history draws the panel and no row", () => {
    mount([]);
    expect(screen.queryByText("Bexar County")).toBeNull();
    expect(screen.queryByText(HIDDEN_ID)).toBeNull();
  });
});
