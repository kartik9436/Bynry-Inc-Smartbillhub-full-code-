// ── Trace ──────────────────────────────────────────────
// Screen:  Meter Reads blueprint entry 21 — A ROUTE, THE DETAIL (pages 49–53).
// Rules:   BR-MET-010 · BR-MET-011 (narrowed 2026-09-14 — route configuration is
//          Settings' and this screen does not write it) · BR-MET-075 (an
//          excluded meter keeps its premises on the walk) · CR-029 D6 + OQ-343
//          (**no reader anywhere**) · D11 (the walk is numbered per PREMISES) ·
//          B14 rule 16 (a pagination footer on every list table) · 31 (no
//          database id on screen) · 40 (the page title is 32px).
// ───────────────────────────────────────────────────────
// THE LOAD-BEARING CASES, and each was proved RED before it was trusted green:
//
//   1. **The walk is READ-ONLY here.** A DOM scan for any control that could
//      reorder or save — the shape `RoutesCyclesPage.test.tsx` already uses for
//      BR-MET-011, because "no write control" has to be checked as an ABSENCE
//      over the rendered screen rather than as a missing import.
//   2. **No reader is rendered**, against the drawing and per two PO rulings.
//      The fixture carries a reader NAME precisely so that "the name is absent"
//      cannot be mistaken for "the fixture had none" — the same device
//      `RoutesCyclesDetail.test.tsx` uses for D6.
//   3. **No uuid reaches the screen** (B14 rule 31): the assertion reads the
//      rendered text and refuses anything uuid-shaped, so a cell that starts
//      printing an id fails here rather than in front of a utility.
//   4. **The door opens** — S26's route link lands on THIS address, asserted by
//      ADDRESS, because a test that only mounts the page cannot tell whether
//      anybody can reach it (hard-won law 2).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  CycleRow,
  ReadChaseList,
  ReadChaseRow,
  RouteDetail,
  RouteMeterPicker,
  RouteReadWindowRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";
import { ToastProvider } from "@/components/Toast";

import {
  RouteReadsPage,
  historyStatus,
  monthOf,
  routeReadsChaseKey,
  routeReadsCyclesKey,
  routeReadsDetailKey,
  routeReadsMetersKey,
  routeReadsPath,
  routeReadsTabFrom,
  routeReadsWindowsKey,
  stopRows,
  stopState,
  windowOptions,
  windowStateKey,
} from "./RouteReadsPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ⚠ **REAL UUIDS IN THE FIXTURE, ON PURPOSE.** B14 rule 31's check below refuses
// a uuid-shaped string in the rendered text; a fixture using `"r1"` would make
// that assertion pass over a screen printing every id it holds.
const ROUTE_ID = "6f1b1f7a-2f3b-4f6c-9a2a-1f0f2a3b4c5d";
const PREMISES_A = "11111111-2222-3333-4444-555555555555";
const PREMISES_B = "66666666-7777-8888-9999-000000000000";
const UNIT_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const UNIT_B = "abababab-cdcd-efef-0101-232323232323";
const METER_A = "12121212-3434-5656-7878-909090909090";
const METER_B = "98989898-7676-5454-3232-101010101010";
const CYCLE_ID = "c1c1c1c1-c2c2-c3c3-c4c4-c5c5c5c5c5c5";

const DETAIL: RouteDetail = {
  id: ROUTE_ID,
  code: "RT-005",
  name: "North Elm",
  route_type: "walk",
  feeder_ref: null,
  // ⚠ A READER IS ON THE ROW AND MUST NOT REACH THE SCREEN — CR-029 D6, OQ-343.
  assigned_to: "J. Alvarez",
  cycle_id: CYCLE_ID,
  cycle_code: "CY-001",
  status: "active",
  members: 2,
  meters: 2,
  collected: null,
  last_completion: "2026-08-01T06:00:00Z",
  progress: null,
  service_id: null,
  service_code: null,
  services: ["E"],
  service_ids: [],
  area_id: null,
  area_code: null,
  area_name: null,
  notes: null,
  premises: 2,
  units: 2,
  meters_available: 2,
  meters_excluded: 1,
  excluded_asset_ids: [METER_B],
  exclusions: [],
  membership: [
    {
      unit_id: UNIT_A,
      unit_label: "2C",
      premises_id: PREMISES_A,
      premise_no: "PR-1",
      walk_order: 1,
    },
    {
      unit_id: UNIT_B,
      unit_label: "—",
      premises_id: PREMISES_B,
      premise_no: "PR-2",
      walk_order: 2,
    },
  ],
  premises_order: [
    { premises_id: PREMISES_A, premise_no: "PR-1", walk_order: 1, units: 1 },
    { premises_id: PREMISES_B, premise_no: "PR-2", walk_order: 2, units: 1 },
  ],
};

const METERS: RouteMeterPicker = {
  meters: [
    {
      id: METER_A,
      asset_no: "MTR-0471",
      unit_id: UNIT_A,
      unit_label: "2C",
      premises_id: PREMISES_A,
      address_line: "1408 Elm",
      service_code: "E",
      size_class: null,
      read_method: null,
      excluded: false,
      exclusion_reason: null,
    },
    {
      id: METER_B,
      asset_no: "MTR-0488",
      unit_id: UNIT_B,
      unit_label: "—",
      premises_id: PREMISES_B,
      address_line: "17 Pecan Way",
      service_code: "E",
      size_class: null,
      read_method: null,
      // BR-MET-075 — excluded, and the premises KEEPS its row.
      excluded: true,
      exclusion_reason: "vacant since 06/2026",
    },
  ],
  total: 2,
  included: 1,
  premises_without_meter: 0,
  // `CR-131-BRC07` — the picker answers by PREMISES and pages
  // server-side, so a fixture that omits these is not the payload.
  premises: 2,
  page: 1,
  per: null,
};

const CHASE_ROW: ReadChaseRow = {
  unit_id: UNIT_A,
  unit: "2C",
  premises: "1408 Elm",
  meter: "MTR-0471",
  asset_id: METER_A,
  route: "RT-005",
  service: "E",
  missing_channels: ["tou_mid", "demand"],
  days_left: 0,
};

const CHASE: ReadChaseList = {
  cycle_id: CYCLE_ID,
  cycle_code: "CY-001",
  window: { period_start: "2026-09-01", period_end: "2026-09-03", state: "closed" },
  expected_records: 11,
  collected_records: 0,
  missing_records: 11,
  completeness_pct: "0.0",
  expected_meters: 2,
  pending_meters: 1,
  days_left: 0,
  rows: [
    CHASE_ROW,
    // A row on ANOTHER route: the narrowing must drop it.
    { ...CHASE_ROW, route: "RT-009", meter: "MTR-9999", asset_id: null, unit_id: "zz" },
  ],
  count: 2,
};

const WINDOWS: RouteReadWindowRow[] = [
  {
    id: "w1",
    route_id: ROUTE_ID,
    cycle_id: CYCLE_ID,
    period_start: "2026-08-01",
    period_end: "2026-08-03",
    read_on: "2026-08-03",
    collected: 11,
    expected: 11,
    skips: 0,
    result: "Complete",
    closed_at: "2026-08-03T12:00:00Z",
  },
];

const CYCLES: CycleRow[] = [
  {
    id: CYCLE_ID,
    code: "CY-001",
    routes: ["RT-005"],
    window_start: "2026-09-01",
    window_end: "2026-09-03",
    bill_date: null,
    due_days: null,
    due_date: null,
    expected: 11,
    collected: 0,
    progress: 0,
    status: "in_progress",
    lifecycle_status: "active",
    name: null,
    frequency: "monthly",
    start_day: null,
    days_to_complete: null,
    read_window_source: "stored",
    first_run_date: null,
    bill_day: null,
    accounts: 0,
    route_ids: [],
    proposed_windows: [],
    next_period: null,
    next_cycle_date: null,
    effective_start_day: 1,
    start_day_differs: false,
    schedule_warning: null,
    schedule_gap: null,
  },
];

function mount(tab?: string, window?: string): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  queryClient.setQueryData(routeReadsDetailKey(ROUTE_ID), DETAIL);
  queryClient.setQueryData(routeReadsWindowsKey(ROUTE_ID), WINDOWS);
  queryClient.setQueryData(routeReadsCyclesKey, CYCLES);
  queryClient.setQueryData(routeReadsChaseKey(CYCLE_ID, window ?? ""), CHASE);
  // `CR-131-BRC07` — the meter list is asked for by ROUTE now, so the key
  // no longer carries a unit list. A test still seeding the old key would
  // mount a permanent loading skeleton and assert against it.
  queryClient.setQueryData(routeReadsMetersKey(ROUTE_ID), METERS);
  const search = [
    tab === undefined ? null : `tab=${tab}`,
    window === undefined ? null : `window=${window}`,
  ]
    .filter((part): part is string => part !== null)
    .join("&");
  // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
  // `/:tenant/reads/routes/:routeId` route leaves `useParams()` empty, so the
  // screen fetches nothing and every `toContain` reads a blank page as a pass
  // (hard-won law 2's fixture clause).
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[
            `/${TEST_TENANT}/reads/routes/${ROUTE_ID}${search === "" ? "" : `?${search}`}`,
          ]}
        >
          <Routes>
            <Route
              path="/:tenant/reads/routes/:routeId"
              element={<RouteReadsPage timeZone="America/Chicago" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ── The pure half, provable without a browser ──────────────────────────────

describe("entry 21 — the pieces", () => {
  it("a window param is a MONTH, because that is what the chase list takes", () => {
    expect(monthOf("2026-09-01")).toBe("2026-09");
    expect(monthOf(null)).toBeNull();
  });

  it("an unknown tab falls back to Overview rather than rendering nothing", () => {
    expect(routeReadsTabFrom("stops")).toBe("stops");
    expect(routeReadsTabFrom("nonsense")).toBe("overview");
    expect(routeReadsTabFrom(null)).toBe("overview");
  });

  it("the address carries the window, so a ticket can link straight at one", () => {
    expect(routeReadsPath(ROUTE_ID, "2026-09")).toBe(
      `/reads/routes/${ROUTE_ID}?window=2026-09`,
    );
    expect(routeReadsPath(ROUTE_ID)).toBe(`/reads/routes/${ROUTE_ID}`);
  });

  it("the OPEN window heads the selector and a month is never offered twice", () => {
    const options = windowOptions(
      { month: "2026-09", cycleId: CYCLE_ID, periodStart: "2026-09-01", periodEnd: "2026-09-03" },
      [...WINDOWS, { ...WINDOWS[0], id: "w2", period_start: "2026-09-01" }],
    );
    expect(options.map((option) => option.month)).toEqual(["2026-09", "2026-08"]);
  });

  it("CR-029 D11: one row per PREMISES, and an all-excluded stop KEEPS its row", () => {
    const rows = stopRows(DETAIL, METERS.meters, [CHASE_ROW]);
    expect(rows).toHaveLength(2);
    expect(rows[0].stopNo).toBe(1);
    expect(rows[0].address).toBe("1408 Elm");
    expect(rows[0].shortChannels).toEqual(["tou_mid", "demand"]);
    expect(stopState(rows[0])).toBe("short");
    // BR-MET-075 — the excluded meter's premises is still a row, and it is not
    // counted short: nobody is walking to it.
    expect(rows[1].address).toBe("17 Pecan Way");
    expect(stopState(rows[1])).toBe("excluded");
    expect(rows[1].shortChannels).toEqual([]);
  });

  it("a window's verdict is STATED, never inferred from the counts", () => {
    expect(historyStatus(WINDOWS[0])).toEqual({ key: "complete", tone: "success" });
    expect(historyStatus({ ...WINDOWS[0], closed_at: null, result: null }).key).toBe("in_progress");
    expect(historyStatus({ ...WINDOWS[0], result: "Incomplete" }).key).toBe("incomplete");
    // A closed window the closer never gave a verdict is CLOSED, not Complete.
    expect(historyStatus({ ...WINDOWS[0], result: null }).key).toBe("closed");
  });

  it("an unrecognised window state answers `unknown`, never the first option", () => {
    expect(windowStateKey("open")).toBe("open");
    expect(windowStateKey(null)).toBe("unknown");
    expect(windowStateKey("whatever")).toBe("unknown");
  });
});

// ── The screen ─────────────────────────────────────────────────────────────

describe("entry 21 — the route detail", () => {
  it("the header names the route by its CODE and the window it is measured against", () => {
    const html = mount();
    expect(html).toContain("RT-005");
    expect(html).toContain("North Elm");
    expect(html).toContain(t("metering.routeReads.measuredAgainst"));
    // B14 rule 1 — the ← names where it EXITS to: the cycle, not the last tab.
    expect(html).toContain("CY-001");
  });

  it("B14 rule 40: the page title carries the 32px class on the element", () => {
    // The component emits it; `cr093-page-title-size.mjs` is what proves it
    // RENDERS, because a utility in an unlisted file is in the DOM and styles
    // nothing. This asserts the half a source test can honestly reach.
    expect(mount()).toContain("text-h2");
  });

  it("B14 rule 31: no uuid-shaped value reaches the rendered text", () => {
    const html = mount("stops");
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    // …and the meter is on screen by its issued number, so the check above is
    // not passing over an empty page.
    expect(text).toContain("MTR-0471");
  });

  it("CR-029 D6 + OQ-343: the reader is NOWHERE, though the fixture carries one", () => {
    // *"B: no reader anywhere, correct the screenshot and drop the stored
    // name"* — PO 2026-08-23. The blueprint draws a reader chip, a Reader fact
    // and a Reader column; none of the three is built.
    for (const tab of [undefined, "stops", "short", "reads", "history"]) {
      expect(mount(tab)).not.toContain("J. Alvarez");
    }
  });

  it("BR-MET-011 as narrowed: this screen writes NOTHING about the walk", () => {
    const html = mount("stops");
    // The whole rule as an absence over the RENDERED screen: nothing in a stop
    // row can be pressed or typed into, so no control here can move the walk.
    //
    // ⚠ **THIS ASSERTION WAS WRONG THE FIRST TIME AND THE WRONGNESS IS WORTH
    // RECORDING.** It read `not.toMatch(/aria-label="[^"]*(Move|Reorder)/i)`
    // and went red on the correct screen, because the kit's own column chooser
    // labels its buttons *"Move Stop up"* — that moves a COLUMN, which is not
    // what BR-MET-011 is about. A check that cannot tell the walk order from
    // the column order is a check that would send the next lane to delete the
    // column chooser. The row body is the subject, so the row body is what is
    // read.
    const body = /<tbody>([\s\S]*?)<\/tbody>/.exec(html)?.[1] ?? "";
    expect(body).toContain("1408 Elm");
    expect(body).not.toContain("<button");
    expect(body).not.toContain("<input");
    expect(html).not.toContain("<form");
    // …and the pointer to the one screen that DOES set it is present.
    expect(mount()).toContain(t("metering.routeReads.manageInSettings"));
  });

  it("the shortfall is narrowed to THIS route, and the register names travel", () => {
    const html = mount("short");
    expect(html).toContain("MTR-0471");
    // The chase list's second row is on RT-009 and must not appear here.
    expect(html).not.toContain("MTR-9999");
    // Hard rule 3's spirit — the registers by NAME, never a bare count.
    expect(html).toContain(t("metering.reads.channel.tou_mid"));
    expect(html).toContain(t("metering.reads.channel.demand"));
    // BR-MET-026/062, stated where a clerk acts on it.
    expect(html).toContain(t("metering.routeReads.demandNote"));
  });

  it("B14 rule 16: every list tab draws a pagination footer", () => {
    for (const tab of ["stops", "short", "history"]) {
      expect(mount(tab)).toContain(t("table.pager.pageSize"));
    }
  });

  it("the History tab lists the route's closed windows by their cycle CODE", () => {
    const html = mount("history");
    expect(html).toContain("CY-001");
    expect(html).toContain(t("metering.routeReads.result.complete"));
    // The reader column the drawing carries is not among the headers.
    expect(html).not.toContain("J. Alvarez");
  });

  it("Overview states the shortfall and the cycles this route is walked on", () => {
    const html = mount();
    expect(html).toContain(t("metering.routeReads.kpi.shortRegisters"));
    expect(html).toContain(t("metering.routeReads.theWalk"));
    expect(html).toContain(t("metering.routeReads.cycles"));
    expect(html).toContain(t("metering.routeReads.cyclesNote"));
  });
});

// ── The door (hard-won law 2) ──────────────────────────────────────────────
// `DEF-GOV-10106` — S26's route link was this page's door and was asserted
// here; S26 (`RoutesOpsPage`) is deleted. The live door is the read cycle
// detail's Routes table, whose code cell links `routeReadsPath(row.id, …)`
// (`ReadCycleDetailPage.tsx`). ⚠ No test asserts that link by address yet —
// it was unasserted before this deletion too; reported, not hidden.
