// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — the two tables the raise ticks
//           rows in: the building's UNITS (image 14, ruling 19) and the ticked
//           units' ASSETS (image 15, rulings 20 and 22; image 19 on an account).
// Rules:    B14 rules 20 (ONE table type — this is the kit's `TableArray`,
//           read-only, with a tick column), 21, 31 (no uuid is drawn), 33,
//           43, 44 · NFR-3 (the rows are a SERVER page, searched on the
//           server) · NFR-5 (no maximum anywhere).
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE COMPONENT FOR BOTH TABLES, BECAUSE THE DRAWING DRAWS ONE SHAPE
// TWICE** — a search box, *N of M chosen* hard right, a tick-all header, the
// rows, the pager, and one instruction under it. Only the columns differ, so
// the host passes those and this file owns the ticking.
//
// ⚠ **THE TICK-ALL BOX TICKS THE PAGE IN HAND, NOT THE WHOLE BUILDING.** A
// building's units are a server page (NFR-3), so "all" of a four-hundred-flat
// block is rows this screen has never read. Ticking what is visible is a fact
// the clerk can see; ticking what is not would raise jobs on units nobody
// looked at. The count beside the box is the honest total.
import type { ReactNode } from "react";

import { ListPager } from "@/components/ListPager";
import { TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import type { PageSize } from "@/components/tableTypes";

export interface PickRow {
  id: string;
  /** What the row's tick is named after — *Apt 101*, *W-5040*. */
  name: string;
}

export function RaisePickTable<Row extends PickRow>(props: {
  title: string;
  /** The DOM handle (`data-testid`) a walkthrough and a test find it by. */
  collection: string;
  rows: readonly Row[];
  total: number;
  chosen: ReadonlySet<string>;
  /** ONE call for every row the gesture moved — the tick-all box moves the
   *  page in one write (`DEF-WRK-9616`: one write per row read the same stale
   *  form ten times and kept only the last). */
  onToggle: (rows: readonly Row[], ticked: boolean) => void;
  columns: readonly TableArrayColumn<Row>[];
  search?: { label: string; placeholder: string; value: string; onChange: (value: string) => void };
  /** Chips beside the search — image 14's *All · Residential · Commercial*. */
  chips?: ReactNode;
  /** *N of M chosen* — already translated. */
  chosenFact: string;
  tickLabel: (row: Row) => string;
  tickAllLabel: string;
  emptyText: string;
  note?: ReactNode;
  /** A refusal under the note, already translated. */
  error?: string;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
}) {
  const allTicked = props.rows.length > 0 && props.rows.every((row) => props.chosen.has(row.id));
  const tickColumn: TableArrayColumn<Row> = {
    key: "tick",
    label: props.tickAllLabel,
    header: (
      <input
        type="checkbox"
        aria-label={props.tickAllLabel}
        checked={allTicked}
        disabled={props.rows.length === 0}
        onChange={(event) => {
          const ticked = event.target.checked;
          props.onToggle(props.rows.filter((row) => props.chosen.has(row.id) !== ticked), ticked);
        }}
      />
    ),
    cell: (row) => (
      <input
        type="checkbox"
        aria-label={props.tickLabel(row)}
        checked={props.chosen.has(row.id)}
        onChange={(event) => props.onToggle([row], event.target.checked)}
      />
    ),
  };
  return (
    <div data-testid={props.collection}>
      <TableArray<Row>
        readOnly
        title={props.title}
        collection={props.collection}
        fact={<span className="font-semibold text-neutral-900">{props.chosenFact}</span>}
        lead={
          props.search === undefined ? undefined : (
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="search"
                className="input w-full max-w-md"
                aria-label={props.search.label}
                placeholder={props.search.placeholder}
                value={props.search.value}
                onChange={(event) => props.search?.onChange(event.target.value)}
              />
              {props.chips}
            </div>
          )
        }
        columns={[tickColumn, ...props.columns]}
        rows={props.rows}
        rowKey={(row) => row.id}
        emptyText={props.emptyText}
        note={props.note}
      >
        {props.total > props.rows.length || props.page > 1 ? (
          <ListPager
            total={props.total}
            page={props.page}
            per={props.per}
            onPage={props.onPage}
            onPer={props.onPer}
          />
        ) : null}
        {props.error !== undefined && (
          <p className="mt-2 mb-0 text-base text-danger-700" role="alert" data-pick-error={props.collection}>
            {props.error}
          </p>
        )}
      </TableArray>
    </div>
  );
}
