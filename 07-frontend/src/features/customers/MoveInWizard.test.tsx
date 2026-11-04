// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard, SIX steps since 2026-09-12 —
//           `CR-094-BRC01` wave H) · US-CUS-007 (the
//           deposit fields inside step 4)
//           Screens: S19
// Rules:    BR-CUS-017 (one active account per unit) · BR-CUS-019 (the customer
//           search is advisory — and unbuildable) · BR-CUS-020 (vacant units
//           only) · BR-CUS-021 (initial reads belong to metering) ·
//           BR-CUS-022 (bill-from options have no column) · BR-CUS-023 /
//           BR-CUS-024 (the deposit is a plan lookup; carry-forward rides the
//           customer entity) · BR-CUS-028 (the preference set) · BR-CUS-029 (no
//           account plan snapshot) · BR-CUS-045 (the last four of a government
//           id only) · BR-CUS-054 (no customer entity) · BR-CUS-056 (the
//           incoming account starts the day AFTER the move day) · BR-CUS-059
//           (autopay capture-only) · BR-MET-044 (the unit keeps its plan) ·
//           BR-SHL-018/019 (the shared rail and ONE commit) · BR-SHL-025
//           (disabled WITH the reason) · BR-SHL-044 (one header)
// ───────────────────────────────────────────────────────
// §4 test data is U-10432-A's turnover: A-10432 closed Aug 14 2026, the next
// occupant starting Aug 15 (US-CUS-004 §4 / US-CUS-005 TC-8). Rendered through
// the seeded query cache — no network, ever.
//
// The payload assertions are the sharp end: `moveInPayload` must carry EXACTLY
// what the endpoint accepts and never a field it refuses, because a refused
// field fails the whole move-in and a silently dropped one is a decision the
// user believes was recorded.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountDetail, AccountMoveInResult, MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { accountDetailQueryKey } from "./AccountDetailPage";
import {
  MOVE_IN_STEP_COUNT,
  MOVE_IN_STEP_IDS,
  MoveInWizard,
  moveInDateProblem,
  moveInPayload,
  moveInStepFromParam,
} from "./MoveInWizard";
import { MoveInCompleted } from "./moveInWizard/MoveInCompleted";
import type { MoveInCompletedResult } from "./moveInWizard/MoveInCompleted";
import { moveInMessagesQueryKey } from "./MoveInMessages";
import type { MoveInMessagePlan } from "./MoveInMessages";
import { emptyCustomerForm, emptyPreferencesForm } from "./NewAccountWizard";
import { MOVE_IN_STEPS, parkStoreBlockedReason, wizardParkPort } from "./moveShared";
import {
  groupsInOrder,
  unitAssetsPath,
  unitAssetsQueryKey,
} from "./UnitAssetsPanel";
import type { UnitAssetGroup, UnitAssets } from "./UnitAssetsPanel";
import {
  currentMonthPeriod,
  money,
  UnitPricingPanel,
  unitPricingPath,
  unitPricingQueryKey,
} from "./UnitPricingPanel";
import type { UnitPricing } from "./UnitPricingPanel";
import {
  ACCOUNTS_PERMISSION,
  accountMoveInPath,
  earliestMoveInDate,
  warningText,
} from "./customersShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The OUTGOING account — closed Aug 14, so the unit is free from Aug 15. */
function outgoing(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-10432",
    account_no: "A-10432",
    // BR-CUS-068 — `kind` is served on every account payload (regular | master).
    kind: "regular",
    name: "Miller, Sarah",
    unit_id: "u-10432a",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric", "water"],
    balance: "0.000000",
    // DEF-127 — the LEDGER's figure and the CHAR(3) it derived for it.
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "closed",
    status_name: "Closed",
    status_behavior_class: "terminal",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2024-02-14",
    closed_at: "2026-08-14",
    last_bill_at: null,
    aging: null,
    deposit_on_file: "150.000000",
    deposit_received_on: "2024-02-14",
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [
      {
        id: "c-1",
        full_name: "Miller, Sarah",
        email: "sarah.miller@example.com",
        phone: "+1 (512) 555-0184",
        dob: "1987-04-12",
        gov_id_last4: "4218",
        is_primary: true,
      },
    ],
    addresses: [],
    service_agreements: [
      {
        id: "sa-1",
        service_point_id: "sp-1",
        service: "electric",
        started_on: "2024-02-14",
        ended_on: "2026-08-14",
      },
    ],
    meters: [
      { id: "ast-4023", asset_no: "M-4023", qualifier: null },
      { id: "ast-4024", asset_no: "M-4024", qualifier: null },
    ],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    // DEF-2419 — the plan the UNIT stands on. Null here: these fixtures are
    // about a flow, not about the plan cell, and null is a real state
    // (a unit with no plan) rather than a placeholder.
    unit_plan: null,
    // BR-CUS-054's entity landed 2026-08-11 (US-CUS-019). An account created
    // before it — which is every account in these fixtures — carries no link,
    // and null is the honest value rather than a customer nobody created.
    customer: null,
    ...over,
  };
}

/**
 * The FIVE the server answers a move-in with: the three a turnover adds
 * (`services.MOVE_IN_UNAVAILABLE`) plus the two `_make_occupying` appends on
 * every occupying path.
 */
const FIVE_WARNINGS = [
  { code: "customer_not_linked", br_ref: "BR-CUS-054" },
  { code: "deposit_carry_forward_unavailable", br_ref: "BR-CUS-024" },
  { code: "initial_reads_not_committed", br_ref: "BR-CUS-021" },
  { code: "plan_snapshot_not_recorded", br_ref: "BR-CUS-029" },
  { code: "deposit_not_applied", br_ref: "BR-CUS-023" },
];

function moveInResult(): AccountMoveInResult {
  return {
    ...outgoing({
      id: "acc-12049",
      account_no: "A-12049",
      name: "Nguyen, Thomas",
      status: "active",
      status_name: "Active",
      status_behavior_class: "billable",
      opened_at: "2026-08-15",
      closed_at: null,
    }),
    warnings: FIVE_WARNINGS,
    moved_in_after_account_id: "acc-10432",
    moved_in_after_account_no: "A-10432",
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

// ══════════════════════════════════════════════════════════════════════════
// CR-030 W5 tasks 5.2 / 5.3 — the two unit reads step 3 and step 4 now call
// ══════════════════════════════════════════════════════════════════════════
//
// B18 TC-MVI-4's own fixture: *"a unit with 2 meters + 1 sub-meter + 1 PV
// inverter"* → *"all four listed, grouped"*. The grouping key is
// `asset_types.category` (BR-AST-004), NOT the `(sub)/(master)` qualifier, and
// the inverter is exactly where the two disagree: it hangs off its meter by
// `parent_asset`, so the qualifier says `sub` and the category says
// `behind_the_meter`. 2 / 1 / 1 groups only on the category.
const UNIT_ID = "u-10432a";

function assetGroups(): UnitAssetGroup[] {
  return [
    {
      category: "meters",
      assets: [
        {
          id: "ast-4023",
          asset_no: "M-4023",
          type: "electric_meter",
          type_name: "Electric meter",
          category: "meters",
          qualifier: null,
          service: "electric",
          // A committed head: consumption AND its explicit unit, together.
          last_read: {
            read_id: "rd-1",
            read_at: "2026-07-31",
            channel: "total",
            current_value: "42864.000000",
            consumption: "684.000000",
            unit: "kWh",
            current_value_display: "42864 kWh",
          },
        },
        {
          id: "ast-4024",
          asset_no: "M-4024",
          type: "water_meter",
          type_name: "Water meter",
          category: "meters",
          qualifier: null,
          service: "water",
          // NEVER READ. `null`, and nothing may render that as a 0.
          last_read: null,
        },
      ],
    },
    {
      category: "sub_meters",
      assets: [
        {
          id: "ast-8801",
          asset_no: "SM-8801",
          type: "sub_meter",
          type_name: "Sub-meter",
          category: "sub_meters",
          qualifier: "sub",
          service: "electric",
          last_read: null,
        },
      ],
    },
    {
      category: "behind_the_meter",
      assets: [
        {
          id: "ast-3300",
          asset_no: "PV-3300",
          type: "pv_inverter",
          type_name: "PV inverter",
          category: "behind_the_meter",
          // ⚠ The disagreement, kept: the qualifier files it as a sub-meter.
          qualifier: "sub",
          service: "electric",
          last_read: null,
        },
      ],
    },
    { category: "unclassified", assets: [] },
  ];
}

function unitAssets(over: Partial<UnitAssets> = {}): UnitAssets {
  const groups = over.groups ?? assetGroups();
  return {
    unit: {
      id: UNIT_ID,
      unit_no: "A",
      label: "A",
      premises_id: "prem-1408",
      premise_no: "P-1408",
      premise_address: "1408 Elm St",
    },
    groups,
    counts: {
      meters: 2,
      sub_meters: 1,
      behind_the_meter: 1,
      unclassified: 0,
      total: groups.reduce((sum, group) => sum + group.assets.length, 0),
    },
    // DEF-495 — `tenant_services.metered` has no reader anywhere.
    reading_expected: {
      served: false,
      reason: "metered_declaration_has_no_reader",
      tracks: "DEF-495",
    },
    ...over,
  };
}

/** The plan fixture the backend's own TC-5 uses: electric 8.000000 + water
 *  12.500000, Σ 20.500000 — rating's DERIVED figure (BR-RAT-027), forwarded.
 *  ⚠ NOTHING IN THIS FILE ADDS THOSE TWO UP, and the worked-month case below
 *  asserts that no screen does either. */
// EXPORTED for CR-034: the unit's own Plan tab mounts the same panel, and a
// second copy of this fixture in that suite would drift from the payload the
// server actually serves. One fixture, two readers.
export function unitPricing(over: Partial<UnitPricing> = {}): UnitPricing {
  return {
    unit: {
      id: UNIT_ID,
      unit_no: "A",
      label: "A",
      premise_no: "P-1408",
      premise_address: "1408 Elm St",
      rate_plan_id: "plan-77",
      plan_effective_from: "2026-01-01",
      plan_locked: false,
    },
    plan: {
      id: "plan-77",
      code: "SC-1",
      name: "Small Commercial",
      description: "Two services on one plan.",
      status: "published",
      version: 3,
      effective_from: "2026-01-01",
      effective_to: null,
      base_charges: "20.500000",
      minimum_bill_amount: null,
      budget_billing: false,
      // CR-034 (b) — WHICH DATE resolved this plan (BR-RAT-007's `as_of`).
      resolved_on: "2026-08-25",
    },
    plan_absent: null,
    // CR-034 (b) · the wizard supplies NO period, so none is invented and
    // `as_of` is the tenant's today. This is the shape step 4 always receives.
    period: {
      start: null,
      end: null,
      as_of: "2026-08-25",
      supplied: false,
      source: "not_supplied_defaults_to_today",
    },
    plan_history: {
      served: false,
      reason: "period_not_supplied",
      tracks: null,
      stretches: [],
      splits_at: [],
    },
    services: [
      {
        service: "electric",
        name: "Electric",
        base_charge: "8.000000",
        currency: "USD",
        minimum_amount: null,
      },
      {
        service: "water",
        name: "Water",
        base_charge: "12.500000",
        currency: "USD",
        minimum_amount: null,
      },
    ],
    rate_schedules: [
      {
        service: "electric",
        tariff_id: "tar-1",
        tariff_name: "Residential Electric",
        schedule: {
          id: "tar-1",
          name: "Residential Electric",
          service: "electric",
          service_name: "Electric",
          structure: "tiered",
          status: "in_force",
          effective_from: "2026-01-01",
          block_count: 2,
          season_labels: null,
          window_count: 0,
          size_count: 0,
          current_version: {
            id: "tv-1",
            model: "tiered",
            uom: "kWh",
            currency: "USD",
            base_charge: "8.000000",
            minimum_bill: null,
            effective_from: "2026-01-01",
            structure: {
              model: "tiered",
unit: "kgal",
currency: "USD",
              tiers: [
                {
                  seq: 1,
                  season: null,
                  size_class: null,
                  from_qty: "0.000000",
                  to_qty: "500.000000",
                  from_qty_display: "0 kWh",
                  to_qty_display: "500 kWh",
                  unit_price: "0.114000",
                },
                {
                  seq: 2,
                  season: null,
                  size_class: null,
                  from_qty: "500.000000",
                  to_qty: null,
                  from_qty_display: "500 kWh",
                  to_qty_display: null,
                  unit_price: "0.138000",
                },
              ],
            },
          },
          uom_gate: {
            satisfied: true,
            reason: "match",
            schedule_uom: "kWh",
            billed_uom: null,
            priced_against: "kWh",
            conversion_factor: null,
          },
        },
        absent: null,
      },
      {
        service: "water",
        tariff_id: "tar-2",
        tariff_name: "Residential Water",
        // A plan line whose schedule cannot be read is reported on its OWN row.
        schedule: null,
        absent: { reason: "schedule_not_readable" },
      },
    ],
    minimum_charges: { plan: null, services: [], schedules: [] },
    charge_codes: [
      {
        id: "pcr-1",
        charge_id: "chg-1",
        code: "CUST-SVC",
        name: "Customer service charge",
        amount_override: "4.250000",
        amount_override_display: "4.25",
        recurrence: "monthly",
        taxable: true,
        // CR-034 (b) — the CODE's own row, beside the plan's override. Both
        // travel; neither is collapsed into an "effective amount".
        service: null,
        charge_type: "recurring",
        is_base: false,
        amount_rule: "flat",
        amount: "5.000000",
        amount_display: "5.00",
        percent_display: null,
        min_amount_display: null,
        max_amount_display: null,
        applies_to_customer_classes: [],
        size_amounts: [],
      },
    ],
    discounts: {
      offered: [],
      // BR-RAT-069 — never `[]`, which reads as "none apply".
      granted: { served: false, reason: "unit_has_no_account", tracks: null },
    },
    // CR-020 — the PO's own contracts-on-plans request, captured and HELD.
    // `tracks` stays null (that field is for a DEF or an OQ); the CR is its own.
    contract: {
      served: false,
      reason: "captured_and_held_by_the_product_owner",
      tracks: null,
      change_request: "CR-020",
    },
    taxes: {
      jurisdiction_rules: [
        { jurisdiction_id: "jur-1", jurisdiction: "City of Brazos Bend", rate_override: null },
      ],
      attachments: [
        {
          tax_id: "tax-1",
          name: "PUC Regulatory Fee",
          kind: "percent",
          rate_display: "0.17%",
          flat_amount_display: null,
          jurisdiction: { id: "jur-2", name: "Texas PUC" },
        },
      ],
      // DEF-273 — the PLAN's bindings and attachments, NOT R7's final answer:
      // the set narrows again by the account's customer class at bill time.
      narrowing: {
        final: false,
        reason: "narrows_by_customer_class_at_bill_time",
        tracks: null,
      },
    },
    penalty_rule: {
      late_fee_min: "5.000000",
      late_fee_pct: "1.500000",
      grace_days: 10,
      grace_mode: "calendar",
    },
    // ⛔ NEVER SERVED — OQ-363. No total, no amount, no month figure.
    worked_month: {
      served: false,
      reason: "no_service_prices_a_plan_outside_a_bill_run",
      tracks: "OQ-363",
    },
    ...over,
  };
}

/**
 * ⛔ **THE STEP'S NUMBER, DERIVED FROM ITS ID — `BR-CUS-1101`, and it is
 * `DEF-648`'s lesson applied to this file.**
 *
 * Twenty-one cases here navigated by a LITERAL `?step=${stepOf("billing")}`, so inserting the
 * Services step at position 2 on 2026-09-25 moved five steps along and every
 * one of those cases silently started asserting the WRONG SCREEN — a test
 * looking at the wrong thing, which is hard-won law 7's fourth shape and the
 * failure mode this whole file exists to catch in the product.
 *
 * Bumping the literals would have worked today and rotted the next time a step
 * moves. This reads the one declared list (`BR-SHL-046`) instead, so a step
 * inserted anywhere carries every case with it and a step RENAMED fails loudly
 * here rather than quietly opening the wrong panel.
 */
function stepOf(id: (typeof MOVE_IN_STEP_IDS)[number]): number {
  const at = MOVE_IN_STEP_IDS.indexOf(id);
  if (at < 0) {
    throw new Error(`no move-in step called ${id} — the declared list moved under this test`);
  }
  return at + 1;
}

function renderWizard(
  path: string,
  seed: {
    detail?: AccountDetail;
    access?: string;
    assets?: UnitAssets;
    pricing?: UnitPricing;
    /** `DEF-CUS-6365` — the review step's *What goes out* read. */
    messages?: MoveInMessagePlan;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed.messages !== undefined) {
    // ⚠ **SEEDED AT THE KEY AN UNTOUCHED WIZARD ASKS FOR, DERIVED AND NEVER
    // TYPED.** The category is `emptyCustomerForm()`'s default and the deposit
    // is untaken, so a key written out by hand here goes stale the day either
    // default moves — and a MISSED key renders the loading skeleton, which
    // reads like a screen that simply has not finished rather than like a
    // broken assertion.
    queryClient.setQueryData(
      moveInMessagesQueryKey(emptyCustomerForm().account_type, false, false),
      seed.messages,
    );
  }
  if (seed.detail !== undefined) {
    queryClient.setQueryData(accountDetailQueryKey(seed.detail.id), seed.detail);
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  if (seed.assets !== undefined) {
    queryClient.setQueryData(unitAssetsQueryKey(seed.assets.unit.id), seed.assets);
  }
  if (seed.pricing !== undefined) {
    queryClient.setQueryData(unitPricingQueryKey(seed.pricing.unit.id), seed.pricing);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId/move-in" element={<MoveInWizard />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * ⚠ **CR-171-BRC10 P2.28 (lane MVI-WIZ-BILL) — STEP 3 NO LONGER MOUNTS
 * `UnitPricingPanel`.** The Billing step reads the move-in's own NARROWED
 * pricing (`GET /move-ins/pricing`, image 42) and draws the shared
 * `PlanSections`; the unit-pricing panel stays the unit's Plan tab's. So the
 * cases that pinned the panel THROUGH step 3 now mount it the way step 3 did
 * — no period, `workedMonthAbsence={false}` — and still guard every figure.
 */
function renderPricingPanel(seed: { pricing: UnitPricing }): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(unitPricingQueryKey(seed.pricing.unit.id), seed.pricing);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/units`]}>
        <Routes>
          <Route
            path="/:tenant/units"
            element={<UnitPricingPanel unitId={seed.pricing.unit.id} t={t} workedMonthAbsence={false} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Image 48's own story, as the four-step Complete answers it (§9.FLOW
 *  P1.21, §9.MONEY). Every item is one the server sent. */
function completedResult(): MoveInCompletedResult {
  return {
    ...moveInResult(),
    customer_no: "CU-000412",
    customer_outcome: "created",
    customer: { id: "cus-1", kind: "person", display_name: "Nilesh G", external_ref: null, accounts: [] },
    unit_label: "SCW-U-308",
    unit_plan: { name: "Sample — Residential", code: "SAMPLE-RES", version: 3, since: "2026-01-01" },
    service_agreements: [
      { id: "sa-1", service_point_id: "sp-1", service: "water", started_on: "2026-10-10", ended_on: null },
      { id: "sa-2", service_point_id: "sp-2", service: "sewer", started_on: "2026-10-10", ended_on: null },
    ],
    warnings: [{ code: "deposit_carry_forward_unavailable", br_ref: "BR-CUS-024" }],
    request_no: "SR-26-0014",
    what_happened: {
      move_no: "MVI-26-0011",
      request_no: "SR-26-0014",
      items: [
        { key: "customer", outcome: "created", customer_no: "CU-000412" },
        { key: "account", account_no: "A-12049" },
        { key: "services", count: 2, starts_on: "2026-10-10" },
        { key: "opening_reads", posted: 2 },
        { key: "unit", now: "occupied", was: "vacant" },
        { key: "co_owners", count: 1 },
        { key: "documents", count: 1 },
        { key: "work_orders", count: 1, declined: false, orders: [{ order_no: "WO-0062", assignee: "R. Patel" }] },
        {
          key: "fees",
          detail: { lines: [{ code: "DEPOSIT" }, { code: "CONNECT" }], total: "175.0000", currency: "USD" },
        },
        {
          key: "payment",
          detail: { mode: "pay_now", currency: "USD", amount_paid: "175.0000", receipt_no: "RC-2026-01177" },
        },
        { key: "messages", queued: 2, planned: 0 },
      ],
    },
  } as MoveInCompletedResult;
}

function renderDone(result: MoveInCompletedResult = completedResult()): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[`/${TEST_TENANT}/move-ins/new`]}>
      <Routes>
        <Route
          path="/:tenant/move-ins/new"
          element={
            <MoveInCompleted
              result={result}
              t={t}
              timeZone="America/Chicago"
              dateFormat="MM/DD/YYYY"
              onStartAnother={() => undefined}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** The document with every `title=` attribute removed — the reasons NAME what
 * they refuse, and a whole-document `not.toContain` would read that
 * explanation as the defect it exists to prevent. */
function visible(html: string): string {
  return html.replace(/ title="[^"]*"/g, "");
}

const CUSTOMER = {
  ...emptyCustomerForm(),
  account_type: "residential",
  full_name: "Nguyen, Thomas",
  email: "thomas.nguyen@example.com",
  phone: "+1 (512) 555-0219",
  dob: "1990-06-02",
  gov_id_last4: "7781",
};

describe("US-CUS-004 — the S19 Move-in wizard", () => {
  it("US-CUS-004 §1 / BR-SHL-018: the FOUR ruled steps render on the SHARED wizard frame", () => {
    // ⚠ **FOUR SINCE 2026-10-05 — `CR-171-BRC10` P2.15 (images 30–47).** It
    // was six (2026-09-12, `CR-094-BRC01`) and then seven (2026-09-25,
    // `BR-CUS-1101`); the redesign folds the services, the date, the reads and
    // the visit into the UNIT and the preferences and deposit into BILLING.
    // The COUNT and the IDS are both asserted, because the rail and the
    // Move-ins tab's STEP column are DERIVED from this one list (`BR-SHL-046`)
    // — `DEF-CUS-9703` was the list reading `of 6` while the wizard drew 7.
    expect([...MOVE_IN_STEP_IDS]).toEqual(["unit", "customer", "billing", "review"]);
    expect(MOVE_IN_STEP_COUNT).toBe(4);
    const html = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing(),
      access: "Full",
    });
    expect(html).toContain('data-wizard="frame"');
    expect(html).toContain('data-wizard="rail"');
    expect((html.match(/data-wizard-step=/g) ?? []).length).toBe(4);
    for (const label of ["Unit", "Customer", "Billing", "Review"]) {
      expect(html).toMatch(new RegExp(`data-wizard-step=[^>]*>[\\s\\S]*?${label}`));
    }
    // The seven-step names are GONE rather than present beside the four.
    for (const gone of ["Find unit", "Which services", "Start &amp; read", "Account preferences"]) {
      expect(html).not.toContain(`>${gone}<`);
    }
  });

  it("CR-171-BRC10 P2.17 / image 30: the head is back link · title · Save draft & exit, and nothing else", () => {
    // ⚠ **REWRITTEN 2026-10-05.** This asserted the prototype's kicker
    // (*Move-in*) and the title *"New occupant moving into a vacant unit."*.
    // Image 30 draws *New move-in* with no kicker, and *Save draft & exit* at
    // the head's right instead of *Save & exit* beside Park.
    // RED-FIRST, verbatim, against the pushed 2.532.0 head (the kicker still
    // drawn):
    //   AssertionError: expected '<div class="cus-page"><div class="pag…' not
    //   to match />Move-in<\/(p|span|div)>/
    const html = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing(),
      access: "Full",
    });
    expect(html).toContain("page-header");
    expect(html).toMatch(/<h1[^>]*>New move-in<\/h1>/);
    expect(html).not.toContain("New occupant moving into a vacant unit.");
    expect(html).not.toMatch(/>Move-in<\/(p|span|div)>/);
    expect(html).toMatch(/data-move-in-save-draft=""[^>]*>Save draft &amp; exit</);
    // The frame's own *Save & exit* is gone; Park stays at the bottom left.
    expect(html).not.toContain(">Save &amp; exit<");
    expect(html).toContain(">Park<");
    // CR §2 S9 — the audit sentence is ruled out of this wizard.
    expect(html).not.toContain("recorded in the audit log by the server");
    expect(html).not.toContain("cus-head");
  });

  it("US-CUS-004 TC-2 / BR-CUS-017: step 1 shows the unit it inherits and offers NO picker", () => {
    const html = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing(),
      access: "Full",
    });
    // `CR-171-BRC10` P2.18 (lane MVI-WIZ-UNIT) — image 30's *Unit* box; on the
    // account road it is the card alone (its own tests are
    // `moveInWizard/StepUnit.dom.test.tsx`). 11b §S19 is account-scoped, so
    // no unit field exists to pick into, and nothing says so (rule 33).
    expect(html).toContain('data-move-pick="unit"');
    expect(html).not.toContain('id="mvi_unit"');
    expect(html).not.toContain('id="unit_id"');
    expect(html).not.toContain("There is no picker here");
    expect(visible(html)).not.toContain("U-11602-103");
  });

  it("US-CUS-004 TC-6 / BR-CUS-017: an account that still HOLDS its unit is refused before the commit", () => {
    const stillHeld = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing({
        status: "active",
        status_name: "Active",
        status_behavior_class: "billable",
        closed_at: null,
      }),
      access: "Full",
    });
    expect(stillHeld).toContain("This account still holds the unit");
  });

  // `CR-171-BRC10` P2.18 — the *Plan · Kept from the last tenancy* row is
  // gone: image 30 does not draw it, and the card's History group says how
  // many times the unit's plan changed instead. BR-MET-044 itself is the
  // server's (the account derives its plan from the unit) and is unchanged.

  // ⚠ RE-POINTED 2026-10-05 (`CR-171-BRC10` P2.23, lane MVI-WIZ-CUST): images
  // 33–37 draw *Search customer ID* on step 2, so "NO customer search" is
  // superseded; the old returning-customer table and its sentence stay gone.
  // The step's own cases are `moveInWizard/StepCustomer.dom.test.tsx`.
  it("US-CUS-004 TC-1 / BR-CUS-054: step 2 collects one contact; the search is Search customer ID", () => {
    const html = renderWizard(`${accountMoveInPath("acc-10432")}?step=${stepOf("customer")}`, {
      detail: outgoing(),
      access: "Full",
    });
    expect(html).toContain("Who is moving in");
    expect(html).toContain("data-search-customer-id");
    expect(html).toContain('id="full_name"');
    expect(html).toContain('id="gov_id_last4"');
    // BR-CUS-045: four digits, because four digits is all the column holds.
    // `DEF-CUS-6360` — the hint was rationale (B14 rule 33) and is deleted.
    expect(html).not.toContain("The server keeps four digits");
    // The prototype's returning-customer table and its "Use" buttons. The
    // sentence explaining their absence was rationale and false (`DEF-CUS-6360`).
    expect(html).not.toContain("There is no search");
    expect(html).not.toContain('id="customer_search"');
    expect(visible(html)).not.toContain("A-11208 (closed Jul 2025)");
    expect(html).not.toContain("Use existing customer");
  });

  it("US-CUS-004 TC-4 / BR-CUS-022 / BR-CUS-021: step 1 collects the DATE; bill-from is refused", () => {
    const html = renderWizard(`${accountMoveInPath("acc-10432")}?step=${stepOf("unit")}`, {
      detail: outgoing(),
      access: "Full",
      assets: unitAssets(),
    });
    // `CR-171-BRC10` P2.19 — image 30's own *Move-in date* box.
    expect(html).toContain("data-move-in-date");
    expect(html).toContain('id="opened_at"');
    expect(html).toContain('type="date"');
    // BR-CUS-056: the earliest legal start is proposed, not merely described.
    expect(html).toContain('value="2026-08-15"');
    expect(html).toContain("08/15/2026");
    expect(html).toContain("Rates and reads use this date.");
    // BR-CUS-022: no "Bill from" select — the option set has no column, and
    // since `DEF-CUS-6361` nothing says so either (rule 33).
    expect(html).not.toContain("Not chosen here");
    expect(html).not.toContain('id="bill_from"');
    expect(visible(html)).not.toContain("Next cycle start");
    // ⚠ **THE OPENING READS MOVED (`CR-171-BRC10` P2.20).** They are typed in
    // image 30's *Services and meters* table, read from
    // `GET /units/{id}/move-in-meters` and asserted in
    // `moveInWizard/StepUnit.dom.test.tsx` — the eight-column reading table
    // (`moveIn-read-<asset id>`) is the move-out's and the transfer's now.
    expect(html).not.toContain('id="moveIn-read-ast-4023"');
    expect(html).not.toContain("Start date &amp; initial meter read.");
  });

  it("CR-171-BRC10 P2.28–P2.31 / images 41–44: step 3 is Plan, Preferences, Discounts, Tax, Fees, Payment", () => {
    // ⚠ **RE-POINTED (lane MVI-WIZ-BILL, 2026-10-05).** These two cases pinned
    // the seven-step wizard's *Account preferences* (step 4) and *Deposit*
    // (step 5), which the split moved whole into step 3. The redesign
    // replaces both bodies: the preferences are a ticked section of
    // dropdowns, the deposit is the Fees table's first row and its money is
    // the Payment panel's (§9.MONEY). The case-by-case behaviour lives in
    // `moveInWizard/StepBilling.dom.test.tsx`; this one proves the WIZARD
    // mounts the new body at step 3 and none of the old one.
    const html = renderWizard(`${accountMoveInPath("acc-10432")}?step=${stepOf("billing")}`, {
      detail: outgoing(),
      access: "Full",
    });
    expect(html).toContain('data-move-in-billing=""');
    for (const name of ["preferences", "discounts", "tax"]) {
      expect(html).toContain(`data-billing-section="${name}"`);
    }
    expect(html).toContain('data-array="move-in-fees"');
    expect(html).toContain('data-move-in-payment="pay_now"');
    // Paperless and text reminders are still offered — now as dropdowns.
    expect(html).toMatch(/<select[^>]*id="paperless"/);
    expect(html).toMatch(/<select[^>]*id="sms_reminders"/);
    expect(html).toMatch(/<select[^>]*id="preferred_language"/);
    // The old step-5 deposit form and the old pricing mount are gone.
    expect(html).not.toContain('id="deposit_decision"');
    expect(html).not.toContain('data-deposit-plan=');
    expect(html).not.toContain("No plan recorded");
    // `OQ-BIL-12788` (a) and ruling (2) of 2026-10-05.
    expect(visible(html)).not.toMatch(/Taxable|System Admin/);
  });

  it("US-CUS-004 §5 / BR-SHL-019: step 4 reviews, and there is exactly ONE commit", () => {
    const html = renderWizard(`${accountMoveInPath("acc-10432")}?step=${stepOf("review")}`, {
      detail: outgoing(),
      access: "Full",
    });
    // ⚠ **RE-POINTED 2026-10-05 (`CR-171-BRC10` P2.32, images 45–46).** The
    // one-panel *Confirm move-in.* review became three sections and the
    // Messaging table; `Confirm move-in.` is retired with its key.
    expect(html).toContain('data-move-in-review=""');
    for (const section of ["unit", "customer", "billing"]) {
      expect(html).toContain(`data-review-section="${section}"`);
    }
    // BR-TEN-035: the number is given at Complete, so none is shown before it.
    expect(html).toContain("Given when you complete");
    expect(html).not.toContain("A-12049");
    // ⚠ **THIS ASSERTED `What this move-in will not write` UNTIL 2026-09-24.**
    // That 60-word paragraph was RATIONALE (B14 rule 33 · `DEF-CUS-6365`) and
    // is deleted; the review's last section is now what the customer is sent,
    // drawn from blueprint p077. The section is asserted rather than the
    // paragraph so this case still proves step 6 rendered its whole body.
    expect(html).toContain('data-move-in-messages=""');
    expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
    expect(html).toContain("Complete move-in ✓");
  });

  it("US-CUS-004 TC-1 §5: the payload is EXACTLY the field set the endpoint accepts", () => {
    const payload = moveInPayload({
      customer: CUSTOMER,
      preferences: { ...emptyPreferencesForm(), autopay: true },
      openedAt: "2026-08-15",
    });
    expect(payload).toEqual({
      account_type: "residential",
      status: "active",
      opened_at: "2026-08-15",
      autopay: true,
      tax_exempt: false,
      // `BR-CUS-028` + `BR-BIL-036` — the two delivery elections, sent
      // UNCONDITIONALLY because `false` is a real answer: "not paperless" is a
      // preference, not an absent value. Writable since `customers 0034`
      // (2026-08-31) and collected on the wizard since `CR-094-BRC01` wave H.
      paperless: false,
      sms_reminders: false,
      contact: {
        full_name: "Nguyen, Thomas",
        email: "thomas.nguyen@example.com",
        phone: "+1 (512) 555-0219",
        dob: "1990-06-02",
        gov_id_last4: "7781",
        is_primary: true,
      },
      // ⛔ **THE `customer` BLOCK JOINED THIS PAYLOAD ON 2026-09-01 (`CR-058`
      // task 8).** `POST /accounts/{id}/move-in` has accepted it since
      // `CR-056` W3 and this screen sent a CONTACT ONLY, so every move-in at
      // the counter produced an account with a blank customer column — law 2,
      // built is not wired, on the second of two screens. PO on this door:
      // *"You either create new Customer ID or you link existing customer ID
      // here"*.
      //
      // No `kind` and no `identity` here because `CUSTOMER` states no customer
      // kind — which is a real answer and, since the same day's ruling, one the
      // step itself refuses to advance on (`BR-CUS-1024`). The block still
      // carries the NAME, which is what the server matches nothing on and
      // reports as a shortfall.
      customer: { display_name: "Nguyen, Thomas" },
    });
  });

  it("US-CUS-004 §5: no refused field can reach the wire, whatever is entered", () => {
    const payload = moveInPayload({
      // `DEF-CUS-6359` — written only with *Same as service address* unticked.
      customer: { ...CUSTOMER, mailing_same: false, mailing_line1: "PO Box 88", mailing_city: "Katy" },
      preferences: {
        autopay: true,
        // `CR-094-BRC01` wave H — `BR-CUS-028`'s two delivery elections, in
        // `PreferencesForm` since the refusal on both columns expired.
        paperless: true,
        sms_reminders: false,
        preferred_language: " es ",
        tax_exempt: true,
        tax_exempt_ref: "TX-4491",
        tax_exempt_expires: "2027-01-01",
        custom_data: {},
      },
      openedAt: "2026-08-15",
    });
    // `services.REFUSED_FIELDS` — each of these fails the WHOLE move-in.
    //
    // ⚠ **`initial_reads` LEFT THIS LIST 2026-08-26 (CR-038 W9 task 3)** — it is
    // in `MOVE_IN_FIELDS` now and the wizard SENDS it when readings were keyed.
    // The case above builds this payload with NO reads, and the assertion below
    // still holds for exactly the right reason: `readsPayloadPart` omits the key
    // rather than sending `[]`. `final_reads` stays here — it is the MOVE-OUT's
    // key and is still refused whole by the move-in endpoint.
    for (const refused of [
      "unit_id",
      "bill_from",
      "final_reads",
      "plan",
      "rate_plan_id",
      "plan_version",
      // ⛔ **`customer` LEFT THIS LIST ON 2026-09-01 (`CR-058` task 8)** — it is
      // in `MOVE_IN_FIELDS` (it always was, through `CREATE_FIELDS`) and the
      // wizard SENDS it now. The entry was written when S19 had no linking path
      // at all; `customer_id` stays, because this screen still offers no
      // "use this existing customer" picker and would be naming a row it never
      // showed anybody.
      "customer_id",
      "carry_deposit_from",
      "deposit_on_file",
      "deposit_election",
      "credit_tier",
      // ⛔ **`paperless` AND `sms_reminders` LEFT THIS LIST ON 2026-09-12
      // (`CR-094-BRC01` wave H).** They were removed from
      // `services.REFUSED_FIELDS` on 2026-08-31 (`CR-052` task 14, migration
      // `customers 0034`) and have been in `CREATE_FIELDS` AND `PATCH_FIELDS`
      // ever since; the SCREENS went on refusing them for twelve days. A test
      // that pins an expired refusal is green on the bug — `DEF-1840`'s shape —
      // so the entries are deleted rather than reworded (hard-won law 1).
      "budget_billing",
      "statement_language",
      "bill_delivery_day",
      "account_no",
      "balance",
      "currency",
      "closed_at",
    ]) {
      expect(payload).not.toHaveProperty(refused);
    }
    // What IS accepted travels trimmed, and the mailing address is a real row.
    expect(payload.preferred_language).toBe("es");
    expect(payload.tax_exempt_ref).toBe("TX-4491");
    expect(payload.addresses).toEqual([
      { kind: "mailing", line1: "PO Box 88", city: "Katy", state: "", postal_code: "" },
    ]);
  });

  it("US-CUS-004 §1 / BR-CUS-045: an empty contact is omitted and a long id is cut to four digits", () => {
    const empty = moveInPayload({
      customer: emptyCustomerForm(),
      preferences: emptyPreferencesForm(),
      openedAt: "",
    });
    // The server requires `full_name` once a contact is sent, so an empty one
    // is omitted rather than posted as a nameless contact row.
    expect(empty).not.toHaveProperty("contact");
    // B2 §2: no mailing row means "same as service".
    expect(empty).not.toHaveProperty("addresses");
    // An unset start date is omitted, not sent as an empty string.
    expect(empty).not.toHaveProperty("opened_at");
    // The move-in always occupies — the DRAFT road is `POST /accounts` (S18).
    expect(empty.status).toBe("active");

    const long = moveInPayload({
      customer: { ...CUSTOMER, gov_id_last4: "123456789" },
      preferences: emptyPreferencesForm(),
      openedAt: "2026-08-15",
    });
    expect((long.contact as Record<string, unknown>).gov_id_last4).toBe("6789");
  });

  it("US-CUS-004 TC-6 / BR-CUS-056: the start date may not land on or before the outgoing move day", () => {
    expect(earliestMoveInDate("2026-08-14")).toBe("2026-08-15");
    expect(moveInDateProblem("", "2026-08-15")).toBe("required");
    expect(moveInDateProblem("2026-08-14", "2026-08-15")).toBe("on_or_before_move_day");
    expect(moveInDateProblem("2026-08-13", "2026-08-15")).toBe("on_or_before_move_day");
    expect(moveInDateProblem("2026-08-15", "2026-08-15")).toBeNull();
    expect(moveInDateProblem("2026-09-01", "2026-08-15")).toBeNull();
    // A predecessor closed WITHOUT a date is not a boundary — never a guess.
    expect(moveInDateProblem("2020-01-01", null)).toBeNull();
  });

  it("US-CUS-004 §5 / BR-SHL-011: an out-of-range or non-numeric ?step= clamps rather than erroring", () => {
    expect(moveInStepFromParam(null)).toBe(1);
    expect(moveInStepFromParam("4")).toBe(4);
    expect(moveInStepFromParam("0")).toBe(1);
    // FOUR since `CR-171-BRC10` — the clamp is the LIST's length and was
    // never a literal, which is why this one number is the only change.
    expect(moveInStepFromParam("99")).toBe(4);
    expect(moveInStepFromParam("banana")).toBe(1);
  });

  it("CR-171-BRC10 P2.16 / image 48: Move-in completed — the number, where it came from, What happened, three doors", () => {
    // ⚠ **REWRITTEN 2026-10-05 (`DEF-CUS-9702`).** This asserted the old result
    // panel: *"What the server could not do"* over FIVE warnings, two of them
    // false (*no same customer to carry from* on the screen that created the
    // customer; *the table that holds an account's plan does not exist*). The
    // server stopped serving the false one (P1.21); image 48 draws the answer.
    // RED-FIRST, verbatim, with `whatHappenedRows` reading no items (the old
    // panel drew none of the server's list):
    //   AssertionError: expected [] to deeply equal [ 'customer', 'account', …(9) ]
    const html = renderDone();
    const text = visible(html);
    expect(html).toMatch(/<h1[^>]*>Move-in completed<\/h1>/);
    expect(text).toContain("Completed");
    expect(text).toContain("MVI-26-0011");
    expect(text).toContain("From request SR-26-0014 · Nilesh G · SCW-U-308");
    expect(text).toContain("What happened");
    // The ✓ rows in the server's order, each a row the commit reported.
    const labels = [...html.matchAll(/data-check="([a-z_]+)"/g)].map((match) => match[1]);
    expect(labels).toEqual([
      "customer",
      "account",
      "services",
      "opening_reads",
      "unit",
      "co_owners",
      "documents",
      "work_orders",
      "fees",
      "payment",
      "messages",
    ]);
    expect(text).toContain("Created CU-000412 · Nilesh G");
    expect(text).toContain("Opened A-12049 · Sample — Residential · v3");
    expect(text).toContain("Water · Sewer start 10/10/2026");
    expect(text).toContain("SCW-U-308 · Vacant → Occupied");
    expect(text).toContain("WO-0062 · R. Patel");
    expect(text).toContain("$175.00 posted · DEPOSIT, CONNECT");
    expect(text).toContain("$175.00 received · receipt RC-2026-01177");
    // The three doors, in the drawn order.
    expect(text).toMatch(/\+ Start another move-in[\s\S]*Open the move-in[\s\S]*Open the account →/);
    expect(html).toContain(`href="/${TEST_TENANT}/moves/MVI-26-0011"`);
    expect(html).toContain(`href="/${TEST_TENANT}/accounts/acc-12049"`);
    // A true warning still shows; the old panel's words are gone.
    expect(text).toContain(warningText({ code: "deposit_carry_forward_unavailable", br_ref: "BR-CUS-024" }, t).slice(0, 30));
    for (const gone of ["Move-in complete.", "What was written", "Open the new account", "What happens next"]) {
      expect(text).not.toContain(gone);
    }
  });

  it("CR-171-BRC10 P2.16: a key the commit did not report draws NO row (absent, never zero)", () => {
    const base = completedResult();
    const html = renderDone({
      ...base,
      what_happened: {
        move_no: "MVI-26-0011",
        request_no: null,
        items: (base.what_happened?.items ?? []).filter(
          (item) => !["co_owners", "documents", "fees", "payment"].includes(item.key),
        ),
      },
      request_no: null,
    });
    for (const absent of ["co_owners", "documents", "fees", "payment"]) {
      expect(html).not.toContain(`data-check="${absent}"`);
    }
    expect(visible(html)).not.toContain("From request");
  });

  it("CR-171-BRC10 P2.16: a co-owner or document count of 0 draws no ✓ row — nothing was done", () => {
    // Found on the lane walk (W48-completed.png, 2.535.0): *Co-owners · 0 added*
    // and *Documents · 0 filed on the customer*, each ticked.
    // RED-FIRST, verbatim: expected '…' not to contain 'data-check="co_owners"'
    const base = completedResult();
    const html = renderDone({
      ...base,
      what_happened: {
        move_no: "MVI-26-0011",
        request_no: null,
        items: (base.what_happened?.items ?? []).map((item) =>
          item.key === "co_owners" || item.key === "documents" ? { ...item, count: 0 } : item,
        ),
      },
    });
    expect(html).not.toContain('data-check="co_owners"');
    expect(html).not.toContain('data-check="documents"');
    expect(html).toContain('data-check="messages"');
  });

  it("US-CUS-004 §RBAC / BR-SHL-025: a View role sees the flow with the reason, and a '—' cell sees nothing", () => {
    const viewOnly = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing(),
      access: "View",
    });
    expect(viewOnly).toContain("Your role can view accounts but not change them.");
    expect(viewOnly).toContain('data-wizard="frame"');

    const denied = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing(),
      access: "—",
    });
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain('data-wizard="frame"');
  });

  it.todo(
    "US-CUS-004 TC-1: Continue through all six steps and commit — the click path needs a browser; each step's fields, the payload and the answer are asserted statically above",
  );
  it.todo(
    "US-CUS-004 TC-3: a plan override warns about a services mismatch and writes the unit's assignment history — no plan field exists, because the account plan table does not (BR-CUS-029)",
  );
  it.todo(
    "US-CUS-004 TC-5 (negative): an initial read below the prior final routes into the metering exception path — there is no initial-read control to refuse (BR-CUS-021)",
  );
  it.todo(
    "US-CUS-004 TC-7 (isolation): J. Okafor's customer search returns nothing — there is no customer search (BR-CUS-054), and scoping is server/RLS (G5)",
  );
});


// ══════════════════════════════════════════════════════════════════════════
// CR-030 W5 task 5.1 · BR-SHL-047 — the move-in half of "EVERY wizard parks"
// ══════════════════════════════════════════════════════════════════════════

describe("BR-SHL-047 — the move-in wizard's exit controls", () => {
  /**
   * ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-08-26, AND IT WAS RIGHT.**
   * It read *"carries `Save & exit` and `Park`, the latter DISABLED CARRYING its
   * reason"* and asserted `data-wizard="park-blocked"`, the visible sentence
   * *"Parking is not available here yet"*, `wizardParkPort()).toBeNull()` and
   * `parkStoreBlockedReason(t)).not.toBeNull()`. Every one of those was true
   * while there was no store: BR-SHL-025 asks for the control disabled CARRYING
   * its reason, and it was.
   *
   * **CR-035 built the store (PO 2026-08-26: *"Park to actually work on the
   * wizards - it should work"*), so the FACT changed and the rule did not.** The
   * assertions are inverted here rather than deleted, because the pair — a
   * control that cannot act says why, a control that can act is not disabled —
   * is one rule read from both ends, and losing the second half is how a
   * regression to `null` would ship silently.
   *
   * The behavioural half — the panel, the POST, resume, the rail staying locked
   * — is `wizardPark.dom.test.tsx`, in jsdom, because none of it is visible in
   * a first paint.
   */
  it("carries `Save draft & exit` and `Park`, and Park is NOT disabled now that the store exists", () => {
    const html = renderWizard(accountMoveInPath("acc-10432"), {
      detail: outgoing(),
      access: "Full",
    });
    expect(html).toContain('data-wizard="exit"');
    // `CR-171-BRC10` P2.17 — image 30 puts it in the page head, worded so.
    expect(html).toContain("Save draft &amp; exit");
    // BR-SHL-025's disabled-with-reason wrapper renders only when there IS a
    // reason. There is not.
    expect(html).not.toContain('data-wizard="park-blocked"');
    expect(html.replace(/ title="[^"]*"/g, "")).not.toContain("Parking is not available here yet");
    // ✅ CR-035 — `wizard_parks` is the store the superseded sentence said was
    // missing. It holds a saved FORM and not a move-in: BR-SHL-048 keeps Unit 12
    // reading Vacant for as long as the draft sits.
    expect(wizardParkPort()).not.toBeNull();
    expect(parkStoreBlockedReason(t)).toBeNull();
  });

  it("BR-SHL-046: the FOUR steps come from the SAME declared list the frame draws", () => {
    expect(MOVE_IN_STEP_COUNT).toBe(MOVE_IN_STEPS.length);
    expect(MOVE_IN_STEP_IDS).toEqual(MOVE_IN_STEPS.map((step) => step.id));
    // DEF-648 was the move-out's four-against-six; move-in was never in dispute
    // and reads the one list anyway, because the mechanism is the ruling's
    // durable half and a second literal is how the defect recurs.
    expect(MOVE_IN_STEP_COUNT).toBe(4);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-030 W5 task 5.2 — MOVE-IN STEP 3'S ASSET PANEL (B18 §5.5.3 / §5.5.5)
// ══════════════════════════════════════════════════════════════════════════
//
// The endpoint landed on 2026-08-25 with NO CALLER — hard-won law 2, *"built is
// not wired"*. These cases assert the wiring itself (the exact path), the
// grouping B18 TC-MVI-4 asks for, and the three things the panel must refuse to
// draw.

// ⚠ `CR-171-BRC10` P2.20 (lane MVI-WIZ-UNIT): the four cases that rendered
// the move-in's eight-column reading table (row order, the unit on a reading,
// a dash for a register never read, the empty sentence) and DEF-495's *no box
// is required* are re-pointed to image 30's *Services and meters* in
// `moveInWizard/StepUnit.dom.test.tsx` — where the opening read IS required
// as drawn, unless a field visit is booked (decision log). The pure helpers
// below still belong to `UnitAssetsPanel`, which the move-out mounts.
describe("CR-030 W5 task 5.2 — move-in step 3's asset panel", () => {
  it("calls the REAL path, and there is exactly one string that names it", () => {
    // Hard-won law 2's own check: the route in the panel is the route the
    // backend mounted (`path("units/<uuid:unit_id>/assets", …)`).
    expect(unitAssetsPath(UNIT_ID)).toBe(`/units/${UNIT_ID}/assets`);
    // An id with a slash or a space cannot escape its segment.
    expect(unitAssetsPath("a/b c")).toBe("/units/a%2Fb%20c/assets");
    expect([...unitAssetsQueryKey(UNIT_ID)]).toEqual(["metering", "unit", UNIT_ID, "assets"]);
  });

  it("a group the server did not send is still drawn, and an unknown one is not dropped", () => {
    // The four declared groups always render — a clerk reads "sub-meters:
    // none" rather than inferring it from an absence.
    expect(groupsInOrder([{ category: "meters", assets: [] }]).map((g) => g.category)).toEqual([
      "meters",
      "sub_meters",
      "behind_the_meter",
      "unclassified",
    ]);
    // A fifth category is APPENDED, never dropped: hiding installed equipment
    // from the clerk taking a unit over is the worse failure.
    const withExtra = groupsInOrder([
      { category: "storage", assets: [] },
      { category: "meters", assets: [] },
    ]);
    expect(withExtra.map((g) => g.category)).toEqual([
      "meters",
      "sub_meters",
      "behind_the_meter",
      "unclassified",
      "storage",
    ]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-030 W5 task 5.3 — MOVE-IN STEP 4'S PRICING PANEL (B18 §5.5.3 / §5.5.5)
// ══════════════════════════════════════════════════════════════════════════

describe("CR-030 W5 task 5.3 — move-in step 4's pricing panel", () => {
  it("calls the REAL path", () => {
    expect(unitPricingPath(UNIT_ID)).toBe(`/units/${UNIT_ID}/pricing`);
    expect(unitPricingPath("a/b c")).toBe("/units/a%2Fb%20c/pricing");
    // ⚠ AMENDED 2026-08-26 (CR-034 (b)) — THE PERIOD IS PART OF THE CACHE KEY,
    // and it has to be: two periods are two different answers (a rate filing or
    // a plan change moves them), so sharing one cache entry would show July's
    // rates under August's heading the moment a user switched back. `null, null`
    // is the no-period answer this wizard always asks for.
    expect([...unitPricingQueryKey(UNIT_ID)]).toEqual([
      "metering",
      "unit",
      UNIT_ID,
      "pricing",
      null,
      null,
    ]);
    expect([...unitPricingQueryKey(UNIT_ID, { start: "2026-07-01", end: "2026-07-31" })]).toEqual([
      "metering",
      "unit",
      UNIT_ID,
      "pricing",
      "2026-07-01",
      "2026-07-31",
    ]);
    // …and the period reaches the wire as query params, both or neither.
    expect(unitPricingPath(UNIT_ID, { start: "2026-07-01", end: "2026-07-31" })).toBe(
      `/units/${UNIT_ID}/pricing?period_start=2026-07-01&period_end=2026-07-31`,
    );
  });

  it("⚠ PO 2026-08-26: the STAFF Plan tab defaults to this month — THIS mount still does not", () => {
    // ⚠ **THE OPPOSITE-DIRECTION GUARD, AND IT IS THE ONE THAT MATTERS.** The
    // PO ruled *"B Default to this month"* and it is implemented in the PANEL,
    // on the `showPeriod` mount only. This wizard is the customer-facing mount:
    // a person signing up on the 25th must not be shown a rate version that
    // takes effect on the 28th, under a heading about what they will pay.
    //
    // If anyone ever "completes" that ruling by pushing the default down into
    // `getUnitPricing`, the endpoint or this wizard, step 4 starts asking on the
    // month key, finds nothing seeded on the `null, null` key below, and this
    // test measures A18's skeleton instead of the plan.
    const html = renderPricingPanel({
      pricing: unitPricing(), // seeded on the NO-PERIOD key by `renderPricingPanel`
    });
    expect(html).toContain("Small Commercial"); // it asked with no period
    // …and it draws no period control, because it never chooses a period.
    expect(html).not.toContain('data-pricing-period-control=""');
    // Seeded on the MONTH key instead, the same mount finds nothing — which is
    // what proves the assertion above is about the KEY and not about luck.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const pricing = unitPricing();
    queryClient.setQueryData(unitPricingQueryKey(pricing.unit.id, currentMonthPeriod()), pricing);
    const onMonthKey = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <UnitPricingPanel unitId={pricing.unit.id} t={t} workedMonthAbsence={false} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(onMonthKey).not.toContain("Small Commercial");
  });

  it("B18 §5.5.5: the plan, its rate blocks, its charge codes and its taxes all render", () => {
    const html = renderPricingPanel({
      pricing: unitPricing(),
    });
    // The plan itself.
    expect(html).toContain("Small Commercial");
    expect(html).toContain("SC-1");
    // BR-RAT-027 — rating's DERIVED Σ, forwarded and DISPLAYED at 2 places
    // (hard rule 2: stored 4/6, display 2). 20.500000 → $20.50.
    expect(html).toContain("$20.50");
    expect(html).not.toContain("20.500000");
    // Per-service base charges, each at its own 2 places.
    expect(html).toContain("$8.00");
    expect(html).toContain("$12.50");
    // "rate schedules with blocks" — the in-force version's own tiers.
    expect(html).toContain("Residential Electric");
    // ⚠ **AMENDED 2026-08-27 (DEF-1121 · OQ-620(a)).** The expected string was
    // the STORED rate, `0.114000` — and the surrounding case says "verbatim",
    // which was the whole rule until the PO ruled one: *"What does a tariff
    // rate show? Four ($0.1420). A rate is not money and not a quantity - 4
    // decimal places"*. Since 2026-10-02 (*"Show unit prices with up to 4
    // decimals and keep every total at 2."*) it reads `$0.114` — up to four
    // places, zeros past the second dropped, and NOT `formatMoney`'s two
    // (`$0.11`). What the case guards is unchanged: the figure is the stored
    // row's, never re-derived.
    expect(html).toContain(">$0.114<");
    expect(html).toContain(">$0.138<"); // DEF-1121 — was "0.138000"
    // Charge codes.
    expect(html).toContain("CUST-SVC");
    expect(html).toContain("$4.25");
    // BR-RAT-096 bindings and BR-RAT-113 attachments stay TWO lists.
    expect(html).toContain("City of Brazos Bend");
    expect(html).toContain("PUC Regulatory Fee");
    expect(html).toContain('data-br-ref="BR-RAT-096"');
    expect(html).toContain('data-br-ref="BR-RAT-113"');
    // A percentage is rating's own display string — never re-formatted here.
    expect(html).toContain("0.17%");
    // The penalty rule.
    expect(html).toContain("10 days (calendar)");
  });

  it("DEF-SHL-6348 / B14 rule 31: a tax authority with no name reads as a dash, never its id", () => {
    const base = unitPricing();
    const html = renderPricingPanel({
      pricing: unitPricing({
        taxes: {
          ...base.taxes,
          jurisdiction_rules: [{ jurisdiction_id: "jur-1", jurisdiction: null, rate_override: null }],
        },
      }),
    });
    expect(visible(html)).not.toContain("jur-1");
    expect(html).toContain('data-plan-taxes=""');
  });

  it("⛔ OQ-363: step 4 draws NO worked month — neither a figure nor its absence", () => {
    const html = renderPricingPanel({
      pricing: unitPricing(),
    });
    // ⚠ **AMENDED 2026-09-23 (`DEF-CUS-6364`).** This asserted the stated
    // absence *"An example month — We cannot show a worked example month
    // yet…"* with `data-tracks="OQ-363"`. The PO cut that paragraph from this
    // step; the unit's Plan tab still draws it (`UnitsPage.test.tsx`), so
    // OQ-363 keeps a screen that names it.
    expect(html).not.toContain("We cannot show a worked example month yet.");
    expect(html).not.toContain("An example month");
    expect(html).not.toContain('data-tracks="OQ-363"');
    // ⚠ THE ASSERTION THAT MATTERS IS UNCHANGED. Σ(8.00, 12.50) = 20.50 and
    // Σ + the charge code = 24.75; a lane "helpfully" summing the base charges
    // would produce one of them, and that is BR-RAT-005's tax base
    // reimplemented outside the ❄️ FROZEN engine. $20.50 IS on the screen —
    // rating's own `base_charges`, in the plan panel — and $24.75 is nowhere.
    expect(visible(html)).not.toContain("$24.75");
    expect(visible(html)).not.toContain("from $");
  });

  it("BR-RAT-038: a schedule whose UoM gate is closed says a bill cannot be produced", () => {
    const base = unitPricing();
    const gated = unitPricing({
      rate_schedules: [
        {
          ...base.rate_schedules[0],
          schedule: {
            ...base.rate_schedules[0].schedule!,
            uom_gate: {
              satisfied: false,
              reason: "mismatch_no_factor",
              schedule_uom: "kWh",
              // DEF-3201 — THE PRODUCTION SHAPE, and the reason this case did
              // not catch what the PO saw. `tenant_services.billed_uom` is NULL
              // on every tenant ever provisioned; this fixture filled it in, so
              // the sentence rendered a unit here and rendered a BLANK on the
              // real screen. NULL declared, `priced_against` carrying the unit.
              billed_uom: null,
              priced_against: "therm",
              conversion_factor: null,
            },
          },
        },
      ],
    });
    const html = renderPricingPanel({
      pricing: gated,
    });
    expect(html).toContain("This schedule prices in kWh and the service is billed in therm");
    expect(html).toContain('role="alert"');
  });

  it("each `plan_absent` reason renders ITS OWN sentence — three states, three answers", () => {
    const sentences: Record<string, string> = {
      unit_has_no_plan: "This unit is not on a rate plan yet.",
      rating_not_wired: "Plans and rates are not available right now",
      plan_not_found: "This unit names a rate plan we cannot open.",
    };
    for (const [reason, sentence] of Object.entries(sentences)) {
      const html = renderPricingPanel({
        pricing: unitPricing({
          plan: null,
          plan_absent: { reason, tracks: null },
          services: [],
          rate_schedules: [],
          charge_codes: [],
          taxes: {
            jurisdiction_rules: [],
            attachments: [],
            // DEF-273 — the plan's bindings are not R7's final answer.
            narrowing: {
              final: false,
              reason: "narrows_by_customer_class_at_bill_time",
              tracks: null,
            },
          },
          penalty_rule: null,
        }),
      });
      expect(html).toContain(`data-plan-absent="${reason}"`);
      expect(html).toContain(sentence);
      // BR-MET-100 — none of the three is an error on the unit.
      expect(html).not.toContain("state-failed");
      // And each is DIFFERENT: a screen that rendered one sentence for all
      // three would tell staff the wrong thing twice.
      for (const [other, otherSentence] of Object.entries(sentences)) {
        if (other !== reason) {
          expect(html).not.toContain(otherSentence);
        }
      }
    }
  });

  it("DEF-725: a tax section whose only rows are BINDINGS says so", () => {
    // The PO read this section on the deployed v2.49.0 and said "you would
    // ahve shown tax rates". Seven rows, every one labelled Authority, not one
    // tax and not one rate — and every value on it TRUE, which is why no
    // assertion fired.
    //
    // Rating serves taxes in TWO shapes. A JURISDICTION BINDING carries an
    // authority and by design names no tax and no rate; an ATTACHMENT carries
    // the name and the rate. This tenant's seeded plan has bindings and no
    // attachments, so the section could not answer the question it was opened
    // for — and said nothing about that.
    const html = renderPricingPanel({
      pricing: unitPricing({
        taxes: {
          jurisdiction_rules: [
            { jurisdiction_id: "jur-1", jurisdiction: "City of Brazos Bend", rate_override: null },
          ],
          attachments: [],
          narrowing: {
            final: false,
            reason: "narrows_by_customer_class_at_bill_time",
            tracks: null,
          },
        },
      }),
    });
    expect(html).toContain('data-tax-bindings-only=""');
    expect(html).toContain("No specific tax or fee is attached to it");
    // The binding is still LISTED — the fix states the absence, it does not
    // hide the authorities.
    expect(html).toContain("City of Brazos Bend");
  });

  it("DEF-725: the bindings-only note is ABSENT once a real tax is attached", () => {
    // The note must not become permanent furniture: the default fixture
    // carries the PUC Regulatory Fee at 0.17%, which is exactly the case the
    // section exists to show.
    const html = renderPricingPanel({
      pricing: unitPricing(),
    });
    expect(html).toContain("PUC Regulatory Fee");
    expect(html).not.toContain('data-tax-bindings-only=""');
    expect(html).not.toContain("No specific tax or fee is attached to it");
  });

  it("a plan line whose schedule cannot be read is reported on its OWN row", () => {
    const html = renderPricingPanel({
      pricing: unitPricing(),
    });
    expect(html).toContain("This service&#x27;s rate schedule could not be read");
    // The OTHER service still prices on screen.
    expect(html).toContain(">$0.114<");
  });

  it("hard rule 2: an amount with no CHAR(3) currency renders a sentence, never a defaulted $", () => {
    // `MoneyCell` refuses an absent amount (DEF-151/176); a missing CURRENCY is
    // the same defect one column over — inventing USD puts a currency on a
    // screen the tenant never chose.
    expect(money("8.000000", "USD")).toEqual({ amount: "8.000000", currency: "USD" });
    expect(money("8.000000", null)).toBeNull();
    expect(money("8.000000", "")).toBeNull();
    expect(money(null, "USD")).toBeNull();
    expect(money("", "USD")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE REVIEW'S "WHAT GOES OUT" TABLE — blueprint p077, `DEF-CUS-6365`
// ══════════════════════════════════════════════════════════════════════════
//
// Replaces `CR-030 W5 task 5.6`'s *"what we'll send"* panel, which was a
// hard-coded list of two written when no delivery existed. The PO, 2026-09-23:
// *"reduce this text; As per drawing you are not showing consumer
// communication related items email, contract, text , inapp message taht will
// be sent to cutomer once move-in is approve"*.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** the two deleted blocks are asserted
// ABSENT by their own opening words rather than by a key, because a key that
// stops being called still renders wherever else it is called; and the table is
// asserted by its ROWS, because a heading with no rows under it reads as
// *nothing goes out* — the opposite claim.

// ⚠ RE-POINTED 2026-10-05 from Accounts blueprint p077 to the move-in
// redesign's images 45–46 (`CR-171-BRC10` P2.33): the table is the kit's
// `TableArray` (SEND · MESSAGE · TO · CHANNEL · WHEN), the template column is
// not drawn, and the defaults are named as the drawing names them.
describe("the review draws the customer's messages as images 45–46 draw them", () => {
  const PLAN: MoveInMessagePlan = {
    served: true,
    results: [
      {
        key: "move_in_welcome",
        channels: ["email", "pdf_print"],
        template: { code: "email_welcome", name: "Welcome — move-in", version: 5 },
      },
      {
        key: "payment_received",
        channels: ["email"],
        template: { code: "email_payment_receipt", name: "Deposit receipt", version: 3 },
      },
      { key: "service_agreement", channels: [], template: null },
    ],
  };

  function reviewHtml(messages: MoveInMessagePlan = PLAN): string {
    return renderWizard(`${accountMoveInPath("acc-10432")}?step=${stepOf("review")}`, {
      detail: outgoing(),
      access: "Full",
      messages,
    });
  }

  it("draws one row per message the SERVER says the save will queue", () => {
    const html = reviewHtml();
    expect(html).toContain('data-move-in-messages=""');
    expect(html).toContain('data-array="move-in-messages"');
    // The three rows, by the server's own key — never by a list in the screen.
    expect(html).toContain('data-message-name="move_in_welcome"');
    expect(html).toContain('data-message-name="payment_received"');
    expect(html).toContain('data-message-name="service_agreement"');
    expect((html.match(/data-editable-row=/g) ?? []).length).toBe(3);
    const shown = visible(html);
    expect(shown).toContain("Messaging");
    for (const column of ["Send", "Message", "To", "Channel", "When"]) {
      expect(shown).toContain(column);
    }
    expect(shown).not.toContain("Template");
    // The channels are the ones the NOTIFICATION RULES screen names, joined in
    // the server's order — not a second vocabulary for the same channels.
    expect(shown).toContain("Email · Printed letter");
    expect(shown).toContain("Welcome · account opened");
    expect(shown).toContain("Deposit receipt");
  });

  it("the CONTRACT is drawn, and it is drawn as going out on nothing", () => {
    // The PO named it in their own words — *"email, contract, text , inapp
    // message"* — and p077 draws it third. A move-in WRITES the service
    // agreement and queues no message for it, so the row is present, its box is
    // not ticked and its channel is a dash. Claiming a delivery here is the
    // fabrication `BR-NOT-013` exists to stop.
    const html = reviewHtml();
    const at = html.indexOf('data-message-name="service_agreement"');
    const row = html.slice(html.lastIndexOf("<tr", at), html.indexOf("</tr>", at));
    expect(row).toContain("disabled");
    expect(visible(row)).toContain("Service agreement");
    expect(visible(row)).toContain("—");
  });

  it("every SEND box is disabled — the commit takes no message choice", () => {
    // Hard-won law 2's mirror: a live control over a door that would refuse the
    // key. `POST /accounts/{id}/move-in` has no parameter for which messages to
    // queue. The day one is ruled, this assertion is what goes red.
    const table = reviewHtml().slice(reviewHtml().indexOf('data-move-in-messages=""'));
    const cells = table.split('type="checkbox"').slice(1);
    expect(cells.length).toBe(3);
    for (const cell of cells) {
      expect(cell.slice(0, 200)).toContain("disabled");
    }
  });

  it("the 60-word paragraph and the 'nothing is delivered' block are GONE", () => {
    const html = visible(reviewHtml());
    // B14 rule 33 — RATIONALE is ZERO words on screen. Both of these were
    // rationale, and both had clauses that had quietly become false.
    expect(html).not.toContain("What this move-in will not write");
    expect(html).not.toContain("This creates the new account with its own number");
    expect(html).not.toContain("Nothing is delivered to the customer");
    expect(html).not.toContain("There is no email, text or print delivery in this release");
    expect(html).not.toContain("What we&#x27;ll send");
    expect(html).not.toContain("Email — not sent");
    expect(html).not.toContain("Document — not produced");
  });

  it("NO fabricated send status — not `emailed`, `sent`, `posted` or `delivered`", () => {
    // Carried over from task 5.6 unchanged in intent: `BR-NOT-013` still holds,
    // so a `✓ emailed` chip here would stop a clerk chasing a letter that was
    // never sent. Asserted on rendered VALUES, never on the words (DEF-182).
    const html = visible(reviewHtml());
    const panel = html.slice(html.indexOf('data-move-in-messages=""'));
    for (const fabricated of ["emailed", "posted", "sent", "delivered", "certified sent"]) {
      expect(panel).not.toContain(`>${fabricated}<`);
      expect(panel).not.toContain(`✓ ${fabricated}`);
    }
  });

  it("a read that did not answer SAYS so, rather than drawing an empty list", () => {
    // `served: false` is notifications publishing no answer at all. An empty
    // table under the heading would read as *nothing goes out to this customer*
    // — a claim, and the wrong one.
    const html = visible(reviewHtml({ served: false, results: [] }));
    expect(html).toContain("This list could not be read.");
    expect(html).not.toContain("data-editable-row=");
  });

  it("BR-CUS-059 / B18 TC-MVI-7: autopay reads as RECORDED, never as 'we will collect'", () => {
    const html = visible(reviewHtml());
    expect(html).not.toContain("we will collect");
    expect(html).not.toContain("will be collected");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE HEAD, AGAINST THE DRAWING — blueprint pages 66–74, lane A 2026-09-13
// ══════════════════════════════════════════════════════════════════════════
describe("the move-in head says how many steps there are, and which one you are on", () => {
  it("CR-171-BRC10 P2.17: no roll-up and no step line — the four-step rail says where the clerk is", () => {
    // ⚠ **REWRITTEN 2026-10-05.** These two cases asserted the *Step n of 7 ·
    // name* line under the title on every step (Accounts blueprint p071).
    // The move-in's own drawing is now images 30–47, which draw the numbered
    // rail and no step line (B14 rule 41; rule 33 — the rail already says
    // it). The COUNT still comes from the one declared list (BR-SHL-046).
    // RED-FIRST, verbatim, with the old line still drawn:
    //   AssertionError: expected '<div class="cus-page"><div class="pag…' not
    //   to contain 'Step 1 of'
    for (const index of MOVE_IN_STEPS.keys()) {
      const html = visible(
        renderWizard(`${accountMoveInPath("acc-10432")}?step=${index + 1}`, {
          detail: outgoing(),
          access: "Full",
        }),
      );
      expect(html).not.toContain("Five steps");
      expect(html).not.toContain("the account that has just left it");
      expect(html).not.toContain("Step 1 of");
      expect(html).not.toMatch(/Step \d of \d/);
      expect((html.match(/data-wizard-step=/g) ?? []).length).toBe(MOVE_IN_STEPS.length);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-004@bbed56d (story+rules snapshot — EP-CUS-02 move-in story)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — S19) · AMENDED 2026-08-25 by the CR-030 W5 R1 lane (14 cases for tasks 5.2/5.3/5.6: the two endpoints' exact paths; B18 TC-MVI-4's four assets in the four groups asserted BY POSITION; hard rule 3's consumption-with-its-unit, asserted both rendered and as the pure function; a never-read register asserted PER ROW (a whole-document check fails on the `unclassified` group's legitimate count of 0); BR-MET-100's empty unit; DEF-495's stated absence; the plan/rates/blocks/charges/taxes content; BR-RAT-038's UoM gate; the three `plan_absent` reasons each asserted to render its OWN sentence AND none of the other two; OQ-363's worked month with NO dollar figure; and the step-5 send panel's missing adapter with no fabricated status. TC-4 amended: the two meters now arrive from `GET /units/{id}/assets` instead of `AccountDetail.meters`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [CR-030 W5 R1, 2026-08-25] tsc✔ · eslint --max-warnings 0✔ · vitest this file 35 passed / 4 todo (39)✔, from 21 passed / 4 todo. ⚠ LAW 7 — SIXTEEN RED PROOFS, EACH BREAKING THE THING ITS CASE GUARDS, EACH QUOTED, EACH RESTORED, and a repo-wide grep for the mutation marker clean afterwards (DEF-666 — the marker string is deliberately NOT written out here, because a trailer quoting it trips the very grep it describes): R1 wrong assets route → `expected '/units/u-10432a/meters' to be '/units/u-10432a/assets'`; R2 wrong pricing route → `'/units/u-10432a/rates'` vs `'/units/u-10432a/pricing'`; R3 group order reversed → `expected [5401,5747,6962,8155] to deeply equal [8155,6962,5747,5401]`; R4 undeclared groups dropped → `expected ['meters'] to deeply equal ['meters','sub_meters',…]`; R5 consumption returned without its unit → `to contain '684.000000 kWh'`; R6 the never-read sentence replaced by `0` → `to contain 'No reading on record'`; R7 empty-unit sentence replaced by an error → `to contain 'Nothing is installed at this unit yet.'`; R8 `tracks` dropped → `to contain 'data-tracks="DEF-495"'`; R9 tax attachments dropped → `to contain 'PUC Regulatory Fee'`; R10 rate blocks dropped → `to contain '0.114000'`; R11 worked-month sentence replaced → `to contain 'We cannot show a worked example month…'`; R12 one shared plan_absent sentence → `to contain 'This unit is not on a rate plan yet.'`; R13 the send panel claiming both will go out → `to contain 'There is no email, text or print delivery in this release'`; R14 an `emailed` status chip → `not to contain '>emailed<'`. ⚠ R11 and R6 each fired on the FIRST assertion in their case, so the two guards that matter most were re-proved on their own: R15 kept the honest sentence and planted a summed `Typical month: $24.75` beside it → `expected … not to contain '$24.75'`; R16 kept the sentence and planted a `0` in a never-read row → `expected 'data-asset="ast-4024">…' not to match />\s*0(\.0+)?\s*</`. ORIGINAL 2026-08-11 RUN: tsc✔ · eslint --max-warnings 0✔ · vitest 702 passed / 168 todo across 51 files✔ (670 passed / 160 todo across 49 files was the pre-lane baseline — this lane adds 32 passing + 8 todo and dropped nothing) · vite build✔ · run_gates 12 PASS · 2 FAIL · 1 SKIP — and the two FAILs ARE NOT THIS LANE'S, stated rather than rounded up (hard-won law 1): G7 names six 06-backend files (db/rls_ledger_w5.sql, db/rls_notifications_w3.sql, ledger 0002_rls_w5_and_immutability.py, notifications 0002_rls_w3_outbound_queue.py …) with no human-review-ledger row, and G10 names US-BIL-023/024 · US-NOT-002/015 · US-PAY-014 with no backend TC test. All eleven belong to the W3/W5 billing·notifications·ledger lanes landing in 06-backend during this session; this lane touched no backend file. The FRONTEND half of G10 is clean (0 of the frontend-cited stories miss a test, US-CUS-004/005 included), and G13 unwired-props, G14 prototype-conformance and G15 i18n-parity (5 locales × 2466 keys, identical sets) all PASS. The pre-lane baseline for this session was 14 PASS · 0 FAIL · 1 SKIP
// exceptions: E4 TC-1's five-step walk and the commit itself need a browser (the frame's Continue is a click): every step's fields, every refusal, the exact payload and the rendered answer are asserted statically instead · E4 TC-3 (plan override → unit assignment history) cannot be asserted at all — no plan field exists because BR-CUS-029's table does not · E4 TC-5's low-initial-read refusal has no control to refuse: initial reads are metering's (BR-CUS-021) · E4 TC-7 is server/RLS scope (G5), and there is no customer search to scope
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

