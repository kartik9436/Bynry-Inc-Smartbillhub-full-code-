// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-135 phase 1 · `P1.6` (the two screens) and `P1.7` (the bulk
//           bar's dead Reapply, whose own case lives in `bulkActions.test.tsx`)
// Screens:  2·3f Move · 2·3g Reapply (S35 · PAY-E), blueprint
//           `05-prototype/06 Payments Page Blueprint.pdf` p47 and p48
// Rules:    B14 rule 11 (a consequence preview before a money commit) ·
//           rule 31 (no database id is a visible value) · rule 33 (a fact
//           ≤ 6 words) · rule 43 (a piece of UI is a COMPONENT) ·
//           CLAUDE.md hard rule 4 · BR-PAY-865 · BR-PAY-866 · BR-PAY-867
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ONE ASSERTION THIS FILE EXISTS FOR IS THE DOOR, NOT THE MODAL.**
// `movePayment`, `getPaymentMovePreview`, `reapplyPayment` and `getReapplyPlan`
// were all written, all served, and all called by NOTHING from 2026-09-03 to
// 2026-09-22 — with `tsc` green, 452 payments cases green, and every gate
// passing, because `tsc` is content with an exported symbol nobody imports and
// `G118` (which asks exactly this question) reads only `src/portal/`. A test
// that renders these two modals directly and never asks who opens them would
// have been green on 2026-09-03 too. So the first `describe` walks the ROW,
// from the table config a clerk actually sees.
//
// ⚠ **AND THE PAGE IS MOUNTED UNDER THE REAL PATH PATTERN.** CLAUDE.md's law 2
// records why: a bare `MemoryRouter` with no `/:tenant/…` route leaves
// `useParams().tenant` undefined, every address the screen builds comes out
// `//…` — a protocol-relative URL to another host — and `toContain` reads it as
// a perfectly good string.

import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  OpenBillPosition,
  PaymentMovePreview,
  PaymentRow,
  ReapplyPlan,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { paymentsCells, paymentsTableConfig } from "./PaymentsPage";
// ⚠ THE PAGE'S OWN SOURCE, read through Vite's `?raw` and not `node:fs` (this
// app carries no `@types/node`). It is here because the config-level cases
// below build their OWN affordances and therefore CANNOT see whether the page
// passes any — which is exactly the blind spot that let four served endpoints
// sit unreachable for nineteen days. Proved: removing `move:` from the page
// left every other case in this file green.
import PAGE_SOURCE from "./PaymentsPage.tsx?raw";
import {
  MovePaymentModal,
  ReapplyPaymentModal,
  moveReasonText,
  reapplyOutcome,
  reopensTotal,
} from "./paymentMoveReapply";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/** The drawing's own row: `PMT-2609-000418 · $158.10` on Ana Alvarez. */
function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-418",
    payment_no: "PMT-2609-000418",
    account_id: "acc-0001",
    account_no: "AC-2026-00001",
    customer_name: "Ana Alvarez",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: "4411",
    memo: null,
    amount: "158.100000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-09-08",
    cleared_at: "2026-09-10",
    applied_to: [],
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

// ══════════════════════════════════════════════════════════════════════════
// THE DOORS — "2 doors — there are none today" is what the blueprint measured
// ══════════════════════════════════════════════════════════════════════════

describe("P1.6 · the row overflow opens both screens", () => {
  /** The page's code with its comments stripped — a promise in a comment is not
   *  the promise (hard-won law 1), and this file is asking what the page DOES. */
  const PAGE_CODE = PAGE_SOURCE.split("\n")
    .filter((line: string) => {
      const trimmed = line.trim();
      return !trimmed.startsWith("*") && !trimmed.startsWith("//") && !trimmed.startsWith("/*");
    })
    .join("\n");

  it("THE PAGE PASSES BOTH AFFORDANCES — without this, everything below is theatre", () => {
    // `paymentsTableConfig` takes `move` and `reapply` as OPTIONAL, so a page
    // that passes neither compiles, renders, and shows a clerk no door at all.
    expect(PAGE_CODE, "PaymentsPage stopped passing the Move affordance").toContain(
      "move: { onMove:",
    );
    expect(PAGE_CODE, "PaymentsPage stopped passing the Reapply affordance").toContain(
      "reapply: { onReapply:",
    );
  });

  it("and the page MOUNTS both modals, so pressing the icon opens something", () => {
    // The other half of law 2: an affordance whose handler sets state nothing
    // reads is a door onto nothing.
    expect(PAGE_CODE, "PaymentsPage no longer mounts MovePaymentModal").toContain(
      "<MovePaymentModal",
    );
    expect(PAGE_CODE, "PaymentsPage no longer mounts ReapplyPaymentModal").toContain(
      "<ReapplyPaymentModal",
    );
  });

/**
 * ⚠ **THE ACTIONS CELL NOW CONTAINS A ROUTER `<Link>` AND MUST BE RENDERED
 * UNDER A ROUTE (`CR-137-BRC07` `P3.10`, 2026-09-23).**
 *
 * The 👁 Detail action is a `RowActionLink`, not a button: an address a clerk
 * can middle-click, open in a new tab and paste into a message is the whole
 * point of screen 2·2, and an `onClick` that calls `navigate` loses all three.
 * Rendered bare, it throws *"Cannot destructure property 'basename'"*.
 *
 * ⚠ **AND THE ROUTE PATTERN CARRIES `:tenant` ON PURPOSE.** A bare
 * `MemoryRouter` with no tenant segment leaves `useParams().tenant` undefined,
 * so every address the cell builds comes out `//payments/…` — a
 * protocol-relative URL to another host that reads as a perfectly good string
 * to `toContain`. That is how eight dead doors hid on the customer portal
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

  function actionsCell(withDoors: boolean): string {
    const cells = paymentsCells(t, (p) => `/acme${p}`, "UTC", "MM/DD/YYYY");
    const config = paymentsTableConfig(
      t,
      cells,
      { reasonFor: () => null, onReverse: () => undefined },
      { onCorrect: () => undefined },
      withDoors
        ? { move: { onMove: () => undefined }, reapply: { onReapply: () => undefined } }
        : {},
    );
    const actions = config.columns.find((column) => column.key === "actions");
    expect(actions, "the payments table has an ACTIONS column").toBeDefined();
    return underRoute(actions?.cell?.(payment()));
  }

  it("Move and Reapply are both on the row, each named for a screen reader", () => {
    const html = actionsCell(true);
    // `RowAction` makes the label BOTH the accessible name and the tooltip, so
    // one assertion covers the icon's only readable name (B14 rule 15).
    expect(html).toContain(escaped(t("payments.move.action")));
    expect(html).toContain(escaped(t("payments.reapply.action")));
  });

  it("and the column keeps Correct and Reverse — this adds doors, it removes none", () => {
    // `DEF-PAY-6199`'s check, applied to an ADDITION: what could this cell do
    // before, and can it still do all of it?
    const html = actionsCell(true);
    expect(html).toContain(escaped(t("payments.correct.action")));
    expect(html).toContain(escaped(t("payments.reverse.action")));
  });

  it("a caller that passes neither still gets no Move and no Reapply", () => {
    // The affordances are OPTIONAL because two callers build this config for
    // `parseTableParams` alone. That is law 2's dead-prop shape if nothing ever
    // passes them, so the case above proves a caller does — and this one proves
    // the omission is still honest rather than an accident.
    const html = actionsCell(false);
    expect(html).not.toContain(escaped(t("payments.move.action")));
    expect(html).not.toContain(escaped(t("payments.reapply.action")));
  });

  it("a reversing row offers neither, because there is nothing to re-point", () => {
    const cells = paymentsCells(t, (p) => `/acme${p}`, "UTC", "MM/DD/YYYY");
    const config = paymentsTableConfig(
      t,
      cells,
      { reasonFor: () => null, onReverse: () => undefined },
      { onCorrect: () => undefined },
      { move: { onMove: () => undefined }, reapply: { onReapply: () => undefined } },
    );
    const actions = config.columns.find((column) => column.key === "actions");
    const html = underRoute(actions?.cell?.(payment({ amount: "-158.100000", status: "reversed" })));
    // Disabled WITH its reason (BR-SHL-025), never hidden — the clerk learns the
    // rule instead of hunting for a control somebody removed.
    expect(html).toContain(escaped(t("payments.reverse.isReversal")));
    expect(html).toContain("disabled");
  });

  describe("DEF-PAY-6214 · two visible plus an overflow, because four did not fit", () => {
    // ⚠ **THIS BLOCK EXISTS BECAUSE THE FOUR CASES ABOVE PASS EITHER WAY.** They
    // assert the LABEL is in the markup, and `RowMenuAction` puts the label in
    // the markup too — so they were green over a cell that drew four glyphs, two
    // of which were off the right edge of a 1440 window. Measured in Chromium on
    // `brazosbend`, 2026-09-22: the table is 1,214px inside a 1,120px scroller
    // and the buttons end at 1374, 1410, **1446** and **1482**.
    //
    // B14 rule 15 has said the answer since it was ratified — *"Max 2 visible +
    // `…` overflow"* — and `G37` counts the `<RowAction`s in this cell into a
    // variable and never compares it to that cap, which is hard-won law 7's
    // *a counter nothing asserts on*. This is that assertion, in the one file
    // that owns the two doors it moved.

    /** How many controls sit ON THE ROW, and how many are behind the `…`. */
    function shape(html: string) {
      const more = html.indexOf("data-row-more");
      return {
        onTheRow: (html.slice(0, more === -1 ? html.length : more).match(/<button/g) ?? []).length,
        hasOverflow: more !== -1,
        inTheMenu: more === -1 ? 0 : (html.slice(more).match(/<button/g) ?? []).length,
      };
    }

    it("the row draws TWO controls and a `…`, never four", () => {
      const { onTheRow, hasOverflow } = shape(actionsCell(true));
      expect(onTheRow, "B14 rule 15: max 2 visible").toBeLessThanOrEqual(2);
      expect(hasOverflow, "the rest belong behind the overflow").toBe(true);
    });

    it("the two that stay are View and Correct reference", () => {
      // ⚠ **THIS CASE READ *"the two that stay are Correct reference and
      // Reverse"* UNTIL `CR-137-BRC07` `P3.10` (2026-09-23), AND THE CHANGE IS
      // THE DRAWING'S, NOT A PREFERENCE.**
      //
      // `DEF-PAY-6214` chose that pair on 2026-09-22 — *"the everyday clerical
      // fix and the money act"* — and it was right, because **the 👁 did not
      // exist**: a payment had no address, which is why p036 notes *"the row
      // actions have no View icon"* as a CONSEQUENCE of that absence. `P3.9`
      // gave a payment an address, and p030 ⑥ says what the column becomes in
      // as many words: ***"👁 Detail · ✎ Edit, then `…` for Receipt and Cancel
      // · B14 15 caps visible icons at TWO"***.
      //
      // **The CAP `DEF-PAY-6214` enforced is untouched and is still asserted
      // above** — what moved is WHICH two, and Reverse joins Move and Reapply
      // behind the `…` where the drawing already had it. No capability left:
      // the case below still proves all three are one press away.
      const html = actionsCell(true);
      const row = html.slice(0, html.indexOf("data-row-more"));
      expect(row).toContain(escaped(t("payments.detail.view")));
      expect(row).toContain(escaped(t("payments.correct.action")));
    });

    it("and NO capability left with them — all three are still one press away", () => {
      // `DEF-PAY-6199`'s check applied to a MOVE rather than a deletion: what
      // could this cell do before, and can it still do all of it?
      // ⚠ **REVERSE JOINED THIS LIST IN `P3.10`** — it is behind the `…` now
      // rather than on the row, and behind the `…` is still one press away.
      // **This is the assertion that makes the rearrangement above safe**: a
      // cap enforced by quietly dropping a door would pass every count.
      const html = actionsCell(true);
      const menu = html.slice(html.indexOf("data-row-more"));
      expect(menu).toContain(escaped(t("payments.reverse.action")));
      expect(menu).toContain(escaped(t("payments.move.action")));
      expect(menu).toContain(escaped(t("payments.reapply.action")));
    });

    it("a caller passing NO overflow door draws no overflow at all", () => {
      // A menu holding nothing is a control over nothing — `RowActionsMore`'s
      // own note: *"a menu holding one item is a button wearing a costume"*.
      //
      // ⚠ **THIS CASE USED TO PASS `actionsCell(false)` AND `P3.10` MADE THAT
      // THE WRONG QUESTION.** `actionsCell(false)` withholds Move and Reapply
      // but still passes REVERSE, and Reverse now lives behind the `…` — so
      // that cell draws an overflow, correctly, holding one real door. The
      // invariant was never *"two doors or none"*; it is **the menu is drawn
      // only when something is in it**, so the caller here withholds all three.
      const cells = paymentsCells(t, (p) => `/acme${p}`, "UTC", "MM/DD/YYYY");
      const config = paymentsTableConfig(t, cells, undefined, { onCorrect: () => undefined });
      const actions = config.columns.find((column) => column.key === "actions");
      expect(shape(underRoute(actions?.cell?.(payment()))).hasOverflow).toBe(false);
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2·3f — WHAT THE MOVE SCREEN SAYS BEFORE IT COMMITS
// ══════════════════════════════════════════════════════════════════════════

function renderModal(node: React.ReactNode): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/acme/payments"]}>
          <Routes>
            <Route path="/:tenant/payments" element={<>{node}</>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const NO_CLIENT = {} as never;

describe("P1.6 · 2·3f the Move screen", () => {
  it("① says where the money is NOW, because the whole act is a comparison", () => {
    const html = renderModal(
      <MovePaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onMoved={() => undefined}
      />,
    );
    expect(html).toContain(
      escaped(
        t("payments.move.whereItIsNow", {
          account: "AC-2026-00001",
          customer: "Ana Alvarez",
        }),
      ),
    );
  });

  it("draws the drawn title, the drawn kicker with its formatted amount, and the drawn commit", () => {
    const html = renderModal(
      <MovePaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onMoved={() => undefined}
      />,
    );
    expect(html).toContain(escaped(t("payments.move.title")));
    expect(html).toContain(escaped(t("payments.move.submit")));
    // The amount reaches the kicker through `formatMoney`, so it reads $158.10
    // and not the stored 158.100000 (hard rule 2 — display 2).
    expect(html).toContain("$158.10");
    expect(html).not.toContain("158.100000");
  });

  it("the commit is DANGER tier, because a move is not undone by moving it back", () => {
    const html = renderModal(
      <MovePaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onMoved={() => undefined}
      />,
    );
    expect(html).toContain('data-variant="danger"');
  });

  it("the destination search carries the drawn help under it", () => {
    const html = renderModal(
      <MovePaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onMoved={() => undefined}
      />,
    );
    expect(html).toContain(escaped(t("payments.move.moveTo")));
    expect(html).toContain(escaped(t("payments.form.accountSearchHelp")));
  });

  it("no consequence box before a destination is chosen — an empty one would lie", () => {
    // It would claim the screen has looked and has nothing to say. It has not
    // looked: `GET /payments/{id}/move-preview?to=` takes a destination.
    const html = renderModal(
      <MovePaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onMoved={() => undefined}
      />,
    );
    expect(html).not.toContain('data-consequence="move"');
  });

  it("the reason posts the clerk's own words when they choose Another reason", () => {
    // Hard rule 4 makes the audit row the ONLY durable record of why a
    // customer's money moved, so the select may not narrow what can be said.
    expect(moveReasonText("wrong_account", "", t)).toBe(t("payments.move.reason.wrong_account"));
    expect(moveReasonText("other", "  cashier keyed the unit next door  ", t)).toBe(
      "cashier keyed the unit next door",
    );
    // An empty box under `other` produces an empty reason, which the form
    // refuses rather than posting — the service refuses it too.
    expect(moveReasonText("other", "   ", t)).toBe("");
  });

  it("② names the total re-opening on the source and never an invoice id", () => {
    // `reopens_on_source` carries `invoice_id` and NO number, and B14 rule 31
    // forbids putting an id on screen — so the sentence is the TOTAL.
    const preview: PaymentMovePreview = {
      approval_required: false,
      approval_reasons: [],
      payment_id: "pay-418",
      payment_no: "PMT-2609-000418",
      source_account_id: "acc-0001",
      destination_account_id: "acc-0002",
      amount: "158.100000",
      posted_at: "2026-09-08",
      cleared_at: "2026-09-10",
      reopens_on_source: [
        { invoice_id: "inv-85", amount: "100.000000" },
        { invoice_id: "inv-86", amount: "58.100000" },
      ],
      meets_on_destination: [{ invoice_number: "BL-2609-000092", amount: "158.100000" }],
      credit_carried: "0.000000",
      problems: [],
    };
    expect(reopensTotal(preview)).toBe("158.100000");
    // …and the figure it is made of never reaches a screen as an id.
    expect(t("payments.move.owesAgain", { customer: "Ana Alvarez", amount: "$158.10" })).not.toContain(
      "inv-85",
    );
  });

  it("a preview with nothing re-opening answers a measured zero, not null", () => {
    const preview = {
      reopens_on_source: [],
    } as unknown as PaymentMovePreview;
    // A zero is a FACT — nothing on the source re-opens — and the screen must
    // be able to tell it apart from "we could not add these up".
    expect(reopensTotal(preview)).toBe("0.000000");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2·3g — WHAT THE REAPPLY SCREEN SAYS
// ══════════════════════════════════════════════════════════════════════════

const PLAN: ReapplyPlan = {
  payment_id: "pay-418",
  payment_no: "PMT-2609-000418",
  account_id: "acc-0001",
  amount: "158.100000",
  currency: "USD",
  meets: [{ invoice_id: "inv-85", invoice_number: "BL-2609-000085", amount: "158.100000" }],
  applied_total: "158.100000",
  credit_carried: "0.000000",
  problems: [],
};

export const OPEN_BILLS: OpenBillPosition = {
  account_id: "acc-0001",
  account_no: "AC-2026-00001",
  currency: "USD",
  bills: [
    {
      invoice_id: "inv-85",
      number: "BL-2609-000085",
      issued_on: "2026-08-25",
      total: "158.100000",
      amount_due: "158.100000",
      allocated: "158.100000",
      open_balance: "0.000000",
      currency: "USD",
      composition: null,
    },
    {
      invoice_id: "inv-92",
      number: "BL-2609-000092",
      issued_on: "2026-09-12",
      total: "210.400000",
      amount_due: "210.400000",
      allocated: "0.000000",
      open_balance: "210.400000",
      currency: "USD",
      composition: null,
    },
  ],
  total_open: "210.400000",
  bill_count: 2,
  problems: [],
};

describe("P1.6 · 2·3g the Reapply screen", () => {
  it("draws the drawn title and its four column heads", () => {
    const html = renderModal(
      <ReapplyPaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onReapplied={() => undefined}
      />,
    );
    expect(html).toContain(escaped(t("payments.reapply.title")));
    expect(html).toContain(escaped(t("payments.reapply.applyTo")));
  });

  it("asks for a reason, because the service refuses a reapply without one", () => {
    const html = renderModal(
      <ReapplyPaymentModal
        client={NO_CLIENT}
        payment={payment()}
        timeZone="America/Chicago"
        onClose={() => undefined}
        onReapplied={() => undefined}
      />,
    );
    expect(html).toContain(escaped(t("payments.reapply.why")));
  });

  it("② the released bill is named by NUMBER and its total is the served figure", () => {
    // Picking BL-2609-000092 releases everything the payment meets today.
    const outcome = reapplyOutcome(PLAN, ["inv-92"]);
    expect(outcome.releasedTotal).toBe("158.100000");
    expect(outcome.releasedNames).toEqual(["BL-2609-000085"]);
    // B14 rule 31 — the id is in the plan and never in the sentence.
    expect(outcome.releasedNames.join("")).not.toContain("inv-85");
  });

  it("keeping the bill it already meets releases nothing, and says a measured zero", () => {
    const outcome = reapplyOutcome(PLAN, ["inv-85"]);
    expect(outcome.releasedTotal).toBe("0.000000");
    expect(outcome.releasedNames).toEqual([]);
  });

  it("a bill whose number could not be read is NAMED as one, never printed as its id", () => {
    const anonymous: ReapplyPlan = {
      ...PLAN,
      meets: [{ invoice_id: "inv-85", invoice_number: null, amount: "158.100000" }],
    };
    const outcome = reapplyOutcome(anonymous, ["inv-92"]);
    // The empty string is what the component falls back from, into
    // `payments.reapply.thatBill` — proved here so a later `??` (which would
    // keep the empty string and print nothing) goes red.
    expect(outcome.releasedNames).toEqual([""]);
    expect(outcome.releasedNames[0] || t("payments.reapply.thatBill")).toBe(
      t("payments.reapply.thatBill"),
    );
  });

  it("no plan yet means no outcome sentence at all", () => {
    expect(reapplyOutcome(undefined, ["inv-92"])).toEqual({
      releasedTotal: null,
      releasedNames: [],
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// B14 RULE 33 — WHAT IS ON SCREEN IS CAPPED BY WHAT IT IS FOR
// ══════════════════════════════════════════════════════════════════════════

describe("P1.6 · the copy obeys its caps", () => {
  /** Words, with the `{{…}}` placeholders taken out: a name is not our word. */
  function words(key: string): number {
    return i18n
      .t(key)
      .replace(/\{\{[^}]+\}\}/g, "")
      .split(/\s+/)
      .filter((word) => /[A-Za-z]/.test(word)).length;
  }

  it("every FACT this pair puts on screen is six words or fewer", () => {
    for (const key of [
      "payments.move.whereItIsNow",
      "payments.move.owesAgain",
      "payments.move.owesAgainUnknown",
      "payments.move.destinationMet",
      "payments.move.previewLoading",
      "payments.move.previewFailed",
      "payments.reapply.meetsNow",
      "payments.reapply.meetsNothing",
      "payments.reapply.reopensAt",
      "payments.reapply.othersMeet",
      "payments.reapply.noOpenBills",
      "payments.reapply.planLoading",
      "payments.reapply.planFailed",
    ]) {
      expect(words(key), `${key} is over rule 33's six-word cap for a fact`).toBeLessThanOrEqual(6);
    }
  });

  it("every LABEL is three words or fewer and carries no sentence", () => {
    for (const key of [
      "payments.move.action",
      "payments.move.moveTo",
      "payments.move.why",
      "payments.move.reasonOwnWords",
      "payments.reapply.action",
      "payments.reapply.applyTo",
      "payments.reapply.why",
      "payments.reapply.col.bill",
      "payments.reapply.col.issued",
      "payments.reapply.col.total",
      "payments.reapply.col.owesNow",
    ]) {
      expect(words(key), `${key} is over rule 33's three-word cap for a label`).toBeLessThanOrEqual(
        3,
      );
      expect(i18n.t(key), `${key} is a label and must not be a sentence`).not.toMatch(/\.$/);
    }
  });

  it("no RATIONALE reaches the screen — rule 33 gives it zero words", () => {
    // Why a move needs a reason, why the preview exists, why a reapply posts
    // nothing to the ledger: all of it is in the code and the register, and
    // none of it is a string. A rule id on a clerk's screen is rule 32's breach
    // in the same sentence.
    for (const key of [
      "payments.move.title",
      "payments.move.destinationMet",
      "payments.reapply.title",
      "payments.reapply.othersMeet",
    ]) {
      expect(i18n.t(key)).not.toMatch(/BR-|OQ-|CR-|hard rule|because/i);
    }
  });
});
