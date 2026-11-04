// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — EDIT a discount, built as the SAME
//           full-page form as New with three choices (images 27–36 of
//           `05-prototype/discounts-2026-10-03/images/`, B14 rules 42, 44, 37).
// Defects:  DEF-RAT-9292 (D35 two edit buttons · D36 value editable on a live
//           discount · D38 a fix with no before and after)
// Rules:    README point 7, PO 2026-10-03 — *"Edit is the same full-page form:
//           Name and details (same version; value, limits and start locked) ·
//           New value from a date (old version ends the day before) · Fix a
//           mistake (same dates, reason required, old row kept)."* · the tax
//           precedent, PO verbatim: *"We dont use side panel for edit - you
//           will need to send it back to Edit form - You can use add form with
//           variation"* · BR-RAT-1016's three verbs · BR-RAT-087 (a discount's
//           percent is stored in percentage POINTS) · hard rule 2
// Contract: CR-166-BRC10 §9 — `PATCH /discounts/{id}`,
//           `POST /discounts/{id}/new-value`, `POST /discounts/{id}/corrections`
// ───────────────────────────────────────────────────────
//
// THE PURE HALF OF THE EDIT FORM — no React, so every rule is a unit test.
//
// ONE DRAFT SHAPE FOR NEW AND EDIT. A discount is read back into the New form's
// `DiscountFormDraft` (`discountDraftFromRow`), the New form's own section
// components mount over it with a set of LOCKED fields per variation, and each
// variation sends exactly the keys its server door accepts:
//
//   info    → `PATCH /discounts/{id}`               the CHANGED name and detail keys only
//   change  → `POST /discounts/{id}/new-value`       the value + any changed scope/limit + the new window
//   correct → `POST /discounts/{id}/corrections`     the CHANGED value/scope/limit keys + a reason
//
// ⚠ **A DRAFT IS NOT A LIVE DISCOUNT, AND ITS EDIT LOCKS NOTHING.** The server's
// `update_discount_details` edits a never-submitted draft in place, every
// field (BR-RAT-1016 verb 1 — it has priced nothing). A draft has no version in
// force, so *New value from a date* and *Fix a mistake* cannot act on it
// (`new_value_needs_live`, `correct_draft`): their cards are drawn disabled.
import { dayBefore } from "../taxForm/taxEditModel";
import type { DiscountEditRow } from "@/api/discountEditEndpoints";
import { optionCode } from "@/api/discountEditEndpoints";
import type { DiscountEligibilityOption } from "@/api/discountFormEndpoints";

import {
  SCOPE_NAMED_CODES,
  SCOPE_ONE_SERVICE,
  SCOPE_SPECIFIC_SERVICES,
  SERVER_FIELD_BOXES,
  discountFormPayload,
  effectiveType,
  isProofCondition,
  stepGaps,
  valueBoxFor,
} from "./discountFormModel";
import type { DiscountFormDraft, DiscountStepId } from "./discountFormModel";

export { dayBefore };

// ── The three variations ───────────────────────────────────────────────────

export type DiscountEditMode = "info" | "change" | "correct";

/** The order the *What to change* cards are drawn in (image 27). */
export const DISCOUNT_EDIT_MODES: readonly DiscountEditMode[] = ["info", "change", "correct"];

/** The URL param the chosen card lives in — the details page links to
 *  `…/discounts/{id}/edit?change=info|change|correct`, the tax edit's address
 *  shape (`CR-165` §13 judgment 1). */
export const CHANGE_PARAM = "change";

/** The pre-redesign Fix door's spelling (`…/edit?correct=1`, the old details
 *  page's *Fix this version*). Read as *Fix a mistake*, so an old link lands
 *  on the right card instead of on *Name and details*. */
export const LEGACY_CORRECT_PARAM = "correct";

export function discountEditModeOf(params: URLSearchParams): DiscountEditMode {
  const raw = params.get(CHANGE_PARAM);
  if (raw === "change" || raw === "correct" || raw === "info") return raw;
  return params.get(LEGACY_CORRECT_PARAM) === "1" ? "correct" : "info";
}

/** The tenant-relative address one choice opens — what the details page's
 *  Edit links to. Spelled once, beside the param it sets. */
export function discountEditPath(discountId: string, mode: DiscountEditMode): string {
  return `/plans-rates/discounts/${encodeURIComponent(discountId)}/edit?${CHANGE_PARAM}=${mode}`;
}

/** A step of an edit variation. `value` is the one step only an edit has —
 *  *New value* (image 31) and *Fix the value* (image 34). */
export type DiscountEditStepId = DiscountStepId | "value";

export interface DiscountEditStepSpec {
  id: DiscountEditStepId;
  labelKey: string;
}

/** The step lists, as DATA. The labels are the drawing's. */
export const EDIT_STEPS: Readonly<Record<DiscountEditMode, readonly DiscountEditStepSpec[]>> = {
  info: [
    { id: "details", labelKey: "rating.discountForm.step.details" },
    { id: "eligibility", labelKey: "rating.discountForm.step.eligibility" },
    { id: "review", labelKey: "rating.discountForm.step.review" },
  ],
  change: [
    { id: "value", labelKey: "rating.discountEdit.step.newValue" },
    { id: "review", labelKey: "rating.discountForm.step.review" },
  ],
  correct: [
    { id: "value", labelKey: "rating.discountEdit.step.fixValue" },
    { id: "review", labelKey: "rating.discountForm.step.review" },
  ],
};

export function editStepNumberOf(id: DiscountEditStepId, steps: readonly DiscountEditStepSpec[]): number {
  const index = steps.findIndex((step) => step.id === id);
  return index === -1 ? 1 : index + 1;
}

// ── What each variation may change ─────────────────────────────────────────

const ALL_FIELDS: readonly (keyof DiscountFormDraft)[] = [
  "code", "name", "program_owner", "funding_source", "report_in_assistance_filing", "discount_type",
  "value", "rate_schedule", "applies_to", "applies_to_service", "applies_to_services", "applies_to_charge_codes",
  "cap_per_bill", "cap_per_year", "cap_lifetime", "bill_floor_amount", "stacking_precedence",
  "stacks_with_others", "exclusivity_group",
  "eligibility", "enrolment_mode", "verification_method", "proof_before_first_reduction",
  "recertification_months", "recertification_notice_days", "recertification_grace_days", "lapse_behaviour",
  "effective_from", "effective_to", "budget_cap", "budget_period", "exhaustion_behaviour",
];

/** *Name and details* on a LIVE discount — the server's identity fields plus
 *  the version's non-priced details; `LOCKED_ON_LIVE` (value, type, scope,
 *  caps, floor, stacking, exclusivity, start) is refused there by name. The
 *  code is drawn as a fact (image 27): one code names one programme. */
const INFO_EDITABLE: readonly (keyof DiscountFormDraft)[] = [
  "name", "program_owner", "funding_source", "report_in_assistance_filing",
  "eligibility", "enrolment_mode", "verification_method", "proof_before_first_reduction",
  "recertification_months", "recertification_notice_days", "recertification_grace_days", "lapse_behaviour",
  "effective_to", "budget_cap", "budget_period", "exhaustion_behaviour",
];

/** What a value is worth and what it is taken off — the fields *New value*
 *  and *Fix the value* draw (images 31, 34): the Value section and Limits. */
const VALUE_FIELDS: readonly (keyof DiscountFormDraft)[] = [
  "value", "applies_to", "applies_to_service", "applies_to_services", "applies_to_charge_codes",
  "cap_per_bill", "cap_per_year", "cap_lifetime", "bill_floor_amount", "stacking_precedence",
  "stacks_with_others", "exclusivity_group",
];

const CHANGE_EDITABLE: readonly (keyof DiscountFormDraft)[] = [...VALUE_FIELDS, "effective_from", "effective_to"];

/** A correction restates the SAME window (`correct_discount_version` copies
 *  it), so the dates are drawn as facts (image 34, *Same dates as today.*). */
const CORRECT_EDITABLE: readonly (keyof DiscountFormDraft)[] = VALUE_FIELDS;

const EDITABLE: Readonly<Record<DiscountEditMode, readonly (keyof DiscountFormDraft)[]>> = {
  info: INFO_EDITABLE,
  change: CHANGE_EDITABLE,
  correct: CORRECT_EDITABLE,
};

export function editableFields(mode: DiscountEditMode, isDraft: boolean): readonly (keyof DiscountFormDraft)[] {
  return isDraft ? ALL_FIELDS.filter((field) => field !== "rate_schedule") : EDITABLE[mode];
}

export function lockedFields(mode: DiscountEditMode, isDraft: boolean): ReadonlySet<keyof DiscountFormDraft> {
  const editable = new Set(editableFields(mode, isDraft));
  return new Set(ALL_FIELDS.filter((field) => !editable.has(field)));
}

/** A draft — the derived §9 status says `draft` (a version sent back by an
 *  approver is a draft again, and edits in place like one). */
export function isDraftRow(row: Pick<DiscountEditRow, "status">): boolean {
  return row.status === "draft";
}

// ── The served row, read back into the form's draft ─────────────────────────

/** A stored money figure (`25.000000`) as a box shows it (`25.00`): trailing
 *  zeros past the cents are dropped, never rounded. */
export function storedMoney(raw: string | null | undefined): string {
  if (raw === null || raw === undefined) return "";
  const match = /^(\d+)(?:\.(\d*))?$/.exec(raw.trim());
  if (match === null) return raw.trim();
  const whole = match[1].replace(/^0+(?=\d)/, "");
  const part = (match[2] ?? "").replace(/0+$/, "").padEnd(2, "0");
  return `${whole}.${part}`;
}

/** Stored percentage POINTS (`15.000000`, `1.500000`) as the clerk typed them
 *  (`15`, `1.5`) — never divided, never rounded (BR-RAT-087). */
export function storedPoints(raw: string | null | undefined): string {
  if (raw === null || raw === undefined) return "";
  const match = /^(\d+)(?:\.(\d*))?$/.exec(raw.trim());
  if (match === null) return raw.trim();
  const whole = match[1].replace(/^0+(?=\d)/, "");
  const part = (match[2] ?? "").replace(/0+$/, "");
  return part === "" ? whole : `${whole}.${part}`;
}

/** A zero floor is the stored DEFAULT (BR-RAT-074: the bill may reach zero) —
 *  the New form's empty box. Read back as empty, so an untouched discount
 *  reads *No limits* (image 31) rather than *1 set*. */
function storedFloor(raw: string | null | undefined): string {
  const shown = storedMoney(raw);
  return /^0+(\.0+)?$/.test(shown) ? "" : shown;
}

function count(raw: number | null | undefined): string {
  return raw === null || raw === undefined ? "" : String(raw);
}

export function discountDraftFromRow(row: DiscountEditRow): DiscountFormDraft {
  const type = row.type ?? "";
  const box = valueBoxFor(type === "" ? "percentage" : type);
  const value = box === "money" ? storedMoney(row.value) : box === "percent" || box === "units" ? storedPoints(row.value) : "";
  return {
    code: row.code ?? "",
    name: row.name ?? "",
    program_owner: optionCode(row.program_owner) || (row.programme_owner ?? ""),
    funding_source: row.funding_source ?? "",
    report_in_assistance_filing: row.report_in_assistance_filing === true,
    discount_type: type,
    value,
    rate_schedule: "",
    applies_to: row.applies_to ?? "",
    applies_to_service: row.applies_to_service ?? "",
    applies_to_services: [...(row.applies_to_services ?? [])],
    applies_to_charge_codes: [...(row.applies_to_charge_codes ?? [])],
    cap_per_bill: storedMoney(row.cap_per_bill),
    cap_per_year: storedMoney(row.cap_per_year),
    cap_lifetime: storedMoney(row.cap_lifetime),
    bill_floor_amount: storedFloor(row.bill_floor_amount),
    stacking_precedence: count(row.stacking_precedence),
    stacks_with_others: row.stacks_with_others !== false,
    exclusivity_group: optionCode(row.exclusivity_group),
    eligibility: optionCode(row.eligibility),
    enrolment_mode: row.enrolment_mode ?? "",
    verification_method: row.verification ?? "",
    proof_before_first_reduction: row.proof_before_first_reduction === true,
    recertification_months: count(row.recertification_months),
    recertification_notice_days: count(row.recertification_notice_days),
    recertification_grace_days: count(row.recertification_grace_days),
    lapse_behaviour: row.lapse_behaviour ?? "",
    effective_from: row.effective_from ?? "",
    effective_to: row.effective_to ?? "",
    budget_cap: storedMoney(row.budget_cap),
    budget_period: row.budget_period ?? "",
    exhaustion_behaviour: row.exhaustion_behaviour ?? "",
  };
}

// ── What moved ─────────────────────────────────────────────────────────────

function same(a: DiscountFormDraft[keyof DiscountFormDraft], b: DiscountFormDraft[keyof DiscountFormDraft]): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return [...a].sort().join("\u0000") === [...b].sort().join("\u0000");
  }
  return typeof a === "string" && typeof b === "string" ? a.trim() === b.trim() : a === b;
}

/** The fields THIS variation may change that the clerk did change. A
 *  re-ordered list is not a change; a locked field never counts. */
export function changedFields(
  mode: DiscountEditMode,
  isDraft: boolean,
  original: DiscountFormDraft,
  current: DiscountFormDraft,
): (keyof DiscountFormDraft)[] {
  return editableFields(mode, isDraft).filter((field) => !same(original[field], current[field]));
}

/** The scope travels as ONE group: a discount moved off *One service* drops
 *  its service, so the server never keeps a target GATE 3 no longer reads. */
const SCOPE_GROUP: ReadonlySet<keyof DiscountFormDraft> = new Set<keyof DiscountFormDraft>([
  "applies_to", "applies_to_service", "applies_to_services", "applies_to_charge_codes",
]);

interface PayloadContext {
  eligibility: readonly DiscountEligibilityOption[];
}

/**
 * The CHANGED keys as the server spells them. A cleared box is SENT as null,
 * so "the clerk emptied it" reaches the server rather than being read as "the
 * clerk did not touch it". Two exceptions, each a stored default: a cleared
 * FLOOR is `0` (BR-RAT-074 — the column is not nullable and zero is its
 * no-floor), and a cleared exclusivity group is `none`.
 */
function changedBody(
  fields: readonly (keyof DiscountFormDraft)[],
  current: DiscountFormDraft,
  ctx: PayloadContext,
): Record<string, unknown> {
  const whole = discountFormPayload(current, { currency: null, eligibility: ctx.eligibility });
  const body: Record<string, unknown> = {};
  const put = (key: string) => {
    body[key] = key in whole ? whole[key] : null;
  };
  let scope = false;
  for (const field of fields) {
    if (SCOPE_GROUP.has(field)) {
      scope = true;
      continue;
    }
    if (field === "eligibility") {
      put("eligibility");
      // The flag follows the condition (ruling 3); sent with it so a proof
      // condition never travels without its requirement.
      body.proof_required = isProofCondition(current, ctx.eligibility);
      body.proof_before_first_reduction = whole.proof_before_first_reduction;
      continue;
    }
    if (field === "proof_before_first_reduction") {
      body.proof_before_first_reduction = whole.proof_before_first_reduction;
      continue;
    }
    if (field === "bill_floor_amount") {
      body.bill_floor_amount = "bill_floor_amount" in whole ? whole.bill_floor_amount : "0";
      continue;
    }
    if (field === "exclusivity_group") {
      body.exclusivity_group = "exclusivity_group" in whole ? whole.exclusivity_group : "none";
      continue;
    }
    if (field === "code") {
      body.code = whole.code;
      continue;
    }
    put(field);
  }
  if (scope) {
    const applies = whole.applies_to as string;
    body.applies_to = applies;
    body.applies_to_service = applies === SCOPE_ONE_SERVICE ? (whole.applies_to_service ?? null) : null;
    body.applies_to_services = applies === SCOPE_SPECIFIC_SERVICES ? (whole.applies_to_services ?? []) : [];
    body.applies_to_charge_codes = applies === SCOPE_NAMED_CODES ? (whole.applies_to_charge_codes ?? []) : [];
  }
  return body;
}

/** `PATCH /discounts/{id}` — the CHANGED name and detail keys, nothing else.
 *  On a live discount nothing in `LOCKED_ON_LIVE` can be in it: those fields
 *  are not editable in this variation, so they can never count as changed. */
export function infoPatchPayload(
  original: DiscountFormDraft,
  current: DiscountFormDraft,
  ctx: PayloadContext & { isDraft: boolean },
): Record<string, unknown> {
  return changedBody(changedFields("info", ctx.isDraft, original, current), current, ctx);
}

/** `POST /discounts/{id}/new-value` — the value (always: it is what the new
 *  version is FOR), any changed scope or limit, and the new window. */
export function newValuePayload(
  original: DiscountFormDraft,
  current: DiscountFormDraft,
  ctx: PayloadContext,
): Record<string, unknown> {
  const moved = changedFields("change", false, original, current).filter(
    (field) => field !== "effective_from" && field !== "effective_to",
  );
  const body = changedBody(moved, current, ctx);
  const box = valueBoxFor(effectiveType(current));
  if ((box === "percent" || box === "money" || box === "units") && current.value.trim() !== "") {
    body.value = current.value.trim();
  }
  body.effective_from = current.effective_from;
  if (current.effective_to !== "") body.effective_to = current.effective_to;
  return body;
}

/** `POST /discounts/{id}/corrections` — what MOVED, plus the reason. The
 *  window is never sent: the server copies the corrected row's own. */
export function correctionPayload(
  original: DiscountFormDraft,
  current: DiscountFormDraft,
  reason: string,
  ctx: PayloadContext,
): Record<string, unknown> {
  const body = changedBody(changedFields("correct", false, original, current), current, ctx);
  return { ...body, reason: reason.trim() };
}

// ── Validation ─────────────────────────────────────────────────────────────

export interface EditGap {
  key: string;
  params?: Record<string, unknown>;
}

/** The boxes each variation's steps draw that the New form's `stepGaps` checks.
 *  A box NOT drawn (or drawn as a fact) is never marked: the clerk could do
 *  nothing about it. */
const VALUE_STEP_BOXES: ReadonlySet<string> = new Set([
  "discount-value", "discount-service", "discount-services", "discount-codes",
  "discount-cap-bill", "discount-cap-year", "discount-cap-lifetime", "discount-floor", "discount-stacking",
]);
const INFO_DETAILS_BOXES: ReadonlySet<string> = new Set(["discount-label"]);

/** WHICH boxes on an edit step are wrong — the New form's own `stepGaps` for
 *  the boxes a variation draws, plus the variation's own two rules: a new
 *  value must start AFTER today's (image 32) and a fix needs a reason
 *  (image 35). */
export function editStepGaps(
  mode: DiscountEditMode,
  stepId: DiscountEditStepId,
  draft: DiscountFormDraft,
  ctx: { eligibility: readonly DiscountEligibilityOption[]; isDraft: boolean; liveFrom: string; reason: string },
): Record<string, EditGap> {
  const gaps: Record<string, EditGap> = {};
  if (stepId === "review") return gaps;
  if (stepId === "details" || stepId === "eligibility") {
    for (const [box, key] of Object.entries(stepGaps(stepId, draft, ctx.eligibility))) {
      if (ctx.isDraft || stepId === "eligibility" || INFO_DETAILS_BOXES.has(box)) gaps[box] = { key };
    }
    return gaps;
  }
  for (const [box, key] of Object.entries(stepGaps("details", draft, ctx.eligibility))) {
    if (VALUE_STEP_BOXES.has(box)) gaps[box] = { key };
  }
  if (mode === "change") {
    if (draft.effective_from === "") {
      gaps["discount-starts"] = { key: "rating.discountForm.gap.starts" };
    } else if (ctx.liveFrom !== "" && draft.effective_from <= ctx.liveFrom) {
      gaps["discount-starts"] = { key: "rating.discountEdit.gap.startAfter", params: { date: ctx.liveFrom } };
    }
    if (draft.effective_to !== "" && draft.effective_from !== "" && draft.effective_to < draft.effective_from) {
      gaps["discount-ends"] = { key: "rating.discountForm.gap.endsBefore" };
    }
  }
  if (mode === "correct" && ctx.reason.trim() === "") {
    gaps["discount-reason"] = { key: "rating.discountEdit.gap.reason" };
  }
  return gaps;
}

/** Where a refusal from an edit save lands: the box and the step that holds
 *  it in THIS variation, or nothing (the strip says it) when the variation
 *  draws no such box. */
export function editFieldHome(
  mode: DiscountEditMode,
  field: string,
): { box: string; step: DiscountEditStepId } | undefined {
  if (field === "reason") return mode === "correct" ? { box: "discount-reason", step: "value" } : undefined;
  const home = SERVER_FIELD_BOXES[field];
  if (home === undefined) return undefined;
  if (mode === "info") return home;
  const valueStep = new Set<string>([...VALUE_FIELDS, ...(mode === "change" ? ["effective_from", "effective_to"] : [])]);
  return valueStep.has(field) || field === "currency" ? { box: home.box, step: "value" } : undefined;
}

export { ALL_FIELDS as DISCOUNT_FORM_FIELDS };
