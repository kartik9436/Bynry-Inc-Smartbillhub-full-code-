// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · **P2.24** — *"Drill down in place. A group
//          row expands to the next level **without leaving the report** — Area
//          opens its routes, a route its premises. Collapse restores it."*
//          Outcome, verbatim: *"Three levels open and close without a page
//          load."* Read from `05-prototype/09 Reports Build Brief.pdf` **p013**
//          (the task row) and **p028** (2·1E, note ②: *"A group row · ▾ open ·
//          ▸ closed, expands in place, no page load"*), both opened as
//          RENDERED IMAGES per B14 rule 42.
// Rules:   CLAUDE.md hard-won law 2 and its MIRROR (never a control the query
//          cannot honour) · law 7 clause 2 (what would make this pass
//          WRONGLY) · B14 rule 33 (a LABEL ≤ 3 words; RATIONALE is zero words
//          on screen) · rule 43 (built as a component) · NFR-3.
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE OUTCOME IS A NUMBER, AND THE NUMBER IS ZERO REQUESTS                ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// *"without leaving the report"* and *"no page load"* are the whole task. A
// disclosure that refetches is not this feature — it is the drill-THROUGH
// (`P2.18`) wearing a triangle. So the spy counts requests across an open and a
// close, and the count is asserted at zero ABOVE the count for the first paint,
// which is asserted non-zero so that a screen which never loaded cannot pass.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  AND A GROUP WITH NO CHILDREN GETS NO CONTROL AT ALL                     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ⚠ **MEASURED BEFORE A LINE WAS WRITTEN, ON REAL POSTGRESQL 16 AGAINST THE
// SEEDED `brazosbend` TENANT, 2026-09-27** (`10-scripts/rep_p2_24_grouping_depth.py`):
// of the **46** live report definitions, **1** can group to three levels
// (`trend_pack`), **2** to exactly one (`ar_aging` by consumer class,
// `journal_export` by service) and **43** cannot group at all.
//
// So the DEEPEST group row on 45 of the 46 has nothing beneath it, and a
// disclosure drawn on it would be hard-won law 2's mirror exactly — a control
// that runs, changes nothing, and tells a clerk there is more to see. The
// expandability is therefore DERIVED FROM THE PAYLOAD (is the next row
// deeper?) and never from the fact that a row is a group. The one-level case
// below is not an edge case; it is two thirds of everything that groups today.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2):
//
//   · **Asserting a row is ABSENT when the screen is empty.** A crashed viewer
//     satisfies every *"not on screen"* assertion perfectly. Each case that
//     asserts an absence first asserts the level-0 row IS on screen.
//   · **A bare `MemoryRouter`.** `useParams().tenant` would be undefined and
//     the screen would build `//reports/…`. Mounted on the real
//     `/:tenant/reports/:reportKey`, as `reportViewerControls.dom.test.tsx`
//     records.
//   · **Counting requests only after the click.** A screen that refetches on
//     EVERY render would show zero between two snapshots taken too late, so the
//     spy is read immediately before the click and immediately after.
//   · **Testing the pure function only.** `visibleRows` can be perfect while
//     nothing calls it — law 2's *built is not wired*. The DOM cases below
//     drive the real `ReportViewerPage`.
//   · **A close that is not a close.** Collapsing the OUTER level while the
//     inner one is still in the open set must hide BOTH; a naive
//     implementation that only checks a row's own parent passes an open/close
//     pair and fails this one.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";
import type { ApiClient } from "@/api/client";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportGroupRow, ReportResponse, ReportRow } from "@/api/reportsEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportViewerPage, pagerTotal } from "./ReportViewerPage";
import { groupDisclosureKey, openableGroups, visibleRows } from "./ReportGroupRow";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const t = i18n.getFixedT("en");
const TENANT = "brazosbend";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

// ── The fixture is the SERVER'S OWN ANSWER, not an invention ───────────────
//
// `runner.run("trend_pack", {"group_by": ["year", "accounting_period",
// "service"]})` on real PostgreSQL 16 against the seeded `brazosbend` tenant,
// 2026-09-27, returns `collapsed: True` and exactly three rows — one per level,
// each covering 36 lines. Reproduced by `10-scripts/rep_p2_24_grouping_depth.py`.
//
// ⚠ **THE THIRD LEVEL'S VALUE IS `null` AND ITS `filters` ARE `null`, AND BOTH
// ARE THE SERVER'S REAL ANSWER RATHER THAN A GAP IN THE FIXTURE** — the seeded
// journal lines carry no service, so the level exists and names nothing. It is
// kept because it is what a clerk will actually meet.
function groupRow(
  level: number,
  dimension: string,
  value: string | null,
  filters: Record<string, string> | null,
): ReportGroupRow {
  return {
    __kind__: "group",
    level,
    dimension,
    value,
    path: [{ dimension, column: dimension, value }],
    filters,
    drill_unavailable: filters === null ? "drill_through_filter_is_not_declared" : null,
    rows: 36,
    subtotals: { debit: "15816.000000", credit: "15816.000000" },
  };
}

const YEAR = groupRow(0, "year", "2026-01-01", { from: "2026-01-01", to: "2026-12-31" });
const MONTH = groupRow(1, "accounting_period", "2026-09-01", {
  from: "2026-09-01",
  to: "2026-09-30",
});
const SERVICE = groupRow(2, "service", null, null);

/** `trend_pack`, grouped three deep — `collapsed: true`, so no fact rows. */
const THREE_LEVELS = {
  key: "trend_pack",
  basis: "posting",
  window: { start: "2026-01-01", end: "2026-12-31" },
  currency: "USD",
  columns: ["posted_on", "account_name", "debit", "credit"],
  rows: [YEAR, MONTH, SERVICE],
  kpis: [],
  totals: { debit: "15816.000000", credit: "15816.000000" },
  unavailable: [],
  grain: "journal line",
  group_by: ["year", "accounting_period", "service"],
  collapsed: true,
  page: { page: 1, per: 50, total: 36, pages: 1 },
  controls: { sorts: ["posted_on"], sort: "posted_on", dir: "asc", searchable: true },
};

/** `ar_aging` grouped by consumer class — ONE level, facts interleaved, which
 *  is the OTHER shape the server serves (`collapsed: false`, the Python path).
 *  Two thirds of everything that groups today looks like this. */
const FACT: ReportRow = {
  account_id: "a1",
  account_no: "100244",
  customer: "Ruiz, Marisol",
  total: "108.88",
} as unknown as ReportRow;

const ONE_LEVEL = {
  ...THREE_LEVELS,
  key: "ar_aging",
  columns: ["account_no", "customer", "total"],
  rows: [groupRow(0, "consumer_class", "Residential", { class: "residential" }), FACT],
  group_by: ["consumer_class"],
  collapsed: false,
  page: { page: 1, per: 50, total: 26, pages: 1 },
};

function recordingClient(report: unknown): { client: ApiClient; reportCalls: string[] } {
  const reportCalls: string[] = [];
  const get = async (path: string) => {
    if (path.startsWith("/reports/")) {
      reportCalls.push(path);
      return { data: report, status: 200 };
    }
    if (path === "/reports") {
      return {
        data: { cards: [], vocabularies: { services: [], bill_types: [], purposes: [] } },
        status: 200,
      };
    }
    return { data: { results: [], count: 0 }, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    reportCalls,
    client: {
      request: get,
      get,
      post: write,
      put: write,
      patch: write,
      delete: write,
    } as unknown as ApiClient,
  };
}

function mountViewer(client: ApiClient, reportKey: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: (
          <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-09-26" />
        ),
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/${reportKey}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The disclosure for one group row, by its accessible name — which is the
 *  kit's own `table.expand.row` / `rowCollapse`, so this asserts the SHIPPED
 *  string and not one this test invented. */
function discloser(label: string, open: boolean): HTMLElement | null {
  const key = open ? "table.expand.rowCollapse" : "table.expand.row";
  return screen.queryByRole("button", { name: t(key, { row: label }) });
}

// ═══════════════════════════════════════════════════════════════════════════
// THE PURE FUNCTIONS — asserted without a browser, because they are arithmetic
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.24 · which group rows can be opened at all", () => {
  it("names the two that have something beneath them and NOT the deepest", () => {
    const open = openableGroups([YEAR, MONTH, SERVICE]);
    expect(open.has(groupDisclosureKey(YEAR))).toBe(true);
    expect(open.has(groupDisclosureKey(MONTH))).toBe(true);
    // ⚠ THE LOAD-BEARING ONE. `collapsed: true` means the facts are NOT in this
    // payload, so the third level opens nothing. A control here would be law
    // 2's mirror — and on 45 of the 46 live definitions this is the ONLY kind
    // of group row there is.
    expect(open.has(groupDisclosureKey(SERVICE))).toBe(false);
  });

  it("names a one-level group WITH interleaved facts, and none without", () => {
    const solo = groupRow(0, "consumer_class", "Residential", { class: "residential" });
    expect(openableGroups([solo, FACT]).has(groupDisclosureKey(solo))).toBe(true);
    expect(openableGroups([solo]).size).toBe(0);
  });

  it("finds nothing to open in an UNGROUPED report", () => {
    expect(openableGroups([FACT, FACT]).size).toBe(0);
  });
});

describe("P2.24 · what is visible at each state", () => {
  const keyOf = groupDisclosureKey;

  it("rests CLOSED — only the outermost level is on the screen", () => {
    expect(visibleRows([YEAR, MONTH, SERVICE], new Set())).toEqual([YEAR]);
  });

  it("opens ONE level at a time, never the whole tree", () => {
    const open = new Set([keyOf(YEAR)]);
    expect(visibleRows([YEAR, MONTH, SERVICE], open)).toEqual([YEAR, MONTH]);
  });

  it("opens all three when both parents are open", () => {
    const open = new Set([keyOf(YEAR), keyOf(MONTH)]);
    expect(visibleRows([YEAR, MONTH, SERVICE], open)).toEqual([YEAR, MONTH, SERVICE]);
  });

  it("closes the OUTER level and takes the inner one with it, still open or not", () => {
    // ⚠ The inner level is STILL in the open set. A row is visible only when
    // EVERY ancestor is open, so closing the year hides the month AND the
    // service — and re-opening the year restores the month expanded, which is
    // *"collapse restores it"* read exactly.
    const open = new Set([keyOf(MONTH)]);
    expect(visibleRows([YEAR, MONTH, SERVICE], open)).toEqual([YEAR]);
  });

  it("hides interleaved FACT rows under a closed group and shows them under an open one", () => {
    const solo = groupRow(0, "consumer_class", "Residential", { class: "residential" });
    expect(visibleRows([solo, FACT], new Set())).toEqual([solo]);
    expect(visibleRows([solo, FACT], new Set([keyOf(solo)]))).toEqual([solo, FACT]);
  });

  it("leaves an UNGROUPED report exactly as served", () => {
    const rows = [FACT, FACT];
    expect(visibleRows(rows, new Set())).toEqual(rows);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THE SCREEN — built is not wired, so these drive the real page
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.24 · three levels open and close on the running screen", () => {
  it("opens and closes without a single request", async () => {
    const { client, reportCalls } = recordingClient(THREE_LEVELS);
    mountViewer(client, "trend-pack");

    await waitFor(() => expect(screen.getByText("2026-01-01")).toBeTruthy());
    // A zero that cannot be told from a screen which never loaded is worth
    // nothing, so the first paint is asserted to have COST something.
    expect(reportCalls.length).toBeGreaterThan(0);

    // Rests closed: the month is not drawn.
    expect(screen.queryByText("2026-09-01")).toBeNull();

    const beforeOpen = reportCalls.length;
    fireEvent.click(discloser("2026-01-01", false)!);
    await waitFor(() => expect(screen.getByText("2026-09-01")).toBeTruthy());
    expect(reportCalls.length).toBe(beforeOpen);

    // Second level opens the third — three levels, one payload.
    fireEvent.click(discloser("2026-09-01", false)!);
    await waitFor(() =>
      expect(screen.getByText(t("reports.subtotal.blank"))).toBeTruthy(),
    );
    expect(reportCalls.length).toBe(beforeOpen);

    // Collapse restores it — and takes the third level with it.
    fireEvent.click(discloser("2026-01-01", true)!);
    await waitFor(() => expect(screen.queryByText("2026-09-01")).toBeNull());
    expect(screen.queryByText(t("reports.subtotal.blank"))).toBeNull();
    expect(screen.getByText("2026-01-01")).toBeTruthy();
    expect(reportCalls.length).toBe(beforeOpen);
  });

  // ── `DEF-REP-6891` · THE PAGER COUNTS WHAT THE TABLE DRAWS ───────────────
  it("counts its own GROUP rows on a collapsed answer, never the facts behind them", async () => {
    // ⚠ **`THREE_LEVELS` IS THE DEFECT EXACTLY**: three group rows served,
    // `page.total: 36` — a count of FACT rows. Walked at 1440 on the trend
    // pack grouped three deep, the table drew three lines under **"1–36 of
    // 36"**. Both numbers were right about different things.
    expect(THREE_LEVELS.page.total).toBe(36);
    expect(THREE_LEVELS.rows.length).toBe(3);
    expect(pagerTotal(THREE_LEVELS as unknown as ReportResponse)).toBe(3);

    // And on the screen, where it was photographed.
    const { client } = recordingClient(THREE_LEVELS);
    mountViewer(client, "trend-pack");
    await waitFor(() => expect(screen.getByText("2026-01-01")).toBeTruthy());
    expect(document.body.textContent ?? "").not.toMatch(/of\s*36\b/);
  });

  it("still quotes the SERVER's total where the facts ARE the rows", () => {
    // The half that keeps `ar_aging` right: `collapsed: false` interleaves
    // FACT rows, so `page.total` and the rows on screen are the same kind of
    // thing. Counting rows here would print "1–2 of 2" over a receivable of
    // any size — the mirror of the defect above.
    expect(pagerTotal(ONE_LEVEL as unknown as ReportResponse)).toBe(26);
    // A report that does not page at all is saying *this is all of it*.
    const unpaged: Record<string, unknown> = { ...ONE_LEVEL };
    delete unpaged.page;
    expect(pagerTotal(unpaged as unknown as ReportResponse)).toBe(2);
    expect(pagerTotal(undefined)).toBeNull();
  });

  it("draws NO disclosure on the deepest level, which has nothing behind it", async () => {
    const { client } = recordingClient(THREE_LEVELS);
    mountViewer(client, "trend-pack");

    await waitFor(() => expect(screen.getByText("2026-01-01")).toBeTruthy());
    fireEvent.click(discloser("2026-01-01", false)!);
    await waitFor(() => expect(screen.getByText("2026-09-01")).toBeTruthy());
    fireEvent.click(discloser("2026-09-01", false)!);
    await waitFor(() =>
      expect(screen.getByText(t("reports.subtotal.blank"))).toBeTruthy(),
    );

    // The row IS on screen — so this absence is an absence and not a crash.
    expect(discloser(t("reports.subtotal.blank"), false)).toBeNull();
    expect(discloser(t("reports.subtotal.blank"), true)).toBeNull();
  });

  it("opens a one-level report onto its FACT rows, still with no request", async () => {
    const { client, reportCalls } = recordingClient(ONE_LEVEL);
    mountViewer(client, "ar-aging");

    await waitFor(() => expect(screen.getByText("Residential")).toBeTruthy());
    expect(screen.queryByText("100244")).toBeNull();

    const before = reportCalls.length;
    fireEvent.click(discloser("Residential", false)!);
    await waitFor(() => expect(screen.getByText("100244")).toBeTruthy());
    expect(reportCalls.length).toBe(before);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P2.24 (05-prototype/09 Reports Build Brief.pdf p013 + p028 2·1E note ②, read as images per B14 rule 42)
// screens: 2·1E group rows
// generated: 2026-09-27 by lane REP-P2-REST
// gates: RED PROVED FIRST through `npx vitest run` — the harness that runs it — before ReportGroupRow exported any of these three functions
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
