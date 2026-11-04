// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W5 task 5.3 — move-in step 4's PRICING PANEL, the frontend
//           half of `GET /units/{id}/pricing` (B18 §5.5.5, marked NEW there).
//           ⚠ NO STORY OWNS IT — hard-won law 8, same finding the backend half
//           reported: B18 widens US-CUS-004 §S19 step 4 and
//           `05-user-stories.md` carries no story for the panel.
//           Screens: S19 (step 4)
// Rules:    BR-RAT-027 (the plan's base-charge Σ is RATING's DERIVED figure —
//           forwarded, never recomputed) · BR-RAT-038 (a schedule priced in a
//           unit the service does not bill in cannot produce a bill, and the
//           screen must be able to say so) · BR-RAT-096 / BR-RAT-113 (tax
//           jurisdiction BINDINGS and explicit ATTACHMENTS are two different
//           sentences and stay two lists) · BR-MET-100 (a unit with no plan is
//           counted and findable, not an error) · BR-CUS-029 (the account plan
//           snapshot has no table — this panel READS the unit's plan and
//           records nothing) · hard rule 2 (money stored 4 dp, percentages 6,
//           both DISPLAY 2) · B14 rule 21 (Tailwind utilities, no stylesheet
//           class) · B4/B5 ❄️ FROZEN
// ───────────────────────────────────────────────────────
// B18 §5.5.3 step 4, verbatim: *"Plan with its rate schedules, charge codes,
// taxes and a worked month; eligibility panel; deposit with carry-forward"* —
// *"WIDENED — today it shows a plan name and one figure"*.
//
// ⛔ **THE WORKED MONTH IS NOT COMPUTED HERE AND MUST NEVER BE.** The server
// serves it as `{served:false, reason:"no_service_prices_a_plan_outside_a_bill_
// run", tracks:"OQ-363"}` and this panel renders that sentence. Two things are
// missing and only ONE of them is an engine:
//
//   (a) **Nothing in this product prices a plan outside a bill run.**
//       `engine.price_bill` / `price_period` are pure functions and every
//       assembly that feeds them is keyed on an ACCOUNT — which a move-in at
//       step 4 does not have yet.
//   (b) **No signed rule says what a brand-new tenant is assumed to CONSUME.**
//       Typical household, the last tenant's usage, or nothing at all are three
//       different dollar figures on the same screen. **(b) stands even if (a)
//       were solved**, which is why it is a QUESTION (OQ-363) before it is a gap.
//
// ⚠ **AND DO NOT "SOLVE" IT BY SUMMING THE BASE CHARGES.** A base-only month
// looks like arithmetic a screen may do and is not: it is BR-RAT-005's tax base
// reimplemented outside the ❄️ FROZEN engine, in TypeScript, where GT-1..61
// cannot see it. No `from $X`, no total, no multiplication of a rate by a
// plausible usage. Every figure below is a STORED string this panel forwards.
//
// ⚠ **WHAT THIS PANEL DOES WITH MONEY, EXACTLY.** It calls `MoneyCell`, which
// is the app's ONE display boundary (BR-SHL-023 / BR-TEN-080: storage 6 dp,
// wire 4 dp, DISPLAY 2 dp). That is a render, not a computation — nothing here
// adds, subtracts, prorates or taxes, and nothing written here is ever sent
// back. `plan.base_charges` is rating's own Σ (BR-RAT-027) and is printed as
// received; this file never sums the `services[]` rows that produce it.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { ArrivesWith } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import type { StatedAbsence } from "./UnitAssetsPanel";
import { formatRate } from "@/components/MoneyCell";
import { formatNamedDate } from "@/components/DateCell";

// ── The wire (read off apps/metering/selectors.unit_pricing) ───────────────
//
// ⚠ Typed here rather than in `src/api/endpoints.ts` for the same lane reason
// `UnitAssetsPanel` states: that file is the app's one typed client (B13 §2)
// and this lane does not own it. The move is OWED.

/** One tier/block of a rate schedule version. Every figure is rating's stored
 *  string, forwarded — `unit_price` is NOT money-formatted as a price per unit
 *  here, it is shown as filed. */
export interface RateTierRow {
  seq: number;
  season: string | null;
  size_class: string | null;
  from_qty: string | null;
  to_qty: string | null;
  unit_price: string | null;
  /** DEF-1121 — the bounds composed by the server with the version's UoM. */
  from_qty_display: string | null;
  to_qty_display: string | null;
}

export interface RateVersionRow {
  id: string;
  model: string | null;
  uom: string | null;
  currency: string | null;
  base_charge: string | null;
  minimum_bill: string | null;
  effective_from: string | null;
  // DEF-1121 — `unit` and `currency` ride with the structure now: a tier
  // BOUND cannot render without its unit and a tier PRICE cannot render
  // without its currency, and this panel had neither.
  structure: {
    model?: string;
    unit?: string | null;
    currency?: string | null;
    tiers?: RateTierRow[];
  } | null;
}

/** BR-RAT-038 — the unit-of-measure gate. `satisfied:false` means this
 *  schedule cannot produce a bill, and step 4 must be able to say so. */
/**
 * **WHAT AXIS PRICES ONE SERVICE** — `CR-089` wave H `H3` (`PUJ-35`,
 * `BR-MET-1166`), served by `apps/metering/selectors._service_priced_on`.
 *
 * ⛔ **A SHAPE, NEVER A PRICE.** Three of the six services on the Product
 * Owner's own Plan tab read `$0.00` — Trash, Solar and **Fire** — and every one
 * of those zeros is CORRECT: fire is priced by the size of the line times how
 * many there are, trash per cart, solar by capacity. The zero was right and
 * read as broken. This is the fact that fixes that, and it carries no figure:
 * the server answers `size_bands` / `capacity` / `no_size_axis` / `not_ruled`
 * out of `apps/tenancy`'s ratified size classes, and the catalogue turns each
 * into one sentence. Nothing is computed here and nothing is inferred from the
 * service CODE — a twelfth service lands on whichever side its own rows put it.
 */
export interface ServicePricedOn {
  shape: "size_bands" | "capacity" | "no_size_axis" | "not_ruled";
  /** The unit a capacity service SUMS in (`kW`, `ERU`, `Mbps`, `ton`). */
  capacity_uom: string | null;
  size_count: number | null;
}

export interface UomGate {
  satisfied: boolean;
  reason: string;
  schedule_uom: string | null;
  /** The DECLARED column — NULL on every tenant ever provisioned (DEF-3201). */
  billed_uom: string | null;
  /**
   * THE UNIT THE THING THAT PRICES IT IS WRITTEN IN — `billed_uom` or, where
   * that is NULL, the register's own unit. This is what a message must name.
   */
  priced_against: string | null;
  conversion_factor: string | null;
}

export interface RateScheduleCard {
  id: string;
  name: string | null;
  service: string | null;
  service_name: string | null;
  structure: string | null;
  status: string | null;
  effective_from: string | null;
  block_count: number | null;
  season_labels: string[] | null;
  window_count: number | null;
  size_count: number | null;
  current_version: RateVersionRow | null;
  uom_gate: UomGate | null;
}

export interface UnitPricingSchedule {
  service: string | null;
  tariff_id: string | null;
  tariff_name: string | null;
  schedule: RateScheduleCard | null;
  /** A plan line whose schedule cannot be read is REPORTED on its own row; the
   *  other services still price on screen. */
  absent: { reason: string } | null;
}

export interface UnitPricingService {
  service: string;
  name: string | null;
  base_charge: string | null;
  currency: string | null;
  minimum_amount: string | null;
  /** CR-089 wave H `H3` — see `ServicePricedOn`. Optional on the wire so a
   *  cached payload from before this landed renders the row without the cell
   *  rather than crashing on it. */
  priced_on?: ServicePricedOn | null;
}

export interface UnitPricingSizeAmount {
  size_class: string | null;
  amount: string | null;
  /** BR-RAT-087 — rating's own two-place string. The client never formats money. */
  amount_display: string | null;
  currency: string | null;
}

export interface UnitPricingChargeCode {
  id: string;
  charge_id: string;
  code: string;
  name: string | null;
  /** NULL = this plan does not restate the price, and the code's own `amount`
   *  below is what bills. The two are DIFFERENT FACTS and neither is collapsed
   *  into an "effective amount" here: which one wins is billing's precedence
   *  rule (DEF-154) and it is not reimplemented on a screen. */
  amount_override: string | null;
  amount_override_display: string | null;
  recurrence: string | null;
  taxable: boolean;
  /** CR-034 (b) — THE CODE'S OWN ROW. This panel used to print *"At the charge
   *  code's own amount"* with no amount: a sentence that promises a figure and
   *  withholds it, which reads as *unknowable* rather than *unfetched*. */
  service: string | null;
  charge_type: string | null;
  /** BR-RAT-088 — declared, never inferred from the code string. An `is_base`
   *  code reaches a bill as its service's BASE (through R4), not as a fee line,
   *  so listing it silently among the fees says it bills twice. */
  is_base: boolean;
  amount_rule: string | null;
  amount: string | null;
  amount_display: string | null;
  percent_display: string | null;
  min_amount_display: string | null;
  max_amount_display: string | null;
  /** BR-RAT-108 — an EMPTY list means EVERY class. Not the same as a named one. */
  applies_to_customer_classes: string[];
  /** DEF-431 — r10's water matrix prices 5/8" at $12.00 and 2" at $64.00. */
  size_amounts: UnitPricingSizeAmount[];
}

/** CR-034 (b) · SECTION 1 — the window this whole answer is about.
 *
 *  `as_of` is the one date every narrowing below resolved on: the period END
 *  (BR-RAT-007, *"the plan version in force on the SERVICE-PERIOD END DATE"*).
 *  `supplied: false` means NO PERIOD WAS INVENTED — `as_of` is the tenant's
 *  today and the heading says so. */
export interface UnitPricingPeriod {
  start: string | null;
  end: string | null;
  as_of: string;
  supplied: boolean;
  source: string;
}

/** One stretch of *"this unit was on THIS plan"* (BR-RAT-114 / DEF-504). */
export interface UnitPricingPlanStretch {
  rate_plan_id: string;
  /** NULL when the plan is no longer published (BR-RAT-030). The id still
   *  travels, so the row is drawn rather than dropped. */
  plan_name: string | null;
  plan_code: string | null;
  plan_version: number | null;
  assigned_from: string | null;
  assigned_to: string | null;
  source: string | null;
}

export interface UnitPricingPlanHistory {
  served: boolean;
  reason: string | null;
  tracks: string | null;
  stretches: UnitPricingPlanStretch[];
  /** The dates a real bill for this period would SPLIT on. */
  splits_at: string[];
}

export interface UnitPricingMinimumCharges {
  plan: { amount: string | null; source: string } | null;
  services: {
    service: string | null;
    name: string | null;
    minimum_amount: string | null;
    currency: string | null;
    source: string;
  }[];
  schedules: {
    service: string | null;
    tariff_id: string | null;
    tariff_name: string | null;
    version_id: string | null;
    /** DEF-MET-8823 — the minimum the version's size row states for THIS
     *  unit's connection size (PO 2026-10-01, option A), never the version's
     *  own figure, which billing no longer charges. Null is "No minimum". */
    minimum_bill: string | null;
    minimum_bill_display: string | null;
    currency: string | null;
    /** The connection size's NAME (B14 rule 31: never its code). */
    size_label: string | null;
    minimum_state: "size_minimum" | "size_has_no_minimum" | "no_size_recorded";
    size_rows: { size_class: string | null; minimum_bill_display: string | null }[];
    source: string;
  }[];
}

/** CR-034 §7 (PO 2026-08-26) — WHAT A CUSTOMER MUST SATISFY TO AVAIL ONE.
 *
 *  Every field is a stored column of the discount version in force, forwarded.
 *  ⚠ **`eligibility_checked` IS THE ONE THAT KEEPS THIS HONEST.** The rule a
 *  builder authored is stored and NOTHING EVALUATES IT, so the panel says the
 *  conditions are recorded and checked by a person — never that the product
 *  enforces them. Rendering an advisory sentence as an enforced gate would tell
 *  a clerk this product refuses customers it does not refuse. */
export interface UnitPricingDiscountTerms {
  version_no: number | null;
  version_status: string | null;
  effective_from: string | null;
  effective_to: string | null;
  resolved_on: string;
  eligibility_summary: string | null;
  eligibility_rule_recorded: boolean;
  eligibility_checked: StatedAbsence;
  enrolment_mode: string | null;
  verification_method: string | null;
  proof_required: boolean;
  accepted_proof_kinds: string[];
  proof_before_first_reduction: boolean;
  recertification_months: number | null;
  recertification_notice_days: number | null;
  recertification_grace_days: number | null;
  lapse_behaviour: string | null;
  applies_to: string | null;
  applies_to_service: string | null;
  applies_to_service_name: string | null;
  applies_to_charge_codes: string[];
  currency: string | null;
  /** ⚠ DISPLAY STRINGS, and the server serves no other form of them (hard rule
   *  2: money stored 4 dp, DISPLAY 2). `null` is UNCAPPED — a decision an
   *  operator made — and is never rendered as `0.00`, which would say the
   *  discount reduces nothing. */
  cap_per_bill_display: string | null;
  cap_per_year_display: string | null;
  cap_lifetime_display: string | null;
  bill_floor_amount_display: string | null;
  stacks_with_others: boolean;
  exclusivity_group: string | null;
  stacking_precedence: number | null;
}

export interface UnitPricingOfferedDiscount {
  discount_id: string;
  code: string | null;
  name: string | null;
  status: string | null;
  type: string | null;
  /** Rating's OWN string, never `value` — which stores percentage POINTS and
   *  renders `15` as `1500.00%` through a fraction formatter (DEF-291). */
  value_display: string | null;
  eligibility: string | null;
  available_from: string | null;
  available_to: string | null;
  /** `null` when the discount has no version at all — *states no conditions*,
   *  which is a different fact from *has none*. */
  terms: UnitPricingDiscountTerms | null;
}

export interface UnitPricingDiscounts {
  /** What the PLAN OFFERS (BR-RAT-110). */
  offered: UnitPricingOfferedDiscount[];
  /** ⛔ NEVER SERVED FROM A UNIT. BR-RAT-069: binding a discount to a plan
   *  grants it to nobody — a bill run reads `discount_enrolments`, and an
   *  enrolment belongs to an ACCOUNT. `{served:false, reason:"unit_has_no_
   *  account"}`, never `[]`, which a reader would take for *none apply*. */
  granted: StatedAbsence;
}

export interface UnitPricingJurisdictionRule {
  jurisdiction_id: string;
  jurisdiction: string | null;
  rate_override: string | null;
}

export interface UnitPricingTaxAttachment {
  tax_id: string;
  name: string | null;
  kind: string | null;
  /** BR-RAT-087 / DEF-291 — the DISPLAY string rating computed, never `rate`.
   *  Percentages are stored to 6 places and displayed at 2. */
  rate_display: string | null;
  flat_amount_display: string | null;
  jurisdiction: { id?: string; name?: string } | null;
}

export interface UnitPricingPenaltyRule {
  late_fee_min: string | null;
  late_fee_pct: string | null;
  grace_days: number | null;
  grace_mode: string | null;
}

export interface UnitPricing {
  unit: {
    id: string;
    unit_no: string | null;
    label: string | null;
    premise_no: string | null;
    premise_address: string | null;
    rate_plan_id: string | null;
    plan_effective_from: string | null;
    plan_locked: boolean;
  };
  plan: {
    id: string;
    code: string | null;
    name: string | null;
    description: string | null;
    status: string | null;
    version: number | null;
    effective_from: string | null;
    effective_to: string | null;
    /** BR-RAT-027 — rating's DERIVED Σ. Forwarded, never recomputed. */
    base_charges: string | null;
    minimum_bill_amount: string | null;
    budget_billing: boolean | null;
    /** WHICH DATE resolved this plan. Carried beside it so a reader never has
     *  to assume the answer is about today (DEF-276: a figure has to be able to
     *  name its own inputs). */
    resolved_on: string;
  } | null;
  plan_absent: { reason: string; tracks: string | null } | null;
  period: UnitPricingPeriod;
  plan_history: UnitPricingPlanHistory;
  services: UnitPricingService[];
  rate_schedules: UnitPricingSchedule[];
  minimum_charges: UnitPricingMinimumCharges;
  charge_codes: UnitPricingChargeCode[];
  discounts: UnitPricingDiscounts;
  taxes: {
    jurisdiction_rules: UnitPricingJurisdictionRule[];
    attachments: UnitPricingTaxAttachment[];
    /** ⚠ DEF-273 — these are the PLAN's bindings, NOT R7's final answer: three
     *  of r10's five Texas rates scope by CUSTOMER CLASS, which is an account
     *  fact a unit cannot supply. `final:false` says so on every response. */
    narrowing: { final: boolean; reason: string; tracks: string | null } | null;
  };
  penalty_rule: UnitPricingPenaltyRule | null;
  /** ⛔ NOT BUILT — no contract object exists in this product.
   *
   *  `tracks` is null because that field is typed for an EXPIRY row (a DEF or
   *  an OQ) and this is neither: it is `CR-020`, the PO's own contracts-on-plans
   *  request, captured 2026-08-20 and HELD by them 2026-08-21. The change
   *  request travels in its own field rather than being smuggled into `tracks`. */
  contract: StatedAbsence & { change_request?: string | null };
  /** ⛔ NEVER SERVED. `{served:false, reason:…, tracks:"OQ-363"}`. */
  worked_month: StatedAbsence;
}

/** The ONE place this route is spelled. */
/** A period the caller states, or nothing at all — BOTH ends or NEITHER.
 *  Half a window is refused by the server rather than half-defaulted, because
 *  `as_of` IS the end and a start with no end names no service date. */
export interface PricingPeriodInput {
  start: string;
  end: string;
}

/** The ONE place this route is spelled. */
export function unitPricingPath(unitId: string, period?: PricingPeriodInput | null): string {
  const base = `/units/${encodeURIComponent(unitId)}/pricing`;
  if (!period) {
    return base; // ⚠ NO PERIOD IS INVENTED — see `UnitPricingPanel`'s note.
  }
  const query = new URLSearchParams({
    period_start: period.start,
    period_end: period.end,
  });
  return `${base}?${query.toString()}`;
}

/** The CALENDAR MONTH `day` falls in, as the two dates the endpoint takes.
 *
 * ⚠ **PO RULING 2026-08-26, VERBATIM: *"B Default to this month"***, over a
 * recommendation of *"as of today"* that this lane and its coordinator both
 * argued for. It is implemented HERE, in the panel, and NOT in the endpoint —
 * and that scope is the whole of why the objection does not survive:
 *
 *   * `UnitDetailPage`'s staff Plan tab passes `showPeriod` and gets the month.
 *   * `MoveInWizard`'s step 4 passes nothing and is UNCHANGED — no period on
 *     the wire, `as_of` = the tenant's today.
 *
 * The objection was that on the 25th a month-END `as_of` resolves a rate
 * version effective the 28th that is not in force today. That is a hazard for a
 * CUSTOMER signing up, and the customer-facing mount is the one that does not
 * take this default. **Do not "complete" this by moving it into
 * `getUnitPricing` or the server** — that reinstates exactly the hazard, on the
 * screen it was identified on. The endpoint's no-period answer stays
 * byte-identical (`test_cr034b_tc1`, backend).
 *
 * Local calendar arithmetic only: `new Date(y, m + 1, 0)` is the last day of
 * month `m`, which is the JS idiom for it and handles February without a table.
 * No money, no rates, nothing rounded — a window, which the user can change. */
export function currentMonthPeriod(day: Date = new Date()): PricingPeriodInput {
  const year = day.getFullYear();
  const month = day.getMonth();
  const iso = (value: Date): string =>
    `${String(value.getFullYear()).padStart(4, "0")}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  return { start: iso(new Date(year, month, 1)), end: iso(new Date(year, month + 1, 0)) };
}

export const unitPricingQueryKey = (unitId: string, period?: PricingPeriodInput | null) =>
  ["metering", "unit", unitId, "pricing", period?.start ?? null, period?.end ?? null] as const;

export async function getUnitPricing(
  unitId: string,
  client: ApiClient = api,
  period?: PricingPeriodInput | null,
): Promise<UnitPricing> {
  const response = await client.get<UnitPricing>(unitPricingPath(unitId, period));
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * The currency a row's money is in, taken from the row itself and never
 * defaulted.
 *
 * ⚠ `MoneyCell` REFUSES an absent amount by design (DEF-151/DEF-176), so every
 * call site here is guarded and an unpriced row renders a sentence instead of a
 * `$0.00`. A missing CURRENCY is the same defect one column over: `CHAR(3)` is
 * served with the amount (hard rule 2), and inventing `USD` for a row that did
 * not state one would put a currency on a screen the tenant never chose.
 */
export function money(
  amount: string | null | undefined,
  currency: string | null | undefined,
): { amount: string; currency: string } | null {
  if (amount === null || amount === undefined || amount === "") {
    return null;
  }
  if (currency === null || currency === undefined || currency === "") {
    return null;
  }
  return { amount, currency };
}

// ── The panel ──────────────────────────────────────────────────────────────

const SECTION_HEADING = "mt-4 font-heading text-xs font-semibold uppercase tracking-wide text-text";
// B14 rule 18 (CR-041 task 5) — `max-w-measure` is the `--desc-measure`
// token's utility; `max-w-prose` is a real Tailwind utility and the WRONG
// cap (`65ch` against a rule written as 80% — DEF-900).
const ABSENT = "max-w-measure text-sm text-neutral-700";
const ROW = "flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-divider py-2 last:border-b-0";
const ROW_LABEL = "text-xs uppercase tracking-wide text-neutral-700";
// ⛔ **`ROW_VALUE` KEEPS `max-w-prose`, DELIBERATELY.** Rule 18 caps a
// DESCRIPTION; this is the VALUE half of a label/value row, and the cap on
// it is a wrap guard so a long plan name does not run into its label. A
// percentage measure on a value in a two-column baseline row reads worse,
// which is the same reasoning rule 18's own amendment uses to exempt centred
// empty-state cards and KPI absent-values. Stated so the next sweep does not
// read it as one that was missed.
const ROW_VALUE = "min-w-0 max-w-prose text-sm text-text";

function Row(props: { label: string; children: ReactNode; ruleRef?: string }) {
  return (
    <div
      className={ROW}
      {...(props.ruleRef === undefined ? {} : { "data-br-ref": props.ruleRef })}
    >
      <span className={ROW_LABEL}>{props.label}</span>
      <span className={ROW_VALUE}>{props.children}</span>
    </div>
  );
}

function Absent(props: { children: ReactNode; tracks?: string }) {
  return (
    <span
      role="note"
      className={ABSENT}
      {...(props.tracks === undefined ? {} : { "data-tracks": props.tracks })}
    >
      {props.children}
    </span>
  );
}

function Money(props: {
  amount: string | null | undefined;
  currency: string | null | undefined;
  absent: string;
}) {
  const pair = money(props.amount, props.currency);
  if (pair === null) {
    return <Absent>{props.absent}</Absent>;
  }
  return <MoneyCell amount={pair.amount} currency={pair.currency} />;
}

function BlocksTable(props: {
  tiers: RateTierRow[];
  // DEF-1121 — a RATE cannot render without its currency, and the version is
  // the only row that carries one. Passed rather than defaulted: assuming USD
  // is exactly the kind of guess CLAUDE.md rule 2 forbids for money.
  currency: string | null;
  t: Translator;
}) {
  const { t } = props;
  return (
    <PlainTable>
      <thead>
        <tr>
          <th scope="col">{t("rating.rateDetail.matrix.col.tier", { seq: "#", defaultValue: "Tier" })}</th>
          <th scope="col">{t("rating.rateDetail.field.uom", { defaultValue: "Unit of measure" })}</th>
          <th scope="col">{t("rating.planDetail.charges.col.amount", { defaultValue: "Amount" })}</th>
        </tr>
      </thead>
      <tbody>
        {props.tiers.map((tier) => (
          <tr key={`${tier.seq}-${tier.season ?? ""}-${tier.size_class ?? ""}`}>
            <td>{tier.seq}</td>
            {/* ⚠ **DEF-1121 — THE COMMENT BELOW WAS TRUE AND THE CELLS WERE
                STILL WRONG.** It said a quantity is never a bare number
                "because the row above shows the unit", and meanwhile these
                cells printed `0.000000 – 5.000000` at `8.290000`: the unit was
                stated and the PRECISION was the storage column's. The bounds
                now carry their own unit and BR-MET-144's two trimmed decimals,
                composed server-side; the price is a RATE at four decimals with
                zeros past the 2nd dropped (PO 2026-10-02, narrowing OQ-620(a)). `0 – 5 kgal` at
                `$8.29`. Hard-won law 1: a comment claiming a guarantee is
                not the guarantee. */}
            <td>
              {tier.from_qty_display ?? "—"}
              {" – "}
              {tier.to_qty_display ?? t("customers.moveIn.pricing.blockOpenEnded", {
                defaultValue: "and above",
              })}
            </td>
            <td>
              {tier.unit_price === null || !props.currency
                ? "—"
                : formatRate(tier.unit_price, props.currency)}
            </td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

function ScheduleCard(props: { row: UnitPricingSchedule; t: Translator }) {
  const { row, t } = props;
  const card = row.schedule;
  if (card === null) {
    return (
      <div data-rate-schedule={row.service ?? ""}>
        <h5 className={SECTION_HEADING}>{row.tariff_name ?? row.service ?? ""}</h5>
        <Absent>
          {t(`metering.unit.pricing.schedule_absent.${row.absent?.reason ?? "schedule_not_readable"}`, {
            defaultValue:
              "This service's rate schedule could not be read, so its blocks are not shown.",
          })}
        </Absent>
      </div>
    );
  }
  const tiers = card.current_version?.structure?.tiers ?? [];
  const gate = card.uom_gate;
  return (
    <div data-rate-schedule={row.service ?? ""}>
      <h5 className={SECTION_HEADING}>{card.name ?? row.tariff_name ?? ""}</h5>
      <Row label={t("rating.planDetail.schedules.col.service", { defaultValue: "Service" })}>
        {card.service_name ?? card.service ?? row.service ?? "—"}
      </Row>
      <Row label={t("rating.planDetail.schedules.col.structure", { defaultValue: "Structure" })}>
        {card.structure ?? "—"}
      </Row>
      <Row label={t("rating.planDetail.schedules.col.status", { defaultValue: "Status" })}>
        {card.status ?? "—"}
      </Row>
      <Row label={t("rating.rateDetail.field.uom", { defaultValue: "Unit of measure" })}>
        {card.current_version?.uom ?? (
          <Absent>
            {t("rating.rateDetail.field.uomAbsent", {
              defaultValue: "No unit is recorded on the version in force.",
            })}
          </Absent>
        )}
      </Row>
      {/* BR-RAT-038 — a schedule priced in a unit the service does not bill in
          is a bill that cannot be produced. Said here, before the move-in. */}
      {gate === null || gate.satisfied ? null : (
        <p role="alert" className="mt-2 max-w-measure text-sm text-danger-700">
          {t("customers.moveIn.pricing.uomGate", {
            // DEF-3201 — `priced_against`, NEVER `billed_uom`. The declared
            // column is NULL on every tenant ever provisioned, so this line
            // read "the service is billed in , with no conversion recorded"
            // on the PO's own screen. `priced_against` is the effective unit.
            scheduleUom: gate.schedule_uom ?? "",
            billedUom: gate.priced_against ?? gate.billed_uom ?? "",
            defaultValue:
              "This schedule prices in {{scheduleUom}} and the service is billed in {{billedUom}}, with no conversion recorded. A bill cannot be produced from it until that is settled.",
          })}
        </p>
      )}
      {tiers.length === 0 ? (
        <Absent>
          {t("customers.moveIn.pricing.noBlocks", {
            defaultValue: "This schedule prices at one rate — it has no blocks.",
          })}
        </Absent>
      ) : (
        <BlocksTable tiers={tiers} currency={card.current_version?.currency ?? null} t={t} />
      )}
    </div>
  );
}

// ── CR-034 §7 (PO 2026-08-26) · THE CONDITIONS TO AVAIL A DISCOUNT ─────────
//
// The PO, verbatim: *"We should show all discount plan offer and what condition
// are required to avail that discount ; when account is attached it will avail
// those discounts"*.
//
// ⚠ **EVERY LINE BELOW IS A STORED COLUMN, AND NOT ONE OF THEM IS A CHECK.**
// The discount's `eligibility_rule` — the DIS-02 rule builder's document — is
// stored as authored and **nothing in this product evaluates it**. So this
// block renders the conditions as what they are: what the programme requires
// and a person confirms at enrolment. It never renders them as a gate the
// product enforces, because a clerk who believes the software is refusing
// unqualified customers stops checking, and the software is refusing nobody.
//
// ⚠ **AND NO PROGRAMME-WIDE FIGURE IS DRAWN.** The budget and the enrolled
// count are tenant-wide; the caps here are limits on THIS customer's own
// reduction, which is the difference that lets one appear on a unit screen and
// not the other.
const SUB_HEADING = "mt-3 text-sm font-semibold text-text";

/** An enum value rendered through its own label, or printed as it is stored.
 *  An UNKNOWN value prints itself rather than an empty cell — a value the
 *  catalogue has not met is a fact, and blanking it hides it. */
function label(t: Translator, group: string, value: string | null, labels: Record<string, string>): string | null {
  if (value === null || value === "") {
    return null;
  }
  const fallback = labels[value];
  if (fallback === undefined) {
    return value;
  }
  return t(`rating.discount.${group}.${value}`, { defaultValue: fallback });
}

const SCOPE_LABELS: Record<string, string> = {
  whole_bill: "The whole bill, before taxes",
  one_service: "One service",
  usage_only: "Usage charges only",
  base_only: "Base charges only",
  named_codes: "Named charge codes only",
};

const ENROLMENT_LABELS: Record<string, string> = {
  automatic: "Automatic — the customer does not apply",
  apply_and_approve: "The customer applies and staff approve it",
};

const VERIFICATION_LABELS: Record<string, string> = {
  one_time_proof: "Proof once, at enrolment",
  annual_recertification: "Proof at enrolment and again every year",
  agency_file_monthly: "A monthly file from the agency",
  automatic: "Automatic — no document is collected",
};

const LAPSE_LABELS: Record<string, string> = {
  notify_then_drop: "The customer is notified, then the discount is dropped",
  drop_silently: "The discount is dropped without notice",
  never_expires: "It never expires",
};

const PROOF_KIND_LABELS: Record<string, string> = {
  government_id: "Government ID",
  birth_certificate: "Birth certificate",
  veteran_id: "Veteran ID",
  disability_award: "Disability award letter",
  income_statement: "Income statement",
  tax_return: "Tax return",
  programme_award_letter: "Programme award letter",
  medical_certification: "Medical certification",
  agency_file: "Agency file",
  utility_record: "Utility record",
};

function proofKinds(t: Translator, kinds: string[]): string {
  return kinds
    .map((kind) => label(t, "proofKind", kind, PROOF_KIND_LABELS) ?? kind)
    .join(" · ");
}

function DiscountTerms(props: { row: UnitPricingOfferedDiscount; t: Translator }) {
  const { row, t } = props;
  const terms = row.terms;
  const heading = row.name ?? row.code ?? "";
  if (terms === null) {
    return (
      <div data-discount-terms={row.code ?? ""}>
        <h6 className={SUB_HEADING}>{heading}</h6>
        {/* A discount with no version has not been filled in — which is not the
            same statement as "it asks for nothing". */}
        <Absent>
          {t("metering.unit.pricing.discountTermsUnfiled", {
            defaultValue:
              "No filed version of this discount could be read, so its conditions are not shown. That is not the same as it having none.",
          })}
        </Absent>
      </div>
    );
  }
  const cap = [
    terms.cap_per_bill_display === null
      ? null
      : t("metering.unit.pricing.discountCapPerBill", {
          amount: terms.cap_per_bill_display,
          currency: terms.currency ?? "",
          defaultValue: "At most {{amount}} {{currency}} off one bill",
        }),
    terms.cap_per_year_display === null
      ? null
      : t("metering.unit.pricing.discountCapPerYear", {
          amount: terms.cap_per_year_display,
          currency: terms.currency ?? "",
          defaultValue: "At most {{amount}} {{currency}} in a year",
        }),
    terms.cap_lifetime_display === null
      ? null
      : t("metering.unit.pricing.discountCapLifetime", {
          amount: terms.cap_lifetime_display,
          currency: terms.currency ?? "",
          defaultValue: "At most {{amount}} {{currency}} in total, ever",
        }),
  ].filter((line): line is string => line !== null);
  return (
    <div data-discount-terms={row.code ?? ""}>
      <h6 className={SUB_HEADING}>{heading}</h6>

      {/* ── WHO QUALIFIES ────────────────────────────────────────────────
          The sentence a human wrote on the programme (r10's `Age 65+`), and
          immediately beneath it the fact that nothing checks it. */}
      <Row label={t("metering.unit.pricing.discountWhoQualifies", { defaultValue: "Who qualifies" })}>
        {terms.eligibility_summary ?? (
          <Absent>
            {t("metering.unit.pricing.discountNoEligibilityStated", {
              defaultValue:
                "This programme records no eligibility condition, so nothing here states who qualifies.",
            })}
          </Absent>
        )}
      </Row>
      {terms.eligibility_checked.served ? null : (
        <p
          role="note"
          className={`mt-1 ${ABSENT}`}
          data-discount-eligibility-unchecked={terms.eligibility_checked.reason}
        >
          {terms.eligibility_rule_recorded
            ? t("metering.unit.pricing.discountEligibilityRecordedNotChecked", {
                defaultValue:
                  "A rule for this condition is recorded on the programme, and nothing in this product evaluates it. Staff confirm it when the account is enrolled.",
              })
            : t("metering.unit.pricing.discountEligibilityNotChecked", {
                defaultValue:
                  "Nothing in this product checks this condition. Staff confirm it when the account is enrolled.",
              })}
        </p>
      )}

      {/* ── HOW IT IS OBTAINED, AND WHAT PROOF IT TAKES ──────────────────── */}
      <Row label={t("metering.unit.pricing.discountHowToGetIt", { defaultValue: "How it is granted" })}>
        {label(t, "enrolmentMode", terms.enrolment_mode, ENROLMENT_LABELS) ?? "—"}
      </Row>
      <Row label={t("metering.unit.pricing.discountProof", { defaultValue: "Proof required" })}>
        {terms.proof_required
          ? terms.accepted_proof_kinds.length === 0
            ? t("metering.unit.pricing.discountProofKindsUnstated", {
                defaultValue: "Yes — the accepted documents are not stated on this programme.",
              })
            : proofKinds(t, terms.accepted_proof_kinds)
          : t("customers.account.no", { defaultValue: "No" })}
      </Row>
      {terms.proof_required ? (
        <Row
          label={t("metering.unit.pricing.discountProofTiming", {
            defaultValue: "Before the first reduction",
          })}
        >
          {terms.proof_before_first_reduction
            ? t("metering.unit.pricing.discountProofFirst", {
                defaultValue: "Yes — nothing comes off a bill until the proof is on file.",
              })
            : t("metering.unit.pricing.discountProofLater", {
                defaultValue: "No — the reduction starts and the proof is chased afterwards.",
              })}
        </Row>
      ) : null}
      <Row label={t("metering.unit.pricing.discountVerification", { defaultValue: "Verification" })}>
        {label(t, "verification", terms.verification_method, VERIFICATION_LABELS) ?? "—"}
      </Row>

      {/* ── HOW IT IS KEPT ───────────────────────────────────────────────── */}
      <Row label={t("metering.unit.pricing.discountKeeping", { defaultValue: "Keeping it" })}>
        {terms.recertification_months === null
          ? t("metering.unit.pricing.discountNoRecert", {
              defaultValue: "Nothing to recertify.",
            })
          : t("metering.unit.pricing.discountRecert", {
              months: terms.recertification_months,
              defaultValue: "Recertified every {{months}} month(s).",
            })}{" "}
        {label(t, "lapse", terms.lapse_behaviour, LAPSE_LABELS) ?? ""}
        {terms.lapse_behaviour === "notify_then_drop" && terms.recertification_notice_days !== null
          ? ` (${t("metering.unit.pricing.discountNoticeDays", {
              days: terms.recertification_notice_days,
              defaultValue: "{{days}} days' notice",
            })})`
          : ""}
      </Row>

      {/* ── WHAT IT REDUCES, AND BY HOW MUCH AT MOST ─────────────────────── */}
      <Row label={t("metering.unit.pricing.discountAppliesTo", { defaultValue: "What it reduces" })}>
        {label(t, "scope", terms.applies_to, SCOPE_LABELS) ?? "—"}
        {terms.applies_to === "one_service" && (terms.applies_to_service_name ?? terms.applies_to_service) !== null
          ? ` · ${terms.applies_to_service_name ?? terms.applies_to_service}`
          : ""}
        {terms.applies_to === "named_codes" && terms.applies_to_charge_codes.length > 0
          ? ` · ${terms.applies_to_charge_codes.join(" · ")}`
          : ""}
      </Row>
      <Row label={t("metering.unit.pricing.discountCaps", { defaultValue: "Most it can take off" })}>
        {cap.length === 0
          ? t("metering.unit.pricing.discountNoCap", {
              defaultValue: "No cap is set on this programme.",
            })
          : cap.join(" · ")}
      </Row>
      {/* BR-RAT-074 — the floor. `0.00` is the DEFAULT and it is a real
          statement: a discount may take a bill to zero and never below,
          because a negative bill is a CREDIT, a different object with a
          different ledger posting that no discount may mint. */}
      <Row
        label={t("metering.unit.pricing.discountFloor", { defaultValue: "The bill cannot go below" })}
        ruleRef="BR-RAT-074"
      >
        {terms.bill_floor_amount_display === null
          ? "—"
          : `${terms.bill_floor_amount_display}${terms.currency === null ? "" : ` ${terms.currency}`}`}
      </Row>

      {/* ── WITH OTHER DISCOUNTS ─────────────────────────────────────────── */}
      <Row
        label={t("metering.unit.pricing.discountStacking", { defaultValue: "With other discounts" })}
        ruleRef="BR-RAT-073"
      >
        {terms.stacks_with_others
          ? t("metering.unit.pricing.discountStacks", {
              defaultValue: "Can be held alongside others.",
            })
          : t("metering.unit.pricing.discountNoStack", {
              defaultValue: "Cannot be held alongside another discount.",
            })}
        {terms.exclusivity_group === null
          ? ""
          : ` ${t("metering.unit.pricing.discountExclusive", {
              group: terms.exclusivity_group,
              defaultValue:
                "Only one “{{group}}” discount applies to an account — the larger one.",
            })}`}
      </Row>
    </div>
  );
}

/**
 * **WHAT THE SERVICE ON THIS ROW IS PRICED ON** — `CR-089` wave H `H3`
 * (`PUJ-35`, `BR-MET-1166`).
 *
 * **THE RULE, VERBATIM FROM THE DECISION LOG OF 2026-09-08:** *"a screen
 * showing a base charge of zero must say what the service is priced on
 * instead, on the same row. Not in a footnote, not in a tooltip. The figure and
 * its explanation are one fact."*
 *
 * ⛔ **NOT A LOOKUP TABLE KEYED ON THE SERVICE CODE, AND THAT IS THE WHOLE
 * DESIGN.** Writing *"Fire → by the size of the line"* here would put product
 * knowledge in TypeScript where a tenant who prices trash by weight makes it
 * wrong, and where a twelfth service silently gets nothing. The SHAPE is
 * `apps/tenancy`'s ratified law, resolved on the server
 * (`_service_priced_on`), and this turns it into one sentence per shape. Four
 * sentences, eleven services, and the twelfth needs no edit here.
 *
 * ⚠ **IT IS DRAWN ON EVERY ROW, NOT ONLY THE ZEROS.** The axis is true of a
 * `$8.00` water base as much as a `$0.00` fire one — water's own base is picked
 * by the meter's size band — and a column filled on three rows of six reads as
 * a warning about those three rather than as a fact about all six. Where the
 * server said nothing (an older cached payload) the cell is EMPTY rather than
 * guessing: an absence is not a shape.
 */
function PricedOnCell(props: { pricedOn: ServicePricedOn | null; t: Translator }) {
  const { pricedOn, t } = props;
  if (pricedOn === null) return null;
  if (pricedOn.shape === "capacity") {
    return (
      <span data-priced-on="capacity">
        {t("metering.unit.pricing.pricedOnCapacity", {
          uom: pricedOn.capacity_uom ?? "",
          defaultValue: "By capacity — the {{uom}} installed",
        })}
      </span>
    );
  }
  if (pricedOn.shape === "size_bands") {
    return (
      <span data-priced-on="size_bands">
        {t("metering.unit.pricing.pricedOnSizeBands", {
          defaultValue: "By the size of each one, times how many",
        })}
      </span>
    );
  }
  if (pricedOn.shape === "no_size_axis") {
    return (
      <span data-priced-on="no_size_axis">
        {t("metering.unit.pricing.pricedOnNoSizeAxis", {
          defaultValue: "Not by size or capacity",
        })}
      </span>
    );
  }
  // `not_ruled` — thermal steam's bands were never put to the Product Owner
  // (`OQ-560`). The prime directive forbids answering that by choosing one, so
  // the screen says it is open rather than inventing an axis.
  return (
    <span data-priced-on="not_ruled">
      {t("metering.unit.pricing.pricedOnNotRuled", {
        defaultValue: "Not decided yet for this service",
      })}
    </span>
  );
}

/**
 * **ONE DATE SHAPE FOR THIS WHOLE TAB — `1 Jun 2026`** (`DEF-MET-4689`,
 * `BR-MET-1167`, CR-089 wave H `H1`).
 *
 * `"UTC"` is not a guess and not a tenant fact: every date this panel prints is
 * a CALENDAR date, which `DateCell` formats from its own digits and never
 * routes through a zone. `regionalDateEcho` passes the same constant, for the
 * same reason, in the same file that owns the rule.
 */
function namedDate(iso: string | null | undefined): string | null {
  if (iso === null || iso === undefined || iso === "") return null;
  return formatNamedDate(iso, "UTC");
}

/**
 * The named-month line under a native `<input type="date">`.
 *
 * ⛔ **THE BOX ITSELF CANNOT BE MADE TO SAY THIS AND NO API EXISTS TO ASK IT
 * TO.** A native date input renders in the BROWSER's locale — Chrome follows
 * the browser UI language, Firefox the OS regional setting — so on the Product
 * Owner's own machine these two boxes printed `01/09/2026` and `30/09/2026`,
 * day first, forty pixels under a plan date printed `06/01/2026`, month first.
 * Two opposite conventions on one screen, each correct in isolation.
 *
 * ⚠ **THIS IS NOT `regionalDateEcho` AND MUST NOT BE REPLACED BY IT.** That
 * helper prints the TENANT's format and returns `null` when the control is
 * already showing those characters (CR-043 finding 15 — a date field printing
 * its own value twice). Here the tenant format is one of the four shapes being
 * removed, so echoing it would keep the defect; and a named month can never be
 * the characters a numeric control is showing, so there is no redundant case to
 * suppress. `aria-hidden` because the input already exposes its own value to a
 * screen reader — this line is for the eye that has to compare two boxes.
 */
function NamedDateEcho(props: { value: string }) {
  const shown = namedDate(props.value);
  if (shown === null) return null;
  return (
    <span className="text-xs normal-case tracking-normal text-neutral-700" aria-hidden="true">
      {shown}
    </span>
  );
}

export interface UnitPricingPanelProps {
  unitId: string;
  t: Translator;
  client?: ApiClient; // test seam — screens never build their own transport
  /** CR-034 (b) — show the period control and the plan-change report.
   *
   *  ⚠ **DEFAULT `false`, AND THAT IS NOT TIMIDITY.** The move-in wizard mounts
   *  this same panel at step 4, where a period picker is noise: a customer
   *  signing up is asking *"what will I pay"*, not *"what applied last July"*.
   *  Off means the panel behaves exactly as it did before CR-034 (b) — no
   *  period on the wire, `as_of` = today, and the same rates it always drew.
   *  `UnitDetailPage`'s Plan tab passes `true`; nothing else does. */
  showPeriod?: boolean;
  /** ⚠ **THE HOST SCREEN ALREADY STATES THE PLAN'S IDENTITY, SO THIS PANEL MUST
   *  NOT STATE IT AGAIN** (`U6` §15: *"No second plan block. `Plan`, `Code`,
   *  `Status`, `Effective from`, `Base charges` and `Minimum bill` appear
   *  ONCE"*).
   *
   *  The named defect is `Effective from`, drawn page 74: *"`Effective from`
   *  appears once. It was on the plan panel **and again in the pricing panel
   *  below**, in two different formats — which is how a clerk concludes there
   *  are two dates."* Both are now the same named-month shape, so the second
   *  copy is no longer WRONG — it is still a second copy of one fact, and the
   *  frame draws one.
   *
   *  ⚠ **DEFAULT `false`, FOR THE SAME REASON `showPeriod` IS.** The move-in
   *  wizard mounts this panel with no plan facts above it, so there the block
   *  is the only place a customer sees which plan they are being put on.
   *  Suppressing it unconditionally would delete a fact from a screen that has
   *  nowhere else to say it. */
  planFactsAbove?: boolean;
  /** Whether the *An example month* stated absence is drawn. **Absent means
   *  drawn**, so the unit's Plan tab is unchanged. The move-in's step 4 passes
   *  `false` (`DEF-CUS-6364`, PO 2026-09-23: the paragraph is cut there). */
  workedMonthAbsence?: boolean;
}

/**
 * Move-in step 4's *"what this unit is priced on"* panel.
 *
 * ⚠ **IT SHOWS; IT DOES NOT CHOOSE.** There is no plan picker here, and that is
 * BR-CUS-029 plus the PO's 2026-08-11 ruling rather than an omission: the plan
 * lives ONCE on the unit and the account derives it, so a plan control on this
 * step would write nothing. `MoveInWizard`'s step 4 says so beside this panel.
 */
export function UnitPricingPanel(props: UnitPricingPanelProps) {
  const { t, unitId } = props;
  const client = props.client ?? api;
  const showPeriod = props.showPeriod ?? false;
  const planFactsAbove = props.planFactsAbove ?? false;
  // ⚠ **THE PERIOD PICKER FOLDS AWAY (U6 §8).** Drawn page 74: *"The period
  // picker folds away. `Showing what applies today` with one link to look at
  // another period. **Four controls and a sentence were open permanently** for
  // a question almost nobody asks, above the answer everybody came for."*
  // The controls are unchanged; what changed is that they are CLOSED until the
  // link is pressed. `<details>` and not a `useState` toggle: B14 rule 32 makes
  // a stated absence a `<details>` closed by default, a native disclosure is
  // keyboard-operable with no code, and the summary IS the link the frame draws.
  const [periodOpen, setPeriodOpen] = useState(false);
  // ⚠ THE DRAFT AND THE APPLIED PERIOD ARE TWO PIECES OF STATE ON PURPOSE.
  // Refetching on every keystroke of a date input asks the server about
  // `2026-0`, `2026-07`, `2026-07-0`… — three refusals a person never asked
  // for. The window is applied when BOTH ends are filled and the button is
  // pressed, which is also the shape the server's both-or-neither rule wants.
  //
  // ⚠ **AND THE PLAN TAB OPENS ON THIS MONTH (PO 2026-08-26: *"B Default to
  // this month"*), WHILE THE MOVE-IN WIZARD STILL OPENS ON TODAY.** The two
  // mounts are two screens: staff asking *"what applies"* mean a month, and a
  // customer signing up must not be shown a rate version that takes effect on
  // the 28th under a heading about now. `showPeriod` is the switch, and it is
  // the same one that decides whether the period control is drawn at all — so a
  // mount can never receive the default without the means to change it.
  const [draft, setDraft] = useState<{ start: string; end: string }>(() =>
    showPeriod ? currentMonthPeriod() : { start: "", end: "" },
  );
  const [period, setPeriod] = useState<PricingPeriodInput | null>(() =>
    showPeriod ? currentMonthPeriod() : null,
  );
  const pricingQuery = useQuery({
    queryKey: unitPricingQueryKey(unitId, period),
    queryFn: () => getUnitPricing(unitId, client, period),
    enabled: unitId !== "",
  });

  if (pricingQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  const pricing = pricingQuery.data;
  if (pricing === undefined) {
    return (
      <Note role="note" data-unit-pricing="failed">
        {t("customers.moveIn.pricing.failed", {
          defaultValue:
            "The rates for this unit could not be read, so none are shown. Nothing is assumed in their place.",
        })}
      </Note>
    );
  }

  const plan = pricing.plan;
  const currency = pricing.services.find((row) => row.currency !== null)?.currency ?? null;

  return (
    <div data-unit-pricing={pricing.unit.id}>
      <Note>
        {t("customers.moveIn.pricing.hint", {
          defaultValue:
            "What this unit is priced on today. The new account takes the unit's plan, so these are the rates the first bill will use.",
        })}
      </Note>

      {/* ── CR-034 (b) · SECTION 1 · WHAT WINDOW THIS ANSWER IS ABOUT ───────
          The PO, verbatim: *"showing in - what period you are reporting data
          for"*. Every figure below was resolved on ONE date — `as_of`, the
          period's END (BR-RAT-007) — and this line is where that date is said
          out loud, so nothing on the screen is read as "now" by default.

          ⚠ **AMENDED 2026-08-26 — THE PO RULED THE DEFAULT, AGAINST THIS
          LANE'S RECOMMENDATION AND ITS COORDINATOR'S.** Verbatim: *"B Default
          to this month"*. This block used to read *"with no period, no period
          is invented"* and to record the month default as DECLINED; that is no
          longer the product and the sentence is superseded rather than left to
          be read as law by the next agent.

          **The argument against it was sound and its SCOPE is what answers it**
          — on the 25th a month-END `as_of` resolves a rate version effective
          the 28th that is not in force today. So the month is defaulted on the
          STAFF mount only (`showPeriod`), and the customer-facing move-in
          wizard still opens on today with no period on the wire. See
          `currentMonthPeriod`. The *server* still invents nothing: a request
          with no period is answered `period: null` / `as_of` = today, exactly
          as before. */}
      {/* ── CR-089 wave H · `H1` (`DEF-MET-4689`, `BR-MET-1167`) ──────────
          ⚠ **THE SENTENCE PRINTED THE STORED STRING** — *"Showing what applies
          for 2026-09-01 to 2026-09-30"* — while the two boxes underneath it
          printed the same two dates in the BROWSER's locale and the plan's
          `Effective from` printed a third shape. Four formatters, one screen,
          every one of them right on its own. The dates are now the tab's one
          named-month shape; **the KEYS and their sentences are untouched**,
          because only the substituted VALUE was ever wrong and rewording eleven
          catalogues to fix a date format would be a change with no reader.
          `"UTC"` is the zone `regionalDateEcho` passes for the same reason: a
          calendar date is formatted from its own digits and never routed
          through a timezone (`DateCell`'s own law). */}
      <p className="mt-2 text-sm text-neutral-700" data-pricing-as-of={pricing.period.as_of}>
        {pricing.period.supplied
          ? t("metering.unit.pricing.periodStated", {
              start: namedDate(pricing.period.start),
              end: namedDate(pricing.period.end),
              defaultValue: "Showing what applies for {{start}} to {{end}}",
            })
          : t("metering.unit.pricing.periodAsOf", {
              date: namedDate(pricing.period.as_of),
              // ⚠ **THE SECOND SENTENCE WENT WITH THE PICKER.** It read
              // *"Pick a period to see what applied then."* over four
              // permanently open controls; the instruction is now the link that
              // opens them, which is B14 rule 32's *"a row never repeats what
              // its own control offers"*.
              defaultValue: "Showing what applies today, {{date}}",
            })}
      </p>

      {showPeriod ? (
        <details
          className="mt-2"
          open={periodOpen}
          onToggle={(event) => setPeriodOpen((event.target as HTMLDetailsElement).open)}
        >
          {/* The ONE link the frame draws, in place of four permanently open
              controls. `list-none` and the marker rule strip the native
              triangle so it reads as the link it is drawn as. */}
          <summary
            className="inline-flex cursor-pointer list-none text-sm text-accent-700 underline [&::-webkit-details-marker]:hidden"
            data-pricing-period-toggle=""
          >
            {t("metering.unit.pricing.periodAnother")}
          </summary>
        <div className="mt-2 flex flex-wrap items-end gap-3" data-pricing-period-control="">
          <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-neutral-700">
            {t("metering.unit.pricing.periodStart", { defaultValue: "Period from" })}
            {/* B14 rule 7 — a DATE field uses the date input, never a text box. */}
            <input
              type="date"
              className="min-h-8 max-w-[180px] border border-field-border bg-bg px-2 py-1.5 text-text"
              value={draft.start}
              onChange={(event) => setDraft({ ...draft, start: event.target.value })}
            />
            <NamedDateEcho value={draft.start} />
          </label>
          <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-neutral-700">
            {t("metering.unit.pricing.periodEnd", { defaultValue: "Period to" })}
            <input
              type="date"
              className="min-h-8 max-w-[180px] border border-field-border bg-bg px-2 py-1.5 text-text"
              value={draft.end}
              onChange={(event) => setDraft({ ...draft, end: event.target.value })}
            />
            <NamedDateEcho value={draft.end} />
          </label>
          {/* Disabled until BOTH ends are filled — the server's both-or-neither
              rule, enforced here so a person never sees a refusal they could
              not have avoided. It is NOT the only enforcement: the server
              refuses half a window on its own, because a screen guard is not a
              control (DEF-435's lesson). */}
          <Button
            size="sm"
            variant="secondary"
            disabled={draft.start === "" || draft.end === ""}
            onClick={() => setPeriod({ start: draft.start, end: draft.end })}
          >
            {t("metering.unit.pricing.periodApply", { defaultValue: "Show this period" })}
          </Button>
          {period === null ? null : (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setPeriod(null);
                setDraft({ start: "", end: "" });
              }}
            >
              {t("metering.unit.pricing.periodClear", { defaultValue: "Back to today" })}
            </Button>
          )}
        </div>
        </details>
      ) : null}

      {/* ── BR-RAT-114 / DEF-504 · THE SPLIT IS SHOWN, NEVER COLLAPSED ──────
          A unit's plan can change inside the period, and a bill for that period
          would be produced once per stretch, each on ITS plan. So a screen that
          named one plan as *the* plan for the window would be stating something
          no bill will do. Every stretch is drawn, the split dates are named,
          and the sections below say which date resolved them. */}
      {pricing.plan_history.served && pricing.plan_history.stretches.length > 1 ? (
        <div className="mt-3" data-plan-history="">
          <Note role="note">
            {t("metering.unit.pricing.planChanged", {
              // `DEF-MET-4689` — these were stored strings in a sentence.
              dates: pricing.plan_history.splits_at
                .map((iso) => namedDate(iso) ?? iso)
                .join(", "),
              defaultValue:
                "This unit's plan changed during this period. A bill for it would be split on {{dates}}, with each part priced on its own plan. The details below are for the plan in force at the end of the period.",
            })}
          </Note>
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{t("rating.plans.col.plan", { defaultValue: "Plan" })}</th>
                <th scope="col">
                  {t("metering.unit.pricing.stretchFrom", { defaultValue: "From" })}
                </th>
                <th scope="col">
                  {t("metering.unit.pricing.stretchTo", { defaultValue: "To" })}
                </th>
              </tr>
            </thead>
            <tbody>
              {pricing.plan_history.stretches.map((row) => (
                <tr key={`${row.rate_plan_id}-${row.assigned_from ?? ""}`} data-plan-stretch={row.assigned_from ?? ""}>
                  {/* A plan no longer published resolves no name (BR-RAT-030).
                      The row is still drawn — dropping it would hide a stretch
                      a bill would price. */}
                  {/* `DEF-SHL-6348` — never the database id (B14 rule 31): a
                      stretch with no name and no code reads as a dash. */}
                  <td>{row.plan_name ?? row.plan_code ?? "—"}</td>
                  {/* `DEF-MET-4689` again, and this pair was FOUND BY A SUITE
                      RATHER THAN BY THE BROWSER: no seeded unit changes plan
                      mid-period, so the walkthrough never drew this table and
                      the two stored strings in it would have survived the whole
                      wave. They are dates on this tab like any other. */}
                  <td>{namedDate(row.assigned_from) ?? "—"}</td>
                  <td>
                    {namedDate(row.assigned_to) ??
                      t("metering.unit.pricing.stretchOpen", { defaultValue: "still current" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      ) : null}

      {/* BR-MET-100 / the two rating-side absences: a unit with no plan, a
          plan this tenant cannot open, and rating publishing nothing are three
          different sentences and each has its own. None of them is an error on
          the unit, so none of them replaces the step. */}
      {pricing.plan_absent === null ? null : (
        <p role="note" className="mt-2 max-w-measure text-sm text-neutral-700" data-plan-absent={pricing.plan_absent.reason}>
          {t(`metering.unit.pricing.plan_absent.${pricing.plan_absent.reason}`, {
            defaultValue: "No rate plan can be shown for this unit.",
          })}
        </p>
      )}

      {plan === null ? null : (
        <div data-rate-plan={plan.id}>
          <h5 className={SECTION_HEADING}>
            {t("rating.plans.col.plan", { defaultValue: "Plan" })}
          </h5>
          {/* ⚠ **FOUR ROWS THAT THE HOST SCREEN ALREADY STATES ARE NOT STATED
              TWICE.** `U6` §15 draws ONE plan block; on the unit's Plan tab the
              fact list above already carries the plan, its code, its status and
              its effective date, and this panel repeating them is what made a
              clerk read two dates where there is one. The move-in wizard has no
              such list, so there the block is drawn whole. */}
          {planFactsAbove ? null : (
            <>
              <Row label={t("rating.plans.col.plan", { defaultValue: "Plan" })}>
                {plan.name ?? plan.code ?? "—"}
              </Row>
              <Row label={t("rating.plans.col.code", { defaultValue: "Code" })}>
                {plan.code ?? "—"}
              </Row>
              <Row label={t("rating.plans.col.status", { defaultValue: "Status" })}>
                {plan.status ?? "—"}
              </Row>
              <Row label={t("rating.plans.col.effectiveFrom", { defaultValue: "Effective from" })}>
                {namedDate(plan.effective_from) ?? "—"}
              </Row>
            </>
          )}
          {/* BR-RAT-027 — rating's DERIVED Σ of the plan's base charges,
              printed as received. This file does not add the rows up. */}
          <Row
            label={t("rating.plans.col.base", { defaultValue: "Base charges" })}
            ruleRef="BR-RAT-027"
          >
            <Money
              amount={plan.base_charges}
              currency={currency}
              absent={t("customers.moveIn.pricing.baseAbsent", {
                defaultValue: "No base charge is recorded on this plan.",
              })}
            />
          </Row>
          {/* ── CR-089 wave H · `H2` (`DEF-MET-4693`) ─────────────────────
              **THE ONE PLACE ON THIS TAB THAT SPELLS THE ABSENCE OUT.** The
              same sentence — *"No floor is set on this plan."* — was printed
              SEVEN TIMES on the Product Owner's screen: once here and once for
              each of six services, identically. Seven copies took more of the
              screen than any figure on it, and each was rendered by its own
              component, so no test could ever see them together; only a person
              reading the whole page could. The plan's own row says it in full
              and every other floor cell below reads `none`.
              ⚠ **A NEW KEY RATHER THAN A REWORD.**
              `rating.planDetail.field.minimumBillAbsent` is `PlanDetail`'s too,
              and that screen prints it ONCE where it is exactly right. */}
          <Row label={t("rating.planDetail.field.minimumBill", { defaultValue: "Minimum bill" })}>
            <Money
              amount={plan.minimum_bill_amount}
              currency={currency}
              absent={t("metering.unit.pricing.floorAbsent", {
                defaultValue: "No floor is set — a bill can be any amount, including nothing",
              })}
            />
          </Row>
        </div>
      )}

      {pricing.services.length === 0 ? null : (
        <div data-plan-services="">
          <h5 className={SECTION_HEADING}>
            {t("rating.plans.col.services", { defaultValue: "Services included" })}
          </h5>
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">
                  {t("rating.planDetail.baseRates.col.service", { defaultValue: "Service" })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.baseRates.col.planBase", {
                    defaultValue: "Base kept on this plan",
                  })}
                </th>
                {/* ── CR-089 wave H · `H3` (`PUJ-35`, `BR-MET-1166`) ────
                    Three of the six services on the Product Owner's own plan
                    read `$0.00` — Trash, Solar and Fire — with nothing beside
                    them to say whether that meant FREE or PRICED SOME OTHER
                    WAY. All three are priced another way and correctly, so the
                    zero was right and read as broken. The rule that column
                    obeys: *a screen showing a base charge of zero must say what
                    the service is priced on instead, on the same row* — not in
                    a footnote, not in a tooltip. */}
                <th scope="col">
                  {t("metering.unit.pricing.pricedOn", { defaultValue: "Priced on" })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.baseRates.col.minimum", {
                    defaultValue: "Minimum for this service",
                  })}
                </th>
              </tr>
            </thead>
            <tbody>
              {pricing.services.map((row) => (
                <tr key={row.service} data-plan-service={row.service}>
                  <td>{row.name ?? row.service}</td>
                  <td>
                    <Money
                      amount={row.base_charge}
                      currency={row.currency}
                      absent={t("customers.moveIn.pricing.baseAbsent", {
                        defaultValue: "No base charge is recorded on this plan.",
                      })}
                    />
                  </td>
                  <td>
                    <PricedOnCell pricedOn={row.priced_on ?? null} t={t} />
                  </td>
                  <td>
                    <Money
                      amount={row.minimum_amount}
                      currency={row.currency}
                      absent={t("metering.unit.pricing.floorNone", { defaultValue: "none" })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}

      {pricing.rate_schedules.length === 0 ? null : (
        <div data-rate-schedules="">
          <h5 className={SECTION_HEADING}>
            {t("rating.plans.col.schedules", { defaultValue: "Rate schedules" })}
          </h5>
          {pricing.rate_schedules.map((row) => (
            <ScheduleCard key={row.tariff_id ?? row.service ?? ""} row={row} t={t} />
          ))}
        </div>
      )}

      {/* ── CR-034 (b) · SECTION 5 · THE FLOORS, GATHERED AND NOT RESOLVED ──
          🔒 Three places store a minimum — the plan, the plan's service line
          and the rate-schedule version — and they were scattered across three
          parts of this same screen. They are gathered under one heading here.

          ⚠ **WHICH FLOOR WINS IS NOT DECIDED HERE, ON PURPOSE.** That is
          BR-RAT-016/028, it is PROPOSED on GT-13 rather than ❄️ frozen, and
          deciding it on a screen would be billing math in a second place where
          no golden test can ever see it. Three labelled figures, and the
          sentence says they are three. A null stays null: r10's electric matrix
          draws an em-dash in this column for every size, and `0.00` is a
          different fact (DEF-277). */}
      {pricing.minimum_charges.plan?.amount === null &&
      pricing.minimum_charges.services.every((row) => row.minimum_amount === null) &&
      pricing.minimum_charges.schedules.every((row) => row.minimum_bill === null) ? null : (
        <div data-minimum-charges="">
          <h5 className={SECTION_HEADING}>
            {t("metering.unit.pricing.minimumsTitle", { defaultValue: "Minimum charges" })}
          </h5>
          <Note role="note">
            {t("metering.unit.pricing.minimumsHint", {
              defaultValue:
                "Three separate floors can be set. They are shown as configured; which one a bill applies is decided by the billing rules, not by this screen.",
            })}
          </Note>
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">
                  {t("metering.unit.pricing.minimumWhere", { defaultValue: "Set on" })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.baseRates.col.service", { defaultValue: "Service" })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.field.minimumBill", { defaultValue: "Minimum bill" })}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr data-minimum-source="plan">
                <td>{t("rating.plans.col.plan", { defaultValue: "Plan" })}</td>
                <td>{t("metering.unit.pricing.minimumAllServices", { defaultValue: "All" })}</td>
                <td>
                  <Money
                    amount={pricing.minimum_charges.plan?.amount ?? null}
                    currency={currency}
                    absent={t("metering.unit.pricing.floorNone", { defaultValue: "none" })}
                  />
                </td>
              </tr>
              {pricing.minimum_charges.services.map((row) => (
                <tr key={`svc-${row.service ?? ""}`} data-minimum-source={`plan_service:${row.service ?? ""}`}>
                  <td>
                    {t("metering.unit.pricing.minimumOnPlanService", {
                      defaultValue: "Plan · service line",
                    })}
                  </td>
                  <td>{row.name ?? row.service ?? "—"}</td>
                  <td>
                    <Money
                      amount={row.minimum_amount}
                      currency={row.currency ?? currency}
                      absent={t("metering.unit.pricing.floorNone", { defaultValue: "none" })}
                    />
                  </td>
                </tr>
              ))}
              {pricing.minimum_charges.schedules.map((row) => (
                <tr key={`sch-${row.tariff_id ?? row.service ?? ""}`} data-minimum-source={`rate_schedule:${row.service ?? ""}`}>
                  <td>
                    {t("rating.plans.col.schedules", { defaultValue: "Rate schedules" })}
                  </td>
                  <td>
                    {row.tariff_name ?? row.service ?? "—"}
                    {" · "}
                    <span data-minimum-size={row.minimum_state}>
                      {row.size_label ??
                        t("metering.unit.pricing.noSize", { defaultValue: "No size" })}
                    </span>
                  </td>
                  <td>
                    {/* DEF-MET-8823 — the minimum for THIS unit's connection
                        size (PO 2026-10-01, option A), the figure billing
                        charges. No size, or a size with none: "No minimum". */}
                    <Money
                      amount={row.minimum_bill}
                      currency={row.currency ?? currency}
                      absent={t("metering.unit.pricing.noMinimum", { defaultValue: "No minimum" })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}

      {pricing.charge_codes.length === 0 ? null : (
        <div data-charge-codes="">
          <h5 className={SECTION_HEADING}>
            {t("rating.definition.title.charge", { defaultValue: "Charge code" })}
          </h5>
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{t("rating.charges.col.code", { defaultValue: "Code" })}</th>
                <th scope="col">
                  {t("rating.planDetail.charges.col.charge", { defaultValue: "Charge" })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.charges.col.service", { defaultValue: "Service" })}
                </th>
                <th scope="col">
                  {t("metering.unit.pricing.chargeCodeAmount", {
                    defaultValue: "The code's own amount",
                  })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.charges.col.amount", {
                    defaultValue: "Amount",
                  })}
                </th>
                <th scope="col">
                  {t("rating.planDetail.charges.col.taxable", { defaultValue: "Taxed" })}
                </th>
              </tr>
            </thead>
            <tbody>
              {pricing.charge_codes.map((row) => (
                <tr key={row.id} data-charge-code={row.code}>
                  <td>
                    {row.code}
                    {/* BR-RAT-088 — an `is_base` code reaches a bill as its
                        service's BASE through R4, not as a fee line. Saying so
                        is not decoration: a reader who sees it listed among the
                        fees without this concludes the bill charges it twice,
                        which is exactly the $23,069.50-a-month error §A3
                        priced. */}
                    {row.is_base ? (
                      <span className="ml-1 text-xs uppercase tracking-wide text-neutral-700">
                        {t("metering.unit.pricing.chargeIsBase", {
                          defaultValue: "base charge",
                        })}
                      </span>
                    ) : null}
                  </td>
                  <td>{row.name ?? "—"}</td>
                  {/* CR-013 part 2 — `—` for an account-level code (late fee,
                      NSF): the server serves null and the em-dash is drawn
                      here, never a service literally named "any". */}
                  <td>{row.service ?? "—"}</td>
                  {/* ⚠ THE HOLE CR-034 (b) CLOSED. This column did not exist,
                      so a code with no plan override printed the sentence *"At
                      the charge code's own amount"* WITH NO AMOUNT — a promise
                      of a figure that withholds it, which reads as unknowable
                      rather than merely unfetched. `amount_display` is rating's
                      own two-place string (BR-RAT-087). */}
                  <td data-charge-code-own-amount={row.amount_display ?? ""}>
                    {row.amount_display ??
                      row.percent_display ??
                      t("metering.unit.pricing.chargeNoAmount", {
                        defaultValue: "No amount is set on this code.",
                      })}
                  </td>
                  <td>
                    <Money
                      amount={row.amount_override}
                      currency={currency}
                      absent={t("customers.moveIn.pricing.chargeAtCodeAmount", {
                        defaultValue: "At the charge code's own amount",
                      })}
                    />
                  </td>
                  <td>
                    {row.taxable
                      ? t("customers.account.yes", { defaultValue: "Yes" })
                      : t("customers.account.no", { defaultValue: "No" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}

      {/* ── CR-034 (b) · SECTION 7 · OFFERED IS NOT GRANTED ────────────────
          BR-RAT-069, and it is the whole of this section: binding a discount to
          a plan grants it to NOBODY. A bill run reads `discount_enrolments`,
          an enrolment belongs to an ACCOUNT, and a unit does not have one — so
          what can honestly be shown here is what the plan OFFERS, and the
          reduction a bill would actually take is a stated absence.

          ⚠ **THE `enrolled` COUNT IS NOT ON THIS SCREEN AND THAT IS DELIBERATE.**
          Rating serves it and it is TENANT-WIDE; a number rendered on a UNIT
          screen is read as this unit's however the caption is worded. An absent
          figure is safer than a correctly-labelled misleading one. */}
      {pricing.discounts.offered.length === 0 && pricing.discounts.granted.served ? null : (
        <div data-plan-discounts="">
          <h5 className={SECTION_HEADING}>
            {t("rating.definition.title.discount", { defaultValue: "Discounts" })}
          </h5>
          {pricing.discounts.offered.length === 0 ? (
            <p className={ABSENT}>
              {t("metering.unit.pricing.noDiscountsOffered", {
                defaultValue: "This plan offers no discounts.",
              })}
            </p>
          ) : (
            <>
              {/* ── CR-034 §7 · REQUIREMENT 3, THE FRAMING ──────────────────
                  The PO: *"when account is attached it will avail those
                  discounts"* — so this section is read as a statement about
                  what WILL be available once there is an account, not a list
                  of things that merely exist somewhere.
                  ⚠ **AND IT SAYS *ENROLLED*, NOT *ATTACHED*, BECAUSE THAT IS
                  WHAT REDUCES A BILL.** BR-RAT-069: attaching an account to
                  this unit puts it on this plan, and the plan grants a
                  discount to nobody. Writing the softer sentence — *"an
                  account here gets these"* — would promise a reduction the
                  bill run will not make, on a screen a clerk quotes from. */}
              <p className={`mb-2 ${ABSENT}`} data-discount-framing="">
                {t("metering.unit.pricing.discountFraming", {
                  defaultValue:
                    "An account attached to this unit takes this plan, so these are the discounts it can be given. Each one is granted by enrolling the account in it, and these are the conditions that enrolment has to satisfy.",
                })}
              </p>
              <PlainTable>
              <thead>
                <tr>
                  <th scope="col">{t("rating.charges.col.code", { defaultValue: "Code" })}</th>
                  <th scope="col">
                    {t("rating.planDetail.charges.col.charge", { defaultValue: "Charge" })}
                  </th>
                  <th scope="col">
                    {t("rating.planDetail.charges.col.amount", { defaultValue: "Amount" })}
                  </th>
                </tr>
              </thead>
              <tbody>
                {pricing.discounts.offered.map((row) => (
                  <tr key={row.discount_id} data-discount-offered={row.code ?? ""}>
                    <td>{row.code ?? "—"}</td>
                    <td>{row.name ?? "—"}</td>
                    {/* `value_display` is rating's own string. Never `value`,
                        which stores percentage POINTS and renders `15` as
                        `1500.00%` through a fraction formatter (DEF-291). */}
                    <td>{row.value_display ?? "—"}</td>
                  </tr>
                ))}
                </tbody>
              </PlainTable>
              {/* ── CR-034 §7 · REQUIREMENT 2, THE CONDITIONS ───────────────
                  One block per discount, BELOW the table rather than as more
                  columns in it: the table answers *"what does this plan
                  offer"* in three cells and stays readable, and a condition
                  is a paragraph, not a cell. The table's row shape is pinned
                  by a test that closes the `</tr>`; growing it sideways is
                  how the tenant-wide `enrolled` count would arrive one day. */}
              {pricing.discounts.offered.map((row) => (
                <DiscountTerms key={`${row.discount_id}-terms`} row={row} t={t} />
              ))}
            </>
          )}
          {pricing.discounts.granted.served ? null : (
            <p
              role="note"
              className={`mt-2 ${ABSENT}`}
              data-discount-granted-absent={pricing.discounts.granted.reason}
            >
              {t(`metering.unit.pricing.discount_granted.${pricing.discounts.granted.reason}`, {
                defaultValue:
                  "These are the discounts the plan offers. Whether any of them actually comes off a bill depends on the account being enrolled, and a unit has no account — so no discount is shown as applying here.",
              })}
            </p>
          )}
        </div>
      )}

      {/* BR-RAT-096 BINDINGS and BR-RAT-113 ATTACHMENTS are different
          sentences and stay two lists — "this plan binds the state of Texas"
          is not "this plan attaches the PUC Regulatory Fee". */}
      {pricing.taxes.jurisdiction_rules.length === 0 &&
      pricing.taxes.attachments.length === 0 ? null : (
        <div data-plan-taxes="">
          <h5 className={SECTION_HEADING}>
            {t("rating.definition.title.tax", { defaultValue: "Tax or fee" })}
          </h5>
          {pricing.taxes.jurisdiction_rules.map((row) => (
            <Row
              key={row.jurisdiction_id}
              label={t("rating.planDetail.taxes.col.jurisdiction", { defaultValue: "Authority" })}
              ruleRef="BR-RAT-096"
            >
              {/* `DEF-SHL-6348` — a dash, never the id (B14 rule 31). */}
              {row.jurisdiction ?? "—"}
            </Row>
          ))}
          {/* ⚠ **DEF-725 — SEVEN ROWS ALL LABELLED “Authority” AND NOT ONE
              TAX OR RATE.** The PO read this section on the deployed build and
              said *"you would ahve shown tax rates"*. Every value on it was
              TRUE, which is exactly why no assertion fired: rating serves taxes
              in TWO shapes and this plan has only the first. A JURISDICTION
              BINDING carries an authority and a `rate_override` and by design
              names no tax and no rate — *"this plan is bound to the State of
              Texas"* is a different sentence from *"this plan attaches the PUC
              Regulatory Fee"*. The ATTACHMENTS below carry the name and the
              rate, and this tenant's seeded plan has none of them.

              So the section is not wrong, it is UNANSWERABLE, and the fix is to
              say so rather than to let a list of bare authority names read as
              the answer to the question the clerk opened it for. This is
              DEF-445's lesson pointed at an absence that was never stated at
              all: a screen that cannot answer must say which question it is
              failing to answer. */}
          {pricing.taxes.attachments.length === 0 &&
          pricing.taxes.jurisdiction_rules.length > 0 ? (
            <p role="note" className={`mt-2 ${ABSENT}`} data-tax-bindings-only="">
              {t("metering.unit.pricing.tax_bindings_only", {
                defaultValue:
                  "These are the authorities this plan is bound to. No specific tax or fee is attached to it, so no rate can be shown here yet.",
              })}
            </p>
          ) : null}
          {pricing.taxes.attachments.map((row) => (
            <Row
              key={row.tax_id}
              label={row.name ?? row.kind ?? ""}
              ruleRef="BR-RAT-113"
            >
              {/* `rate_display` and `flat_amount_display` are rating's OWN
                  two-place strings (BR-RAT-087 / DEF-291). Nothing here
                  re-formats a percentage: stored to 6 places, displayed at 2,
                  by the module that owns the figure. */}
              {row.rate_display ?? row.flat_amount_display ?? "—"}
            </Row>
          ))}
          {/* ⚠ DEF-273 — THIS IS NOT THE FINAL TAX SET, and saying so is the
              point. Three of r10's five Texas rates scope by CUSTOMER CLASS
              (*"Comm, Industrial only · Residential exempt"*), which is an
              account fact a unit cannot supply. A screen that let this list
              read as "the taxes on the bill" would be wrong for every
              class-scoped rate. */}
          {pricing.taxes.narrowing === null || pricing.taxes.narrowing.final ? null : (
            <p
              role="note"
              className={`mt-2 ${ABSENT}`}
              data-tax-narrowing={pricing.taxes.narrowing.reason}
            >
              {t(`metering.unit.pricing.tax_narrowing.${pricing.taxes.narrowing.reason}`, {
                defaultValue:
                  "These are the taxes and fees the plan is bound to. Which of them a bill charges narrows again by the account's customer class, so this is the set to choose from and not the final list.",
              })}
            </p>
          )}
        </div>
      )}

      {pricing.penalty_rule === null ? null : (
        <div data-penalty-rule="">
          <h5 className={SECTION_HEADING}>
            {t("customers.moveIn.pricing.penaltyTitle", { defaultValue: "Late payment" })}
          </h5>
          <Row
            label={t("customers.moveIn.pricing.penaltyGrace", { defaultValue: "Grace period" })}
          >
            {pricing.penalty_rule.grace_days === null
              ? "—"
              : t("customers.moveIn.pricing.penaltyGraceDays", {
                  days: pricing.penalty_rule.grace_days,
                  mode: pricing.penalty_rule.grace_mode ?? "",
                  defaultValue: "{{days}} days ({{mode}})",
                })}
          </Row>
          <Row
            label={t("customers.moveIn.pricing.penaltyFee", { defaultValue: "Late fee" })}
          >
            <Money
              amount={pricing.penalty_rule.late_fee_min}
              currency={currency}
              absent={t("customers.moveIn.pricing.penaltyNoMinimum", {
                defaultValue: "No minimum late fee is set.",
              })}
            />
          </Row>
        </div>
      )}

      {/* ── CR-034 (b) · SECTION 9 · THE CONTRACT ──────────────────────────
          There is no contract object in this product — no table, no endpoint,
          no rule. So it is a stated absence and NOT an empty section: a heading
          with nothing under it reads as *this unit has no contract*, which is a
          claim nobody can make.

          ⚠ **NOT `ArrivesWith`, AND THE COMPONENT IS THE ARGUMENT.**
          `ArrivesWith` promises that a thing is ON ITS WAY with a later story.
          Nothing is on its way here: the PO captured contracts-on-plans as
          `CR-020` on 2026-08-20 and then HELD it on 2026-08-21 in as many words
          — *"hold on dont proceed"*. Drawing an *arrives-with* box over work the
          requester paused tells them the opposite of what they decided.

          ⚠ **AND NO OPEN QUESTION IS OWED AFTER ALL.** This lane's first draft
          served `tracks: null` and was going to report an OQ as owed; `CR-020`
          already covers it, and `rating/selectors.py` states the same fact one
          module over (*"CR-020, deferred by the PO"*). Minting an OQ beside a
          live CR is the duplicate-id failure from the other direction (OQ-197).
          The id rides on `data-cr`, never in the sentence (DEF-332). */}
      {pricing.contract.served ? null : (
        <div data-plan-contract="">
          <h5 className={SECTION_HEADING}>
            {t("metering.unit.pricing.contractTitle", { defaultValue: "Contract" })}
          </h5>
          <p
            role="note"
            className={ABSENT}
            data-contract-absent={pricing.contract.reason}
            data-cr={pricing.contract.change_request ?? undefined}
          >
            {t(`metering.unit.pricing.contract.${pricing.contract.reason}`, {
              defaultValue:
                "Contracts are not part of the product yet — the work is written down and paused, so there is nothing to show here. Nothing is assumed in its place.",
            })}
          </p>
        </div>
      )}

      {/* ⛔ OQ-363. The one panel B18 asks for that this lane refuses to invent.
          NO FIGURE — not a total, not a "from $X", not a sum of the base
          charges above. The id rides on `data-tracks` (DEF-332). */}
      {/* ⚠ `tracks` IS A LITERAL, NOT `{pricing.worked_month.tracks}` — and the
          first draft wrote the expression. G38 reports that as an absence
          citing NOTHING, and it is right: the whole value of the id is that
          closing OQ-363 points a reader at every screen still claiming it, and
          neither G38 nor a human grep can see an id that exists only at
          runtime. The SERVED value is not ignored — `MoveInWizard.test.tsx`
          asserts the rendered `data-tracks` against the fixture's own
          `worked_month.tracks`, so a literal that drifts from the payload's id
          goes RED. */}
      {pricing.worked_month.served || props.workedMonthAbsence === false ? null : (
        <ArrivesWith
          title={t("customers.moveIn.pricing.workedMonthTitle", {
            defaultValue: "An example month",
          })}
          message={t(`metering.unit.pricing.worked_month.${pricing.worked_month.reason}`, {
            defaultValue:
              "We cannot show a worked example month yet. Nothing prices a plan outside a bill run, and there is no agreed figure for how much a new tenant is assumed to use — so any number here would be invented. The rates, charges and taxes below are the real ones.",
          })}
          tracks="OQ-363"
        />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W5 task 5.3 (B18 §5.5.3 step 4 + §5.5.5) — NO STORY OWNS IT, reported (hard-won law 8)
// generated: 2026-08-25 by the CR-030 W5 R1 lane (the FRONTEND half of `GET /units/{id}/pricing`, which shipped 2026-08-25 with no caller — hard-won law 2)
// AMENDED 2026-08-26 by the CR-034 §7 DISCCOND lane (PO: *"We should show all discount plan offer and what condition are required to avail that discount ; when account is attached it will avail those discounts"*. `DiscountTerms` renders the twelve stored conditions per discount BELOW the offered table — the table's three-cell row is pinned closed by a test and is deliberately not grown sideways. ⚠ Every condition carries the fact that NOTHING EVALUATES IT: `eligibility_rule` is advisory, so the block prints *"Nothing in this product checks this condition"* and the rule DOCUMENT is never shipped to the client. The programme's tenant-wide `budget_cap` is absent at source, like `enrolled`; the customer's own caps are shown. 52 new keys handed over as `newkeys-DISCCOND.json`, every call site carrying a `defaultValue`, including five enum-label families where an UNKNOWN value prints itself rather than blank. ALSO: `currentMonthPeriod` — PO 2026-08-26 *"B Default to this month"*, on the `showPeriod` mount ONLY; the move-in wizard is unchanged and the endpoint invents no period, guarded in both directions)
// checklist: A✔ B=n/a(no-backend-half) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see MoveInWizard.tsx's trailer — this file and UnitAssetsPanel.tsx are that lane's two new components. This file's OWN two: G31 declared-classes goes 0→5 because it is written in Tailwind utilities per B14 rule 21 and `src/styles/route-b-migrated.txt` (not this lane's file) has no line for it yet — the line owed is `features/customers/UnitPricingPanel.tsx`; and G27 i18n-keys names 13 new keys, handed over as `newkeys-R1.json`, every call site carrying a `defaultValue` so nothing renders a raw key meanwhile. ⚠ Every utility this file names was compiled through the REAL Tailwind compiler against `src/styles/tailwind.css` — the stricter question `routeBUtilities.test.ts` will ask the day the ledger lists it — and all of them generate a rule. tsc✔ · eslint --max-warnings 0✔ · vitest via MoveInWizard.test.tsx✔ · G13✔ G38✔ (its stated absence cites a real id) G40✔
// exceptions: E3 THE WORKED MONTH IS NOT COMPUTED AND NO DOLLAR FIGURE STANDS IN FOR IT (OQ-363). Nothing prices a plan outside a bill run and no signed rule states the consumption it would be priced at; summing the base charges would be BR-RAT-005's tax base reimplemented outside the ❄️ FROZEN engine, in TypeScript, where GT-1..61 cannot see it
// exceptions: E3 no plan PICKER (BR-CUS-029 + PO 2026-08-11 — the plan lives once on the unit and the account derives it, so a control here would write nothing); this panel reads and records nothing
// exceptions: E4 every money figure is rating's stored string rendered through the ONE display boundary (`MoneyCell`, BR-SHL-023/BR-TEN-080 — storage 6 dp, wire 4 dp, display 2 dp). Percentages are rating's own `rate_display`, never re-formatted here (BR-RAT-087 / DEF-291)
// exceptions: E4 a row with an amount but NO `CHAR(3)` currency renders its absence sentence rather than a defaulted `USD` — a currency the tenant never chose is a wrong figure, not a missing one
// exceptions: E4 the payload shapes are typed HERE rather than in `src/api/endpoints.ts` (B13 §2) because this lane does not own that file; the move is OWED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
