// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-AST-001 (S49 registry)
// Change:  CR-143-BRC07 — SIZE as a registry column, and in the column
//          chooser. PO, verbatim: *"on asset screen can you add size - column
//          - since it si required for billing it is importan we show in list
//          vview also - add it in column seelctor also"*.
// Rules:   BR-AST-500 (the connection's size class) · BR-RAT-108 (service →
//          account type → size class picks the base charge) · CLAUDE.md's fire
//          paragraph (the size class PICKS the price, the count multiplies it)
//          · CLAUDE.md hard rule 3 (a dimension carries its unit) · B14 rule 31
//          / rule 32 (no id, no internal code on screen) · B14 rule 33 (a
//          heading is a LABEL, ≤ 3 words) · hard-won law 2 (built is not wired)
// Tests:   this file
// Impacts: 06-backend/apps/tenancy/selectors.py
//          (`service_size_class_names`) · 06-backend/apps/assets/seams.py ·
//          06-backend/apps/assets/selectors.py (`asset_page_rows`) ·
//          07-frontend/src/api/endpoints.ts (`AssetRow.size_class_name`) ·
//          07-frontend/src/features/assets/AssetRegistryPage.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS FILE IS FOR, AND WHY THE CHOOSER CASE IS NOT DECORATION.**
// The column and the chooser entry are ONE mechanism — `config.columns` feeds
// both — but only the header is visible to a `toContain` on a heading. A
// chooser that had silently dropped the column would leave a clerk unable to
// hide it and unable to get it back after a reset, and the header assertion
// would still be green. So the chooser is asserted through the one piece of
// markup only IT carries: the item's `title` attribute (`ColumnChooser.tsx`).
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`/:tenant/assets`), not a bare
// `MemoryRouter`: `useParams().tenant` is undefined under a bare one and every
// address the page builds comes out protocol-relative, which reads as a
// perfectly good string to `toContain`.
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
  assetsQueryKey,
  assetsTableConfig,
  meterTypesQueryKey,
  tabFromParam,
} from "./AssetRegistryPage";

const t = (key: string): string => i18n.t(key);
const TENANT = "brazosbend";

function lookup(code: string, name: string, extra: Record<string, unknown> = {}): LookupEntry {
  return { id: `l-${code}`, code, name, active: true, is_system: true, used_by: 0, ...extra };
}

const TYPES: LookupEntry[] = [
  lookup("meter", "Meter", { category: "meters" }),
  lookup("fire_line", "Fire line", { category: "behind_the_meter" }),
];
const STAGES: LookupEntry[] = [
  lookup("active", "Installed/Active", { behavior_class: "in_service" }),
  lookup("inventory", "Inventory/Spare", { behavior_class: "available" }),
];
const METER_TYPES: LookupEntry[] = [lookup("ami", "AMI")];

/** ⚠ **B14 rule 37 — every figure here is an ILLUSTRATION.** The two size
 *  names are the ratified spellings from `apps/tenancy/service_size_classes.py`
 *  because the POINT of this column is that the NAME and not the code reaches
 *  the screen; nothing else in this row is a fact about the product. */
function meter(over: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-7100",
    asset_no: "M-7100",
    serial_no: "SZ-0001",
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "active",
    status_name: "Installed/Active",
    behavior_class: "in_service",
    meter_type: "ami",
    meter_type_name: "AMI",
    read_method: "ami",
    read_method_name: "AMI",
    multiplier: "1.000000",
    size_class: "W-58",
    size_class_name: 'Water 5/8"',
    unit: "kgal",
    net_metering: false,
    manufacturer: "Neptune",
    model: "T-10",
    install_date: "2026-01-05",
    parent_asset_no: null,
    service_point_id: "sp-1",
    assigned_unit_id: "u-1",
    assigned_to: "Unit 1",
    assigned_address: "12 Quarry Hill Road",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit"],
    service: "water",
    ...over,
  } as AssetRow;
}

function paged<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function listTab(path: string): AssetTab {
  const asked = tabFromParam(new URLSearchParams(path.split("?")[1] ?? "").get("tab"));
  return ASSET_TABS.includes(asked as AssetTab) ? (asked as AssetTab) : "meters";
}

function render(rows: AssetRow[], path = `/${TENANT}/assets`): string {
  const config = assetsTableConfig(
    t,
    // ⚠ **NARROWED THE WAY THE PAGE ITSELF NARROWS IT.** `tabFromParam` answers
    // a REGISTRY tab, which includes four that fetch no asset list at all;
    // `assetsTableConfig` only speaks the three DATA tabs. The page resolves
    // that with the same cast plus a `meters` fallback, and a fixture that
    // skips the narrowing is a fixture typed differently from the screen it
    // stands in for (`DEF-AST-7130`).
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
  queryClient.setQueryData(meterTypesQueryKey, paged(METER_TYPES));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route
              path="/:tenant/assets"
              element={<AssetRegistryPage timeZone="America/Chicago" today="2026-09-27" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-143-BRC07 · the registry shows the connection size", () => {
  it("TC-1: a meter with a recorded size draws its NAME, with its unit, and never the code", () => {
    const html = render([meter()]);
    // The heading, from the catalogue key the edit form and the detail Fact
    // already use — one pair of words for one fact, in all eleven languages.
    expect(html).toContain(`>${t("assets.col.sizeClass")}<`);
    // The VALUE. `5/8"` reaches the markup as `5/8&quot;`.
    expect(html).toContain("Water 5/8");
    // ⛔ B14 rule 32 — the code is what the row has carried since BR-AST-500 and
    // it is exactly what must NOT reach a clerk. Without this line the cell
    // could print `W-58` and every other assertion here would still pass.
    expect(html).not.toContain("W-58");
  });

  it("TC-2: a meter with no recorded size draws the registry's own em dash", () => {
    const html = render([meter({ size_class: null, size_class_name: null })]);
    expect(html).toContain(`>${t("assets.col.sizeClass")}<`);
    // The same absence INSTALLED draws. Asserted against a row that DOES carry
    // an installed date, so a page-wide failure cannot satisfy it.
    expect(html).toContain("Jan 2026");
    expect(html).not.toContain("Water 5/8");
  });

  it("TC-3: a recorded size the tenant's list cannot NAME still draws the dash, never the code", () => {
    // The server answers `size_class_name: null` for a code with no row rather
    // than falling back to the code (`service_size_class_names`' own rule).
    const html = render([meter({ size_class: "W-99", size_class_name: null })]);
    expect(html).not.toContain("W-99");
  });

  it("TC-4: the column chooser offers it — the PO asked for the column AND the chooser", () => {
    const html = render([meter()]);
    // `ColumnChooser` puts the label in the item's `title`; the table head does
    // not. So this string is the chooser and only the chooser.
    expect(html).toContain(`title="${t("assets.col.sizeClass")}"`);
  });

  it("TC-5: behind-the-meter carries it too — a fire line's size IS its price", () => {
    const html = render(
      [
        meter({
          id: "a-7101",
          asset_no: "FL-7101",
          type: "fire_line",
          type_name: "Fire line",
          tab: "behind_the_meter",
          service: "fire",
          meter_type: null,
          meter_type_name: null,
          read_method: null,
          read_method_name: null,
          size_class: "FL-6",
          size_class_name: 'Fire line 6"',
        }),
      ],
      `/${TENANT}/assets?tab=behind_the_meter`,
    );
    expect(html).toContain(`>${t("assets.col.sizeClass")}<`);
    expect(html).toContain("Fire line 6");
    expect(html).not.toContain("FL-6<");
  });

  it("TC-6: sub-meters do NOT carry it — a column that could only ever be empty is dead UI", () => {
    // `offersConnectionSize` refuses a size on a sub-meter, so the column would
    // draw a dash on every row for ever (hard-won law 2's mirror).
    const config = assetsTableConfig(
      t,
      "sub_meters",
      { types: [], statuses: [], meterTypes: [], premises: [], services: [] },
      {} as never,
    );
    expect(config.columns.map((c) => c.key)).not.toContain("size_class");
  });

  it("TC-7: on meters it sits between SERVICE and MULT. — the two facts that pick the price, together", () => {
    const config = assetsTableConfig(
      t,
      "meters",
      { types: [], statuses: [], meterTypes: [], premises: [], services: [] },
      {} as never,
    );
    const keys = config.columns.map((c) => c.key);
    expect(keys.indexOf("size_class")).toBe(keys.indexOf("service") + 1);
    expect(keys.indexOf("multiplier")).toBe(keys.indexOf("size_class") + 1);
  });
});
