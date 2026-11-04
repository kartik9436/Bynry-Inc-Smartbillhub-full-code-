// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax DETAILS page, built from
//           images 18–23 of 05-prototype/taxes-fees-2026-10-03 (B14 rule 42).
// Defect:   DEF-RAT-9272 (P29–P43)
// Rules:    B14 rule 31 (no database id on screen) · rule 33 (labels and facts,
//           no rationale) · rule 37 (every drawn figure is an illustration) ·
//           BR-RAT-087 (the server's display strings, never a stored fraction)
// Tests:    src/features/rating/taxDetail/taxDetail.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * THE PURE HALF OF THE TAX DETAILS PAGE — every fact the page shows, worked
 * out from the served row, with no React in it, so each rule can be asserted
 * without mounting a page.
 *
 * ⚠ **THE EDIT DOOR IS ONE ADDRESS AND IT IS SPELLED ONCE, HERE.** The edit
 * lane (round 3 task 7) builds the form behind it in parallel, and the two
 * lanes agreed the door before either was built:
 * `/plans-rates/taxes-fees/:id/edit?change=info|change|correct`. Header *Edit*
 * opens `change=info`; *Fix the rate* on the over-20% band opens
 * `change=correct`. `taxDetail.dom.test.tsx` asserts the literal address, so
 * the day either half moves without the other the suite goes red and names it
 * (hard-won law 2).
 */
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { Fact } from "@/components/FactBlock";
import type { TaxAuditEntry, TaxDetailRow } from "@/api/taxDetailEndpoints";

import { taxWizardEditPath } from "../definitionDetail";
import { taxIsOverTwenty, taxListRate } from "../taxListParts";
import { EXAMPLE_BILL, emptyTaxFormDraft, exampleBill, fractionToPercent } from "../taxForm/taxFormModel";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

export interface TaxRegional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** A value the server did not send — never a zero, never blank. */
export const DASH = "—";

// ── The edit door ─────────────────────────────────────────────────────────

/** The three ways into the edit form (README point 6). */
export const TAX_EDIT_CHANGES = ["info", "change", "correct"] as const;
export type TaxEditChange = (typeof TAX_EDIT_CHANGES)[number];

/** The query parameter the edit form reads to open on one of the three. */
export const TAX_EDIT_CHANGE_PARAM = "change";

/** `/plans-rates/taxes-fees/<id>/edit?change=<change>` — the agreed door. */
export function taxEditDoor(taxId: string, change: TaxEditChange): string {
  return `${taxWizardEditPath(taxId)}?${TAX_EDIT_CHANGE_PARAM}=${change}`;
}

// ── Tabs ──────────────────────────────────────────────────────────────────

/** PO round 6: Overview · Plans · Audit. There is no Rate history tab. */
export const TAX_DETAIL_TABS = ["overview", "plans", "audit"] as const;
export type TaxDetailTab = (typeof TAX_DETAIL_TABS)[number];

/** An unknown or old tab name falls back to Overview — `versions`, the tab's
 *  name before CR-087, still opens Audit so links already sent keep working. */
export function taxDetailTabFrom(raw: string | null): TaxDetailTab {
  if (raw === "versions") return "audit";
  return (TAX_DETAIL_TABS as readonly string[]).includes(raw ?? "") ? (raw as TaxDetailTab) : "overview";
}

// ── The header ────────────────────────────────────────────────────────────

/** `09/01/2026 – 11/10/2027`, or `01/01/2026 – no end`. */
export function taxWindowText(row: TaxDetailRow, regional: TaxRegional, t: Translator): string | null {
  if (row.effective_from === null) return null;
  const from = formatDate(row.effective_from, regional.timeZone, regional.dateFormat);
  const to =
    row.effective_to === null
      ? t("rating.taxDetail.noEnd")
      : formatDate(row.effective_to, regional.timeZone, regional.dateFormat);
  return `${from} – ${to}`;
}

/** *Filing due* is shown on an ACTIVE tax only (PO round 7). */
export function filingDueShown(row: TaxDetailRow): boolean {
  return row.status === "active" && typeof row.next_filing_due === "string" && row.next_filing_due !== "";
}

/** *Next: 6.5% from 01/01/2027* — only when a later version is saved. */
export function scheduledNextShown(row: TaxDetailRow): boolean {
  return (
    row.scheduled_next !== null &&
    row.scheduled_next !== undefined &&
    typeof row.scheduled_next.effective_from === "string"
  );
}

/** The authority the header names — its name, or its level when unnamed. */
export function authorityText(row: TaxDetailRow, t: Translator): string | null {
  const jurisdiction = row.jurisdiction;
  if (jurisdiction === null) return null;
  if (jurisdiction.name.trim() !== "") return jurisdiction.name;
  return jurisdiction.level === null ? null : t(`rating.taxes.level.${jurisdiction.level}`);
}

// ── The over-20% band ─────────────────────────────────────────────────────

export { taxIsOverTwenty };

/**
 * What this tax adds to the drawing's $60.00 example bill — *"On a $60.00
 * bill it adds $90.00"*. The same arithmetic the New form's warning uses
 * (`exampleBill`), fed the served rate read back as the percent it means, so
 * the details page and the form cannot quote two figures for one rate.
 */
export function overTwentyEffect(row: TaxDetailRow): string | null {
  const draft = {
    ...emptyTaxFormDraft(),
    basis: row.kind ?? "",
    rate_percent: fractionToPercent(row.rate),
    base_includes_usage: row.base_includes_usage,
    base_includes_base: row.base_includes_base,
    discount_treatment: row.discount_treatment,
  };
  return exampleBill(draft).effect;
}

export { EXAMPLE_BILL };

// ── The four tiles ────────────────────────────────────────────────────────

/** The Rate tile's figure: the server's display string alone (P34). */
export function taxRateFigure(row: TaxDetailRow, t: Translator): string {
  return taxListRate(row, t);
}

/** The words under the Rate tile. */
export function taxRateUnitKey(row: TaxDetailRow): string {
  if (row.kind === "percent") return "rating.taxDetail.kpi.rateUnit.percent";
  if (row.kind === "flat_per_bill") return "rating.taxDetail.kpi.rateUnit.flat";
  if (row.kind === "per_meter") return "rating.taxDetail.kpi.rateUnit.meter";
  return "rating.taxDetail.kpi.rateUnit.unit";
}

// ── The two fact grids ────────────────────────────────────────────────────

/** Literal keys, so G18 can see every one of them is used. */
const BASIS_KEYS: Readonly<Record<string, string>> = {
  percent: "rating.taxForm.option.basis.percent",
  flat_per_bill: "rating.taxForm.option.basis.flat_per_bill",
  per_unit: "rating.taxForm.option.basis.per_unit",
  per_meter: "rating.taxForm.option.basis.per_meter",
};
const BOUNDARY_KEYS: Readonly<Record<string, string>> = {
  everywhere: "rating.taxForm.option.boundary.everywhere",
  city_limits: "rating.taxForm.option.boundary.city_limits",
  state: "rating.taxForm.option.boundary.state",
};
const DUE_KEYS: Readonly<Record<string, string>> = {
  "15th_next_month": "rating.taxForm.option.due.15th_next_month",
  "20th_next_month": "rating.taxForm.option.due.20th_next_month",
  "25th_next_month": "rating.taxForm.option.due.25th_next_month",
  last_day_next_month: "rating.taxForm.option.due.last_day_next_month",
  "30_days_after_quarter": "rating.taxForm.option.due.30_days_after_quarter",
  jan_31_next_year: "rating.taxForm.option.due.jan_31_next_year",
};
const FILING_KEYS: Readonly<Record<string, string>> = {
  monthly: "rating.taxForm.option.filing.monthly",
  quarterly: "rating.taxForm.option.filing.quarterly",
  annual: "rating.taxForm.option.filing.annual",
};
const ROUNDING_KEYS: Readonly<Record<string, string>> = {
  half_up: "rating.taxForm.rounding.half_up",
  half_even: "rating.taxForm.rounding.half_even",
  up: "rating.taxForm.rounding.up",
  down: "rating.taxForm.rounding.down",
  truncate: "rating.taxForm.rounding.truncate",
};
const DISCOUNT_KEYS: Readonly<Record<string, string>> = {
  after: "rating.taxForm.discount.after",
  before: "rating.taxForm.discount.before",
};
const INTEREST_BASIS_KEYS: Readonly<Record<string, string>> = {
  daily: "rating.taxDetail.per.day",
  monthly: "rating.taxForm.perMonthShort",
  annual: "rating.taxDetail.per.year",
};

/** A stored code read through a literal key map; an unknown code shows as
 *  itself (a value saved before the codes existed), never as a blank. */
function coded(map: Readonly<Record<string, string>>, value: string | null | undefined, t: Translator): string {
  if (value === null || value === undefined || value === "") return DASH;
  const key = map[value];
  return key === undefined ? value : t(key);
}

function text(value: string | null | undefined): string {
  return value === null || value === undefined || value.trim() === "" ? DASH : value;
}

export function servicesText(codes: readonly string[], t: Translator): string {
  if (codes.length === 0) return t("rating.taxForm.allServices");
  return codes.map((code) => t(`rating.service.${code}`, { defaultValue: code })).join(", ");
}

export function classesText(codes: readonly string[], t: Translator): string {
  if (codes.length === 0) return t("rating.taxes.list.everyClass");
  return codes.map((code) => t(`rating.customerClass.${code}`, { defaultValue: code })).join(", ");
}

function boundaryText(row: TaxDetailRow, t: Translator): string {
  const kind = row.premises_scope_kind ?? "everywhere";
  const label = coded(BOUNDARY_KEYS, kind, t);
  const place = row.premises_scope_value?.trim() ?? "";
  return place === "" ? label : `${label} · ${place}`;
}

function taxedText(row: TaxDetailRow, t: Translator): string {
  if (row.kind !== "percent") return DASH;
  const parts = [
    row.base_includes_usage ? t("rating.taxForm.taxed.usage") : null,
    row.base_includes_base ? t("rating.taxForm.taxed.base") : null,
  ].filter((part): part is string => part !== null);
  return parts.length === 0 ? DASH : parts.join(", ");
}

function dayText(value: string | null, regional: TaxRegional): string {
  return value === null ? DASH : formatDate(value, regional.timeZone, regional.dateFormat);
}

/** *Rate and scope* — what the tax charges and who it reaches (image 18). */
export function rateAndScopeFacts(row: TaxDetailRow, t: Translator, regional: TaxRegional): Fact[] {
  return [
    { id: "basis", label: t("rating.taxForm.field.basis"), value: coded(BASIS_KEYS, row.kind, t) },
    { id: "rate", label: t("rating.taxForm.field.rate"), value: taxRateFigure(row, t) },
    { id: "taxed", label: t("rating.taxForm.field.taxed"), value: taxedText(row, t) },
    { id: "services", label: t("rating.taxForm.field.services"), value: servicesText(row.applies_to_services, t) },
    {
      id: "classes",
      label: t("rating.taxForm.field.classes"),
      value: classesText(row.applies_to_customer_classes, t),
    },
    { id: "boundary", label: t("rating.taxForm.field.boundary"), value: boundaryText(row, t) },
    { id: "from", label: t("rating.taxForm.field.from"), value: dayText(row.effective_from, regional) },
    {
      id: "to",
      label: t("rating.taxForm.field.to"),
      value: row.effective_to === null ? t("rating.taxes.list.noEnd") : dayText(row.effective_to, regional),
    },
    {
      id: "discounts",
      label: t("rating.taxDetail.fact.discountsRounding"),
      value: `${coded(DISCOUNT_KEYS, row.discount_treatment, t)} · ${coded(ROUNDING_KEYS, row.rounding_rule, t)}`,
    },
  ];
}

function liabilityText(row: TaxDetailRow): string {
  const code = row.gl_account_code ?? null;
  const name = row.gl_account_name ?? null;
  if (code === null) return DASH;
  return name === null ? code : `${code} · ${name}`;
}

function interestText(row: TaxDetailRow, t: Translator): string {
  const figure = row.interest_penalty_percent_display;
  if (figure === null || figure === undefined || figure === "") return DASH;
  const basis = row.interest_penalty_basis;
  const key = basis === null ? undefined : INTEREST_BASIS_KEYS[basis];
  return key === undefined ? figure : `${figure} ${t(key)}`;
}

/** *On the bill and filing* — everything step 3 of the New form collects. */
export function billAndFilingFacts(row: TaxDetailRow, t: Translator): Fact[] {
  return [
    { id: "code", label: t("rating.taxForm.field.code"), value: text(row.code) },
    { id: "billLabel", label: t("rating.taxForm.field.billLabel"), value: text(row.bill_label ?? row.name) },
    { id: "liability", label: t("rating.taxForm.field.liability"), value: liabilityText(row) },
    { id: "filed", label: t("rating.taxForm.field.filed"), value: coded(FILING_KEYS, row.filing_frequency, t) },
    { id: "due", label: t("rating.taxForm.field.due"), value: coded(DUE_KEYS, row.due_date_rule, t) },
    {
      id: "authorityAccount",
      label: t("rating.taxForm.field.authorityAccount"),
      value: text(row.authority_account?.label ?? null),
    },
    {
      id: "allowance",
      label: t("rating.taxForm.field.allowance"),
      value: text(row.collection_allowance_percent_display),
    },
    { id: "interest", label: t("rating.taxForm.field.interest"), value: interestText(row, t) },
    { id: "reminder", label: t("rating.taxForm.field.reminder"), value: text(row.filing_reminder_recipient) },
  ];
}

// ── The Audit tab ─────────────────────────────────────────────────────────

/** The WHAT column's word for each action the server writes (§9). */
const ACTION_KEYS: Readonly<Record<string, string>> = {
  "tax.created": "rating.taxDetail.audit.action.created",
  "tax.updated": "rating.taxDetail.audit.action.updated",
  "tax.corrected": "rating.taxDetail.audit.action.corrected",
  "tax.correction_created": "rating.taxDetail.audit.action.correctionCreated",
  "tax.new_rate_created": "rating.taxDetail.audit.action.newRate",
  "tax.ended_for_new_rate": "rating.taxDetail.audit.action.endedForNewRate",
  "tax.retired": "rating.taxDetail.audit.action.retired",
  "tax.attached_to_plan": "rating.taxDetail.audit.action.attached",
  "tax.detached_from_plan": "rating.taxDetail.audit.action.detached",
  "tax.deactivated": "rating.taxDetail.audit.action.deactivated",
  "tax.activated": "rating.taxDetail.audit.action.activated",
  "tax.reactivated": "rating.taxDetail.audit.action.activated",
};

export function auditWhat(action: string, t: Translator): string {
  const key = ACTION_KEYS[action];
  return key === undefined ? action : t(key);
}

/** The field labels the CHANGE column names — the New form's own words. */
const FIELD_KEYS: Readonly<Record<string, string>> = {
  name: "rating.taxForm.field.name",
  code: "rating.taxForm.field.code",
  bill_label: "rating.taxForm.field.billLabel",
  kind: "rating.taxForm.field.basis",
  rate_display: "rating.taxForm.field.rate",
  flat_amount: "rating.taxForm.field.rate",
  per_unit_amount: "rating.taxForm.field.rate",
  per_meter_amount: "rating.taxForm.field.rate",
  per_unit_uom: "rating.taxForm.field.uom",
  applies_to_services: "rating.taxForm.field.services",
  applies_to_customer_classes: "rating.taxForm.field.classes",
  premises_scope_kind: "rating.taxForm.field.boundary",
  premises_scope_value: "rating.taxForm.field.place",
  effective_from: "rating.taxForm.field.from",
  effective_to: "rating.taxForm.field.to",
  filing_frequency: "rating.taxForm.field.filed",
  due_date_rule: "rating.taxForm.field.due",
  filing_reminder_recipient: "rating.taxForm.field.reminder",
  authority_account: "rating.taxForm.field.authorityAccount",
  gl_account_code: "rating.taxForm.field.liability",
  discount_treatment: "rating.taxForm.field.discounts",
  status: "rating.taxDetail.audit.field.status",
};

/** Fields the CHANGE column skips: a version number moves with every write
 *  and says nothing a clerk did; the other three repeat a field already named. */
const QUIET_FIELDS = new Set(["version", "tax_type", "filing_form", "remit_method", "remit_reference", "remit_to", "applies_above_units"]);

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function auditValue(field: string, value: unknown, t: Translator, regional: TaxRegional): string {
  if (value === null || value === undefined || value === "") {
    if (field === "effective_to") return t("rating.taxes.list.noEnd");
    return DASH;
  }
  if (Array.isArray(value)) {
    const codes = value.map(String);
    if (field === "applies_to_services") return servicesText(codes, t);
    if (field === "applies_to_customer_classes") return classesText(codes, t);
    return codes.length === 0 ? DASH : codes.join(", ");
  }
  const raw = String(value);
  if (field === "status") return t(`rating.status.${raw}`, { defaultValue: raw });
  if (field === "kind") return coded(BASIS_KEYS, raw, t);
  if (field === "premises_scope_kind") return coded(BOUNDARY_KEYS, raw, t);
  if (field === "due_date_rule") return coded(DUE_KEYS, raw, t);
  if (field === "filing_frequency") return coded(FILING_KEYS, raw, t);
  if (field === "discount_treatment") return coded(DISCOUNT_KEYS, raw, t);
  if (ISO_DAY.test(raw)) return formatDate(raw, regional.timeZone, regional.dateFormat);
  return raw;
}

/**
 * The CHANGE column: each field that moved as *Ends: No end → 11/10/2027*, and
 * on a create the snapshot's rate and services; on a plan link, the plan's
 * NAME (the server writes the name, never the id — B14 rule 31).
 */
export function auditChange(entry: TaxAuditEntry, t: Translator, regional: TaxRegional): string {
  const after = entry.after ?? {};
  const before = entry.before;
  if (typeof after.plan === "string") return after.plan;
  if (before === null) {
    const parts = ["status", "rate_display", "applies_to_services"]
      .filter((field) => field in after && after[field] !== null && after[field] !== undefined)
      .map((field) => auditValue(field, after[field], t, regional));
    return parts.length === 0 ? DASH : parts.join(" · ");
  }
  const fields = Object.keys(after).filter((field) => !QUIET_FIELDS.has(field) && field !== "reason");
  if (fields.length === 0) return DASH;
  return fields
    .map((field) => {
      const key = FIELD_KEYS[field];
      const label = key === undefined ? field : t(key);
      return `${label}: ${auditValue(field, before[field], t, regional)} → ${auditValue(field, after[field], t, regional)}`;
    })
    .join(" · ");
}

/** WHO — the actor's NAME; an unnamed system job reads *System*. */
export function auditWho(entry: TaxAuditEntry, t: Translator): string {
  const name = entry.actor?.name ?? null;
  return name === null || name.trim() === "" ? t("rating.taxDetail.audit.system") : name;
}
