// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-009 (Taxes & fees) — test support only, never shipped code.
// Rules:    BR-RAT-103 (the four statuses + `active`) · BR-RAT-106 (discount
//           treatment defaults to the engine's own behaviour)
// ───────────────────────────────────────────────────────
/**
 * ONE default `TaxRow`, so six test files stop each holding their own copy of
 * the contract.
 *
 * ── WHY THIS EXISTS (CR-013 P4, 2026-08-21) ─────────────────────────────────
 * `TaxRow` gained twenty fields when the tax data model landed
 * (DEF-380/382/383/384/385/387), and SIX test files each built a complete
 * literal of it: `ChargesTaxes`, `DefinitionDetail`, `PlanDetail`,
 * `PlanWizard`, `TaxWizard` and `SettingsAccountingTab`. Every one of them went
 * red on the same day for the same reason — not because anything they test
 * changed, but because each was a hand-maintained copy of a contract that is
 * declared once in `endpoints.ts`.
 *
 * That is the same shape as the defects this repo keeps filing about second
 * homes for one fact. So the shared half lives here and each fixture spreads
 * it and overrides only what its own case is ABOUT — which is also what makes
 * those files readable: what is left in each literal is the thing under test.
 *
 * ⚠ **NOT A FACTORY WITH CLEVER DEFAULTS.** Every value below is the neutral
 * one — the state a tax is in when nobody has said anything: no code, no bill
 * label, no exemption categories, `active` and in force, and
 * `discount_treatment: "after"`, which is what a tax carries when nobody has
 * stated an answer (BR-RAT-650, the PO's ruling of 2026-08-27 — the utility
 * remits tax on the full service value). ⚠ IT READ `"before"` UNTIL 2026-08-28
 * and the docstring above is exactly why it had to move: this file claims every
 * value here is the NEUTRAL one, so a fixture left on the old default would
 * have gone on asserting a neutral state the product no longer has. A fixture
 * whose defaults were interesting would make tests pass for reasons their
 * authors never wrote down.
 */
import type { TaxRow } from "@/api/endpoints";

export function taxRowDefaults(): Omit<
  TaxRow,
  "id" | "name" | "jurisdiction" | "kind" | "rate" | "rate_display"
> {
  return {
    base_includes_usage: true,
    base_includes_base: true,
    flat_amount: null,
    flat_frequency: null,
    per_unit_amount: null,
    per_unit_uom: null,
    per_meter_amount: null,
    per_meter_amount_display: null,
    applies_above_units: null,
    applies_to_services: [],
    applies_to_customer_classes: [],
    premises_scope_kind: null,
    premises_scope_value: null,
    liability_gl_account_id: null,
    remit_to: null,
    filing_frequency: null,
    filing_form: null,
    effective_from: null,
    effective_to: null,
    // BR-RAT-103 — the lifecycle. `active`/`in_force` are the neutral pair: a
    // tax nobody has deactivated, drafted, scheduled or expired.
    status: "active",
    active: true,
    in_force: true,
    // DEF-385 — recorded by nobody, which is the state every existing row is in.
    code: null,
    bill_label: null,
    tax_type: null,
    rounding_rule: null,
    due_date_rule: null,
    remit_method: null,
    remit_reference: null,
    collection_allowance_percent: null,
    collection_allowance_percent_display: null,
    collection_allowance_gl_account_id: null,
    interest_penalty_percent: null,
    interest_penalty_percent_display: null,
    interest_penalty_basis: null,
    filing_reminder_recipient: null,
    // BR-RAT-650 — the ruled answer, never null. A tax that says nothing levies
    // on the full service value; `before` is still lawful and still per tax.
    discount_treatment: "after",
    // DEF-384 — not a correction and not corrected.
    corrects_tax_id: null,
    superseded_by_tax_id: null,
    correction_reason: null,
    exemption_category_count: 0,
    used_by_plans: 0,
  };
}
