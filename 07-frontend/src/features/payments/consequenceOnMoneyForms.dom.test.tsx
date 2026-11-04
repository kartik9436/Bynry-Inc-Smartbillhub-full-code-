// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `P0.12` of `05-prototype/06 Payments Page Blueprint.pdf` —
//           *"ConsequenceBox into payments … rendered at 52 call sites across
//           seventeen areas — and zero times in staff payments"*. Outcome: *"The
//           rule-11 box exists in this module for the first time. Three
//           violations in §06 are fixed by it."*
// Rules:    B14 rule 11 (*"any form writing money, service state or legal
//           notices shows a 'what this will do' box before its commit
//           button"*) · B14 rule 32 (one sentence per section) · B14 rule 36
//           (the shared component kit is how you comply) · BR-TEN-042 (one
//           currency per tenant, read off the response)
// Screens:  2·3a Record a payment · 2·3b Edit the reference · 2·3e Reverse
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE THREE, NAMED — BECAUSE "THREE VIOLATIONS" IS A NUMBER AND THESE ARE FACTS
// ══════════════════════════════════════════════════════════════════════════
// The blueprint's rule table counts **rule 11 × 3 — "No consequence preview on
// any of the three money forms"**, and its own note is what makes this a defect
// rather than a nicety:
//
//     "ConsequenceBox … is rendered at 52 non-test call sites across seventeen
//      areas — assets, metering, customers, work, plans, and
//      portal/payments/PayNow.tsx, the screen where a CUSTOMER pays. In
//      features/payments/, where a clerk writes to the ledger, it is rendered
//      ZERO times. So the customer-facing payment screen obeys rule 11 and the
//      staff one does not, on the same money."
//
// ⚠ **`Move` AND `Reapply` ALREADY HAD ONE WHEN THIS LANDED**, from `P1.6`
// earlier the same day, so the module's count was no longer zero. The three the
// blueprint files are still the three below. Recorded rather than left, because
// *"zero times in staff payments"* is now a stale sentence in a document a
// later lane will read.
//
// ⚠ **EACH CASE MOUNTS THE MODAL AND DRIVES IT**, rather than asserting that a
// component is imported. An import is not a render: the box draws NOTHING a
// test can find if the branch that renders it is never reached, which is the
// false pass hard-won law 7 calls *looking at the wrong thing*. The Record case
// therefore types an amount and PICKS AN ACCOUNT through the real search, which
// is the only state in which that form has a figure to state.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";

import { ToastProvider } from "@/components/Toast";
import type { ApiClient } from "@/api/client";
import type { AccountRow, PaymentMethodOption, PaymentRow } from "@/api/endpoints";
import {
  CorrectReferenceModal,
  ReversePaymentModal,
} from "./PaymentsPage";
// ⚠ **`RecordPaymentModal` BECAME `RecordPaymentForm` ON 2026-09-23 (`DEF-PAY-6317`).**
// 2·3a is a PAGE at `/:tenant/payments/record/new` (blueprint p037), so the
// form is a COMPONENT (B14 rule 43) inside `FormPage` rather than `FormModal`.
// Same props, with `onClose` renamed `onCancel` — a page goes BACK somewhere;
// it does not close. Every case below is unchanged and asserts the same thing.
import { RecordPaymentForm } from "./RecordPaymentPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const TENANT = "brazosbend";

const METHODS: PaymentMethodOption[] = [
  { id: "met-check", code: "check", name: "Cheque" },
  { id: "met-cash", code: "cash", name: "Cash" },
];

/** The cleared cheque 2·3b opens over — the blueprint's own worked row. */
const PAYMENT = {
  id: "pay-0418",
  payment_no: "PMT-2609-000418",
  account_id: "acc-0001",
  account_no: "AC-2026-00001",
  customer_name: "Ana Alvarez",
  amount: "158.1000",
  currency: "USD",
  status: "cleared",
  type: "payment",
  method: "check",
  confirmation: "4471",
  memo: null,
  purpose: "bill",
  posted_at: "2026-09-21",
  cleared_at: "2026-09-21",
  applied_to: [],
  deposit_batch_id: null,
  receipt_no: null,
} as unknown as PaymentRow;

function account(): AccountRow {
  return {
    id: "acc-0050",
    account_no: "AC-2026-00050",
    customer_no: "CU-2026-00050",
    name: "Miller, Sarah",
    premise: "1408 Elm St · A",
    services: ["electric"],
    balance: "108.880000",
    balance_currency: "USD",
    currency: "USD",
    status: "active",
    status_name: "Active",
    kind: "regular",
    account_type: "residential",
    autopay: false,
    opened_at: "2026-01-04",
    closed_at: null,
  } as unknown as AccountRow;
}

/** A client that answers the account search and nothing else. */
function client(): ApiClient {
  return {
    get: vi.fn().mockImplementation((path: string) => {
      if (path === "/accounts") {
        const rows = [account()];
        return Promise.resolve({
          data: { results: rows, count: rows.length, page: 1, per: 50 },
        });
      }
      return Promise.resolve({ data: { results: [], count: 0 } });
    }),
  } as unknown as ApiClient;
}

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, for `DEF-CWP-3925`'s reason: a
 *  bare `MemoryRouter` leaves `useParams().tenant` undefined and every address
 *  a mounted screen builds comes out pointing at another host. */
function mount(node: JSX.Element) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/record`]}>
          <Routes>
            <Route path="/:tenant/payments/:tab" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function correctionModal() {
  return mount(
    <CorrectReferenceModal
      client={client()}
      payment={PAYMENT}
      methods={METHODS}
      onClose={() => undefined}
      onCorrected={() => undefined}
    />,
  );
}

function recordModal(currency: string | null) {
  return mount(
    <RecordPaymentForm
      client={client()}
      methods={METHODS}
      today="2026-09-22"
      dateFormat="MM/DD/YYYY"
      currency={currency}
      onCancel={() => undefined}
      onRecorded={() => undefined}
    />,
  );
}

/** Type an account number, wait for the served matches, choose the row.
 *
 *  ⚠ The ids are the ones `accountSearch.dom.test.tsx` already drives — one
 *  harness shape for one form, rather than a second understanding of it.
 *
 *  ⚠ **ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`).** There was a
 *  `#account_query` box and a `#account_id` SELECT beside it; the picker is a
 *  combobox now, so the typing and the choosing happen on the same element and
 *  the matches are `role="option"` rows in its panel. What this helper is FOR
 *  did not change. */
async function chooseAccount(): Promise<void> {
  const box = document.querySelector<HTMLInputElement>("#account_id");
  expect(box).not.toBeNull();
  fireEvent.change(box as HTMLInputElement, { target: { value: "AC-2026-00050" } });
  await waitFor(() =>
    expect(document.querySelector<HTMLElement>('[data-panel-state="matches"]')).not.toBeNull(),
  );
  const options = [...document.querySelectorAll<HTMLElement>('[role="option"]')];
  expect(options.length).toBeGreaterThan(0);
  fireEvent.click(options[0]);
}

function typeAmount(value: string): void {
  const box = document.querySelector<HTMLInputElement>("#amount");
  expect(box).not.toBeNull();
  fireEvent.change(box as HTMLInputElement, { target: { value } });
}

/** A client that answers the reversal plan — two bills re-opening. */
function planClient(): ApiClient {
  return {
    get: vi.fn().mockImplementation((path: string) => {
      if (path.endsWith("/reversal-plan")) {
        return Promise.resolve({
          data: {
            reason: "data_entry_error",
            is_staff_correction: true,
            on: "2026-09-22",
            already_reversed: "0.0000",
            stands_for: "158.1000",
            window: {
              tender: "check",
              measured_from: "2026-09-21",
              days_elapsed: 1,
              limit_days: 90,
              unlimited: false,
              within: true,
              named_by_the_rule: true,
            },
            window_applies: true,
            approval: { required: false, reasons: [], problems: [] },
            consequences: {
              currency: "USD",
              amount: "158.1000",
              bills_reopening: [
                { bill_no: "BL-2609-000085", amount: "100.0000", currency: "USD" },
                { bill_no: "BL-2609-000086", amount: "58.1000", currency: "USD" },
              ],
              bills_reopening_total: "158.1000",
              credit_taken_back: "0.0000",
              credit_after: null,
              credit_goes_negative: false,
              problems: [],
            },
            can_reverse: true,
            problems: [],
          },
        });
      }
      return Promise.resolve({ data: { results: [], count: 0 } });
    }),
  } as unknown as ApiClient;
}

describe("P0.12 — 2·3b Edit the reference", () => {
  it("draws the box, and it says no money moves", () => {
    const { container } = correctionModal();
    const box = container.querySelector('[data-consequence="correct"]');
    expect(box).not.toBeNull();
    expect(box?.textContent).toContain(t("payments.correct.consequence.title"));
    expect(box?.textContent).toContain(t("payments.correct.consequence.body"));
  });

  it("draws it in the state the modal OPENS in, before anything is typed", () => {
    // ⚠ **THE REGRESSION THIS CASE HOLDS.** The first draft gated the box on
    // *something changed* — which hides it in the only state a hesitating clerk
    // is ever looking at. The statement is a fact about the FORM (this door
    // cannot move money, at the database, whatever is typed), not about the
    // current edits.
    const { container } = correctionModal();
    expect(container.querySelector('[data-consequence="correct"]')).not.toBeNull();
  });

  it("and it is the ONLY thing said here — the retention disclosure is gone", () => {
    // ⚠ **THIS CASE WAS THE EXACT OPPOSITE UNTIL `P3.18` (2026-09-23).** It read
    // *"keeps the retention disclosure, which is a different question"* and
    // asserted `payments.correct.retentionSummary` was on screen. It was a
    // correct case when it was written: *what changes* and *where the old value
    // goes* ARE two facts, and folding them would lose the half rule 11 is
    // about.
    //
    // **What changed is not rule 11 — it is that the second thing stopped
    // belonging on a screen at all.** The PO closed `OQ-1340` that day (*"keep
    // the same rule s; when audit log is delete - it is deleted thats okay"*),
    // which made the disclosure's own last sentence false; and B14 rule 33 puts
    // RATIONALE at **zero words on screen**, so rewording it would have kept the
    // breach and made it terser. **Rule 11's box stays; the rationale goes.**
    const { container } = correctionModal();
    const text = (container.textContent ?? "").toLowerCase();
    for (const word of ["retention", "audit trail", "not kept", "for ever"]) {
      expect(text).not.toContain(word);
    }
    // The box itself is still there — proved above, and re-asserted here so this
    // case cannot pass by the modal failing to render at all.
    expect(container.querySelector('[data-consequence="correct"]')).not.toBeNull();
  });
});

describe("P0.12 — 2·3a Record a payment", () => {
  it("draws the box once an account and an amount are chosen", async () => {
    const { container } = recordModal("USD");
    expect(container.querySelector('[data-consequence="record"]')).toBeNull();

    await chooseAccount();
    typeAmount("158.10");

    await waitFor(() =>
      expect(container.querySelector('[data-consequence="record"]')).not.toBeNull(),
    );
    const box = container.querySelector('[data-consequence="record"]');
    // The figure, in the tenant's own code — and the DESTINATION, which is the
    // half the drawing leads with.
    expect(box?.textContent).toContain("158.10");
    // ⛔ `DEF-PAY-10737` (2026-10-30) — this asserted DEF-PAY-10157's
    // "meets no bill until cleared" and then typed a clearing date. CR-186
    // applies every payment at entry and the box is gone, so the default
    // allocation is stated straight away, in the clerk's terms.
    expect(box?.textContent).toContain(t("payments.form.consequence.oldest"));
    expect(box?.textContent).not.toContain(t("payments.form.consequence.notCleared"));
    expect(document.querySelector("#cleared_at")).toBeNull();
  });

  it("draws nothing on an empty form", () => {
    // B14 rule 32: a consequence of nothing is noise, and noise in the one
    // place the product says what is about to happen is how a clerk learns to
    // read past it.
    const { container } = recordModal("USD");
    expect(container.querySelector('[data-consequence="record"]')).toBeNull();
  });

  it("never invents a currency when the tenant's code could not be read", async () => {
    // ⚠ **THE FALSE PASS THIS CASE EXISTS FOR.** Defaulting to USD would print
    // a dollar sign on a Canadian utility's money and every other assertion in
    // this file would still pass. `currency` is genuinely `null` on a new
    // tenant with issued bills and no payments.
    const { container } = recordModal(null);
    await chooseAccount();
    typeAmount("158.10");
    expect(container.querySelector('[data-consequence="record"]')).toBeNull();
  });
});

describe("P0.12 — 2·3e Reverse", () => {
  it("draws the box once the server has answered with a plan", async () => {
    // ⚠ **A STAFF REASON AND A DATE, BECAUSE THE READ IS `enabled: false` FOR A
    // BOUNCE.** `reversePayment.test.tsx` renders this modal with the default
    // reason, which IS a bounce, so the consequence panel never draws there and
    // an assertion on its sentence would pass whether a box existed or not —
    // hard-won law 7's *looking at the wrong thing*. This case is the only one
    // in the suite that reaches the branch.
    const { container } = mount(
      <ReversePaymentModal
        client={planClient()}
        payment={PAYMENT}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onReversed={() => undefined}
      />,
    );
    expect(container.querySelector('[data-consequence="reverse"]')).toBeNull();

    const reason = document.querySelector<HTMLSelectElement>("#reason") as HTMLSelectElement;
    fireEvent.change(reason, { target: { value: "data_entry_error" } });
    const on = document.querySelector<HTMLInputElement>("#returned_on") as HTMLInputElement;
    fireEvent.change(on, { target: { value: "2026-09-22" } });

    await waitFor(() =>
      expect(container.querySelector('[data-consequence="reverse"]')).not.toBeNull(),
    );
    const box = container.querySelector('[data-consequence="reverse"]');
    // The SERVER's figures, unread by this component — the sentence did not
    // change when it moved into the box, and this pins that.
    expect(box?.textContent).toContain("2");
    expect(box?.textContent).toContain(t("payments.reverse.consequence.body"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p7 (the rule table), p13 `P0.12`, p38 (③ the Record form's box), p98 (the per-screen change list)
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B✔ C✔ D=n/a(no endpoint) E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/consequenceOnMoneyForms.dom.test.tsx · tsc --noEmit
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
