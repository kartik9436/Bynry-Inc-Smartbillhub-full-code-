// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-179-BRC10 point (1), PO 2026-10-12 (*"this is correct"*): each
//          history row gets **Open in report**, re-opening the standard viewer
//          with that run's parameters — declared inputs (typed rates included)
//          as `in.<param>`, the fixed filters the way `searchFrom` writes them.
// Rules:   hard-won law 2 (a door is asserted by ADDRESS, and by what the
//          screen behind it then ASKS the server) · its fixture clause (mount
//          under the real `/:tenant/reports/...` patterns) · law 7 (red first).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2): an href that is
// right as a string and wrong as a route. So the Rate Impact case CLICKS the
// link and asserts what the viewer then sends to the server — `rows` parsed as
// JSON and compared whole, beside `services` and `months`.
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportRun } from "@/api/runHistoryEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportRunsPage } from "./ReportRunsPage";
import { ReportViewerPage } from "./ReportViewerPage";
import { HISTORY_ROUTE } from "./ReportsTabs";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

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

const PERIOD = { fy_label: "FY2026", period: 9, start: "2026-09-01", end: "2026-09-30", status: "open" };

const ROWS_JSON = JSON.stringify([
  { type: "rate", item: "t-wrf", version: "v-wrf-3", capacity: "58", base: "9.00", price: "4.6000", min: "10.00" },
  { type: "charge", item: "c-inf", version: "v-inf-2", capacity: "", base: "4.00", price: null, min: null },
]);

function run(id: string, report: string, filters: Record<string, string>): ReportRun {
  return {
    id,
    report,
    ran_at: new Date().toISOString(),
    started_by: "Dana Whitfield",
    filters,
    status: "ready",
    progress: { done: 12, total: 12 },
    rows: 12,
    error: null,
    expires_at: null,
    file: `/api/exports/${id}/file`,
  };
}

const RATE_RUN: ReportRun = {
  ...run("r1", "rate_impact", { services: "water,trash", months: "6", rows: ROWS_JSON }),
  // `apps/reports/run_history.summary` — the run IN WORDS (B14 rule 31).
  summary: [
    { parts: [{ text: "Water, Trash" }, { label_key: "reports.input.allClasses" }, { label_key: "reports.input.months_other", params: { count: 6 } }] },
    {
      parts: [{ text: "Water · Residential Flat" }, { text: "v3" }, { text: '5/8" meter' }],
      figures: [
        { label_key: "reports.rateImpact.input.rows.column.base", kind: "money", value: "9.0000" },
        { label_key: "reports.rateImpact.input.rows.column.price", kind: "unit_price", value: "4.6000" },
        { label_key: "reports.rateImpact.input.rows.column.min", kind: "money", value: "10.0000" },
      ],
    },
    {
      parts: [{ text: "Infrastructure fee" }, { text: "v2" }],
      figures: [{ label_key: "reports.rateImpact.input.rows.column.base", kind: "money", value: "4.0000" }],
    },
  ],
};
/** A Rate Impact run whose stored rows no longer resolve: no summary. */
const UNRESOLVED_RUN = run("r4", "rate_impact", { months: "6", rows: ROWS_JSON });
const REGISTER_RUN = run("r2", "billing_register", {
  from: "2026-09-01",
  to: "2026-09-30",
  bill_type: "regular",
  q: "100244",
  page: "3",
});
/** A run whose report this deployment cannot open in the viewer. */
const ROUTE_RUN = run("r3", "account_activity", { from: "2026-09-01", to: "2026-09-30" });

function card(key: string, kind: "viewer" | "route", available = true) {
  return {
    key,
    name: key,
    name_overridden: false,
    group: "billing",
    group_name: "Billing",
    sub_group: null,
    kind,
    origin: "built_in",
    badge: "",
    available,
    basis: null,
    basis_label: null,
    reason_code: null,
    reason_detail: null,
    routes_to_screen: null,
    service_codes: [],
    pinned: false,
  };
}

function fakeServer(): { client: ApiClient; reportCalls: string[] } {
  const reportCalls: string[] = [];
  const get = async (path: string) => {
    if (path.startsWith("/reports/history")) {
      return {
        data: {
          count: 4,
          next: null,
          previous: null,
          results: [RATE_RUN, REGISTER_RUN, ROUTE_RUN, UNRESOLVED_RUN],
          reports: ["rate_impact", "billing_register", "account_activity"],
          statuses: ["ready"],
          retention_days: 3,
        },
        status: 200,
      };
    }
    if (path === "/reports") {
      return {
        data: {
          cards: [card("rate_impact", "viewer"), card("billing_register", "viewer"), card("account_activity", "route")],
          vocabularies: { services: [], bill_types: ["regular"], purposes: [] },
        },
        status: 200,
      };
    }
    if (path.startsWith("/reports/")) {
      reportCalls.push(path);
      return {
        data: {
          key: "rate_impact",
          basis: "posting",
          window: { start: "2026-04-01", end: "2026-09-30" },
          currency: "USD",
          columns: [],
          rows: [],
          kpis: [],
          totals: {},
          unavailable: [],
        },
        status: 200,
      };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    reportCalls,
    client: { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient,
  };
}

function mount() {
  const server = fakeServer();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const router = createMemoryRouter(
    [
      { path: `/:tenant${HISTORY_ROUTE}`, element: <ReportRunsPage client={server.client} /> },
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: <ReportViewerPage client={server.client} timeZone="America/Chicago" today="2026-10-12" />,
      },
    ],
    { initialEntries: [`/${TENANT}${HISTORY_ROUTE}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...server, router };
}

function openLink(runId: string): HTMLAnchorElement | null {
  return document.querySelector<HTMLAnchorElement>(`[data-run-report="${runId}"] a`);
}

describe("CR-179 · a history row opens its report with the run's parameters", () => {
  it("Rate Impact: declared inputs return as in.<param> and the viewer sends them back", async () => {
    const { router, reportCalls } = mount();
    await waitFor(() => expect(openLink("r1")).not.toBeNull());
    const link = openLink("r1") as HTMLAnchorElement;
    expect(link.getAttribute("aria-label")).toBe("Open in report");
    const url = new URL(link.getAttribute("href") ?? "", "http://x");
    expect(url.pathname).toBe(`/${TENANT}${REPORTS_ROUTE}/rate-impact`);
    expect(url.searchParams.get("in.services")).toBe("water,trash");
    expect(url.searchParams.get("in.months")).toBe("6");
    expect(url.searchParams.get("in.rows")).toBe(ROWS_JSON);

    fireEvent.click(link);
    await waitFor(() => expect(reportCalls.length).toBeGreaterThan(0));
    expect(router.state.location.pathname).toBe(`/${TENANT}${REPORTS_ROUTE}/rate-impact`);
    const [path, search = ""] = reportCalls[reportCalls.length - 1].split("?");
    expect(path).toBe("/reports/rate_impact");
    const sent = new URLSearchParams(search);
    expect(sent.get("services")).toBe("water,trash");
    expect(sent.get("months")).toBe("6");
    expect(JSON.parse(sent.get("rows") ?? "null")).toEqual(JSON.parse(ROWS_JSON));
  });

  it("an older report's run still links the existing way — f.<filter>, bare controls, never the page", async () => {
    mount();
    await waitFor(() => expect(openLink("r2")).not.toBeNull());
    const url = new URL(openLink("r2")?.getAttribute("href") ?? "", "http://x");
    expect(url.pathname).toBe(`/${TENANT}${REPORTS_ROUTE}/billing-register`);
    expect(Object.fromEntries(url.searchParams)).toEqual({
      "f.from": "2026-09-01",
      "f.to": "2026-09-30",
      "f.bill_type": "regular",
      q: "100244",
    });
  });

  it("the PARAMETERS cell names a Rate Impact run in words — never an id or a size code (B14 rule 31)", async () => {
    // RED before: the cell printed the raw rows JSON — `t-wrf`, `v-wrf-3`, `58`.
    mount();
    await waitFor(() => expect(openLink("r1")).not.toBeNull());
    const row = document.querySelector('[data-run-report="r1"]')?.closest("tr") as HTMLElement;
    const summary = row.querySelector("[data-run-summary]") as HTMLElement;
    expect(summary).not.toBeNull();
    expect(Array.from(summary.querySelectorAll("li")).map((one) => one.textContent)).toEqual([
      "Water, Trash · All classes · 6 months",
      'Water · Residential Flat · v3 · 5/8" meter · Base / month 9.00 · Price per unit 4.60 · Minimum 10.00',
      "Infrastructure fee · v2 · Base / month 4.00",
    ]);
    for (const id of ["t-wrf", "v-wrf-3", "c-inf", "v-inf-2", '"capacity"']) {
      expect(row.textContent).not.toContain(id);
    }
    // A run that cannot be named prints no JSON either — and still opens.
    const unresolved = document.querySelector('[data-run-report="r4"]')?.closest("tr") as HTMLElement;
    expect(unresolved.textContent).not.toContain("t-wrf");
    expect(unresolved.textContent).toContain("6");
    expect(openLink("r4")).not.toBeNull();
  });

  it("draws no link for a run whose report does not open in the viewer", async () => {
    mount();
    await waitFor(() => expect(openLink("r1")).not.toBeNull());
    const row = document.querySelector('[data-run-open="r3"]')?.closest("tr") as HTMLElement;
    expect(row).toBeTruthy();
    expect(within(row).queryByLabelText("Open in report")).toBeNull();
    expect(openLink("r3")).toBeNull();
  });
});
