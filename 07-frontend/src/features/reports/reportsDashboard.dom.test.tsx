// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11` (the
//          screen), `P4.12` (period and comparison) and `P4.13` (the
//          panel→report handoff). Screen `3·1`, drawn on p036–p038, read as
//          IMAGES per B14 rule 42.
// Rules:   B14 rule 31 (no database id on screen) · rule 33 (RATIONALE is zero
//          words on screen) · CLAUDE.md hard rule 2 (money DISPLAY 2) ·
//          hard-won law 2 AND ITS MIRROR · its fixture clause (mount the
//          routed component under the REAL path pattern) · law 7 clause 2
//          Screens: `3·1`
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7 clause 2), asked
// before any of them was written:
//
//   · **Mounting `ReportsDashboardPage` bare** would leave
//     `useParams().tenant` undefined, and every panel address would come out
//     `//reports/ar_aging?…` — a protocol-relative URL to another host that
//     reads as a perfectly good string to `toContain`. That is the customer
//     portal's own defect, recorded in CLAUDE.md under hard-won law 2. Every
//     mount here is under the real `/:tenant/reports/dashboard` pattern, and
//     the door case asserts the address STARTS with `/brazosbend/`.
//   · **Asserting a panel "has a link"** would pass whether or not the link
//     carried the period, which is the only thing `P4.13` asks. The door case
//     reads the query string out of the `href` and compares it with the
//     period the screen was served.
//   · **Asserting the ageing panel renders** would pass on five em-dashes, and
//     an em-dash is exactly what `ar_aging` returns when it is handed a range
//     instead of an as-at date. So the panel case asserts a FORMATTED MONEY
//     STRING is on screen.
//   · **Asserting the KPI band renders four tiles** would pass over four
//     blanks. Each tile is asserted by the figure it shows, and the tile with
//     no figure is asserted by the words *Not counted yet*.
//   · **Asserting the Dashboard tab exists** would pass on a `<span>`. The tab
//     case asserts it is a TAB by role and that pressing it navigates.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { ReportsDashboardResponse } from "@/api/dashboardTabEndpoints";

import { ReportsDashboardPage } from "./ReportsDashboardPage";
import { DASHBOARD_TAB_ROUTE, LIVE_REPORT_TABS } from "./ReportsTabs";

afterEach(cleanup);

const TENANT = "brazosbend";

/** The signed figures p036 draws, as the server serves them: EXACT decimal
 *  strings at storage width. The screen is what rounds to two (hard rule 2). */
const PAYLOAD: ReportsDashboardResponse = {
  period: { id: "2026-09-01", start: "2026-09-01", end: "2026-09-30", fy_label: "FY2026", period_no: 12 },
  periods: [
    { id: "2026-09-01", start: "2026-09-01", end: "2026-09-30" },
    { id: "2026-08-01", start: "2026-08-01", end: "2026-08-31" },
  ],
  comparison: "same_period_last_year",
  comparisons: [{ id: "same_period_last_year" }, { id: "previous_period" }],
  comparison_period: { id: "2025-09-01", start: "2025-09-01", end: "2025-09-30" },
  basis: "posting",
  currency: "USD",
  kpis: [
    {
      id: "billed",
      kind: "money",
      value: "124855.5600",
      reason_code: null,
      comparison: { value: "121100.0000", change_pct: "3.100743", reason_code: null },
    },
    {
      id: "collected",
      kind: "money",
      value: "117604.1000",
      reason_code: null,
      comparison: { value: "110000.0000", change_pct: "6.912818", reason_code: null },
    },
    {
      id: "outstanding",
      kind: "money",
      value: "48221.1400",
      reason_code: null,
      comparison: { value: "48905.0000", change_pct: "-1.398221", reason_code: null },
    },
    {
      id: "days_to_collect",
      kind: "count",
      value: null,
      reason_code: "days_to_collect_is_not_published",
      comparison: { value: null, change_pct: null, reason_code: "days_to_collect_is_not_published" },
    },
  ],
  panels: [
    {
      id: "revenue_12_months",
      report_key: "revenue_by_service_rate",
      opens: true,
      report_params: { "f.from": "2026-09-01", "f.to": "2026-09-30" },
      reason_code: null,
      bars: [
        { period_id: "2025-10-01", start: "2025-10-01", end: "2025-10-31", value: "90000.0000", reason_code: null, current: false },
        { period_id: "2026-09-01", start: "2026-09-01", end: "2026-09-30", value: "124855.5600", reason_code: null, current: true },
      ],
    },
    {
      id: "where_the_money_sits",
      report_key: "ar_aging",
      opens: true,
      // ⚠ `f.as_of` AND NOT A RANGE — see the door case below.
      report_params: { "f.as_of": "2026-09-30" },
      reason_code: null,
      bands: [
        { band: "current", value: "28104.4000", share_pct: "58.3" },
        { band: "1-30", value: "11882.1000", share_pct: "24.6" },
        { band: "31-60", value: "4118.0000", share_pct: "8.5" },
        { band: "61-90", value: "2204.2400", share_pct: "4.6" },
        { band: "90+", value: "1912.4000", share_pct: "4.0" },
      ],
    },
    {
      id: "service_mix",
      report_key: "revenue_by_service_rate",
      opens: true,
      report_params: { "f.from": "2026-09-01", "f.to": "2026-09-30" },
      reason_code: null,
      services: [
        { service_code: "water", value: "84486.1000" },
        { service_code: "sewer", value: "31459.4600" },
        { service_code: null, value: "0.0000" },
      ],
    },
    {
      id: "biggest_movers",
      report_key: "usage_and_ranking",
      opens: true,
      report_params: { "f.from": "2026-09-01", "f.to": "2026-09-30" },
      reason_code: "usage_movers_are_not_published",
      movers: [],
    },
    {
      id: "month_closed",
      report_key: "close_pack",
      opens: true,
      report_params: { "f.from": "2026-09-01", "f.to": "2026-09-30" },
      reason_code: null,
      blocked: false,
      checks: [
        {
          check: "accounts_receivable",
          ours: "48221.1400",
          theirs: "48221.1400",
          difference: "0.0000",
          result: "agreed",
        },
      ],
    },
  ],
  unavailable: [
    { code: "budget_comparison_is_not_offered" },
    { code: "days_to_collect_is_not_published" },
    { code: "usage_movers_are_not_published" },
  ],
};

function serverFor(payload: ReportsDashboardResponse, calls: string[] = []): ApiClient {
  const get = async (path: string) => {
    calls.push(path);
    return { data: payload, status: 200 };
  };
  return { request: get, get, post: get, put: get, patch: get, delete: get } as unknown as ApiClient;
}

/**
 * Mount the screen **under the real tenant-scoped path pattern**.
 *
 * ⚠ Mounting it bare is the fixture fault CLAUDE.md records under hard-won
 * law 2: `useParams().tenant` comes back undefined, the page builds
 * `//reports/ar_aging`, and every `toContain` assertion still passes over a
 * URL pointing at another host.
 */
function mount(payload = PAYLOAD, calls: string[] = [], entry = `/${TENANT}${DASHBOARD_TAB_ROUTE}`) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${DASHBOARD_TAB_ROUTE}`,
        element: <ReportsDashboardPage client={serverFor(payload, calls)} />,
      },
      // The four addresses the tab strip navigates to must EXIST, or a click
      // resolves to nothing and the case passes over a broken strip.
      { path: "/:tenant/reports", element: <div>catalogue</div> },
      { path: "/:tenant/reports/scheduled", element: <div>scheduled</div> },
      { path: "/:tenant/reports/history", element: <div>history</div> },
    ],
    { initialEntries: [entry] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** Wait for the screen to have the served data in it.
 *
 * ⚠ **`findAllByText` AND NOT `findByText`.** An ambiguous anchor throws
 * *"Found multiple elements"* and fails EVERY case in the file for a reason
 * that has nothing to do with what any of them asserts — which is exactly the
 * kind of red that looks like a broken screen and is a broken test. */
async function ready() {
  return screen.findAllByText("$124,855.56");
}

describe("`3·1` — the Reports Dashboard tab", () => {
  it("draws the four tiles by their figures, DISPLAYED at two decimals", async () => {
    mount();
    await ready();
    // ⚠ **SCOPED TO THE KPI BAND, NOT TO THE WHOLE DOCUMENT.** `$48,221.14`
    // is the Outstanding tile AND both sides of the AR tie-out at the foot,
    // and `$124,855.56` is also a bar's own `title` — a document-wide
    // `getByText` throws *"Found multiple elements"* and fails the case over
    // a screen that is entirely correct. Two screens showing one figure is
    // fine when they are showing the same fact; what is forbidden is two
    // screens DERIVING it, which is what this whole module is arranged
    // against.
    const band = document.querySelector(".kpi-grid") as HTMLElement;
    expect(band, "the KPI band is not on screen").not.toBeNull();
    // Hard rule 2: served at storage width, shown at two.
    expect(within(band).getByText("$124,855.56")).toBeTruthy();
    expect(within(band).getByText("$117,604.10")).toBeTruthy();
    expect(within(band).getByText("$48,221.14")).toBeTruthy();
    // ⚠ And the raw string must be nowhere on screen — `124855.5600` under a
    // tile is the defect `MONEY_COLUMNS` records on the statement.
    expect(document.body.textContent).not.toContain("124855.5600");
  });

  it("the tile whose owner publishes no count reads `Not counted yet`", async () => {
    mount();
    await ready();
    expect(screen.getByText("Not counted yet")).toBeTruthy();
    // B14 rule 33: RATIONALE is ZERO words on screen. The reason a figure is
    // absent lives in the payload and in the code, never in the tile.
    expect(document.body.textContent).not.toContain("days_to_collect_is_not_published");
    expect(document.body.textContent).not.toMatch(/because|no definition|catalogue publishes/i);
  });

  it("each tile carries its comparison underneath, rounded to two", async () => {
    mount();
    await ready();
    expect(screen.getByText("3.10% against the comparison")).toBeTruthy();
    expect(screen.getByText("-1.40% against the comparison")).toBeTruthy();
  });

  it("draws all five panels", async () => {
    mount();
    await ready();
    for (const title of [
      "Revenue, 12 months",
      "Where the money sits",
      "Service mix",
      "Biggest movers",
      "Is the month closed?",
    ]) {
      expect(screen.getByText(title), `${title} is not on screen`).toBeTruthy();
    }
  });

  it("the ageing panel shows FIGURES and shares, not em-dashes", async () => {
    mount();
    await ready();
    const panel = document.querySelector('[data-panel-body="where_the_money_sits"]');
    expect(panel).not.toBeNull();
    const body = panel?.textContent ?? "";
    // ⚠ **A FORMATTED FIGURE, NOT MERELY A BAND ROW.** `ar_aging` handed a
    // RANGE returns an em-dash for every band through `additivity.footer`, and
    // a case that only counted rows would pass on five dashes.
    expect(body).toContain("$28,104.40");
    expect(body).toContain("58.3%");
    expect(body).not.toContain("—");
  });

  it("a period with NO revenue draws a sentence, not a blank panel", async () => {
    const empty = {
      ...PAYLOAD,
      panels: PAYLOAD.panels.map((panel) =>
        panel.id === "service_mix" ? { ...panel, services: [] } : panel,
      ),
    } as typeof PAYLOAD;
    mount(empty);
    await ready();
    const panel = document.querySelector('[data-panel-body="service_mix"]');
    // ⚠ **THE FIXTURE CARRIES THE EMPTY SHAPE BECAUSE THE FULL ONE HID A REAL
    // DEFECT** (`DEF-REP-6939`). With three services in every fixture, no case
    // ever mounted the shape this deployment actually serves for September
    // 2026 — and the panel rendered a heading, a link and two inches of
    // nothing, which a reader cannot tell apart from a panel that failed.
    expect(panel?.textContent).toBe("No revenue in this period.");
  });

  it("the movers panel says six words and keeps its door", async () => {
    mount();
    await ready();
    const panel = document.querySelector('[data-panel-body="biggest_movers"]');
    expect(panel?.textContent).toBe("Usage movers are not published");
    // Its report opens and is real, so the LINK stays live — two different
    // sentences, and hiding the link would say the wrong one.
    const link = screen
      .getAllByRole("link")
      .find((node) => (node.getAttribute("href") ?? "").includes("usage-and-ranking"));
    expect(link, "the movers panel lost its door").toBeTruthy();
  });

  it("the close pack shows the report's own verdict and never re-derives it", async () => {
    mount();
    await ready();
    const row = document.querySelector('[data-tie-out="accounts_receivable"]');
    expect(within(row as HTMLElement).getByText("Foots")).toBeTruthy();
    expect(row?.querySelector('[data-tie-out-result="agreed"]')).not.toBeNull();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `P4.13` — THE PERIOD CROSSES INTO THE REPORT
  // ═══════════════════════════════════════════════════════════════════════
  it("every panel's door carries the period, and it is tenant-scoped", async () => {
    mount();
    await ready();
    const hrefs = screen
      .getAllByRole("link")
      .map((node) => node.getAttribute("href") ?? "")
      .filter((href) => href.includes("/reports/"));
    expect(hrefs.length).toBe(5);
    for (const href of hrefs) {
      // ⚠ **TENANT-SCOPED.** `//reports/…` is a protocol-relative URL to
      // another host and `toContain("/reports/")` passes on it happily.
      expect(href.startsWith(`/${TENANT}/reports/`), `${href} is not tenant-scoped`).toBe(true);
      const query = new URLSearchParams(href.split("?")[1] ?? "");
      // ⚠ **THE PERIOD IS READ OUT OF THE HREF.** Asserting a link EXISTS says
      // nothing about the window it opens on, which is the only thing `P4.13`
      // asks: *"a dashboard that drops you into a report on a different window
      // is worse than one with no links."*
      if (query.has("f.as_of")) {
        expect(query.get("f.as_of")).toBe("2026-09-30");
      } else {
        expect(query.get("f.from")).toBe("2026-09-01");
        expect(query.get("f.to")).toBe("2026-09-30");
      }
    }
  });

  it("the ageing door is an as-at date and never a range", async () => {
    mount();
    await ready();
    const href =
      screen
        .getAllByRole("link")
        .map((node) => node.getAttribute("href") ?? "")
        .find((candidate) => candidate.includes("/reports/ar-aging")) ?? "";
    expect(href).toContain("f.as_of=2026-09-30");
    expect(href).not.toContain("f.from");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `P4.12` — THE PERIOD RIDES IN THE URL AND NOTHING IS REMEMBERED
  // ═══════════════════════════════════════════════════════════════════════
  it("changing the period moves the URL and re-reads, and stores nothing", async () => {
    const calls: string[] = [];
    const router = mount(PAYLOAD, calls);
    await ready();
    fireEvent.change(document.querySelector("[data-dashboard-period]") as HTMLSelectElement, {
      target: { value: "2026-08-01" },
    });
    await waitFor(() => expect(router.state.location.search).toContain("f.period=2026-08-01"));
    await waitFor(() => expect(calls.some((path) => path.includes("f.period=2026-08-01"))).toBe(true));
    // p036 ④: *"No write of any kind, not even a remembered period."*
    expect(window.localStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("opens on the period the URL names", async () => {
    const calls: string[] = [];
    mount(PAYLOAD, calls, `/${TENANT}${DASHBOARD_TAB_ROUTE}?f.period=2026-08-01`);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls[0]).toContain("f.period=2026-08-01");
  });

  it("offers the two comparisons the server offers, and no budget", async () => {
    mount();
    await ready();
    const control = document.querySelector("[data-dashboard-compare]") as HTMLSelectElement;
    expect([...control.options].map((option) => option.value)).toEqual([
      "same_period_last_year",
      "previous_period",
    ]);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // THE HOLD THAT EXPIRED
  // ═══════════════════════════════════════════════════════════════════════
  it("the tab strip now draws all four words, Dashboard among them", async () => {
    mount();
    await ready();
    expect(LIVE_REPORT_TABS.map((tab) => tab.id)).toEqual([
      "catalogue",
      "dashboard",
      "scheduled",
      "history",
    ]);
    // ⚠ **BY ROLE.** A nav word rendered as a `<span>` is the dead control
    // hard-won law 2's mirror is about — it looks like a door and opens
    // nothing.
    const tab = screen.getByRole("tab", { name: "Dashboard" });
    expect(tab).toBeTruthy();
  });

  it("pressing another tab navigates to its tenant-scoped address", async () => {
    const router = mount();
    await ready();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/${TENANT}/reports/history`),
    );
  });

  // ═══════════════════════════════════════════════════════════════════════
  // B14 rule 31
  // ═══════════════════════════════════════════════════════════════════════
  it("shows no database id anywhere on the screen", async () => {
    mount();
    await ready();
    // A uuid anywhere in the rendered text, in any cell — asserting one cell
    // is clean would pass while it sat in another.
    expect(document.body.textContent ?? "").not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });
});
