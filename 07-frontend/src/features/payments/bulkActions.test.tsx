// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-41 "select payments and act on them" · CS-43 "total a
//           selection on the server" (screen half) · CS-44 (the Batch column).
// Story:    US-PAY-004  Screens: S33 · S21
// Rules:    BR-SHL-025 · BR-SHL-013 · BR-PAY-014 · BR-PAY-021 · BR-PAY-028 ·
//           CLAUDE.md hard rule 2 · B14 rule 31 · B14 rule 33
// Defects:  DEF-3505 · DEF-2352 (the Batch cell would print a uuid)
// ───────────────────────────────────────────────────────
// §3's figures are CR-059 §0d.2's own acceptance lines, unchanged:
//
//   CS-41 — *"a clerk ticks three payments, a bar reads '3 selected ·
//   1,242.87', they press Refund, and three refunds appear as pending"*.
//   620.00 + 380.00 + 242.87 = **1,242.87**.
//
//   CS-43 — *"four rows selected on page one and two on page two show
//   '6 selected · 3,918.44' — not a blank"*.
//   1,242.87 + 988.70 + 412.50 + 274.37 on page one, 620.00 + 380.00 on page
//   two = **3,918.44**.
//
// ⚠ **THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES**, and each one is a
// defect that has actually happened somewhere in this repo: the total must not
// silently shrink when the page turns, a run must not lose the rows that
// succeeded when one fails, a retry must not mint a new idempotency key, and no
// cell and no result line may print a database id at a clerk.
//
// RED FIRST (hard-won law 7) — each proof is quoted beside the case it belongs
// to, taken by breaking the source and running these tests before restoring it.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentRow } from "@/api/endpoints";

import {
  BulkRunPanel,
  EMPTY_SELECTION,
  PaymentsBulkBar,
  bulkActionRefusal,
  bulkRefundRefusal,
  bulkReverseRefusal,
  deselectMany,
  failedRows,
  keyFor,
  refreshSelection,
  runPerRow,
  runTally,
  succeededIds,
  toggleSelected,
} from "./paymentsBulk";
import type { BulkRun, PaymentSelection, SelectionTotalResponse } from "./paymentsBulk";
import { paymentsCells, paymentsTableConfig } from "./PaymentsPage";
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
    payment_no: "PMT-2608-000412",
    account_id: "acc-1",
    account_no: "2608-0141",
    customer_name: "Ridge Coffee Co.",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: "8842",
    memo: null,
    amount: "620.000000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-08-08",
    cleared_at: "2026-08-10",
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
    ...over,
  };
}

function selectionOf(rows: readonly PaymentRow[]): PaymentSelection {
  let selection = EMPTY_SELECTION;
  for (const row of rows) {
    selection = toggleSelected(selection, row);
  }
  return selection;
}

/** CS-41's own three. */
const THREE: PaymentRow[] = [
  payment({ id: "p1", payment_no: "PMT-2608-000412", amount: "620.000000" }),
  payment({ id: "p2", payment_no: "PMT-2608-000413", amount: "380.000000" }),
  payment({ id: "p3", payment_no: "PMT-2608-000414", amount: "242.870000" }),
];

/** CS-43's page one. */
const PAGE_ONE: PaymentRow[] = [
  payment({ id: "a1", payment_no: "PMT-2608-000401", amount: "1242.870000" }),
  payment({ id: "a2", payment_no: "PMT-2608-000402", amount: "988.700000" }),
  payment({ id: "a3", payment_no: "PMT-2608-000403", amount: "412.500000" }),
  payment({ id: "a4", payment_no: "PMT-2608-000404", amount: "274.370000" }),
];

/** …and its page two. */
const PAGE_TWO: PaymentRow[] = [
  payment({ id: "b1", payment_no: "PMT-2608-000411", amount: "620.000000" }),
  payment({ id: "b2", payment_no: "PMT-2608-000412", amount: "380.000000" }),
];

/** What `POST /payments/selection-total` answers, shape for shape. */
function served(over: Partial<SelectionTotalResponse> = {}): SelectionTotalResponse {
  return {
    requested: 3,
    count: 3,
    amount: "1242.870000",
    amount_display: "1242.87",
    currency: "USD",
    amount_unavailable: null,
    excluded_count: 0,
    ...over,
  };
}

/**
 * ⚠ **`"unread"` IS A SENTINEL AND NOT A TIDY-UP.** Written as
 * `total: SelectionTotalResponse | undefined = served()`, passing `undefined`
 * EXPLICITLY still takes the default — that is what a JS default parameter
 * does — so the unread branch was unreachable and its case asserted the served
 * figure while claiming to assert its absence. The suite caught it:
 *     AssertionError: expected '<div class="pay-bulk"...' to contain
 *       'No total to show yet'
 * A test that cannot reach the branch it names is the shape DEF-182 calls worse
 * than no check, because it is trusted.
 */
function bar(
  selection: PaymentSelection,
  role: string | null = "system_admin",
  total: SelectionTotalResponse | "unread" = served(),
): string {
  return renderToStaticMarkup(
    <PaymentsBulkBar
      selection={selection}
      role={role}
      currency="USD"
      total={total === "unread" ? undefined : total}
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

describe("CS-41 · the bar reads what is ticked", () => {
  it("three ticked payments read '3 selected' and 1,242.87 — the CR's own line", () => {
    const html = bar(selectionOf(THREE));
    expect(html).toContain(escaped(t("payments.bulk.selected", { count: 3 })));
    expect(html).toContain("1,242.87");
  });

  it("an untick removes exactly that row and nothing else", () => {
    const three = selectionOf(THREE);
    const two = toggleSelected(three, THREE[1]);
    expect(two.size).toBe(2);
    expect(two.has("p2")).toBe(false);
  });

  it("the COUNT is the tick count and does not wait for the server", () => {
    // Two different questions. The count is *"how many did I tick"* — the map's
    // size, instant, and it cannot flicker while a request is in flight. The
    // server's `count` is *"how many of those this tenant still has"*, which is
    // legitimately smaller when a selection has gone stale.
    const html = bar(selectionOf(THREE), "system_admin", "unread");
    expect(html).toContain(escaped(t("payments.bulk.selected", { count: 3 })));
  });
});

describe("CS-43 · the selection survives the page turning", () => {
  // ⚠ RED FIRST, PROVED. Rebuilding the selection from the CURRENT PAGE — which
  // is what S34 does, and what CR-059 §0d.2 names as the reason CS-43 blocks
  // CS-41 — was put back into `refreshSelection` and this case reported:
  //     AssertionError: expected 2 to be 6 // Object.is equality
  // The four page-one rows are not in `rows` any more, so they leave the COUNT
  // and the TOTAL together, with nothing on screen saying a number changed
  // meaning.
  it("four on page one plus two on page two read '6 selected · 3,918.44', not a blank", () => {
    let selection = selectionOf(PAGE_ONE);
    // The clerk pages. The list response is now page two only — exactly the
    // state that makes an id-list selection lie.
    selection = refreshSelection(selection, PAGE_TWO);
    for (const row of PAGE_TWO) {
      selection = toggleSelected(selection, row);
    }
    expect(selection.size).toBe(6);

    // The MONEY is the server's — `POST /payments/selection-total` over these
    // six ids — because CS-35 makes the figure the day's CASH and a browser sum
    // of every ticked row would put a credit into it.
    const html = bar(
      selection,
      "system_admin",
      served({ requested: 6, count: 6, amount: "3918.440000", amount_display: "3918.44" }),
    );
    expect(html).toContain(escaped(t("payments.bulk.selected", { count: 6 })));
    expect(html).toContain("3,918.44");
    // CS-43's acceptance line in its own words: *"not a blank"*.
    expect(html).not.toContain(escaped(t("payments.bulk.totalUnread")));
  });

  it("a selected row that comes back on a later page is re-snapshotted", () => {
    // The rows are still HELD even though the money is the server's: the per-row
    // refusals read `status` and `amount`, and `refundOne` sends each payment's
    // own account and amount. A held row can be older than what the server would
    // answer now, so the ones a clerk can SEE are refreshed.
    const selection = selectionOf([PAGE_ONE[0]]);
    const moved = refreshSelection(selection, [{ ...PAGE_ONE[0], amount: "1000.000000" }]);
    expect(moved.get("a1")?.amount).toBe("1000.000000");
  });

  it("a row that is NOT on this page keeps the snapshot it was ticked with", () => {
    const selection = selectionOf(PAGE_ONE);
    const after = refreshSelection(selection, PAGE_TWO);
    expect(after.size).toBe(4);
    expect(after.get("a1")?.amount).toBe("1242.870000");
  });

  it("an empty selection is returned unchanged, so no render loop can start", () => {
    expect(refreshSelection(EMPTY_SELECTION, PAGE_ONE)).toBe(EMPTY_SELECTION);
  });
});

describe("CS-43 · a figure that cannot be stated says so, and never shows a number", () => {
  // ⚠ **THE THREE REASONS ARE THE FILTER TOTALS LINE'S OWN KEYS**, so one
  // screen does not explain the same absence in two vocabularies. The server
  // groups on the same three codes for the same reason.
  it("two currencies produce NO total and name the reason", () => {
    const selection = selectionOf([
      payment({ id: "u", amount: "620.000000", currency: "USD" }),
      payment({ id: "e", amount: "380.000000", currency: "EUR" }),
    ]);
    const html = bar(
      selection,
      "system_admin",
      served({ requested: 2, count: 2, amount: null, amount_display: null, currency: null, amount_unavailable: "mixed_currencies" }),
    );
    expect(html).toContain(escaped(t("payments.totals.unavailable.mixed_currencies")));
    // Adding 620.00 USD to 380.00 EUR is not 1,000.00 of anything.
    expect(html).not.toContain("1,000.00");
  });

  it("a selection holding only credits says so rather than reading $0.00", () => {
    // CS-35: the figure is the day's CASH. "0.00" here would claim these rows
    // are worth nothing, which is a different and wrong sentence.
    const html = bar(
      selectionOf([payment({ id: "c", type: "credit" })]),
      "system_admin",
      served({ requested: 1, count: 1, amount: null, amount_display: null, currency: null, amount_unavailable: "no_cash_rows", excluded_count: 1 }),
    );
    expect(html).toContain(escaped(t("payments.totals.unavailable.no_cash_rows")));
    expect(html).not.toContain("0.00");
  });

  it("CS-35 · the bar says how many ticked rows the CASH figure left out", () => {
    // A total that silently covered a credit would tie to nothing. The count is
    // stated; the credit's own amount is not, because whether its sign lives on
    // `amount` is B2's O-4 residue and is still open.
    const html = bar(selectionOf(THREE), "system_admin", served({ excluded_count: 1 }));
    expect(html).toContain(escaped(t("payments.bulk.notCash", { count: 1 })));
  });

  it("a run of nothing excluded carries NO extra item — rule 32 on a bar read daily", () => {
    expect(bar(selectionOf(THREE))).not.toContain(escaped(t("payments.bulk.notCash", { count: 0 })));
  });

  it("an unread total says so and NEVER substitutes a browser sum", () => {
    // ⚠ RED FIRST, PROVED. A browser-sum fallback for the unread case — which
    // is what this file did for one commit — reported:
    //     AssertionError: expected '<div class="pay-bulk" role="group" ar...'
    //       to contain 'No total to show yet'
    // The figure is not wrong arithmetic; it is a DIFFERENT figure under the
    // same label, because CS-35's total excludes credits and a browser sum
    // cannot. Two answers to one question on one screen is what
    // `selectors.selection_total` cites hard-won law 5 against.
    const html = bar(selectionOf(THREE), "system_admin", "unread");
    expect(html).toContain(escaped(t("payments.bulk.totalUnread")));
    expect(html).not.toContain("1,242.87");
  });

  it("the client-sum reasons are RETIRED from every catalogue, not left dead", () => {
    // A catalogue entry beats a code default, so a key with no call site prints
    // nothing useful and teaches the next reader a control exists that does not.
    expect(t("payments.bulk.noTotal.mixed_currencies")).toBe(
      "payments.bulk.noTotal.mixed_currencies",
    );
    expect(t("payments.bulk.noTotal.not_addable")).toBe("payments.bulk.noTotal.not_addable");
  });
});

describe("CR-135 P1.7 · the two dead controls come OFF the bar, they do not stay greyed", () => {
  // ⚠ THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-22, and it was right when it
  // was written. It read *"Reapply and Send receipts render DISABLED WITH THEIR
  // REASON, never hidden"* on `BR-SHL-025` and S34's pattern, over a comment
  // saying *"`/reallocate` is CS-11 and unbuilt; there is no receipts route at
  // any layer"*. **`POST /payments/{id}/reapply` landed on 2026-09-03** and
  // nothing re-checked the refusal — hard-won law 2's mirror, and this test is
  // the thing that held it in place, because a case asserting a stale rule
  // makes correcting the code look like breaking the suite.
  //
  // The blueprint's §03 frame 2·1b rules both off in terms: *"Reverse, danger
  // tier, with Refund beside it. **Nothing else on the bar**"*, under a GAP box
  // headed *"The two dead controls come off the bar; they do not stay greyed"*.

  // ⚠ **SUPERSEDED 2026-10-30 — THE HOLD EXPIRED AND THIS CASE IS ITS EXPIRY
  // TEST.** The bulk acts landed (Q4, PO ruling; `DEF-PAY-10747`,
  // `apps/payments/bulk_acts.py`), so both controls are BACK on the bar with
  // their eligible count. This case asserted their absence until that commit,
  // and went red on it — the law-2 expiry working as intended.
  it("Reapply and Send receipts are back on the bar, each with its count", () => {
    const html = bar(selectionOf(THREE));
    expect(html).toContain(escaped(t("payments.bulk.action.reapplyCount", { count: 3 })));
    expect(html).toContain(escaped(t("payments.bulk.action.receiptsCount", { count: 3 })));
    // ⚠ **THE TWO `…Unavailable` ASSERTIONS THAT WERE HERE ARE GONE WITH THEIR
    // KEYS (`P2.6`, Finance blueprint p015).** They read
    // `expect(html).not.toContain(escaped(t("payments.bulk.reapplyUnavailable")))`
    // — and once the keys were retired `t()` returns the KEY ITSELF, which no
    // markup contains either, so both would have gone on passing while
    // asserting nothing at all. That is hard-won law 7's *structurally
    // incapable of failing*, and the failing form is silent: a green line.
    // The two assertions above still carry the real question, because the
    // LABELS are kept (see the case below).
  });

  it("and the bar keeps the three controls the drawing gives it", () => {
    // ⚠ THE HALF THAT STOPS THIS BEING A DELETION TEST. The four assertions
    // above would ALL pass on a bar with no buttons at all — which is
    // `DEF-PAY-6199` exactly, a fold that did not carry every act. So the
    // survivors are named: Reverse, Refund, Clear selection.
    const html = bar(selectionOf(THREE));
    expect(html).toContain(escaped(t("payments.bulk.action.reverse")));
    expect(html).toContain(escaped(t("payments.bulk.action.refund")));
    expect(html).toContain(escaped(t("payments.bulk.clear")));
  });

  it("the two LABELS are kept and the two REASONS are retired", () => {
    // The mirror of the `noTotal.*` case above, and it now gives OPPOSITE
    // verdicts to the two halves of this pair — which is the point.
    //
    // ⚠ **THE LABELS COME BACK; THE REASONS NEVER DO (`P2.6`).** A bulk reapply
    // and a bulk receipt send are real future features, so
    // `payments.bulk.action.*` is kept and retiring it would be work done
    // twice. But `payments.bulk.reapplyUnavailable` said *"Reapplying is not
    // built yet"* — and `POST /payments/{id}/reapply` LANDED on 2026-09-03, so
    // the sentence was already false, and on the day the BULK version ships it
    // is false twice over. A reason for an absence cannot survive the absence.
    expect(t("payments.bulk.action.reapply")).not.toBe("payments.bulk.action.reapply");
    expect(t("payments.bulk.action.receipts")).not.toBe("payments.bulk.action.receipts");
    // Retired — `t()` echoes a key it does not hold, which is what proves it
    // gone rather than merely unused.
    expect(t("payments.bulk.reapplyUnavailable")).toBe("payments.bulk.reapplyUnavailable");
    expect(t("payments.bulk.receiptsUnavailable")).toBe("payments.bulk.receiptsUnavailable");
  });

  it("Reverse and Refund are OFFERED when a selected row can take them", () => {
    const html = bar(selectionOf(THREE));
    expect(html).toContain(escaped(t("payments.bulk.action.reverse")));
    expect(html).toContain(escaped(t("payments.bulk.action.refund")));
    expect(html).not.toContain(escaped(t("payments.bulk.noneReversible")));
    expect(html).not.toContain(escaped(t("payments.bulk.noneRefundable")));
  });

  it("a selection nothing can be done to disables the button WITH its reason", () => {
    // A button that would refuse every row it was given is a control over
    // nothing — CR-059's own argument for leaving this toolbar out. Every row
    // here is refused for the SAME reason, so that reason is what shows.
    const processing = selectionOf([payment({ id: "p", status: "processing" })]);
    const html = bar(processing);
    expect(html).toContain(escaped(t("payments.reverse.notCleared")));
    expect(html).toContain(escaped(t("payments.bulk.refundNotCleared")));
  });

  it("rows refused for DIFFERENT reasons fall back to the one true sentence", () => {
    // No single reason is true of this selection, so neither row's reason may
    // stand for both — that would tell a clerk something false about one of
    // them. This is the case `payments.bulk.noneReversible` exists for.
    const html = bar(
      selectionOf([
        payment({ id: "a", status: "processing" }),
        payment({ id: "b", status: "reversed" }),
      ]),
    );
    expect(html).toContain(escaped(t("payments.bulk.noneReversible")));
  });

  it("a selection where SOME rows qualify stays live — the rest are reported per row", () => {
    const mixed = selectionOf([payment({ id: "ok" }), payment({ id: "no", status: "processing" })]);
    expect(bar(mixed)).not.toContain(escaped(t("payments.bulk.noneReversible")));
  });

  it("a non-admin cannot bulk reverse, and the reason is the row action's own", () => {
    // BR-PAY-1070 is Admin-only, and the bulk control must refuse exactly what
    // the single Reverse refuses or the two disagree about one rule.
    expect(bar(selectionOf(THREE), "billing_clerk")).toContain(
      escaped(t("payments.reverse.adminOnly")),
    );
  });
});

describe("CS-41 · which rows a run would refuse before it sends anything", () => {
  it("money that has not arrived cannot be given back — the service's own refusal", () => {
    expect(bulkRefundRefusal(payment({ status: "processing" }), t)).toBe(
      t("payments.bulk.refundNotCleared"),
    );
  });

  it("a reversing row has nothing to refund, and the sign is read off the STRING", () => {
    // `Number()` on money is the float hard rule 2 keeps out.
    expect(bulkRefundRefusal(payment({ amount: "-292.870000" }), t)).toBe(
      t("payments.bulk.refundNotPositive"),
    );
  });

  it("a cleared positive payment carries NO screen-side refusal — the credit test is the server's", () => {
    // BR-PAY-014's credit position is not on the row, so a guard here would be a
    // guess dressed as a rule. It comes back per row and lands in the panel.
    expect(bulkRefundRefusal(payment(), t)).toBeNull();
  });

  it("reverse refuses a reversal, a processing row and a non-admin — and nothing else", () => {
    expect(bulkReverseRefusal(payment(), "system_admin", t)).toBeNull();
    expect(bulkReverseRefusal(payment(), null, t)).toBeNull();
    expect(bulkReverseRefusal(payment({ status: "reversed" }), "system_admin", t)).toBe(
      t("payments.reverse.isReversal"),
    );
  });

  it("an empty selection disables the button rather than offering an empty run", () => {
    expect(bulkActionRefusal([], () => null, "none")).toBe("none");
  });
});

describe("CS-41 · N rows are N sequential calls and none of them ends the others", () => {
  it("a failure in the MIDDLE does not lose the two that worked", async () => {
    // ⚠ RED FIRST, PROVED. Letting the error out of the loop — `await call(row)`
    // with no try — was put back, and this case and two others reported the raw
    // rejection instead of a result:
    //     × a failure in the MIDDLE does not lose the two that worked
    //       → no credit
    //     × every row ends with a verdict, whatever happened to it → boom
    //     × the failure sentence is the SERVER's … → boom
    // On the running product that shape throws away the refund that already went
    // through before it and never attempts the one after.
    const outcomes: string[] = [];
    const sent: string[] = [];
    await runPerRow(
      THREE,
      () => null,
      (row) => row.payment_no ?? "",
      async (row) => {
        sent.push(row.id);
        if (row.id === "p2") {
          throw new Error("no credit");
        }
      },
      () => "the server said no",
      (outcome) => outcomes.push(`${outcome.id}:${outcome.status}`),
    );
    expect(sent).toEqual(["p1", "p2", "p3"]);
    expect(outcomes).toEqual(["p1:done", "p2:failed", "p3:done"]);
  });

  it("the calls are SEQUENTIAL — one finishes before the next starts", async () => {
    let inFlight = 0;
    let overlapped = false;
    await runPerRow(
      THREE,
      () => null,
      () => "x",
      async () => {
        inFlight += 1;
        if (inFlight > 1) {
          overlapped = true;
        }
        await Promise.resolve();
        inFlight -= 1;
      },
      () => "",
      () => undefined,
    );
    expect(overlapped).toBe(false);
  });

  it("a row this screen already knows will be refused is NOT sent", async () => {
    const call = vi.fn(async () => undefined);
    const outcomes: string[] = [];
    await runPerRow(
      THREE,
      (row) => (row.id === "p2" ? "the money has not arrived" : null),
      () => "x",
      call,
      () => "",
      (outcome) => outcomes.push(outcome.status),
    );
    expect(call).toHaveBeenCalledTimes(2);
    expect(outcomes).toEqual(["done", "refused", "done"]);
  });

  it("every row ends with a verdict, whatever happened to it", async () => {
    const outcomes: string[] = [];
    await runPerRow(
      THREE,
      (row) => (row.id === "p1" ? "refused here" : null),
      () => "x",
      async (row) => {
        if (row.id === "p2") {
          throw new Error("boom");
        }
      },
      () => "the server said no",
      (outcome) => outcomes.push(outcome.status),
    );
    // A single "1 of 3 worked" would leave a clerk with no way to find the two.
    expect(outcomes).toHaveLength(3);
    expect(new Set(outcomes)).toEqual(new Set(["refused", "failed", "done"]));
  });

  it("the failure sentence is the SERVER's, carried onto the row it belongs to", async () => {
    const details: (string | null)[] = [];
    await runPerRow(
      [THREE[0]],
      () => null,
      () => "x",
      async () => {
        throw new Error("boom");
      },
      () => "this account holds no credit",
      (outcome) => details.push(outcome.detail),
    );
    expect(details).toEqual(["this account holds no credit"]);
  });
});

describe("CS-41 · the successes are dropped and the failures are kept — a money rule", () => {
  const run: BulkRun = {
    action: "refund",
    total: 3,
    running: false,
    outcomes: [
      { id: "p1", label: "PMT-2608-000412", status: "done", detail: null },
      { id: "p2", label: "PMT-2608-000413", status: "failed", detail: "no credit" },
      { id: "p3", label: "PMT-2608-000414", status: "done", detail: null },
    ],
  };

  it("a second press cannot re-send a refund that already went through", () => {
    // ⚠ RED FIRST, PROVED. Skipping the deselect leaves all three ticked, and a
    // retry then raises a SECOND refund against two overpayments that were
    // already refunded. Made to return the selection untouched, this case
    // reported:
    //     AssertionError: expected 3 to be 1 // Object.is equality
    const after = deselectMany(selectionOf(THREE), succeededIds(run));
    expect(after.size).toBe(1);
    expect(after.has("p2")).toBe(true);
  });

  it("the retry is aimed at the failures ONLY", () => {
    expect(failedRows(run, selectionOf(THREE)).map((row) => row.id)).toEqual(["p2"]);
  });

  it("a run with nothing to retry offers no retry", () => {
    const clean: BulkRun = { ...run, outcomes: [run.outcomes[0]] };
    expect(failedRows(clean, selectionOf(THREE))).toEqual([]);
  });

  it("the tally counts each verdict separately", () => {
    expect(runTally(run)).toEqual({ done: 2, failed: 1, refused: 0 });
  });
});

describe("BR-PAY-028 · a retry carries the key its first attempt carried", () => {
  it("the same payment gets the SAME idempotency key twice", () => {
    // ⚠ RED FIRST, PROVED. Minting per call — `crypto.randomUUID()` with the map
    // lookup deleted — reported:
    //     AssertionError: expected '719694ab-639e-4280-9d37-5668aa953132'
    //       to be 'f7cf4291-aa52-41f5-bd9b-6a75a38c570a' // Object.is equality
    // On the running product an ambiguous network failure then becomes a second
    // refund against the same overpayment, because the server dedupes on this
    // key and cannot tell the two attempts apart without it.
    const keys = new Map<string, string>();
    const first = keyFor(keys, "p1");
    expect(keyFor(keys, "p1")).toBe(first);
  });

  it("two different payments get two different keys", () => {
    const keys = new Map<string, string>();
    expect(keyFor(keys, "p1")).not.toBe(keyFor(keys, "p2"));
  });
});

describe("CS-41 · the result panel names every row and never a database id", () => {
  const run: BulkRun = {
    action: "refund",
    total: 2,
    running: false,
    outcomes: [
      { id: "8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11", label: "PMT-2608-000412", status: "done", detail: null },
      {
        id: "1c383cd3-0b7c-4b7e-9c94-1d38f8f2e4aa",
        label: "PMT-2608-000413",
        status: "failed",
        detail: "this account holds no credit",
      },
    ],
  };

  function panel(): string {
    return renderToStaticMarkup(
      <BulkRunPanel run={run} refundsHref="/t/finance/refunds" onRetry={null} onDismiss={() => undefined} />,
    );
  }

  it("both payments are listed, each with its own verdict", () => {
    const html = panel();
    expect(html).toContain("PMT-2608-000412");
    expect(html).toContain("PMT-2608-000413");
    expect(html).toContain(escaped(t("payments.bulk.outcome.done")));
    expect(html).toContain(escaped(t("payments.bulk.outcome.failed")));
  });

  it("the server's own sentence rides on the row it belongs to", () => {
    expect(panel()).toContain(escaped("this account holds no credit"));
  });

  it("B14 rule 31 — no uuid reaches the panel, although the run holds them", () => {
    expect(panel()).not.toContain("8f14e45f");
    expect(panel()).not.toContain("1c383cd3");
  });

  it("a refund run that got something through points at the queue it went into", () => {
    // CS-41's acceptance line ends *"three refunds appear as pending"*, and this
    // is where a clerk goes to see them.
    expect(panel()).toContain(escaped(t("payments.bulk.openRefundQueue")));
  });
});

describe("CS-41 · the tick rides in the identity cell", () => {
  const cells = paymentsCells(t, (path) => path, "UTC", "YYYY-MM-DD");

  function identityCell(row: PaymentRow, selected: boolean): string {
    const config = paymentsTableConfig(t, cells, undefined, undefined, {
      select: { isSelected: () => selected, onToggle: () => undefined },
    });
    const column = config.columns.find((one) => one.key === "payment_no");
    return renderToStaticMarkup(<>{column?.cell?.(row)}</>);
  }

  it("the checkbox and the payment number are in the ONE column that cannot be hidden", () => {
    // ⚠ RED FIRST, and this is the case that would have shipped broken. A
    // separate `select` COLUMN is filtered out by any saved column preference —
    // `columnsFromPreference` keeps only stored keys, and a column that did not
    // exist when the preference was written can never be in it — so the whole
    // feature would be missing for every clerk who has customised this list,
    // with every test green. BR-SHL-013 guarantees the identity column is
    // always re-inserted.
    const html = identityCell(payment(), false);
    expect(html).toContain('type="checkbox"');
    expect(html).toContain("PMT-2608-000412");
    expect(paymentsTableConfig(t, cells).columns.some((one) => one.key === "select")).toBe(false);
  });

  it("the checkbox is named by the payment NUMBER, never by its id (B14 rule 31)", () => {
    const html = identityCell(payment({ id: "8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11" }), false);
    expect(html).toContain(escaped(t("payments.bulk.selectRow", { number: "PMT-2608-000412" })));
    expect(html).not.toContain("8f14e45f");
  });

  it("a row with no number is still selectable, under its stated absence", () => {
    const html = identityCell(payment({ payment_no: null }), false);
    expect(html).toContain('type="checkbox"');
    expect(html).toContain(escaped(t("payments.row.noNumber")));
  });

  it("a table with no selection draws the plain identity cell and no checkbox", () => {
    // BR-SHL-010: a capability not declared is not rendered.
    const config = paymentsTableConfig(t, cells);
    const column = config.columns.find((one) => one.key === "payment_no");
    const html = renderToStaticMarkup(<>{column?.cell?.(payment())}</>);
    expect(html).not.toContain('type="checkbox"');
    expect(html).toContain("PMT-2608-000412");
  });
});

describe("CS-44 · the Batch column, checked before it was filled (DEF-2353 · DEF-2352)", () => {
  const cells = paymentsCells(t, (path) => path, "UTC", "YYYY-MM-DD");

  // ⚠ **THE COLUMN IS FILLED NOW (`CR-135` `P1.9`), SO THESE TWO CASES MOVED
  // WITH IT RATHER THAN BEING DELETED.** The old `depositBatch` cell stated an
  // absence; `batch` serves the batch's own CODE, which is what CS-44 asked for
  // and what closes `DEF-2353`. The RULE both cases existed for — B14 rule 31,
  // no database id is ever the visible value of a field — is unchanged, and it
  // is asserted here over EVERY cell rather than over the one that used to
  // break it, because the next uuid will arrive in a different column.

  it("no uuid reaches ANY cell, even when the server sends one", () => {
    // ⚠ RED FIRST, PROVED. Point `batch` at `deposit_batch_id` instead of
    // `batch_ref` and this reports:
    //     AssertionError: expected '<span class="pay-id">8f14e45f-ea5c-4f…'
    //       not to contain '8f14e45f'
    const uuid = "8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11";
    const row = payment({ deposit_batch_id: uuid, batch_ref: "DEP-260922-0001" });
    const config = paymentsTableConfig(t, cells);
    for (const column of config.columns) {
      const html = renderToStaticMarkup(<>{column.cell?.(row)}</>);
      expect(html, `column ${column.key} printed a uuid`).not.toContain("8f14e45f");
    }
  });

  it("the Batch cell shows the code the server served", () => {
    const html = renderToStaticMarkup(<>{cells.batch(payment({ batch_ref: "DEP-260922-0001" }))}</>);
    expect(html).toContain("DEP-260922-0001");
  });

  it("a payment in no batch says so rather than rendering blank", () => {
    // ⚠ **THE ABSENCE IS STILL REAL AND IT IS NARROWER THAN IT WAS.** A card
    // taken and not yet settled belongs to no batch, because there is no
    // settlement run in the product — the drawing's own gap note ⑦. A blank
    // cell there reads as a failed load.
    const html = renderToStaticMarkup(<>{cells.batch(payment({ batch_ref: null }))}</>);
    expect(html).toContain(escaped(t("payments.row.noBatch")));
  });

  it("the Source cell names the drawn word, never the stored one", () => {
    // B14 rule 31. `entry · webhook · import` are what the column holds; a
    // clerk reads *Counter · Digital · Post*.
    const html = renderToStaticMarkup(<>{cells.source(payment({ origin: "import" }))}</>);
    expect(html).toContain(escaped(t("payments.source.import")));
    expect(html).not.toContain("import<");
  });

  it("Q6 — a store network's payment reads Store · Hy-Vee; a lockbox row keeps File", () => {
    // PO 2026-10-30 Q6: the network name comes from the file's Network column.
    const store = renderToStaticMarkup(
      <>{cells.source(payment({ origin: "import", store_network: "Hy-Vee" }))}</>,
    );
    expect(store).toContain(escaped("Store · Hy-Vee"));
    const lockbox = renderToStaticMarkup(
      <>{cells.source(payment({ origin: "import", store_network: null }))}</>,
    );
    expect(lockbox).toContain(escaped(t("payments.source.import")));
    expect(lockbox).not.toContain("Store");
  });

  it("the Receipt column's absence is still TRUE and still says so", () => {
    // BR-PAY-024's receipt queue is US-PAY-025's and unbuilt at every layer.
    const html = renderToStaticMarkup(<>{cells.receiptNo(payment())}</>);
    expect(html).toContain(escaped(t("payments.row.noReceipt")));
  });
});
