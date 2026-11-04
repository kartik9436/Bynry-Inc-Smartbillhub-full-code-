// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 8, lane FIX-8B — Work › Orders (image 01):
//             DEF-WRK-9689 — no Select all (beta #29, P3.6)
//             DEF-WRK-9582 — job type and sub-type were one flat list (P2.3)
//             DEF-WRK-9680 — the five tiles wrapped at 1440 (the kit's opt-in;
//                            the row count itself is measured in the browser,
//                            because jsdom performs no layout)
//             DEF-SHL-5345 — two clear crosses in the search box
//           Each case was run against the tip BEFORE the fix first and failed;
//           the failures are quoted in CR-168 §30.
// ───────────────────────────────────────────────────────
//
// ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2's fixture clause).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { OrdersPage } from "./OrdersPage";
import type { WorkOrderDispatchRow } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;
const EMPTY = { count: 0, next: null, previous: null, results: [] };

afterEach(() => cleanup());

function row(n: number): WorkOrderDispatchRow {
  return {
    id: `wo-${n}`,
    order_no: `WO-00${n}`,
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
    due_at: null,
    window_start: null,
    window_end: null,
    dispatch_state: "queued",
    source: "dispatcher",
    source_ref: null,
    area: null,
  } as WorkOrderDispatchRow;
}

const TYPES = {
  count: 4,
  next: null,
  previous: null,
  results: [
    { id: "t-el", code: "ELECTRICAL_LINE", name: "Electrical Line", active: true, is_system: false, used_by: 0, parent_name: null },
    { id: "t-out", code: "OUTAGE", name: "Outage report", active: true, is_system: false, used_by: 0, parent_name: "Electrical Line" },
    { id: "t-tx", code: "TX_FAULT", name: "Transformer fault", active: true, is_system: false, used_by: 0, parent_name: "Electrical Line" },
    { id: "t-mx", code: "METER_EXCHANGE", name: "Meter exchange", active: true, is_system: false, used_by: 0, parent_name: null },
  ],
};

/** 3 orders match; a page of 50 shows two of them (the third is on page 2 of
 *  a small page), and a read of 500 answers all three. */
function client(reads: { path: string; query: Record<string, unknown> }[]): ApiClient {
  const all = [row(41), row(42), row(43)];
  return {
    get: async (path: string, opts?: { query?: Record<string, unknown> }) => {
      const query = opts?.query ?? {};
      reads.push({ path, query });
      if (path === "/work-orders") {
        const results = Number(query.per) >= 500 ? all : all.slice(0, 2);
        return ok({ count: 3, next: null, previous: null, results });
      }
      if (path === "/work/kpis")
        return ok({
          open_total: 3,
          unassigned: { count: 3 },
          due_today: { count: 0, urgent: 0 },
          in_field: { count: 0 },
          awaiting_approval: { count: 0 },
          overdue: { count: 0, worst: null },
        });
      if (path === "/lookups/work_order_types") return ok(TYPES);
      if (path === "/work/areas") return ok({ results: [] });
      if (path === "/work/crews") return ok({ ...EMPTY, counts: { rows: 0, people: 0, crews: 0, contractors: 0 } });
      if (path.startsWith("/lookups/")) return ok(EMPTY);
      return ok(EMPTY);
    },
    post: async () => ok({}),
    patch: async () => ok({}),
    put: async () => ok({}),
    del: async () => ok({}),
    request: async () => ok({}),
  } as unknown as ApiClient;
}

function mount(reads: { path: string; query: Record<string, unknown> }[] = []) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
          <Routes>
            <Route path="/:tenant/work/orders" element={<OrdersPage client={client(reads)} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-WRK-9689 — Select all, then every order the filter matches (beta #29, P3.6)", () => {
  it("the head box ticks the page; Choose all 3 gathers the rest, page by page", async () => {
    const reads: { path: string; query: Record<string, unknown> }[] = [];
    const { container } = mount(reads);
    await waitFor(() => expect(screen.getAllByText("WO-0042").length).toBeGreaterThan(0));
    const head = container.querySelector("thead input[type=checkbox][data-select-all]") as HTMLInputElement;
    expect(head, "no Select all box in the select column's head").not.toBeNull();
    expect(head.getAttribute("aria-label")).toBe(t("work.orders.selectAll"));
    fireEvent.click(head);
    expect(container.querySelector("[data-bulk-bar]")?.textContent).toContain(
      t("work.orders.bulk.selected", { count: 2 }),
    );
    const chooseAll = await screen.findByText(t("work.orders.bulk.chooseAll", { n: 3 }));
    fireEvent.click(chooseAll);
    await waitFor(() => expect(screen.getByText(t("work.orders.bulk.allChosen", { n: 3 }))).toBeTruthy());
    expect(container.querySelector("[data-bulk-bar]")?.textContent).toContain(
      t("work.orders.bulk.selected", { count: 3 }),
    );
    // Paged, never unpaginated (NFR-3): the gathering read names its page size.
    expect(reads.some((r) => r.path === "/work-orders" && r.query.per === 500 && r.query.page === 1)).toBe(true);
  });
});

describe("DEF-WRK-9582 — the Type filter is two levels: a heading, its sub-types under it (P2.3)", () => {
  it("Electrical Line is a heading; Outage report and Transformer fault sit indented under it", async () => {
    const { container } = mount();
    await waitFor(() => expect(container.querySelector('label[data-filter-level="2"]')).not.toBeNull());
    const labels = Array.from(container.querySelectorAll("fieldset label")).map((l) => ({
      text: l.textContent,
      level: l.getAttribute("data-filter-level"),
    }));
    const typeRows = labels.filter((l) => ["Electrical Line", "Outage report", "Transformer fault", "Meter exchange"].includes(l.text ?? ""));
    expect(typeRows).toEqual([
      { text: "Electrical Line", level: "1" },
      { text: "Outage report", level: "2" },
      { text: "Transformer fault", level: "2" },
      { text: "Meter exchange", level: null },
    ]);
  });
});

describe("DEF-WRK-9680 — the five Orders tiles are a strip of COUNTS (image 01)", () => {
  it("opts into the kit's count track, so five fit one row at 1440", async () => {
    const { container } = mount();
    await waitFor(() => expect(container.querySelector(".kpi-grid")).not.toBeNull());
    const grid = container.querySelector(".kpi-grid") as HTMLElement;
    expect(grid.getAttribute("data-kpi-tiles")).toBe("count");
    expect(grid.style.getPropertyValue("--kpi-tile-min")).toBe("14rem");
  });
});

describe("DEF-SHL-5345 — the toolbar search shows ONE clear cross", () => {
  it("the browser's own search-cancel button is hidden on the kit's search box", async () => {
    const { container } = mount();
    await waitFor(() => expect(container.querySelector('input[type="search"]')).not.toBeNull());
    const box = container.querySelector('input[type="search"]') as HTMLInputElement;
    expect(box.className).toContain("[&::-webkit-search-cancel-button]:appearance-none");
  });
});

describe("DEF-WRK-9698 — the order number never wraps (image 01)", () => {
  it("the Order cell carries whitespace-nowrap, so WO-0016 is one line at 1440", async () => {
    // jsdom performs no layout, so this asserts the CLASS; the line count is
    // measured in Chromium by 10-scripts/cr168_finw_walk.mjs (one line each).
    const { container } = mount();
    await waitFor(() => expect(container.querySelector("[data-order-no]")).not.toBeNull());
    const cells = [...container.querySelectorAll("[data-order-no]")] as HTMLElement[];
    expect(cells.map((cell) => cell.textContent)).toEqual(["WO-0041", "WO-0042"]);
    for (const cell of cells) expect(cell.className.split(" ")).toContain("whitespace-nowrap");
  });
});
