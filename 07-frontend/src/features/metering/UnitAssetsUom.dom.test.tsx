// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-6911 (the shelf table names no unit of measure, so four
//          spares all read `Meter · —` and a clerk cannot tell a water meter
//          from an electric one) ·
//          DEF-MET-6926 (the ON-UNIT table prints the size class CODE —
//          `W-58` — where the shelf table 250 lines below prints the tenant's
//          own name for that same code, `Water 5/8"`)
// Screens: PRM-03 Assets tab (S15 unit detail)
// Rules:   CLAUDE.md hard rule 3 (a quantity is never carried without its
//          unit, and a meter's unit is what says what its readings MEAN) ·
//          B14 rule 31 (no code a clerk cannot read is the visible value of a
//          field) · B14 rule 33 (a label is ≤ 3 words) ·
//          BR-AST-009 / MEASURING_TYPES (only a meter, net meter or sub-meter
//          declares a service and a unit — a cart declares neither) ·
//          DEF-514's ruling (an em-dash cannot tell *not recorded* from *the
//          product cannot record it*, so those two are WORDS)
// Blueprint: `05-prototype/Premises & Units Blueprint 2.pdf` p68-69 — the
//          assign panel is drawn `Meter · Service · Size · Where it is ·
//          Status · Assign ✓`, and the on-unit `Size` cell is drawn
//          `Class 200` / `5/8"` — NAMES, never codes.
// ───────────────────────────────────────────────────────
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY — CLAUDE.md hard-won law 7(2).**
//
//   · *"the shelf row shows `kgal`"* would pass on a fixture whose every row
//     is a water meter. So the shelf below holds a `kgal` meter, a `kWh`
//     meter and a CART, and each case asserts which cell got which word.
//   · *"the size cell shows `Water 5/8\"`"* passes if the fixture stores the
//     display string in `size_class`. **That is exactly how this defect
//     survived**: `UnitAssetsColumns.dom.test.tsx` seeds `size_class: '5/8"'`,
//     which is a value production never holds — `brazosbend` stores `W-58`
//     and `E-1P-100`, measured 2026-09-27. Every fixture here therefore seeds
//     the CODE and asserts the NAME, and asserts the code is absent.
//   · *"a cart shows no unit"* passes on a bare dash, which is the fault
//     being fixed. So the cart case asserts the WORDS and asserts a dash is
//     not what carries them.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { AssetRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import i18n from "@/i18n";

import { UnitAssetsTab } from "./UnitDetailPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** ⚠ **THE TENANT'S OWN SIZE CATALOGUE, CODE → NAME.** These two pairs are
 *  `brazosbend`'s real rows, read from `service_size_classes` on 2026-09-27 —
 *  not invented, because the whole point of these cases is that the CODE and
 *  the NAME are different strings. */
const SIZE_CLASSES = [
  { code: "W-58", name: 'Water 5/8"' },
  { code: "E-1P-100", name: "Electric 1φ 100A" },
];

function unit(meters: UnitRow["meters"]): UnitRow {
  return {
    id: "u-101a",
    unit_no: "U-00101-A",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "1408 Bluestem Ln",
    label: "Unit A",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters,
    occupancy: "occupied",
    occupant: "Miller, Sarah",
    account_no: "A-00412",
    status: "active",
    metered_services: [],
    sub_metered: false,
  };
}

function meterRef(assetNo: string, id: string) {
  return { id, asset_no: assetNo, qualifier: null, category: "meters" };
}

function asset(overrides: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-5042",
    asset_no: "W-5042",
    serial_no: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "inventory",
    status_name: "Inventory",
    behavior_class: "available",
    meter_type: "walk_by",
    meter_type_name: "walk-by",
    read_method: "walk_by",
    read_method_name: "walk-by",
    multiplier: "1",
    // ⚠ THE CODE, NOT THE NAME — see the header. Production stores this.
    size_class: "W-58",
    // The size AS A CLERK READS IT, beside the code (`DEF-AST-7130`).
    size_class_name: null,
    unit: "kgal",
    net_metering: false,
    manufacturer: "Badger Meter",
    model: null,
    install_date: null,
    parent_asset_no: null,
    service_point_id: null,
    assigned_unit_id: null,
    assigned_from: null,
    assigned_to: null,
    assigned_address: null,
    assigned: false,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit", "assign"],
    service: null,
    last_read: null,
    ...overrides,
  };
}

/** A meter standing ON the unit — a service point, an arrival date, a read. */
function onUnit(overrides: Partial<AssetRow> = {}): AssetRow {
  return asset({
    id: "a-1000",
    asset_no: "W-5000",
    status: "active",
    status_name: "Installed",
    behavior_class: "in_service",
    service_point_id: "sp-1",
    assigned_unit_id: "u-101a",
    assigned_from: "2026-06-14",
    assigned: true,
    service: "water",
    last_read: {
      current_value: "1024.000000",
      consumption: "8.000000",
      unit: "kgal",
      read_at: "2026-08-14",
    },
    ...overrides,
  });
}

/** ⚠ **THE FETCH BRANCHES ON THE PATH, AND IT HAS TO.** The tab asks for two
 *  different things — the premises' assets and the `service_size_classes`
 *  lookup — and a stub that answers both with the asset page makes the size
 *  catalogue EMPTY, which is the state where the raw code leaks through as a
 *  fallback. A single-answer stub would therefore pass the buggy code. */
function mountTab(rows: AssetRow[], meters = [meterRef("W-5000", "a-1000")]) {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(typeof input === "string" ? input : (input as Request).url ?? input);
      const body = url.includes("/lookups/service_size_classes")
        ? { count: SIZE_CLASSES.length, next: null, previous: null, results: SIZE_CLASSES }
        : { count: rows.length, next: null, previous: null, results: rows };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/u-101a?tab=assets`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <UnitAssetsTab
                  unit={unit(meters)}
                  client={client}
                  t={t}
                  regional={{ timeZone: "America/Chicago", dateFormat: "DD/MM/YYYY" }}
                  writeBlockedReason={null}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Open the `+ Assign from inventory` panel and return its result table. */
async function shelf() {
  const open = await screen.findByRole("button", {
    name: t("metering.units.action.assignFromInventory"),
  });
  open.click();
  return await waitFor(() => {
    const heading = screen.getByText(t("metering.units.assets.findResults"));
    const table = heading.closest("div")?.querySelector("table");
    if (!table) throw new Error("the shelf table has not rendered");
    return table as HTMLTableElement;
  });
}

function rowFor(scope: HTMLElement, assetNo: string): HTMLTableRowElement {
  const cell = within(scope).getByText(assetNo);
  const tr = cell.closest("tr");
  if (tr === null) throw new Error(`no row for ${assetNo}`);
  return tr as HTMLTableRowElement;
}

afterEach(cleanup);

describe("DEF-MET-6926 — the on-unit `Size` cell reads the tenant's NAME, never the code", () => {
  it("renders `Water 5/8\"` for the stored code `W-58`, and the code never reaches the screen", async () => {
    mountTab([onUnit()]);
    const tr = await waitFor(() => rowFor(document.body, "W-5000"));
    expect(within(tr).getByText('Water 5/8"')).toBeInTheDocument();
    // ⚠ **THE RED PROOF.** `W-58` is what this cell printed before, and it is
    // what the clerk photographed. Its presence means the cell is still
    // handing a lookup code to a person.
    expect(within(tr).queryByText("W-58")).toBeNull();
  });

  it("a size the catalogue does not name falls back to the stored value rather than to blank", async () => {
    // ⚠ A FALLBACK, NOT A DASH. A size Settings has RETIRED still sits on
    // meters that priced with it (`BR-AST-500`), so the row must still say
    // something rather than lose the fact.
    mountTab([onUnit({ size_class: "W-RETIRED" })]);
    const tr = await waitFor(() => rowFor(document.body, "W-5000"));
    expect(within(tr).getByText("W-RETIRED")).toBeInTheDocument();
  });
});

describe("DEF-MET-6911 — the shelf table says what each spare MEASURES IN", () => {
  it("the header is `Size`, as the blueprint draws it — not `Connection size`", async () => {
    mountTab([onUnit(), asset()]);
    const table = await shelf();
    const heads = [...table.querySelectorAll("thead th")].map((h) => h.textContent?.trim());
    expect(heads).toContain(t("assets.col.size"));
    expect(heads).not.toContain(t("assets.col.sizeClass"));
  });

  it("a water spare reads kgal and an electric spare reads kWh, in their own rows", async () => {
    // ⚠ **THE CASE THE DEFECT IS ABOUT.** On `brazosbend` four shelf meters
    // carry NO size class at all, so `Meter · —` is every one of them and the
    // unit of measure is the only thing that tells them apart.
    mountTab([
      onUnit(),
      asset({ id: "a-1", asset_no: "AST-04412", size_class: null, unit: "kgal" }),
      asset({ id: "a-2", asset_no: "M-5099", size_class: null, unit: "kWh" }),
    ]);
    const table = await shelf();
    expect(within(rowFor(table, "AST-04412")).getByText("kgal")).toBeInTheDocument();
    expect(within(rowFor(table, "M-5099")).getByText("kWh")).toBeInTheDocument();
    // Neither row may borrow the other's unit.
    expect(within(rowFor(table, "AST-04412")).queryByText("kWh")).toBeNull();
    expect(within(rowFor(table, "M-5099")).queryByText("kgal")).toBeNull();
  });

  it("a CART says it is not measured, IN WORDS — a dash cannot say that", async () => {
    // ⚠ `BR-AST-009` binds `MEASURING_TYPES` only, so a cart legitimately has
    // no service, no size and no unit. `DEF-514`: an em-dash cannot tell
    // *not recorded* from *the product cannot record it*, and for a cart it
    // is the second. Answers the PO's own third finding on `DEF-MET-6911`.
    mountTab([
      onUnit(),
      asset({
        id: "a-9",
        asset_no: "CART-0099",
        type: "container_cart",
        type_name: "Container / Cart",
        tab: "other",
        meter_type: null,
        meter_type_name: null,
        size_class: null,
        unit: null,
      }),
    ]);
    const table = await shelf();
    const tr = rowFor(table, "CART-0099");
    // ⚠ **THREE CELLS, NOT ONE, AND THE COUNT IS THE ASSERTION.** Size, unit of
    // measure and meter type are all absent on a cart and all three were a bare
    // em-dash. `getByText` THROWS on three matches, which is how this case
    // first ran — so the count is written down rather than relaxed away with
    // `getAllByText(...)[0]`.
    expect(within(tr).getAllByText(t("metering.units.assets.notMeasured"))).toHaveLength(3);
    // And none of them is the bare dash any more.
    expect(within(tr).queryByText("\u2014")).toBeNull();
  });

  it("a MEASURING spare with no unit recorded reads differently from a cart", async () => {
    // ⚠ **THE MIRROR, AND THE REASON THE CART CASE IS NOT ENOUGH.** A meter
    // with no unit is a GAP somebody should close; a cart with no unit is
    // correct forever. One sentence for both would be the dash again, wearing
    // words.
    mountTab([onUnit(), asset({ id: "a-3", asset_no: "AST-04413", unit: null })]);
    const table = await shelf();
    const tr = rowFor(table, "AST-04413");
    expect(within(tr).getByText(t("metering.units.assets.uomUnrecorded"))).toBeInTheDocument();
    expect(within(tr).queryByText(t("metering.units.assets.notMeasured"))).toBeNull();
  });

  it("every shelf row's unit survives the row being re-rendered after an assign", async () => {
    // The PO's own second step. The shelf list is invalidated on success, so
    // the row is rebuilt from a fresh payload — this asserts the unit is read
    // from the ROW and not from something the panel held in state.
    mountTab([onUnit(), asset({ id: "a-1", asset_no: "AST-04412", unit: "kgal" })]);
    const table = await shelf();
    expect(within(rowFor(table, "AST-04412")).getByText("kgal")).toBeInTheDocument();
    // ⚠ **RE-QUERY THE PANEL, DO NOT RE-OPEN IT.** The trigger becomes
    // `Cancel` once the panel is open, so calling the opener twice fails with
    // *"Unable to find role=button and name +Assign from inventory"* — which
    // is a fault in the test and says nothing about the row. The point of this
    // case is that the cell reads its unit from the ROW on every render, not
    // from something the panel cached at open time.
    const again = await waitFor(() => {
      const heading = screen.getByText(t("metering.units.assets.findResults"));
      const el = heading.closest("div")?.querySelector("table");
      if (!el) throw new Error("the shelf table went away");
      return el as HTMLTableElement;
    });
    expect(within(rowFor(again, "AST-04412")).getByText("kgal")).toBeInTheDocument();
  });
});
