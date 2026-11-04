// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-38 · task 25 — a goodwill concession appears on the
//           account as a credit, and the chase says why it is smaller than the
//           bill. CS-38's own words: *"the concession appears on the Payments
//           tab as a signed credit row, described as a concession and not as
//           money received"*, and *"of everything in this document this is the
//           one where the customer has been told something in writing that the
//           system then contradicts."*
// Story:    US-PAY-004 (S33 · S21 Payments tab) · US-PAY-013 (S34)
//           Screens: S21 · S33 · S34
// Rules:    B2 O-4 (whether a credit's sign lives on `amount` is UNRESOLVED and
//           stays that way) · BR-PAY-041 (a negative credit position is a real
//           debt and is not floored) · BR-SHL-023 (one money path) · B14 rule
//           32 (a description budget — nothing is drawn on a row that has no
//           credit) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
// ❄️ **GT-6's FIGURES, UNMOVED AND NOW REACHED ON A SCREEN.** The frozen case is
// a **25.00** concession on a **247.30** bill leaving the customer owing
// **222.30**. Task 24 proved all three where the money is worked out; task 26's
// row says in as many words that what did not exist was *"any test that renders
// 222.30"*. These are those.
import { cleanup } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { OutstandingRow, PaymentRow } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import { CreditApplied, isZeroDecimal } from "./OutstandingsTab";
import { paymentsCells } from "./PaymentsPage";

const t: Translator = (key, params) => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function debtor(over: Partial<OutstandingRow> = {}): OutstandingRow {
  return {
    account_id: "acc-1",
    account_no: "A-10802",
    customer_name: "Ajinkya Kulkarni",
    // ❄️ GT-6: 247.30 billed, 25.00 conceded, 222.30 chased.
    balance: "222.3000",
    days_late: 6,
    bucket: "current",
    open_bills: 1,
    last_payment_on: null,
    notice_summary: null,
    collection_tier: null,
    next_step_due: null,
    plan_status: null,
    autopay: false,
    bad_address: false,
    gross_balance: "247.3000",
    credit_applied: "25.0000",
    ...over,
  };
}

function creditLine(over: Partial<OutstandingRow> = {}): string {
  return renderToStaticMarkup(
    <CreditApplied row={debtor(over)} currency="USD" t={t} />,
  );
}

function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-1",
    payment_no: "PMT-000412",
    account_id: "acc-1",
    account_no: "A-10802",
    customer_name: "Ajinkya Kulkarni",
    type: "credit",
    method: null,
    method_name: null,
    confirmation: null,
    memo: "Goodwill — outage on 14 Aug",
    amount: "25.0000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-08-20T00:00:00Z",
    cleared_at: "2026-08-20T00:00:00Z",
    applied_to: [],
    applied_total: "0.0000",
    deposit_batch_id: null,
    receipt_no: null,
    // CR-059 CS-30 · CS-32 — a cheque's own state and the move marks.
    // Null on an ordinary payment, which is a STATE and not a missing value.
    cheque_date: null,
    drawer_bank: null,
    bankable_from: null,
    moved_from_payment_no: null,
    moved_from_account_no: null,
    moved_to_payment_no: null,
    moved_to_account_no: null,
    // `CR-135` `P1.9` — the blueprint's §03 2·1 Source and Batch.
    origin: "entry",
    batch_ref: null,
    batch_kind: null,
    ...over,
  };
}

function amountCell(row: PaymentRow): string {
  const cells = paymentsCells(t, (path) => path, "UTC", "MM/DD/YYYY");
  return renderToStaticMarkup(<>{cells.amount(row)}</>);
}

afterEach(cleanup);

describe("CS-38 · the chase says WHY it is not the bill total", () => {
  it("222.30 is shown beside the 247.30 the bills say and the 25.00 that came off", () => {
    // Before this line the row read 222.30 and a clerk could not tell it from a
    // bill of 222.30 — while a letter had gone out telling the customer about
    // the 25.00.
    const html = creditLine();
    expect(html).toContain("25.00");
    expect(html).toContain("247.30");
    expect(html).toContain(escaped(t("payments.outstandings.creditApplied")));
    expect(html).toContain(escaped(t("payments.outstandings.billsSay")));
  });

  it("draws NOTHING on a row that holds no credit — which is nearly all of them", () => {
    // B14 rule 32's budget. A second figure under every balance would be noise
    // on the screen a clerk scans fastest.
    expect(creditLine({ credit_applied: "0.0000", gross_balance: "222.3000" })).toBe("");
  });

  it("draws nothing when the read could not state what the bills alone said", () => {
    // `gross_balance` null is not `balance`. Echoing the net back into this
    // line would invent the gross from the net, which is DEF-127's shape.
    expect(creditLine({ gross_balance: null })).toBe("");
    // …and a deployment whose read predates the change sends neither field.
    expect(creditLine({ gross_balance: undefined, credit_applied: undefined })).toBe("");
  });

  it("isZeroDecimal reads the STRING and never a float", () => {
    expect(isZeroDecimal("0.0000")).toBe(true);
    expect(isZeroDecimal("0")).toBe(true);
    expect(isZeroDecimal("25.0000")).toBe(false);
    // A credit smaller than a cent is still a credit, and a float comparison is
    // the shape of every money defect this repository has logged.
    expect(isZeroDecimal("0.0001")).toBe(false);
  });
});

describe("CS-38 · a concession is described as one, not as money received", () => {
  it("the credit row says so under its figure", () => {
    const html = amountCell(payment());
    expect(html).toContain("25.00");
    expect(html).toContain(escaped(t("payments.row.notMoneyReceived")));
  });

  it("an adjustment says the same thing", () => {
    expect(amountCell(payment({ type: "adjustment" }))).toContain(
      escaped(t("payments.row.notMoneyReceived")),
    );
  });

  it("a real payment says NOTHING extra — the sentence marks the exception", () => {
    const html = amountCell(payment({ type: "payment", amount: "100.0000" }));
    expect(html).toContain("100.00");
    expect(html).not.toContain(escaped(t("payments.row.notMoneyReceived")));
  });

  it("B2 O-4 — no sign is written on the credit, because none is ruled", () => {
    // Whether a credit's sign lives on `amount` is B2's own unresolved residue.
    // A minus drawn here would be this screen answering an open question on a
    // money figure; the SENTENCE says what the row is and needs no sign.
    const html = amountCell(payment());
    expect(html).not.toContain("-25.00");
    expect(html).not.toContain("−25.00");
    expect(html).not.toContain("(25.00)");
  });
});
