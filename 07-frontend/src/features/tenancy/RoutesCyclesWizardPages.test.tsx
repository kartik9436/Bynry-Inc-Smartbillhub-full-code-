// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3-T5 (PO 2026-08-23) — the wizards become ADDRESSABLE
//          full-page routes with their own screen ids, and Edit opens PRE-FILLED.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §4, §7
// Story:   US-MET-006  Screens: SET-06.1–4 · SET-07.1–4
// Rules:   BR-SHL-011 (URL grammar — a stateful surface is addressable) ·
//          BR-MET-035b (read-only WITH the reason) · DEF-222 (an edit commits
//          with "Save … ✓", never "Create … ✓")
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE DEFECT THIS TASK CLOSES IS INVISIBLE FROM THE SOURCE.** SET-06 and
 * SET-07 were `useState` inside the landing tab: three steps into a route,
 * with 140 premises picked, F5 put the user back on the list with nothing
 * kept — and every test passed, because nothing in a component test presses
 * refresh. The fix is a URL, and the assertion is that each of the four flows
 * HAS one and that the editor arrives with the row already in it.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CycleRow, RouteDetail } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { CycleWizardPage, RouteWizardPage } from "./RoutesCyclesWizardPages";
import { routeDetailQueryKey } from "./RouteDetailPage";
import { cycleWizardPath, routeWizardPath } from "./routesCyclesShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ROUTE: RouteDetail = {
  id: "r1",
  code: "RT-001",
  name: "Downtown",
  route_type: "walk",
  feeder_ref: null,
  assigned_to: null,
  cycle_id: null,
  cycle_code: null,
  status: "active",
  members: 0,
  meters: 0,
  collected: null,
  last_completion: null,
  progress: null,
  service_id: "s1",
  service_code: "water",
  services: ["water"],
  service_ids: ["s1"],
  area_id: null,
  area_code: null,
  area_name: null,
  notes: "Gate code 4417",
  premises: 0,
  units: 0,
  meters_available: 0,
  meters_excluded: 0,
  excluded_asset_ids: [],
  exclusions: [],
  membership: [],
  premises_order: [],
};

const CYCLE: CycleRow = {
  id: "c1",
  code: "CY-001",
  routes: [],
  window_start: null,
  window_end: null,
  bill_date: null,
  due_days: null,
  due_date: null,
  expected: 0,
  collected: null,
  progress: null,
  status: "scheduled",
  lifecycle_status: "active",
  name: "Monthly — residential",
  frequency: "Monthly",
  start_day: 1,
  days_to_complete: 3,
  read_window_source: "derived",
  first_run_date: "2026-10-01",
  bill_day: 5,
  accounts: 0,
  route_ids: [],
  proposed_windows: [],
  next_period: null,
  next_cycle_date: null,
  effective_start_day: 1,
  start_day_differs: false,
  schedule_warning: null,
  schedule_gap: null,
};

function seed(): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(routeDetailQueryKey("r1"), ROUTE);
  // ⚠ **BY ID, NOT A LIST (`DEF-MET-5743`).** The editor read `GET /cycles`
  // whole and `.find` its row, and was handed every route in the tenant for
  // step 2. It reads `GET /cycles/{id}` now — which has existed since RC-W3b —
  // and step 2 asks for the page it draws, so the fixture seeds one cycle by
  // id and the cycle's own routes, and nothing seeds a whole-tenant list.
  queryClient.setQueryData([...queryKeys.cycles, "c1"], CYCLE);
  queryClient.setQueryData(["cycles", "routes", "c1"], []);
  // The wizard's own step-1 reads (`RoutesCyclesWizards`): it renders a
  // skeleton until BOTH land, so a page test that seeded only the row would
  // assert against a skeleton and pass every absence check in the file.
  queryClient.setQueryData(["settings", "services"], []);
  queryClient.setQueryData(["lookups", "areas", "picker"], { results: [], count: 0 });
  queryClient.setQueryData(["routes", "next-code"], { code: "RT-002", warnings: [] });
  queryClient.setQueryData(["cycles", "next-code"], { code: "CY-002", warnings: [] });
  return queryClient;
}

function renderAt(path: string): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={seed()}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/acme${path}`]}>
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/routes/new"
              element={<RouteWizardPage />}
            />
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/routes/:routeId/edit"
              element={<RouteWizardPage />}
            />
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/cycles/new"
              element={<CycleWizardPage />}
            />
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/cycles/:cycleId/edit"
              element={<CycleWizardPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("RC-W3-T5 — each wizard is a URL, so a refresh keeps the flow", () => {
  it("the route creator renders at its own path", () => {
    const html = renderAt(routeWizardPath(null));
    expect(html).toContain(t("settings.routes.wizard.headNew"));
    expect(html).toContain(t("settings.routes.wizard.step1Title"));
  });

  it("the cycle creator renders at its own path", () => {
    const html = renderAt(cycleWizardPath(null));
    expect(html).toContain(t("settings.cycles.wizard.headNew"));
  });
});

describe("RC-W3-T5 — Edit opens PRE-FILLED, and commits with Save (DEF-222)", () => {
  it("the route editor arrives with the row's own values already in the fields", () => {
    const html = renderAt(routeWizardPath("r1"));
    expect(html).toContain(t("settings.routes.wizard.headEdit"));
    // The row, not a blank form: its code, its name and its notes.
    expect(html).toContain('value="RT-001"');
    expect(html).toContain('value="Downtown"');
    expect(html).toContain("Gate code 4417");
    // ⚠ AND NOT THE CREATOR'S HEADING. An editor that says "New route" over a
    // pre-filled form is the DEF-222 shape one step earlier.
    expect(html).not.toContain(t("settings.routes.wizard.headNew"));
  });

  it("the cycle editor arrives pre-filled from the cycles list", () => {
    const html = renderAt(cycleWizardPath("c1"));
    expect(html).toContain(t("settings.cycles.wizard.headEdit"));
    expect(html).toContain('value="CY-001"');
    expect(html).toContain('value="Monthly — residential"');
  });

  it("DEF-222: the commit verb agrees with the step-4 title, in both wizards", () => {
    // The pair a person reads a second apart. `commitSave` is chosen on
    // `editing`, `commitActivate` on create — and this is the general guard the
    // defect's own prevention note asked for.
    expect(t("settings.routes.wizard.step4TitleEdit", { code: "RT-001" })).toContain("save");
    expect(t("settings.routes.wizard.commitSave")).toContain("Save");
    expect(t("settings.routes.wizard.commitActivate")).toContain("Create");
    expect(t("settings.cycles.wizard.step4TitleEdit", { code: "CY-001" })).toContain("save");
    expect(t("settings.cycles.wizard.commitSave")).toContain("Save");
    expect(t("settings.cycles.wizard.commitActivate")).toContain("Create");
  });
});
