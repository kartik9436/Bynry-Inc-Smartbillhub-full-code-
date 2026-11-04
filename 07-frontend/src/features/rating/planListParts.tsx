// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 6 — the pieces of one Plans LIST row,
//           built from images 01–03 of 05-prototype/plans-2026-10-03.
// Defect:   DEF-RAT-9333
// Rules:    B14 rules 21 · 31 · 37 · 43 · 44 · NFR-3 · NFR-5 · BR-RAT-1040
// ───────────────────────────────────────────────────────
/**
 * THE CELLS OF ONE PLAN ROW, THE LIST'S SORT VOCABULARY, AND HOW A CUSTOMER
 * CLASS IS NAMED ON IT.
 *
 * ⚠ **THE ROUND-2 FIELDS ARE OPTIONAL HERE ON PURPOSE** — the
 * `discountListParts.tsx` posture. `schedules`, `units`, `upcoming_version` and
 * `customer_classes` are CR-167 §7.3's `GET /plans` additions (the last one is
 * asked of the back end by this lane, see the CR's §12), and the server that
 * serves them is being built by a sibling lane at the same time as this
 * screen. They are declared on a LOCAL type so this lane edits no line of the
 * shared `endpoints.ts` the form lane is also editing. A row from a server
 * that predates them still renders: Schedules counts the row's own
 * `rate_schedules`, Units reads the old `accounts` count (which IS the current
 * unit-assignment count, `selectors.plan_row`).
 *
 * ⚠ **A CLASS IS NAMED ONLY BY THE ROW'S OWN `customer_classes` (`DEF-RAT-9354`,
 * 2.484.2).** The server serves them on every row from one names read per page;
 * the list's second read of the tenant's whole class list is gone.
 */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { PLAN_SORTS } from "@/api/endpoints";
import type { PlanRow } from "@/api/endpoints";
import { InlineLinkTo } from "@/components/Surfaces";

/** A per-utility list value as the contract serves it. */
export interface PlanListOption {
  value: string;
  label: string;
}

/** A list row as the round-2 contract serves it. */
export type PlanListRow = PlanRow & {
  /** How many rate schedules the plan names — one per priced service. */
  schedules?: number | null;
  /** Current unit assignments — the Units tab's number. */
  units?: number | null;
  upcoming_version?: { version: number; effective_from: string } | null;
  /** The plan's classes as words; `[]` is every class. */
  customer_classes?: PlanListOption[] | null;
};

/**
 * The sorts the list offers, and every one is the SERVER's (NFR-3): CR-167
 * §7.3 adds `version`, `effective_from`, `effective_to` and `units` to the
 * existing `name` and `status`.
 *
 * ⚠ **`base_charges` IS NOT HERE, AND THE CONTRACT ROW THAT LISTS IT IS
 * OVERRULED BY `BR-RAT-1040` (PO 2026-09-27, closing `DEF-RAT-6927`).** The
 * figure is a walk over class- and size-narrowed charge codes, not a column,
 * so there is nothing for `ORDER BY` to read; a sortable head would be a live
 * control over an order that means nothing. Reported to the coordinator.
 */
export const PLAN_LIST_SORTS = PLAN_SORTS;

/** A dash for a value the server has not served — never a zero, never blank. */
export const DASH = "—";

/** Schedules: the served count, else the row's own list. */
export function planListSchedules(row: PlanListRow): number {
  return row.schedules ?? row.rate_schedules.length;
}

/** Units: the served count, else today's assignment count. */
export function planListUnits(row: PlanListRow): number {
  return row.units ?? row.accounts;
}

/**
 * The class words under a plan's code — the row's served labels; `[]` is every
 * class. A row from a server that predates `customer_classes` names no class
 * it cannot word (B14 rule 31: never an id), and an older row with no classes
 * is still every class.
 */
export function planListClasses(row: PlanListRow, everyClass: string): string {
  if (row.customer_classes !== undefined && row.customer_classes !== null) {
    if (row.customer_classes.length === 0) return everyClass;
    return row.customer_classes.map((option) => option.label).join(", ");
  }
  return (row.account_type_ids ?? []).length === 0 ? everyClass : "";
}

/** Plan: the name (the door to details), and `CODE · Class` under it. */
export function PlanNameCell(props: { row: PlanListRow; to: string; classes: string }): ReactNode {
  const under = [props.row.code, props.classes].filter((part) => part !== "").join(" · ");
  return (
    <div className="flex flex-col">
      <InlineLinkTo to={props.to} className="font-semibold">
        {props.row.name}
      </InlineLinkTo>
      <span className="text-sm text-neutral-700">{under}</span>
    </div>
  );
}

/** Version: `V3` in a small grey tag (the taxes and discounts lists' tag). */
export function PlanVersionTag(props: { version: number | null | undefined }): ReactNode {
  const { t } = useTranslation();
  if (props.version === null || props.version === undefined) return <span>{DASH}</span>;
  return (
    <span className="inline-block bg-neutral-200 px-1.5 text-xs font-semibold text-neutral-700">
      {t("rating.taxes.list.version", { n: props.version })}
    </span>
  );
}
