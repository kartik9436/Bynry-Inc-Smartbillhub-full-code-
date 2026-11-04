// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-004 (S9 Rate schedules)   Screens: S9 → S11
// Defect:   DEF-441 — *"rate schedule is in table format in Proto - you ahve
//           done card format"* (Product Owner, side-by-side screenshots,
//           2026-08-21). r10 line 764 draws
//           `<table class="table lt">` with NINE headers: Schedule · Svc ·
//           Structure · Sizes · Seasons · Plans · Accounts · Effective · Status.
// Rule:     r10 is THE reference (PO ruling 2026-08-16) · B14 rule 3 (ONE table
//           type) · B14 rule 15 (row actions are ICONS) · BR-SHL-011 (the URL
//           grammar the sort keys travel in) · BR-RAT-031 (three derived
//           statuses) · DEF-360 (an empty size axis MEANS "one rate, every size")
// ───────────────────────────────────────────────────────
// WHY THIS FILE EXISTS AT ALL, WHICH IS THE INSTRUCTIVE PART
// ---------------------------------------------------------
// There was NO rendering test for this surface. `PlansRatesPage.test.tsx`
// imported exactly two things from it — `previewKind` and `scheduleTableConfig`
// — both pure. So the card grid could be, and was, the wrong layout for months
// with a green suite: nothing in the repo had ever looked at what it drew.
//
// PROVED RED BEFORE TRUSTED GREEN (hard-won law 7). Every assertion below was
// first run against the card-grid implementation at HEAD~1:
//   · the nine headers          → 0 of 9 found (a card grid has no <th>)
//   · sortable headers          → 0 sort buttons
//   · `5 sizes` / `Summer / Winter` / `1,098` / the effective date
//                               → absent; the card drew none of these fields
//   · the column chooser        → absent (the card grid had no toolbar)
//   · `— ` for a zero count     → the card drew "Used by 0 plans · applied to 0
//                                 accounts", so the em-dash assertion failed
//   · the sort-key/server match → RED once SCHEDULE_SORTS grew to nine and the
//                                 config still declared three
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { SCHEDULE_SORTS } from "@/api/endpoints";
import type {
  MyPermissions,
  Paginated,
  TenantServiceRow,
  VersionRow,
} from "@/api/endpoints";
import type { ScheduleListRow } from "@/api/rateScheduleReads";
import { queryKeys } from "@/api/queryClient";
import { serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { PlansRatesPage, ROLLUP_QUERY_KEY } from "./PlansRatesPage";
import {
  countText,
  scheduleTableConfig,
  seasonsText,
  sizesText,
  structureText,
} from "./RateSchedulesTab";
import type { Translator } from "./ratingShared";

const t: Translator = (key, params) => i18n.t(key, params);

// CR-157-BRC10 B — the 2026-10-01 drawing's headers, left to right, read off
// `05-prototype/rate-schedules-2026-10-01/images/01-list-all.png`. r10's nine
// (with Svc and Seasons) are superseded by it.
const DRAWN_HEADERS = [
  "Schedule",
  "Service",
  "Structure",
  "Customer class",
  "Base code",
  "Sizes",
  "Effective",
  "Plans",
  "Accounts",
  "Status",
  "Actions",
] as const;

const SERVICES: TenantServiceRow[] = [
  { service: "water", name: "Water", enabled: true },
  { service: "electric", name: "Electric", enabled: true },
] as unknown as TenantServiceRow[];

function version(overrides: Partial<VersionRow> = {}): VersionRow {
  return {
    id: "v1",
    // DEF-RAT-5715 — BR-RAT-104's chain. The server sends all four on every
    // version row; a plain (uncorrected) version reads null for each.
    corrects: null,
    superseded_by: null,
    correction_reason: null,
    corrected_by: null,
    model: "tiered",
    uom: "kGal",
    currency: "USD",
    base_charge: null,
    minimum_bill: null,
    base_charge_display: null,
    minimum_bill_display: null,
    size_rows: [],
    filing_authority: null,
    filed_on: null,
    regulator_approved_on: null,
    regulator_approver: null,
    effective_from: "2026-01-01",
    effective_to: null,
    approved_by: null,
    regulator_ref: null,
    submitted_by: null, // DEF-367 — no filer recorded on this fixture
    version_label: null, // DEF-369 — falls back to the derived ordinal
    change_reason: null, // DEF-280 — no authored change note
    notify_customers: false,
    publish_public: false,
    structure: { model: "tiered", unit: "kgal", currency: "USD" },
    ...overrides,
  };
}

function card(overrides: Partial<ScheduleListRow>): ScheduleListRow {
  return {
    customer_class_name: null,
    base_code: "BASE-W",
    sizes_priced: 5,
    sizes_total: 5,
    id: "t-1",
    name: "Residential Water · Inclining block",
    service: "water",
    service_name: "Water",
    account_type_id: null,
    structure: "tiered",
    status: "active",
    scheduled_change: null,
    current_version: version(),
    draft_version: null,
    used_by_plans: 2,
    applied_to_accounts: 914,
    size_count: 5,
    season_labels: [],
    block_count: 3,
    window_count: 0,
    effective_from: "2026-01-01",
    ...overrides,
  };
}

// r10's own table, row for row, so a failure here is comparable to the drawing.
const ROWS: ScheduleListRow[] = [
  card({}),
  card({
    id: "t-2",
    name: "Commercial Electric · Time-of-use",
    service: "electric",
    service_name: "Electric",
    structure: "time_of_use",
    customer_class_name: "Residential",
    base_code: "BASE-E",
    sizes_priced: 3,
    sizes_total: 3,
    scheduled_change: "2027-01-01",
    size_count: 3,
    season_labels: ["Summer", "Winter", "Shoulder"],
    block_count: 0,
    window_count: 2,
    used_by_plans: 1,
    applied_to_accounts: 1098,
    effective_from: "2026-03-01",
  }),
  card({
    id: "t-3",
    name: "Commercial Water · Seasonal",
    structure: "seasonal",
    size_count: 4,
    season_labels: ["Summer", "Winter"],
    block_count: 2,
    window_count: 0,
    used_by_plans: 1,
    applied_to_accounts: 84,
    effective_from: "2026-06-01",
  }),
  card({
    id: "t-4",
    name: "Residential Water 2027 filing",
    status: "draft",
    structure: "flat",
    // BR-RAT-031: a draft is a version with NO date, and r10 draws an em-dash
    // in Accounts for exactly this row.
    current_version: null,
    draft_version: version({ id: "v-draft", effective_from: null }),
    size_count: 0, // DEF-360: one rate prices every connection size
    base_code: null,
    sizes_priced: 0,
    sizes_total: 0,
    season_labels: [],
    block_count: 0,
    window_count: 0,
    used_by_plans: 0,
    applied_to_accounts: 0,
    effective_from: null,
  }),
];

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access }],
  };
}

const CONFIG = scheduleTableConfig(t, []);

function schedules(rows: ScheduleListRow[]): Paginated<ScheduleListRow> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** S9's Rate schedules tab with its answers already cached — no network. */
function renderRates(rows: ScheduleListRow[] = ROWS, access = "Full"): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  queryClient.setQueryData(queryKeys.plans(ROLLUP_QUERY_KEY), {
    count: 0,
    next: null,
    previous: null,
    results: [],
    rollup: { plans: 0, rate_schedules: rows.length, charge_codes: 0, effective_from: null },
  });
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  const state = {
    q: "",
    sort: CONFIG.defaultSort.sort,
    dir: CONFIG.defaultSort.dir,
    page: 1,
    per: 50 as const,
    filters: {},
  };
  queryClient.setQueryData(
    queryKeys.rateSchedules(serializeTableParams(state, CONFIG).toString()),
    schedules(rows),
  );
  const page = <PlansRatesPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/plans-rates/rates"]}>
          <Routes>
            <Route path="/plans-rates" element={page} />
            <Route path="/plans-rates/:tab" element={page} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-441 — the rate schedules TABLE (r10 line 764)", () => {
  it("draws a <table>, not a card grid", () => {
    const html = renderRates();
    expect(html).toContain('<table class="data-table"');
    // The card grid's own container. Its absence is what the PO asked for.
    expect(html).not.toContain("grid-cols-[repeat(auto-fill,minmax(320px,1fr))]");
  });

  it("DEF-RAT-9101 — New rate schedule sits in the page head, top-right beside History; nothing under the table", () => {
    // Supersedes DEF-RAT-8824's bottom bar (decision log 2026-10-02, B14 rule 2).
    const html = renderRates();
    const label = `>${i18n.t("rating.rates.new")}<`;
    const head = html.slice(html.indexOf('class="page-header-actions"'), html.indexOf("data-page-header-tabs"));
    expect(head).toContain(label);
    expect(head).toContain(`>${i18n.t("rating.tab.history")}<`);
    expect(html).not.toContain("data-rs-actions");
    expect(html.slice(html.indexOf("</table>"))).not.toContain(label);
  });

  it("carries the drawing's ELEVEN headers, in the drawing's order (CR-157-BRC10 B)", () => {
    // Scoped to the <thead>, because "Plans" and "Status" also appear in the
    // tab strip and the explainer above it — a whole-page indexOf would find
    // those and report a passing order for a table that had none.
    const html = renderRates();
    const head = html.slice(html.indexOf("<thead>"), html.indexOf("</thead>"));
    const positions = DRAWN_HEADERS.map((header) => head.indexOf(`>${header}<`));
    for (const [index, position] of positions.entries()) {
      expect(position, `header "${DRAWN_HEADERS[index]}" is missing`).toBeGreaterThan(-1);
    }
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    // Seasons and Svc are not drawn any more.
    expect(head).not.toContain(">Seasons<");
    expect(head).not.toContain(">Svc<");
  });

  it("the seven server sorts stay sortable; the three new derived columns do not", () => {
    const sortable = CONFIG.columns.filter((column) => column.sortable === true).map((c) => c.key);
    expect(sortable).toEqual([
      "name",
      "service",
      "structure",
      "effective",
      "plans",
      "accounts",
      "status",
    ]);
    const html = renderRates();
    expect(html.split('class="table-sort"').length - 1).toBe(7);
  });

  it("every sortable header is a key the server sorts — a header cannot claim a sort the API ignores", () => {
    const sortable = CONFIG.columns
      .filter((column) => column.sortable === true)
      .map((column) => column.key);
    for (const key of sortable) {
      expect(SCHEDULE_SORTS, key).toContain(key);
    }
  });

  it("CUSTOMER CLASS · BASE CODE · SIZES reach the screen as the drawing writes them", () => {
    const html = renderRates();
    expect(html).toContain(">Every class<"); // no class on the schedule
    expect(html).toContain(">Residential<");
    expect(html).toContain(">BASE-W<");
    expect(html).toContain(">BASE-E<");
    expect(html).toContain(">5 of 5<");
    expect(html).toContain(">3 of 3<");
    expect(html).toContain("01/01/2026"); // Effective, in the TENANT's format
    expect(html).toContain("03/01/2026");
    // the service is a WORD, not the letter badge
    expect(html).toContain(">Water<");
  });

  it("a base priced as one amount is an em-dash in Sizes, never `0 of 0`", () => {
    const html = renderRates([ROWS[3]]);
    expect(html).not.toContain("0 of 0");
    expect(html).toContain("—");
  });

  it("STATUS reads In force, with Scheduled under it when a change is filed", () => {
    const html = renderRates();
    expect(html).toContain(">In force<");
    expect(html).toContain(">Scheduled<");
  });

  it("DEF-RAT-9110 — a base code and the status pill each stay on one line", () => {
    const html = renderRates();
    expect(html).toContain('<span class="whitespace-nowrap"><span>BASE-W</span></span>');
    expect(html).toMatch(/<span class="inline-flex flex-col items-start gap-1 whitespace-nowrap">/);
  });

  it("DEF-RAT-9103 — Service is a group inside + Filter; no row of service buttons", () => {
    // PO 2026-10-02: "all these should be part of filter - and sepearte button
    // should not be given". Supersedes wave B's quick chips (2.432.0).
    const html = renderRates();
    expect(html).not.toContain("data-quick-filter");
    const panel = html.slice(html.indexOf("<details"), html.indexOf("</details>"));
    expect(panel).toContain(">Service<");
    expect(panel).toContain(">Water<");
    expect(panel).toContain(">Electric<");
  });

  it("ACCOUNTS carries r10's thousands separator: 1,098 and not 1098", () => {
    const html = renderRates();
    expect(html).toContain("1,098");
    expect(html).not.toContain(">1098<");
  });

  it("the STRUCTURE helper still counts blocks and periods (used off the list)", () => {
    expect(structureText(t, ROWS[0])).toBe("Tiered · 3 blocks");
    expect(structureText(t, ROWS[1])).toBe("Time-of-use · 2 periods");
    expect(structureText(t, ROWS[2])).toBe("Seasonal · 2 blocks");
    // A model with neither count is the model alone — never "· 0 blocks".
    expect(structureText(t, ROWS[3])).toBe("Flat");
  });

  it("DEF-360: ZERO size rows is 'one rate, every size' — NOT an em-dash", () => {
    // The helper is still read by the detail and the plan card.
    expect(sizesText(t, ROWS[3])).toBe("One rate, every size");
    expect(sizesText(t, card({ size_count: 1 }))).toBe("1 size");
    expect(sizesText(t, card({ size_count: 5 }))).toBe("5 sizes");
  });

  it("SEASONS: names while they fit, a count when they do not, an em-dash when there are none", () => {
    expect(seasonsText(t, card({ season_labels: [] }))).toBeNull();
    expect(seasonsText(t, card({ season_labels: ["Summer"] }))).toBe("Summer");
    expect(seasonsText(t, card({ season_labels: ["Summer", "Winter"] }))).toBe("Summer / Winter");
    expect(seasonsText(t, card({ season_labels: ["A", "B", "C"] }))).toBe("3 seasons");
  });

  it("a ZERO count renders r10's em-dash, never the digit 0", () => {
    expect(countText(0)).toBeNull();
    expect(countText(914)).toBe("914");
    expect(countText(1098)).toBe("1,098");
    const html = renderRates([ROWS[3]]);
    expect(html).toContain("—");
    expect(html).not.toContain(">0<");
  });

  it("a DRAFT has no effective date and says what draft costs (BR-RAT-031)", () => {
    const html = renderRates([ROWS[3]]);
    expect(html).toContain("Draft");
    expect(html).toContain("not selectable in a plan until it is activated");
  });

  it("the IS-5 column chooser is present — the card grid had none", () => {
    const html = renderRates();
    expect(html).toContain(i18n.t("table.columns.open"));
    expect(html).toContain(i18n.t("table.columns.reset"));
  });

  it("row actions are ICONS with accessible names (B14 rule 15, G37)", () => {
    const html = renderRates();
    // The label travels as the accessible name, not as a red word in the cell.
    // CR-157-BRC10 B — Edit · Duplicate · Retire, in the drawn order.
    const edit = html.indexOf('aria-label="Edit"');
    const duplicate = html.indexOf('aria-label="Duplicate"');
    const retire = html.indexOf('aria-label="Retire"');
    expect(edit).toBeGreaterThan(-1);
    expect(duplicate).toBeGreaterThan(edit);
    expect(retire).toBeGreaterThan(duplicate);
    expect(html).toContain("<svg");
  });

  it("BR-RAT-031: there is no fourth status and no approve control anywhere", () => {
    const html = renderRates();
    expect(html.toLowerCase()).not.toContain("approve");
    expect(html.toLowerCase()).not.toContain("pending approval");
  });
});

describe("DEF-RAT-8840 — the Rate schedules tab carries no explainer (01-list-all.png)", () => {
  it("draws none, as Charge codes, and its retired key is in no catalogue", async () => {
    const { RATING_TABS } = await import("./ratingShared");
    const rates = RATING_TABS.find((tab) => tab.id === "rates");
    expect(rates?.explainerKey).toBeUndefined();
    expect(i18n.exists("rating.explainer.rates")).toBe(false);
  });
});
