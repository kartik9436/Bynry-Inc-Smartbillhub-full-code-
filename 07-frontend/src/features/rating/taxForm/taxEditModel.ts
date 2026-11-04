// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — the EDIT form, built from images 24–33 of
//           `05-prototype/taxes-fees-2026-10-03/images/` (B14 rules 42, 44, 37).
// Defects:  DEF-RAT-9273 (P44–P50: one form for every kind of edit, rate and
//           reach editable on a live tax, no new-rate path, no picture of the
//           rows on save)
// Rules:    PO 2026-10-03, README point 6 — *"Edit opens the SAME full-page form
//           as New, with 'What to change' first: Name and filing (same version,
//           rate and reach locked) · New rate from a date (old version ends the
//           day before) · Fix a mistake (same dates, reason required, old row
//           superseded and kept)."* · BR-RAT-1016's three verbs (edit in place ·
//           correct · change over a new window) · CR-008 as amended by the PO on
//           2026-10-03 (*"Pick it when you create the tax; change it later only
//           in Settings"*) · hard rule 2 (money is a decimal string)
// ───────────────────────────────────────────────────────
//
// THE PURE HALF OF THE EDIT FORM — no React, so every rule is a unit test.
//
// ONE DRAFT SHAPE FOR NEW AND EDIT. A live tax is read back into the New form's
// `TaxFormDraft` (`taxFormDraftFromRow`), the steps mount over it with a set of
// LOCKED fields per variation, and each variation sends exactly the keys its
// server door accepts:
//
//   info    → `PATCH /taxes/{id}`               name and filing, the CHANGED keys only
//   change  → `POST /taxes/{id}/new-rate`        the figure and its form + the new window
//   correct → `POST /taxes/{id}/corrections`     the CHANGED rate fields + a reason
//
// ⚠ **THE LIABILITY ACCOUNT IS NEVER SENT FROM HERE.** The server refuses it on a
// live tax by name (`rating.taxes.liability_edit_in_settings`); Settings ›
// Accounting is its one door after creation. It is locked in every variation
// AND left out of every payload, so a locked box that somehow changed still
// cannot reach the wire.
import { BASIS_FLAT, BASIS_PERCENT, BASIS_PER_METER, BASIS_PER_UNIT, effectiveBasis, fractionToPercent, stepGaps, taxFormPayload } from "./taxFormModel";
import type { StepContext, TaxFormDraft, TaxFormStepSpec } from "./taxFormModel";
import type { TaxEditRow } from "@/api/taxEditEndpoints";

import { TAX_WIZARD_NEW_ROUTE, taxWizardEditPath } from "../definitionDetail";

// ── The three variations ───────────────────────────────────────────────────

export type TaxEditMode = "info" | "change" | "correct";

/** The order the *What to change* cards are drawn in (image 24). */
export const TAX_EDIT_MODES: readonly TaxEditMode[] = ["info", "change", "correct"];

/** The URL param the chosen card lives in — the details page links to
 *  `…/taxes-fees/{id}/edit?change=info|change|correct`. */
export const CHANGE_PARAM = "change";

/** The address one choice opens — what the details page's Edit and *Fix the
 *  rate* link to. Spelled once, beside the param it sets. */
export function taxEditPath(taxId: string, mode: TaxEditMode): string {
  return `${taxWizardEditPath(taxId)}?${CHANGE_PARAM}=${mode}`;
}

export function editModeOf(raw: string | null): TaxEditMode {
  return raw === "change" || raw === "correct" ? raw : "info";
}

/** The step lists, as DATA — module-private: `EDIT_STEPS` is the one
 *  export, and the census in `wizardRailCensus.test.ts` sees it reach the
 *  frame (`DEF-RAT-10105`). (the New form's own `NEW_TAX_STEPS` contract). The
 *  ids are the New form's, so `stepOfField` sends a Review row's Edit link to
 *  the step that holds the field; the LABELS are the drawing's. */
const EDIT_INFO_STEPS: readonly TaxFormStepSpec[] = [
  { id: "what", labelKey: "rating.taxEdit.step.name" },
  { id: "filing", labelKey: "rating.taxForm.step.filing" },
  { id: "review", labelKey: "rating.taxForm.step.review" },
];
const EDIT_CHANGE_STEPS: readonly TaxFormStepSpec[] = [
  { id: "much", labelKey: "rating.taxEdit.step.newRate" },
  { id: "review", labelKey: "rating.taxForm.step.review" },
];
const EDIT_CORRECT_STEPS: readonly TaxFormStepSpec[] = [
  { id: "much", labelKey: "rating.taxEdit.step.fixRate" },
  { id: "review", labelKey: "rating.taxForm.step.review" },
];

export const EDIT_STEPS: Readonly<Record<TaxEditMode, readonly TaxFormStepSpec[]>> = {
  info: EDIT_INFO_STEPS,
  change: EDIT_CHANGE_STEPS,
  correct: EDIT_CORRECT_STEPS,
};

// ── What each variation may change ─────────────────────────────────────────

const ALL_FIELDS: readonly (keyof TaxFormDraft)[] = [
  "name", "jurisdiction", "boundary", "place_name", "services", "customer_classes",
  "basis", "rate_percent", "amount", "per_unit_uom", "base_includes_usage", "base_includes_base",
  "effective_from", "effective_to", "discount_treatment", "rounding_rule",
  "code", "bill_label", "liability_gl_account_id", "filing_frequency", "due_date_rule",
  "authority_account_id", "allowance_percent", "interest_percent", "filing_reminder_recipient",
];

/** *Name and filing* — `update_tax` allows these on a live tax and refuses the
 *  nineteen rate-history columns; the liability account is Settings' alone. */
const INFO_EDITABLE: readonly (keyof TaxFormDraft)[] = [
  "name", "code", "bill_label", "filing_frequency", "due_date_rule", "authority_account_id",
  "allowance_percent", "interest_percent", "filing_reminder_recipient",
];

/** *New rate from a date* — `NEW_RATE_FIELDS` on the server: the figure and its
 *  form, the new window, and — as image 28 draws them editable — what is taxed,
 *  discounts and rounding for the new version (CR-165 §16, web walk). */
const CHANGE_EDITABLE: readonly (keyof TaxFormDraft)[] = [
  "basis", "rate_percent", "amount", "per_unit_uom", "base_includes_usage", "base_includes_base",
  "discount_treatment", "rounding_rule", "effective_from", "effective_to",
];

/** The new-rate fields that are not the figure: sent only when the clerk changed
 *  them, so a version the clerk left alone copies the old version's own values. */
const CHANGE_SCOPE_FIELDS: readonly (keyof TaxFormDraft)[] = [
  "base_includes_usage", "base_includes_base", "discount_treatment", "rounding_rule",
];

/** *Fix a mistake* — the rate step as drawn (image 31), dates locked: a
 *  correction restates the SAME window (`correct_tax` copies it). */
const CORRECT_EDITABLE: readonly (keyof TaxFormDraft)[] = [
  "basis", "rate_percent", "amount", "per_unit_uom", "base_includes_usage", "base_includes_base",
  "discount_treatment", "rounding_rule",
];

const EDITABLE: Readonly<Record<TaxEditMode, readonly (keyof TaxFormDraft)[]>> = {
  info: INFO_EDITABLE,
  change: CHANGE_EDITABLE,
  correct: CORRECT_EDITABLE,
};

export function editableFields(mode: TaxEditMode): readonly (keyof TaxFormDraft)[] {
  return EDITABLE[mode];
}

export function lockedFields(mode: TaxEditMode): ReadonlySet<keyof TaxFormDraft> {
  const editable = new Set(EDITABLE[mode]);
  return new Set(ALL_FIELDS.filter((field) => !editable.has(field)));
}

// ── The served row, read back into the form's draft ─────────────────────────

/** A stored money figure (`1.250000`) as the box shows it (`1.25`): trailing
 *  zeros past the cents are dropped, never rounded. */
export function storedAmount(raw: string | null | undefined): string {
  if (raw === null || raw === undefined) return "";
  const match = /^(\d+)(?:\.(\d*))?$/.exec(raw.trim());
  if (match === null) return raw.trim();
  const whole = match[1].replace(/^0+(?=\d)/, "");
  const part = (match[2] ?? "").replace(/0+$/, "").padEnd(2, "0");
  return `${whole}.${part}`;
}

export function taxFormDraftFromRow(row: TaxEditRow): TaxFormDraft {
  const kind = row.kind ?? BASIS_PERCENT;
  const amount =
    kind === BASIS_FLAT
      ? storedAmount(row.flat_amount)
      : kind === BASIS_PER_UNIT
        ? storedAmount(row.per_unit_amount)
        : kind === BASIS_PER_METER
          ? storedAmount(row.per_meter_amount)
          : "";
  return {
    name: row.name ?? "",
    jurisdiction: row.jurisdiction?.id ?? "",
    boundary: row.premises_scope_kind ?? "everywhere",
    place_name: row.premises_scope_value ?? "",
    services: [...(row.applies_to_services ?? [])],
    customer_classes: [...(row.applies_to_customer_classes ?? [])],
    basis: kind,
    rate_percent: kind === BASIS_PERCENT ? fractionToPercent(row.rate) : "",
    amount,
    per_unit_uom: row.per_unit_uom ?? "",
    base_includes_usage: row.base_includes_usage,
    base_includes_base: row.base_includes_base,
    effective_from: row.effective_from ?? "",
    effective_to: row.effective_to ?? "",
    discount_treatment: row.discount_treatment ?? "after",
    rounding_rule: row.rounding_rule ?? "half_up",
    code: row.code ?? "",
    bill_label: row.bill_label ?? "",
    liability_gl_account_id: row.liability_gl_account_id ?? "",
    filing_frequency: row.filing_frequency ?? "",
    due_date_rule: row.due_date_rule ?? "",
    authority_account_id: row.authority_account?.id ?? "",
    allowance_percent: fractionToPercent(row.collection_allowance_percent),
    interest_percent: fractionToPercent(row.interest_penalty_percent),
    filing_reminder_recipient: row.filing_reminder_recipient ?? "",
  };
}

// ── What moved ─────────────────────────────────────────────────────────────

function same(a: TaxFormDraft[keyof TaxFormDraft], b: TaxFormDraft[keyof TaxFormDraft]): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return [...a].sort().join("\u0000") === [...b].sort().join("\u0000");
  }
  return typeof a === "string" && typeof b === "string" ? a.trim() === b.trim() : a === b;
}

/** The fields THIS variation may change that the clerk did change. A re-ordered
 *  list is not a change; a locked field never counts, whatever it holds. */
export function changedFields(
  mode: TaxEditMode,
  original: TaxFormDraft,
  current: TaxFormDraft,
): (keyof TaxFormDraft)[] {
  return EDITABLE[mode].filter((field) => !same(original[field], current[field]));
}

/** Which server keys each draft field is written as (`taxFormPayload`'s names). */
const SERVER_KEYS: Partial<Record<keyof TaxFormDraft, readonly string[]>> = {
  name: ["name"],
  code: ["code"],
  bill_label: ["bill_label"],
  filing_frequency: ["filing_frequency"],
  due_date_rule: ["due_date_rule"],
  authority_account_id: ["authority_account_id"],
  allowance_percent: ["collection_allowance_percent"],
  interest_percent: ["interest_penalty_percent", "interest_penalty_basis"],
  filing_reminder_recipient: ["filing_reminder_recipient"],
  base_includes_usage: ["base_includes_usage"],
  base_includes_base: ["base_includes_base"],
  discount_treatment: ["discount_treatment"],
  rounding_rule: ["rounding_rule"],
};

const PLACE_NONE = { asDraft: false, placeBoundaries: [] as readonly string[] };

/** A cleared optional box is SENT as null, so "the clerk emptied it" reaches
 *  the server rather than being read as "the clerk did not touch it". */
function pick(whole: Record<string, unknown>, keys: readonly string[]): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const key of keys) body[key] = key in whole ? whole[key] : null;
  return body;
}

/** `PATCH /taxes/{id}` — the CHANGED name and filing keys, nothing else. */
export function infoPatchPayload(original: TaxFormDraft, current: TaxFormDraft): Record<string, unknown> {
  const whole = taxFormPayload(current, PLACE_NONE);
  let body: Record<string, unknown> = {};
  for (const field of changedFields("info", original, current)) {
    body = { ...body, ...pick(whole, SERVER_KEYS[field] ?? []) };
  }
  if (body.interest_penalty_percent === null) delete body.interest_penalty_basis;
  delete body.liability_gl_account_id;
  return body;
}

/** The figure and its form, as `NEW_RATE_FIELDS` names them. */
function rateKeys(current: TaxFormDraft): Record<string, unknown> {
  const whole = taxFormPayload(current, PLACE_NONE);
  const basis = effectiveBasis(current);
  const keys =
    basis === BASIS_PERCENT
      ? ["rate"]
      : basis === BASIS_FLAT
        ? ["flat_amount", "flat_frequency"]
        : basis === BASIS_PER_UNIT
          ? ["per_unit_amount", "per_unit_uom"]
          : ["per_meter_amount"];
  // BR-RAT-036: a tax states exactly ONE figure. The other forms' figures are
  // sent as null, so a correction from a percent to a fixed fee does not keep
  // the old row's rate beside its new amount (the server merges a correction
  // over the corrected row's own values).
  const others = { rate: null, flat_amount: null, per_unit_amount: null, per_meter_amount: null };
  return { kind: basis, ...others, ...pick(whole, keys) };
}

/** `POST /taxes/{id}/new-rate` — the figure, its form and the new window, plus
 *  what is taxed, discounts and rounding where the clerk changed them. */
export function newRatePayload(current: TaxFormDraft, original?: TaxFormDraft): Record<string, unknown> {
  const whole = taxFormPayload(current, PLACE_NONE);
  let scope: Record<string, unknown> = {};
  if (original !== undefined) {
    for (const field of CHANGE_SCOPE_FIELDS) {
      if (!same(original[field], current[field])) scope = { ...scope, ...pick(whole, SERVER_KEYS[field] ?? []) };
    }
  }
  const body: Record<string, unknown> = {
    ...rateKeys(current),
    ...scope,
    effective_from: current.effective_from,
  };
  if (current.effective_to !== "") body.effective_to = current.effective_to;
  return body;
}

const RATE_FIELDS: ReadonlySet<keyof TaxFormDraft> = new Set(["basis", "rate_percent", "amount", "per_unit_uom"]);

/** `POST /taxes/{id}/corrections` — what MOVED, plus the reason. The window is
 *  never sent: the server copies the corrected row's own. */
export function correctionPayload(
  original: TaxFormDraft,
  current: TaxFormDraft,
  reason: string,
): Record<string, unknown> {
  const whole = taxFormPayload(current, PLACE_NONE);
  let body: Record<string, unknown> = {};
  for (const field of changedFields("correct", original, current)) {
    body = RATE_FIELDS.has(field) ? { ...body, ...rateKeys(current) } : { ...body, ...pick(whole, SERVER_KEYS[field] ?? []) };
  }
  return { ...body, reason: reason.trim() };
}

// ── Duplicate (image 21, DEF-RAT-9299) ──────────────────────────────────────

/** The New form's query parameter naming the tax it opens filled from. */
export const DUPLICATE_PARAM = "duplicate";

/** `/plans-rates/taxes-fees/new?duplicate=<id>` — tenant-relative, like
 *  `taxEditPath`; the caller adds the tenant. */
export function taxDuplicatePath(taxId: string): string {
  return `${TAX_WIZARD_NEW_ROUTE}?${DUPLICATE_PARAM}=${encodeURIComponent(taxId)}`;
}

/** The New form's query parameter naming a DRAFT it finishes (DEF-RAT-9305):
 *  the form opens filled from the draft, *Save tax* saves it in place and puts
 *  it into force, *Save draft & exit* saves it in place and leaves it a draft. */
export const DRAFT_PARAM = "draft";

/** `/plans-rates/taxes-fees/new?draft=<id>` — where a draft's Edit goes. */
export function taxFinishDraftPath(taxId: string): string {
  return `${TAX_WIZARD_NEW_ROUTE}?${DRAFT_PARAM}=${encodeURIComponent(taxId)}`;
}

/** The New form's draft, filled from an existing tax: every box as saved,
 *  except the code — one code names one tax (`ex_taxes_code_one_chain`), so a
 *  copy carrying it would be refused at Save. */
export function duplicateDraft(row: TaxEditRow): TaxFormDraft {
  return { ...taxFormDraftFromRow(row), code: "" };
}

// ── Dates ──────────────────────────────────────────────────────────────────

/** `2026-11-01` → `2026-10-31`: the day the version a new rate replaces ends.
 *  Calendar arithmetic in UTC, so no time zone can move it by a day. */
export function dayBefore(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (match === null) return "";
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

// ── Validation ─────────────────────────────────────────────────────────────

export interface EditGap {
  key: string;
  params?: Record<string, unknown>;
}

/** WHICH boxes on an edit step are wrong — the New form's own `stepGaps` for
 *  the boxes a variation can edit, plus the variation's own rules. A LOCKED
 *  box is never marked: the clerk could do nothing about it. */
export function editStepGaps(
  mode: TaxEditMode,
  stepId: string,
  draft: TaxFormDraft,
  ctx: StepContext & { liveFrom: string; reason: string },
): Record<string, EditGap> {
  const base = stepGaps(stepId, draft, ctx);
  const gaps: Record<string, EditGap> = {};
  const lockedBoxes =
    mode === "info"
      ? new Set(["tax-authority", "tax-place", "tax-liability"])
      : mode === "correct"
        ? new Set(["tax-from", "tax-to", "tax-uom"])
        : new Set<string>();
  for (const [box, key] of Object.entries(base)) {
    if (!lockedBoxes.has(box)) gaps[box] = { key };
  }
  if (mode === "change" && stepId === "much" && draft.effective_from !== "" && ctx.liveFrom !== "") {
    if (draft.effective_from <= ctx.liveFrom) {
      gaps["tax-from"] = { key: "rating.taxEdit.gap.startAfter", params: { date: ctx.liveFrom } };
    }
  }
  if (mode === "correct" && stepId === "much" && ctx.reason.trim() === "") {
    gaps["tax-reason"] = { key: "rating.taxEdit.gap.reason" };
  }
  return gaps;
}

/** A refusal names the server's field; `reason` is the one an edit adds. */
export const EDIT_SERVER_FIELD_BOXES: Readonly<Record<string, { box: string; step: TaxFormStepSpec["id"] }>> = {
  reason: { box: "tax-reason", step: "much" },
};
