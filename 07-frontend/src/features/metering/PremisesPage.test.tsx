// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 premises list + detail)   Screens: S14
// Rules:    BR-MET-034 (premises types are Reference data) · BR-MET-036 (occupancy is
//           DERIVED — it renders, it never edits) · BR-MET-037 (Delete only at zero units) ·
//           BR-MET-045 (the detail tab set) · BR-MET-048 (audited server-side) ·
//           BR-SHL-011 (URL grammar) · BR-SHL-025 (server-authoritative RBAC) ·
//           BR-SHL-032 (a confirm NAMES the action)
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend Utilities (US-MET-001 §4), rendered through the
// mocked client seam — no network, ever.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountRow, AuditListResult, AuditRow, MyPermissions, PremisesDetail, PremisesPage, PremisesType, UnitRow } from "@/api/endpoints";
import type { CityGisState } from "@/api/endpoints";
import { cityGisQueryKey } from "@/features/metering/CityGis";
import { queryKeys } from "@/api/queryClient";
import { PageHeader } from "@/components/PageHeader";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { masterRefusalEnvelope, premisesMasterQueryKey } from "./CommonAreasTab";
import {
  PremisesDetailPage,
  entityAuditQueryKey,
  premisesDetailQueryKey,
  premisesAssetsQueryKey,
  premisesAreaSplit,
  premisesTabs,
  premisesHeadline,
} from "./PremisesDetailPage";
import { PremisesTabsPage, premisesRollupQueryKey } from "./PremisesTabsPage";
import EN from "../../i18n/locales/en.json";
import {
  canOfferDelete,
  premisesLocality,
  premisesMapState,
  premisesQueryKey,
  premisesTableConfig,
  premisesTypeOptions,
  premisesTypesQueryKey,
} from "./PremisesListPage";
import {
  PREMISES_PERMISSION,
  PREMISES_TAB_IMPORTS,
  PREMISES_TAB_PREMISES,
  PREMISES_TAB_STRIP,
  PREMISES_TAB_UNITS,
  accessCell,
  auditViewerPath,
  isDenied,
  isReadOnly,
  premisesDetailPath,
  premisesRollupLine,
  premisesStripTabs,
  unitDetailPath,
} from "./meteringShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`, so
// the screens below are rendered under one and the render helpers take the
// TENANT-RELATIVE path the route config is written in.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const TYPES: PremisesType[] = [
  { id: "t1", code: "single_family", name: "Single-family", active: true, is_system: true },
  { id: "t2", code: "commercial", name: "Commercial building", active: true, is_system: true },
  { id: "t3", code: "retired_type", name: "Retired type", active: false, is_system: false },
];

function premise(over: Partial<PremisesDetail> = {}): PremisesDetail {
  return {
    id: "p-101",
    premise_no: "P-00101",
    name: null,
    address_line: "1408 Bluestem Ln",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    // BR-MET-071 — the area tag the PO asked for on 2026-08-17. Untagged by
    // default here, so every existing case still asserts the "—" it did.
    // DEF-507 — three-state: `null` is *nobody was ever asked*, which is what
    // every case here means. Cases that need an answer override it.
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "single_family",
    premises_type_name: "Single-family",
    services_available: ["electric", "water"],
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

function unitRow(over: Partial<UnitRow> = {}): UnitRow {
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
    // CR-089 wave A · BR-MET-1162 — a unit's own point. `null` is the state
    // all 1,109 units are in today, and `point.source: "premises"` is the
    // ruled fallback: this unit reads its building's.
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters: [
      { id: "a1", asset_no: "M-7001", qualifier: null },
      { id: "a2", asset_no: "W-7001", qualifier: "sub" },
    ],
    occupancy: "occupied",
    occupant: "Miller, Sarah",
    account_no: "A-00412",
    status: "active",
    // DEF-755 — *what is METERED here*, now under its own name. `services`
    // above is what the unit's PREMISES offers; the two answer different
    // questions and no longer share a word.
    metered_services: [],
    sub_metered: true,
    ...over,
  };
}

// ── BR-CUS-068 · r10's two common areas at 1408 Elm, and their master ───────
// r10 draws `Hallway & exterior lighting · M-4109 · Small Commercial · $41.20`
// and `Shared irrigation · M-4110 · … · $28.40`. The LABELS and the METERS are
// ours to render; the two money figures are not (bill assembly prices the
// account's anchor unit only), which is what the case above protects.

const COMMON_HALLWAY: UnitRow = unitRow({
  id: "u-common-1",
  unit_no: "U-00101-C1",
  label: "Hallway & exterior lighting",
  unit_type: "common_area",
  is_common_area: true,
  occupancy: "vacant",
  occupant: null,
  account_no: null,
  meters: [{ id: "a9", asset_no: "M-4109", qualifier: null }],
  services: ["electric"],
});

const COMMON_IRRIGATION: UnitRow = unitRow({
  id: "u-common-2",
  unit_no: "U-00101-C2",
  label: "Shared irrigation",
  unit_type: "common_area",
  is_common_area: true,
  occupancy: "vacant",
  occupant: null,
  account_no: null,
  meters: [{ id: "a10", asset_no: "M-4110", qualifier: null }],
  services: ["water"],
});

/** The master account the server serves — an ORDINARY account row carrying
 *  `kind: "master"`, which is the whole point of the ruled design. */
function masterRow(over: Partial<AccountRow> = {}): AccountRow {
  return {
    id: "acc-master-1",
    account_no: "A-00900",
    name: "Miller Property LLC",
    // ⚠ **`CR-056` W1 / `BR-CUS-1010` — THIS FIXTURE HELD THE ANCHOR AND THE
    // SERVER NO LONGER SENDS ONE.** It read `unit_id: COMMON_HALLWAY.id`, "the
    // ANCHOR — coverage rides the agreements". A master account is the owner's
    // account at an ADDRESS: it carries `premises_id`, `unit_id` is null, and
    // ALL of its coverage rides the agreements now, the first common area
    // included. A fixture still holding an anchor would let a screen read one
    // and pass.
    unit_id: null,
    unit_label: null,
    premises_id: "p-101", // the ADDRESS it hangs off — the fixture premises
    premise: "1408 Bluestem Ln",
    services: ["electric", "water"],
    balance: null,
    balance_currency: null,
    balance_basis: null,
    balance_source: null,
    balance_unavailable: [],
    balance_cached: null,
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "master",
    account_type: "commercial",
    account_subtype: null,
    autopay: false,
    opened_at: "2024-01-04",
    closed_at: null,
    ...over,
  } as AccountRow;
}

function page(rows: PremisesDetail[]): PremisesPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    rollup: { premises: 6, units: 143, common: 0, vacant: 9, pending_activation: 1 },
  };
}

const CONFIG = premisesTableConfig(t, [], [], {
  premiseNo: () => <span />,
  address: () => <span />,
  type: () => <span />,
  services: () => <span />,
  owner: () => <span />,
  // CR-089 `PUJ-01` / `DEF-4740` — the ninth column. Stubbed here like every
  // other cell; the RENDERED pill is asserted through `renderList` below,
  // because a stub can only prove the column is declared.
  onTheMap: () => <span />,
  status: () => <span />,
  actions: () => <span />,
});

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderList(
  path: string,
  seed: { list?: PremisesPage; types?: PremisesType[]; access?: string } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(path.split("?")[1] ?? ""), CONFIG);
  if (seed.list !== undefined) {
    queryClient.setQueryData(
      premisesQueryKey(serializeTableParams(state, CONFIG).toString()),
      seed.list,
    );
  }
  if (seed.types !== undefined) {
    queryClient.setQueryData(premisesTypesQueryKey, seed.types);
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  // CR-023 P0: the page is the SHELL and the list is its Premises tab body.
  // Rendering the body alone would draw no head at all, which is exactly what
  // the BR-SHL-044 cases below are about — so the tests mount what the ROUTE
  // mounts. The rollup query is seeded from the same page the list uses,
  // because the head's counts sentence reads `GET /premises` -> `rollup`.
  if (seed.list !== undefined) {
    queryClient.setQueryData(premisesRollupQueryKey, seed.list);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <PremisesTabsPage tab={PREMISES_TAB_PREMISES} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The Imports tab (PRM-04) through the same shell. */
function renderImports(seed: { access?: string } = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/imports`]}>
          <PremisesTabsPage tab={PREMISES_TAB_IMPORTS} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * DEF-579 — what `GET /audit-log?f.entity_type=&f.entity_id=` answers for ONE
 * entity. r10's PRM-02 audit table draws four rows, two of them SYSTEM jobs, so
 * the fixture carries both actor shapes (BR-AUD-003: a null actor is a system
 * job and is NAMED, never blanked).
 */
function auditResult(rows: Partial<AuditRow>[] = []): AuditListResult {
  const results = rows.map((over, index) => ({
    id: `au-${index}`,
    created_at: "2026-02-12T10:04:00Z",
    actor: { id: "u-1", name: "Alex Reed" },
    action: "premises.updated",
    entity_type: "premises",
    entity_id: "p-101",
    summary: "Sub-area changed Route 2 → Route 3",
    source: null,
    ...over,
  })) as AuditRow[];
  return {
    page: { count: results.length, next: null, previous: null, results },
    window: { window: "hot", from: "2024-08-22T00:00:00Z" },
  };
}

/**
 * BR-CUS-068 — the premises' master account(s), as `GET /accounts?f.kind=master`
 * answers. `null` (the default) seeds NOTHING, which is the honest first paint
 * for every case written before master accounts existed: the query is still in
 * flight and the tile renders an em-dash rather than claiming "none".
 */
/** The header row's labels, in order — the DRAWN column set of the Common
 *  areas tab.
 *
 * ⚠ It reads `<thead>` and nothing else on purpose. The shared table's column
 * chooser lists every DECLARED column, hidden ones included, so a substring
 * search over the whole render can never tell a drawn column from a hidden one
 * — a check that cannot fail (hard-won law 7). */
function commonAreaFirstRow(html: string): string[] {
  const body = /<tbody>(.*?)<\/tbody>/s.exec(html);
  if (body === null) {
    return [];
  }
  const row = /<tr[^>]*>(.*?)<\/tr>/s.exec(body[1]);
  if (row === null) {
    return [];
  }
  return [...row[1].matchAll(/<td[^>]*>(.*?)<\/td>/gs)].map((m) =>
    m[1]
      .replace(/<[^>]*>/g, " ")
      .replace(/&amp;/g, "&")
      .replace(/\s+/g, " ")
      .trim(),
  );
}

function commonAreaHeaders(html: string): string[] {
  const head = /<thead>(.*?)<\/thead>/s.exec(html);
  if (head === null) {
    return [];
  }
  return [...head[1].matchAll(/<th[^>]*>(.*?)<\/th>/gs)].map((m) =>
    m[1].replace(/<[^>]*>/g, "").replace(/[▲▼]/g, "").trim(),
  );
}

function renderDetail(
  path: string,
  detail: PremisesDetail,
  assets: unknown[] = [],
  masters: AccountRow[] | null = null,
  audit: AuditListResult | null = null,
  // CR-089 wave C `C2` — BR-SHL-025 says a forbidden control renders DISABLED
  // with its reason, and that is only assertable if a test can say which cell
  // the reader holds. Seeded exactly as `renderList` already seeds it.
  access?: string,
  // GIS Lane D (`DEF-MET-10003`, 2026-10-07) — the City's facts are drawn only
  // where a City GIS is in use. Every case written before that is a utility
  // WITH one, so that is the default; `none` is the gap-9 case below.
  city: CityGisState = "working",
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(premisesDetailQueryKey(detail.id), detail);
  queryClient.setQueryData(cityGisQueryKey, { state: city, message_key: null });
  if (access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  }
  // DEF-579: the Audit log tab reads the entity's OWN rows. `null` seeds
  // nothing, which leaves the tab in A18's loading state — the honest first
  // paint for every case written before the rows were drawn here.
  if (audit !== null) {
    queryClient.setQueryData(entityAuditQueryKey("premises", detail.id), audit);
  }
  if (masters !== null) {
    queryClient.setQueryData(premisesMasterQueryKey(detail.id), masters);
  }
  queryClient.setQueryData(premisesAssetsQueryKey(detail.id), {
    count: assets.length,
    next: null,
    previous: null,
    results: assets,
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/premises/:premisesId" element={<PremisesDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}


/**
 * **THE LABELS THE REDESIGNED PROPERTY PAGE ACTUALLY DRAWS (`DEF-MET-4803`).**
 *
 * `5ca82a824` (2026-09-09, `CR-089` P4) rebuilt this screen onto the blueprint's
 * drawn frame and **ten assertions in this file were left describing the screen
 * as it was before**. They went red that day and were still red a day later,
 * read by nobody: three lanes ran the suite past them, and the failure
 * `Unable to find a label with the text of: Jurisdiction` reads like a missing
 * control rather than a renamed word.
 *
 * ⚠ **EVERY ONE OF THEM WAS THE TEST BEING WRONG, AND THAT WAS CHECKED RATHER
 * THAN ASSUMED.** The drawn frame is
 * `04-docs/05-modules/04-metering/conformance/CR-089-p019-property-overview.md`,
 * transcribed from the blueprint character for character. Against it: the fact
 * rows are **thirteen in ONE column** (so the old `grid-cols-2` assertion was
 * asserting a layout the drawing does not have), the address carries **no comma
 * before the postcode**, the kicker is **`PREMISE` alone** with the property
 * number moved down to the identity line, and the common-area split moved out
 * of the Units tile into fact row 13, where it **names** the areas instead of
 * counting them. Nothing was lost; four facts moved and one word changed.
 *
 * ⚠ **SO THE LABELS ARE CONSTANTS, ANCHORED TO THE CATALOGUE BELOW.** Four
 * copies of a label is four places to miss when it moves again; one is one, and
 * the anchor case fails with the reason attached instead of failing inside six
 * cases about something else.
 */
const CITY_LIMITS_LABEL = "City limits";
const SERVICES_LABEL = "Utility services";

describe("DEF-MET-4803 — the labels these cases ask for are the labels the product draws", () => {
  it("the catalogue still calls these fields what this file asks for", () => {
    // Reword either and THIS fails, naming the constant to change — instead of
    // six cases failing on `Unable to find …`, which reads as a broken screen.
    const en = EN as Record<string, string>;
    expect(en["metering.premises.field.jurisdiction"]).toBe(CITY_LIMITS_LABEL);
    expect(en["metering.premises.col.services"]).toBe(SERVICES_LABEL);
  });
});

describe("US-MET-001 — the S14 premises list", () => {
  it("US-MET-001 TC-1: the seeded rows and the header roll-up render from the server's own counts", () => {
    const html = renderList("/premises", { list: page([premise()]), types: TYPES });
    expect(html).toContain("P-00101");
    expect(html).toContain("1408 Bluestem Ln");
    expect(html).toContain("Whitfield Rentals LLC");
    // ⚠ **AMENDED 2026-09-19 (`DEF-MET-5855`) — THE PREMISES TAB DRAWS THE
    // DRAWN SUBTITLE, NOT THE ROLL-UP.** This read `expect(html).toContain("143")`
    // and `toContain("pending activation")` over a head that reads
    // `90 premises · 141 + 1 common units · 73 vacant · 4 pending activation`.
    // `CR-089-p005-property-list.md` §Header: *"No roll-up sentence is drawn.
    // The line under the title is the subtitle"*, and §Tiles: *"None. The screen
    // draws no stat tiles and no KPI strip."* B14 rule 41 makes the drawing the
    // specification. The SLOT is unchanged — `page-header-rollup` is the one
    // line under the title and the Units tab has filled it with a subtitle
    // since 2026-09-10 — so only what goes in it moved.
    expect(html).toContain("page-header-rollup");
    expect(html).toContain(t("metering.premises.listSubtitle"));
    // BR-MET-003 / CR-023 §9.7: the tenant's enabled services render as r10's
    // coloured LETTER SQUARES, from the one badge component the whole product
    // shares. The full-name chips this replaced are DEF-439's shape.
    expect(html).toContain("var(--color-service-electric)");
    expect(html).toContain("var(--color-service-water)");
    expect(html).not.toContain("var(--color-service-gas)");
    expect(html).toContain('aria-label="Electric"');
    // The capability row: premise # is the identity column, sorted asc.
    expect(CONFIG.defaultSort).toEqual({ sort: "premise_no", dir: "asc" });
    expect(CONFIG.columns.find((c) => c.identity === true)?.key).toBe("premise_no");
  });

  it("US-MET-001 / BR-SHL-016: the capability row's Download renders, CSV only", () => {
    // "Export: CSV (IS-9)" had no route until POST /exports landed
    // (2026-08-10); the shared control now fills the table's download slot and
    // posts THIS screen's request state. IS-11 forbids XLSX, and no prop asks.
    const html = renderList("/premises", { list: page([premise()]) });
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="premises"');
    expect(html.toLowerCase()).not.toContain("xlsx");
  });

  it("US-MET-001 TC-2 / BR-MET-034: the Type filter's options ARE the tenant's Reference-data list", () => {
    // Not a hardcoded enum, and a deactivated entry is not offered.
    expect(premisesTypeOptions(TYPES)).toEqual([
      { value: "single_family", label: "Single-family" },
      { value: "commercial", label: "Commercial building" },
    ]);
    expect(premisesTypeOptions(undefined)).toEqual([]);
    const html = renderList("/premises", { list: page([premise()]), types: TYPES });
    expect(html).toContain("Commercial building");
  });

  it("DEF-1700: the premises-type chip row is GONE and the dimension is still offered", () => {
    // ⚠ **THE SCREEN THE PRODUCT OWNER PHOTOGRAPHED.** A `SegmentedFilter`
    // drew Apartment complex · Commercial building · Government building ·
    // Mixed-use · Mobile-home park · Single-family on a second toolbar row.
    // PO 2026-08-27, verbatim: *"on premsies screen - why we are having -
    // apartment complex, comemrcial building etc in toolkit as per our stadard
    // first raw of tookkit is more than suficient"*.
    //
    // The chip row was PURE DUPLICATION: `type` was already a declared
    // `TableConfig` filter fed by the SAME `premisesTypeOptions(typesQuery)`
    // and writing the SAME `f.type` param (the test below pins that
    // round-trip). So this asserts both halves — the control is gone, and the
    // dimension is not.
    const html = renderList("/premises", { list: page([premise()]), types: TYPES });
    // The segmented control drew `.seg` / `role="radiogroup"`; neither may
    // survive on a list toolbar, and no second row may be rendered at all.
    expect(html).not.toContain('class="seg"');
    expect(html).not.toContain('role="radiogroup"');
    expect(html).not.toContain('data-table-row="dimensions"');
    // …and every type is still reachable from the ONE `+ Filter` panel.
    expect(html).toContain("+ Filter");
    expect(html).toContain("Commercial building");
    expect(CONFIG.filters?.map((f) => f.name)).toContain("type");
  });

  it("US-MET-001 TC-2 / BR-SHL-011: every declared filter round-trips through the URL", () => {
    // ⚠ **`location` JOINED THIS LIST IN CR-089 WAVE A AND THIS ASSERTION WENT
    // RED, WHICH IS THE ASSERTION WORKING.** It pins the DECLARED set, and a
    // filter the client offers but does not declare here is dropped in silence
    // by `parseTableParams` — the same shape as `DEF-836`, where a chip on this
    // very list was ignored server-side and the whole tenant came back looking
    // like a filter that had found everything.
    // ⚠ `area` is absent BY CONSTRUCTION, not by omission: it is declared only
    // when the tenant HAS areas, and this fixture has none.
    // ⚠ **`owner` JOINED IN CR-089 WAVE B (`d4e86212`, 2.234.7, 2026-09-09) —
    // `B1`'s *Needs an owner* list — AND THIS LINE WENT RED THE SAME WAY
    // `location` MADE IT GO RED IN WAVE A. That is the assertion doing its
    // job.** It is corrected here, by the wave C lane, rather than left
    // standing: `git log -S '"owner"'` dates the filter to wave B's commit and
    // this file was already open in front of me, and a true red left in place
    // is how the next reader learns to skim past a failing suite
    // (`DEF-CWP-4187`).
    expect(CONFIG.filters?.map((f) => f.name)).toEqual([
      "type",
      "status",
      "location",
      "owner",
    ]);
    // ⚠ **THREE VALUES SINCE 2026-09-10 (`DEF-4740`), NOT TWO, AND THE VALUE
    // STRINGS ARE THE SERVER'S OWN.** `selectors.premises_list` learned
    // `checked` and `placed_unchecked` in the same commit; a client value the
    // server does not know falls through to NO filter, so the chip comes back
    // with the whole tenant looking like a filter that found everything —
    // DEF-836, on this very list. `placed` LEFT the offered set (it is the
    // union of the other two) and stays a server branch for URLs bookmarked
    // since wave A.
    expect(
      CONFIG.filters?.find((f) => f.name === "location")?.options.map((o) => o.value),
    ).toEqual(["checked", "placed_unchecked", "needs_location"]);
    const state = parseTableParams(
      new URLSearchParams("f.type=commercial&f.status=active&q=Bluestem"),
      CONFIG,
    );
    expect(state.filters).toEqual({ type: "commercial", status: "active" });
    expect(state.q).toBe("Bluestem");
    expect(serializeTableParams(state, CONFIG).get("f.type")).toBe("commercial");
    // CR-089 `PUJ-01` — **Needs a location**, round-tripped like any other, and
    // the value string is the SERVER's own (`needs_location`). A second
    // spelling on the client is exactly how a chip comes to lie.
    const located = parseTableParams(
      new URLSearchParams("f.location=needs_location"),
      CONFIG,
    );
    expect(located.filters).toEqual({ location: "needs_location" });
    expect(serializeTableParams(located, CONFIG).get("f.location")).toBe("needs_location");
    // CR-089 `B2` — **Needs an owner**, the same round trip and the same rule
    // about the value string: `needs_owner` is the SERVER's own word, and a
    // second spelling on the client is how a chip comes to lie. Measured on the
    // demo utility the day it landed: 78 of 84 properties.
    // ⚠ The DECLARATION above was corrected by the wave C lane reading a red it
    // did not cause; this is the round trip, which is the half that would still
    // have passed with the chip mis-spelled.
    const unowned = parseTableParams(new URLSearchParams("f.owner=needs_owner"), CONFIG);
    expect(unowned.filters).toEqual({ owner: "needs_owner" });
    expect(serializeTableParams(unowned, CONFIG).get("f.owner")).toBe("needs_owner");
    // An undeclared filter is ignored rather than sent (US-SHL-007 TC-5).
    expect(parseTableParams(new URLSearchParams("f.nonsense=1"), CONFIG).filters).toEqual({});
  });

  it("US-MET-001 TC-3: the declared search fields are the epic's own set", () => {
    expect(CONFIG.searchFields).toEqual(["address", "premise_no", "owner_manager"]);
  });

  it("US-MET-001 TC-4: the row opens the PREMISE, and the eye into the Units tab is gone", () => {
    const html = renderList("/premises", { list: page([premise()]), access: "Full" });
    // ── `DEF-MET-5841` ────────────────────────────────────────────────────
    // ⚠ **THIS ASSERTED THE EYE ICON'S `href` AND THE ASSERTION WAS RIGHT
    // UNTIL THE PO REMOVED THE CONTROL.** Verbatim, having been told the
    // premise number already opens the premise: *"remove Eye icon… not
    // required since you ahve given view on P-00001"*. The row action went to
    // `/premises/units?f.premises_id=…` — the UNITS tab — under an icon that
    // reads as *view this thing*, which is what they reported first:
    // *"should redirect to view detail of premise"*.
    //
    // ⚠ **THE NEGATIVE IS THE HALF THAT CAN ROT, SO IT IS PINNED BY ADDRESS.**
    // Asserting only that the premise link is present would pass just as well
    // with the eye still there beside it; this fails if anything puts a
    // premises-scoped units link back on a ROW.
    expect(html).not.toContain("?f.premises_id=p-101");
    // The helper stays TENANT-RELATIVE; the tenant is added at the link, so one
    // helper serves every tenant and no row can point at another utility's data.
    expect(premisesDetailPath("p-101")).toBe("/premises/p-101");
    expect(html).toContain(`href="/${TEST_TENANT}${premisesDetailPath("p-101")}"`);
  });

  it("US-MET-001 TC-5 / BR-MET-037: Delete is guarded while the premise has units, with the reason", () => {
    expect(canOfferDelete(premise({ units: 2 }))).toBe(false);
    expect(canOfferDelete(premise({ units: 0 }))).toBe(true);
    const withUnits = renderList("/premises", { list: page([premise({ units: 2 })]), access: "Full" });
    // BR-SHL-025: disabled WITH the reason — never a vanished control.
    expect(withUnits).toContain("It has 2 unit(s). Deactivate it instead.");
    const empty = renderList("/premises", {
      list: page([premise({ id: "p-420", premise_no: "P-00420", units: 0 })]),
      access: "Full",
    });
    expect(empty).not.toContain("deactivate it instead");
  });

  it("BR-SHL-032 / BR-MET-048: the copy names the action and never claims to have written the audit row", () => {
    expect(t("metering.premises.confirm.deleteTitle", { premise: "P-00101" })).toBe(
      "Delete premise P-00101?",
    );
    expect(t("metering.premises.confirm.deleteAction")).toBe("Delete premise");
    expect(t("metering.premises.confirm.deactivateAction")).toBe("Deactivate premise");
    // The audit line states the SERVER records it — it does not claim to.
    expect(t("metering.auditLine")).toContain("by the server");
    const html = renderList("/premises", { list: page([premise()]), access: "Full" });
    expect(html).toContain("recorded in the audit log by the server");
  });

  it("US-MET-001 §RBAC / BR-SHL-025: a '—' cell hides the whole surface, a 'View' cell disables its writes", () => {
    expect(accessCell(permissions("—"), PREMISES_PERMISSION)).toBe("—");
    expect(isDenied(accessCell(permissions("—"), PREMISES_PERMISSION))).toBe(true);
    expect(isReadOnly(accessCell(permissions("View"), PREMISES_PERMISSION))).toBe(true);
    // An unread permission set hides NOTHING — the endpoint's own 403 is then
    // the boundary, which is the honest default.
    expect(accessCell(undefined, PREMISES_PERMISSION)).toBeNull();
    expect(isDenied(null)).toBe(false);

    const denied = renderList("/premises", { list: page([premise()]), access: "—" });
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain("P-00101");

    const viewOnly = renderList("/premises", { list: page([premise()]), access: "View" });
    expect(viewOnly).toContain("Your role can view this but not change it.");
    expect(viewOnly).toContain("P-00101");
  });

  it.todo(
    "US-MET-001 TC-6: a 500 renders A18 failed-with-retry and Retry re-issues the identical query — the retry click is browser scope",
  );
  it.todo(
    "US-MET-001 TC-7 (isolation): a Lone Star Ridge session sees no Brazos Bend premise in any permutation — server/RLS scope (G5)",
  );
});

// ── CR-089 `PUJ-01` · `DEF-4740` / `DEF-4741` / `DEF-4743` ─────────────────
// The blueprint (*Premises & Units Blueprint 2*, pages 5-8 for the list, 36-41
// for the edit form) against what the screen actually renders. These are the
// TIER-2 assertions of the UI skill's §14 — they can prove a column exists,
// carries the drawn words and sits in the drawn place; they cannot prove it
// LOOKS right, which is what the browser walk is for.
describe("CR-089 — the property list matches its drawing", () => {
  it("DEF-4740: `On the map` is drawn between Owner and Status, with its three states", () => {
    const columns = CONFIG.columns.map((column) => column.key);
    // The POSITION is the specification, not just the presence.
    expect(columns.indexOf("on_the_map")).toBe(columns.indexOf("owner_manager") + 1);
    expect(columns.indexOf("status")).toBe(columns.indexOf("on_the_map") + 1);
    expect(CONFIG.columns.find((column) => column.key === "on_the_map")?.label).toBe(
      "On the map",
    );

    // ⚠ **`gis_unchecked` IS `false` ON ALL THREE ROWS AND THAT IS THE POINT.**
    // The column reads `gis_checked_at`; a version reading the boolean would
    // call every one of these *Checked*, which is the state of the whole
    // estate today and would tell a clerk it had all been verified.
    const html = renderList("/premises", {
      list: page([
        premise({ id: "p-1", premise_no: "P-00001", gis_checked_at: "2026-09-08T00:00:00Z" }),
        premise({ id: "p-2", premise_no: "P-00002" }),
        premise({ id: "p-3", premise_no: "P-00003", lat: null, lng: null }),
      ]),
      access: "Full",
    });
    expect(html).toContain("Checked");
    expect(html).toContain("Placed, unchecked");
    expect(html).toContain("Not placed");
    // The pill is the KIT's, not a component invented for this column.
    expect(html).toContain('class="pill');
  });

  it("DEF-4740: the pure state function reads the pair, never the flag alone", () => {
    expect(premisesMapState({ lat: "30.7", lng: "-98.2", gis_checked_at: "2026-09-08" })).toBe(
      "checked",
    );
    expect(premisesMapState({ lat: "30.7", lng: "-98.2", gis_checked_at: null })).toBe(
      "placed_unchecked",
    );
    expect(premisesMapState({ lat: null, lng: null, gis_checked_at: null })).toBe("not_placed");
    // Half a point cannot be drawn either — the same predicate the server's
    // *Not placed* filter uses (`lat IS NULL OR lng IS NULL`).
    expect(premisesMapState({ lat: "30.7", lng: null, gis_checked_at: "2026-09-08" })).toBe(
      "not_placed",
    );
    expect(premisesMapState({ lat: null, lng: "-98.2", gis_checked_at: null })).toBe(
      "not_placed",
    );
  });

  it("DEF-4740: the address is ONE cell on TWO lines, and the header words are the drawn ones", () => {
    expect(premisesLocality({ city: "Silver Creek", state: "TX", postal_code: "78611" })).toBe(
      "Silver Creek, TX 78611",
    );
    // A row carrying none of the three draws one line rather than an empty
    // second one.
    expect(premisesLocality({ city: null, state: null, postal_code: null })).toBe("");
    expect(premisesLocality({ city: "Katy", state: null, postal_code: null })).toBe("Katy");

    const html = renderList("/premises", { list: page([premise()]), access: "Full" });
    expect(html).toContain("<strong>1408 Bluestem Ln</strong>");
    expect(html).toContain("Katy, TX 77494");
    // ⚠ `met-qualifier` is a class `metering.css` ALREADY DECLARES. This file
    // is not on `src/styles/route-b-migrated.txt`, so a Tailwind utility here
    // would render as nothing at all while every assertion below still passed
    // (B14 rule 21's per-file clause). Asserting the declared class is the
    // closest a test can get to that; the browser walk is the rest.
    expect(html).toContain('class="met-qualifier"');

    // The drawn header words, character for character.
    expect(CONFIG.columns.find((column) => column.key === "premise_no")?.label).toBe("Premise");
    expect(CONFIG.columns.find((column) => column.key === "services")?.label).toBe("Services");
  });

  it("DEF-4743: the row's shortcut opens the dialog that records a date and a reason", () => {
    const html = renderList("/premises", { list: page([premise()]), access: "Full" });
    // The row action is still there — the PO's ruling was *keep the shortcut,
    // point it at the real dialog* — and it now says what the dialog behind it
    // will offer.
    expect(html).toContain("Take out of service");
    // ⚠ **THE OLD PLAIN CONFIRM IS GONE AND ITS ABSENCE IS THE ASSERTION.**
    // `Deactivate premise P-00101?` asked no date and no reason, so a clerk who
    // came through this row recorded neither on an act the property's page
    // records both for.
    expect(html).not.toContain("Deactivate premise");
    // A property already out of service offers the other direction, because
    // the dialog does.
    const inactive = renderList("/premises", {
      list: page([premise({ status: "inactive" })]),
      access: "Full",
    });
    expect(inactive).toContain("Put back in service");
  });

  it("the empty state offers BOTH drawn ways out", () => {
    const html = renderList("/premises", { list: page([]), access: "Full" });
    expect(html).toContain("No premises yet.");
    expect(html).toContain("+ New premise");
    // *"…offers the two ways to fill it — add one, or import a list."* The
    // second was missing, which made the import a door a clerk had to already
    // know about on the one screen where they know least.
    expect(html).toContain("↑ Import");
  });
});

describe("US-MET-001 — the S14 detail (BR-MET-045 tabs)", () => {
  // ⚠ THIS CASE PINNED THE DEFECT TOO (`DEF-578`). It asserted SIX tabs and
  // said in its own comment that Accounts "is kept because dropping a tab a
  // ratified rule names, to match a drawing, is a rule change rather than a
  // conformance fix". The PO made it a rule change on 2026-08-22, with five
  // screenshots: *"look at tabs and details within tabs"*. BR-MET-045 is
  // AMENDED, dated, in the metering business rules.
  it("DEF-578: r10's five tabs, no Accounts tab — and CR-070 wave O's sixth", () => {
    // ⚠ AMENDED 2026-09-04 (CR-070 wave O). `DEF-578` removed a tab; this wave
    // ADDS one, and the two are not the same kind of change. Accounts went
    // because it asserted something nothing could support. **Work orders**
    // arrives because `/connections/<uuid>` stopped being a place a person
    // navigates to — PO: *"you cannot have two differnt screen - this is an
    // integration problem"* — and a job at an address has to be reachable from
    // the address.
    //
    // ⚠ AND **BUILD** IS NOT IN THIS LIST, ON ANY PREMISES (CR-162-BRC10, PO
    // 2026-10-02: *"build ta on premises is not required"*). A New Connection
    // is tracked on its own page; a Pending premises links to it from the
    // header instead (`PendingBuildLink`).
    expect(premisesTabs(t).map((tab) => tab.id)).toEqual([
      "overview",
      "units",
      "common-areas",
      "assets",
      "work-orders",
      "audit",
    ]);
    const html = renderDetail("/premises/p-101", premise());
    // r10's labels, including `Audit log` where this shipped `Audit`.
    for (const label of ["Overview", "Units", "Common areas", "Assets", "Audit log"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).not.toContain(">Accounts<");
    // Drawn: `412 Cypress Row, Silver Creek, TX 78611` — state and postcode
    // are ONE field on an envelope and take no comma between them.
    expect(premisesHeadline(premise())).toBe("1408 Bluestem Ln, Katy, TX 77494");
  });

  // The route that REPLACES the removed tab, asserted so the removal cannot
  // quietly become a dead end: a premise's accounts are reached through its
  // units, which is what the removed tab's own copy said.
  it("DEF-578: with the Accounts tab gone, the Units tab still links every unit to its own detail", () => {
    const html = renderDetail("/premises/p-101?tab=units", premise({ unit_rows: [unitRow()] }));
    expect(html).toContain(`href="/${TEST_TENANT}${unitDetailPath("u-101a")}"`);
  });

  it("DEF-MET-10003: no City GIS — the City's three rows are not drawn, the import reference is", () => {
    const html = renderDetail(
      "/premises/p-101?tab=overview",
      premise({ unit_rows: [unitRow()] }),
      [],
      null,
      null,
      undefined,
      "none",
    );
    expect(html).toContain(">Import reference<");
    for (const label of ["Parcel", "On the map", "Checked against GIS"]) {
      expect(html, `${label} is drawn for a utility with no City GIS`).not.toContain(`>${label}<`);
    }
  });

  it("DEF-578 / DEF-584: Overview is r10's TWO-COLUMN grid, in r10's own field order", () => {
    const html = renderDetail(
      "/premises/p-101?tab=overview",
      premise({
        area_code: "route-3",
        area_name: "Route 3",
        area_parent_code: "north",
        area_path: "North district · Route 3",
        unit_rows: [unitRow(), COMMON_HALLWAY],
      }),
    );
    // ⚠ **ONE COLUMN OF THIRTEEN, WHICH IS WHAT THE FRAME DRAWS.** This
    // asserted `grid-cols-2` + `max-md:grid-cols-1` until 2026-09-10, from
    // r10. The blueprint supersedes r10 here — `CR-089-p019` §5 is headed
    // *"Fact rows — THIRTEEN, ONE column, in this exact order"* — so the old
    // pair was asserting a layout the agreed design does not have.
    //
    // ⚠ **AND THE ORDER IS ASSERTED, NOT JUST THE PRESENCE.** Row order is the
    // frame's, and a `toContain` per label passes on any arrangement — the
    // failure this whole file exists to catch is a row quietly moving.
    // ⚠ **`Import reference` THEN `Parcel` FROM 2026-10-07 (`DEF-MET-10008`).**
    // The row that read `Parcel` was `external_ref` — the IMPORT key since
    // `BR-MET-1173` — so it reads as what it is, and the City's parcel
    // (`gis_parcel_id`) takes the drawn word in the drawn place beneath it.
    const DRAWN_ROWS = [
      "Address",
      "Import reference",
      "Parcel",
      "On the map",
      "Checked against GIS",
      CITY_LIMITS_LABEL,
      "Area",
      "Sub-area",
      "Read route",
      "Billing cycle",
      SERVICES_LABEL,
      // PO 2026-09-23: the one vocabulary is the ACCOUNT, shortened at their
      // request ("make it small m acct or somehing line this"). OQ-MET-12610.
      "Master a/c",
      "Managed by",
      "Common areas",
    ];
    // ⚠ **SEARCH THE FACT LIST, NOT THE WHOLE PAGE — MY OWN FIRST DRAFT OF
    // THIS ASSERTION LOOKED AT THE WRONG THING.** Five of the six TABS are
    // also fact-row labels somewhere in this product, and `Common areas` is
    // both a tab and row 13. Searching the whole document found the TAB at
    // index 2255 and reported row 13 as out of order against a row at 6787 —
    // a true-looking failure about a screen that was correct. The fact rows
    // are the only thing after the tab strip, so anchor there.
    const FACT_ROW = 'class="flex justify-between gap-4 py-3';
    const factsAt = html.indexOf(FACT_ROW);
    expect(factsAt, "the Overview draws no fact rows at all").toBeGreaterThan(-1);
    const facts = html.slice(factsAt);

    let cursor = -1;
    for (const label of DRAWN_ROWS) {
      const at = facts.indexOf(`>${label}<`);
      expect(at, `${label} is not drawn on the Overview`).toBeGreaterThan(-1);
      expect(at, `${label} is drawn out of the frame's order`).toBeGreaterThan(cursor);
      cursor = at;
    }
    // `Units` duplicated the KPI tile above it; `External ref` is a column on
    // the list and a field on the Edit form. Both dropped, neither hidden.
    expect(html).not.toContain(">External ref<");
    // BR-MET-071's tag, split into r10's two facts from what the server sent.
    expect(html).toContain("North district");
    expect(html).toContain("Route 3");
    // BR-MET-101: the common areas are NAMED, because their labels are served.
    expect(html).toContain("Hallway &amp; exterior lighting");
    // ⚠ **THE LAYOUT HALF (`DEF-584`).** The stated absence used to be a
    // full-width `<div>` dropped inside a `<dl class="met-facts">` — a grid
    // item that is neither `dt` nor `dd` takes a CELL, so the label column grew
    // to its width and every value was squeezed into a ribbon down the right
    // edge. The `<dl>` is gone; the absence is a VALUE in its own row.
    expect(html).not.toContain("met-facts");
    expect(html).not.toContain("rating-arrives");
  });

  it("DEF-578: an untagged premise says so in BOTH area facts rather than inventing a parent", () => {
    const html = renderDetail("/premises/p-101?tab=overview", premise());
    expect(html).toContain("Sub-area");
    expect(premisesAreaSplit(premise())).toEqual({ area: null, subArea: null });
    // A TOP-LEVEL tag is an Area with no sub-area — not a sub-area of itself.
    expect(
      premisesAreaSplit(premise({ area_code: "north", area_name: "North district", area_path: "North district" })),
    ).toEqual({ area: "North district", subArea: null });
    // DEF-583: the parent's NAME exists only inside `area_path`, so a join the
    // server rewords degrades to the CODE — traceable, never blank.
    expect(
      premisesAreaSplit(
        premise({ area_code: "r3", area_name: "Route 3", area_parent_code: "north", area_path: "Route 3" }),
      ),
    ).toEqual({ area: "north", subArea: "Route 3" });
  });

  it("DEF-578: a premise with no common areas states that, and does not draw an em-dash", () => {
    const html = renderDetail("/premises/p-101?tab=overview", premise({ unit_rows: [unitRow()] }));
    expect(html).toContain("None on this premise");
  });

  it("BR-MET-036: occupancy renders, it never edits — and the Occupant cell is where it reads", () => {
    const html = renderDetail("/premises/p-101?tab=units", premise({ unit_rows: [unitRow()] }));
    // The occupant is a NAME and its account, which is what `DEF-4740` put in
    // place of the old `Occupancy` state word: *"the state is in the status
    // pill where it belongs."*
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain('data-occupant-state="named"');
    expect(html).toContain("U-00101-A");
    // ⚠ **THIS CASE USED TO ASSERT `not.toContain("<input")` AND `("<select")`
    // AND THAT STOPPED BEING A STATEMENT ABOUT OCCUPANCY THE MOMENT THE TAB
    // GAINED THE SHARED TOOLBAR (`DEF-4739`).** The search box is an
    // `<input>`, the filter panel is full of checkboxes and the pager's
    // rows-per-page is a `<select>` — none of them has anything to do with
    // occupancy, and a blanket ban on two tag names would have failed on
    // furniture the blueprint asks for. What BR-MET-036 actually forbids is an
    // EDITOR of the derived field, so that is what is asserted.
    expect(html.toLowerCase()).not.toContain("<form");
    expect(html).not.toContain('name="occupancy"');
  });

  it("US-MET-002 TC-1: the meters cell carries the (sub)/(master) qualifier the server supplied", () => {
    const html = renderDetail("/premises/p-101?tab=units", premise({ unit_rows: [unitRow()] }));
    expect(html).toContain("M-7001");
    expect(html).toContain("W-7001");
    expect(html).toContain("(sub)");
  });

  // ── CR-089 wave C · C1 (PUJ-12) ─────────────────────────────────────────
  //
  // The tab listed a building's flats and carried NO MONEY, so *which of my
  // flats owes something* — the question a landlord rings about — could not be
  // answered from the tab that lists them.
  //
  // The shape is wave E's `owed_for_units`, adopted rather than duplicated:
  // `_balance_cells`' own output, the same derivation the accounts list and
  // the S21 header show.

  const OWED = {
    account_id: "acc-1",
    account_no: "A-00412",
    balance: "61.4000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_unavailable: [] as string[],
    balance_not_yet_billable: false,
  };

  it("C1: the Units tab carries what each unit owes, at two decimals, in its own column", () => {
    const html = renderDetail(
      "/premises/p-101?tab=units",
      premise({ unit_rows: [unitRow({ owed: OWED })] }),
    );
    expect(html).toContain("Owed");
    // CLAUDE.md hard rule 2 — stored at four, DISPLAYED at two, and the
    // rounding happens here rather than on the server.
    expect(html).toContain("$61.40");
    expect(html).not.toContain("61.4000");
    // A money column is scanned DOWN, so the digits have to line up.
    expect(html).toContain("tabular-nums");
    expect(html).toContain('data-owed-state="figure"');
    // ⚠ **THE ALIGNMENT IS ASSERTED ON A BLOCK CHILD, AND THAT IS THE WHOLE
    // POINT OF THE ASSERTION.** `text-right` on the `<td>` renders LEFT:
    // `PlainTable` writes `[&_td]:text-left` on the table at the same
    // specificity, and the compiler emits the table's last. The browser is
    // what found it — `tsc`, eslint and a `toContain("text-right")` all pass
    // over a class that is in the DOM doing nothing (hard-won law 2's shape).
    expect(html).toContain('class="block text-right tabular-nums"');
  });

  it("C1: a vacant unit says who the base charge goes to, and shows NO figure", () => {
    // ⚠ THIS IS THE ONE PLACE THIS WAVE DEPARTS FROM CR-089 §6's WORKED LINE,
    // which writes `Unit 4 · 0.00 · Vacant — …`. `owed_for_units` resolves the
    // OCCUPYING account, so a vacant unit produces no ledger read at all — and
    // a unit whose tenant left still owing has a CLOSED account that map
    // excludes. A `0.00` there would say *nothing is owed* over a real debt,
    // which is DEF-138 word for word. The seam's own contract agrees: "the
    // caller says vacant, never 0.00".
    const html = renderDetail(
      "/premises/p-101?tab=units",
      premise({
        unit_rows: [
          unitRow({
            unit_no: "U-00101-D",
            label: "Unit 4",
            occupancy: "vacant",
            occupant: null,
            account_no: null,
            status: "vacant",
            owed: null,
          }),
        ],
      }),
    );
    // BR-MET-094 (a vacancy IS billed, automatically) + BR-CUS-170 (the
    // owner's master account carries the base charge of every unlet unit).
    expect(html).toContain("Vacant — base charges bill to the owner");
    expect(html).not.toContain("$0.00");
    expect(html).toContain('data-owed-state="no-account"');
  });

  it("C1: books that could NOT be asked say so — they never print a zero", () => {
    const html = renderDetail(
      "/premises/p-101?tab=units",
      premise({
        unit_rows: [
          unitRow({
            owed: {
              ...OWED,
              balance: null,
              balance_unavailable: ["no_ar_designation"],
            },
          }),
        ],
      }),
    );
    // DEF-138 — a guard that cannot check must not pass, and a COLUMN that
    // cannot read must not print `0.00`.
    expect(html).toContain("We could not read this.");
    expect(html).not.toContain("$0.00");
    expect(html).toContain('data-owed-state="unreadable"');
  });

  it("C1: a payload with no `owed` key at all draws the quiet dash", () => {
    // `undefined` means *not sent*, which is not the same claim as *nothing is
    // owed* and not the same claim as *nobody is renting this* either.
    const html = renderDetail("/premises/p-101?tab=units", premise({ unit_rows: [unitRow()] }));
    expect(html).toContain("Owed");
    expect(html).not.toContain("$0.00");
    expect(html).not.toContain("Vacant — base charges bill to the owner");
  });

  it("C1: a common area gets the master-account sentence, never the vacancy one", () => {
    // BR-MET-101: the flag is what separates a common area from a vacant unit
    // billed to the owner, so telling a clerk a hallway is *vacant* is the one
    // place those two rows must not read the same.
    const html = renderDetail(
      "/premises/p-101?tab=units",
      premise({
        unit_rows: [unitRow({ is_common_area: true, occupancy: "vacant", owed: null })],
      }),
    );
    // ⚠ `renderToStaticMarkup` escapes the apostrophe, so the raw sentence
    // never appears in the string. Asserted either side of it rather than
    // against `&#x27;`, which is a fact about React and not about this screen.
    expect(html).toContain("Always billed to the owner");
    expect(html).toContain("Always billed to the owner.");
    expect(html).not.toContain("Vacant — base charges bill to the owner");
  });

  // ⚠ **THIS CASE ASSERTED THE DEFECT — `DEF-579`.** It read *"the Audit tab
  // LINKS to the one audit viewer"* and closed with `expect(html).not
  // .toContain("<table")`, so the tab that drew NO ROWS was pinned as correct
  // by the suite. `BR-AUD-010` (CONFIRMED) says a per-entity Audit tab is a
  // read-only WINDOW into `audit_log` **and** links to S61 — render AND link.
  // The PO reported the missing half on 2026-08-22.
  it("DEF-579 / BR-AUD-010: the Audit log tab draws THIS premises' own rows, and still links to the full viewer", () => {
    expect(auditViewerPath("premises", "p-101")).toBe(
      "/audit-log?f.entity_type=premises&f.entity_id=p-101",
    );
    const html = renderDetail("/premises/p-101?tab=audit", premise(), [], null, auditResult([
      {},
      { actor: null, action: "premises.created", summary: "Premise created · 3 units" },
    ]));
    expect(html).toContain("<table");
    // ⚠ **THE DRAWN SIX, AND `Actor` IS NOW `Who` (`DEF-4740`).** The
    // blueprint's WHAT CHANGED block renames the column and pulls the values
    // out of the Action cell: *"From and To as columns, so a history is read
    // down the page instead of expanded row by row. That is the whole use of
    // an audit log: seeing what a field used to say."*
    expect(html).toContain(">When<");
    expect(html).toContain(">Who<");
    expect(html).toContain(">What changed<");
    expect(html).toContain(">From<");
    expect(html).toContain(">To<");
    expect(html).not.toContain(">Actor<");
    // The rows themselves — the thing the tab did not have.
    expect(html).toContain("Alex Reed");
    // AMENDED 2026-08-24 (DEF-645). This used to assert the raw action code
    // `premises.created` and the server's summary string. Both are what the PO
    // photographed on the account tab — same cell, same component — so the
    // Action column now reads as a sentence and the recorded values open
    // behind a disclosure instead of being truncated with "(+N more)".
    expect(html).toContain("Premises updated");
    expect(html).toContain("Premises added");
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("premises.created");
    expect(html).toContain('data-audit-action="premises.created"');
    // BR-AUD-003: a null actor is a SYSTEM job, named.
    expect(html).toContain("System job");
    // BR-AUD-010's second half is kept: the window says which window answered
    // and the full log is one click away.
    expect(html).toContain("/audit-log?f.entity_type=premises&amp;f.entity_id=p-101");
    expect(html).toContain("Showing the last 2 years");
  });

  // ── CR-089 wave C · C6 (PUJ-17) ─────────────────────────────────────────
  //
  // The row said WHAT happened. What a person is on this tab to read is what
  // the value WAS, and that was behind an `Expand`, one row at a time.

  it("C6: an audit row shows the old value beside the new one, with no press", () => {
    const html = renderDetail(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      null,
      auditResult([
        {
          action: "premises.updated",
          // Served on the ROW because the query names an entity
          // (`audit_page(..., with_values=True)`), so this costs no request.
          before: { owner_manager: null },
          after: { owner_manager: "Creekside Holdings LP" },
        },
      ]),
    );
    // ⚠ **THE VALUES ARE COLUMNS NOW, NOT A `label: before → after` LIST
    // INSIDE THE ACTION CELL (`DEF-4740`).** The arrow went with the list:
    // reading across the row IS the arrow.
    expect(html).toContain("Creekside Holdings LP");
    expect(html).toContain('data-audit-field="owner_manager"');
    expect(html).toContain('data-audit-from="owner_manager"');
    expect(html).toContain('data-audit-to="owner_manager"');
    // ⚠ **AND THE SHARPEST MISS THE BLUEPRINT RECORDS ON THIS SCREEN: AN
    // ABSENT PREVIOUS VALUE IS DRAWN AS AN ABSENCE.** *"A property that had no
    // route now says `None → Route 12`, which is a different fact from a route
    // being changed."* Rendered as nothing, the two read identically.
    expect(html).toMatch(/data-audit-from="owner_manager"><span class="italic[^"]*">Not set</);
    // ⚠ AND THE PRESS IS GONE, which is the half that would pass wrongly if
    // the values were merely ADDED underneath a disclosure that still opened.
    // The press is the `Expand` control the shared `Disclosure` draws; on this
    // tab the audit rows are the only thing that could draw one.
    expect(html).not.toContain("Expand");
    expect(html).not.toContain("aria-expanded");
  });

  it("C6: a payload that does not carry the values keeps the expandable cell", () => {
    // `undefined` means *not sent*; drawing an absence there would claim the
    // event recorded nothing. Old payloads and the S61 list both land here.
    const html = renderDetail(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      null,
      auditResult([{ action: "premises.updated" }]),
    );
    expect(html).toContain("Expand");
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain('data-audit-inline=""');
  });

  it("DEF-579: an entity with nothing recorded says so — it never draws an empty table", () => {
    const html = renderDetail("/premises/p-101?tab=audit", premise(), [], null, auditResult([]));
    expect(html).not.toContain("<table");
    // ⚠ NOT "never" — the log is time-bounded server-side (BR-AUD-013), so the
    // sentence is about the WINDOW, and the full viewer with its archive
    // opt-in is still offered.
    expect(html).toContain("in the window the log covers");
    expect(html).toContain("/audit-log?f.entity_type=premises&amp;f.entity_id=p-101");
  });

  it("DEF-4740 / BR-AST-044: three type columns become two, and Service and Size arrive", () => {
    const html = renderDetail("/premises/p-101?tab=assets", premise(), [
      {
        id: "a1",
        asset_no: "M-4021",
        // ⚠ ADDED 2026-09-09 (CR-089 wave C `C3`). `tab` is `AssetRow`'s own
        // required field — the server's `asset_types.category` — and this
        // fixture had always omitted it. It went unnoticed because nothing
        // read it; the moment the tab GROUPS by it, a fixture that does not
        // say which family a net meter is in cannot test the rule any more.
        tab: "meters",
        type: "net_meter",
        type_name: "Net meter",
        meter_type_name: "AMI",
        read_method_name: "AMI",
        // ⚠ SERVED ALL ALONG AND READ BY NOTHING — that is `DEF-4740` in one
        // line: `assets.col.service` and `assets.col.sizeClass` were both in
        // the eleven catalogues and neither was ever drawn on this tab.
        service: "water",
        size_class: "Class 200",
        assigned_to: "Unit A",
        install_date: "2024-03-12",
        status_name: "Installed/Active",
      },
    ]);
    // ⚠ **THE BLUEPRINT REVERSES WHAT THIS CASE USED TO ASSERT, IN WRITING.**
    // It asked for `Asset type · Meter type · Read method` here; the drawn
    // frame carries `What it is` and `Service` and neither of the other two —
    // *"Three type columns become two — what it is, and the service it belongs
    // to."* `BR-AST-044` is untouched: it binds the DETAIL view (S50) and the
    // list filters, not every table, and its own amendment makes `meter_type`
    // UNAVAILABLE on a non-measuring type.
    expect(html).toContain(">What it is<");
    expect(html).toContain(">Service<");
    expect(html).toContain(">Size<");
    expect(html).toContain(">Where<");
    expect(html).not.toContain(">Meter type<");
    expect(html).not.toContain(">Read method<");
    // The two absent columns, with their values, from the row the API sends.
    expect(html).toContain("Water");
    expect(html).toContain("Class 200");
    expect(html).toContain("M-4021");
    // BR-SHL-034: the install date went through the shared formatter.
    expect(html).toContain("03/12/2024");
  });

  // ── CR-089 wave C · C3 and C4 (PUJ-14) ──────────────────────────────────
  //
  // The tab drew ONE flat table of seven columns, three of which said what
  // kind of thing a row was and none of which said when it was last read. A
  // cart and a meter were drawn identically.

  /** Four assets across both families, shaped as the server serves them. */
  const MIXED_ASSETS = [
    {
      id: "a1",
      asset_no: "M-4021",
      tab: "meters",
      type: "meter",
      type_name: "Meter",
      meter_type_name: "AMI",
      read_method_name: "AMI",
      assigned_to: "Unit A",
      install_date: "2024-03-12",
      status_name: "Installed",
      last_read: { consumption: "412.0000", unit: "kgal", read_at: "2026-08-31" },
    },
    {
      id: "a2",
      asset_no: "M-4022",
      tab: "meters",
      type: "meter",
      type_name: "Meter",
      meter_type_name: "walk-by",
      read_method_name: "Manual",
      assigned_to: "Unit B",
      install_date: "2024-03-12",
      status_name: "Installed",
      last_read: null,
    },
    {
      id: "a3",
      asset_no: "FS-00311",
      tab: "behind_the_meter",
      type: "fire_line",
      type_name: "Fire service line",
      meter_type_name: null,
      read_method_name: null,
      assigned_to: "Unit A",
      install_date: null,
      status_name: "Installed",
    },
    {
      id: "a4",
      asset_no: "CRT-08820",
      tab: "behind_the_meter",
      type: "container_cart",
      type_name: "Container / Cart",
      meter_type_name: null,
      read_method_name: null,
      assigned_to: "Unit B",
      install_date: null,
      status_name: "Installed",
    },
  ];

  it("DEF-4739 / C3: what BILLS still leads, the two families are the filter, the counts are the footer", () => {
    const html = renderDetail("/premises/p-101?tab=assets", premise(), MIXED_ASSETS);
    // ⚠ **THE TWO GROUP HEADING ROWS ARE NOT BUILT, AND THAT IS A RECORDED
    // DIVERGENCE RATHER THAN A SILENT LOSS.** The blueprint draws one table
    // with a full-width caption row before each family; `DataTable` has no
    // group-row capability and growing the kit for one tab is a bigger act
    // than this fix. Everything those headings bought a clerk survives in
    // three things the frame also draws, and all three are asserted here.
    // 1 · the rows that BILL lead, whatever the page is sorted by.
    expect(html.indexOf("M-4021")).toBeLessThan(html.indexOf("CRT-08820"));
    // 2 · the two family names are the `+ Filter ▾` panel's options.
    expect(html).toContain("Meters and sub-meters");
    expect(html).toContain("Behind the meter");
    // 3 · the counts are the drawn footer sentence — one meter carries a
    //     reading, one does not, and two rows are not read by design.
    expect(html).toContain("1 read this cycle, 2 not read by design");
    // …and the one still to read LEADS it, which is the blueprint's own
    // overdue-reads state: *"the count leads the footer"*.
    expect(html).toContain('data-assets-still-to-read="1"');
  });

  it("DEF-4739 / C3: a property with nothing behind the meter says so in the footer, not by hiding a heading", () => {
    const html = renderDetail("/premises/p-101?tab=assets", premise(), [MIXED_ASSETS[0]]);
    expect(html).not.toContain("CRT-08820");
    expect(html).toContain("1 read this cycle, 0 not read by design");
    // The DIMENSION is still offered: the option list is the product's two
    // families, not this building's, and the rows are what say it has none.
    expect(html).toContain("Behind the meter");
  });

  it("C4: the last-read column says the DATE, or *not read* and why — three different sentences", () => {
    const html = renderDetail("/premises/p-101?tab=assets", premise(), MIXED_ASSETS);
    expect(html).toContain("Last read");
    // A meter with a reading: the date, through the shared formatter.
    expect(html).toContain("08/31/2026");
    // A meter with none: a fact about THIS meter, and one worth chasing.
    expect(html).toContain("no read yet");
    // ⚠ THE TWO THE TASK NAMES BY NUMBER. The reason is the type's own
    // billing shape — CR-063 prices a fire line by diameter, BR-RAT-090
    // prices trash per cart — and neither is metered.
    expect(html).toContain("not read — billed on size");
    expect(html).toContain("not read — billed per cart");
    expect(html).toContain('data-not-read="fire_line"');
    expect(html).toContain('data-not-read="container_cart"');
  });

  it("C4: a behind-the-meter type this build does not know falls to the general sentence", () => {
    // BR-TEN-036 — `asset_types` is tenant-extensible, so a utility may add a
    // kind nothing here has heard of. Claiming *billed on size* about it would
    // be inventing a price rule.
    const html = renderDetail("/premises/p-101?tab=assets", premise(), [
      {
        ...MIXED_ASSETS[2],
        id: "a9",
        asset_no: "XX-1",
        type: "penstock_valve",
        type_name: "Penstock valve",
      },
    ]);
    expect(html).toContain("not read — we own it");
    expect(html).not.toContain("billed on size");
  });

  it("DEF-4740 / C3-C4: `Meter type` and `Read method` are drawn on NEITHER family now", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-10** — *"dropped from
    // the behind-the-meter table only"* — and the blueprint draws neither
    // column on either family: *"Three type columns become two."* There is ONE
    // table now, so "on the metered one" has nowhere left to mean.
    const html = renderDetail("/premises/p-101?tab=assets", premise(), MIXED_ASSETS);
    expect(html).not.toContain(">Meter type<");
    expect(html).not.toContain(">Read method<");
    expect(html).toContain(">What it is<");
    expect(html).toContain(">Service<");
  });

  it("the unit link points at the unit's own detail route", () => {
    expect(unitDetailPath("u-101a")).toBe("/premises/units/u-101a");
  });

  it.todo(
    "US-MET-001 detail TC (isolation): a cross-tenant premises id answers not-found under RLS — server scope (G5)",
  );
});

// ── US-SHL-020 / BR-SHL-044 — S14 through the shared page header ────────────
// The prototype (UtilityBilling.html line 713) draws Premises and Units as ONE
// head with two tabs; this app routes them separately, so the law under test is
// that the two routes wear the SAME header and the slot's contents — not the
// slot — are what change.

/** The header, up to the tab strip: where the ONE primary action must live. */
function headerActions(html: string): string {
  const end = html.indexOf('class="page-header-tabs"');
  return end === -1 ? html : html.slice(0, end);
}

describe("US-SHL-020 — S14 wears the shared page header (BR-SHL-044)", () => {
  it("TC-1: the primary action is per-TAB — the same slot, a different button", () => {
    // ONE config, rendered at both ids. Premises and Units are two routes, so
    // this is where the "same slot" claim is actually provable: the id is the
    // only thing that differs between these two renders.
    const tabs = premisesStripTabs({
      t,
      writeBlockedReason: null,
      onNewPremise: () => undefined,
      onNewUnit: () => undefined,
    });
    const render = (activeTabId: string): string =>
      renderToStaticMarkup(
        <MemoryRouter>
          <PageHeader title="Premises" tabs={tabs} activeTabId={activeTabId} />
        </MemoryRouter>,
      );

    const onPremises = render(PREMISES_TAB_PREMISES);
    expect(headerActions(onPremises)).toContain("+ New premise");
    expect(onPremises).not.toContain("+ New unit");

    const onUnits = render(PREMISES_TAB_UNITS);
    expect(headerActions(onUnits)).toContain("+ New unit");
    expect(onUnits).not.toContain("+ New premise");

    // …and the live screen is that config, not a second copy of it.
    const html = renderList("/premises", { list: page([premise()]), access: "Full" });
    expect(headerActions(html)).toContain("+ New premise");
    expect(html).not.toContain("+ New unit");
    // CR-023 P0: THREE tabs, and `/premises/units` is byte-identical to what it
    // was — TC-24's property, asserted here because it is the one thing the
    // restructure could silently have broken for every existing deep link.
    expect(PREMISES_TAB_STRIP.map((tab) => tab.path)).toEqual([
      "/premises",
      "/premises/units",
      "/premises/imports",
    ]);
  });

  it("TC-2: the Premises tab draws NO explainer at all", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-19**, exactly as the
    // Units tab's TC-2 did until 2026-09-10, and for the same three reasons.
    // The tab drew a 27-word explainer below the strip: *"A premise is a
    // physical property or address. Each premise may contain one or more units
    // (apartments, suites, sub-metered spaces) — those live in the Units tab."*
    //
    // (1) The PO asked for it, 2026-09-19: *"On premsies list page reduce this
    //     text - A premise is a physical property or address..."*.
    // (2) B14 rule 33 puts RATIONALE at ZERO words on screen, and a definition
    //     of *premise* plus a pointer at a tab drawn two lines above is
    //     rationale end to end — rule 32 bans the pointer a second time, as
    //     *a row never repeats what its own control offers*.
    // (3) The blueprint's own stated absence for this screen is *"No prose on
    //     the screen at all — a list explains itself or it is the wrong list."*
    //     (`CR-089-p005-property-list.md`).
    const html = renderList("/premises", { list: page([premise()]), access: "Full" });
    expect(html).not.toContain("A premise is a physical property or address.");
    expect(html).not.toContain("page-header-explainer");
    // The Units tab's guidance belongs to the Units route, not to this one.
    expect(html).not.toContain("A unit is a metered space inside a premise");
  });

  it("TC-5: the LIST screen has no back link; the DETAIL screen has one", () => {
    const list = renderList("/premises", { list: page([premise()]), access: "Full" });
    expect(list).not.toContain("page-header-back");

    const detail = renderDetail("/premises/p-101", premise());
    expect(detail).toContain("page-header-back");
    // The arrow belongs to the component; the label is the destination's name,
    // so the rendered link still reads exactly as the catalog's "← Premises".
    expect(detail).toContain("← Premises");
    expect(detail).not.toContain("← ← ");
  });

  it("TC-6: the header offers exactly one primary action", () => {
    const html = headerActions(renderList("/premises", { list: page([premise()]), access: "Full" }));
    expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
    // CR-023 §3: the secondary CHANGES with the tab — the premises import
    // here, `↑ Import units` on the Units tab — and it is beside the primary,
    // never in it. B14 rule 4 gives `↑` to import.
    // ⚠ **IT READS `↑ Import` FROM 2026-09-10 AND SAID `↑ Import premises`
    // BEFORE.** The blueprint's head draws the short form (page 6) and the tab
    // strip directly below it already says which list you are on, so the
    // qualifier was a word the head repeated. The LONG form is still the
    // catalogue's `metering.premises.action.import` and is still what the
    // Imports tab draws, where it sits beside `↑ Import units` and is the only
    // thing telling the two apart — see the PRM-04 case below.
    expect(html).toContain("↑ Import");
    expect(html).not.toContain("↑ Import premises");
    expect(html).not.toContain("↑ Import units");
  });

  it("BR-SHL-025 survives the move: a View role sees the header primary disabled WITH its reason", () => {
    const html = headerActions(renderList("/premises", { list: page([premise()]), access: "View" }));
    expect(html).toContain("+ New premise");
    expect(html).toContain("disabled");
    expect(html).toContain("Your role can view this but not change it.");
  });

  it("the detail header carries the kicker, the roll-up and the status pill in the ruled order", () => {
    const html = renderDetail("/premises/p-101", premise());
    expect(html.indexOf("page-header-back")).toBeLessThan(html.indexOf("kicker"));
    expect(html.indexOf("<h1")).toBeGreaterThan(-1);
    expect(html.indexOf("kicker")).toBeLessThan(html.indexOf("<h1"));
    expect(html.indexOf("<h1")).toBeLessThan(html.indexOf("page-header-rollup"));
    // ⚠ **AMENDED 2026-08-22 (`DEF-578`) — THE THREE FACTS SWAPPED SLOTS.**
    // This read `Premise · Single-family` in the eyebrow and `P-00101` in the
    // H1. r10 draws `Premise · P-10432 · North district · Route 3` / `1408 Elm
    // Street` / a descriptive sub-line, so the NUMBER is the eyebrow's, the
    // STREET LINE is the title's and the type is the sub-line's.
    // ⚠ **THE KICKER IS `Premise` ALONE — AMENDED 2026-09-10 (`DEF-MET-4803`).**
    // This asserted `Premise · P-00101`, and `Premise · P-00101 · North
    // district · Route 3` when tagged. `CR-089-p019` §1 draws the kicker as the
    // bare word and moves the property number down to the identity line:
    // *"the property number LEADS the identity line rather than sitting in the
    // kicker. It appears once, in the header, and not again in the facts
    // below."* The area went further, to fact rows 6 and 7.
    expect(html).toContain("Premise");
    expect(html).not.toContain("Premise · P-00101");
    expect(html).toMatch(/<h1[^>]*>1408 Bluestem Ln<\/h1>/);
    // ⚠ **THE NUMBER MUST STILL BE ON SCREEN, and that is the half worth
    // asserting** — a fact that moves is fine, a fact that vanishes is the
    // defect. `premisesSubline` joins number · locality · type.
    expect(html).toContain("P-00101");
    expect(html).toContain("Single-family");
    // The area is no longer in the header at all; it is a fact row, so a tagged
    // premise must draw it THERE and not back in the eyebrow.
    const tagged = renderDetail(
      "/premises/p-101",
      premise({ area_code: "route-3", area_name: "Route 3", area_parent_code: "north", area_path: "North district · Route 3" }),
    );
    expect(tagged).not.toContain("Premise · P-00101 · North district");
    expect(tagged).toContain("North district");
    // The pill is in the action row, ahead of any button.
    expect(headerActions(html)).toContain('class="pill bg-success-100 text-success-700"'); // CR-018: the ok tone's utilities
    expect(html).toContain("page-header-actions");
    // ⚠ **THIS SCREEN HAD NO HEADER ACTION AT ALL AND NOW HAS TWO (CR-023 P2).**
    // r10's PRM-02 action row is `● Active │ ↓ Export CSV │ ✏ Edit │ + Add
    // unit`, so Edit is a secondary and Add unit is the one primary. `↓ Export
    // CSV` is deliberately NOT here: the shared export posts a LIST state and
    // there is no per-premises export, so the button would have exported the
    // whole tenant under a label naming one property.
    expect(headerActions(html)).toContain("Edit");
    expect((headerActions(html).match(/data-variant="primary"/g) ?? []).length).toBe(1);
    expect(html).not.toContain("Export CSV");
  });

  it("CR-023 §2A.3: the Jurisdiction line reads the FLAG — the stated absence is gone (DEF-507)", () => {
    // ⚠ **THIS CASE USED TO ASSERT THE OPPOSITE AND THE REVERSAL IS THE FIX.**
    // It pinned `data-tracks="DEF-507"` and `not.toContain("Inside city
    // limits")` — correct while `premises_detail_dict` served twenty keys and
    // not this one. The selector now serves `inside_city_limits` as its three
    // real states, so the paragraph explaining our own blindness is a lie that
    // reads as honesty (PO, 2026-08-26: *"Why Juridiction is showing the in
    // text it should shown inside city and outside city"*).
    const html = renderDetail("/premises/p-101", premise({ inside_city_limits: true }));
    // `Jurisdiction` until 2026-09-10; the frame draws the clerk's word.
    expect(html).toContain(CITY_LIMITS_LABEL);
    expect(html).toContain("Inside city limits");
    expect(html).not.toContain('data-tracks="DEF-507"');
    // The r10 line reads "Inside city limits — no ×1.5 multiplier". The SECOND
    // half is a claim about the RATE and this payload has no field for it, so
    // it is still not drawn. (Asserted on the WORD: `1.5` alone appears in
    // Tailwind spacing classes all over this page and would pass for the wrong
    // reason — a check whose output cannot tell pass from fail is worse than
    // none.)
    expect(html).not.toContain("multiplier");
  });

  it("CR-023 §2A.3: outside the city says so, in the clerk's words and not a raw false", () => {
    const html = renderDetail("/premises/p-101", premise({ inside_city_limits: false }));
    expect(html).toContain("Outside city limits");
    expect(html).not.toContain("Inside city limits");
  });

  it("⚠ DEF-507: NOBODY ASKED renders a dash — never 'Outside city limits'", () => {
    // The state that decides money. `null` is *unrecorded*; "Outside" is an
    // ANSWER, and it is the answer that adds the outside-city surcharge to
    // every bill at this address. A screen that printed it on a guess would be
    // charging a customer on the strength of a default.
    const html = renderDetail("/premises/p-101", premise({ inside_city_limits: null }));
    expect(html).toContain(CITY_LIMITS_LABEL);
    expect(html).not.toContain("Outside city limits");
    expect(html).not.toContain("Inside city limits");
    // …and it is the SAME "we do not know" mark every other unanswered fact in
    // this grid uses (`<Dash />`), not a second vocabulary invented for this
    // row. Read out of the Jurisdiction fact's own value slot, so a dash
    // belonging to some other fact cannot satisfy it.
    const slot = html.slice(html.indexOf(CITY_LIMITS_LABEL), html.indexOf(CITY_LIMITS_LABEL) + 220);
    expect(slot).toContain('<span class="met-muted">—</span>');
  });

  it("CR-023 §2A.3: the Common areas tab refuses to draw a figure it has no source for", () => {
    // ⚠ **AMENDED 2026-08-22 AND THE PREMISE CHANGED WITH IT.** This case used
    // to render a premise with NO common areas and assert one whole-tab absence
    // note. BR-CUS-068 built the master account, so the tab draws real rows now
    // — and the thing worth protecting is narrower and sharper: **the two r10
    // figures that STILL have no source must not appear**, on the tab that
    // finally has data around them. `$69.60` needs the master bill run (billing
    // prices the anchor unit only) and `3.1%` is computed nowhere (OQ-327).
    const html = renderDetail(
      "/premises/p-101?tab=common-areas",
      premise({ units_common: 2, unit_rows: [COMMON_HALLWAY, COMMON_IRRIGATION] }),
    );
    // ⚠ **AMENDED 2026-09-10 (`DEF-4739`).** The three notes are still stated
    // and still cited — they are inside the tab's `About this tab` disclosure,
    // which B14 rule 32 requires to be CLOSED by default, and the kit unmounts
    // a closed disclosure's body rather than hiding it. So what is asserted
    // here is the half that matters and always did: **the two r10 figures that
    // have no source must not appear**, on a tab that now has real data around
    // them. The disclosure's own presence is asserted by its title.
    expect(html).toContain("About this tab");
    expect(html).not.toContain("3.1%");
    expect(html).not.toContain("$69.60");
    expect(html).not.toContain("$41.20");
  });

  it("BR-CUS-068: the tab names the premises' master account and links to it", () => {
    // The account number is the account's OWN from the BR-TEN-035 tenant series
    // — r10 draws `MA-1408` and minting a second numbering series is a rule
    // nobody signed (decision log 2026-08-22, judgment 4).
    const html = renderDetail(
      "/premises/p-101?tab=common-areas",
      premise({ units_common: 2, unit_rows: [COMMON_HALLWAY, COMMON_IRRIGATION] }),
      [],
      [masterRow()],
    );
    // ⚠ **TWICE, AND THE COUNT IS THE ASSERTION.** The KPI tile above the tabs
    // and the tab's own Master account fact read the SAME query, so a `toContain`
    // alone passes when EITHER renders — which is exactly what happened when
    // this case was proven RED: swapping the tab's number for the anchor unit id
    // left the tile's copy behind and the test stayed green. Both surfaces are
    // the deliverable; both are counted.
    // ⚠ **AMENDED 2026-09-10 (`DEF-4740`) — THE COUNT MOVED BECAUSE THE FACT
    // MOVED.** This used to count the number twice (the KPI tile and the tab's
    // Master account fact) and its links three times (both of those plus an
    // `Open master account` button at the foot). `CR-089` `F3` replaced the
    // tile set, and `CR-089-p025` §12 draws the fact block as ABSENT — the
    // blueprint puts the payer on EVERY ROW instead, in the `Billed to` column
    // it calls *"the only question this tab exists to answer"*. So the number
    // and the link are per-row now, and the count is still the assertion:
    // two common areas, two links, or the column is drawing from the wrong
    // place.
    expect((html.match(/A-00900/g) ?? []).length).toBe(2);
    expect(
      (html.match(new RegExp(`href="/${TEST_TENANT}/accounts/acc-master-1"`, "g")) ?? []).length,
    ).toBe(2);
    // The PAYER is the master account's own contact, not the premises column,
    // and it is named beside the account on every row.
    expect((html.match(/Miller Property LLC/g) ?? []).length).toBe(2);
    expect(html).not.toContain("MA-1408");
    // The two common areas, by name, with the plan column BR-MET-040 refuses on.
    expect(html).toContain("Hallway &amp; exterior lighting");
    expect(html).toContain("Shared irrigation");
    // …and the KPI tile above the tabs reads the SAME query, so it carries the
    // number too rather than the absence note it used to render.
    expect(html).not.toContain("does not exist in this product yet");
  });

  it("BR-CUS-068: with no master account the tab offers to create one, guarded by role", () => {
    const detail = premise({ units_common: 2, unit_rows: [COMMON_HALLWAY, COMMON_IRRIGATION] });
    const html = renderDetail("/premises/p-101?tab=common-areas", detail, [], []);
    // B14 rule 15 — an ordinary button says a WORD (PO 2026-08-20).
    expect(html).toContain("Create master account");
    expect(html).not.toContain("Create another");
    // ⚠ **AMENDED 2026-09-10 (`DEF-4740`).** `None yet` was the KPI tile's word
    // and the master fact's; both are gone (`CR-089` `F3`, and `p025` §12 draws
    // the fact block as absent). The blueprint's own STATE for an address with
    // nobody to bill is a `Billed to` cell reading **Needs an owner** that
    // LINKS to it — *"a common area with nobody to bill is a real problem, not
    // a blank cell"* — so that is what is asserted, on every row.
    expect((html.match(/Needs an owner/g) ?? []).length).toBe(2);
    expect(html).toContain(`href="/${TEST_TENANT}/premises/p-101?tab=overview"`);
  });

  it("DEF-565 / DEF-559: each master refusal picks its sentence from the envelope the SERVER sends", () => {
    // ⚠ **EVERY ENVELOPE BELOW IS THE ONE `create_master_account` ACTUALLY
    // RAISES, NOT ONE WRITTEN FROM READING IT.** That distinction IS DEF-565:
    // the first version of this mapping assumed the double-coverage guard
    // (BR-CUS-068) would answer "this premises already has a master", and the
    // guard that fires first is BR-CUS-017's occupancy check on the anchor —
    // so the branch never ran and a clerk was told to move a tenant out of a
    // hallway. Found by clicking, not by a test that agreed with its author.
    const say = (envelope: Parameters<typeof masterRefusalEnvelope>[0]) =>
      t(masterRefusalEnvelope(envelope).message_key, {
        ...(envelope.params ?? {}),
      });

    // 1 · BR-CUS-017 — `_refuse_if_unit_occupied`, which runs FIRST. Its params
    // carry `account_no` and NO `label`, and never say the occupant is a master.
    expect(
      say({
        code: "BIZ-002",
        br_ref: "BR-CUS-017",
        message_key: "customers.account.unit_already_occupied",
        params: { unit_id: "u-common-1", account_no: "AC-2026-00050", status: "active" },
      }),
    ).toBe("Account AC-2026-00050 holds it. Open that account.");

    // 2 · BR-CUS-068 — `_refuse_if_master_covered`, reachable by narrowing the
    // new master to an area the existing one covers WITHOUT anchoring on. Its
    // params DO name the unit and DO say the holder is a master.
    expect(
      say({
        code: "BIZ-002",
        br_ref: "BR-CUS-068",
        message_key: "customers.account.unit_already_occupied",
        params: { unit_id: "u-common-2", label: "Shared irrigation", account_no: "AC-2026-00050" },
      }),
    ).toBe(
      "Master account AC-2026-00050 covers Shared irrigation. Open that account.",
    );

    // 3 · BR-CUS-068 with NO message_key at all (DEF-559) — the sentence comes
    // from the server's own `reason` discriminator and names the unit.
    expect(
      say({
        code: "BIZ-002",
        br_ref: "BR-CUS-068",
        message_key: "errors.biz-state",
        params: {
          reason: "not_a_common_area_of_this_premises",
          label: "Unit A",
          unit_id: "u-101a",
        },
      }),
    ).toBe("Unit A is not a common area. Uncheck it.");

    // 4 · the same refusal when the server could NOT resolve a label: the
    // sentence drops the name rather than rendering "null" (DEF-332's shape).
    expect(
      say({
        code: "BIZ-002",
        br_ref: "BR-CUS-068",
        message_key: "errors.biz-state",
        params: { reason: "not_a_common_area_of_this_premises", label: null, unit_id: "u-101a" },
      }),
    ).toBe("That unit is not a common area. Uncheck it.");

    // 5 · no common areas at all.
    expect(
      say({
        code: "BIZ-002",
        br_ref: "BR-CUS-068",
        message_key: "errors.biz-state",
        params: { reason: "no_common_area_units", premises_id: "p-101" },
      }),
    ).toBe("This property has no common areas. Flag a unit as common first.");

    // 6 · A REFUSAL THIS SCREEN DOES NOT OWN PASSES THROUGH UNTOUCHED. The
    // mapping must never swallow a rule it was not written for.
    const passthrough = masterRefusalEnvelope({
      code: "BIZ-001",
      br_ref: "BR-CUS-022",
      message_key: "customers.account.start_date_required",
      params: { field: "opened_at" },
    });
    expect(passthrough.message_key).toBe("customers.account.start_date_required");
  });

  it("BR-MET-101: a premise with nothing flagged says so, and offers no master create", () => {
    // The empty state this case used to be. `is_common_area` is the queryable
    // fact, so "no common areas" is a real answer — and a Create button here
    // would only be refused server-side on `no_common_area_units`.
    const html = renderDetail("/premises/p-101?tab=common-areas", premise());
    // ⚠ **AMENDED 2026-09-10.** The old sentence — *"No unit here is flagged as
    // a common area. Flag one on the Units tab…"* — pointed a clerk at another
    // tab and at a checkbox inside a unit's edit form. The blueprint's STATES
    // row asks the empty state to say **what a common area is** and to offer to
    // add one, which is what it now does.
    expect(html).toContain("No shared space here yet");
    expect(html).toContain("shared space with its own meter");
    expect(html).not.toContain("Create master account");
  });

  // ── CR-089 wave C · C2 (PUJ-13) ─────────────────────────────────────────
  //
  // Every new building read *None on this premise*, and the only route off
  // that sentence was one a clerk had to already know: the flag is a checkbox
  // inside a unit's edit form on another tab.

  it("C2: the empty state OFFERS the thing it is empty of", () => {
    const html = renderDetail("/premises/p-101?tab=common-areas", premise());
    expect(html).toContain("No shared space here yet");
    // B14's button grammar is `+ Noun` opens a creator, and the blueprint draws
    // `+ Add a common area`. The label carried no `+`, so the drawing and the
    // system agreed and the product was out on its own.
    expect(html).toContain("+ Add a common area");
  });

  it("C2: the control is on the populated tab too, beside the master-account buttons", () => {
    const detail = premise({
      unit_rows: [unitRow({ is_common_area: true, label: "Laundry" })],
    });
    const html = renderDetail("/premises/p-101?tab=common-areas", detail, [], []);
    expect(html).toContain("Add a common area");
    expect(html).toContain("Laundry");
  });

  it("C2: BR-SHL-025 — a role that may not write gets the control DISABLED with its reason", () => {
    const html = renderDetail(
      "/premises/p-101?tab=common-areas",
      premise(),
      [],
      [],
      null,
      "Read",
    );
    expect(html).toContain("Add a common area");
    expect(html).toContain("disabled");
  });

  // ── CR-089 P6 · the DRAWN frame (blueprint pages 25–28) ─────────────────
  //
  // `DEF-4739` (the table component) and `DEF-4740` (the columns). Every case
  // below was proved RED against the tab as it stood at `67da0e4f2`: four
  // columns — `Common area · Meters · Plan · Status` — inside the small
  // in-panel table, with no search box, no column chooser and no footer.

  it("P6: the tab draws the SEVEN drawn columns, in the drawn order", () => {
    const html = renderDetail(
      "/premises/p-101?tab=common-areas",
      premise({ units_common: 2, unit_rows: [COMMON_HALLWAY, COMMON_IRRIGATION] }),
      [],
      [masterRow()],
    );
    expect(commonAreaHeaders(html)).toEqual([
      "Common area",
      "What it is",
      "Meters",
      "Billed to",
      "Owed",
      "Status",
      "Actions",
    ]);
    // §12 draws `Plan` NOWHERE and the product drew it. The header row is what
    // is read: the column chooser legitimately lists every declared column.
    expect(commonAreaHeaders(html)).not.toContain("Plan");
  });

  it("P6: the shared table brings the search box and the pagination footer with it", () => {
    // `DEF-4739`'s whole point: one component swap restores five controls that
    // were absent because the tab drew the small in-panel table instead.
    const html = renderDetail(
      "/premises/p-101?tab=common-areas",
      premise({ units_common: 2, unit_rows: [COMMON_HALLWAY, COMMON_IRRIGATION] }),
      [],
      [masterRow()],
    );
    expect(html).toContain("Search common areas…");
    expect(html).toContain("Show or hide columns");
    expect(html).toContain("table-pager");
    // §5: *"No `ALL` chip and no `+ Filter` on this tab — that is the Units
    // tab's toolbar, not this one."* `BR-SHL-010` draws only what is declared,
    // so declaring no filters IS how that absence gets drawn.
    expect(html).not.toContain("+ Filter");
  });

  it("P6: every drawn cell of the first row holds what §6 says it holds", () => {
    // ⚠ **THE CELLS, NOT A SUBSTRING SEARCH.** `expect(html).toContain("Common
    // area")` passes on a render that never drew the column at all — the words
    // are in the tab strip, in the add button and in the column chooser. Read
    // the row.
    const html = renderDetail(
      "/premises/p-101?tab=common-areas",
      premise({ units_common: 1, unit_rows: [COMMON_HALLWAY] }),
      [],
      [masterRow()],
    );
    const cells = commonAreaFirstRow(html);
    expect(cells[0]).toBe("Hallway & exterior lighting");
    // §6: *"in words — shared room, shared lighting, car park — never a type
    // code."* The stored code is the one thing this column may never print
    // (B14 rule 32 — no internal code in clerk copy).
    expect(cells[1]).toBe("Common area");
    expect(html).not.toContain("common_area");
    expect(cells[2]).toContain("M-4109");
    // §6 col 4, *"the reason the tab exists"*: the owner's party, then its
    // account, quiet.
    expect(cells[3]).toBe("Miller Property LLC A-00900");
  });

  it("CR-023 W2 · PRM-04: both import buttons, and the run TABLE where the stated absence was", () => {
    const html = renderImports({ access: "Full" });
    // r10 draws the import buttons TWICE on this tab with the emphasis
    // reversed — secondary in the head, primary in the toolbar (B15 §9.8).
    // ⚠ **THE HEAD'S ONE READS `↑ Import` FROM 2026-09-10 AND THE TOOLBAR'S
    // KEEPS THE LONG FORM**, so the count of the long string is now ONE. The
    // words diverge on purpose: in the head the tab strip says which list you
    // are on, and in the toolbar this button sits beside `↑ Import units` and
    // the qualifier is the only thing telling them apart. Both doors are still
    // drawn, which is what this case is actually about.
    expect((html.match(/↑ Import premises/g) ?? []).length).toBe(1);
    expect((html.match(/↑ Import(?! premises| units)/g) ?? []).length).toBe(1);
    expect(html).toContain("↑ Import units");
    // ⚠ **THIS ASSERTION IS INVERTED FROM WHAT IT WAS, AND THAT IS THE POINT
    // (G38).** It used to require `data-tracks="DEF-520"` — the note saying a
    // run list needs an import that records a run. `GET /imports` serves that
    // list now, so the note is GONE and the table is here. A stated absence
    // that outlives its reason is the same defect as the empty table it was
    // written to avoid (DEF-445), which is why the gate counts them and why
    // this case now asserts the note is absent rather than present.
    expect(html).not.toContain('data-tracks="DEF-520"');
    // The nine columns r10 draws — RUN | SOURCE | STARTED | BY | IN | LOADED |
    // REJECTED | STATUS | ↺ — rendered before any row has arrived.
    // ⚠ r10's OWN WORDS, including the terse `In` — G14 caught the first
    // draft rewording it to "Rows in", which is a column r10 does not have
    // wearing the name of one it does (B15 §9.8: copy it, do not tidy it).
    for (const column of ["Run", "Source", "Started", "In", "Loaded", "Rejected"]) {
      expect(html).toContain(column);
    }
    // ⚠ And STILL no invented data: the first paint is the loading state, not
    // a row. `RUN-2812` is r10's own sample and must never reach a screen.
    expect(html).not.toContain("RUN-2812");
    // The definition line is the page HEAD's and is drawn ONCE (BR-SHL-044) —
    // the first draft of the tab repeated it in the body.
    expect((html.match(/Every bulk load, with its receipt/g) ?? []).length).toBe(1);
    // The head is the SAME head — h1 reads Premises on all three tabs.
    expect(html).toMatch(/<h1[^>]*>Premises<\/h1>/);
  });

  it.todo(
    "US-SHL-020 TC-1 (browser): clicking Units moves the strip to the other ROUTE and the slot re-labels — navigation is browser scope",
  );
});

// ── BR-MET-101 — "N + M common" on the premises surfaces (W3 lane 2026-08-22) ──

describe("BR-MET-101 — the premises surfaces draw the common-area split", () => {
  it("the PRM-02 Units tile draws r10's '3 + common' from the SERVER's split", () => {
    // ⚠ **THE SPLIT MOVED OUT OF THE TILE — AMENDED 2026-09-10 (`DEF-MET-4803`).**
    // This asserted `3 + common` and `2 common` in the Units tile. `CR-089-p019`
    // draws that tile's detail line as `3 occupied · 1 vacant` and gives the
    // common areas **fact row 13**, where they are NAMED rather than counted —
    // which is more use to a clerk than a number: *which* hallway, not how many.
    //
    // ⚠ **`BR-MET-101` IS NOT WEAKENED BY THIS AND THAT IS THE POINT OF THE
    // CASE.** The rule is that a common area is never counted as a rentable
    // unit. The tile said so by arithmetic; the fact row says so by listing
    // them apart from the units entirely. So the assertion is that the common
    // area appears in ITS OWN ROW and NOT in the units count.
    const html = renderDetail(
      "/premises/p-101",
      premise({ units: 5, units_common: 2, unit_rows: [unitRow(), COMMON_HALLWAY] }),
    );
    // Anchored past the tab strip for the reason the order case records: the
    // string `Common areas` is a TAB as well as fact row 13.
    const facts = html.slice(html.indexOf('class="flex justify-between gap-4 py-3'));
    const row = facts.slice(facts.indexOf(">Common areas<"));
    expect(row).toContain("Hallway &amp; exterior lighting");
    // …and the units count beside it never absorbs the common area.
    expect(row).not.toContain("5 units");
  });

  it("a premise with no common areas draws the plain total, as r10 does everywhere else", () => {
    const html = renderDetail("/premises/p-101", premise({ units: 2, units_common: 0 }));
    expect(html).not.toContain("+ common");
  });

  it("the detail's Units tab marks the flagged row 'Common' — the vocabulary of r10's unit slot", () => {
    const html = renderDetail(
      "/premises/p-101?tab=units",
      premise({
        unit_rows: [
          unitRow(),
          unitRow({ id: "u-101c", label: "Hallway lighting", is_common_area: true }),
        ],
      }),
    );
    expect(html).toContain("Hallway lighting");
    expect((html.match(/>Common</g) ?? []).length).toBe(1);
  });

  it("the roll-up sentence splits to 'N + M common units' when M > 0", () => {
    // ⚠ **ASSERTED ON THE FUNCTION, NOT THROUGH THE PREMISES TAB, SINCE
    // `DEF-MET-5855`.** That tab draws the blueprint's subtitle now; the
    // sentence still renders on the Imports tab, which no blueprint plate
    // covers, so the arithmetic this case exists for is asked of the thing that
    // owns it. 143 total − 4 common = 139 lived-in units; both server numbers
    // named (BR-MET-101).
    const html = renderToStaticMarkup(
      premisesRollupLine(t, {
        premises: 6,
        units: 143,
        common: 4,
        vacant: 9,
        pending_activation: 1,
      }),
    );
    expect(html).toContain("139 + 4 common units");
  });

  // ── `DEF-MET-5855` · THE CASE THAT WOULD HAVE CAUGHT IT ──────────────────
  // The human QA team reported the roll-up where the blueprint draws a
  // subtitle, and no check in this repo could see it: `tsc`, eslint and every
  // gate are blind to which STRING fills a head slot, and the case above
  // asserted the roll-up was there. So this asserts the drawn line by its own
  // text AND the roll-up's ABSENCE by its most distinctive fragment — an
  // absence is invisible to every other check here (`DEF-CUS-3653`).
  it("DEF-MET-5855: the Premises tab draws the drawn subtitle and NO roll-up sentence", () => {
    const html = renderList("/premises", {
      list: { ...page([premise()]), rollup: { premises: 6, units: 143, common: 4, vacant: 9, pending_activation: 1 } },
      types: TYPES,
    });
    expect(html).toContain(t("metering.premises.listSubtitle"));
    expect(html).not.toContain("pending activation");
    expect(html).not.toContain("139 + 4 common units");
    // …and the Imports tab, which the blueprint does not draw, is untouched.
    expect(renderImports()).toContain("page-header-rollup");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-001@947cf31 (story+rules snapshot hash — EP-MET-01 lead story)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — TC-1/TC-2/TC-5/TC-6 for S14, plus the RBAC and header-order assertions the move had to survive)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline; this file adds 5 passing + 1 todo) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 US-SHL-020 TC-1's CLICK (moving between the Premises and Units routes) needs a live browser and stays an honest it.todo — the half a static render can prove, that one config puts a different button in the SAME slot per tab id, is asserted here · E4 the isolation halves of the §3 tables are the G5 suite's, on live Postgres · E4 the Retry click of TC-6 is browser scope; the state it renders is asserted through the DataTable error prop in the units suite
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
