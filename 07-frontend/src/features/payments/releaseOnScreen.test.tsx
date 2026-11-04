// ── Trace ──────────────────────────────────────────────
// Change:  CR-059 · CS-36 · task 20 — the screens for the release the backend
//          landed on 2026-09-01: S21 and S33 showing a release AS A RELEASE,
//          and S30's settlement panel on the correction preview.
// Story:   US-PAY-004 (the S33 ledger) · US-BIL-015 (the correction preview)
//          Screens: S33 · S21 (the same table, scoped) · S30
// Rules:   BR-PAY-1072 (the release is an append-only NEGATIVE mirror row hung
//          off the payment — never an edit) · BR-PAY-1073 (it posts no journal
//          line) · BR-PAY-013 (a bounce hangs its negatives off the REVERSING
//          payment) · BR-BIL-044 (nine preview sections, none collapsible) ·
//          BR-SHL-020 r2 (the server sends codes; the UI renders language) ·
//          B14 rule 31 (no rule id in clerk-facing copy) · rule 33 (a fact is
//          six words)
// ───────────────────────────────────────────────────────
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE FIGURES WERE ALREADY RIGHT. WHAT WAS MISSING WAS THE WORD.          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// When a paid bill is corrected, the payment's application to it comes off as an
// append-only NEGATIVE mirror row against the SAME bill. On screen that read as
// the bill listed TWICE against one payment — the amount, and the same amount
// back off it — with the applied total at 0.00 and nothing saying why. A clerk
// looking at Ajinkya's 100.00 saw `BL-2608-0141` and `BL-2608-0141`.
//
// **RED PROVED FIRST (hard-won law 7)**, against the pre-fix cell:
//
//     × one line per bill, and a released bill says so
//       → expected [ 'BL-2608-0141', 'BL-2608-0141' ] to have a length of 1
//     × the release names WHY the money came back off
//       → expected '…BL-2608-0141BL-2608-0141…' to contain 'this bill was corrected'
//
// and, on the S30 panel before `settlement_preview` existed:
//
//     × the settlement panel states the four figures
//       → Unable to find an element with the text: Replacement takes
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentRow } from "@/api/endpoints";
import { ExistingBills } from "@/features/billing/fixABill/CheckStep";
import { PREVIEW_ONE } from "@/features/billing/fixABill/__fixtures__/fixABillFixtures";

import { paymentsCells } from "./PaymentsPage";
import { appliedBills, releasedByCorrection } from "./paymentsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const CELLS = paymentsCells(t, (p) => p, "UTC", "MM/DD/YYYY");

/**
 * CS-36's own case, as `GET /payments` serves it after the correction ran.
 *
 * Ajinkya paid **100.00** for a 100.00 bill on 15 Aug. On 28 Aug the read turned
 * out to be wrong, the bill was corrected to 80.00, and the release wrote ONE
 * negative mirror row against `BL-2608-0141` — hung off THIS payment, whose own
 * amount stays positive. Both rows are real and both stand forever.
 */
function releasedPayment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-0141",
    payment_no: "PMT-000318",
    account_id: "acc-1042",
    account_no: "ACC-1042",
    customer_name: "Ajinkya Patil",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: null,
    memo: null,
    amount: "100.000000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-08-15",
    cleared_at: "2026-08-17",
    applied_to: [
      { invoice_id: "inv-0141", invoice_number: "BL-2608-0141", amount: "100.000000" },
      { invoice_id: "inv-0141", invoice_number: "BL-2608-0141", amount: "-100.000000" },
    ],
    applied_total: "0.000000",
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

/** The REVERSING row a bounce writes: its own amount is negative, its status is
 *  `reversed`, and its allocations are the mirrors of the original's. */
function reversingPayment(): PaymentRow {
  return releasedPayment({
    id: "pay-rev",
    payment_no: "PMT-000319",
    amount: "-100.000000",
    status: "reversed",
    applied_to: [
      { invoice_id: "inv-0141", invoice_number: "BL-2608-0141", amount: "-100.000000" },
    ],
  });
}

function cellHtml(row: PaymentRow): string {
  return renderToStaticMarkup(<>{CELLS.appliedTo(row)}</>);
}

describe("CR-059 CS-36 · S33 and S21 show a release AS a release", () => {
  it("one line per BILL — a corrected bill is not listed twice", () => {
    const bills = appliedBills(releasedPayment());
    expect(bills.map((bill) => bill.invoiceNumber)).toEqual(["BL-2608-0141"]);
    // Netted, exactly, on the NUMERIC grid — never through a float.
    expect(bills[0].net).toBe("0.000000");
    expect(bills[0].releasedBack).toBe("100.000000");
  });

  it("the released line says WHY the money came back off", () => {
    const html = cellHtml(releasedPayment());
    expect(html).toContain("this bill was corrected");
    // …and once. A duplicate bill number was also a duplicate React key.
    expect(html.split("BL-2608-0141").length - 1).toBe(1);
  });

  it("a BOUNCE is not called a correction, and the sign of the payment is what says so", () => {
    // `allocation_release` hangs its mirror off the SAME payment (positive
    // amount); `reverse_payment` hangs its mirrors off the NEW reversing
    // payment (negative amount). There is no reason column on `allocations` —
    // CS-36's own spec says "Data: None" — so this is the whole test, and it
    // is a fact about which row holds the negative, not an inference.
    expect(releasedByCorrection(releasedPayment())).toBe(true);
    expect(releasedByCorrection(reversingPayment())).toBe(false);
    expect(cellHtml(reversingPayment())).toContain("the payment was reversed");
  });

  it("an ordinary payment gains no qualifier at all", () => {
    const ordinary = releasedPayment({
      applied_to: [
        { invoice_id: "inv-0141", invoice_number: "BL-2608-0141", amount: "100.000000" },
      ],
      applied_total: "100.000000",
    });
    const html = cellHtml(ordinary);
    expect(html).toContain("BL-2608-0141");
    expect(html).not.toContain("corrected");
    expect(html).not.toContain("reversed");
    expect(appliedBills(ordinary)[0].releasedBack).toBeNull();
  });

  it("two bills, one released: only the released one carries the sentence", () => {
    const both = releasedPayment({
      amount: "292.870000",
      applied_to: [
        { invoice_id: "inv-8311", invoice_number: "BL-2607-018311", amount: "45.000000" },
        { invoice_id: "inv-0141", invoice_number: "BL-2608-0141", amount: "247.870000" },
        { invoice_id: "inv-0141", invoice_number: "BL-2608-0141", amount: "-247.870000" },
      ],
    });
    const bills = appliedBills(both);
    expect(bills.map((bill) => bill.invoiceNumber)).toEqual([
      "BL-2607-018311",
      "BL-2608-0141",
    ]);
    expect(bills[0].releasedBack).toBeNull();
    expect(bills[1].releasedBack).toBe("247.870000");
    expect(cellHtml(both).split("this bill was corrected").length - 1).toBe(1);
  });
});

// ── S30's settlement panel ────────────────────────────────────────────────
// CR-180-BRC10 replaced the nine-section case renderer with step 3's *Existing
// bills* table (`05-prototype/fix-a-bill-2026-10-12/16`). CS-36's rule is
// unchanged and is asserted there: what was paid, what moves to the new bill
// and what is still owed are the SERVER's figures, at two places, none
// computed here.
describe("CR-059 CS-36 · S30's settlement, on Fix a bill's Check step", () => {
  const fmt = { t, currency: "USD", language: "en-US" };

  it("states paid, moves to the new bill and still owed — all served, none computed here", () => {
    const bill = {
      ...PREVIEW_ONE.bills[0],
      paid: "100.0000",
      moves_to_new_bill: "80.0000",
      still_owed: "0.0000",
    };
    const html = renderToStaticMarkup(
      <ExistingBills preview={{ ...PREVIEW_ONE, bills: [bill] }} cls="restatement" t={t} fmt={fmt} />,
    );
    expect(html).toContain(t("billing.fixBill.col.paid"));
    expect(html).toContain(t("billing.fixBill.col.moves"));
    expect(html).toContain(t("billing.fixBill.col.stillOwed"));
    expect(html).toContain("$100.00");
    expect(html).toContain("$80.00");
    expect(html).toContain("$0.00");
  });

  it("an absent figure is a dash, never a zero the server did not send", () => {
    const bill = { ...PREVIEW_ONE.bills[0], paid: null, moves_to_new_bill: null, still_owed: null };
    const html = renderToStaticMarkup(
      <ExistingBills preview={{ ...PREVIEW_ONE, bills: [bill] }} cls="restatement" t={t} fmt={fmt} />,
    );
    expect(html).not.toContain("$0.00");
    expect(html).toContain("—");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-059 §8 CS-36 · §10 · §11 task 20 · 04-docs/02-decisions/14-ui-conventions.md rules 11/31/32/33
// generated: 2026-09-02 by the CR-059 task 20 lane (CS-36's screens)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the two duplicate-bill failures and the missing
//        settlement panel are quoted verbatim in this file's header
// exceptions: (1) the release line is a QUALIFIER under the bill number rather
//        than a StatusPill: a pill is a state of the ROW (B14's own vocabulary)
//        and this is a fact about one bill inside a multi-bill cell. Reported
//        rather than taken quietly.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
