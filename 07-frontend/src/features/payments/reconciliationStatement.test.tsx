// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · wave W8 · task 48 (P8) — the reconciliation statement.
//           CS-14 · CS-16 · CS-17 · CS-18.
// Story:    US-PAY-020 (S37) · US-PAY-022 (S40)   Screens: S37 · S40
// Rules:    PO ruling 2026-09-02 (`OQ-1310` closed) — the statement states two
//           facts and explains the gap; it adjusts neither side · BR-SHL-020
//           (an absence is SAID) · BR-SHL-023 (one money path) · B14 rule 31
//           (no database id is the visible value of a field) · rule 32 (a
//           stated absence is a `<details>` CLOSED by default) ·
//           CLAUDE.md rule 2 (money is a decimal string, never a number)
// ───────────────────────────────────────────────────────
// ⚠ **THESE ASSERT RENDERED MARKUP, NOT PROPS.** No gate in this repository
// reads rendered output — that is the sentence B14's own status table uses
// about itself — so a test that checked the component received the right
// object would pass over a screen that printed none of it.
//
// The figures are CS-14's own, from the change request and from
// `bankrec_read.reconciliation_statement`'s docstring, and not one of them is
// computed here: bank **48,112.40**, books **46,946.12**, and the
// **1,166.28** between them explained by **1,122.78 − 44.50 + 88.00**.
import { cleanup } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  DifferenceReport,
  ReconcilingItem,
  ReconciliationStatement,
} from "@/api/bankRecEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  DifferencesTable,
  ReconcilingItemsTable,
  StatementAbsence,
  TieOut,
  UnexplainedTable,
  itemOf,
  residualOf,
  scaledToDecimal,
} from "./ReconciliationStatementPage";

const t: Translator = (key, params) => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

const IN_TRANSIT: ReconcilingItem = {
  code: "deposits_in_transit",
  amount: "1122.780000",
  count: 2,
  as_of: "2026-08-31",
  oldest_age_days: 4,
  rows: [
    {
      id: "b-1",
      code: "DEP-260828-CHK",
      deposited_on: "2026-08-27",
      amount: "1000.000000",
      age_days: 4,
    },
    {
      id: "b-2",
      code: "DEP-260829-ACH",
      deposited_on: "2026-08-29",
      amount: "122.780000",
      age_days: 2,
    },
  ],
};

const REFUNDS: ReconcilingItem = {
  code: "outstanding_refunds",
  amount: "44.500000",
  count: 1,
  as_of: "2026-08-31",
  oldest_age_days: 20,
  rows: [
    { id: "r-1", reference: "CHQ-4021", issued_on: "2026-08-11", amount: "44.500000", age_days: 20 },
  ],
};

const UNEXPLAINED: ReconcilingItem = {
  code: "unexplained_lines",
  amount: "88.000000",
  count: 1,
  as_of: "2026-08-31",
  oldest_age_days: 9,
  rows: [
    {
      bank_line_id: "0f2c5b1e-0000-4000-8000-000000000001",
      line_no: 17,
      posted_on: "2026-08-22",
      reference: "ACH CREDIT PARKS DEPT",
      amount: "88.000000",
      age_days: 9,
    },
  ],
};

function statement(over: Partial<ReconciliationStatement> = {}): ReconciliationStatement {
  return {
    statement: {
      id: "s-1",
      bank_account_name: "Operating",
      bank_account_mask: "1234",
      period_start: "2026-08-01",
      period_end: "2026-08-31",
      opening_balance: "40000.000000",
      closing_balance: "48112.400000",
    },
    reconciling_items: [IN_TRANSIT, REFUNDS, UNEXPLAINED],
    explained_not_posted: { amount: "0.000000", count: 0 },
    bank_closing_balance: "48112.400000",
    book_cash_balance: "46946.120000",
    difference_bank_less_books: "1166.280000",
    bank_equals_books: false,
    currency: "USD",
    unavailable: [],
    ...over,
  };
}

function tieOutHtml(over: Partial<ReconciliationStatement> = {}): string {
  return renderToStaticMarkup(<TieOut body={statement(over)} t={t} />);
}

afterEach(cleanup);

describe("CS-14 · the tie-out states two facts and explains the gap", () => {
  it("prints the bank's figure, the books' figure and the difference between them", () => {
    const html = tieOutHtml();
    expect(html).toContain("48,112.40");
    expect(html).toContain("46,946.12");
    expect(html).toContain("1,166.28");
  });

  it("says the listed items account for the whole difference when they do", () => {
    // 1,122.78 − 44.50 + 88.00 = 1,166.28, which is the difference exactly.
    expect(residualOf(statement())).toBe(0n);
    expect(tieOutHtml()).toContain(escaped(t("payments.deposits.statement.explains")));
  });

  it("NAMES what the items do not account for, with its figure", () => {
    // ⚠ THE ASSERTION THIS SCREEN EXISTS FOR. The unexplained lines fall from
    // 88.00 to 22.00 while the difference stays at 1,166.28, so 66.00 of it is
    // now accounted for by nothing. A screen that let a person leave that
    // unexplained would be a report, not a reconciliation.
    const body = statement({
      reconciling_items: [
        IN_TRANSIT,
        REFUNDS,
        { ...UNEXPLAINED, amount: "22.000000" },
      ],
    });
    expect(residualOf(body)).toBe(66_000000n);
    const html = renderToStaticMarkup(<TieOut body={body} t={t} />);
    expect(html).toContain("66.00");
    expect(html).toContain(escaped(t("payments.deposits.statement.residualLabel")));
    // …and it must NOT claim the items explain it.
    expect(html).not.toContain(escaped(t("payments.deposits.statement.explains")));
  });

  it("UNKNOWN IS NOT ZERO — a statement with no bank balance says so", () => {
    // Every statement imported before 2026-09-01 carries no balances and
    // nothing backfills them. "We could not do the sum" and "the two agree"
    // are different answers (DEF-127).
    const body = statement({
      bank_closing_balance: null,
      difference_bank_less_books: null,
      bank_equals_books: null,
    });
    expect(residualOf(body)).toBeNull();
    const html = renderToStaticMarkup(<TieOut body={body} t={t} />);
    expect(html).toContain(escaped(t("payments.deposits.statement.cannotCheck")));
    expect(html).toContain(escaped(t("payments.deposits.statement.bankUnknown")));
    expect(html).not.toContain(escaped(t("payments.deposits.statement.agree")));
  });

  it("a chart with no designated cash account leaves the books' side unknown", () => {
    const html = tieOutHtml({
      book_cash_balance: null,
      difference_bank_less_books: null,
      bank_equals_books: null,
    });
    expect(html).toContain(escaped(t("payments.deposits.statement.booksUnknown")));
  });

  it("says the two agree when they are the same number", () => {
    const html = tieOutHtml({
      book_cash_balance: "48112.400000",
      difference_bank_less_books: "0.000000",
      bank_equals_books: true,
    });
    expect(html).toContain(escaped(t("payments.deposits.statement.agree")));
  });

  it("never prints the words 'not reconciled' over legitimate deposits in transit", () => {
    // `bank_equals_books` is a FACT and not a verdict: a properly reconciled
    // period with money still in transit reads false, and a screen that
    // labelled it "not reconciled" would accuse a clerk of a problem they do
    // not have (PO ruling 2026-09-02).
    expect(tieOutHtml().toLowerCase()).not.toContain("not reconciled");
  });
});

describe("scaledToDecimal · exact, and never a float", () => {
  it("puts the point back where the six-decimal grid says it is", () => {
    expect(scaledToDecimal(66_000000n)).toBe("66.000000");
    expect(scaledToDecimal(-147_500000n)).toBe("-147.500000");
    // A residual smaller than a cent is still a residual, and rounding it away
    // here would report a statement as fully explained when it is not.
    expect(scaledToDecimal(1n)).toBe("0.000001");
  });
});

describe("CS-14 · the reconciling items are listed, aged and unsigned", () => {
  it("names each item in words and carries its count and its oldest age", () => {
    const html = renderToStaticMarkup(
      <ReconcilingItemsTable body={statement()} t={t} />,
    );
    expect(html).toContain(escaped(t("payments.deposits.statement.item.deposits_in_transit")));
    expect(html).toContain(escaped(t("payments.deposits.statement.item.outstanding_refunds")));
    expect(html).toContain(escaped(t("payments.deposits.statement.item.unexplained_lines")));
    expect(html).toContain("1,122.78");
    expect(html).toContain(escaped(t("payments.deposits.statement.days", { count: 20 })));
  });

  it("prints no item with a sign — they explain the difference, they do not move it", () => {
    // The server deleted `sign` and `signed_amount` on 2026-09-02 so that no
    // screen could render an item as an addend to a balance. A minus in this
    // table would put them back.
    const html = renderToStaticMarkup(
      <ReconcilingItemsTable body={statement()} t={t} />,
    );
    expect(html).not.toContain("-44.50");
    expect(html).not.toContain("−44.50");
  });
});

describe("CS-16 · a line nobody has explained is actionable, and named", () => {
  function unexplainedHtml(item: ReconcilingItem | undefined): string {
    return renderToStaticMarkup(
      <UnexplainedTable
        item={item}
        currency="USD"
        t={t}
        timeZone="UTC"
        dateFormat="MM/DD/YYYY"
        selected={[]}
        onToggle={() => undefined}
        onExplain={() => undefined}
        onMatchSeveral={() => undefined}
      />,
    );
  }

  it("offers an Explain control on the row", () => {
    expect(unexplainedHtml(UNEXPLAINED)).toContain(
      escaped(t("payments.deposits.statement.explain")),
    );
  });

  it("DEF-PAY-10780 — a credit line also offers + Match to several deposits", () => {
    expect(unexplainedHtml(UNEXPLAINED)).toContain(escaped(t("payments.deposits.several.open")));
  });

  it("B14 rule 31 — the row is named by the bank's own reference, never by an id", () => {
    const html = unexplainedHtml(UNEXPLAINED);
    expect(html).toContain("ACH CREDIT PARKS DEPT");
    expect(html).not.toContain("0f2c5b1e-0000-4000-8000-000000000001");
  });

  it("says every line is accounted for rather than drawing an empty table", () => {
    const html = unexplainedHtml({ ...UNEXPLAINED, count: 0, rows: [] });
    expect(html).toContain(escaped(t("payments.deposits.statement.unexplainedNone")));
  });
});

describe("CS-18 · differences by reason name the account, never its id", () => {
  const report: DifferenceReport = {
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    rows: [
      {
        reason_code: "processor_fee",
        gl_account_id: "9c1d0000-0000-4000-8000-00000000abcd",
        gl_account_code: "6800",
        gl_account_name: "Bank fees",
        total: "-30.000000",
        count: 2,
        batch_count: 2,
        line_count: 0,
        posted_count: 2,
      },
    ],
    total: "-30.000000",
    resolution_count: 2,
    currency: "USD",
    unavailable: [],
    reasons: [
      {
        code: "processor_fee",
        name: "Card processor fee",
        default_gl_account_id: null,
        is_system: true,
      },
    ],
  };

  it("renders the chart's code and name and not the account id", () => {
    const html = renderToStaticMarkup(<DifferencesTable report={report} t={t} />);
    expect(html).toContain("6800 Bank fees");
    expect(html).not.toContain("9c1d0000-0000-4000-8000-00000000abcd");
  });

  it("keeps the sign — a fee the bank took is negative and is not made positive", () => {
    const html = renderToStaticMarkup(<DifferencesTable report={report} t={t} />);
    expect(html).toContain("30.00");
    expect(html).toContain(escaped("Card processor fee"));
  });

  it("says nothing was explained rather than drawing an empty table", () => {
    const html = renderToStaticMarkup(
      <DifferencesTable report={{ ...report, rows: [] }} t={t} />,
    );
    expect(html).toContain(escaped(t("payments.deposits.statement.differencesNone")));
  });
});

describe("B14 rule 32 · the stated absence is a <details> CLOSED by default", () => {
  it("renders closed, carries the row that will kill it, and shows no id to a clerk", () => {
    const html = renderToStaticMarkup(
      <StatementAbsence
        summary={t("payments.deposits.statement.notPosted")}
        message={t("payments.deposits.statement.notPostedBody")}
        tracks="OQ-1310"
      />,
    );
    expect(html).toContain('<details data-tracks="OQ-1310"');
    // `<details open>` renders the same summary and the same body, so the
    // assertion that matters is the one about the attribute.
    expect(html).not.toContain('<details data-tracks="OQ-1310" open');
    // DEF-332 / B14 rule 31 — the id is on the ELEMENT, never in the sentence.
    expect(html).not.toContain(">OQ-1310<");
  });
});

describe("itemOf · an item the server did not send is undefined, never zero", () => {
  it("returns undefined for a code that is not on the body", () => {
    expect(itemOf(statement({ reconciling_items: [] }), "unexplained_lines")).toBeUndefined();
    // …and the residual is then unanswerable rather than reading as explained.
    expect(residualOf(statement({ reconciling_items: [] }))).toBeNull();
  });
});
