// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-002 (S15 units list + detail)   Screens: S15
// Rules:    BR-MET-002 (a unit belongs to exactly one premise) · BR-MET-036 (occupancy is
//           DERIVED — displayed, never editable) · BR-MET-037 (delete guard) ·
//           BR-MET-040/041/042 (plan assignment, bulk, override-with-warning) ·
//           BR-MET-046 (a unit NEVER moves between premises) · BR-MET-047 (blockers named) ·
//           BR-SHL-011 (URL grammar) · BR-SHL-025 (server-authoritative RBAC) ·
//           BR-SHL-032 (confirms name the action) · BR-SHL-033 (long lists are searchable)
// ───────────────────────────────────────────────────────
// The two load-bearing tests here are DOM SCANS for absences: no occupancy
// control anywhere on S15, and no premises control on a unit edit. If a future
// change adds either, these fail — which is the only way BR-MET-036 and
// BR-MET-046 stay true after the packet that wrote them.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type {
  MyPermissions,
  Paginated,
  PremisesRow,
  ServerWarning,
  UnitPlanOption,
  UnitRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { apiErrorText } from "@/features/tenancy/settingsShared";

import {
  PLAN_FILTER_VALUES,
  UNIT_TYPES,
  planOverrideWarningKey,
  planPickerOptions,
  premisesPickerOptions,
  unitPlanOptionsKey,
  unitPremisesPickerKey,
  unitsParamsFrom,
  unitsQueryKey,
  unitsSearchPlaceholderKey,
  OCCUPANCY_FILTER_VALUES,
  unitsTableConfig,
  UNITS_SEARCH_PLACEHOLDER_KEY,
  chipFilters,
} from "./UnitsListPage";
import { MoveUnitModal, moveDestinationOptions } from "./MoveUnitModal";
import { entityAuditQueryKey, premisesAssetsQueryKey } from "./PremisesDetailPage";
import { PremisesTabsPage, premisesRollupQueryKey } from "./PremisesTabsPage";
import {
  UnitDetailPage,
  currentAccount,
  unitAccountQueryKey,
  unitAccountsQueryKey,
  unitAssetsQueryKey,
  unitDetailQueryKey,
  unitKicker,
  unitSubline,
  unitTabs,
  unitTitle,
} from "./UnitDetailPage";
import {
  currentMonthPeriod,
  unitPricingPath,
  unitPricingQueryKey,
  type UnitPricingMinimumCharges,
} from "@/features/customers/UnitPricingPanel";
import { unitPricing } from "@/features/customers/MoveInWizard.test";
import {
  PREMISES_PERMISSION,
  PREMISES_TAB_STRIP,
  PREMISES_TAB_UNITS,
  UNITS_ADD_ROUTE,
  unitStatusTone,
  unitsAddPath,
} from "./meteringShared";
import { SERVICE_CODES } from "@/features/rating/ratingShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`, so
// the screens below are rendered under one and the render helpers take the
// TENANT-RELATIVE path the route config is written in.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function unit(over: Partial<UnitRow> = {}): UnitRow {
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
      { id: "a2", asset_no: "M-7204", qualifier: "sub" },
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

const VACANT = unit({
  id: "u-101b",
  unit_no: "U-00101-B",
  label: "Unit B",
  occupancy: "vacant",
  occupant: null,
  account_no: null,
  status: "vacant",
  meters: [],
  sub_metered: false,
});

const CELLS = {
  select: () => <span />,
  unitNo: () => <span />,
  premise: () => <span />,
  owed: () => <span />, // CR-089 wave E
  label: () => <span />,
  type: () => <span />,
  services: () => <span />,
  offered: () => <span />,
  missing: () => <span />,
  meters: () => <span />,
  occupancy: () => <span />,
  occupant: () => <span />,
  status: () => <span />,
  actions: () => <span />,
};

const CONFIG = unitsTableConfig(t, [], [], CELLS);

/** One open account on the unit, as `GET /accounts?f.unit_id=` serves it. */
const ACCOUNTS = [
  {
    id: "acc-1",
    account_no: "A-00412",
    name: "Miller, Sarah",
    unit_id: "u-101a",
    unit_label: "Unit A",
    premise: "1408 Bluestem Ln · A",
    services: ["electric", "water"],
    balance: "247.300000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_cached: null,
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2024-03-12",
    closed_at: null,
    last_bill_at: null,
    aging: null,
  },
];

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

/**
 * ⚠ **`count` IS SEPARABLE FROM `results.length`, AND IT HAD TO BECOME SO**
 * (`DEF-TEN-5840`). This helper hard-wired `count: rows.length`, which makes it
 * a fixture that CANNOT TELL A WORKING SELECT-ALL FROM A BROKEN ONE: the page
 * total and the match total are the same number in every case it can build, so
 * a control that ticked only the visible page would satisfy an assertion about
 * the count exactly as well as one that walks the whole match set. That is
 * `DEF-CWP-3925`'s shape — the fixture, not the assertion, is what decides
 * whether a test can fail.
 */
function paged<T>(rows: T[], count?: number): Paginated<T> {
  return { count: count ?? rows.length, next: null, previous: null, results: rows };
}

const PREMISES: PremisesRow[] = [
  {
    id: "p-101",
    premise_no: "P-00101",
    name: null,
    address_line: "1408 Bluestem Ln",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    // DEF-507 — `null` is *nobody was ever asked*, never "outside the city".
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "single_family",
    premises_type_name: "Single-family",
    services_available: ["electric"],
    owner_manager: null,
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
  },
];

// DEF-114: PLANS, not tariffs. `GET /plans` is what the picker reads and
// `rate_plans` is what `POST /units/{id}/plan-assignments` resolves against —
// one vocabulary at both ends. A fixture shaped like a rate SCHEDULE is what
// let the broken pair look tested for four days.
const PLANS: UnitPlanOption[] = [
  {
    id: "rp-1",
    code: "RES-STD",
    name: "Residential Standard",
    status: "published",
    services: ["electric", "water"],
  },
];

/**
 * ONE `<tr>` of the rendered table, found by a string that only that row holds.
 *
 * ⚠ **THIS EXISTS BECAUSE AN ASSERTION ABOUT A ROW PASSED OFF THE FILTER
 * PICKER FOR WEEKS (`DEF-MET-4718`).** `premisesPickerOptions` builds
 * `P-00101 · 1408 Bluestem Ln` from the same fixture the row is built from, so
 * `expect(html).toContain(…)` was true of the whole document whatever the row
 * did. Slice the row first, then assert.
 */
function rowFor(html: string, marker: string): string {
  const at = html.indexOf(marker);
  if (at < 0) {
    throw new Error(`no row containing ${marker}`);
  }
  const start = html.lastIndexOf("<tr", at);
  const end = html.indexOf("</tr>", at);
  if (start < 0 || end < 0) {
    throw new Error(`${marker} is not inside a table row`);
  }
  return html.slice(start, end);
}

/** ONE `<td>` of a row — the cell that holds `marker`. A row carries the unit
 *  number in its checkbox's accessible name as well as in its identity cell, so
 *  an order assertion made across the whole row reads the wrong one. */
function cellWith(row: string, marker: string): { at: number; html: string } {
  const at = row.indexOf(marker);
  const start = row.lastIndexOf("<td", at);
  const end = row.indexOf("</td>", at);
  if (at < 0 || start < 0 || end < 0) {
    throw new Error(`${marker} is not inside a table cell`);
  }
  return { at: start, html: row.slice(start, end) };
}

function renderUnits(
  path: string,
  seed: {
    rows?: UnitRow[];
    access?: string;
    premises?: PremisesRow[];
    /** The SERVER's match total, when it differs from the rows on this page —
     *  the only way to mount a page-of-fifty over a match set of thousands. */
    count?: number;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(path.split("?")[1] ?? ""), CONFIG);
  if (seed.rows !== undefined) {
    queryClient.setQueryData(
      unitsQueryKey(serializeTableParams(state, CONFIG).toString()),
      paged(seed.rows, seed.count),
    );
  }
  queryClient.setQueryData(unitPremisesPickerKey, {
    ...paged(seed.premises ?? PREMISES),
    rollup: { premises: 1, units: 2, vacant: 1, pending_activation: 0 },
  });
  queryClient.setQueryData(unitPlanOptionsKey, paged(PLANS));
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  // CR-023 P0: `/premises/units` still resolves — it just mounts the SHELL with
  // its Units tab open (TC-24). The head, its counts sentence and the three-tab
  // strip belong to the shell now, so a test about the header has to mount it.
  queryClient.setQueryData(premisesRollupQueryKey, {
    ...paged(seed.premises ?? PREMISES),
    rollup: { premises: 1, units: 2, vacant: 1, pending_activation: 0 },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <PremisesTabsPage tab={PREMISES_TAB_UNITS} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The Account tab's payload, built from the accounts this harness was handed.
 *
 * CR-089 wave I moved the tab onto `GET /units/{id}/account`. Every existing
 * caller in this file passes ACCOUNT ROWS, so the answer is derived from them
 * rather than each call site being rewritten — the occupant is the one with no
 * end date, which is the same account those tests already meant.
 *
 * ⚠ **EVERY MONEY STATE IS A STATED `none`, NEVER AN OMITTED KEY.** That is the
 * shape the screen has to render (`PUJ-39`): a missing row means *nobody
 * looked*, and a fixture that omitted them would let the tab pass while drawing
 * nothing. The cases that need a protection, a note or a cash-only sanction
 * build their own answer in `UnitAccountTab.dom.test.tsx`.
 */
function unitAccountAnswer(row: UnitRow, accounts: unknown[]): unknown {
  const open = (accounts as Record<string, unknown>[]).filter((a) => a.closed_at === null);
  const current = open.length > 0 ? open[0] : null;
  return {
    unit: { id: row.id, unit_no: row.unit_no, label: row.label, is_common_area: false },
    account: current,
    facts:
      current === null
        ? null
        : {
            protections: {
              in_force: [],
              lapsed: [],
              disconnection_held: false,
              kinds_in_force: [],
            },
            customer_class: {
              code: "residential",
              name: "Residential",
              legacy: false,
              subtype_code: null,
              subtype_name: null,
            },
            autopay: {
              elected: Boolean(current.autopay),
              cash_only: false,
              nsf_count: 0,
              nsf_threshold: 2,
              will_be_taken: Boolean(current.autopay),
              reading: current.autopay ? "taken" : "not_elected",
            },
            payment_plan: { state: "none", count: 0, running: 0 },
            budget_billing: { state: "none", level: null, currency: null },
            collections: { state: "none", tier: null, paused_reason: null },
            bounced_payments: { count: 0 },
            tax_exemption: { claimed: false, reference: null, expires_on: null },
            deposit: { held: "0.000000", currency: "USD", received_on: null, any: false },
            notes: [],
            reach: {
              bad_address: false,
              paperless: false,
              sms_reminders: false,
              preferred_language: null,
            },
            external_ref: null,
            credit_tier: { value: null, computed: false, why: "credit_tier_rules_unbuilt" },
          },
    owner_account: null,
    no_account_reason: current === null ? "vacant" : null,
    facts_unavailable: null,
  };
}

function renderUnitDetail(
  path: string,
  row: UnitRow,
  accounts: unknown[] = ACCOUNTS,
  audit: unknown = null,
  assets: unknown[] = [],
  // CR-034: the Plan tab mounts `UnitPricingPanel`. Unseeded it renders A18's
  // skeleton, so an assertion about the unfold would be measuring a spinner —
  // the same reason the accounts rollup is seeded below.
  pricing: unknown = null,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(unitDetailQueryKey(row.id), row);
  // DEF-MET-8362: the Assets tab reads the UNIT's own registry page
  // (`f.unit_id`), no longer the premises' first 200 narrowed in the browser.
  // The premises key stays seeded for PRM-02's readers.
  queryClient.setQueryData(unitAssetsQueryKey(row.id), {
    count: assets.length,
    next: null,
    previous: null,
    results: assets,
  });
  queryClient.setQueryData(premisesAssetsQueryKey(row.premises_id), {
    count: assets.length,
    next: null,
    previous: null,
    results: assets,
  });
  // DEF-579: the Audit log tab reads the UNIT's own rows through the shared
  // component. Unseeded leaves it in A18's loading state.
  if (audit !== null) {
    queryClient.setQueryData(entityAuditQueryKey("unit", row.id), audit);
  }
  // CR-089 wave I: the ACCOUNT tab moved off the accounts list onto its own
  // read, `GET /units/{id}/account` — a protection, a note, a payment plan and
  // a budget enrolment are not columns on a list row, which is exactly why
  // `DEF-CUS-4691` was possible. The OCCUPANCY tab still reads the list below,
  // because it wants every account this unit has ever carried; the two keys are
  // deliberately separate. Unseeded, the Account tab renders A18's skeleton and
  // every assertion about it would be measuring a spinner.
  queryClient.setQueryData(unitAccountQueryKey(row.id), unitAccountAnswer(row, accounts));
  // CR-023 P2: the Occupancy tab READS the accounts on this unit
  // (`GET /accounts?f.unit_id=` — DEF-473's absence is closed).
  queryClient.setQueryData(unitAccountsQueryKey(row.id), {
    count: accounts.length,
    next: null,
    previous: null,
    results: accounts,
    rollup: {
      accounts: accounts.length,
      outstanding: null,
      currency: null,
      outstanding_basis: null,
      outstanding_unavailable: [],
      past_due_60_plus: null,
    },
  });
  if (pricing !== null) {
    // ⚠ **THE MONTH KEY, NOT THE NULL ONE — AND THAT IS A GUARD, NOT A
    // FIXTURE DETAIL (PO 2026-08-26: *"B Default to this month"*).** The staff
    // Plan tab mounts the panel with `showPeriod`, which opens it on the
    // current calendar month, so the request it makes is keyed on that window.
    // Seeded here and NOWHERE ELSE: if the default is ever removed or pushed
    // down into the endpoint, the panel asks on the `null, null` key, finds no
    // seeded answer, and every Plan-tab assertion in this file measures A18's
    // loading skeleton instead — loudly, rather than silently drawing today's
    // rates under a month heading.
    queryClient.setQueryData(unitPricingQueryKey(row.id, currentMonthPeriod()), pricing);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/premises/units/:unitId" element={<UnitDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-MET-002 — the S15 units list", () => {
  it("US-MET-002 TC-1: premise, meters with their qualifiers, occupant and status all render", () => {
    const html = renderUnits("/premises/units", { rows: [unit(), VACANT] });
    expect(html).toContain("U-00101-A");
    // ⚠ **THIS ASKED FOR `M-7001`, `M-7204` AND `(sub)` UNTIL 2026-09-10.** The
    // frame draws a COUNT in the `Meters` column of the estate-wide list —
    // *"a COUNT — `2`; `none` in the muted italic absence style where there are
    // none"* — and the asset numbers stay on the property's own Units tab,
    // where a clerk is holding one of them. The two states are asserted rather
    // than the one, because a cell that printed `2` for an empty unit is the
    // defect this column can now have.
    const withMeters = rowFor(html, "U-00101-A");
    expect(withMeters).toContain(">2<");
    expect(withMeters).not.toContain("M-7001");
    expect(rowFor(html, "U-00101-B")).toContain("No meters");
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain("A-00412");
    // CR-023 §3.2 col 2: BOTH parts of the address cell are rendered — the id
    // alone is not enough for a clerk holding a work order, and the address
    // alone does not match a premise number typed into the search box.
    //
    // ⚠ **THIS ASSERTION USED TO READ `toContain("P-00101 · 1408 Bluestem Ln")`
    // AND IT WAS NOT LOOKING AT THE ROW (`DEF-MET-4718`).** That exact string is
    // ALSO what `premisesPickerOptions` builds for the premise filter's
    // type-ahead, from the same fixture — so the assertion passed off the
    // FILTER, and it went on passing through CR-089 wave E splitting the cell
    // into two lines, which is precisely the change it existed to catch. A
    // check that cannot fail on the thing it names is worse than no check
    // (hard-won law 7). It reads the ROW now.
    const row = rowFor(html, "U-00101-A");
    expect(row).toContain("1408 Bluestem Ln");
    expect(row).toContain("P-00101");
    // §9.7: the service cell is the one shared letter-square badge.
    expect(html).toContain("var(--color-service-electric)");
    expect(html).toContain('aria-label="Water"');
    // ⚠ **THE DEFAULT SORT IS THE LABEL FROM 2026-09-10.** The frame says so of
    // column one — *"Sortable, and the default sort is the LABEL"* — and
    // `unit_no` ordered a building's flats by the series number they happened
    // to be minted in rather than by what is written on their doors. `label` is
    // one of the server's own `UNIT_SORTS` names, so nothing new is asked of it.
    expect(CONFIG.defaultSort).toEqual({ sort: "label", dir: "asc" });
  });

  it("CR-089 E1: Address is the second column and Owed is on the row", () => {
    // ⚠ **THE ORDER IS THE TASK, AND THE FIRST TWO SWAPPED BACK ON
    // 2026-09-10.** This list used to open `Select · Unit ID · Premise · Unit`,
    // so the first sortable column was the series NUMBER and the two things a
    // person scans by — the street and the flat — were third and fourth. Wave E
    // read `E1`'s task sentence and put the ADDRESS first; the blueprint's own
    // frame (page 51) draws `Unit ⇅` first and `Address ⇅` second, and the
    // conformance record rules the tie — *"where a commitment sentence
    // disagrees with the frame, the frame wins"* (PO, 2026-09-10). The
    // property's own Units tab already opened with `Unit`, so both lists of
    // units in this product now open the same way.
    //
    // What wave E actually fixed is untouched: the series number no longer
    // LEADS anything. The label leads column one and the street leads column
    // two, each with its quiet number beneath.
    //
    // `label` and `occupancy` are both available-not-default for the same
    // stated reason: the fact each draws is already on the row once, and a
    // column drawing it twice is what B14 rule 32 refuses. Neither is deleted —
    // deleting a sortable column is a capability cut.
    const visible = CONFIG.columns
      .filter((c) => c.defaultVisible !== false && c.key !== "select" && c.key !== "actions")
      .map((c) => c.key);
    // ⚠ **`missing` JOINED THIS LIST ON 2026-09-28 AND IT IS A RATIFIED MOVE,
    // NOT DRIFT.** PO ruling of that date, verbatim: *"the Units "Missing
    // services" block — filter or leave it. - filter"*, and on the columns:
    // *an `Offered here` column · a `Missing` column*. The `U1` frame (pages
    // 50–52) draws neither, because the frame is older than the ruling; the
    // departure is recorded in `CR-089-p050-units-list.md` rather than left to
    // be found. **This assertion is still the drift guard it was** — a column
    // nobody ratified still turns it red, which is why the list is spelled out
    // rather than filtered down to a length.
    expect(visible).toEqual([
      "unit_no",
      "address",
      "type",
      "services",
      "missing",
      "meters",
      "occupant",
      "owed",
      "status",
      // ⚠ **`created` AND `age` JOINED ON 2026-10-17, RATIFIED** — PO ruling
      // `DEF-MET-10164`: *"Similar functonality require on unit also"* and
      // *"you will ahve to display athe age in list view of Premsies and
      // Units"*. Both default-visible, after Status.
      "created",
      "age",
    ]);
    expect(CONFIG.columns.find((c) => c.key === "occupancy")?.defaultVisible).toBe(false);
    // ⚠ **AND `offered` IS DECLARED AND NOT DEFAULT, WHICH IS THE OTHER HALF.**
    // `row.services` is already what the ADDRESS offers (`DEF-755`), so the
    // ratified `Offered here` column draws the same fact as the drawn
    // `Services` column two places up — one fact twice on a row that already
    // carries ten is what B14 rule 32 refuses. It is DECLARED because the PO
    // ratified it by name; it is HIDDEN because the overlap is real, and that
    // is the one thing on this change going back to them.
    expect(CONFIG.columns.find((c) => c.key === "offered")?.defaultVisible).toBe(false);
    expect(CONFIG.columns.find((c) => c.key === "offered")).toBeDefined();
    expect(CONFIG.columns.find((c) => c.key === "label")?.defaultVisible).toBe(false);
    // Both stay sortable: sorting a building's units by `Apt 101 … Apt 110` is
    // a real thing to want, and `unit_no` does not answer it.
    expect(CONFIG.columns.find((c) => c.key === "label")?.sortable).toBe(true);
    // A column labelled Address that sorted by the premise NUMBER would be the
    // kind of quiet lie this repo files defects about.
    expect(CONFIG.columns.find((c) => c.key === "address")?.sortable).toBe(true);
    // Money is right-aligned and tabular, or a column of figures does not read
    // as a column.
    expect(CONFIG.columns.find((c) => c.key === "owed")?.numeric).toBe(true);
  });

  it("CR-089 E1: the label leads over the unit number, and the street over the premise number", () => {
    // The correction recorded before this wave started: `unit_no` is NOT a
    // database id — it is a printed reference off the tenant's own series, as
    // legitimate on screen as a premise number. Nothing is removed. What
    // changes is weight, and weight is order: the label is the link, the number
    // is the quiet second line under it.
    const html = renderUnits("/premises/units", { rows: [unit()] });
    const row = rowFor(html, "U-00101-A");
    const address = cellWith(row, "1408 Bluestem Ln");
    const identity = cellWith(row, "Unit A");
    expect(address.html.indexOf("1408 Bluestem Ln")).toBeLessThan(
      address.html.indexOf("P-00101"),
    );
    expect(identity.html.indexOf("Unit A")).toBeLessThan(identity.html.indexOf("U-00101-A"));
    // …and the UNIT cell comes before the address cell, which is the frame's
    // own order (page 51, columns 1 and 2).
    expect(identity.at).toBeLessThan(address.at);
  });

  it("CR-089 E1: Owed renders the ledger's figure, and every absence is a different sentence", () => {
    // ⚠ **DEF-127 IS THE REASON THIS TEST HAS FOUR CASES.** That defect is an
    // absence rendered as a zero — S17 read `Outstanding $0.00` over an issued,
    // unpaid 108.88. `0.00` may only ever mean *the books answered and nothing
    // is owed*; the other three states say so in words.
    const owing = unit({
      owed: {
        account_id: "acc-1",
        account_no: "A-00412",
        balance: "61.400000",
        balance_currency: "USD",
        balance_basis: "posting",
        balance_unavailable: [],
        balance_not_yet_billable: false,
      },
    });
    expect(rowFor(renderUnits("/premises/units", { rows: [owing] }), "U-00101-A")).toContain(
      "$61.40",
    );

    // The books could not be asked. NEVER a figure, and never a zero.
    const unreadable = unit({
      owed: {
        account_id: "acc-1",
        account_no: "A-00412",
        balance: null,
        balance_currency: "USD",
        balance_basis: null,
        balance_unavailable: ["ar_account_not_designated"],
        balance_not_yet_billable: false,
      },
    });
    const unreadableRow = rowFor(renderUnits("/premises/units", { rows: [unreadable] }), "U-00101-A");
    expect(unreadableRow).toContain("We could not read this.");
    expect(unreadableRow).not.toContain("0.00");

    // BR-CUS-510's real zero on an account that cannot be billed yet — the
    // accounts list's own word, read from the accounts list's own key.
    const awaiting = unit({
      owed: {
        account_id: "acc-1",
        account_no: "A-00412",
        balance: "0.000000",
        balance_currency: "USD",
        balance_basis: "posting",
        balance_unavailable: [],
        balance_not_yet_billable: true,
      },
    });
    expect(rowFor(renderUnits("/premises/units", { rows: [awaiting] }), "U-00101-A")).toContain(
      "Awaiting",
    );

    // ⚠ **NO OCCUPYING ACCOUNT — AND THIS PAIR OF ASSERTIONS USED TO PASS OVER
    // A TOOLTIP.** The row drew a bare `—` with the sentence in a `title=`
    // attribute, which is in the row's HTML and is therefore in the string this
    // check reads: a clerk saw a dash, a keyboard reached nothing, and the test
    // was green. The frame puts the sentence in the `Occupant` cell as its
    // VISIBLE TEXT and puts `Not measured` in the money column (PO ruling
    // 2026-09-10 — `0.00` only when the balance really is zero). So the check
    // now strips the markup before reading it, which is the only form that can
    // tell a rendered sentence from an attribute.
    const vacantRow = rowFor(
      renderUnits("/premises/units", {
        rows: [unit({ owed: null, occupancy: "vacant", occupant: null, account_no: null })],
      }),
      "U-00101-A",
    );
    const visibleText = vacantRow.replace(/<[^>]*>/g, " ");
    expect(visibleText).toContain("Vacant — base charges bill to the owner");
    expect(visibleText).toContain("Not measured");
    expect(vacantRow).not.toContain("0.00");
  });

  it("CR-089 E3: the add-units address, and what it does with a building", () => {
    // ⚠ **THIS CASE USED TO CLAIM MORE THAN IT ASSERTED, AND THE CLAIM WAS
    // WRONG FOR A DAY (`DEF-MET-4801`).** It was called *"+ New unit opens the
    // add-units wizard, and can carry the building"* and it checked FOUR
    // STRINGS out of a helper **no door in the product called**: both buttons
    // on the property's own page navigated to the bare route, so the building
    // was lost on every press and this test was green throughout. A
    // `renderToStaticMarkup` suite cannot see that — the destination of an
    // `onClick` is not in the markup — so the door is asserted where it can be
    // pressed, in `AddUnitsFromABuilding.dom.test.tsx`, by the ADDRESS the
    // browser ends on.
    //
    // What is left here is the URL GRAMMAR that test depends on, under a name
    // that says so.
    expect(UNITS_ADD_ROUTE).toBe("/premises/units/new");
    // The units LIST's own door carries no building, and that is the drawing:
    // *"the units list → `+ New unit`, where there is none — that door exists"*.
    expect(unitsAddPath()).toBe("/premises/units/new");
    expect(unitsAddPath("p-101")).toBe("/premises/units/new?premises=p-101");
    // An id with a character that means something in a URL must survive it.
    expect(unitsAddPath("a/b?c")).toBe("/premises/units/new?premises=a%2Fb%3Fc");
  });

  it("CR-089 E2: an address finds the units at it, and the box says so", () => {
    // The SERVER half already worked — `units_list` matches
    // `premises__address_line__icontains` — and nothing on the screen or in
    // this suite said so, so nobody could tell a working search from a search
    // nobody had tried. Two halves, both asserted: the search term reaches the
    // server on `q`, and the placeholder tells a clerk that an address is a
    // thing they may type.
    expect(t(UNITS_SEARCH_PLACEHOLDER_KEY)).toContain("address");
    const typed = parseTableParams(new URLSearchParams("q=412+Cypress+Row"), CONFIG);
    expect(unitsParamsFrom(typed).q).toBe("412 Cypress Row");
    // …and the screen declares the address as one of the fields it searches, so
    // the placeholder above is a promise the config keeps.
    expect(CONFIG.searchFields).toContain("premise");
  });

  it("CR-023 §3.2: r10's FOURTH status is real, and it draws the danger pill", () => {
    // ⚠ B15 §3.2 warns: *"Check what the product derives before assuming it
    // exists"*. It DOES: `selectors._unit_status` returns the ACCOUNT's status
    // code, and `marked_disconnect` is one of BR-CUS-055's five seeded statuses
    // (`apps/customers/services.py`). It had no label and no tone, so it
    // rendered the raw string `marked_disconnect` in a neutral pill.
    expect(unitStatusTone("marked_disconnect")).toBe("danger");
    expect(t("metering.units.status.marked_disconnect")).toBe("Marked disconnect");
    const html = renderUnits("/premises/units", {
      rows: [{ ...unit(), status: "marked_disconnect" }],
    });
    expect(html).toContain("Marked disconnect");
    expect(html).not.toContain(">marked_disconnect<");
  });

  it("US-MET-002 / BR-SHL-016: the capability row's Download renders, CSV only", () => {
    const html = renderUnits("/premises/units", { rows: [unit()] });
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="units"');
    expect(html.toLowerCase()).not.toContain("xlsx");
  });

  it("US-MET-002 TC-2/TC-3 / BR-MET-036: the occupancy filter offers the derived partition, in one control", () => {
    const filter = CONFIG.filters?.find((f) => f.name === "occupancy");
    expect(filter?.options.map((o) => o.value)).toEqual(["occupied", "vacant", "sub_metered"]);
    const state = parseTableParams(new URLSearchParams("f.occupancy=vacant"), CONFIG);
    expect(state.filters.occupancy).toBe("vacant");
    expect(serializeTableParams(state, CONFIG).get("f.occupancy")).toBe("vacant");
  });

  it("US-MET-002 TC-4: the declared search fields include the meter number", () => {
    expect(CONFIG.searchFields).toEqual(["premise", "label", "meter_no"]);
  });

  it("BR-MET-036: occupancy renders, and NO editable occupancy control exists anywhere on S15", () => {
    const html = renderUnits("/premises/units", { rows: [unit(), VACANT], access: "Full" });
    expect(html).toContain("Occupied");
    expect(html).toContain("Vacant");
    // The scan: nothing on this screen is named for occupancy except the
    // read-only column header, the filter, and the pills.
    expect(html).not.toContain('name="occupancy"');
    expect(html).not.toContain('id="occupancy"');
    // Every <select> on the page is accounted for — and since DEF-442 there is
    // exactly ONE: the pager's rows-per-page.
    // ⚠ AMENDED 2026-08-21 (DEF-442). This expected 3, counting the occupancy
    // and service FILTERS as dropdowns. r10 draws filters as one `+ Filter ▾`
    // panel of grouped checkboxes with removable chips, and the shared
    // FilterBar was redrawn to match, so those two <select>s are gone.
    // THE RULE THIS TEST ASKS ABOUT IS UNCHANGED: a filter narrows a list and
    // never writes a value, and S15 still has no occupancy input, radio or
    // textarea of any kind — the `name="occupancy"` / `id="occupancy"` scans
    // above are what actually carry that, and they were untouched by the
    // redraw. The count is the supporting evidence, not the rule.
    const selects = html.match(/<select/g) ?? [];
    expect(selects.length).toBe(1);
    // The occupancy filter still EXISTS — it moved into the panel. Asserted so
    // that "1 select" can never be satisfied by the filter quietly vanishing.
    expect(html).toContain("+ Filter");
    expect(html).toContain('type="checkbox"');
    expect(html).not.toContain("<textarea");
    // ⚠ **AMENDED TWICE, AND THE SECOND AMENDMENT PUTS THE BAN BACK
    // (2026-08-21 CR-023 P1, then 2026-08-27 DEF-1700).**
    //
    // This line was originally `expect(html).not.toContain('type="radio"')` —
    // true only because nothing on the screen had ever used a radio. CR-023 P1
    // added r10's toolbar segment (All · Occupied · Vacant · Sub-metered),
    // which IS a radiogroup and has to be, so the ban was narrowed to "no radio
    // may be named for the occupancy FIELD".
    //
    // **DEF-1700 deleted the segment**, on the Product Owner's ruling that the
    // first toolbar row is sufficient — `occupancy` was already a declared
    // `TableConfig` filter over the same `OCCUPANCY_FILTER_VALUES`, so the
    // segment duplicated the `+ Filter` panel next to it. With it gone the
    // blanket ban is true again, and it is restored rather than left narrowed:
    // a narrowed ban over a control that no longer exists is a check that
    // cannot distinguish pass from fail (DEF-182).
    expect(html).not.toContain('type="radio"');
    // …and the dimension itself is NOT lost — that is the assertion that goes
    // red if a later lane removes the filter instead of the duplicate control.
    // All four of r10's cells are still offered, Sub-metered included.
    expect(html).toContain("+ Filter");
    expect(OCCUPANCY_FILTER_VALUES).toContain("sub_metered");
    expect((CONFIG.filters ?? []).map((filter) => filter.name)).toContain("occupancy");
  });

  it("BR-MET-095 (CR-024): the premise cell is a LINK, and the MOVE is a deliberate row action", () => {
    // ⚠ **THIS TEST USED TO ASSERT THE OPPOSITE HALF OF THE RULE AND THE RULE
    // CHANGED.** BR-MET-046 — *"units NEVER move between premises"* — is
    // SUPERSEDED-REFINED by BR-MET-095 (PO 2026-08-21: *"please ensure move
    // units works in Units … user has put a unit in wrong premises"*). What
    // survives untouched is the part that mattered: the premise on a ROW is
    // still navigation and never assignment, so no stray click can re-parent a
    // unit. The move is an explicit action, a modal, a date and a reason.
    const html = renderUnits("/premises/units", { rows: [unit()], access: "Full" });
    expect(html).toContain('href="/brazosbend/premises/p-101"');
    // Still no premises control on the LIST — the edit path cannot send one.
    expect(html).not.toContain('name="premises_id"');
    // …and the move is offered as a named action, not as a dropdown in the row.
    // ⚠ **IT IS BEHIND THE `…` FROM 2026-09-10 AND IT IS STILL NAMED.** The
    // frame draws three glyphs on this row — `👁 ✎ …` — and B14 rule 15 has
    // always ended *"Max 2 visible, then `…`"*, so Move, Assign plan,
    // Deactivate and Delete moved into the overflow. Inside an opened menu the
    // action carries its WORD beside its glyph, which is why this reads the
    // rendered text rather than an `aria-label`: a menu of four icons would be
    // a puzzle, and asserting the attribute would have hidden that.
    expect(html).toContain("More actions");
    expect(html.replace(/<[^>]*>/g, " ")).toContain("Move");
  });

  it("BR-MET-037: Delete is guarded on a referenced unit, with the reason on the control", () => {
    const html = renderUnits("/premises/units", { rows: [unit()], access: "Full" });
    expect(html).toContain("An account, asset or read uses it.");
    // A never-referenced unit offers the control instead.
    const clean = renderUnits("/premises/units", {
      rows: [unit({ id: "u-new", unit_no: "U-00999", meters: [], account_no: null })],
      access: "Full",
    });
    expect(clean).not.toContain("An account, asset or read uses it.");
  });

  it("BR-SHL-032: the delete confirm NAMES the action", () => {
    expect(t("metering.units.confirm.deleteTitle", { unit: "U-00101-A" })).toBe(
      "Delete unit U-00101-A?",
    );
    expect(t("metering.units.confirm.deleteAction")).toBe("Delete unit");
    // ⚠ **DEACTIVATE IS NO LONGER A CONFIRM AND ITS THREE STRINGS ARE RETIRED
    // (`DEF-MET-4761`).** The row action opens `StatusChangeDialog`, which
    // demands a date and a reason and names what is holding the commit; the
    // drawn word `Deactivate unit` moved onto that dialog's own footer button.
    // `UnitsListOneDoor.dom.test.tsx` is what guards it now — asserting a
    // catalogue string here could not tell which door was wearing it.
    expect(t("metering.units.status.deactivateAction")).toBe("Deactivate unit");
  });

  it("BR-SHL-033: the premises picker is a SEARCHABLE combobox, not a scroll list", () => {
    // ⚠ **THE ADDRESS LEADS FROM 2026-09-10.** The label read
    // `P-00101 · 1408 Bluestem Ln`, so the add-units wizard's *Search premises*
    // box showed a property CODE first — not what anybody types into it, and
    // not what the frame draws. Found by looking at the rendered screen. The
    // number has not left; the two swapped places, as they did in the units
    // list's address cell and in the building card.
    // ⚠ **`search` IS ASSERTED, NOT TOLERATED (`DEF-MET-5837`).** It was added
    // on 2026-09-11 so a clerk can find a property by parcel — the picker's own
    // help promises "By address, property number or parcel" — and these
    // assertions went red that day and were read by nobody for eight days. An
    // exhaustive `toEqual` is the right shape here precisely because it notices;
    // what was missing is somebody looking. It holds the cells the label does
    // NOT draw, so a value here is the whole point of the field.
    expect(premisesPickerOptions(PREMISES)).toEqual([
      { value: "p-101", label: "1408 Bluestem Ln · P-00101", search: "Katy" },
    ]);
    expect(planPickerOptions(PLANS)).toEqual([
      { value: "rp-1", label: "Residential Standard · electric, water" },
    ]);
    const html = renderUnits("/premises/units", { rows: [unit()] });
    expect(html).toContain('role="combobox"');
    expect(html).toContain('id="f.premises_id"');
  });

  it("BR-MET-041: selecting rows is what unlocks bulk plan assignment — nothing else does", () => {
    const html = renderUnits("/premises/units", { rows: [unit()], access: "Full" });
    // ── `DEF-TEN-5840` ────────────────────────────────────────────────────
    // ⚠ **THIS ASSERTED THE BAR WAS ABSENT, AND THAT IS WHAT MADE `Select all`
    // UNREACHABLE.** The bar is where a select-all control has to live, and it
    // only appeared once something was already ticked — so the only way to
    // select 3,412 units was to tick 3,412 boxes. The bar now shows whenever
    // the list has rows.
    //
    // ⚠ **BR-MET-041 IS UNCHANGED AND IS STILL ASSERTED, ONE LAYER IN.** The
    // rule is that a SELECTION unlocks the bulk assignment, not that the bar
    // is hidden — so the button is GUARDED rather than missing (BR-SHL-025:
    // disabled WITH its reason). A clerk now learns what the control needs
    // instead of hunting for a bar that is not drawn.
    //
    // ⚠ **SUPERSEDED IN PART BY THE PO ON 2026-10-09 (`CR-176-BRC10`,
    // `DEF-MET-10035`): *"the selection bar shows only once a unit is ticked
    // (no '0 unit(s) selected')"*.** With nothing ticked there is no bar and
    // no bulk button at all; one tick brings both, `Select all` with them —
    // `AddUnitsRedesign.dom.test.tsx` asserts that by ticking.
    expect(html).not.toContain("Assign a plan to these");
    expect(html).not.toContain("unit(s) selected");
    // The per-row control exists regardless, for the single case.
    expect(html).toContain("Assign plan");
  });

  it("DEF-TEN-5840: `Select all` states the SERVER's total, never the rows on this page", () => {
    // ⚠ **THE COUNT IS THE WHOLE POINT AND IT IS WHY THIS ASSERTS A NUMBER.**
    // Every list on this screen is server-paginated (`NFR-3`), so a control
    // that ticked the visible page under a filter matching 3,412 would leave a
    // clerk believing they had selected 3,412 and assigning a plan to one.
    // A test asserting merely that *a select-all control exists* passes on
    // exactly that bug, which is the false pass this case is written against.
    // ⚠ `CR-176-BRC10` (PO 2026-10-09): the bar — and `Select all` in it —
    // appears only once a unit is ticked, which a static render cannot do. The
    // count is now asserted by ticking one row in
    // `AddUnitsRedesign.dom.test.tsx` (*"one tick: the bar, with Select all
    // stating the SERVER's total"*), against a page of ONE row and a server
    // total of 3412 — the same pair that tells the two apart here.
    const html = renderUnits("/premises/units", {
      rows: [unit()],
      access: "Full",
      count: 3412,
    });
    expect(html).not.toContain(">Select all 1<");
  });

  it("BR-MET-042: the OVERRIDE warning is the SERVER's — this screen renders it, never predicts it", () => {
    const override: ServerWarning = {
      code: "unit_plan_override_on_occupied_unit",
      br_ref: "BR-MET-042",
    };
    expect(planOverrideWarningKey(override)).toBe("metering.units.plan.overrideWarning");
    expect(t(planOverrideWarningKey(override) as string)).toContain("That was an override.");
    // An unrecognised warning still surfaces — never swallowed.
    expect(planOverrideWarningKey({ code: "something_new" })).toBe(
      "metering.units.plan.genericWarning",
    );
    // No warning means no notice at all.
    expect(planOverrideWarningKey(null)).toBeNull();
    // The rule is also stated up front, before the save.
    const html = renderUnits("/premises/units", { rows: [unit()], access: "Full" });
    expect(html).toContain("Assign plan");
    expect(t("metering.units.plan.overrideNote")).toContain("Normal changes go through the account.");
  });

  it("BR-MET-047: the server's blockers render verbatim through the shared refusal path", () => {
    const blocked = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "metering.unit.deactivate_blocked",
      params: { blockers: [{ unit: "Unit A", blocker: "active_account" }] },
      br_ref: "BR-MET-047",
    });
    // The message key is the SERVER's; the catalog renders it (TD-16). Until a
    // shared error catalog carries it the fallback is the plain unexpected
    // line — never a client-assembled sentence about accounts.
    expect(typeof apiErrorText(blocked, t)).toBe("string");
    expect(blocked.brRef).toBe("BR-MET-047");
  });

  it("US-MET-002 §RBAC / BR-SHL-025: '—' hides the screen, 'View' disables its writes", () => {
    const denied = renderUnits("/premises/units", { rows: [unit()], access: "—" });
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain("U-00101-A");
    const viewOnly = renderUnits("/premises/units", { rows: [unit()], access: "View" });
    expect(viewOnly).toContain("Your role can view this but not change it.");
    expect(viewOnly).toContain("U-00101-A");
  });

  it("the five ratified unit types are the server's own set", () => {
    expect([...UNIT_TYPES]).toEqual([
      "residential",
      "residential_submetered",
      "commercial",
      "commercial_master",
      "common_area",
    ]);
  });

  it.todo(
    "US-MET-002 TC-5/TC-6: the delete refusal and the duplicate-label inline error are server verdicts — asserted in the backend suite; the click path is browser scope",
  );
  it.todo(
    "US-MET-002 TC-7 (isolation): two tenants may both own a 'Unit A' and neither list shows the other's — server/RLS scope (G5)",
  );
});

describe("US-MET-002 — the S15 unit detail (BR-MET-045 tabs)", () => {
  it("CR-023 §2A.2: r10's six tabs, in order", () => {
    // ⚠ WAS FIVE (BR-MET-045: Overview · Assets · Account history · Plan
    // history · Audit). r10 draws **Overview · Assets · Plan · Account ·
    // Occupancy · Audit log**: the two "history" tabs are renamed to what they
    // actually show (the CURRENT plan and the CURRENT account), and Occupancy —
    // the who-held-this-unit timeline — is genuinely new.
    expect(unitTabs(t).map((tab) => tab.id)).toEqual([
      "overview",
      "assets",
      "plan",
      "account",
      "occupancy",
      "audit",
    ]);
    const html = renderUnitDetail("/premises/units/u-101a", unit());
    // DEF-580: `Audit log` is r10's label — this shipped `Audit`.
    for (const label of ["Overview", "Assets", "Plan", "Account", "Occupancy", "Audit log"]) {
      expect(html).toContain(`>${label}<`);
    }
  });

  it("⚠ DEF-755: the S15 cell shows what the ADDRESS OFFERS, not what happens to be metered", () => {
    // ⚠ **THE PO'S OWN SCREEN.** *"We ahve fixed premises already . premises
    // are showing Utility services now"* — and 9,881 units still read "No
    // services", because the cell was derived from SERVICE POINTS. A migrated
    // unit has none, so a unit whose address demonstrably offers Electric and
    // Water showed nothing at all. The rule in force (PO, 2026-08-26, after
    // CR-037 was withdrawn) is that a unit's services ARE its premises'.
    const migrated = unit({ services: ["electric", "water"], metered_services: [] });
    const html = renderUnits("/premises/units", { rows: [migrated] });
    expect(html).toContain("Electric");
    expect(html).toContain("Water");
    expect(html).not.toContain("No services");
  });

  it("⚠ DEF-755: an address NOBODY HAS BEEN ASKED about reads 'Not recorded', never 'No services'", () => {
    // DEF-762's three states, inherited through the premises. `[]` here would
    // be the screen answering *this unit offers nothing* on the utility's
    // behalf for every unit of every unasked address.
    const html = renderUnits("/premises/units", {
      rows: [unit({ services: null, metered_services: [] })],
    });
    expect(html).toContain("Not recorded");
    expect(html).not.toContain("No services");
  });

  it("⚠ DEF-755: a clerk's ANSWER of 'this address offers nothing' still reads 'No services'", () => {
    const html = renderUnits("/premises/units", {
      rows: [unit({ services: [], metered_services: [] })],
    });
    expect(html).toContain("No services");
    expect(html).not.toContain("Not recorded");
  });

  it("⚠ DEF-755: the sub-line says what the unit CAN TAKE, never what is connected", () => {
    // Swapping the source without swapping the word would have traded a true
    // sentence for a false one: a unit can have Water available with no meter
    // and nothing connected. `metering.units.servicesConnected` is RETIRED
    // rather than reworded — a catalogue entry beats a code `defaultValue`, so
    // an in-place reword would ship a fix nobody sees in ten languages.
    // ⚠ **AND `available` FOLLOWED IT, BECAUSE OF WHERE IT LANDED.** Drawn page
    // 74: the trailing word attached itself to the last service — *"… Solar +
    // Fire available"* reads as a claim about Fire — so the clause is set off
    // by an em dash and names what the list is.
    const available = unit({ services: ["electric", "water"], metered_services: [] });
    expect(unitSubline(available, t)).toBe("Electric · Water — the 2 this unit can take");
    expect(unitSubline(available, t)).not.toContain("connected");
    // The separator is `·`, not `+`: every other list in this product uses it,
    // and `+` reads as arithmetic on a screen whose other lines carry money.
    expect(unitSubline(available, t)).not.toContain(" + ");
    // An unasked address draws NO clause at all rather than an empty one — a
    // sub-line is a summary and "not recorded" belongs in the fact row.
    expect(unitSubline(unit({ services: null, square_feet: null }), t)).toBe(null);
  });

  it("⚠ DEF-763: ALL TEN platform services read as NAMES on this screen — never a raw slug", () => {
    // ⚠ **THE PLATFORM SELLS TEN SERVICES, NOT SIX** (BR-RAT-024; CLAUDE.md's
    // own header said six until 2026-08-16 while the seed carried ten). This
    // sub-line read `metering.service.*`, which holds SIX keys, with
    // `defaultValue: code` — so a unit connected to any of the other four
    // printed `storm_water` at a clerk. Nothing rendered blank and nothing
    // threw, which is exactly why it sat unfiled in a comment for weeks.
    const four = unit({ services: ["storm_water", "solar", "thermal_heat", "battery"] });
    // "can take", not "connected" — see the DEF-755 case below.
    expect(unitSubline(four, t)).toBe(
      "Storm water · Solar · Thermal / Heat · Battery — the 4 this unit can take",
    );
    // …and on the RENDERED page, not only through the pure helper.
    const html = renderUnitDetail("/premises/units/u-101a", four);
    for (const name of ["Storm water", "Solar", "Thermal / Heat", "Battery"]) {
      expect(html).toContain(name);
    }
    for (const slug of ["storm_water", "thermal_heat"]) {
      expect(html).not.toContain(slug);
    }
    // The six that always worked still work — this changed the namespace, not
    // the vocabulary.
    expect(unitSubline(unit({ services: ["electric", "water"] }), t)).toBe(
      "Electric · Water — the 2 this unit can take",
    );
  });

  // ── U6 §1 SUB-LINE 2 — THE LIST IS IN SEED ORDER ─────────────────────────
  // Drawn page 74: *"a list, in the order the eleven services are defined"*.
  // ⚠ **NOTHING SORTED IT**, so the same six services read in a different order
  // on two units of one building and a clerk could not scan by position. The
  // order asserted is `SERVICE_CODES`' own, read from the one place the front
  // end defines it — retyping the eleven here would be the hand-typed list this
  // repo has already been bitten by twice.
  it("⚠ the services line is in SEED ORDER whatever order the server sent", () => {
    const scrambled = unit({ services: ["fire", "sewer", "battery", "water", "solar", "trash"] });
    const line = unitSubline(scrambled, t) ?? "";
    const seeded = SERVICE_CODES.filter((code) => scrambled.services?.includes(code)).map((code) =>
      t(`rating.service.${code}`),
    );
    const positions = seeded.map((name) => line.indexOf(name));
    expect(positions.every((at) => at >= 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    // A tenant-added code the ordered list has never met sorts to the END and
    // is never dropped — a service we do not recognise is still real data.
    const extra = unit({ services: ["hydrogen", "water"] });
    const withExtra = unitSubline(extra, t) ?? "";
    expect(withExtra.indexOf("Water")).toBeLessThan(withExtra.indexOf("hydrogen"));
  });

  // ⚠ **THE PO REPORTED THIS SCREEN AS A WHOLE (`DEF-580`, 2026-08-22):**
  // *"Details view of Unit; UI does not match with Prototype"*. The tab SET
  // already matched, so nothing had ever compared the HEADER or the tab bodies
  // to the drawing — which is what these cases now do.
  it("DEF-580: the header is r10's — premise ADDRESS in the eyebrow, `Unit A · main house` as the title", () => {
    const html = renderUnitDetail("/premises/units/u-101a", unit());
    expect(unitKicker(unit(), t)).toBe("Unit · 1408 Bluestem Ln");
    expect(unitTitle(unit(), t)).toBe("U-00101-A · Unit A");
    expect(html).toMatch(/<h1[^>]*>U-00101-A · Unit A<\/h1>/);
    // The sub-line is r10's description, from what the server sends.
    // ⚠ "available" and NOT "connected" since 2026-08-26 (DEF-755): the field
    // moved from service points to the PREMISES, and a unit can have Water
    // available with no meter and nothing connected. Swapping the source
    // without swapping the word would have traded a true sentence for a false
    // one.
    expect(unitSubline(unit({ square_feet: 1480 }), t)).toBe(
      "1,480 sq ft · Electric · Water — the 2 this unit can take",
    );
    // ⛔ r10's third part — `access: side gate, dog on property` — is DEF-591:
    // `UnitCore` has no access field, and a reassuring blank in front of a
    // meter reader is the one guess this screen must never make.
    expect(html).not.toContain("access:");
    // A unit with neither fact gets NO sub-line rather than an empty one.
    expect(unitSubline(unit({ square_feet: null, services: [] }), t)).toBeNull();
  });

  it("CR-023 §2A.2: the four KPI tiles read served facts and dash where a fact is absent", () => {
    // r10: `ACCOUNT A-10432 (Miller, Sarah · active) │ PLAN Res Standard │
    // METERS 2 │ SINCE Mar 2024`. This unit has an account and two meters and
    // NO plan, so three tiles carry a value and the plan tile says "No plan yet"
    // rather than drawing a blank that reads like a rendering failure.
    const html = renderUnitDetail("/premises/units/u-101a", unit());
    expect(html).toContain("A-00412");
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain("No plan yet");
    expect(html).toContain("kpi-grid");
  });

  it("CR-023 §2A.3: the Plan tab refuses to print an eligibility verdict nothing computed", () => {
    // ⛔ r10 prints `Passes — residential · 5/8" & 1φ 100A · inside city`.
    // DEF-404: the rule builder does not exist and `eligibility_rule` is read by
    // NO code, and `PlanRow.eligibility` is ADVISORY by its own contract. A
    // green "Passes" against a rule nobody ran is the worst line on the screen.
    const html = renderUnitDetail("/premises/units/u-101a?tab=plan", unit());
    expect(html).toContain("Eligibility check");
    expect(html).toContain('data-tracks="DEF-404"');
    expect(html).not.toContain("Passes");
  });

  it("CR-023 §2A.2: the Occupancy tab states the ONE absence it still owes a clerk", () => {
    // ⚠ **AMENDED 2026-09-10 — ONE OF THE TWO EXPLANATIONS EXPIRED.**
    //
    // `DEF-509` explained why r10's `CLOSING READ` and `FINAL BILL` columns are
    // missing, and that was right while r10 was the drawing: a column of
    // em-dashes there is the sentence "there was no closing read". The U8
    // blueprint frame has since RATIFIED a SIX-column table that contains
    // neither of them, so their absence is no longer something a clerk is owed
    // a paragraph about — and that frame's own budget is "six columns, no
    // prose". `DEF-509` stays OPEN because the underlying gap is real; what
    // went is the explanation, not the defect.
    //
    // `OQ-316` is a different kind of absence and STAYS: the vacancy rows ARE
    // drawn, they say the owner is billed, and whether that means the base
    // charge alone or the full bill is a live question about money on a row a
    // clerk can see. An open question about what IS on the screen is owed a
    // sentence; an explanation of something the drawing no longer asks for is
    // not.
    const html = renderUnitDetail("/premises/units/u-101a?tab=occupancy", unit());
    expect(html).not.toContain('data-tracks="DEF-509"');
    expect(html).toContain('data-tracks="OQ-316"');
    expect(html).not.toContain("Closing read</th>");
    expect(html).not.toContain("Final bill</th>");
  });

  it("BR-MET-095 (CR-024): the destination picker never offers the premise the unit is already on", () => {
    // The server refuses a same-premise move by name; this is the convenience
    // half — an option that can only fail is worse than no option.
    expect(moveDestinationOptions(PREMISES, "p-101")).toEqual([]);
    expect(moveDestinationOptions(PREMISES, "p-999")).toEqual([
      // Carries `search` because it delegates to `premisesPickerOptions` —
      // see the note there (`DEF-MET-5837`).
      { value: "p-101", label: "1408 Bluestem Ln · P-00101", search: "Katy" },
    ]);
  });

  it("BR-MET-095 (CR-024): the move modal states the posted-money guarantee and asks for a reason", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units`]}>
            <MoveUnitModal
              unit={unit()}
              onClose={() => undefined}
              onMoved={() => undefined}
            />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // ⚠ **THE REASSURING HALF MOVED INTO THE CONSEQUENCE TABLE (`DEF-MET-4763`)
    // AND THAT IS A REAL CHANGE, NOT A RE-WORDING.** It used to be a note above
    // the fields, drawn from the moment the modal opened; the `U11` frame draws
    // it as row 1 of `WHAT THIS WILL DO`, which appears once a destination is
    // chosen. So a clerk who has picked nothing yet no longer reads it — an
    // accepted cost of following the frame, recorded in the conformance file
    // and asserted where it now lives (`MoveUnitModal.test.tsx`, row 1).
    expect(html).not.toContain("Bills already issued keep the property they were billed under");
    // Three required inputs, and the date's help says a future date is refused.
    // DEF-MET-4721: the id IS the server's field name and the zod key, so an
    // error can actually reach the field it is about. It used to be three
    // different strings and pressing the button on an empty form did nothing.
    expect(html).toContain('id="premises_id"');
    expect(html).toContain('id="effective_date"');
    expect(html).toContain('id="reason"');
    expect(html).toContain("A future date is refused");
    // ⛔ The override panel is drawn only once the SERVER has stated a count —
    // from `GET /units/{id}/move-preview`, or from a refusal. Neither has
    // answered in a static render, so it is not here; this screen never counts
    // a unit's past accounts for itself.
    expect(html).not.toContain('id="move-acknowledge"');
    // DEF-MET-4694: the machine plural is gone from every catalogue, so this
    // assertion is now about the whole product rather than about this render.
    expect(html).not.toContain("account(s)");
  });

  it("DEF-MET-4694 (CR-089 PUJ-47): the warning has a human plural and the date refusal points at the calendar", () => {
    // ⚠ THIS CASE USED TO ASSERT THE DEFECT. It pinned *"2 account(s)"* and
    // *"Enter the date as YYYY-MM-DD"* — both correct strings, both what a
    // machine writes, and no check in this repo reads copy for tone. The
    // assertions are inverted rather than deleted so the old wording cannot
    // come back unnoticed.
    expect(t("metering.units.move.accountsWarning", { count: 1 })).toContain("one account");
    expect(t("metering.units.move.accountsWarning", { count: 2 })).toContain("2 accounts");
    expect(t("metering.units.move.accountsWarning", { count: 2 })).not.toContain("account(s)");
    expect(t("metering.unit.move_needs_override", { accounts: 2, count: 2 })).toBe(
      "This unit has carried 2 accounts. Confirm to move it anyway.",
    );
    // The field IS a native date picker (`DatePickerField`), so a refusal
    // spelling out a wire format was describing a control this screen does not
    // use. B14 rule 33 caps a refusal at five or six words.
    expect(t("metering.unit.move_date_format")).toBe("Pick the date from the calendar.");
    expect(t("metering.unit.move_date_format")).not.toContain("YYYY");
    expect(t("metering.unit.move_date_future")).toBe("A move cannot be dated in the future.");
    // DEF-511 is still open: the bill count is stated as absent, never as 0.
    expect(t("metering.units.move.billCountUnavailable")).toContain("are not counted per unit yet");
  });

  it("CR-023 §2A.2: the CURRENT account is the open one, not merely the newest row", () => {
    const rows = [
      { account_no: "A-1", opened_at: "2022-02-01", closed_at: "2024-01-04" },
      { account_no: "A-2", opened_at: "2024-03-12", closed_at: null },
      { account_no: "A-3", opened_at: "2026-01-01", closed_at: "2026-02-01" },
    ] as unknown as Parameters<typeof currentAccount>[0];
    expect(currentAccount(rows)?.account_no).toBe("A-2");
    // A unit whose accounts are ALL closed has no current account — "closed six
    // months ago" is not what a clerk means when they open this tab.
    const closed = rows.filter((row) => row.closed_at !== null);
    expect(currentAccount(closed)).toBeNull();
  });

  it("BR-MET-036: the Overview states the occupancy rule and offers no control for it", () => {
    const html = renderUnitDetail("/premises/units/u-101a?tab=overview", unit());
    expect(html).toContain("Occupied");
    expect(html).toContain("follows the active account");
    expect(html).toContain('href="/brazosbend/premises/p-101"');
    // ⚠ **THIS CASE USED TO ASSERT A SENTENCE THAT STOPPED BEING TRUE ON
    // 2026-08-21 (`DEF-MET-4696`).** `BR-MET-095` (`CR-024`) built the move and
    // this page's header has carried `Move` since; the qualifier told a clerk
    // to deactivate and re-create instead. The assertion is INVERTED rather
    // than deleted, so the retired sentence cannot come back unnoticed —
    // the same posture the move-warning case above takes.
    expect(html).not.toContain("A unit never moves between premises");
    // Read-only markup: no form, no input, no select on the Overview tab.
    expect(html).not.toContain("<input");
    expect(html).not.toContain("<select");
    expect(html.toLowerCase()).not.toContain("<form");
  });

  it("CR-023 §2A.2 / DEF-473 CLOSED: the Account tab READS the accounts instead of naming their absence", () => {
    // ⚠ **THIS TEST USED TO ASSERT A STATED ABSENCE, AND THE ABSENCE IS GONE.**
    // DEF-473 recorded that both detail views said the accounts module was not
    // built when it had shipped; the honest sentence then said the accounts
    // "are served" and this tab did not read them. Now it does —
    // `GET /accounts?f.unit_id=` — which is what closing a stated absence is
    // supposed to look like rather than re-wording it a third time.
    const html = renderUnitDetail("/premises/units/u-101a?tab=account", unit());
    expect(html).toContain("A-00412");
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain("Active");
    expect(html).not.toContain('data-tracks="DEF-473"');

    // ⚠ **AND THE PLAN TAB'S OWN ARRIVES-WITH BLOCK IS GONE TOO, FOR A
    // DIFFERENT REASON — the GAP is still there.** `BR-CUS-013`'s per-unit
    // assignment history is still rating-owned and still read back by no route,
    // and `DEF-473` stays OPEN for it. What went is the PARAGRAPH: `U6` §15
    // names *"no plan-history arrives-with block"* as a drawn absence, and B14
    // rule 32 gives this tab one sentence per section. An explanation of our
    // implementation is not one of the sentences a clerk is owed.
    // The assertions are inverted rather than deleted so the block cannot
    // return unnoticed.
    const plans = renderUnitDetail("/premises/units/u-101a?tab=plan", unit());
    expect(plans).toContain("No plan yet");
    expect(plans).not.toContain("no endpoint reads it back yet");
    expect(plans).not.toContain('data-tracks="DEF-473"');
  });

  // ⚠ **THIS TAB DREW THE SAME METER TWICE, IN A BULLET LIST (`DEF-580`).**
  // `MetersCell` printed the comma-joined numbers and a `<ul>` repeated them
  // underneath — no type, no install date, no status. r10 draws a TABLE with a
  // heading, a primary button and a RULE callout.
  // ── U5 · THE ON-UNIT TABLE IS THE SHARED `DataTable` IN SIX DRAWN COLUMNS ──
  // ⚠ **THIS CASE USED TO ASSERT THE DEFECT.** It pinned `Net meter · AMI · AMI`
  // — three classifications joined into one `Type` cell — and it pinned the
  // ABSENCE of a `Last read` column, over a note claiming the reading could not
  // be sourced. The frame draws `Service` and `Size` where that join was
  // (*"three type columns become two"*) and draws `Last read` as a COLUMN;
  // `selectors.asset_page_rows` has served the reading for every meter and
  // sub-meter since wave C. The assertions are inverted rather than deleted, so
  // neither the join nor the false note can come back unnoticed.
  it("DEF-580 / U5: the Assets tab is the shared table in the six drawn columns", () => {
    const html = renderUnitDetail("/premises/units/u-101a?tab=assets", unit(), ACCOUNTS, null, [
      {
        id: "a1",
        asset_no: "M-7001",
        type_name: "Net meter",
        meter_type_name: "AMI",
        read_method_name: "AMI",
        service: "electric",
        size_class: "Class 200",
        tab: "meters",
        status_name: "Active",
        install_date: "2024-03-12",
        // `On since` reads the seat's `assigned_from` (`DEF-MET-5861`); this
        // fixture carried only `install_date` and went red on it at the tip.
        assigned_from: "2024-03-12",
        assigned_unit_id: "u-101a",
        last_read: {
          current_value: "4182.000000",
          consumption: "4182.000000",
          unit: "kWh",
          read_at: "2026-08-28",
        },
      },
      // `DEF-MET-8362`: the server's unit page is the table's spine, so the
      // sub-meter the unit payload names comes back as a registry row too.
      {
        id: "a2",
        asset_no: "M-7204",
        type_name: "Sub-meter",
        service: "electric",
        tab: "sub_meters",
        status_name: "Active",
        assigned_unit_id: "u-101a",
      },
      // Another unit's asset. The server narrows by `f.unit_id` now; the
      // `assigned_unit_id` guard on the answer still keeps a stray row out.
      {
        id: "a9",
        asset_no: "M-9999",
        type_name: "Meter",
        status_name: "Active",
        install_date: "2020-01-01",
        assigned_unit_id: "u-999",
      },
    ]);
    expect(html).toContain("Assets on this unit");
    expect(html).toContain("+ Assign from inventory");
    expect(html).toContain("<table");
    expect(html).toContain('href="/brazosbend/assets/a1"');
    expect(html).toContain("M-7204");
    expect(html).toContain("(sub)");
    expect(html).not.toContain("M-9999");
    // ── THE SIX DRAWN COLUMNS, IN THE DRAWN ORDER ────────────────────────
    // Order is asserted, not merely presence: a table with all six headers in
    // the wrong sequence satisfies six `toContain` checks and is still not the
    // screen that was agreed.
    const headers = Array.from(html.matchAll(/<th[^>]*>(?:<button[^>]*>)?([^<]+)/g)).map(
      (m) => m[1],
    );
    // ⚠ **PRESENCE IS ASSERTED BEFORE ORDER, AND THAT IS NOT BELT-AND-BRACES.**
    // An `indexOf` comparison over a MISSING header reads `0 < -1` and fails
    // with a message about two numbers — true, and it tells the reader nothing
    // about which column is gone. The named list fails with the column in it.
    expect(headers).toEqual(
      expect.arrayContaining(["Asset", "Service", "Size", "Status", "On since", "Last read"]),
    );
    for (const pair of [
      ["Asset", "Service"],
      ["Service", "Size"],
      ["Size", "Status"],
      ["Status", "On since"],
      ["On since", "Last read"],
    ] as const) {
      expect(headers.indexOf(pair[0])).toBeLessThan(headers.indexOf(pair[1]));
    }
    // `Installed` is named as an ABSENCE by the frame; `On since` replaces it.
    expect(headers).not.toContain("Installed");
    // Three classifications in one cell is what `Service` + `Size` replace.
    expect(html).not.toContain("Net meter · AMI · AMI");
    // The served values, each in its own column.
    expect(html).toContain("Electric");
    expect(html).toContain("Class 200");
    expect(html).toContain("03/12/2024");
    // `Last read` is a DATE and a QUANTITY WITH ITS UNIT (CLAUDE.md rule 3).
    expect(html).toContain("08/28/2026");
    expect(html).toContain("kWh");
    // ⚠ **THE FALSE SENTENCE IS GONE.** It told a clerk the reading could not
    // be joined; one query joins it. Hard-won law 1 in a user-visible string.
    expect(html).not.toContain('data-tracks="DEF-592"');
    expect(html).not.toContain("nothing joins the reads onto it");
    // The status is a PILL, not plain text, and the row action is an ICON with
    // an accessible name — never a text button in a column headed `Change`.
    expect(html).toContain('class="pill');
    expect(html).toContain('aria-label="Change status"');
    expect(headers).not.toContain("Change");
    // r10's RULE callout stays: it is what says removing a meter has a cost.
    expect(html).toContain("Removal records a final read.");
  });

  // ⚠ **FOUND BY OPENING THE SCREEN, NOT BY A TEST (`DEF-595`, hard-won law 6).**
  // The unit's Account tab printed `48.450000 USD` — the stored decimal string
  // interpolated raw. CLAUDE.md hard rule 2, PO re-signed 2026-08-22: money is
  // stored to 4 and DISPLAYED to 2.
  it("DEF-595: the balance renders through the ONE money formatter — two decimals, with its symbol", () => {
    const html = renderUnitDetail("/premises/units/u-101a?tab=account", unit(), [
      { ...(ACCOUNTS[0] as Record<string, unknown>), balance: "48.450000", currency: "USD" },
    ]);
    expect(html).toContain("$48.45");
    expect(html).not.toContain("48.450000");
    expect(html).toContain("cell-money-amount");
    // A null balance is NOT zero — the books could not be asked, and "$0.00"
    // there reads as a settled account.
    const unknown = renderUnitDetail("/premises/units/u-101a?tab=account", unit(), [
      { ...(ACCOUNTS[0] as Record<string, unknown>), balance: null },
    ]);
    expect(unknown).not.toContain("$0.00");
  });

  // CR-034 (PO 2026-08-25, on the live build): *"when i go on this screen it
  // should show me what all details from plan are applicable"*, and then
  // *"dont remove plan details keep it as it is"*. So this asserts BOTH halves
  // — the six facts stay AND the unfold arrives — because a change that adds
  // one by losing the other is not what was asked for.
  it("CR-034: the Plan tab keeps its facts AND mounts the pricing unfold", () => {
    const plan = renderUnitDetail("/premises/units/u-101a?tab=plan", unit());

    // The facts that were already there. Named individually rather than as a
    // count: a count passes when one is swapped for another.
    expect(plan).toContain("Current plan");
    expect(plan).toContain("Effective from");
    expect(plan).toContain("Lock the plan on this unit");
    expect(plan).toContain("Vacant standby");
    expect(plan).toContain("Change plan →");

    // ⚠ AND THE UNFOLD IS MOUNTED. `UnitPricingPanel` and
    // `GET /units/{id}/pricing` both existed since W5 T5.3 and only the Move-in
    // wizard called them; this tab — the obvious place to ask "what is this
    // unit priced on" — did not. Hard-won law 2 in its third shape: built,
    // wired elsewhere, absent from the screen that needs it.
    //
    // ⚠ THE FIRST VERSION OF THIS ASSERTION COULD NOT FAIL FOR THE RIGHT
    // REASON. The panel renders async, so a static render returns its SKELETON
    // whatever the cache holds — and asserting "a skeleton is present" cannot
    // tell a mounted panel from any other pending query on the tab. That is the
    // flaw class this repo has recorded six times. So the cache is SEEDED, the
    // same way the harness seeds the unit and the audit rows, and the assertion
    // reads the panel's own rendered output.
    const seeded = unitPricing();
    seeded.unit.id = "u-101a";
    const priced = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    expect(priced).toContain('data-unit-pricing="u-101a"');
    // And it really is the UNFOLD, not just a mounted box: a per-service base
    // charge is what the PO asked to see on this screen.
    expect(priced).toContain("Priced on");
    // ── U6 §15 · NO SECOND PLAN BLOCK ────────────────────────────────────
    // ⚠ **THIS ASSERTION IS INVERTED FROM WHAT IT WAS.** It pinned the plan's
    // NAME inside the pricing panel, which is the frame's own named defect:
    // *"`Effective from` appears once. It was on the plan panel **and again in
    // the pricing panel below**, in two different formats — which is how a
    // clerk concludes there are two dates."* The fact list above states the
    // plan, its code, its status and its date; the panel below states them no
    // longer. `Effective from` appearing ONCE on the whole tab is the check.
    expect((priced.match(/Effective from/g) ?? []).length).toBe(1);
    expect(priced).not.toContain("Small Commercial");
    // The move-in wizard mounts the SAME panel with no facts above it, so
    // there the block is drawn whole — asserted in `MoveInWizard.test.tsx`.
  });

  it("CR-034 (b): the Plan tab states the PERIOD it is answering for, and invents none", () => {
    // The PO, verbatim: *"showing in - what period you are reporting data
    // for"*. With no period on the wire the heading says *as of <today>* — it
    // does NOT name a month nobody chose. That default was declined against a
    // calendar: on the 25th, defaulting to the current month makes the service
    // date the 31st and resolves a rate version effective the 28th, which is
    // not in force today, under a heading claiming to describe today.
    const seeded = unitPricing();
    seeded.unit.id = "u-101a";
    const html = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    // ⚠ THE ATTRIBUTE STAYS ISO AND THE SENTENCE NAMES ITS MONTH — CR-089
    // wave H (`DEF-MET-4689`). `data-pricing-as-of` is a machine value and a
    // date a PERSON reads is `25 Aug 2026`, because `08/25/2026` and
    // `2026-08-25` forty pixels apart is the defect this closed.
    expect(html).toContain('data-pricing-as-of="2026-08-25"');
    expect(html).toContain("Showing what applies today, 25 Aug 2026");
    // ── U6 §8 · THE PICKER FOLDS AWAY TO ONE LINK ────────────────────────
    // Drawn page 74: *"**Four controls and a sentence were open permanently**
    // for a question almost nobody asks, above the answer everybody came
    // for."* The link is what is on screen; the controls are behind it.
    expect(html).toContain('data-pricing-period-toggle=""');
    expect(html).toContain("look at another period");
    // ⚠ **CLOSED, AND THAT IS ASSERTED RATHER THAN ASSUMED.** A `<details>`
    // renders its contents in the DOM whether it is open or shut, so
    // `toContain("Period from")` cannot tell the two apart — which is exactly
    // the "check that cannot fail" shape this repo has recorded 56 times. The
    // OPEN attribute is what carries the fact.
    expect(html).not.toMatch(/<details[^>]*\sopen\b/);
    // …and the control is still MOUNTED behind it, which is the half
    // `showPeriod` exists for. G13's law: an optional prop nothing passes is
    // dead UI, and a folded control is not a deleted one.
    expect(html).toContain('data-pricing-period-control=""');
    expect(html).toContain("Period from");
    expect(html).toContain("Period to");
    expect(html).toContain('type="date"'); // B14 rule 7
  });

  it("CR-034 (b): a stated period is echoed on screen, and a mid-period plan change is NOT collapsed", () => {
    // BR-RAT-114 / DEF-504 — a bill for a window containing a plan change is
    // produced once per stretch, each on ITS plan. A screen naming ONE plan as
    // *the* plan for the period would state something no bill will do.
    const seeded = unitPricing({
      period: {
        start: "2026-07-01",
        end: "2026-07-31",
        as_of: "2026-07-31",
        supplied: true,
        source: "caller",
      },
      plan_history: {
        served: true,
        reason: null,
        tracks: null,
        stretches: [
          {
            rate_plan_id: "plan-77",
            plan_name: "Small Commercial",
            plan_code: "SC-1",
            plan_version: 3,
            assigned_from: "2026-07-01",
            assigned_to: "2026-07-15",
            source: "change_plan",
          },
          {
            rate_plan_id: "plan-88",
            plan_name: "Residential",
            plan_code: "RES-1",
            plan_version: 1,
            assigned_from: "2026-07-15",
            assigned_to: null,
            source: "change_plan",
          },
        ],
        splits_at: ["2026-07-15"],
      },
    });
    seeded.unit.id = "u-101a";
    const html = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    expect(html).toContain("Showing what applies for 1 Jul 2026 to 31 Jul 2026");
    expect(html).toContain('data-plan-history=""');
    // BOTH stretches, and the date a real bill would split on. The `data-`
    // keys stay ISO — they are how a test and a script find a row — and every
    // date a person READS names its month (CR-089 wave H, `DEF-MET-4689`).
    expect(html).toContain('data-plan-stretch="2026-07-01"');
    expect(html).toContain('data-plan-stretch="2026-07-15"');
    expect(html).toContain("would be split on 15 Jul 2026");
    // ⚠ THE STRETCH TABLE'S OWN CELLS, which no browser walkthrough can reach:
    // nothing seeded changes plan mid-period, so this suite is the only thing
    // that draws them and the only thing that can hold them to one shape.
    expect(html).toContain("<td>1 Jul 2026</td>");
    expect(html).toContain("<td>15 Jul 2026</td>");
    expect(html).toContain("Residential");
  });

  it("CR-034 (b): a charge code with no plan override SHOWS the code's own amount", () => {
    // The panel printed *"At the charge code's own amount"* with no amount — a
    // sentence that promises a figure and withholds it, which reads as
    // *unknowable* rather than merely *unfetched*. Both facts now travel and
    // NEITHER is collapsed: which one bills is billing's precedence rule.
    const seeded = unitPricing();
    seeded.unit.id = "u-101a";
    seeded.charge_codes = [
      {
        ...seeded.charge_codes[0],
        amount_override: null,
        amount_override_display: null,
        amount: "18.000000",
        amount_display: "18.00",
      },
    ];
    const html = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    expect(html).toContain('data-charge-code-own-amount="18.00"');
    expect(html).toContain("The code&#x27;s own amount"); // the new column's header
    // The old sentence still stands where it belongs — beside an ABSENT
    // override — and now it has the number next to it.
    expect(html).toContain("At the charge code&#x27;s own amount");
  });

  it("CR-034 (b): the plan's OFFERED discounts show, and the GRANT is a stated absence", () => {
    // BR-RAT-069 — binding a discount to a plan grants it to nobody; a bill run
    // reads `discount_enrolments`, and an enrolment belongs to an ACCOUNT which
    // a unit does not have.
    const seeded = unitPricing({
      discounts: {
        offered: [
          {
            discount_id: "dis-1",
            code: "SENIOR",
            name: "Senior",
            status: "active",
            type: "percentage",
            value_display: "10.00%",
            eligibility: null,
            available_from: null,
            available_to: null,
            terms: null, // CR-034 §7 — the conditions have their own test below
          },
        ],
        granted: { served: false, reason: "unit_has_no_account", tracks: null },
      },
    });
    seeded.unit.id = "u-101a";
    const html = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    expect(html).toContain('data-discount-offered="SENIOR"');
    expect(html).toContain("10.00%");
    expect(html).toContain('data-discount-granted-absent="unit_has_no_account"');
    expect(html).toContain("a unit has no account");
    // ⚠ AND THE TENANT-WIDE COUNT IS NOWHERE IN THIS SECTION. Rating serves an
    // `enrolled` figure that is not plan-scoped and certainly not unit-scoped;
    // a number here is read as this unit's however it is captioned.
    //
    // Asserted as the row's EXACT three cells rather than as
    // `not.toContain("enrolled")` — the page carries that word elsewhere, so
    // the negative form would pass or fail for reasons that have nothing to do
    // with this table.
    //
    // ⚠ **`</tr>` IS PART OF THIS STRING AND IT IS THE WHOLE GUARD.** The first
    // version of this line stopped after the third `</td>` and a mutation that
    // appended a fourth cell PASSED — a substring match cannot see what comes
    // after it, so the check reported success over exactly the thing it was
    // pointed at. Closing the row is what makes it a statement about the WHOLE
    // row instead of its first three cells (DEF-182's shape, one file over).
    expect(html).toContain("<td>SENIOR</td><td>Senior</td><td>10.00%</td></tr>");
  });

  // ── CR-034 §7 · AMENDED 2026-08-26 · THE CONDITIONS TO AVAIL A DISCOUNT ───
  //
  // PO, verbatim: *"We should show all discount plan offer and what condition
  // are required to avail that discount ; when account is attached it will
  // avail those discounts"*.
  const SENIOR_TERMS = {
    version_no: 2,
    version_status: "active",
    effective_from: "2026-01-01",
    effective_to: null,
    resolved_on: "2026-08-31",
    eligibility_summary: "Age 65+",
    eligibility_rule_recorded: true,
    eligibility_checked: {
      served: false,
      reason: "no_code_evaluates_a_discount_eligibility_rule",
      tracks: null,
    },
    enrolment_mode: "apply_and_approve",
    verification_method: "annual_recertification",
    proof_required: true,
    accepted_proof_kinds: ["government_id", "birth_certificate"],
    proof_before_first_reduction: true,
    recertification_months: 12,
    recertification_notice_days: 60,
    recertification_grace_days: 0,
    lapse_behaviour: "notify_then_drop",
    applies_to: "whole_bill",
    applies_to_service: null,
    applies_to_service_name: null,
    applies_to_charge_codes: [],
    currency: "USD",
    cap_per_bill_display: "20.00",
    cap_per_year_display: null,
    cap_lifetime_display: null,
    bill_floor_amount_display: "0.00",
    stacks_with_others: false,
    exclusivity_group: "assistance",
    stacking_precedence: 10,
  };

  function withSeniorTerms(over: Record<string, unknown> = {}) {
    const seeded = unitPricing({
      discounts: {
        offered: [
          {
            discount_id: "dis-1",
            code: "SENIOR",
            name: "Senior discount",
            status: "active",
            type: "percentage",
            value_display: "15.00%",
            eligibility: "Age 65+",
            available_from: null,
            available_to: null,
            terms: { ...SENIOR_TERMS, ...over },
          },
        ],
        granted: { served: false, reason: "unit_has_no_account", tracks: null },
      },
    });
    seeded.unit.id = "u-101a";
    return renderUnitDetail("/premises/units/u-101a?tab=plan", unit(), ACCOUNTS, null, [], seeded);
  }

  it("CR-034 §7: every condition required to AVAIL the discount is on the screen", () => {
    const html = withSeniorTerms();
    // The block exists and is named for the discount it belongs to.
    expect(html).toContain('data-discount-terms="SENIOR"');
    // WHO QUALIFIES — the sentence a human wrote on the programme.
    expect(html).toContain("Age 65+");
    // HOW IT IS GRANTED, and the proof it takes, by DOCUMENT rather than by
    // a bare `true`: "proof_required: yes" tells a clerk nothing they can ask
    // the customer for.
    expect(html).toContain("The customer applies and staff approve it");
    expect(html).toContain("Government ID · Birth certificate");
    expect(html).toContain("nothing comes off a bill until the proof is on file");
    expect(html).toContain("Proof at enrollment and again every year");
    // HOW IT IS KEPT.
    expect(html).toContain("Recertified every 12 month(s).");
    expect(html).toContain("60 days&#x27; notice");
    // WHAT IT REDUCES and BY HOW MUCH AT MOST — the cap is the customer's own
    // limit, which is why it may appear on a unit screen at all.
    expect(html).toContain("The whole bill, before taxes");
    expect(html).toContain("At most 20.00 USD off one bill");
    // BR-RAT-074 — the floor, at its stored 0.00, which is a real statement
    // (to zero, never below: a negative bill is a CREDIT).
    expect(html).toContain('data-br-ref="BR-RAT-074"');
    // BR-RAT-073 — the exclusivity sentence r10's SENIOR detail states.
    expect(html).toContain('data-br-ref="BR-RAT-073"');
    expect(html).toContain("Cannot be held alongside another discount.");
    expect(html).toContain("assistance");
  });

  it("CR-034 §7: the conditions are shown as RECORDED, never as ENFORCED", () => {
    // ⚠ THE LOAD-BEARING TEST OF THIS SLICE. `eligibility_rule` is stored and
    // NOTHING in this product evaluates it (`apps/rating/discounts.py`, and
    // `discount_services`' own *"It does not evaluate eligibility"*). A screen
    // that presented `Age 65+` as a checked condition would tell a clerk the
    // software refuses unqualified customers — it refuses nobody, and the
    // clerk stops checking. So the absence travels beside the condition.
    const html = withSeniorTerms();
    expect(html).toContain(
      'data-discount-eligibility-unchecked="no_code_evaluates_a_discount_eligibility_rule"',
    );
    expect(html).toContain("nothing in this product evaluates it");
    expect(html).toContain("Staff confirm it when the account is enrolled.");
    // …and with NO rule recorded the sentence is the other one, because
    // "a rule is recorded and unread" and "no rule exists" are two facts.
    const none = withSeniorTerms({ eligibility_rule_recorded: false });
    expect(none).toContain("Nothing in this product checks this condition.");
    expect(none).not.toContain("A rule for this condition is recorded");
  });

  it("CR-034 §7: the section says these apply once an ACCOUNT IS ENROLLED", () => {
    // Requirement 3 — the PO reads the section as a statement about what will
    // apply, not a catalogue. ⚠ And it says ENROLLED rather than ATTACHED:
    // BR-RAT-069, a plan grants a discount to nobody, so the softer sentence
    // would promise a reduction the bill run does not make.
    const html = withSeniorTerms();
    expect(html).toContain('data-discount-framing=""');
    expect(html).toContain("granted by enrolling the account");
    // The GRANT is still a stated absence and still says why.
    expect(html).toContain('data-discount-granted-absent="unit_has_no_account"');
  });

  it("CR-034 §7: a discount with NO filed version says so and invents no conditions", () => {
    const html = withSeniorTerms();
    expect(html).not.toContain("No filed version of this discount could be read");
    const unfiled = unitPricing({
      discounts: {
        offered: [
          {
            discount_id: "dis-2",
            code: "MILITARY",
            name: "Veteran discount",
            status: "draft",
            type: null,
            value_display: null,
            eligibility: null,
            available_from: null,
            available_to: null,
            terms: null,
          },
        ],
        granted: { served: false, reason: "unit_has_no_account", tracks: null },
      },
    });
    unfiled.unit.id = "u-101a";
    const drawn = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      unfiled,
    );
    expect(drawn).toContain('data-discount-terms="MILITARY"');
    expect(drawn).toContain("No filed version of this discount could be read");
    // ⚠ "not filed" is not "asks for nothing", and the sentence says which.
    expect(drawn).toContain("That is not the same as it having none.");
  });

  it("CR-034 §7: the tenant-wide count stays off the screen even beside the conditions", () => {
    // The same guard as the offered-row one, one section down: the conditions
    // block grew the discounts section by twelve lines, and none of them is a
    // programme-wide figure. `budget_cap` is omitted at SOURCE
    // (`rating._discount_terms`) so it cannot be rendered by accident.
    const html = withSeniorTerms();
    expect(html).toContain("<td>SENIOR</td><td>Senior discount</td><td>15.00%</td></tr>");
    expect(html).not.toContain("12,312");
    expect(html).not.toContain("data-discount-enrolled");
  });

  // ── PO 2026-08-26 · *"B Default to this month"* ──────────────────────────
  it("CR-034: the STAFF Plan tab opens on the current month", () => {
    // ⚠ TWO ASSERTIONS IN OPPOSITE DIRECTIONS, and the second one is in
    // `MoveInWizard.test.tsx`: staff get the month, a customer signing up
    // still gets *as of today* with no period on the wire. A month-END
    // `as_of` resolves a rate version effective the 28th on the 25th, which is
    // wrong to show a person who is about to sign — and right for staff asking
    // what applies this month.
    //
    // This asserts what the panel ASKED FOR, not what the heading printed: the
    // heading renders the SERVER's `period`, so a panel that had silently
    // stopped sending the month would still print it from the fixture.
    expect(currentMonthPeriod(new Date(2026, 7, 25))).toEqual({
      start: "2026-08-01",
      end: "2026-08-31",
    });
    expect(currentMonthPeriod(new Date(2026, 1, 14))).toEqual({
      start: "2026-02-01",
      end: "2026-02-28",
    });
    expect(currentMonthPeriod(new Date(2028, 1, 14))).toEqual({
      start: "2028-02-01",
      end: "2028-02-29", // a leap February, from the calendar and not a table
    });
    // …and the window reaches the wire as the endpoint's own both-or-neither
    // params.
    const month = currentMonthPeriod(new Date(2026, 7, 25));
    expect(unitPricingPath("u-101a", month)).toBe(
      "/units/u-101a/pricing?period_start=2026-08-01&period_end=2026-08-31",
    );
    // The Plan tab renders from data seeded ONLY on the month key
    // (`renderUnitDetail`), so this drawing is the proof it asked on it.
    const html = withSeniorTerms();
    expect(html).toContain('data-pricing-period-control=""');
    expect(html).toContain("SENIOR");
  });

  it("CR-034 (b): the three minimum floors are shown side by side and none is derived", () => {
    // 🔒 Which floor WINS is BR-RAT-016/028 — PROPOSED on GT-13, not ❄️ frozen.
    // Deciding it on a screen would be billing math in a second place where no
    // golden test can see it. Three labelled figures, and the sentence says so.
    const seeded = unitPricing({
      minimum_charges: {
        plan: { amount: "15.000000", source: "plan" },
        services: [
          {
            service: "electric",
            name: "Electric",
            minimum_amount: "6.000000",
            currency: "USD",
            source: "plan_service",
          },
        ],
        schedules: [
          {
            service: "electric",
            tariff_id: "tar-1",
            tariff_name: "Commercial Electric",
            version_id: "ver-1",
            minimum_bill: "5.000000",
            minimum_bill_display: "5.00",
            currency: "USD",
            size_label: 'Electric 200A',
            minimum_state: "size_minimum",
            size_rows: [],
            source: "rate_size_row",
          },
        ],
      },
    });
    seeded.unit.id = "u-101a";
    const html = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    expect(html).toContain('data-minimum-charges=""');
    expect(html).toContain('data-minimum-source="plan"');
    expect(html).toContain('data-minimum-source="plan_service:electric"');
    expect(html).toContain('data-minimum-source="rate_schedule:electric"');
    // …and the screen says which one applies is not its call.
    expect(html).toContain("decided by the billing rules, not by this screen");
  });

  it("DEF-MET-8823: the schedule row shows the minimum for the unit's connection size", () => {
    // PO 2026-10-01, option A — the minimum is set PER METER SIZE. Water
    // Residential: 5/8" $15.00, 1" $25.00, 2" $40.00. One 1" connection shows
    // $25.00; an unsized connection shows "No minimum", never a version figure.
    const row = (over: Partial<UnitPricingMinimumCharges["schedules"][number]>) => ({
      service: "water",
      tariff_id: "tar-w",
      tariff_name: "Water Residential",
      version_id: "ver-w",
      minimum_bill: "25.000000",
      minimum_bill_display: "25.00",
      currency: "USD",
      size_label: 'Water 1"',
      minimum_state: "size_minimum" as const,
      size_rows: [],
      source: "rate_size_row",
      ...over,
    });
    const render = (schedule: UnitPricingMinimumCharges["schedules"][number]) => {
      const seeded = unitPricing({
        minimum_charges: { plan: { amount: "15.000000", source: "plan" }, services: [], schedules: [schedule] },
      });
      seeded.unit.id = "u-101a";
      return renderUnitDetail("/premises/units/u-101a?tab=plan", unit(), ACCOUNTS, null, [], seeded);
    };
    const sized = render(row({}));
    expect(sized).toContain("$25.00");
    expect(sized).toContain('Water 1&quot;');
    expect(sized).not.toContain("tar-w");

    const unsized = render(
      row({ minimum_bill: null, minimum_bill_display: null, size_label: null, minimum_state: "no_size_recorded" }),
    );
    expect(unsized).toContain('data-minimum-size="no_size_recorded"');
    expect(unsized).toContain("No size");
    expect(unsized).toContain("No minimum");
    expect(unsized).not.toContain("$25.00");
  });

  it("CR-034 (b): the contract and the tax set state their limits rather than filling them", () => {
    // Two absences, two DIFFERENT sentences, neither of them an empty section.
    const seeded = unitPricing();
    seeded.unit.id = "u-101a";
    const html = renderUnitDetail(
      "/premises/units/u-101a?tab=plan",
      unit(),
      ACCOUNTS,
      null,
      [],
      seeded,
    );
    expect(html).toContain('data-contract-absent="captured_and_held_by_the_product_owner"');
    // ⚠ IT CITES A REAL ROW AND NOT A FABRICATED ONE. `CR-020` is the PO's own
    // contracts-on-plans request — captured 2026-08-20, HELD 2026-08-21 (*"hold
    // on dont proceed"*). No OQ was minted beside it, which would have been one
    // question under two ids (OQ-197's failure, from the other direction).
    expect(html).toContain('data-cr="CR-020"');
    // …and it is NOT an `ArrivesWith`: nothing is arriving, the work is paused.
    expect(html).toContain("written down and paused");
    // DEF-273 — the plan's tax bindings are the set to choose FROM, and the
    // final list narrows again by the account's customer class.
    expect(html).toContain('data-tax-narrowing="narrows_by_customer_class_at_bill_time"');
    expect(html).toContain("not the final list");
    // …and the worked month is UNCHANGED and still says so (OQ-363).
    expect(html).toContain('data-tracks="OQ-363"');
  });

  it("DEF-580: the Plan tab ends in `Change plan →` and the Account tab in `Open account →` + `Move-out…`", () => {
    const plan = renderUnitDetail("/premises/units/u-101a?tab=plan", unit());
    expect(plan).toContain("Change plan →");
    // ── U6 §8 · IT IS THE OUTLINE TIER, NOT THE PRIMARY ──────────────────
    // ⚠ **THIS ASSERTION IS INVERTED FROM WHAT IT WAS.** `DEF-580` made it a
    // PRIMARY, deliberately, from r10. The blueprint frame draws it in the
    // outline tier in a footer bar at the END of the frame — so the loudest
    // control on the tab no longer interrupts the answer a clerk came for.
    // The tier is read off the button that carries the label, not off the
    // page: a `toContain('data-variant="secondary"')` would pass on any of the
    // other secondaries on this tab.
    const changePlanButton = plan.slice(0, plan.indexOf("Change plan →")).lastIndexOf("<button");
    expect(plan.slice(changePlanButton, plan.indexOf("Change plan →"))).toContain(
      'data-variant="secondary"',
    );
    // …and it sits BELOW the pricing panel, which is what "at the end of the
    // frame" means on a tab whose answer is that panel.
    expect(plan.indexOf("data-unit-pricing")).toBeLessThan(plan.indexOf("Change plan →"));
    // ── U6 §5 ROWS 6 AND 7 · A CLAUSE, NEVER A BARE WORD ─────────────────
    // Drawn page 74: *"Locked and standby say what they mean rather than `No`
    // twice."* Two rows reading `No` are answers to two different questions and
    // are indistinguishable without the clause.
    expect(plan).toContain("a change here does not need a supervisor");
    expect(plan).toContain("nothing bills while the unit is empty");
    // ── U6 §15 · NO `Rate schedules` FACT ROW ────────────────────────────
    // The pricing panel below names the schedule on every service row, so the
    // fact row said the same thing less well and forty pixels higher up.
    expect(plan).not.toContain("Rate schedules");
    // ⚠ DEF-584's second site: the eligibility absence used to be a `<div>`
    // inside the `<dl class="met-facts">` grid, which blew the label column to
    // full width. It is a VALUE in its own row now.
    expect(plan).toContain('data-tracks="DEF-404"');
    expect(plan).not.toContain("rating-arrives");

    const account = renderUnitDetail("/premises/units/u-101a?tab=account", unit());
    // ⚠ **`Open the account →`, REWORDED 2026-09-10 TO THE DRAWN LABEL.** The
    // U7 frame draws the article and the button read `Open account →`, which is
    // the same act in telegram English — the label is the only thing that
    // moved. The DESTINATION and the pair of footer actions are what this case
    // is about and both are unchanged.
    expect(account).toContain("Open the account →");
    expect(account).toContain("Move-out…");
    // ⛔ BR-SHL-025: Move-out is DISABLED WITH ITS REASON, never wired to
    // something adjacent (hard-won law 2) and never silently missing.
    //
    // ⚠ **THE REASON CHANGED ON 2026-09-08 AND THIS ASSERTION IS THE RECORD OF
    // WHY (`DEF-CUS-4702`).** It read *"This unit has no door to it yet"*,
    // which a clerk reads as *the flow is not built* — and `MoveOutWizard` has
    // been routed and live at `/{tenant}/accounts/{id}/move-out` since
    // 2026-08-25. That is hard-won law 2's MIRROR: a live screen behind a dead
    // control, with `tsc`, `G13` and this very test passing over it, because
    // nothing anywhere asks whether a REFUSAL is still true. The control stays
    // held (this unit owns no door to that flow and building one is not wave
    // I's); the sentence now says where the flow lives, so the clerk can reach
    // it through `Open account →` beside it.
    expect(account).toContain("Move-out runs from the account");
    expect(account).not.toContain("no door to it yet");
    expect(account).toContain("disabled");
  });

  // ⚠ THE PO REPORTED THIS ONE BY NAME (`DEF-579`, 2026-08-22): *"in Premises
  // and Unit level Audit log does not point to audit log it should audit log on
  // that perticular unit or premises"*. r10's PRM-03 draws four unit-scoped
  // rows in the tab; the shipped tab drew a link and left the screen.
  it("DEF-579 / BR-AUD-010: the Audit log tab draws THIS unit's own rows, and still links to the full viewer", () => {
    const html = renderUnitDetail("/premises/units/u-101a?tab=audit", unit(), ACCOUNTS, {
      page: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "au-1",
            created_at: "2026-03-12T09:00:00Z",
            actor: null,
            action: "unit.plan_assigned",
            entity_type: "unit",
            entity_id: "u-101a",
            summary: "Move-in · account A-10432 opened",
            source: null,
          },
        ],
      },
      window: { window: "hot", from: "2024-08-22T00:00:00Z" },
    });
    expect(html).toContain("<table");
    // AMENDED 2026-08-24 (DEF-645, the same cell one screen along): the Action
    // column is the event as a sentence and the recorded values open behind a
    // disclosure — the code and the server's summary blob are not drawn.
    expect(html).toContain("Plan assigned to a unit");
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("unit.plan_assigned");
    expect(html).toContain('data-audit-action="unit.plan_assigned"');
    expect(html).toContain("System job"); // BR-AUD-003
    expect(html).toContain("/audit-log?f.entity_type=unit&amp;f.entity_id=u-101a");
  });

  it.todo(
    "US-MET-002 detail (isolation): a cross-tenant unit id answers not-found under RLS — server scope (G5)",
  );
});

// ── US-SHL-020 / BR-SHL-044 — S15's half of the shared strip ────────────────
// S14 asserts the other half. Together they are the claim the prototype makes
// on one page (UtilityBilling.html line 713) and this app has to keep across
// two routes: one header, one strip, and only the slot's contents change.

/** The header, up to the tab strip: where the ONE primary action must live. */
function headerActions(html: string): string {
  const end = html.indexOf('class="page-header-tabs"');
  return end === -1 ? html : html.slice(0, end);
}

describe("US-SHL-020 — S15 wears the shared page header (BR-SHL-044)", () => {
  it("TC-1: the same slot carries '+ New unit' on this route, and no premise action", () => {
    const html = renderUnits("/premises/units", { rows: [unit()], access: "Full" });
    expect(headerActions(html)).toContain("+ New unit");
    expect(html).not.toContain("+ New premise");
    // Both tabs are drawn here — this route is the SAME strip, not its own.
    expect(html).toContain(">Premises</button>");
    expect(html).toContain(">Units</button>");
    expect(html).toContain(">Imports</button>");
    expect(PREMISES_TAB_STRIP.map((tab) => tab.id)).toEqual(["premises", "units", "imports"]);
    // ⚠ **THE HEADING FOLLOWS THE TAB, AND THAT REVERSES A SIGNED RULE.** This
    // read `<h1>Premises</h1>` on all three tabs, from `CR-023` §3 and r10 line
    // 630. The Product Owner was shown the drawn frame beside the shipped
    // screen on 2026-09-10 and ruled the other way — *"The drawing says Units
    // with its own subtitle. - t should say Unit"* — so the Units tab draws the
    // frame's own title and the frame's own line under it, in the slot between
    // the title and the strip.
    expect(html).toMatch(/<h1[^>]*>Units<\/h1>/);
    expect(html).toContain("Every unit that can take service, across every property.");
    // ⚠ **ALL THREE TABS, NOT ONLY THE ONE THAT CHANGED.** A check that reads
    // the tab it was written for is how the other two drift: the heading is a
    // property of the strip now, so the strip is what is asserted.
    expect(
      PREMISES_TAB_STRIP.map((tab) => [tab.id, t(tab.titleKey)] as const),
    ).toEqual([
      ["premises", "Premises"],
      ["units", "Units"],
      ["imports", "Premises"],
    ]);
    // …and the secondary changes with the tab, so it is the UNITS importer here.
    expect(headerActions(html)).toContain("↑ Import units");
    expect(headerActions(html)).not.toContain("↑ Import premises");
  });

  it("TC-2: the Units tab carries ONE line and it sits ABOVE the strip", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-10 AND THE FRAME IS WHY.**
    // The tab drew a two-sentence explainer below the strip. The frame's own
    // cognitive-load budget is *"Nine columns, one search, no prose"* and it
    // lists prose of any kind — and the roll-up sentence — among its drawn
    // absences, so the tab's one line is the subtitle ABOVE the strip and there
    // is not a second one below it. B14 rule 32's description budget says the
    // same thing in general terms.
    const html = renderUnits("/premises/units", { rows: [unit()] });
    expect(html).not.toContain("A unit is a metered space inside a premise");
    expect(html).not.toContain("page-header-explainer");
    expect(html).not.toContain("A premise is a physical property or address.");
    // The one line, and it is above the strip rather than below it.
    const line = html.indexOf("Every unit that can take service");
    expect(line).toBeGreaterThan(-1);
    expect(line).toBeLessThan(html.indexOf("page-header-tabs"));
    // ⚠ **AND ONE TAB KEEPS ITS EXPLAINER**, which is what stops this becoming
    // a sweep nobody asked for. It was TWO until 2026-09-19, when the PO asked
    // for the Premises tab's 27-word explainer to go the same way this one did
    // — *"On premsies list page reduce this text"* — leaving Imports alone.
    expect(PREMISES_TAB_STRIP.filter((tab) => tab.explainerKey !== null)).toHaveLength(1);
  });

  it("TC-5: the list screen has no back link; the unit detail has one", () => {
    expect(renderUnits("/premises/units", { rows: [unit()] })).not.toContain("page-header-back");
    const detail = renderUnitDetail("/premises/units/u-101a", unit());
    expect(detail).toContain("page-header-back");
    expect(detail).toContain("← Units");
    expect(detail).not.toContain("← ← ");
  });

  it("TC-6: exactly one primary action in the header, and it stays guarded", () => {
    const html = headerActions(renderUnits("/premises/units", { rows: [unit()], access: "Full" }));
    expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
    // BR-SHL-025 travelled with the button: a View role still gets it disabled
    // WITH the reason rather than a control that quietly vanished.
    const viewOnly = headerActions(
      renderUnits("/premises/units", { rows: [unit()], access: "View" }),
    );
    expect(viewOnly).toContain("+ New unit");
    expect(viewOnly).toContain("disabled");
    expect(viewOnly).toContain("Your role can view this but not change it.");
  });

  it("the unit detail header keeps both pills in the status slot, ahead of the strip", () => {
    const html = renderUnitDetail("/premises/units/u-101a", unit());
    const head = headerActions(html);
    // BR-MET-036: occupancy is a pill in the identity block, never a control.
    expect(head).toContain("Occupied");
    expect(head).toContain("Active");
    expect(html.indexOf("page-header-actions")).toBeLessThan(html.indexOf("page-header-tabs"));
    expect(head).not.toContain('data-variant="primary"');
  });
});

// ── BR-MET-101 / BR-MET-100 — the flag and the gap on S15 (W3 lane 2026-08-22) ──

describe("BR-MET-101 — a common area is a unit with a VISIBLE flag", () => {
  it("the flagged row draws r10's word — 'Common' — and the merely-vacant row does not", () => {
    // BR-MET-101's accepted cost, verbatim: the flag "is what separates a
    // common area from a vacant unit billed to the owner (BR-MET-094), which
    // would otherwise be the same row". Both rows here are vacant; exactly one
    // is flagged; exactly one pill renders.
    const html = renderUnits("/premises/units", {
      rows: [
        unit({
          id: "u-101c",
          unit_no: "U-00101-C",
          label: "Hallway lighting",
          is_common_area: true,
          occupancy: "vacant",
          occupant: null,
          account_no: null,
          status: "vacant",
        }),
        VACANT,
      ],
    });
    expect(html).toContain("Hallway lighting");
    expect((html.match(/>Common</g) ?? []).length).toBe(1);
  });

  it("the unit detail carries the flag in the identity block and as a stated fact", () => {
    const flagged = renderUnitDetail(
      "/premises/units/u-101a",
      unit({ is_common_area: true }),
    );
    expect(flagged).toContain(">Common<");
    const overview = renderUnitDetail(
      "/premises/units/u-101a?tab=overview",
      unit({ is_common_area: false }),
    );
    // the fact renders in BOTH states — an absent row would be unreadable as
    // "not common" vs "nobody asked".
    expect(overview).toContain("Common area");
    expect(overview).not.toContain(">Common<");
  });
});

describe("BR-MET-100 — an unplanned unit is COUNTED AND FINDABLE on S15", () => {
  it("a unit with no plan draws the worded gap chip; a planned one draws none", () => {
    // The ruling's own words: the missing plan "renders as a visible gap
    // rather than an empty cell" — because an unplanned unit "does not fail —
    // it simply never appears on a bill" while looking complete.
    // the CHIP is asserted by its warning-pill markup, because the words "No
    // plan" legitimately also appear as the filter's own option label.
    const unplanned = renderUnits("/premises/units", { rows: [unit()] }); // rate_plan_id: null
    // CR-018 Route B: the warn tone renders its utility pair now.
    expect(unplanned).toContain('pill bg-warning-100 text-warning-700">No plan<');
    const planned = renderUnits("/premises/units", {
      rows: [unit({ rate_plan_id: "rp-1" })],
    });
    expect(planned).not.toContain('pill bg-warning-100 text-warning-700">No plan<');
  });

  it("the Units tab DECLARES the plan filter, with the ruled 'unplanned' value first", () => {
    // Declared is load-bearing: BE-05 ignores an undeclared `f.` param, so an
    // undeclared control would silently return every unit as a filtered slice.
    expect(PLAN_FILTER_VALUES).toEqual(["unplanned", "planned"]);
    const filter = CONFIG.filters?.find((f) => f.name === "plan");
    expect(filter?.options.map((o) => o.value)).toEqual(["unplanned", "planned"]);
    const html = renderUnits("/premises/units", { rows: [unit()] });
    expect(html).toContain("No plan");
  });
});

// ── DEF-782 · PRM-01U's control row (PO 2026-08-26) ────────────────────────
// *"also can you see this Unit landing screen - search, filter, colume filter,
// description - I ahve also given you screenshot from prototype - can you
// correct the ui"*.
//
// ⚠ THESE ARE MARKUP ASSERTIONS, NOT PROP ASSERTIONS (hard-won law 2). Each of
// the three DOM ones was run against the unmodified screen first and each
// failed there; the failures are quoted in the lane report. The GEOMETRY —
// that the toolbar is one 36px band and not three — is not assertable in
// jsdom at all and lives in `10-scripts/render-checks/units-toolbar.mjs`,
// which measures it in a real Chromium (hard-won law 6).
describe("S15 · the toolbar reads like r10's PRM-01U (DEF-782)", () => {
  it("the filter slot is no longer the .met-filters full-width GRID", () => {
    // `.met-filters` is `display:grid; width:100%` — dropped into
    // `.table-toolbar`'s flex row it claimed the whole line and pushed the
    // occupancy segment and the export onto a third row. Measured in Chromium:
    // 156px tall before, 36px after.
    expect(renderUnits("/premises/units", { rows: [unit()] })).not.toContain(
      'class="met-filters"',
    );
  });

  it("a premise-scoped list NAMES the premise in a removable chip (B14 rule 12)", () => {
    const html = renderUnits("/premises/units?sort=unit_no&dir=asc&f.premises_id=prem-1", {
      rows: [unit()],
    });
    expect(html).toContain('aria-label="Remove');
  });

  it("and the picker is not left beside that chip still showing its placeholder", () => {
    // SearchSelectField seeds its displayed text ONCE from the option matching
    // `value`, and this picker's options arrive on a SECOND request — so on a
    // scoped list the box settled on "Any premise" while the list was scoped to
    // one premise. Two controls, one fact, and they disagreed.
    const html = renderUnits("/premises/units?sort=unit_no&dir=asc&f.premises_id=prem-1", {
      rows: [unit()],
    });
    expect(html).not.toContain('id="f.premises_id"');
  });

  it("the picker IS there while nothing is applied (the capability is not cut)", () => {
    expect(renderUnits("/premises/units", { rows: [unit()] })).toContain('id="f.premises_id"');
  });

  // ── chipFilters, the pure half ──────────────────────────────────────────
  const declared = [
    { name: "occupancy", label: "Occupancy", options: [{ value: "vacant", label: "Vacant" }] },
    { name: "premises_id", label: "Premise", options: [] },
  ];
  const premisesOptions = [
    { value: "prem-1", label: "P-11024 · 500 Main Plaza" },
    { value: "prem-2", label: "P-10432 · 1408 Elm St" },
  ];
  const stateWith = (filters: Record<string, string>) =>
    parseTableParams(new URLSearchParams(), CONFIG) && {
      ...parseTableParams(new URLSearchParams(), CONFIG),
      filters,
    };

  it("chipFilters hides the premise group entirely while nothing is applied", () => {
    const out = chipFilters(declared, stateWith({}), premisesOptions);
    expect(out.map((f) => f.name)).toEqual(["occupancy"]);
  });

  it("chipFilters hands the panel ONE option, never the whole premises list", () => {
    // BR-SHL-033 · B14 rule 9: 1,247 premises are a type-ahead, never a wall of
    // checkboxes. The chip needs exactly the applied option and nothing else.
    const out = chipFilters(declared, stateWith({ premises_id: "prem-1" }), premisesOptions);
    const premise = out.find((f) => f.name === "premises_id");
    expect(premise?.options).toEqual([{ value: "prem-1", label: "P-11024 · 500 Main Plaza" }]);
  });

  it("chipFilters survives an applied id the picker has not loaded a label for", () => {
    const out = chipFilters(declared, stateWith({ premises_id: "prem-9" }), premisesOptions);
    expect(out.find((f) => f.name === "premises_id")?.options).toEqual([]);
  });

  it("chipFilters drops a group with NO options — a legend over nothing (BR-SHL-010)", () => {
    // The `service` group drew exactly that on every units list in the product:
    // `options: []` in the config, so the + Filter panel headed a fieldset
    // "Service" with not one box under it.
    const withEmpty = [...declared, { name: "service", label: "Service", options: [] }];
    const out = chipFilters(withEmpty, stateWith({}), premisesOptions);
    expect(out.map((f) => f.name)).toEqual(["occupancy"]);
  });

  it("the service filter's vocabulary is the TENANT's enabled set, not the page's rows", () => {
    // BR-MET-003. Deriving it from whichever units are on screen would offer a
    // different set on page 2 than on page 1.
    const config = unitsTableConfig(
      t,
      [],
      [
        { value: "electric", label: "Electric" },
        { value: "water", label: "Water" },
      ],
      CELLS,
    );
    expect(config.filters?.find((f) => f.name === "service")?.options).toEqual([
      { value: "electric", label: "Electric" },
      { value: "water", label: "Water" },
    ]);
  });

  // ── B14 rule 19, and the fail-closed resolution ────────────────────────
  it("the search prompt is THIS list's own sentence once the catalogue carries it", () => {
    expect(unitsSearchPlaceholderKey(() => "Search premises, units, meters…")).toBe(
      UNITS_SEARCH_PLACEHOLDER_KEY,
    );
  });

  it("and falls back rather than printing the key at a user (law 3)", () => {
    // DataTable calls t() on this key with NO defaultValue, so an un-fanned-in
    // key would render its own name into the search box in all eleven locales.
    expect(unitsSearchPlaceholderKey((k) => k)).toBeUndefined();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-002@947cf31 (story+rules snapshot hash — EP-MET-01)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — S15's half of TC-1/TC-2/TC-5/TC-6; S14 asserts the other)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline; this file adds 5 passing) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 US-SHL-020's tab CLICK is browser scope and is the it.todo in the S14 suite rather than restated here; this file asserts what the Units ROUTE renders, which is the other half of the same claim · E4 TC-5/TC-6 assert SERVER verdicts (the delete refusal, the label-uniqueness error); the frontend half is the guarded control and the rendered envelope, both asserted here — the click path itself is browser scope · E4 the isolation halves are the G5 suite's, on live Postgres
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
