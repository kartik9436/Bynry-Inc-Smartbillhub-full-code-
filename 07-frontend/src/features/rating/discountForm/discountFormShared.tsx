// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — what every step of the discount form
//           shares.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, importable by round 3's
//           edit variations) · B14 rule 31 (no database id is ever the visible
//           value of a field — every value below is shown by its label) · B14
//           rule 35 (the clerk reads the catalogue's words, never the server's
//           English fallback)
// ───────────────────────────────────────────────────────
//
// THE CONTRACT BETWEEN THE PAGE AND ITS STEPS.
//
// A step is a component of `DiscountStepProps`: the draft, a patch function,
// the lists it renders from, and a set of LOCKED fields. The New page locks
// nothing; round 3's *Name and details* locks value, limits and the start, *New
// value from a date* locks the details, *Fix a mistake* locks the dates — the
// same components, the same boxes, greyed. Nothing about a step knows which
// page mounted it.
import type { ReactNode } from "react";

import type { CheckDropdownOption } from "@/components/CheckDropdown";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { DiscountEligibilityOption, DiscountFormOption } from "@/api/discountFormEndpoints";

import type { DiscountFormDraft } from "./discountFormModel";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/** Every list a step renders from. Each comes from the server; an empty list
 *  is a read that has not landed or a route that is not served yet. */
export interface DiscountFormLists {
  programOwners: DiscountFormOption[];
  exclusivityGroups: DiscountFormOption[];
  eligibility: DiscountEligibilityOption[];
  enrollmentModes: DiscountFormOption[];
  verification: DiscountFormOption[];
  lapse: DiscountFormOption[];
  budgetPeriods: DiscountFormOption[];
  budgetOut: DiscountFormOption[];
  types: DiscountFormOption[];
  appliesTo: DiscountFormOption[];
  /** The services this utility has switched on (`GET /settings/services`). */
  services: CheckDropdownOption[];
  /** The utility's charge codes, valued by CODE — `discount_pricing` joins on
   *  `line.charge_code`, so an id here would price nothing. */
  chargeCodes: CheckDropdownOption[];
  /** The utility's own currency code (`USD`), or `null` until it is read. */
  currency: string | null;
  /** The unit a usage allowance counts in, from the service it names
   *  (`BR-RAT-960`), or `null` when no single service is chosen. */
  allowanceUnit: string | null;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** The UI language, for the currency's name. */
  language: string;
}

export interface DiscountStepProps {
  draft: DiscountFormDraft;
  onChange: (patch: Partial<DiscountFormDraft>) => void;
  lists: DiscountFormLists;
  /** Fields drawn but not editable — the round-3 edit variations. */
  locked?: ReadonlySet<keyof DiscountFormDraft>;
  t: Translator;
}

export function isLocked(props: Pick<DiscountStepProps, "locked">, field: keyof DiscountFormDraft): boolean {
  return props.locked?.has(field) === true;
}

/** A form section: a box with its heading inside. */
export const SECTION_HEADING = "m-0 mb-4 font-heading text-h4";

/** Two fields side by side, as every drawn row of this form sets them. */
export const PAIR = "grid grid-cols-2 gap-x-4 gap-y-5";

/**
 * The frame draws rail, content and footer as one column; this lays its parts
 * onto two — the rail across both, the step and its footer on the left, the
 * summary on the right — by the `data-wizard` hooks it already renders (the
 * tax form's device). The frame's own refusal line is hidden because this form
 * says *Fix N things first.* beside Continue instead (images 13, 14, 16, 32,
 * 35). Shared by the New form and the Edit form (round 3), so the two pages
 * cannot lay out differently.
 */
export const DISCOUNT_FORM_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 items-start " +
  "[&_[data-wizard=frame]]:contents " +
  "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
  "[&_[data-wizard=rail]]:mb-5 [&_[data-wizard=rail]]:border [&_[data-wizard=rail]]:bg-surface " +
  "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-2 " +
  "[&_[data-wizard=content]]:mb-0 " +
  "[&_[data-wizard=actions]]:col-start-1 [&_[data-wizard=actions]]:row-start-3 " +
  "[&_[data-wizard=actions]]:mt-5 [&_[data-wizard=actions]]:border-t " +
  "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
  "[&_[data-wizard=blocked]]:hidden";

/** The lock line beside a section heading on the Edit form — *🔒 Change with
 *  a new value.* (image 27), *🔒 Same dates as today.* (image 34). */
export function LockNote(props: { children: ReactNode }) {
  return (
    <p className="m-0 text-sm text-neutral-700" data-discount-lock-note="">
      <span aria-hidden="true">🔒</span> {props.children}
    </p>
  );
}

/**
 * THE SERVER'S LISTS, IN THE CLERK'S LANGUAGE (B14 rule 35). `GET
 * /discounts/form-options` sends an English `label` as a FALLBACK; for the
 * PLATFORM's own codes (types, scopes, enrollment, verification, lapse, budget)
 * the words a clerk reads are the catalogue's, keyed on the value — written as
 * LITERAL keys so G18 can see each is used. A value this map does not know is
 * shown by the server's label, so a new option appears without a screen change.
 *
 * ⚠ **PROGRAM OWNER, EXCLUSIVITY GROUP AND WHO QUALIFIES ARE NOT IN THIS MAP
 * ON PURPOSE.** They are each UTILITY's own lists, edited in Settings (CR-166
 * §9), so their labels are the utility's data, typed by the utility — the same
 * as a plan name. Translating a value a clerk can rename would show a word the
 * utility never chose.
 */
const OPTION_KEYS: Readonly<Record<string, string>> = {
  "type:percentage": "rating.discounts.type.percentage",
  "type:fixed_amount": "rating.discounts.type.fixed_amount",
  "type:rate_override": "rating.discounts.type.rate_override",
  "type:charge_waiver": "rating.discounts.type.charge_waiver",
  "type:usage_allowance": "rating.discounts.type.usage_allowance",
  "scope:whole_bill": "rating.discounts.scope.whole_bill",
  "scope:all_services": "rating.discounts.scope.all_services",
  "scope:specific_services": "rating.discounts.scope.specific_services",
  "scope:one_service": "rating.discounts.scope.one_service",
  "scope:usage_only": "rating.discounts.scope.usage_only",
  "scope:base_only": "rating.discounts.scope.base_only",
  "scope:named_codes": "rating.discounts.scope.named_codes",
  "enrollment:automatic": "rating.discounts.enrolment.automatic",
  "enrollment:apply_and_approve": "rating.discounts.enrolment.apply_and_approve",
  "verification:one_time_proof": "rating.discounts.verification.one_time_proof",
  "verification:annual_recertification": "rating.discounts.verification.annual_recertification",
  "verification:agency_file_monthly": "rating.discounts.verification.agency_file_monthly",
  "verification:automatic": "rating.discounts.verification.automatic",
  "lapse:notify_then_drop": "rating.discountWizard.lapse.notify_then_drop",
  "lapse:drop_silently": "rating.discountWizard.lapse.drop_silently",
  "lapse:never_expires": "rating.discountWizard.lapse.never_expires",
  "period:monthly": "rating.discountWizard.budgetPeriod.monthly",
  "period:annual": "rating.discountWizard.budgetPeriod.annual",
  "period:lifetime": "rating.discountWizard.budgetPeriod.lifetime",
  "out:suspend": "rating.discountWizard.exhaustion.suspend",
  "out:refuse_new_enrolment": "rating.discountWizard.exhaustion.refuse_new_enrolment",
  "out:continue_over_budget": "rating.discountWizard.exhaustion.continue_over_budget",
};

/** The words after the type's name in the Type dropdown (image 05: *Percentage
 *  — A share of the charges*). */
const TYPE_HINT_KEYS: Readonly<Record<string, string>> = {
  percentage: "rating.discountForm.typeHint.percentage",
  fixed_amount: "rating.discountForm.typeHint.fixed_amount",
  rate_override: "rating.discountForm.typeHint.rate_override",
  charge_waiver: "rating.discountForm.typeHint.charge_waiver",
  usage_allowance: "rating.discountForm.typeHint.usage_allowance",
};

export function localiseOptions<O extends DiscountFormOption>(
  list: "type" | "scope" | "enrollment" | "verification" | "lapse" | "period" | "out",
  options: readonly O[],
  t: Translator,
): O[] {
  return options.map((option) => {
    const key = OPTION_KEYS[`${list}:${option.value}`];
    return key === undefined ? option : { ...option, label: t(key) };
  });
}

/** *off subtotal before taxes* — one whole phrase per platform scope, in each
 *  catalogue's own words (DEF-RAT-9316). Never a capitalised list label dropped
 *  into a sentence, and never that label lowercased: a German noun keeps its
 *  capital and Japanese puts the scope before the verb. */
const OFF_SCOPE_KEYS: Record<string, string> = {
  whole_bill: "rating.discountForm.offScope.whole_bill",
  base_only: "rating.discountForm.offScope.base_only",
  usage_only: "rating.discountForm.offScope.usage_only",
  all_services: "rating.discountForm.offScope.all_services",
  one_service: "rating.discountForm.offScope.one_service",
  specific_services: "rating.discountForm.offScope.specific_services",
  named_codes: "rating.discountForm.offScope.named_codes",
};

/** The phrase for a scope code, or `null` for a code that has none. */
export function offScopePhrase(code: string | null | undefined, t: Translator): string | null {
  const key = code ? OFF_SCOPE_KEYS[code] : undefined;
  return key === undefined ? null : t(key);
}

/** The Type dropdown's option: *Percentage — A share of the charges*. */
export function typeOptionLabel(option: DiscountFormOption, t: Translator): string {
  const hint = TYPE_HINT_KEYS[option.value];
  return hint === undefined ? option.label : `${option.label} — ${t(hint)}`;
}

export function labelOf(options: readonly DiscountFormOption[], value: string): string {
  if (value === "") return "";
  return options.find((option) => option.value === value)?.label ?? "";
}

/** `USD · US dollar` — the code and its name in the clerk's language. The name
 *  comes from the browser's own currency names, so no list of currencies is
 *  typed out here. */
export function currencyLine(code: string | null, language: string): string {
  if (code === null || code === "") return "—";
  try {
    const name = new Intl.DisplayNames([language], { type: "currency" }).of(code);
    return name === undefined || name === code ? code : `${code} · ${name}`;
  } catch {
    return code;
  }
}
