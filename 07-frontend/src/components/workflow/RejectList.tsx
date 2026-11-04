// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 3 VALIDATE, the rejects (design B15 §4.3) ·
//           CR-028 debt sweep D8 (2026-08-22) — the inline "fix here" editor
//           r10 promises in the caption finally exists: a correction control
//           per reject row feeding PATCH /imports/{id}/rows/{row_no} ·
//           CR-036 amendment 1 (b) 2026-08-26 — the PO could not press that
//           control on a 9,881-reject run; the list pages now (B14 rule 16)
// Rules:    BR-MET-086 (a units row naming a premise not on file fails stage 3
//           "with a sentence saying WHICH is missing") · CR-016 (the problem
//           and the fix are PLAIN ENGLISH — no rule id, no column name in the
//           SENTENCES; the editor's labels are the operator's own file
//           headers, which is a different thing) · B14 rule 20 (one table
//           type) · B14 rule 21 (Tailwind) · B14 rule 16 (pagination footer on
//           every list table; wizard SUMMARY tables are exempt and a
//           four-figure reject list is not one)
// Impacts:  features/metering/ImportWorkflowPage.tsx stage 3 composes this.
// ───────────────────────────────────────────────────────
import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { ListPager, pageSlice } from "@/components/ListPager";
import { PlainTable } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE, type PageSize } from "@/components/tableTypes";

import type { RejectedRow } from "./contract";
import * as WF from "./workflowKit";

/**
 * `ROW │ KEY │ PROBLEM │ SUGGESTED FIX` (+ the fix control when wired).
 *
 * ⚠ THE FOURTH COLUMN IS THE ONE THAT EARNS THE SCREEN. A reject list that says
 * only what is wrong sends an operator back to a spreadsheet with 431 rows and
 * no instruction; r10's own pairs are the model — *"Parent premise P-11902 was
 * not loaded"* → *"Load the premise first"*, and *"Street name will not
 * geocode"* → *"Correct the address"*. The fix travels with the problem.
 *
 * ⚠ BOTH SENTENCES ARE THE SERVER'S AND BOTH ARE PLAIN ENGLISH. CR-016 applies
 * here like any other screen: a clerk must never read a rule code or a column
 * name. The row NUMBER is not an internal reference — it is the operator's own
 * spreadsheet line, and it is the single most useful thing on the row.
 *
 * ⚠ `row_number` IS RIGHT-ALIGNED AND TABULAR so a column of line numbers reads
 * as a column (B15 §9 note 6).
 *
 * ⚠ **IT PAGES, AND THAT IS `CR-036` AMENDMENT 1 (b) — NOT A TIDY-UP.** On a
 * live deployment a units file rejected **9,881 of 9,881 rows**, and this table
 * drew every one of them. MEASURED on the whole page in jsdom, which does no
 * layout, no style recalc and no paint (`ImportRejectFix.dom.test.tsx`):
 *
 * ```
 * before   rows=9881  buttons=9881  nodes=69241  stage-3 render=3616ms
 *          click+re-render=1114ms   editor opens
 *          SECOND click=782ms       editor CLOSED AGAIN
 * after    rows=50    buttons=50    nodes=435    stage-3 render=189ms
 *          click+re-render=12ms     editor opens
 * ```
 *
 * A real browser must ALSO re-measure every cell of an auto-layout table that
 * size on the same click, so 1.1 s is the floor and not the figure. **That is
 * the symptom, exactly: the editor opened and then closed again** — the
 * Product Owner clicked a control that had not repainted, clicked it a second
 * time, and the toggle below took the second click as "close".
 *
 * So two things changed together, and NEITHER alone is the fix:
 *
 * 1. **The window is a page, and the page is what re-renders.** It is also what
 *    **B14 rule 16** has required all along — *"pagination footer on every list
 *    table … wizard SUMMARY tables are exempt"* — and a four-figure reject list
 *    is the opposite of a summary table. `ListPager` + `pageSlice` are the
 *    shared footer the other five non-`DataTable` lists use; no new component,
 *    no new class, no new copy.
 * 2. **`Fix here…` OPENS. It does not close.** A control that opens an editor
 *    and then closes it on the next click is a coin toss whenever the screen is
 *    slower than the operator — and slowness is a property of the file, not of
 *    this component, so it can come back. Clicking the same row again is
 *    IDEMPOTENT (it stays open); clicking another row's control moves the
 *    editor there; the editor's own `Cancel` is what closes it, which is the
 *    control that says so. `aria-expanded` states which row is open.
 *
 * ⚠ **AND `editing` IS KEYED BY THE OPERATOR'S ROW NUMBER, NOT BY POSITION.**
 * A background run's rejects arrive from a poll, so the array underneath can be
 * replaced while the operator is typing. Row numbers survive that; array
 * identity does not. An editor a refresh can close is not fixed by polling more
 * slowly, so it is pinned by a test (`RejectListFix.dom.test.tsx`).
 *
 * THE INLINE EDITOR (D8 — DEBT: r10 stage 3 draws *"Fix the rejects here — no
 * need to re-upload"*, the backend PATCH landed with AST-W3, and this table
 * offered only the sentence). When the caller passes `onFix` AND the row
 * carries its `raw` source cells, each reject grows a "Fix here" control that
 * opens the row's OWN cells — labelled by the operator's file headers, valued
 * as staged — and saves ONLY the changed ones. The caller owns what happens
 * next (the run drops to stage 1 server-side and stages 2–3 re-run — never a
 * commit over a stale verdict).
 */
export interface RejectListProps {
  caption: string;
  rejects: readonly RejectedRow[];
  /** B14 rule 17 — an empty list says so. "Nothing was rejected" is good news
   *  and a blank table is not the way to deliver it. */
  emptyMessage: string;
  /** D8: save the changed cells of one reject row. Absent = read-only table
   *  (exactly the pre-D8 render, so every other consumer is untouched). */
  onFix?: (rowNumber: number, values: Record<string, string | null>) => void;
  /** True while a fix is in flight — the save buttons hold. */
  fixing?: boolean;
  /** Rows per page. The pager offers the shared sizes; this is only the one it
   *  opens on, and exists so a test can page a short list. Ignored in
   *  `serverPage` mode, where the window is the caller's to hold. */
  initialPageSize?: PageSize;
  /**
   * **DEF-766 — SERVER-WINDOWED MODE.** Passed, `rejects` is ONE PAGE the
   * SERVER sliced, `total` is the server's own COUNT of the whole reject list,
   * and turning a page is a request rather than a slice.
   *
   * ⚠ Why the table could not simply be handed all of them and left to page:
   * every reject carries its `raw` source cells so the inline editor has
   * something to edit, and `GET /imports/{id}` is polled every two seconds — so
   * an all-reject run shipped 4.28 MB every two seconds to draw fifty rows.
   * Bounding the payload without this prop would have cost the operator the
   * rows beyond the first page; bounding it WITH this prop costs nothing —
   * the footer still counts 9,881 and the pager still reaches row 9,881.
   *
   * Omitted, this component behaves exactly as it did: it pages the array it
   * was handed, which is what every other caller and an older server want.
   */
  serverPage?: {
    total: number;
    page: number;
    per: PageSize;
    onPage: (page: number) => void;
    onPer: (per: PageSize) => void;
  };
}

function RejectFixEditor(props: {
  row: RejectedRow;
  fixing: boolean;
  onSave: (values: Record<string, string | null>) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const raw = props.row.raw ?? {};
  /**
   * `BR-MET-1032` — the cells the server is showing as `••••6789`.
   *
   * ⚠ **A MASKED CELL OPENS EMPTY AND IS NEVER PRE-FILLED WITH ITS MASK.** An
   * input holding `••••6789` that an operator clicks into and appends a digit
   * to sends `••••67891`, and the server's `normalise_identifier` strips the
   * bullets — so `67891` would be filed as somebody's Social Security number,
   * matched against nobody, and a second customer minted for them. Nothing
   * would object anywhere. Empty-with-a-placeholder makes the only two acts
   * available the two that are safe: leave it, or type the whole number.
   */
  const masked = new Set(props.row.masked ?? []);
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(raw).map(([key, value]) => [key, masked.has(key) ? "" : (value ?? "")]),
    ),
  );
  // Only the cells the operator actually CHANGED travel — a full-row echo
  // would stamp every column as "fixed" in the audit trail.
  const changed: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(drafts)) {
    if (masked.has(key)) {
      // ⚠ **AN EMPTY MASKED CELL IS "UNCHANGED", NOT "CLEARED".** It is what
      // this editor OPENS with, so reading it as a clear would wipe the
      // identifier off every row an operator opened and closed — and that is
      // the value the matcher joins on. Clearing an identifier is a change to
      // the file, which is where the operator's own copy lives; the PO's
      // ruling of 2026-09-01 puts the whole number there and only there.
      if (value !== "") {
        changed[key] = value;
      }
      continue;
    }
    if ((raw[key] ?? "") !== value) {
      changed[key] = value === "" ? null : value;
    }
  }
  return (
    <div className="flex flex-col gap-2 py-2" data-workflow-fix-editor={props.row.row_number}>
      <div className="grid grid-cols-2 gap-2 max-md:grid-cols-1">
        {Object.keys(raw).map((column) => (
          <label key={column} className="flex flex-col gap-1 text-base">
            {/* The operator's OWN file header — not a product column name. */}
            <span className={WF.CELL_MUTED}>{column}</span>
            <input
              type="text"
              className="input"
              value={drafts[column] ?? ""}
              placeholder={masked.has(column) ? (raw[column] ?? "") : undefined}
              onChange={(event) => setDrafts({ ...drafts, [column]: event.target.value })}
            />
          </label>
        ))}
      </div>
      <div className="flex gap-2">
        <Button
          size="row"
          disabled={props.fixing || Object.keys(changed).length === 0}
          onClick={() => props.onSave(changed)}
        >
          {t("workflow.rejects.fix.save")}
        </Button>
        <Button size="row" variant="ghost" onClick={props.onCancel}>
          {t("forms.cancel")}
        </Button>
      </div>
      {/* fix_row's law, said before the click: the run re-runs stages 2–3. */}
      <p className={`m-0 ${WF.CELL_MUTED}`}>{t("workflow.rejects.fix.revalidates")}</p>
    </div>
  );
}

export function RejectList({
  caption,
  rejects,
  emptyMessage,
  onFix,
  fixing,
  initialPageSize = DEFAULT_PAGE_SIZE,
  serverPage,
}: RejectListProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(initialPageSize);
  const editable = onFix !== undefined;
  const columnCount = editable ? 5 : 4;
  // ⚠ **THE TOTAL IS THE SERVER'S WHEN THERE IS ONE (DEF-766).** In windowed
  // mode `rejects.length` is the size of ONE PAGE, so counting it would print
  // *"1–50 of 50"* under a run that rejected 9,881 rows — the exact figure the
  // operator needs and the exact way a bound loses it.
  const windowed = serverPage !== undefined;
  const shownPer = windowed ? serverPage.per : per;
  const total = windowed ? serverPage.total : rejects.length;
  // The list shrinks under the operator every time a fix lands, so the page
  // they are on can stop existing. Clamped on read rather than in an effect:
  // an effect would draw one frame of an empty page first.
  const pages = Math.max(1, Math.ceil(total / shownPer));
  const current = Math.min(windowed ? serverPage.page : page, pages);
  // Windowed, the server already sliced; unwindowed, this is the only slice.
  const pageRows = windowed ? [...rejects] : pageSlice(rejects, current, shownPer);
  return (
    <div className={WF.TABLE_WRAP} data-workflow="rejects">
      <PlainTable>
        <caption className={WF.TABLE_CAPTION}>{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className={WF.NUM_HEAD}>
              {t("workflow.rejects.col.row")}
            </th>
            <th scope="col">{t("workflow.rejects.col.key")}</th>
            <th scope="col">{t("workflow.rejects.col.problem")}</th>
            <th scope="col">{t("workflow.rejects.col.fix")}</th>
            {editable && <th scope="col">{t("workflow.rejects.col.action")}</th>}
          </tr>
        </thead>
        <tbody>
          {total === 0 && (
            <tr>
              <td colSpan={columnCount}>{emptyMessage}</td>
            </tr>
          )}
          {pageRows.map((reject) => (
            <Fragment key={`${reject.row_number}-${reject.key}`}>
              <tr data-workflow-reject={reject.row_number}>
                <td className={WF.NUM_CELL}>{reject.row_number}</td>
                <td>{reject.key}</td>
                <td>{reject.problem}</td>
                <td className={WF.CELL_MUTED}>{reject.suggested_fix}</td>
                {editable && (
                  <td>
                    {/* No raw cells served (older server) → no control: the
                        table degrades to exactly its pre-D8 self. */}
                    {reject.raw !== undefined && Object.keys(reject.raw).length > 0 && (
                      <Button
                        size="row"
                        variant="secondary"
                        aria-expanded={editing === reject.row_number}
                        onClick={() => setEditing(reject.row_number)}
                      >
                        {t("workflow.rejects.fix.open")}
                      </Button>
                    )}
                  </td>
                )}
              </tr>
              {editable && editing === reject.row_number && (
                <tr>
                  <td colSpan={columnCount}>
                    <RejectFixEditor
                      row={reject}
                      fixing={fixing === true}
                      onSave={(values) => {
                        setEditing(null);
                        onFix(reject.row_number, values);
                      }}
                      onCancel={() => setEditing(null)}
                    />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </PlainTable>
      {/* B14 rule 16. Drawn only when there IS a list — "0–0 of 0" under an
          empty-state sentence is a footer arguing with the row above it. */}
      {total > 0 && (
        <ListPager
          total={total}
          page={current}
          per={shownPer}
          onPage={windowed ? serverPage.onPage : setPage}
          onPer={
            windowed
              ? serverPage.onPer
              : (next) => {
                  setPer(next);
                  setPage(1);
                }
          }
        />
      )}
    </div>
  );
}
