// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-184-BRC10 — receivables by service on screen: the `receivables`
//          dataset in the builder, a custom report on it with its As-of box,
//          and the library report *Receivables over 90 days by service*.
// Rules:   hard-won law 2's fixture clause (mount under the REAL path
//          patterns `App.tsx` registers) · law 7 (what would make these pass
//          wrongly) · B14 rule 31 (no code on screen — `taxes` reads *Taxes*)
//          · hard rule 2 (money displays at 2)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
//   · **A screen that never asked the server.** Every case waits on the fake
//     server's call before asserting.
//   · **A raw code that happens to read like a word.** `taxes` and `Taxes`
//     differ only in case, so the class row is asserted as `Other charges` —
//     which no code spells — and the code `other` is asserted ABSENT.
//   · **An As-of box from the report key.** The custom report's key is one no
//     map names (`my-over-90`); only the dataset fallback can draw the box.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportEditorPage } from "./ReportEditorPage";
import { offeredFilters } from "./ReportParameters";
import { ReportViewerPage } from "./ReportViewerPage";
import { REPORTS_ROUTE, REPORT_BUILDER_NEW_ROUTE } from "./reportsShared";

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

const MONEY = { type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 };
const TEXT = { type: "text", unit: null, unit_from: null, money_basis: null, scale: null };

/** `apps/reports/datasets.RECEIVABLES`, as `GET /reports/datasets` serves it. */
const RECEIVABLES_DATASET = {
  code: "receivables",
  owner_module: "payments",
  grain: "one account and service",
  columns: [
    { name: "account_no", ...TEXT },
    { name: "customer_name", ...TEXT },
    { name: "service", ...TEXT },
    { name: "service_code", ...TEXT },
    { name: "charge_class", ...TEXT },
    { name: "current", ...MONEY },
    { name: "d1_30", ...MONEY },
    { name: "d31_60", ...MONEY },
    { name: "d61_90", ...MONEY },
    { name: "d90_plus", ...MONEY },
    { name: "total", ...MONEY },
  ],
  measures: ["current", "d1_30", "d31_60", "d61_90", "d90_plus", "total"].map((name) => ({
    name,
    aggregation: "sum",
    additivity: "semi",
    forbidden_across: ["time"],
  })),
  dimensions: [
    { name: "time", attributes: [], hierarchy: null, conformed: true },
    { name: "service", attributes: [], hierarchy: null, conformed: true },
    { name: "age_bucket", attributes: [], hierarchy: null, conformed: false },
  ],
  filters: ["as_of", "to", "service"],
  time_hierarchy: "calendar",
  paginates: true,
};

/** The worked figure the PO was shown: water 40.00 + sewer 20.00 owed, tax
 *  8.00 and fee 5.00 untouched — plus a line no class places (*Other*). */
const CUSTOM = {
  key: "my-over-90",
  dataset: "receivables",
  name: "My over 90",
  basis: "posting",
  window: { as_of: "2026-09-30" },
  currency: "USD",
  columns: ["account_no", "service", "charge_class", "d90_plus", "total"],
  column_meta: {
    account_no: TEXT,
    service: TEXT,
    charge_class: TEXT,
    d90_plus: MONEY,
    total: MONEY,
  },
  rows: [
    { account_no: "AC-1", service: "Water", service_code: "water", charge_class: null, d90_plus: "40.0000", total: "40.0000" },
    { account_no: "AC-1", service: "Sewer", service_code: "sewer", charge_class: null, d90_plus: "20.0000", total: "20.0000" },
    { account_no: "AC-1", service: null, service_code: null, charge_class: "taxes", d90_plus: "8.0000", total: "8.0000" },
    { account_no: "AC-1", service: null, service_code: null, charge_class: "other", d90_plus: "5.0000", total: "5.0000" },
  ],
  kpis: [],
  totals: { d90_plus: "73.0000", total: "73.0000" },
  unavailable: [],
  grain: "account_service",
  page: { page: 1, per: 50, total: 4, pages: 1 },
  controls: { sorts: ["total", "d90_plus", "account_no"], sort: "total", dir: "desc", searchable: false },
};

const LIBRARY = {
  key: "receivables_over_90_by_service",
  dataset: "receivables",
  name: "Receivables over 90 days by service",
  basis: "posting",
  window: { as_of: "2026-09-30" },
  currency: "USD",
  columns: ["service", "charge_class", "debtors", "d90_plus", "share_pct", "total"],
  column_meta: {
    debtors: { type: "count", unit: null, unit_from: null, money_basis: null, scale: null },
    d90_plus: MONEY,
    total: MONEY,
    share_pct: { type: "percent", unit: null, unit_from: null, money_basis: null, scale: 6 },
  },
  rows: [
    { service: "Water", service_code: "water", charge_class: null, debtors: 2, d90_plus: "60.0000", share_pct: "64.516129", total: "60.0000" },
    { service: "Sewer", service_code: "sewer", charge_class: null, debtors: 2, d90_plus: "20.0000", share_pct: "21.505376", total: "27.0000" },
    { service: null, service_code: null, charge_class: "taxes", debtors: 1, d90_plus: "8.0000", share_pct: "8.602151", total: "8.0000" },
    { service: null, service_code: null, charge_class: "fees", debtors: 1, d90_plus: "5.0000", share_pct: "5.376344", total: "5.0000" },
  ],
  kpis: [
    { key: "d90_plus", value: "93.0000", kind: "money", detail: null, reason_code: null },
    { key: "debtors", value: 2, kind: "count", detail: null, reason_code: null },
    { key: "total_ar", value: "100.0000", kind: "money", detail: null, reason_code: null },
  ],
  totals: { debtors: 2, d90_plus: "93.0000", total: "100.0000", ar_control: "140.0000" },
  unavailable: [
    {
      code: "receivables_by_service_does_not_foot_to_the_ar_control_total",
      br_ref: "BR-REP-008 · BR-LED-007",
      detail: "Σ of every service row is 100.0000 and the ledger's AR control total is 140.0000",
    },
  ],
  grain: "service",
  exportable: true,
};

function fakeServer(): { client: ApiClient; calls: string[] } {
  const calls: string[] = [];
  const get = async (path: string) => {
    calls.push(path);
    if (path === "/reports/datasets") {
      return { data: { datasets: [RECEIVABLES_DATASET], count: 1 }, status: 200 };
    }
    if (path === "/reports") {
      return {
        data: {
          cards: [],
          groups: [{ code: "receivables", name: "Receivables", sub_groups: [] }],
          vocabularies: { services: [], bill_types: [], purposes: [] },
        },
        status: 200,
      };
    }
    if (path.startsWith("/reports/receivables_over_90_by_service")) return { data: LIBRARY, status: 200 };
    if (path.startsWith("/reports/my-over-90") || path.startsWith("/reports/my_over_90")) {
      return { data: CUSTOM, status: 200 };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    calls,
    client: { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient,
  };
}

function seeded(): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  return queryClient;
}

function mountViewer(client: ApiClient, segment: string) {
  // ⚠ THE REAL PATH PATTERN — `/:tenant/reports/:reportKey`.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-10-14" />,
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/${segment}`] },
  );
  render(
    <QueryClientProvider client={seeded()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function mountBuilder(client: ApiClient) {
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORT_BUILDER_NEW_ROUTE}`,
        element: <ReportEditorPage blank client={client} timeZone="America/Chicago" today="2026-10-14" />,
      },
      { path: `/:tenant${REPORTS_ROUTE}/:reportKey`, element: <p>the viewer</p> },
    ],
    { initialEntries: [`/${TENANT}${REPORT_BUILDER_NEW_ROUTE}`] },
  );
  render(
    <QueryClientProvider client={seeded()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-184 · receivables by service on screen", () => {
  it("the builder offers the Receivables dataset in words and draws its columns", async () => {
    const server = fakeServer();
    mountBuilder(server.client);
    const chooser = (await screen.findByLabelText("Dataset")) as HTMLSelectElement;
    await waitFor(() =>
      expect(Array.from(chooser.options).map((one) => one.value)).toContain("receivables"),
    );
    const option = Array.from(chooser.options).find((one) => one.value === "receivables");
    expect(option?.textContent, "the dataset code reached the screen (B14 rule 31)").toBe("Receivables");
    fireEvent.change(chooser, { target: { value: "receivables" } });
    await waitFor(() => expect(screen.getByText("Charge type")).toBeTruthy());
    expect(screen.getAllByText("Over 90 days").length).toBeGreaterThan(0);
    expect(screen.getByText("one account and service")).toBeTruthy();
    // DEF-REP-10145 — every filter and group-by option reads as a WORD; the
    // raw names `as_of` and `age_bucket` used to be printed as they are.
    const optionTexts = Array.from(document.querySelectorAll("option")).map((one) => one.textContent?.trim());
    expect(optionTexts).not.toContain("as_of");
    expect(optionTexts).not.toContain("age_bucket");
    expect(optionTexts).toContain("As of");
    expect(optionTexts).toContain("Age band");
  });

  it("a custom report on the dataset renders, with class rows in words", async () => {
    const server = fakeServer();
    mountViewer(server.client, "my-over-90");
    await waitFor(() => expect(server.calls.some((one) => one.startsWith("/reports/my"))).toBe(true));
    await waitFor(() => expect(screen.getByText("Other charges")).toBeTruthy());
    expect(screen.getByText("Taxes")).toBeTruthy();
    expect(screen.getByText("Water")).toBeTruthy();
    expect(screen.getAllByText("$40.00").length).toBeGreaterThan(0);
    // The raw class code never reaches a cell.
    const cells = Array.from(document.querySelectorAll("td")).map((td) => td.textContent?.trim());
    expect(cells).not.toContain("other");
    expect(cells).not.toContain("taxes");
  });

  it("a custom report on the dataset draws the As-of box its key does not name", async () => {
    expect(offeredFilters("my-over-90")).toEqual([]);
    expect(offeredFilters("my-over-90", "receivables")).toEqual(["asOf"]);
    const server = fakeServer();
    mountViewer(server.client, "my-over-90");
    await waitFor(() => expect(screen.getByText("Other charges")).toBeTruthy());
    expect(screen.getByLabelText("As of")).toBeTruthy();
  });

  it("the library report renders one row per service and says it does not foot", async () => {
    const server = fakeServer();
    mountViewer(server.client, "receivables-over-90-by-service");
    await waitFor(() =>
      expect(server.calls.some((one) => one.startsWith("/reports/receivables_over_90_by_service"))).toBe(true),
    );
    await waitFor(() => expect(screen.getByText("Fees")).toBeTruthy());
    expect(screen.getByText("Sewer")).toBeTruthy();
    expect(screen.getAllByText("$60.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Rows do not match the books. The report never adjusts itself.")).toBeTruthy();
    expect(screen.getByLabelText("As of")).toBeTruthy();
  });
});
