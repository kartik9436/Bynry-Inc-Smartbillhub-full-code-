// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 tasks 4 and 5 — the plan-sections read and the
//           New plan form's lists and save.
// Contract: CR-167-BRC10 §7.3 (AGREED) — `GET /plans/form-options`,
//           `GET /plans/{id}?as_of=` (its sections), `POST /plans`. Names are
//           fixed there and never renamed here; the few fields this lane needed
//           and §7.3 did not name are appended to §7 as "added by FORM" with the
//           reason, in the commit that reads them.
// ───────────────────────────────────────────────────────
//
// Kept in its own file so the server lane, the list lane and this lane do not
// all append to the one 22,000-line `endpoints.ts` at once (the tax and
// discount forms' precedent).
//
// ⚠ **EVERY READ IS NORMALISED, NEVER TRUSTED.** A route not served yet, a
// field missing, a row of the wrong shape: each becomes an EMPTY list or a
// `null`, never a thrown render. The form then shows an empty dropdown and keeps
// working (the round-2 brief), and the shared sections show a dash.
//
// ⚠ **MONEY ARRIVES AS DECIMAL STRINGS AND NOTHING HERE PARSES IT** (hard rule
// 2). `*_display` money is a bare 2-place figure (`"10.00"`) that the screen
// shows with the utility's currency through `formatMoney`; `rate_display` and
// `percent_display` are the server's finished words (`"$4.24 per kgal"`,
// `"6.25%"`). The two raw figures the form adds up — `base.monthly_amount` and
// a tax's `rate_percent` — are summed by `moneyMath`'s exact `BigInt`
// arithmetic, never as `number`.
import { api } from "./client";
import type { ApiClient } from "./client";
import type { PlanDetail } from "./endpoints";

// ── The one reference shape (§7.3) ─────────────────────────────────────────

export type PlanRefKind = "schedule" | "base_code" | "charge_code" | "deposit_code" | "tax" | "discount";

/** Everything a plan names, drawn as *NAME · V2 · from 09/01/2026* (ruling 8). */
export interface PlanRef {
  /** For keying and linking. ⚠ **NEVER RENDERED** — B14 rule 31. */
  id: string;
  kind: PlanRefKind;
  code: string;
  name: string;
  /** The pill; `null` only for a draft item. */
  version: number | null;
  version_label: string | null;
  /** ISO date — *from MM/DD/YYYY*. */
  effective_from: string | null;
  effective_to: string | null;
  /** A later version already filed. */
  next: { version: number | null; effective_from: string | null } | null;
}

export interface PlanGl {
  code: string;
  name: string;
}

export interface PlanOption {
  value: string;
  label: string;
}

/** One size's figure — *5/8"  $10.00*. */
export interface PlanSizeAmount {
  size_class: string;
  size_label: string;
  amount_display: string | null;
}

/** `not_named` (`DEF-RAT-9832`, PO 2026-10-06): the schedule names no base
 *  code, so the bill charges `$0.00` — `flat_display` carries it — and the
 *  screen asks the clerk to choose one. No code is taken from the pool. */
export type PlanBaseState = "ok" | "none" | "ambiguous" | "refused" | "not_named";

/**
 * THE BASE A BILL CHARGES — never the catalogue (`DEF-RAT-9336`). `code` is the
 * schedule's named base code, else the class-narrowed `is_base` code, exactly as
 * the live path resolves it; `ambiguous` lists `codes` and shows no figure.
 */
export interface PlanBaseOption {
  code: string;
  classes: string[];
}

export interface PlanBase {
  code: PlanRef | null;
  /** *meter size*, *cart size*, *fire line size* — the base table's heading.
   *  Added by FORM (§7). `null` reads *Base charges*. */
  sized_by_label: string | null;
  by_size: PlanSizeAmount[];
  flat_display: string | null;
  state: PlanBaseState;
  codes: string[];
  /** `DEF-RAT-9504` — on `ambiguous`, each candidate code with the customer
   *  classes it reaches, by NAME (an every-class plan: the bill picks by the
   *  account's class). Empty otherwise. */
  options: PlanBaseOption[];
  /** J8's figure for this service — the flat base, else the smallest size's —
   *  as a 4-place decimal string. Added by FORM (§7) so the monthly total is a
   *  sum of the server's figures, never of display strings. */
  monthly_amount: string | null;
  /** `DEF-CUS-9821` — the schedule's version in force NAMES its base code.
   *  `false` is New Connect's *"its rate schedule names no base code"*;
   *  absent (an older server) says nothing either way. */
  named?: boolean;
  /** `DEF-CUS-9821` — the served code's customer classes by NAME; `[]` is
   *  every class. */
  classes?: string[];
}

export interface PlanMinimum {
  by_size: PlanSizeAmount[];
  flat_display: string | null;
}

export interface PlanUsageRow {
  label: string;
  rate_display: string;
  /** `DEF-RAT-9502` — the codes behind the server's English words, so each
   *  catalogue words the row: `label_key` names the product's own word
   *  (`over`, `eachMonth`, `allSizes`, `each`, `energy`, `demand`, `share`,
   *  `shareAny`) with `label_args`; null means `label` is the utility's data
   *  (a size, a window). `rate_amount` + `rate_unit` say *per* in the
   *  language. All optional: an older server leaves them out and the English
   *  is drawn as before. */
  label_key?: string | null;
  label_args?: Record<string, string>;
  season?: string | null;
  rate_amount?: string | null;
  rate_unit?: string | null;
}

export interface PlanUsage {
  kind: string;
  /** *Block (per month)*, *Per cart, per month* — the usage table's heading.
   *  Added by FORM (§7). */
  kind_label: string | null;
  rows: PlanUsageRow[];
}

export interface PlanScheduleRef extends PlanRef {
  model: string;
  model_label: string | null;
}

export interface PlanServiceSection {
  service: string;
  name: string;
  gl: PlanGl | null;
  schedule: PlanScheduleRef | null;
  base: PlanBase;
  minimum: PlanMinimum;
  usage: PlanUsage;
  outside_city: { surcharged: boolean; percent_display: string | null };
}

export interface PlanPricedRow {
  class_or_size_label: string;
  /** `DEF-RAT-9502` — true where the server's label is its English *Everyone*. */
  everyone?: boolean;
  amount_display: string | null;
  percent_display: string | null;
  min_display: string | null;
}

export type PlanPricedBy = "class" | "size" | "one_amount" | "percent";

export interface PlanChargeSection {
  ref: PlanRef;
  priced_by: PlanPricedBy | string;
  rows: PlanPricedRow[];
  gl: PlanGl | null;
  type_label: string | null;
  when_label: string | null;
  /** PO 2026-10-06 11 (a) — a penalty code's late-fee grace; `from` is
   *  `plan` for an override the plan stated before the ruling. */
  grace?: PlanGrace | null;
}

export interface PlanGrace {
  days: number;
  mode: "calendar" | "business" | string;
  from: "plan" | "charge_code" | "billing_defaults" | string;
}

export interface PlanTaxSection {
  ref: PlanRef;
  rate_display: string | null;
  /** The rate in percentage POINTS as a 6-place decimal string (`"6.250000"`),
   *  summed exactly for the form's *combined*. Added by FORM (§7). */
  rate_percent: string | null;
  what_is_taxed_label: string | null;
  /** `DEF-RAT-9502` — `usage`, `base`: what the tax is levied on, as codes. */
  what_is_taxed?: string[];
  gl: PlanGl | null;
  /** *Texas Comptroller of Public Accounts* — kept under the name so the
   *  details page loses no fact (CR-167 §5.5). Added by FORM (§7). */
  authority: string | null;
  brought_by: "jurisdiction" | "attached" | string;
  /** `DEF-RAT-9519` — do the plan's classes pay it? `none` is listed MARKED
   *  and left out of *combined*; any `some` means no one combined figure. */
  reaches_plan_classes?: "all" | "some" | "none";
  /** `DEF-CUS-9821` — who pays it, by NAME; `[]` is every class. */
  customer_classes?: string[];
}

export interface PlanDepositSection {
  ref: PlanRef;
  priced_by: PlanPricedBy | string;
  rows: PlanPricedRow[];
  gl: PlanGl | null;
}

/**
 * A deposit as the SHARED SECTIONS read serves it (`plan_reads._deposits`):
 * a deposit code, or — `ref: null` — a TYPED `plan_deposit_rules` row, the
 * plan's own figure with no code behind it (`DEF-RAT-9740`). Only the sections
 * read carries the typed kind; `form-options` deposit codes always have a ref.
 */
export type PlanSectionDeposit = Omit<PlanDepositSection, "ref"> & {
  ref: PlanRef | null;
  /** `DEF-CUS-9821` — the code's type is *refundable*; `null` for a typed rule. */
  refundable?: boolean | null;
};

export interface PlanDiscountSection {
  ref: PlanRef;
  value_display: string | null;
  gl: PlanGl | null;
  enrolled: number | null;
  offered_from: string | null;
  offered_until: string | null;
  /** `DEF-CUS-9821` — `automatic` | `apply_and_approve`, from the version in
   *  force; and whether proof is asked. Absent on an older server. */
  enrolment_mode?: string | null;
  proof_required?: boolean | null;
}

export interface PlanIntendedFor {
  cap_proof: boolean;
  min_demand_25kw: boolean;
  owner_occupied: boolean;
}

export interface PlanNote {
  attribute: string;
  operator: string;
  value: string;
}

export interface PlanDetailsSection {
  name: string;
  code: string;
  /** `[]` is EVERY class. Labels, never ids (`DEF-RAT-9285`). */
  customer_classes: PlanOption[];
  description: string | null;
  intended_for: PlanIntendedFor;
  notes: PlanNote[];
  minimum_bill_display: string | null;
  budget_billing: boolean;
}

/**
 * EVERYTHING THE SHARED PLAN-SECTIONS COMPONENT DRAWS (ruling 11). The details
 * page reads it from `GET /plans/{id}?as_of=`; the New form's Review builds the
 * SAME shape from its draft and `form-options`, so the two screens cannot draw
 * one plan two ways.
 */
export interface PlanSections {
  details: PlanDetailsSection;
  services: PlanServiceSection[];
  base_total: { amount_display: string | null; unavailable: string | null };
  /** *25% on Water, Sewer* — the plan's surcharge and the services it
   *  reaches; `null` when it has none. Added by FORM (§7). */
  outside_city_surcharge: { percent_display: string; service_names: string[] } | null;
  charge_codes: PlanChargeSection[];
  taxes: PlanTaxSection[];
  combined_tax_rate_display: string | null;
  deposits: PlanSectionDeposit[];
  discounts: PlanDiscountSection[];
  /** CHAR(3), the utility's own; `null` until read. */
  currency: string | null;
}

// ── `GET /plans/form-options` ──────────────────────────────────────────────

export interface PlanFormServiceOption extends PlanOption {
  gl: PlanGl | null;
}

/** A schedule the Services row can pick, with what that row shows once it is
 *  picked: base and minimum (ruling 7) and the usage block Review draws. */
export interface PlanFormScheduleOption {
  ref: PlanScheduleRef;
  service: string;
  base: PlanBase;
  minimum: PlanMinimum;
  usage: PlanUsage;
}

export interface PlanFormChargeOption extends PlanChargeSection {
  /** The utility's default late-fee code is offered PRE-FILLED as a row on a
   *  new plan, visible and removable — `DEF-RAT-9328`. Added by FORM (§7). */
  default_on_new_plan: boolean;
}

export interface PlanNoteAttribute {
  key: string;
  label: string;
  values: PlanOption[];
}

export interface PlanFormOptions {
  services: PlanFormServiceOption[];
  schedules: PlanFormScheduleOption[];
  charge_codes: PlanFormChargeOption[];
  taxes: PlanTaxSection[];
  discounts: PlanDiscountSection[];
  deposit_codes: PlanDepositSection[];
  /** *Every customer class* is the screen's own first row, not one of these. */
  customer_classes: PlanOption[];
  currency: string | null;
}

export const EMPTY_PLAN_FORM_OPTIONS: PlanFormOptions = {
  services: [],
  schedules: [],
  charge_codes: [],
  taxes: [],
  discounts: [],
  deposit_codes: [],
  customer_classes: [],
  currency: null,
};

export const PLAN_FORM_OPTIONS_PATH = "/plans/form-options";

// ── Normalisers ────────────────────────────────────────────────────────────

type Raw = Record<string, unknown>;

function obj(raw: unknown): Raw | null {
  return typeof raw === "object" && raw !== null && !Array.isArray(raw) ? (raw as Raw) : null;
}

function str(raw: unknown): string | null {
  return typeof raw === "string" ? raw : typeof raw === "number" ? String(raw) : null;
}

function list(raw: unknown): unknown[] {
  return Array.isArray(raw) ? raw : [];
}

function int(raw: unknown): number | null {
  return typeof raw === "number" && Number.isInteger(raw) ? raw : null;
}

function bool(raw: unknown): boolean {
  return raw === true;
}

export function normaliseRef(raw: unknown, kind: PlanRefKind): PlanRef | null {
  const row = obj(raw);
  if (row === null) return null;
  const id = str(row.id);
  const code = str(row.code);
  if (id === null || code === null) return null;
  const next = obj(row.next);
  return {
    id,
    kind: (str(row.kind) as PlanRefKind | null) ?? kind,
    code,
    name: str(row.name) ?? "",
    version: int(row.version),
    version_label: str(row.version_label),
    effective_from: str(row.effective_from),
    effective_to: str(row.effective_to),
    next: next === null ? null : { version: int(next.version), effective_from: str(next.effective_from) },
  };
}

function scheduleRef(raw: unknown): PlanScheduleRef | null {
  const ref = normaliseRef(raw, "schedule");
  if (ref === null) return null;
  const row = obj(raw) as Raw;
  return { ...ref, model: str(row.model) ?? "", model_label: str(row.model_label) };
}

function gl(raw: unknown): PlanGl | null {
  const row = obj(raw);
  const code = row === null ? null : str(row.code);
  return row === null || code === null ? null : { code, name: str(row.name) ?? "" };
}

function options(raw: unknown): PlanOption[] {
  return list(raw).flatMap((item) => {
    const row = obj(item);
    const value = row === null ? null : str(row.value);
    const label = row === null ? null : str(row.label);
    return value === null || label === null ? [] : [{ value, label }];
  });
}

function sizes(raw: unknown): PlanSizeAmount[] {
  return list(raw).flatMap((item) => {
    const row = obj(item);
    if (row === null) return [];
    const label = str(row.size_label);
    if (label === null) return [];
    return [{ size_class: str(row.size_class) ?? label, size_label: label, amount_display: str(row.amount_display) }];
  });
}

const BASE_STATES: readonly PlanBaseState[] = ["ok", "none", "ambiguous", "refused", "not_named"];

function base(raw: unknown): PlanBase {
  const row = obj(raw) ?? {};
  const state = str(row.state);
  return {
    code: normaliseRef(row.code, "base_code"),
    sized_by_label: str(row.sized_by_label),
    by_size: sizes(row.by_size),
    flat_display: str(row.flat_display),
    state: BASE_STATES.includes(state as PlanBaseState) ? (state as PlanBaseState) : "none",
    codes: list(row.codes).flatMap((code) => (typeof code === "string" ? [code] : [])),
    options: list(row.options).flatMap((raw) => {
      const option = obj(raw);
      const code = option === null ? null : str(option.code);
      if (option === null || code === null) return [];
      return [{ code, classes: list(option.classes).flatMap((name) => (typeof name === "string" ? [name] : [])) }];
    }),
    monthly_amount: str(row.monthly_amount),
    ...(typeof row.named === "boolean" ? { named: row.named } : {}),
    ...(Array.isArray(row.classes) ? { classes: names(row.classes) } : {}),
  };
}

/** A list of names; anything that is not a string is dropped. */
function names(raw: unknown): string[] {
  return list(raw).flatMap((name) => (typeof name === "string" ? [name] : []));
}

function minimum(raw: unknown): PlanMinimum {
  const row = obj(raw) ?? {};
  return { by_size: sizes(row.by_size), flat_display: str(row.flat_display) };
}

function usage(raw: unknown): PlanUsage {
  const row = obj(raw) ?? {};
  return {
    kind: str(row.kind) ?? "",
    kind_label: str(row.kind_label),
    rows: list(row.rows).flatMap((item) => {
      const r = obj(item);
      const label = r === null ? null : str(r.label);
      const rate = r === null ? null : str(r.rate_display);
      if (r === null || label === null || rate === null) return [];
      const args = obj(r.label_args) ?? {};
      return [
        {
          label,
          rate_display: rate,
          label_key: str(r.label_key),
          label_args: Object.fromEntries(Object.entries(args).flatMap(([k, v]) => (str(v) === null ? [] : [[k, str(v) as string]]))),
          season: str(r.season),
          rate_amount: str(r.rate_amount),
          rate_unit: str(r.rate_unit),
        },
      ];
    }),
  };
}

function pricedRows(raw: unknown): PlanPricedRow[] {
  return list(raw).flatMap((item) => {
    const row = obj(item);
    if (row === null) return [];
    return [
      {
        class_or_size_label: str(row.class_or_size_label) ?? "",
        everyone: row.everyone === true,
        amount_display: str(row.amount_display),
        percent_display: str(row.percent_display),
        min_display: str(row.min_display),
      },
    ];
  });
}

function chargeSection(raw: unknown): PlanChargeSection | null {
  const row = obj(raw);
  const ref = row === null ? null : normaliseRef(row.ref, "charge_code");
  if (row === null || ref === null) return null;
  return {
    ref,
    priced_by: str(row.priced_by) ?? "one_amount",
    rows: pricedRows(row.rows),
    gl: gl(row.gl),
    type_label: str(row.type_label),
    when_label: str(row.when_label),
    grace: graceOf(row.grace),
  };
}

/** PO 2026-10-06 11 (a) — a penalty code's grace, or null (any other code). */
function graceOf(raw: unknown): PlanGrace | null {
  const row = obj(raw);
  const days = row === null ? null : int(row.days);
  const mode = row === null ? null : str(row.mode);
  if (row === null || days === null || mode === null) return null;
  return { days, mode, from: str(row.from) ?? "charge_code" };
}

function taxSection(raw: unknown): PlanTaxSection | null {
  const row = obj(raw);
  const ref = row === null ? null : normaliseRef(row.ref, "tax");
  if (row === null || ref === null) return null;
  return {
    ref,
    rate_display: str(row.rate_display),
    rate_percent: str(row.rate_percent),
    what_is_taxed_label: str(row.what_is_taxed_label),
    what_is_taxed: list(row.what_is_taxed).flatMap((code) => (str(code) === null ? [] : [str(code) as string])),
    gl: gl(row.gl),
    authority: str(row.authority),
    brought_by: str(row.brought_by) ?? "attached",
    reaches_plan_classes: taxReach(row.reaches_plan_classes),
    ...(Array.isArray(row.customer_classes) ? { customer_classes: names(row.customer_classes) } : {}),
  };
}

function taxReach(raw: unknown): "all" | "some" | "none" {
  return raw === "none" || raw === "some" ? raw : "all";
}

function depositSection(raw: unknown): PlanDepositSection | null {
  const row = obj(raw);
  const ref = row === null ? null : normaliseRef(row.ref, "deposit_code");
  if (row === null || ref === null) return null;
  return { ref, priced_by: str(row.priced_by) ?? "class", rows: pricedRows(row.rows), gl: gl(row.gl) };
}

/** `DEF-RAT-9740` — the sections read keeps a typed rule (`ref: null`) rather
 *  than dropping the plan's $150.00 on the floor; a malformed ref still goes. */
function sectionDeposit(raw: unknown): PlanSectionDeposit | null {
  const row = obj(raw);
  if (row === null) return null;
  const refundable = typeof row.refundable === "boolean" ? row.refundable : null;
  if (row.ref === null || row.ref === undefined) {
    return { ref: null, priced_by: str(row.priced_by) ?? "class", rows: pricedRows(row.rows), gl: gl(row.gl), refundable };
  }
  const section = depositSection(raw);
  return section === null ? null : { ...section, refundable };
}

function discountSection(raw: unknown): PlanDiscountSection | null {
  const row = obj(raw);
  const ref = row === null ? null : normaliseRef(row.ref, "discount");
  if (row === null || ref === null) return null;
  return {
    ref,
    value_display: str(row.value_display),
    gl: gl(row.gl),
    enrolled: int(row.enrolled),
    offered_from: str(row.offered_from),
    offered_until: str(row.offered_until),
    enrolment_mode: str(row.enrolment_mode),
    proof_required: typeof row.proof_required === "boolean" ? row.proof_required : null,
  };
}

function serviceSection(raw: unknown): PlanServiceSection | null {
  const row = obj(raw);
  const service = row === null ? null : str(row.service);
  if (row === null || service === null) return null;
  const outside = obj(row.outside_city) ?? {};
  return {
    service,
    name: str(row.name) ?? service,
    gl: gl(row.gl),
    schedule: scheduleRef(row.schedule),
    base: base(row.base),
    minimum: minimum(row.minimum),
    usage: usage(row.usage),
    outside_city: { surcharged: bool(outside.surcharged), percent_display: str(outside.percent_display) },
  };
}

function surcharge(raw: unknown): PlanSections["outside_city_surcharge"] {
  const row = obj(raw);
  const percent = row === null ? null : str(row.percent_display);
  if (row === null || percent === null) return null;
  return {
    percent_display: percent,
    service_names: list(row.service_names).flatMap((name) => (typeof name === "string" ? [name] : [])),
  };
}

function compact<T>(rows: (T | null)[]): T[] {
  return rows.filter((row): row is T => row !== null);
}

export function normalisePlanFormOptions(raw: unknown): PlanFormOptions {
  const body = obj(raw) ?? {};
  return {
    services: list(body.services).flatMap((item) => {
      const [option] = options([item]);
      return option === undefined ? [] : [{ ...option, gl: gl((item as Raw).gl) }];
    }),
    schedules: compact(
      list(body.schedules).map((item) => {
        const row = obj(item);
        const ref = row === null ? null : scheduleRef(row.ref);
        const service = row === null ? null : str(row.service);
        if (row === null || ref === null || service === null) return null;
        return { ref, service, base: base(row.base), minimum: minimum(row.minimum), usage: usage(row.usage) };
      }),
    ),
    charge_codes: compact(
      list(body.charge_codes).map((item) => {
        const section = chargeSection(item);
        return section === null ? null : { ...section, default_on_new_plan: bool((item as Raw).default_on_new_plan) };
      }),
    ),
    taxes: compact(list(body.taxes).map(taxSection)),
    discounts: compact(list(body.discounts).map(discountSection)),
    deposit_codes: compact(list(body.deposit_codes).map(depositSection)),
    customer_classes: options(body.customer_classes),
    currency: str(body.currency),
  };
}

/** `GET /plans/{id}`'s sections, for the details tabs (round 3 mounts them). */
export function normalisePlanSections(raw: unknown): PlanSections {
  const body = obj(raw) ?? {};
  const details = obj(body.details) ?? {};
  const intended = obj(details.intended_for) ?? {};
  const total = obj(body.base_total) ?? {};
  return {
    details: {
      name: str(details.name) ?? str(body.name) ?? "",
      code: str(details.code) ?? str(body.code) ?? "",
      customer_classes: options(details.customer_classes),
      description: str(details.description),
      intended_for: {
        cap_proof: bool(intended.cap_proof),
        min_demand_25kw: bool(intended.min_demand_25kw),
        owner_occupied: bool(intended.owner_occupied),
      },
      notes: list(details.notes).flatMap((item) => {
        const row = obj(item);
        if (row === null) return [];
        const attribute = str(row.attribute);
        const operator = str(row.operator);
        const value = str(row.value);
        return attribute === null || operator === null || value === null ? [] : [{ attribute, operator, value }];
      }),
      minimum_bill_display: str(details.minimum_bill_display),
      budget_billing: bool(details.budget_billing),
    },
    services: compact(list(body.services).map(serviceSection)),
    base_total: { amount_display: str(total.amount_display), unavailable: str(total.unavailable) },
    outside_city_surcharge: surcharge(body.outside_city_surcharge),
    charge_codes: compact(list(body.charge_codes).map(chargeSection)),
    taxes: compact(list(body.taxes).map(taxSection)),
    combined_tax_rate_display: str(body.combined_tax_rate_display),
    deposits: compact(list(body.deposits).map(sectionDeposit)),
    discounts: compact(list(body.discounts).map(discountSection)),
    currency: str(body.currency),
  };
}

/**
 * `classes` — the customer classes the plan is for (step 1's ticks; *Every
 * customer class* sends every class). The server narrows each schedule's base
 * to them exactly as the plan's own read does (`CR-167` §7.3, `DEF-RAT-9351`):
 * without them a utility with one water base per class answers *Several base
 * codes* and the form has no figure to add up.
 */
export async function getPlanFormOptions(
  on: string | null = null,
  client: ApiClient = api,
  classes: readonly string[] = [],
): Promise<PlanFormOptions> {
  const query: Record<string, string> = {};
  if (on !== null && on !== "") query.on = on;
  if (classes.length > 0) query.classes = classes.join(",");
  const response = await client.get<unknown>(PLAN_FORM_OPTIONS_PATH, { query });
  return normalisePlanFormOptions(response.data);
}

export async function getPlanSections(
  planId: string,
  asOf: string | null = null,
  client: ApiClient = api,
  /** `DEF-CUS-9821` — an account's class codes: the server narrows each
   *  service's BASE to them, as the bill picks it. Empty = the plan's own. */
  classes: readonly string[] = [],
): Promise<PlanSections> {
  const query: Record<string, string> = {};
  if (asOf !== null && asOf !== "") query.as_of = asOf;
  if (classes.length > 0) query.classes = classes.join(",");
  const response = await client.get<unknown>(`/plans/${encodeURIComponent(planId)}`, { query });
  return normalisePlanSections(response.data);
}

/**
 * `DEF-CUS-9821` — `GET /plans/{id}` ONCE, as both of the shapes it serves:
 * the plan's own row (`PlanDetail`: status, version, dates, classes, minimum)
 * and its sections. New Connect step 2 needs both and the server sends both in
 * one body (`api.plan_item`), so a second request for the same address would
 * be a second read of one fact.
 */
export async function getPlanWithSections(
  planId: string,
  classes: readonly string[] = [],
  client: ApiClient = api,
): Promise<{ detail: PlanDetail; sections: PlanSections }> {
  const query: Record<string, string> = {};
  if (classes.length > 0) query.classes = classes.join(",");
  const response = await client.get<PlanDetail>(`/plans/${encodeURIComponent(planId)}`, { query });
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return { detail: response.data, sections: normalisePlanSections(response.data) };
}

/** What `POST /plans` answers with — only what the saved panel needs. */
export interface PlanFormSaved {
  id: string;
  name: string;
  status: string;
  effective_from: string | null;
}

/** `POST /plans` in §7.3's shape — *Save as draft* (`publish: false`) or
 *  *Publish plan* (`publish: true`) in ONE call (BR-SHL-019). */
export async function savePlanForm(payload: Record<string, unknown>, client: ApiClient = api): Promise<PlanFormSaved> {
  const response = await client.post<unknown>("/plans", payload);
  const row = obj(response.data) ?? {};
  return {
    id: str(row.id) ?? "",
    name: str(row.name) ?? str(obj(row.details)?.name) ?? "",
    status: str(row.status) ?? "",
    effective_from: str(row.effective_from),
  };
}
