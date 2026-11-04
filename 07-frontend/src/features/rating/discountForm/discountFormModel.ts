// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — the New discount form, built from
//           images 05–18 of `05-prototype/discounts-2026-10-03/images/`.
// Defects:  DEF-RAT-9289 (D1–D13, the form)
// Rules:    PO 2026-10-03 — three one-word steps *Details · Eligibility ·
//           Review*, all of today's boxes kept on the decision-log map ·
//           *"Currency - it is default of utility - user cannot change it"* ·
//           ruling 3: a *customer shows proof* condition cannot be Automatic ·
//           BR-RAT-087 (a discount's percentage is stored in percentage POINTS)
//           · CLAUDE.md hard rule 2 (money is a decimal string, never a float)
// ───────────────────────────────────────────────────────
//
// THE PURE HALF OF THE FORM — no React, so every rule below is a unit test.
//
// ⚠ **A DISCOUNT'S PERCENT IS NOT CONVERTED, AND THAT IS THE OPPOSITE OF
// TAXES.** `discount_versions.value` holds percentage POINTS
// (`selectors.discount_value_display`: *"`percentage` -> percentage points
// (`15` -> `15.00%`)"*), while a tax rate holds a fraction. So the clerk types
// `15`, the wire carries `"15"`, and the bill takes 15 %. Borrowing the tax
// form's `percentToFraction` here would store `0.15` — a 0.15 % discount —
// and every test that only round-trips the screen would pass.
import { scaledAmount, unscaledAmount } from "@/components/moneyMath";

import type { DiscountEligibilityOption, DiscountFormOption } from "@/api/discountFormEndpoints";

// ── The codes the form BRANCHES on ─────────────────────────────────────────
// The LISTS a clerk picks from are the server's (`GET /discounts/form-options`);
// these are only the values a box's shape depends on, as `BASIS_PERCENT` is
// for taxes. A value the server adds later is offered and saved; it simply
// draws no special box.

export const TYPE_PERCENTAGE = "percentage";
export const TYPE_FIXED = "fixed_amount";
export const TYPE_RATE_OVERRIDE = "rate_override";
export const TYPE_WAIVER = "charge_waiver";
export const TYPE_ALLOWANCE = "usage_allowance";

/**
 * The types a clerk may CHOOSE — the server's list less *Usage allowance*.
 *
 * PO ruling 2026-10-03 (decision log, *"A USAGE ALLOWANCE IS NOT OFFERED ON
 * THE NEW DISCOUNT FORM UNTIL 'FREE UNITS BEFORE PRICING' IS BUILT"*, option
 * b): `BR-RAT-962` keeps the type unpriceable, so one saved now could never go
 * live. The server still SERVES the type in `form-options`, because a draft
 * saved before the ruling must still read its own type; it refuses a new one
 * by name (`rating.discounts.usage_allowance_not_offered`). When the step is
 * built, this filter goes.
 */
export function offeredTypes<T extends { value: string }>(types: readonly T[]): T[] {
  return types.filter((option) => option.value !== TYPE_ALLOWANCE);
}

export const SCOPE_WHOLE_BILL = "whole_bill";
export const SCOPE_ALL_SERVICES = "all_services";
export const SCOPE_BASE_ONLY = "base_only";
export const SCOPE_USAGE_ONLY = "usage_only";
export const SCOPE_ONE_SERVICE = "one_service";
export const SCOPE_SPECIFIC_SERVICES = "specific_services";
export const SCOPE_NAMED_CODES = "named_codes";

export const ENROLLMENT_AUTOMATIC = "automatic";

/** The exclusivity group meaning "in no group" — the drawn list's *None*.
 *  An empty value means the same. */
export const EXCLUSIVITY_NONE = "none";

// ── The draft ──────────────────────────────────────────────────────────────

/** Every value is a STRING or a boolean, start to finish (hard rule 2). */
export interface DiscountFormDraft {
  // Details · Basics
  code: string;
  name: string; // the bill line label
  program_owner: string;
  funding_source: string;
  report_in_assistance_filing: boolean;
  discount_type: string;
  // Details · Value
  value: string; // percent POINTS, dollars or units, as typed
  rate_schedule: string; // drawn (image 08); BR-RAT-961 gives it no column
  applies_to: string;
  applies_to_service: string;
  applies_to_services: string[];
  applies_to_charge_codes: string[];
  // Details · Limits
  cap_per_bill: string;
  cap_per_year: string;
  cap_lifetime: string;
  bill_floor_amount: string;
  stacking_precedence: string;
  stacks_with_others: boolean;
  exclusivity_group: string;
  // Eligibility · Who qualifies
  eligibility: string;
  enrolment_mode: string;
  verification_method: string;
  proof_before_first_reduction: boolean;
  recertification_months: string;
  recertification_notice_days: string;
  recertification_grace_days: string;
  lapse_behaviour: string;
  // Eligibility · Dates and budget
  effective_from: string;
  effective_to: string;
  budget_cap: string;
  budget_period: string;
  exhaustion_behaviour: string;
}

export function emptyDiscountFormDraft(): DiscountFormDraft {
  return {
    code: "",
    name: "",
    program_owner: "",
    funding_source: "",
    report_in_assistance_filing: false,
    discount_type: "",
    value: "",
    rate_schedule: "",
    applies_to: "",
    applies_to_service: "",
    applies_to_services: [],
    applies_to_charge_codes: [],
    cap_per_bill: "",
    cap_per_year: "",
    cap_lifetime: "",
    bill_floor_amount: "",
    stacking_precedence: "",
    stacks_with_others: true,
    exclusivity_group: "",
    eligibility: "",
    enrolment_mode: "",
    verification_method: "",
    proof_before_first_reduction: false,
    recertification_months: "",
    recertification_notice_days: "",
    recertification_grace_days: "",
    lapse_behaviour: "",
    effective_from: "",
    effective_to: "",
    budget_cap: "",
    budget_period: "",
    exhaustion_behaviour: "",
  };
}

export interface DiscountListsForDefaults {
  types: readonly DiscountFormOption[];
  applies_to: readonly DiscountFormOption[];
  enrollment_modes: readonly DiscountFormOption[];
  verification: readonly DiscountFormOption[];
  lapse: readonly DiscountFormOption[];
  budget_periods: readonly DiscountFormOption[];
  budget_out: readonly DiscountFormOption[];
  exclusivity_groups: readonly DiscountFormOption[];
}

/** Fill each list's first value the first time it arrives. Never overwrites a
 *  choice already made — nothing typed is lost. Program owner and who
 *  qualifies open on *Choose* (image 13): they have no default. The
 *  exclusivity group opens on the list's first row (*None*, image 06), because
 *  a select with no empty option SHOWS its first row — leaving the draft empty
 *  under it would make Review say *—* over a box that reads *None*. */
export function withListDefaults(draft: DiscountFormDraft, lists: DiscountListsForDefaults): DiscountFormDraft {
  const next = { ...draft };
  const first = (field: keyof DiscountFormDraft, list: readonly DiscountFormOption[]) => {
    if (next[field] === "" && list.length > 0) {
      (next as Record<string, unknown>)[field] = list[0].value;
    }
  };
  first("discount_type", offeredTypes(lists.types));
  first("applies_to", lists.applies_to);
  first("enrolment_mode", lists.enrollment_modes);
  first("verification_method", lists.verification);
  first("lapse_behaviour", lists.lapse);
  first("budget_period", lists.budget_periods);
  first("exhaustion_behaviour", lists.budget_out);
  first("exclusivity_group", lists.exclusivity_groups);
  return next;
}

/** Until the server's type list arrives there is nothing to branch on; a
 *  percent box is what the drawing opens on (image 05). */
export function effectiveType(draft: DiscountFormDraft): string {
  return draft.discount_type === "" ? TYPE_PERCENTAGE : draft.discount_type;
}

/** The kind of box the Value section draws for a type. */
export type ValueBox = "percent" | "money" | "units" | "schedule" | "whole";

export function valueBoxFor(discountType: string): ValueBox {
  if (discountType === TYPE_FIXED) return "money";
  if (discountType === TYPE_ALLOWANCE) return "units";
  if (discountType === TYPE_RATE_OVERRIDE) return "schedule";
  if (discountType === TYPE_WAIVER) return "whole";
  return "percent";
}

/** Whether the chosen *Who qualifies* is a proof condition. Unknown or none
 *  chosen is `false` — nothing is refused on a guess. */
export function isProofCondition(draft: DiscountFormDraft, eligibility: readonly DiscountEligibilityOption[]): boolean {
  return eligibility.find((row) => row.value === draft.eligibility)?.checked_by === "proof";
}

/**
 * RULING 3 (PO 2026-10-03): *"A 'customer shows proof' condition cannot be
 * Automatic."* `BR-RAT-076`'s refused combination, in the new words. The
 * enrollment list draws Automatic DISABLED under a proof condition, and a
 * draft already holding the pair is a gap on the Enrollment box — the form
 * never silently changes a choice the clerk made.
 */
export function automaticRefused(draft: DiscountFormDraft, eligibility: readonly DiscountEligibilityOption[]): boolean {
  return draft.enrolment_mode === ENROLLMENT_AUTOMATIC && isProofCondition(draft, eligibility);
}

// ── Limits ─────────────────────────────────────────────────────────────────

/** How many limits are set — the closed section's *N set* (image 07). The
 *  stacking order and the stacks-with tick always hold something, so they are
 *  order, not limits, and are not counted. */
export function limitsSetCount(draft: DiscountFormDraft): number {
  const money = [draft.cap_per_bill, draft.cap_per_year, draft.cap_lifetime, draft.bill_floor_amount].filter(
    (raw) => raw.trim() !== "",
  ).length;
  const group = draft.exclusivity_group !== "" && draft.exclusivity_group !== EXCLUSIVITY_NONE ? 1 : 0;
  return money + group;
}

// ── Validation ─────────────────────────────────────────────────────────────

const MONEY_RE = /^\d{1,9}(\.\d{1,4})?$/;
/** Percentage points: stored to six places (hard rule 2). */
const PERCENT_RE = /^\d{1,3}(\.\d{1,6})?$/;
const UNITS_RE = /^\d{1,9}(\.\d{1,4})?$/;
const WHOLE_RE = /^\d{1,4}$/;

export function percentOver100(typed: string): boolean {
  const text = typed.trim();
  return PERCENT_RE.test(text) && scaledAmount(text, 6) > scaledAmount("100", 6);
}

export type DiscountStepId = "details" | "eligibility" | "review";

/** WHICH boxes on a step are wrong — box id → catalogue key. PRESENCE and SHAPE
 *  only; every rule about money stays the server's. */
export function stepGaps(
  stepId: DiscountStepId,
  draft: DiscountFormDraft,
  eligibility: readonly DiscountEligibilityOption[],
): Record<string, string> {
  const gaps: Record<string, string> = {};
  const money = (box: string, raw: string) => {
    if (raw.trim() !== "" && !MONEY_RE.test(raw.trim())) gaps[box] = "rating.discountForm.gap.money";
  };
  const whole = (box: string, raw: string) => {
    if (raw.trim() !== "" && !WHOLE_RE.test(raw.trim())) gaps[box] = "rating.discountForm.gap.whole";
  };
  if (stepId === "details") {
    if (draft.code.trim() === "") gaps["discount-code"] = "rating.discountForm.gap.code";
    if (draft.name.trim() === "") gaps["discount-label"] = "rating.discountForm.gap.label";
    const box = valueBoxFor(effectiveType(draft));
    const value = draft.value.trim();
    if (box === "percent") {
      if (value === "") gaps["discount-value"] = "rating.discountForm.gap.value";
      else if (!PERCENT_RE.test(value)) gaps["discount-value"] = "rating.discountForm.gap.number";
      else if (percentOver100(value)) gaps["discount-value"] = "rating.discountForm.gap.over100";
    } else if (box === "money") {
      if (value === "") gaps["discount-value"] = "rating.discountForm.gap.value";
      else if (!MONEY_RE.test(value)) gaps["discount-value"] = "rating.discountForm.gap.money";
    } else if (box === "units") {
      if (value === "") gaps["discount-value"] = "rating.discountForm.gap.value";
      else if (!UNITS_RE.test(value)) gaps["discount-value"] = "rating.discountForm.gap.number";
    }
    if (draft.applies_to === SCOPE_ONE_SERVICE && draft.applies_to_service === "") {
      gaps["discount-service"] = "rating.discountForm.gap.service";
    }
    if (draft.applies_to === SCOPE_SPECIFIC_SERVICES && draft.applies_to_services.length === 0) {
      gaps["discount-services"] = "rating.discountForm.gap.services";
    }
    if (draft.applies_to === SCOPE_NAMED_CODES && draft.applies_to_charge_codes.length === 0) {
      gaps["discount-codes"] = "rating.discountForm.gap.codes";
    }
    money("discount-cap-bill", draft.cap_per_bill);
    money("discount-cap-year", draft.cap_per_year);
    money("discount-cap-lifetime", draft.cap_lifetime);
    money("discount-floor", draft.bill_floor_amount);
    whole("discount-stacking", draft.stacking_precedence);
  }
  if (stepId === "eligibility") {
    if (draft.eligibility === "") gaps["discount-who"] = "rating.discountForm.gap.who";
    if (automaticRefused(draft, eligibility)) gaps["discount-enrollment"] = "rating.discountForm.gap.automaticProof";
    whole("discount-recertify", draft.recertification_months);
    whole("discount-notice", draft.recertification_notice_days);
    whole("discount-grace", draft.recertification_grace_days);
    if (draft.effective_from === "") gaps["discount-starts"] = "rating.discountForm.gap.starts";
    if (draft.effective_to !== "" && draft.effective_from !== "" && draft.effective_to < draft.effective_from) {
      gaps["discount-ends"] = "rating.discountForm.gap.endsBefore";
    }
    money("discount-budget", draft.budget_cap);
  }
  return gaps;
}

/** The boxes that live inside the Limits section — a gap in any of them opens
 *  it, so a marked box is never hidden behind *No limits*. */
export const LIMIT_BOXES = [
  "discount-cap-bill",
  "discount-cap-year",
  "discount-cap-lifetime",
  "discount-floor",
  "discount-stacking",
  "discount-stacks",
  "discount-exclusivity",
] as const;

// ── The example bill ───────────────────────────────────────────────────────

/** The drawing's $60.00 bill of $40.00 usage and $20.00 base (images 05, 17).
 *  An ILLUSTRATION (B14 rule 37), fixed so every discount is compared against
 *  the same bill. */
export const EXAMPLE_BILL = "60.00";
const EXAMPLE_USAGE = "40.00";
const EXAMPLE_BASE = "20.00";

function toCents(value: bigint, scale: number): bigint {
  const unit = 10n ** BigInt(scale - 2);
  return (value + unit / 2n) / unit;
}

/**
 * What this discount takes off the $60.00 bill, in cents as `"9.00"`, or
 * `null` where the figure depends on something the example does not have — a
 * rate override's schedule, an allowance's tariff, the codes or services a
 * scope names.
 *
 * The cap per bill trims it and the bill floor stops it, as the engine does
 * (`BR-RAT-075`); it never exceeds the bill.
 */
export function exampleReduction(draft: DiscountFormDraft): string | null {
  const type = effectiveType(draft);
  const bill = scaledAmount(EXAMPLE_BILL, 2);
  let cents: bigint | null = null;
  const value = draft.value.trim();
  if (type === TYPE_PERCENTAGE) {
    if (!PERCENT_RE.test(value)) return null;
    // 60.00 × points / 100, at 2 + 6 + 2 places, rounded half up to cents.
    cents = toCents(bill * scaledAmount(value, 6), 10);
  } else if (type === TYPE_FIXED) {
    if (!MONEY_RE.test(value)) return null;
    cents = toCents(scaledAmount(value, 4), 4);
  } else if (type === TYPE_WAIVER) {
    const scope = draft.applies_to;
    if (scope === "" || scope === SCOPE_WHOLE_BILL || scope === SCOPE_ALL_SERVICES) cents = bill;
    else if (scope === SCOPE_BASE_ONLY) cents = scaledAmount(EXAMPLE_BASE, 2);
    else if (scope === SCOPE_USAGE_ONLY) cents = scaledAmount(EXAMPLE_USAGE, 2);
    else return null;
  } else {
    return null;
  }
  if (MONEY_RE.test(draft.cap_per_bill.trim())) {
    const cap = toCents(scaledAmount(draft.cap_per_bill.trim(), 4), 4);
    if (cents > cap) cents = cap;
  }
  let ceiling = bill;
  if (MONEY_RE.test(draft.bill_floor_amount.trim())) {
    ceiling = bill - toCents(scaledAmount(draft.bill_floor_amount.trim(), 4), 4);
    if (ceiling < 0n) ceiling = 0n;
  }
  if (cents > ceiling) cents = ceiling;
  return unscaledAmount(cents, 2);
}

/** `$60.00 − reduction` — the Review table's *Before taxes* row. */
export function exampleAfter(reduction: string | null): string | null {
  if (reduction === null) return null;
  return unscaledAmount(scaledAmount(EXAMPLE_BILL, 2) - scaledAmount(reduction, 2), 2);
}

export function twoPlaces(amount: string): string {
  const [whole, part = ""] = amount.trim().split(".");
  return `${whole.replace(/^0+(?=\d)/, "")}.${part.padEnd(2, "0").slice(0, 2)}`;
}

/** `15%` / `$25.00` / `2` — the figure a value box holds, for display. */
export function valueFigure(draft: DiscountFormDraft): string | null {
  const box = valueBoxFor(effectiveType(draft));
  const value = draft.value.trim();
  if (box === "percent") return PERCENT_RE.test(value) ? `${value.replace(/^0+(?=\d)/, "")}%` : null;
  if (box === "money") return MONEY_RE.test(value) ? `$${twoPlaces(value)}` : null;
  if (box === "units") return UNITS_RE.test(value) ? value : null;
  return null;
}

// ── The payload ────────────────────────────────────────────────────────────

function blank(raw: string): string | undefined {
  const value = raw.trim();
  return value === "" ? undefined : value;
}

/**
 * The ONE body `POST /discounts` is sent; `POST /discounts` saves a DRAFT
 * (CR-166 §9), so both exits send the same body.
 *
 * ⚠ **`currency` IS THE UTILITY'S OWN OR IT IS ABSENT — NEVER ANYTHING
 * ELSE.** PO 2026-10-03: *"Currency - it is default of utility - user cannot
 * change it"*. There is no box to type one into, and when the utility's code
 * is not known yet the key is left out, so the server sets it rather than the
 * form guessing `USD` (§4 D4 saved `CAD` on a USD utility).
 *
 * ⚠ **`value` IS SENT EXACTLY AS TYPED** — percentage POINTS for a
 * percentage (see the head of this file).
 *
 * ⚠ **`proof_required` IS DERIVED, NEVER TYPED.** The drawing has no proof
 * dropdown any more: a *customer shows proof* condition IS the requirement
 * (ruling 3), so the flag follows the chosen *Who qualifies*.
 *
 * ⚠ **`rate_schedule` IS NOT SENT.** Image 08 draws *Bill from schedule*;
 * `BR-RAT-961` ruled the mechanism away and no column holds it (CR-166 §11).
 */
export function discountFormPayload(
  draft: DiscountFormDraft,
  ctx: { currency: string | null; eligibility: readonly DiscountEligibilityOption[] },
): Record<string, unknown> {
  const type = effectiveType(draft);
  const box = valueBoxFor(type);
  const payload: Record<string, unknown> = {
    code: draft.code.trim().toUpperCase(),
    name: draft.name.trim(),
    funding_source: draft.funding_source.trim(),
    report_in_assistance_filing: draft.report_in_assistance_filing,
    discount_type: type,
    applies_to: draft.applies_to === "" ? SCOPE_WHOLE_BILL : draft.applies_to,
    stacks_with_others: draft.stacks_with_others,
    proof_required: isProofCondition(draft, ctx.eligibility),
    proof_before_first_reduction: isProofCondition(draft, ctx.eligibility) && draft.proof_before_first_reduction,
  };
  const optional: [string, string | undefined][] = [
    ["program_owner", blank(draft.program_owner)],
    ["exclusivity_group", blank(draft.exclusivity_group)],
    ["eligibility", blank(draft.eligibility)],
    ["enrolment_mode", blank(draft.enrolment_mode)],
    ["verification_method", blank(draft.verification_method)],
    ["lapse_behaviour", blank(draft.lapse_behaviour)],
    ["budget_period", blank(draft.budget_period)],
    ["exhaustion_behaviour", blank(draft.exhaustion_behaviour)],
    ["effective_from", blank(draft.effective_from)],
    ["effective_to", blank(draft.effective_to)],
    ["cap_per_bill", blank(draft.cap_per_bill)],
    ["cap_per_year", blank(draft.cap_per_year)],
    ["cap_lifetime", blank(draft.cap_lifetime)],
    ["bill_floor_amount", blank(draft.bill_floor_amount)],
    ["budget_cap", blank(draft.budget_cap)],
  ];
  for (const [field, value] of optional) {
    if (value !== undefined) payload[field] = value;
  }
  const counts: [string, string][] = [
    ["stacking_precedence", draft.stacking_precedence],
    ["recertification_months", draft.recertification_months],
    ["recertification_notice_days", draft.recertification_notice_days],
    ["recertification_grace_days", draft.recertification_grace_days],
  ];
  for (const [field, raw] of counts) {
    if (WHOLE_RE.test(raw.trim())) payload[field] = Number(raw.trim());
  }
  if (box === "percent" || box === "money" || box === "units") {
    const value = blank(draft.value);
    if (value !== undefined) payload.value = value;
  } else {
    // DEF-RAT-9318: the server requires `value` on every version, and a type
    // that draws no box (a waiver removes the WHOLE charge; a rate override's
    // value was a schedule swap, BR-RAT-961) sent none — so a charge waiver
    // could never be saved. Pricing never reads a waiver's value
    // (`discount_pricing._raw_reduction` returns the base) and the list serves
    // it as a dash (`selectors.discount_value_display`), so 0 is stored.
    payload.value = "0";
  }
  if (payload.applies_to === SCOPE_ONE_SERVICE && draft.applies_to_service !== "") {
    payload.applies_to_service = draft.applies_to_service;
  }
  if (payload.applies_to === SCOPE_SPECIFIC_SERVICES) {
    payload.applies_to_services = [...draft.applies_to_services];
  }
  if (payload.applies_to === SCOPE_NAMED_CODES) {
    payload.applies_to_charge_codes = [...draft.applies_to_charge_codes];
  }
  if (ctx.currency !== null && ctx.currency !== "") payload.currency = ctx.currency;
  return payload;
}

// ── The steps, as DATA ─────────────────────────────────────────────────────

/** The step list is an array, never fixed indexes, so round 3's three edit
 *  variations (*Name and details · New value from a date · Fix a mistake*)
 *  drop, rename or reorder steps without touching a component. */
export interface DiscountFormStepSpec {
  id: DiscountStepId;
  labelKey: string;
}

export const NEW_DISCOUNT_STEPS: readonly DiscountFormStepSpec[] = [
  { id: "details", labelKey: "rating.discountForm.step.details" },
  { id: "eligibility", labelKey: "rating.discountForm.step.eligibility" },
  { id: "review", labelKey: "rating.discountForm.step.review" },
];

const ELIGIBILITY_FIELDS: ReadonlySet<keyof DiscountFormDraft> = new Set<keyof DiscountFormDraft>([
  "eligibility",
  "enrolment_mode",
  "verification_method",
  "proof_before_first_reduction",
  "recertification_months",
  "recertification_notice_days",
  "recertification_grace_days",
  "lapse_behaviour",
  "effective_from",
  "effective_to",
  "budget_cap",
  "budget_period",
  "exhaustion_behaviour",
]);

/** Which step a field lives on — what a Review row's Edit link opens. */
export function stepOfField(field: keyof DiscountFormDraft, steps: readonly DiscountFormStepSpec[]): number {
  return stepNumberOf(ELIGIBILITY_FIELDS.has(field) ? "eligibility" : "details", steps);
}

export function stepNumberOf(id: DiscountStepId, steps: readonly DiscountFormStepSpec[]): number {
  const index = steps.findIndex((step) => step.id === id);
  return index === -1 ? 1 : index + 1;
}

// ── The server's field names → the boxes that show them ────────────────────

/** A refusal from `POST /discounts` names the SERVER's field; this says which
 *  box on which step carries it, so the clerk is taken to the box and nothing
 *  typed is lost (the draft is never reset by a refusal). */
export const SERVER_FIELD_BOXES: Readonly<Record<string, { box: string; step: DiscountStepId }>> = {
  code: { box: "discount-code", step: "details" },
  name: { box: "discount-label", step: "details" },
  program_owner: { box: "discount-owner", step: "details" },
  funding_source: { box: "discount-funding", step: "details" },
  report_in_assistance_filing: { box: "discount-assistance", step: "details" },
  discount_type: { box: "discount-type", step: "details" },
  value: { box: "discount-value", step: "details" },
  currency: { box: "discount-value", step: "details" },
  applies_to: { box: "discount-applies", step: "details" },
  applies_to_service: { box: "discount-service", step: "details" },
  applies_to_services: { box: "discount-services", step: "details" },
  applies_to_charge_codes: { box: "discount-codes", step: "details" },
  cap_per_bill: { box: "discount-cap-bill", step: "details" },
  cap_per_year: { box: "discount-cap-year", step: "details" },
  cap_lifetime: { box: "discount-cap-lifetime", step: "details" },
  bill_floor_amount: { box: "discount-floor", step: "details" },
  stacking_precedence: { box: "discount-stacking", step: "details" },
  stacks_with_others: { box: "discount-stacks", step: "details" },
  exclusivity_group: { box: "discount-exclusivity", step: "details" },
  eligibility: { box: "discount-who", step: "eligibility" },
  accepted_proof_kinds: { box: "discount-who", step: "eligibility" },
  enrolment_mode: { box: "discount-enrollment", step: "eligibility" },
  proof_required: { box: "discount-enrollment", step: "eligibility" },
  verification_method: { box: "discount-verification", step: "eligibility" },
  proof_before_first_reduction: { box: "discount-proof-before", step: "eligibility" },
  recertification_months: { box: "discount-recertify", step: "eligibility" },
  recertification_notice_days: { box: "discount-notice", step: "eligibility" },
  recertification_grace_days: { box: "discount-grace", step: "eligibility" },
  lapse_behaviour: { box: "discount-lapse", step: "eligibility" },
  effective_from: { box: "discount-starts", step: "eligibility" },
  effective_to: { box: "discount-ends", step: "eligibility" },
  budget_cap: { box: "discount-budget", step: "eligibility" },
  budget_period: { box: "discount-budget-period", step: "eligibility" },
  exhaustion_behaviour: { box: "discount-budget-out", step: "eligibility" },
};
