// CR-167-BRC10 round 2 task 5 — `GET /plans/form-options` as the agreed
// contract (§7.3) serves it, for the form's tests. Test-only; nothing in the
// product imports it.
function ref(id: string, kind: string, code: string, name: string, version: number, from: string) {
  return { id, kind, code, name, version, version_label: null, effective_from: from, effective_to: null, next: null };
}

export const FORM_OPTIONS = {
  currency: "USD",
  customer_classes: [
    { value: "cls-res", label: "Residential" },
    { value: "cls-com", label: "Commercial" },
  ],
  services: [
    { value: "water", label: "Water", gl: { code: "4110", name: "Water revenue" } },
    { value: "sewer", label: "Sewer", gl: { code: "4120", name: "Sewer revenue" } },
  ],
  schedules: [
    {
      ref: { ...ref("sch-w", "schedule", "RW", "Residential water", 4, "2026-09-30"), model: "tiered", model_label: "Tiered" },
      service: "water",
      base: {
        code: ref("bc-w1", "base_code", "BASE-W1", "Water base", 2, "2026-09-01"),
        sized_by_label: "meter size",
        by_size: [
          { size_class: "5_8", size_label: '5/8"', amount_display: "10.00" },
          { size_class: "1", size_label: '1"', amount_display: "18.00" },
        ],
        flat_display: null,
        state: "ok",
        codes: ["BASE-W1"],
        monthly_amount: "10.0000",
      },
      minimum: { by_size: [], flat_display: "5.00" },
      usage: { kind: "blocks", kind_label: "Block (per month)", rows: [{ label: "0 – 5 kgal", rate_display: "$4.24 per kgal" }] },
    },
    {
      ref: { ...ref("sch-s", "schedule", "SF", "Sewer flat rate", 3, "2026-09-28"), model: "flat", model_label: "Flat" },
      service: "sewer",
      base: {
        code: ref("bc-s", "base_code", "BASE-S", "Sewer base", 1, "2026-08-01"),
        sized_by_label: null,
        by_size: [],
        flat_display: "9.00",
        state: "ok",
        codes: ["BASE-S"],
        monthly_amount: "9.0000",
      },
      minimum: { by_size: [], flat_display: null },
      usage: { kind: "flat", kind_label: null, rows: [{ label: "Each month", rate_display: "$14.00 flat" }] },
    },
  ],
  charge_codes: [
    {
      ref: ref("cc-late", "charge_code", "LATE", "Late payment fee", 1, "2026-08-01"),
      priced_by: "class",
      rows: [{ class_or_size_label: "Residential", amount_display: null, percent_display: "1.50%", min_display: "5.00" }],
      gl: { code: "2610", name: "Late fees" },
      type_label: "penalty", // the server serves the stored type (DEF-RAT-9356)
      when_label: "After the due date",
      default_on_new_plan: true,
    },
    {
      ref: ref("cc-recon", "charge_code", "RECON", "Reconnection fee", 2, "2026-09-15"),
      priced_by: "one_amount",
      rows: [{ class_or_size_label: "", amount_display: "75.00", percent_display: null, min_display: null }],
      gl: { code: "4310", name: "Service fees" },
      type_label: "one_time",
      when_label: "On reconnection",
      default_on_new_plan: false,
    },
  ],
  taxes: [
    {
      ref: ref("tx-state", "tax", "TX-STATE", "TX State Utility Tax", 1, "2026-01-01"),
      rate_display: "6.25%",
      rate_percent: "6.250000",
      what_is_taxed_label: "Usage and base charges",
      gl: { code: "2200-02", name: "Tax payable · State" },
      authority: "Texas Comptroller",
      brought_by: "attached",
    },
    {
      ref: ref("tx-bexar", "tax", "BEXAR", "Bexar County", 3, "2026-01-01"),
      rate_display: "2%",
      rate_percent: "2.000000",
      what_is_taxed_label: "Usage and base charges",
      gl: { code: "2200-01", name: "Tax payable · Local" },
      authority: null,
      brought_by: "attached",
    },
  ],
  deposit_codes: [
    {
      ref: ref("dep-1", "deposit_code", "DEPOSIT", "Security deposit", 2, "2026-09-01"),
      priced_by: "class",
      rows: [
        { class_or_size_label: "Residential", amount_display: "150.00", percent_display: null, min_display: null },
        { class_or_size_label: "Commercial", amount_display: "300.00", percent_display: null, min_display: null },
      ],
      gl: { code: "2300", name: "Deposits held" },
    },
  ],
  discounts: [
    {
      ref: ref("disc-senior", "discount", "SENIOR", "Senior discount", 1, "2026-08-01"),
      value_display: "15%",
      gl: { code: "4760", name: "Customer discounts" },
      enrolled: 12,
      offered_from: null,
      offered_until: null,
    },
  ],
};

