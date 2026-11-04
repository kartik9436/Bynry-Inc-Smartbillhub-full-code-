// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — step 4 *Review & save*, built from images
//           15–16 of `05-prototype/taxes-fees-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9277 P17 (the rate reads back as a percent, never the
//           fraction) · P18 (dates in the tenant's format, and an example bill)
//           · P9 (over 20 % warns on Review with the effect on a $60.00 bill)
// ───────────────────────────────────────────────────────
//
// Every value the form collected, one row each, with an Edit link that opens
// the step that holds it. The rows are DATA (`reviewRows`) so the round-3 edit
// variations can show the same rows with a before → after column.
import type { ReactNode } from "react";

import { formatDate } from "@/components/DateCell";
import { checkDropdownSummary } from "@/components/CheckDropdown";
import { Panel } from "@/components/Panel";
import { InlineLink, PlainTable } from "@/components/Surfaces";

import {
  BASIS_PERCENT,
  EXAMPLE_BILL,
  effectiveBasis,
  exampleBill,
  percentIsHigh,
  percentToFraction,
  fractionToPercent,
  stepOfField,
} from "./taxFormModel";
import type { TaxFormDraft, TaxFormStepSpec } from "./taxFormModel";
import { MONEY_COLUMNS, SECTION_HEADING, labelOf, rateFigure, rateUnitKey } from "./taxFormShared";
import type { TaxFormLists, Translator } from "./taxFormShared";

export interface ReviewRow {
  id: string;
  label: string;
  value: ReactNode;
  /** The field whose step the Edit link opens. */
  field: keyof TaxFormDraft;
  strong?: boolean;
}

function percentText(typed: string): string | null {
  const fraction = percentToFraction(typed);
  return fraction === null ? null : `${fractionToPercent(fraction)}%`;
}

export function reviewRows(draft: TaxFormDraft, lists: TaxFormLists, t: Translator): ReviewRow[] {
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  const percent = effectiveBasis(draft) === BASIS_PERCENT;
  const taxed = [
    draft.base_includes_usage ? t("rating.taxForm.taxed.usage") : null,
    draft.base_includes_base ? t("rating.taxForm.taxed.base") : null,
  ].filter((x): x is string => x !== null);
  const rate = rateFigure(draft);
  const boundary = labelOf(lists.boundaries, draft.boundary);
  const place = lists.placeBoundaries.includes(draft.boundary) && draft.place_name.trim() !== "" ? ` · ${draft.place_name.trim()}` : "";
  const join = (...parts: string[]) => {
    const kept = parts.filter((part) => part !== "");
    return kept.length === 0 ? "—" : kept.join(" · ");
  };
  const allowance = percentText(draft.allowance_percent);
  const interest = percentText(draft.interest_percent);
  const rows: ReviewRow[] = [
    { id: "name", label: t("rating.taxForm.field.name"), value: draft.name.trim() || "—", field: "name" },
    { id: "authority", label: t("rating.taxForm.field.authority"), value: labelOf(lists.authorities, draft.jurisdiction) || "—", field: "jurisdiction" },
    { id: "boundary", label: t("rating.taxForm.field.boundary"), value: `${boundary || "—"}${place}`, field: "boundary" },
    { id: "services", label: t("rating.taxForm.field.services"), value: checkDropdownSummary(lists.services, draft.services, t("rating.taxForm.allServices")), field: "services" },
    { id: "classes", label: t("rating.taxForm.field.classes"), value: checkDropdownSummary(lists.classes, draft.customer_classes, t("rating.taxForm.allClasses")), field: "customer_classes" },
    { id: "rate", label: t("rating.taxForm.field.rate"), value: rate === null ? "—" : `${rate} ${t(rateUnitKey(draft))}`, field: "rate_percent", strong: true },
  ];
  if (percent) {
    rows.push({ id: "taxed", label: t("rating.taxForm.field.taxed"), value: taxed.join(", ") || "—", field: "base_includes_usage" });
  }
  rows.push(
    { id: "from", label: t("rating.taxForm.field.from"), value: day(draft.effective_from), field: "effective_from" },
    { id: "to", label: t("rating.taxForm.field.to"), value: draft.effective_to === "" ? t("rating.taxForm.noEnd") : day(draft.effective_to), field: "effective_to" },
    { id: "discounts", label: t("rating.taxForm.field.discounts"), value: labelOf(lists.discounts, draft.discount_treatment) || "—", field: "discount_treatment" },
    { id: "rounding", label: t("rating.taxForm.field.rounding"), value: labelOf(lists.rounding, draft.rounding_rule) || "—", field: "rounding_rule" },
    { id: "code", label: t("rating.taxForm.review.codeLabel"), value: join(draft.code.trim(), draft.bill_label.trim() || draft.name.trim()), field: "code" },
    { id: "liability", label: t("rating.taxForm.field.liability"), value: labelOf(lists.liabilityAccounts, draft.liability_gl_account_id) || "—", field: "liability_gl_account_id" },
    { id: "filed", label: t("rating.taxForm.review.filedDue"), value: join(labelOf(lists.filingFrequencies, draft.filing_frequency), labelOf(lists.dueRules, draft.due_date_rule)), field: "filing_frequency" },
    { id: "account", label: t("rating.taxForm.field.authorityAccount"), value: labelOf(lists.authorityAccounts, draft.authority_account_id) || "—", field: "authority_account_id" },
    {
      id: "allowance",
      label: t("rating.taxForm.review.allowanceInterest"),
      value: join(allowance ?? "", interest === null ? "" : `${interest} ${t("rating.taxForm.perMonthShort")}`),
      field: "allowance_percent",
    },
    { id: "reminder", label: t("rating.taxForm.field.reminder"), value: draft.filing_reminder_recipient.trim() || "—", field: "filing_reminder_recipient" },
  );
  return rows;
}

/** The over-20 % warning, with what it costs on the example bill. Shown on
 *  step 2 beside the box and here above the table (PO, README point 2). */
export function HighRateBanner(props: { draft: TaxFormDraft; t: Translator }) {
  const { draft, t } = props;
  if (effectiveBasis(draft) !== BASIS_PERCENT || !percentIsHigh(draft.rate_percent)) {
    return null;
  }
  const effect = exampleBill(draft).effect;
  return (
    <p className="m-0 bg-warning-100 px-3 py-3 text-base text-warning-700" role="status" data-tax-high-rate="">
      <strong className="font-semibold">{t("rating.taxForm.rateHigh", { rate: rateFigure(draft) })}</strong>{" "}
      {t("rating.taxForm.rateHighEffect", { bill: EXAMPLE_BILL, amount: effect ?? "0.00" })}
    </p>
  );
}

export function ReviewStep(props: {
  draft: TaxFormDraft;
  lists: TaxFormLists;
  steps: readonly TaxFormStepSpec[];
  onEdit: (step: number) => void;
  t: Translator;
}) {
  const { draft, lists, t } = props;
  const rows = reviewRows(draft, lists, t);
  const bill = exampleBill(draft);
  const reach = lists.reach;
  return (
    <div className="flex flex-col gap-5" data-tax-step="review">
      <HighRateBanner draft={draft} t={t} />
      <Panel as="section" aria-labelledby="tax-sec-check">
        <h2 id="tax-sec-check" className={SECTION_HEADING}>
          {t("rating.taxForm.section.check")}
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
                      aria-label={t("rating.taxForm.editRow", { field: row.label })}
                      onClick={() => props.onEdit(stepOfField(row.field, props.steps))}
                    >
                      {t("rating.taxForm.edit")}
                    </InlineLink>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="tax-sec-example">
        <h2 id="tax-sec-example" className={SECTION_HEADING}>
          {t("rating.taxForm.section.example")}
        </h2>
        <div className="border border-divider" data-tax-example="review">
          <PlainTable className={MONEY_COLUMNS}>
            <tbody>
              <tr>
                <td>{t("rating.taxForm.taxed.usage")}</td>
                <td className="tabular-nums">${bill.usage}</td>
              </tr>
              <tr>
                <td>{t("rating.taxForm.taxed.base")}</td>
                <td className="tabular-nums">${bill.base}</td>
              </tr>
              <tr>
                <td>{t("rating.taxForm.example.taxed")}</td>
                <td className="tabular-nums">
                  ${draft.discount_treatment === "before" ? bill.taxedAfterDiscount : bill.taxedFull}
                </td>
              </tr>
              <tr className="bg-neutral-100 font-semibold">
                <td>{draft.name.trim() || t("rating.taxForm.thisTax")}</td>
                <td className="tabular-nums" data-tax-example-effect="">
                  {bill.effect === null ? "—" : `$${bill.effect}`}
                </td>
              </tr>
            </tbody>
          </PlainTable>
        </div>
        {reach !== null && (
          <p className="m-0 mt-4 bg-info-100 px-3 py-3 text-base text-info-700" data-tax-reach-note="">
            {t("rating.taxForm.review.reach", { count: reach.count, total: reach.total })}
            {draft.effective_from !== "" &&
              ` ${t("rating.taxForm.review.nobodyBefore", {
                date: formatDate(draft.effective_from, lists.timeZone, lists.dateFormat),
              })}`}
          </p>
        )}
      </Panel>
    </div>
  );
}
