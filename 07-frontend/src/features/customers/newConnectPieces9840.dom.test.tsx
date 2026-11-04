// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9840 — PO, 2026-10-06: "on step 3 unit - in unit and
//           service user added multiple solar pannel on one unit then service
//           order, completes, occupancy statsu showing dash".
// Ruling:   PO (a), 2026-10-06 — one work order per service, one asset per
//           panel tagged to the unit, the bill on the sum of installed kW
//           (decision log "EXTRA SOLAR PANELS ON ONE UNIT").
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
 *  * finding the text anywhere on the page — every assertion reads the cell
 *    of the PIECE row (`data-editable-nested`), never the service row's;
 *  * a sum typed per size in the component — the sizes here carry capacities
 *    the real ladder does not (`SOL-X7` = 7.5 kW), so only a sum read off the
 *    lookup's own `capacity` can produce *2 panels · 17.5 kW*;
 *  * a confirm that never fires — the ✕ on the service row asserts the draft is
 *    NOT patched until the dialog's button is pressed.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as renderDom, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import type { TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { ProposedWorkOrder } from "@/features/work/workEndpoints";

import { commitUnitServicesOf, draftUnitServices, emptyDraft, unitServiceKey } from "./newConnectDraft";
import type { NewConnectDraft, UnitServiceCell } from "./newConnectDraft";
import type { DraftUnit } from "./newConnectShared";
import { UnitsStep, piecesTotal, plannedAssets } from "./NewConnectUnitsStep";
import type { SizeRow } from "./NewConnectUnitsStep";
import { assetSizeSuffix } from "@/features/work/buildRecord/BuildUnitsTab";

const TENANT = "brazosbend";
const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

const ASSET_TYPES = [
  { code: "pv", name: "PV panel", category: "behind_the_meter" },
  { code: "container_cart", name: "Cart", category: "behind_the_meter" },
  { code: "fire_line", name: "Fire line", category: "behind_the_meter" },
];

const SIZES: SizeRow[] = [
  { code: "SOL-P1", name: "Solar panel 1 kW", service: { code: "solar" }, capacity: "1.0000", capacity_uom: "kW" },
  { code: "SOL-P10", name: "Solar panel 10 kW", service: { code: "solar" }, capacity: "10.0000", capacity_uom: "kW" },
  { code: "SOL-X7", name: "Solar panel 7.5 kW", service: { code: "solar" }, capacity: "7.5000", capacity_uom: "kW" },
  { code: "CART-64", name: "Cart 64 gal", service: { code: "trash" }, capacity: null, capacity_uom: null },
  { code: "CART-96", name: "Cart 96 gal", service: { code: "trash" }, capacity: null, capacity_uom: null },
  { code: "FL-2", name: 'Fire line 2"', service: { code: "fire" }, capacity: null, capacity_uom: null },
  { code: "FL-6", name: 'Fire line 6"', service: { code: "fire" }, capacity: null, capacity_uom: null },
];

const SERVICES = ["solar", "trash", "fire"];
const UNITS: DraftUnit[] = [{ label: "Unit 1", isCommonArea: false }];

const INSTALL: ProposedWorkOrder = {
  template_id: "tpl-solar",
  template_no: "WT-1",
  name: "Solar installation",
  service: { id: "s1", code: "solar", name: "Solar" },
  scope: "per_unit",
  sequence: 1,
  job_type: null,
  is_gate: true,
  version: 1,
  est_duration_minutes: null,
};

const KEY = unitServiceKey("Unit 1", "solar");
const SOLAR: UnitServiceCell = {
  taken: true,
  assetType: "pv",
  sizeClass: "SOL-P1",
  more: ["SOL-P10", "SOL-P10"],
  workOrderTemplateId: "tpl-solar",
};

function draftOf(grid: Record<string, UnitServiceCell>): NewConnectDraft {
  return {
    ...emptyDraft(),
    premiseServices: ["solar"],
    occupancy: "vacant_service_off",
    pattern: { prefix: "Unit ", from: "1", to: "1", includeCommonArea: false },
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
  queryClient.setQueryData(["lookups", "unit_types", "new-connect"], { count: 0, results: [] });
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
                  proposed={[INSTALL]}
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

function pieceRows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-editable-nested]")];
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("DEF-CUS-9840 — a unit's extra solar panels on step 3", () => {
  it("draws each extra panel as a sub-row named Panel 2, Panel 3 under its Solar row", () => {
    mount(draftOf({ [KEY]: SOLAR }), () => undefined);
    const rows = pieceRows();
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector('[data-piece-of="solar"]')?.textContent).toBe(
      "↳ Panel 2 · Solar panel 10 kW",
    );
    expect(rows[1].querySelector('[data-piece-of="solar"]')?.textContent).toBe(
      "↳ Panel 3 · Solar panel 10 kW",
    );
  });

  it("a panel's Work order, Completes and Occupancy show the Solar row's, greyed — never a dash", () => {
    mount(draftOf({ [KEY]: SOLAR }), () => undefined);
    // Two rows, or the loop below asserts nothing (it passed vacuously on the
    // shipped code, where no piece row was nested — found by the red run).
    expect(pieceRows()).toHaveLength(2);
    for (const row of pieceRows()) {
      const order = row.querySelector<HTMLSelectElement>('select[data-cell="work-order"]');
      expect(order?.value).toBe("tpl-solar");
      expect(order?.disabled).toBe(true);
      expect(order?.title).toBe("Same as Solar row");
      expect(row.querySelector('[data-same-as]')?.textContent).toBe("Same as Solar row");
      const completes = row.querySelector<HTMLInputElement>('input[data-cell="completes"]');
      expect(completes?.checked).toBe(true);
      expect(completes?.disabled).toBe(true);
      expect(completes?.title).toBe("Same as Solar row");
      const occupancy = row.querySelector<HTMLSelectElement>('select[data-cell="occupancy"]');
      expect(occupancy?.value).toBe("vacant_service_off");
      expect(occupancy?.disabled).toBe(true);
      // No cell of a piece row is the bare dash any more, except Kind/Unit's
      // own grouping, which a sub-row does not draw.
      for (const name of ["work-order", "completes", "occupancy"]) {
        expect(row.querySelector(`[data-cell="${name}"]`)?.textContent ?? "").not.toBe("—");
      }
    }
  });

  it("the Solar row stays the editable one", () => {
    mount(draftOf({ [KEY]: SOLAR }), () => undefined);
    const main = document.querySelector<HTMLElement>(`[data-pieces-summary="${KEY}"]`)?.closest("tr");
    expect(main).not.toBeNull();
    expect(main?.hasAttribute("data-editable-nested")).toBe(false);
    expect(main?.querySelector<HTMLSelectElement>('select[data-cell="work-order"]')?.disabled).toBe(false);
  });

  it("the Solar row reads 3 panels · 21 kW, summed from the size list's own capacity", () => {
    mount(draftOf({ [KEY]: SOLAR }), () => undefined);
    expect(document.querySelector(`[data-pieces-summary="${KEY}"]`)?.textContent).toBe("3 panels · 21 kW");
  });

  it("a size the code could not know sums from the data: 10 kW + 7.5 kW = 17.5 kW", () => {
    mount(draftOf({ [KEY]: { ...SOLAR, sizeClass: "SOL-P10", more: ["SOL-X7"] } }), () => undefined);
    expect(document.querySelector(`[data-pieces-summary="${KEY}"]`)?.textContent).toBe(
      "2 panels · 17.5 kW",
    );
  });

  it("carts and fire lines are COUNTED: 3 carts, 2 lines, with no sum", () => {
    const trash = unitServiceKey("Unit 1", "trash");
    const fire = unitServiceKey("Unit 1", "fire");
    mount(
      draftOf({
        [KEY]: { taken: false },
        [trash]: { taken: true, assetType: "container_cart", sizeClass: "CART-96", more: ["CART-96", "CART-64"] },
        [fire]: { taken: true, assetType: "fire_line", sizeClass: "FL-6", more: ["FL-2"] },
      }),
      () => undefined,
    );
    expect(document.querySelector(`[data-pieces-summary="${trash}"]`)?.textContent).toBe("3 carts");
    expect(document.querySelector(`[data-pieces-summary="${fire}"]`)?.textContent).toBe("2 lines");
    expect(pieceRows().map((row) => row.querySelector("[data-piece-of]")?.textContent)).toEqual([
      "↳ Cart 2 · Cart 96 gal",
      "↳ Cart 3 · Cart 64 gal",
      "↳ Line 2 · Fire line 2\"",
    ]);
  });

  it("✕ on a panel removes that panel only", () => {
    const onPatch = vi.fn();
    mount(draftOf({ [KEY]: SOLAR }), onPatch);
    const remove = pieceRows()[0].querySelector<HTMLButtonElement>("button[aria-label^='Remove row']");
    expect(remove).not.toBeNull();
    fireEvent.click(remove as HTMLButtonElement);
    expect(onPatch).toHaveBeenCalledTimes(1);
    const grid = onPatch.mock.calls[0][0].unitServiceGrid as Record<string, UnitServiceCell>;
    expect(grid[KEY].taken).toBe(true);
    expect(grid[KEY].more).toEqual(["SOL-P10"]);
  });

  it("✕ on the Solar row asks first, then removes it with every panel", () => {
    const onPatch = vi.fn();
    mount(draftOf({ [KEY]: SOLAR }), onPatch);
    const main = document.querySelector<HTMLElement>(`[data-pieces-summary="${KEY}"]`)?.closest("tr");
    fireEvent.click(main?.querySelector("button[aria-label^='Remove row']") as HTMLButtonElement);
    expect(onPatch).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog").textContent).toContain("Remove Solar from Unit 1?");
    expect(screen.getByRole("alertdialog").textContent).toContain("Removes 3 panels · 21 kW too.");
    fireEvent.click(screen.getByRole("button", { name: /Remove all/ }));
    const grid = onPatch.mock.calls[0][0].unitServiceGrid as Record<string, UnitServiceCell>;
    expect(grid[KEY].taken).toBe(false);
    expect(grid[KEY].more).toEqual([]);
  });
});

describe("DEF-CUS-9840 — the sums and the assets Create makes", () => {
  it("sums only when every piece's size has a capacity in one unit", () => {
    expect(piecesTotal(SOLAR, SIZES)).toEqual({ count: 3, total: "21", uom: "kW" });
    expect(piecesTotal({ ...SOLAR, more: ["SOL-P10", ""] }, SIZES).total).toBeNull();
    expect(piecesTotal({ sizeClass: "CART-96", more: ["CART-64"] }, SIZES)).toEqual({
      count: 2,
      total: null,
      uom: null,
    });
  });

  it("Review lists one asset per panel, off the commit's own payload", () => {
    const draft = draftOf({ [KEY]: SOLAR });
    const planned = plannedAssets(commitUnitServicesOf(draft, UNITS, draftUnitServices(draft)));
    expect(planned).toEqual([
      { unit: "Unit 1", service: "solar", type: "pv", size: "SOL-P1" },
      { unit: "Unit 1", service: "solar", type: "pv", size: "SOL-P10" },
      { unit: "Unit 1", service: "solar", type: "pv", size: "SOL-P10" },
    ]);
  });
});

describe("DEF-CUS-9840 — the build record names each panel's size beside its number", () => {
  const asset = (no: string, size: string) => ({
    id: no,
    asset_no: no,
    type: "pv",
    type_name: "PV panel",
    size_class: size,
    status: "active",
    status_name: "Installed",
    install_date: "2026-10-06",
  });
  const names = new Map(SIZES.map((row) => [row.code, row.name]));

  it("several pieces: each number carries its size; one piece: the Size column says it", () => {
    const three = [asset("A-1", "SOL-P1"), asset("A-2", "SOL-P10"), asset("A-3", "SOL-P10")];
    expect(three.map((one) => `${one.asset_no}${assetSizeSuffix(three, one, names)}`)).toEqual([
      "A-1 · Solar panel 1 kW",
      "A-2 · Solar panel 10 kW",
      "A-3 · Solar panel 10 kW",
    ]);
    expect(assetSizeSuffix([three[0]], three[0], names)).toBe("");
  });
});
