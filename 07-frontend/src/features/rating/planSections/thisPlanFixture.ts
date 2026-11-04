// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-9821 — the approved drawing's plan, as `GET /plans/{id}`
//           serves it, for the This-plan block's tests (the block's own file
//           and New Connect step 2's).
// ───────────────────────────────────────────────────────
//
// THE DRAWING'S OWN FIGURES (claude.ai/artifact/9poRZzcU1ooxCw9A78jXgy):
// *Municipal Solar PV & Battery Service Plan*, MBSP v1, Published, from
// 10/01/2026. Solar names BASE-SOL ($10.00, Residential); Battery's schedule
// names NO base code and none serves it. Battery's blocks are unit prices to
// four places. LATE 1.50% min $5.00 with 5 calendar days' grace; CONN $25.00;
// DEPOSIT Residential $150.00 / Commercial $300.00; two taxes, 8.00% combined;
// three discounts. Read THROUGH the normaliser, so a test reads what the screen
// reads.
import type { PlanDetail } from "@/api/endpoints";
import { normalisePlanSections } from "@/api/planFormEndpoints";
import type { PlanSections } from "@/api/planFormEndpoints";

export const DRAWN_PLAN_ID = "11111111-2222-4333-8444-555555555555";

function ref(id: string, kind: string, code: string, name: string, version: number | null, from: string | null) {
  return { id, kind, code, name, version, version_label: null, effective_from: from, effective_to: null, next: null };
}

export const DRAWN_RAW = {
  id: DRAWN_PLAN_ID,
  code: "MBSP",
  name: "Municipal Solar PV & Battery Service Plan",
  status: "published",
  version: 1,
  effective_from: "2026-10-01",
  effective_to: null,
  account_type_ids: [],
  currency: "USD",
  details: {
    name: "Municipal Solar PV & Battery Service Plan",
    code: "MBSP",
    customer_classes: [],
    description: null,
    intended_for: { cap_proof: false, min_demand_25kw: false, owner_occupied: false },
    notes: [],
    minimum_bill_display: null,
    budget_billing: false,
  },
  services: [
    {
      service: "solar",
      name: "Solar",
      gl: null,
      schedule: {
        ...ref("sch-sol", "schedule", "", "Bryant Solar and Battery Service Pilot Rate", 1, "2026-10-01"),
        model: "capacity",
        model_label: "Capacity",
      },
      base: {
        code: ref("bc-sol", "base_code", "BASE-SOL", "Solar base", 1, "2026-10-01"),
        sized_by_label: null,
        by_size: [],
        flat_display: "10.00",
        state: "ok",
        codes: ["BASE-SOL"],
        options: [],
        monthly_amount: "10.0000",
        named: true,
        classes: ["Residential"],
      },
      minimum: { by_size: [], flat_display: null },
      usage: {
        kind: "per_count",
        kind_label: "Per item, per month",
        rows: [{ label: "kW", rate_display: "$14.00", label_key: null, rate_amount: "$14.00", rate_unit: null }],
      },
      outside_city: { surcharged: false, percent_display: null },
    },
    {
      service: "battery",
      name: "Battery",
      gl: null,
      schedule: {
        ...ref("sch-bat", "schedule", "", "Municipal Battery Service Rate", 1, "2026-10-01"),
        model: "tiered",
        model_label: "Tiered",
      },
      base: {
        code: null,
        sized_by_label: null,
        by_size: [],
        flat_display: null,
        state: "none",
        codes: [],
        options: [],
        monthly_amount: null,
        named: false,
        classes: [],
      },
      minimum: { by_size: [], flat_display: null },
      usage: {
        kind: "blocks",
        kind_label: "Block (per month)",
        rows: [
          { label: "0 kWh – 500 kWh", rate_display: "$0.0425 per kWh", label_key: null, rate_amount: "$0.0425", rate_unit: "kWh" },
          { label: "Over 500 kWh", rate_display: "$0.039 per kWh", label_key: "over", label_args: { qty: "500 kWh" }, rate_amount: "$0.039", rate_unit: "kWh" },
        ],
      },
      outside_city: { surcharged: false, percent_display: null },
    },
  ],
  base_total: { amount_display: null, unavailable: "battery:none" },
  outside_city_surcharge: null,
  charge_codes: [
    {
      ref: ref("ch-late", "charge_code", "LATE", "Late payment fee", 1, null),
      late_fee: true,
      grace: { days: 5, mode: "calendar", from: "charge_code" },
      priced_by: "percent",
      rows: [{ class_or_size_label: "Everyone", everyone: true, amount_display: null, percent_display: "1.50%", min_display: "5.00" }],
      gl: null,
      type_label: "penalty",
      when_label: "After the due date",
    },
    {
      ref: ref("ch-conn", "charge_code", "CONN", "Connection fee", 1, "2026-10-01"),
      late_fee: false,
      grace: null,
      priced_by: "one_amount",
      rows: [{ class_or_size_label: "Everyone", everyone: true, amount_display: "25.00", percent_display: null, min_display: null }],
      gl: null,
      type_label: "one_time",
      when_label: "Once",
    },
  ],
  taxes: [
    {
      ref: ref("tx-state", "tax", "", "State sales tax", 1, "2026-01-01"),
      rate_display: "6.00%",
      rate_percent: "6.000000",
      what_is_taxed_label: "Usage and base charges",
      what_is_taxed: ["usage", "base"],
      gl: null,
      authority: "State of Michigan",
      brought_by: "attached",
      reaches_plan_classes: "all",
      customer_classes: [],
    },
    {
      ref: ref("tx-city", "tax", "", "City utility tax", 1, "2026-01-01"),
      rate_display: "2.00%",
      rate_percent: "2.000000",
      what_is_taxed_label: "Usage charges",
      what_is_taxed: ["usage"],
      gl: null,
      authority: "City of Ann Arbor",
      brought_by: "attached",
      reaches_plan_classes: "all",
      customer_classes: ["Residential", "Commercial"],
    },
  ],
  combined_tax_rate_display: "8.00%",
  deposits: [
    {
      ref: ref("dep", "deposit_code", "DEPOSIT", "Security deposit", 1, "2026-10-01"),
      priced_by: "class",
      rows: [
        { class_or_size_label: "Residential", everyone: false, amount_display: "150.00" },
        { class_or_size_label: "Commercial", everyone: false, amount_display: "300.00" },
      ],
      gl: null,
      refundable: true,
    },
  ],
  discounts: [
    {
      ref: ref("ds-cap", "discount", "CAP", "CAP / low-income credit", 1, "2026-01-01"),
      value_display: "10%",
      gl: null,
      enrolled: 0,
      offered_from: null,
      offered_until: null,
      enrolment_mode: "apply_and_approve",
      proof_required: true,
    },
    {
      ref: ref("ds-auto", "discount", "AUTOPAY", "Autopay", 1, "2026-01-01"),
      value_display: "$1.00",
      gl: null,
      enrolled: 0,
      offered_from: null,
      offered_until: null,
      enrolment_mode: "automatic",
      proof_required: false,
    },
  ],
};

export const DRAWN_DETAIL = DRAWN_RAW as unknown as PlanDetail;
export const DRAWN_SECTIONS: PlanSections = normalisePlanSections(DRAWN_RAW);
