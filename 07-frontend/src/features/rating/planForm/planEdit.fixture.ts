// CR-167-BRC10 round 3 task 8 — `GET /plans/{id}` for a published plan, in the
// shape the server built at 2.484.0 answers (read off PostgreSQL 16 for
// `SCW-RES`, then filled with ids the form-options fixture also serves).
// Test-only; nothing in the product imports it.
import { FORM_OPTIONS } from "./planFormOptions.fixture";

const [water, sewer] = FORM_OPTIONS.schedules;
const [late, recon] = FORM_OPTIONS.charge_codes;
const [state, bexar] = FORM_OPTIONS.taxes;

export const PLAN_ID = "p-rcp";

export const PUBLISHED_PLAN = {
  id: PLAN_ID,
  code: "RCP",
  name: "Residential City Plan",
  status: "published",
  version: 1,
  minimum_bill_amount: "10.0000",
  outside_city_percent: "25.000000",
  effective_from: "2026-09-01",
  effective_to: null,
  accounts: 5,
  currency: "USD",
  plan_version: { version: 1, status: "in_force", effective_from: "2026-09-01", effective_to: null, reason: null },
  versions: [{ version: 1, version_no: 1, status: "in_force", effective_from: "2026-09-01", effective_to: null }],
  details: {
    name: "Residential City Plan",
    code: "RCP",
    customer_classes: [{ value: "cls-res", label: "Residential" }],
    description: "Water and sewer for homes inside the city.",
    intended_for: { cap_proof: false, min_demand_25kw: false, owner_occupied: false },
    notes: [{ attribute: "customer_class", operator: "is", value: "Residential", value_label: "Residential" }],
    minimum_bill_display: "10.00",
    budget_billing: false,
  },
  services: [
    {
      service: "water",
      name: "Water",
      gl: { code: "4110", name: "Water revenue" },
      schedule: water?.ref,
      base: water?.base,
      minimum: water?.minimum,
      usage: water?.usage,
      outside_city: { surcharged: true, percent_display: "25.00%" },
    },
    {
      service: "sewer",
      name: "Sewer",
      gl: { code: "4120", name: "Sewer revenue" },
      schedule: sewer?.ref,
      base: sewer?.base,
      minimum: sewer?.minimum,
      usage: sewer?.usage,
      outside_city: { surcharged: false, percent_display: null },
    },
  ],
  base_total: { amount_display: "19.00", unavailable: null },
  outside_city_surcharge: { percent_display: "25.00%", service_names: ["Water"] },
  charge_codes: [
    { ...late, late_fee: true },
    { ...recon },
  ],
  // Both taxes reach this plan through its JURISDICTION — re-sent as `{tax}`
  // they would become attachments, so an untouched save must not send them.
  taxes: [
    { ...state, brought_by: "jurisdiction" },
    { ...bexar, brought_by: "jurisdiction" },
  ],
  combined_tax_rate_display: "8.25%",
  deposits: [FORM_OPTIONS.deposit_codes[0]],
  discounts: [{ ...FORM_OPTIONS.discounts[0], offered_from: "2026-09-01", offered_until: "2026-10-31" }],
};

export const DRAFT_PLAN = {
  ...PUBLISHED_PLAN,
  id: "p-draft",
  status: "draft",
  plan_version: null,
  versions: [],
  effective_from: null,
};
