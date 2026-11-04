// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the New tax or fee form, built from images
//           04–17 of `05-prototype/taxes-fees-2026-10-03/images/`.
// Defects:  DEF-RAT-9277 (P1–P20, the wizard) · DEF-RAT-9275 (Save draft & exit
//           put the tax in force)
// Rules:    BR-RAT-087 / BR-RAT-092 (store 4 / 6, display 2 — a rate is STORED
//           as a fraction and TYPED and SHOWN as a percent) · BR-RAT-036 (what
//           is taxed is usage and base only) · CLAUDE.md hard rule 2 (money is a
//           decimal string, never a float)
// ───────────────────────────────────────────────────────
//
// THE PURE HALF OF THE FORM — no React, so every rule below is a unit test.
//
// ⚠ **THE PERCENT IS CONVERTED HERE AND NOWHERE ELSE (P8, P17, P43).** The
// server stores a rate as a FRACTION with six places (`0.062500` is 6.25 %)
// and the clerk types and reads a PERCENT (`6.25`). Today's wizard asked the
// clerk to type the fraction, so a clerk who typed `1.5` meaning 1.5 % saved a
// 150 % tax (CR-165 §4, P9). The conversion is a decimal-point shift done on
// the STRING — never `Number(x) / 100`, which turns `0.07` into
// `0.0007000000000000001`.
import { scaledAmount, unscaledAmount } from "@/components/moneyMath";

// ── Percent ⇄ fraction ─────────────────────────────────────────────────────

/** A percent a clerk may type: digits, an optional point, at most four places
 *  (four places of a percent are the six places of the stored fraction). */
const PERCENT_RE = /^\d{1,4}(\.\d{1,4})?$/;

export function isPercentShape(typed: string): boolean {
  return PERCENT_RE.test(typed.trim());
}

/** `6.25` → `0.0625`. `null` when the box does not hold a percent. */
export function percentToFraction(typed: string): string | null {
  const text = typed.trim();
  if (!PERCENT_RE.test(text)) {
    return null;
  }
  const [whole, part = ""] = text.split(".");
  const digits = `${whole}${part}`;
  const places = part.length + 2;
  const padded = digits.padStart(places + 1, "0");
  const raw = `${padded.slice(0, padded.length - places)}.${padded.slice(padded.length - places)}`;
  return trimDecimal(raw);
}

/** `0.062500` → `6.25`. A stored fraction read back as the percent it means. */
export function fractionToPercent(stored: string | null | undefined): string {
  if (stored === null || stored === undefined || stored.trim() === "") {
    return "";
  }
  const text = stored.trim();
  if (!/^\d+(\.\d+)?$/.test(text)) {
    return "";
  }
  const [whole, part = ""] = text.split(".");
  const fraction = part.padEnd(2, "0");
  return trimDecimal(`${whole}${fraction.slice(0, 2)}.${fraction.slice(2)}`);
}

function trimDecimal(raw: string): string {
  let [whole, part = ""] = raw.split(".");
  whole = whole.replace(/^0+(?=\d)/, "");
  part = part.replace(/0+$/, "");
  return part === "" ? whole : `${whole}.${part}`;
}

/**
 * OVER 20 % WARNS — PO ruling 2026-10-03, README point 2 (*"over 20% warns
 * before saving and on Review"*). A warning, not a refusal: a franchise fee can
 * lawfully be high, and the clerk is the one who knows. 150 typed is flagged;
 * 20 itself is not.
 */
export const HIGH_RATE_PERCENT = "20";

export function percentIsHigh(typed: string): boolean {
  if (!isPercentShape(typed)) {
    return false;
  }
  return scaledAmount(typed.trim(), 4) > scaledAmount(HIGH_RATE_PERCENT, 4);
}

// ── The draft ──────────────────────────────────────────────────────────────

/** Basis codes the form knows how to collect an amount for. The LIST a clerk
 *  chooses from is the server's (`GET /taxes/form-options` → `bases`); these
 *  are only the codes the amount box branches on. */
export const BASIS_PERCENT = "percent";
export const BASIS_FLAT = "flat_per_bill";
export const BASIS_PER_UNIT = "per_unit";
export const BASIS_PER_METER = "per_meter";

/** The boundary meaning "every premises this utility serves". It is sent as no
 *  scope at all, which is what the server means by everywhere. */
export const BOUNDARY_EVERYWHERE = "everywhere";

/** Every value is a STRING, start to finish (hard rule 2). Percent fields hold
 *  what the clerk TYPED — a percent — and are converted only in the payload. */
export interface TaxFormDraft {
  // Step 1 · What it is
  name: string;
  jurisdiction: string;
  boundary: string;
  place_name: string;
  services: string[]; // [] = all services
  customer_classes: string[]; // [] = every customer class
  // Step 2 · How much
  basis: string;
  rate_percent: string;
  amount: string; // flat / per-unit / per-meter dollars
  per_unit_uom: string;
  base_includes_usage: boolean;
  base_includes_base: boolean;
  effective_from: string;
  effective_to: string;
  discount_treatment: string;
  rounding_rule: string;
  // Step 3 · Filing
  code: string;
  bill_label: string;
  liability_gl_account_id: string;
  filing_frequency: string;
  due_date_rule: string;
  authority_account_id: string;
  allowance_percent: string;
  interest_percent: string;
  filing_reminder_recipient: string;
}

export function emptyTaxFormDraft(): TaxFormDraft {
  return {
    name: "",
    jurisdiction: "",
    boundary: "",
    place_name: "",
    services: [],
    customer_classes: [],
    basis: "",
    rate_percent: "",
    amount: "",
    per_unit_uom: "",
    base_includes_usage: true,
    base_includes_base: true,
    effective_from: "",
    effective_to: "",
    // The ruled answer (DEF-652): the utility remits on the FULL service value.
    discount_treatment: "after",
    rounding_rule: "half_up",
    code: "",
    bill_label: "",
    liability_gl_account_id: "",
    filing_frequency: "",
    due_date_rule: "",
    authority_account_id: "",
    allowance_percent: "",
    interest_percent: "",
    filing_reminder_recipient: "",
  };
}

/** Fill the server-listed defaults the first time each list arrives: the first
 *  boundary, basis and filing frequency the server offers. Never overwrites a
 *  value the clerk has already chosen — nothing typed is lost. */
export function withListDefaults(
  draft: TaxFormDraft,
  lists: { boundaries: readonly { value: string }[]; bases: readonly { value: string }[]; filing_frequencies: readonly { value: string }[] },
): TaxFormDraft {
  const next = { ...draft };
  if (next.boundary === "" && lists.boundaries.length > 0) next.boundary = lists.boundaries[0].value;
  if (next.basis === "" && lists.bases.length > 0) next.basis = lists.bases[0].value;
  if (next.filing_frequency === "" && lists.filing_frequencies.length > 0) {
    next.filing_frequency = lists.filing_frequencies[0].value;
  }
  return next;
}

/** The basis the amount box should treat the draft as. Until the server's list
 *  has arrived the form has nothing to branch on, and a percent box is the
 *  honest default — it is what the drawing opens on. */
export function effectiveBasis(draft: TaxFormDraft): string {
  return draft.basis === "" ? BASIS_PERCENT : draft.basis;
}

export function isPercentBasis(draft: TaxFormDraft): boolean {
  return effectiveBasis(draft) === BASIS_PERCENT;
}

// ── Services ───────────────────────────────────────────────────────────────

/**
 * P1 — ONLY the services this utility has switched on. `GET /settings/services`
 * answers all eleven platform services with an `enabled` flag per row; today's
 * wizard mapped every row, so a two-service utility was offered eleven.
 */
export function enabledServiceOptions(
  rows: readonly { service: string; name: string; enabled: boolean }[] | undefined,
): { value: string; label: string }[] {
  return (rows ?? []).filter((row) => row.enabled).map((row) => ({ value: row.service, label: row.name }));
}

// ── Validation ─────────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MONEY_RE = /^\d{1,9}(\.\d{1,4})?$/;

export interface StepContext {
  /** Boundary values whose drawing asks for a place name (image 07). */
  placeBoundaries: readonly string[];
}

/** WHICH boxes on a step are wrong — field id → catalogue key. PRESENCE and
 *  SHAPE only; every bound on money stays the server's (ratingShared). */
export function stepGaps(stepId: string, draft: TaxFormDraft, ctx: StepContext): Record<string, string> {
  const gaps: Record<string, string> = {};
  if (stepId === "what") {
    if (draft.name.trim() === "") gaps["tax-name"] = "rating.taxForm.gap.name";
    if (draft.jurisdiction === "") gaps["tax-authority"] = "rating.taxForm.gap.authority";
    if (ctx.placeBoundaries.includes(draft.boundary) && draft.place_name.trim() === "") {
      gaps["tax-place"] = "rating.taxForm.gap.place";
    }
  }
  if (stepId === "much") {
    const basis = effectiveBasis(draft);
    if (basis === BASIS_PERCENT) {
      if (draft.rate_percent.trim() === "") gaps["tax-rate"] = "rating.taxForm.gap.rate";
      else if (!isPercentShape(draft.rate_percent)) gaps["tax-rate"] = "rating.taxForm.gap.rateShape";
      if (!draft.base_includes_usage && !draft.base_includes_base) {
        gaps["tax-taxed"] = "rating.taxForm.gap.taxed";
      }
    } else {
      if (draft.amount.trim() === "") gaps["tax-rate"] = "rating.taxForm.gap.rate";
      else if (!MONEY_RE.test(draft.amount.trim())) gaps["tax-rate"] = "rating.taxForm.gap.amountShape";
      if (basis === BASIS_PER_UNIT && draft.per_unit_uom.trim() === "") {
        gaps["tax-uom"] = "rating.taxForm.gap.uom";
      }
    }
    if (draft.effective_from === "") gaps["tax-from"] = "rating.taxForm.gap.from";
    if (draft.effective_to !== "" && draft.effective_from !== "" && draft.effective_to < draft.effective_from) {
      gaps["tax-to"] = "rating.taxForm.gap.toBeforeFrom";
    }
  }
  if (stepId === "filing") {
    if (draft.liability_gl_account_id === "") gaps["tax-liability"] = "rating.taxForm.gap.liability";
    if (draft.allowance_percent.trim() !== "" && !isPercentShape(draft.allowance_percent)) {
      gaps["tax-allowance"] = "rating.taxForm.gap.percentShape";
    }
    if (draft.interest_percent.trim() !== "" && !isPercentShape(draft.interest_percent)) {
      gaps["tax-interest"] = "rating.taxForm.gap.percentShape";
    }
    const email = draft.filing_reminder_recipient.trim();
    if (email !== "" && !EMAIL_RE.test(email)) gaps["tax-reminder"] = "rating.taxForm.gap.email";
  }
  return gaps;
}

// ── The example bill ───────────────────────────────────────────────────────

/** The drawing's example: a $60.00 bill of $40.00 usage and $20.00 base, with a
 *  $5.00 discount for the after-discounts column (images 09, 15). Illustrative
 *  figures, fixed on purpose so every tax is compared against the same bill. */
export const EXAMPLE_USAGE = "40.00";
export const EXAMPLE_BASE = "20.00";
export const EXAMPLE_BILL = "60.00";
export const EXAMPLE_DISCOUNT = "5.00";

/** Round a value at `scale` places to cents, half up — display only. */
function toCents(value: bigint, scale: number): string {
  const unit = 10n ** BigInt(scale - 2);
  const negative = value < 0n;
  const abs = negative ? -value : value;
  const cents = (abs + unit / 2n) / unit;
  return unscaledAmount(negative ? -cents : cents, 2);
}

export interface ExampleBill {
  usage: string;
  base: string;
  taxedFull: string;
  discount: string;
  taxedAfterDiscount: string;
  taxFull: string | null;
  taxAfterDiscount: string | null;
  /** What this tax adds to the $60.00 bill under the chosen discount rule. */
  effect: string | null;
}

export function exampleBill(draft: TaxFormDraft): ExampleBill {
  const basis = effectiveBasis(draft);
  const usage = basis !== BASIS_PERCENT || draft.base_includes_usage ? EXAMPLE_USAGE : "0.00";
  const base = basis !== BASIS_PERCENT || draft.base_includes_base ? EXAMPLE_BASE : "0.00";
  const taxedFull = scaledAmount(usage, 2) + scaledAmount(base, 2);
  const taxedAfter = taxedFull - scaledAmount(EXAMPLE_DISCOUNT, 2);
  let taxFull: string | null = null;
  let taxAfter: string | null = null;
  if (basis === BASIS_PERCENT) {
    const fraction = percentToFraction(draft.rate_percent);
    if (fraction !== null) {
      const rate = scaledAmount(fraction, 6);
      taxFull = toCents(taxedFull * rate, 8);
      taxAfter = toCents(taxedAfter * rate, 8);
    }
  } else if (basis === BASIS_FLAT && MONEY_RE.test(draft.amount.trim())) {
    taxFull = toCents(scaledAmount(draft.amount.trim(), 4), 4);
    taxAfter = taxFull;
  }
  // `before` = the discounted amount is taxed; `after` = the full amount is.
  const effect = draft.discount_treatment === "before" ? taxAfter : taxFull;
  return {
    usage,
    base,
    taxedFull: unscaledAmount(taxedFull, 2),
    discount: EXAMPLE_DISCOUNT,
    taxedAfterDiscount: unscaledAmount(taxedAfter, 2),
    taxFull,
    taxAfterDiscount: taxAfter,
    effect,
  };
}

// ── The payload ────────────────────────────────────────────────────────────

function blankToNull(raw: string): string | null {
  const value = raw.trim();
  return value === "" ? null : value;
}

/**
 * The ONE body `POST /taxes` is sent, for both exits.
 *
 * ⚠ **`as_draft: true` IS SENT BY *Save draft & exit* AND BY NOTHING ELSE
 * (DEF-RAT-9275).** Today's wizard posted the same body from both buttons, so a
 * half-finished 150 % tax saved as a draft was IN FORCE at the next bill run.
 * The key is the contract's (`CR-165-BRC10` §9) and is absent — not `false` —
 * on *Save tax*, so a server that predates it sees the body it always saw.
 */
export function taxFormPayload(
  draft: TaxFormDraft,
  options: { asDraft: boolean; placeBoundaries: readonly string[] },
): Record<string, unknown> {
  const basis = effectiveBasis(draft);
  const everywhere = draft.boundary === "" || draft.boundary === BOUNDARY_EVERYWHERE;
  const payload: Record<string, unknown> = {
    name: draft.name.trim(),
    jurisdiction: draft.jurisdiction,
    kind: basis,
    premises_scope_kind: everywhere ? null : draft.boundary,
    premises_scope_value: options.placeBoundaries.includes(draft.boundary) ? draft.place_name.trim() : "",
    applies_to_services: [...draft.services],
    applies_to_customer_classes: [...draft.customer_classes],
    base_includes_usage: basis === BASIS_PERCENT ? draft.base_includes_usage : true,
    base_includes_base: basis === BASIS_PERCENT ? draft.base_includes_base : true,
    effective_from: draft.effective_from === "" ? null : draft.effective_from,
    effective_to: draft.effective_to === "" ? null : draft.effective_to,
    discount_treatment: draft.discount_treatment,
    rounding_rule: blankToNull(draft.rounding_rule),
    code: blankToNull(draft.code),
    bill_label: blankToNull(draft.bill_label),
    due_date_rule: blankToNull(draft.due_date_rule),
    filing_reminder_recipient: blankToNull(draft.filing_reminder_recipient),
  };
  if (draft.filing_frequency !== "") payload.filing_frequency = draft.filing_frequency;
  if (draft.liability_gl_account_id !== "") payload.liability_gl_account_id = draft.liability_gl_account_id;
  if (draft.authority_account_id !== "") payload.authority_account_id = draft.authority_account_id;
  if (basis === BASIS_PERCENT) {
    const fraction = percentToFraction(draft.rate_percent);
    if (fraction !== null) payload.rate = fraction;
  } else if (draft.amount.trim() !== "") {
    const amount = draft.amount.trim();
    if (basis === BASIS_FLAT) {
      payload.flat_amount = amount;
      payload.flat_frequency = "per_bill";
    } else if (basis === BASIS_PER_UNIT) {
      payload.per_unit_amount = amount;
      payload.per_unit_uom = draft.per_unit_uom.trim();
    } else if (basis === BASIS_PER_METER) {
      payload.per_meter_amount = amount;
    }
  }
  const allowance = percentToFraction(draft.allowance_percent);
  if (allowance !== null) payload.collection_allowance_percent = allowance;
  const interest = percentToFraction(draft.interest_percent);
  if (interest !== null) {
    payload.interest_penalty_percent = interest;
    // The drawing labels the box "% / month" (image 13), and the server refuses
    // a percent with no period rather than guess one.
    payload.interest_penalty_basis = "monthly";
  }
  if (options.asDraft) payload.as_draft = true;
  return payload;
}

// ── The steps, as DATA ─────────────────────────────────────────────────────

/** The step list is an array, never fixed indexes, so the round-3 edit
 *  variations can drop or reorder steps without touching a component. */
export interface TaxFormStepSpec {
  id: "what" | "much" | "filing" | "review";
  labelKey: string;
}

export const NEW_TAX_STEPS: readonly TaxFormStepSpec[] = [
  { id: "what", labelKey: "rating.taxForm.step.what" },
  { id: "much", labelKey: "rating.taxForm.step.much" },
  { id: "filing", labelKey: "rating.taxForm.step.filing" },
  { id: "review", labelKey: "rating.taxForm.step.review" },
];

/** Which step a field lives on — what a Review row's Edit link jumps to. */
export function stepOfField(field: keyof TaxFormDraft, steps: readonly TaxFormStepSpec[]): number {
  const home: Record<string, TaxFormStepSpec["id"]> = {
    name: "what", jurisdiction: "what", boundary: "what", place_name: "what", services: "what", customer_classes: "what",
    basis: "much", rate_percent: "much", amount: "much", per_unit_uom: "much", base_includes_usage: "much",
    base_includes_base: "much", effective_from: "much", effective_to: "much", discount_treatment: "much", rounding_rule: "much",
  };
  const id = home[field] ?? "filing";
  return stepNumberOf(id, steps);
}

export function stepNumberOf(id: TaxFormStepSpec["id"], steps: readonly TaxFormStepSpec[]): number {
  const index = steps.findIndex((step) => step.id === id);
  return index === -1 ? 1 : index + 1;
}

// ── The server's field names → the boxes that show them ────────────────────

/** A refusal from `POST /taxes` names the SERVER's field; this says which box
 *  on which step carries it, so the clerk is taken to the box (and nothing
 *  typed is lost — the draft is never reset by a refusal). */
export const SERVER_FIELD_BOXES: Readonly<Record<string, { box: string; step: TaxFormStepSpec["id"] }>> = {
  name: { box: "tax-name", step: "what" },
  jurisdiction: { box: "tax-authority", step: "what" },
  premises_scope_kind: { box: "tax-boundary", step: "what" },
  premises_scope_value: { box: "tax-place", step: "what" },
  applies_to_services: { box: "tax-services", step: "what" },
  applies_to_customer_classes: { box: "tax-classes", step: "what" },
  kind: { box: "tax-basis", step: "much" },
  rate: { box: "tax-rate", step: "much" },
  flat_amount: { box: "tax-rate", step: "much" },
  per_unit_amount: { box: "tax-rate", step: "much" },
  per_meter_amount: { box: "tax-rate", step: "much" },
  per_unit_uom: { box: "tax-uom", step: "much" },
  base_includes_usage: { box: "tax-taxed", step: "much" },
  base_includes_base: { box: "tax-taxed", step: "much" },
  effective_from: { box: "tax-from", step: "much" },
  effective_to: { box: "tax-to", step: "much" },
  discount_treatment: { box: "tax-discounts", step: "much" },
  rounding_rule: { box: "tax-rounding", step: "much" },
  code: { box: "tax-code", step: "filing" },
  bill_label: { box: "tax-bill-label", step: "filing" },
  liability_gl_account_id: { box: "tax-liability", step: "filing" },
  filing_frequency: { box: "tax-filed", step: "filing" },
  due_date_rule: { box: "tax-due", step: "filing" },
  authority_account_id: { box: "tax-authority-account", step: "filing" },
  collection_allowance_percent: { box: "tax-allowance", step: "filing" },
  interest_penalty_percent: { box: "tax-interest", step: "filing" },
  interest_penalty_basis: { box: "tax-interest", step: "filing" },
  filing_reminder_recipient: { box: "tax-reminder", step: "filing" },
};
