// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — step 3 *Review*, built from image 17
//           of `05-prototype/discounts-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9289 D9 (Review lists EVERY value with an Edit link to its
//           step, and the discount on a $60.00 bill) · D10 (one line —
//           *Saves as a draft.* — where there was a paragraph)
// ───────────────────────────────────────────────────────
//
// The rows are DATA (`discountReviewRows`) so round 3's edit variations show
// the same rows with a before → after column (images 29, 33, 36).
import type { ReactNode } from "react";

import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { InlineLink, PlainTable } from "@/components/Surfaces";

import {
  EXAMPLE_BILL,
  exampleAfter,
  exampleReduction,
  isProofCondition,
  stepOfField,
  twoPlaces,
  valueFigure,
} from "./discountFormModel";
import type { DiscountFormDraft, DiscountFormStepSpec } from "./discountFormModel";
import { SECTION_HEADING, labelOf } from "./discountFormShared";
import type { DiscountFormLists, Translator } from "./discountFormShared";
import { bigFigure, reductionText, scopeWords } from "./DiscountSummaryPanel";

export interface DiscountReviewRow {
  id: string;
  label: string;
  value: ReactNode;
  /** The field whose step the Edit link opens. */
  field: keyof DiscountFormDraft;
  strong?: boolean;
}

function money(raw: string): string {
  return raw.trim() === "" ? "—" : `$${twoPlaces(raw)}`;
}

export function discountReviewRows(draft: DiscountFormDraft, lists: DiscountFormLists, t: Translator): DiscountReviewRow[] {
  const yesNo = (on: boolean) => t(on ? "rating.discountForm.yes" : "rating.discountForm.no");
  const day = (value: string) => formatDate(value, lists.timeZone, lists.dateFormat);
  const count = (raw: string, unitKey: string) =>
    raw.trim() === "" ? "—" : `${raw.trim()} ${t(unitKey)}`;
  const value = valueFigure(draft) ?? bigFigure(draft, t);
  const applies = labelOf(lists.appliesTo, draft.applies_to) || "—";
  const scope = scopeWords(draft, lists);
  const rows: DiscountReviewRow[] = [
    { id: "code", label: t("rating.discountForm.field.code"), value: draft.code.trim().toUpperCase() || "—", field: "code" },
    { id: "label", label: t("rating.discountForm.field.label"), value: draft.name.trim() || "—", field: "name" },
    { id: "owner", label: t("rating.discountForm.field.owner"), value: labelOf(lists.programOwners, draft.program_owner) || "—", field: "program_owner" },
    { id: "funding", label: t("rating.discountForm.field.funding"), value: draft.funding_source.trim() || "—", field: "funding_source" },
    { id: "assistance", label: t("rating.discountForm.field.assistance"), value: yesNo(draft.report_in_assistance_filing), field: "report_in_assistance_filing" },
    { id: "type", label: t("rating.discountForm.field.type"), value: labelOf(lists.types, draft.discount_type) || "—", field: "discount_type" },
    { id: "value", label: t("rating.discountForm.review.value"), value, field: "value", strong: true },
    { id: "currency", label: t("rating.discountForm.field.currency"), value: lists.currency ?? "—", field: "value" },
    {
      id: "applies",
      label: t("rating.discountForm.field.appliesTo"),
      value: scope === applies || scope === "—" ? applies : `${applies} · ${scope}`,
      field: "applies_to",
    },
    {
      id: "caps",
      label: t("rating.discountForm.review.caps"),
      value: [draft.cap_per_bill, draft.cap_per_year, draft.cap_lifetime].map(money).join(" · "),
      field: "cap_per_bill",
    },
    { id: "floor", label: t("rating.discountForm.field.floor"), value: money(draft.bill_floor_amount), field: "bill_floor_amount" },
    { id: "stacking", label: t("rating.discountForm.field.stacking"), value: draft.stacking_precedence.trim() || "—", field: "stacking_precedence" },
    { id: "stacks", label: t("rating.discountForm.review.stacks"), value: yesNo(draft.stacks_with_others), field: "stacks_with_others" },
    { id: "exclusivity", label: t("rating.discountForm.field.exclusivity"), value: labelOf(lists.exclusivityGroups, draft.exclusivity_group) || "—", field: "exclusivity_group" },
    { id: "who", label: t("rating.discountForm.field.who"), value: labelOf(lists.eligibility, draft.eligibility) || "—", field: "eligibility" },
    { id: "enrollment", label: t("rating.discountForm.field.enrollment"), value: labelOf(lists.enrollmentModes, draft.enrolment_mode) || "—", field: "enrolment_mode" },
  ];
  if (isProofCondition(draft, lists.eligibility)) {
    rows.push({
      id: "proof",
      label: t("rating.discountForm.review.proofBefore"),
      value: yesNo(draft.proof_before_first_reduction),
      field: "proof_before_first_reduction",
    });
  }
  rows.push(
    { id: "verification", label: t("rating.discountForm.field.verification"), value: labelOf(lists.verification, draft.verification_method) || "—", field: "verification_method" },
    { id: "recertify", label: t("rating.discountForm.field.recertify"), value: count(draft.recertification_months, "rating.discountForm.unit.months"), field: "recertification_months" },
    {
      id: "notice",
      label: t("rating.discountForm.review.noticeGrace"),
      value: `${count(draft.recertification_notice_days, "rating.discountForm.unit.days")} · ${count(draft.recertification_grace_days, "rating.discountForm.unit.days")}`,
      field: "recertification_notice_days",
    },
    { id: "lapse", label: t("rating.discountForm.field.lapse"), value: labelOf(lists.lapse, draft.lapse_behaviour) || "—", field: "lapse_behaviour" },
    { id: "starts", label: t("rating.discountForm.field.starts"), value: draft.effective_from === "" ? "—" : day(draft.effective_from), field: "effective_from" },
    { id: "ends", label: t("rating.discountForm.field.ends"), value: draft.effective_to === "" ? t("rating.discountForm.noEnd") : day(draft.effective_to), field: "effective_to" },
    {
      id: "budget",
      label: t("rating.discountForm.review.budget"),
      value: `${draft.budget_cap.trim() === "" ? t("rating.discountForm.noCeiling") : money(draft.budget_cap)} · ${labelOf(lists.budgetPeriods, draft.budget_period) || "—"}`,
      field: "budget_cap",
    },
    { id: "budgetOut", label: t("rating.discountForm.field.budgetOut"), value: labelOf(lists.budgetOut, draft.exhaustion_behaviour) || "—", field: "exhaustion_behaviour" },
  );
  return rows;
}

export function ReviewStep(props: {
  draft: DiscountFormDraft;
  lists: DiscountFormLists;
  steps: readonly DiscountFormStepSpec[];
  onEdit: (step: number) => void;
  t: Translator;
}) {
  const { draft, lists, t } = props;
  const rows = discountReviewRows(draft, lists, t);
  const reduction = exampleReduction(draft);
  const after = exampleAfter(reduction);
  return (
    <div className="flex flex-col gap-5" data-discount-step="review">
      <Panel as="section" aria-labelledby="discount-sec-check">
        <h2 id="discount-sec-check" className={SECTION_HEADING}>
          {t("rating.discountForm.section.check")}
        </h2>
        <div className="border border-divider">
          <PlainTable>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} data-review-row={row.id}>
                  <th scope="row" className="w-44 bg-neutral-100 font-normal text-neutral-700">
                    {row.label}
                  </th>
                  <td>
                    <span className={row.strong === true ? "font-semibold" : undefined}>{row.value}</span>{" "}
                    <InlineLink
                      className="ml-2 text-sm"
                      aria-label={t("rating.discountForm.editRow", { field: row.label })}
                      onClick={() => props.onEdit(stepOfField(row.field, props.steps))}
                    >
                      {t("rating.discountForm.edit")}
                    </InlineLink>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="discount-sec-example">
        <h2 id="discount-sec-example" className={SECTION_HEADING}>
          {t("rating.discountForm.section.example")}
        </h2>
        <div
          className="border border-divider [&_td:not(:first-child)]:text-right"
          data-discount-example=""
        >
          <PlainTable>
            <tbody>
              <tr>
                <td>{t("rating.discountForm.example.charges")}</td>
                <td className="tabular-nums">${EXAMPLE_BILL}</td>
              </tr>
              <tr>
                <td>{draft.name.trim() || t("rating.discountForm.thisDiscount")}</td>
                <td className="tabular-nums" data-discount-example-reduction="">
                  {reductionText(reduction)}
                </td>
              </tr>
              <tr className="bg-neutral-100 font-semibold">
                <td>{t("rating.discountForm.example.beforeTaxes")}</td>
                <td className="tabular-nums">{after === null ? "—" : `$${after}`}</td>
              </tr>
            </tbody>
          </PlainTable>
        </div>
        <p className="m-0 mt-4 bg-info-100 px-3 py-3 text-base text-info-700" data-discount-saves-draft="">
          {t("rating.discountForm.savesDraft")}
        </p>
      </Panel>
    </div>
  );
}
