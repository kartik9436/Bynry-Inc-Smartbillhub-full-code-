// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-029 RC-W5-T8 (PO 2026-08-23) — the browser walkthrough, and the
//           defect it found on the SET-05 sub-tabs.
// Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §4/§7
// Rules:    B17 §4 (the Cycles landing's ruled columns) · BR-SHL-013 (column
//           show/hide is per TABLE) · hard-won law 2 (built is not wired) ·
//           hard-won law 6 (diff the running app against the prototype)
// ───────────────────────────────────────────────────────
/**
 * **SIX OF NINE COLUMNS DISAPPEARED ON THE WAY A PERSON ACTUALLY GETS THERE.**
 *
 * Found in Chromium by W5-T8 and by nothing else. Loading
 * `/settings/reference-data/routes-cycles?rc=cycles` directly renders the
 * ruled landing exactly as B17 §4 specifies:
 *
 *     Cycle # · Name · Frequency · Start day · Days to complete · Routes ·
 *     Accounts · Status · Actions
 *
 * Landing on Routes — which is the default sub-tab, and therefore what every
 * user does — and then clicking **Cycles** renders **three**:
 *
 *     Cycle # · Name · Actions
 *
 * which is exactly the INTERSECTION of the two tables' column keys.
 *
 * **WHY.** `SettingsRoutesCyclesTab` renders
 * `active === "routes" ? <DataTable config={routeConfig}…/> : <DataTable
 * config={cycleConfig}…/>`. Both branches put a `DataTable` at the SAME
 * position under the same parent, so React reconciles them as ONE component
 * and keeps its state. `DataTable`'s `internalVisible` is
 * `useState(() => defaultVisibleColumns(config))` — initialised once, from
 * whichever config mounted first — and its own defensive line then drops every
 * stored key the new config does not declare (BR-SHL-024: an unknown
 * preference reads as absent). Two correct pieces of code; one wrong screen.
 *
 * **WHY EVERY GATE WAS GREEN.** The existing suites render ONE sub-tab, so the
 * shared instance never happens. G13 is about unwired props, G31 about classes,
 * G14 about the prototype's markup — none of them switches a tab. This file
 * does the switch, which is the only thing that shows it.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { ApiClient } from "@/api/client";
import type { CycleRow, RouteRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { RoutesCyclesTab } from "./SettingsRoutesCyclesTab";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ROUTE: RouteRow = {
  id: "r1",
  code: "RT-001",
  name: "Katy North",
  route_type: "walk",
  feeder_ref: null,
  assigned_to: null,
  cycle_id: "c1",
  cycle_code: "CY-001",
  status: "active",
  members: 2,
  meters: 2,
  collected: null,
  last_completion: null,
  progress: null,
  service_id: null,
  service_code: "water",
  services: ["water"],
  service_ids: [],
  area_id: null,
  area_code: "NORTH",
  area_name: "North district",
  notes: null,
  premises: 2,
  units: 3,
  meters_available: 2,
  meters_excluded: 0,
  excluded_asset_ids: [],
  exclusions: [],
};

const CYCLE: CycleRow = {
  id: "c1",
  code: "CY-001",
  name: "Residential monthly",
  frequency: "Monthly",
  start_day: 1,
  days_to_complete: 3,
  read_window_source: "derived",
  first_run_date: "2026-09-01",
  bill_day: 5,
  accounts: 48,
  route_ids: ["r1"],
  routes: ["RT-001"],
  proposed_windows: [],
  next_period: null,
  next_cycle_date: null,
  effective_start_day: 1,
  start_day_differs: false,
  schedule_warning: null,
  schedule_gap: null,
  window_start: "2026-08-01",
  window_end: "2026-08-03",
  bill_date: null,
  due_days: 20,
  due_date: null,
  expected: 2,
  collected: 0,
  progress: 0,
  status: "scheduled",
  lifecycle_status: "active",
} as CycleRow;

/** A client that answers both list endpoints with the paged envelope W5-T6
 *  made unconditional. */
function stubClient(): ApiClient {
  return {
    get: async (path: string) => {
      const rows = path.startsWith("/routes") ? [ROUTE] : [CYCLE];
      return { data: { count: 1, next: null, previous: null, results: rows }, status: 200 };
    },
  } as unknown as ApiClient;
}

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/settings/reference-data/routes-cycles"]}>
        <ToastProvider>
          <RoutesCyclesTab readOnly={false} client={stubClient()} />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function headers(): Promise<string[]> {
  const table = await screen.findByRole("table");
  return within(table)
    .getAllByRole("columnheader")
    .map((cell) => (cell.textContent ?? "").replace(/[▲▼]/g, "").trim());
}

describe("W5-T8 · the SET-05 sub-tabs keep their own columns", () => {
  it("shows the cycles landing's NINE ruled columns after switching from routes", async () => {
    const user = userEvent.setup();
    renderTab();

    // Land on Routes — the default, and what every user does.
    await waitFor(async () => expect(await headers()).toContain(t("settings.routes.col.routeNo")));

    await user.click(screen.getByRole("tab", { name: t("settings.routesCycles.subTab.cycles") }));

    const cycleHeaders = await waitFor(async () => {
      const found = await headers();
      expect(found).toContain(t("settings.cycles.col.cycleNo"));
      return found;
    });

    // B17 §4's Cycles landing, column for column. The six in the middle are the
    // ones that vanished.
    for (const label of [
      t("settings.cycles.col.cycleNo"),
      t("settings.cycles.col.name"),
      t("settings.cycles.col.frequency"),
      t("settings.cycles.col.startDay"),
      t("settings.cycles.col.daysToComplete"),
      t("settings.cycles.col.routes"),
      t("settings.cycles.col.accounts"),
      t("settings.routes.col.status"),
      t("settings.reference.col.actions"),
    ]) {
      expect(cycleHeaders).toContain(label);
    }
  });

  it("and switching BACK leaves the routes landing whole", async () => {
    // The same fault runs in both directions — the routes table would lose
    // Type, Service(s), Area, Members, Meters and Cycle on the way back.
    const user = userEvent.setup();
    renderTab();
    await waitFor(async () => expect(await headers()).toContain(t("settings.routes.col.routeNo")));
    await user.click(screen.getByRole("tab", { name: t("settings.routesCycles.subTab.cycles") }));
    await waitFor(async () => expect(await headers()).toContain(t("settings.cycles.col.frequency")));
    await user.click(screen.getByRole("tab", { name: t("settings.routesCycles.subTab.routes") }));

    const routeHeaders = await waitFor(async () => {
      const found = await headers();
      expect(found).toContain(t("settings.routes.col.routeNo"));
      return found;
    });
    for (const label of [
      t("settings.routes.col.type"),
      t("settings.routes.col.services"),
      t("settings.routes.col.area"),
      t("settings.routes.col.members"),
      t("settings.routes.col.meters"),
      t("settings.routes.col.cycle"),
    ]) {
      expect(routeHeaders).toContain(label);
    }
  });
});
