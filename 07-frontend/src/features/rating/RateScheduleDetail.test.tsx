// ── Trace ──────────────────────────────────────────────
// Story:    RAT-02 — the rate schedule DETAIL screen (CR-013 P3, screen
//           inventory §18 row 5)   Screens: S11 (A1) · RAT-02 (r10)
// Change:   CR-157-BRC10 wave B — rebuilt from the 2026-10-01 drawing
//           (05-prototype/rate-schedules-2026-10-01/images/08–39); each case
//           below names the image it was written from.
// Rules:    BR-RAT-088 (the CHARGE CODE owns the base; the matrix shows it
//           read-only and its EDIT MODE DOES NOT INCLUDE IT) · BR-RAT-031
//           (status is DERIVED; a dateless version IS the draft) ·
//           BR-RAT-032/033 (stored rows, verbatim) · BR-SHL-025 (RBAC) ·
//           BR-SHL-044 (one page header, exactly one primary)
// ───────────────────────────────────────────────────────
// Two things this suite exists to hold still.
//
// **BR-RAT-088 has to be checkable, not commented.** The base column is
// read-only and an edit mode may not offer it; §A3 prices getting that wrong at
// $23,069.50 a month across 1,247 connections, *"and no test catches it,
// because both rows are individually correct."* `editableMatrixColumns()` is
// the shape the rule takes in code, and it is asserted here.
//
// **Every absence has to STAY a stated absence.** Five facts r10 draws are not
// served (per-size rows, revenue by schedule, the authored change sentence, the
// submitter, a worked bill). The failure mode is not a blank screen — it is a
// future lane filling one of them with a plausible zero, a dash, or a uuid. So
// the assertions are that the REASON is on screen, and that the two forbidden
// renderings never are: no `0` where a count is unknown, no raw uuid at a
// person.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  MyPermissions,
  ScheduleDetail,
  TenantServiceRow,
  TierRow,
  VersionRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import type { ScheduleCardExtras, SchedulePlanRow, ScheduleRates } from "@/api/rateScheduleReads";
import { ToastProvider } from "@/components/Toast";

import {
  MATRIX_COLUMNS,
  RATE_DETAIL_TABS,
  RateScheduleDetail,
  editableMatrixColumns,
  rateDetailTabFromParam,
  versionLabel,
  versionLines,
  versionOrdinal,
  versionState,
  correctionRowReason,
  auditChangeText,
  inForceVersionId,
} from "./RateScheduleDetail";
import type { Translator } from "./ratingShared";

const t: Translator = (key, params) => i18n.t(key, params);

/**
 * A catalog string AS IT APPEARS IN MARKUP.
 *
 * ⚠ WITHOUT THIS, EVERY EXPECTATION CARRYING AN APOSTROPHE OR AN `&` FAILS ON A
 * CORRECT SCREEN — and, worse, a lane that "fixed" it by rewording the copy
 * would be changing the product to suit its test. React escapes on the way out,
 * so `Plans & Rates` is `Plans &amp; Rates` and `doesn't` is `doesn&#x27;t`.
 * The assertion is about what a person READS, so the escaping is applied to the
 * expectation rather than stripped from the subject (stripping would also
 * decode `&lt;`, and `not.toContain("<input")` below depends on it not being).
 */
function shown(key: string, params?: Record<string, unknown>): string {
  return t(key, params)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";
const TARIFF_ID = "t-water";

// The r10 water schedule, `07-r10-plans-rates-readout.md` §4 — its tier prices
// verbatim, because a test's own expected value is legitimately a literal.
const TIERS: TierRow[] = [
  { seq: 1, season: null, size_class: null, from_qty: "0", to_qty: "4", from_qty_display: "0 kgal", to_qty_display: "4 kgal", unit_price: "3.200000" },
  { seq: 2, season: null, size_class: null, from_qty: "4", to_qty: "10", from_qty_display: "4 kgal", to_qty_display: "10 kgal", unit_price: "4.800000" },
  { seq: 3, season: null, size_class: null, from_qty: "10", to_qty: null, from_qty_display: "10 kgal", to_qty_display: null, unit_price: "7.200000" },
];

const V1: VersionRow = {
  id: "v-1",
  // DEF-RAT-5715 — BR-RAT-104's chain. The server sends all four on every
  // version row; a plain (uncorrected) version reads null for each.
  corrects: null,
  superseded_by: null,
  correction_reason: null,
  corrected_by: null,
  model: "tiered",
  uom: "kgal",
  currency: "USD",
  base_charge: "11.000000",
  minimum_bill: "17.000000",
  base_charge_display: "11.00",
  minimum_bill_display: "17.00",
  size_rows: [],
  effective_from: "2025-01-01",
  effective_to: "2025-12-31",
  // DEF-367 — `{id, name}`, not a bare uuid. A uuid at a person is DEF-206.
  approved_by: { id: "5f4d3c2b-1a09-4e8d-9c7b-6a5f4e3d2c1b", name: "M. Torres" },
  regulator_ref: "PUC #W-2024-0912",
  submitted_by: null, // DEF-367 — no filer recorded on this fixture
  version_label: null, // DEF-369 — falls back to the derived ordinal
  change_reason: null, // DEF-280 — no authored change note
  filing_authority: null,
  filed_on: null,
  regulator_approved_on: null,
  regulator_approver: null,
  notify_customers: false,
  publish_public: false,
  structure: { model: "tiered", unit: "kgal", currency: "USD", tiers: TIERS },
};

const V2: VersionRow = {
  ...V1,
  id: "v-2",
  base_charge: "12.000000",
  base_charge_display: "12.00",
  minimum_bill: "18.000000",
  minimum_bill_display: "18.00",
  effective_from: "2026-01-01",
  effective_to: null,
  regulator_ref: "PUC #W-2025-1184",
  submitted_by: null, // DEF-367 — no filer recorded on this fixture
  version_label: null, // DEF-369 — falls back to the derived ordinal
  change_reason: null, // DEF-280 — no authored change note
};

/** BR-RAT-031: a NULL `effective_from` is THE draft — never history. */
const DRAFT: VersionRow = {
  ...V1,
  id: "v-draft",
  effective_from: null,
  effective_to: null,
  regulator_ref: "2027 filing (pending)",
  submitted_by: null, // DEF-367 — no filer recorded on this fixture
  version_label: null, // DEF-369 — falls back to the derived ordinal
  change_reason: null, // DEF-280 — no authored change note
};

function detail(
  overrides: Partial<ScheduleDetail & ScheduleCardExtras> = {},
): ScheduleDetail & ScheduleCardExtras {
  return {
    id: TARIFF_ID,
    name: "Residential water",
    service: "water",
    service_name: "Water",
    account_type_id: null,
    structure: "tiered",
    status: "active",
    scheduled_change: null,
    current_version: V2,
    draft_version: null,
    used_by_plans: 2,
    applied_to_accounts: 914,
    // DEF-441 — r10 line 764's five columns. A fixture states them
    // explicitly rather than defaulting, because "0 sizes" and
    // "no seasons" are the values the cells render differently.
    size_count: 0,
    season_labels: [],
    block_count: 0,
    window_count: 0,
    effective_from: null,
    versions: [V1, V2],
    uom_gate: {
      satisfied: true,
      reason: "match",
      schedule_uom: "kgal",
      billed_uom: "kgal",
      priced_against: "kgal",
      conversion_factor: null,
    },
    ...overrides,
  };
}

const SERVICES: TenantServiceRow[] = [
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
    // BR-BIL-067: the mapped account the schedule DISPLAYS and never owns.
    revenue_account: { id: "gl-4115", code: "4115", name: "Water revenue" },
    base_revenue_account: null,
    rate_schedules: 3,
    active_accounts: 950,
  },
];

function permissions(access: string): MyPermissions {
  return {
    role: "owner",
    role_name: "Owner",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access }],
  };
}


// ══════════════════════════════════════════════════════════════════════════
// CR-157-BRC10 wave B — THE VIEW AS THE 2026-10-01 DRAWING DRAWS IT
// (`05-prototype/rate-schedules-2026-10-01/images/08–39`). Each case names the
// image it was written from. The FIVE-tab screen these cases replace drew a
// rate matrix, a tier chart, a Billing rules tab, a Revenue band and a Sample
// bill; the adopted drawing draws none of them, so their cases went with them.
// ══════════════════════════════════════════════════════════════════════════

const RATES: ScheduleRates = {
  base_code: { id: "c-base-w", code: "BASE-W", name: "Water base" },
  sizes_priced: 2,
  sizes_total: 3,
  units_total: 1306,
  base_rows: [
    { seq: 1, size_class: "W-58", size_name: 'Water 5/8"', priced: true, amount: "8.0000", amount_display: "8.00", version: 1, effective_from: "2026-01-01", effective_to: null, minimum: "8.0000", minimum_display: "8.00", units: 829 },
    { seq: 2, size_class: "W-1", size_name: 'Water 1"', priced: true, amount: "11.5000", amount_display: "11.50", version: 2, effective_from: "2026-09-01", effective_to: null, minimum: null, minimum_display: null, units: 119 },
    { seq: 3, size_class: "W-2", size_name: 'Water 2"', priced: false, amount: null, amount_display: null, version: null, effective_from: null, effective_to: null, minimum: null, minimum_display: null, units: 26 },
  ],
};

const PLAN_ROWS: SchedulePlanRow[] = [
  { plan_id: "p-1", plan_name: "Residential standard", plan_code: "RES-STD", customer_classes: ["Residential"], class_differs: false, status: "published", units: 1102 },
  { plan_id: "p-2", plan_name: "Small commercial", plan_code: "COM-SM", customer_classes: ["Commercial"], class_differs: true, status: "published", units: 66 },
];

function render(options: {
  schedule?: ScheduleDetail & ScheduleCardExtras;
  access?: string;
  tab?: string;
  rates?: ScheduleRates;
  plans?: SchedulePlanRow[];
}): string {
  const schedule = options.schedule ?? detail();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(options.access ?? "Full"));
  queryClient.setQueryData(queryKeys.rateSchedule(schedule.id), schedule);
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  queryClient.setQueryData(["rate-schedules", "rates", schedule.id], options.rates ?? RATES);
  const rows = options.plans ?? PLAN_ROWS;
  queryClient.setQueryData(["rate-schedules", "plans", schedule.id, 1, 50], {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
  });
  const search = options.tab === undefined ? "" : `?tab=${options.tab}`;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[`/${TEST_TENANT}/plans-rates/rates/${schedule.id}${search}`]}
        >
          <Routes>
            <Route
              path="/:tenant/plans-rates/rates/:tariffId"
              element={
                <RateScheduleDetail timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("RAT-02 — the header (08-view-W-RES-overview.png)", () => {
  it("back link · eyebrow · title · status · In force from … · no end", () => {
    const html = render({});
    expect(html).toContain(`/${TEST_TENANT}/plans-rates/rates`);
    expect(html).toContain(shown("rating.rateDetail.back"));
    // The drawn eyebrow is FOUR parts — no customer class in it.
    expect(html).toContain("Rate schedule · Water · Tiered · v2");
    expect(html).toMatch(/<h1[^>]*>Residential water<\/h1>/);
    expect(html).toContain(shown("rating.rateDetail.effectiveFrom"));
    expect(html).toContain(shown("rating.rs.noEndLower"));
    expect(html).toContain(shown("rating.schedule.status.active"));
    // The policy sentence and the GL left the header: rule 33 (rationale is
    // zero words) and the drawing, which puts the GL in Overview's Details.
    expect(html).not.toContain(shown("rating.rateDetail.policyNote"));
  });

  it("CR-087 E1 — Duplicate · Edit · Retire, in that order, Retire in the danger tier", () => {
    const html = render({});
    // Read from the page head (DEF-RAT-9101), which comes before Overview's
    // own "Retire" field label on the page.
    const bar = html.indexOf('class="page-header-actions"');
    const at = [
      "rating.rateDetail.action.duplicate",
      "rating.rateDetail.action.edit",
      "rating.rateDetail.action.retire",
    ].map((key) => html.indexOf(`>${i18n.t(key)}<`, bar));
    for (const index of at) {
      expect(index).toBeGreaterThan(-1);
    }
    expect(at[0]).toBeLessThan(at[1]);
    expect(at[1]).toBeLessThan(at[2]);
    expect(html).toContain('data-variant="danger"');
    for (const glyph of ["✏", "🗑", "⟲", "👁"]) {
      expect(html).not.toContain(glyph);
    }
  });

  it("DEF-RAT-9101 — the three sit in the page head, top-right, on every tab; no bottom bar", () => {
    // Supersedes DEF-RAT-8824 (decision log 2026-10-02, B14 rule 2).
    for (const tab of [undefined, "rates", "plans", "audit"]) {
      const html = render({ tab });
      const head = html.slice(html.indexOf('class="page-header-actions"'), html.indexOf("data-page-header-tabs"));
      const at = ["duplicate", "edit", "retire"].map((key) =>
        head.indexOf(`>${i18n.t(`rating.rateDetail.action.${key}`)}<`),
      );
      expect(at[0]).toBeGreaterThan(-1);
      expect(at[0]).toBeLessThan(at[1]);
      expect(at[1]).toBeLessThan(at[2]);
      expect(head).toContain('data-variant="danger"');
      expect(html).not.toContain("data-rs-actions");
    }
  });

  it("DEF-370 · BR-SHL-025: Duplicate is live, and View-only disables every write WITH its reason", () => {
    expect(render({})).not.toMatch(/<button[^>]*disabled=""[^>]*>Duplicate<\/button>/);
    const viewOnly = render({ access: "View" });
    expect(viewOnly).toMatch(/<button[^>]*disabled=""[^>]*>Duplicate<\/button>/);
    expect(viewOnly).toContain(shown("rating.readOnlyReason"));
  });

  it("BR-SHL-003: a role with — on plans_rates never sees the surface", () => {
    const html = render({ access: "—" });
    expect(html).toContain(shown("rating.denied"));
    expect(html).not.toContain("Residential water");
  });

  it("a filed change draws the band — Change scheduled. New prices start …", () => {
    const later: VersionRow = { ...V2, id: "v-3", effective_from: "2027-01-01", effective_to: null };
    const html = render({
      schedule: detail({
        scheduled_change: "2027-01-01",
        current_version: { ...V2, effective_to: "2026-12-31" },
        versions: [V1, { ...V2, effective_to: "2026-12-31" }, later],
      }),
    });
    expect(html).toContain("data-scheduled-change");
    expect(html).toContain(shown("rating.rs.changeScheduled"));
    expect(html).toContain("01/01/2027");
    // …and no band when nothing is filed.
    expect(render({})).not.toContain("data-scheduled-change");
  });
});

describe("DEF-RAT-8004 — the Versions overlap band", () => {
  it("names each overlapping version, winner first, and the one bills use", () => {
    const html = render({
      schedule: detail({
        versions_overlap: [
          {
            on: "2026-09-01",
            versions: [
              { label: "Rate case 2026", effective_from: "2026-09-01", effective_to: null },
              { label: null, effective_from: "2026-08-01", effective_to: null },
            ],
          },
        ],
      }),
    });
    expect(html).toContain("data-versions-overlap");
    expect(html).toContain(shown("rating.rateDetail.overlap.title"));
    expect(html).toContain(
      t("rating.rateDetail.overlap.body", { versions: "Rate case 2026, 08/01/2026", used: "Rate case 2026" }),
    );
    // above the tab strip, with the other schedule-wide facts
    expect(html.indexOf("data-versions-overlap")).toBeLessThan(html.indexOf("data-page-header-tabs"));
  });

  it("draws nothing when no versions overlap", () => {
    expect(render({ schedule: detail({ versions_overlap: [] }) })).not.toContain("data-versions-overlap");
    expect(render({})).not.toContain(shown("rating.rateDetail.overlap.title"));
  });
});

describe("RAT-02 — the four drawn tiles", () => {
  it("IN FORCE · UNITS · SIZES PRICED · NEXT CHANGE, in that order", () => {
    const html = render({});
    const at = [
      "rating.rateDetail.kpi.inForce",
      "rating.rateDetail.kpi.units",
      "rating.rs.kpi.sizesPriced",
      "rating.rateDetail.kpi.nextChange",
    ].map((key) => html.indexOf(shown(key)));
    for (const index of at) {
      expect(index).toBeGreaterThan(-1);
    }
    expect(at).toEqual([...at].sort((a, b) => a - b));
    // The Revenue absence band is gone with the drawing that drew it.
    expect(html).not.toContain(shown("rating.rateDetail.kpi.revenue"));
  });

  it("the band and the tiles sit ABOVE the tab strip, as `08` draws them", () => {
    const html = render({ schedule: detail({ scheduled_change: "2027-01-01" }) });
    const strip = html.indexOf("data-page-header-tabs");
    expect(strip).toBeGreaterThan(-1);
    expect(html.indexOf("data-scheduled-change")).toBeGreaterThan(-1);
    expect(html.indexOf("data-scheduled-change")).toBeLessThan(strip);
    const tile = html.indexOf(shown("rating.rs.kpi.sizesPriced"));
    expect(tile).toBeGreaterThan(-1);
    expect(tile).toBeLessThan(strip);
  });

  it("UNITS carries the separator and the plan count beneath it", () => {
    const html = render({ schedule: detail({ applied_to_accounts: 1306, used_by_plans: 3 }) });
    expect(html).toContain("1,306");
    expect(html).toContain(shown("rating.rs.kpi.onPlans", { count: 3 }));
  });

  it("SIZES PRICED reads `n of m`, and a base priced once reads One amount", () => {
    expect(render({ schedule: detail({ sizes_priced: 5, sizes_total: 5 }) })).toContain(">5 of 5<");
    expect(render({ schedule: detail({ sizes_priced: 0, sizes_total: 0 }) })).toContain(
      shown("rating.rs.oneAmount"),
    );
  });

  it("NEXT CHANGE names the version and its date — `v3 · 01/01/2027`", () => {
    const ended = { ...V2, effective_to: "2026-12-31" };
    const later: VersionRow = { ...V2, id: "v-3", effective_from: "2027-01-01", effective_to: null };
    const html = render({
      schedule: detail({ scheduled_change: "2027-01-01", current_version: ended, versions: [V1, ended, later] }),
    });
    expect(html).toMatch(/v3 · <\/span>.*01\/01\/2027/);
    expect(render({})).toContain(shown("rating.rs.none"));
  });
});

describe("RAT-02 — FOUR tabs (decision log 2026-10-01)", () => {
  it("Overview · Rates · Plans · Audit, in that order, and nothing else", () => {
    expect([...RATE_DETAIL_TABS]).toEqual(["overview", "rates", "plans", "audit"]);
    const html = render({});
    const labels = RATE_DETAIL_TABS.map((id) => html.indexOf(`>${i18n.t(`rating.rs.tab.${id}`)}<`));
    expect(labels.every((index) => index > -1)).toBe(true);
    expect(labels).toEqual([...labels].sort((a, b) => a - b));
    expect(html).not.toContain(">Rate matrix<");
    expect(html).not.toContain(">Billing rules</button>");
  });

  it("BR-SHL-011: an unknown tab falls back to Overview; the old addresses still land", () => {
    expect(rateDetailTabFromParam(null)).toBe("overview");
    expect(rateDetailTabFromParam("nonsense")).toBe("overview");
    expect(rateDetailTabFromParam("matrix")).toBe("rates");
    expect(rateDetailTabFromParam("versions")).toBe("audit");
    expect(rateDetailTabFromParam("billing-rules")).toBe("overview");
  });
});

describe("RAT-02 — Overview (08-view-W-RES-overview.png)", () => {
  it("Details as label-over-value, in the drawn order", () => {
    const html = render({
      schedule: detail({ customer_class_name: "Residential", base_code: "BASE-W" }),
    });
    const block = html.slice(html.indexOf('data-facts="rs-details"'));
    const order = [
      "rating.rates.col.structure",
      "rating.rs.col.service",
      "rating.rs.col.customerClass",
      "rating.rs.fact.unit",
      "rating.rs.fact.baseChargeCode",
      "rating.rs.col.minimum",
      "rating.rs.fact.glAccount",
      "rating.rs.fact.currency",
      "rating.rs.fact.effectiveFrom",
      "rating.rs.fact.effectiveTo",
      "rating.rs.fact.regulatorRef",
    ].map((key) => block.indexOf(`>${shown(key)}<`));
    expect(order.every((index) => index > -1)).toBe(true);
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(block).toContain(">Residential<");
    expect(block).toContain(">BASE-W<");
    expect(block).toContain("4115 — Water revenue");
    expect(block).toContain(shown("rating.rs.noEnd"));
  });

  it("the MINIMUM is per size (PO 2026-10-01, option A) — never a per-version figure", () => {
    const html = render({});
    expect(html).toContain(shown("rating.rs.minimum.perSize"));
    // V2 still STORES a version minimum of 18.00; the screen must not show it.
    expect(html).not.toContain("$18.00");
  });

  it("Billing rules are five facts", () => {
    const html = render({});
    const block = html.slice(html.indexOf('data-facts="rs-billing-rules"'));
    for (const id of ["partMonth", "rounding", "priceChange", "mistake", "retire"]) {
      expect(block).toContain(shown(`rating.rs.rule.${id}Value`));
    }
  });

  it("a schedule with no class says Every class, and no id reaches the page", () => {
    const html = render({ schedule: detail({ account_type_id: "at-res", customer_class_name: null }) });
    expect(html).toContain(shown("rating.rs.everyClass"));
    expect(html).not.toContain("at-res");
  });
});

describe("RAT-02 — Rates (09-view-W-RES-rates.png · 33-view-TRASH-rates.png)", () => {
  it("Base charges: # · Size · Base charge · Minimum · Units · Version · From · To", () => {
    const html = render({ tab: "rates" });
    const table = html.slice(html.indexOf("data-base-table"), html.indexOf("</table>", html.indexOf("data-base-table")));
    const heads = [
      "#",
      shown("rating.tier.size"),
      shown("rating.rs.col.baseCharge"),
      shown("rating.rs.col.minimum"),
      shown("rating.plans.col.units"),
      shown("rating.rateDetail.versions.col.version"),
      shown("rating.rs.col.from"),
      shown("rating.rs.col.to"),
    ].map((label) => table.indexOf(`>${label}</th>`));
    expect(heads.every((index) => index > -1)).toBe(true);
    expect(heads).toEqual([...heads].sort((a, b) => a - b));
  });

  it("each size carries its own base price, version and dates — v1 and v2 side by side", () => {
    const html = render({ tab: "rates" });
    expect(html).toContain("$8.00");
    expect(html).toContain("$11.50");
    expect(html).toContain(">v1<");
    expect(html).toContain(">v2<");
    expect(html).toContain("09/01/2026");
    expect(html).toContain(shown("rating.rs.noEnd"));
    expect(html).toContain("829");
  });

  it("a size reads 5/8\" — the schedule already names the service (09)", () => {
    const html = render({ tab: "rates" });
    const table = html.slice(html.indexOf("data-base-table"), html.indexOf("</table>", html.indexOf("data-base-table")));
    expect(table).toContain("5/8&quot;");
    expect(table).not.toContain("Water 5/8");
  });

  it("a size the code does not price says Not priced — never $0.00", () => {
    const html = render({ tab: "rates" });
    expect(html).toContain(shown("rating.rs.notPriced"));
    expect(html).not.toContain("$0.00");
  });

  it("a blank per-size minimum reads No minimum", () => {
    const html = render({ tab: "rates" });
    expect(html).toContain(shown("rating.rs.noMinimum"));
  });

  it("From BASE-W is a link to that charge code's View details", () => {
    const html = render({ tab: "rates" });
    const at = html.indexOf("data-base-code-link");
    const link = html.slice(html.lastIndexOf("<a", at), html.indexOf("</a>", at));
    expect(link).toContain(`href="/${TEST_TENANT}/plans-rates/charge-codes/c-base-w"`);
    expect(html).toContain("BASE-W ↗");
  });

  it("Usage charges names the method and draws its table, with no version strip", () => {
    const html = render({ tab: "rates" });
    expect(html).toContain(shown("rating.rs.methodIs", { method: "Tiered" }));
    expect(html).toContain('data-usage-table="tiered"');
    expect(html).toContain(">$4.80<");
    expect(html).toContain(shown("rating.tier.openEnded"));
  });
});

describe("RAT-02 — Plans (10-view-W-RES-plans.png)", () => {
  it("Plan · Code · Customer class · Status · Units, with Class differs", () => {
    const html = render({ tab: "plans" });
    expect(html).toContain("Residential standard");
    expect(html).toContain("COM-SM");
    expect(html).toContain(shown("rating.rs.plans.classDiffers"));
    expect(html).toContain("1,102");
    expect(html.split(shown("rating.rs.plans.classDiffers")).length - 1).toBe(1);
  });

  it("says so when nothing carries the schedule", () => {
    expect(render({ tab: "plans", plans: [] })).toContain(shown("rating.rs.plans.empty"));
  });
});

describe("RAT-02 — Audit (11-view-W-RES-audit.png · 15-view-SEWER-audit.png)", () => {
  it("Version · Effective from · Effective to · Filed as · What changed · By · Status", () => {
    const html = render({ tab: "audit" });
    const panel = html.slice(html.indexOf('data-rs-tab="audit"'));
    const heads = [
      "rating.rateDetail.versions.col.version",
      "rating.rs.fact.effectiveFrom",
      "rating.rs.fact.effectiveTo",
      "rating.rateDetail.versions.col.filedAs",
      "rating.rateDetail.versions.col.change",
      "rating.rateDetail.versions.col.by",
      "rating.rateDetail.versions.col.status",
    ].map((key) => panel.indexOf(`>${shown(key)}</th>`));
    expect(heads.every((index) => index > -1)).toBe(true);
    expect(heads).toEqual([...heads].sort((a, b) => a - b));
  });

  it("newest first; the first version with no note reads Created; Filed as is the docket", () => {
    const html = render({ tab: "audit" });
    expect(html.indexOf("PUC #W-2025-1184")).toBeLessThan(html.indexOf("PUC #W-2024-0912"));
    expect(html).toContain(shown("rating.rs.audit.created"));
    expect(html).toContain(shown("rating.rs.audit.status.active"));
    expect(html).toContain(shown("rating.rs.audit.status.superseded"));
  });
});

describe("DEF-367 / DEF-369 — the filing record on the Audit tab", () => {
  const filed: VersionRow = {
    ...V2,
    version_label: "2027-A",
    change_reason: "TWDB pass-through, 4.5% on volumetric blocks",
    submitted_by: { id: "u-alex", name: "Alex Reed" },
  };

  it("DEF-369: a FILED label wins over the position this screen counts", () => {
    const [line] = versionLines(detail({ current_version: filed, versions: [filed] }));
    expect(versionLabel(line)).toEqual({ text: "2027-A", derived: false });
    const [plain] = versionLines(detail());
    expect(versionLabel(plain)).toEqual({ text: null, derived: true });
  });

  it("the BY and WHAT CHANGED cells are filled, and no uuid is shown", () => {
    const html = render({ tab: "audit", schedule: detail({ current_version: filed, versions: [filed] }) });
    expect(html).toContain("Alex Reed");
    expect(html).toContain("TWDB pass-through, 4.5% on volumetric blocks");
    expect(html).toContain("2027-A");
    expect(html).not.toContain("u-alex");
    expect(html).not.toContain("5f4d3c2b-1a09-4e8d-9c7b-6a5f4e3d2c1b");
  });

  it("DEF-368: an active schedule's saved DRAFT is listed, above the one in force", () => {
    const lines = versionLines(detail({ current_version: V2, draft_version: DRAFT, versions: [V1, V2] }));
    expect(lines[0].version.id).toBe("v-draft");
    expect(lines[0].state).toBe("draft");
    expect(lines[1].state).toBe("active");
  });
});

// `DEF-RAT-5827` / `BR-RAT-1044` — a correction is visible on the schedule's own
// Audit tab: the corrected row reads CORRECTED (never Scheduled), the
// correction row prints its own reason (`15-view-SEWER-audit.png`: *Fixes v1:
// $6.2500* / *Corrected*).
const CORRECTED: VersionRow = { ...V2, id: "v-2", superseded_by: "v-fix", change_reason: "2026 general rate case" };
const CORRECTION: VersionRow = {
  ...V2,
  id: "v-fix",
  corrects: "v-2",
  superseded_by: null,
  change_reason: "2026 general rate case",
  correction_reason: "The 0.1150 was keyed from the wrong sheet",
  corrected_by: { id: "u-dana", name: "Dana Whitfield" },
};
const CORRECTED_DETAIL = (): ScheduleDetail =>
  detail({ current_version: CORRECTION, versions: [V1, CORRECTED, CORRECTION] });

describe("DEF-RAT-5827 — a correction is visible on the Audit tab", () => {
  it("the corrected row is CORRECTED, never Scheduled — with or without its stamped end", () => {
    expect(versionState(CORRECTED, "v-fix")).toBe("corrected");
    expect(versionState({ ...CORRECTED, effective_to: "2026-03-01" }, "v-fix")).toBe("corrected");
    expect(versionState(CORRECTION, "v-fix")).toBe("active");
    const html = render({ schedule: CORRECTED_DETAIL(), tab: "audit" });
    expect(html).toContain(shown("rating.rs.audit.status.corrected"));
    expect(html).not.toContain(shown("rating.rs.audit.status.scheduled"));
  });

  it("the correction's OWN reason is what the correction row shows", () => {
    expect(correctionRowReason(CORRECTION)).toBe("The 0.1150 was keyed from the wrong sheet");
    expect(correctionRowReason(CORRECTED)).toBe("2026 general rate case");
    const html = render({ schedule: CORRECTED_DETAIL(), tab: "audit" });
    expect(html).toContain("The 0.1150 was keyed from the wrong sheet");
    expect(html).not.toContain("v-fix");
  });
});

describe("DEF-RAT-8829 — one numbering: a version's position, a correction included", () => {
  // The walk's shape as the server serves it: October's v1, its correction,
  // then a November change (`15-view-SEWER-audit.png` draws a correction as a
  // version of its own — `v2 · Fixes v1`).
  const OCT: VersionRow = { ...V1, id: "v-oct", effective_from: "2026-10-01", effective_to: "2026-10-31", superseded_by: "v-oct-fix" };
  const OCT_FIX: VersionRow = { ...OCT, id: "v-oct-fix", corrects: "v-oct", superseded_by: null, correction_reason: "Typed 4.4096 for 4.0496" };
  const NOV: VersionRow = { ...V1, id: "v-nov", effective_from: "2026-11-01", effective_to: null };

  it("the surfaces and the wizard read the same number for the same row", () => {
    const versions = [OCT, OCT_FIX, NOV];
    const lines = versionLines(detail({ current_version: OCT_FIX, versions }));
    expect(lines.map((line) => [line.version.id, line.ordinal])).toEqual([
      ["v-nov", 3],
      ["v-oct-fix", 2],
      ["v-oct", 1],
    ]);
    expect(versions.map((row) => versionOrdinal(versions, row.id))).toEqual([1, 2, 3]);
    expect(versionOrdinal(versions, "v-missing")).toBeNull();
  });
});

describe("DEF-RAT-9003 — a version's number never changes once shown", () => {
  // Saved in this order: October v1, November v2 (announced as v2), then a
  // correction of October. The server serves them by date; the numbers follow
  // the order they were SAVED.
  const OCT: VersionRow = { ...V1, id: "v-oct", effective_from: "2026-10-01", effective_to: "2026-10-31", superseded_by: "v-fix", created_at: "2026-10-01T09:00:00Z" };
  const NOV: VersionRow = { ...V1, id: "v-nov", effective_from: "2026-11-01", effective_to: null, created_at: "2026-10-01T10:00:00Z", change_reason: "Board approved" };
  const FIX: VersionRow = { ...OCT, id: "v-fix", corrects: "v-oct", superseded_by: null, correction_reason: "Typed 4.4096 for 4.0496", created_at: "2026-10-01T11:00:00Z" };

  it("keeps November as v2; the correction is v3 and says it fixes v1", () => {
    const served = [OCT, FIX, NOV];
    const lines = versionLines(detail({ current_version: FIX, versions: served }));
    expect(lines.map((line) => [line.version.id, line.ordinal])).toEqual([
      ["v-nov", 2],
      ["v-fix", 3],
      ["v-oct", 1],
    ]);
    expect(versionOrdinal(served, "v-nov")).toBe(2);
    const fix = lines.find((line) => line.version.id === "v-fix")!;
    expect(auditChangeText(t, fix, lines)).toBe(
      i18n.t("rating.rs.audit.fixes", { n: 1, reason: "Typed 4.4096 for 4.0496" }),
    );
  });
});

describe("DEF-RAT-5831 — nothing in force means nothing is named as in force", () => {
  const FUTURE: VersionRow = { ...V2, id: "v-future", effective_from: "2027-03-01", effective_to: null };
  const futureFiled = (): ScheduleDetail =>
    detail({ status: "draft", scheduled_change: "2027-03-01", current_version: FUTURE, versions: [FUTURE] });

  it("the fallback version is NOT treated as the one in force", () => {
    expect(inForceVersionId(futureFiled())).toBeNull();
    expect(inForceVersionId(detail())).toBe("v-2");
    expect(inForceVersionId(detail({ status: "archived" }))).toBe("v-2");
  });

  it("the future row reads Scheduled; the IN FORCE tile says nothing is; the eyebrow says Draft", () => {
    expect(versionLines(futureFiled()).map((line) => line.state)).toEqual(["scheduled"]);
    const html = render({ schedule: futureFiled() });
    expect(html).toContain(shown("rating.rateDetail.kpi.inForceNone"));
    expect(html).toContain(shown("rating.rateDetail.kicker.draft"));
    expect(html).toContain(shown("rating.rateDetail.noVersion"));
    // Scoped to the Audit panel: the IN FORCE tile's own LABEL is the same word.
    const page = render({ schedule: futureFiled(), tab: "audit" });
    const audit = page.slice(page.indexOf('data-rs-tab="audit"'));
    expect(audit).toContain(shown("rating.rs.audit.status.scheduled"));
    expect(audit).not.toContain(shown("rating.rs.audit.status.active"));
  });
});

describe("BR-RAT-088 — the matrix columns the wizard still reads", () => {
  it("the base column is NOT editable, so an edit mode cannot offer it", () => {
    expect(MATRIX_COLUMNS.find((column) => column.key === "base")?.editable).toBe(false);
    expect(editableMatrixColumns().map((column) => column.key)).not.toContain("base");
  });
});

// ── DEF-RAT-8846 · DEF-RAT-8833 (charge-code walk 33, 2026-10-01) ─────────────
// Red first (law 7): on the tip before the fix the tile read None over a base
// price scheduled for 11/01, and the Rates tab drew only the first base code.
describe("DEF-RAT-8846 · a base price scheduled on the code shows as the Next change", () => {
  it("reads $9.00 from 11/01/2026 instead of None when no version change is scheduled", () => {
    const html = render({
      rates: {
        ...RATES,
        base_next_change: {
          code: "BASE-W",
          customer_class: null,
          size_name: 'Water 5/8"',
          amount: "9.0000",
          amount_display: "9.00",
          effective_from: "2026-11-01",
        },
      },
    });
    expect(html).toContain("data-next-base-price");
    expect(html).toContain("$9.00");
    expect(html).toContain("11/01/2026");
  });

  it("still reads None when nothing is scheduled", () => {
    expect(render({})).not.toContain("data-next-base-price");
  });
});

// DEF-RAT-9011 — red first: the tile drew "$181.00 from 11/01/2026" as ONE value,
// which wrapped and cut the date at 1440, and never said whose price it was.
describe("DEF-RAT-9011 · the Next change tile: the amount as its value, the date below", () => {
  const NEXT = {
    code: "BASE-E-IND",
    customer_class: "industrial",
    size_name: null,
    amount: "181.0000",
    amount_display: "181.00",
    effective_from: "2026-11-01",
  };
  const fromLine = (html: string): string => {
    const at = html.indexOf("data-next-base-from");
    return at < 0 ? "" : html.slice(at, html.indexOf("</div>", at));
  };

  it("the value is the amount alone; the detail reads from 11/01/2026", () => {
    const html = render({ rates: { ...RATES, base_next_change: NEXT } });
    expect(html).toMatch(/data-next-base-price="">\$181\.00</);
    expect(fromLine(html)).toContain("11/01/2026");
    expect(fromLine(html)).toContain(shown("rating.rs.kpi.from"));
    expect(fromLine(html)).not.toContain("BASE-E-IND");
  });

  it("names the code when the schedule shows more than one base code", () => {
    const html = render({
      rates: {
        ...RATES,
        base_next_change: NEXT,
        base_codes: [
          { id: "c-ind", code: "BASE-E-IND", name: "Electric base — industrial", customer_class: "industrial" },
          { id: "c-com", code: "NB-E-COM", name: "Electric base — commercial", customer_class: "commercial" },
        ],
      },
    });
    expect(fromLine(html)).toContain("BASE-E-IND");
  });
});

describe("DEF-RAT-8833 · a schedule naming no class shows every class's base code", () => {
  it("one row per class, each naming its class and code, and every code linked", () => {
    const html = render({
      tab: "rates",
      rates: {
        ...RATES,
        base_code: { id: "c-base-e", code: "BASE-E", name: "Electric base" },
        base_codes: [
          { id: "c-base-e", code: "BASE-E", name: "Electric base", customer_class: "residential" },
          { id: "c-base-e-ind", code: "BASE-E-IND", name: "Electric base — industrial", customer_class: "industrial" },
        ],
        base_rows: [
          { ...RATES.base_rows[0], seq: 1, size_class: null, size_name: null, amount: "12.0000", amount_display: "12.00", code: "BASE-E", customer_class: "residential" },
          { ...RATES.base_rows[0], seq: 2, size_class: null, size_name: null, amount: "180.0000", amount_display: "180.00", code: "BASE-E-IND", customer_class: "industrial" },
        ],
      },
    });
    expect(html).toContain("data-base-row-class");
    expect(html).toContain("BASE-E-IND");
    expect(html).toContain("$180.00");
    expect(html).toContain('data-base-code-link="BASE-E-IND"');
  });
});

describe("DEF-RAT-9117 · one word for a schedule in force", () => {
  it("the details header reads the list's In force, in every catalogue", () => {
    const html = render({});
    const head = html.slice(0, html.indexOf("data-page-header-tabs"));
    expect(head).toContain(`>${i18n.t("rating.rs.status.inForce")}<`);
    for (const lng of Object.keys(i18n.options.resources ?? {})) {
      expect(i18n.getFixedT(lng)("rating.schedule.status.active")).toBe(i18n.getFixedT(lng)("rating.rs.status.inForce"));
    }
  });
});

describe("DEF-RAT-9102 · Base charges From is the date the price is in force ON THIS SCHEDULE", () => {
  // PO 2026-10-02: "in rate schedule form date is not displayed" — every row of
  // a backfilled base code read From "—". The schedule's version (V2) starts
  // 2026-01-01, so From is the LATER of the price's own start and that.
  const rowHtml = (html: string, size: string): string => {
    const at = html.indexOf(`data-base-row="${size}"`);
    return html.slice(at, html.indexOf("</tr>", at));
  };
  it("a backfilled price (served null) and an earlier price read the version's start; a later price reads its own", () => {
    const html = render({
      tab: "rates",
      rates: {
        ...RATES,
        base_rows: [
          { ...RATES.base_rows[0], size_class: "W-58", effective_from: null },
          { ...RATES.base_rows[1], size_class: "W-1", effective_from: "2025-06-01" },
          { ...RATES.base_rows[0], seq: 3, size_class: "W-2", size_name: 'Water 2"', effective_from: "2026-11-01" },
        ],
      },
    });
    expect(rowHtml(html, "W-58")).toContain("01/01/2026");
    expect(rowHtml(html, "W-1")).toContain("01/01/2026");
    expect(rowHtml(html, "W-1")).not.toContain("06/01/2025");
    expect(rowHtml(html, "W-2")).toContain("11/01/2026");
    expect(html).not.toContain("01/01/2000");
  });
  it("a size the code does not price still reads no date — none exists", () => {
    const html = render({ tab: "rates" });
    expect(rowHtml(html, "W-2")).toContain("<td");
    expect(rowHtml(html, "W-2")).not.toContain("01/01/2026");
  });
});
