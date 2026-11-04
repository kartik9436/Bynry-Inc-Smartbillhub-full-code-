// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-5 · task 16 — P2, the Reverse row action and the S35
//           modal. Its backend half is task 15 (`POST /payments/{id}/reverse`).
// Story:    US-PAY-009 (NSF) · J12 the bounce chain
//           Screens: S33 (the row action) · S35 (the modal) · S21 (the account
//           Payments tab, which gets the action from the SAME table)
// Rules:    BR-PAY-1070 (reversing is Admin-only, gated in the SERVICE) ·
//           BR-PAY-013 (reversing row + reversed allocations, AR reinstated at
//           the ORIGINAL due date) · BR-PAY-021 (NSF is a CLEARING-side
//           failure) · BR-PAY-036 (money is always accepted — a customer who
//           pays again after a bounce makes a NEW payment) · BR-SHL-025 (a
//           control this role may not use renders DISABLED WITH ITS REASON) ·
//           B14 rule 15 (row actions are ICONS with an accessible name) ·
//           B14 rule 31 (no database id is the visible value of a field) ·
//           CLAUDE.md rule 2 (no float touches money)
// ───────────────────────────────────────────────────────
// §4 test data is `PE-7`, verbatim: a **292.87** cheque on `ACC-1042` settling
// BL-2607-018311 (**45.00**) and BL-2608-018410 (**247.87**) comes back, the
// reversing row is **−292.87**, and **292.87** goes back on the bills.
//
// THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES. This screen must not
// hide the Reverse control from a clerk, must not render −292.87 unsigned, must
// not print an invoice id where a bill number belongs, and must not read "the
// bounce count is zero" when the server said it did not count.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { REVERSAL_REASONS } from "@/api/endpoints";
import type { PaymentRow, ReversedPayment } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  ReversedPaymentPanel,
  ReversePaymentModal,
  paymentsCells,
  paymentsTableConfig,
  reverseBlockedReason,
  reversePaymentSchema,
} from "./PaymentsPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** Copy as `renderToStaticMarkup` writes it — an apostrophe in real English
 *  prose comes out as `&#x27;`, and a test comparing the raw string would fail
 *  on the copy being written well rather than on the screen being wrong. */
function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/** PE-7's cheque, as `GET /payments` serves it. */
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

/** What `reverse_payment` answers with — `selectors.reversed_payment_dict`. */
function reversed(over: Partial<ReversedPayment> = {}): ReversedPayment {
  return {
    id: "pay-rev-1",
    payment_no: "PMT-000318",
    original_payment_id: "pay-8842",
    created: true,
    amount: "-292.870000",
    currency: "USD",
    reason: "nsf",
    allocations_reversed: "292.870000",
    reopened: [
      { invoice_id: "inv-018311", amount: "45.000000" },
      { invoice_id: "inv-018410", amount: "247.870000" },
    ],
    credit_reversed: "0.000000",
    credit_position_after: "0.000000",
    journal_entry_id: "je-77",
    posting_key: "reverse:pay-8842",
    bank_fee: null,
    bank_fee_entry_id: null,
    nsf_count: 2,
    cash_only_no_autopay: false,
    privilege_flag_tripped: false,
    // CR-059 CS-33 — a whole-payment reversal leaves nothing standing.
    is_partial: false,
    still_stands: "0.0000",
    problems: [{ code: "nsf_fee_not_added", br_ref: "BR-BIL-007", detail: "billing's charge code" }],
    ...over,
  };
}

describe("CS-5 · who may reverse, and who is merely TOLD they may not", () => {
  it("BR-PAY-1070: a Billing Clerk gets a REASON, not a null — the control stays", () => {
    // The cost the backend lane named in terms: the clerk who takes the 292.87
    // cheque at the counter cannot record its return.
    expect(reverseBlockedReason(payment(), "billing_clerk", t)).toBe(
      t("payments.reverse.adminOnly"),
    );
  });

  it("an Admin is allowed, and so is a role the server has not answered for yet", () => {
    expect(reverseBlockedReason(payment(), "system_admin", t)).toBeNull();
    // `null` = /me/permissions has not returned. Offering the control is right:
    // the service's own @require_role is the boundary either way, and a control
    // withheld on a pending read teaches a clerk a rule that does not exist.
    expect(reverseBlockedReason(payment(), null, t)).toBeNull();
  });

  it("US-PAY-009 TC-5: a PROCESSING payment cannot bounce — the money never came", () => {
    expect(reverseBlockedReason(payment({ status: "processing" }), "system_admin", t)).toBe(
      t("payments.reverse.notCleared"),
    );
  });

  it("BR-PAY-036: a reversing row cannot itself be reversed", () => {
    // Both halves the service refuses: the status the reversing row carries…
    expect(reverseBlockedReason(payment({ status: "reversed" }), "system_admin", t)).toBe(
      t("payments.reverse.isReversal"),
    );
    // …and the sign, which is the fact underneath it. Read as a STRING: a
    // Number() here would be the float CLAUDE.md rule 2 keeps out of money.
    expect(
      reverseBlockedReason(payment({ amount: "-292.870000" }), "system_admin", t),
    ).toBe(t("payments.reverse.isReversal"));
  });

  it("the ROLE is answered before the status, so a clerk reads one stable reason", () => {
    // A clerk looking at a processing payment must not be told "the money has
    // not arrived" — that reason disappears tomorrow and the real one does not.
    expect(reverseBlockedReason(payment({ status: "processing" }), "billing_clerk", t)).toBe(
      t("payments.reverse.adminOnly"),
    );
  });
});

/**
 * ⚠ **THE ACTIONS CELL CONTAINS A ROUTER `<Link>` SINCE `CR-137-BRC07` `P3.10`
 * AND MUST BE RENDERED UNDER A ROUTE.** The 👁 Detail action is a
 * `RowActionLink`, not a button: an address a clerk can middle-click, open in
 * a new tab and paste into a message is the whole point of screen 2·2, and an
 * `onClick` that calls `navigate` loses all three. Rendered bare it throws
 * *"Cannot destructure property 'basename'"*.
 *
 * ⚠ **THE PATTERN CARRIES `:tenant` ON PURPOSE.** A bare `MemoryRouter` with
 * no tenant segment leaves `useParams().tenant` undefined, so every address
 * the cell builds comes out `//payments/…` — a protocol-relative URL to
 * another host that reads as a perfectly good string to `toContain`
 * (CLAUDE.md hard-won law 2).
 */
function underRoute(node: React.ReactNode): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/payments"]}>
      <Routes>
        <Route path="/:tenant/payments" element={<>{node}</>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CS-5 · the row action is an ICON, present on every row (B14 rule 15)", () => {
  const cells = paymentsCells(t, (p) => p, "UTC", "MM/DD/YYYY");

  it("the actions column exists only where rows are RENDERED", () => {
    // The parse-only callers build a config for `parseTableParams`, which reads
    // column KEYS and never renders a cell (law 2: an unrendered column is not
    // a feature).
    const parseOnly = paymentsTableConfig(t, cells);
    expect(parseOnly.columns.some((column) => column.key === "actions")).toBe(false);

    const rendering = paymentsTableConfig(t, cells, {
      reasonFor: () => null,
      onReverse: () => undefined,
    });
    expect(rendering.columns.some((column) => column.key === "actions")).toBe(true);
  });

  it("BR-SHL-025: a clerk sees the control DISABLED with its reason, never hidden", () => {
    const config = paymentsTableConfig(t, cells, {
      reasonFor: () => t("payments.reverse.adminOnly"),
      onReverse: () => undefined,
    });
    const actions = config.columns.find((column) => column.key === "actions");
    if (actions?.cell === undefined) {
      throw new Error("the actions column is missing — BR-SHL-025 has nothing to render");
    }
    const html = underRoute(actions.cell(payment()));
    // ⚠ **REVERSE MOVED BEHIND THE `…` IN `CR-137-BRC07` `P3.10`, AND EVERY
    // GUARANTEE THIS CASE ASSERTS STILL HOLDS — ONLY THE PLACE CHANGED.**
    // p030 ⑥ draws the column as *"👁 Detail · ✎ Edit, then `…` for Receipt
    // and Cancel"*, with B14 rule 15's cap of two visible; the 👁 could not
    // exist before `P3.9` gave a payment an address. **`RowMenuAction` carries
    // the same three properties `RowAction` did** — it is rendered, it is
    // `disabled`, and its `title` says why — so BR-SHL-025 is satisfied in the
    // menu exactly as it was on the row. The assertions below are UNCHANGED in
    // substance and only look in the right place.
    const menu = html.slice(html.indexOf("data-row-more"));
    // Visible…
    expect(menu).toContain(escaped(t("payments.reverse.action")));
    // …disabled (the ATTRIBUTE, not the `disabled:` utility every button
    // carries in its class list — the naive substring passes on both)…
    expect(menu).toContain('disabled=""');
    // …and saying WHY, which is the whole of BR-SHL-025.
    expect(menu).toContain(`title="${escaped(t("payments.reverse.adminOnly"))}"`);
    // Still an icon beside the word — rule 15's own note: *"a clerk who learns
    // `⟲` on one table recognises it on the next"*.
    expect(menu).toContain("<svg");
  });

  it("an allowed row carries no title-reason and is not disabled", () => {
    const config = paymentsTableConfig(t, cells, {
      reasonFor: () => null,
      onReverse: () => undefined,
    });
    const actions = config.columns.find((column) => column.key === "actions");
    if (actions?.cell === undefined) {
      throw new Error("the actions column is missing — BR-SHL-025 has nothing to render");
    }
    const html = underRoute(actions.cell(payment()));
    // Behind the `…` since `P3.10` — see the case above. An ALLOWED row has no
    // disabled control anywhere in the cell, which is the stronger statement.
    expect(html).not.toContain('disabled=""');
    expect(html.slice(html.indexOf("data-row-more"))).toContain(
      escaped(t("payments.reverse.action")),
    );
  });
});

describe("CS-5 · the modal (S35)", () => {
  function modal(row: PaymentRow = payment()): string {
    // ⚠ **THE PROVIDER IS NEW (CR-059 CS-31, task 36) AND IT IS NOT DECORATION.**
    // The modal now READS `GET /payments/{id}/reversal-plan` when a STAFF reason
    // is picked, because CS-31 puts the window, the approval trigger and the
    // consequence message on the server — *"it must be computed by the service,
    // not assembled on the screen, or the warning and the outcome can
    // disagree."* The read is `enabled: false` for a bounce, which is what
    // every case below renders, so nothing is fetched here.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    return renderToStaticMarkup(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <ReversePaymentModal
            client={{} as never}
            payment={row}
            dateFormat="MM/DD/YYYY"
            onClose={() => undefined}
            onReversed={() => undefined}
          />
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("FOUR reasons, and the bounce is the one that is pre-selected", () => {
    // ⚠ **THIS CASE ASSERTED *ONE* REASON UNTIL 2026-09-03 AND IT IS INVERTED,
    // NOT DELETED (hard-won law 1).** BR-PAY-011 names four and the column has
    // always carried four; the SERVICE accepted one, because that rule's
    // windows, approval path and consequence message were CS-31 and unbuilt —
    // so a picker would have been four options over a service that fails on
    // submit. CS-31 (tasks 35 and 36) built all three, and the picker is now
    // four options over a service that honours four.
    const html = modal();
    expect(html).toContain('id="reason"');
    for (const code of REVERSAL_REASONS) {
      expect(html).toContain(escaped(t(`payments.reverse.reason.${code}`)));
    }
    // The BOUNCE is the default, deliberately: it is the only reason that needs
    // no window and no approval, so a clerk who changes nothing gets the least
    // restrictive path and is never walked into a staff correction.
    expect(html).toContain('value="nsf" selected=""');
  });

  it("the sentence a staff correction shows exists and is not a fallback", () => {
    // `BR-PAY-013` is the bounce rule and its NAME is the boundary: a correction
    // of our own record counts nothing against the customer and sends no
    // letter. Selecting a reason is a click, so what is asserted here is that
    // the copy EXISTS in the catalogue and is NOT rendered for the bounce —
    // the default this modal opens on.
    expect(t("payments.reverse.staffCorrection")).not.toBe(
      "payments.reverse.staffCorrection",
    );
    expect(t("payments.reverse.staffCorrection")).toContain("nothing is counted");
    expect(modal()).not.toContain(escaped(t("payments.reverse.staffCorrection")));
  });

  it("P2's consequences are previewed BEFORE the button, from the row itself", () => {
    const html = modal();
    expect(html).toContain(escaped(t("payments.reverse.willReopen")));
    expect(html).toContain("BL-2607-018311");
    expect(html).toContain("BL-2608-018410");
    expect(html).toContain('<span class="cell-money-amount">$45.00</span>');
    expect(html).toContain('<span class="cell-money-amount">$247.87</span>');
  });

  it("a payment that met no bill says so rather than showing an empty list", () => {
    const html = modal(payment({ applied_to: [], applied_total: "0.000000" }));
    expect(html).toContain(escaped(t("payments.reverse.willReopenNone")));
  });

  it("OQ-134 is CLOSED: no locked-batch refusal is drawn anywhere", () => {
    // CS-5 asks for it and §10's P2 spells the sentence out. The PO closed the
    // question on 2026-08-12 — a bounce inside a reconciled batch is lawful —
    // so drawing it would put a rule on screen that nobody holds.
    const html = modal(payment({ deposit_batch_id: "DEP-260808-CHK" }));
    expect(html).not.toContain("DEP-260808-CHK");
    expect(html).not.toContain("reconciled");
  });

  it("BR-PAY-021: the bank's return date is required and is NOT pre-filled", () => {
    const html = modal();
    expect(html).toContain(escaped(t("payments.reverse.returnedOn")));
    // A returned item reaches a clerk days later on a statement. A pre-filled
    // today would be accepted unread and would date the bounce wrongly.
    const field = html.slice(html.indexOf('<input id="returned_on"'));
    expect(field.slice(0, field.indexOf("/>"))).toContain('value=""');
  });

  it("the ladder choice is OFF by default — a bounce pauses, a person resumes", () => {
    const html = modal();
    expect(html).toContain(escaped(t("payments.reverse.resume")));
    expect(html).not.toContain('id="resume_collections" type="checkbox" checked');
  });

  it("the schema refuses a missing return date and a non-money bank fee", () => {
    // ⚠ `amount: ""` is CS-33's field (task 67) and it is carried here rather
    // than omitted, because the schema mirrors what the FORM holds and the form
    // always holds it. Blank is the field's own default and means *"the whole
    // of what still stands"* — `partialReversal.dom.test.tsx` owns that rule.
    const schema = reversePaymentSchema(t);
    const blank = { bank_fee: "", amount: "" };
    expect(schema.safeParse({ ...blank, returned_on: "" }).success).toBe(false);
    expect(schema.safeParse({ ...blank, returned_on: "2026-07-22" }).success).toBe(true);
    expect(
      schema.safeParse({ ...blank, returned_on: "2026-07-22", bank_fee: "12.50" }).success,
    ).toBe(true);
    expect(
      schema.safeParse({ ...blank, returned_on: "2026-07-22", bank_fee: "-12.50" }).success,
    ).toBe(false);
    expect(
      schema.safeParse({ ...blank, returned_on: "2026-07-22", bank_fee: "12,50" }).success,
    ).toBe(false);
  });

  it("the approval is required ONLY when the server said one is needed", () => {
    // BR-PAY-011's approval clause (CR-059 CS-31). This side never predicts
    // *"applied to an issued bill, or a closed month"* — a second copy of that
    // rule is a second place for it to drift — so the marker beside the label
    // follows the SERVER's answer and nothing else.
    const relaxed = reversePaymentSchema(t, false);
    const strict = reversePaymentSchema(t, true);
    const body = { returned_on: "2026-07-22", bank_fee: "", amount: "" };

    expect(relaxed.safeParse({ ...body, approval: "" }).success).toBe(true);
    expect(strict.safeParse({ ...body, approval: "" }).success).toBe(false);
    expect(strict.safeParse({ ...body, approval: "   " }).success).toBe(false);
    expect(strict.safeParse({ ...body, approval: "approved by D. Whitfield" }).success).toBe(
      true,
    );
  });
});

describe("CS-5 · the result panel — PE-7, end to end", () => {
  function panel(result: ReversedPayment = reversed(), original: PaymentRow = payment()): string {
    // The re-opened bills are record links (PO 2026-10-19), which build a
    // tenant address — so the panel mounts inside a tenant path.
    return renderToStaticMarkup(
      <MemoryRouter initialEntries={["/acme/payments"]}>
        <ToastProvider>
          <ReversedPaymentPanel result={result} original={original} onDismiss={() => undefined} />
        </ToastProvider>
      </MemoryRouter>,
    );
  }

  it("PE-7: the reversing row is NEGATIVE and 292.87 goes back on the bills", () => {
    const html = panel();
    expect(html).toContain(escaped(t("payments.reverse.done", { number: "PMT-000318" })));
    // Unsigned, this would tell a clerk a SECOND payment of 292.87 had arrived.
    expect(html).toContain('<span class="cell-money-amount">-$292.87</span>');
    expect(html).toContain('<span class="cell-money-amount">$292.87</span>');
  });

  it("B14 rule 31: the re-opened bills are named by NUMBER, never by their id", () => {
    const html = panel();
    expect(html).toContain("BL-2607-018311");
    expect(html).toContain("BL-2608-018410");
    // Record links (PO 2026-10-19): the number OPENS the bill, whose address is
    // its id (`billDetailPath`). The id lives in the href and nowhere a person
    // reads — so strip the attribute before asking rule 31's question.
    expect(html).toContain('href="/acme/billing/bills/inv-018311"');
    const visible = html.replace(/href="[^"]*"/g, "");
    expect(visible).not.toContain("inv-018311");
    expect(visible).not.toContain("inv-018410");
  });

  it("a bill the row cannot name states the absence instead of printing the id", () => {
    const html = panel(reversed(), payment({ applied_to: [] }));
    expect(html).toContain(escaped(t("payments.row.billNumberUnavailable")));
    expect(html).not.toContain("inv-018311");
  });

  it("a null bounce count is NOT zero — it says the count did not run", () => {
    const html = panel(reversed({ nsf_count: null }));
    expect(html).toContain(escaped(t("payments.reverse.nsfCountUnknown")));
    expect(html).not.toContain(`${t("payments.reverse.nsfCountLabel")}</dt><dd>0<`);
  });

  it("OQ-132: a credit position BELOW zero is shown as the debt it is", () => {
    const html = panel(reversed({ credit_position_after: "-57.130000" }));
    expect(html).toContain('<span class="cell-money-amount">-$57.13</span>');
  });

  it("the bank fee is stated either way — silence would leave it ambiguous", () => {
    expect(panel()).toContain(escaped(t("payments.reverse.bankFeeNone")));
    expect(panel(reversed({ bank_fee: "12.500000", bank_fee_entry_id: "je-78" }))).toContain(
      escaped(t("payments.reverse.bankFeePosted")),
    );
  });

  it("the server's own problems are rendered, not swallowed", () => {
    // The customer's returned-cheque fee is billing's charge code and this path
    // deliberately does not add it — every result says so.
    expect(panel()).toContain(escaped(t("payments.problem.nsf_fee_not_added")));
  });

  it("a REPLAY is not congratulated as a second bounce", () => {
    const html = panel(reversed({ created: false }));
    expect(html).toContain(escaped(t("payments.reverse.replay")));
    expect(html).not.toContain(escaped(t("payments.reverse.done", { number: "PMT-000318" })));
  });
});

describe("DEF-3030 · the panel that contradicted the control is gone", () => {
  it("the catalogue no longer defines the false absence claim, in any language", () => {
    // It said reversing a payment and issuing a refund "are not built" and that
    // OQ-132 and OQ-133 were open. All three clauses were false. `t()` returns
    // the KEY when nothing defines it, which is exactly what this asserts.
    expect(t("payments.list.awaits.actions")).toBe("payments.list.awaits.actions");
    expect(t("payments.list.awaits.actionsTitle")).toBe("payments.list.awaits.actionsTitle");
  });

  it("the ONE panel that is still true keeps its copy", () => {
    // ⚠ **THIS ASSERTED TWO PANELS UNTIL 2026-09-03, AND THE SECOND ONE
    // STOPPED BEING TRUE (CR-059 CS-40, `DEF-3504`).** The date-range panel said
    // the list *"already answers a posted-date range and a cleared-date range,
    // and this page cannot yet offer them"*. It can now: `TableFilterConfig`
    // grew a `dateRange` descriptor, `FilterBar` draws it, and
    // `paymentsFilters` declares both ranges on the server's own param names.
    // Its keys are deleted from all eleven catalogues and `PaymentsPage.test`
    // asserts they no longer resolve -- exactly what this block did for the
    // reverse/refund panel when those routes landed.
    //
    // The lockbox import panel is untouched and is STILL TRUE: `CS-2` is
    // unbuilt, and the posting-date rule it names is still open.
    expect(t("payments.list.awaits.import")).not.toBe("payments.list.awaits.import");
    expect(t("payments.list.awaits.filters")).toBe("payments.list.awaits.filters");
  });
});
