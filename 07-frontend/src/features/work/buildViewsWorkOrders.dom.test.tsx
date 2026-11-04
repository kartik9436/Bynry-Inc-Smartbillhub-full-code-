// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-004 — the jobs at a place, and on an account.
// Change:   CR-089 P8 (blueprint pages 32–34) · DEF-4739 (the table component)
//           · DEF-4740 (the columns)
// Rules:    B14 rule 12 (filters are chips) · rule 17 (an empty state says what
//           is missing and offers the action that fills it) · rule 31 (no
//           database id is ever a visible value)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ONE THING THIS FILE EXISTS TO ASSERT AND `buildViews.test.tsx`
// CANNOT.** That file renders to STATIC MARKUP, so it can see the tab's ARRIVAL
// state and nothing else. The blueprint draws the chip `OPEN` as the default
// filter, and the sentence the tab keeps — *every job here, finished ones
// included* — is only TRUE if pressing `All` brings the finished ones back. A
// static render can never answer that, and asserting it there would be a test
// named after a claim it does not make (hard-won law 7).
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`/:tenant/premises/:premisesId`),
// never bare: `DEF-CWP-3925`'s second lesson is that a component mounted with no
// matching route has `useParams()` undefined, so every address it builds comes
// out `//…` — a protocol-relative URL to another host, which reads as a
// perfectly good string to `toContain`.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { WorkOrdersTab, scopedOrdersQueryKey } from "./buildViews";
import type { ScopedWorkOrderList, ScopedWorkOrderRow } from "./workEndpoints";

const TENANT = "brazosbend";
const PREMISES = "prm-1408";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function order(over: Partial<ScopedWorkOrderRow> = {}): ScopedWorkOrderRow {
  return {
    id: "wo-4822",
    order_no: "WO-4822",
    type: "Meter change",
    premise: { id: PREMISES, premise_no: "P-01408", address: "412 Cypress Row" },
    service: "water",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-03T12:00:00Z",
    stands_on: "unit",
    scope: "per_unit",
    unit_label: "Unit 4",
    external_ref: null,
    completed_at: null,
    accepted_at: null,
    accepted_by: null,
    field_data: null,
    technician: null,
    window_start: null,
    window_end: null,
    due_at: null,
    ...over,
  };
}

const DONE = order({
  id: "wo-4610",
  order_no: "WO-4610",
  type: "Leak investigation",
  state: "completed",
  completed_at: "2026-09-01T15:00:00Z",
  unit_label: "Laundry",
});

function mount(rows: ScopedWorkOrderRow[]): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const payload: ScopedWorkOrderList = {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
  };
  queryClient.setQueryData(scopedOrdersQueryKey("premises", PREMISES), payload);
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/premises/${PREMISES}?tab=work-orders`]}>
        <Routes>
          <Route
            path="/:tenant/premises/:premisesId"
            element={
              <WorkOrdersTab
                host="premises"
                hostId={PREMISES}
                t={t}
                timeZone="America/Chicago"
                dateFormat="MM/DD/YYYY"
                openOrderId={null}
                onOpenOrder={() => undefined}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    </QueryClientProvider>,
  );
}

describe("CR-089 P8 — the drawn OPEN chip, pressed", () => {
  it("the tab arrives filtered to OPEN, and `All` brings the finished job back", () => {
    mount([order(), DONE]);
    expect(screen.getByText("WO-4822")).toBeTruthy();
    expect(screen.queryByText("WO-4610")).toBeNull();

    // r10's `All` chip is the clear-all control the moment something is
    // applied, and its accessible name says so.
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));

    expect(screen.getByText("WO-4822")).toBeTruthy();
    expect(screen.getByText("WO-4610")).toBeTruthy();
  });

  it("the search box matches WHERE, which is a column the drawer used to hide", () => {
    mount([order(), DONE]);
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    const search = screen.getByRole("searchbox");
    fireEvent.change(search, { target: { value: "Laundry" } });
    // IS-3 debounces the commit by 300 ms; the assertion below is about the
    // FILTER, so the state has to be given its chance to land.
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(screen.queryByText("WO-4822")).toBeNull();
        expect(screen.getByText("WO-4610")).toBeTruthy();
        resolve();
      }, 400);
    });
  });

  it("an address with no jobs offers the door the blueprint draws, and it opens", () => {
    mount([]);
    const raise = screen.getAllByText("⚡ Raise work here")[0].closest("a");
    // CR-168 round 3 (`DEF-WRK-4752`): the door carries the building.
    expect(raise?.getAttribute("href")).toBe(`/${TENANT}/work/orders/new?premises=${PREMISES}`);
  });
});

describe("record links (PO 2026-10-19) — the Work orders tab", () => {
  it("the order number opens the order's own page; the drawer stays the row's", () => {
    mount([order()]);
    const link = screen.getByRole("link", { name: "WO-4822" });
    expect(link.getAttribute("href")).toBe(`/${TENANT}/work/orders/wo-4822`);
  });
});
