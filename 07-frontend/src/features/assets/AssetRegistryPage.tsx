// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-001 (S49 registry — three tabs, search, filters) ·
//           US-AST-002 (S51 add asset — the shared modal) ·
//           US-AST-003 (edit specs; delete only unreferenced inventory) ·
//           US-AST-009 (bulk assign inventory→units from the list) ·
//           US-SHL-020 (the one page header — this screen's conversion)
//           Screens: S49 (S15 in A1's platform-shell numbering), S51
// Change:   CR-028 AST-W1 (B16 §4.1–§4.3, all ten §10 rulings 2026-08-22) —
//           the registry to r10's AST-01: per-tab column sets, KPI grids over
//           explainer prose (D9/D2), tab-named workflow imports (BR-AST-046),
//           the ×1/Mar-2024 display fixes, DEF-592's last-read column.
// Rules:    BR-AST-004 (tabs partition by type category) · BR-AST-005 (status-filter
//           semantics) · BR-AST-006 (row actions vary by state — the SERVER's set) ·
//           BR-AST-007 (Test-due is derived) · BR-AST-009/010 (service + UoM required for
//           measuring types; net metering locked on for net meters, refused on BTM) ·
//           BR-AST-011 (assign-on-create) · BR-AST-012 (billing fields are forward-only) ·
//           BR-AST-013 (hard delete only for never-referenced inventory) ·
//           BR-AST-025 (this module never displays credit money — D2 kept the
//           BTM tab free of tariffs and credited dollars) · BR-AST-026 (three
//           identifiers — the uuid is never displayed) · BR-AST-031 (stages are
//           Reference data) · BR-AST-032 (roles; server-enforced) ·
//           BR-AST-033 (duplicate # blocks, duplicate serial warns) ·
//           BR-AST-036/038 (bulk assign is inventory→unit ONLY) · BR-AST-041 (the
//           capability row) · BR-AST-044 (BOTH classifications, both filterable;
//           meter_type is UNAVAILABLE on non-measuring types and the server refuses it) ·
//           BR-AST-046 (imports are tab-named entries onto the ONE workflow runner) ·
//           BR-SHL-010/011/012 · BR-SHL-025 · BR-SHL-032 · BR-SHL-033 · BR-SHL-034 ·
//           BR-SHL-044 (the one page-header skeleton, and its three properties)
// ───────────────────────────────────────────────────────
// S49 — the one registry of every billable asset.
//
// Three things this screen takes from the server rather than deciding:
//
//   1. **The action set.** BR-AST-006 makes the row's actions a function of the
//      lifecycle stage's BEHAVIOR CLASS, and the server computes them into
//      `row.actions`. This screen renders that array. A tenant that renames
//      "Needs repair" changes nothing here, which is the whole point of
//      BR-AST-031's behavior classes.
//
//   2. **The refusals.** meter_type on a battery (BR-AST-044), a duplicate
//      asset number (BR-AST-033), a delete on a referenced asset (BR-AST-013)
//      — each comes back as a B12 §3 envelope and renders where it belongs:
//      under the offending field, or as the form-level message.
//
//   3. **The KPI figures.** No aggregate endpoint is served, so the strips
//      count over the COMPLETE unfiltered result set or show the quiet dash —
//      a page's count is never presented as the utility's (B16 T1).
//
// The S52 staged-import MODAL that lived in this file is GONE (BR-AST-046,
// PO 2026-08-22): every import entry is now the tab-named button that
// navigates to the one workflow runner — see AssetImportWorkflow.tsx. The
// backend staged endpoints remain until AST-W3 lands the runner targets and
// retires that path end to end (US-AST-010's API tests still pin them).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import i18n from "@/i18n";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  bulkAssignAssets,
  deleteAsset,
  getAssets,
  getLookupEntries,
  getPremises,
  getTenantServices,
  getUnits,
} from "@/api/endpoints";
import type { AssetRow, AssetTab, LookupEntry } from "@/api/endpoints";
import { METER_TYPE_UNCLASSIFIED } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DataTable } from "@/components/DataTable";
import { useCustomFieldColumns } from "@/components/CustomFields";
import { FilterBar } from "@/components/FilterBar";
import { DateCell, formatMonthDay, todayInZone } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { UnitCell } from "@/components/UnitCell";
import {
  DatePickerField,
  FormModal,
  SearchSelectField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { PermissionDenied } from "@/components/StateFrame";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { RecordLink } from "@/components/RecordLink";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { enabledServiceRows } from "@/features/metering/ServicesAvailableField";
import { toEnvelope } from "@/features/metering/PremisesListPage";
import { chipFilters, premisesPickerOptions } from "@/features/metering/UnitsListPage";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  GuardedButton,
  PREMISES_PERMISSION,
  isDenied,
  unitDetailPath,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  apiErrorText,
  isPermissionDenied,
  refusalOf,
  RefusalNotice,
} from "@/features/tenancy/settingsShared";
import type { Refusal, Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AssetImportsTab } from "./AssetImportsTab";
import { AssetInventoryTab, stockDrillPath } from "./AssetInventoryTab";
import { AssetLifecycleTab } from "./AssetLifecycleTab";
import { AssetMapTab } from "./AssetMapTab";
import { bulkAssignFailureKey, unitPickerOptions } from "./AssetLifecycleModals";
import { ServiceTags } from "@/features/rating/ratingShared";

import { assetImportPath } from "./AssetImportWorkflow";
import {
  ASSET_TAB_IDS,
  AssetAgeCell,
  AssetDash,
  AssetStatusCell,
  STATUS_FILTER_ALL,
  STATUS_FILTER_UNASSIGNED,
  STATUS_FILTER_UNINSTALLED,
  assetDetailPath,
  assetEditPath,
  assetMaintenanceNewPath,
  assetNewPath,
  assetReassignPath,
  assetRetirePath,
  btmKpis,
  hasAction,
  kpiRowsComplete,
  metersKpis,
  repairActionKey,
  roleOf,
  trimDecimalZeros,
} from "./assetsShared";
import { Button } from "@/components/Button";
import { EyeIcon, PencilIcon, RetireIcon, SwapIcon, TrashIcon, WrenchIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const TAB_PARAM = "tab";

export const assetsQueryKey = (query: string) => ["assets", query] as const;
export const assetTypesQueryKey = ["lookups", "asset_types"] as const;
export const assetStatusesQueryKey = ["lookups", "asset_statuses"] as const;
export const meterTypesQueryKey = ["lookups", "meter_types"] as const;
export const readMethodsQueryKey = ["lookups", "read_methods"] as const;
/** BR-AST-530 — the connection-size list, read by the S51 edit form (AST-02). */
export const sizeClassesQueryKey = ["lookups", "service_size_classes"] as const;
export const assetPremisesPickerKey = ["premises", "asset-picker"] as const;
export const assetUnitsPickerKey = ["units", "asset-assign-picker"] as const;

/** CR-028 AST-W3-T4 + AST-W5: the page's tab strip is the three type tabs
 *  PLUS the four CR-028 tabs — Inventory (AST-01.inventory) · Lifecycle
 *  (AST-01.lifecycle) · Map (AST-03) · Imports (AST-04) — in the PO's own
 *  seven-tab order. UI tabs, not BR-AST-004 type partitions, so they are a
 *  separate vocabulary from `AssetTab` and never reach the server as a
 *  `f.tab` filter. */
export type RegistryTab = AssetTab | "inventory" | "lifecycle" | "map" | "imports";
export const REGISTRY_TAB_IDS: readonly RegistryTab[] = [
  ...ASSET_TAB_IDS,
  "inventory",
  "lifecycle",
  "map",
  "imports",
];
/** The tabs whose body is NOT the asset list — no registry read is spent on
 *  them, and the shared head carries no import button for them (Inventory's
 *  stock-count import is D5-DEFERRED; Lifecycle and Map have no imports of
 *  their own — B16 §4.7b: "four targets is the complete set"). */
const NON_LIST_TABS: readonly RegistryTab[] = ["inventory", "lifecycle", "map", "imports"];

/** BR-SHL-011's spirit: an unknown `?tab=` falls back rather than erroring. */
export function tabFromParam(raw: string | null): RegistryTab {
  return (REGISTRY_TAB_IDS as readonly string[]).includes(raw ?? "")
    ? (raw as RegistryTab)
    : "meters";
}

/** BR-AST-004: the tab's own type set, from the tenant's catalog `category`. */
export function typesForTab(
  entries: readonly LookupEntry[] | undefined,
  tab: AssetTab,
): LookupEntry[] {
  return (entries ?? []).filter((entry) => entry.active && String(entry.category ?? "") === tab);
}

/**
 * BR-AST-044: the meter-type filter's options, plus the reserved
 * "unclassified" choice. Migration 0004 backfilled nothing, so "which assets
 * still have no meter type?" is a real, answerable question — and `f.meter_type=
 * none` is how the server answers it.
 */
export function meterTypeFilterOptions(
  entries: readonly LookupEntry[] | undefined,
  t: Translator,
): { value: string; label: string }[] {
  const options = (entries ?? [])
    .filter((entry) => entry.active)
    .map((entry) => ({ value: entry.code, label: entry.name }));
  return [
    ...options,
    { value: METER_TYPE_UNCLASSIFIED, label: t("assets.filter.meterTypeUnclassified") },
  ];
}

/**
 * The BTM strip's "Exported · July" month name, from the tenant "today" seed
 * (IS-8). Null when no seed reached this screen — the card then keeps its
 * plain label rather than presenting the browser's clock as the tenant's.
 * Month name via Intl in the rendering language, the DateCell discipline.
 */
export function exportMonthLabel(
  today: string,
  locale: string = i18n.language || "en",
): string | null {
  const match = /^\d{4}-(\d{2})/.exec(today);
  if (match === null) {
    return null;
  }
  try {
    return new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(
      new Date(Date.UTC(2000, Number(match[1]) - 1, 15)),
    );
  } catch {
    return null;
  }
}

/** BR-AST-005: All (includes retired) · Unassigned · each tenant stage code. */
export function statusFilterOptions(
  entries: readonly LookupEntry[] | undefined,
  t: Translator,
): { value: string; label: string }[] {
  return [
    { value: STATUS_FILTER_ALL, label: t("assets.filter.statusAll") },
    { value: STATUS_FILTER_UNASSIGNED, label: t("assets.filter.statusUnassigned") },
    // CR-028 AST-W5: the Inventory drill's landing state gets its label so a
    // preset `f.status=uninstalled` reads as a choice, not a mystery.
    { value: STATUS_FILTER_UNINSTALLED, label: t("assets.filter.statusUninstalled") },
    ...(entries ?? [])
      .filter((entry) => entry.active)
      .map((entry) => ({ value: entry.code, label: entry.name })),
  ];
}

export interface AssetRegistryCells {
  select: (row: AssetRow) => JSX.Element;
  assetNo: (row: AssetRow) => JSX.Element;
  // The column KEY is the server's sort name (`type`); the readable value is
  // `type_name` (folded with the meter type, r10's "Meter · AMI" shape). The
  // renderer bridges the two so the sort stays the API's.
  type: (row: AssetRow) => JSX.Element;
  role: (row: AssetRow) => JSX.Element;
  service: (row: AssetRow) => JSX.Element;
  multiplier: (row: AssetRow) => JSX.Element;
  sizeClass: (row: AssetRow) => JSX.Element;
  meterType: (row: AssetRow) => JSX.Element;
  readMethod: (row: AssetRow) => JSX.Element;
  installed: (row: AssetRow) => JSX.Element;
  /** `DEF-AST-10178` — the shared Age cell, on all three data tabs. */
  age: (row: AssetRow) => JSX.Element;
  status: (row: AssetRow) => JSX.Element;
  actions: (row: AssetRow) => JSX.Element;
  parentMaster: (row: AssetRow) => JSX.Element;
  lastRead: (row: AssetRow) => JSX.Element;
  premisesUnit: (row: AssetRow) => JSX.Element;
  meter: (row: AssetRow) => JSX.Element;
  exportCapacity: (row: AssetRow) => JSX.Element;
  nextTest: (row: AssetRow) => JSX.Element;
  warranty: (row: AssetRow) => JSX.Element;
}

/**
 * CR-028 AST-W1 T2–T4 (B16 §4.1–§4.3): each tab carries r10's OWN column set —
 * the deployed page shipped Sub-meters and Behind-the-meter as filtered clones
 * of the Meters columns, which is exactly the measured drift §4.8 names. The
 * BR-AST-044 classification columns stay AVAILABLE (the ⋮ chooser) but off by
 * default on Meters: r10 folds the meter type into the Type cell instead.
 */
export function assetsTableConfig(
  t: Translator,
  tab: AssetTab,
  options: {
    types: { value: string; label: string }[];
    statuses: { value: string; label: string }[];
    meterTypes: { value: string; label: string }[];
    premises: { value: string; label: string }[];
    /** BR-MET-003 · the TENANT's enabled services, and nothing else. Empty
     *  until `GET /settings/services` answers — `chipFilters` drops the group
     *  while it is, so the panel never draws a heading over nothing (DEF-782,
     *  DEF-1701). ⚠ It said "and permanently for a role that may not read
     *  Settings", which reads as a permission boundary and is not one
     *  (`DEF-MET-4982`): the route is `AnyTenantRole`, so every signed-in
     *  tenant role reads it. An empty group here means the read FAILED, never
     *  that the reader was refused. */
    services: { value: string; label: string }[];
  },
  cells: AssetRegistryCells,
): TableConfig<AssetRow> {
  const columns: TableConfig<AssetRow>["columns"] = [
    // BR-AST-036: the multi-select that drives bulk assign. DataTable has no
    // built-in selection yet, so the checkbox is a cell in THIS config.
    { key: "select", label: t("assets.col.select"), cell: cells.select },
    {
      key: "asset_no",
      label: t(`assets.col.assetNo.${tab}`),
      sortable: true,
      identity: true, // BR-AST-026: the user-facing number, never the uuid
      cell: cells.assetNo,
    },
  ];
  if (tab === "meters") {
    // r10 AST-01: Meter # · Type · Role · Service · Mult. · Assigned to ·
    // Installed · Status.
    columns.push(
      { key: "type", label: t("assets.col.type"), sortable: true, cell: cells.type },
      { key: "role", label: t("assets.col.role"), cell: cells.role },
      { key: "service", label: t("assets.col.service"), cell: cells.service },
      // ── `CR-143-BRC07` — CONNECTION SIZE, A BILLING INPUT ON A LIST THAT
      // ── AUDITS BILLS. PO, verbatim: *"on asset screen can you add size -
      // ── column - since it si required for billing it is importan we show in
      // ── list vview also - add it in column seelctor also"*.
      //
      // ⚠ **IT IS NOT DRAWN.** The Assets blueprint's Figure 1 (p7) and its own
      // remedy Figure 52 (p142) both draw TEN columns and stamp them
      // `UNCHANGED`; this is an eleventh, added by ruling. The departure is
      // recorded in `04-docs/05-modules/05-assets/conformance/` rather than
      // left for a later reader to find as drift.
      //
      // ⚠ **PLACED HERE BECAUSE SERVICE AND SIZE ARE ONE ANSWER.** The base
      // charge resolves service → account type → size class (BR-RAT-108,
      // R3 of the R1–R7 chain), so the two facts that pick the price sit
      // together and MULT. — the thing that multiplies a metered quantity —
      // stays beside the reading columns it belongs to.
      { key: "size_class", label: t("assets.col.sizeClass"), cell: cells.sizeClass },
      { key: "multiplier", label: t("assets.col.multiplier"), numeric: true, cell: cells.multiplier },
      { key: "assigned_to", label: t("assets.col.assignedTo") },
      { key: "installed", label: t("assets.col.installed"), sortable: true, cell: cells.installed },
      // `DEF-AST-10178` (PO 2026-10-17) — sorts by the age's START date
      // server-side (`age`), so ascending is oldest first.
      { key: "age", label: t("common.col.age"), sortable: true, cell: cells.age },
      { key: "status", label: t("assets.col.status"), sortable: true, cell: cells.status },
      // BR-AST-044: both classifications REMAIN columns — off by default since
      // the Type cell already reads "Meter · AMI" (r10), on offer in the ⋮.
      { key: "meter_type", label: t("assets.col.meterType"), cell: cells.meterType, defaultVisible: false },
      { key: "read_method", label: t("assets.col.readMethod"), cell: cells.readMethod, defaultVisible: false },
      { key: "unit", label: t("assets.col.uom"), defaultVisible: false },
    );
  } else if (tab === "sub_meters") {
    // r10 AST-01.sub (B16 §4.2): Sub-meter # · Parent / master · Service ·
    // Unit · Last read (DEF-592, right-aligned) · Installed · Status.
    columns.push(
      { key: "parent", label: t("assets.col.parent"), sortable: true, cell: cells.parentMaster },
      { key: "service", label: t("assets.col.service"), cell: cells.service },
      { key: "assigned_to", label: t("assets.col.unit") },
      { key: "last_read", label: t("assets.col.lastRead"), numeric: true, cell: cells.lastRead },
      { key: "installed", label: t("assets.col.installed"), sortable: true, cell: cells.installed },
      // `DEF-AST-10178` (PO 2026-10-17) — sorts by the age's START date
      // server-side (`age`), so ascending is oldest first.
      { key: "age", label: t("common.col.age"), sortable: true, cell: cells.age },
      { key: "status", label: t("assets.col.status"), sortable: true, cell: cells.status },
      { key: "type", label: t("assets.col.type"), cell: cells.type, defaultVisible: false },
      { key: "meter_type", label: t("assets.col.meterType"), cell: cells.meterType, defaultVisible: false },
      { key: "read_method", label: t("assets.col.readMethod"), cell: cells.readMethod, defaultVisible: false },
      { key: "unit", label: t("assets.col.uom"), defaultVisible: false },
    );
  } else {
    // r10 AST-01.btm under the D2 ruling (B16 §4.3): Device # · Type ·
    // Premises · unit · Meter · Export capacity · Next test · Warranty
    // (hidden by default) · Status — NO tariff, NO credited dollars.
    columns.push(
      { key: "type", label: t("assets.col.type"), sortable: true, cell: cells.type },
      { key: "premises", label: t("assets.col.premisesUnit"), cell: cells.premisesUnit },
      { key: "meter", label: t("assets.col.meter"), cell: cells.meter },
      // `CR-143-BRC07` — and this is the tab where the size IS the price:
      // CLAUDE.md's fire rule is that the size class PICKS the charge and the
      // count multiplies it (one 6" line `$60.00`, one 2" line `$12.00`), and a
      // fire line is a behind-the-meter asset. Sub-meters get no such column:
      // `offersConnectionSize` refuses a size on one, so it could only ever be
      // empty — a dead column is hard-won law 2 in its mirror.
      { key: "size_class", label: t("assets.col.sizeClass"), cell: cells.sizeClass },
      { key: "export_capacity", label: t("assets.col.exportCapacity"), numeric: true, cell: cells.exportCapacity },
      { key: "next_test", label: t("assets.col.nextTest"), cell: cells.nextTest },
      { key: "warranty", label: t("assets.col.warranty"), cell: cells.warranty, defaultVisible: false },
      // `DEF-AST-10178` — this tab had NO Installed column, so an age here
      // would have had no date beside it to read against (PO: *"Behind the
      // meter gets an Installed column too"*).
      { key: "installed", label: t("assets.col.installed"), sortable: true, cell: cells.installed },
      { key: "age", label: t("common.col.age"), sortable: true, cell: cells.age },
      { key: "status", label: t("assets.col.status"), sortable: true, cell: cells.status },
      { key: "read_method", label: t("assets.col.readMethod"), cell: cells.readMethod, defaultVisible: false },
    );
  }
  columns.push(
    { key: "serial_no", label: t("assets.col.serial"), defaultVisible: false },
    { key: "manufacturer", label: t("assets.col.manufacturer"), defaultVisible: false },
    { key: "actions", label: t("assets.col.actions"), cell: cells.actions },
  );
  return {
    screenId: "S49",
    columns,
    getRowId: (row) => row.id,
    // BR-AST-041: asset # · serial · manufacturer/model · premises-unit address.
    // VERIFIED AGAINST THE PREDICATE 2026-08-27 (CR-041 task 2): `assets/
    // selectors.py` ORs `asset_no | serial_no | manufacturer | model |
    // parent_asset__asset_no` and then unions the assets assigned to the units
    // `_unit_ids_matching_address(term)` returns — so every field declared here
    // is genuinely matched, and there is a SIXTH leg (a parent/master's asset #)
    // that this row does not declare.
    searchFields: ["asset_no", "serial_no", "manufacturer", "model", "address"],
    // ⚠ **B14 rule 19 — AND r10's `Search meters or addresses…` (line 3220) IS
    // NOT WHAT THIS BOX DOES.** It matches five things, and a clerk holding a
    // serial number off the side of a meter would read r10's sentence and not
    // try it. The prompt names the five; the parent/master leg above is left
    // out of the COPY on purpose — naming six fields makes a prompt nobody
    // reads, and finding a master by its own asset # is what typing that asset #
    // already does. Under-promising by one derived leg is not a false promise;
    // the reverse would be (DEF-950).
    searchPlaceholder: "assets.registry.searchPlaceholder",
    filters: [
      { name: "status", label: t("assets.filter.status"), options: options.statuses },
      { name: "type", label: t("assets.filter.type"), options: options.types },
      // BR-AST-044: BOTH classifications filter, side by side.
      { name: "meter_type", label: t("assets.filter.meterType"), options: options.meterTypes },
      // ⚠ **THIS READ `options: []` AND WAS A LEGEND OVER NOTHING (DEF-782's
      // shape, found by DEF-1701).** It went unnoticed for as long as it did
      // because this screen rendered NO filter panel at all, so the dead group
      // was invisible: a defect hiding inside a defect. `asset_list` really
      // does filter on `f.service` (`selectors.py`), so the capability is real
      // and what was missing was its vocabulary.
      { name: "service", label: t("assets.filter.service"), options: options.services },
      { name: "premises_id", label: t("assets.filter.premises"), options: options.premises },
      {
        name: "assigned",
        label: t("assets.filter.assigned"),
        options: [{ value: "true", label: t("assets.filter.assignedYes") }],
      },
      {
        name: "test_due",
        label: t("assets.filter.testDue"),
        options: [{ value: "true", label: t("assets.filter.testDueYes") }],
      },
    ],
    defaultSort: { sort: "asset_no", dir: "asc" }, // BR-AST-041: asset # A→Z
  };
}

export function assetsParamsFrom(state: TableRequestState, tab: AssetTab) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    // BR-AST-004: the tab is a filter on the server — one request, one law.
    filters: { ...state.filters, tab },
  };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface AssetRegistryPageProps extends RegionalProps {
  client?: ApiClient;
  today?: string; // tenant "today" for the date prefills (IS-8 seed)
}

// CR-028 AST-W4 (the not-modal amendment): add / repair / retire / reassign
// left this union — those flows NAVIGATE to their full-page screens now
// (AST-05..AST-08). ⚠ **EDIT LEFT IT TOO, ON 2026-09-12** (`AST-B-12`, PO:
// "this should be form and not modal") and now navigates to AST-09 at
// `/assets/{id}/edit`. What remains modal here is the delete confirm — a
// destructive confirm is always a dialog — and bulk assign.
type AssetAction =
  | { kind: "bulkAssign" }
  | { kind: "delete"; row: AssetRow };

export function AssetRegistryPage(props: AssetRegistryPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pending, setPending] = useState<AssetAction | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const { timeZone, dateFormat } = useRegional(props);
  // ⚠ **`DEF-MET-4991`'s FOURTH DATE FIELD, AND ITS FIX MISSED THIS ONE.** The
  // router mounts this screen with NO props, so `props.today` is undefined and
  // this read `?? ""` — which made `BulkAssignModal`'s `prefill` undefined and
  // the Effective date box open empty, against `BR-PAY-033`. `AssetRetireWizard`
  // and both `AssetFlowPages` screens took `?? todayInZone(timeZone)` on
  // 2026-09-12; this line did not, and nothing went red because every TEST
  // passes `today` and only the ROUTER does not.
  //
  // It is load-bearing now rather than tidy: screen 07's drawn helper says the
  // date *defaults to today*, and the kit's own law is that a promise a help
  // sentence makes must actually be passed (`FormModal.tsx` DatePickerField) —
  // a helper over a field that does not do it is good copy to every check here
  // and a lie to the clerk.
  const today = props.today ?? todayInZone(timeZone);

  const registryTab = tabFromParam(searchParams.get(TAB_PARAM));
  // The DATA tab the table/config/query speak (BR-AST-004's partition). On
  // the four non-list tabs no asset list is fetched at all (`enabled` below);
  // the fallback value only keeps the config hooks stable.
  const isListTab = !(NON_LIST_TABS as readonly string[]).includes(registryTab);
  const tab: AssetTab = isListTab ? (registryTab as AssetTab) : "meters";
  const cell = useAccessCell(PREMISES_PERMISSION, client);
  const writeBlockedReason = cell === CELL_FULL || cell === null ? null : t("assets.rbac.readOnly");

  const typesQuery = useQuery({
    queryKey: assetTypesQueryKey,
    queryFn: () => getLookupEntries("asset_types", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const statusesQuery = useQuery({
    queryKey: assetStatusesQueryKey,
    queryFn: () => getLookupEntries("asset_statuses", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const meterTypesQuery = useQuery({
    queryKey: meterTypesQueryKey,
    queryFn: () => getLookupEntries("meter_types", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const premisesQuery = useQuery({
    queryKey: assetPremisesPickerKey,
    queryFn: () => getPremises({ per: 500 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  // BR-MET-003: the service filter's vocabulary is the TENANT's enabled set,
  // never a list derived from whichever rows are on this page. Reference data,
  // so it rides the shared staleness and never retries: a role that cannot read
  // Settings gets no group, not a spinner (DEF-1701).
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const premisesOptions = premisesPickerOptions(premisesQuery.data?.results);

  const config = assetsTableConfig(
    translate,
    tab,
    {
      types: typesForTab(typesQuery.data?.results, tab).map((entry) => ({
        value: entry.code,
        label: entry.name,
      })),
      statuses: statusFilterOptions(statusesQuery.data?.results, translate),
      meterTypes: meterTypeFilterOptions(meterTypesQuery.data?.results, translate),
      premises: premisesOptions,
      services: enabledServiceRows(servicesQuery.data).map((row) => ({
        value: row.service,
        label: row.name,
      })),
    },
    {
      select: (row) => (
        <input
          type="checkbox"
          aria-label={t("assets.selectRow", { asset: row.asset_no })}
          checked={selected.includes(row.id)}
          onChange={(event) =>
            setSelected(
              event.target.checked ? [...selected, row.id] : selected.filter((id) => id !== row.id),
            )
          }
        />
      ),
      assetNo: (row) => (
        <Link className="cursor-pointer border-0 p-0 text-left text-accent-700 no-underline hover:underline focus-visible:underline" to={tenantPath(assetDetailPath(row.id))}>
          {row.asset_no}
        </Link>
      ),
      // r10's Type cell folds both classifications — "Net meter · AMI". A null
      // meter type renders the type alone (unclassified stays findable through
      // the BR-AST-044 filter and the hidden Meter-type column).
      type: (row) => (
        <span>
          {row.meter_type_name !== null ? `${row.type_name} · ${row.meter_type_name}` : row.type_name}
        </span>
      ),
      // r10's Role column: Standard · the accent Master tag with its SERVED
      // child count · "Sub → <master>". Never a client-side guess (B16 §4.1).
      role: (row) => {
        const role = roleOf(row);
        if (role.kind === "sub") {
          return <span>{t("assets.role.sub", { parent: role.parent })}</span>;
        }
        if (role.kind === "master") {
          return (
            <span className="inline-flex border border-accent-500 px-1 text-xs uppercase tracking-label text-accent-700">
              {t("assets.role.master", { count: role.count })}
            </span>
          );
        }
        return <span>{t("assets.role.standard")}</span>;
      },
      // The ONE service badge (FE registry / ratingShared) — letter + full
      // accessible name, never a bare letter for a screen reader.
      service: (row) =>
        row.service !== null && row.service !== undefined ? (
          <ServiceTags services={[row.service]} />
        ) : (
          <AssetDash />
        ),
      // ×10 / ×1 — display trimming only; the decimal string is untouched (T6).
      multiplier: (row) => (
        <span>{t("assets.multiplierShort", { multiplier: trimDecimalZeros(row.multiplier) })}</span>
      ),
      // BR-AST-044: a null meter type on a measuring asset is UNCLASSIFIED, not
      // blank — and the filter above can find exactly these rows.
      meterType: (row) =>
        row.meter_type_name !== null ? (
          <span>{row.meter_type_name}</span>
        ) : (
          <span className="italic text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]">{t("assets.meterTypeUnclassified")}</span>
        ),
      readMethod: (row) =>
        row.read_method_name !== null ? <span>{row.read_method_name}</span> : <AssetDash />,
      // BR-AST-500 · `CR-143-BRC07` — the tenant's NAME for the size class,
      // never the code. `Water 5/8"` carries its unit (CLAUDE.md hard rule 3);
      // `W-58` carries neither a unit nor a meaning, and B14 rule 32 keeps an
      // internal code off clerk-facing copy.
      //
      // ⚠ **THE DASH COVERS BOTH ABSENCES ON PURPOSE, AND THE DETAIL SCREEN
      // IS RIGHT TO DO OTHERWISE.** On a detail Fact there is room to say *Not
      // recorded — a rate ladder that prices by size cannot price this meter*
      // (`assets.sizeClassUnrecorded`), and the screen does. In a list CELL that
      // sentence is 12 words in every row of a 50-row page, which B14 rule 33
      // caps at six and rule 32's description budget refuses outright. So the
      // list draws the registry's own em dash, the same one INSTALLED draws.
      sizeClass: (row) =>
        row.size_class_name != null && row.size_class_name !== "" ? (
          <span className="whitespace-nowrap">{row.size_class_name}</span>
        ) : (
          <AssetDash />
        ),
      installed: (row) =>
        row.install_date === null ? (
          <AssetDash />
        ) : (
          // BR-SHL-034: one formatter — at r10's month-year list density (T6).
          <DateCell value={row.install_date} timeZone={timeZone} dateFormat={dateFormat} monthYear />
        ),
      age: (row) => <AssetAgeCell row={row} today={today} timeZone={timeZone} t={translate} />,
      status: (row) => <AssetStatusCell row={row} t={translate} />,
      // r10's Parent / master cell: parent number · the master's premises.
      // Record links (PO 2026-10-19): the parent's NUMBER opens the parent.
      parentMaster: (row) =>
        row.parent_asset_no === null ? (
          <AssetDash />
        ) : (
          <span>
            <RecordLink to={row.parent_asset_id ? tenantPath(assetDetailPath(row.parent_asset_id)) : null}>
              {row.parent_asset_no}
            </RecordLink>
            {row.parent_premises != null && row.parent_premises !== "" ? ` · ${row.parent_premises}` : null}
          </span>
        ),
      // DEF-592: the metering-owned last-read summary, r10's "2,140 kWh · Aug 3"
      // shape — QUANTITY with its explicit unit (CLAUDE.md rule 3), and the
      // quiet dash when no committed read exists yet — never a zero.
      lastRead: (row) => {
        const read = row.last_read;
        if (read == null || read.consumption === null || read.unit === null) {
          return <AssetDash />;
        }
        return (
          <span className="whitespace-nowrap">
            <UnitCell quantity={trimDecimalZeros(read.consumption)} unit={read.unit} />
            {read.read_at !== null && <span>{` · ${formatMonthDay(read.read_at)}`}</span>}
          </span>
        );
      },
      // r10's BTM "Premises · unit" cell, from the current assignment.
      // Record links (PO 2026-10-19): the cell opens the UNIT it stands on.
      premisesUnit: (row) =>
        row.assigned_address === null ? (
          <AssetDash />
        ) : (
          <RecordLink to={row.assigned_unit_id ? tenantPath(unitDetailPath(row.assigned_unit_id)) : null}>
            {row.assigned_to !== null
              ? `${row.assigned_address} · ${row.assigned_to}`
              : row.assigned_address}
          </RecordLink>
        ),
      // The device's linked meter (parent asset), when the payload carries one.
      meter: (row) =>
        row.parent_asset_no === null ? (
          <AssetDash />
        ) : (
          <RecordLink to={row.parent_asset_id ? tenantPath(assetDetailPath(row.parent_asset_id)) : null}>
            {row.parent_asset_no}
          </RecordLink>
        ),
      // A capacity, never money (BR-AST-025 / D2). Null → the quiet dash.
      exportCapacity: (row) =>
        row.export_capacity_kw != null ? (
          <UnitCell quantity={trimDecimalZeros(row.export_capacity_kw)} unit="kW" />
        ) : (
          <AssetDash />
        ),
      nextTest: (row) =>
        row.next_test != null ? (
          <DateCell value={row.next_test} timeZone={timeZone} dateFormat={dateFormat} monthYear />
        ) : (
          <AssetDash />
        ),
      warranty: (row) =>
        row.warranty_end != null ? (
          <DateCell value={row.warranty_end} timeZone={timeZone} dateFormat={dateFormat} monthYear />
        ) : (
          <AssetDash />
        ),
      // BR-AST-006: the SERVER's action set for this row's state — never a
      // client-side guess from a status label.
      actions: (row) => (
        <RowActions>
          {hasAction(row, "view") && (
            <RowAction
              label={t("assets.action.view")}
              icon={<EyeIcon />}
              onClick={() => navigate(tenantPath(assetDetailPath(row.id)))}
            />
          )}
          {hasAction(row, "edit") && (
            <RowAction
              label={t("assets.action.edit")}
              icon={<PencilIcon />}
              reason={writeBlockedReason}
              // `AST-B-12`: AST-09 is a full-page screen at its own address
              // (PO 2026-09-11, "this should be form and not modal") — the
              // action NAVIGATES, exactly as reassign, log-repair and retire
              // have since CR-028 AST-W4.
              onClick={() => navigate(tenantPath(assetEditPath(row.id)))}
            />
          )}
          {(hasAction(row, "reassign") || hasAction(row, "assign")) && (
            <RowAction
              label={
                hasAction(row, "assign") ? t("assets.action.assign") : t("assets.action.reassign")
              }
              icon={<SwapIcon />}
              reason={writeBlockedReason}
              // AST-06 is a full-page screen (CR-028 W4) — the action NAVIGATES.
              onClick={() => navigate(tenantPath(assetReassignPath(row.id)))}
            />
          )}
          {hasAction(row, "log_repair") && (
            <RowAction
              label={t(repairActionKey(row))}
              icon={<WrenchIcon />}
              reason={writeBlockedReason}
              // AST-07 is a full-page screen (CR-028 W4).
              onClick={() => navigate(tenantPath(assetMaintenanceNewPath(row.id)))}
            />
          )}
          {hasAction(row, "retire") && (
            // ⚠ RETIRE IS NOT THE TRASH GLYPH. A retired asset still exists and
            // is still reportable; delete removes it. The two sit in this same
            // cell, so one glyph for both would be a real ambiguity rather than
            // a tidy one. r10 draws retire as ✕ and this is its exact path.
            <RowAction
              label={t("assets.action.retire")}
              icon={<RetireIcon />}
              danger
              reason={writeBlockedReason}
              // AST-08 is a full-page 3-step wizard (CR-028 W4).
              onClick={() => navigate(tenantPath(assetRetirePath(row.id)))}
            />
          )}
          {/* BR-AST-013: Delete appears only on an inventory row, and even then
              the server re-probes every reference before it removes anything. */}
          {hasAction(row, "delete") && (
            <RowAction
              label={t("assets.action.delete")}
              icon={<TrashIcon />}
              danger
              reason={writeBlockedReason}
              onClick={() => setPending({ kind: "delete", row })}
            />
          )}
        </RowActions>
      ),
    },
  );
  // ── `CR-161-BRC10` W3 · `DEF-AST-9171` — the optional column ────────────
  // One column per Assets field switched to *Show as column* on this list
  // (default *Not shown*), before the row actions. None for a tenant with none.
  const customColumns = useCustomFieldColumns<AssetRow>({
    entity: "assets",
    screen: "S49",
    valuesOf: (row) => [{ values: row.custom_data ?? {} }],
    client,
  });
  config.columns.splice(config.columns.length - 1, 0, ...customColumns);

  const state = parseTableParams(searchParams, config);
  function writeParams(next: TableRequestState, nextTab: RegistryTab): void {
    const params = serializeTableParams(next, config);
    params.set(TAB_PARAM, nextTab);
    setSearchParams(params, { replace: true });
  }
  function setState(next: TableRequestState): void {
    writeParams(next, registryTab);
    setSelected([]);
  }
  function selectTab(next: RegistryTab): void {
    // A different tab is a different result set — the old selection and the old
    // type filter are about rows that are no longer on screen.
    const filters = { ...state.filters };
    delete filters.type;
    writeParams({ ...state, filters, page: 1 }, next);
    setSelected([]);
  }

  const listQuery = useQuery({
    queryKey: assetsQueryKey(`${serializeTableParams(state, config).toString()}|${tab}`),
    queryFn: () => getAssets(assetsParamsFrom(state, tab), client),
    // The four non-list tabs draw their own reads — no registry read is
    // spent on any of them.
    enabled: isListTab,
  });

  function afterWrite(messageKey: string, params?: Record<string, unknown>): void {
    setPending(null);
    setRefusal(null);
    void queryClient.invalidateQueries({ queryKey: ["assets"] });
    fireToast(t(messageKey, params));
  }

  const remove = useMutation({
    mutationFn: (row: AssetRow) => deleteAsset(row.id, client),
    onSuccess: (_void, variables) =>
      afterWrite("assets.toast.deleted", { asset: variables.asset_no }),
    // BR-AST-013: the refusal names the reason and points at Retire.
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("assets.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (listQuery.data === undefined && listQuery.isError && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("assets.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  // US-SHL-020 / BR-SHL-044: the screen DECLARES its header instead of drawing
  // one. BR-AST-004's three tabs, the sentence that belongs to each of them and
  // the one slot the "+ Add …" button lands in are all config here, so the
  // layout is the component's and this screen cannot get it wrong on its own.
  const headerTabs = [
    ...ASSET_TAB_IDS.map((id) => ({
      id: id as string,
      label: t(`assets.tab.${id}`),
      // (b) ⚠ **EVERY TAB CARRIES ITS SENTENCE NOW — R6 / `AST-B-15`, and this
      // line read `id === "sub_meters" ? … : undefined` until today.** D9
      // (2026-08-22, B16 §10) ruled that r10 draws a KPI grid and NO prose on
      // Meters and Behind-the-meter, so only Sub-meters kept a caption. **The
      // ASSETS BLUEPRINT of 2026-09-13 supersedes r10 for this surface** — R6
      // (pp150–151) is a red COMMITMENT card headed *"One description per
      // screen, six to eight words"* and it draws a sentence in that slot on
      // all six tabs — exactly as B17 §4 superseded r10 for Routes & Cycles.
      // B14 rule 41, ratified the same day, is the other half: the product UI
      // matches the blueprint.
      //
      // The cost of the old line was TWO DEAD STRINGS: `assets.explainer.meters`
      // and `.behind_the_meter` sat in all eleven catalogues and reached no
      // screen, so the two busiest tabs in the module opened with nothing under
      // the title. Nothing could see it — `tsc`, every suite and every gate pass
      // over an explainer that is simply never asked for (hard-won law 2).
      //
      // ⚠ **THE TWO SENTENCES WERE CUT TO SIX WORDS IN THE SAME COMMIT**, for
      // the reason `DEF-MET-4961` cut the other four on 2026-09-12: they were
      // written when nobody could read them (11 words and 10), and B14 rule 33
      // caps a fact at six. R6's own proposals are SEVEN words each, so they are
      // a drawing that contradicts a signed rule — reported to the PO as one
      // decision covering all six tabs, never resolved here by choosing.
      //
      // `EXPLAINERS_NOT_IN_R10` does NOT move: G14 counts explainers r10 draws
      // nowhere, and these two have had no r10 sentence to match since the gate
      // was written. Changing their words leaves that count at three.
      explainer: t(`assets.explainer.${id}`),
      // (a) ONE primary slot whose label is the tab's own — the action state
      // lives on this page (`setPending`), so static config is all it needs.
      primaryAction: (
        <GuardedButton
          label={t(`assets.action.add.${id}`)}
          reason={writeBlockedReason}
          // The header's ONE primary slot renders a PRIMARY button. Guarded, so
          // BR-SHL-025's disabled-with-reason travels with it rather than the
          // header growing an unguarded button of its own.
          variant="primary"
          // AST-05 is a full-page 4-step wizard (CR-028 W4 · §10-D8): the add
          // NAVIGATES, carrying the tab as the wizard's asset class.
          onClick={() => navigate(tenantPath(assetNewPath(id as AssetTab)))}
        />
      ),
    })),
    // CR-028 AST-W5 — the three D1 tabs, in the PO's seven-tab order. No add
    // button (their rows are aggregates/markers, not creatable entities) and
    // no import button (Inventory's stock-count import is D5-DEFERRED;
    // Lifecycle and Map have none — B16 §4.7b).
    ...(["inventory", "lifecycle", "map"] as const).map((id) => ({
      id: id as string,
      label: t(`assets.tab.${id}`),
      explainer: t(`assets.explainer.${id}`),
      primaryAction: undefined as JSX.Element | undefined,
    })),
    // CR-028 AST-W3-T4 — AST-04. No add button (a run is made by importing)
    // and its own explainer; the three import buttons live in the tab body.
    {
      id: "imports",
      label: t("assets.tab.imports"),
      explainer: t("assets.explainer.imports"),
      primaryAction: undefined as JSX.Element | undefined,
    },
  ];

  // ── The KPI strips (T1 · D9 · D2) ─────────────────────────────────────────
  // Counted ONLY over the complete unfiltered result set — anything less shows
  // the quiet dash (see kpiRowsComplete). No aggregate endpoint is served and
  // no number is invented here.
  const rows = listQuery.data?.results ?? [];
  const kpisComplete = kpiRowsComplete(state, rows.length, listQuery.data?.count ?? null);
  const kpiValue = (value: number | null): JSX.Element =>
    value === null ? (
      <span data-kpi-absent="true">—</span>
    ) : (
      <span>{value.toLocaleString()}</span>
    );
  // DEF-MET-4953 — the SERVED figures for the two tabs that draw a grid. They
  // count the tab's whole population, so the cards carry a number on page 2
  // and under a filter, which is the state a real tenant is always in. The
  // client count below stays as the fallback and `kpisComplete` still governs
  // it; nothing invents a number in either path.
  const servedKpis = listQuery.data?.kpis;
  const meterKpis =
    registryTab === "meters"
      ? metersKpis(
          rows,
          kpisComplete,
          servedKpis !== undefined && "in_service" in servedKpis ? servedKpis : undefined,
        )
      : null;
  const deviceKpis =
    registryTab === "behind_the_meter"
      ? btmKpis(
          rows,
          kpisComplete,
          servedKpis !== undefined && "devices" in servedKpis ? servedKpis : undefined,
        )
      : null;
  // CR-028 debt sweep D4: the BTM list answer carries the SERVED rollup — the
  // last complete tenant-calendar month's export-channel quantities, grouped
  // by unit (rule 3). Absent/empty renders the quiet dash, never a zero.
  const exportRollup =
    registryTab === "behind_the_meter" ? (listQuery.data?.export_rollup ?? null) : null;
  // The card names the SERVED month when a rollup arrived; otherwise it falls
  // back to the tenant "today" seed (IS-8) — and with neither it keeps its
  // plain label rather than guessing the browser's clock as the tenant's.
  const exportMonth = exportMonthLabel(exportRollup?.month ?? today);

  return (
    <div className="px-4 pt-6 pb-8">
      {/* CR-018 Route B: `.ast-page .page-header { margin-bottom: 16px }` and
          `.ast-page .page-header h1 { font-size: var(--text-h2); margin: 0 }`
          were descendant rules reaching into the shared PageHeader. Route B has
          no parent selector, so they travel onto a wrapper holding only the
          header — the one `<h1>` beneath it is PageHeader's own. */}
      <div className="mb-4 [&_h1]:m-0 [&_h1]:text-h2">
        <PageHeader
          // No kicker: the prototype's Assets head is an H1 and its tab strip.
          // This screen rendered the kicker "Assets" above the H1 "Asset
          // registry", which is the DEF-021 duplication US-SHL-020 exists to end.
          title={t("assets.title")}
          // BR-AST-046 (T5): the import is NAMED FOR ITS TAB and NAVIGATES to
          // the one workflow runner with that tab's target — the staged modal
          // is retired with this button (no second import pipeline survives).
          // On AST-04 itself the head carries none: the tab body draws all
          // three tab-named entries.
          secondaryActions={
            !isListTab ? undefined : (
              <GuardedButton
                label={t(`assets.action.import.${tab}`)}
                reason={writeBlockedReason}
                onClick={() => navigate(tenantPath(assetImportPath(tab)))}
              />
            )
          }
          tabs={headerTabs}
          activeTabId={registryTab}
          tabsLabel={t("assets.tabsLabel")}
          // The tab stays URL state (BR-SHL-011): selectTab still rewrites the
          // params, drops the stale type filter and clears the selection.
          onTabSelect={(next) => selectTab(tabFromParam(next.id))}
        />
      </div>

      {/* CR-028 AST-W3-T4 — AST-04: the run-history table replaces the whole
          registry body; the shared page head above is untouched (one head,
          seven tabs — B16 §4's own skeleton). */}
      {registryTab === "imports" && (
        <AssetImportsTab
          writeBlockedReason={writeBlockedReason}
          onImport={(target) => navigate(tenantPath(`/assets/import?target=${target}`))}
          client={client}
        />
      )}
      {/* CR-028 AST-W5 — the three D1 tab bodies, each with its own read. */}
      {registryTab === "inventory" && (
        <AssetInventoryTab
          writeBlockedReason={writeBlockedReason}
          // The drill: one stock line → the REAL registry, preset to that
          // type's uninstalled rows (client-side navigation, filters preset).
          onDrill={(row) => navigate(tenantPath(stockDrillPath(row)))}
          client={client}
        />
      )}
      {registryTab === "lifecycle" && (
        <AssetLifecycleTab
          writeBlockedReason={writeBlockedReason}
          client={client}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
      {registryTab === "map" && <AssetMapTab client={client} />}
      {isListTab && (
      <>
      {/* T1/D9 — r10's four Meters cards replace the explainer prose. The
          needs-repair card carries NO work-order sub-label: Work is R5 (D7). */}
      {meterKpis !== null && (
        <div className="mb-5">
          <KPIStrip
            loading={listQuery.isPending}
            kpis={[
              {
                id: "meters_in_service",
                label: t("assets.kpi.metersInService"),
                value: kpiValue(meterKpis.inService),
                detail:
                  meterKpis.masters !== null &&
                  meterKpis.subs !== null &&
                  meterKpis.amiPct !== null
                    ? t("assets.kpi.metersInServiceDetail", {
                        masters: meterKpis.masters,
                        subs: meterKpis.subs,
                        ami: meterKpis.amiPct,
                      })
                    : undefined,
              },
              {
                id: "needs_repair",
                label: t("assets.kpi.needsRepair"),
                value: kpiValue(meterKpis.needsRepair),
              },
              {
                id: "in_inventory",
                label: t("assets.kpi.inInventory"),
                value: kpiValue(meterKpis.inInventory),
                detail: t("assets.kpi.inInventoryDetail"),
              },
              {
                id: "past_certification",
                label: t("assets.kpi.pastCertification"),
                value: kpiValue(meterKpis.pastCertification),
                detail: t("assets.kpi.pastCertificationDetail"),
              },
            ]}
          />
        </div>
      )}
      {/* T1/D2 — three BTM cards, RULED: no credited-$ KPI, no tariff. The
          exported-kWh VALUE stays absent until a served quantity exists —
          rendered, labeled, and never invented. */}
      {deviceKpis !== null && (
        <div className="mb-5">
          <KPIStrip
            loading={listQuery.isPending}
            kpis={[
              {
                id: "devices",
                label: t("assets.kpi.devices"),
                value: kpiValue(deviceKpis.devices),
              },
              {
                id: "exporting_devices",
                label: t("assets.kpi.exportingDevices"),
                value: kpiValue(deviceKpis.exporting),
              },
              {
                id: "exported_kwh",
                label:
                  exportMonth === null
                    ? t("assets.kpi.exported")
                    : t("assets.kpi.exportedMonth", { month: exportMonth }),
                // D4 (DEF closed): the served rollup renders quantity WITH its
                // unit, one entry per unit — never summed across units and
                // never invented: no rollup (or an empty month) keeps the dash.
                value:
                  exportRollup === null || exportRollup.totals.length === 0 ? (
                    kpiValue(null)
                  ) : (
                    <span>
                      {exportRollup.totals
                        .map((total) => `${trimDecimalZeros(total.quantity)} ${total.unit}`)
                        .join(" · ")}
                    </span>
                  ),
              },
            ]}
          />
        </div>
      )}

      <RefusalNotice refusal={refusal} />
      {notice !== null && (
        <RefusalStrip role="alert">
          {notice}
        </RefusalStrip>
      )}

      {/* BR-AST-036/038: bulk assign is INVENTORY→UNIT only. There is no bulk
          unit→unit control here or anywhere — mass moves go by file import. */}
      {selected.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-3 border border-l-[3px] border-divider border-l-accent-500 bg-surface px-3 py-2 text-base" role="status">
          <span>{t("assets.bulk.selected", { count: selected.length })}</span>
          <GuardedButton
            label={t("assets.bulk.assign")}
            reason={writeBlockedReason}
            onClick={() => setPending({ kind: "bulkAssign" })}
          />
          <Button variant="ghost" onClick={() => setSelected([])}>
            {t("assets.bulk.clear")}
          </Button>
          <span className="italic text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]">{t("assets.bulk.inventoryOnly")}</span>
        </div>
      )}

      <DataTable<AssetRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError && listQuery.data === undefined
            ? {
                reason: apiErrorText(listQuery.error, translate),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        // ⚠ **THIS SLOT WAS NOT PASSED AT ALL, AND THAT IS THE WHOLE OF
        //    DEF-1701.** `assetsTableConfig` has declared SEVEN filters —
        //    status · type · meter_type · service · premises_id · assigned ·
        //    test_due, every one of them genuinely matched by
        //    `assets.selectors.asset_list` — and this screen rendered no filter
        //    control, on all four asset tabs. PO 2026-08-27: *"on assets -
        //    tookkit dont have filters; same is the case with sub meters,
        //    devices, investory"*.
        //
        //    Hard-won law 2 exactly, in the ONE direction G13 cannot see:
        //    G13 asks whether every optional PROP has a caller, and this was a
        //    CONFIG KEY nobody read. `filters: [...]` type-checks, renders and
        //    passes every test, because the absent control asserts nothing.
        //    `G45` is the sibling gate that asks the config question.
        //
        //    ⚠ **`chipFilters`, NOT `config.filters` STRAIGHT THROUGH**, and
        //    both reasons are rules rather than taste: `premises_id` carries up
        //    to 500 options and B14 rule 9 refuses a wall of checkboxes, so it
        //    is a REMOVABLE CHIP while applied and never an option list; and a
        //    group whose options have not arrived (or that a Clerk may not
        //    read) is dropped rather than drawn as an empty legend
        //    (BR-SHL-010). It is the same helper and the same treatment
        //    `UnitsListPage` has had since DEF-442.
        filterBarSlot={
          <FilterBar
            filters={chipFilters(config.filters ?? [], state, premisesOptions)}
            state={state}
            onStateChange={setState}
          />
        }
        downloadSlot={
          // BR-AST-004: the tab IS a server filter, so the export carries it
          // the same way the list request does (assetsParamsFrom) — the
          // Sub-meters tab exports sub-meters, not the whole registry.
          <ListExportButton
            resource="assets"
            state={{ ...state, filters: { ...state.filters, tab } }}
            client={client}
          />
        }
        empty={{
          title: t(`assets.empty.${tab}`),
          helper: t("assets.emptyHelper"),
          ctaLabel: t(`assets.action.add.${tab}`),
          onCta: () => navigate(tenantPath(assetNewPath(tab))),
        }}
      />

      <p className="settings-audit-line">{t("assets.auditLine")}</p>

      {pending?.kind === "delete" && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete an asset.
          confirmVariant="danger"
          // BR-SHL-032: the confirm NAMES the action and its subject.
          title={t("assets.confirm.deleteTitle", { asset: pending.row.asset_no })}
          consequence={t("assets.confirm.deleteBody")}
          confirmLabel={t("assets.confirm.deleteAction")}
          working={remove.isPending}
          onConfirm={() => remove.mutate(pending.row)}
          onCancel={() => setPending(null)}
        />
      )}
      {/* CR-028 AST-W4: the repair / retire / reassign MODALS are gone — the
          row actions above navigate to AST-06/07/08's full-page screens. */}
      {pending?.kind === "bulkAssign" && (
        <BulkAssignModal
          assetIds={selected}
          client={client}
          dateFormat={dateFormat}
          today={today}
          onClose={() => setPending(null)}
          onDone={(message) => {
            setNotice(message);
            setSelected([]);
            afterWrite("assets.toast.bulkAssigned", { count: selected.length });
          }}
        />
      )}
      </>
      )}
    </div>
  );
}

// ── S51/AST-09 — Edit one asset: A FULL PAGE, NOT A DIALOG ──────────
// `AssetFormModal` and `assetSchema` LEFT THIS FILE for
// `AssetEditPage.tsx` under `AST-B-12` (PO instruction 2026-09-11, verbatim:
// "this should be form and not modal"), which is the same conversion CR-028
// AST-W4 made for reassign, log-repair and retire on 2026-08-22. The pencil in
// the row actions above NAVIGATES to `/assets/{id}/edit`; nothing in this file
// edits an asset any more, and there is no second copy of that form.
//
// What is left modal on this screen: delete (a destructive confirm, always a
// dialog) and bulk-assign.

// ── Bulk assign (BR-AST-036/038) ───────────────────────────────────────────

function BulkAssignModal(props: {
  assetIds: string[];
  client: ApiClient;
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
  today: string;
  onClose: () => void;
  onDone: (message: string | null) => void;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState({ unit_id: "", effective_date: "" });
  const unitsQuery = useQuery({
    queryKey: assetUnitsPickerKey,
    queryFn: () => getUnits({ per: 500 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // The unit picker's helper says how many there are to filter THROUGH, and it
  // reads the SERVED total rather than `results.length` — the request asks for
  // 500 and a tenant may hold more, so counting the page would state a number
  // that is wrong exactly when the sentence matters most.
  //
  // ⚠ **THE DRAWING'S `121` IS AN ILLUSTRATION AND IS NEVER ASSERTED** (B14
  // rule 37). Until the count arrives the helper is the short sentence — a line
  // that is present from the first paint (no reflow when the list lands) and
  // that never states a figure the screen does not have.
  const unitCount = unitsQuery.data?.count ?? null;

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const result = await bulkAssignAssets(
        {
          assignments: props.assetIds.map((assetId) => ({
            asset_id: assetId,
            unit_id: values.unit_id,
          })),
          effective_date: values.effective_date === "" ? undefined : values.effective_date,
        },
        props.client,
      );
      // BR-AST-036: a row that is NOT in inventory comes back refused, with the
      // alternative the rule names. The batch result is shown, never smoothed.
      const failures = result.errors
        .map((error) => t(bulkAssignFailureKey(error.reason), { asset: error.asset ?? "" }))
        .join(" ");
      props.onDone(
        result.failed === 0
          ? null
          : t("assets.bulk.partial", { assigned: result.assigned, failed: result.failed }) +
              " " +
              failures,
      );
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={t("assets.bulk.title", { count: props.assetIds.length })}
      kicker={t("assets.kicker")}
      schema={z.object({
        unit_id: z.string().trim().min(1, t("assets.bulk.unitRequired")),
        effective_date: z.string(),
      })}
      values={values}
      submitLabel={t("assets.bulk.save")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* ⚠ **THE 24-WORD LIMIT SENTENCE IS NOT DRAWN INSIDE THIS CARD, AND IT
          WAS RENDERED HERE AS WELL AS ON THE BAR BEHIND — so a clerk read it
          twice, three inches apart.** Figure 9 (pp32–33) puts the title, two
          fields and the consequence inside the card and nothing else; p33's
          *Words* row puts the limit on the SELECTION BAR — *"The bar says the
          limit out loud."* The bar still says it (`assets.bulk.inventoryOnly`
          above), which is the one place it belongs, and B14 rule 32 gives a
          section one sentence. The `<Note>` that stood here is gone. */}
      <SearchSelectField
        id="unit_id"
        label={t("assets.reassign.unit")}
        required
        value={values.unit_id}
        options={unitPickerOptions(unitsQuery.data?.results)}
        placeholder={t("assets.reassign.unitPlaceholder")}
        // Drawn under the input on Figure 9 and NOT passed until today, though
        // this kit field has taken `help` since it was written — the mirror of
        // hard-won law 2: a capability that exists and is never asked for.
        help={
          unitCount === null
            ? t("assets.bulk.unitHelpLoading")
            : t("assets.bulk.unitHelp", { count: unitCount })
        }
        onChange={(value) => setValues({ ...values, unit_id: value })}
      />
      <DatePickerField
        id="effective_date"
        label={t("assets.reassign.effectiveDate")}
        value={values.effective_date}
        prefill={props.today === "" ? undefined : props.today}
        dateFormat={props.dateFormat}
        help={t("assets.bulk.effectiveDateHelp")}
        onChange={(value) => setValues({ ...values, effective_date: value })}
      />
      {/* ⚠ **B14 RULE 11 — A FORM WRITING SERVICE STATE SHOWS WHAT IT WILL DO,
          AND THIS ONE SHOWED NOTHING.** Drawn on Figure 9 as the last thing in
          the card, headed `WHAT THIS WILL DO`, over two lines; p33 names rule 11
          among the screen's own rules. It moves assets between units, so the
          kit's `move` tone.
          ⚠ **BUILT FROM THE KIT RATHER THAN FROM THE PICTURE (B14 rule 38):**
          the drawing rules a thin accent line down the left of a heading and two
          paragraphs; the kit's staff box is a tagged card, and how a form is
          BUILT is the UI rules' call while what it CONTAINS is the drawing's.
          `AssetPanelEdits.tsx` renders the same shape for the forward-only
          notice, so the two assets write-surfaces look like one product.
          ⚠ **THE DRAWN LINE IS 14 WORDS AND THIS ONE IS 8.** The clause it drops
          — *"each with its own assignment row"* — describes a row a clerk never
          sees and cannot act on, which B14 rule 33 puts at zero words on screen.
          The count is PLURALISED rather than interpolated into one sentence, so
          a single-asset selection does not read *"1 assets move"*. */}
      <ConsequenceBox
        tone="move"
        data-consequence="bulk-assign"
        tag={t("assets.bulk.consequence.tag")}
        title={t("assets.bulk.consequence.moves", { count: props.assetIds.length })}
        body={t("assets.bulk.consequence.billed")}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-001@566072b (story+rules snapshot hash — EP-AST-01 registry story; co-stories US-AST-002/003@566072b; co-packet US-SHL-020@9941789 — EP-SHL-01, the page-header conversion) · CR-028@B16 (04-docs/02-decisions/16-cr028-assets-design.md §4.1–§4.3 + §10 rulings, AST-W1)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — the bespoke `.ast-head`/`.ast-head-row`/`.ast-head-actions`/`.ast-tabs` block is replaced by one declared `PageHeader`; BR-AST-004's three tabs, their per-tab guidance and the per-tab "+ Add …" primary are config now) · AMENDED 2026-08-22 by the CR-028 AST-W1 lane (T1 KPI grids replace the Meters/BTM explainers per D9/D2 · T2 r10 Meters columns incl. Role/Service/folded Type, title "Assets", "+ Add asset" · T3 Sub-meters own column set incl. DEF-592 last read · T4 BTM device columns, no money · T5 tab-named import buttons navigate to the ONE runner (BR-AST-046) and the S52 staged modal is DELETED from this file · T6 ×-multiplier, month-year dates) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (T4: the strip gains the AST-04 Imports tab (RegistryTab vocabulary — a UI tab, never a server f.tab), which mounts AssetImportsTab in place of the registry body; the asset list query is disabled on it) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (the not-modal ruling: + Add navigates to the AST-05 wizard (/assets/new?class=), reassign/repair/retire row actions navigate to AST-06/07/08's routes; AssetFormModal is EDIT-ONLY now — the create branches left with the stale keys retired from all 11 catalogs) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (the strip completes the PO's SEVEN-tab order: Inventory · Lifecycle · Map mount their own tab bodies (AssetInventoryTab/AssetLifecycleTab/AssetMapTab), the asset list query is disabled on all four non-list tabs, the head carries no import button on them (D5: stock-count import deferred; B16 §4.7b: four targets is the complete set), and statusFilterOptions gains the reserved `uninstalled` value — the Inventory drill's landing state) · AMENDED 2026-09-13 by the CR-092 blueprint build lane 1 (screens 01/02/03/04/07 of `05-prototype/01 Assets Menu Blueprint.pdf`, read as page IMAGES per B14 rule 42): (1) **R6 / `AST-B-15` — every tab's description renders**, so the Meters and Behind-the-meter slots stop opening empty and their two catalogue strings stop being dead; the blueprint of 2026-09-13 supersedes r10's D9 for this surface the way B17 §4 superseded it for Routes & Cycles. (2) The two sentences were CUT to six words each in all eleven catalogues, `DEF-MET-4961`'s move applied to the two tabs it could not reach. (3) `+ Add behind-the-meter asset` becomes **`+ Add device`**, the drawn label (Figure 3, p14). (4) Screen 07, the bulk-assign dialog, gains the **consequence box B14 rule 11 requires and it had none of** (Figure 9, pp32–33), **both drawn field helpers** — which the kit's fields have accepted since they were written — and LOSES the 24-word limit sentence that was rendered inside the card as well as on the selection bar behind it, where p33 puts it. (5) `today` falls back to `todayInZone(timeZone)`, the fourth date field `DEF-MET-4991`'s fix missed, without which the new *defaults to today* helper would have been a lie)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-change baseline; this lane adds 15 passing + 2 todo across the two assets test files and a CONCURRENT Premises lane is adding to the same suite — nothing was dropped) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (11 PASS/0 FAIL/2 SKIP was the baseline; a CONCURRENT lane added G14 prototype-conformance, which this conversion turns green for S15 and S16) · [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 [US-SHL-020 2026-08-10] the prototype puts the per-tab sentence in the head's `sub` slot — ABOVE the tab strip (05-prototype/UtilityBilling.html:4378, 4400, 4419). BR-SHL-044 (b) puts a per-tab explainer BELOW the strip, and the RATIFIED SKELETON WINS: this whole story exists so all four converted screens share one skeleton, so the three sentences render as the tab's `explainer` and `rollup` is left unset. The divergence is deliberate and recorded here rather than resolved in the prototype's favour · E2 [US-SHL-020] the prototype's registry H1 reads "Assets"; this screen ships `assets.title` = "Asset registry" and the copy is NOT changed — the i18n catalogs are outside this lane's ownership and STRUCTURE/PLACEMENT is what was converted. Same for the three primary labels: the prototype says "+ Add asset" / "+ Add behind-the-meter asset" where the catalog says "+ Add meter" / "+ Add device". Reported, not rewritten · E2 [US-SHL-020] the kicker "Assets" that sat above the H1 "Asset registry" is GONE: the prototype's registry head carries no kicker, and the pair was the same DEF-021 duplication Plans & Rates had. `assets.sub` ("Every meter, sub-meter and behind-the-meter device that can affect a bill.") is thereby ORPHANED — it is no longer rendered anywhere, and it is left in all five catalogs because this lane may not edit them · E4 [US-SHL-020] `GuardedButton` (features/metering, another lane's file) renders `btn btn-secondary` with no primary variant, so the header's primary action carries secondary styling where the prototype uses `btn-primary`. That is a VISUAL divergence only — the slot, the ordering and the per-tab label are the skeleton's — and it is reported rather than fixed by a second button implementation · E3 [list-export lane 2026-08-10] the S49 Download control is WIRED to POST /exports and carries the TAB as a filter (BR-AST-004), so each tab exports its own rows — but **the EP-AST-01 capability row declares Export "— (not shown in design)"**: it was built because the PO ruling of 2026-08-09 names S49 among the nine, and that divergence is REPORTED rather than silently resolved either way; BR-AST-041's "Service" column has no field on the served row, so the file omits it (the screen renders none either) · E3 the S51 modal has NO parent-meter picker on the Sub-meters tab: BR-AST-003 requires `parent_asset_no` for a sub-meter and the server refuses one without it, but no role-safe endpoint lists candidate parents distinctly from the asset list itself — the refusal renders under the form and the gap is REPORTED (US-AST-002 §5 already flags the same GAP in the prototype modal) · E3 the Service field is free text against the tenant's enabled-service codes: `GET /settings/services` is System-Admin-only, so a Billing Clerk (who may create assets per BR-AST-032) would get an empty dropdown; the server validates the code and refuses an unenabled one · E3 the import endpoints answer SYNCHRONOUSLY (no job store on this deployment — the backend packet reported it), so no 202/progress affordance is drawn · E4 the tab is its own URL param rather than a declared filter, so `?tab=` reads like S61's `?archive=` and the declared `f.type` filter can be scoped to the tab's own type set · [CR-028 AST-W1 2026-08-22 — three earlier E2s above are RESOLVED by this lane: the H1 is "Assets", the primaries read "+ Add asset"/"+ Add behind-the-meter asset", and the catalogs were amended in the same commit] · E3 [CLOSED 2026-09-12, `DEF-MET-4953`, PO ruling "a) Fix the figures"] this read "the KPI strips have NO served aggregate: values are counted client-side ONLY over the complete unfiltered result set (kpiRowsComplete) and render the quiet dash otherwise — a tenant whose tab exceeds one page sees dashes until a rollup endpoint is served". The rollup is now served: `GET /assets` carries `kpis` for the two tabs that draw a grid, counting the TAB's whole population, and the client count survives only as a fallback. Measured on `pine-hill` before: four em-dashes at `?tab=meters` (110 meters, 50 to a page) · E3 [SUPERSEDED — the absence was closed by D4 and this sentence did not move; `DEF-MET-4964` names the shape] this read "the BTM 'Exported · month' KPI VALUE is always the stated dash — no export quantity rides the list payload". It has ridden the list payload since the CR-028 debt sweep (`export_rollup`, wired at the `exported_kwh` card above) and reads a real quantity with its unit · E4 "Master · N units" counts the master's SUB-METERS via the served `sub_count` (each sub bills its own unit, BR-AST-003) — the only honest figure the payload offers for r10's "units" wording · E3 CLOSED 2026-09-12 (CR-092 lane 5, DEF-MET-4982): this read "the Service field is free text ... `GET /settings/services` is System-Admin-only, so a Billing Clerk would get an empty dropdown". The permission half is FALSE — the route is `AnyTenantRole` (apps/tenancy/api.py:419) and a Billing Clerk reads it exactly as this page's own service filter does at :507. The S51 modal it described is gone; AssetAddWizard.tsx now picks the service from that endpoint
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
