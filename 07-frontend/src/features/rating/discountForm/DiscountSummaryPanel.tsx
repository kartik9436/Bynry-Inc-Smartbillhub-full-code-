// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — the *This discount* panel on the
//           right of every step of the New discount form (images 05–18 of
//           `05-prototype/discounts-2026-10-03/images/`).
// ───────────────────────────────────────────────────────
//
// What the discount will be, as it stands, beside every step: the value in
// large type, what it is taken off, six facts and what it takes off a $60.00
// bill.
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import {
  EXAMPLE_BILL,
  SCOPE_NAMED_CODES,
  SCOPE_ONE_SERVICE,
  SCOPE_SPECIFIC_SERVICES,
  effectiveType,
  exampleReduction,
  limitsSetCount,
  valueBoxFor,
  valueFigure,
} from "./discountFormModel";
import type { DiscountFormDraft } from "./discountFormModel";
import { labelOf, offScopePhrase } from "./discountFormShared";
import type { DiscountFormLists, Translator } from "./discountFormShared";

const ROW = "flex items-baseline justify-between gap-3 text-base";

/** What a percentage is taken OFF: the scope, or the service or codes it names. */
export function scopeWords(draft: DiscountFormDraft, lists: DiscountFormLists): string {
  if (draft.applies_to === SCOPE_ONE_SERVICE) {
    return labelOf(lists.services, draft.applies_to_service) || "—";
  }
  if (draft.applies_to === SCOPE_SPECIFIC_SERVICES) {
    const chosen = lists.services.filter((row) => draft.applies_to_services.includes(row.value));
    return chosen.length === 0 ? "—" : chosen.map((row) => row.label).join(", ");
  }
  if (draft.applies_to === SCOPE_NAMED_CODES) {
    return draft.applies_to_charge_codes.length === 0 ? "—" : draft.applies_to_charge_codes.join(", ");
  }
  return labelOf(lists.appliesTo, draft.applies_to) || "—";
}

/** The big figure: `15%`, `$25.00`, *Whole charge*, or a dash. */
export function bigFigure(draft: DiscountFormDraft, t: Translator): string {
  const box = valueBoxFor(effectiveType(draft));
  if (box === "whole") return t("rating.discountForm.summary.whole");
  if (box === "percent" || box === "money") return valueFigure(draft) ?? "—";
  return "—";
}

/** The line under it: *off subtotal before taxes* for a percentage, the type's
 *  name for the rest (images 05, 07–10). A service or charge codes the draft
 *  names are the utility's own words, so they go into `summary.off`. */
export function figureUnit(draft: DiscountFormDraft, lists: DiscountFormLists, t: Translator): string {
  const type = effectiveType(draft);
  if (valueBoxFor(type) === "percent") {
    const names =
      draft.applies_to === SCOPE_ONE_SERVICE ||
      draft.applies_to === SCOPE_SPECIFIC_SERVICES ||
      draft.applies_to === SCOPE_NAMED_CODES;
    const phrase = names ? null : offScopePhrase(draft.applies_to, t);
    return phrase ?? t("rating.discountForm.summary.off", { scope: scopeWords(draft, lists) });
  }
  return labelOf(lists.types, type) || "—";
}

/** `−$9.00`, `$0.00` when it takes nothing, `—` when the example cannot say. */
export function reductionText(reduction: string | null): string {
  if (reduction === null) return "—";
  return reduction === "0.00" ? "$0.00" : `−$${reduction}`;
}

export function DiscountSummaryPanel(props: { draft: DiscountFormDraft; lists: DiscountFormLists; t: Translator }) {
  const { draft, lists, t } = props;
  const limits = limitsSetCount(draft);
  const facts: [string, string, string][] = [
    ["label", t("rating.discountForm.summary.label"), draft.name.trim() || "—"],
    ["code", t("rating.discountForm.summary.code"), draft.code.trim().toUpperCase() || "—"],
    ["who", t("rating.discountForm.summary.who"), labelOf(lists.eligibility, draft.eligibility) || "—"],
    ["enrollment", t("rating.discountForm.field.enrollment"), labelOf(lists.enrollmentModes, draft.enrolment_mode) || "—"],
    [
      "limits",
      t("rating.discountForm.section.limits"),
      limits === 0 ? t("rating.discountForm.summary.none") : t("rating.discountForm.limits.set", { count: limits }),
    ],
    [
      "starts",
      t("rating.discountForm.field.starts"),
      draft.effective_from === "" ? "—" : formatDate(draft.effective_from, lists.timeZone, lists.dateFormat),
    ],
  ];
  return (
    <Panel as="aside" aria-label={t("rating.discountForm.summary.kicker")} data-discount-summary="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t("rating.discountForm.summary.kicker")}
      </p>
      <p className="m-0 mt-3 font-heading text-metric-lg font-semibold" data-discount-summary-figure="">
        {bigFigure(draft, t)}
      </p>
      <p className="m-0 mt-2 text-lead text-neutral-700">{figureUnit(draft, lists, t)}</p>
      <dl className="m-0 mt-4 flex flex-col gap-2 border-t border-divider pt-4">
        {facts.map(([id, label, value]) => (
          <div key={id} className={ROW} data-discount-summary-fact={id}>
            <dt className="text-neutral-700">{label}</dt>
            <dd className="m-0 text-right font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      <div className={`${ROW} mt-4 border-t border-divider pt-4`}>
        <span className="text-neutral-700">{t("rating.discountForm.summary.onBill", { bill: EXAMPLE_BILL })}</span>
        <span className="font-semibold tabular-nums" data-discount-summary-effect="">
          {reductionText(exampleReduction(draft))}
        </span>
      </div>
    </Panel>
  );
}
