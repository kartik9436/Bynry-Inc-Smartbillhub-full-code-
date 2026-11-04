// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — what every step of the tax form shares.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, importable by the
//           round-3 edit variations) · B14 rule 31 (no database id is ever the
//           visible value of a field — every id below is shown by its label)
// ───────────────────────────────────────────────────────
//
// THE CONTRACT BETWEEN THE PAGE AND ITS STEPS.
//
// A step is a component of `StepProps`: the draft, a patch function, the lists
// it renders from, and a set of LOCKED fields. The new-tax page locks nothing;
// round 3's *Name and filing* locks rate and reach, *Fix a mistake* locks the
// dates — the same components, the same boxes, greyed. Nothing about a step
// knows which page mounted it.
import type { ReactNode } from "react";

import type { RegionalDateFormat } from "@/components/DateCell";
import type { CheckDropdownOption } from "@/components/CheckDropdown";
import type { MatchedPremises } from "@/api/endpoints";
import type { TaxFormOption } from "@/api/taxFormEndpoints";

import { serviceBadge } from "../ratingShared";
import { BASIS_FLAT, BASIS_PERCENT, effectiveBasis, fractionToPercent, percentToFraction } from "./taxFormModel";
import type { TaxFormDraft } from "./taxFormModel";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/** Every list a step renders from. Each one comes from the server; an empty
 *  list is a read that has not landed or a route that is not served yet. */
export interface TaxFormLists {
  authorities: TaxFormOption[];
  boundaries: TaxFormOption[];
  /** Boundary values that ask for a place name (image 07). */
  placeBoundaries: string[];
  services: CheckDropdownOption[];
  classes: CheckDropdownOption[];
  bases: TaxFormOption[];
  rounding: TaxFormOption[];
  discounts: TaxFormOption[];
  liabilityAccounts: TaxFormOption[];
  filingFrequencies: TaxFormOption[];
  dueRules: TaxFormOption[];
  authorityAccounts: TaxFormOption[];
  /** How many registration numbers are held with the tax's authority (a saved
   *  but retired one is not counted) — 0 opens the *None held* note. */
  authorityAccountsHeld: number;
  /** The tax's authority by name, for that note; "" when none is chosen. */
  authorityName: string;
  /** The reach of the boundary as typed — `null` while it is counted. */
  reach: MatchedPremises | null;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** Where the "Add one" link under *Tax registration no.* goes. */
  authorityAccountsHref: string;
}

export interface StepProps {
  draft: TaxFormDraft;
  onChange: (patch: Partial<TaxFormDraft>) => void;
  lists: TaxFormLists;
  /** Fields drawn but not editable — the round-3 edit variations. */
  locked?: ReadonlySet<keyof TaxFormDraft>;
  t: Translator;
}

export function isLocked(props: Pick<StepProps, "locked">, field: keyof TaxFormDraft): boolean {
  return props.locked?.has(field) === true;
}

/** A form section: a box with its heading inside (`Panel` is the information
 *  group of the kit; the drawing's sections are boxes with a heading). */
export const SECTION_HEADING = "m-0 mb-4 font-heading text-h4";

/** Two fields side by side, as every drawn row of this form sets them. */
export const PAIR = "grid grid-cols-2 gap-x-4 gap-y-5";

/** A small money table: every column after the first is a figure, right-aligned
 *  (the kit's `PlainTable` sets cells left; this narrower selector wins). */
export const MONEY_COLUMNS =
  "[&_td:not(:first-child)]:text-right [&_th:not(:first-child)]:text-right";

/** The service colour square the drawing puts beside a service's name. */
export function ServiceMarker(props: { code: string }) {
  const badge = serviceBadge(props.code);
  return (
    <span
      aria-hidden="true"
      className="inline-block h-2.5 w-2.5 flex-none"
      style={{ background: `var(${badge.token})` }}
    />
  );
}

/**
 * THE SERVER'S LISTS, IN THE CLERK'S LANGUAGE (B14 rule 35). `GET
 * /taxes/form-options` sends an English `label` as a FALLBACK; the words a
 * clerk reads are this catalogue's, keyed on the `value`. Written as LITERAL
 * keys rather than assembled from the value, because a template key renders
 * and is invisible to G18, which reads literal dotted strings. A value this
 * map does not know (a boundary the server adds later) shows the server's
 * label, so a new option appears without a screen change.
 */
const OPTION_KEYS: Readonly<Record<string, string>> = {
  "basis:percent": "rating.taxForm.option.basis.percent",
  "basis:flat_per_bill": "rating.taxForm.option.basis.flat_per_bill",
  "basis:per_unit": "rating.taxForm.option.basis.per_unit",
  "basis:per_meter": "rating.taxForm.option.basis.per_meter",
  "boundary:everywhere": "rating.taxForm.option.boundary.everywhere",
  "boundary:city_limits": "rating.taxForm.option.boundary.city_limits",
  "boundary:state": "rating.taxForm.option.boundary.state",
  "due:15th_next_month": "rating.taxForm.option.due.15th_next_month",
  "due:20th_next_month": "rating.taxForm.option.due.20th_next_month",
  "due:25th_next_month": "rating.taxForm.option.due.25th_next_month",
  "due:last_day_next_month": "rating.taxForm.option.due.last_day_next_month",
  "due:30_days_after_quarter": "rating.taxForm.option.due.30_days_after_quarter",
  "due:jan_31_next_year": "rating.taxForm.option.due.jan_31_next_year",
  "filing:monthly": "rating.taxForm.option.filing.monthly",
  "filing:quarterly": "rating.taxForm.option.filing.quarterly",
  "filing:annual": "rating.taxForm.option.filing.annual",
};

export function localiseOptions<O extends TaxFormOption>(
  list: "basis" | "boundary" | "due" | "filing",
  options: readonly O[],
  t: Translator,
): O[] {
  return options.map((option) => {
    const key = OPTION_KEYS[`${list}:${option.value}`];
    return key === undefined ? option : { ...option, label: t(key) };
  });
}

export function labelOf(options: readonly TaxFormOption[], value: string): string {
  if (value === "") return "";
  return options.find((option) => option.value === value)?.label ?? "";
}

/** `6.25%` / `$6.25` — the big figure on the summary and the Rate row. */
export function rateFigure(draft: TaxFormDraft): string | null {
  const basis = effectiveBasis(draft);
  if (basis === BASIS_PERCENT) {
    const fraction = percentToFraction(draft.rate_percent);
    return fraction === null ? null : `${fractionToPercent(fraction)}%`;
  }
  const amount = draft.amount.trim();
  return /^\d{1,9}(\.\d{1,4})?$/.test(amount) ? `$${twoPlaces(amount)}` : null;
}

export function twoPlaces(amount: string): string {
  const [whole, part = ""] = amount.split(".");
  return `${whole.replace(/^0+(?=\d)/, "")}.${part.padEnd(2, "0").slice(0, 2)}`;
}

/** The words under the big figure: *of the bill* / *fixed amount per bill*. */
export function rateUnitKey(draft: TaxFormDraft): string {
  const basis = effectiveBasis(draft);
  if (basis === BASIS_PERCENT) return "rating.taxForm.unit.percent";
  if (basis === BASIS_FLAT) return "rating.taxForm.unit.flat";
  return "rating.taxForm.unit.other";
}

/**
 * *🔒 Change with a new rate.* / *🔒 Same dates as today.* — the note the edit
 * variations put at the right of a section whose boxes they lock (images 24,
 * 31). One INSTRUCTION or FACT, never the reason (B14 rule 33).
 */
export function LockNote(props: { children: ReactNode }) {
  return (
    <p className="m-0 text-sm text-neutral-700" data-tax-lock-note="">
      <span aria-hidden="true">🔒</span> {props.children}
    </p>
  );
}
