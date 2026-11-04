// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-004 (S50 header + Overview) · US-AST-005 (the Reads tab —
//           SERVED, CR-028 AST-W2 T4/DEF-475) · US-AST-006 (history ·
//           maintenance · audit) · US-SHL-020 (the one page header)
//           Screens: S50 (S16 in A1's platform-shell numbering) / AST-02
// Change:   CR-028 AST-W2 (B16 §5.1/§5.1b, 2026-08-22) — r10's AST-02 for
//           EVERY KIND: header sub-line to r10, Specifications absorb the
//           classification panel, THREE Overview panels (Assignment ·
//           Warranty & supplier · Lifecycle), Reads served with the net fold,
//           Audit inline (the CR-23/DEF-579 pattern), names not uuids,
//           maintenance cost captured NEVER posted (§10-D3), device 4-tab /
//           inverter 5-tab sets (§5.1b A/B).
// Rules:    BR-AST-006 · BR-AST-007 · BR-AST-014 · BR-AST-015 · BR-AST-017/018
//           BR-AST-019 + BR-AUD-010 (per-entity audit tab RENDERS and links) ·
//           BR-AST-026 · BR-AST-029 (two typed records fold per date) ·
//           BR-AST-025/016 (no money on read surfaces) · BR-AST-030 ·
//           BR-AST-039 (live chain, account leg live) · BR-AST-044 ·
//           BR-AST-047 (valuation captured, no GL link) · BR-SHL-034 ·
//           BR-SHL-025 · BR-SHL-044
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type {
  AssetDetail,
  AssetMaintenanceResult,
  AssetReadRow,
  AuditListResult,
  MyPermissions,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { PREMISES_PERMISSION } from "@/features/metering/meteringShared";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";

import type { AssetWorkOrderRow, AssetWorkOrders } from "@/features/work/workEndpoints";

import {
  ASSET_DETAIL_TABS,
  AssetDetailPage,
  assetDetailTabsFor,
  assetAssignmentsQueryKey,
  assetDetailQueryKey,
  assetDetailTabFrom,
  assetMaintenanceQueryKey,
  assetReadsQueryKey,
  registerDigitsOf,
} from "./AssetDetailPage";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`, so
// the screens below are rendered under one and the render helpers take the
// TENANT-RELATIVE path the route config is written in.
const TEST_TENANT = "brazosbend";

function detail(over: Partial<AssetDetail> = {}): AssetDetail {
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
    parent_asset_id: null,
    has_test_cadence: false,
    service: "electric",
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
    specs: {
      form_class: "2S",
      register_digits: 5,
      firmware_version: "5.2.1",
      seal_no: "TX-88121",
      warranty_end: "2029-03-12",
      last_test_date: "2026-06-02",
      test_interval_months: 24,
      location_note: "left side wall, behind gate",
      allocation_rule: null,
      loss_tolerance_pct: null,
      allocation_share_pct: null,
    },
    classifications: {
      asset_type: { code: "net_meter", name: "Net meter" },
      meter_type: { code: "ami", name: "AMI" },
      read_method: { code: "ami", name: "AMI" },
    },
    billing_chain: {
      premises_id: "p-101",
      premise_no: "P-00101",
      premise_address: "1408 Elm Street",
      unit_id: "u-101a",
      unit_label: "Unit A",
      // CR-028 AST-W2: the account leg is LIVE (customers owns tables now).
      account: {
        id: "acc-1",
        account_no: "A-10432",
        customer_name: "Miller, Sarah",
        status: "active",
      },
    },
    sub_assets: [],
    // ── CR-028 AST-W2 (BR-AST-047 / B16 §5.1) ──
    valuation: {
      supplier: "Itron Direct",
      purchase_cost: "164.0000",
      purchase_date: null,
      warranty_end: "2029-03-12",
      warranty_covered: true,
      depreciation_method: null,
      currency: "USD",
    },
    lifecycle: {
      age_months: 29, // 2 yrs 5 mo — the B16 §5.1 worked figure
      expected_life_years: 8,
      certification_due: "2028-06-02",
      replacement_year: 2032,
    },
    linked_meter: null,
    ...over,
  };
}

const BATTERY = detail({
  id: "a-0904",
  asset_no: "BAT-0904",
  type: "battery",
  type_name: "Battery storage",
  tab: "behind_the_meter",
  meter_type: null,
  meter_type_name: null,
  read_method: null,
  read_method_name: null,
  unit: null,
  net_metering: false,
  service: null,
  assigned: false,
  assigned_to: null,
  assigned_unit_id: null,
  status: "inventory",
  status_name: "Inventory/Spare",
  behavior_class: "available",
  actions: ["assign", "edit", "delete"],
  classifications: {
    asset_type: { code: "battery", name: "Battery storage" },
    meter_type: null,
    read_method: null,
  },
  billing_chain: {
    premises_id: null,
    premise_no: null,
    premise_address: null,
    unit_id: null,
    unit_label: null,
    account: null,
  },
  specs: { ...detail().specs, register_digits: null },
  valuation: { ...detail().valuation, warranty_end: null, warranty_covered: null },
  lifecycle: {
    age_months: 3,
    expected_life_years: null,
    certification_due: null,
    replacement_year: null,
  },
});

/** §5.1b (A): a plain non-measuring device with a test cadence — FOUR tabs. */
const BACKFLOW = detail({
  id: "a-3301",
  asset_no: "BF-3301",
  type: "backflow",
  type_name: "Backflow preventer",
  tab: "behind_the_meter",
  meter_type: null,
  meter_type_name: null,
  read_method: null,
  read_method_name: null,
  unit: null,
  net_metering: false,
  service: null,
  has_test_cadence: true,
  test_due: true,
  classifications: {
    asset_type: { code: "backflow", name: "Backflow preventer" },
    meter_type: null,
    read_method: null,
  },
  specs: {
    ...detail().specs,
    last_test_date: "2025-06-02",
    test_interval_months: 12,
  },
  lifecycle: {
    age_months: 29,
    expected_life_years: null,
    certification_due: "2026-06-02",
    replacement_year: null,
  },
});

/** §5.1b (B): an exporting inverter — FIVE tabs, Export replaces Reads. */
const INVERTER = detail({
  id: "a-1204",
  asset_no: "PV-1204",
  type: "pv",
  type_name: "PV / solar",
  tab: "behind_the_meter",
  meter_type: null,
  meter_type_name: null,
  read_method: null,
  read_method_name: null,
  unit: null,
  net_metering: false,
  service: null,
  parent_asset_no: "M-4310",
  parent_asset_id: "a-4310",
  classifications: {
    asset_type: { code: "pv", name: "PV / solar" },
    meter_type: null,
    read_method: null,
  },
  linked_meter: { id: "a-4310", asset_no: "M-4310", net_metering: true },
});

/** §5.1b: a sub-meter — the sub-line names its MASTER, specs add the link. */
const SUB = detail({
  id: "a-8801",
  asset_no: "SM-8801",
  type: "sub_meter",
  type_name: "Sub-meter",
  tab: "sub_meters",
  net_metering: false,
  parent_asset_no: "M-MASTER-12",
  parent_asset_id: "a-master-12",
  parent_premises: "Vega Apts",
  classifications: {
    asset_type: { code: "sub_meter", name: "Sub-meter" },
    meter_type: { code: "sub_meter", name: "Sub-meter" },
    read_method: { code: "ami", name: "AMI" },
  },
  specs: { ...detail().specs, allocation_share_pct: null },
});

const RETIRED = detail({
  id: "a-4204",
  asset_no: "M-4204",
  status: "retired",
  status_name: "Retired",
  behavior_class: "terminal",
  retire_date: "2026-08-08",
  retire_reason: "failed",
  replaced_by: "M-5100",
  actions: ["view"],
});

const ASSIGNMENTS = [
  {
    id: "as-2",
    from_date: "2024-03-12",
    to_date: null,
    current: true,
    unit_id: "u-101a",
    unit_label: "Unit A",
    premise_address: "1408 Elm Street",
    by: "Dana Whitfield", // CR-028 AST-W2 T6: resolved NAME, never the uuid
    final_read_id: null,
  },
  {
    id: "as-1",
    from_date: "2023-01-01",
    to_date: "2024-03-12",
    current: false,
    unit_id: "u-000",
    unit_label: null,
    premise_address: null,
    by: "System",
    final_read_id: null,
  },
];

/** CR-028 AST-W2 T7: rows + the server's lifetime total + the CHAR(3).
 *  ⚠ `total` since `AST-B-19`: this route is SERVER-PAGED and the fixture has
 *  to carry what the wire carries, or it is once again describing a shape the
 *  product does not answer with — which is the whole reason the reads break
 *  survived (this file seeds React Query directly, so it never crossed the
 *  boundary that changed). */
const MAINTENANCE: AssetMaintenanceResult = {
  total: 2,
  rows: [
    {
      id: "m-2",
      date: "2026-07-02",
      kind: "repair",
      detail: "Comms module replaced",
      tech_user_id: "u-ray",
      technician: "Ray Delgado",
      resulting_status: "active",
      closed_at: null,
      cost: "88.4000",
    },
    {
      id: "m-1",
      date: "2026-06-02",
      kind: "inspection",
      detail: "Annual accuracy check — passed",
      tech_user_id: "u-ray",
      technician: "Ray Delgado",
      resulting_status: "active",
      closed_at: null,
      cost: "31.0000",
    },
  ],
  lifetime_cost: "119.4000",
  currency: "USD",
};

/** BR-AST-029's fold, as the server serves it: newest first, the net pair
 *  as ONE row with Import and Export quantities, each with its unit. */
const READS: AssetReadRow[] = [
  {
    read_id: "r-2",
    date: "2026-09-03",
    channel: "total",
    read_type: "consumption",
    reading: "43566.000000",
    consumption: "702.000000",
    unit: "kWh",
    export: "141.000000",
    export_unit: "kWh",
    export_read_id: "r-2e",
    source: "import",
    status: "ok",
  },
  {
    read_id: "r-1",
    date: "2026-08-03",
    channel: "total",
    read_type: "consumption",
    reading: "42864.000000",
    consumption: "684.000000",
    unit: "kWh",
    export: null,
    export_unit: null,
    export_read_id: null,
    source: "import",
    status: "ok",
  },
];

const AUDIT: AuditListResult = {
  page: {
    count: 2,
    next: null,
    previous: null,
    results: [
      {
        id: "au-2",
        created_at: "2026-08-22T14:05:00+00:00",
        actor: { id: "u-dana", name: "Dana Whitfield" },
        action: "asset.maintenance_logged",
        entity_type: "asset",
        entity_id: "a-4021",
        summary: "kind: repair",
        source: null,
      },
      {
        id: "au-1",
        created_at: "2026-08-21T10:00:00+00:00",
        actor: null, // BR-AUD-003: a system job, named — never blanked
        action: "asset.updated",
        entity_type: "asset",
        entity_id: "a-4021",
        summary: "seal_no: — → TX-88121",
        source: null,
      },
    ],
  },
  window: { window: "hot", from: null },
};

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

/**
 * `GET /assets/{id}/work-orders`, as `listAssetWorkOrders` hands it on — the
 * ENVELOPE keys plus the by-date index. `DEF-MET-4967`: the page fetched this
 * and read only `maintenance_index`, so `rows` and `total` were paid for on
 * every Maintenance tab open and thrown away. Two orders, one open and one
 * done, so the Open work panel's filter is exercised rather than assumed.
 */
function workOrder(over: Partial<AssetWorkOrderRow> = {}): AssetWorkOrderRow {
  // ⚠ TYPED AS THE WIRE ROW, not as the handful of keys this screen draws.
  // `AssetWorkOrderRow` is `_scoped_row`'s own shape, so a fixture that drifts
  // from what the server sends stops compiling instead of quietly proving a
  // panel against data no endpoint produces.
  return {
    id: "wo-1",
    order_no: "WO-4908",
    type: "Meter exchange",
    premise: null,
    service: "electric",
    state: "in_progress",
    outcome: null,
    mode: "standard",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-02T15:00:00+00:00",
    stands_on: "asset",
    scope: "asset",
    unit_label: null,
    external_ref: null,
    completed_at: null,
    accepted_at: null,
    accepted_by: null,
    field_data: null,
    technician: { kind: "person", name: "Sam Reyes", slug: "sam-reyes" },
    window_start: null,
    window_end: null,
    due_at: "2026-09-15T17:00:00+00:00",
    ...over,
  };
}

const WORK_ORDERS: AssetWorkOrders = {
  rows: [
    workOrder(),
    workOrder({
      id: "wo-2",
      order_no: "WO-4900",
      type: "Backflow test",
      state: "completed",
      raised_at: "2026-06-01T15:00:00+00:00",
      completed_at: "2026-06-09T15:00:00+00:00",
      due_at: null,
      technician: null,
    }),
  ],
  total: 2,
  maintenance_index: { "2026-07-02": "WO-4908" },
};

/** The key `MaintenanceTab` builds inline. Written out here rather than
 *  imported so a rename of the page's helper cannot silently stop this fixture
 *  reaching the component while every assertion still "passes" on an empty
 *  panel — the shape of `DEF-CWP-3925`. */
const workOrdersQueryKey = (assetId: string) => ["assets", assetId, "work-orders"] as const;

interface SeedOptions {
  access?: string;
  reads?: AssetReadRow[] | null;
  linkedReads?: AssetReadRow[] | null;
  /** `null` leaves the work-order query unseeded — the state every asset on
   *  this database is actually in (0 of 65 orders carry an `asset_id`). */
  workOrders?: AssetWorkOrders | null;
  /** `DEF-AST-9691` — the served `count`, in READ DATES, when it differs from
   *  the number of rows (two readings kept on one day). */
  readsTotal?: number;
  /** DEF-MET-4101: the tenant's timezone, so a case can render the SAME read
   *  east and west of UTC. Defaults to `America/Chicago` — Brazos Bend's, and
   *  west of UTC, which is where a date bug of this kind actually shows. */
  timeZone?: string;
}

/** ⚠ **THE SHAPE THIS FILE SEEDS IS THE SHAPE THE WRAPPER RETURNS, AND GETTING
 *  THAT WRONG IS WHY `AST-B-19` WAS A LIVE BREAK RATHER THAN A MISSING
 *  FEATURE.** These cases seed React Query directly, so they never cross the
 *  API boundary — which is exactly the boundary `2.237.8` moved. For four
 *  hours the server answered `{count, next, previous, results}`, this file
 *  handed the component an `AssetReadRow[]`, every case here passed, and the
 *  Reads tab threw in a browser. A paged list is seeded as `{rows, total}`
 *  now, because that is what `readListPage` hands a screen.
 *
 *  `AssetPagedLists.dom.test.tsx` is the case that CANNOT be fooled this way:
 *  it answers through a stub `ApiClient` with the recorded server body and
 *  lets the real wrapper unwrap it. Both kinds are needed — this one is fast
 *  and reaches every panel, that one is the only one that sees the wire. */
function paged<Row>(rows: readonly Row[], total?: number) {
  return { rows: rows as Row[], total: total ?? rows.length };
}

function renderDetail(path: string, asset: AssetDetail, options: SeedOptions = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(assetDetailQueryKey(asset.id), asset);
  queryClient.setQueryData(assetAssignmentsQueryKey(asset.id), paged(ASSIGNMENTS));
  queryClient.setQueryData(assetMaintenanceQueryKey(asset.id), MAINTENANCE);
  queryClient.setQueryData(entityAuditQueryKey("asset", asset.id), AUDIT);
  if (options.reads !== null) {
    queryClient.setQueryData(
      assetReadsQueryKey(asset.id),
      paged(options.reads ?? READS, options.readsTotal),
    );
  }
  if (options.linkedReads != null && asset.linked_meter != null) {
    queryClient.setQueryData(assetReadsQueryKey(asset.linked_meter.id), paged(options.linkedReads));
  }
  // ⚠ UNSEEDED BY DEFAULT, and that is the honest default rather than a
  // convenience: `work_orders.asset_id` is null on all 65 orders across all
  // three tenants, so "no job has ever been raised against this asset" is the
  // state every existing case above was written in. A case that wants rows
  // asks for them.
  if (options.workOrders != null) {
    queryClient.setQueryData(workOrdersQueryKey(asset.id), options.workOrders);
  }
  queryClient.setQueryData(queryKeys.myPermissions, permissions(options.access ?? "Full"));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route
              path="/:tenant/assets/:assetId"
              element={<AssetDetailPage timeZone={options.timeZone ?? "America/Chicago"} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-AST-004 — the S50 header and Overview", () => {
  it("US-AST-004 TC-1 / BR-AST-044: ALL THREE classifications show on the detail view", () => {
    const html = renderDetail("/assets/a-4021", detail());
    // CR-028 AST-W2 T3: classification lives INSIDE Specifications now — the
    // repeated panel above every tab is gone (B16 §4.8's measured drift).
    expect(html).not.toContain(">Classification<");
    expect(html).toContain(">Asset type<");
    expect(html).toContain(">Meter type<");
    expect(html).toContain(">Read method<");
    expect(html).toContain("Net meter");
    expect(html).toContain("AMI");
    expect(html).toContain("M-4021");
  });

  // ⛔ **DEF-1900 / BR-AST-530 — THE SIZE A PERSON READS.** The connection size
  // is recorded on AST-05 and on the S51 edit form and it is PRICED by the
  // per-size rate ladder, so a detail screen that shows every other billing
  // input and not this one leaves a clerk unable to answer *"why is this bill
  // on the 2\" rung"*.
  //
  // RED-FIRST (r11 2d), against the branch base `db84bc6` in a clean worktree:
  // `expected '…' to contain '>Connection size<'` — the row did not exist, and
  // `grep size_class 07-frontend/src/features/assets` returned nothing at all.
  it("DEF-1900 / BR-AST-530: the meter's connection size shows, and its absence is a SENTENCE not a dash", () => {
    const shown = renderDetail("/assets/a-4021", detail({ size_class: "W-2" }));
    expect(shown).toContain(">Connection size<");
    expect(shown).toContain("W-2");
    // ⚠ NOT RECORDED IS A REAL, LAWFUL STATE (BR-AST-500) AND IT SAYS WHAT IT
    // COSTS. DEF-514's own escape reason is that a null rendered as an em-dash
    // reads as "not recorded" when it can equally mean "the product cannot
    // record it" — so this one is words.
    const blank = renderDetail("/assets/a-4021", detail({ size_class: null }));
    expect(blank).toContain(">Connection size<");
    expect(blank).toContain("Not recorded");
  });

  it("DEF-1900 / BR-AST-530: a SUB-METER has no connection-size row at all", () => {
    // PO ruling 2026-08-28, judgment 4: sub-meters and devices are OUT. A
    // connection size describes the service connection a meter sits ON, and a
    // sub-meter sits behind one — so the row is ABSENT rather than dashed,
    // because a dash would claim the fact applies and is merely unknown.
    const html = renderDetail("/assets/a-4021", detail({ tab: "sub_meters", type: "sub_meter" }));
    expect(html).not.toContain(">Connection size<");
  });

  it("BR-AST-044: a MEASURING asset with no meter type reads 'not classified'; a battery reads 'not applicable'", () => {
    const unclassified = renderDetail(
      "/assets/a-4021",
      detail({
        classifications: {
          asset_type: { code: "meter", name: "Meter" },
          meter_type: null,
          read_method: { code: "ami", name: "AMI" },
        },
      }),
    );
    expect(unclassified).toContain("Not classified");
    const battery = renderDetail("/assets/a-0904", BATTERY);
    expect(battery).toContain("Not applicable to this type");
    expect(battery).not.toContain("Not classified");
  });

  it("BR-AST-026: the internal uuid is NEVER displayed — only the asset number and the serial", () => {
    const html = renderDetail("/assets/a-4021", detail());
    expect(html).toContain("M-4021");
    expect(html).toContain("3894-A2210");
    expect(html).not.toContain(">a-4021<");
  });

  it("US-AST-004 TC-1 / BR-AST-014: the extended capture-only spec set renders", () => {
    const html = renderDetail("/assets/a-4021", detail());
    for (const value of ["2S", "5.2.1", "TX-88121", "left side wall, behind gate"]) {
      expect(html).toContain(value);
    }
    // ⚠ `Every 24 months`, capital E — the `Requirement` row moved out of the
    // device-only Test & certification panel into `What's due`, which every
    // kind carries, and it reads as a sentence of its own rather than as the
    // tail of a phrase (`CR-092` wave C lane 1, screen 08).
    expect(html).toContain("Every 24 months");
    // BR-SHL-034: the panel dates still go through the shared formatter.
    expect(html).toContain("03/12/2029"); // cover ends (Warranty panel)
    expect(html).toContain("06/02/2026"); // last test
  });

  it("US-AST-004 TC-5 / BR-AST-015: register digits show the stored value, or 9 marked as the default", () => {
    expect(registerDigitsOf(5)).toBe(5);
    expect(registerDigitsOf(null)).toBe(9);
    const stored = renderDetail("/assets/a-4021", detail());
    expect(stored).toContain("Register digits");
    expect(stored).not.toContain("(default)");
    const measuringUnset = renderDetail(
      "/assets/a-4021",
      detail({ specs: { ...detail().specs, register_digits: null } }),
    );
    expect(measuringUnset).toContain("(default)");
  });

  it("US-AST-004 TC-3 / BR-AST-007: the Test-due chip sits beside an UNCHANGED status", () => {
    const html = renderDetail("/assets/a-4021", detail({ test_due: true }));
    expect(html).toContain("Test due");
    expect(html).toContain("Installed/Active");
  });

  it("BR-AST-006 / BR-AST-030: a RETIRED asset offers no lifecycle action at all", () => {
    const html = renderDetail("/assets/a-4204", RETIRED);
    expect(html).toContain("M-4204");
    expect(html).toContain("Retired");
    expect(html).toContain("Failed / unrepairable");
    expect(html).toContain("M-5100");
    for (const forbidden of [">Retire<", ">Reassign<", ">Log repair<", ">Edit<", ">Delete<"]) {
      expect(html).not.toContain(forbidden);
    }
  });

  it("US-AST-004 TC-6: a detail that cannot be read renders a STATE, never a blank shell", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.myPermissions, permissions("Full"));
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/assets/a-missing`]}>
            <Routes>
              <Route path="/:tenant/assets/:assetId" element={<AssetDetailPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain("skeleton");
    expect(html).not.toContain("data-asset-facts");
  });
});

describe("CR-028 AST-W2 T2 — the header to r10", () => {
  /**
   * ⚠ **THIS CASE ASSERTED THE ×MULTIPLIER AND THE r10 ORDER UNTIL 2026-09-13,
   * AND THE BLUEPRINT SUPERSEDES BOTH.** Page 36 of
   * `05-prototype/01 Assets Menu Blueprint.pdf` states the header in four
   * numbered rules and the first is this line, verbatim: *"the place line
   * leading with the **address** and carrying the **account**, which is served
   * today and shown nowhere · and the multiplier **gone** from it, because a ×1
   * is configuration rather than identity."* Read as an image, per B14 rule 42.
   *
   * So two things changed and each is asserted here rather than dropped: the
   * multiplier LEFT (it is the Measurement panel's, and figure 10's place line
   * carries no ×), and the ACCOUNT ARRIVED — `billing_chain.account` has been
   * on this payload since `CR-028` and reached no header, so a clerk holding a
   * disputed bill had to open a panel to learn whose meter it was.
   *
   * The old assertion is written out rather than deleted so that a reader can
   * see WHICH fact moved: `expect(rollup).toContain("×10")`.
   */
  it("T2 / page 36 rule 1: the place line leads with the ADDRESS, carries the ACCOUNT, and the multiplier is GONE", () => {
    const html = renderDetail("/assets/a-4021", detail());
    const rollup = html.slice(html.indexOf("page-header-rollup"), html.indexOf("page-header-tabs"));
    // Figure 10's own order: address · unit · account · service · Installed Mon YYYY.
    expect(rollup).toContain("1408 Elm Street");
    expect(rollup).toContain("Unit A");
    expect(rollup).toContain("A-10432 Miller, Sarah"); // the account, the point of the change
    expect(rollup).toContain("Electric");
    expect(rollup).toContain("Mar 2024"); // month-year density (BR-SHL-034 formatter)
    expect(rollup.indexOf("1408 Elm Street")).toBeLessThan(rollup.indexOf("Unit A"));
    expect(rollup.indexOf("Unit A")).toBeLessThan(rollup.indexOf("A-10432"));
    expect(rollup.indexOf("A-10432")).toBeLessThan(rollup.indexOf("Electric"));
    expect(rollup.indexOf("Electric")).toBeLessThan(rollup.indexOf("Mar 2024"));
    // The multiplier is gone in BOTH spellings — asserting only the trimmed one
    // would pass over a header that had quietly kept `×10.000000`.
    expect(rollup).not.toContain("×10");
    expect(rollup).not.toContain("10.000000");
  });

  /**
   * ⚠ **`Vega Apts` IS THE MASTER'S PREMISES AND THE LIVE CHAIN NOW WINS.**
   * Figure 12 (p39) draws a sub-meter's place line as *"Sub of E-5000 · 118
   * Bayou Bend Dr · **Unit 1** · ACC-20194 Ruth Alvarez · Water"* — and its
   * master, figure 10, sits at *Unit A* of the same building. The unit differs,
   * so the address on a sub-meter's header is the SUB-METER'S OWN walk, not its
   * master's, which is hard rule 8 read the only way it can be. The master
   * still LEADS, because it is the fact that places the thing.
   *
   * `parent_premises` survives as the fallback for a payload with no live chain
   * and no registry copy, so the negative below is what pins the precedence.
   */
  it("T2 / §5.1b: a sub-meter's line leads with its MASTER, then the premises IT is at — not the master's", () => {
    const html = renderDetail("/assets/a-8801", SUB);
    const rollup = html.slice(html.indexOf("page-header-rollup"), html.indexOf("page-header-tabs"));
    expect(rollup).toContain("Sub → M-MASTER-12");
    expect(rollup).toContain("1408 Elm Street"); // the live chain
    expect(rollup).not.toContain("Vega Apts"); // `parent_premises`, the master's
    expect(rollup.indexOf("Sub → M-MASTER-12")).toBeLessThan(rollup.indexOf("1408 Elm Street"));
  });

  it("T2 / §5.1b: an inventory asset's sub-line reads 'In inventory · unassigned'", () => {
    const html = renderDetail("/assets/a-0904", BATTERY);
    const rollup = html.slice(html.indexOf("page-header-rollup"), html.indexOf("page-header-tabs"));
    expect(rollup).toContain("In inventory · unassigned");
  });

  it("T2 / §5.1b (A): a device with a test cadence relabels the repair action 'Log test'", () => {
    const html = renderDetail("/assets/a-3301", BACKFLOW);
    expect(html).toContain("Log test");
    expect(html).not.toContain(">Log repair<");
    // ⚠ **THE KICKER CARRIED THE ASSET NUMBER UNTIL 2026-09-13 AND PAGE 36
    // TAKES IT OUT** — header rule 1, verbatim: *"kicker without the number ·
    // the number once, in the title"*. It was in both and adjacent, which makes
    // neither copy authoritative. The kicker is the device's TYPE alone here:
    // the meter-type leg is null on a non-measuring kind and filters out.
    // Asserted INSIDE the kicker, because `BF-3301` is legitimately all over
    // this page and a page-wide check could not tell the two places apart.
    const kicker = html.slice(html.indexOf("kicker"), html.indexOf("<h1"));
    expect(kicker).toContain("Backflow preventer");
    expect(kicker).not.toContain("BF-3301");
    expect(html).toContain("<h1 class=\"text-h2\">BF-3301</h1>");
  });
});

describe("CR-028 AST-W2 T3 — the Overview panels, re-cut by CR-092 wave C", () => {
  it("T3: the Device panel carries the classifications and the net fold, and the asset number and status are said ONCE", () => {
    const html = renderDetail("/assets/a-4021", detail());
    // ⚠ **THIS CASE ASSERTED `>Asset #<` AND THE STATUS PILL INSIDE THE PANEL
    // UNTIL 2026-09-12, AND BOTH WERE `AST-R-09` VIOLATIONS** — *a fact is
    // said once*. The number is the title and the status is the header pill,
    // and in both cases the header carries the COMPLETE value, which is the
    // test for a summary against a repeat. Screen 08's carry-over table moves
    // each to the header and removes the duplicate row.
    expect(html).not.toContain(">Asset #<");
    expect(html).toContain(">Device<");
    expect(html).toContain("net (bidirectional)"); // the Type fold, r10's wording
    expect(html).toContain(">Service<"); // now on Assignment, where the chain is
    // The status pill renders EXACTLY once, in the header.
    expect(html.split("Installed/Active").length - 1).toBe(1);
  });

  it("T3: the Assignment panel carries the LIVE chain — account included (BR-AST-039)", () => {
    const html = renderDetail("/assets/a-4021", detail());
    expect(html).toContain('href="/brazosbend/premises/p-101"');
    expect(html).toContain('href="/brazosbend/premises/units/u-101a"');
    expect(html).toContain("A-10432 · Miller, Sarah");
    expect(html).not.toContain("Arrives with the Accounts module"); // stale copy gone
    // A net meter states its export channel in the panel.
    expect(html).toContain("Net metering");
    // Reassign lives in the panel as well as the header.
    expect((html.match(/Reassign/g) ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it("T3: an unassigned asset's panel reads Inventory (unassigned) and offers Assign", () => {
    const html = renderDetail("/assets/a-0904", BATTERY);
    expect(html).toContain("Inventory (unassigned)");
    expect(html).toContain("Assign");
  });

  it("T3: Cost & value — supplier, $164.00 at 2 dp, term dash; the warranty DATE moves to What's due", () => {
    const html = renderDetail("/assets/a-4021", detail());
    // The `Warranty & supplier` panel is gone: screen 08 splits it, the
    // purchase facts to `Cost & value` and the date that EXPIRES to
    // `What's due`, because a thing that falls due is a different question
    // from what the estate cost.
    expect(html).not.toContain("Warranty &amp; supplier");
    expect(html).toContain("Cost &amp; value");
    expect(html).toContain("What&#x27;s due");
    expect(html).toContain("Itron Direct");
    expect(html).toContain("$164.00"); // stored 164.0000, DISPLAYED 2 dp (rule 2)
    expect(html).not.toContain("164.0000");
    expect(html).toContain("Warranty term");
    expect(html).toContain("Covered");
    // Expired is the other pill, not this asset's.
    expect(html).not.toContain(">Expired<");
  });

  it("T3: Warranty pill reads Expired when cover has ended, dash when none on record", () => {
    const expired = renderDetail(
      "/assets/a-4021",
      detail({ valuation: { ...detail().valuation, warranty_covered: false } }),
    );
    expect(expired).toContain("Expired");
    const none = renderDetail("/assets/a-0904", BATTERY);
    expect(none).not.toContain(">Covered<");
    expect(none).not.toContain(">Expired<");
  });

  it("T3: Lifecycle — age 2 yrs 5 mo · expected life · certification due · forecast 2032", () => {
    const html = renderDetail("/assets/a-4021", detail());
    expect(html).toContain("2 yrs 5 mo"); // age_months 29, the worked figure
    expect(html).toContain("8 years");
    expect(html).toContain("06/02/2028"); // certification due, the ONE formatter
    expect(html).toContain("2032"); // replacement forecast = install + life
    // §10-D3: NO GL sentence anywhere on this screen.
    expect(html).not.toContain("5300");
    expect(html).not.toContain("5400");
  });
});

describe("CR-028 AST-W2 T4 — the Reads tab, SERVED (DEF-475 closed)", () => {
  it("T4 / BR-AST-029: the net pair renders folded — Import and Export columns, units explicit", () => {
    const html = renderDetail("/assets/a-4021?tab=reads", detail());
    expect(html).toContain("<table");
    expect(html).toContain(">Import<");
    expect(html).toContain(">Export (net)<");
    expect(html).toContain("702");
    expect(html).toContain("141");
    expect(html).toContain("kWh");
    expect(html).toContain(">Source<");
    // The stale arrives-with copy is GONE — the tab is served now.
    expect(html).not.toContain("settings-arrives");
    expect(html).not.toContain("DEF-475");
    // No money on any read surface (BR-AST-016/025).
    expect(html).not.toContain("$");
  });

  it("T4: a non-net meter draws no Export column at all", () => {
    const flat = detail({ net_metering: false, type: "meter", type_name: "Meter" });
    const html = renderDetail("/assets/a-4021?tab=reads", flat, {
      reads: [{ ...READS[1] }],
    });
    expect(html).toContain("<table");
    expect(html).not.toContain(">Export (net)<");
    expect(html).toContain("684");
  });

  it("T4: an asset with no reads says 'No reads yet' — an honest empty, distinct from unserved", () => {
    const html = renderDetail("/assets/a-4021?tab=reads", detail(), { reads: [] });
    expect(html).toContain("No reads yet");
    expect(html).not.toContain("<table");
  });
});

// ── DEF-MET-4101 ────────────────────────────────────────────────────────────
//
// **THE CASE THAT WAS MISSING, AND ITS ABSENCE IS THE WHOLE DEFECT.** Every
// meter read drew ONE DAY EARLY for every tenant west of UTC — the entire reads
// history, on every screen that shows one — and roughly 10,300 automated checks
// passed over it for three weeks.
//
// ⚠ **THE REASON NOTHING CAUGHT IT IS VISIBLE IN THIS VERY FILE.** The harness
// above has ALWAYS mounted the page at `America/Chicago`, and the fixture has
// always carried the value the server actually sent. Both halves of the bug were
// sitting here. What was missing was an assertion on the DRAWN DATE: the suite
// checked quantities, units, columns and copy, and never once the day. Every
// check in the repo compared UTC dates and the screen rendered local ones, so
// the two never met — a walkthrough even asserted this read through `fetch()`
// from inside the browser and went green, because the PAYLOAD was right. A check
// that fetches JSON from inside a browser is not a check on what the browser
// DREW.
//
// So these two cases assert the day, in both hemispheres, and the pair is
// deliberate: **a fix that is right for Chicago and wrong for Berlin is half a
// fix**, and only the second case can tell you so.
describe("DEF-MET-4101 — a read's date is a CALENDAR DATE, in every tenant timezone", () => {
  // What the server serves, from `assets.selectors._fold_row`: the read's own
  // calendar day. Stored as `2026-09-03T00:00:00Z`, because that midnight is
  // what makes the per-date uniqueness key work — but it IS a date.
  const STORED_DAY = "09/03/2026";
  const DAY_BEFORE = "09/02/2026";
  const DAY_AFTER = "09/04/2026";

  it("draws the read's OWN day for a tenant WEST of UTC (America/Chicago)", () => {
    const html = renderDetail("/assets/a-4021?tab=reads", detail());
    expect(html).toContain(STORED_DAY);
    // The defect, named: midnight UTC converted into Chicago is the day before.
    expect(html).not.toContain(DAY_BEFORE);
  });

  it("draws the SAME day for a tenant EAST of UTC (Europe/Berlin)", () => {
    const html = renderDetail("/assets/a-4021?tab=reads", detail(), {
      timeZone: "Europe/Berlin",
    });
    expect(html).toContain(STORED_DAY);
    expect(html).not.toContain(DAY_AFTER);
  });

  it("draws the identical day EAST and WEST — which is what a calendar date MEANS", () => {
    // The strongest statement of the rule, and the one a future refactor will
    // trip over first: two tenants on opposite sides of UTC, one read, one day.
    // A serve-side regression to an instant fails this even if someone has
    // "fixed" the west-of-UTC case by shifting it the other way.
    const chicago = renderDetail("/assets/a-4021?tab=reads", detail());
    const berlin = renderDetail("/assets/a-4021?tab=reads", detail(), {
      timeZone: "Europe/Berlin",
    });
    const dates = (html: string) => html.match(/\d{2}\/\d{2}\/\d{4}/g) ?? [];
    expect(dates(chicago).length).toBeGreaterThan(0);
    expect(dates(chicago)).toEqual(dates(berlin));
  });
});

describe("CR-028 AST-W2 T5 — the Audit tab INLINE (the CR-23/DEF-579 pattern)", () => {
  it("T5 / BR-AUD-010: the tab RENDERS the asset's own rows — When · Who · What changed — and still links", () => {
    const html = renderDetail("/assets/a-4021?tab=audit", detail());
    expect(html).toContain("<table");
    // ⚠ **`Actor · Action` BECAME `Who · What changed · From · To` ON
    // 2026-09-10 (`DEF-4740`), AND IT MOVED HERE BECAUSE THE TAB IS SHARED.**
    // `BR-AUD-010` says there is ONE audit surface, so the asset detail draws
    // metering's `AuditTab`; the premises blueprint renamed the column and
    // pulled the values into columns, and this screen gets both.
    expect(html).toContain(">When<");
    expect(html).toContain(">Who<");
    expect(html).toContain(">What changed<");
    expect(html).toContain(">From<");
    expect(html).toContain(">To<");
    expect(html).not.toContain(">Actor<");
    expect(html).toContain("asset.maintenance_logged");
    expect(html).toContain("Dana Whitfield");
    expect(html).toContain("System"); // BR-AUD-003: a null actor is named
    // BR-AUD-010's second half: the full-log link STAYS.
    expect(html).toContain("/audit-log?f.entity_type=asset&amp;f.entity_id=a-4021");
    // The old link-only body is gone.
    expect(html).not.toContain("Open the audit log for this asset");
  });
});

describe("CR-028 AST-W2 T7 — maintenance: cost captured, totalled, NEVER posted", () => {
  /**
   * ⚠ **THE ADDRESS MOVED ON 2026-09-13 AND THE RULE DID NOT.** Screen 12 of
   * the blueprint merges Maintenance into `Work & maintenance` at
   * `/:tenant/assets/{id}?tab=work` (p58, read as an image) and splits it into
   * two sub-tabs — figure 18 draws `Open work | History` under the tab strip,
   * and figure 19's caption makes `Open work` the default *"the half you can
   * act on, so it is the half you land on"*. The history table therefore only
   * renders at `?tab=work&section=history`, and a case that keeps asking for
   * `?tab=maintenance` lands on the OPEN half where none of these columns are.
   */
  it("T7: Date · Type · Technician · Detail · Work order · Cost · Outcome, and the lifetime line", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=history", detail());
    expect(html).toContain("Maintenance history");
    for (const header of [">Technician<", ">Work order<", ">Cost<", ">Outcome<"]) {
      expect(html).toContain(header);
    }
    expect(html).toContain("Ray Delgado"); // T6: the NAME, not u-ray's uuid
    expect(html).toContain("$88.40"); // stored 88.4000, displayed 2 dp
    expect(html).toContain("$31.00");
    expect(html).toContain("Lifetime maintenance $119.40"); // the server's sum
    expect(html).toContain("+ Log repair");
    // §10-D3, asserted as absences: no GL account, no posting, no Finance link.
    expect(html).not.toContain("5300");
    expect(html).not.toContain("Finance");
    expect(html).not.toContain("O&amp;M");
  });

  /**
   * ⚠ **THIS CASE IS INVERTED, AND THE OLD ASSERTION IS WRITTEN OUT HERE
   * RATHER THAN DELETED (`DEF-MET-4966`, 2026-09-12).**
   *
   * It used to read `expect(html).not.toContain("Raise work order")`, with the
   * comment *"No wo storage exists yet (Work is R5)"*. **That premise died the
   * day `apps/work` shipped**: `work_orders.asset_id` is a column, 27
   * migrations stand behind it, `apps/work/asset_door.py` is named for this
   * exact door, and `POST /work-orders` with `asset_id` has been live since
   * `CR-070` wave M. `BR-WRK-056` is CONFIRMED and names four ways in — and
   * the two on this screen were never built, while this green assertion held
   * one of them shut.
   *
   * **A hold with no test that fires when it expires is a promise nobody is
   * keeping** (hard-won law 2's mirror). This one had the opposite: a test
   * that fired only if somebody tried to KEEP the promise. So the case is kept
   * at its own address, with its own id, asserting the thing the rule actually
   * wants — because deleting it would leave no record that the door was ever
   * pinned shut, and that record is the whole finding.
   */
  it("DEF-MET-4966 / BR-WRK-056: the Maintenance tab OFFERS the raise door — the hold expired when Work shipped", () => {
    const html = renderDetail("/assets/a-4021?tab=maintenance", detail());
    expect(html).toContain("Raise work order");
    // The destination, by ADDRESS — the assertion `DEF-WRK-4051` exists for.
    // A control whose label is right and whose href is `//assets/…` reads as a
    // perfectly good string to `toContain` and opens another host.
    expect(html).toContain("/brazosbend/assets/a-4021/work-orders/new");
  });
});

describe("CR-028 AST-W2 T8 — the device model (B16 §5.1b)", () => {
  /**
   * ⚠ **THE COUNT DID NOT MOVE; THE ID AND THE LABEL DID (2026-09-13).** The
   * blueprint's page 40 draws a backflow preventer's own tab strip and it reads
   * **`Overview · Assignment history · Work & maintenance · Audit`** — still
   * four, and the device fork `Tests & maintenance` is gone: one label on every
   * kind. The id `maintenance` became `work` with the merge (screen 12, p58),
   * and it survives as a deliberate alias, asserted below.
   */
  it("T8 (A): a plain device has FOUR tabs — no Reads — and Work & maintenance", () => {
    expect(assetDetailTabsFor(BACKFLOW)).toEqual([
      "overview",
      "assignments",
      "work",
      "audit",
    ]);
    const html = renderDetail("/assets/a-3301", BACKFLOW);
    expect(html).not.toContain(">Reads<");
    expect(html).toContain("Work &amp; maintenance");
    // The device-only fork is gone rather than renamed — p40 draws the same
    // words a meter's strip carries.
    expect(html).not.toContain("Tests &amp; maintenance");
  });

  it("T8 (A): a device's testing calendar lives in What's due — requirement · last test · next due · overdue", () => {
    const html = renderDetail("/assets/a-3301", BACKFLOW);
    // The device-only `Test & certification` panel is folded into `What's due`,
    // which EVERY kind carries — `AST-R-11`: the panel order never varies by
    // kind, a kind that skips a panel closes the gap.
    expect(html).not.toContain("Test &amp; certification");
    expect(html).toContain("What&#x27;s due");
    expect(html).toContain("Every 12 months");
    expect(html).toContain("06/02/2025"); // last test
    expect(html).toContain("06/02/2026"); // next due
    expect(html).toContain("Overdue"); // test_due — the derived state
  });

  it("T8 (B): an exporting inverter has FIVE tabs — Export replaces Reads", () => {
    expect(assetDetailTabsFor(INVERTER)).toEqual([
      "overview",
      "export",
      "assignments",
      "work",
      "audit",
    ]);
    const html = renderDetail("/assets/a-1204?tab=export", INVERTER, { linkedReads: READS });
    expect(html).toContain(">Export<");
    expect(html).not.toContain(">Reads<");
    // The linked meter's records, read-only, with the measured-by header.
    expect(html).toContain("Measured by");
    expect(html).toContain("M-4310 · net →");
    expect(html).toContain('href="/brazosbend/assets/a-4310"');
    expect(html).toContain("141"); // the export quantity
    expect(html).toContain("kWh");
  });

  it("T8: the five measuring tabs still number five, and the strip stays URL state", () => {
    expect([...ASSET_DETAIL_TABS]).toEqual([
      "overview",
      "reads",
      "assignments",
      "work",
      "audit",
    ]);
    expect(assetDetailTabsFor(detail())).toEqual([...ASSET_DETAIL_TABS]);
    expect(assetDetailTabFrom(null)).toBe("overview");
    // ⚠ **`maintenance` IS A DELIBERATE ALIAS, NOT AN ID.** It asserted
    // `toBe("maintenance")` until 2026-09-13. The merge renamed the tab and the
    // old id is in live bookmarks, in this repository's own walkthroughs and in
    // whatever a beta tester has open right now — so it MAPS rather than
    // falling through to Overview, which is what a silently-lost link looks
    // like. `selectTab` only ever writes the new id, so the address a person
    // copies out of the bar is the current one.
    expect(assetDetailTabFrom("maintenance")).toBe("work");
    expect(assetDetailTabFrom("work")).toBe("work");
    expect(assetDetailTabFrom("nonsense")).toBe("overview");
    // A tab another kind owns falls back rather than rendering a dead pane.
    expect(assetDetailTabFrom("export", assetDetailTabsFor(detail()))).toBe("overview");
    expect(assetDetailTabFrom("reads", assetDetailTabsFor(BACKFLOW))).toBe("overview");
  });

  it("T8 / §5.1b: sub-meter specs add Parent / master as a LINK and the allocation share", () => {
    const html = renderDetail("/assets/a-8801", SUB);
    expect(html).toContain(">Parent / master<");
    expect(html).toContain('href="/brazosbend/assets/a-master-12"');
    expect(html).toContain("M-MASTER-12");
    expect(html).toContain(">Allocation share<");
    expect(html).toContain("Metered (no share)"); // blank = metered, never 0%
    const allocated = renderDetail(
      "/assets/a-8801",
      detail({
        ...SUB,
        specs: { ...SUB.specs, allocation_share_pct: "25.000000" },
      }),
    );
    // Hard rule 2: a percentage DISPLAYS at 2 dp (stored 6).
    expect(allocated).toContain("25.00%");
  });
});

describe("US-AST-006 — assignment history and append-only law", () => {
  it("US-AST-006 TC-1 / BR-AST-017: history is newest-first, current on top, append-only", () => {
    const html = renderDetail("/assets/a-4021?tab=assignments", detail());
    expect(html).toContain("Unit A");
    expect(html).toContain("1408 Elm Street");
    // ⚠ **IT WAS `<strong>Current</strong>` UNTIL 2026-09-13.** Figure 17 (p56,
    // read as an image) draws a green outlined pill in the TO cell, which is
    // how every other state in this product is drawn; a `<strong>` was the only
    // bold word on the screen and read as emphasis rather than as a state.
    expect(html).toContain('<span class="pill bg-success-100 text-success-700">Current</span>');
    expect(html).not.toContain("<strong>Current</strong>");
    expect(html).toContain("Dana Whitfield"); // T6: the resolved name renders
    expect(html).toContain("System");
    expect(html).toContain("append-only and never overlaps");
    expect(html).not.toContain("<input");
    expect(html.toLowerCase()).not.toContain("<form");
  });

  /**
   * The Work & maintenance tab's HISTORY section — the page's header and its
   * action block sit above it and are not this rule's.
   *
   * ⚠ **BOUNDED AT BOTH ENDS SINCE 2026-09-13, AND THAT IS THE POINT.** This
   * used to slice from the heading to the END of the document, which was a real
   * scope only as long as the history panel was the last thing on the page. It
   * is now one of two sub-tab panels (screen 12, figure 18), so the bound is the
   * panel's own `</section>` and the helper asserts BOTH ends were found —
   * `indexOf` returning -1 makes `slice` silently hand back the whole rest of
   * the page, which is hard-won law 7's *check that cannot fail*.
   */
  function maintenanceLog(html: string): string {
    const from = html.indexOf("<h3>Maintenance history</h3>");
    expect(from).toBeGreaterThan(-1);
    const to = html.indexOf("</section>", from);
    expect(to).toBeGreaterThan(from);
    return html.slice(from, to);
  }

  it("US-AST-006 TC-2/TC-5 / BR-AST-018: the maintenance log offers no edit or delete", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=history", detail());
    expect(html).toContain("Annual accuracy check — passed");
    expect(html).toContain("Inspection");
    expect(html).toContain("06/02/2026");
    expect(html).toContain("never edited or deleted");
    // ⚠ **SCOPED TO THE LOG, WHICH IS WHAT BR-AST-018 IS ABOUT.** These two
    // assertions read the WHOLE page until 2026-09-12, and `AST-B-12` put an
    // Edit button in the asset HEADER — a control that corrects the asset's
    // SPECIFICATION and cannot touch a maintenance entry, since the API defines
    // no verb for one. A page-wide `not.toContain(">Edit<")` therefore failed on
    // a change the rule it cites has nothing to say about. The rule is that the
    // LOG is append-only, so the log is what is read.
    const log = maintenanceLog(html);
    expect(log).not.toContain(">Edit<");
    expect(log).not.toContain(">Delete<");
  });

  it.todo(
    "US-AST-006 TC-4: a logged `test` entry moves the Overview's last-test date and clears the chip — the server owns both; the round trip is browser scope",
  );
  it.todo(
    "US-AST-006 TC-6 (isolation): a cross-tenant asset's tabs answer not-found — server/RLS scope (G5)",
  );
});

describe("US-SHL-020 — S16 through the shared page header (BR-SHL-044)", () => {
  function headerActions(html: string): string {
    return html.slice(html.indexOf("page-header-actions"), html.indexOf("page-header-tabs"));
  }

  it("US-SHL-020 TC-3 / BR-SHL-044 (c): the Audit tab carries NO header action, and the row still renders", () => {
    const audit = renderDetail("/assets/a-4021?tab=audit", detail());
    expect(audit).toContain("page-header-actions");
    expect(headerActions(audit)).not.toContain('data-variant="primary"');
    const overview = renderDetail("/assets/a-4021", detail());
    expect(headerActions(audit)).toBe(headerActions(overview));
  });

  it("US-SHL-020 TC-4: the header carries Reassign · Log repair · Retire; the History section's own control is in its BODY", () => {
    // The `+ Log repair` control lives under the HISTORY half of the merged tab
    // — it adds a row to that log. `?tab=work&section=history` is its address
    // since the merge (screen 12, p58).
    const maintenance = renderDetail("/assets/a-4021?tab=work&section=history", detail());
    const actions = headerActions(maintenance);
    expect(actions).toContain("Reassign");
    expect(actions).toContain("Log repair");
    expect(actions).toContain("Retire");
    expect(maintenance).toContain("+ Log repair");
    expect(maintenance.lastIndexOf("Log repair")).toBeGreaterThan(
      maintenance.indexOf("page-header-tabs"),
    );
  });

  it("US-SHL-020 TC-5: a DETAIL screen renders the back link, above everything else", () => {
    const html = renderDetail("/assets/a-4021", detail());
    expect(html).toContain("page-header-back");
    expect(html).toContain("← Assets");
    expect(html).toContain('href="/brazosbend/assets"');
    expect(html.indexOf("page-header-back")).toBeLessThan(html.indexOf("kicker"));
  });

  it("US-SHL-020 TC-6: the detail header can never offer two primary actions", () => {
    for (const tab of ASSET_DETAIL_TABS) {
      const actions = headerActions(renderDetail(`/assets/a-4021?tab=${tab}`, detail()));
      expect(actions).not.toContain('data-variant="primary"');
    }
  });

  it("US-SHL-020: back-link → kicker → H1 → roll-up → strip, in the skeleton's order", () => {
    const html = renderDetail("/assets/a-4021", detail());
    // ⚠ `"<h1"` rather than `"<h1>"` — B14 rule 40 (2026-09-12) put a size class
    // on the page-head title, and a matcher keyed to the bare tag stops finding
    // an element that is right there. A negative index compares as less-than
    // everything, so the index is asserted non-negative FIRST or this shape
    // reports the order as correct over a missing title.
    const title = html.indexOf("<h1");
    expect(title).toBeGreaterThan(-1);
    expect(html.indexOf("kicker")).toBeLessThan(title);
    expect(title).toBeLessThan(html.indexOf("page-header-rollup"));
    expect(html.indexOf("page-header-rollup")).toBeLessThan(html.indexOf("page-header-tabs"));
    // ⚠ **THE KICKER READ `Net meter · M-4021 · AMI` UNTIL 2026-09-13.** Page
    // 36 header rule 1: *"kicker without the number · the number once, in the
    // title"*. Asserted inside the kicker, so the number being in the `<h1>`
    // right below cannot make this pass.
    const kicker = html.slice(html.indexOf("kicker"), title);
    expect(kicker).toContain("Net meter · AMI");
    expect(kicker).not.toContain("M-4021");
    expect(html).toContain("<h1 class=\"text-h2\">M-4021</h1>");
  });

  it("US-SHL-020 / BR-AST-030: a RETIRED asset's header is a status pill and nothing else", () => {
    // ⚠ **THE CLAIM IS UNCHANGED; THE SLICE MOVED (DEF-966, second half).** The
    // pill used to be the first child of `.page-header-actions` and now renders
    // with the IDENTITY, because a status is a fact about the record and not an
    // action — which is what let BIL-02's action row grow wide enough to wrap.
    // So "a status pill and nothing else" is now asserted in two halves: the
    // pill is in the HEADER, and the ACTION ROW holds none of the four
    // lifecycle buttons.
    const html = renderDetail("/assets/a-4204", RETIRED);
    const header = html.slice(html.indexOf("page-header"), html.indexOf("page-header-tabs"));
    expect(header).toContain("Retired");
    expect(headerActions(html)).not.toContain("Retired");
    for (const forbidden of [">Retire<", ">Reassign<", ">Log repair<", ">Delete<"]) {
      expect(headerActions(html)).not.toContain(forbidden);
    }
  });

  it("US-SHL-020 / BR-SHL-025: the header's lifecycle controls survive DISABLED, never hidden", () => {
    const actions = headerActions(renderDetail("/assets/a-4021", detail(), { access: "View" }));
    expect(actions).toContain("Reassign");
    expect(actions).toContain("disabled");
    expect(actions).toContain("Your role can view this but not change it.");
  });

  it("US-SHL-020: S16 draws no head or tab strip of its own any more (DEF-021)", () => {
    const html = renderDetail("/assets/a-4021", detail());
    expect(html).toContain("page-header");
    expect(html).not.toContain("ast-head");
    expect(html).not.toContain("ast-tabs");
  });

  it.todo(
    "US-SHL-020 TC-3 (interaction): moving Overview → Audit leaves the header's own height unchanged — a rendered-height assertion needs a browser (Playwright)",
  );
});

// ══════════════════════════════════════════════════════════════════════════
// CR-092-BRC01 lane 2 — the raise-work-order door, the work list, and the
// register column. Six defect rows, and every case below was proved RED
// against `ce623f444` before a line of the fix was written.
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-MET-4965 / BR-WRK-056 — the Assets door has four ways in, and two are on THIS screen", () => {
  function headerActions(html: string): string {
    return html.slice(html.indexOf("page-header-actions"), html.indexOf("page-header-tabs"));
  }

  it("DEF-MET-4965: the header offers Raise work order, on every tab, pointing at the door's own address", () => {
    // `TC-3` asserts the header action block is byte-identical across tabs, so
    // this control belongs to all five or to none.
    for (const tab of ASSET_DETAIL_TABS) {
      const actions = headerActions(renderDetail(`/assets/a-4021?tab=${tab}`, detail()));
      expect(actions).toContain("Raise work order");
      expect(actions).toContain('href="/brazosbend/assets/a-4021/work-orders/new"');
      // `TC-6`: the detail header never offers a second primary action.
      expect(actions).not.toContain('data-variant="primary"');
    }
  });

  it("DEF-MET-4965: the header keeps its drawn order — Raise work order leads, Retire still trails", () => {
    const actions = headerActions(renderDetail("/assets/a-4021", detail()));
    expect(actions.indexOf("Raise work order")).toBeLessThan(actions.indexOf("Reassign"));
    expect(actions.indexOf("Reassign")).toBeLessThan(actions.indexOf("Retire"));
  });

  it("BR-AST-534: a RETIRED asset shows the control DISABLED with its reason — never hidden", () => {
    const html = renderDetail("/assets/a-4204", RETIRED);
    const actions = headerActions(html);
    // The ruling, on screen: shown, disabled, carrying the reason.
    expect(actions).toContain("Raise work order");
    expect(actions).toContain("disabled");
    expect(actions).toContain("This asset is retired.");
    // …and it is NOT a link a middle-click could still open.
    expect(actions).not.toContain('href="/brazosbend/assets/a-4204/work-orders/new"');
    // BR-AST-030 is untouched: the four lifecycle verbs stay gone.
    for (const forbidden of [">Retire<", ">Reassign<", ">Log repair<", ">Delete<"]) {
      expect(actions).not.toContain(forbidden);
    }
  });

  it("BR-SHL-025 still wins on a role without write, and the state reason takes the retired case", () => {
    const viewOnly = headerActions(
      renderDetail("/assets/a-4021", detail(), { access: "View" }),
    );
    expect(viewOnly).toContain("Raise work order");
    expect(viewOnly).toContain("Your role can view this but not change it.");
    const retiredViewOnly = headerActions(
      renderDetail("/assets/a-4204", RETIRED, { access: "View" }),
    );
    // One control, one sentence: the STATE reason is true for every role and
    // does not change when permissions do, so it is the one shown.
    expect(retiredViewOnly).toContain("This asset is retired.");
  });
});

describe("DEF-MET-4967 / AST-B-18 — the work-order list is RENDERED, not fetched and discarded", () => {
  /**
   * ⚠ **THESE FOUR CASES WENT ON PASSING THROUGH THE 2026-09-13 REBUILD AND
   * THREE OF THEM HAD STOPPED CHECKING ANYTHING (hard-won law 7).**
   *
   * They scoped themselves with
   * `html.slice(html.indexOf("Open work"), html.indexOf("Maintenance history"))`
   * — which was a real bound only while both headings sat on ONE page. Screen
   * 12 split the tab into two sub-tabs (figure 18), so on the default half the
   * history heading is simply absent, `indexOf` returns **-1**, and
   * `slice(start, -1)` hands back **the entire rest of the document**.
   * Measured on the failing tree: page 8,160 chars, `Open work` at 4,976,
   * `Maintenance history` at **-1**, slice length **3,183** — everything from
   * the heading to the last character. The comment three lines below this one
   * names the exact false pass the bound existed to prevent, and the bound had
   * silently become that false pass.
   *
   * **Nothing went red**, which is the whole lesson: a slice whose end index is
   * missing degrades into no scope at all rather than into an error.
   *
   * Fixed in two ways, both needed. The ADDRESS is now the canonical
   * `?tab=work&section=open` rather than the `?tab=maintenance` alias, so the
   * case says which half it is reading; and the bound is the panel's own
   * `</section>`, with BOTH ends asserted found.
   */
  function openWork(html: string): string {
    const from = html.indexOf("<h3>Open work</h3>");
    expect(from).toBeGreaterThan(-1);
    const to = html.indexOf("</section>", from);
    expect(to).toBeGreaterThan(from);
    return html.slice(from, to);
  }

  it("DEF-MET-4967: the Open work panel draws the order, its type, state, dates and who has it", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=open", detail(), {
      workOrders: WORK_ORDERS,
    });
    expect(html).toContain("Open work");
    // ⚠ SCOPED TO THE PANEL, not to the page. `>Technician<` is also the
    // Maintenance history's own column header, so a page-wide `toContain`
    // would pass over an Open work panel that drew no such column at all —
    // a check that cannot fail (hard-won law 7).
    const panel = openWork(html);
    // B14 rule 31: the ORDER NUMBER, never the uuid.
    expect(panel).toContain("WO-4908");
    expect(panel).not.toContain("wo-1");
    expect(panel).toContain("Meter exchange");
    // The three facts `AST-B-18` asks for, two of which were already served.
    expect(panel).toContain(">Expected completion<");
    expect(panel).toContain(">Technician<");
    expect(panel).toContain("Sam Reyes");
    expect(panel).toContain("09/15/2026");
    // Figure 18 draws the order number as a LINK into Work's own screen, and
    // the route keys on the NUMBER — so no id travels in the href either.
    expect(panel).toContain('href="/brazosbend/work/orders/WO-4908"');
    // The drawing's own two sentences.
    expect(panel).toContain("Jobs raised and not yet done.");
    expect(panel).toContain("Raised in Work, read here.");
  });

  it("DEF-MET-4967: an unassigned job says so — the product's sentence, not a blank cell", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=open", detail(), {
      workOrders: {
        ...WORK_ORDERS,
        rows: [workOrder({ technician: null, state: "blocked" })],
      },
    });
    const panel = openWork(html);
    expect(panel).toContain("Nobody yet");
    expect(panel).toContain("Blocked");
  });

  it("DEF-MET-4967: a DONE order is not open work — the panel is what is outstanding", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=open", detail(), {
      workOrders: WORK_ORDERS,
    });
    const panel = openWork(html);
    expect(panel).toContain("WO-4908");
    expect(panel).not.toContain("WO-4900");
  });

  it("DEF-MET-4967: no job raised yet is a SENTENCE, and the raise control still draws", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=open", detail());
    const panel = openWork(html);
    expect(panel).toContain("No open jobs on this asset.");
    // ⚠ **SCOPED TO THE PANEL, AND IT WAS PAGE-WIDE UNTIL 2026-09-13.** The
    // HEADER carries a `Raise work order` button on every tab (`DEF-MET-4965`),
    // so a page-wide check here passed whether or not the empty panel kept its
    // own door — the second of `BR-WRK-056`'s two ways in on this screen, and
    // the one this case is named for.
    expect(panel).toContain("Raise work order");
  });
});

describe("DEF-MET-4969 — a register is named in words, never as the served code", () => {
  it("DEF-MET-4969: the reads table names the register, and only when there is more than one", () => {
    const multi = renderDetail("/assets/a-4021?tab=reads", detail(), {
      reads: [
        { ...READS[0], read_id: "r-3", channel: "tou_on", consumption: "412.000000" },
        { ...READS[0], read_id: "r-4", channel: "tou_off", consumption: "290.000000" },
      ],
    });
    expect(multi).toContain(">Channel<");
    expect(multi).toContain("On-peak");
    expect(multi).toContain("Off-peak");
    // The code itself never reaches a clerk.
    expect(multi).not.toContain("tou_on");
    expect(multi).not.toContain("tou_off");

    // One register — no column of one repeated word, the same reasoning the
    // Export column already follows.
    const single = renderDetail("/assets/a-4021?tab=reads", detail());
    expect(single).not.toContain(">Channel<");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-004@9f23548 (story+rules snapshot hash — EP-AST-02; co-story US-AST-006@9f23548; co-packet US-SHL-020@9941789 — EP-SHL-01) + CR-028 AST-W2 (B16 §5.1/§5.1b)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 (path-tenancy · US-SHL-020 conversion) · REWRITTEN 2026-08-22 by the CR-028 AST-W2 lane (tests FIRST — the new describe blocks ran RED against the pre-change page; the pre-existing blocks were amended only where the ratified surface itself moved: the classification panel folded into Specifications, the Reads tab now SERVED (DEF-475), the Audit tab inline (BR-AUD-010/DEF-579's premises pattern), the account leg live, the "03/12/2024" rollup date now r10's "Mar 2024")
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report (tsc · eslint · vitest run quoted there)
// exceptions: E4 the not-found path still asserts the LOADING state (renderToStaticMarkup cannot run the query); E4 the isolation halves are the G5 suite's; E4 interaction cases stay honest it.todo (browser scope)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("DEF-AST-9686 — a finished job stays on the meter's Work tab", () => {
  function finished(html: string): string {
    const from = html.indexOf("<h3>Finished work</h3>");
    expect(from).toBeGreaterThan(-1);
    const to = html.indexOf("</section>", from);
    expect(to).toBeGreaterThan(from);
    return html.slice(from, to);
  }

  it("History lists the done job, accepted, with its completion date", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=history", detail(), {
      workOrders: {
        ...WORK_ORDERS,
        rows: [
          workOrder(),
          workOrder({
            id: "wo-50",
            order_no: "WO-0050",
            type: "Re-read",
            state: "completed",
            completed_at: "2026-10-05T15:00:00+00:00",
            accepted_at: "2026-10-05T16:00:00+00:00",
            accepted_by: "Dana Whitfield",
            technician: { kind: "person", name: "R. Patel", slug: "r-patel" },
          }),
        ],
      },
    });
    const panel = finished(html);
    expect(panel).toContain('href="/brazosbend/work/orders/WO-0050"');
    expect(panel).toContain("Re-read");
    expect(panel).toContain("Accepted");
    expect(panel).toContain("10/05/2026");
    expect(panel).toContain("R. Patel");
    // Still open work is not history.
    expect(panel).not.toContain("WO-4908");
  });

  it("says how many of how many when the meter has more jobs than one page", () => {
    const html = renderDetail("/assets/a-4021?tab=work&section=history", detail(), {
      workOrders: { ...WORK_ORDERS, total: 63 },
    });
    expect(finished(html)).toContain("Newest 2 of 63 jobs.");
  });
});

describe("DEF-AST-9691 — the Reads footer counts what it pages: read dates", () => {
  it("two readings kept on one day are three rows over two dates, and the footer says dates", () => {
    const sameDay: AssetReadRow = { ...READS[0], read_id: "r-2b", reading: "43578.000000" };
    const html = renderDetail("/assets/a-4021?tab=reads", detail(), {
      reads: [READS[0], sameDay, READS[1]],
      readsTotal: 2,
    });
    // Three rows drawn …
    expect(html.split("43566").length - 1 + (html.split("43578").length - 1)).toBeGreaterThanOrEqual(2);
    // … under a footer that names its unit rather than reading *1–2 of 2*.
    expect(html).toContain("Read dates 1–2 of 2");
    expect(html).toContain("Dates per page");
  });
});
