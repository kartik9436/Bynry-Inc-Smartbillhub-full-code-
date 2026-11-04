// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-RAT-10148 (a seasonal schedule reopened on Edit showed every
//          season's price blank on step 2 and on Review) · DEF-RAT-10149
//          (Effective from empty on Review when editing a live schedule)
// Ruling:  decision log 2026-10-14, "RATE SCHEDULE EDIT: "EFFECTIVE FROM" IS
//          PREFILLED WITH THE FIRST DAY OF NEXT MONTH; SEASONAL PRICES COME
//          BACK ON EDIT" (PO "go A")
// Screen:  S11 — RAT-03 Edit, mounted under its real route pattern
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
 *   · prices asserted off the draft rather than the screen — step 2 reads the
 *     RENDERED price inputs and Review reads the rendered usage table;
 *   · a round trip asserted against the client's own draft — the posted
 *     `structure` is compared with a literal written from what the SERVER
 *     stores (`services._validate_structure`), never with `structurePayload`
 *     of the same draft;
 *   · "0 changes" read off the function — it is read off the rendered count;
 *   · the date read off the browser clock — the clock is pinned to an instant
 *     whose UTC day (10/15) differs from the tenant's Chicago day (10/14 at
 *     9 pm), so a browser/UTC read would still give 11/01 but a month-end
 *     instant (10/31 9 pm Chicago = 11/01 UTC) separates them; that case is
 *     the third date test.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { ChargeRow, LookupEntry, MyPermissions, ScheduleDetail, TenantServiceRow, VersionRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { RateScheduleThreeStep } from "./RateScheduleThreeStep";
import { draftFromSchedule, suggestedEffectiveFrom } from "./RateScheduleWizard";

const TENANT = "annarbor";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
} as unknown as MyPermissions;

const SERVICES = [
  { service: "solar", name: "Solar", enabled: true, primary_uom: "kW-DC", alt_uom: null, billed_uom: null },
  { service: "electric", name: "Electric", enabled: true, primary_uom: "kWh", alt_uom: null, billed_uom: null },
  { service: "water", name: "Water", enabled: true, primary_uom: "kgal", alt_uom: null, billed_uom: null },
  { service: "sewer", name: "Sewer", enabled: true, primary_uom: "kgal", alt_uom: null, billed_uom: null, billing_basis: "share" },
] as unknown as TenantServiceRow[];

const uom = (code: string, service: string | null) =>
  ({ id: code, code, name: code, active: true, is_system: true, used_by: 0, service: service === null ? null : { id: service, code: service } }) as unknown as LookupEntry;
const UOMS = [uom("kW-DC", null), uom("kWh", "electric"), uom("kgal", "water"), uom("kW", "electric")];
const SIZES = [
  { id: "W-58", code: "W-58", name: 'Water 5/8"', active: true, is_system: true, used_by: 0, service: { id: "water", code: "water" } },
  { id: "W-2", code: "W-2", name: 'Water 2"', active: true, is_system: true, used_by: 0, service: { id: "water", code: "water" } },
] as unknown as LookupEntry[];
const CLASSES = [
  { id: "at-res", code: "residential", name: "Residential", active: true, is_system: true, used_by: 0 },
] as unknown as LookupEntry[];

function base(code: string, service: string): ChargeRow {
  return {
    id: `chg-${code}`,
    code,
    name: `${code} base`,
    service,
    is_base: true,
    status: "active",
    amount: "10.000000",
    amount_display: "10.00",
    size_amounts: [],
  } as unknown as ChargeRow;
}
const CHARGES = [base("BASE-S", "solar"), base("BASE-E", "electric"), base("BASE-W", "water"), base("BASE-SW", "sewer")];

interface Stub {
  client: ApiClient;
  posts: { path: string; body: Record<string, unknown> }[];
}

function stub(detail: ScheduleDetail): Stub {
  const posts: Stub["posts"] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const saved = () => ({ ...detail, status: "active", scheduled_change: null, notices: [] }) as unknown as ScheduleDetail;
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/uoms")) return ok({ count: UOMS.length, results: UOMS });
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: SIZES.length, results: SIZES });
      if (path.startsWith("/lookups/")) return ok({ count: CLASSES.length, results: CLASSES });
      if (path === "/charges") return ok({ count: CHARGES.length, next: null, previous: null, results: CHARGES });
      if (path.startsWith("/rate-schedules/percent-basis-options")) return ok({ results: [{ code: "water", name: "Water" }] });
      if (path.startsWith("/rate-schedules/")) return ok(detail);
      throw new Error(`no stub for ${path}`);
    }),
    post: vi.fn(async (path: string, body: Record<string, unknown>) => {
      posts.push({ path, body });
      return ok(saved());
    }),
    request: vi.fn(async (path: string, options: { body: Record<string, unknown> }) => {
      posts.push({ path, body: options.body });
      return ok(saved());
    }),
  } as unknown as ApiClient;
  return { client, posts };
}

function mountEdit(s: Stub, id: string) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  qc.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/rates/${id}/edit`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/rates/:tariffId/edit"
              element={<RateScheduleThreeStep client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" displayYear={2026} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}

const continueButton = () => screen.getByRole("button", { name: t("wizard.continue") });
const fromBox = () => document.getElementById("rs-effective-from") as HTMLInputElement;

/** A version row as `selectors.version_structure` serves it: six-place strings. */
function version(over: Partial<VersionRow> & { structure: VersionRow["structure"] }): VersionRow {
  return {
    id: "v-1",
    corrects: null,
    superseded_by: null,
    correction_reason: null,
    corrected_by: null,
    model: "flat",
    uom: "kWh",
    currency: "USD",
    base_charge: null,
    base_charge_code: "chg-BASE-E",
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
    submitted_by: null,
    version_label: null,
    change_reason: "Board approved",
    regulator_ref: null,
    notify_customers: false,
    publish_public: false,
    ...over,
  } as unknown as VersionRow;
}

function live(name: string, service: string, current: VersionRow, extra: Partial<ScheduleDetail> = {}): ScheduleDetail {
  return {
    id: "t-1",
    name,
    service,
    service_name: service,
    account_type_id: null,
    structure: current.model,
    status: "active",
    scheduled_change: null,
    current_version: current,
    draft_version: null,
    used_by_plans: 1,
    applied_to_accounts: 40,
    size_count: 0,
    season_labels: [],
    block_count: 0,
    window_count: 0,
    effective_from: current.effective_from,
    versions: [current],
    uom_gate: { satisfied: true, reason: "match", schedule_uom: current.uom, billed_uom: current.uom, priced_against: current.uom, conversion_factor: null },
    current_version_issued_bills: 0,
    closing_version_effective_from: current.effective_from,
    closing_version_effective_to: null,
    ...extra,
  } as unknown as ScheduleDetail;
}

/** Ann Arbor's *Bryant Solar and Battery Service Pilot Rate*, as the server
 *  serves it: Summer 1 Apr–30 Sep, Winter 1 Oct–31 Mar, each price on a
 *  `0 → ∞` line tagged with its season's label. */
const SEASONAL = version({
  model: "seasonal",
  uom: "kW-DC",
  base_charge_code: "chg-BASE-S",
  effective_from: "2026-05-01",
  structure: {
    model: "seasonal",
    unit: "kW-DC",
    currency: "USD",
    seasons: [
      { label: "Summer", start_month: 4, start_day: 1, end_month: 9, end_day: 30 },
      { label: "Winter", start_month: 10, start_day: 1, end_month: 3, end_day: 31 },
    ],
    tiers: [
      { seq: 1, season: "Summer", size_class: null, from_qty: "0.000000", to_qty: null, unit_price: "12.500000", from_qty_display: "0 kW-DC", to_qty_display: null },
      { seq: 1, season: "Winter", size_class: null, from_qty: "0.000000", to_qty: null, unit_price: "9.750000", from_qty_display: "0 kW-DC", to_qty_display: null },
    ],
  } as unknown as VersionRow["structure"],
});
const ANN_ARBOR = live("Bryant Solar and Battery Service Pilot Rate", "solar", SEASONAL);

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** Pin the clock (Date only — timers stay real so react-query and user-event run). */
function pinClock(iso: string) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(iso));
}

async function toReview(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(document.querySelector('[data-step="details"]')).toBeInTheDocument());
  await waitFor(() => expect((document.getElementById("rs-service") as HTMLSelectElement).options.length).toBeGreaterThan(1));
  await user.click(continueButton());
  await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
  await user.click(continueButton());
  await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
}

async function createVersion(user: ReturnType<typeof userEvent.setup>, s: Stub) {
  await user.type(document.getElementById("rs-what-changed") as HTMLTextAreaElement, "Same rate, re-filed");
  await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.createVersion") }));
  await waitFor(() => expect(s.posts.length).toBe(1));
  return s.posts[0];
}

const changesCount = () =>
  document.querySelector('[data-collection="rs-changes"]')?.textContent ?? document.body.textContent ?? "";

describe("DEF-RAT-10148 — a seasonal kW-DC schedule reopens with its prices", () => {
  it("step 2 shows Summer 12.50 and Winter 9.75 in Price per kW-DC", async () => {
    const user = mountEdit(stub(ANN_ARBOR), "t-1");
    await waitFor(() => expect(document.querySelector('[data-step="details"]')).toBeInTheDocument());
    await waitFor(() => expect((document.getElementById("rs-service") as HTMLSelectElement).options.length).toBeGreaterThan(1));
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-cell="season-price-0"]')).toBeInTheDocument());
    expect((document.querySelector('[data-cell="season-price-0"]') as HTMLInputElement).value).toBe("12.5000");
    expect((document.querySelector('[data-cell="season-price-1"]') as HTMLInputElement).value).toBe("9.7500");
  });

  it("Review shows both prices, What changes reads 0, and a no-change save posts the same prices", async () => {
    const s = stub(ANN_ARBOR);
    const user = mountEdit(s, "t-1");
    await toReview(user);
    const usage = document.querySelector('[data-usage-table="seasonal"]')?.textContent ?? "";
    expect(usage).toContain("$12.50");
    expect(usage).toContain("$9.75");
    expect(changesCount()).toContain(t("rating.rs.wiz.changesCount", { count: 0 }));
    const posted = await createVersion(user, s);
    expect(posted.path).toBe("/rate-schedules/t-1/versions");
    // What the server stores for these two seasons — written out, not derived.
    expect(posted.body.structure).toEqual({
      seasons: [
        { label: "Summer", start_month: "4", start_day: "1", end_month: "9", end_day: "30", unit_price: "12.500000" },
        { label: "Winter", start_month: "10", start_day: "1", end_month: "3", end_day: "31", unit_price: "9.750000" },
      ],
    });
  });

  it("the season lines are not ALSO read as a base ladder (no double count)", () => {
    const draft = draftFromSchedule(ANN_ARBOR);
    expect(draft.seasons.map((season) => season.unit_price)).toEqual(["12.500000", "9.750000"]);
    // The default single empty row, not the two season lines.
    expect(draft.tiers.every((tier) => tier.unit_price === "")).toBe(true);
  });
});

describe("DEF-RAT-10149 — Effective from is proposed on Edit (PO 'go A', 2026-10-14)", () => {
  it("today 10/14 in the tenant's zone → 11/01/2026; Effective to stays blank", async () => {
    pinClock("2026-10-15T02:00:00Z"); // 10/14 9 pm in Chicago
    const s = stub(ANN_ARBOR);
    const user = mountEdit(s, "t-1");
    await toReview(user);
    expect(fromBox().value).toBe("2026-11-01");
    expect((document.getElementById("rs-effective-to") as HTMLInputElement).value).toBe("");
    const posted = await createVersion(user, s);
    expect(posted.body.effective_from).toBe("2026-11-01");
    expect(posted.body.effective_to).toBeNull(); // blank = open-ended (DEF-RAT-5833)
  });

  it("the current version starts 12/01 → the proposal is 12/02, so the server cannot refuse it", async () => {
    pinClock("2026-10-14T15:00:00Z");
    const future = live("Bryant Solar and Battery Service Pilot Rate", "solar", { ...SEASONAL, effective_from: "2026-12-01" } as VersionRow, {
      closing_version_effective_from: "2026-12-01",
    });
    const user = mountEdit(stub(future), "t-1");
    await toReview(user);
    expect(fromBox().value).toBe("2026-12-02");
  });

  it("the tenant's day decides, not UTC: 10/31 9 pm Chicago is 11/01 UTC and still proposes 11/01", async () => {
    pinClock("2026-11-01T02:00:00Z");
    const user = mountEdit(stub(ANN_ARBOR), "t-1");
    await toReview(user);
    expect(fromBox().value).toBe("2026-11-01");
  });

  it("a parked draft keeps the date the clerk typed", async () => {
    pinClock("2026-10-14T15:00:00Z");
    const parked = live("Bryant Solar and Battery Service Pilot Rate", "solar", SEASONAL, {
      draft_version: { ...SEASONAL, id: "v-draft", effective_from: "2027-03-15", effective_to: null } as VersionRow,
    });
    const user = mountEdit(stub(parked), "t-1");
    await toReview(user);
    expect(fromBox().value).toBe("2027-03-15");
  });

  it("the pure rule: first of next month, rolls the year, or the day after a later start", () => {
    expect(suggestedEffectiveFrom("2026-10-14", "2026-05-01")).toBe("2026-11-01");
    expect(suggestedEffectiveFrom("2026-12-31", null)).toBe("2027-01-01");
    expect(suggestedEffectiveFrom("2026-10-14", "2026-12-01")).toBe("2026-12-02");
    expect(suggestedEffectiveFrom("2026-10-14", "2026-11-01")).toBe("2026-11-02");
    expect(suggestedEffectiveFrom("", null)).toBe("");
  });
});

/**
 * Every other method, reopened on Edit and saved with NOTHING changed: the
 * posted structure must be what the server stored, price for price.
 */
const TIERS = (rows: [string, string | null, string, string | null][]) =>
  rows.map(([from_qty, to_qty, unit_price, size_class], index) => ({
    seq: index + 1,
    season: null,
    size_class,
    from_qty,
    to_qty,
    unit_price,
    from_qty_display: null,
    to_qty_display: null,
  }));

const REOPEN_CASES: { name: string; detail: ScheduleDetail; structure: Record<string, unknown> }[] = [
  {
    name: "flat",
    detail: live("Electric flat", "electric", version({
      model: "flat",
      structure: { model: "flat", unit: "kWh", currency: "USD", tiers: TIERS([["0.000000", null, "0.104200", null]]) } as unknown as VersionRow["structure"],
    })),
    structure: { unit_price: "0.104200" },
  },
  {
    name: "tiered with a 2\" size ladder",
    detail: live("Water tiered", "water", version({
      model: "tiered",
      uom: "kgal",
      base_charge_code: "chg-BASE-W",
      structure: {
        model: "tiered",
        unit: "kgal",
        currency: "USD",
        tiers: TIERS([
          ["0.000000", "5.000000", "3.200000", null],
          ["5.000000", null, "4.800000", null],
          ["0.000000", "5.000000", "3.450000", "W-2"],
          ["5.000000", null, "5.100000", "W-2"],
        ]),
      } as unknown as VersionRow["structure"],
    })),
    structure: {
      tiers: [
        { from_qty: "0.000000", to_qty: "5.000000", unit_price: "3.200000" },
        { from_qty: "5.000000", unit_price: "4.800000" },
        { from_qty: "0.000000", to_qty: "5.000000", unit_price: "3.450000", size_class: "W-2" },
        { from_qty: "5.000000", unit_price: "5.100000", size_class: "W-2" },
      ],
    },
  },
  {
    name: "time of use, windows × seasons",
    detail: live("Electric TOU", "electric", version({
      model: "time_of_use",
      structure: {
        model: "time_of_use",
        unit: "kWh",
        currency: "USD",
        seasons: [
          { label: "Summer", start_month: 6, start_day: 1, end_month: 9, end_day: 30 },
          { label: "Winter", start_month: 10, start_day: 1, end_month: 5, end_day: 31 },
        ],
        windows: [
          { label: "On-peak", season: "Summer", day_type: "weekday", start_time: "14:00", end_time: "19:00", unit_price: "0.210000", channel: "on_peak" },
          { label: "Off-peak", season: "Winter", day_type: "all", start_time: "00:00", end_time: "23:59", unit_price: "0.080000", channel: "off_peak" },
        ],
      } as unknown as VersionRow["structure"],
    })),
    structure: {
      seasons: [
        { label: "Summer", start_month: "6", start_day: "1", end_month: "9", end_day: "30" },
        { label: "Winter", start_month: "10", start_day: "1", end_month: "5", end_day: "31" },
      ],
      windows: [
        { label: "On-peak", season: "Summer", day_type: "weekday", start_time: "14:00", end_time: "19:00", unit_price: "0.210000", channel: "on_peak" },
        { label: "Off-peak", season: "Winter", day_type: "all", start_time: "00:00", end_time: "23:59", unit_price: "0.080000", channel: "off_peak" },
      ],
    },
  },
  {
    name: "demand",
    detail: live("Industrial demand", "electric", version({
      model: "demand",
      structure: {
        model: "demand",
        unit: "kWh",
        currency: "USD",
        demand: {
          energy_rate_per_kwh: "0.061000",
          demand_rate_per_kw: "14.250000",
          peak_window_label: "On-peak",
          ratchet_enabled: true,
          ratchet_pct: "80.000000",
          pf_penalty_enabled: false,
          pf_penalty_rate_per_kw: null,
        },
      } as unknown as VersionRow["structure"],
    })),
    structure: {
      demand: {
        energy_rate_per_kwh: "0.061000",
        demand_rate_per_kw: "14.250000",
        ratchet_enabled: true,
        pf_penalty_enabled: false,
        peak_window_label: "On-peak",
        ratchet_pct: "80.000000",
      },
    },
  },
  {
    name: "capacity",
    detail: live("Solar capacity", "solar", version({
      model: "capacity",
      uom: "kW-DC",
      base_charge_code: "chg-BASE-S",
      structure: {
        model: "capacity",
        unit: "kW-DC",
        currency: "USD",
        capacity: { unit_label: "kW-DC", rate_per_unit: "3.150000", currency: "USD" },
      } as unknown as VersionRow["structure"],
    })),
    structure: { capacity: { unit_label: "kW-DC", rate_per_unit: "3.150000" } },
  },
  {
    name: "percent of another service",
    detail: live("Sewer share", "sewer", version({
      model: "percent_of_service",
      uom: "kgal",
      base_charge_code: "chg-BASE-SW",
      structure: {
        model: "percent_of_service",
        unit: "kgal",
        currency: "USD",
        percent: "85.000000",
        basis_service: "water",
        percent_basis: "usage",
        tiers: TIERS([["0.000000", null, "2.400000", null]]),
      } as unknown as VersionRow["structure"],
    })),
    structure: {
      percent: "85.000000",
      basis_service: "water",
      percent_basis: "usage",
      tiers: [{ from_qty: "0.000000", to_qty: null, unit_price: "2.400000" }],
      unit_price: "2.400000",
    },
  },
];

describe("reopen on Edit brings every method's prices back, and a no-change save posts them unchanged", () => {
  it.each(REOPEN_CASES)("$name", async ({ detail, structure }) => {
    const s = stub(detail);
    const user = mountEdit(s, "t-1");
    await toReview(user);
    expect(changesCount()).toContain(t("rating.rs.wiz.changesCount", { count: 0 }));
    const posted = await createVersion(user, s);
    expect(posted.body.structure).toEqual(structure);
  });
});
