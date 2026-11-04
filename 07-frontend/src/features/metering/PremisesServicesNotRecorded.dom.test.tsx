// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-762 — *"'NOBODY HAS ASKED ABOUT THIS ADDRESS' AND 'THIS ADDRESS
//          OFFERS NOTHING' RENDER IDENTICALLY — THE READ PATH COLLAPSES NULL
//          INTO []"*
// Change:  CR-036 (h) — *"existing premises hold NULL … NULL is not 'none', it
//          is NEVER ASKED; do not backfill"* (PO, 2026-08-26)
// Screens: S14 premises list · PRM-02 premises detail · the PRM-01 edit modal
// Rules:   BR-MET-003 (services_available ⊆ the tenant's ENABLED services)
// ───────────────────────────────────────────────────────
// ⚠ **EVERY ASSERTION HERE IS ABOUT RENDERED OUTPUT, AND THAT IS DELIBERATE.**
// The defect lived in a serialiser, but its harm was on a screen: a clerk read
// "No services" and could not tell whether the address had been ASKED. A test
// that asserted the prop would have gone green on a page that still printed the
// wrong sentence — so the three screens are rendered and their TEXT is read.
//
// ⚠ **AND NOTHING BELOW WEAKENS THE NO-BACKFILL GUARANTEE.** The write-side
// pins (`06-backend/tests/test_cr036h_premises_services_write.py`, and the
// untouched-control case in `PremisesServices.dom.test.tsx`) are what keep the
// NULL in the column; these are about publishing it. The last case here asserts
// the same no-backfill behaviour a second time, on the shape that now actually
// reaches the screen (`null`, not `[]`).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import type {
  PremisesDetail,
  PremisesPage,
  PremisesRow,
  PremisesType,
  TenantServiceRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";

import { PremisesDetailPage, premisesDetailQueryKey, premisesAssetsQueryKey } from "./PremisesDetailPage";
import {
  PremisesEditModal,
  premisesQueryKey,
  premisesTableConfig,
  premisesTypesQueryKey,
} from "./PremisesListPage";
import { PremisesTabsPage, premisesRollupQueryKey } from "./PremisesTabsPage";
import { PREMISES_TAB_PREMISES } from "./meteringShared";
import EN from "../../i18n/locales/en.json";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const TYPES: PremisesType[] = [
  { id: "t1", code: "single_family", name: "Single-family", active: true, is_system: true },
];

/** `GET /settings/services` for a utility that sells three of the ten platform
 *  services. Read by the edit modal's control; nothing seeds it. */
function tenantServices(): TenantServiceRow[] {
  const row = (service: string, name: string, enabled: boolean): TenantServiceRow => ({
    service,
    name,
    enabled,
    primary_uom: null,
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  });
  return [
    row("electric", "Electric", true),
    row("water", "Water", true),
    row("gas", "Gas", false),
  ];
}

function premise(over: Partial<PremisesDetail> = {}): PremisesDetail {
  return {
    id: "p-101",
    premise_no: "P-00101",
    name: null,
    address_line: "1408 Bluestem Ln",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "single_family",
    premises_type_name: "Single-family",
    // The row nobody has been asked about. Every case below overrides it.
    services_available: null,
    owner_manager: "Whitfield Rentals LLC",
    owner: null,
    owner_unmatched: false,
    external_ref: null,
    // CR-069 wave M — `OQ-INT-1471`'s mark. `false` is the true answer for
    // every address not typed past an unreachable City.
    gis_unchecked: false,
    // CR-089 wave A `PUJ-10`. A placed property that NOBODY HAS CHECKED — the
    // state all 673 are in: `gis_unchecked` is `false` because that is the
    // column's default, and `gis_checked_at` being null is what makes the
    // screen read *Not checked yet* rather than *Checked*.
    lat: "30.752104",
    lng: "-98.238391",
    gis_checked_at: null,
    gis_checked_by: null,
    status: "active",
    units: 2,
    unit_rows: [],
    units_common: 0,
    ...over,
  };
}

function page(rows: PremisesDetail[]): PremisesPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    rollup: { premises: rows.length, units: 2, common: 0, vacant: 0, pending_activation: 0 },
  };
}

/** The param-parsing config only — the LIST page builds its own cells, which is
 *  what makes this a rendered-output test and not a prop test. */
const CONFIG = premisesTableConfig(t, [], [], {
  premiseNo: () => <span />,
  address: () => <span />,
  type: () => <span />,
  services: () => <span />,
  owner: () => <span />,
  // CR-089 `DEF-4740` — the *On the map* column joined the cells contract on
  // 2026-09-10; this file stubs every cell and asserts on the services one.
  onTheMap: () => <span />,
  status: () => <span />,
  actions: () => <span />,
});

function renderList(rows: PremisesDetail[]): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(), CONFIG);
  const list = page(rows);
  queryClient.setQueryData(premisesQueryKey(serializeTableParams(state, CONFIG).toString()), list);
  queryClient.setQueryData(premisesRollupQueryKey, list);
  queryClient.setQueryData(premisesTypesQueryKey, TYPES);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises`]}>
          <PremisesTabsPage tab={PREMISES_TAB_PREMISES} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderDetail(detail: PremisesDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(premisesDetailQueryKey(detail.id), detail);
  queryClient.setQueryData(premisesAssetsQueryKey(detail.id), {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/${detail.id}`]}>
          <Routes>
            <Route path="/:tenant/premises/:premisesId" element={<PremisesDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

interface Sent {
  method: string;
  body: Record<string, unknown> | null;
}

function recordingClient(sent: Sent[], row: PremisesRow) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      const method = init?.method ?? "GET";
      if (method !== "GET") {
        sent.push({
          method,
          body:
            init?.body === undefined || init?.body === null
              ? null
              : (JSON.parse(String(init.body)) as Record<string, unknown>),
        });
      }
      return new Response(JSON.stringify(row), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
}

function mountEdit(sent: Sent[], row: PremisesRow) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(queryKeys.tenantServices, tenantServices());
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises`]}>
          <PremisesEditModal
            row={row}
            types={TYPES}
            client={recordingClient(sent, row)}
            onClose={() => undefined}
            onSaved={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);


/**
 * **THE FIELD'S VISIBLE NAME (`DEF-MET-4803`, the sibling of `DEF-MET-4760`).**
 *
 * `Services available` left the English catalogue on 2026-09-09 when the field
 * was reworded to the PO's own term — *"Services available = Utility services =
 * drop down - multi select"* (2026-09-08). `PremisesServices.dom.test.tsx` was
 * repaired that morning and **this sibling file was missed**, which is the
 * whole lesson: one stale literal per file is four places to miss, so it is a
 * constant anchored to the catalogue in both files now.
 */
const SERVICES_LABEL = "Utility services";

describe("DEF-MET-4803 — the label this file asks for is the label the product draws", () => {
  it("the catalogue still calls the field what this case asks for", () => {
    expect((EN as Record<string, string>)["metering.premises.col.services"]).toBe(SERVICES_LABEL);
  });
});

describe("DEF-762 — the S14 list tells the two states apart", () => {
  it("prints 'Not recorded' for an address nobody has been asked about", () => {
    const html = renderList([premise({ services_available: null })]);
    expect(html).toContain("Not recorded");
    // …and NOT the sentence that used to stand in for it. This is the assertion
    // the defect was: both rows said "No services" and a clerk could not act.
    expect(html).not.toContain("No services");
  });

  it("still prints 'No services' for an address a clerk answered with none", () => {
    const html = renderList([premise({ services_available: [] })]);
    expect(html).toContain("No services");
    expect(html).not.toContain("Not recorded");
  });

  it("draws the two rows DIFFERENTLY in one table — the whole point", () => {
    const html = renderList([
      premise({ id: "p-1", premise_no: "P-1", services_available: null }),
      premise({ id: "p-2", premise_no: "P-2", services_available: [] }),
      premise({ id: "p-3", premise_no: "P-3", services_available: ["electric"] }),
    ]);
    expect(html).toContain("Not recorded");
    expect(html).toContain("No services");
    // The ordinary row is untouched by any of this.
    expect(html).toContain("Electric");
  });
});

describe("DEF-762 — the PRM-02 detail tells them apart too", () => {
  it("prints 'Not recorded' where the column was never written", () => {
    const html = renderDetail(premise({ services_available: null }));
    expect(html).toContain("Not recorded");
    expect(html).not.toContain("No services");
  });

  it("prints 'No services' where the answer was none", () => {
    const html = renderDetail(premise({ services_available: [] }));
    expect(html).toContain("No services");
    expect(html).not.toContain("Not recorded");
  });
});

describe("DEF-762 — the edit modal says which state it opened in", () => {
  it("an unasked address opens saying so, not as an empty answer", async () => {
    mountEdit([], premise({ services_available: null }));
    expect(
      await screen.findByText(/nobody has been asked/i),
    ).toBeInTheDocument();
  });

  it("⚠ AND STILL DOES NOT BACKFILL: untouched, it sends no services field", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountEdit(sent, premise({ services_available: null }));
    await user.type(screen.getByLabelText(/Address/i), " Unit 2");
    await user.click(screen.getByRole("button", { name: "Save premise" }));
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].method).toBe("PATCH");
    expect(sent[0].body).not.toHaveProperty("services_available");
  });

  it("and an answer given on an unasked address IS sent", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountEdit(sent, premise({ services_available: null }));
    await user.selectOptions(screen.getByRole("combobox", { name: SERVICES_LABEL }), "water");
    await user.click(screen.getByRole("button", { name: "Save premise" }));
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body?.services_available).toEqual(["water"]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-762 (12-governance/10-defect-log.csv) + CR-036 (h) scope row 5,
//         12-governance/11-change-requests.md (verbatim) + BR-MET-003
// screens: S14 (A1) · PRM-01 / PRM-02 (r10)
// generated: 2026-08-26 by lane DEFSWEEP
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
