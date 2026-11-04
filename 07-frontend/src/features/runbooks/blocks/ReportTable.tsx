// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — the shape three blocks share.
// Rules: B14 rule 20 (ONE table type) · rule 36 · rule 31 · hard rule 2 · 3.
// ───────────────────────────────────────────────────────
// **Breakdown, Reconciled and Row decisions are one table with different
// columns**, which is the whole reason twelve blocks can draw thirty-four
// runbooks. B14 rule 20 says the product has ONE table type — 13.5px body under
// a 12px header — so this composes the class the shared stylesheet already
// declares rather than inventing a second.
//
// ⚠ IT IS NOT `DataTable`, AND THAT IS DELIBERATE. `DataTable` (FE-02) is the
// server-paged LIST: it owns a request state, a toolbar, filters and a pager,
// and every one of those is a question about a query. A frozen report block has
// no query — `BR-RBS-020`: the report is composed at close and FROZEN, so a
// past run reopened draws exactly what it drew that day. Handing `DataTable` a
// static array would mean inventing an `onStateChange` that must never fire.
// The `Records` block, which DOES page, uses `DataTable`; these three do not.
// ⚠ `cell-num` IS THE SHARED STYLESHEET'S OWN CLASS, AND THE FIRST DRAFT WROTE
// `num` — which no stylesheet declares and no compiler emits, so the numeric
// columns rendered LEFT-ALIGNED with the class sitting in the DOM doing nothing.
// `tsc`, eslint and every `toContain` assertion passed over it. It was found by
// looking at the rendered table beside `RBS-006-R9`, which right-aligns its
// money columns — hard-won law 6, and the second thing in this wave that only
// looking could catch.
//
// Reusing a class the stylesheet ALREADY declares is what B14 rule 21 asks for
// (it adds none), and it is `DataTable.tsx`'s own class, so the two table
// families cannot drift on what a numeric column looks like.
import { ReportValueCell } from "./ReportValueCell";
import type { BlockContext, ReportColumn, ReportRow } from "./types";

export function ReportTable(props: {
  columns: ReportColumn[];
  rows: ReportRow[];
  ctx: BlockContext;
  /** An extra trailing column the caller draws itself — the `Decide` column on
   *  `RBS-006-R20`, and nothing else so far. */
  trailing?: { label: string; render: (row: ReportRow) => React.ReactNode };
  caption: string;
}) {
  return (
    <table className="data-table" data-report-table="">
      <caption className="sr-only">{props.caption}</caption>
      <thead>
        <tr>
          {props.columns.map((column) => (
            <th key={column.key} scope="col" className={column.numeric === true ? "cell-num" : undefined}>
              {column.label}
            </th>
          ))}
          {props.trailing !== undefined && <th scope="col">{props.trailing.label}</th>}
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          // ⚠ `row.id` is the KEY and never a cell — B14 rule 31: no database id
          // is ever the visible value of a field.
          <tr key={row.id} data-report-row="">
            {props.columns.map((column) => (
              <td key={column.key} className={column.numeric === true ? "cell-num" : undefined}>
                {row.cells[column.key] === undefined ? null : (
                  <ReportValueCell value={row.cells[column.key]} ctx={props.ctx} />
                )}
              </td>
            ))}
            {props.trailing !== undefined && <td>{props.trailing.render(row)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
