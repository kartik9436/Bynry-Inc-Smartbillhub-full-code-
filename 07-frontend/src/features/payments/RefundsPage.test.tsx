// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-6 · CS-7 · task 18 — P3, the whole refunds page (S58).
//           Its backend half is task 17 (raise · issue · clear).
// Story:    US-PAY-011 (refunds) · J15 steps 1–4
//           Screens: S58
// Rules:    BR-PAY-014 (Admin approval; check/ACH v1; DR 2400 / CR 1000) ·
//           BR-PAY-037 (one user MAY raise and approve in v1, as long as both
//           acts are recorded separately) · BR-PAY-1071 (issue and clear carry
//           a SERVICE role gate) · BR-SHL-025 (disabled WITH its reason, never
//           hidden) · B14 rule 15 (row actions are ICONS) · B14 rule 31 (no
//           database id is the visible value of a field) · CLAUDE.md rule 2
// Ruling:   OQ-135 (2026-08-12, CLOSED — offset first) · OQ-132 (2026-08-11,
//           CLOSED — a credit may go below zero)
// ───────────────────────────────────────────────────────
// §4 test data is `PE-9`, verbatim: Marcus (Clerk) raises **57.13** against
// `ACC-1042` as cheque **#10241**, Dana (Admin) approves and issues it, and the
// credit goes to **0.00**. An Executive records the cheque clearing five days
// later and **no journal entry is written** — the money left at issue.
//
// THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES. This screen must not
// hide an act from the role that may not run it, must not print a refund's
// payment id or a raiser's user id, must not offer a `card` method BR-PAY-014
// does not have, and must not claim a credit position that no step reported.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentRow, RefundRow } from "@/api/endpoints";
import { FINANCE_TABS } from "@/features/ledger/financeShared";
import { ToastProvider } from "@/components/Toast";

import {
  CreditPositionPanel,
  REFUND_ACT_COPY,
  RefundRowActions,
  paymentPickerLabel,
  raiseRefundSchema,
  refundActBlockedReason,
  refundActSchema,
  refundStatusTone,
  refundsQueryKey,
} from "./RefundsPage";
// CR-060 C25 / T10 — the door the tab used to be. See the reachability block
// at the foot of this file.
import { RefundsQueuePanel, refundsQueuePanelQueryKey } from "./RefundsQueuePanel";
import { REFUNDS_LEGACY_ROUTE, REFUNDS_ROUTE } from "./paymentsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/** PE-9's refund, as `selectors.refund_row` serves it. */
function refund(over: Partial<RefundRow> = {}): RefundRow {
  return {
    id: "ref-9001",
    payment_id: "pay-8842",
    // ⚠ `P3.3` — `RefundRow` gained `account_id`, which the server has served
    // since `CR-059` CS-7 and the type omitted. `payments/0018` makes the
    // column NOT NULL, so a fixture without one describes a row that cannot
    // exist: a refund with no account is a cheque with no addressee.
    account_id: "acc-1042",
    amount: "57.130000",
    currency: "USD",
    status: "requested",
    method: "check",
    reference: "10241",
    reason: "overpaid twice",
    requested_by: "user-marcus",
    requested_at: "2026-08-18T00:00:00Z",
    approved_by: null,
    approved_at: null,
    issued_at: null,
    cleared_at: null,
    voided_at: null,
    void_reason: null,
    journal_entry_id: null,
    void_journal_entry_id: null,
    ...over,
  };
}

/**
 * ⚠ **`RefundsTable` WAS MOUNTED HERE UNTIL 2026-09-23 (`CR-138-BRC07`
 * `P4.26`), AND THE CASES BELOW SPLIT IN TWO WHEN IT WENT.**
 *
 * That component was a bespoke seven-column `PlainTable` with no toolbar, no
 * filter, no column chooser and no pagination footer. 6·1's list is
 * `RefundsAndCreditsList` on the kit's `DataTable` now, and what survived the
 * replacement is `RefundRowActions` — **the four acts, which are the half that
 * was load-bearing**. The cases that assert the ACTS mount it here and are
 * otherwise unchanged; the cases that asserted a CELL of the old table moved to
 * `refundsAndCredits.dom.test.tsx`, where those cells now live, and are named
 * in this file where they left so nobody thinks they were dropped.
 */
function acts(
  row: RefundRow,
  props: { role?: string | null } = {},
): string {
  return renderToStaticMarkup(
    <ToastProvider>
      <RefundRowActions
        refund={row}
        role={props.role === undefined ? "system_admin" : props.role}
        t={t}
        onAct={() => undefined}
        onCorrect={() => undefined}
      />
    </ToastProvider>,
  );
}

describe("CS-6 · five acts, five gates, and every refusal is the SERVICE's", () => {
  it("BR-PAY-014: only an Admin may approve, issue or void", () => {
    for (const act of ["approve", "issue", "void"] as const) {
      const row = refund({ status: act === "approve" ? "requested" : "issued" });
      expect(refundActBlockedReason(act, row, "billing_clerk", t)).toBe(
        t("payments.refunds.adminOnly"),
      );
      expect(refundActBlockedReason(act, row, "executive", t)).toBe(
        t("payments.refunds.adminOnly"),
      );
    }
  });

  it("CS-6: clearing is *a bank fact, not an approval* — Admin OR Executive", () => {
    const issued = refund({ status: "issued" });
    expect(refundActBlockedReason("clear", issued, "executive", t)).toBeNull();
    expect(refundActBlockedReason("clear", issued, "system_admin", t)).toBeNull();
    // A Billing Clerk is refused, which is NARROWER than yesterday — this
    // service accepted anybody at all before BR-PAY-1071.
    expect(refundActBlockedReason("clear", issued, "billing_clerk", t)).toBe(
      t("payments.refunds.adminOrExecutiveOnly"),
    );
  });

  it("a role the server has not answered for yet is OFFERED the act", () => {
    // The service's own @require_role is the boundary either way; withholding a
    // control on a pending read teaches a rule that does not exist.
    expect(refundActBlockedReason("approve", refund(), null, t)).toBeNull();
    expect(refundActBlockedReason("clear", refund({ status: "issued" }), null, t)).toBeNull();
  });

  it("the STATUS ladder is the service's own, act by act", () => {
    const admin = "system_admin";
    // requested → approve only
    expect(refundActBlockedReason("approve", refund(), admin, t)).toBeNull();
    expect(refundActBlockedReason("issue", refund(), admin, t)).toBe(
      t("payments.refunds.issueUnavailable"),
    );
    expect(refundActBlockedReason("void", refund(), admin, t)).toBe(
      t("payments.refunds.voidUnavailable"),
    );
    // approved → issue only
    const approved = refund({ status: "approved" });
    expect(refundActBlockedReason("issue", approved, admin, t)).toBeNull();
    expect(refundActBlockedReason("approve", approved, admin, t)).toBe(
      t("payments.refunds.approveUnavailable"),
    );
    // issued → clear, and void
    const issued = refund({ status: "issued" });
    expect(refundActBlockedReason("clear", issued, admin, t)).toBeNull();
    expect(refundActBlockedReason("void", issued, admin, t)).toBeNull();
    // cleared → void only ("only a refund that has actually gone out")
    const cleared = refund({ status: "cleared" });
    expect(refundActBlockedReason("void", cleared, admin, t)).toBeNull();
    expect(refundActBlockedReason("clear", cleared, admin, t)).toBe(
      t("payments.refunds.clearUnavailable"),
    );
  });

  it("the ROLE is answered before the status, so a clerk reads one stable reason", () => {
    expect(refundActBlockedReason("issue", refund(), "billing_clerk", t)).toBe(
      t("payments.refunds.adminOnly"),
    );
  });
});

describe("CS-6 · the four acts on a refund row (S58 · 6·1)", () => {
  it("BR-SHL-025: all four acts render on every row, disabled WITH their reason", () => {
    const html = acts(refund(), { role: "billing_clerk" });
    for (const act of ["approve", "issue", "clear", "void"] as const) {
      expect(html).toContain(`aria-label="${escaped(t(`payments.refunds.action.${act}`))}"`);
    }
    expect(html).toContain(`title="${escaped(t("payments.refunds.adminOnly"))}"`);
    expect(html).toContain(`title="${escaped(t("payments.refunds.adminOrExecutiveOnly"))}"`);
    expect(html).toContain('disabled=""');
  });

  it("B14 rule 15: they are ICONS, not text links", () => {
    const html = acts(refund());
    expect(html).toContain("<svg");
    expect(html).not.toContain(`>${t("payments.refunds.action.approve")}<`);
  });

  it("B14 rule 31: no id of any kind rides in the act controls", () => {
    const html = acts(refund());
    expect(html).not.toContain("pay-8842");
    expect(html).not.toContain("user-marcus");
    expect(html).not.toContain("ref-9001");
  });

  it("BR-PAY-037: the act is never BLOCKED for the person who raised it", () => {
    // The rule is CONFIRMED and permits one user to initiate and approve in v1.
    // The MARKER that says *you raised this* is a column on the list now
    // (`RefundsAndCreditsList`'s `raised_by`) rather than a cell of the table
    // this component replaced — the divergence from the drawing and its reason
    // are on that prop. What belongs HERE is that the control still runs.
    const html = acts(refund(), { role: "system_admin" });
    expect(html).not.toContain(`title="${escaped(t("payments.refunds.adminOnly"))}"`);
  });

  // ⚠ **FIVE CASES LEFT THIS BLOCK ON 2026-09-23 AND NONE WAS DROPPED.** They
  // asserted CELLS of `RefundsTable`, which no longer exists: the cheque-number
  // absence, the unapproved-date absence, PE-9's money path, the empty state and
  // the id-fallback row. Every one of those cells is now
  // `refundsAndCreditsShared`'s, and the equivalents live in
  // `refundsAndCredits.dom.test.tsx` — including the stronger version of the
  // absence case, which now also covers a credit note's STATE. Named here rather
  // than deleted silently, because a case that vanishes with no note reads
  // exactly like a case somebody found inconvenient.
});

describe("CS-6 · the status vocabulary", () => {
  it("cleared is success, void is danger, and ISSUED is neither", () => {
    expect(refundStatusTone("cleared")).toBe("success");
    expect(refundStatusTone("void")).toBe("danger");
    expect(refundStatusTone("requested")).toBe("warning");
    // The money has left the building and the bank has not confirmed it. That
    // is a waiting state, not good news.
    expect(refundStatusTone("issued")).toBe("neutral");
  });

  it("all five REFUND_STATUSES have a sentence, in every catalogue", () => {
    for (const status of ["requested", "approved", "issued", "cleared", "void"]) {
      expect(t(`payments.refunds.status.${status}`)).not.toBe(
        `payments.refunds.status.${status}`,
      );
    }
  });
});

describe("CS-6/CS-7 · the raise form", () => {
  it("the schema requires an account, a payment, a positive amount and a date", () => {
    const schema = raiseRefundSchema(t);
    const good = {
      account_id: "acc-1042",
      payment_id: "pay-8842",
      amount: "57.13",
      requested_at: "2026-08-18",
    };
    expect(schema.safeParse(good).success).toBe(true);
    expect(schema.safeParse({ ...good, account_id: "" }).success).toBe(false);
    // CS-7 is unbuilt: `refunds.payment_id` is still NOT NULL, so the form must
    // still collect the payment behind the credit.
    expect(schema.safeParse({ ...good, payment_id: "" }).success).toBe(false);
    expect(schema.safeParse({ ...good, requested_at: "" }).success).toBe(false);
    // CLAUDE.md rule 2 — the amount is a STRING pattern, never parsed.
    expect(schema.safeParse({ ...good, amount: "0.00" }).success).toBe(false);
    expect(schema.safeParse({ ...good, amount: "-57.13" }).success).toBe(false);
    expect(schema.safeParse({ ...good, amount: "57,13" }).success).toBe(false);
  });

  it("B14 rule 31: the payment picker never falls back to the id", () => {
    const payment: PaymentRow = {
      id: "pay-8842",
      payment_no: "PMT-000241",
      account_id: "acc-1042",
      account_no: "ACC-1042",
      customer_name: null,
      type: "payment",
      method: null,
      method_name: null,
      confirmation: null,
      memo: null,
      amount: "292.870000",
      currency: "USD",
      status: "cleared",
      purpose: "bill",
      posted_at: "2026-07-14",
      cleared_at: "2026-07-16",
      applied_to: [],
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
    };
    expect(paymentPickerLabel(payment, t)).toContain("PMT-000241");
    const unnumbered = paymentPickerLabel({ ...payment, payment_no: null }, t);
    expect(unnumbered).toContain(t("payments.row.noNumber"));
    expect(unnumbered).not.toContain("pay-8842");
  });
});

describe("CS-6 · the act modals", () => {
  it("a void REQUIRES a reason; the other three do not", () => {
    expect(
      refundActSchema("void", t).safeParse({ acted_at: "2026-08-25", void_reason: "", reference: "" })
        .success,
    ).toBe(false);
    expect(
      refundActSchema("void", t).safeParse({
        acted_at: "2026-08-25",
        void_reason: "lost in post",
        reference: "",
      }).success,
    ).toBe(true);
    expect(
      refundActSchema("issue", t).safeParse({
        acted_at: "2026-08-20",
        void_reason: "",
        reference: "",
      }).success,
    ).toBe(true);
  });

  // ⚠ **THE THIRD CASE ABOVE STILL PASSES WITH AN EMPTY `reference`, AND THAT
  // IS NOT AN OVERSIGHT (`DEF-PAY-6331`).** The schema's third argument is the
  // METHOD, not the act: US-PAY-011 §5 is *"required for check"*, so an ACH
  // refund is issued with nothing in that field. The cheque case is the one
  // below, and both are needed — a rule asserted in only the direction that
  // refuses would pass just as well if it refused everything.
  it("issuing a CHEQUE requires its number; issuing a bank transfer does not", () => {
    const cheque = refundActSchema("issue", t, true);
    expect(cheque.safeParse({ acted_at: "2026-09-21", void_reason: "", reference: "" }).success).toBe(
      false,
    );
    expect(
      cheque.safeParse({ acted_at: "2026-09-21", void_reason: "", reference: "10307" }).success,
    ).toBe(true);
    const transfer = refundActSchema("issue", t, false);
    expect(
      transfer.safeParse({ acted_at: "2026-09-21", void_reason: "", reference: "" }).success,
    ).toBe(true);
  });

  it("every act names its own DATE field, so none can stamp the wrong column", () => {
    const dates = Object.values(REFUND_ACT_COPY).map((copy) => copy.date);
    expect(new Set(dates).size).toBe(4);
    for (const copy of Object.values(REFUND_ACT_COPY)) {
      for (const key of [copy.title, copy.date, copy.submit, copy.done]) {
        expect(t(key)).not.toBe(key);
      }
    }
  });

  it("BR-TEN-043: no act pre-fills its date from a clock", () => {
    const schema = refundActSchema("approve", t);
    expect(schema.safeParse({ acted_at: "", void_reason: "", reference: "" }).success).toBe(false);
  });
});

describe("CS-6 · the credit position is REPORTED, never cached", () => {
  it("it renders the figure the last step handed back", () => {
    const html = renderToStaticMarkup(
      <ToastProvider>
        <CreditPositionPanel amount="0.000000" currency="USD" onDismiss={() => undefined} />
      </ToastProvider>,
    );
    expect(html).toContain(escaped(t("payments.refunds.creditAfter")));
    // PE-9: the credit goes to 0.00 at issue. Shown, not hidden — "nothing is
    // left" is the fact a clerk needs.
    expect(html).toContain('<span class="cell-money-amount">$0.00</span>');
  });

  it("OQ-132: a position BELOW zero is shown as the debt it is", () => {
    const html = renderToStaticMarkup(
      <ToastProvider>
        <CreditPositionPanel amount="-57.130000" currency="USD" onDismiss={() => undefined} />
      </ToastProvider>,
    );
    expect(html).toContain('<span class="cell-money-amount">-$57.13</span>');
  });
});

describe("task 18 · the screen is REACHABLE", () => {
  // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-03, AND BOTH VERSIONS ARE
  // THE SAME REQUIREMENT.** It read *"the Finance tab strip names it — a screen
  // with no tab is a typed URL"* and was RIGHT to: the tab was the only door.
  // The PO then ruled the strip at six — asked directly, verbatim: *"C25 says
  // six tabs. - this is correct."* — and `CR-060` `C25` does not name Refunds.
  // **So the tab went and the door moved**, to `RefundsQueuePanel` inside
  // Revenue & AR, on `C25`'s own principle (a refund gives back money the
  // account holds as credit, and the credit position lives in that tab).
  //
  // The requirement never changed and neither did what this case is for: **a
  // screen with no door is a typed URL.** What changed is which surface is the
  // door — so the assertion checks BOTH halves, the tab's absence and the
  // panel's presence, because either one alone passes on a broken product.
  it("CR-060 C25 — Refunds is NOT a tab, and the ruling is what took it out", () => {
    expect(FINANCE_TABS.map((tab) => tab.id)).not.toContain("refunds");
    // The tab label key is NOT orphaned — it is the panel's heading now, so it
    // is still translated and still asserted. Removing it from eleven
    // catalogues would have been a second change nobody ruled on.
    expect(t("finance.tab.refunds")).not.toBe("finance.tab.refunds");
  });

  it("the door is the Revenue & AR panel, and it links to this page", () => {
    // Hard-won law 2 — *built is not wired*. The panel is the whole reason
    // removing the tab cost nothing, so a test that only checked the tab was
    // gone would go green on a refunds page nobody can reach.
    expect(RefundsQueuePanel).toBeTypeOf("function");
    // ⚠ **THIS READ `"/finance/refunds"` UNTIL 2026-09-23 AND THE CASE WENT RED
    // THE MOMENT `CR-138-BRC07` `P4.10` MOVED THE SCREEN — WHICH IS THIS CASE
    // WORKING.** The panel links by the CONSTANT, so its door followed the
    // screen without a line changing in `RefundsQueuePanel`; what had to change
    // is the literal pinned here. The supersedes chain for the move is on
    // `paymentsShared.REFUNDS_ROUTE`, and the old address still redirects.
    expect(REFUNDS_ROUTE).toBe("/payments/refunds");
    expect(REFUNDS_LEGACY_ROUTE).toBe("/finance/refunds");
    // Its link and its heading are keys the catalogues already carry; this
    // lane added none (another lane held the eleven catalogues).
    expect(t("payments.bulk.openRefundQueue")).not.toBe("payments.bulk.openRefundQueue");
  });

  it("the panel reads the SAME query key this page's waiting view does", () => {
    // Two literals, one queue. They are separate because importing this page
    // into `RevenueArPage` would drag five modals and zod into that bundle —
    // so the equality is pinned here instead of left to drift, which is the
    // only way a second key can quietly disagree about what is waiting.
    expect(refundsQueuePanelQueryKey).toEqual(refundsQueryKey("requested"));
  });

  it("the refund status vocabulary is the SERVER's, and no array in this file", () => {
    // ⚠ **`REFUND_FILTERS` STOOD HERE AND IS GONE (`P1.5` · `DEF-PAY-6557`).**
    // This case asserted its three values and that each `labelKey` resolved,
    // and the assertion was TRUE the whole time — over a control that no screen
    // had rendered since `P4.26` landed on 2026-09-23. A check passing over an
    // absence is hard-won law 7's *looking at the wrong thing*.
    //
    // **The reason the array was KEPT is what changed**, and it is worth
    // writing down rather than deleting: the case above it argued *"deleting
    // the constant would take the queue's vocabulary with it"*, which was
    // correct — `GET /refunds` took `f.status` and nothing else served the five
    // words. `P1.5` serves them: the queue's envelope now carries `statuses`
    // and `methods` off `models.REFUND_STATUSES` and `models.REFUND_METHODS`,
    // so the vocabulary has a home that is not a literal in a screen, and a
    // sixth status added server-side appears with no front-end change.
    //
    // What this asserts instead is that the CATALOGUE can still say all five
    // words — the half the old case was actually protecting. The server sends
    // `payments.refunds.status.<value>` and a key that resolved to itself would
    // reach a clerk as the raw enum.
    for (const status of ["requested", "approved", "issued", "cleared", "void"]) {
      expect(t(`payments.refunds.status.${status}`)).not.toBe(
        `payments.refunds.status.${status}`,
      );
    }
    for (const method of ["check", "ach"]) {
      expect(t(`payments.refunds.method.${method}`)).not.toBe(
        `payments.refunds.method.${method}`,
      );
    }
  });
});
