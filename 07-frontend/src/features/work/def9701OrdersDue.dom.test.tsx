// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-WRK-9701 — Work › Orders printed the Due date as `10/8/2026`
//           while the order page printed `10/09/2026`: two formats (and, across
//           a zone, two DAYS) for one fact in one workflow.
// Rules:    IS-8 (an instant shows in the TENANT's zone and format) · B14 rule
//           44 (our UI standard) — one formatter, `orderFormat.dueText`
// ───────────────────────────────────────────────────────
//
// ⚠ Mounted under the real path pattern and inside a tenant's regional
// settings, so the cell is read the way a Chicago utility's clerk reads it.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { OrdersPage } from "./OrdersPage";
import type { WorkKpis, WorkOrderDispatchRow } from "./workEndpoints";

afterEach(() => cleanup());

const CHICAGO = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" as const };
const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;
const EMPTY = { count: 0, next: null, previous: null, results: [] };
const KPIS: WorkKpis = {
  open_total: 1,
  unassigned: { count: 1 },
  due_today: { count: 0, urgent: 0 },
  in_field: { count: 0 },
  awaiting_approval: { count: 0 },
  overdue: { count: 0, worst: null },
};

// The tenant's midnight on 9 October, as the server keeps a picked due date —
// 05:00 UTC in Chicago. A browser reading it in UTC with its own locale prints
// `10/9/…`; one west of Chicago prints the 8th.
const DUE = "2030-10-09T05:00:00Z";

function row(): WorkOrderDispatchRow {
  return {
    id: "wo-0050",
    order_no: "WO-0050",
    type: "Meter exchange — residential",
    premise: { id: "p-1", premise_no: "P-00101", address: "101 Silver Creek Rd" },
    service: "water",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-24T12:00:00Z",
    priority: null,
    technician: null,
    due_at: DUE,
    window_start: null,
    window_end: null,
    dispatch_state: "queued",
    source: "dispatcher",
    source_ref: null,
    area: null,
  };
}

function client(): ApiClient {
  const reads: Record<string, unknown> = {
    "/work/kpis": KPIS,
    "/work/areas": { results: [] },
    "/work/crews": { ...EMPTY, counts: { rows: 0, people: 0, crews: 0, contractors: 0 } },
    "/work-orders": { count: 1, next: null, previous: null, results: [row()] },
  };
  return {
    get: async (path: string) => {
      if (path in reads) return ok(reads[path]);
      if (path.startsWith("/lookups/")) return ok(EMPTY);
      if (path.startsWith("/custom-fields")) return ok({ results: [] });
      return ok(EMPTY);
    },
  } as unknown as ApiClient;
}

describe("DEF-WRK-9701 — the list's Due reads through the tenant's one date formatter", () => {
  it("prints MM/DD/YYYY in the tenant's zone, the same string the order page prints", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.customFieldRegistry("work_orders", "WORK_EDIT", "input"), []);
    render(
      <QueryClientProvider client={queryClient}>
        <TenantRegionalProvider value={CHICAGO}>
          <ToastProvider>
            <MemoryRouter initialEntries={["/brazosbend/work/orders"]}>
              <Routes>
                <Route path="/:tenant/work/orders" element={<OrdersPage client={client()} />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getAllByText("WO-0050").length).toBeGreaterThan(0));
    const cell = document.querySelector(`[title="${DUE}"]`);
    expect(cell?.textContent).toBe("10/09/2030");
  });
});
