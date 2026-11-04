// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 5 — the pieces of one Discounts LIST row,
//           built from images 01–04 of 05-prototype/discounts-2026-10-03.
// Defect:   DEF-RAT-9290 (D14–D17)
// Rules:    B14 rules 21 · 31 · 37 · 43 · BR-RAT-087 (the server's display
//           string, never a client-side format) · NFR-3
// ───────────────────────────────────────────────────────
/**
 * THE CELLS OF ONE DISCOUNT ROW, AND THE LIST'S OWN STATUS VOCABULARY.
 *
 * ⚠ **THE ROUND-2 FIELDS ARE OPTIONAL HERE ON PURPOSE.** `effective_to`,
 * `receiving`, `offered_to`, `version` and the `{value,label}` shapes of
 * `eligibility` and `verification` are the API contract round 2 builds against
 * (CR-166 §9, task 3), and the back end that serves them is being built by a
 * sibling lane at the same time as this screen. A row from a server that
 * predates them renders a dash in those cells and nothing breaks. They are
 * declared on a LOCAL type rather than on `DiscountRow` so this lane edits no
 * line of the shared `endpoints.ts` the form and details lanes are also
 * editing — the same posture as `taxListParts.tsx`.
 *
 * ⚠ **THE `$` IS THE SERVER'S.** The contract serves `value_display` *"with
 * `$` or `%`"*. This file prints that string and nothing else (BR-RAT-087), so
 * the symbol and its currency are decided once, on the server, beside the
 * tenant's currency — a client that added `$` would be wrong on the first
 * utility that bills in another currency.
 */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { DiscountRow } from "@/api/endpoints";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";

/** A per-utility list value as the contract serves it. */
export interface DiscountListOption {
  value: string;
  label: string;
  checked_by?: "system" | "proof";
}

/** A contract field that may arrive as a code (an older server), one option or several. */
export type DiscountListLabelled = string | DiscountListOption | DiscountListOption[] | null;

/** A list row as the round-2 contract serves it. */
export type DiscountListRow = Omit<DiscountRow, "eligibility" | "verification"> & {
  eligibility: DiscountListLabelled;
  verification: DiscountListLabelled;
  version?: number | null;
  effective_to?: string | null;
  /** Accounts actually getting it — what `Enrolled` counts once served. */
  receiving?: number | null;
  offered_to?: number | null;
};

/**
 * The Status filter's options — the five words of the PO's lifecycle
 * (2026-10-03), in the order a clerk scans them. The server's `scheduled`
 * (approved, start date not yet reached) still renders with its own word if it
 * is served; it is not offered as a filter because the drawing does not offer
 * it (image 02).
 */
export const DISCOUNT_LIST_STATUSES = [
  "active",
  "draft",
  "waiting_approval",
  "ended",
  "retired",
] as const;

/** A dash for a value the server has not served — never a zero, never blank. */
export const DASH = "—";

/** Status meaning only (A12): live is success, waiting is info, over is muted. */
export function discountListStatusTone(status: string): StatusTone {
  if (status === "active") return "success";
  if (status === "scheduled") return "info";
  if (status === "suspended_funding_exhausted") return "danger";
  if (status === "ended" || status === "retired") return "muted";
  return "neutral";
}

/**
 * A labelled contract field as words. An option shows its `label`; several are
 * joined; a bare code (an older server) goes through `stem` so it reads as a
 * word and never as a code (B14 rule 31). Nothing served is a dash.
 */
export function discountListLabel(
  value: DiscountListLabelled,
  codeLabel: (code: string) => string,
): string {
  if (value === null || value === "") return DASH;
  if (typeof value === "string") return codeLabel(value);
  const options = Array.isArray(value) ? value : [value];
  const labels = options.map((option) => option.label).filter((label) => label !== "");
  return labels.length === 0 ? DASH : labels.join(", ");
}

/** Code: bold, the door to the details page. */
export function DiscountCodeCell(props: { row: DiscountListRow; to: string }): ReactNode {
  return (
    <InlineLinkTo to={props.to} className="font-semibold">
      {props.row.code}
    </InlineLinkTo>
  );
}

/** Value: the server's string, bold — `$25.00` or `15%` (D15). */
export function DiscountValueCell(props: { row: DiscountListRow }): ReactNode {
  return (
    // DEF-RAT-9319: no `whitespace-nowrap` — `$25.00` and `15.00%` carry no
    // space to break at, and an allowance's `2.00 kgal` may put its unit under
    // the figure; held on one line it pushed the German list past 1,120px.
    <span className="font-semibold">{props.row.value_display ?? DASH}</span>
  );
}

/** Enrolled: accounts RECEIVING it once served, today's count before that. */
export function discountListEnrolled(row: DiscountListRow): number {
  return row.receiving ?? row.enrolled;
}

export function DiscountStatusCell(props: { status: string }): ReactNode {
  const { t } = useTranslation();
  return (
    <StatusPill tone={discountListStatusTone(props.status)}>
      {t(`rating.discounts.status.${props.status}`, { defaultValue: props.status })}
    </StatusPill>
  );
}
