// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — EDIT a plan: the New form with three
//           choices, built from images 37–44 of
//           `05-prototype/plans-2026-10-03/images/` (B14 rules 42, 44, 37).
// Defects:  DEF-RAT-9332 (Edit half — the edit intent was a radio on step 1 of
//           eight) · DEF-RAT-9328 (Edit half — the late fee a row of the plan's
//           ONE Charges list, removable, never re-added silently)
// Rules:    PO ruling 1 (2026-10-03) — *"Edit uses the same form, with three
//           'What to change' cards: Name and details (same version), Change from
//           a date (new version), Fix a mistake (same dates, with a reason)"* ·
//           ruling 10 — *"When editing, these are Save new version and Publish
//           new version"* · BR-RAT-1066 (a plan version has dates and owns its
//           bindings) · BR-RAT-1067 (name and details on the same version) ·
//           BR-RAT-1016 verb 2 (a correction keeps the number and the window) ·
//           hard rule 2 (money is a decimal string)
// Contract: CR-167-BRC10 §7.3 / §9 — `PATCH /plans/{id}`,
//           `POST /plans/{id}/versions`, `POST /plans/{id}/corrections`
// ───────────────────────────────────────────────────────
//
// THE PURE HALF OF THE EDIT FORM — no React, so every rule is a unit test.
//
// ONE DRAFT SHAPE FOR NEW AND EDIT. A plan is read back into the New form's
// `PlanFormDraft` (`planDraftFromRow`), the New form's own step components
// mount over it with a set of LOCKED fields per choice, and each choice sends
// ONLY THE KEYS THAT MOVED to the one server door that accepts them:
//
//   info    → `PATCH /plans/{id}`             `details` (the moved keys)
//   change  → `POST /plans/{id}/versions`     moved content + window + reason + publish
//   correct → `POST /plans/{id}/corrections`  moved content + reason + version
//   (draft) → `PATCH /plans/{id}`             any moved key; *Publish plan* then publishes
//
// ⚠ **ONLY WHAT MOVED TRAVELS, AND THAT IS A MONEY RULE, NOT TIDINESS.** The
// server copies the version's bindings and replaces a set only when its key is
// present (`plan_writes._copy_bindings`, `_apply_plan_children`). A tax the
// plan carries through its JURISDICTION reads back as one tax; re-sent as
// `{tax}` it would become an attachment, a different binding. Sending an
// untouched table would rewrite it; omitting it keeps it exactly as filed
// (`planUntouchedSave.dom.test.tsx` guards this end to end).
//
// ⚠ **THE LATE FEE IS A ROW OF THE PLAN'S CHARGES, READ BACK AS ONE
// (`DEF-RAT-9328`, Edit half).** The draft opens with `charge_codes_touched`
// set, so the New form's default — the utility's late-fee code offered as a row
// on a NEW plan — is never added to a plan someone already chose for.
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { PlanEditRow } from "@/api/planEditEndpoints";
import type {
  PlanDepositSection,
  PlanFormOptions,
  PlanFormScheduleOption,
  PlanSections,
} from "@/api/planFormEndpoints";

import { storedMoney, storedPoints } from "../discountForm/discountEditModel";
import { dayBefore } from "../taxForm/taxEditModel";
import {
  NEW_PLAN_STEPS,
  NOTE_ATTRIBUTE_CLASS,
  NOTE_ATTRIBUTE_SERVICE,
  SERVER_FIELD_BOXES,
  emptyPlanFormDraft,
  planFormPayload,
  rowKey,
  stepGaps,
} from "./planFormModel";
import type { PayloadContext, PlanFormDraft, PlanFormStepSpec, PlanStepId } from "./planFormModel";

export { dayBefore };

// ── The three choices ──────────────────────────────────────────────────────

export type PlanEditMode = "info" | "change" | "correct";

/** The order the *What to change* cards are drawn in (images 38, 40, 43). */
export const PLAN_EDIT_MODES: readonly PlanEditMode[] = ["info", "change", "correct"];

/** The URL params — the details page links to
 *  `…/plans/{id}/edit?change=info|change|correct&step=<n>` (lane PLAN-DETAIL,
 *  agreed 2026-10-03; CR-167 §14). A draft is linked without `change`. */
export const CHANGE_PARAM = "change";
export const STEP_PARAM = "step";

export function planEditModeOf(params: URLSearchParams): PlanEditMode {
  const raw = params.get(CHANGE_PARAM);
  return raw === "change" || raw === "correct" ? raw : "info";
}

/** The tenant-relative address one choice opens. `mode` null is a draft's
 *  edit (no cards); `step` is 1-based within that choice's own steps. */
export function planEditPath(planId: string, mode: PlanEditMode | null, step?: number): string {
  const params = new URLSearchParams();
  if (mode !== null) params.set(CHANGE_PARAM, mode);
  if (step !== undefined) params.set(STEP_PARAM, String(step));
  const query = params.toString();
  return `/plans-rates/plans/${encodeURIComponent(planId)}/edit${query === "" ? "" : `?${query}`}`;
}

/** The step lists, as DATA. *Name and details* is Details · Review (images
 *  38–39); *Change from a date* and *Fix a mistake* are Services · Charges ·
 *  Billing · Review (images 37, 40, 43). A draft has the New form's five. */
export const EDIT_STEPS: Readonly<Record<PlanEditMode, readonly PlanFormStepSpec[]>> = {
  info: [NEW_PLAN_STEPS[0], NEW_PLAN_STEPS[4]],
  change: NEW_PLAN_STEPS.slice(1),
  correct: NEW_PLAN_STEPS.slice(1),
};

export function editSteps(mode: PlanEditMode, isDraft: boolean): readonly PlanFormStepSpec[] {
  return isDraft ? NEW_PLAN_STEPS : EDIT_STEPS[mode];
}

/** The step the address asks for, kept inside the list (a stale link opens
 *  step 1 rather than nothing). */
export function stepFromParams(params: URLSearchParams, steps: readonly PlanFormStepSpec[]): number {
  const raw = Number.parseInt(params.get(STEP_PARAM) ?? "", 10);
  return Number.isInteger(raw) && raw >= 1 && raw <= steps.length ? raw : 1;
}

// ── What each choice may change ────────────────────────────────────────────

/** The six fields that price nothing (BR-RAT-1067). */
export const DETAIL_FIELDS: readonly (keyof PlanFormDraft)[] = [
  "name", "code", "customer_classes", "description", "intended_for", "notes",
];

/** Everything a bill is priced from — the version's (BR-RAT-1066). */
export const PRICE_FIELDS: readonly (keyof PlanFormDraft)[] = [
  "services", "outside_city", "outside_city_percent", "charge_codes", "taxes",
  "deposits", "discounts", "budget_billing", "minimum_bill",
];

const WINDOW_FIELDS: readonly (keyof PlanFormDraft)[] = ["effective_from", "effective_to"];

export function lockedFields(mode: PlanEditMode, isDraft: boolean): ReadonlySet<keyof PlanFormDraft> {
  if (isDraft) return new Set();
  // The code is drawn as a fact on *Name and details* (image 38): one code
  // names one plan, and the details page and the list are found by it.
  if (mode === "info") return new Set([...PRICE_FIELDS, ...WINDOW_FIELDS, "code"]);
  if (mode === "change") return new Set(DETAIL_FIELDS);
  return new Set([...DETAIL_FIELDS, ...WINDOW_FIELDS]);
}

export function isDraftPlan(row: Pick<PlanEditRow, "status">): boolean {
  return row.status === "draft";
}

// ── The served plan, read back into the form's draft ───────────────────────

/** A note's stored value as the box's choice: a class or service is stored
 *  by NAME (`DEF-RAT-9285`) and older notes by id — either finds its option. */
function noteChoice(attribute: string, stored: string, options: PlanFormOptions): string {
  const list =
    attribute === NOTE_ATTRIBUTE_CLASS
      ? options.customer_classes
      : attribute === NOTE_ATTRIBUTE_SERVICE
        ? options.services
        : [];
  const found = list.find((option) => option.value === stored || option.label === stored);
  return found?.value ?? stored;
}

/** A percentage the server stored as a positive number of points — `0` and
 *  null are both *no surcharge*. */
function surchargeOn(percent: string): boolean {
  return percent !== "" && !/^0+(\.0+)?$/.test(percent);
}

export function planDraftFromRow(row: PlanEditRow, options: PlanFormOptions): PlanFormDraft {
  const s = row.sections;
  const percent = storedPoints(row.outside_city_percent);
  const minimum = storedMoney(row.minimum_bill_amount);
  return {
    ...emptyPlanFormDraft(),
    name: s.details.name,
    code: s.details.code,
    customer_classes: s.details.customer_classes.map((option) => option.value),
    description: s.details.description ?? "",
    intended_for: { ...s.details.intended_for },
    notes: s.details.notes.map((note) => ({
      key: rowKey("note"),
      attribute: note.attribute,
      operator: note.operator,
      value: noteChoice(note.attribute, note.value, options),
    })),
    services: s.services.map((section) => ({
      key: rowKey("svc"),
      service: section.service,
      schedule: section.schedule?.id ?? "",
      surcharged: section.outside_city.surcharged,
    })),
    outside_city: surchargeOn(percent) ? "yes" : "no",
    outside_city_percent: surchargeOn(percent) ? percent : "",
    charge_codes: s.charge_codes.map((section) => ({ key: rowKey("chg"), value: section.ref.id })),
    // ⚠ DEF-RAT-9328 — what the plan charges is the clerk's earlier answer;
    // the New form's default rows are never added over it.
    charge_codes_touched: true,
    taxes: s.taxes.map((section) => ({ key: rowKey("tax"), value: section.ref.id })),
    // A typed rule (`ref: null`, DEF-RAT-9740) has no code for the form to pick.
    deposits: s.deposits.flatMap((section) => (section.ref === null ? [] : [{ key: rowKey("dep"), value: section.ref.id }])),
    discounts: s.discounts.map((section) => ({
      key: rowKey("disc"),
      discount: section.ref.id,
      offered_from: section.offered_from ?? "",
      offered_until: section.offered_until ?? "",
    })),
    budget_billing: s.details.budget_billing,
    minimum_bill: minimum,
    effective_from: row.effective_from ?? "",
    effective_to: row.effective_to ?? "",
  };
}

/** The draft a choice OPENS on: *Change from a date* asks for the new
 *  version's window, so its dates start empty (image 41 — the clerk types the
 *  start; the end is *No end* until typed). */
export function openingDraft(original: PlanFormDraft, mode: PlanEditMode, isDraft: boolean): PlanFormDraft {
  return !isDraft && mode === "change" ? { ...original, effective_from: "", effective_to: "" } : original;
}

/**
 * The form's lists with THIS plan's own items in them. A schedule, code, tax,
 * deposit or discount the plan carries may no longer be OFFERED to a new plan
 * (a retired code, a schedule priced from a later date), and a row whose value
 * is missing from its dropdown reads as empty and is refused. The plan's own
 * read wins over the catalogue's for its own items, because it resolves the
 * base for the plan's classes (`DEF-RAT-9336`).
 */
export function withPlanItems(options: PlanFormOptions, sections: PlanSections): PlanFormOptions {
  const merge = <T>(list: readonly T[], own: readonly T[], id: (row: T) => string): T[] => {
    const ownIds = new Set(own.map(id));
    return [...own, ...list.filter((row) => !ownIds.has(id(row)))];
  };
  const schedules: PlanFormScheduleOption[] = sections.services.flatMap((section) =>
    section.schedule === null
      ? []
      : [{ ref: section.schedule, service: section.service, base: section.base, minimum: section.minimum, usage: section.usage }],
  );
  const services = merge(
    options.services,
    sections.services
      .filter((section) => !options.services.some((option) => option.value === section.service))
      .map((section) => ({ value: section.service, label: section.name, gl: section.gl })),
    (row) => row.value,
  );
  return {
    ...options,
    services,
    schedules: merge(options.schedules, schedules, (row) => row.ref.id),
    charge_codes: merge(
      options.charge_codes,
      sections.charge_codes.map((row) => ({ ...row, default_on_new_plan: false })),
      (row) => row.ref.id,
    ),
    taxes: merge(options.taxes, sections.taxes, (row) => row.ref.id),
    deposit_codes: merge(
      options.deposit_codes,
      sections.deposits.filter((row): row is PlanDepositSection => row.ref !== null),
      (row) => row.ref.id,
    ),
    discounts: merge(options.discounts, sections.discounts, (row) => row.ref.id),
    customer_classes: merge(options.customer_classes, sections.details.customer_classes, (row) => row.value),
    currency: options.currency ?? sections.currency,
  };
}

// ── What moved ─────────────────────────────────────────────────────────────

/** The body's keys, each with the draft fields that make it. */
const BODY_GROUPS: readonly { key: string; fields: readonly (keyof PlanFormDraft)[] }[] = [
  { key: "services", fields: ["services", "outside_city"] },
  { key: "outside_city_percent", fields: ["outside_city", "outside_city_percent"] },
  { key: "charge_codes", fields: ["charge_codes"] },
  { key: "taxes", fields: ["taxes"] },
  { key: "deposits", fields: ["deposits"] },
  { key: "discounts", fields: ["discounts"] },
  { key: "budget_billing", fields: ["budget_billing"] },
  { key: "minimum_bill_amount", fields: ["minimum_bill"] },
  { key: "effective_from", fields: ["effective_from"] },
  { key: "effective_to", fields: ["effective_to"] },
];

/** A field's comparable form: row keys dropped, lists ORDER-FREE (a re-ordered
 *  table is not a change), text trimmed, money and points by value. */
function comparable(draft: PlanFormDraft, field: keyof PlanFormDraft): string {
  const sorted = (rows: string[]) => JSON.stringify([...rows].sort());
  switch (field) {
    case "services":
      return sorted(
        draft.services.map((row) =>
          JSON.stringify([row.service, row.schedule, draft.outside_city === "yes" && row.surcharged]),
        ),
      );
    case "outside_city_percent":
      return draft.outside_city === "yes" ? storedPoints(draft.outside_city_percent.trim()) : "";
    case "charge_codes":
    case "taxes":
    case "deposits":
      return sorted(draft[field].map((row) => row.value));
    case "discounts":
      return sorted(draft.discounts.map((row) => JSON.stringify([row.discount, row.offered_from, row.offered_until])));
    case "notes":
      return sorted(draft.notes.map((row) => JSON.stringify([row.attribute, row.operator, row.value.trim()])));
    case "customer_classes":
      return sorted(draft.customer_classes);
    case "intended_for":
      return JSON.stringify([draft.intended_for.cap_proof, draft.intended_for.min_demand_25kw, draft.intended_for.owner_occupied]);
    case "minimum_bill":
      return storedMoney(draft.minimum_bill.trim());
    case "charge_codes_touched":
      return "";
    default: {
      const value = draft[field];
      return typeof value === "string" ? value.trim() : JSON.stringify(value);
    }
  }
}

/** The fields THIS choice may change that the clerk did change. A locked
 *  field never counts. */
export function changedFields(
  mode: PlanEditMode,
  isDraft: boolean,
  original: PlanFormDraft,
  current: PlanFormDraft,
): (keyof PlanFormDraft)[] {
  const locked = lockedFields(mode, isDraft);
  const fields = [...DETAIL_FIELDS, ...PRICE_FIELDS, ...WINDOW_FIELDS];
  return fields.filter((field) => !locked.has(field) && comparable(original, field) !== comparable(current, field));
}

/**
 * The moved keys as the server spells them. A cleared minimum bill is SENT as
 * null — "the clerk emptied it" must reach the server rather than be read as
 * "the clerk did not touch it".
 */
export function changedBody(
  fields: readonly (keyof PlanFormDraft)[],
  current: PlanFormDraft,
  ctx: PayloadContext,
): Record<string, unknown> {
  const whole = planFormPayload(current, false, ctx);
  const moved = new Set(fields);
  const body: Record<string, unknown> = {};
  const details = whole.details as Record<string, unknown>;
  const changedDetails: Record<string, unknown> = {};
  for (const field of DETAIL_FIELDS) {
    if (moved.has(field)) changedDetails[field] = details[field];
  }
  if (Object.keys(changedDetails).length > 0) body.details = changedDetails;
  for (const group of BODY_GROUPS) {
    if (!group.fields.some((field) => moved.has(field))) continue;
    body[group.key] = group.key in whole ? whole[group.key] : null;
  }
  return body;
}

/** `PATCH /plans/{id}` — *Name and details* on a live plan (`details` only),
 *  or a draft's edit in place (every moved key). */
export function patchPayload(
  isDraft: boolean,
  original: PlanFormDraft,
  current: PlanFormDraft,
  ctx: PayloadContext,
): Record<string, unknown> {
  const body = changedBody(changedFields("info", isDraft, original, current), current, ctx);
  // `DEF-RAT-9514` — `details` is ALWAYS sent, empty when no detail moved: the
  // server tells this body from the old 8-step one by that key
  // (`plan_writes.is_contract_body`), and `services` / `discounts` exist in
  // both with different shapes. Without it a draft edited only on a priced
  // step was refused (`taxes` unknown) and never saved.
  if (body.details === undefined) body.details = {};
  return body;
}

/** `POST /plans/{id}/versions` — the moved content, the NEW window, the
 *  reason, and whether it is published now (ruling 10). */
export function newVersionPayload(
  original: PlanFormDraft,
  current: PlanFormDraft,
  reason: string,
  publish: boolean,
  ctx: PayloadContext,
): Record<string, unknown> {
  const moved = changedFields("change", false, original, current).filter((field) => !WINDOW_FIELDS.includes(field));
  const body = changedBody(moved, current, ctx);
  body.effective_from = current.effective_from === "" ? null : current.effective_from;
  if (current.effective_to !== "") body.effective_to = current.effective_to;
  body.reason = reason.trim();
  body.publish = publish;
  return body;
}

/** `POST /plans/{id}/corrections` — what moved, the reason, and WHICH version
 *  it restates. The window is never sent: the server copies it. */
export function correctionPayload(
  original: PlanFormDraft,
  current: PlanFormDraft,
  reason: string,
  version: number,
  ctx: PayloadContext,
): Record<string, unknown> {
  const body = changedBody(changedFields("correct", false, original, current), current, ctx);
  return { ...body, reason: reason.trim(), version };
}

// ── Validation ─────────────────────────────────────────────────────────────

export interface EditGap {
  key: string;
  params?: Record<string, unknown>;
}

export interface EditGapContext {
  isDraft: boolean;
  /** The start of the version in force — a new version must start after it. */
  liveFrom: string;
  reason: string;
  /** A refused publish marks the start date too. */
  publish: boolean;
}

/** WHICH boxes on an edit step are wrong — the New form's own `stepGaps` for
 *  the boxes a choice draws, plus the choice's own rules on Review: a new
 *  version needs a start after today's version's and a reason (image 42); a
 *  fix needs a reason (image 44). */
export function editStepGaps(
  mode: PlanEditMode,
  stepId: PlanStepId,
  draft: PlanFormDraft,
  ctx: EditGapContext,
): Record<string, EditGap> {
  const gaps: Record<string, EditGap> = {};
  if (ctx.isDraft) {
    for (const [box, key] of Object.entries(stepGaps(stepId, draft, ctx.publish))) gaps[box] = { key };
    return gaps;
  }
  if (stepId !== "review") {
    const locked = lockedFields(mode, false);
    for (const [box, key] of Object.entries(stepGaps(stepId, draft))) {
      // A box drawn as a fact is never marked: the clerk could do nothing about it.
      if (box === "plan-code" && locked.has("code")) continue;
      gaps[box] = { key };
    }
    return gaps;
  }
  if (mode === "change") {
    if (draft.effective_from === "") {
      gaps["plan-starts"] = { key: "rating.planForm.gap.starts" };
    } else if (ctx.liveFrom !== "" && draft.effective_from <= ctx.liveFrom) {
      gaps["plan-starts"] = { key: "rating.planEdit.gap.startAfter", params: { date: ctx.liveFrom } };
    }
    if (draft.effective_to !== "" && draft.effective_from !== "" && draft.effective_to < draft.effective_from) {
      gaps["plan-ends"] = { key: "rating.planForm.gap.endsBefore" };
    }
  }
  if ((mode === "change" || mode === "correct") && ctx.reason.trim() === "") {
    gaps["plan-reason"] = { key: "rating.planEdit.gap.reason" };
  }
  return gaps;
}

/** Every gap on every step of a choice — what a save must clear first, and
 *  the first step that holds one. */
export function allEditGaps(
  mode: PlanEditMode,
  steps: readonly PlanFormStepSpec[],
  draft: PlanFormDraft,
  ctx: EditGapContext,
): { gaps: Record<string, EditGap>; firstStep: number | null } {
  const gaps: Record<string, EditGap> = {};
  let firstStep: number | null = null;
  steps.forEach((step, index) => {
    const found = editStepGaps(mode, step.id, draft, ctx);
    if (Object.keys(found).length > 0 && firstStep === null) firstStep = index + 1;
    Object.assign(gaps, found);
  });
  return { gaps, firstStep };
}

/** Where a refusal from an edit save lands: the box and the step that holds
 *  it in THIS choice, or nothing (the strip says it) when the choice draws no
 *  such box. */
export function editFieldHome(
  field: string,
  steps: readonly PlanFormStepSpec[],
): { box: string; step: PlanStepId } | undefined {
  const root = field.split("[")[0] ?? field;
  const home = root === "reason" ? { box: "plan-reason", step: "review" as const } : SERVER_FIELD_BOXES[root];
  if (home === undefined) return undefined;
  return steps.some((step) => step.id === home.step) ? home : undefined;
}

// ── How it is saved (images 41, 44) ────────────────────────────────────────

/** The number a NEW version takes — one past the highest the plan has. */
export function nextVersionNumber(row: Pick<PlanEditRow, "version" | "versions">): number {
  return Math.max(row.version, ...row.versions.map((one) => one.version)) + 1;
}

/** A day as the utility reads it, or a dash. */
export function dayText(value: string | null | undefined, timeZone: string, dateFormat: RegionalDateFormat): string {
  return value === null || value === undefined || value === "" ? "—" : formatDate(value, timeZone, dateFormat);
}
