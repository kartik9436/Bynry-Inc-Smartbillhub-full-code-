// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-001 (S49 registry) · US-AST-002 (S51 add) · US-AST-003 (edit + delete
//           guard) · US-AST-009 (bulk assign from the list) · US-AST-010 (S52 import) ·
//           US-SHL-020 (the one page header — this screen's conversion)
//           Screens: S49 (S15 in A1's platform-shell numbering), S51, S52
// Rules:    BR-AST-004 (tab partition) · BR-AST-005 (status filter semantics) ·
//           BR-AST-006 (row actions are the SERVER's set) · BR-AST-007 (Test due derived) ·
//           BR-AST-010 (net metering locked/unavailable) · BR-AST-013 (delete gate) ·
//           BR-AST-023/034 (staged import, always-shown summary) · BR-AST-026 (three
//           identifiers) · BR-AST-033 (duplicate # blocks, duplicate serial warns) ·
//           BR-AST-036/038 (bulk assign inventory→unit only) · BR-AST-041 (capability row) ·
//           BR-AST-044 (BOTH classifications; meter_type REFUSED on non-measuring types) ·
//           BR-SHL-011 · BR-SHL-025 · BR-SHL-032 ·
//           BR-SHL-044 (a) per-tab primary action · (b) per-tab explainer, BELOW the strip
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient, formErrorEnvelope, isApiError } from "@/api/client";
import { METER_TYPE_UNCLASSIFIED, bulkAssignAssets, createAsset } from "@/api/endpoints";
import type { AssetRow, LookupEntry, MyPermissions, Paginated } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { envelopeErrors } from "@/components/FormModal";
import { defaultRequestState, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { PREMISES_PERMISSION } from "@/features/metering/meteringShared";
import { chipFilters } from "@/features/metering/UnitsListPage";

import {
  AssetRegistryPage,
  assetStatusesQueryKey,
  assetTypesQueryKey,
  assetsQueryKey,
  assetsTableConfig,
  meterTypeFilterOptions,
  meterTypesQueryKey,
  statusFilterOptions,
  tabFromParam,
  typesForTab,
} from "./AssetRegistryPage";
import { ASSET_TAB_IDS, hasAction, isMeasuringCategory, repairActionKey } from "./assetsShared";
import { AssetImportWorkflowPage, assetImportPath } from "./AssetImportWorkflow";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`. Tests state the tenant
// the browser would be showing, so both are visible here rather than implied.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function lookup(code: string, name: string, extra: Record<string, unknown> = {}): LookupEntry {
  return { id: `l-${code}`, code, name, active: true, is_system: true, used_by: 0, ...extra };
}

const TYPES: LookupEntry[] = [
  lookup("meter", "Meter", { category: "meters" }),
  lookup("net_meter", "Net meter", { category: "meters" }),
  lookup("sub_meter", "Sub-meter", { category: "sub_meters" }),
  lookup("battery", "Battery storage", { category: "behind_the_meter" }),
  lookup("backflow", "Backflow preventer", { category: "behind_the_meter" }),
];
const STAGES: LookupEntry[] = [
  lookup("inventory", "Inventory/Spare", { behavior_class: "available" }),
  lookup("active", "Installed/Active", { behavior_class: "in_service" }),
  lookup("needs_repair", "Needs repair", { behavior_class: "out_of_service" }),
  lookup("retired", "Retired", { behavior_class: "terminal" }),
];
const METER_TYPES: LookupEntry[] = [lookup("ami", "AMI"), lookup("amr", "AMR")];

function asset(over: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-4021",
    asset_no: "M-4021",
    serial_no: "3894-A2210",
    type: "net_meter",
    type_name: "Net meter",
    tab: "meters",
    status: "active",
    status_name: "Installed/Active",
    behavior_class: "in_service",
    meter_type: "ami",
    meter_type_name: "AMI",
    read_method: "ami",
    read_method_name: "AMI",
    multiplier: "10.000000",
    // BR-AST-500: null is the state every meter loaded before 2026-08-28 is in.
    size_class: null,
    // The size AS A CLERK READS IT, beside the code (`DEF-AST-7130`).
    size_class_name: null,
    unit: "kWh",
    net_metering: true,
    manufacturer: "Itron",
    model: "OpenWay",
    install_date: "2024-03-12",
    parent_asset_no: null,
    service_point_id: "sp-1",
    assigned_unit_id: "u-101a",
    assigned_to: "Unit A",
    assigned_address: "1408 Elm Street",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit", "reassign", "log_repair", "retire"],
    // CR-028 AST-W1: the registry columns r10 draws (B16 §4.8 MEASURED drift).
    service: "electric",
    sub_count: 0,
    last_read: null,
    parent_premises: null,
    export_capacity_kw: null,
    warranty_end: null,
    next_test: null,
    ...over,
  };
}

// r10 AST-01's own master row: the Role column renders the `Master · N units`
// tag from the SERVED child count, never a client-side guess (B16 §4.1).
const MASTER = asset({
  id: "a-master-12",
  asset_no: "M-MASTER-12",
  type: "meter",
  type_name: "Master meter",
  multiplier: "1.000000",
  sub_count: 24,
  assigned_to: "Vega Apts · building",
});

// r10 AST-01.sub's own row shape (B16 §4.2): parent + premises, unit, and the
// DEF-592 last-read summary served through the metering seam.
const SUB = asset({
  id: "a-8801",
  asset_no: "SM-8801",
  type: "sub_meter",
  type_name: "Sub-meter",
  tab: "sub_meters",
  multiplier: "1.000000",
  parent_asset_no: "M-MASTER-12",
  parent_premises: "Vega Apts",
  assigned_to: "Apt 102",
  last_read: { consumption: "2140.000", unit: "kWh", read_at: "2026-08-03" },
});

// r10 AST-01.btm's exporting inverter (B16 §4.3 · D2: structure yes, money no).
const PV = asset({
  id: "a-1204",
  asset_no: "PV-1204",
  type: "solar_inverter",
  type_name: "Solar inverter",
  tab: "behind_the_meter",
  meter_type: null,
  meter_type_name: null,
  unit: null,
  net_metering: false,
  parent_asset_no: "M-4310",
  assigned_address: "1200 Business Park",
  assigned_to: null,
  export_capacity_kw: "24.0000",
  next_test: "2027-03-01",
  warranty_end: "2030-09-01",
  actions: ["view", "edit", "reassign", "log_repair", "retire"],
});

const INVENTORY = asset({
  id: "a-5099",
  asset_no: "M-5099",
  serial_no: null,
  type: "meter",
  type_name: "Meter",
  status: "inventory",
  status_name: "Inventory/Spare",
  behavior_class: "available",
  meter_type: null,
  meter_type_name: null,
  assigned: false,
  assigned_unit_id: null,
  assigned_to: null,
  net_metering: false,
  actions: ["assign", "edit", "delete"],
});

const RETIRED = asset({
  id: "a-4204",
  asset_no: "M-4204",
  status: "retired",
  status_name: "Retired",
  behavior_class: "terminal",
  actions: ["view"],
});

const BACKFLOW = asset({
  id: "a-3301",
  asset_no: "BF-3301",
  type: "backflow",
  type_name: "Backflow preventer",
  tab: "behind_the_meter",
  meter_type: null,
  meter_type_name: null,
  unit: null,
  net_metering: false,
  test_due: true, // BR-AST-007: DERIVED, with the stored status unchanged
  actions: ["view", "edit", "reassign", "log_repair", "retire"],
});

const BLANK_CELLS = {
  select: () => <span />,
  assetNo: () => <span />,
  type: () => <span />,
  role: () => <span />,
  service: () => <span />,
  multiplier: () => <span />,
  sizeClass: () => <span />,
  meterType: () => <span />,
  readMethod: () => <span />,
  installed: () => <span />,
  age: () => <span />,
  status: () => <span />,
  actions: () => <span />,
  parentMaster: () => <span />,
  lastRead: () => <span />,
  premisesUnit: () => <span />,
  meter: () => <span />,
  exportCapacity: () => <span />,
  nextTest: () => <span />,
  warranty: () => <span />,
};

const CONFIG = assetsTableConfig(
  t,
  "meters",
  { types: [], statuses: [], meterTypes: [], premises: [], services: [] },
  BLANK_CELLS,
);

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function paged<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function renderRegistry(
  path: string,
  rows: AssetRow[],
  access?: string,
  listExtra?: Record<string, unknown>,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const search = new URLSearchParams(path.split("?")[1] ?? "");
  const tab = tabFromParam(search.get("tab"));
  const state = parseTableParams(search, CONFIG);
  queryClient.setQueryData(
    assetsQueryKey(`${serializeTableParams(state, CONFIG).toString()}|${tab}`),
    // D4: the BTM answer can carry `export_rollup` beside the page envelope.
    { ...paged(rows), ...(listExtra ?? {}) },
  );
  queryClient.setQueryData(assetTypesQueryKey, paged(TYPES));
  queryClient.setQueryData(assetStatusesQueryKey, paged(STAGES));
  queryClient.setQueryData(meterTypesQueryKey, paged(METER_TYPES));
  if (access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <AssetRegistryPage timeZone="America/Chicago" today="2026-08-09" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-AST-001 — the S49 registry", () => {
  it("US-AST-001 TC-1: rows render with the capability row's columns and the default sort", () => {
    const html = renderRegistry("/assets", [asset(), INVENTORY]);
    expect(html).toContain("M-4021");
    expect(html).toContain("M-5099");
    expect(CONFIG.defaultSort).toEqual({ sort: "asset_no", dir: "asc" });
    expect(CONFIG.columns.find((c) => c.identity === true)?.key).toBe("asset_no");
    // The Download control (POST /exports, 2026-08-10). BR-AST-004: the TAB is
    // a server filter, so the export carries it and a tab exports its own rows.
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="assets"');
    expect(html.toLowerCase()).not.toContain("xlsx");
    // BR-AST-041's search set.
    expect(CONFIG.searchFields).toEqual([
      "asset_no",
      "serial_no",
      "manufacturer",
      "model",
      "address",
    ]);
    // Serial and manufacturer are AVAILABLE columns, off by default (IS-5) —
    // present in the ⋮ menu, absent from the row until a user asks for them.
    expect(html).toContain(">Manufacturer<");
    expect(html).not.toContain(">Itron<");
  });

  it("DEF-1701: the registry RENDERS its declared filters, on every list tab", () => {
    // ⚠ **THE DEFECT THE PRODUCT OWNER REPORTED FROM FOUR SCREENSHOTS**:
    // *"on assets - tookkit dont have filters; same is the case with sub
    // meters, devices, investory"*. `assetsTableConfig` declared SEVEN filter
    // groups and `AssetRegistryPage` never passed `DataTable`'s
    // `filterBarSlot`, so the capability existed in configuration and the
    // control did not exist on screen — hard-won law 2, in the one direction
    // G13 cannot see (a CONFIG KEY nothing reads, not a PROP nothing passes).
    //
    // ⚠ **ASSERTED ON EVERY LIST TAB, because the defect was reported on all
    // of them** and a single-tab check would go green on the same bug: the tab
    // is a server filter (BR-AST-004), not a different screen, but nothing in
    // this file said the toolbar survives the switch.
    //
    // ⚠ **AND IT IS THREE TABS, NOT FOUR — DEF-1701's ROW SAYS FOUR AND THE
    // ROW IS OFF BY ONE.** The PO named Meters, Sub-meters, devices and
    // Inventory, and `Inventory` is NOT the registry list: `NON_LIST_TABS`
    // routes it to `AssetInventoryTab`, an aggregate stock roll-up that draws
    // the detail-panel TABLE and deliberately no `DataTable` at all ("nothing
    // to search, sort or page on a handful of aggregates", its own §17). It
    // has no toolbar to put a filter on, and the drill from a stock line lands
    // on THIS list with the filters preset — so the fix reaches the PO's
    // Inventory complaint through the screen it drills into. Measured, not
    // assumed; recorded here and on the defect row rather than quietly
    // dropping a tab the register names.
    for (const tab of ["meters", "sub_meters", "behind_the_meter"]) {
      const html = renderRegistry(`/assets?tab=${tab}`, [asset()]);
      expect(html, `no filter control on the ${tab} tab`).toContain("+ Filter");
      // The panel names its dimensions before it is opened — that title is
      // what proves the DECLARED groups reached the control, not just that
      // some button rendered.
      expect(html).toContain("Status");
    }
  });

  it("DEF-1701 / DEF-782: the service group is the tenant's own set, and is dropped while empty", () => {
    // `service` was declared `options: []` — DEF-782's exact shape, a legend
    // over nothing — and it survived because this screen rendered no panel for
    // the empty group to show up in: a defect hiding inside a defect. The
    // capability is real (`asset_list` filters on `f.service`), so the fix is
    // the vocabulary, not the declaration.
    expect(
      assetsTableConfig(
        t,
        "meters",
        {
          types: [],
          statuses: [],
          meterTypes: [],
          premises: [],
          services: [{ value: "water", label: "Water" }],
        },
        BLANK_CELLS,
      ).filters?.find((f) => f.name === "service")?.options,
    ).toEqual([{ value: "water", label: "Water" }]);
    // …and with no options — a Clerk who may not read Settings — `chipFilters`
    // drops the group rather than drawing an empty heading (BR-SHL-010).
    expect(
      chipFilters(CONFIG.filters ?? [], defaultRequestState(CONFIG), []).map((f) => f.name),
    ).not.toContain("service");
    // `premises_id` never reaches the panel as an option list either: B14 rule
    // 9 refuses a wall of checkboxes and this picker holds up to 500.
    expect(
      chipFilters(CONFIG.filters ?? [], defaultRequestState(CONFIG), []).map((f) => f.name),
    ).not.toContain("premises_id");
  });

  it("CR-028 T6: the multiplier renders ×10, never the raw 10.000000 decimal", () => {
    // The value STAYS a decimal string end to end; trailing zeros are trimmed
    // at DISPLAY only (r10 draws ×10 / ×1 — B16 §4.8 measured drift).
    const html = renderRegistry("/assets", [asset(), INVENTORY]);
    expect(html).toContain("×10");
    expect(html).not.toContain("10.000000");
    expect(html).toContain("×1");
  });

  it("CR-028 T6: the Installed column renders month-year, the way r10 draws it", () => {
    const html = renderRegistry("/assets", [asset()]);
    expect(html).toContain("Mar 2024");
    expect(html).not.toContain("03/12/2024");
  });

  it("CR-028 T2: the Meters tab draws r10's own column set — Role and Service included", () => {
    const keys = CONFIG.columns.map((c) => c.key);
    for (const key of [
      "select",
      "asset_no",
      "type",
      "role",
      "service",
      "multiplier",
      "assigned_to",
      "installed",
      "status",
      "actions",
    ]) {
      expect(keys).toContain(key);
    }
    const html = renderRegistry("/assets", [asset(), MASTER, INVENTORY]);
    expect(html).toContain(">Role<");
    expect(html).toContain(">Service<");
    expect(html).toContain(">Mult.<");
    // The Type cell folds both classifications the way r10 writes them.
    expect(html).toContain("Net meter · AMI");
    // Role: Standard · the Master tag with its served child count · Sub →.
    expect(html).toContain("Standard");
    expect(html).toContain("Master · 24 units");
    // The Service cell is the shared service badge with its accessible name.
    expect(html).toContain('aria-label="Electric"');
  });

  it("CR-028 T2: the page title is r10's — Assets, not Asset registry", () => {
    const html = renderRegistry("/assets", [asset()]);
    expect(html).toContain(">Assets<");
    expect(html).not.toContain("Asset registry");
  });

  it("US-AST-001 TC-2/TC-3 / BR-AST-004: three tabs, and the tab is URL state that falls back", () => {
    expect([...ASSET_TAB_IDS]).toEqual(["meters", "sub_meters", "behind_the_meter"]);
    expect(tabFromParam(null)).toBe("meters");
    expect(tabFromParam("behind_the_meter")).toBe("behind_the_meter");
    expect(tabFromParam("nonsense")).toBe("meters");
    // The tab's type filter offers only the types whose CATEGORY is that tab.
    expect(typesForTab(TYPES, "sub_meters").map((e) => e.code)).toEqual(["sub_meter"]);
    expect(typesForTab(TYPES, "behind_the_meter").map((e) => e.code)).toEqual([
      "battery",
      "backflow",
    ]);
    const html = renderRegistry("/assets?tab=behind_the_meter", [BACKFLOW]);
    expect(html).toContain("Behind the meter");
    expect(html).toContain("BF-3301");
  });

  it("US-AST-001 TC-3 / BR-AST-007: 'Test due' is a DERIVED chip beside an unchanged status", () => {
    const html = renderRegistry("/assets?tab=behind_the_meter", [BACKFLOW]);
    expect(html).toContain("Test due");
    expect(html).toContain('data-asset-chip="test-due"');
    // The stored stage label is still the one the server sent.
    expect(html).toContain("Installed/Active");
  });

  it("US-AST-001 TC-4 / BR-AST-005: the status filter's vocabulary is All · Unassigned · the tenant's stages", () => {
    const options = statusFilterOptions(STAGES, t);
    expect(options[0].value).toBe("all");
    expect(options[1].value).toBe("unassigned");
    // CR-028 AST-W5: the Inventory drill's reserved value sits with the other
    // two reserved values, ahead of the tenant's own stages — a behavior-CLASS
    // filter (BR-AST-031), so the stock line's link survives renamed stages.
    expect(options[2].value).toBe("uninstalled");
    expect(options.slice(3).map((o) => o.value)).toEqual([
      "inventory",
      "active",
      "needs_repair",
      "retired",
    ]);
    // BR-SHL-011: it round-trips through the URL like every other filter.
    const state = parseTableParams(new URLSearchParams("f.status=unassigned"), CONFIG);
    expect(state.filters.status).toBe("unassigned");
    expect(serializeTableParams(state, CONFIG).get("f.status")).toBe("unassigned");
  });

  it("BR-AST-044: meter_type is a first-class FILTER, with an 'unclassified' choice", () => {
    const options = meterTypeFilterOptions(METER_TYPES, t);
    expect(options.map((o) => o.value)).toEqual(["ami", "amr", METER_TYPE_UNCLASSIFIED]);
    expect(METER_TYPE_UNCLASSIFIED).toBe("none");
    expect(CONFIG.filters?.map((f) => f.name)).toContain("meter_type");
    const html = renderRegistry("/assets", [asset(), INVENTORY]);
    // Both classifications remain COLUMNS (off by default since CR-028 T2 —
    // r10 folds the meter type into the Type cell, so the standalone columns
    // live in the ⋮ chooser like Serial and Manufacturer).
    expect(html).toContain(">Meter type<");
    expect(html).toContain(">Read method<");
    // An unclassified measuring asset renders its type alone, never blank.
    expect(html).toContain(">Meter<");
  });

  it("BR-AST-006: the row's action set is the SERVER's — a retired row offers view only", () => {
    expect(hasAction(asset(), "retire")).toBe(true);
    expect(hasAction(RETIRED, "retire")).toBe(false);
    expect(hasAction(RETIRED, "edit")).toBe(false);
    expect(hasAction(INVENTORY, "delete")).toBe(true);
    expect(hasAction(asset(), "delete")).toBe(false);
    const retired = renderRegistry("/assets?f.status=all", [RETIRED], "Full");
    expect(retired).toContain("M-4204");
    // BR-AST-030: nothing on a retired row can transition it, ever.
    expect(retired).not.toContain(">Retire<");
    expect(retired).not.toContain(">Reassign<");
    expect(retired).not.toContain(">Log repair<");
  });

  it("BR-AST-006: a backflow device's repair action is labelled 'Log test'", () => {
    expect(repairActionKey(BACKFLOW)).toBe("assets.action.logTest");
    expect(repairActionKey(asset())).toBe("assets.action.logRepair");
    const html = renderRegistry("/assets?tab=behind_the_meter", [BACKFLOW], "Full");
    expect(html).toContain("Log test");
  });

  it("US-AST-003 TC-3/TC-4 / BR-AST-013: Delete appears ONLY on an inventory row", () => {
    // ⚠ WAS `toContain(">Delete<")` UNTIL 2026-08-20 — the row action was a
    // WORD and is a glyph now (PO ruling, B14 rule 15). The accessible name is
    // where the word went, and it is the better assertion anyway: it is the
    // string a screen reader announces, so this case fails if the label breaks.
    const inventory = renderRegistry("/assets", [INVENTORY], "Full");
    expect(inventory).toContain('aria-label="Delete"');
    const assigned = renderRegistry("/assets", [asset()], "Full");
    expect(assigned).not.toContain('aria-label="Delete"');
    // …and the confirm names the action and its one legal case.
    expect(t("assets.confirm.deleteTitle", { asset: "M-5099" })).toBe("Delete asset M-5099?");
    expect(t("assets.confirm.deleteAction")).toBe("Delete asset");
    expect(t("assets.confirm.deleteBody")).toContain("never read, assigned, repaired or billed");
  });

  it("BR-AST-013: the server's delete refusal renders through the shared refusal path", () => {
    const refused = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "assets.delete_blocked_referenced",
      params: { asset_no: "M-4021", alternative: "retire" },
      br_ref: "BR-AST-013",
    });
    expect(isApiError(refused)).toBe(true);
    expect(refused.brRef).toBe("BR-AST-013");
    expect(refused.params.alternative).toBe("retire");
  });

  it("BR-AST-036/038: the bulk bar appears only with a selection, and says inventory-only", () => {
    const html = renderRegistry("/assets", [INVENTORY], "Full");
    // Nothing is selected on first paint, so there is no bulk action to take.
    expect(html).not.toContain("Assign these to a unit");
    // The rule's own wording exists in the catalog for when it does appear.
    expect(t("assets.bulk.inventoryOnly")).toContain("inventory to units only");
    expect(t("assets.bulk.inventoryOnly")).toContain("file import");
  });

  it("US-AST-009 TC-10 / BR-AST-036: a non-inventory row comes back REFUSED from the batch", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            assigned: 1,
            failed: 1,
            results: [{ asset_no: "M-5099", warnings: [] }],
            errors: [
              {
                asset: "M-4021",
                reason: "not_inventory",
                br_ref: "BR-AST-036",
                alternative: "single_reassign_or_file_import",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    });
    const result = await bulkAssignAssets(
      { assignments: [{ asset_id: "a-5099", unit_id: "u-1" }] },
      client,
    );
    expect(result.assigned).toBe(1);
    expect(result.errors[0].reason).toBe("not_inventory");
    expect(t("assets.bulk.error.notInventory", { asset: "M-4021" })).toContain(
      "already on a unit",
    );
  });

  it("US-AST-001 §RBAC / BR-SHL-025: '—' hides the registry, 'View' disables its writes", () => {
    const denied = renderRegistry("/assets", [asset()], "—");
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain("M-4021");
    const viewOnly = renderRegistry("/assets", [asset()], "View");
    expect(viewOnly).toContain("Your role can view this but not change it.");
    expect(viewOnly).toContain("M-4021");
  });

  it.todo(
    "US-AST-001 TC-5/TC-6: the search AND filter combination and the zero-results state are server-driven — the interaction is browser scope",
  );
  it.todo(
    "US-AST-001 TC-7 (isolation): two tenants may both own an M-4021 and neither list shows the other's — server/RLS scope (G5)",
  );
});

describe("CR-028 AST-W1 — the registry to r10's AST-01 (B16 §4.1–§4.3)", () => {
  it("T1/D9: the Meters tab draws the four-card KPI grid and no explainer prose", () => {
    const html = renderRegistry("/assets", [asset(), MASTER, INVENTORY]);
    expect(html).toContain("Meters in service");
    expect(html).toContain("Needs repair");
    expect(html).toContain("In inventory");
    expect(html).toContain("Past certification age");
    expect(html).toContain("Ready to assign");
    expect(html).toContain("Exchange due this year");
    // D7: Work is R5 — the needs-repair card carries NO work-order clause.
    expect(html).not.toContain("open work order");
    // D9 closed the DEF-527 residue: the prose is gone, the grid replaced it.
    expect(html).not.toContain(
      "Meters and behind-the-meter devices · assign to units · track lifecycle",
    );
    // The figures are counted from the COMPLETE loaded result set: 2 rows in
    // service (M-4021 + the master) · 1 master · 24 subs hanging off it ·
    // AMI on both in-service rows.
    expect(html).toContain("1 masters · 24 subs · 100% AMI");
  });

  it("T1: a filtered view renders the KPI values as — rather than a dishonest count", () => {
    // With a user filter on, the loaded rows are not the tab's whole
    // population, so no number is invented (B16 T1: never invent numbers).
    const html = renderRegistry("/assets?f.status=all", [RETIRED]);
    expect(html).toContain("Meters in service");
    expect(html).toContain('data-kpi-absent="true"');
  });

  it("T3: the Sub-meters tab has its OWN column set with the DEF-592 last read", () => {
    const html = renderRegistry("/assets?tab=sub_meters", [SUB], "Full");
    expect(html).toContain(">Sub-meter #<");
    expect(html).toContain(">Parent / master<");
    expect(html).toContain(">Unit<");
    expect(html).toContain(">Last read<");
    // Parent / master composes parent number · its premises (r10's own cell).
    expect(html).toContain("M-MASTER-12 · Vega Apts");
    expect(html).toContain("Apt 102");
    // The last-read summary in r10's shape: quantity, unit, month-day.
    expect(html).toContain("2,140");
    expect(html).toContain("kWh");
    expect(html).toContain("Aug 3");
    // The caption stays — r10 draws it on this tab (no KPI strip here). ⚠ Its
    // WORDING moved on 2026-09-12 (`DEF-MET-4961`): r10's own 24-word pair was
    // adopted whole by DEF-527 on 2026-08-22, and B14 rules 32 and 33 — both
    // ratified AFTER that — allow one sentence of six words. The second
    // sentence named the four row actions visible three inches below it.
    expect(html).toContain("Sub-meters bill their own unit.");
    // … and the old pair is gone rather than merely un-asserted, because a
    // dropped assertion is how a reverted string goes unnoticed.
    expect(html).not.toContain("Click one for its detail");
    // The four row actions, by accessible name — and Edit is the EDIT modal,
    // never the repair screen (r10's own bug, recorded in B16 §11, not copied).
    expect(html).toContain('aria-label="View"');
    expect(html).toContain('aria-label="Edit"');
    expect(html).toContain('aria-label="Reassign"');
    expect(html).toContain('aria-label="Retire"');
  });

  it("T3: a sub-meter without a read yet renders the quiet dash, never a zero", () => {
    const html = renderRegistry("/assets?tab=sub_meters", [
      asset({ ...SUB, id: "a-8802", asset_no: "SM-8802", last_read: null }),
    ]);
    expect(html).toContain("SM-8802");
    expect(html).not.toContain("2,140");
  });

  it("T4/D2: the Behind-the-meter tab is the device registry WITHOUT money", () => {
    const html = renderRegistry("/assets?tab=behind_the_meter", [PV, BACKFLOW]);
    expect(html).toContain(">Device #<");
    expect(html).toContain(">Premises · unit<");
    expect(html).toContain(">Meter<");
    expect(html).toContain(">Export capacity<");
    expect(html).toContain(">Next test<");
    // Warranty is AVAILABLE but hidden by default (the ⋮ chooser carries it).
    expect(html).toContain(">Warranty<");
    expect(html).not.toContain("Sep 2030");
    // The linked meter and the capacity, from the served row.
    expect(html).toContain("M-4310");
    expect(html).toContain("24");
    expect(html).toContain("kW");
    expect(html).toContain("Mar 2027");
    // D2, ruled: no tariff column, no credited dollars, anywhere on this tab.
    expect(html).not.toContain("Tariff");
    expect(html).not.toContain("$");
    expect(html).not.toContain("Credited to bills");
  });

  it("T1/D2: the BTM KPI strip is THREE cards — devices · exporting · exported kWh", () => {
    const html = renderRegistry("/assets?tab=behind_the_meter", [PV, BACKFLOW]);
    expect(html).toContain(">Devices<");
    expect(html).toContain("Exporting devices");
    expect(html).toContain("Exported ·");
    expect(html).not.toContain("Credited to bills");
  });

  it("D4 (CR-028 debt sweep): a SERVED export rollup fills the Exported card — its month, quantity WITH unit", () => {
    // RED before the sweep: the card's value was hardcoded `kpiValue(null)` —
    // a dash forever, whatever metering had measured.
    const html = renderRegistry("/assets?tab=behind_the_meter", [PV, BACKFLOW], undefined, {
      export_rollup: {
        month: "2026-07-01",
        totals: [{ quantity: "21.000000", unit: "kWh" }],
      },
    });
    // The label names the SERVED month (the last COMPLETE month), not today's.
    expect(html).toContain("Exported · July");
    // Rule 3: the quantity renders with its explicit unit, trailing zeros trimmed.
    expect(html).toContain("21 kWh");
    // Still no money anywhere on this tab (BR-AST-025 / D2's ruling).
    expect(html).not.toContain("$");
  });

  it("D4: an EMPTY month keeps the quiet dash — a zero nobody measured is never served", () => {
    const html = renderRegistry("/assets?tab=behind_the_meter", [PV, BACKFLOW], undefined, {
      export_rollup: { month: "2026-07-01", totals: [] },
    });
    expect(html).toContain('data-kpi-absent="true"');
    expect(html).not.toContain("0 kWh");
  });

  it("T5/BR-AST-046: each tab's import button is named for the tab and NAVIGATES", () => {
    const meters = renderRegistry("/assets", [asset()]);
    expect(meters).toContain("↑ Import meters");
    expect(meters).not.toContain("Bulk import");
    const sub = renderRegistry("/assets?tab=sub_meters", [SUB]);
    expect(sub).toContain("↑ Import sub-meters");
    const btm = renderRegistry("/assets?tab=behind_the_meter", [PV]);
    expect(btm).toContain("↑ Import devices");
  });

  /**
   * ⚠ **THE BTM PRIMARY READ `+ Add behind-the-meter asset` UNTIL 2026-09-13.**
   * Figure 3 on page 14 of `05-prototype/01 Assets Menu Blueprint.pdf` draws
   * **`+ Add device`** in the header's one primary slot, and the screen table
   * beside it states the same under *Primary action*. Read as an image, per B14
   * rule 42. The Meters label is unchanged — the drawing keeps `+ Add asset`
   * there.
   */
  it("T2: the primary is + Add asset on Meters and + Add device on BTM (figure 3, p14)", () => {
    const meters = renderRegistry("/assets", [asset()]);
    expect(meters).toContain("+ Add asset");
    expect(meters).not.toContain("+ Add meter<");
    const btm = renderRegistry("/assets?tab=behind_the_meter", [PV]);
    expect(btm).toContain("+ Add device");
    expect(btm).not.toContain("+ Add behind-the-meter asset");
  });
});

describe("US-SHL-020 — S15 through the shared page header (BR-SHL-044)", () => {
  /**
   * The header's action row, sliced out of the static markup: from the row's
   * own class up to the tab strip that closes the header's top half.
   *
   * Counting a label across the WHOLE page would also count the empty state's
   * CTA, which is deliberately the same words in a different place — so "the
   * header offers exactly one primary" has to be asked of the header.
   */
  function headerActions(html: string): string {
    return html.slice(html.indexOf("page-header-actions"), html.indexOf("page-header-tabs"));
  }

  it("US-SHL-020 TC-1 / BR-SHL-044 (a): the primary action is per-TAB, in the ONE slot", () => {
    const meters = renderRegistry("/assets", [asset()]);
    expect(headerActions(meters)).toContain("+ Add asset");
    expect(headerActions(meters)).not.toContain("+ Add sub-meter");
    expect(headerActions(meters)).not.toContain("+ Add behind-the-meter asset");

    const sub = renderRegistry("/assets?tab=sub_meters", [asset({ tab: "sub_meters" })]);
    expect(headerActions(sub)).toContain("+ Add sub-meter");
    expect(headerActions(sub)).not.toContain("+ Add asset");

    // Figure 3 (p14) renamed this one to `+ Add device` on 2026-09-13; the
    // per-TAB rule this case is named for is untouched.
    const devices = renderRegistry("/assets?tab=behind_the_meter", [BACKFLOW]);
    expect(headerActions(devices)).toContain("+ Add device");
    expect(headerActions(devices)).not.toContain("+ Add asset<");
  });

  it("US-SHL-020 TC-1 / CR-028 T5: the import secondary relabels with the tab", () => {
    expect(headerActions(renderRegistry("/assets", [asset()]))).toContain("↑ Import meters");
    expect(headerActions(renderRegistry("/assets?tab=sub_meters", [asset()]))).toContain(
      "↑ Import sub-meters",
    );
    expect(headerActions(renderRegistry("/assets?tab=behind_the_meter", [asset()]))).toContain(
      "↑ Import devices",
    );
  });

  /**
   * ⚠ **THIS CASE PINNED D9's "NO PROSE ON METERS AND BTM" SHUT, AND THE
   * BLUEPRINT OVERTURNS IT (`AST-B-15` / remedy R6, 2026-09-13).**
   *
   * Page 6 of `05-prototype/01 Assets Menu Blueprint.pdf` carries a commitment
   * card headed *"And this tab has no description at all"*, and it is worth
   * quoting because it names the mechanism: *"The catalogue holds one —
   * `assets.explainer.meters` … and the screen never renders it …
   * **That was a ruling — the KPI grid replaced the prose on those two tabs —
   * taken when the grid showed numbers; the grid now shows dashes, so those two
   * tabs carry neither. Two dead strings, and two screens with nothing under
   * the title.**"* Page 14's own annotation on the Behind-the-meter tab says
   * the same of the second: *"no description — the tab renders none"*.
   *
   * So D9 was correct when it was taken and stopped being correct when its
   * premise moved, and the assertion that survived it was holding an empty slot
   * open on two screens. Both sentences were cut to six words for B14 rule 33
   * in the same commit, so the long r10 forms are asserted ABSENT below — the
   * supersession is pinned in both directions rather than simply relaxed.
   */
  it("US-SHL-020 TC-2 / BR-SHL-044 (b) / AST-B-15: EVERY tab's description renders, and it sits BELOW the strip", () => {
    const meters = renderRegistry("/assets", [asset()]);
    // The six-word form, and NOT the 24-word r10 sentence it replaced.
    expect(meters).toContain("Meters, where they sit, their state");
    expect(meters).not.toContain(
      "Meters and behind-the-meter devices · assign to units · track lifecycle",
    );
    expect(meters).toContain("page-header-explainer");
    expect(meters.indexOf("page-header-tabs")).toBeLessThan(
      meters.indexOf("page-header-explainer"),
    );
    expect(meters.indexOf("<h1")).toBeGreaterThan(-1);
    expect(meters.indexOf("<h1")).toBeLessThan(meters.indexOf("page-header-tabs"));

    const sub = renderRegistry("/assets?tab=sub_meters", [asset({ tab: "sub_meters" })]);
    // r10's own sentence for the Sub-meters tab (SMARTBillHub.dc.html line
    // 3246) was adopted for DEF-527 on 2026-08-22 — G14 pinned the catalogue
    // value to the prototype and this test pins the RENDERING to the catalogue.
    // ⚠ **B14 rules 32 and 33 SUPERSEDE that adoption** (`DEF-MET-4961`,
    // 2026-09-12): one sentence per section, six words per sentence, and r10's
    // was 24 words in two. `EXPLAINERS_NOT_IN_R10` moves 2 → 3 in the same
    // commit with the supersession named on the constant, which is what
    // CLAUDE.md means by *"B14 wins and every divergence is stamped there"*.
    expect(sub).toContain("Sub-meters bill their own unit.");
    expect(sub).not.toContain("Click one for its detail");
    // Index ordering in the static markup, the way PageHeader.test.tsx asks it:
    // the strip is what a returning user reaches for first, so the guidance is
    // underneath it — NOT in the head, where the prototype put it.
    expect(sub.indexOf("page-header-tabs")).toBeLessThan(sub.indexOf("page-header-explainer"));

    const devices = renderRegistry("/assets?tab=behind_the_meter", [BACKFLOW]);
    expect(devices).toContain("Customer-side devices, capacity and test dates");
    expect(devices).not.toContain(
      "Behind-the-meter assets — assigned to units, tracked through their lifecycle",
    );
    expect(devices.indexOf("page-header-tabs")).toBeLessThan(
      devices.indexOf("page-header-explainer"),
    );
  });

  it("US-SHL-020 TC-5: a LIST screen renders no back link", () => {
    expect(renderRegistry("/assets", [asset()])).not.toContain("page-header-back");
  });

  it("US-SHL-020 TC-6: the header can never offer two primary actions", () => {
    // One active tab ⇒ one "+ Add …" in the header, whichever tab is open.
    for (const path of ["/assets", "/assets?tab=sub_meters", "/assets?tab=behind_the_meter"]) {
      const actions = headerActions(renderRegistry(path, [asset()]));
      expect((actions.match(/\+ Add/g) ?? []).length).toBe(1);
    }
  });

  it("US-SHL-020 / BR-SHL-025: the header's controls survive the conversion DISABLED, never hidden", () => {
    const actions = headerActions(renderRegistry("/assets", [asset()], "View"));
    expect(actions).toContain("+ Add asset"); // present…
    expect(actions).toContain("↑ Import meters");
    expect(actions).toContain("disabled"); // …unusable…
    expect(actions).toContain("Your role can view this but not change it."); // …and it says why
  });

  it("US-SHL-020: S15 draws no head or tab strip of its own any more (DEF-021)", () => {
    const html = renderRegistry("/assets", [asset()]);
    expect(html).toContain("page-header");
    expect(html).not.toContain("ast-head");
    expect(html).not.toContain("ast-tabs");
    // The old single page sentence is gone with it — the three per-tab ones
    // replaced it, so nothing on screen speaks for all three tabs at once.
    expect(html).not.toContain("Every meter, sub-meter and behind-the-meter device");
  });

  it.todo(
    "US-SHL-020 TC-1 (interaction): clicking Sub-meters rewrites ?tab=, swaps the primary's label IN PLACE and clears the selection — the click path is browser scope",
  );
});

describe("US-AST-002 — the S51 add-asset modal", () => {
  it("US-AST-002 TC-1 / BR-AST-026: the create carries the THREE identifiers, and never a uuid", async () => {
    let sent: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(JSON.stringify({ ...asset({ asset_no: "M-5100" }), warnings: [] }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const created = await createAsset(
      {
        asset_no: "M-5100", // 1: the user asset number (blank → the series)
        serial_no: "IT-88412", // 2: the physical identifier
        type: "meter",
        meter_type: "ami",
        read_method: "ami",
        unit: "kWh",
        multiplier: "1",
        install_date: "2026-08-08",
        unit_id: "u-200",
      },
      client,
    );
    expect(created.asset_no).toBe("M-5100");
    expect(sent.asset_no).toBe("M-5100");
    expect(sent.serial_no).toBe("IT-88412");
    // 3: the internal uuid is never sent and never displayed.
    expect(sent).not.toHaveProperty("id");
    // CLAUDE.md #3: the measuring asset carries an EXPLICIT unit of measure.
    expect(sent.unit).toBe("kWh");
  });

  it("BR-AST-044: meter_type is ACCEPTED on a meter and REFUSED on a battery — the server's own envelope renders", async () => {
    // Accepted: a measuring type takes the second classification.
    const okClient = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify({ ...asset({ meter_type: "ami" }), warnings: [] }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
    });
    const ok = await createAsset({ type: "meter", meter_type: "ami" }, okClient);
    expect(ok.meter_type).toBe("ami");

    // Refused: a non-measuring type has no meter type, and the server says so
    // as a FIELD error — which renders under the offending input (A18 §5).
    const refusingClient = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "VAL-002",
            message_key: "assets.meter_type_unavailable",
            params: { type: "battery" },
            field_errors: [
              {
                field: "meter_type",
                code: "VAL-002",
                message_key: "assets.meter_type_unavailable",
                params: { type: "battery" },
              },
            ],
            br_ref: "BR-AST-044",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
    });
    let refusal: ApiError | null = null;
    try {
      await createAsset({ type: "battery", meter_type: "ami" }, refusingClient);
    } catch (error) {
      refusal = isApiError(error) ? error : null;
    }
    expect(refusal).not.toBeNull();
    expect(refusal?.status).toBe(422);
    expect(refusal?.brRef).toBe("BR-AST-044");
    const mapped = envelopeErrors(formErrorEnvelope(refusal as ApiError), t);
    expect(Object.keys(mapped.fields)).toEqual(["meter_type"]);
    expect(mapped.fields.meter_type).toContain("does not apply to this kind of device");
  });

  it("BR-AST-044 / BR-AST-009: 'measuring' follows the type's CATEGORY, not a hardcoded code list", () => {
    expect(isMeasuringCategory("meters")).toBe(true);
    expect(isMeasuringCategory("sub_meters")).toBe(true);
    expect(isMeasuringCategory("behind_the_meter")).toBe(false);
    expect(isMeasuringCategory(null)).toBe(false);
    expect(isMeasuringCategory(undefined)).toBe(false);
  });

  it("US-AST-002 TC-5/TC-9 / BR-AST-033: a duplicate NUMBER blocks; a duplicate SERIAL warns and saves", async () => {
    // Hard block: 409 BIZ-STATE, nothing written.
    const blocking = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "BIZ-STATE",
            message_key: "assets.asset_no_duplicate",
            params: { asset_no: "M-4021" },
            br_ref: "BR-AST-033",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
    });
    await expect(createAsset({ type: "meter", asset_no: "M-4021" }, blocking)).rejects.toThrow();

    // Warn-but-allow: the row IS created and the warning rides in the body.
    const warning = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            ...asset({ asset_no: "M-5100" }),
            warnings: [{ code: "duplicate_serial", existing_asset_no: "M-4021" }],
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
    });
    const created = await createAsset(
      { type: "meter", serial_no: "3894-A2210" },
      warning,
    );
    expect(created.asset_no).toBe("M-5100");
    expect(created.warnings[0].code).toBe("duplicate_serial");
  });

  it.todo(
    "US-AST-002 TC-4/TC-7: the Sub-meters tab has no parent picker (no role-safe endpoint lists candidate parents) — the server's 'parent required' refusal is the guard; reported",
  );
  it.todo(
    "US-AST-002 TC-3/TC-6: the net-metering lock and the missing-UoM refusal are asserted server-side; the checkbox's locked state is browser scope",
  );
  it.todo(
    "US-AST-002 TC-8 (isolation): the same asset number in two tenants both succeed — server/RLS scope (G5)",
  );
});

describe("US-AST-010 — RETIRED to the runner (CR-028 AST-W3-T5)", () => {
  // The staged-import wrappers (stageAssetImport / commitAssetImport) are
  // GONE with the path they wrapped: the server refuses both write verbs
  // (`assets.import_moved_to_runner`, asserted in the backend suite) and the
  // assets import is `extractImport` with an assets target — the tests that
  // stood here asserted a pipeline BR-MET-096 forbids to survive.
  it("the retirement's user-facing sentence exists in the catalogue", () => {
    expect(t("assets.import_moved_to_runner")).toContain("Import");
  });
});

describe("CR-028 — the assets import entries on the ONE runner (BR-AST-046)", () => {
  it("each tab's import destination carries its own target", () => {
    expect(assetImportPath("meters")).toBe("/assets/import?target=assets_meters");
    expect(assetImportPath("sub_meters")).toBe("/assets/import?target=assets_submeters");
    expect(assetImportPath("behind_the_meter")).toBe("/assets/import?target=assets_devices");
  });

  it("AST-W3 T4: a registered assets target mounts the REAL five-stage runner", () => {
    // AST-W1 left an honest not-available state here; AST-W3 registered the
    // three kinds, so the same route now mounts the runner with the meters
    // kind's own copy — and the not-available body is GONE for it.
    const html = renderToStaticMarkup(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/assets/import?target=assets_meters"]}>
            <AssetImportWorkflowPage />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain(t("workflow.assets_meters.kicker"));
    expect(html).toContain(t("workflow.stage.extract"));
    expect(html).not.toContain("Nothing can be uploaded here");
  });

  it("a target nobody registered still renders the honest not-available state", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/assets/import?target=assets_stock"]}>
        <AssetImportWorkflowPage />
      </MemoryRouter>,
    );
    // `assets_stock` is B16 §4.7b's PROPOSED fourth target, deliberately not
    // extracted — the honest state keeps telling the truth about it.
    expect(html).toContain("Nothing can be uploaded here");
    expect(html).toContain(t("assets.import.unavailable.back"));
    expect(html).toContain('data-tracks="BR-AST-046"');
  });

  it("AST-04: the Imports tab is on the strip and mounts the run table with the three buttons", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (input) => {
        const url = String(input);
        if (url.includes("/imports")) {
          return new Response(
            JSON.stringify({
              rows: [
                {
                  id: "run-1",
                  run_no: "RUN-0101",
                  target: "assets_meters",
                  file_name: "meters.csv",
                  rows_in: 20,
                  loaded: 17,
                  rejected: 3,
                  status: "loaded",
                  run_by: "clerk@scw.test",
                  started_at: "2026-08-22T10:00:00Z",
                  finished_at: "2026-08-22T10:01:00Z",
                },
                {
                  // A premises run — MUST NOT render on the assets tab
                  // (B16 §4.7: a FILTERED view of the one runner's runs).
                  id: "run-2",
                  run_no: "RUN-0100",
                  target: "premises",
                  file_name: "premises.csv",
                  rows_in: 431,
                  loaded: 425,
                  rejected: 6,
                  status: "loaded",
                  run_by: "clerk@scw.test",
                  started_at: "2026-08-21T10:00:00Z",
                  finished_at: "2026-08-21T10:02:00Z",
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify({ results: [], count: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    await queryClient.prefetchQuery({
      // ⚠ THE EMPTY FILTER OBJECT IS PART OF THE KEY (CR-045 wave D · D.13).
      // AST-04's query is keyed on `state.filters` so that ticking a status
      // refetches instead of being served the cached unfiltered response;
      // seeding `["import-runs", "assets"]` alone is the "near-miss that
      // renders a skeleton" this harness's siblings warn about, and it renders
      // the loading frame rather than the run.
      queryKey: ["import-runs", "assets", {}],
      queryFn: () => import("@/api/endpoints").then((m) => m.getImportRuns(client, {})),
    });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/assets?tab=imports"]}>
            <AssetRegistryPage client={client} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // The strip carries the fourth tab; the body carries the r10 callout,
    // the three tab-named buttons and the assets run — not the premises one.
    expect(html).toContain(t("assets.tab.imports"));
    expect(html).toContain(t("assets.imports.rollbackCallout"));
    expect(html).toContain(t("assets.action.import.meters"));
    expect(html).toContain(t("assets.action.import.sub_meters"));
    expect(html).toContain(t("assets.action.import.behind_the_meter"));
    expect(html).toContain("RUN-0101");
    expect(html).not.toContain("RUN-0100");
  });

  it("the ?tab= vocabulary accepts all seven tabs and still falls back on junk", () => {
    expect(tabFromParam("imports")).toBe("imports");
    // CR-028 AST-W5 (D1): the three new tabs are REAL vocabulary now — the
    // pre-W5 pin here expected "lifecycle" to fall back, and this amendment
    // is that pin moving WITH the ruling, not a loosened test.
    expect(tabFromParam("inventory")).toBe("inventory");
    expect(tabFromParam("lifecycle")).toBe("lifecycle");
    expect(tabFromParam("map")).toBe("map");
    expect(tabFromParam("workshop")).toBe("meters"); // junk still falls back
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-001@566072b (story+rules snapshot hash — EP-AST-01; co-stories US-AST-002/003@566072b · US-AST-010@5be132f; co-packet US-SHL-020@9941789 — EP-SHL-01)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — TC-1/TC-2/TC-5/TC-6 for S15 through the shared header, plus the BR-SHL-025 and DEF-021 regressions) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (the US-AST-010 staged-import cases are replaced by the retirement case; the runner-mount, honest-absence, AST-04 imports-tab and RegistryTab cases land) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (two pins move WITH the D1 ruling: the ?tab= vocabulary accepts inventory/lifecycle/map, and the status filter's reserved values gain `uninstalled` ahead of the tenant stages)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-change baseline) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (11 PASS/0 FAIL/2 SKIP was the baseline; a CONCURRENT lane added G14 prototype-conformance, which this conversion turns green for S15 and S16) · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 [US-SHL-020] TC-1/TC-6 count a label inside the HEADER's own action row, sliced out of the static markup, because the empty state's CTA is deliberately the same words in a different place — a whole-page count would answer a question nobody asked · E4 [US-SHL-020] TC-2 asserts the explainer's position by INDEX ORDERING in the static markup, the way PageHeader.test.tsx does; a rendered-geometry assertion needs a browser and stays the Playwright journey's · E4 the TCs that assert a SERVER refusal (duplicate #, missing UoM, the row cap, skip-errors OFF) are asserted here through the rendered envelope where the frontend owns the rendering, and left to the backend suite where it owns the verdict · E4 the isolation halves are the G5 suite's, on live Postgres
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("record links (PO 2026-10-19) — the registry's record cells", () => {
  it("a sub-meter's Parent / master opens the master asset", () => {
    const html = renderRegistry(`/${TEST_TENANT}/assets?tab=sub_meters`, [
      { ...SUB, parent_asset_id: "a-master-12" },
    ]);
    expect(html).toContain(`href="/${TEST_TENANT}/assets/a-master-12"`);
    expect(html).toContain(">M-MASTER-12</a> · Vega Apts");
  });

  it("a behind-the-meter device's Meter opens the meter and Premises · unit opens the unit", () => {
    const html = renderRegistry(`/${TEST_TENANT}/assets?tab=behind_the_meter`, [
      { ...PV, parent_asset_id: "a-4310", assigned_unit_id: "u-1200", assigned_to: "Suite 3" },
    ]);
    expect(html).toContain(`href="/${TEST_TENANT}/assets/a-4310"`);
    expect(html).toContain(`href="/${TEST_TENANT}/premises/units/u-1200"`);
  });

  it("no id on the row means the same words, unlinked — never a guessed address", () => {
    const html = renderRegistry(`/${TEST_TENANT}/assets?tab=sub_meters`, [SUB]);
    expect(html).toContain("M-MASTER-12 · Vega Apts");
    expect(html).not.toContain(">M-MASTER-12</a>");
  });
});
