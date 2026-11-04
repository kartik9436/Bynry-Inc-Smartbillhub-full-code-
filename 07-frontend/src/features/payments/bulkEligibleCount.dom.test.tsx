// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-135` `P1.8` — §03 frame 2·1b *Bulk* (p031–p033), read at 2.0.
//           *To build:* *"The eligible count on the bar · the per-row confirm ·
//           a consequence box"*. Outcome: **"The button reads *Reverse 2*,
//           never *Reverse 3*."**
// Screens:  2·1b · S33
// Rules:    B14 rule 11 (a consequence preview before a money commit) ·
//           rule 12 (ONE toolbar) · rule 15 · rule 31 (no database id on
//           screen) · rule 32 · rule 33 · hard rule 2 (money is a decimal
//           string, never a float)
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE GAP THIS CLOSES, IN THE BLUEPRINT'S OWN WORDS
// ══════════════════════════════════════════════════════════════════════════
// *"`bulkActionRefusal` returns "allowed" if ANY selected row can be acted on.
// Select five payments where one is reversible and four are not, and the button
// is live, bright, and says nothing. The confirm that follows takes **only a
// count** — it asks "Reverse 5 payments?" when it is about to reverse one and
// silently refuse four. You find out afterwards, per row."*
//
// ⚠ **SO EVERY CASE BELOW USES A MIXED SELECTION.** A selection where every row
// qualifies passes on the OLD code and the NEW one alike — three eligible rows
// make *"Reverse 3"* correct either way — so a suite built on the happy path
// would be green over the whole defect. The fixture is two reversible payments
// and one that is already a reversal, which is exactly the drawing's own.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentRow } from "@/api/endpoints";

import {
  BulkRefundModal,
  BulkReverseModal,
  EMPTY_SELECTION,
  PaymentsBulkBar,
  reversalConsequence,
  splitSelection,
  toggleSelected,
} from "./paymentsBulk";
import type { PaymentSelection, SelectionTotalResponse } from "./paymentsBulk";
import type { Translator } from "@/features/tenancy/settingsShared";

const t: Translator = (key, params) => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-1",
    payment_no: "PMT-2609-000418",
    account_id: "acc-1",
    account_no: "AC-2026-00001",
    customer_name: "Ana Alvarez",
    type: "payment",
    method: "check",
    method_name: "Cheque",
    confirmation: "4471",
    memo: null,
    amount: "158.100000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-09-21",
    cleared_at: "2026-09-21",
    applied_to: [
      { invoice_id: "inv-85", invoice_number: "BL-2609-000085", amount: "158.100000" },
    ],
    applied_total: "158.100000",
    deposit_batch_id: null,
    receipt_no: null,
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

/**
 * 2·1b's own three rows: two cleared payments on two accounts, and one that is
 * already a reversal and therefore cannot be reversed again.
 *
 * The amounts are the drawing's, and they are what makes the consequence figure
 * checkable: `158.10 + 120.00 = 278.10`, on TWO accounts, over TWO bills.
 */
const DRAWN_THREE: PaymentRow[] = [
  payment({ id: "p418", payment_no: "PMT-2609-000418", amount: "158.100000" }),
  payment({
    id: "p417",
    payment_no: "PMT-2609-000417",
    account_id: "acc-24",
    account_no: "AC-2026-00024",
    amount: "120.000000",
    applied_to: [
      { invoice_id: "inv-81", invoice_number: "BL-2609-000081", amount: "120.000000" },
    ],
  }),
  payment({
    id: "p412",
    payment_no: "PMT-2609-000412",
    account_id: "acc-31",
    account_no: "AC-2026-00031",
    amount: "802.430000",
    status: "reversed",
    applied_to: [
      { invoice_id: "inv-79", invoice_number: "BL-2609-000079", amount: "802.430000" },
    ],
  }),
];

function selectionOf(rows: readonly PaymentRow[]): PaymentSelection {
  let selection = EMPTY_SELECTION;
  for (const row of rows) {
    selection = toggleSelected(selection, row);
  }
  return selection;
}

const SERVED: SelectionTotalResponse = {
  requested: 3,
  count: 3,
  amount: "1080.530000",
  amount_display: "1080.53",
  currency: "USD",
  amount_unavailable: null,
  excluded_count: 0,
};

function bar(rows: readonly PaymentRow[] = DRAWN_THREE): string {
  return renderToStaticMarkup(
    <PaymentsBulkBar
      selection={selectionOf(rows)}
      role="system_admin"
      currency="USD"
      total={SERVED}
      running={null}
      progress={null}
      onClear={() => undefined}
      onReverse={() => undefined}
      onRefund={() => undefined}
      onSendReceipts={() => undefined}
      onReapply={() => undefined}
    />,
  );
}

function reverseConfirm(rows: readonly PaymentRow[] = DRAWN_THREE): string {
  return renderToStaticMarkup(
    <BulkReverseModal
      rows={rows}
      role="system_admin"
      currency="USD"
      dateFormat="MM/DD/YYYY"
      onClose={() => undefined}
      onConfirm={() => undefined}
    />,
  );
}

describe("P1.8 · ② the bar says what can ACTUALLY happen", () => {
  it("the button reads Reverse 2, never Reverse 3", () => {
    const html = bar();
    expect(html).toContain(escaped(t("payments.bulk.action.reverseCount", { count: 2 })));
    expect(html).not.toContain(escaped(t("payments.bulk.action.reverseCount", { count: 3 })));
  });

  it("and it names the split beside it — 2 can be reversed · 1 cannot", () => {
    expect(bar()).toContain(
      escaped(t("payments.bulk.eligible.reverse", { can: 2, cannot: 1 })),
    );
  });

  it("a selection with nothing skipped carries NO split sentence (B14 rule 32)", () => {
    // A permanent "3 can be reversed · 0 cannot" is noise on a bar a clerk
    // reads before pressing a danger-tier button.
    const clean = [DRAWN_THREE[0], DRAWN_THREE[1]];
    expect(bar(clean)).not.toContain("can be reversed");
  });

  it("the TICK count is still the tick count — the two figures answer two questions", () => {
    // *"how many did I tick"* stays 3. The button's figure is *"how many will
    // run"*, and conflating them is how the old confirm came to lie.
    expect(bar()).toContain(escaped(t("payments.bulk.selected", { count: 3 })));
  });
});

describe("P1.8 · ④⑤ the confirm is per row, and names who is skipped", () => {
  it("2 of 3 will be reversed, and the sentence says so before the table", () => {
    const html = reverseConfirm();
    expect(html).toContain(
      escaped(t("payments.bulk.willRun", { run: 2, total: 3, skipped: 1 })),
    );
  });

  it("every selected row is drawn — including the one that will NOT run", () => {
    const html = reverseConfirm();
    for (const row of DRAWN_THREE) {
      expect(html).toContain(`data-preview-row="${row.id}"`);
    }
    expect(html).toContain('data-preview-skipped="true"');
    expect(html).toContain('data-preview-skipped="false"');
  });

  it("the skipped row carries the REASON it will be skipped, not a blank", () => {
    // Note ④ is *"Who is skipped, **and why**"*, and the reason is the row
    // action's own sentence — `bulkReverseRefusal`, the same predicate the run
    // uses. A screen that refused something the row Reverse allows would be
    // two answers to one rule on one page.
    expect(reverseConfirm()).toContain(escaped(t("payments.reverse.isReversal")));
  });

  it("no database id reaches the clerk — the payment NUMBER, never the uuid (B14 rule 31)", () => {
    const html = reverseConfirm();
    expect(html).toContain("PMT-2609-000418");
    expect(html).toContain("AC-2026-00024");
    // The uuid rides on the `data-` hook, which is markup a person never reads;
    // it must not be a VISIBLE value. Read as text, not as markup — rule 31's
    // own sentence puts the internal value somewhere a support engineer can
    // find it.
    expect(html).not.toContain(">p418<");
  });

  it("the title and the submit both carry the figure that will RUN", () => {
    const html = reverseConfirm();
    expect(html).toContain(escaped(t("payments.bulk.reverseTitle", { count: 2 })));
    expect(html).toContain(escaped(t("payments.bulk.reverseSubmit", { count: 2 })));
    expect(html).not.toContain(escaped(t("payments.bulk.reverseSubmit", { count: 3 })));
  });

  it("⑥ one reason for all of them, said out loud under the Why field", () => {
    expect(reverseConfirm()).toContain(escaped(t("payments.bulk.reverseWhyHelp")));
  });
});

describe("P1.8 · ⑦ what it will do, in the customer's terms (B14 rule 11)", () => {
  it("$278.10 goes back to 2 accounts, and 2 bills re-open", () => {
    // ⚠ **THE ARITHMETIC IS THE ASSERTION.** 158.10 + 120.00 = 278.10 over the
    // two ELIGIBLE rows; the skipped 802.43 is not in it, which is the whole
    // reason this figure differs from the bar's $1,080.53 above. Counted with
    // `sumDecimalStrings` on the storage grid — never a float (hard rule 2).
    const consequence = reversalConsequence([DRAWN_THREE[0], DRAWN_THREE[1]]);
    expect(consequence.amount).toBe("278.100000");
    expect(consequence.accounts).toBe(2);
    expect(consequence.bills).toBe(2);

    const html = reverseConfirm();
    expect(html).toContain('data-consequence="bulk-reverse"');
    expect(html).toContain("278.10");
    expect(html).toContain(escaped(t("payments.bulk.consequence.bills", { count: 2 })));
  });

  it("the consequence counts the ELIGIBLE rows only, never the whole selection", () => {
    // The mirror, and the one that would catch a lane "simplifying" the split
    // away: over all three rows the money would read $1,080.53 and three
    // accounts — a promise to move money the run will not move.
    const all = reversalConsequence(DRAWN_THREE);
    expect(all.amount).toBe("1080.530000");
    expect(reverseConfirm()).not.toContain("1,080.53");
  });

  it("nothing eligible draws NO consequence box — a box promising nothing is worse", () => {
    const html = reverseConfirm([DRAWN_THREE[2]]);
    expect(html).not.toContain('data-consequence="bulk-reverse"');
  });
});

describe("P1.8 · the refund confirm is the same shape, and the drawing draws only one", () => {
  it("a processing payment is skipped, and the refund figure follows the split", () => {
    // Recorded as this lane's judgment in the decision log: 2·1b draws the
    // REVERSAL's confirm, and its GAP box — *"a bulk reversal writes money
    // across several accounts and shows no 'what this will do' box at all"* —
    // is true word for word of a bulk refund. Two forms one step apart, one
    // asking per row and one asking for a count, teaches a clerk two habits.
    const rows = [
      payment({ id: "r1", payment_no: "PMT-2609-000501" }),
      payment({ id: "r2", payment_no: "PMT-2609-000502", status: "processing" }),
    ];
    const html = renderToStaticMarkup(
      <BulkRefundModal
        rows={rows}
        currency="USD"
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onConfirm={() => undefined}
      />,
    );
    expect(html).toContain(escaped(t("payments.bulk.refundSubmit", { count: 1 })));
    expect(html).toContain(escaped(t("payments.bulk.refundNotCleared")));
    expect(html).toContain('data-preview-skipped="true"');
  });
});

describe("DEF-PAY-10703 (lockbox audit LBX-10) · ONE payment reads as one, never as *1 payments*", () => {
  // ⚠ **LITERAL ENGLISH, NOT `t(key)`.** Every case above compares the markup
  // with `t(key, { count })`, which renders the same wrong plural on both
  // sides and so passes over the defect — the shape `DEF-CWP-4873` was.
  const ONE = [DRAWN_THREE[0]];

  it("the reverse confirm says Reverse 1 payment, $158.10 goes back to 1 account., 1 bill re-opens.", () => {
    const html = reverseConfirm(ONE);
    expect(html).toContain("Reverse 1 payment<");
    expect(html).not.toContain("1 payments");
    expect(html).toContain("$158.10 goes back to 1 account.");
    expect(html).not.toContain("1 accounts");
    expect(html).toContain("1 bill re-opens.");
    expect(html).not.toContain("1 bills");
  });

  it("two still read as two", () => {
    const html = reverseConfirm();
    expect(html).toContain("Reverse 2 payments");
    expect(html).toContain("goes back to 2 accounts.");
    expect(html).toContain("2 bills re-open.");
  });

  it("the sibling refund confirm says Refund 1 payment and Raise 1 refund", () => {
    const html = renderToStaticMarkup(
      <BulkRefundModal
        rows={ONE}
        currency="USD"
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onConfirm={() => undefined}
      />,
    );
    expect(html).toContain("Refund 1 payment<");
    expect(html).toContain("Raise 1 refund<");
    expect(html).not.toContain("1 payments");
    expect(html).not.toContain("1 refunds");
  });

  it("every catalogue carries both forms of every counted Reverse/Refund string", () => {
    for (const key of [
      "payments.bulk.consequence.accounts",
      "payments.bulk.consequence.bills",
      "payments.bulk.consequence.money",
      "payments.bulk.reverseSubmit",
      "payments.bulk.reverseTitle",
      "payments.bulk.refundSubmit",
      "payments.bulk.refundTitle",
    ]) {
      const resources = (i18n.options.resources ?? {}) as Record<string, Record<string, Record<string, string>>>;
      const langs = Object.keys(resources);
      expect(langs.length).toBe(11);
      for (const lang of langs) {
        for (const bundle of Object.values(resources[lang])) {
          expect(typeof bundle[`${key}_one`], `${lang} ${key}_one`).toBe("string");
          expect(typeof bundle[`${key}_other`], `${lang} ${key}_other`).toBe("string");
          expect(bundle[key], `${lang} ${key} retired`).toBeUndefined();
        }
      }
    }
  });
});

describe("P1.8 · the split calls the run's own predicate and adds no rule", () => {
  it("splitSelection returns the same verdict the run will reach, per row", () => {
    // ⚠ **THE CASE THAT STOPS THE TWO DRIFTING.** The blueprint's fix is
    // *"showing what is already computed"* — a second rule here would be a
    // screen that says one thing before the button and does another after it,
    // over money.
    const split = splitSelection(DRAWN_THREE, (row) =>
      row.status === "reversed" ? "no" : null,
    );
    expect(split.eligible.map((row) => row.id)).toEqual(["p418", "p417"]);
    expect(split.skipped.map((entry) => entry.row.id)).toEqual(["p412"]);
    expect(split.skipped[0]?.reason).toBe("no");
  });

  it("an amount that is not a decimal produces NO money figure rather than NaN", () => {
    // Hard rule 2: money never becomes a float. `sumDecimalStrings` answers
    // null, and the box then states what it can — the account count — instead
    // of printing a guess.
    const broken = reversalConsequence([payment({ amount: "not-a-number" })]);
    expect(broken.amount).toBeNull();
    expect(broken.accounts).toBe(1);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p14 `P1.8` · §03 frame 2·1b (p031–p033) rendered at 2.0
// generated: 2026-09-22 by LANE P1-C
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/bulkEligibleCount.dom.test.tsx · tsc --noEmit
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
