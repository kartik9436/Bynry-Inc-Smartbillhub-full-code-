// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9267 — New Connection step 3 pre-selected the FIRST size
//           of every sized service and pinned it into the draft, so every
//           storm-water unit silently took "Apartment building" (6 ERU), and
//           every cart, fire line, tonnage and meter took whatever sorted first.
// Ruling:   coordinator, hard-won law 3 (defaults fail closed): no default —
//           the size box starts empty and Continue names the missing size.
// ⚠ NOT TOUCHED: how a storm-water size is priced or split across units (a
//           pending PO question). This asserts only what a row carries when
//           the clerk picks nothing.
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as renderDom } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import type { TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { commitPlanOf, draftUnits, emptyDraft, unitServiceKey } from "./newConnectDraft";
import type { NewConnectDraft, UnitServiceCell } from "./newConnectDraft";
import type { DraftUnit } from "./newConnectShared";
import { UnitsStep, equipmentCounts, rowsMissingSize } from "./NewConnectUnitsStep";

const TENANT = "brazosbend";
const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

const ASSET_TYPES = [
  { code: "meter", name: "Meter", category: "meters" },
  { code: "container_cart", name: "Cart", category: "behind_the_meter" },
  { code: "fire_line", name: "Fire line", category: "behind_the_meter" },
];

/** In NAME order, as `service_size_classes` serves them — so *Apartment
 *  building* (6 ERU) is the first storm-water row, exactly as on the walk. */
const SIZES = [
  { code: "SW-APT", name: "Apartment building", service: { code: "storm_water" } },
  { code: "SW-SF", name: "Single-family home", service: { code: "storm_water" } },
  { code: "CART-64", name: "Cart 64 gal", service: { code: "trash" } },
  { code: "CART-96", name: "Cart 96 gal", service: { code: "trash" } },
  { code: "FL-2", name: 'Fire line 2"', service: { code: "fire" } },
  { code: "FL-6", name: 'Fire line 6"', service: { code: "fire" } },
  { code: "TH-T10", name: "10 tons", service: { code: "thermal_heat" } },
  { code: "TH-T25", name: "25 tons", service: { code: "thermal_heat" } },
  { code: "W-1", name: 'Water 1"', service: { code: "water" } },
];

const SERVICES = ["water", "trash", "storm_water", "thermal_heat", "fire"];
const UNITS: DraftUnit[] = [
  { label: "1", isCommonArea: false },
  { label: "2", isCommonArea: false },
];

function draftOf(grid: Record<string, UnitServiceCell> = {}): NewConnectDraft {
  return {
    ...emptyDraft(),
    premiseServices: SERVICES,
    pattern: { prefix: "", from: "1", to: "2", includeCommonArea: false },
    unitServiceGrid: grid,
  };
}

function tenantServices(enabled: readonly string[]): TenantServiceRow[] {
  return enabled.map((service) => ({
    service,
    name: service,
    enabled: true,
    primary_uom: null,
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  }));
}

function mount(draft: NewConnectDraft, onPatch: (next: Partial<NewConnectDraft>) => void) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.tenantServices, tenantServices(SERVICES));
  queryClient.setQueryData(["lookups", "asset_types", "new-connect"], {
    count: ASSET_TYPES.length,
    results: ASSET_TYPES,
  });
  queryClient.setQueryData(["lookups", "service_size_classes", "new-connect"], {
    count: SIZES.length,
    results: SIZES,
  });
  queryClient.setQueryData(["connection-wizard-templates"], { count: 0, results: [] });
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  renderDom(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/connections/new?step=3`]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={
                <UnitsStep
                  draft={draft}
                  units={UNITS}
                  labelsAlreadyHere={[]}
                  breaches={[]}
                  sewerGaps={[]}
                  proposed={[]}
                  proposalsUnavailable={false}
                  onPatch={onPatch}
                  client={client}
                  t={t}
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("DEF-CUS-9267 — no size is assumed on step 3", () => {
  it("draws every size box EMPTY when the clerk has picked none", () => {
    mount(draftOf(), () => undefined);
    const sizes = [
      ...document.querySelectorAll('[data-array="units-and-service-points"] select[data-cell="size"]'),
    ] as HTMLSelectElement[];
    // Five services × the open group's rows; every one of them blank.
    expect(sizes.length).toBeGreaterThan(0);
    expect(sizes.map((one) => one.value).filter((value) => value !== "")).toEqual([]);
  });

  it("writes NO size into the draft on its own — storm water is not 6 ERU by default", () => {
    const patches: Partial<NewConnectDraft>[] = [];
    mount(draftOf(), (next) => patches.push(next));
    const written = patches.flatMap((patch) =>
      Object.entries(patch.unitServiceGrid ?? {}).filter(([, cell]) => cell.sizeClass !== undefined),
    );
    expect(written).toEqual([]);
    // The DEVICE is still pinned — a cart shown is a cart sent (DEF-MET-6119).
    const grid = Object.assign({}, ...patches.map((patch) => patch.unitServiceGrid ?? {}));
    expect(grid[unitServiceKey("1", "trash")]?.assetType).toBe("container_cart");
    expect(grid[unitServiceKey("1", "fire")]?.assetType).toBe("fire_line");
  });

  it("names every row still missing a size, and none once each is picked", () => {
    const blank = draftOf();
    const missing = rowsMissingSize(blank, draftUnits(blank), SIZES, ASSET_TYPES).map(
      (row) => `${row.unit.label}|${row.service}`,
    );
    expect(missing).toEqual([
      "1|water",
      "1|trash",
      "1|storm_water",
      "1|thermal_heat",
      "1|fire",
      "2|water",
      "2|trash",
      "2|storm_water",
      "2|thermal_heat",
      "2|fire",
    ]);

    const picked: Record<string, UnitServiceCell> = {};
    for (const unit of ["1", "2"]) {
      picked[unitServiceKey(unit, "water")] = { taken: true, sizeClass: "W-1" };
      picked[unitServiceKey(unit, "trash")] = { taken: true, assetType: "container_cart", sizeClass: "CART-96" };
      picked[unitServiceKey(unit, "storm_water")] = { taken: true, sizeClass: "SW-SF" };
      picked[unitServiceKey(unit, "thermal_heat")] = { taken: true, sizeClass: "TH-T10" };
      picked[unitServiceKey(unit, "fire")] = { taken: true, assetType: "fire_line", sizeClass: "FL-6" };
    }
    const full = draftOf(picked);
    expect(rowsMissingSize(full, draftUnits(full), SIZES, ASSET_TYPES)).toEqual([]);
  });

  it("a further fire line with no size is missing too; a cart set to None needs none", () => {
    const draft = draftOf({
      [unitServiceKey("1", "fire")]: { taken: true, assetType: "fire_line", sizeClass: "FL-6", more: [""] },
      [unitServiceKey("1", "trash")]: { taken: true, assetType: "" },
    });
    const missing = rowsMissingSize(draft, draftUnits(draft), SIZES, ASSET_TYPES).map(
      (row) => `${row.unit.label}|${row.service}`,
    );
    expect(missing).toContain("1|fire");
    expect(missing).not.toContain("1|trash");
  });

  it("step 5 still counts and sends exactly what the clerk picked", () => {
    const grid: Record<string, UnitServiceCell> = {
      [unitServiceKey("1", "storm_water")]: { taken: true, sizeClass: "SW-SF" },
      [unitServiceKey("2", "storm_water")]: { taken: true, sizeClass: "SW-APT" },
      [unitServiceKey("1", "fire")]: { taken: true, assetType: "fire_line", sizeClass: "FL-6", more: ["FL-2"] },
      [unitServiceKey("1", "water")]: { taken: true, sizeClass: "W-1" },
      [unitServiceKey("2", "water")]: { taken: true, sizeClass: "W-1" },
    };
    const draft = { ...draftOf(grid), premiseServices: ["water", "storm_water"] };
    const plan = commitPlanOf(draft, null, []);
    const sized = Object.fromEntries(
      plan.unit_services
        .filter((row) => row.service === "storm_water")
        .map((row) => [row.unit_label, row.size_class]),
    );
    expect(sized).toEqual({ "1": "SW-SF", "2": "SW-APT" });
    expect(plan.unit_services.find((row) => row.service === "fire")?.equipment).toEqual([
      { type: "fire_line", size_class: "FL-6", count: 1 },
      { type: "fire_line", size_class: "FL-2", count: 1 },
    ]);
    expect(plan.meters.map((row) => row.size_class)).toEqual(["W-1", "W-1"]);
    const counted = equipmentCounts(draft, draftUnits(draft), ASSET_TYPES);
    expect(counted.meters).toBe(plan.meters.length);
  });
});
