// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-1702 — nine list screens had no filter control. FIVE were
//           `inert`: `filterBarSlot` held a `WorklistSegments` strip whose
//           handler was `onSelect={() => undefined}`, or nothing at all.
// Change:   CR-045 wave G (the wave-D lane finished four; these are the five
//           it measured as worse than bare)
// Rules:    BR-SHL-010 (only DECLARED capabilities render) · BR-SHL-011 (the
//           `f.<name>` URL grammar) · B14 rule 12 (one toolbar row)
// ───────────────────────────────────────────────────────
//
// **WHY THIS FILE EXISTS BESIDE THE FIVE STATIC SUITES.**
//
// Each screen's own suite now asserts that `f.<name>` reaches the URL. That is
// the right assertion and it has one hole: it drives `listX(…, {filters})`
// DIRECTLY. It proves the WRAPPER serializes, and it cannot prove that a person
// clicking the panel ever reaches the wrapper — which is the whole of hard-won
// law 2, and the reason four of these screens shipped with a control that
// rendered and did nothing.
//
// So this file does the one thing no static render can: it CLICKS.
//
// ⚠ **AND THE ASSERTION IS BUILT SO THAT CLIENT-SIDE FILTERING FAILS IT.** The
// unfiltered response holds `A-100` and `A-200`. The filtered response holds
// `A-999` **and nothing else** — a row that is NOT in the unfiltered set. If the
// screen narrowed the page in hand, `A-999` could never appear, because it was
// never in the browser. It appears only if the request went out again and the
// SERVER answered a different result set. The total moves with it (2 → 1), so
// the pager reports the server's count and not `rows.length`.
//
// That is the difference DEF-1702 turns on: *"a control that narrowed the page
// in hand would show a subset of a subset, which is worse than the bare toolbar
// this defect is about."*
//
// ⚠ **ONE SCREEN, AND THAT IS A MEASURED CHOICE RATHER THAN A SHORTCUT.** The
// round trip under test is entirely shared: `FilterBar` writes `state.filters`,
// the screen's `queryKey` carries it, and `worklistFilterParams` serializes it.
// All five screens use those three and nothing else, so a second copy of this
// fixture would re-test the same three functions through a different set of
// column renderers. What is NOT shared — which dimension each screen declares
// and which options it may offer — is asserted per screen, in each screen's own
// suite, where the reasoning for it lives.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";

import { TransfersTab } from "./TransfersTab";
import type { TransferList, TransferRow } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";

afterEach(cleanup);

function row(accountNo: string, state: string): TransferRow {
  return {
    id: `id-${accountNo}`,
    transfer_no: null,
    transfer_no_unavailable: null,
    state,
    step: 3,
    step_of: 5,
    step_label: "Final read",
    step_cell: "3 of 5",
    customer_id: `cust-${accountNo}`,
    customer: `Customer ${accountNo}`,
    customer_no: `C-${accountNo}`,
    from_account_id: `from-${accountNo}`,
    from_account_no: accountNo,
    to_account_id: null,
    to_account_no: null,
    from_cell: [accountNo, "→ —"],
    to_unit_id: null,
    from_to: { from: "1 Old Road", to: null, to_absence: { reason: "not chosen yet" } },
    out_date: null,
    in_date: null,
    same_day: null,
    deposit_carry_elected: false,
    arrears_follow_elected: false,
    committed_at: null,
    cancelled_at: null,
    money: { currency: "USD", lines: [], sentences: [], gaps: [], unavailable: [] },
    moving_this_week: false,
  };
}

function list(rows: TransferRow[]): TransferList {
  return {
    rows,
    kpis: {
      open: rows.length,
      moving_this_week: 0,
      deposits_carrying: 0,
      arrears_following: 0,
      completed_this_month: 0,
      period_basis: "calendar month",
      as_of: "2026-08-27",
    },
    page: 1,
    per: 50,
    total: rows.length,
    pages: 1,
    columns: ["reference", "customer", "fromTo", "outDate", "inDate", "money", "step", "state"],
    // The SERVER's own vocabulary — `TRANSFER_FILTER_STATES`, which subtracts
    // `cancelled` because `list_queryset` excludes it. The panel reads this and
    // never a list typed on the client (BR-SHL-010).
    filters: ["state"],
    states: [{ code: "scheduled" }, { code: "in_progress" }, { code: "done" }],
    steps: [{ step: 3, label: "Final read" }],
    search: { hint: "Customer, account #, or either address…", min_chars: 2, legs: [], unavailable: [] },
    exclusion: { callout: "One job, not two.", contract: [], half_account_ids: [] },
    as_of: "2026-08-27",
  };
}

/** The UNFILTERED page, and the DIFFERENT result set the server answers for
 *  `f.state=done`. `A-999` is deliberately absent from the first. */
const UNFILTERED = list([row("A-100", "scheduled"), row("A-200", "in_progress")]);
const FILTERED = list([row("A-999", "done")]);

function mount(): { urls: string[] } {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      urls.push(url);
      return new Response(JSON.stringify(url.includes("f.state=done") ? FILTERED : UNFILTERED), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=transfers`]}>
        <TransfersTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { urls };
}

describe("DEF-1702 · CR-045 wave G — the worklist filter narrows the SERVER's result set", () => {
  it("ticking a filter option issues a NEW request carrying `f.state`, and the rows that come back are the SERVER's", async () => {
    const user = userEvent.setup();
    const { urls } = mount();

    // ── 1 · the unfiltered list, and no `f.` on the first request ──────────
    await waitFor(() => expect(screen.getByText("A-100")).toBeInTheDocument());
    expect(screen.getByText("A-200")).toBeInTheDocument();
    expect(screen.queryByText("A-999")).not.toBeInTheDocument();
    expect(urls).toHaveLength(1);
    expect(urls[0]).not.toContain("f.");

    // ── 2 · open the ONE panel B14 rule 12 puts on the toolbar row ────────
    // ⚠ **THE `▾` IS ITS OWN `aria-hidden` SPAN, so the summary's text is
    // SPLIT and `getByText("+ Filter ▾")` finds nothing — measured, it is the
    // first thing this case failed on. The regex matches the word.
    await user.click(screen.getByText(/\+ Filter/));

    // ⚠ **THE OPTION IS FOUND BY ITS OWN LABEL, NOT BY A COLUMN HEADING.** The
    // sibling suites learned this the hard way: `getByText("Loaded")` matched a
    // `<th>` and would have passed on an empty list. `Done` is a checkbox label
    // inside the panel, and the STATE column heading on this table reads
    // `State`, so there is no collision — but the query is scoped to the
    // checkbox's accessible name rather than to page text for that reason.
    await user.click(screen.getByRole("checkbox", { name: "Done" }));

    // ── 3 · a SECOND request went out, and it carried BR-SHL-011's grammar ──
    await waitFor(() => expect(urls).toHaveLength(2));
    expect(urls[1]).toContain("f.state=done");
    expect(urls[1]).not.toMatch(/[?&]state=done/);

    // ── 4 · THE ASSERTION THAT CLIENT-SIDE FILTERING CANNOT PASS ──────────
    // `A-999` was never in the browser. It is on screen only because the
    // request went out again and the server answered a different result set.
    await waitFor(() => expect(screen.getByText("A-999")).toBeInTheDocument());
    expect(screen.queryByText("A-100")).not.toBeInTheDocument();
    expect(screen.queryByText("A-200")).not.toBeInTheDocument();

    // ── 5 · and the TOTAL is the server's, not `rows.length` after a slice ──
    expect(screen.getByText("1–1 of 1")).toBeInTheDocument();

    // ── 6 · IS-4's chip is on screen, so the user can see WHY the list is
    //        short and can undo it in one click (DEF-442's load-bearing half) ─
    expect(screen.getByRole("button", { name: /clear all/i })).toBeInTheDocument();
  });

  it("clearing the filter asks the server for the unfiltered list again", async () => {
    const user = userEvent.setup();
    const { urls } = mount();
    await waitFor(() => expect(screen.getByText("A-100")).toBeInTheDocument());

    await user.click(screen.getByText(/\+ Filter/));
    await user.click(screen.getByRole("checkbox", { name: "Done" }));
    await waitFor(() => expect(screen.getByText("A-999")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /clear all/i }));

    // ⚠ A THIRD REQUEST, NOT A CACHE READ THAT HAPPENS TO LOOK RIGHT. The
    // unfiltered page IS in cache, so react-query may answer instantly — what
    // this asserts is that the SCREEN went back to the unfiltered KEY, which is
    // the half that breaks when `state.filters` is left out of `queryKey`.
    await waitFor(() => expect(screen.getByText("A-100")).toBeInTheDocument());
    expect(screen.queryByText("A-999")).not.toBeInTheDocument();
    expect(urls.filter((url) => url.includes("f.state=done"))).toHaveLength(1);
  });
});
