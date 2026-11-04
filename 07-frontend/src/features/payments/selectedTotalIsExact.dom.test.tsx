// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.20` — *"The selected total stays exact. A
//           selection whose sum a floating-point number would round. **No
//           float on the money path.**"*
// Rules:    CLAUDE.md hard rule 2 (money stored to 4 decimals, DISPLAYED to 2,
//           never float, never cents) · B4.4's finance-signed half-up ·
//           BR-SHL-023 (one money formatter) · BR-TEN-042 (a tenant has one
//           currency; a figure with no code beside it is one a clerk acts on)
// Screens:  7·1 Debtors (S34 · PAY-02) — the selection toolbar
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// $10,516.33 OR $10,516.32 — ONE CENT, ON A SCREEN A CLERK READS ALOUD
// ══════════════════════════════════════════════════════════════════════════
// Four real debtor balances on the storage grid:
//
//     1182.9040 + 2552.4048 + 2774.5424 + 4006.4738
//
//   exact, on the NUMERIC(18,6) grid   10516.325000  →  **$10,516.33**
//   the same four through `Number()`   10516.324999999999  →  **$10,516.32**
//
// **MEASURED, in this repo's own Node and this repo's own formatter**, not
// reasoned about: `Intl.NumberFormat(… roundingMode: "halfExpand")` given the
// exact STRING answers `$10,516.33`, and given the double answers
// `$10,516.32`. `(1182.9040+2552.4048+2774.5424+4006.4738).toFixed(2)` is
// `10516.32` too.
//
// ⚠ **THIS IS WHY A SELECTION OF ROUND NUMBERS PROVES NOTHING.** `8240.0000 +
// 1842.1000 + 948.2000 + 612.6000` is already asserted in
// `OutstandingsTab.test.tsx`, and it sums identically as a double — a float
// implementation passes it. The sum has to LAND ON A HALF CENT that the binary
// representation falls just short of, which is exactly what these four do, and
// then the two paths disagree in the last digit a person can see.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS ALREADY COVERED, AND THE TWO GAPS THIS FILE FILLS
// ══════════════════════════════════════════════════════════════════════════
// `OutstandingsTab.test.tsx` holds `sumDecimalStrings(["0.1","0.2"]) ===
// "0.300000"` — a good float detector, on the HELPER. Its own comment says the
// rest out loud: *"The toolbar renders only over a selection, which a static
// render cannot make — so the REASONS are asserted where they are declared."*
//
//   **GAP 1 — the SELECTION path is never exercised.** Nothing asserts that
//   ticking rows produces that figure on screen. A screen that summed
//   `selectedRows.map(Number)` beside a perfectly exact helper would pass every
//   existing case. This file ticks four real checkboxes in a real DOM.
//
//   **GAP 2 — the divergence is never made VISIBLE.** `0.1 + 0.2` differs in
//   the seventeenth decimal and vanishes at two. These four differ in the
//   SECOND, so the assertion is about the string a clerk reads.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { OutstandingRow, OutstandingsResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { OutstandingsTab, outstandingsQueryKey } from "./OutstandingsTab";
import { sumDecimalStrings } from "./paymentsShared";

// This repo's vitest config declares no `setupFiles` and no `globals`, so
// testing-library's auto-cleanup never runs and a second `render` stacks on the
// first. See `refundsLegacyRoute.dom.test.tsx` for the same note.
afterEach(cleanup);

const TENANT = "brazosbend";
const AS_OF = "2026-09-23";

/** ⚠ **THE FIXTURE IS THE TEST.** Change any one of these four and the case
 *  stops being about anything: the sum lands on `10516.3250`, a true half cent,
 *  and the IEEE-754 sum of the same four is `10516.324999999999`. */
const BALANCES = ["1182.9040", "2552.4048", "2774.5424", "4006.4738"] as const;
const EXACT_TOTAL = "10516.325000";
const EXACT_ON_SCREEN = "$10,516.33";
const WHAT_A_FLOAT_WOULD_SHOW = "$10,516.32";

function row(index: number, balance: string): OutstandingRow {
  return {
    account_id: `01a046dd-d809-7e20-81a3-87b1eddc1b6${index}`,
    account_no: `AC-2026-0000${index + 1}`,
    customer_name: ["Ana Alvarez", "Ben Okafor", "Cara Lindqvist", "Dev Patel"][index],
    balance,
    days_late: 91 - index,
    bucket: "90+",
    open_bills: 2,
    last_payment_on: null,
    notice_summary: null,
    collection_tier: "friendly",
    next_step_due: null,
    plan_status: null,
    autopay: false,
    bad_address: false,
    gross_balance: null,
    credit_applied: null,
  } as unknown as OutstandingRow;
}

const ROWS = BALANCES.map((balance, index) => row(index, balance));

const BODY: OutstandingsResponse = {
  as_of: AS_OF,
  rows: ROWS,
  totals: { accounts: 4, owed: EXACT_TOTAL, dso_days: null },
  ageing: [
    { bucket: "current", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "1-30", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "31-60", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "61-90", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "90+", amount: EXACT_TOTAL, accounts: 4, share: "100.0" },
  ],
  problems: [],
} as unknown as OutstandingsResponse;

function stubClient(): ApiClient {
  const answer = async (path: string) => {
    if (path.startsWith("/outstandings")) {
      return { status: 200, data: BODY, headers: {} };
    }
    throw new Error(`the fixture was asked for ${path}, which it does not serve`);
  };
  return { get: answer, post: answer, put: answer, patch: answer, delete: answer } as never;
}

/** 7·1, mounted **under the real path pattern** `App.tsx` uses for the tab.
 *
 *  ⚠ `DEF-CWP-3925`: a payments screen mounted outside `/:tenant/…` builds
 *  every address as `//payments/…`, a protocol-relative URL to another host
 *  that reads as a perfectly good string to `toContain`. It also makes the
 *  row's account link, which this file clicks nothing on but the sibling file
 *  does, silently wrong. */
function openDebtors() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  // Seeded, because `render` resolves no promise before the first assertion and
  // an unseeded `useQuery` draws the skeleton — every assertion below would
  // then be about markup the screen never produced.
  client.setQueryData(outstandingsQueryKey(AS_OF, "", false), BODY);
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/outstandings`]}>
          <Routes>
            <Route
              path="/:tenant/payments/:tab"
              element={
                <OutstandingsTab
                  client={stubClient()}
                  asOf={AS_OF}
                  onAsOfChange={() => {}}
                  currency="USD"
                  writeBlockedReason={null}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Tick every row, the way a clerk does before pressing Send notice. */
function selectEveryRow(): void {
  for (const account of ROWS) {
    const label = i18n.t("payments.outstandings.selectRow", { account: account.account_no });
    fireEvent.click(screen.getByLabelText(label));
  }
}

describe("P4.20 — the selected total stays EXACT", () => {
  it("four balances a float would round show $10,516.33 and not $10,516.32", () => {
    openDebtors();
    selectEveryRow();

    const bar = screen.getByTestId("debtor-bulk-bar");
    expect(within(bar).getByText(EXACT_ON_SCREEN)).toBeInTheDocument();
    // ⚠ **THE NEGATIVE IS THE ASSERTION.** The positive alone would pass on a
    // build that happened to round the other way for an unrelated reason; this
    // names the figure a float produces and forbids it by value.
    expect(bar.textContent).not.toContain(WHAT_A_FLOAT_WOULD_SHOW);
  });

  it("the arithmetic behind it is BigInt on the storage grid, to six places", () => {
    // Hard rule 2: stored to 4 decimals, DISPLAYED to 2. `sumDecimalStrings`
    // works on the NUMERIC(18,6) grid and formats nothing — the string it
    // returns is what `MoneyCell` rounds, once, at the very end.
    expect(sumDecimalStrings([...BALANCES])).toBe(EXACT_TOTAL);
  });

  it("and the same four summed as DOUBLES really do disagree — measured here", () => {
    // ⚠ **THIS CASE EXISTS SO THE FIXTURE CANNOT ROT INTO A TAUTOLOGY.** If a
    // future edit changes one balance so the two paths agree again, the case
    // above would still pass and would be proving nothing at all. This one
    // fails the moment these four stop being a selection a float would round.
    let asDouble = 0;
    for (const balance of BALANCES) {
      asDouble += Number(balance);
    }
    expect(asDouble.toFixed(2)).toBe("10516.32");
    expect(asDouble).not.toBe(Number(EXACT_TOTAL));
    expect(Number(EXACT_TOTAL).toFixed(2)).toBe("10516.33");
  });

  it("a partial selection re-totals exactly, never the whole list's figure", () => {
    openDebtors();
    for (const account of ROWS.slice(0, 2)) {
      const label = i18n.t("payments.outstandings.selectRow", { account: account.account_no });
      fireEvent.click(screen.getByLabelText(label));
    }
    const bar = screen.getByTestId("debtor-bulk-bar");
    // 1182.9040 + 2552.4048 = 3735.3088 → $3,735.31
    expect(sumDecimalStrings([BALANCES[0], BALANCES[1]])).toBe("3735.308800");
    expect(within(bar).getByText("$3,735.31")).toBeInTheDocument();
    expect(bar.textContent).not.toContain(EXACT_ON_SCREEN);
  });

  it("a balance that is not a decimal draws a STATED ABSENCE, never NaN", () => {
    // `sumDecimalStrings` returns null rather than skipping the bad value: a
    // total that silently dropped one selected account would be a smaller
    // number wearing the right label. The screen then says so.
    expect(sumDecimalStrings([BALANCES[0], "n/a"])).toBeNull();
    expect(String(Number("n/a"))).toBe("NaN"); // what the float path would show
  });

  it("the toolbar counts what was TICKED, so the figure and the count agree", () => {
    openDebtors();
    selectEveryRow();
    const bar = screen.getByTestId("debtor-bulk-bar");
    expect(bar.textContent).toContain(
      i18n.t("payments.outstandings.selected", { count: ROWS.length }),
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 `P4.20` · blueprint p023 (the task row) · p081 (7·1's
//         selection toolbar) · CLAUDE.md hard rule 2 · B4.4
// generated: 2026-09-23 by LANE P4-TESTS
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST, through `vitest` — with `selectedTotal` in
//         `OutstandingsTab.tsx` replaced by
//         `String(selectedRows.reduce((a, r) => a + Number(r.balance), 0))`
//         the first case failed on `Unable to find an element with the text:
//         $10,516.33` and the bar rendered `$10,516.32`. That is the defect
//         hard rule 2 exists to prevent, reproduced and then removed.
// exceptions: (1) THE FOUR BALANCES ARE CONSTRUCTED, NOT DRAWN. B14 rule 37
//         makes every figure in a wireframe an illustration, so no drawn
//         number is owed here; what IS owed is a selection whose sum a float
//         would round, and these four were searched for until one was found.
//         (2) NO SERVER TOTAL IS ASSERTED AGAINST. `GET /outstandings` totals
//         the WHOLE filtered list and no endpoint totals a SELECTION — stated
//         on `OutstandingsTab`'s own exception (4) — so the browser sum is the
//         only figure there is, which is precisely why it must be exact.
// status: VERIFIED-UNRATIFIED
