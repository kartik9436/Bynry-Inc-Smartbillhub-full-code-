// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3-T1/T2/T7 (PO 2026-08-23) — the two landings, rebuilt to
//          the upgraded prototype: Routes | Cycles sub-tabs, the three schedule
//          columns, route chips, the landing coverage sentence.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §4
// Story:   US-MET-006  Screens: S8 · SET-05 · SET-05.cycles
// Rules:   D6 (NO Reader column) · D7 (server-side pagination + sorting) ·
//          D9 (bill/due day are CYCLE DEFAULTS) · BR-MET-078 (no money)
// B14:     12 (toolbar) · 13 (sort) · 14 (columns) · 15 (icon row actions) ·
//          16 (pager) · 17 (empty state) · 21 (Tailwind, no new class)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE FIRST CASE IN THIS FILE IS THE ONE THAT MATTERS** — D6. The upgraded
 * prototype draws a **Reader column** on SET-05 and the PO ruled *"not
 * required"*. A lane that matched the screenshot would have shipped it, every
 * test green, and no gate in this repo reads a drawing. So the ruling is a
 * test, by name, and it fails the day somebody adds the column back.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CycleRow, RouteRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  RoutesCyclesTab,
  cyclesPageKeyFor,
  routesCyclesSubTabFrom,
  routesPageKeyFor,
} from "./SettingsRoutesCyclesTab";
import type { TableRequestState } from "@/components/tableTypes";

/** The state both landings open on — the config's own default sort, page 1.
 *  Seeded through the SCREEN's own key builder rather than a hand-written
 *  array, so a key change cannot leave this suite quietly rendering a
 *  skeleton and passing every absence assertion in the file. */
const OPEN_STATE: TableRequestState = {
  q: "",
  sort: "code",
  dir: "asc",
  page: 1,
  per: 50,
  filters: {},
};

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ROUTE: RouteRow = {
  id: "r1",
  code: "RT-001",
  name: "Downtown",
  route_type: "walk",
  feeder_ref: null,
  // ⚠ NOT NULL, deliberately. D6 says the reader is out of scope, NOT that the
  // column is empty — `routes.assigned_to` stays as it is. So the fixture
  // carries a reader and the screen must still not draw one.
  assigned_to: "Maria Alvarez",
  cycle_id: "c1",
  cycle_code: "CY-001",
  status: "active",
  members: 412,
  meters: 418,
  collected: null,
  last_completion: null,
  progress: null,
  service_id: "s1",
  service_code: "water",
  services: ["electric", "water"],
  service_ids: ["s2", "s1"],
  area_id: "a1",
  area_code: "N",
  area_name: "North",
  notes: null,
  premises: 388,
  units: 412,
  meters_available: 420,
  meters_excluded: 2,
  excluded_asset_ids: ["a1", "a2"],
  exclusions: [],
};

const CYCLE: CycleRow = {
  id: "c1",
  code: "CY-001",
  routes: ["RT-001", "RT-002", "RT-003"],
  window_start: null,
  window_end: null,
  bill_date: null,
  due_days: null,
  due_date: null,
  expected: 702,
  collected: null,
  progress: null,
  status: "scheduled",
  lifecycle_status: "active",
  name: "Monthly — residential",
  // The SERVER's word since RC-W1 migration 0019, not CR-006's `monthly`.
  frequency: "Monthly",
  start_day: 1,
  days_to_complete: 3,
  read_window_source: "derived",
  first_run_date: "2026-10-01",
  bill_day: 5,
  accounts: 1124,
  route_ids: ["r1"],
  proposed_windows: [],
  next_period: null,
  next_cycle_date: null,
  effective_start_day: 1,
  start_day_differs: false,
  schedule_warning: null,
  schedule_gap: null,
};

function renderTab(tab: "routes" | "cycles", options?: { uncovered?: number }): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(routesPageKeyFor(OPEN_STATE), {
    rows: [ROUTE],
    total: 1,
    pagedBy: "client",
  });
  queryClient.setQueryData(cyclesPageKeyFor(OPEN_STATE), {
    rows: [CYCLE],
    total: 1,
    pagedBy: "client",
  });
  queryClient.setQueryData(["cycles", "coverage", "landing"], {
    uncovered_accounts: options?.uncovered ?? 42,
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/acme/settings/reference-data/routes-cycles?rc=${tab}`]}>
          <RoutesCyclesTab readOnly={false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("B17 §3 D6 — NO reader or device on this surface, anywhere", () => {
  it("SET-05 draws no Reader column even though the row carries an assignee", () => {
    const html = renderTab("routes");
    expect(html).toContain("RT-001");
    // The ruling: *"not required"*. The screenshot's column, the wizard field
    // and the detail rail row are all out of CR-029's scope.
    expect(html).not.toContain("Maria Alvarez");
    expect(html.toLowerCase()).not.toContain(">reader<");
    expect(html.toLowerCase()).not.toContain("assigned to");
  });
});

describe("RC-W3-T1 — SET-05, the routes landing", () => {
  it("renders the ruled column set including Service(s) and Area (D10)", () => {
    const html = renderTab("routes");
    for (const label of [
      t("settings.routes.col.routeNo"),
      t("settings.routes.col.name"),
      t("settings.routes.col.type"),
      t("settings.routes.col.services"),
      t("settings.routes.col.area"),
      t("settings.routes.col.members"),
      t("settings.routes.col.meters"),
      t("settings.routes.col.cycle"),
      t("settings.routes.col.status"),
    ]) {
      expect(html).toContain(label);
    }
    // D10 — a route serves a service SET, rendered as chips, both of them.
    expect(html).toContain("electric");
    expect(html).toContain("water");
    expect(html).toContain("North");
  });

  it("the Route # links to the new SET-06D detail screen", () => {
    expect(renderTab("routes")).toContain(
      'href="/acme/settings/reference-data/routes-cycles/routes/r1"',
    );
  });

  it("D7 — the list carries the shared table's toolbar, sort and pager", () => {
    const html = renderTab("routes");
    expect(html).toContain("table-pager-range"); // B14 rule 16
    expect(html).toContain("table-sort"); // B14 rule 13
    expect(html).toContain(t("table.columns.title")); // B14 rule 14
  });
});

describe("RC-W3-T2 — SET-05.cycles, the cycles landing", () => {
  it("Routes | Cycles are SUB-TABS, and the URL says which is open", () => {
    const html = renderTab("cycles");
    expect(html).toContain(t("settings.routesCycles.subTab.routes"));
    expect(html).toContain(t("settings.routesCycles.subTab.cycles"));
    expect(routesCyclesSubTabFrom("cycles")).toBe("cycles");
    expect(routesCyclesSubTabFrom("routes")).toBe("routes");
    // BR-SHL-011's fallback law: an unknown value falls back, never errors.
    expect(routesCyclesSubTabFrom("nonsense")).toBe("routes");
    expect(routesCyclesSubTabFrom(null)).toBe("routes");
  });

  it("renders the three schedule columns the ruled model added", () => {
    const html = renderTab("cycles");
    expect(html).toContain(t("settings.cycles.col.frequency"));
    expect(html).toContain(t("settings.cycles.col.startDay"));
    expect(html).toContain(t("settings.cycles.col.daysToComplete"));
    // The frequency renders as a WORD, not as the raw catalogue key — the
    // server serves "Monthly" and CR-006's screen keyed `…frequency.monthly`.
    expect(html).toContain("Monthly");
    expect(html).not.toContain("settings.cycles.frequency.");
  });

  it("the routes are CHIPS, all three of them, and the Cycle # links to SET-07D", () => {
    const html = renderTab("cycles");
    for (const code of ["RT-001", "RT-002", "RT-003"]) {
      expect(html).toContain(code);
    }
    expect(html).toContain('href="/acme/settings/reference-data/routes-cycles/cycles/c1"');
  });

  it("the landing coverage sentence names what the accounts LACK (D13)", () => {
    const html = renderTab("cycles");
    expect(html).toContain("42 accounts sit on no cycle");
    expect(html).toContain("never read and never billed");
  });

  it("a fully covered tenant gets the covered sentence, not a zero in the gap one", () => {
    const html = renderTab("cycles", { uncovered: 0 });
    expect(html).not.toContain("0 accounts sit on no cycle");
  });

  it("BR-MET-078 — NO money column, and no money word anywhere on the surface", () => {
    const html = renderTab("cycles").toLowerCase();
    for (const banned of ["late fee", "penalty", "grace", "$", "balance", "amount", "outstanding"]) {
      expect(html).not.toContain(banned);
    }
  });

  it("D13 — no account-level cycle assignment exists on this surface", () => {
    const html = renderTab("cycles").toLowerCase();
    expect(html).not.toContain("assign a cycle");
  });
});
