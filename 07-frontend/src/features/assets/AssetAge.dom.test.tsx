// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-AST-10178 — the Meters, Sub-meters and Behind-the-meter lists
//          show no age and cannot sort oldest to newest.
// Ruling:  12-governance/02-decision-log.md "2026-10-17 — ASSET AGE ON METERS,
//          SUB-METERS AND BEHIND-THE-METER LISTS" (PO: "this is all corect"),
//          and its six worked examples, today 10/17/2026.
// Rules:   PO "use same code components" (the shared AgeCell) · B14 rule 43 ·
//          B14 rule 33 (the note is a fact, ≤ 6 words) · hard-won law 2
// Tests:   this file
// Impacts: 07-frontend/src/features/assets/AssetRegistryPage.tsx ·
//          07-frontend/src/features/assets/assetsShared.tsx (`AssetAgeCell`)
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`/:tenant/assets`) with `today`
// pinned to the ruling's 10/17/2026, so the six figures are the PO's own.
import "@/i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { ASSET_TABS } from "@/api/endpoints";
import type { AssetRow, AssetTab, LookupEntry, Paginated } from "@/api/endpoints";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import {
  AssetRegistryPage,
  assetStatusesQueryKey,
  assetTypesQueryKey,
  assetsParamsFrom,
  assetsQueryKey,
  assetsTableConfig,
  meterTypesQueryKey,
  tabFromParam,
} from "./AssetRegistryPage";

const t = (key: string): string => i18n.t(key);
const TENANT = "brazosbend";
const TODAY = "2026-10-17";

function lookup(code: string, name: string, extra: Record<string, unknown> = {}): LookupEntry {
  return { id: `l-${code}`, code, name, active: true, is_system: true, used_by: 0, ...extra };
}

const TYPES: LookupEntry[] = [
  lookup("meter", "Meter", { category: "meters" }),
  lookup("sub_meter", "Sub-meter", { category: "sub_meters" }),
  lookup("pv", "PV / solar", { category: "behind_the_meter" }),
];
const STAGES: LookupEntry[] = [
  lookup("active", "Installed/Active", { behavior_class: "in_service" }),
  lookup("retired", "Retired", { behavior_class: "terminal" }),
];

function asset(over: Partial<AssetRow>): AssetRow {
  return {
    id: `a-${over.asset_no ?? "x"}`,
    asset_no: "X",
    serial_no: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "active",
    status_name: "Installed/Active",
    behavior_class: "in_service",
    meter_type: null,
    meter_type_name: null,
    read_method: null,
    read_method_name: null,
    multiplier: "1.000000",
    size_class: null,
    size_class_name: null,
    unit: "kgal",
    net_metering: false,
    manufacturer: null,
    model: null,
    install_date: null,
    parent_asset_no: null,
    service_point_id: null,
    assigned_unit_id: null,
    assigned_to: null,
    assigned_address: null,
    assigned: false,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view"],
    service: "water",
    age_end: null,
    expected_life_years: null,
    ...over,
  } as AssetRow;
}

// ── The six worked examples (today 10/17/2026) ────────────────────────────
const METERS = [
  asset({
    asset_no: "334556",
    install_date: "2026-09-12",
    age_start: "2026-09-12",
    age_start_source: "install",
  }),
  asset({
    asset_no: "M-2010",
    install_date: "2010-05-01",
    age_start: "2010-05-01",
    age_start_source: "install",
    expected_life_years: 15,
  }),
  asset({
    asset_no: "M-2012",
    install_date: "2012-05-15",
    age_start: "2012-05-15",
    age_start_source: "install",
    retire_date: "2025-06-30",
    age_end: "2025-06-30",
    status: "retired",
    status_name: "Retired",
    behavior_class: "terminal",
  }),
];
const SUBS = [
  asset({
    asset_no: "SM-7040",
    type: "sub_meter",
    type_name: "Sub-meter",
    tab: "sub_meters",
    install_date: "2026-01-15",
    age_start: "2026-01-15",
    age_start_source: "install",
  }),
];
const DEVICES = [
  asset({
    asset_no: "AST-04413",
    type: "pv",
    type_name: "PV / solar",
    tab: "behind_the_meter",
    age_start: "2024-03-01",
    age_start_source: "purchase",
  }),
  asset({
    asset_no: "AST-00010",
    type: "pv",
    type_name: "PV / solar",
    tab: "behind_the_meter",
    age_start: "2026-10-02",
    age_start_source: "record",
  }),
];

function paged<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function listTab(path: string): AssetTab {
  const asked = tabFromParam(new URLSearchParams(path.split("?")[1] ?? "").get("tab"));
  return ASSET_TABS.includes(asked as AssetTab) ? (asked as AssetTab) : "meters";
}

function render(rows: AssetRow[], path: string): Document {
  const config = assetsTableConfig(
    t,
    listTab(path),
    { types: [], statuses: [], meterTypes: [], premises: [], services: [] },
    {} as never,
  );
  const search = new URLSearchParams(path.split("?")[1] ?? "");
  const tab = tabFromParam(search.get("tab"));
  const state = parseTableParams(search, config);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    assetsQueryKey(`${serializeTableParams(state, config).toString()}|${tab}`),
    paged(rows),
  );
  queryClient.setQueryData(assetTypesQueryKey, paged(TYPES));
  queryClient.setQueryData(assetStatusesQueryKey, paged(STAGES));
  queryClient.setQueryData(meterTypesQueryKey, paged([]));
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route
              path="/:tenant/assets"
              element={<AssetRegistryPage timeZone="America/Chicago" today={TODAY} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return new DOMParser().parseFromString(html, "text/html");
}

/** The Age cell of the row whose text holds `assetNo`. */
function ageOf(doc: Document, assetNo: string): HTMLElement {
  const row = Array.from(doc.querySelectorAll("tbody tr")).find((tr) =>
    (tr.textContent ?? "").includes(assetNo),
  );
  expect(row, `row ${assetNo}`).toBeTruthy();
  const cell = row!.querySelector<HTMLElement>("[data-age-cell]");
  expect(cell, `age cell on ${assetNo}`).toBeTruthy();
  return cell!;
}

function headers(doc: Document): string[] {
  return Array.from(doc.querySelectorAll("thead th")).map((th) => (th.textContent ?? "").trim());
}

describe("DEF-AST-10178 · Age on the three asset lists (today 10/17/2026)", () => {
  it("Meters: 334556 installed 09/12/2026 reads 1 mo, with no note", () => {
    const doc = render(METERS, `/${TENANT}/assets?f.status=all`);
    expect(headers(doc).some((h) => h.startsWith(t("common.col.age")))).toBe(true);
    const cell = ageOf(doc, "334556");
    expect(cell.textContent).toBe("1 mo");
  });

  it("Meters: installed 05/01/2010 with a 15-year life reads 16 yrs 5 mos, red, Past life", () => {
    const doc = render(METERS, `/${TENANT}/assets?f.status=all`);
    const cell = ageOf(doc, "M-2010");
    expect(cell.textContent).toBe(`16 yrs 5 mos${t("assets.age.pastLife")}`);
    expect(cell.innerHTML).toContain("text-danger-700");
    // ⛔ and a meter inside its life is NOT red.
    expect(ageOf(doc, "334556").innerHTML).not.toContain("text-danger-700");
  });

  it("Meters: retired 06/30/2025 stops ageing — 13 yrs 1 mo, not 14 yrs", () => {
    const doc = render(METERS, `/${TENANT}/assets?f.status=all`);
    expect(ageOf(doc, "M-2012").textContent).toBe("13 yrs 1 mo");
  });

  it("Sub-meters: SM-7040 installed 01/15/2026 reads 9 mos", () => {
    const doc = render(SUBS, `/${TENANT}/assets?tab=sub_meters`);
    expect(headers(doc).some((h) => h.startsWith(t("common.col.age")))).toBe(true);
    expect(ageOf(doc, "SM-7040").textContent).toBe("9 mos");
  });

  it("Behind the meter: bought, never installed — 2 yrs 7 mos · from purchase", () => {
    const doc = render(DEVICES, `/${TENANT}/assets?tab=behind_the_meter`);
    expect(ageOf(doc, "AST-04413").textContent).toBe(`2 yrs 7 mos${t("assets.age.fromPurchase")}`);
  });

  it("Behind the meter: only a record date — 15 days · from record", () => {
    const doc = render(DEVICES, `/${TENANT}/assets?tab=behind_the_meter`);
    expect(ageOf(doc, "AST-00010").textContent).toBe(`15 days${t("assets.age.fromRecord")}`);
  });

  it("Behind the meter gains an Installed column beside Age", () => {
    const doc = render(DEVICES, `/${TENANT}/assets?tab=behind_the_meter`);
    const heads = headers(doc);
    const installed = heads.findIndex((h) => h.startsWith(t("assets.col.installed")));
    const age = heads.findIndex((h) => h.startsWith(t("common.col.age")));
    expect(installed).toBeGreaterThan(-1);
    expect(age).toBe(installed + 1);
  });

  it.each(ASSET_TABS)("%s: Age is sortable and asks the server for sort=age both ways", (tab) => {
    const config = assetsTableConfig(
      t,
      tab,
      { types: [], statuses: [], meterTypes: [], premises: [], services: [] },
      {} as never,
    );
    const column = config.columns.find((c) => c.key === "age");
    expect(column?.sortable).toBe(true);
    for (const dir of ["asc", "desc"] as const) {
      const state = parseTableParams(new URLSearchParams(`sort=age&dir=${dir}`), config);
      expect(assetsParamsFrom(state, tab)).toMatchObject({ sort: "age", dir });
    }
  });
});
