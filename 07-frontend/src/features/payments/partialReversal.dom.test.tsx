// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-059 · CS-33 · task 67 — the amount field on the Reverse modal,
//          and the line saying what will still stand afterwards. Its schema
//          half is task 66 (`payments/0019`), which landed 2026-09-03 with no
//          screen: a partial reversal was expressible in the database, in the
//          service and at the door, and by nobody.
// Story:   US-PAY-009   Screens: S35 (the Reverse modal) · S33 · S21
// Rules:   BR-PAY-884 (a partial may not exceed what the payment still stands
//          for, and the SUM of all reversals may never exceed it) ·
//          CLAUDE.md rule 2 (no float touches money) · B14 rule 31
// ───────────────────────────────────────────────────────
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE WORKED FIGURE: $100.00 OFF A $292.87 CHEQUE LEAVES $192.87,        ║
// ║  AND THE DATABASE REFUSES A CENT MORE.                                  ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// CS-33's case is a cheque where the words and the figures disagree and the
// bank honours the lower. Before this the office had to reverse the whole thing
// and record a second payment for the part that stood — *"the customer's
// history then shows a payment that bounced when it did not"*, and on a cheque
// that is an NSF count and a cash-only flag behind it.
//
// ⚠ **THE REMAINDER IS MEASURED OFF THE SERVER'S `stands_for`, NOT OFF
// `PaymentRow.amount`, AND THAT IS THE ASSERTION THAT MATTERS MOST HERE.**
// They are the same figure only until the first partial reversal. A screen
// subtracting from `amount` would tell the clerk 192.87 when the payment
// already stood at 192.87 and the truth was 92.87 — a number offered at the
// exact moment somebody is deciding, which the service would then refuse.
// `secondPartial()` is that case and it is the reason this file exists.
//
// **RED PROVED FIRST (hard-won law 7).** Every case below was run against the
// build at 4c625924 — the tip after the API wrappers landed and before the
// field did. The shapes:
//
//   · `the amount box exists and is EMPTY, so touching nothing reverses it all`
//     → `expected null not to be null` — there was no `#amount` on the modal.
//   · `the remainder is the SERVER's stands_for, never PaymentRow.amount`
//     → `Unable to find an element with the text: $92.87` — nothing rendered a
//     remainder at all.
//   · `a blank box is sent as ABSENT and never as 0.00` → `expected true to be
//     false` — `reversePaymentSchema` had no `amount` member, so a typed
//     `"0.00"` parsed cleanly and the modal would have posted a reversal that
//     takes nothing back.
//   · `a PARTIAL reversal says what is left` → `Unable to find an element with
//     the text: Still stands`.
//
// **SIX OF THE EIGHT WENT RED; THE TWO THAT DID NOT ARE NAMED HERE ON PURPOSE.**
// `no remainder is drawn while the box is blank` and `a FULL reversal draws no
// such line` are ABSENCE assertions, and an absence is trivially true on a build
// with no feature in it. They are kept because they are the two ways this
// feature could regress into showing a `$0.00` that reads as a measurement —
// but a check that cannot fail on the defect it was written for is not evidence,
// and saying which two those are is the honest half (hard-won law 7).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { PaymentRow, ReversedPayment } from "@/api/endpoints";
import type { ReversalPlan } from "@/api/bankRecEndpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ReversedPaymentPanel, ReversePaymentModal, reversePaymentSchema } from "./PaymentsPage";

/** The result panel's bill numbers are record links (PO 2026-10-19), which
 *  build a tenant address — so everything mounts inside a tenant path. */
function render(ui: ReactElement) {
  return rtlRender(<MemoryRouter initialEntries={["/acme/payments"]}>{ui}</MemoryRouter>);
}

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** PE-7's cheque: 292.87, cleared, meeting two bills. */
function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-8842",
    payment_no: "PMT-000241",
    account_id: "acc-1042",
    account_no: "ACC-1042",
    customer_name: "Ridge Coffee Co.",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: "8842",
    memo: null,
    amount: "292.870000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-07-14",
    cleared_at: "2026-07-16",
    applied_to: [
      { invoice_id: "inv-018311", invoice_number: "BL-2607-018311", amount: "45.000000" },
      { invoice_id: "inv-018410", invoice_number: "BL-2608-018410", amount: "247.870000" },
    ],
    applied_total: "292.870000",
    deposit_batch_id: null,
    receipt_no: null,
    cheque_date: "2026-07-14",
    drawer_bank: "First National",
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

/** `GET /payments/{id}/reversal-plan` — nothing has come back off it yet. */
function plan(over: Partial<ReversalPlan> = {}): ReversalPlan {
  return {
    reason: "nsf",
    is_staff_correction: false,
    on: "2026-08-12",
    already_reversed: "0.0000",
    stands_for: "292.8700",
    window: {
      tender: "check",
      measured_from: "2026-07-16",
      days_elapsed: 27,
      limit_days: null,
      unlimited: true,
      named_by_the_rule: true,
      within: true,
    },
    window_applies: false,
    approval: { required: false, reasons: [], problems: [] },
    consequences: {
      currency: "USD",
      amount: "292.8700",
      bills_reopening: [],
      bills_reopening_total: "292.8700",
      credit_taken_back: "0.0000",
      credit_after: "0.0000",
      credit_goes_negative: false,
      problems: [],
    },
    can_reverse: true,
    problems: [],
    ...over,
  };
}

/** The SECOND partial: 100.00 has already come back, so it stands at 192.87. */
function secondPartial(): ReversalPlan {
  return plan({ already_reversed: "100.0000", stands_for: "192.8700" });
}

function client(answer: ReversalPlan): ApiClient {
  return {
    get: vi.fn().mockImplementation((path: string) => {
      if (path.includes("/reversal-plan")) {
        return Promise.resolve({ data: answer });
      }
      return Promise.resolve({ data: {} });
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  } as unknown as ApiClient;
}

function mount(answer: ReversalPlan = plan()) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <ReversePaymentModal
          client={client(answer)}
          payment={payment()}
          dateFormat="MM/DD/YYYY"
          onClose={() => undefined}
          onReversed={() => undefined}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function set(id: string, value: string): void {
  const box = document.querySelector<HTMLInputElement>(`#${id}`);
  expect(box).not.toBeNull();
  fireEvent.change(box as HTMLInputElement, { target: { value } });
}

describe("CS-33 · the amount field, and blank meaning ALL of it", () => {
  it("the amount box exists and is EMPTY, so touching nothing reverses it all", () => {
    mount();
    const box = document.querySelector<HTMLInputElement>("#amount");
    expect(box).not.toBeNull();
    // NOT pre-filled with 292.87. A pre-filled figure is one a clerk scrolls
    // past, and the whole-payment case is the common one that needs no typing.
    expect((box as HTMLInputElement).value).toBe("");
    // And the label says which way round it is.
    expect(screen.getByLabelText(t("payments.reverse.amount"))).toBe(box);
  });

  it("a blank box is ABSENT and never 0.00 — the service refuses a zero by name", () => {
    const schema = reversePaymentSchema(t);
    // Blank passes: it means "the whole of what still stands".
    expect(schema.safeParse({ returned_on: "2026-08-12", bank_fee: "", amount: "" }).success).toBe(
      true,
    );
    // A typed zero does NOT: a reversal that takes nothing back is not a thing,
    // and letting it through would put the refusal after the button instead of
    // beside the field.
    const zero = schema.safeParse({ returned_on: "2026-08-12", bank_fee: "", amount: "0.00" });
    expect(zero.success).toBe(false);
    // Neither does something that is not money at all. Checked as a STRING
    // pattern and never parsed — a `Number()` here is the float rule 2 keeps
    // out of money, in the one place it is most tempting.
    expect(
      schema.safeParse({ returned_on: "2026-08-12", bank_fee: "", amount: "one hundred" }).success,
    ).toBe(false);
    expect(
      schema.safeParse({ returned_on: "2026-08-12", bank_fee: "", amount: "100.00" }).success,
    ).toBe(true);
  });

  it("no remainder is drawn while the box is blank", () => {
    mount();
    set("returned_on", "2026-08-12");
    // A full reversal leaves nothing standing, and "$0.00 still stands" reads
    // as a figure somebody measured rather than as the end of the payment.
    expect(screen.queryByText(t("payments.reverse.stillStands"))).toBeNull();
  });
});

describe("CS-33 · the remainder is the SERVER's, and the worked figure is 192.87", () => {
  it("$100.00 off a $292.87 cheque leaves $192.87", async () => {
    mount();
    set("returned_on", "2026-08-12");
    set("amount", "100.00");
    await waitFor(() => {
      expect(screen.getByText(t("payments.reverse.stillStands"))).toBeInTheDocument();
    });
    // Rendered through MoneyCell at TWO decimals beside its CHAR(3), from a
    // four-decimal wire figure (CLAUDE.md rule 2).
    expect(await screen.findByText("$192.87")).toBeInTheDocument();
  });

  it("after one partial it is 92.87, because the base is `stands_for` and not `amount`", async () => {
    // ⚠ THE CASE THIS WHOLE FILE EXISTS FOR. The payment is still 292.87 and
    // 100.00 has already come back, so a second 100.00 leaves 92.87. A screen
    // subtracting from `PaymentRow.amount` would say 192.87 — a figure the
    // service is about to refuse, shown while somebody is deciding.
    mount(secondPartial());
    set("returned_on", "2026-08-12");
    set("amount", "100.00");
    expect(await screen.findByText("$92.87")).toBeInTheDocument();
    expect(screen.queryByText("$192.87")).toBeNull();
  });

  it("a plan that cannot be read states the absence rather than guessing", async () => {
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const failing = {
      get: vi.fn().mockRejectedValue(new Error("network")),
      post: vi.fn(),
    } as unknown as ApiClient;
    render(
      <QueryClientProvider client={queries}>
        <ToastProvider>
          <ReversePaymentModal
            client={failing}
            payment={payment()}
            dateFormat="MM/DD/YYYY"
            onClose={() => undefined}
            onReversed={() => undefined}
          />
        </ToastProvider>
      </QueryClientProvider>,
    );
    set("returned_on", "2026-08-12");
    set("amount", "100.00");
    // No remainder is invented from the row. The clerk may still submit — the
    // SERVER holds BR-PAY-884 either way — and is simply not shown a figure
    // nobody measured.
    await waitFor(() => {
      expect(screen.queryByText("$192.87")).toBeNull();
    });
    expect(screen.queryByText(t("payments.reverse.stillStands"))).toBeNull();
  });
});

describe("CS-33 · what the panel says afterwards", () => {
  function result(over: Partial<ReversedPayment> = {}): ReversedPayment {
    return {
      id: "rev-1",
      payment_no: "PMT-000242",
      original_payment_id: "pay-8842",
      created: true,
      amount: "-100.000000",
      currency: "USD",
      reason: "nsf",
      allocations_reversed: "100.000000",
      reopened: [],
      credit_reversed: "0.000000",
      credit_position_after: "0.000000",
      journal_entry_id: "je-1",
      posting_key: "k",
      bank_fee: null,
      bank_fee_entry_id: null,
      nsf_count: 1,
      cash_only_no_autopay: false,
      privilege_flag_tripped: false,
      is_partial: true,
      still_stands: "192.870000",
      problems: [],
      ...over,
    };
  }

  it("a PARTIAL reversal says what is left, from the service's own figure", () => {
    render(
      <ReversedPaymentPanel
        result={result()}
        original={payment()}
        onDismiss={() => undefined}
      />,
    );
    expect(screen.getByText(t("payments.reverse.stillStandsLabel"))).toBeInTheDocument();
    expect(screen.getByText("$192.87")).toBeInTheDocument();
  });

  it("a FULL reversal draws no such line — 0.00 would read as a measurement", () => {
    render(
      <ReversedPaymentPanel
        result={result({ is_partial: false, still_stands: "0.000000", amount: "-292.870000" })}
        original={payment()}
        onDismiss={() => undefined}
      />,
    );
    expect(screen.queryByText(t("payments.reverse.stillStandsLabel"))).toBeNull();
  });
});
