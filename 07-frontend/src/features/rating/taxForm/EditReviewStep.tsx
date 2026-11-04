// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — the edit form's *Review & save*, built from
//           images 26, 30 and 33 of `05-prototype/taxes-fees-2026-10-03/images/`
//           (B14 rule 42).
// Defects:  DEF-RAT-9273 P49 (saving gives a picture of the rows: before →
//           after, the $60.00 bill before → after, and the versions saved) ·
//           P50 (issued bills keep the old rate, said where it is decided)
// ───────────────────────────────────────────────────────
//
// Three sections, as drawn:
//   *What changes*     every field that moved, before → after, with its Edit link
//                      (and the reason, on *Fix a mistake*);
//   *On a $60.00 bill* this tax before → after — only where the rate can move
//                      (image 26, *Name and filing*, draws no bill);
//   *How it is saved*  the version rows as they will stand, and one note.
//
// The rows reuse the New form's `reviewRows`, so a field reads the same words
// on both forms; a row is listed here only when its words changed.
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { InlineLink, PlainTable } from "@/components/Surfaces";

import { reviewRows } from "./ReviewStep";
import { dayBefore } from "./taxEditModel";
import type { TaxEditMode } from "./taxEditModel";
import { EXAMPLE_BILL, exampleBill, stepOfField } from "./taxFormModel";
import type { TaxFormDraft, TaxFormStepSpec } from "./taxFormModel";
import { MONEY_COLUMNS, SECTION_HEADING, rateFigure } from "./taxFormShared";
import type { TaxFormLists, Translator } from "./taxFormShared";

export interface EditReviewProps {
  mode: TaxEditMode;
  original: TaxFormDraft;
  draft: TaxFormDraft;
  /** The version in force today — `v1` on a tax nobody has re-rated. */
  version: number;
  reason: string;
  lists: TaxFormLists;
  steps: readonly TaxFormStepSpec[];
  onEdit: (step: number) => void;
  t: Translator;
}

/** The rows whose words moved — the same rows the New form reviews. The rate
 *  reads as its figure alone (*150%* → *6.25%*), as drawn. */
export function changedReviewRows(props: Pick<EditReviewProps, "original" | "draft" | "lists" | "t">) {
  const before = reviewRows(props.original, props.lists, props.t);
  const after = reviewRows(props.draft, props.lists, props.t);
  return after
    .map((row) => {
      const was = before.find((other) => other.id === row.id);
      const figure = (draft: TaxFormDraft) => rateFigure(draft) ?? "—";
      return row.id === "rate"
        ? { ...row, before: figure(props.original), after: figure(props.draft) }
        : { ...row, before: String(was?.value ?? "—"), after: String(row.value) };
    })
    .filter((row) => row.before !== row.after);
}

export function EditReviewStep(props: EditReviewProps) {
  const { mode, original, draft, lists, t } = props;
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  const span = (from: string, to: string) => `${day(from)} – ${to === "" ? t("rating.taxForm.noEnd") : day(to)}`;
  const rows = changedReviewRows(props);
  const oldRate = rateFigure(original) ?? "—";
  const newRate = rateFigure(draft) ?? "—";
  const before = exampleBill(original).effect;
  const after = exampleBill(draft).effect;
  const v = props.version;

  const versions =
    mode === "info"
      ? [{ id: "this", label: t("rating.taxEdit.version.this", { v }), rate: oldRate, dates: span(original.effective_from, original.effective_to), after: t("rating.taxEdit.after.inPlace"), strong: false }]
      : mode === "change"
        ? [
            { id: "today", label: t("rating.taxEdit.version.today", { v }), rate: oldRate, dates: span(original.effective_from, dayBefore(draft.effective_from)), after: t("rating.taxEdit.after.endDate"), strong: false },
            { id: "next", label: t("rating.taxEdit.version.new", { v: v + 1 }), rate: newRate, dates: span(draft.effective_from, draft.effective_to), after: t("rating.taxEdit.after.newVersion"), strong: true },
          ]
        : [
            { id: "today", label: t("rating.taxEdit.version.today", { v }), rate: oldRate, dates: span(original.effective_from, original.effective_to), after: t("rating.taxEdit.after.superseded"), strong: false },
            { id: "next", label: t("rating.taxEdit.version.correction", { v: v + 1 }), rate: newRate, dates: span(original.effective_from, original.effective_to), after: t("rating.taxEdit.after.replaces", { v }), strong: true },
          ];

  return (
    <div className="flex flex-col gap-5" data-tax-step="edit-review">
      <Panel as="section" aria-labelledby="tax-sec-changes">
        <h2 id="tax-sec-changes" className={SECTION_HEADING}>
          {t("rating.taxEdit.section.changes")}
        </h2>
        <div className="border border-divider">
          <PlainTable>
            <thead>
              <tr className="bg-neutral-100">
                <th scope="col">{t("rating.taxEdit.col.field")}</th>
                <th scope="col">{t("rating.taxEdit.col.before")}</th>
                <th scope="col">{t("rating.taxEdit.col.after")}</th>
                <th scope="col">
                  <span className="sr-only">{t("rating.taxForm.edit")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr data-tax-change="none">
                  <td colSpan={4} className="text-neutral-700">
                    {t("rating.taxEdit.noChanges")}
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} data-tax-change={row.id}>
                    <td>{row.label}</td>
                    <td className="text-neutral-700">{row.before}</td>
                    <td className="font-semibold">{row.after}</td>
                    <td>
                      <InlineLink
                        aria-label={t("rating.taxForm.editRow", { field: row.label })}
                        onClick={() => props.onEdit(stepOfField(row.field, props.steps))}
                      >
                        {t("rating.taxForm.edit")}
                      </InlineLink>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </PlainTable>
        </div>
        {mode === "correct" && (
          <div className="mt-5" data-tax-review-reason="">
            <p className="field-label">{t("rating.taxEdit.section.reason")}</p>
            <p className="m-0 mt-3 font-semibold">{props.reason.trim() || "—"}</p>
          </div>
        )}
      </Panel>

      {mode !== "info" && (
        <Panel as="section" aria-labelledby="tax-sec-bill">
          <h2 id="tax-sec-bill" className={SECTION_HEADING}>
            {t("rating.taxEdit.section.bill", { bill: EXAMPLE_BILL })}
          </h2>
          <div className="border border-divider" data-tax-example="edit">
            <PlainTable className={MONEY_COLUMNS}>
              <thead>
                <tr className="bg-neutral-100">
                  <th scope="col">
                    <span className="sr-only">{t("rating.taxForm.thisTax")}</span>
                  </th>
                  <th scope="col">{t("rating.taxEdit.col.before")}</th>
                  <th scope="col">{t("rating.taxEdit.col.after")}</th>
                </tr>
              </thead>
              <tbody>
                <tr className="bg-neutral-100 font-semibold">
                  <td>{draft.name.trim() || t("rating.taxForm.thisTax")}</td>
                  <td className="tabular-nums" data-tax-bill-before="">{before === null ? "—" : `$${before}`}</td>
                  <td className="tabular-nums" data-tax-bill-after="">{after === null ? "—" : `$${after}`}</td>
                </tr>
              </tbody>
            </PlainTable>
          </div>
        </Panel>
      )}

      <Panel as="section" aria-labelledby="tax-sec-saved-as">
        <h2 id="tax-sec-saved-as" className={SECTION_HEADING}>
          {t("rating.taxEdit.section.saved")}
        </h2>
        <div className="border border-divider" data-tax-versions="">
          <PlainTable>
            <thead>
              <tr className="bg-neutral-100">
                <th scope="col">{t("rating.taxEdit.col.version")}</th>
                <th scope="col" className="text-right">{t("rating.taxForm.field.rate")}</th>
                <th scope="col">{t("rating.taxEdit.facts.dates")}</th>
                <th scope="col">{t("rating.taxEdit.col.afterSaving")}</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((row) => (
                <tr key={row.id} data-tax-version={row.id} className={row.strong ? "font-semibold" : undefined}>
                  <td>{row.label}</td>
                  <td className="text-right tabular-nums">{row.rate}</td>
                  <td className="tabular-nums">{row.dates}</td>
                  <td>{row.after}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
        {mode === "change" && draft.effective_from !== "" && (
          <p className="m-0 mt-4 bg-info-100 px-3 py-3 text-base text-info-700" data-tax-saved-note="change">
            {t("rating.taxEdit.note.billsBefore", { date: day(draft.effective_from), rate: oldRate })}
          </p>
        )}
        {mode === "correct" && (
          <p className="m-0 mt-4 bg-warning-100 px-3 py-3 text-base text-warning-700" role="status" data-tax-saved-note="correct">
            {t("rating.taxEdit.note.issuedKeep", { rate: oldRate })}
          </p>
        )}
      </Panel>
    </div>
  );
}
