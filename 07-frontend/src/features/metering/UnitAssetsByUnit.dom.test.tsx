// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-8362 — on a premises holding more than 200 assets, a unit's
//          Assets tab drew '—' for service, size and status: the tab asked for
//          the PREMISES' registry at `per=200` and filtered it in the browser,
//          so any unit whose assets sorted past row 200 found no registry row.
// Screens: PRM-03 Assets tab (S15 unit detail)
// Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps)
// Journey: 08-qa/01-e2e/journeys/J71-asset-upload-carts-and-fire-lines-to-the-bill.md
// Evidence: 08-qa/screens/asset-upload-2026-09-30/1280-DEF-MET-8362-unit-B-assets-tab-dashes.png
// ───────────────────────────────────────────────────────
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — CLAUDE.md hard-won law 7(2).**
//
//   · A stub that answers every `/assets` request with the unit's rows would
//     pass the old code too: it asked for the premises and the stub gave it
//     the unit anyway. So this stub answers the way the SERVER answers — a
//     premises request gets the premises' first 200 rows, none of which is
//     on Unit B, and only a request carrying `f.unit_id=<Unit B>` gets Unit
//     B's rows. The old code draws dashes against it; the fix draws values.
//   · A mount outside the real route could not tell a working link from a
//     broken one (law 2's fixture clause), so the tab is mounted under
//     `/:tenant/premises/units/:unitId`, the pattern `App.tsx` mounts it at.
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
const UNIT_B = "u-00003";
const PREMISES = "p-1408";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const SIZE_CLASSES = [
  { code: "T-96", name: "Trash 96 gal" },
  { code: "F-2", name: 'Fire 2"' },
];

function unitB(meters: UnitRow["meters"]): UnitRow {
  return {
    id: UNIT_B,
    unit_no: "U-00003",
    premises_id: PREMISES,
    premise_no: "P-01408",
    premise_address: "1408 Elm St",
    label: "Unit B",
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
    services: ["trash", "fire"],
    meters,
    occupancy: "occupied",
    occupant: "Miller, Sarah",
    account_no: "A-00412",
    status: "active",
    metered_services: [],
    sub_metered: false,
  };
}

function row(overrides: Partial<AssetRow>): AssetRow {
  return {
    id: "a-0",
    asset_no: "AST-00000",
    serial_no: null,
    type: "cart",
    type_name: "Cart",
    tab: "behind_the_meter",
    status: "active",
    status_name: "Installed",
    behavior_class: "in_service",
    meter_type: null,
    meter_type_name: null,
    read_method: null,
    read_method_name: null,
    multiplier: "1",
    size_class: "T-96",
    size_class_name: null,
    unit: null,
    net_metering: false,
    manufacturer: null,
    model: null,
    install_date: "2026-09-30",
    parent_asset_no: null,
    service_point_id: "sp-1",
    assigned_unit_id: UNIT_B,
    assigned_from: "2026-09-30",
    assigned_to: "Unit B",
    assigned_address: "1408 Elm St",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit"],
    service: "trash",
    last_read: null,
    ...overrides,
  } as AssetRow;
}

/** Unit B's two, where the walk found them: AFTER row 200 of the premises. */
const UNIT_B_ROWS = [
  row({ id: "a-756", asset_no: "AST-00756" }),
  row({ id: "a-758", asset_no: "FS-00758", type: "fire_line", type_name: "Fire line", service: "fire", size_class: "F-2" }),
];

/** The premises' first 200 — every one on Bulk 1, none on Unit B. */
const PREMISES_PAGE = Array.from({ length: 200 }, (_, i) =>
  row({ id: `bulk-${i}`, asset_no: `AST-${String(i).padStart(5, "0")}`, assigned_unit_id: "u-bulk-1" }),
);

function mount(requests: URL[]) {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const raw = String(typeof input === "string" ? input : (input as Request).url ?? input);
      const url = new URL(raw, "http://test.local");
      requests.push(url);
      let body: unknown;
      if (url.pathname.includes("/lookups/service_size_classes")) {
        body = { count: SIZE_CLASSES.length, next: null, previous: null, results: SIZE_CLASSES };
      } else if (url.searchParams.get("f.unit_id") === UNIT_B) {
        body = { count: UNIT_B_ROWS.length, next: null, previous: null, results: UNIT_B_ROWS };
      } else if (url.searchParams.get("f.premises_id") === PREMISES) {
        body = { count: 1000, next: "page=2", previous: null, results: PREMISES_PAGE };
      } else {
        body = { count: 0, next: null, previous: null, results: [] };
      }
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
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/${UNIT_B}?tab=assets`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <UnitAssetsTab
                  unit={unitB([
                    { id: "a-756", asset_no: "AST-00756", qualifier: null, tab: "behind_the_meter" },
                    { id: "a-758", asset_no: "FS-00758", qualifier: null, tab: "behind_the_meter" },
                  ])}
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

function rowFor(assetNo: string): HTMLTableRowElement {
  const tr = screen.getByText(assetNo).closest("tr");
  if (tr === null) throw new Error(`no row for ${assetNo}`);
  return tr as HTMLTableRowElement;
}

afterEach(cleanup);

describe("DEF-MET-8362 — the unit's Assets tab asks the server for THIS unit's assets", () => {
  it("requests the registry by unit, never by premises", async () => {
    const requests: URL[] = [];
    mount(requests);
    await waitFor(() => expect(screen.getByText("AST-00756")).toBeInTheDocument());
    const registry = requests.filter(
      (url) => url.pathname.endsWith("/assets") && !url.searchParams.has("terms"),
    );
    expect(registry.length).toBeGreaterThan(0);
    for (const url of registry.filter((u) => u.searchParams.get("f.assigned") !== "false")) {
      expect(url.searchParams.get("f.unit_id")).toBe(UNIT_B);
      expect(url.searchParams.has("f.premises_id")).toBe(false);
      // A server page, never the old fixed 200 (NFR-3 / NFR-5).
      expect(url.searchParams.get("per")).not.toBe("200");
    }
  });

  it("draws service, size and status for a unit whose assets sort past row 200 of its premises", async () => {
    mount([]);
    const cart = await waitFor(() => rowFor("AST-00756"));
    await waitFor(() => expect(within(cart).getByText("Trash 96 gal")).toBeInTheDocument());
    expect(within(cart).getByText(t("rating.service.trash"))).toBeInTheDocument();
    expect(within(cart).getByText("Installed")).toBeInTheDocument();
    const line = rowFor("FS-00758");
    expect(within(line).getByText('Fire 2"')).toBeInTheDocument();
    expect(within(line).getByText(t("rating.service.fire"))).toBeInTheDocument();
  });
});
