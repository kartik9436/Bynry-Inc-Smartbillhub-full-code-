// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3-T3/T4 (PO 2026-08-23) — SET-06D and SET-07D, two NEW
//          screens built to the upgraded prototype.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §4
// Story:   US-MET-006  Screens: SET-06D (route detail) · SET-07D (cycle detail)
// Rules:   D6 (NO reader rail row) · D9 (bill/due day are CYCLE DEFAULTS the run
//          may override) · D11 (walking order PER PREMISES) · D12 (NO Balance
//          column) · D13 (NO account-level cycle assignment) ·
//          BR-MET-078 (no money) · BR-AUD-010 (a per-entity Audit tab RENDERS
//          the entity's rows AND links to S61) · OQ-339 (month-end, UNRULED)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **FOUR OF THESE DESCRIBE BLOCKS EXIST BECAUSE THE SCREENSHOT IS WRONG.**
 * B17 §3 lists four places the PO's rulings supersede their own upgraded
 * prototype, and three of the four live on these two screens. Nothing in this
 * repo reads a drawing, so the rulings are asserted here by name.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  BillRunHistoryRow,
  CycleCoverage,
  CycleRow,
  RouteAccountsPayload,
  RouteDetail,
  RouteMeterPicker,
  RouteReadWindowRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";

import {
  CycleDetailPage,
  cycleCoverageQueryKey,
  cycleDetailQueryKey,
  cycleRunsQueryKey,
  runStatusLabel,
} from "./CycleDetailPage";
import {
  frequencyLabel,
  pluralKey,
  scheduleGapKey,
  windowStatusKey,
} from "./routesCyclesShared";
import {
  RouteDetailPage,
  routeAccountsQueryKey,
  routeDetailQueryKey,
  routeMetersQueryKey,
  routeReadWindowsQueryKey,
} from "./RouteDetailPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ROUTE: RouteDetail = {
  id: "r1",
  code: "RT-001",
  name: "Downtown",
  route_type: "walk",
  feeder_ref: null,
  // D6 — the column stays populated in the data and unrendered on the screen.
  assigned_to: "Maria Alvarez",
  cycle_id: "c1",
  cycle_code: "CY-001",
  status: "active",
  members: 5,
  meters: 3,
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
  premises: 3,
  units: 5,
  meters_available: 4,
  meters_excluded: 1,
  excluded_asset_ids: ["m4"],
  // ⚠ THE SERVED PER-UNIT `walk_order` IS THE STOP'S NUMBER (D11) — the server
  // projects the ruled per-premises order back onto it, so 1408 Elm's three
  // units all carry 1. It only ORDERS the rows and is never rendered.
  membership: [
    { unit_id: "u1", unit_label: "Apt 1", premises_id: "p1", premise_no: "1408 Elm", walk_order: 1 },
    { unit_id: "u2", unit_label: "Apt 2", premises_id: "p1", premise_no: "1408 Elm", walk_order: 1 },
    { unit_id: "u3", unit_label: "Apt 3", premises_id: "p1", premise_no: "1408 Elm", walk_order: 1 },
    { unit_id: "u4", unit_label: "House", premises_id: "p2", premise_no: "22 Cedar Ct", walk_order: 2 },
    { unit_id: "u5", unit_label: "House", premises_id: "p3", premise_no: "7 Birch Ln", walk_order: 3 },
  ],
  // D11 — the ruled walk, as `GET /routes/{id}` serves it back (RC-W3b).
  premises_order: [
    { premises_id: "p1", premise_no: "1408 Elm", walk_order: 1, units: 3 },
    { premises_id: "p2", premise_no: "22 Cedar Ct", walk_order: 2, units: 1 },
    { premises_id: "p3", premise_no: "7 Birch Ln", walk_order: 3, units: 1 },
  ],
  exclusions: [{ asset_id: "m4", reason: "premise demolished" }],
};

const METERS: RouteMeterPicker = {
  meters: [
    {
      id: "m1",
      asset_no: "MTR-W1001",
      unit_id: "u1",
      unit_label: "Apt 1",
      premises_id: "p1",
      address_line: "1408 Elm St",
      service_code: "water",
      size_class: "5/8",
      read_method: "walk",
      excluded: false,
      exclusion_reason: null,
    },
    {
      id: "m4",
      asset_no: "MTR-W2262",
      unit_id: "u4",
      unit_label: "House",
      premises_id: "p2",
      address_line: "22 Cedar Ct",
      service_code: "water",
      size_class: "5/8",
      read_method: "walk",
      excluded: true,
      // B17 §6 — *"two words, shown in place"*, and the served payload now
      // carries them (`selectors.route_meter_picker`).
      exclusion_reason: "premise demolished",
    },
  ],
  total: 2,
  included: 1,
  premises_without_meter: 1,
  // `CR-131-BRC07` — the picker answers by PREMISES and pages
  // server-side, so a fixture that omits these is not the payload.
  premises: 2,
  page: 1,
  per: null,
};

/**
 * ⚠ **RC-W2's PROPOSAL, AS THE SERVER NOW SENDS IT.** `cycles_list` carries
 * `proposed_windows` (with the screenshot's own Next/Scheduled statuses),
 * `next_period`, `next_cycle_date` and `schedule_gap`. The engine's worked
 * figure, from `period_engine.occurrences`: Monthly, start day 1, 3 days to
 * complete, first run 1 Sep 2026 → **1–3 Sep, 1–3 Oct, 1–3 Nov**.
 */
const CYCLE: CycleRow = {
  id: "c1",
  code: "CY-001",
  routes: ["RT-001", "RT-002"],
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
  frequency: "Monthly",
  start_day: 1,
  days_to_complete: 3,
  read_window_source: "derived",
  first_run_date: "2026-09-01",
  bill_day: 5,
  accounts: 1124,
  route_ids: ["r1", "r2"],
  proposed_windows: [
    { period_start: "2026-09-01", period_end: "2026-09-03", status: "Next", occurrence: 1 },
    { period_start: "2026-10-01", period_end: "2026-10-03", status: "Scheduled", occurrence: 2 },
    { period_start: "2026-11-01", period_end: "2026-11-03", status: "Scheduled", occurrence: 3 },
  ],
  next_period: { period_start: "2026-09-01", period_end: "2026-09-03" },
  next_cycle_date: "2026-09-01",
  effective_start_day: 1,
  start_day_differs: false,
  schedule_warning: null,
  schedule_gap: null,
};

const READ_WINDOWS: RouteReadWindowRow[] = [
  {
    id: "w1",
    route_id: "r1",
    cycle_id: "c1",
    period_start: "2026-08-01",
    period_end: "2026-08-03",
    read_on: "2026-08-03",
    // ⚠ NO `reader_id` / `reader_name`. OQ-343 (CLOSED 2026-08-23, PO verbatim
    // *"B: no reader anywhere, correct the screenshot and drop the stored
    // name"*) took the field out of the contract, so a fixture carrying
    // *"M. Chen"* here would not compile — which is the point. The absence
    // assertions below now test a screen that has nothing to leak.
    collected: 196,
    expected: 196,
    skips: 0,
    result: "Complete",
    closed_at: "2026-08-03T18:02:00Z",
  },
];

const ROUTE_ACCOUNTS: RouteAccountsPayload = {
  accounts: [
    {
      account_id: "a1",
      account_no: "ACC-1042",
      customer_name: "R. Okafor",
      status: "active",
      unit_id: "u1",
      unit_label: "Apt 1",
      premises_id: "p1",
      premise_no: "1408 Elm",
    },
  ],
  total: 1,
  units: 5,
  units_without_account: 4,
};

/** Two runs on CY-001: one finished and one that has issued nothing yet. */
const RUNS: BillRunHistoryRow[] = [
  {
    id: "run-1",
    // ⚠ ALWAYS NULL, and the fixture holds it null on purpose: the screenshot
    // reads "RUN-0814" and no number column, no series and no D5 ruling exist.
    run_no: null,
    cycle_id: "c1",
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    issued_at: "2026-08-01",
    accounts: 1124,
    bills_issued: 1118,
    held: 6,
    // ⚠ THE STORED COLUMN NOTHING EVER ADVANCES. A finished run still says
    // "draft"; the fixture carries it so "the column is absent" cannot be
    // mistaken for "the data happened to be empty".
    status: "draft",
    bill_type: "cycle",
    created_at: "2026-07-31T09:00:00Z",
  },
  {
    id: "run-2",
    run_no: null,
    cycle_id: "c1",
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    issued_at: null,
    accounts: 1124,
    bills_issued: 0,
    held: 0,
    status: "draft",
    bill_type: "cycle",
    created_at: "2026-08-23T09:00:00Z",
  },
];

const COVERAGE: CycleCoverage = {
  uncovered_accounts: 42,
  uncovered: [
    {
      account_id: "a9",
      account_no: "ACC-3020",
      customer_name: "T. Ngata",
      status: "active",
      unit_id: "u9",
      unit_label: "Unit 2",
      premises_id: "p9",
      premise_no: "7 Birch Ln",
      lacks: "route",
    },
  ],
  truncated: false,
};

function seed(cycle: CycleRow = CYCLE): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(routeDetailQueryKey("r1"), ROUTE);
  queryClient.setQueryData(routeMetersQueryKey("r1"), METERS);
  queryClient.setQueryData(routeReadWindowsQueryKey("r1"), READ_WINDOWS);
  queryClient.setQueryData(routeAccountsQueryKey("r1"), ROUTE_ACCOUNTS);
  queryClient.setQueryData(cycleDetailQueryKey("c1"), cycle);
  queryClient.setQueryData(cycleCoverageQueryKey("c1"), COVERAGE);
  queryClient.setQueryData(cycleRunsQueryKey("c1"), RUNS);
  queryClient.setQueryData(entityAuditQueryKey("route", "r1"), {
    page: { count: 0, next: null, previous: null, results: [] },
    window: { window: "hot", from: null },
  });
  queryClient.setQueryData(entityAuditQueryKey("cycle", "c1"), {
    page: { count: 0, next: null, previous: null, results: [] },
    window: { window: "hot", from: null },
  });
  return queryClient;
}

function renderRoute(tab = "premises"): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={seed()}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[`/acme/settings/reference-data/routes-cycles/routes/r1?tab=${tab}`]}
        >
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/routes/:routeId"
              element={<RouteDetailPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderCycle(tab = "schedule", cycle: CycleRow = CYCLE): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={seed(cycle)}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[`/acme/settings/reference-data/routes-cycles/cycles/c1?tab=${tab}`]}
        >
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/cycles/:cycleId"
              element={<CycleDetailPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The same cycle with the engine's silence instead of its proposal. */
function withGap(code: string, detail: string): CycleRow {
  return {
    ...CYCLE,
    proposed_windows: [],
    next_period: null,
    next_cycle_date: null,
    schedule_gap: { code, detail },
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// SET-06D · the route detail
// ═══════════════════════════════════════════════════════════════════════════

describe("SET-06D — the route detail, five tabs and a Facts rail", () => {
  it("draws all five ruled tabs and no sixth", () => {
    const html = renderRoute();
    for (const key of ["premises", "units", "assets", "accounts", "audit"]) {
      expect(html).toContain(t(`settings.routes.detail.tab.${key}`));
    }
  });

  it("the Facts rail carries the ruled facts including the service SET (D10)", () => {
    const html = renderRoute();
    expect(html).toContain(t("settings.routes.detail.fact.routeNo"));
    expect(html).toContain(t("settings.routes.detail.fact.services"));
    expect(html).toContain("electric");
    expect(html).toContain("water");
    // BR-MET-075 — both halves of the meter count, always.
    expect(html).toContain(t("settings.routes.detail.metersOnRoute", { meters: 3, excluded: 1 }));
  });

  it("D6 — the Facts rail has NO reader row, and no inline reader edit", () => {
    const html = renderRoute();
    expect(html).not.toContain("Maria Alvarez");
    expect(html.toLowerCase()).not.toContain("reader");
  });

  it("the members hint says where membership comes from and when a change lands", () => {
    expect(renderRoute()).toContain(t("settings.routes.detail.membersHint"));
  });
});

describe("SET-06D · D11 — the walking order is PER PREMISES", () => {
  it("a three-unit building is ONE stop at sequence 1, not three stops", () => {
    const html = renderRoute("premises");
    // Three premises, three stops.
    expect(html.match(/data-rc="stop"/g)).toHaveLength(3);
    expect(html).toContain("1408 Elm");
    // …and its three units are counted on the one stop.
    expect(html).toContain(t(pluralKey("settings.routes.detail.unitsOnStop", 3), { count: 3 }));
    // ⚠ DEF-224's own shape: a count of one must not read "1 units".
    expect(t(pluralKey("settings.routes.detail.unitsOnStop", 1), { count: 1 })).toBe("1 unit");
  });

  it("the reorder controls are real buttons with the stop's own name (keyboard, not mouse-only)", () => {
    const html = renderRoute("premises");
    expect(html).toContain(t("settings.routes.detail.moveUp", { stop: "22 Cedar Ct" }));
    expect(html).toContain(t("settings.routes.detail.moveDown", { stop: "1408 Elm" }));
    expect(html).toContain('draggable="true"');
  });

  it("a premises with no meter says so in place — it stays on the route", () => {
    expect(renderRoute("premises")).toContain(t("settings.routes.detail.noMeterVerify"));
  });

  it("Print route sheet exists and the printable list is the SAME order", () => {
    const html = renderRoute("premises");
    expect(html).toContain(t("settings.routes.detail.printSheet"));
    expect(html).toContain('data-rc="route-sheet"');
  });
});

describe("SET-06D · D12 — the Accounts tab is STATUS ONLY", () => {
  it("no Balance column, and no money word anywhere on the screen", () => {
    const html = renderRoute("accounts").toLowerCase();
    for (const banned of ["balance", "$", "amount", "outstanding", "past due"]) {
      expect(html).not.toContain(banned);
    }
  });
});

describe("SET-06D · the Audit tab is INLINE, never a jump to the global log", () => {
  it("renders the route's own change rows on the tab (BR-AUD-010's first half)", () => {
    const html = renderRoute("audit");
    // The empty state of the entity's OWN log — not a link standing in for it.
    expect(html).toContain(t("metering.audit.empty"));
    expect(html).toContain(t("metering.audit.openViewer"));
  });

});

// ═══════════════════════════════════════════════════════════════════════════
// SET-07D · the cycle detail
// ═══════════════════════════════════════════════════════════════════════════

describe("SET-07D — the cycle detail, five tabs and a Facts rail", () => {
  it("draws all five ruled tabs", () => {
    const html = renderCycle();
    for (const key of ["schedule", "routes", "coverage", "runs", "audit"]) {
      expect(html).toContain(t(`settings.cycles.detail.tab.${key}`));
    }
  });

  it("D9 — the rail says the bill and due days are CYCLE DEFAULTS a run may override", () => {
    const html = renderCycle();
    // ⚠ AN APOSTROPHE-FREE SPAN, DELIBERATELY: `renderToStaticMarkup` escapes
    // `'` to `&#x27;`, so asserting the whole sentence would fail on the
    // ENCODING rather than on the copy — a check that cannot distinguish pass
    // from fail is worse than none (DEF-182).
    expect(html).toContain("Charges and taxes live on the plan, never here.");
    expect(html).toContain("a run starts from them and can change them for that");
    // ⚠ THE SCREENSHOT'S OWN SENTENCE IS NOW WRONG AND MUST NOT SURVIVE.
    expect(html).not.toContain("belong to the run, not the cycle");
  });

  it("the schedule card states the window is DERIVED, not stored", () => {
    const html = renderCycle("schedule");
    expect(html).toContain(t("settings.cycles.window.derived"));
    expect(html).toContain(t("settings.cycles.detail.starts"));
    expect(html).toContain(t("settings.cycles.detail.daysToComplete"));
    expect(html).toContain(t("settings.cycles.detail.firstRun"));
  });

  it("the FROM-NEXT callout is on the schedule tab, verbatim", () => {
    expect(renderCycle("schedule")).toContain(
      "Changing the schedule applies from the next window — nothing already issued changes",
    );
  });

  it("the Routes tab carries the move footnote, verbatim", () => {
    expect(renderCycle("routes")).toContain(
      "Moving one here removes it from its old cycle at the next window",
    );
  });
});

describe("SET-07D · D13 — a cycle is DERIVED at bill-run time", () => {
  it("the Coverage tab has the KPI trio and the uncovered accounts' real lack", () => {
    const html = renderCycle("coverage");
    expect(html).toContain(t("settings.cycles.detail.kpi.accounts"));
    expect(html).toContain(t("settings.cycles.detail.kpi.uncovered"));
    expect(html).toContain(t("settings.cycles.detail.kpi.routes"));
    // ⚠ **AMENDED 2026-09-19 (`DEF-MET-5854`).** This asserted the opening of a
    // 37-word paragraph explaining the derivation MECHANISM — rationale, which
    // B14 rule 33 puts at zero words on screen — and that paragraph never said
    // the thing a reader actually needed: the list is the whole utility's.
    expect(html).toContain(t("settings.cycles.detail.uncoveredTitle"));
    expect(html).toContain(t("settings.cycles.detail.uncoveredScope"));
  });

  // ── `DEF-MET-5854` · THE CASE THAT WOULD HAVE CAUGHT IT ──────────────────
  // The human QA team reported *"accounts that were not selected still appear"*
  // on this tab. They were right about what they saw and the data was right
  // too: `derivation.covered_unit_ids` walks EVERY active route on EVERY
  // non-draft cycle, so two different cycles draw the identical list. Measured
  // on the demo utility 2026-09-19 — `CY-007` (5 routes, 28 accounts) and
  // `CY-001` (0 routes, 0 accounts) both drew the SAME 26 rows. What was
  // missing was a sentence saying so, and no check in this repo can see a
  // MISSING sentence, which is why this one names it.
  it("DEF-MET-5854: the uncovered list states that it is the WHOLE utility, not this cycle", () => {
    const html = renderCycle("coverage");
    expect(html).toContain(t("settings.cycles.detail.uncoveredTitle"));
    expect(html).toContain(t("settings.cycles.detail.uncoveredScope"));
    // The heading sits ABOVE the table it describes, never under it.
    expect(html.indexOf(t("settings.cycles.detail.uncoveredTitle"))).toBeLessThan(
      html.indexOf('data-rc="uncovered"'),
    );
    // …and the rationale paragraph is GONE rather than shortened (rule 33).
    expect(html).not.toContain("The accounts counted here are on no route");
    expect(html).not.toContain("worked out when the bill run happens");
  });

  it("there is NO 'Assign a cycle →' row action, and no account-level assignment at all", () => {
    const html = renderCycle("coverage").toLowerCase();
    expect(html).not.toContain("assign a cycle");
    expect(html).not.toContain("assign cycle");
  });

  it("BR-MET-078 — no money reaches the cycle detail either", () => {
    const html = renderCycle("coverage").toLowerCase();
    for (const banned of ["late fee", "penalty", "grace", "$", "balance"]) {
      expect(html).not.toContain(banned);
    }
  });
});

describe("SET-07D · the Runs tab lists real runs (GET /billing/runs, RC-W4b)", () => {
  it("draws the run's period, when it went out and what it produced", () => {
    const html = renderCycle("runs");
    expect(html).toContain(t("settings.cycles.detail.openInBilling"));
    expect(html).toContain('data-rc="run"');
    // ⚠ THE STATUS IS COMPOSED, not the stored column (DEF-602). The PO's
    // screenshot's own wording: "Issued", "Issued · 5 held".
    expect(html).toContain(t("settings.cycles.detail.runStatus.issuedHeld", { held: 6 }));
    expect(html).toContain(t("settings.cycles.detail.runBills", { issued: 1118, accounts: 1124 }));
    // The stated absence it replaces is gone.
    expect(html).not.toContain("Past runs are not listed yet");
  });

  it("neither of the two fields the server cannot honestly produce is rendered", () => {
    const html = renderCycle("runs");
    // `run_no` is always null — no number column, no series, D5 never ruled a
    // grammar for runs. The row is identified by its PERIOD instead.
    expect(html).not.toContain("RUN-");
    // `status` is a stored column nothing ever advances: every historical run
    // reads "draft", so a Status column would title finished work Draft.
    expect(html.toLowerCase()).not.toContain(">draft<");
  });

  it("BR-MET-078 — a run history on this surface carries no money", () => {
    const html = renderCycle("runs").toLowerCase();
    for (const banned of ["$", "amount", "total", "balance"]) {
      expect(html).not.toContain(banned);
    }
  });

  it("a run that has issued nothing says so — it is a state, not a blank", () => {
    const html = renderCycle("runs");
    expect(html).toContain(t("settings.cycles.detail.notIssued"));
    expect(html).toContain(t("settings.cycles.detail.runStatus.notIssued"));
  });

  it("OQ-342 — the run is named by its PERIOD, because `run_no` has no source", () => {
    const html = renderCycle("runs");
    // "Jul 2026" — a real fact about the run. Never a minted RUN-#### label.
    expect(html).toContain("Jul 2026");
  });

  it("the composed status is a pure function of the two fields with evidence", () => {
    const base = RUNS[0];
    expect(runStatusLabel({ ...base, issued_at: null }, t)).toBe("Not issued yet");
    expect(runStatusLabel({ ...base, held: 0 }, t)).toBe("Issued");
    expect(runStatusLabel({ ...base, held: 5 }, t)).toBe("Issued · 5 held");
    // …and the stored column never reaches it: a "draft" run whose bills went
    // out reads Issued, which is the whole point of DEF-602's workaround.
    expect(base.status).toBe("draft");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// RC-W3c · the next-windows card is REAL (the engine landed, the route serves)
// ═══════════════════════════════════════════════════════════════════════════

describe("SET-07D · the NEXT THREE WINDOWS card", () => {
  it("draws the served occurrences with their Next/Scheduled statuses", () => {
    const html = renderCycle("schedule");
    expect(html).toContain(t("settings.cycles.detail.nextWindows"));
    expect(html).toContain(t("settings.cycles.window.status.next"));
    expect(html).toContain(t("settings.cycles.window.status.scheduled"));
    // Three rows, one per served occurrence. Never a fourth invented one.
    expect(html.match(/data-rc="window"/g)).toHaveLength(3);
    // The engine's own worked figure, rendered through the tenant's format.
    expect(html).toContain("09/01/2026");
    expect(html).toContain("11/03/2026");
  });

  it("the countdown target is the SERVED next cycle date, never derived here", () => {
    expect(renderCycle("schedule")).toContain(t("settings.cycles.detail.nextCycleDate"));
  });

  it("the placeholder that said nothing sent the windows is GONE", () => {
    const html = renderCycle("schedule");
    expect(html).not.toContain("not shown yet");
    // ⚠ hard-won law 1 in reverse: a sentence claiming a gap that has closed.
    expect(html).not.toContain("nothing sends them to this screen");
  });

  it("a cycle with neither a proposal nor a gap says so, and still renders", () => {
    const html = renderCycle("schedule", {
      ...CYCLE,
      proposed_windows: [],
      next_period: null,
      next_cycle_date: null,
      effective_start_day: 1,
      start_day_differs: false,
      schedule_warning: null,
      schedule_gap: null,
    });
    expect(html).toContain(t("settings.cycles.detail.noWindowsTitle"));
    // The rest of the cycle is untouched by the absence.
    expect(html).toContain(t("settings.cycles.detail.starts"));
  });

  it("the statuses are the server's two words and nothing else", () => {
    expect(windowStatusKey("Next")).toBe("settings.cycles.window.status.next");
    expect(windowStatusKey("Scheduled")).toBe("settings.cycles.window.status.scheduled");
    // A ninth status is a fact about the data, never a fallback key.
    expect(windowStatusKey("Closed")).toBeNull();
  });
});

describe("SET-07D · `schedule_gap` — three OPEN questions, rendered as sentences", () => {
  const CODES = [
    "cycle_month_end_anchor_unruled",
    "cycle_first_run_disagrees_with_start_day",
    "cycle_windows_would_overlap",
  ] as const;

  it("every gap code has its own catalogue sentence", () => {
    for (const code of CODES) {
      expect(scheduleGapKey(code)).toBe(`settings.cycles.gap.${code}`);
      expect(t(`settings.cycles.gap.${code}`)).not.toBe(`settings.cycles.gap.${code}`);
    }
    // An unrecognised code falls back to a sentence, never to the raw code.
    expect(scheduleGapKey("something_new")).toBe("settings.cycles.gap.unknown");
  });

  it("renders the sentence, keeps the cycle on screen, and proposes NO window", () => {
    for (const code of CODES) {
      const html = renderCycle("schedule", withGap(code, "backend prose nobody translated"));
      // ⚠ AN APOSTROPHE-FREE SPAN, DELIBERATELY (DEF-182's lesson, and this
      // file already states it once): `renderToStaticMarkup` escapes `'` to
      // `&#x27;`, so asserting the whole sentence would fail on the ENCODING
      // rather than on the copy.
      expect(html).toContain(t(`settings.cycles.gap.${code}`).split("'")[0]);
      expect(html).toContain(t("settings.cycles.gap.title"));
      // The rest of the cycle still renders — a silence is not a failure.
      expect(html).toContain(t("settings.cycles.detail.starts"));
      expect(html).toContain("CY-001");
      // …and no window row is drawn beside the silence.
      expect(html).not.toContain('data-rc="window"');
    }
  });

  it("G28 — no OQ id, no rule id, no module path, and no raw code reaches the screen", () => {
    for (const code of CODES) {
      const html = renderCycle("schedule", withGap(code, "backend prose nobody translated"));
      expect(html).not.toContain("OQ-");
      expect(html).not.toContain("BR-MET");
      expect(html).not.toContain("period_engine");
      expect(html).not.toContain(code);
      // The server's own English `detail` is NOT rendered — it is untranslated.
      expect(html).not.toContain("backend prose nobody translated");
    }
  });

  it("never a date and never a guess: the silence itself prints no calendar date", () => {
    const html = renderCycle("schedule", withGap(CODES[0], ""));
    // ⚠ SCOPED TO THE SILENCE, not to the page. The cycle's FIRST RUN is a
    // stored fact and still renders beside it — what must never appear is a
    // date the screen worked out for a window the engine declined to propose.
    const block = /data-rc="stated-absence"[\s\S]*?<\/section>/.exec(html)?.[0] ?? "";
    expect(block).toContain(t("settings.cycles.gap.title"));
    expect(block).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(block).not.toMatch(/\d{2}\/\d{2}\/\d{4}/);
    // …and not a bare day-of-month standing in for one either.
    expect(block).not.toMatch(/\b(29|30|31)\b/);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// RC-W3c · the four RC-W3b doors, wired
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════
// OQ-340 — THE FIRST RUN WINS, SO THE STORED START DAY CAN DESCRIBE NOTHING
//
// PO, verbatim, 2026-08-23: *"A: first window 15–17 Sep (start day becomes
// decorative)"* — and the PO quoted the consequence back in their own ruling.
// The engine follows the first run and does NOT rewrite the column, so a
// screen that printed `start_day` would print a number the product ignores.
// A field that lies to the operator is the defect this repo files most often.
// ═══════════════════════════════════════════════════════════════════════════

/** The PO's own figure: Monthly · start day **1** · 3 days · first run
 *  **15 Sep 2026** → windows on the **15th**. `start_day` stays 1 in the
 *  database and `effective_start_day` is 15. */
const DECORATIVE_START: CycleRow = {
  ...CYCLE,
  start_day: 1,
  first_run_date: "2026-09-15",
  effective_start_day: 15,
  start_day_differs: true,
  proposed_windows: [
    { period_start: "2026-09-15", period_end: "2026-09-17", status: "Next", occurrence: 1 },
    { period_start: "2026-10-15", period_end: "2026-10-17", status: "Scheduled", occurrence: 2 },
    { period_start: "2026-11-15", period_end: "2026-11-17", status: "Scheduled", occurrence: 3 },
  ],
};

describe("SET-07D · the Schedule tab shows what the cycle DOES (OQ-340)", () => {
  it("STARTS reads the effective day, not the stored one", () => {
    const html = renderCycle("schedule", DECORATIVE_START);
    const starts = html.slice(html.indexOf(t("settings.cycles.detail.starts")));
    expect(starts.slice(0, 400)).toContain("15");
  });

  it("and it SAYS the saved day is not used, naming both numbers", () => {
    const html = renderCycle("schedule", DECORATIVE_START);
    expect(html).toContain(t("settings.cycles.startDay.decorative", { effective: 15, stored: 1 }));
  });

  it("the Facts rail agrees with the Schedule tab", () => {
    const html = renderCycle("schedule", DECORATIVE_START);
    const rail = html.slice(html.indexOf('data-rc="facts-rail"'));
    expect(rail).toContain("15");
  });

  it("a cycle whose two dates AGREE says nothing extra", () => {
    const html = renderCycle("schedule", CYCLE);
    expect(html).not.toContain(t("settings.cycles.startDay.decorative", { effective: 1, stored: 1 }));
    expect(html).not.toContain(t("settings.cycles.startDay.saved", { stored: 1 }));
  });
});

describe("SET-07D · OQ-341's overlap WARNING reaches the operator", () => {
  const overlapping: CycleRow = {
    ...CYCLE,
    frequency: "Daily",
    days_to_complete: 3,
    schedule_warning: {
      code: "cycle_windows_overlap",
      frequency: "Daily",
      days_to_complete: 3,
      max_days_to_complete: 1,
      detail: "This cycle takes longer to complete than the gap between its readings…",
    },
  };

  it("renders a TRANSLATED sentence, never the server's English `detail`", () => {
    const html = renderCycle("schedule", overlapping);
    expect(html).toContain(
      t("settings.cycles.schedule.warning.cycle_windows_overlap", {
        // The frequency reaches the sentence as a TRANSLATED business word,
        // through the one resolver — not as the server's raw `Daily`.
        frequency: frequencyLabel("Daily", t, "—"),
        days: 3,
      }),
    );
    expect(html).not.toContain("the gap between its readings");
  });

  it("⚠ IT IS A WARNING BESIDE REAL WINDOWS, NEVER INSTEAD OF THEM (the PO amended their own option B)", () => {
    const html = renderCycle("schedule", overlapping);
    expect(html).toContain(t("settings.cycles.detail.nextWindows"));
  });

  it("a cycle that fits shows no warning", () => {
    expect(renderCycle("schedule", CYCLE)).not.toContain(
      t("settings.cycles.schedule.warning.cycle_windows_overlap", { frequency: "Daily", days: 3 }),
    );
  });
});

describe("SET-06D · Read history is SERVED now (GET /routes/{id}/read-windows)", () => {
  it("renders the closed window's own figures — 196 · 196 · Complete", () => {
    const html = renderRoute("audit");
    expect(html).toContain(t("settings.routes.detail.readHistory"));
    expect(html).toContain("196");
    expect(html).toContain(t("settings.routes.detail.readResult.complete"));
    expect(html).toContain('data-rc="read-window"');
  });

  it("OQ-343 — the Read history is FIVE columns, and the PO's screenshot is corrected", () => {
    const html = renderRoute("audit");
    // The ruled set, positively — an absence assertion alone would pass over a
    // table that had quietly lost `Collected` too.
    for (const key of [
      "settings.routes.detail.col.readWindow",
      "settings.routes.detail.col.readOn",
      "settings.routes.detail.col.collected",
      "settings.routes.detail.col.expected",
      "settings.routes.detail.col.result",
    ]) {
      expect(html).toContain(t(key));
    }
  });

  it("OQ-343 — no reader column, no reader name, no *\"Reader changed\"* row", () => {
    const html = renderRoute("audit");
    expect(html).not.toContain("M. Chen");
    expect(html).not.toContain("D. Ortiz");
    expect(html.toLowerCase()).not.toContain("reader");
  });

  it("the stated absence it replaces is gone", () => {
    expect(renderRoute("audit")).not.toContain("Read history is not available yet");
  });
});

describe("SET-06D · the Accounts tab is SERVED (GET /routes/{id}/accounts)", () => {
  it("lists the accounts a missed read affects, status only", () => {
    const html = renderRoute("accounts");
    expect(html).toContain("ACC-1042");
    expect(html).toContain("R. Okafor");
    expect(html).toContain('data-rc="route-account"');
  });

  it("D12 — still no Balance column and no money word", () => {
    const html = renderRoute("accounts").toLowerCase();
    for (const banned of ["balance", "$", "amount", "outstanding", "past due"]) {
      expect(html).not.toContain(banned);
    }
  });

  it("units with no account are REPORTED, not dropped", () => {
    expect(renderRoute("accounts")).toContain(
      t("settings.routes.detail.accountsSummary", { accounts: 1, units: 5, without: 4 }),
    );
  });
});

describe("SET-06D · an exclusion explains itself IN PLACE (B17 §6)", () => {
  it("the two-word reason renders on the excluded row", () => {
    const html = renderRoute("assets");
    expect(html).toContain("premise demolished");
    expect(html).toContain(t("settings.routes.detail.col.why"));
  });

  it("the stated absence it replaces is gone", () => {
    expect(renderRoute("assets")).not.toContain("Why a meter was left off is not shown yet");
  });
});

describe("SET-07D · the uncovered ACCOUNTS are listed (D13 — and still no assignment)", () => {
  it("names each uncovered account and the thing it actually lacks", () => {
    const html = renderCycle("coverage");
    expect(html).toContain("ACC-3020");
    expect(html).toContain(t("settings.cycles.detail.lacks.route"));
    expect(html).toContain('data-rc="uncovered"');
  });

  it("no row offers an assignment of any kind", () => {
    const html = renderCycle("coverage").toLowerCase();
    expect(html).not.toContain("assign a cycle");
    expect(html).not.toContain("assign cycle");
    expect(html).not.toContain("→</a>");
  });
});

describe("record links (PO 2026-10-19) — routes and cycles", () => {
  it("the route's Units tab opens each premises and unit", () => {
    const html = renderRoute("units");
    expect(html).toContain('href="/acme/premises/p1"');
    expect(html).toContain('href="/acme/premises/units/u4"');
  });

  it("the route's Assets tab opens the meter, its premises and its unit", () => {
    const html = renderRoute("assets");
    expect(html).toContain('href="/acme/assets/m1"');
    expect(html).toContain('href="/acme/premises/p1"');
    expect(html).toContain('href="/acme/premises/units/u1"');
  });

  it("the route's Accounts tab opens the account, premises and unit", () => {
    const html = renderRoute("accounts");
    expect(html).toContain('href="/acme/accounts/a1"');
    expect(html).toContain('href="/acme/premises/units/u1"');
  });

  it("the cycle's uncovered accounts open the account, premises and unit", () => {
    const html = renderCycle("coverage");
    expect(html).toContain('href="/acme/accounts/a9"');
    expect(html).toContain('href="/acme/premises/p9"');
    expect(html).toContain('href="/acme/premises/units/u9"');
  });
});
