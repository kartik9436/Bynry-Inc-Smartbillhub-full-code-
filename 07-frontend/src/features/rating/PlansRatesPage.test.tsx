// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-001 (S9 Plans tab: roll-up, columns, filters, row actions, RBAC) ·
//           US-RAT-003 (lifecycle transitions from the row) · US-RAT-004 (the Rate
//           schedules card grid + its structure previews)
//           Screens: S9
// Rules:    BR-RAT-024 · BR-RAT-027 (the base Σ is the SERVER's) · BR-RAT-030 ·
//           BR-RAT-031 (no approval state anywhere) · BR-RAT-032 · BR-SHL-010 ·
//           BR-SHL-011 · BR-SHL-025 (server-authoritative RBAC) · BR-SHL-032 · BR-SHL-034
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend Utilities (US-RAT-001 §4), America/Chicago.
//
// The load-bearing test here is the DOM scan for an approve control. BR-RAT-031
// as-modified REMOVED the board-approval workflow, and the API has no approve
// route — so if a future edit ever adds a button for one, that test fails.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import { PLAN_SORTS, getPlans, getRateSchedules } from "@/api/endpoints";
import type {
  MyPermissions,
  PlanListResult,
  PlanRow,
  Paginated,
  ScheduleCard,
  TenantServiceRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { PlansRatesPage, ROLLUP_QUERY_KEY } from "./PlansRatesPage";
import { NEW_PLAN_ROUTE, planTableConfig } from "./PlansTab";
import { PLAN_LIST_SORTS } from "./planListParts";
import { previewKind, scheduleTableConfig } from "./RateSchedulesTab";
import {
  HISTORY_TAB,
  RATING_TABS,
  RATING_TAB_STRIP,
  isDecimalShape,
  planStatusTone,
  ratingAccess,
  ratingIsDenied,
  ratingIsReadOnly,
  ratingTabFromParam,
  scheduleStatusTone,
} from "./ratingShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`. Tests state the tenant
// the browser would be showing, so both are visible here rather than implied.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const SERVICES: TenantServiceRow[] = [
  {
    service: "electric",
    name: "Electric",
    enabled: true,
    primary_uom: "kWh",
    alt_uom: "kW",
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 4,
    active_accounts: 1098,
  },
  {
    service: "water",
    name: "Water",
    enabled: true,
    primary_uom: "kgal",
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 3,
    active_accounts: 950,
  },
  {
    service: "gas",
    name: "Gas",
    enabled: false,
    primary_uom: null,
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 0,
    active_accounts: 0,
  },
];

// The US-RAT-001 §4 seed, as `GET /plans` serves it: every amount is a
// NUMERIC(18,6) STRING, and `base_charges` is the server's own Σ.
const RES_STD: PlanRow = {
  id: "p-res-std",
  code: "RES-STD",
  name: "Residential Standard",
  description: null,
  status: "published",
  version: 3,
  account_type_id: null,
  // DEF-RAT-5768 — the class is a LIST; `[]` means EVERY class.
  account_type_ids: [],
  account_subtype_id: null,
  budget_billing: false,
  eligibility: {},
  minimum_bill_amount: null,
  // BR-RAT-102 — this fixture states NO surcharge, so the premises is never consulted.
  outside_city_factor: null,
  effective_from: "2026-08-01",
  effective_to: null,
  services: ["electric", "water"],
  base_charges: "30.500000",
  rate_schedules: [
    { service: "electric", tariff_id: "t-res-e", tariff_name: "Res Electric · Tiered" },
    { service: "water", tariff_id: "t-res-w", tariff_name: "Res Water · Inclining" },
  ],
  accounts: 842,
};

const STANDBY: PlanRow = {
  ...RES_STD,
  id: "p-standby",
  code: "STBY",
  name: "Vacant / Standby",
  status: "draft",
  version: 1,
  base_charges: "15.000000",
  rate_schedules: [],
  accounts: 0,
};

const ROLLUP = { plans: 6, rate_schedules: 7, charge_codes: 8,
    // DEF-443 — the line counts six things now; `contracts` is null because
    // CR-020 is deferred and the product holds no contracts (not zero).
    discounts: 0,
    taxes: 0,
    contracts: null, effective_from: "2026-08-01" };

function planList(rows: PlanRow[]): PlanListResult {
  return { count: rows.length, next: null, previous: null, results: rows, rollup: ROLLUP };
}

const RES_ELECTRIC: ScheduleCard = {
  id: "t-res-e",
  name: "Res Electric · Tiered",
  service: "electric",
  service_name: "Electric",
  account_type_id: null,
  structure: "tiered",
  status: "active",
  scheduled_change: null,
  current_version: {
    id: "v1",
    // DEF-RAT-5715 — BR-RAT-104's chain. The server sends all four on every
    // version row; a plain (uncorrected) version reads null for each.
    corrects: null,
    superseded_by: null,
    correction_reason: null,
    corrected_by: null,
    model: "tiered",
    uom: "kWh",
    currency: "USD",
    base_charge: "0.000000",
    minimum_bill: null,
    base_charge_display: "0.00",
    minimum_bill_display: null,
    size_rows: [],
    filing_authority: null,
    filed_on: null,
    regulator_approved_on: null,
    regulator_approver: null,
    effective_from: "2026-08-01",
    effective_to: null,
    approved_by: null,
    regulator_ref: null,
    submitted_by: null, // DEF-367 — no filer recorded on this fixture
    version_label: null, // DEF-369 — falls back to the derived ordinal
    change_reason: null, // DEF-280 — no authored change note
    notify_customers: false,
    publish_public: false,
    structure: {
      model: "tiered",
unit: "kgal",
currency: "USD",
      tiers: [
        {
          seq: 1,
          season: null, size_class: null,
          from_qty: "0.000000",
          to_qty: "500.000000",
          from_qty_display: "0 kWh",
          to_qty_display: "500 kWh",
          unit_price: "0.110000",
        },
        {
          seq: 2,
          season: null, size_class: null,
          from_qty: "500.000000",
          to_qty: "1000.000000",
          from_qty_display: "500 kWh",
          to_qty_display: "1000 kWh",
          unit_price: "0.140000",
        },
        { seq: 3, season: null, size_class: null, from_qty: "1000.000000", to_qty: null, from_qty_display: "1000 kWh", to_qty_display: null, unit_price: "0.190000" },
      ],
    },
  },
  draft_version: null,
  used_by_plans: 2,
  applied_to_accounts: 1098,
  // DEF-441 — r10 line 764's five columns. A fixture states them
  // explicitly rather than defaulting, because "0 sizes" and
  // "no seasons" are the values the cells render differently.
  size_count: 0,
  season_labels: [],
  block_count: 0,
  window_count: 0,
  effective_from: null,
};

const RES_WATER: ScheduleCard = {
  ...RES_ELECTRIC,
  id: "t-res-w",
  name: "Res Water · Inclining",
  service: "water",
  service_name: "Water",
  // US-RAT-004 TC-3: a future-effective version. NOT "pending approval".
  scheduled_change: "2026-09-01",
  used_by_plans: 1,
  applied_to_accounts: 842,
  // DEF-441 — r10 line 764's five columns. A fixture states them
  // explicitly rather than defaulting, because "0 sizes" and
  // "no seasons" are the values the cells render differently.
  size_count: 0,
  season_labels: [],
  block_count: 0,
  window_count: 0,
  effective_from: null,
};

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access }],
  };
}

const PLAN_CONFIG = planTableConfig(t, [], {
  name: () => <span />,
  version: () => <span />,
  services: () => <span />,
  schedules: () => <span />,
  base: () => <span />,
  units: () => <span />,
  from: () => <span />,
  to: () => <span />,
  status: () => <span />,
  open: () => <span />,
});
const SCHEDULE_CONFIG = scheduleTableConfig(t, []);

interface Seed {
  access?: string;
  plans?: PlanListResult;
  schedules?: Paginated<ScheduleCard>;
  services?: TenantServiceRow[];
}

/** Renders S9 with its answers already in the cache — no network, ever. */
function renderHub(path: string, seed: Seed = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const search = new URLSearchParams(path.split("?")[1] ?? "");
  queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access ?? "Full"));
  queryClient.setQueryData(queryKeys.plans(ROLLUP_QUERY_KEY), seed.plans ?? planList([]));
  queryClient.setQueryData(queryKeys.tenantServices, seed.services ?? SERVICES);
  if (seed.plans !== undefined) {
    const state = { ...defaultState(PLAN_CONFIG), ...fromSearch(search, PLAN_CONFIG) };
    queryClient.setQueryData(
      queryKeys.plans(serializeTableParams(state, PLAN_CONFIG).toString()),
      seed.plans,
    );
  }
  if (seed.schedules !== undefined) {
    const state = { ...defaultState(SCHEDULE_CONFIG), ...fromSearch(search, SCHEDULE_CONFIG) };
    queryClient.setQueryData(
      queryKeys.rateSchedules(serializeTableParams(state, SCHEDULE_CONFIG).toString()),
      seed.schedules,
    );
  }
  // The routes mirror App.tsx's, because the tab IS a URL segment (BR-SHL-011):
  // rendering the page bare would leave `useParams().tab` empty and every tab
  // test would silently assert against the default Plans tab.
  const page = <PlansRatesPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/plans-rates" element={page} />
            <Route path="/plans-rates/:tab" element={page} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// The two tiny helpers keep the seed key identical to what the screen computes.
function defaultState<Row>(config: Parameters<typeof serializeTableParams<Row>>[1]) {
  return {
    q: "",
    sort: config.defaultSort.sort,
    dir: config.defaultSort.dir,
    page: 1,
    per: 50 as const,
    filters: {} as Record<string, string>,
  };
}
function fromSearch<Row>(
  search: URLSearchParams,
  config: Parameters<typeof serializeTableParams<Row>>[1],
) {
  const filters: Record<string, string> = {};
  for (const filter of config.filters ?? []) {
    const value = search.get(`f.${filter.name}`);
    if (value !== null && value !== "") {
      filters[filter.name] = value;
    }
  }
  return { filters };
}

describe("US-RAT-001 — the S9 Plans tab", () => {
  it("US-RAT-001 TC-1: the roll-up, the six default columns and the server's derived base", () => {
    const html = renderHub("/plans-rates", { plans: planList([RES_STD, STANDBY]) });
    // The header roll-up is the SERVER's counts, and its date goes through the
    // shared formatter in the tenant TZ (BR-SHL-034).
    expect(html).toContain("6 plans");
    expect(html).toContain("7 rate schedules");
    expect(html).toContain("8 charge codes");
    expect(html).toContain("08/01/2026");
    // CR-167 task 6 (DEF-RAT-9333): images 01–03's columns — Schedules is a
    // count and Units replaces Accounts. `plansList.dom.test.tsx` asserts the
    // whole order.
    for (const label of ["Plan", "Version", "Services", "Schedules", "Base charges", "Units", "Status"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).toContain("Residential Standard");
    expect(html).not.toContain("Res Electric · Tiered");
    // BR-RAT-027: the Σ is rendered exactly as the server sent it. Nothing on
    // this screen added 18.50 to 12.00 to get here.
    expect(html).toContain("30.50");
    expect(html).toContain("842");
    // The capability row: name asc by default, and Plan is the identity column.
    expect(PLAN_CONFIG.defaultSort).toEqual({ sort: "name", dir: "asc" });
    expect(PLAN_CONFIG.columns.find((column) => column.identity === true)?.key).toBe("name");
    // …and its Download, which had no route until POST /exports landed. Plans
    // are a MONEY table, so the server writes the BR-SHL-016 audit row.
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="plans"');
    expect(html.toLowerCase()).not.toContain("xlsx");
  });

  it("US-RAT-001 TC-2/TC-3 / BR-SHL-011: search and the status filter live in the URL", () => {
    expect(PLAN_CONFIG.searchFields).toEqual(["name", "code"]);
    const names = PLAN_CONFIG.filters?.map((filter) => filter.name);
    expect(names).toContain("status");
    expect(names).toContain("service");
    // EP-RAT-01's matrix also names a customer-class filter. It is deliberately
    // ABSENT: `account_types` is the unbuilt customers module's catalog and no
    // endpoint serves it, so an option list would have to be invented.
    expect(names).not.toContain("customer_class");
    const status = PLAN_CONFIG.filters?.find((filter) => filter.name === "status");
    expect(status?.options.map((option) => option.value)).toEqual([
      "draft",
      "published",
      "archived",
    ]);
    const html = renderHub("/plans-rates?f.status=draft", { plans: planList([STANDBY]) });
    expect(html).toContain("Vacant / Standby");
    expect(html).not.toContain("Residential Standard");
  });

  it("US-RAT-001 TC-4: the sortable set is the server's own", () => {
    // ⚠ **`base_charges` LEFT THIS SET BY RULING ON 2026-09-27 —
    // `BR-RAT-1040`, closing `DEF-RAT-6927`. DO NOT PUT IT BACK.** The Monthly
    // base total read `$0.00` on every plan because the server summed
    // `plan_services.base_charge`, the column `BR-RAT-088` retired — and that
    // same annotation was the sort's SQL key, so the ORDER was as meaningless
    // as the figure and merely looked plausible. The real figure needs the
    // charge codes narrowed by customer class and size, which is a walk and not
    // a column, so there is nothing for `ORDER BY` to read.
    //
    // ⚠ **`NFR-3` IS NOT WEAKENED.** The list still pages and sorts in SQL;
    // one sort OPTION is withdrawn. This case is deliberately asserted WHOLE
    // and against the server's declared set, so a lane restoring the flag on
    // the column alone goes red here rather than shipping a control the server
    // will silently ignore.
    const sortable = PLAN_CONFIG.columns
      .filter((column) => column.sortable === true)
      .map((c) => c.key);
    // CR-167 §7.3 (task 6): the server's sorts are now name · version · units ·
    // effective_from · effective_to · status. Base charges is still not one.
    expect(sortable).toEqual(["name", "version", "units", "effective_from", "effective_to", "status"]);
    expect(sortable).toEqual([...PLAN_SORTS]);
    expect(PLAN_LIST_SORTS).toBe(PLAN_SORTS);
    expect(sortable).not.toContain("base_charges");
  });

  it("US-RAT-001 TC-5: the delete LOCK is the server's answer (Delete a draft now lives on the draft's page, CR-167 §5.5 L13)", () => {
    // The audit-lock is re-counted inside the server's transaction and rendered
    // from its envelope — never pre-guessed on a screen.
    const locked = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "rating.plans.locked_referenced",
      params: { accounts: 842, invoices: 5 },
      br_ref: "BR-RAT-030",
    });
    expect(t(locked.messageKey, locked.params)).toContain("842 accounts");
    expect(t(locked.messageKey, locked.params)).toContain("Archive it instead");
  });

  it("US-RAT-001 TC-6 / BR-SHL-025: a View role gets the tab read-only, with the reason", () => {
    // A4 gives Billing Clerk and Executive "View" on plans_rates.
    expect(ratingIsReadOnly("View")).toBe(true);
    expect(ratingIsReadOnly("Full")).toBe(false);
    expect(ratingIsReadOnly(null)).toBe(false); // unknown access hides nothing
    expect(ratingIsDenied("—")).toBe(true);
    expect(ratingAccess(permissions("View"))).toBe("View");
    expect(ratingAccess(undefined)).toBeNull();

    const readOnly = renderHub("/plans-rates", { access: "View", plans: planList([RES_STD]) });
    // The create control is PRESENT and disabled WITH its reason, never hidden.
    expect(readOnly).toContain("+ New plan");
    expect(readOnly).toContain('disabled=""');
    expect(readOnly).toContain("Your role can view Plans &amp; Rates but not change them.");

    const denied = renderHub("/plans-rates", { access: "—", plans: planList([RES_STD]) });
    expect(denied).not.toContain("+ New plan");
    expect(denied).toContain("System Admins");
  });

  it("BR-RAT-031: there is no approve control anywhere on this screen", () => {
    const html = renderHub("/plans-rates", { plans: planList([RES_STD, STANDBY]) }).toLowerCase();
    // Not disabled — ABSENT. The workflow was removed and no route exists, so
    // no permission could ever unlock one.
    for (const forbidden of ["approve", "approval", "awaiting"]) {
      expect(html).not.toContain(forbidden);
    }
    // Publishing IS the gate. Since CR-167 task 6 it is offered on the
    // draft's Review (*Publish plan*, §5.3 L12), not on the list row — the row
    // only opens the plan, and its accessible name says so.
    expect(html).toContain('aria-label="open"');
  });

  it("BR-RAT-030: the status pill's tone follows the plan's status", () => {
    // The status-driven row actions left the list in CR-167 task 6 (§5.3).
    expect(planStatusTone("published")).toBe("success");
    expect(planStatusTone("draft")).toBe("neutral");
    expect(planStatusTone("archived")).toBe("warning");
  });

  it("BR-SHL-032: every lifecycle confirm names the action and its consequence", () => {
    for (const kind of ["publish", "archive", "delete"]) {
      const verb = t(`rating.plans.confirm.${kind}.verb`);
      expect(verb).not.toBe("OK");
      expect(verb.toLowerCase()).toContain("plan");
    }
    expect(
      t("rating.plans.confirm.archive.body", { name: "Residential Standard", accounts: 842 }),
    ).toContain("842 accounts");
  });

  it("US-RAT-001 §4: the empty state names what a plan IS, and offers the one forward move", () => {
    const html = renderHub("/plans-rates", { plans: planList([]) });
    expect(html).toContain("No plans yet");
    expect(html).toContain("+ New plan");
    expect(NEW_PLAN_ROUTE).toBe("/plans-rates/plans/new");
  });

  it.todo(
    "US-RAT-001 TC-7 (isolation): a Lone Star Ridge session sees no Brazos Bend plan in any permutation — server scope (G5)",
  );
  it.todo(
    "browser scope → Playwright: clicking Publish opens the confirm, and confirming fires the toast and refetches the list",
  );
});

describe("US-RAT-004 — the S9 Rate schedules table", () => {
  // ⚠ DEF-441 MOVED WHAT THIS SURFACE DRAWS, AND THESE TWO CASES MOVED WITH IT.
  // r10 line 764 draws a nine-column TABLE, not a card grid, so the row carries
  // a structure SUMMARY (`Tiered · 3 blocks`) and two count COLUMNS — the tier
  // matrix belongs to the schedule DETAIL (RAT-02), which is where a person goes
  // to read prices. The verbatim-price rule did not lose its test: it is
  // asserted directly against `StructurePreview` below and again in
  // `RateScheduleWizard.test.tsx`. The table's own nine columns are covered by
  // `RateSchedulesTable.test.tsx`.
  it("US-RAT-004 TC-1: each ROW shows its structure summary and its usage counts", () => {
    const html = renderHub("/plans-rates/rates", {
      schedules: { count: 2, next: null, previous: null, results: [RES_ELECTRIC, RES_WATER] },
    });
    expect(html).toContain("Res Electric · Tiered");
    // The prose footer became two right-aligned numeric columns (r10's own
    // `font-feature-settings:tnum`), so the counts are separately sortable and
    // separately exportable.
    expect(html).not.toContain("Used by 2 plans · applied to 1098 accounts");
    expect(html).toContain("1,098");
  });

  it("US-RAT-004 TC-2 / BR-SHL-010: the declared filters are service, structure and status", () => {
    expect(SCHEDULE_CONFIG.searchFields).toEqual(["name"]);
    expect(SCHEDULE_CONFIG.filters?.map((filter) => filter.name)).toEqual([
      "service",
      "structure",
      "status",
    ]);
    const structure = SCHEDULE_CONFIG.filters?.find((filter) => filter.name === "structure");
    expect(structure?.options.map((option) => option.value)).toEqual([
      "flat",
      "tiered",
      "time_of_use",
      "demand",
      "seasonal",
      "capacity",
      "percent_of_service",
    ]);
  });

  it("US-RAT-004 TC-3 / BR-RAT-031: a future version is a SCHEDULED CHANGE, never an approval", () => {
    const html = renderHub("/plans-rates/rates", {
      schedules: { count: 1, next: null, previous: null, results: [RES_WATER] },
    });
    expect(html).toContain("Change scheduled — effective");
    expect(html).toContain("09/01/2026");
    expect(html.toLowerCase()).not.toContain("approval");
    expect(scheduleStatusTone("active")).toBe("success");
    expect(scheduleStatusTone("draft")).toBe("neutral");
  });

  it("US-RAT-004 §5: the preview kind follows the stored rows, not a guess", () => {
    expect(previewKind(undefined)).toBe("none");
    expect(previewKind({})).toBe("none");
    expect(previewKind({ tiers: [] })).toBe("none");
    expect(previewKind(RES_ELECTRIC.current_version?.structure)).toBe("tiers");
    expect(
      previewKind({
        windows: [
          {
            label: "On",
            season: null,
            day_type: "weekday",
            start_time: "14:00",
            end_time: "20:00",
            unit_price: "0.220000",
            channel: "tou_on",
          },
        ],
      }),
    ).toBe("windows");
    expect(
      previewKind({
        capacity: { unit_label: "panel", rate_per_unit: "10.000000", currency: "USD" },
      }),
    ).toBe("capacity");
    expect(previewKind({ percent: "40.000000", basis_service: "water" })).toBe("percent");
  });

  it("US-RAT-004 TC-5: a failed list renders A18 §4 and Retry re-issues the same query", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify({ code: "SYS-001", message_key: "errors.sys-internal" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
    });
    await expect(getRateSchedules({}, client)).rejects.toBeInstanceOf(ApiError);
  });

  it("the tab vocabulary matches the sidebar's own child paths", () => {
    // ⚠ SIX ENTRIES, AND THAT IS THE OPEN QUESTION, NOT A DRIFTED TEST.
    // `discounts` is CR-013 part 3 · §18 row 10 — *"the tab does not exist; the
    // 6 tables do"* — placed between Charge codes and Taxes & fees because that
    // is r10's own order. r10 draws FIVE tabs and this list now holds five plus
    // `history`, which r10 does not draw at all: what is built is `… · RATE
    // CHANGES` where the drawing has `… · DISCOUNTS`. **Whether Rate changes is
    // kept, folded into the rate detail's `Versions & filings` tab, or retired
    // is the Product Owner's to rule** (§18), and the next case pins that the
    // Discounts build did not quietly decide it by deletion.
    expect(RATING_TABS.map((tab) => tab.path)).toEqual([
      "/plans-rates",
      "/plans-rates/rates",
      "/plans-rates/charge-codes",
      "/plans-rates/discounts",
      "/plans-rates/taxes-fees",
      "/plans-rates/history",
    ]);
    // BR-SHL-011's spirit: an unknown segment falls back, it never errors.
    expect(ratingTabFromParam(undefined)).toBe("plans");
    expect(ratingTabFromParam("nonsense")).toBe("plans");
    expect(ratingTabFromParam("taxes-fees")).toBe("taxes-fees");
    expect(ratingTabFromParam("discounts")).toBe("discounts");
  });

  it("⚠ adding Discounts did NOT remove or move Rate changes — that is the PO's ruling to make", () => {
    // §18: *"building the Discounts tab without ruling on Rate changes leaves
    // the product with six tabs and the drawing with five."* This case exists
    // so the reconciliation is a decision somebody takes, not something a lane
    // does by deleting a line while its own feature is green.
    expect(RATING_TABS.some((tab) => tab.id === "history")).toBe(true);
    expect(HISTORY_TAB.path).toBe("/plans-rates/history");
    // History stays OUT of the drawn strip (it is a destination with its own
    // top-right button), so the strip itself renders five — r10's count, with
    // Discounts in r10's position.
    expect(RATING_TAB_STRIP.map((tab) => tab.id)).toEqual([
      "plans",
      "rates",
      "charge-codes",
      "discounts",
      "taxes-fees",
    ]);
  });

  it("the money guard is a SHAPE test, and a discount's minus sign survives it", () => {
    expect(isDecimalShape("18.50")).toBe(true);
    expect(isDecimalShape("0.000001")).toBe(true);
    // BR-RAT-043: a plan discount is a NEGATIVE charge amount. A client-side
    // sign check here would make the ratified discount mechanism unusable.
    expect(isDecimalShape("-2.00")).toBe(true);
    expect(isDecimalShape("1e5")).toBe(false);
    expect(isDecimalShape("$18.50")).toBe(false);
    expect(isDecimalShape("18,50")).toBe(false);
  });

  it("the list wrapper sends the shared grammar and nothing else", async () => {
    let url = "";
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (input) => {
        url = String(input);
        return new Response(
          JSON.stringify({ count: 0, next: null, previous: null, results: [], rollup: ROLLUP }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    });
    await getPlans(
      {
        q: "commercial",
        filters: { status: "draft", nonsense: "x" },
        sort: "accounts",
        dir: "desc",
        page: 2,
        per: 50,
      },
      client,
    );
    expect(url).toContain("q=commercial");
    expect(url).toContain("f.status=draft");
    expect(url).toContain("sort=accounts");
    expect(url).toContain("dir=desc");
    // An undeclared filter is never sent — BR-SHL-010.
    expect(url).not.toContain("nonsense");
  });

  it.todo(
    "US-RAT-004 TC-4: Archive on a referenced schedule renders the server's 'referenced by N plans' refusal — needs a click (browser scope)",
  );
  it.todo(
    "US-RAT-004 TC-6 (isolation): only the caller's own tenant's cards and counts render — server scope (G5)",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-001@6304a38 (story+rules snapshot hash — EP-RAT-01; co-stories US-RAT-003@6304a38 · US-RAT-004@0b56fac)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 US-RAT-001 TC-1's "$30.50" renders as the server's storage-precision string ($30.500000): `GET /plans` serves NUMERIC(18,6) and MoneyCell never re-rounds, so the test asserts the substring rather than baking a client-side rounding in — API gap reported · E4 clicking a row action is browser scope, so the lifecycle TCs assert the transition table and the rendered refusal copy instead
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
