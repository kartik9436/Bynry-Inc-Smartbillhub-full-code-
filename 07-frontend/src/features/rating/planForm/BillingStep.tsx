// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — step 4 *Billing*, built from images
//           17–19 of `05-prototype/plans-2026-10-03/images/` (B14 rule 42).
// Rules:    ruling 9 (*"we did not add dposites anywhere"* — Deposits is a new
//           table array, a deposit CHARGE CODE priced by customer class; §7.3:
//           by class only for now, `BR-RAT-020`) · ruling 2 (discounts' offered
//           from/until and their take-up, budget billing and minimum bill all
//           kept) · ruling 3 · ruling 6 · ruling 8 · DEF-RAT-9287 (the minimum
//           bill is a $ box of two places, never `10.000000`)
// ───────────────────────────────────────────────────────
import { AffixField } from "@/components/AffixField";
import { CheckboxField, DatePickerField, useFieldError } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import type { PlanGl } from "@/api/planFormEndpoints";

import { RefVersion, classOrSizeWord, moneyShown, pricedByText, pricedRowsInOrder } from "../planSections/PlanSections";
import { allAdded, depositOf, discountOf, newDiscountRow, newPickRow, stillOffered } from "./planFormModel";
import type { PlanDiscountRow, PlanPickRow } from "./planFormModel";
import { PAIR, SECTION_HEADING, isLocked } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";

function glText(gl: PlanGl | null): string {
  return gl === null ? "—" : gl.name === "" ? gl.code : `${gl.code} · ${gl.name}`;
}

export function BillingStep(props: PlanStepProps) {
  return (
    <div className="flex flex-col gap-5" data-plan-step="billing">
      <DepositsTable {...props} />
      <DiscountsTable {...props} />
      <BillingTermsSection {...props} />
    </div>
  );
}

export function DepositsTable(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const options = lists.options;
  const error = useFieldError("plan-deposits");
  const offered = options.deposit_codes.map((row) => ({ value: row.ref.id, label: `${row.ref.code} · ${row.ref.name}` }));
  const picked = draft.deposits.map((row) => row.value);

  const columns: TableArrayColumn<PlanPickRow>[] = [
    {
      key: "deposit",
      label: t("rating.planSections.col.deposit"),
      cell: (row, index) => {
        const chosen = depositOf(options, row.value);
        return (
          <span className="flex flex-col">
            <CellSelect
              name="deposit"
              label={t("rating.planSections.col.deposit")}
              value={row.value}
              placeholder={t("rating.planForm.placeholder.deposit")}
              options={stillOffered(offered, picked, row.value)}
              onChange={(value) =>
                props.onChange({ deposits: draft.deposits.map((r, i) => (i === index ? { ...r, value } : r)) })
              }
            />
            {chosen !== undefined && (
              <RefVersion item={chosen.ref} t={t} dateFormat={lists.dateFormat} timeZone={lists.timeZone} />
            )}
          </span>
        );
      },
    },
    {
      key: "pricedBy",
      label: t("rating.planSections.col.pricedBy"),
      cell: (row) => {
        const chosen = depositOf(options, row.value);
        return <CellStatic name="priced-by">{chosen === undefined ? "—" : pricedByText(chosen.priced_by, t)}</CellStatic>;
      },
    },
    {
      key: "amounts",
      label: t("rating.planForm.col.amounts"),
      cell: (row) => {
        const chosen = depositOf(options, row.value);
        if (chosen === undefined || chosen.rows.length === 0) return <CellStatic name="amounts">—</CellStatic>;
        return (
          <span className="flex flex-col" data-cell="amounts">
            {pricedRowsInOrder(chosen).map((line) => (
              <span key={line.class_or_size_label}>
                {classOrSizeWord(line, t)}{" "}
                <span className="font-semibold">{moneyShown(line.amount_display, lists.currency)}</span>
              </span>
            ))}
          </span>
        );
      },
    },
    {
      key: "gl",
      label: t("rating.planSections.col.gl"),
      cell: (row) => <CellStatic name="gl">{glText(depositOf(options, row.value)?.gl ?? null)}</CellStatic>,
    },
  ];

  return (
    <TableArray<PlanPickRow>
      title={t("rating.planForm.section.deposits")}
      fact={t("rating.planForm.fact.onPlan", { count: draft.deposits.filter((row) => row.value !== "").length })}
      collection="plan-deposits"
      columns={columns}
      rows={draft.deposits}
      rowKey={(row) => row.key}
      emptyText={t("rating.planForm.empty.deposits")}
      note={error}
      onChange={(deposits) => props.onChange({ deposits })}
      removeLabel={t("rating.planForm.remove")}
      actions={
        isLocked(props, "deposits")
          ? []
          : [
              {
                key: "add-deposit",
                label: t("rating.planForm.add.deposit"),
                onClick: () => props.onChange({ deposits: [...draft.deposits, newPickRow("deposit")] }),
                blockedReason: allAdded(options.deposit_codes.length, draft.deposits.length)
                  ? t("rating.planForm.allAdded")
                  : undefined,
                showReason: true,
              },
            ]
      }
    />
  );
}

export function DiscountsTable(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const options = lists.options;
  const error = useFieldError("plan-discounts");
  const offered = options.discounts.map((row) => ({ value: row.ref.id, label: `${row.ref.code} · ${row.ref.name}` }));
  const picked = draft.discounts.map((row) => row.discount);

  function setRow(index: number, patch: Partial<PlanDiscountRow>): void {
    props.onChange({ discounts: draft.discounts.map((row, i) => (i === index ? { ...row, ...patch } : row)) });
  }

  const columns: TableArrayColumn<PlanDiscountRow>[] = [
    {
      key: "discount",
      label: t("rating.planSections.col.discount"),
      cell: (row, index) => {
        const chosen = discountOf(options, row.discount);
        return (
          <span className="flex flex-col">
            <CellSelect
              name="discount"
              label={t("rating.planSections.col.discount")}
              value={row.discount}
              placeholder={t("rating.planForm.placeholder.discount")}
              options={stillOffered(offered, picked, row.discount)}
              onChange={(discount) => setRow(index, { discount })}
            />
            {chosen !== undefined && (
              <RefVersion item={chosen.ref} t={t} dateFormat={lists.dateFormat} timeZone={lists.timeZone} />
            )}
          </span>
        );
      },
    },
    {
      key: "value",
      label: t("rating.planForm.col.value"),
      numeric: true,
      cell: (row) => <CellStatic name="value">{discountOf(options, row.discount)?.value_display ?? "—"}</CellStatic>,
    },
    {
      key: "gl",
      label: t("rating.planSections.col.gl"),
      cell: (row) => <CellStatic name="gl">{glText(discountOf(options, row.discount)?.gl ?? null)}</CellStatic>,
    },
    {
      key: "enrolled",
      label: t("rating.planSections.col.enrolled"),
      numeric: true,
      cell: (row) => {
        const enrolled = discountOf(options, row.discount)?.enrolled;
        return <CellStatic name="enrolled">{enrolled === null || enrolled === undefined ? "—" : String(enrolled)}</CellStatic>;
      },
    },
    {
      key: "from",
      label: t("rating.planSections.col.offeredFrom"),
      cell: (row, index) => (
        <DatePickerField
          id={`plan-discount-from-${index}`}
          label={t("rating.planSections.col.offeredFrom")}
          labelHidden
          value={row.offered_from}
          dateFormat={lists.dateFormat}
          onChange={(offered_from) => setRow(index, { offered_from })}
        />
      ),
    },
    {
      key: "until",
      label: t("rating.planSections.col.offeredUntil"),
      cell: (row, index) => (
        <DatePickerField
          id={`plan-discount-until-${index}`}
          label={t("rating.planSections.col.offeredUntil")}
          labelHidden
          value={row.offered_until}
          dateFormat={lists.dateFormat}
          onChange={(offered_until) => setRow(index, { offered_until })}
        />
      ),
    },
  ];

  return (
    <TableArray<PlanDiscountRow>
      title={t("rating.planForm.section.discounts")}
      fact={t("rating.planForm.fact.onPlan", { count: draft.discounts.filter((row) => row.discount !== "").length })}
      collection="plan-discounts"
      columns={columns}
      rows={draft.discounts}
      rowKey={(row) => row.key}
      emptyText={t("rating.planForm.empty.discounts")}
      note={error}
      onChange={(discounts) => props.onChange({ discounts })}
      removeLabel={t("rating.planForm.remove")}
      actions={
        isLocked(props, "discounts")
          ? []
          : [
              {
                key: "add-discount",
                label: t("rating.planForm.add.discount"),
                onClick: () => props.onChange({ discounts: [...draft.discounts, newDiscountRow()] }),
                blockedReason: allAdded(options.discounts.length, draft.discounts.length)
                  ? t("rating.planForm.allAdded")
                  : undefined,
                showReason: true,
              },
            ]
      }
    />
  );
}

export function BillingTermsSection(props: PlanStepProps) {
  const { draft, t } = props;
  return (
    <Panel as="section" aria-labelledby="plan-sec-terms">
      <h2 id="plan-sec-terms" className={SECTION_HEADING}>
        {t("rating.planForm.section.terms")}
      </h2>
      <div className={PAIR}>
        <div className="flex flex-col gap-2">
          <span className="font-heading text-base font-semibold">{t("rating.planForm.field.budget")}</span>
          <CheckboxField
            id="plan-budget"
            label={t("rating.planForm.field.offerBudget")}
            checked={draft.budget_billing}
            disabled={isLocked(props, "budget_billing")}
            onChange={(budget_billing) => props.onChange({ budget_billing })}
          />
        </div>
        <AffixField
          id="plan-minimum"
          label={t("rating.planForm.field.minimum")}
          value={draft.minimum_bill}
          affix="$"
          side="start"
          help={t("rating.planForm.help.minimum")}
          disabled={isLocked(props, "minimum_bill")}
          onChange={(minimum_bill) => props.onChange({ minimum_bill })}
        />
      </div>
    </Panel>
  );
}
