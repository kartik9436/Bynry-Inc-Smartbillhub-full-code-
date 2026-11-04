// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — what every step of the New plan form
//           shares (the discount and tax forms' structure, copied).
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, importable by round 3's
//           three Edit choices) · B14 rule 31 (no database id is ever the
//           visible value of a field)
// ───────────────────────────────────────────────────────
//
// THE CONTRACT BETWEEN THE PAGE AND ITS STEPS.
//
// A step is a component of `PlanStepProps`: the draft, a patch function, the
// lists it renders from, and a set of LOCKED fields. The New page locks
// nothing; round 3's *Name and details* locks every pricing field, *Change
// from a date* and *Fix a mistake* lock the details — the same components, the
// same boxes. Nothing about a step knows which page mounted it.
import type { PlanFormOptions, PlanNoteAttribute } from "@/api/planFormEndpoints";
import type { CheckDropdownOption } from "@/components/CheckDropdown";
import type { RegionalDateFormat } from "@/components/DateCell";

import type { Translator } from "../ratingShared";
import type { PlanFormDraft } from "./planFormModel";

export type { Translator };

export interface PlanFormLists {
  /** Every list, from `GET /plans/form-options`; empty until it lands. */
  options: PlanFormOptions;
  /** The customer classes for the tick dropdown (*Every customer class* is the
   *  dropdown's own first row). */
  classOptions: CheckDropdownOption[];
  /** What a note may be about, each with its value list. */
  noteAttributes: PlanNoteAttribute[];
  /** CHAR(3), the utility's own; `null` until read. */
  currency: string | null;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** Where *Switch more services on ↗* and *Not listed? Define it ↗* open. */
  servicesSettingsHref: string;
  newChargeCodeHref: string;
}

export interface PlanStepProps {
  draft: PlanFormDraft;
  onChange: (patch: Partial<PlanFormDraft>) => void;
  lists: PlanFormLists;
  /** Fields drawn but not editable — round 3's Edit choices. */
  locked?: ReadonlySet<keyof PlanFormDraft>;
  t: Translator;
}

export function isLocked(props: Pick<PlanStepProps, "locked">, field: keyof PlanFormDraft): boolean {
  return props.locked?.has(field) === true;
}

/** A form section's heading, inside its box. */
export const SECTION_HEADING = "m-0 mb-4 font-heading text-h4";

/** Two fields side by side (image 04: Plan name | Code). */
export const PAIR = "grid grid-cols-2 gap-x-4 gap-y-5";

/**
 * The frame draws rail, content and footer as one column; this lays them onto
 * two — the rail across both, the step and its footer on the left, *This plan*
 * on the right (images 04–23) — by the `data-wizard` hooks it already renders.
 * The discount form's device, copied so the two forms cannot lay out
 * differently. The frame's own refusal line is hidden because this form says
 * *Fix N things first.* beside Continue instead (images 05, 10, 15, 19).
 */
export const PLAN_FORM_LAYOUT =
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

/** The words a class or a service is stored by in a note (`DEF-RAT-9285`). */
export function optionLabel(options: readonly { value: string; label: string }[], value: string): string {
  return options.find((option) => option.value === value)?.label ?? "";
}
