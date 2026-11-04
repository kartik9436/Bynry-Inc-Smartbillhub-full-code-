// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — step 3 *Charges*, built from images
//           13–16 of `05-prototype/plans-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9328 (the late fee is a ROW here — visible, removable,
//           listed on Review — never a silent default) · DEF-RAT-9329 (one row
//           per tax, named)
// Rules:    ruling 3 (charge codes and taxes are table arrays) · ruling 6 · ruling
//           7 (no base section here: base codes reach the bill through the
//           schedule, BR-RAT-088, so `form-options` never offers one) · ruling 8
// ───────────────────────────────────────────────────────
import { useFieldError } from "@/components/FormModal";
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";

import { RefVersion, TaxNotCharged, graceLine, moneyShown, taxedWord, whenWord } from "../planSections/PlanSections";
import { allAdded, chargeOf, combinedTaxPercent, newPickRow, stillOffered, taxOf } from "./planFormModel";
import type { PlanPickRow } from "./planFormModel";
import { isLocked } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";
import type { PlanChargeSection, PlanGl } from "@/api/planFormEndpoints";
import { enumLabel } from "../ratingShared";
import type { Translator } from "../ratingShared";

export function ChargesStep(props: PlanStepProps) {
  return (
    <div className="flex flex-col gap-5" data-plan-step="charges">
      <ChargeCodesTable {...props} />
      <TaxesTable {...props} />
    </div>
  );
}

function glText(gl: PlanGl | null): string {
  return gl === null ? "—" : gl.name === "" ? gl.code : `${gl.code} · ${gl.name}`;
}

/** The Amount cell of a code row: *$75.00*, *by customer class*, *by size*. */
export function chargeAmountText(charge: PlanChargeSection, currency: string | null, t: Translator): string {
  if (charge.priced_by === "class") return t("rating.planForm.amount.byClass");
  if (charge.priced_by === "size") return t("rating.planForm.amount.bySize");
  const first = charge.rows[0];
  if (first === undefined) return "—";
  return first.percent_display ?? moneyShown(first.amount_display, currency);
}

export function ChargeCodesTable(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const options = lists.options;
  const error = useFieldError("plan-charges");
  const offered = options.charge_codes.map((row) => ({ value: row.ref.id, label: `${row.ref.code} · ${row.ref.name}` }));
  const picked = draft.charge_codes.map((row) => row.value);

  function setRows(charge_codes: PlanPickRow[]): void {
    props.onChange({ charge_codes, charge_codes_touched: true });
  }

  const columns: TableArrayColumn<PlanPickRow>[] = [
    {
      key: "code",
      label: t("rating.planForm.col.chargeCode"),
      cell: (row, index) => {
        const chosen = chargeOf(options, row.value);
        return (
          <span className="flex flex-col">
            <CellSelect
              name="charge-code"
              label={t("rating.planForm.col.chargeCode")}
              value={row.value}
              placeholder={t("rating.planForm.placeholder.chargeCode")}
              options={stillOffered(offered, picked, row.value)}
              onChange={(value) => setRows(draft.charge_codes.map((r, i) => (i === index ? { ...r, value } : r)))}
            />
            {chosen !== undefined && (
              <RefVersion item={chosen.ref} t={t} dateFormat={lists.dateFormat} timeZone={lists.timeZone} />
            )}
          </span>
        );
      },
    },
    {
      key: "amount",
      label: t("rating.planSections.col.amount"),
      numeric: true,
      cell: (row) => {
        const chosen = chargeOf(options, row.value);
        return <CellStatic name="amount">{chosen === undefined ? "—" : chargeAmountText(chosen, lists.currency, t)}</CellStatic>;
      },
    },
    {
      key: "gl",
      label: t("rating.planSections.col.gl"),
      cell: (row) => <CellStatic name="gl">{glText(chargeOf(options, row.value)?.gl ?? null)}</CellStatic>,
    },
    {
      key: "type",
      label: t("rating.planForm.col.type"),
      // DEF-RAT-9356 — the server serves the STORED type (`one_time`); it is
      // worded through the catalogue, and an unknown one shows as served.
      cell: (row) => (
        <CellStatic name="type">
          {enumLabel(t, "rating.charges.type", chargeOf(options, row.value)?.type_label ?? null)}
        </CellStatic>
      ),
    },
    {
      key: "when",
      label: t("rating.planSections.col.when"),
      // DEF-RAT-9502 — the server's English *When*, worded from the stored type.
      cell: (row) => {
        const chosen = chargeOf(options, row.value);
        // PO 2026-10-06 11 (a) — a late-fee code shows the grace it carries;
        // the plan sets none of its own.
        const grace = chosen === undefined ? null : graceLine(chosen, t);
        return (
          <CellStatic name="when">
            {chosen === undefined ? "—" : whenWord(chosen, t)}
            {grace !== null && <span className="block" data-grace="">{grace}</span>}
          </CellStatic>
        );
      },
    },
  ];

  const full = allAdded(options.charge_codes.length, draft.charge_codes.length);
  return (
    <TableArray<PlanPickRow>
      title={t("rating.planForm.section.charges")}
      fact={t("rating.planForm.fact.onPlan", { count: draft.charge_codes.filter((row) => row.value !== "").length })}
      collection="plan-charges"
      columns={columns}
      rows={draft.charge_codes}
      rowKey={(row) => row.key}
      emptyText={t("rating.planForm.empty.charges")}
      note={error}
      onChange={setRows}
      removeLabel={t("rating.planForm.remove")}
      actions={
        isLocked(props, "charge_codes")
          ? []
          : [
              {
                key: "add-charge",
                label: t("rating.planForm.add.charge"),
                onClick: () => setRows([...draft.charge_codes, newPickRow("charge")]),
                blockedReason: full ? t("rating.planForm.allAdded") : undefined,
                showReason: true,
              },
            ]
      }
      footerTrailing={
        <a
          className="font-semibold text-accent underline"
          href={lists.newChargeCodeHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("rating.planForm.link.defineCode")}
        </a>
      }
    />
  );
}

export function TaxesTable(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const options = lists.options;
  const error = useFieldError("plan-taxes");
  const offered = options.taxes.map((row) => ({ value: row.ref.id, label: row.ref.name || row.ref.code }));
  const picked = draft.taxes.map((row) => row.value);
  const combined = combinedTaxPercent(draft, options);

  const columns: TableArrayColumn<PlanPickRow>[] = [
    {
      key: "tax",
      label: t("rating.planSections.col.tax"),
      cell: (row, index) => {
        const chosen = taxOf(options, row.value);
        return (
          <span className="flex flex-col">
            <CellSelect
              name="tax"
              label={t("rating.planSections.col.tax")}
              value={row.value}
              placeholder={t("rating.planForm.placeholder.tax")}
              options={stillOffered(offered, picked, row.value)}
              onChange={(value) =>
                props.onChange({ taxes: draft.taxes.map((r, i) => (i === index ? { ...r, value } : r)) })
              }
            />
            {chosen !== undefined && (
              <RefVersion item={chosen.ref} t={t} dateFormat={lists.dateFormat} timeZone={lists.timeZone} />
            )}
            {chosen !== undefined && <TaxNotCharged row={chosen} t={t} />}
          </span>
        );
      },
    },
    {
      key: "rate",
      label: t("rating.planSections.col.rate"),
      numeric: true,
      cell: (row) => <CellStatic name="rate">{taxOf(options, row.value)?.rate_display ?? "—"}</CellStatic>,
    },
    {
      key: "gl",
      label: t("rating.planSections.col.gl"),
      cell: (row) => <CellStatic name="gl">{glText(taxOf(options, row.value)?.gl ?? null)}</CellStatic>,
    },
    {
      key: "taxed",
      label: t("rating.planSections.col.whatIsTaxed"),
      cell: (row) => {
        const chosen = taxOf(options, row.value);
        return <CellStatic name="taxed">{chosen === undefined ? "—" : taxedWord(chosen, t)}</CellStatic>;
      },
    },
  ];

  const full = allAdded(options.taxes.length, draft.taxes.length);
  return (
    <TableArray<PlanPickRow>
      title={t("rating.planForm.section.taxes")}
      fact={combined === null ? undefined : t("rating.planSections.taxes.combined", { rate: combined })}
      collection="plan-taxes"
      columns={columns}
      rows={draft.taxes}
      rowKey={(row) => row.key}
      emptyText={t("rating.planForm.empty.taxes")}
      note={error}
      onChange={(taxes) => props.onChange({ taxes })}
      removeLabel={t("rating.planForm.remove")}
      actions={
        isLocked(props, "taxes")
          ? []
          : [
              {
                key: "add-tax",
                label: t("rating.planForm.add.tax"),
                onClick: () => props.onChange({ taxes: [...draft.taxes, newPickRow("tax")] }),
                blockedReason: full ? t("rating.planForm.allAdded") : undefined,
                showReason: true,
              },
            ]
      }
      footerTrailing={
        combined === null ? undefined : (
          <span className="flex gap-6 text-base" data-plan-combined-total="">
            <span className="font-semibold text-neutral-700">{t("rating.planForm.combined")}</span>
            <span className="font-semibold tabular-nums">{combined}</span>
          </span>
        )
      }
    />
  );
}
