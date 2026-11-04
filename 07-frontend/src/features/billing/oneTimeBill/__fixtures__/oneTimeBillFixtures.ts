/**
 * Example previews shaped exactly as contract §2 answers, built from the
 * drawing's example data (`05-prototype/one-time-bill-2026-09-30/`). Every
 * figure is an ILLUSTRATION of a shape (B14 rule 37): tests assert that a
 * served figure reaches the screen, never that the drawing's number is right.
 *
 * Shared by the component tests and the Playwright capture harness
 * (`10-scripts/one_time_bill_capture.mjs`), so both look at the same bill.
 */
import type {
  OneTimeBillAccount,
  OneTimeBillDocument,
  OneTimeBillKind,
  OneTimeBillPreview,
  OneTimeBillRateRow,
  OneTimeBillReadingRow,
  OneTimeBillServiceRow,
} from "@/api/billingOpsEndpoints";
import type { AccountRow } from "@/api/endpoints";

export const ACCOUNT_ID = "11111111-2222-3333-4444-555555555555";

export function accountRow(overrides: Partial<AccountRow> = {}): AccountRow {
  return {
    id: ACCOUNT_ID,
    account_no: "AC-2026-00042",
    customer_no: "C-0042",
    name: "Maria Alvarez",
    unit_id: "unit-1",
    unit_label: "Unit A",
    premises_id: "prem-1",
    // The live list's shape: `customers.selectors._premise_cell` already joins
    // the address and the unit label (DEF-BIL-8302).
    premise: "1408 Elm St · Unit A",
    services: ["water", "electric", "trash", "sewer"],
    balance: "142.1800",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: null,
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "regular",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2025-01-01",
    closed_at: null,
    last_bill_at: "2026-08-31",
    aging: null,
    ...overrides,
  } as AccountRow;
}

const ACCOUNT: OneTimeBillAccount = {
  id: ACCOUNT_ID,
  account_no: "AC-2026-00042",
  name: "Maria Alvarez",
  address: "1408 Elm St · Unit A",
  plan: "Residential Standard",
  status_name: "Active",
  balance: "142.1800",
  currency: "USD",
  cycle_due_days: 21,
  cycle_name: "Cycle 3 · Monthly",
  last_bill_on: "2026-08-31",
  moved_in_on: "2026-09-12",
};

const SERVICES: OneTimeBillServiceRow[] = [
  { service: "water", assets: [{ asset_id: "w1", label: "W-10442" }, { asset_id: "w2", label: "W-10443" }], status: "billed", basis_service: null, count: 2, on_bill: "per_meter_lines" },
  { service: "electric", assets: [{ asset_id: "e1", label: "E-55120" }], status: "billed_base_zero", basis_service: null, count: 1, on_bill: "usage_base_zero" },
  { service: "trash", assets: [{ asset_id: "t1", label: "1 cart · 96 gal" }], status: "billed", basis_service: null, count: 1, on_bill: "count_times_rate" },
  { service: "sewer", assets: [], status: "follows_basis", basis_service: "water", count: 1, on_bill: "percent_of_basis" },
  { service: "gas", assets: [], status: "not_in_service", basis_service: null, count: 0, on_bill: "no_line" },
  { service: "fire", assets: [], status: "not_in_service", basis_service: null, count: 0, on_bill: "no_line" },
  { service: "broadband", assets: [{ asset_id: "b1", label: "Router R-2201" }], status: "not_taken", basis_service: null, count: 1, on_bill: "no_line" },
];

const TIERS = {
  tiers: [
    { up_to: "5.000000", unit: "kgal", price: "3.2500" },
    { up_to: null, unit: "kgal", price: "4.5000" },
  ],
};

function rates(split: boolean, prorated: string | null): OneTimeBillRateRow[] {
  const versions = split
    ? [{ label: "Water v3", from: "2026-06-01" }, { label: "Water v4", from: "2026-08-15" }]
    : [{ label: "Water v4", from: "2026-08-15" }];
  return [
    { service: "water", asset_id: "w1", asset_label: "W-10442", rate_type: "tiered", usage_rate: TIERS, base_charge: { amount: "8.0000", code: "BASE-W", set: true, per_asset: false, prorated }, minimum: null, versions, amount: "29.2000" },
    { service: "water", asset_id: "w2", asset_label: "W-10443", rate_type: "tiered", usage_rate: TIERS, base_charge: { amount: "8.0000", code: "BASE-W", set: true, per_asset: false, prorated }, minimum: null, versions, amount: "21.9800" },
    { service: "electric", asset_id: "e1", asset_label: "E-55120", rate_type: "flat", usage_rate: { price: "0.1245", unit: "kWh" }, base_charge: { amount: "0.0000", code: null, set: false, per_asset: false, prorated: null }, minimum: null, versions: [{ label: "Electric v7", from: "2026-01-01" }], amount: "75.9400" },
    { service: "trash", asset_id: "t1", asset_label: "1 cart", rate_type: "per_asset", usage_rate: { price: "15.0000", unit: "cart" }, base_charge: { amount: "3.0000", code: "BASE-T", set: true, per_asset: true, prorated: null }, minimum: null, versions: [{ label: "Trash v2", from: "2026-01-01" }], amount: "18.0000" },
    { service: "sewer", asset_id: null, asset_label: null, rate_type: "percent_of_service", usage_rate: { percent: "40.000000", basis_service: "water" }, base_charge: { amount: "6.0000", code: "BASE-S", set: true, per_asset: false, prorated }, minimum: "10.0000", versions: [{ label: "Sewer v3", from: "2026-01-01" }], amount: "20.0700" },
    { service: "gas", asset_id: null, asset_label: null, rate_type: null, usage_rate: null, base_charge: null, minimum: null, versions: [], amount: "0.0000" },
    { service: "fire", asset_id: null, asset_label: null, rate_type: null, usage_rate: null, base_charge: null, minimum: null, versions: [], amount: "0.0000" },
  ];
}

function readingRows(kind: OneTimeBillKind): OneTimeBillReadingRow[] {
  const meters = [
    { asset_id: "w1", label: "W-10442", unit: "kgal", prev: "482.3", cur: "488.4", use: "6.1" },
    { asset_id: "w2", label: "W-10443", unit: "kgal", prev: "130.6", cur: "134.9", use: "4.3" },
    { asset_id: "e1", label: "E-55120", unit: "kWh", prev: "18420", cur: "19030", use: "610" },
  ];
  if (kind === "backbill" || kind === "penalty") {
    const out: OneTimeBillReadingRow[] = [];
    const periods = [
      ["2026-06-01", "2026-06-30"],
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
    ];
    periods.forEach(([start, end], index) => {
      for (const meter of meters) {
        const last = index === periods.length - 1;
        out.push({
          asset_id: meter.asset_id,
          label: meter.label,
          unit: meter.unit,
          previous: { value: meter.prev, read_at: start, on_file: true },
          current: { value: kind === "backbill" && last ? null : meter.cur, read_at: end, fixed_date: false },
          usage: kind === "backbill" && last ? null : meter.use,
          status: kind === "penalty" ? "assessed" : last ? "waiting" : index === 1 && meter.asset_id === "w2" ? "estimated" : "actual",
          refusal_key: null,
          period_index: index,
        });
      }
    });
    return out;
  }
  return meters.map((meter) => ({
    asset_id: meter.asset_id,
    label: meter.label,
    unit: meter.unit,
    previous:
      kind === "first" && meter.asset_id === "w2"
        ? { value: null, read_at: null, on_file: false }
        : { value: meter.prev, read_at: kind === "first" ? "2026-09-12" : "2026-08-31", on_file: true },
    current: { value: null, read_at: kind === "final" ? "2026-09-18" : "2026-09-30", fixed_date: kind === "final" },
    usage: null,
    status: "waiting",
    refusal_key: null,
    period_index: null,
  }));
}

function bill(kind: OneTimeBillKind): OneTimeBillDocument {
  if (kind === "fee") {
    return {
      groups: [
        {
          label: "charges",
          period_start: null,
          period_end: null,
          subtotal: "75.0000",
          lines: [{ service: "Reconnection fee", asset_label: null, charge: "fee", quantity: "1", unit: null, rate: "75.0000", amount: "75.0000", flags: [] }],
        },
      ],
      subtotal: "75.0000",
      tax: [{ label: "Utility tax", rate: "2.000000", amount: "1.5000" }],
      total: "76.5000",
      currency: "USD",
    };
  }
  const lines = [
    { service: "water", asset_label: "W-10442", charge: "usage" as const, quantity: "6.1", unit: "kgal", rate: "tiered", amount: "21.2000", flags: [] },
    { service: "water", asset_label: "W-10442", charge: "base" as const, quantity: "1", unit: null, rate: "8.0000", amount: "8.0000", flags: [] },
    { service: "water", asset_label: "W-10443", charge: "usage" as const, quantity: "4.3", unit: "kgal", rate: "tiered", amount: "13.9800", flags: kind === "backbill" ? ["estimated"] : [] },
    { service: "water", asset_label: "W-10443", charge: "base" as const, quantity: "1", unit: null, rate: "8.0000", amount: "8.0000", flags: [] },
    { service: "electric", asset_label: "E-55120", charge: "usage" as const, quantity: "610", unit: "kWh", rate: "0.1245", amount: "75.9400", flags: [] },
    { service: "trash", asset_label: "1 cart", charge: "per_asset" as const, quantity: "1", unit: "cart", rate: "15.0000", amount: "15.0000", flags: [] },
    { service: "trash", asset_label: "1 cart", charge: "base" as const, quantity: "1", unit: null, rate: "3.0000", amount: "3.0000", flags: [] },
    { service: "sewer", asset_label: null, charge: "percent" as const, quantity: "35.18", unit: null, rate: "40.000000", amount: "14.0700", flags: [] },
    { service: "sewer", asset_label: null, charge: "base" as const, quantity: "1", unit: null, rate: "6.0000", amount: "6.0000", flags: [] },
    { service: "electric", asset_label: "E-55120", charge: "base" as const, quantity: null, unit: null, rate: null, amount: "0.0000", flags: ["base_not_set"] },
  ];
  const groups: OneTimeBillDocument["groups"] = [
    { label: "Sep 1 – Sep 30", period_start: "2026-09-01", period_end: "2026-09-30", subtotal: "165.1900", lines },
  ];
  if (kind === "first") {
    groups.push({
      label: "Move-in charges",
      period_start: null,
      period_end: null,
      subtotal: "195.0000",
      lines: [
        { service: "Security deposit", asset_label: null, charge: "deposit", quantity: "1", unit: null, rate: "150.0000", amount: "150.0000", flags: [] },
        { service: "Connection charge", asset_label: null, charge: "fee", quantity: "1", unit: null, rate: "45.0000", amount: "45.0000", flags: [] },
      ],
    });
  }
  return {
    groups,
    subtotal: kind === "first" ? "360.1900" : "165.1900",
    tax: [{ label: "Utility tax", rate: "2.000000", amount: "3.3000" }],
    total: kind === "first" ? "363.4900" : "168.4900",
    currency: "USD",
  };
}

/** A preview for one kind, sections `null` where the kind has none (§2). */
export function previewFor(kind: OneTimeBillKind, overrides: Partial<OneTimeBillPreview> = {}): OneTimeBillPreview {
  const perPeriod = kind === "backbill" || kind === "penalty";
  return {
    kind,
    account: ACCOUNT,
    defaults: { bill_date: "2026-09-30", due_days: 21 },
    due_date: "2026-10-21",
    services: kind === "fee" ? null : SERVICES,
    rates: kind === "fee" ? null : rates(perPeriod, kind === "final" ? "18/30" : null),
    readings:
      kind === "fee"
        ? null
        : {
            needed:
              kind === "interim"
                ? "every_meter"
                : kind === "first"
                  ? "move_in_and_new"
                  : kind === "final"
                    ? "final"
                    : kind === "backbill"
                      ? "last_period"
                      : "none",
            rows: readingRows(kind),
          },
    periods: perPeriod
      ? [
          { period_start: "2026-06-01", period_end: "2026-06-30", days: 30, versions: ["Water v3", "Elec v7"], reading: kind === "penalty" ? "assessed" : "actual", split_on: null },
          { period_start: "2026-07-01", period_end: "2026-07-31", days: 31, versions: ["Water v3", "Elec v7"], reading: kind === "penalty" ? "assessed" : "estimated", split_on: null },
          { period_start: "2026-08-01", period_end: "2026-08-31", days: 31, versions: ["Water v3 → v4", "Elec v7"], reading: kind === "penalty" ? "assessed" : "actual", split_on: "2026-08-15" },
        ]
      : null,
    move_in_charges:
      kind === "first"
        ? {
            moved_in_on: "2026-09-12",
            deposit_asked: "150.0000",
            deposit_paid: "0.0000",
            lines: [
              { kind: "deposit", label: "Security deposit", amount: "150.0000" },
              { kind: "fee", code: "CONN", label: "Connection charge", amount: "45.0000" },
            ],
          }
        : null,
    settlement:
      kind === "final"
        ? {
            this_bill: "152.1700",
            prior_balance: "142.1800",
            deposit: "100.0000",
            interest: "1.2400",
            remainder: "193.1100",
            automatic: null,
            paths: ["collect", "payment_plan", "transfer"],
          }
        : null,
    charge:
      kind === "fee"
        ? { code: "RECON", label: "Reconnection fee", amount: "75.0000", taxable: true }
        : kind === "penalty"
          ? { code: "TAMPER", label: "Tamper charge", amount: "250.0000", taxable: false }
          : null,
    bill: bill(kind),
    warnings: kind === "fee" ? [] : [{ key: "billing.oneTime.warn.baseNotSet", params: { service: "Electric" } }],
    duplicate: null,
    ...overrides,
  };
}
