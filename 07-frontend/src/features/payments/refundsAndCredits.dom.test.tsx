// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.10` (Refunds moves tab, and Credit joins it) and
//           `P4.26` (a Kind column and filter on 6·1), from §03 frame 6·1 of
//           `05-prototype/06 Payments Page Blueprint.pdf` read as images at 2.0.
// Rules:    B14 rule 31 (no database id on screen) · rule 32 (a stated absence)
//           · rule 37 (a figure drawn in a wireframe is an ILLUSTRATION) ·
//           NFR-3 (server pagination)
// Screens:  6·1 Refunds (S58 · PAY-P)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE ASSERTION THIS FILE EXISTS FOR
// ══════════════════════════════════════════════════════════════════════════
// **A CREDIT NOTE MUST NOT BE GIVEN A STATE.** The server sends a credit-note
// row with NO `status` key — not `null`, ABSENT — and `refunds_and_credits.py`
// spells out why every alternative is a lie: *"`\"issued\"` invents a state
// machine the row is not in. `null` reads on screen as we do not know, when the
// truth is there is nothing to know. `\"n/a\"` is the same lie with worse
// manners."* The backend's own test drives RED on *"a credit note was given a
// synthesised status"*; this is the front half of that guard.
//
// ⚠ **AND IT IS WORTH A TEST BECAUSE THE DRAWING DISAGREES WITH ITSELF.** p073's
// five illustrative rows put `Issued` and `Applied` chips in the State column of
// both CRN rows, while the same document's GAP panel (p074), its own annotation
// ⑥ and its task row P4.26 all say a credit note has no state column at all.
// B14 rule 37 settles it — *a figure drawn in a wireframe is an ILLUSTRATION,
// never a fact to build to* — and so does the built read. A lane that "fixed"
// this screen against the drawn rows would reintroduce exactly the drift the
// blueprint says it keeps finding, and this case is what would stop them.
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
// `/:tenant/…` route leaves `useParams().tenant` undefined, so every address a
// page builds comes out `//payments/…` — a protocol-relative URL to another
// host that reads as a perfectly good string to `toContain`. That fixture is
// how the customer portal's eight dead doors hid.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { RefundLifecycle, RefundsAndCreditsRow } from "@/api/endpoints";
import { REFUND_KINDS } from "@/api/endpoints";
import { RefundsAndCreditsList, refundsAndCreditsConfig } from "./RefundsAndCreditsList";
import { refundStatusTone } from "./RefundsPage";
import {
  KIND_CREDIT_NOTE,
  KIND_REFUND,
  kindFilterOptions,
  kindHasState,
  refundKindLabelKey,
} from "./refundsAndCreditsShared";
import {
  PAYMENTS_TABS,
  PAYMENTS_TAB_REFUNDS,
  REFUNDS_LEGACY_ROUTE,
  REFUNDS_ROUTE,
  paymentsTabPath,
} from "./paymentsShared";

const TENANT = "brazosbend";

const LIFECYCLES: Record<string, RefundLifecycle> = {
  [KIND_REFUND]: {
    has_state: true,
    states: ["requested", "approved", "issued", "cleared", "void"],
    detail: "a refund is raised, approved, issued and cleared",
  },
  [KIND_CREDIT_NOTE]: {
    has_state: false,
    states: [],
    detail: "a credit note has no state column at all",
  },
};

/** One refund and one credit note — the shapes the SERVER actually sends. The
 *  credit note carries no `status` key at all, which is the whole point; giving
 *  it `status: null` here would make this file test a fixture rather than the
 *  contract. */
const ROWS: RefundsAndCreditsRow[] = [
  {
    kind: KIND_REFUND,
    id: "01a046dd-d809-7e20-81a3-87b1eddc1b64",
    account_id: "01a046dd-d809-7e20-81a3-87b1eddc1b65",
    amount_returned: "246.000000",
    currency: "USD",
    reason: "Closed in credit",
    occurred_at: "2026-09-08T10:00:00+00:00",
    number: "10241",
    number_absence: null,
    status: "requested",
    source: { method: "check", status: "requested" },
  },
  {
    kind: KIND_CREDIT_NOTE,
    id: "01a046dd-d809-7e20-81a3-87b1eddc1b66",
    account_id: "01a046dd-d809-7e20-81a3-87b1eddc1b67",
    amount_returned: "85.000000",
    currency: "USD",
    reason: "Goodwill",
    occurred_at: "2026-09-07T10:00:00+00:00",
    number: "CRN-2609-0012",
    number_absence: null,
    source: {},
  },
];

function renderList(rows: RefundsAndCreditsRow[] = ROWS) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}${REFUNDS_ROUTE}`]}>
        <Routes>
          <Route
            path="/:tenant/payments/refunds"
            element={
              <RefundsAndCreditsList
                rows={rows}
                totalRows={rows.length}
                state={{ q: "", sort: "occurred_at", dir: "desc", page: 1, per: 50, filters: {} }}
                onStateChange={() => undefined}
                loading={false}
                kinds={REFUND_KINDS}
                lifecycles={LIFECYCLES}
                statusTone={refundStatusTone}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("P4.26 — the two lifecycles are not flattened", () => {
  it("a credit note is given NO state word, and the refund beside it keeps its own", () => {
    renderList();
    // The refund's own status word, from `payments.refunds.status.requested`.
    expect(screen.getByText("Waiting")).toBeInTheDocument();
    // ⚠ THE LOAD-BEARING NEGATIVE. Every word a synthesised status could hold —
    // the two the DRAWING puts on its credit rows included.
    expect(screen.queryByText("Issued")).not.toBeInTheDocument();
    expect(screen.queryByText("Applied")).not.toBeInTheDocument();
    expect(screen.queryByText("n/a")).not.toBeInTheDocument();
    // …and what it draws instead: a stated absence (B14 rule 32).
    expect(screen.getByText("No state")).toBeInTheDocument();
  });

  it("`kindHasState` answers null for a kind the envelope did not describe — not false", () => {
    // *this kind has no lifecycle* and *this build cannot tell you whether it
    // does* are different sentences, and collapsing them is how a screen starts
    // asserting things it was never told.
    expect(kindHasState(KIND_CREDIT_NOTE, LIFECYCLES)).toBe(false);
    expect(kindHasState(KIND_REFUND, LIFECYCLES)).toBe(true);
    expect(kindHasState(KIND_REFUND, undefined)).toBeNull();
    expect(kindHasState("something_new", LIFECYCLES)).toBeNull();
  });

  it("the Kind column names both kinds, and a credit says it stays on the account", () => {
    renderList();
    // ⚠ **SCOPED TO THE TABLE.** `Refund` is also one of the toolbar's Kind
    // FILTER options — which is the task working, since the column and the
    // filter share one vocabulary — so an unscoped `getByText` finds two and
    // throws. Asserting inside the table is the narrower, truer question.
    const table = within(screen.getByRole("table"));
    expect(table.getByText("Refund")).toBeInTheDocument();
    expect(table.getByText("Credit")).toBeInTheDocument();
    // ⑤ How — *"a credit is not paid out at all and says so"*. A blank here
    // would read as *we failed to load the method*.
    expect(table.getByText("Stays on account")).toBeInTheDocument();
    expect(table.getByText("Check")).toBeInTheDocument();
  });

  it("B14 rule 31: no uuid from either row reaches the screen", () => {
    const { container } = renderList();
    for (const row of ROWS) {
      expect(container.innerHTML).not.toContain(row.id);
      expect(container.innerHTML).not.toContain(row.account_id);
    }
  });
});

describe("P4.26 — the filter is DERIVED, never typed out", () => {
  it("offers exactly the kinds the envelope published", () => {
    const config = refundsAndCreditsConfig(
      (key) => key,
      ["refund", "credit_note"],
      refundStatusTone,
      LIFECYCLES,
    );
    const kind = config.filters?.find((filter) => filter.name === "kind");
    expect(kind?.options.map((option) => option.value)).toEqual(["refund", "credit_note"]);
  });

  it("a kind this build has no word for is DROPPED, never rendered as its code", () => {
    // One option fewer is visible. An internal string on a clerk's screen is a
    // rule-31 breach, and it is the failure mode that is invisible.
    const options = kindFilterOptions(["refund", "store_voucher"], (key) => key);
    expect(options.map((option) => option.value)).toEqual(["refund"]);
    expect(refundKindLabelKey("store_voucher")).toBeNull();
  });

  it("the Kind column cannot be hidden — a list with no Kind is a different screen", () => {
    const config = refundsAndCreditsConfig(
      (key) => key,
      REFUND_KINDS,
      refundStatusTone,
      LIFECYCLES,
    );
    expect(config.columns.find((column) => column.key === "kind")?.locked).toBe(true);
  });
});

describe("P4.10 — the screen moved, and the old address is not a dead link", () => {
  it("`REFUNDS_ROUTE` is the payments address and the Refunds tab points at it", () => {
    // ⚠ **THIS SUPERSEDES `CR-059` §10's PLACEMENT, NOT THE RULE BEHIND IT.**
    // The chain is written out on `paymentsShared.REFUNDS_ROUTE`; this case is
    // what makes putting it back a RED test rather than a quiet regression.
    expect(REFUNDS_ROUTE).toBe("/payments/refunds");
    expect(paymentsTabPath(PAYMENTS_TAB_REFUNDS)).toBe("/payments/refunds");
    expect(PAYMENTS_TABS.map((tab) => tab.path)).toContain("/payments/refunds");
  });

  it("the old Finance address is still declared, so nothing in circulation 404s", () => {
    expect(REFUNDS_LEGACY_ROUTE).toBe("/finance/refunds");
  });
});
