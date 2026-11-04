// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — the discount edit form's Review,
//           built from images 29, 33 and 36 of
//           `05-prototype/discounts-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9292 D38 (a fix with no before and after — now every field
//           that moved, before → after, the $60.00 bill before → after, and
//           the version rows as they will stand)
// ───────────────────────────────────────────────────────
//
// Three sections, as drawn:
//   *What changes*     every field that moved, before → after (and the reason,
//                      on *Fix a mistake*, image 36);
//   *On a $60.00 bill* this discount before → after — only where the value can
//                      move (image 29, *Name and details*, draws no bill);
//   *How it is saved*  the version rows as they will stand, and one note.
//
// The rows reuse the New form's `discountReviewRows`, so a field reads the
// same words on both forms; a row is listed here only when its words changed.
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";

import { bigFigure, reductionText } from "./DiscountSummaryPanel";
import { discountReviewRows } from "./ReviewStep";
import { dayBefore } from "./discountEditModel";
import type { DiscountEditMode } from "./discountEditModel";
import { EXAMPLE_BILL, exampleReduction, valueFigure } from "./discountFormModel";
import type { DiscountFormDraft } from "./discountFormModel";
import { SECTION_HEADING } from "./discountFormShared";
import type { DiscountFormLists, Translator } from "./discountFormShared";

export interface EditDiscountReviewProps {
  mode: DiscountEditMode;
  original: DiscountFormDraft;
  draft: DiscountFormDraft;
  /** The version in force today — `v1` on a discount nobody has re-valued. */
  version: number;
  reason: string;
  lists: DiscountFormLists;
  t: Translator;
}

/** Rows a *New value* never lists under *What changes*: the start and end are
 *  the NEW version's window, which *How it is saved* states (image 33). */
const WINDOW_ROWS: ReadonlySet<string> = new Set(["starts", "ends"]);

/** The rows whose words moved — the same rows the New form reviews. */
export function changedDiscountRows(
  props: Pick<EditDiscountReviewProps, "mode" | "original" | "draft" | "lists" | "t">,
): { id: string; label: string; before: string; after: string }[] {
  const before = discountReviewRows(props.original, props.lists, props.t);
  const after = discountReviewRows(props.draft, props.lists, props.t);
  return after
    .filter((row) => !(props.mode === "change" && WINDOW_ROWS.has(row.id)))
    .map((row) => {
      const was = before.find((other) => other.id === row.id);
      return { id: row.id, label: row.label, before: String(was?.value ?? "—"), after: String(row.value) };
    })
    .filter((row) => row.before !== row.after);
}

const TABLE_FRAME = "border border-divider";
const HEAD_ROW = "bg-neutral-100";

export function EditDiscountReviewStep(props: EditDiscountReviewProps) {
  const { mode, original, draft, lists, t } = props;
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  const span = (from: string, to: string) => `${day(from)} – ${to === "" ? t("rating.discountForm.noEnd") : day(to)}`;
  const rows = changedDiscountRows(props);
  const oldValue = valueFigure(original) ?? bigFigure(original, t);
  const newValue = valueFigure(draft) ?? bigFigure(draft, t);
  const v = props.version;

  const versions =
    mode === "info"
      ? [
          {
            id: "this",
            label: t("rating.discountEdit.version.this", { v }),
            value: oldValue,
            dates: span(original.effective_from, draft.effective_to),
            after: t("rating.discountEdit.after.inPlace"),
            strong: false,
          },
        ]
      : mode === "change"
        ? [
            {
              id: "today",
              label: t("rating.discountEdit.version.today", { v }),
              value: oldValue,
              dates: span(original.effective_from, draft.effective_from === "" ? original.effective_to : dayBefore(draft.effective_from)),
              after: t("rating.discountEdit.after.endDate"),
              strong: false,
            },
            {
              id: "next",
              label: t("rating.discountEdit.version.new", { v: v + 1 }),
              value: newValue,
              dates: span(draft.effective_from, draft.effective_to),
              after: t("rating.discountEdit.after.newVersion"),
              strong: true,
            },
          ]
        : [
            {
              id: "today",
              label: t("rating.discountEdit.version.today", { v }),
              value: oldValue,
              dates: span(original.effective_from, original.effective_to),
              after: t("rating.discountEdit.after.superseded"),
              strong: false,
            },
            {
              id: "next",
              label: t("rating.discountEdit.version.correction", { v: v + 1 }),
              value: newValue,
              dates: span(original.effective_from, original.effective_to),
              after: t("rating.discountEdit.after.replaces", { v }),
              strong: true,
            },
          ];

  return (
    <div className="flex flex-col gap-5" data-discount-step="edit-review">
      <Panel as="section" aria-labelledby="discount-sec-changes">
        <h2 id="discount-sec-changes" className={SECTION_HEADING}>
          {t("rating.discountEdit.section.changes")}
        </h2>
        <div className={TABLE_FRAME}>
          <PlainTable>
            <thead>
              <tr className={HEAD_ROW}>
                <th scope="col">{t("rating.discountEdit.col.field")}</th>
                <th scope="col">{t("rating.discountEdit.col.before")}</th>
                <th scope="col">{t("rating.discountEdit.col.after")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr data-discount-change="none">
                  <td colSpan={3} className="text-neutral-700">
                    {t("rating.discountEdit.noChanges")}
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} data-discount-change={row.id}>
                    <td>{row.label}</td>
                    <td className="text-neutral-700">{row.before}</td>
                    <td className={row.id === "value" ? "font-semibold" : undefined}>{row.after}</td>
                  </tr>
                ))
              )}
            </tbody>
          </PlainTable>
        </div>
        {mode === "correct" && (
          <div className="mt-5" data-discount-review-reason="">
            <p className="field-label">{t("rating.discountEdit.section.reason")}</p>
            <p className="m-0 mt-3 font-semibold">{props.reason.trim() || "—"}</p>
          </div>
        )}
      </Panel>

      {mode !== "info" && (
        <Panel as="section" aria-labelledby="discount-sec-bill">
          <h2 id="discount-sec-bill" className={SECTION_HEADING}>
            {t("rating.discountEdit.section.bill", { bill: EXAMPLE_BILL })}
          </h2>
          <div className={`${TABLE_FRAME} [&_td:not(:first-child)]:text-right [&_th:not(:first-child)]:text-right`} data-discount-example="edit">
            <PlainTable>
              <thead>
                <tr className={HEAD_ROW}>
                  <th scope="col">
                    <span className="sr-only">{t("rating.discountForm.thisDiscount")}</span>
                  </th>
                  <th scope="col">{t("rating.discountEdit.col.before")}</th>
                  <th scope="col">{t("rating.discountEdit.col.after")}</th>
                </tr>
              </thead>
              <tbody>
                <tr className="bg-neutral-100 font-semibold">
                  <td>{draft.name.trim() || t("rating.discountForm.thisDiscount")}</td>
                  <td className="tabular-nums" data-discount-bill-before="">
                    {reductionText(exampleReduction(original))}
                  </td>
                  <td className="tabular-nums" data-discount-bill-after="">
                    {reductionText(exampleReduction(draft))}
                  </td>
                </tr>
              </tbody>
            </PlainTable>
          </div>
        </Panel>
      )}

      <Panel as="section" aria-labelledby="discount-sec-saved-as">
        <h2 id="discount-sec-saved-as" className={SECTION_HEADING}>
          {t("rating.discountEdit.section.saved")}
        </h2>
        <div className={TABLE_FRAME} data-discount-versions="">
          <PlainTable>
            <thead>
              <tr className={HEAD_ROW}>
                <th scope="col">{t("rating.discountEdit.col.version")}</th>
                <th scope="col" className="text-right">
                  {t("rating.discountForm.review.value")}
                </th>
                <th scope="col">{t("rating.discountEdit.col.dates")}</th>
                <th scope="col">{t("rating.discountEdit.col.afterSaving")}</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((row) => (
                <tr key={row.id} data-discount-version={row.id} className={row.strong ? "font-semibold" : undefined}>
                  <td>{row.label}</td>
                  <td className="text-right tabular-nums">{row.value}</td>
                  <td className="tabular-nums">{row.dates}</td>
                  <td>{row.after}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
        {mode === "change" && draft.effective_from !== "" && (
          <p className="m-0 mt-4 bg-info-100 px-3 py-3 text-base text-info-700" data-discount-saved-note="change">
            {t("rating.discountEdit.note.billsBefore", { date: day(draft.effective_from), value: oldValue })}
          </p>
        )}
        {mode === "correct" && (
          <p
            className="m-0 mt-4 bg-warning-100 px-3 py-3 text-base text-warning-700"
            role="status"
            data-discount-saved-note="correct"
          >
            {t("rating.discountEdit.note.issuedKeep", { value: oldValue })}
          </p>
        )}
      </Panel>
    </div>
  );
}
