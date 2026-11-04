// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — the New plan form, built from images
//           04–23 of `05-prototype/plans-2026-10-03/images/`.
// Defects:  DEF-RAT-9332 (the form against the drawing) · DEF-RAT-9328 (the late
//           fee bound silently — form side) · DEF-RAT-9287 (minimum bill read
//           back as 10.000000) · DEF-RAT-9285 (a database id in a note)
// Contract: CR-167-BRC10 §7.3 — `GET /plans/form-options`, `POST /plans`
// Rules:    PO rulings 1–14 of 2026-10-03 (README) · CLAUDE.md hard rule 2
//           (money is a decimal string, never a float) · BR-RAT-1011 (the late
//           fee is settable AND clearable)
// ───────────────────────────────────────────────────────
//
// THE PURE HALF OF THE FORM — no React, so every rule below is a unit test.
//
// ⚠ **EVERY TABLE IS A LIST OF ROWS WITH A KEY OF ITS OWN.** A row is added
// empty (*+ Add service*) and refused BY NAME until it is chosen or removed
// (ruling 6), so a row has to exist before it has a value — which is why the
// key is not the value.
//
// ⚠ **THE LATE FEE IS A ROW, NEVER A SILENT DEFAULT (`DEF-RAT-9328`).** Before
// this form, `POST /plans` omitted the key and the server wrote `LATE` onto
// every new plan with no control to see or remove it. Here the utility's
// default codes (`default_on_new_plan`) arrive as ROWS of the Charge codes
// table — visible, removable with ×, listed on Review — and the payload ALWAYS
// carries `charge_codes`, so the server is never left to fill it in.
import { scaledAmount, sumAmounts, unscaledAmount } from "@/components/moneyMath";

import type {
  PlanChargeSection,
  PlanDepositSection,
  PlanDiscountSection,
  PlanFormOptions,
  PlanFormScheduleOption,
  PlanIntendedFor,
  PlanSections,
  PlanServiceSection,
  PlanTaxSection,
} from "@/api/planFormEndpoints";

// ── The draft ──────────────────────────────────────────────────────────────

export interface PlanServiceRow {
  key: string;
  service: string;
  schedule: string; // the schedule's id
  surcharged: boolean;
}

/** A charge code, tax or deposit row: one picked id. */
export interface PlanPickRow {
  key: string;
  value: string;
}

export interface PlanDiscountRow {
  key: string;
  discount: string;
  offered_from: string;
  offered_until: string;
}

export interface PlanNoteRow {
  key: string;
  attribute: string;
  operator: string;
  value: string;
}

/** Every value is a STRING or a boolean, start to finish (hard rule 2). */
export interface PlanFormDraft {
  // Details
  name: string;
  code: string;
  /** `[]` is EVERY class (ruling 4). Values are the classes' ids. */
  customer_classes: string[];
  description: string;
  intended_for: PlanIntendedFor;
  notes: PlanNoteRow[];
  // Services
  services: PlanServiceRow[];
  outside_city: "no" | "yes";
  outside_city_percent: string;
  // Charges
  charge_codes: PlanPickRow[];
  /** Set by the first edit of the Charge codes table — until then the
   *  utility's default codes are shown as rows (`withOptionDefaults`). */
  charge_codes_touched: boolean;
  taxes: PlanPickRow[];
  // Billing
  deposits: PlanPickRow[];
  discounts: PlanDiscountRow[];
  budget_billing: boolean;
  minimum_bill: string;
  // Review
  effective_from: string;
  effective_to: string;
}

export function emptyPlanFormDraft(): PlanFormDraft {
  return {
    name: "",
    code: "",
    customer_classes: [],
    description: "",
    intended_for: { cap_proof: false, min_demand_25kw: false, owner_occupied: false },
    notes: [],
    services: [],
    outside_city: "no",
    outside_city_percent: "",
    charge_codes: [],
    charge_codes_touched: false,
    taxes: [],
    deposits: [],
    discounts: [],
    budget_billing: false,
    minimum_bill: "",
    effective_from: "",
    effective_to: "",
  };
}

let rowCounter = 0;

/** A fresh, never-rendered row key. */
export function rowKey(prefix: string): string {
  rowCounter += 1;
  return `${prefix}-${rowCounter}`;
}

export function newServiceRow(): PlanServiceRow {
  return { key: rowKey("svc"), service: "", schedule: "", surcharged: false };
}

export function newPickRow(prefix: string): PlanPickRow {
  return { key: rowKey(prefix), value: "" };
}

export function newDiscountRow(): PlanDiscountRow {
  return { key: rowKey("disc"), discount: "", offered_from: "", offered_until: "" };
}

export function newNoteRow(): PlanNoteRow {
  return { key: rowKey("note"), attribute: "", operator: "", value: "" };
}

/**
 * The draft with the server's defaults filled in — never over a choice. Today
 * that is one thing: the utility's default charge codes (the late fee) as rows,
 * until the clerk first edits the table.
 */
export function withOptionDefaults(draft: PlanFormDraft, options: PlanFormOptions): PlanFormDraft {
  if (draft.charge_codes_touched || draft.charge_codes.length > 0) return draft;
  const defaults = options.charge_codes.filter((row) => row.default_on_new_plan);
  if (defaults.length === 0) return draft;
  return {
    ...draft,
    charge_codes: defaults.map((row) => ({ key: `default-${row.ref.id}`, value: row.ref.id })),
  };
}

// ── The note grammar (BR-RAT-097, advisory only — BR-RAT-043) ─────────────

/** r10's five operators — the same vocabulary the old step 7 offered. */
export const NOTE_OPERATORS = ["is", "is_not", "lte", "gte", "in_list"] as const;

export const NOTE_ATTRIBUTE_CLASS = "customer_class";
export const NOTE_ATTRIBUTE_SERVICE = "service";

// ── Steps ──────────────────────────────────────────────────────────────────

export type PlanStepId = "details" | "services" | "charges" | "billing" | "review";

/** A step of the form — the New form uses all five; round 3's Edit variations
 *  drop, rename or reorder them without touching a component. */
export interface PlanFormStepSpec {
  id: PlanStepId;
  labelKey: string;
}

export const NEW_PLAN_STEPS: readonly PlanFormStepSpec[] = [
  { id: "details", labelKey: "rating.planForm.step.details" },
  { id: "services", labelKey: "rating.planForm.step.services" },
  { id: "charges", labelKey: "rating.planForm.step.charges" },
  { id: "billing", labelKey: "rating.planForm.step.billing" },
  { id: "review", labelKey: "rating.planForm.step.review" },
];

export function stepNumberOf(id: PlanStepId, steps: readonly PlanFormStepSpec[]): number {
  const index = steps.findIndex((step) => step.id === id);
  return index === -1 ? 1 : index + 1;
}

// ── What a step refuses ────────────────────────────────────────────────────

const MONEY_RE = /^\d+(\.\d{1,2})?$/;
const PERCENT_RE = /^\d+(\.\d{1,4})?$/;

function emptyRows<R>(rows: readonly R[], empty: (row: R) => boolean): boolean {
  return rows.some(empty);
}

/**
 * WHICH boxes on a step are wrong — box id → catalogue key. PRESENCE and SHAPE
 * only; every rule about money and every rule about what may be named together
 * stays the server's (§7.3's refusals map back here through
 * `SERVER_FIELD_BOXES`). `publish` adds the one presence rule that only
 * publishing has: a start date.
 */
export function stepGaps(stepId: PlanStepId, draft: PlanFormDraft, publish = false): Record<string, string> {
  const gaps: Record<string, string> = {};
  if (stepId === "details") {
    if (draft.name.trim() === "") gaps["plan-name"] = "rating.planForm.gap.name";
    if (draft.code.trim() === "") gaps["plan-code"] = "rating.planForm.gap.code";
    if (emptyRows(draft.notes, (row) => row.attribute === "" || row.operator === "" || row.value.trim() === "")) {
      gaps["plan-notes"] = "rating.planForm.gap.noteRow";
    }
  }
  if (stepId === "services") {
    if (draft.services.length === 0) gaps["plan-services"] = "rating.planForm.gap.noService";
    else if (emptyRows(draft.services, (row) => row.service === "")) gaps["plan-services"] = "rating.planForm.gap.serviceRow";
    else if (emptyRows(draft.services, (row) => row.schedule === "")) gaps["plan-services"] = "rating.planForm.gap.scheduleRow";
    if (draft.outside_city === "yes") {
      const percent = draft.outside_city_percent.trim();
      if (percent === "") gaps["plan-surcharge"] = "rating.planForm.gap.surcharge";
      else if (!PERCENT_RE.test(percent)) gaps["plan-surcharge"] = "rating.planForm.gap.number";
    }
  }
  if (stepId === "charges") {
    if (emptyRows(draft.charge_codes, (row) => row.value === "")) gaps["plan-charges"] = "rating.planForm.gap.chargeRow";
    if (emptyRows(draft.taxes, (row) => row.value === "")) gaps["plan-taxes"] = "rating.planForm.gap.taxRow";
  }
  if (stepId === "billing") {
    if (emptyRows(draft.deposits, (row) => row.value === "")) gaps["plan-deposits"] = "rating.planForm.gap.depositRow";
    if (emptyRows(draft.discounts, (row) => row.discount === "")) gaps["plan-discounts"] = "rating.planForm.gap.discountRow";
    else if (
      emptyRows(
        draft.discounts,
        (row) => row.offered_from !== "" && row.offered_until !== "" && row.offered_until < row.offered_from,
      )
    ) {
      gaps["plan-discounts"] = "rating.planForm.gap.offerBackwards";
    }
    const minimum = draft.minimum_bill.trim();
    if (minimum !== "" && !MONEY_RE.test(minimum)) gaps["plan-minimum"] = "rating.planForm.gap.money";
  }
  if (stepId === "review") {
    if (publish && draft.effective_from === "") gaps["plan-starts"] = "rating.planForm.gap.starts";
    if (draft.effective_to !== "" && draft.effective_from !== "" && draft.effective_to < draft.effective_from) {
      gaps["plan-ends"] = "rating.planForm.gap.endsBefore";
    }
  }
  return gaps;
}

/** Every gap on every step before `upTo` — what a publish must clear. */
export function allGaps(draft: PlanFormDraft, steps: readonly PlanFormStepSpec[], publish: boolean): {
  gaps: Record<string, string>;
  firstStep: number | null;
} {
  const gaps: Record<string, string> = {};
  let firstStep: number | null = null;
  steps.forEach((step, index) => {
    const found = stepGaps(step.id, draft, publish);
    if (Object.keys(found).length > 0 && firstStep === null) firstStep = index + 1;
    Object.assign(gaps, found);
  });
  return { gaps, firstStep };
}

// ── What each table may still offer ────────────────────────────────────────

/** The choices a row may pick: everything not already picked by ANOTHER row. */
export function stillOffered<O extends { value: string }>(
  options: readonly O[],
  picked: readonly string[],
  own: string,
): O[] {
  return options.filter((option) => option.value === own || !picked.includes(option.value));
}

/** True when every option is already a row — *+ Add …* greys and says
 *  *All added.* (ruling 6). */
export function allAdded(optionCount: number, rowCount: number): boolean {
  return rowCount >= optionCount;
}

// ── Lookups ────────────────────────────────────────────────────────────────

export function scheduleOf(options: PlanFormOptions, id: string): PlanFormScheduleOption | undefined {
  return id === "" ? undefined : options.schedules.find((row) => row.ref.id === id);
}

export function schedulesFor(options: PlanFormOptions, service: string): PlanFormScheduleOption[] {
  return service === "" ? [] : options.schedules.filter((row) => row.service === service);
}

export function chargeOf(options: PlanFormOptions, id: string): PlanChargeSection | undefined {
  return id === "" ? undefined : options.charge_codes.find((row) => row.ref.id === id);
}

export function taxOf(options: PlanFormOptions, id: string): PlanTaxSection | undefined {
  return id === "" ? undefined : options.taxes.find((row) => row.ref.id === id);
}

export function depositOf(options: PlanFormOptions, id: string): PlanDepositSection | undefined {
  return id === "" ? undefined : options.deposit_codes.find((row) => row.ref.id === id);
}

export function discountOf(options: PlanFormOptions, id: string): PlanDiscountSection | undefined {
  return id === "" ? undefined : options.discounts.find((row) => row.ref.id === id);
}

// ── Figures the form adds up (exact, never `number` — hard rule 2) ─────────

/** Half-up to two places, on a decimal string, exactly. */
export function twoPlacesHalfUp(amount: string): string {
  const scale = Math.max(2, (amount.split(".")[1] ?? "").length);
  const scaled = scaledAmount(amount, scale);
  const step = 10n ** BigInt(scale - 2);
  const negative = scaled < 0n;
  const magnitude = negative ? -scaled : scaled;
  const rounded = (magnitude + step / 2n) / step;
  return unscaledAmount(negative ? -rounded : rounded, 2);
}

/**
 * The services whose picked schedule has no single base figure — the server
 * answered *several base codes* (or none) for the plan's classes. Their own
 * cells name the codes; the total is then not shown (`DEF-RAT-9351`).
 */
export function unresolvedBaseServices(draft: PlanFormDraft, options: PlanFormOptions): string[] {
  return draft.services
    .filter((row) => row.schedule !== "")
    .filter((row) => {
      const base = scheduleOf(options, row.schedule)?.base;
      return base === undefined || base.state !== "ok" || base.monthly_amount === null;
    })
    .map((row) => row.service);
}

/**
 * *Monthly base charges* — J8: the sum, over the chosen services, of each
 * service's base at its smallest size, from the server's own figure. `null`
 * when no chosen row has a schedule yet, AND when any chosen schedule's base
 * does not resolve — a part-sum shown as the plan's total, or `$0.00` for a
 * base the server could not name, reads as a real figure (`DEF-RAT-9351`; the
 * plan read's own `base_total` makes the same call). Callers tell the two
 * apart with `unresolvedBaseServices`.
 */
export function monthlyBaseTotal(draft: PlanFormDraft, options: PlanFormOptions): string | null {
  if (unresolvedBaseServices(draft, options).length > 0) return null;
  const amounts: string[] = [];
  for (const row of draft.services) {
    const monthly = scheduleOf(options, row.schedule)?.base.monthly_amount;
    if (monthly !== null && monthly !== undefined) amounts.push(monthly);
  }
  return amounts.length === 0 ? null : twoPlacesHalfUp(sumAmounts(amounts));
}

/** The figure *Monthly base charges* shows: the total; `"0.00"` before any
 *  schedule is picked (image 04); `null` (a dash) while a picked base does
 *  not resolve — never `$0.00` for a base nobody could name. */
export function monthlyBaseShown(draft: PlanFormDraft, options: PlanFormOptions): string | null {
  if (unresolvedBaseServices(draft, options).length > 0) return null;
  return monthlyBaseTotal(draft, options) ?? "0.00";
}

/** *8.25% combined* — the chosen taxes' points, summed exactly, two places.
 *  `null` with no percentage tax: *none* and *zero* are different facts.
 *  `DEF-RAT-9519` — what a bill on the plan charges: a tax the ticked classes
 *  do not pay is left out, and where they pay different taxes (`some`) there
 *  is no one figure, so `null` — the plan read's own answer. */
export function combinedTaxPercent(draft: PlanFormDraft, options: PlanFormOptions): string | null {
  const rates: string[] = [];
  for (const row of draft.taxes) {
    const tax = taxOf(options, row.value);
    const rate = tax?.rate_percent;
    if (rate === null || rate === undefined || tax === undefined) continue;
    if (tax.reaches_plan_classes === "some") return null;
    if (tax.reaches_plan_classes === "none") continue;
    rates.push(rate);
  }
  return rates.length === 0 ? null : `${twoPlacesHalfUp(sumAmounts(rates))}%`;
}

/** The minimum bill as typed, shown to two places (`DEF-RAT-9287`). */
export function minimumBillDisplay(draft: PlanFormDraft): string | null {
  const typed = draft.minimum_bill.trim();
  return typed === "" || !MONEY_RE.test(typed) ? null : twoPlacesHalfUp(typed);
}

// ── The payload (§7.3 `POST /plans`) ───────────────────────────────────────

export interface PayloadContext {
  /** The classes, so a note naming one stores its NAME (`DEF-RAT-9285`). */
  classLabel: (value: string) => string;
  serviceLabel: (value: string) => string;
}

/** A note's value as stored: a class or service by its NAME, never an id. */
export function noteValueStored(row: PlanNoteRow, context: PayloadContext): string {
  if (row.attribute === NOTE_ATTRIBUTE_CLASS) return context.classLabel(row.value) || row.value;
  if (row.attribute === NOTE_ATTRIBUTE_SERVICE) return context.serviceLabel(row.value) || row.value;
  return row.value.trim();
}

/**
 * The draft → ONE atomic body (BR-SHL-019). Empty rows never travel (Continue
 * refuses them first; this is the floor). A blank minimum bill is OMITTED, not
 * sent as `0`: unset and zero are different facts.
 *
 * ⚠ `charge_codes` IS ALWAYS SENT, INCLUDING AS `[]` — the empty list is the
 * clerk's answer *"this plan charges no late fee"* (BR-RAT-1011's ruled zero),
 * and an omitted key is what let the server bind `LATE` unseen (DEF-RAT-9328).
 */
export function planFormPayload(draft: PlanFormDraft, publish: boolean, context: PayloadContext): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    details: {
      name: draft.name.trim(),
      code: draft.code.trim(),
      description: draft.description.trim() === "" ? null : draft.description.trim(),
      customer_classes: draft.customer_classes,
      intended_for: draft.intended_for,
      notes: draft.notes
        .filter((row) => row.attribute !== "" && row.operator !== "" && row.value.trim() !== "")
        .map((row) => ({ attribute: row.attribute, operator: row.operator, value: noteValueStored(row, context) })),
    },
    services: draft.services
      .filter((row) => row.service !== "")
      .map((row) => ({
        service: row.service,
        schedule: row.schedule === "" ? null : row.schedule,
        surcharged: draft.outside_city === "yes" && row.surcharged,
      })),
    outside_city_percent:
      draft.outside_city === "yes" && draft.outside_city_percent.trim() !== "" ? draft.outside_city_percent.trim() : null,
    charge_codes: draft.charge_codes.filter((row) => row.value !== "").map((row) => ({ charge: row.value })),
    taxes: draft.taxes.filter((row) => row.value !== "").map((row) => ({ tax: row.value })),
    deposits: draft.deposits.filter((row) => row.value !== "").map((row) => ({ charge: row.value })),
    discounts: draft.discounts
      .filter((row) => row.discount !== "")
      .map((row) => ({
        discount: row.discount,
        offered_from: row.offered_from === "" ? null : row.offered_from,
        offered_until: row.offered_until === "" ? null : row.offered_until,
      })),
    budget_billing: draft.budget_billing,
    effective_from: draft.effective_from === "" ? null : draft.effective_from,
    effective_to: draft.effective_to === "" ? null : draft.effective_to,
    publish,
  };
  const minimum = draft.minimum_bill.trim();
  if (minimum !== "") payload.minimum_bill_amount = minimum;
  return payload;
}

// ── The server's field names → the boxes that show them ────────────────────

/** A refusal from `POST /plans` names the SERVER's field (§7.3); this says
 *  which box on which step carries it, so the clerk is taken to the box and
 *  nothing typed is lost. */
export const SERVER_FIELD_BOXES: Readonly<Record<string, { box: string; step: PlanStepId }>> = {
  name: { box: "plan-name", step: "details" },
  "details.name": { box: "plan-name", step: "details" },
  code: { box: "plan-code", step: "details" },
  "details.code": { box: "plan-code", step: "details" },
  customer_classes: { box: "plan-classes", step: "details" },
  "details.customer_classes": { box: "plan-classes", step: "details" },
  description: { box: "plan-description", step: "details" },
  "details.description": { box: "plan-description", step: "details" },
  notes: { box: "plan-notes", step: "details" },
  "details.notes": { box: "plan-notes", step: "details" },
  services: { box: "plan-services", step: "services" },
  outside_city_percent: { box: "plan-surcharge", step: "services" },
  charge_codes: { box: "plan-charges", step: "charges" },
  taxes: { box: "plan-taxes", step: "charges" },
  deposits: { box: "plan-deposits", step: "billing" },
  discounts: { box: "plan-discounts", step: "billing" },
  minimum_bill_amount: { box: "plan-minimum", step: "billing" },
  budget_billing: { box: "plan-budget", step: "billing" },
  effective_from: { box: "plan-starts", step: "review" },
  effective_to: { box: "plan-ends", step: "review" },
};

// ── The draft as the shared sections (Review = details tabs, ruling 11) ────

export interface SectionsContext extends PayloadContext {
  currency: string | null;
  classLabels: (values: readonly string[]) => { value: string; label: string }[];
}

/**
 * The draft in `PlanSections`' shape, so Review mounts the SAME component the
 * details tabs mount (ruling 11) and the two cannot draw one plan two ways.
 * Every figure is the server's (from `form-options`); the form adds only the
 * two sums above.
 */
export function draftSections(draft: PlanFormDraft, options: PlanFormOptions, context: SectionsContext): PlanSections {
  const surcharge = draft.outside_city === "yes" ? draft.outside_city_percent.trim() : "";
  const services: PlanServiceSection[] = draft.services
    .filter((row) => row.service !== "")
    .map((row) => {
      const schedule = scheduleOf(options, row.schedule);
      const service = options.services.find((option) => option.value === row.service);
      return {
        service: row.service,
        name: service?.label ?? row.service,
        gl: service?.gl ?? null,
        schedule: schedule?.ref ?? null,
        base: schedule?.base ?? {
          code: null,
          sized_by_label: null,
          by_size: [],
          flat_display: null,
          state: "none",
          codes: [],
          options: [],
          monthly_amount: null,
        },
        minimum: schedule?.minimum ?? { by_size: [], flat_display: null },
        usage: schedule?.usage ?? { kind: "", kind_label: null, rows: [] },
        outside_city: {
          surcharged: surcharge !== "" && row.surcharged,
          percent_display: surcharge !== "" && row.surcharged ? `${surcharge}%` : null,
        },
      };
    });
  const surchargedNames = services.filter((row) => row.outside_city.surcharged).map((row) => row.name);
  const monthly = monthlyBaseTotal(draft, options);
  return {
    details: {
      name: draft.name.trim(),
      code: draft.code.trim(),
      customer_classes: context.classLabels(draft.customer_classes),
      description: draft.description.trim() === "" ? null : draft.description.trim(),
      intended_for: draft.intended_for,
      notes: draft.notes
        .filter((row) => row.attribute !== "" && row.operator !== "" && row.value.trim() !== "")
        .map((row) => ({ attribute: row.attribute, operator: row.operator, value: noteValueStored(row, context) })),
      minimum_bill_display: minimumBillDisplay(draft),
      budget_billing: draft.budget_billing,
    },
    services,
    base_total: {
      amount_display: monthly,
      unavailable: unresolvedBaseServices(draft, options)[0] ?? null,
    },
    outside_city_surcharge:
      surcharge === "" || surchargedNames.length === 0
        ? null
        : { percent_display: `${surcharge}%`, service_names: surchargedNames },
    charge_codes: draft.charge_codes.flatMap((row) => {
      const found = chargeOf(options, row.value);
      return found === undefined ? [] : [found];
    }),
    taxes: draft.taxes.flatMap((row) => {
      const found = taxOf(options, row.value);
      return found === undefined ? [] : [found];
    }),
    combined_tax_rate_display: combinedTaxPercent(draft, options),
    deposits: draft.deposits.flatMap((row) => {
      const found = depositOf(options, row.value);
      return found === undefined ? [] : [found];
    }),
    discounts: draft.discounts.flatMap((row) => {
      const found = discountOf(options, row.discount);
      return found === undefined
        ? []
        : [
            {
              ...found,
              offered_from: row.offered_from === "" ? null : row.offered_from,
              offered_until: row.offered_until === "" ? null : row.offered_until,
            },
          ];
    }),
    currency: context.currency,
  };
}
