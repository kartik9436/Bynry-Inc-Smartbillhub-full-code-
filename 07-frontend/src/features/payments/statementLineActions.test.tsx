// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10694 (lockbox audit LBX-05) — G3 ruled 2026-10-30
// ───────────────────────────────────────────────────────
// The tester's statement on the two screens it reaches: the import review's
// FIX column offers both actions on a money-out line and says In the books /
// Recorded on an explained one; the reconciliation statement lists the lines
// that are now in the books.
import { MemoryRouter } from "react-router-dom";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  ReconciliationStatement,
  StatementLineRow,
  StatementReview,
} from "@/api/bankRecEndpoints";

import { StatementReviewTable } from "./BankImportWizard";
import { PostedLinesTable } from "./ReconciliationStatementPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function line(over: Partial<StatementLineRow>): StatementLineRow {
  return {
    bank_line_id: "l1",
    posted_on: "2026-10-29",
    reference: "RET1029-01",
    amount: "-76.400000",
    currency: "USD",
    line_no: 2,
    batch_id: null,
    batch_code: null,
    recorded_total: null,
    difference: null,
    state: "needs_a_look",
    actions: ["match_return", "bank_fee"],
    ...over,
  };
}

function review(rows: StatementLineRow[]): StatementReview {
  return {
    rows,
    tiles: {},
    open_batches: [],
    currency: "USD",
    unavailable: [],
  } as unknown as StatementReview;
}

function table(rows: StatementLineRow[], withActions = true): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <StatementReviewTable
        review={review(rows)}
        t={t}
        batchPath={(id) => `/x/${id}`}
        onPair={() => undefined}
        onLineAction={withActions ? () => undefined : undefined}
      />
    </MemoryRouter>,
  );
}

describe("LBX-05 · a line the bank took out", () => {
  it("offers Match to payment and Bank fee on a money-out line", () => {
    const html = table([line({})]);
    expect(html).toContain(t("payments.deposits.lines.matchReturn"));
    expect(html).toContain(t("payments.deposits.lines.bankFee"));
    expect(html).toContain(t("payments.deposits.match.needs_a_look"));
  });

  it("offers neither on a credit, nor when no handler is wired", () => {
    const credit = table([line({ amount: "12.400000", actions: [] })]);
    expect(credit).not.toContain(t("payments.deposits.lines.matchReturn"));
    const readOnly = table([line({})], false);
    expect(readOnly).not.toContain(t("payments.deposits.lines.matchReturn"));
  });

  it("says In the books for a posted line and Recorded for an ordinary explanation", () => {
    const posted = table([line({ state: "explained", posted: true, actions: [] })]);
    expect(posted).toContain(t("payments.deposits.lines.inTheBooks"));
    expect(posted).toContain(t("payments.deposits.match.explained"));
    const recorded = table([line({ state: "explained", posted: false, actions: [] })]);
    expect(recorded).toContain(t("payments.deposits.lines.recorded"));
  });

  it("the reconciliation statement lists the lines in the books", () => {
    const body = {
      currency: "USD",
      posted_lines: {
        amount: "-254.400000",
        count: 3,
        rows: [
          { bank_line_id: "a", line_no: 2, posted_on: "2026-10-29", reference: "RET1029-01", amount: "-76.400000", kind: "returned_item", payment_no: "PMT-1", cheque: "4102" },
          { bank_line_id: "b", line_no: 3, posted_on: "2026-10-29", reference: "RET1029-02", amount: "-154.000000", kind: "returned_item", payment_no: "PMT-2", cheque: "4103" },
          { bank_line_id: "c", line_no: 4, posted_on: "2026-10-31", reference: "FEE1031", amount: "-24.000000", kind: "bank_fee", payment_no: null, cheque: null },
        ],
      },
    } as unknown as ReconciliationStatement;
    const html = renderToStaticMarkup(<PostedLinesTable body={body} t={t} />);
    for (const text of ["RET1029-01", "RET1029-02", "FEE1031", "4102", "4103"]) {
      expect(html).toContain(text);
    }
    expect(html).toContain(t("payments.deposits.lines.kindReturned"));
    expect(html).toContain(t("payments.deposits.lines.bankFee"));
  });
});
