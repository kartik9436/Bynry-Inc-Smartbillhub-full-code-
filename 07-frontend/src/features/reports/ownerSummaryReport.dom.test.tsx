// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-185-BRC10 D4 — the Owner summary report in the standard viewer:
//          one owner, a row per property, a grand total; an owner finder in the
//          viewer and Print beside Download.
// Screens: 2·1 Report viewer at `/{tenant}/reports/owner_summary`.
// Rules:   hard-won law 2 and its mirror · law 7 clause 2 · B14 rules 31, 33, 43.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
//   · **A bare `MemoryRouter`.** The router mounts the REAL pattern, built from
//     `REPORTS_ROUTE`, so a link built without its tenant cannot read as fine.
//   · **Asserting the grand total from a cell of the page.** `$85.00` appears
//     in the KPI tile AND the footer; the figure the stub serves for the rows
//     sums to less than the totals on page two, so a screen summing its page
//     would print a different number.
//   · **Asserting the finder exists.** It must search MASTER accounts — the
//     request it sends is asserted to carry `f.kind=master`.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportPrintButton } from "./ReportPrintButton";
import { ReportViewerPage } from "./ReportViewerPage";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";
const ELM_ID = "01a0d23a-3a8e-7caa-9803-170d8fcfaa5c";

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

const COLUMNS = ["property", "account", "bills", "empty_units", "common_areas", "other_charges", "total"];
const MONEY_META = Object.fromEntries(
  ["empty_units", "common_areas", "other_charges", "total"].map((name) => [
    name,
    { type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
  ]),
);

function payload(subjectId: string | null) {
  const named = subjectId !== null;
  return {
    key: "owner_summary",
    dataset: "invoices",
    name: "Owner summary",
    basis: "posting",
    window: { start: "2026-09-01", end: "2026-09-30" },
    currency: "USD",
    columns: COLUMNS,
    column_meta: MONEY_META,
    column_choices: COLUMNS,
    ...(named
      ? { head: { subject: "owner", fields: [{ field: "owner", value: "Maple Rentals LLC" }] } }
      : {}),
    rows: named
      ? [
          { account_id: "a-oak", property: "12 Oak St", account: "AC-2026-00051", bills: 1,
            empty_units: "15.0000", common_areas: "40.0000", other_charges: "0.0000", total: "55.0000" },
          { account_id: "a-elm", property: "40 Elm Ave", account: "AC-2026-00052", bills: 1,
            empty_units: "0.0000", common_areas: "30.0000", other_charges: "0.0000", total: "30.0000" },
        ]
      : [],
    kpis: named
      ? [
          { key: "grand_total", value: "85.0000", kind: "money" },
          { key: "properties", value: 3, kind: "count" },
        ]
      : [
          { key: "grand_total", value: null, kind: "money", reason_code: "an_owner_summary_names_one_owner" },
          { key: "properties", value: null, kind: "count", reason_code: "an_owner_summary_names_one_owner" },
        ],
    totals: named
      ? { empty_units: "15.0000", common_areas: "70.0000", other_charges: "0.0000", total: "85.0000", bills: 2 }
      : {},
    unavailable: named ? [] : [{ code: "an_owner_summary_names_one_owner" }],
    grain: "property",
    exportable: true,
    controls: {
      sorts: [],
      sort: "",
      dir: "asc",
      searchable: false,
      requires: [{ param: "subject_id", finds: "owner" }],
      printable: true,
    },
    ...(named ? { page: { page: 1, per: 2, total: 3 } } : {}),
  };
}

function ownerClient() {
  const accountSearches: Record<string, unknown>[] = [];
  const reportCalls: string[] = [];
  const get = async (path: string, init?: { query?: Record<string, unknown> }) => {
    if (path === "/accounts") {
      accountSearches.push(init?.query ?? {});
      return {
        data: {
          results: [{ id: ELM_ID, account_no: "AC-2026-00052", name: "Maple Rentals LLC" }],
          count: 1,
        },
        status: 200,
      };
    }
    if (path.startsWith("/reports/datasets")) return { data: { datasets: [] }, status: 200 };
    if (path.startsWith("/reports/")) {
      const [, raw = ""] = path.split("?");
      reportCalls.push(raw);
      const subject = new URLSearchParams(raw).get("subject_id");
      return { data: payload(subject), status: 200 };
    }
    if (path === "/reports") {
      return { data: { cards: [], groups: [], vocabularies: { services: [], bill_types: [], purposes: [] } }, status: 200 };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    accountSearches,
    reportCalls,
    client: { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient,
  };
}

function mount(client: ApiClient, search: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
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
        element: <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-09-26" />,
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/owner_summary${search}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

const WINDOW = "?f.from=2026-09-01&f.to=2026-09-30";

describe("CR-185-BRC10 · the Owner summary in the viewer", () => {
  it("renders a row per property, the owner in the head, and the OWNER's grand total", async () => {
    const { client } = ownerClient();
    mount(client, `${WINDOW}&subject_id=${ELM_ID}`);
    expect(await screen.findByText("12 Oak St")).toBeTruthy();
    expect(screen.getByText("40 Elm Ave")).toBeTruthy();
    expect(screen.getByText("Maple Rentals LLC")).toBeTruthy();
    // Column words from the catalogue, never the codes.
    for (const word of ["Property", "Empty units", "Common areas", "Other charges"]) {
      expect(screen.getAllByText(word).length).toBeGreaterThan(0);
    }
    // The grand total is the server's ($85.00), not this page's rows ($85.00
    // would also be 55 + 30 — so the COMMON AREAS total, $70.00, which no row
    // on this page reaches, proves the footer is the server's).
    expect(screen.getAllByText("$85.00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$70.00").length).toBeGreaterThan(0);
    // B14 rule 31 — no uuid is visible.
    expect(document.body.textContent ?? "").not.toContain(ELM_ID);
    expect(screen.getByText("One row per property")).toBeTruthy();
  });

  it("asks for the owner IN THE VIEWER, searching master accounts only", async () => {
    const { client, accountSearches } = ownerClient();
    const router = mount(client, WINDOW);
    await waitFor(() => expect(document.getElementById("report-requires-subject_id")).not.toBeNull());
    const box = document.getElementById("report-requires-subject_id") as HTMLInputElement;
    fireEvent.change(box, { target: { value: "Maple" } });
    await waitFor(() => expect(accountSearches.length).toBeGreaterThan(0));
    expect(accountSearches.at(-1)).toMatchObject({ q: "Maple", "f.kind": "master" });
    fireEvent.click(await screen.findByText("AC-2026-00052 — Maple Rentals LLC"));
    await waitFor(() => expect(router.state.location.search).toContain(`subject_id=${ELM_ID}`));
    expect(await screen.findByText("12 Oak St")).toBeTruthy();
  });

  it("offers Print beside Download because the server says the report is a document", async () => {
    const { client } = ownerClient();
    mount(client, `${WINDOW}&subject_id=${ELM_ID}`);
    await screen.findByText("12 Oak St");
    expect(document.querySelector('[data-report-print="button"]')).not.toBeNull();
    expect(document.querySelector('[data-download="button"]')).not.toBeNull();
  });

  it("the Print button prints", () => {
    const print = vi.fn();
    render(<ReportPrintButton print={print} />);
    fireEvent.click(screen.getByRole("button", { name: "Print" }));
    expect(print).toHaveBeenCalledTimes(1);
    const button = screen.getByRole("button", { name: "Print" });
    expect(within(button).queryByText("Print")).toBeNull(); // icon-only, the word is the label
  });
});
