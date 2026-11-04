// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-10164 (PO 2026-10-17) — Premises and Units lists show
//          Created (MM/DD/YYYY) and Age, both sortable; both headers send
//          `sort=created`; the unit reads its OWN date.
// ───────────────────────────────────────────────────────
// Mounted under the REAL route patterns (hard-won law 2) with a stub fetch, so
// what is asserted is the rendered cell and the request on the wire.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { MyPermissions, PremisesRow, UnitRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { TenantRegionalProvider } from "@/components/TenantRegional";

import { PREMISES_PERMISSION } from "./meteringShared";
import { PremisesListPage } from "./PremisesListPage";
import { UnitsListPage } from "./UnitsListPage";

const TENANT = "brazosbend";

function fullAccess(): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

function premises(over: Partial<PremisesRow>): PremisesRow {
  return {
    id: "01a0dd9e-0000-7000-8000-0000000000aa",
    premise_no: "P-00101",
    name: null,
    address_line: "101 Silver Creek Rd",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    premises_type: null,
    premises_type_name: null,
    status: "active",
    units: 1,
    services_available: ["water"],
    owner_manager: null,
    lat: null,
    lng: null,
    ...over,
  } as unknown as PremisesRow;
}

function unit(over: Partial<UnitRow>): UnitRow {
  return {
    id: "01a0dd9e-0000-7000-8000-000000000001",
    unit_no: "U-01145",
    premises_id: "01a0dd9e-0000-7000-8000-0000000000aa",
    premise_no: "P-00101",
    premise_address: "101 Silver Creek Rd",
    label: "2",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    services: ["water"],
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "none" },
    active: true,
    metered_services: [],
    missing_services: [],
    meters: [],
    occupancy: "vacant",
    occupant: null,
    account_no: null,
    status: "active",
    sub_metered: false,
    ...over,
  } as UnitRow;
}

function mount(
  path: string,
  pattern: string,
  element: (client: ApiClient) => JSX.Element,
  list: RegExp,
  rows: unknown[],
) {
  const urls: string[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, fullAccess());
  const fetchImpl = async (input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    const body =
      url.includes("/settings/services") || url.includes("/premises/types")
        ? []
        : url.includes("/custom-fields")
          ? { entity: "premises", fields: [] }
          : url.includes("/permissions")
            ? fullAccess()
            : list.test(url.split("#")[0])
              ? {
                  results: rows,
                  count: rows.length,
                  next: null,
                  previous: null,
                  service_gap_count: 0,
                }
              : { results: [], count: 0, next: null, previous: null };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const client = createApiClient({ tenant: TENANT, fetchImpl });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path={pattern} element={element(client)} />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { urls, client };
}

const listCalls = (urls: string[], list: RegExp) => urls.filter((u) => list.test(u.split("#")[0]));

beforeEach(() => {
  // The tenant's "today" — the PO's worked figure is on 10/17/2026.
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-10-17T17:00:00Z") });
});
afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

const PREMISES_LIST = /\/premises(\?|$)/;
const UNITS_LIST = /\/units(\?|$)/;

describe("Premises list — Created and Age (DEF-MET-10164)", () => {
  function mountPremises(rows: PremisesRow[]) {
    return mount(
      `/${TENANT}/premises`,
      "/:tenant/premises",
      (client) => <PremisesListPage client={client} />,
      PREMISES_LIST,
      rows,
    );
  }

  it("draws Created in the tenant format and Age in years and months", async () => {
    // midnight Chicago on 14 Mar 1996 is 06:00 UTC — the day must not slip.
    mountPremises([premises({ created_at: "1996-03-14T06:00:00+00:00" })]);
    const row = (await screen.findByText("101 Silver Creek Rd")).closest("tr")!;
    expect(within(row).getByText("03/14/1996")).toBeInTheDocument();
    expect(within(row).getByText("30 yrs 7 mos")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Created/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Age/ })).toBeInTheDocument();
  });

  it("a record created today reads 0 days", async () => {
    mountPremises([premises({ created_at: "2026-10-17T15:00:00+00:00" })]);
    const row = (await screen.findByText("101 Silver Creek Rd")).closest("tr")!;
    expect(within(row).getByText("10/17/2026")).toBeInTheDocument();
    expect(within(row).getByText("0 days")).toBeInTheDocument();
  });

  it("Created and Age headers both send sort=created, both directions", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { urls } = mountPremises([premises({ created_at: "1996-03-14T06:00:00+00:00" })]);
    await screen.findByText("101 Silver Creek Rd");
    await user.click(
      within(screen.getByRole("columnheader", { name: /Created/ })).getByRole("button"),
    );
    await waitFor(() =>
      expect(listCalls(urls, PREMISES_LIST).at(-1)).toMatch(
        /sort=created&dir=asc|dir=asc.*sort=created|sort=created.*dir=asc/,
      ),
    );
    await user.click(
      within(screen.getByRole("columnheader", { name: /Created/ })).getByRole("button"),
    );
    await waitFor(() => expect(listCalls(urls, PREMISES_LIST).at(-1)).toMatch(/dir=desc/));
    expect(listCalls(urls, PREMISES_LIST).at(-1)).toMatch(/sort=created/);
    // the Age header is the SAME sort: it is shown sorted too, and toggles it
    expect(screen.getByRole("columnheader", { name: /Age/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    await user.click(within(screen.getByRole("columnheader", { name: /Age/ })).getByRole("button"));
    await waitFor(() => expect(listCalls(urls, PREMISES_LIST).at(-1)).toMatch(/dir=asc/));
    expect(listCalls(urls, PREMISES_LIST).at(-1)).toMatch(/sort=created/);
  });
});

describe("Units list — the unit's OWN Created and Age (DEF-MET-10164)", () => {
  function mountUnits(rows: UnitRow[]) {
    return mount(
      `/${TENANT}/premises/units`,
      "/:tenant/premises/units",
      (client) => <UnitsListPage client={client} />,
      UNITS_LIST,
      rows,
    );
  }

  it("a unit added in 2015 to a 1996 building is 11 yrs", async () => {
    mountUnits([unit({ created_at: "2015-06-01T05:00:00+00:00" })]);
    const row = (await screen.findByText("U-01145")).closest("tr")!;
    expect(within(row).getByText("06/01/2015")).toBeInTheDocument();
    expect(within(row).getByText("11 yrs 4 mos")).toBeInTheDocument();
  });

  it("the Age header sends sort=created", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { urls } = mountUnits([unit({ created_at: "2015-06-01T05:00:00+00:00" })]);
    await screen.findByText("U-01145");
    await user.click(within(screen.getByRole("columnheader", { name: /Age/ })).getByRole("button"));
    await waitFor(() => expect(listCalls(urls, UNITS_LIST).at(-1)).toMatch(/sort=created/));
    expect(listCalls(urls, UNITS_LIST).at(-1)).toMatch(/dir=asc/);
    await user.click(
      within(screen.getByRole("columnheader", { name: /Created/ })).getByRole("button"),
    );
    await waitFor(() => expect(listCalls(urls, UNITS_LIST).at(-1)).toMatch(/dir=desc/));
  });
});
