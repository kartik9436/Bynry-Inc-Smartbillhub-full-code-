// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-014 (the seven child collections, as ROWS whose ORDER is
//           data) · US-WRK-016 (EP-WRK-03) — the builder's steps 2, 3, 4, 5
//           and 6. Screens: Work-015 (`wireframes/Work-015.png`), Work-016
//           (`wireframes/Work-016.png`)
// Rules:    BR-WRK-009 (a bundle is ROWS, and `seq` is what the phone shows)
//           · B14 rule 20 (ONE table type) · rule 21 (Tailwind utilities;
//           this file is on `src/styles/route-b-migrated.txt`) · rule 15
//           (icons for row actions) · rule 32 (one sentence per section)
//           · A12 (below 1024px a wide table SCROLLS inside its own box)
// Tests:    src/components/EditableTable.dom.test.tsx ·
//           src/components/TableArray.dom.test.tsx (the groups and the two
//           error slots added 2026-09-28)
// Impacts:  src/features/work/TemplateBuilder.tsx (five collections use it)
//           · src/features/customers/serviceRequestShared.tsx `FeeLinesTable` (the
//           service-request fee lines: capture step 5 editable; the review, the
//           confirmation and the request detail read-only — 2026-09-23)
//           · src/components/TableArray.tsx (the framed table array)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIRST OF THE THREE THINGS `09-component-inventory.md` SAYS THIS
// PRODUCT HAS NEVER HAD**, in its own words: *"`EditableTable` with a drag
// handle and an inline add row (Work-015, Work-016). Nothing in the staff app
// reorders rows by dragging today."*
//
// WHY IT IS IN THE KIT AND NOT IN `features/work/`
// ────────────────────────────────────────────────
// B14 rule 36, ratified 2026-09-04: *"the captured packs give layout and
// detail, r10's UI-RULES.md gives the VISUAL STYLE, and the shared component
// kit is how you comply."* Five collections on one screen use this today and
// `Work-021`, `Work-023` and `Work-026` draw the same shape in later waves. A
// copy per feature is how the portal grew a second kit (`DEF-CWP-3655`).
//
// WHY THE ORDER IS DATA AND NOT PRESENTATION
// ──────────────────────────────────────────
// `wot_tasks.seq` is what the technician's phone lists the job in
// (`BR-WRK-009`). Dragging a row is therefore an EDIT, not a view preference —
// which is why this component hands its owner the WHOLE new list rather than a
// "moved from 3 to 5" event, and why the builder posts a collection back
// whole. `PUT /work/templates/{id}/{collection}` is replace-in-full for exactly
// this reason: six PATCHes would have a moment in between where two rows both
// claim `seq = 3` and the unique key refuses.
//
// ⚠ **KEYBOARD FIRST, AND IT IS NOT AN ACCESSIBILITY AFTERTHOUGHT.** HTML5
// drag-and-drop is invisible to a keyboard, to a screen reader and to
// `@testing-library` alike — a component whose only reordering path is a mouse
// gesture is a component whose reordering CANNOT BE TESTED, and an untestable
// control is the shape hard-won law 2 keeps finding. So every row carries two
// real buttons (move up · move down) that do the whole job, and the pointer
// drag is layered on top of them. The buttons are what the suite drives and
// what a person without a mouse uses; if the drag ever breaks, the feature
// still works and a test still fails.
import { useState } from "react";
import type { ReactNode } from "react";

import { Button } from "./Button";
import { RefusalStrip } from "./Surfaces";

export interface EditableColumn<Row> {
  key: string;
  label: string;
  /** Right-aligns and puts the figure on tabular numerals — the same posture
   *  `DataTable`'s `numeric` column takes, so the two tables agree. */
  numeric?: boolean;
  /**
   * **THE GROUP'S OWN KEY, DRAWN ONCE — on the FIRST row of each group and
   * nowhere else.** Added 2026-09-28 for the New Connect units table, whose
   * drawing carries the instruction in as many words: *"Grouped by unit,
   * confirmed 28 Sep. The unit is named once at the head of its group."* The
   * unit number and its kind are editable on that first row; the four rows
   * under it leave those two cells empty rather than repeating a fact the
   * heading already states.
   *
   * ⚠ **IT MEANS NOTHING WITHOUT `groups` AND IS IGNORED THERE.** A table with
   * no groups has no "first row of the group" to be once within, so a column
   * marked this way in an ungrouped table draws on every row exactly as it
   * would have without the flag. That is deliberate: the alternative — drawing
   * it on row 1 alone — would silently blank a column the day a caller dropped
   * its groups.
   */
  groupOnce?: boolean;
  /**
   * **WHAT THE HEADER CELL DRAWS INSTEAD OF `label`** — opt-in, added
   * 2026-10-04 under B14 rule 36 with its first caller, the raise's units and
   * assets tables (`CR-168-BRC10` images 14, 15, 19: a tick-all box heads the
   * select column). `label` stays the column's name for everything else.
   * Absent renders exactly what every existing table rendered.
   */
  header?: ReactNode;
  cell: (row: Row, index: number) => ReactNode;
}

/**
 * ONE GROUP OF ROWS, with its heading row.
 *
 * The drawing: `Unit 1 · Dwelling` over five service-point rows, then
 * `Unit 2 · Dwelling · 4 service points` and `Unit 15 · Dwelling · 4 service
 * points` with their rows folded away. `Whole build` is a group too — the work
 * order that belongs to the build rather than to a service point becomes its
 * own row under its own heading.
 *
 * ⚠ **COLLAPSE IS A PAIR OR IT IS NOTHING.** `collapsed` and `onToggle` arrive
 * together or neither arrives, because a group whose rows are hidden with no
 * control to bring them back is rows a clerk cannot reach and cannot see they
 * cannot reach. The union below makes that unrepresentable rather than
 * documented — the same move `rowRemoveBlocked` made by returning a REASON
 * instead of a boolean.
 */
export type EditableRowGroup =
  | {
      key: string;
      /** The heading — *Unit 1 · Dwelling*. A FACT, ≤ 6 words (B14 rule 33). */
      heading: ReactNode;
      /** What the heading adds when the rows are folded away — *4 service
       *  points*. A FACT, ≤ 6 words. */
      summary?: ReactNode;
      /** A refusal about the WHOLE group, drawn under its heading — *"Unit 15
       *  takes Broadband. This address does not."* ≤ 6 words per sentence. */
      error?: string;
      collapsed?: undefined;
      onToggle?: undefined;
    }
  | {
      key: string;
      heading: ReactNode;
      summary?: ReactNode;
      error?: string;
      collapsed: boolean;
      /** Presses the heading. Required beside `collapsed`; see the type above. */
      onToggle: () => void;
    };

interface EditableTableBase<Row> {
  /** What the panel calls itself — *TASKS — 7 STEPS · 45 MIN TOTAL*.
   *
   *  ⚠ **`""` DRAWS NO CAPTION BAR (2026-09-23).** Where the table sits in a
   *  panel whose own heading already names it — the fee lines under
   *  *Application fees* — a caption bar would print the same words twice, one
   *  line apart. Every existing caller passes words and renders as before. */
  caption: string;
  columns: EditableColumn<Row>[];
  rows: Row[];
  rowKey: (row: Row, index: number) => string;
  /** The inline add row — the inputs and the **+ Add** button. Absent on a
   *  collection a person may reorder and remove from but not extend. */
  addRow?: ReactNode;
  /**
   * WHERE the add row sits — `"below"` (the default) or `"above"` the table.
   *
   * ⚠ **IT DEFAULTS TO `"below"` SO THAT NOTHING THAT EXISTS MOVES.** The work
   * template builder passes `addRow` five times and asked for none of this; a
   * blanket flip would rearrange a module nobody was looking at, on one
   * screen's authority. Same reasoning `rowRemoveBlocked` was added under, and
   * B14 rule 36's: extend the kit, never copy it into a screen.
   *
   * `"above"` is the PO's ruling of 2026-09-18 for the plan wizard's three
   * binding steps — charges, taxes and discounts. On those three the add row is
   * the PRIMARY act: a clerk arrives to attach something, and the table is the
   * record of what they have attached so far. A control reached for first
   * should not sit under a list that grows.
   */
  addRowPosition?: "above" | "below";
  /** What the table says when it holds nothing (B14 rule 17 — what is missing
   *  AND how to fill it; the add row underneath is the how). */
  emptyText: string;
  /**
   * Whether this collection HAS an order a person may change.
   *
   * ⚠ **DEFAULTS TO `true`, AND THAT IS NOT timidity — IT IS WHAT KEEPS THE
   * FIVE EXISTING COLLECTIONS EXACTLY AS THEY ARE.** This component was built
   * for work-order templates, where `wot_tasks.seq` IS DATA: it is the order a
   * technician's phone lists the jobs in. Reordering there is a feature, and a
   * silent default of `false` would delete it from five live tables.
   *
   * **Pass `false` where the sequence means nothing.** A plan's charges have no
   * order — whether `PAPER` sits above or below `HYDRANT` changes nobody's
   * bill — so a drag handle and two arrows would be three controls claiming a
   * fact the data does not hold, which is hard-won law 2 wearing the opposite
   * face: not a dead control, but a live one that means nothing.
   *
   * When `false`: no `draggable`, no handle, no ↑/↓, and `labels.moveUp`,
   * `moveDown` and `position` become OPTIONAL — a caller should not have to
   * invent accessible names for controls that do not render.
   */
  reorderable?: boolean;
  /**
   * Why this row's × is REFUSED, or `undefined` when it may be removed.
   *
   * ⚠ **OPT-IN, AND ABSENT MEANS EVERY ROW IS REMOVABLE** — so the six
   * collections that predate it render byte-for-byte what they rendered
   * before. It is the same shape, and the same reasoning, as `reorderable`:
   * *the kit gains a prop rather than the screen getting a copy* (B14 rule 36,
   * and the `DEF-RAT-5731` ruling that added the first one).
   *
   * ⚠ **IT EXISTS BECAUSE A REMOVE CAN BE REFUSED BY A RULE RATHER THAN BY
   * TASTE.** It was added for a plan's discount, which could not be unbound
   * while anybody was enrolled — `OQ-322`, CLOSED by PO ruling 2026-10-03 (an
   * unbind now ends those enrolments the day before, so the plan wizard no
   * longer passes it; `ChargeCodeWizard`'s one-row rule still does). Before
   * this prop the only ways to express such a rule were to drop the
   * row's × (a control that vanishes with no reason) or to let the click
   * through and have the save refuse minutes later, on another step. Both are
   * worse than a disabled control that names its reason, which is what
   * `BR-SHL-025` asks for and what the two-pane screen this replaced already
   * did.
   *
   * The returned string is the REASON and it reaches the person as `title`, so
   * it is a catalogue string like every other word this file renders.
   */
  rowRemoveBlocked?: (row: Row, index: number) => string | undefined;
  /**
   * **A ROW'S OWN ACTIONS, drawn in the trailing action cell before its ✕** —
   * the move-in Fees table's *Waive deposit* on the deposit row (PO ruling (7)
   * of 2026-10-05). Hand back `<RowAction>`s (icons with their names, B14
   * rule 15), or `undefined` for a row that has none.
   *
   * ⚠ **ADDED 2026-10-05 UNDER B14 RULES 36 AND 43** — extend the kit as an
   * opt-in, never copy it into a screen. Absent draws nothing, so every
   * collection that predates it renders byte-for-byte as before.
   */
  rowActions?: (row: Row, index: number) => ReactNode | undefined;
  /**
   * Whether the `#` column is drawn. **Absent means drawn** — every collection
   * that predates this prop keeps its row numbers byte-for-byte.
   *
   * ⚠ **ADDED 2026-09-23 FOR THE SERVICE-REQUEST FEE LINES, UNDER B14 RULES 36
   * AND 43** (*extend the kit, never copy it into a screen*). The PO approved
   * that table's columns in so many words — *"Fee · Charged per · Qty · Unit
   * price · Amount · Waive · (remove icon)"* (*"i like this please use this"*)
   * — and a `#` is not one of them. On a work template the number IS the order
   * a technician's phone lists the job in (`BR-WRK-009`); on a fee quote it
   * would be a sixth figure beside five money columns that means nothing.
   */
  numbered?: boolean;
  /**
   * **A FOOTER ROW, ONE CELL PER COLUMN, keyed by `column.key`** — the fee
   * table's `Total`, drawn under `Amount`. A column with no entry gets an empty
   * cell, so the footer lines up with the body whatever the caller leaves out.
   *
   * ⚠ **THE KIT RENDERS WHAT IT IS HANDED AND ADDS NOTHING UP.** A total of
   * money is hard rule 2's to compute and the SERVER's to serve; a component
   * that summed its own cells would be money arithmetic in a browser, in
   * JavaScript numbers, which is the exact defect the rule exists to prevent.
   * Absent draws no footer at all, so no existing collection moves.
   */
  footerCells?: Partial<Record<string, ReactNode>>;
  /**
   * **A REFUSAL ABOUT THE WHOLE ROW**, drawn as a band under it — the units
   * table's *"Sewer follows water."* Absent on a row that is fine.
   *
   * ⚠ **IT IS THE ROW'S AND NOT A CELL'S ON PURPOSE.** *"Unit 15 takes
   * Broadband. This address does not."* is true of the combination, so hanging
   * it under one of the nine cells would point at the wrong thing and make the
   * other eight look innocent.
   */
  rowError?: (row: Row, index: number) => string | undefined;
  /**
   * **A REFUSAL ABOUT ONE CELL**, drawn under that cell's control — the units
   * table's *"already exists here"* on a duplicate unit label. The third
   * argument is `EditableColumn.key`.
   *
   * ⚠ **BOTH SLOTS EXIST BECAUSE THE DRAWING HAS BOTH**, and a screen with only
   * the row band puts a field-level message where a clerk cannot tell which
   * box to correct.
   */
  cellError?: (row: Row, index: number, columnKey: string) => string | undefined;
  /**
   * **WHAT A ROW SHOWS WHEN IT IS OPENED** — a band spanning every column,
   * drawn directly under the row (`undefined` draws nothing). Added
   * 2026-10-05 under B14 rule 36 with its first caller, the move-in's
   * *Services and meters* (`CR-171-BRC10` image 31: a meter's ▸ opens one
   * line of its facts under it). The row's own control decides whether it is
   * open; this slot only draws what it is handed. Absent renders exactly what
   * every existing table rendered.
   */
  rowDetail?: (row: Row, index: number) => ReactNode | undefined;
  /**
   * **A ROW THAT HANGS OFF THE ROW ABOVE IT** is drawn on the muted fill —
   * image 30's sub-meter and behind-the-meter rows under their meter. Added
   * with the same caller as `rowDetail`; absent, every row is drawn as before.
   */
  rowNested?: (row: Row, index: number) => boolean;
  "data-collection": string;
}

/** The labels an EDITABLE table needs for its row controls. Catalogue strings,
 *  always — this file spells no English (`G15`). `remove` is always required;
 *  the three ordering labels are needed only while `reorderable` is not
 *  `false`. */
export interface EditableTableLabels {
  moveUp?: string;
  moveDown?: string;
  remove: string;
  position?: string;
}

/**
 * ⚠ **TWO SHAPES, AND THE TYPE SAYS WHICH ONE A CALLER IS IN (2026-09-23).**
 *
 * **Editable** — every collection that predates `readOnly`, unchanged: it
 * hands back the WHOLE new list through `onChange` and names its row controls
 * through `labels`.
 *
 * **Read-only** — the same table, drawn where the rows are a RECORD rather than
 * something being built: no reorder, no remove, no add row and no action
 * column, and therefore no `onChange` and no control labels to invent. It
 * exists so that one set of fee lines reads identically on the four screens
 * that show it (capture step 5 editable; the review, the confirmation and the
 * request detail read-only) — B14 rule 20's *one table type*, reached by
 * extending the kit rather than by drawing a second `<table>` beside it.
 */
/**
 * **GROUPS AND THE FUNCTION THAT SORTS ROWS INTO THEM ARRIVE TOGETHER OR
 * NEITHER ARRIVES.**
 *
 * Groups with no `groupOf` would draw every heading over nothing; a `groupOf`
 * with no groups would be computed and discarded. Both are the shape law 2
 * keeps finding — a thing that renders and means nothing — so the type refuses
 * them rather than a comment asking a caller not to.
 *
 * Absent on both sides is the flat table every existing collection draws.
 *
 * ⚠ **A ROW WHOSE GROUP IS IN NO GROUP IS STILL DRAWN**, above the first
 * heading and marked `data-editable-ungrouped`. Dropping it would be an
 * absence, and an absence is invisible to every check this repo has
 * (`DEF-CUS-3653`). A caller with a grouping bug can see it.
 *
 * ⚠ **REORDERING IS OFF INSIDE A GROUPED TABLE.** `move()` splices the flat
 * list, so ↑ on the first row of group two would carry it into group one — a
 * control that does something other than what it says.
 */
export type EditableGrouping<Row> =
  | { groups?: undefined; groupOf?: undefined }
  | {
      /** The groups, IN THE ORDER THEY ARE DRAWN. */
      groups: readonly EditableRowGroup[];
      /** Which group a row belongs in; matched against `EditableRowGroup.key`. */
      groupOf: (row: Row, index: number) => string;
    };

export type EditableTableProps<Row> = EditableTableBase<Row> &
  EditableGrouping<Row> &
  (
    | {
        readOnly?: false;
        /** The WHOLE new list, in its new order. See the header: the order is data. */
        onChange: (rows: Row[]) => void;
        /**
         * Called INSTEAD of `onChange` when a row's ✕ is pressed — for rows the
         * SERVER owns, where removing one is a request to the server and not
         * an edit of a list in memory.
         *
         * ⚠ **ADDED 2026-09-23 FOR THE FEE LINES, OPT-IN.** A fee line is a
         * stored row with its own id and its own refusals (`remove_fee_line`
         * refuses a submitted request, a waived line and a paid one), so the
         * caller must be told WHICH row, not handed a shorter list and left to
         * work out the difference. Absent, the ✕ behaves exactly as it always
         * has.
         */
        onRemove?: (row: Row, index: number) => void;
        labels: EditableTableLabels;
      }
    | {
        readOnly: true;
        onChange?: undefined;
        onRemove?: undefined;
        labels?: EditableTableLabels;
      }
  );


/**
 * **THE HEADER TIER — ONE TABLE TYPE (B14 rule 20, `DEF-SHL-5771`).** Exactly
 * `DataTable.css`'s `.data-table th`: the heading face, the 12px header token,
 * semibold, uppercase, 0.08em, neutral-700. This drew `font-mono … tracking-tag`
 * until 2026-10-05, so every TableArray in the product — eight consumers when
 * the PO confirmed the blast radius on 2026-09-19, five of them in the Work
 * template builder — was a second table type beside every list.
 */
const HEADER_TIER =
  "font-heading text-table-header font-semibold uppercase tracking-table-header text-neutral-700";
export function EditableTable<Row>(props: EditableTableProps<Row>) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const readOnly = props.readOnly === true;
  const grouped = props.groups !== undefined;
  // Absent means reorderable — the five collections that predate this prop. A
  // read-only table has no order to change, whatever the caller passed, and
  // neither has a grouped one: see `EditableGrouping`.
  const reorderable = props.reorderable !== false && !readOnly && !grouped;
  // Absent means numbered — every collection that predates `numbered`.
  const numbered = props.numbered !== false;
  // How wide a band or a group heading has to be. Derived from the SAME three
  // flags the header row is built from, so the two cannot drift: a hand-typed
  // number here is a heading that stops short of the last column the day
  // somebody adds one.
  const columnSpan =
    (reorderable ? 1 : 0) + (numbered ? 1 : 0) + props.columns.length + (readOnly ? 0 : 1);
  const labels: EditableTableLabels = props.labels ?? { remove: "" };
  // ⚠ THE BORDER FOLLOWS THE POSITION, and that is not cosmetic: a divider on
  // the wrong side reads as the add row belonging to whatever is beyond it.
  const addAbove = props.addRowPosition === "above";
  const addRowBlock =
    props.addRow === undefined || readOnly ? null : (
      <div
        className={
          addAbove
            ? "flex flex-wrap items-end gap-2 border-b border-divider p-2"
            : "flex flex-wrap items-end gap-2 border-t border-divider p-2"
        }
        data-editable-addrow={addAbove ? "above" : "below"}
      >
        {props.addRow}
      </div>
    );
  // `position` names WHICH row a control acts on, so it is still wanted on the
  // remove button when nothing else orders the rows. A caller that passes no
  // ordering labels gets the row number alone rather than "undefined 3".
  const at = (index: number): string =>
    labels.position === undefined ? String(index + 1) : `${labels.position} ${index + 1}`;

  function move(from: number, to: number): void {
    if (props.readOnly === true) return;
    if (to < 0 || to >= props.rows.length || from === to) return;
    const next = [...props.rows];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    props.onChange(next);
  }

  function remove(index: number): void {
    if (props.readOnly === true) return;
    const row = props.rows[index];
    if (props.onRemove !== undefined && row !== undefined) {
      props.onRemove(row, index);
      return;
    }
    props.onChange(props.rows.filter((_row, i) => i !== index));
  }

  // ── THE ROW, ONCE ──────────────────────────────────────────────────────
  // Extracted 2026-09-28 so the flat path and the grouped path draw the SAME
  // row rather than two that look alike. `index` stays the row's position in
  // the FLAT list whichever path draws it, because that is what `move`,
  // `remove`, `data-editable-row` and every accessible name key off — a group
  // is a way of drawing the list, never a second list.
  //
  // ⚠ `firstOfGroup` is what `EditableColumn.groupOnce` reads. It is `false`
  // on the flat path, and a `groupOnce` column therefore draws on every row
  // there — see that flag's own note for why that is the safe direction.
  function rowNode(
    row: Row,
    index: number,
    firstOfGroup: boolean,
    ungrouped?: boolean,
  ): ReactNode {
    const cellErrorFor = props.cellError;
    return (
      <tr
        key={props.rowKey(row, index)}
        data-editable-row={String(index + 1)}
        data-editable-ungrouped={ungrouped === true ? "" : undefined}
        className={props.rowNested?.(row, index) === true ? "bg-neutral-100" : undefined}
        data-editable-nested={props.rowNested?.(row, index) === true ? "" : undefined}
        draggable={reorderable || undefined}
        onDragStart={reorderable ? () => setDragFrom(index) : undefined}
        onDragOver={reorderable ? (event) => event.preventDefault() : undefined}
        onDrop={
          reorderable
            ? () => {
                if (dragFrom !== null) move(dragFrom, index);
                setDragFrom(null);
              }
            : undefined
        }
      >
        {reorderable && (
          <td className="border-b border-divider px-2 py-2 align-top">
            {/* The drawing's ≡. It is decorative — the two buttons
                at the end of the row are the real controls — so it
                is hidden from the accessibility tree rather than
                announced as a thing that does nothing. */}
            <span className="cursor-grab text-neutral-700" aria-hidden="true">
              ≡
            </span>
          </td>
        )}
        {numbered && (
          <td className="border-b border-divider px-2 py-2 align-top tabular-nums">{index + 1}</td>
        )}
        {props.columns.map((column) => {
          // The group's own key is drawn on the group's first row and nowhere
          // else — the drawing's "the unit is named once at the head of its
          // group". Outside a grouped table the flag means nothing.
          const silent = grouped && column.groupOnce === true && !firstOfGroup;
          const cellError = silent ? undefined : cellErrorFor?.(row, index, column.key);
          return (
            <td
              key={column.key}
              className={
                column.numeric
                  ? "border-b border-divider px-2 py-2 text-right align-top tabular-nums"
                  : "border-b border-divider px-2 py-2 align-top"
              }
              data-group-once={silent ? "" : undefined}
            >
              {silent ? null : column.cell(row, index)}
              {cellError !== undefined && (
                <span
                  className="mt-1 block text-sm text-danger-700"
                  data-cell-error={column.key}
                >
                  {cellError}
                </span>
              )}
            </td>
          );
        })}
        {!readOnly && (
          <td className="border-b border-divider px-2 py-2 text-right align-top">
            <span className="flex justify-end gap-1">
              {reorderable && (
                <>
                  <Button
                    size="row"
                    variant="ghost"
                    onClick={() => move(index, index - 1)}
                    disabled={index === 0}
                    aria-label={`${labels.moveUp} — ${at(index)}`}
                    data-move="up"
                  >
                    ↑
                  </Button>
                  <Button
                    size="row"
                    variant="ghost"
                    onClick={() => move(index, index + 1)}
                    disabled={index === props.rows.length - 1}
                    aria-label={`${labels.moveDown} — ${at(index)}`}
                    data-move="down"
                  >
                    ↓
                  </Button>
                </>
              )}
              {props.rowActions?.(row, index)}
              {/* The reason is computed ONCE and drives both the
                disabled state and the `title`, so a row can never
                be refused with no explanation or explained while
                still clickable. */}
              {(() => {
                const blocked = props.rowRemoveBlocked?.(row, index);
                return (
                  <Button
                    size="row"
                    variant="ghost-danger"
                    onClick={() => remove(index)}
                    disabled={blocked !== undefined}
                    title={blocked}
                    aria-label={`${labels.remove} — ${at(index)}`}
                    data-remove-row={String(index + 1)}
                    data-remove-blocked={blocked === undefined ? undefined : ""}
                  >
                    ✕
                  </Button>
                );
              })()}
            </span>
          </td>
        )}
      </tr>
    );
  }

  /** A band spanning every column — a refusal about a whole row or a whole
   *  group. `RefusalStrip` is the kit's one red strip (BR-SHL-020); the `td`
   *  form and its `colSpan` are why it takes an `as`. */
  function bandNode(key: string, kind: "row" | "group", at: string, message: string): ReactNode {
    return (
      <tr key={key}>
        <RefusalStrip
          as="td"
          colSpan={columnSpan}
          role="alert"
          {...(kind === "row" ? { "data-row-error": at } : { "data-group-error": at })}
        >
          {message}
        </RefusalStrip>
      </tr>
    );
  }

  /** Every row, plus its band — the unit of both paths below. */
  function rowWithBand(
    row: Row,
    index: number,
    firstOfGroup: boolean,
    ungrouped?: boolean,
  ): ReactNode[] {
    const nodes = [rowNode(row, index, firstOfGroup, ungrouped)];
    const detail = props.rowDetail?.(row, index);
    if (detail !== undefined && detail !== null) {
      nodes.push(
        <tr key={`${props.rowKey(row, index)}-detail`} data-row-detail={String(index + 1)}>
          <td
            colSpan={columnSpan}
            className="border-b border-divider bg-neutral-100 px-2 py-2 text-base text-text"
          >
            {detail}
          </td>
        </tr>,
      );
    }
    const message = props.rowError?.(row, index);
    if (message !== undefined) {
      nodes.push(bandNode(`${props.rowKey(row, index)}-error`, "row", String(index + 1), message));
    }
    return nodes;
  }

  const body: ReactNode[] = [];
  if (props.groups === undefined) {
    props.rows.forEach((row, index) => body.push(...rowWithBand(row, index, false)));
  } else {
    const groupOf = props.groupOf;
    // Positions, not rows — the flat index is what every control keys off.
    const orphans: number[] = [];
    const byGroup = new Map<string, number[]>(props.groups.map((group) => [group.key, []]));
    props.rows.forEach((row, index) => {
      const key = groupOf(row, index);
      const bucket = byGroup.get(key);
      if (bucket === undefined) orphans.push(index);
      else bucket.push(index);
    });
    // A row nobody's group claims is DRAWN rather than dropped — see
    // `EditableGrouping`. It is marked so a caller can see its own bug.
    orphans.forEach((index) => {
      body.push(...rowWithBand(props.rows[index] as Row, index, false, true));
    });
    props.groups.forEach((group) => {
      const positions = byGroup.get(group.key) ?? [];
      const folded = group.collapsed === true;
      const heading = (
        <span className="font-semibold">
          {group.heading}
          {group.summary !== undefined && (
            <span className="ml-2 font-normal text-neutral-700">{group.summary}</span>
          )}
        </span>
      );
      body.push(
        <tr key={`group-${group.key}`} data-editable-group={group.key}>
          <th
            scope="colgroup"
            colSpan={columnSpan}
            className="border-b border-divider bg-neutral-200 px-2 py-2 text-left align-middle"
          >
            {group.onToggle === undefined ? (
              heading
            ) : (
              <button
                type="button"
                aria-expanded={!folded}
                onClick={group.onToggle}
                data-group-toggle={group.key}
                className="flex w-full items-center gap-2 bg-transparent px-0 py-0 text-left hover:text-accent-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
              >
                {/* Decorative: `aria-expanded` above is what a screen reader
                    reads, so the glyph is not a second, weaker signal. */}
                <span aria-hidden="true" className="text-neutral-700">
                  {folded ? "▸" : "▾"}
                </span>
                {heading}
              </button>
            )}
          </th>
        </tr>,
      );
      if (group.error !== undefined) {
        body.push(bandNode(`group-${group.key}-error`, "group", group.key, group.error));
      }
      if (!folded) {
        positions.forEach((index, seat) => {
          const row = props.rows[index] as Row;
          body.push(...rowWithBand(row, index, seat === 0));
        });
      }
    });
  }

  return (
    <div data-editable-table={props["data-collection"]}>
      <div className="border border-divider">
        {props.caption !== "" && (
          <div className={`border-b border-divider px-3 py-2 ${HEADER_TIER}`}>
            {props.caption}
          </div>
        )}
        {addAbove ? addRowBlock : null}
        {props.rows.length === 0 ? (
          <p className="m-0 px-3 py-4 text-sm text-neutral-700" data-editable-empty="">
            {props.emptyText}
          </p>
        ) : (
          /* A12 — a wide table scrolls inside its own box rather than pushing
             the page sideways. `Work-016` has eight columns. */
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-base">
              <thead>
                <tr>
                  {/* The handle column and the row number, which the drawing
                      puts before every other column. */}
                  {reorderable && <th className="w-8 border-b border-divider px-2 py-2" />}
                  {numbered && (
                    <th className={`w-10 border-b border-divider px-2 py-2 text-left ${HEADER_TIER}`}>
                      #
                    </th>
                  )}
                  {props.columns.map((column) => (
                    <th
                      key={column.key}
                      className={
                        column.numeric
                          ? `border-b border-divider px-2 py-2 text-right ${HEADER_TIER}`
                          : `border-b border-divider px-2 py-2 text-left ${HEADER_TIER}`
                      }
                    >
                      {column.header ?? column.label}
                    </th>
                  ))}
                  {!readOnly && <th className="w-24 border-b border-divider px-2 py-2" />}
                </tr>
              </thead>
              <tbody>{body}</tbody>
              {props.footerCells !== undefined && (
                <tfoot>
                  <tr data-editable-footer="">
                    {reorderable && <td className="px-2 py-2" />}
                    {numbered && <td className="px-2 py-2" />}
                    {props.columns.map((column) => (
                      <td
                        key={column.key}
                        className={
                          column.numeric
                            ? "px-2 py-2 text-right align-top font-semibold tabular-nums"
                            : "px-2 py-2 align-top font-semibold"
                        }
                      >
                        {props.footerCells?.[column.key] ?? null}
                      </td>
                    ))}
                    {!readOnly && <td className="px-2 py-2" />}
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
        {addAbove ? null : addRowBlock}
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-016@2b08ba9f · US-WRK-014@2b08ba9f (EP-WRK-03) · 09-component-inventory.md row `EditableTable` · wireframes/Work-015.png, Work-016.png
// generated: 2026-09-05 by the CR-070 wave E build lane
// checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E✔(TemplateBuilder renders five of them) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/EditableTable.dom.test.tsx · G31 (this file is on src/styles/route-b-migrated.txt) · G13
// exceptions: E3 the pointer drag is layered ON TOP of two real buttons rather than being the only path — HTML5 drag-and-drop cannot be driven by a keyboard, a screen reader or the test runner, and a control the suite cannot press is the shape law 2 keeps finding
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
