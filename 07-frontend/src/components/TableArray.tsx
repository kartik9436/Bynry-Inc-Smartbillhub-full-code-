// ── Trace ──────────────────────────────────────────────
// Change:   the NEW CONNECT REDESIGN of 2026-09-28 — **THE TABLE ARRAY, IN THE
//           KIT.** The five-step drawings
//           (`05-prototype/new-connect-redesign-2026-09-28/`) carry four of
//           them: the units table (nine columns, grouped by unit), the common
//           selection, the charges table and the messages table.
// Rules:    **B14 rule 43** (a piece of UI is built as a COMPONENT; standalone
//           code inside a page is not reuse) · **rule 36** (extend the kit,
//           never copy it into a screen) · **rule 44** (the drawing says WHAT
//           is on the screen; our UI standard says HOW it is built — spacing,
//           sizes, the type scale, the tokens and the component kit, and it
//           wins every time) · **rule 42** (built from the PNGs as images) ·
//           rule 20 (ONE table type) · rule 21 (Tailwind utilities; this file
//           is on `src/styles/route-b-migrated.txt`) · rule 33 (a label ≤ 3
//           words, a fact ≤ 6, rationale ZERO) · rule 31 (no database id is
//           ever the visible value of a field) · rule 15 (icons for row
//           actions) · BR-SHL-025 (a control that cannot act is DISABLED WITH
//           ITS REASON) · hard rule 2 (money is never multiplied or rounded in
//           a browser)
// Tests:    src/components/TableArray.dom.test.tsx
// Impacts:  src/components/EditableTable.tsx (its groups and its two error
//           slots were added for this) ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY THIS EXISTS AND WHAT IT IS NOT
// ══════════════════════════════════════════════════════════════════════════
// B14 rule 20 is ONE table type, and §13 of the UI method is explicit that a
// second table is a defect rather than a contribution. So this is **not** a
// table: `EditableTable` is the table, and this is the FRAME the drawings put
// around it — a panel, a heading, a fact on the heading's right, a footer of
// actions, and a note under them.
//
// ⚠ **`features/customers/disconnect/DisconnectTableArray.tsx` IS THE SAME
// FRAME, BUILT THREE DAYS EARLIER FOR ONE WIZARD, AND IT STILL EXISTS. THAT IS
// A DUPLICATE AND IT IS NOT FIXED HERE.** This file is the kit's one and that
// one should delegate to it (hard-won law 5, and B14 rule 36). **What blocks
// the merge is ONE attribute name**, not the shape: that wrapper emits
// `data-array-add="<collection>"` on its single button, which four assertions
// in `features/customers/DisconnectWizard.test.tsx` and four lines of
// `10-scripts/def_cus_6750_four_step_disconnect_walkthrough.mjs` read. This
// file keys on the ACTION instead — `data-array-action="<key>"` — because
// `step3-units.png` draws TWO footer buttons on one collection and a handle
// named after the collection cannot tell them apart.
//
// **Merging them is a change to a live wizard, its test and its walkthrough**,
// so it is reported to the coordinator for its own row rather than done inside
// a components lane. ⚠ A comment is a note and never a plan (hard-won law 1) —
// if no row exists against this paragraph, the duplicate is what the repo has.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHAT THE DRAWINGS ASKED FOR THAT THE KIT DID NOT HAVE
// ══════════════════════════════════════════════════════════════════════════
//   * **GROUPS.** `step3-units.png` draws `Unit 1 · Dwelling` over five
//     service-point rows, then two folded groups carrying their counts. The
//     screen's own note says it in words: *"Grouped by unit, confirmed 28 Sep.
//     The unit is named once at the head of its group."* That went into
//     `EditableTable`, because a heading row and a folded group live INSIDE
//     the `<tbody>` and no wrapper can put them there.
//   * **TWO ERROR SLOTS.** The units screen lists both: *"{unit} takes
//     {service}. This address does not." on the row* and *"already exists
//     here" on a duplicate unit label* — one about a whole row, one about one
//     cell. Also in `EditableTable`, for the same reason.
//   * **MORE THAN ONE FOOTER ACTION.** `step3-units.png` draws `+ Add row` and
//     `+ Add work order` side by side; `step4-charges.png` draws `+ Add charge`
//     with the totals block on the same line, right-aligned.
//   * **THE CELL CONTROLS.** Four kinds across the four tables. They are at the
//     bottom of this file and they are the reason it is a component and not a
//     `<select>` typed into four screens (rule 43).
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT IT DELIBERATELY DOES NOT DO
// ══════════════════════════════════════════════════════════════════════════
// **IT ADDS NOTHING UP.** `EditableTable`'s own note says why and hard rule 2
// is the rule: a total of money is the SERVER's to compute, and a component
// that summed its own cells would be money arithmetic in a browser, in
// JavaScript numbers. `footerTrailing` renders the figures it is handed.
//
// **IT SPELLS NO ENGLISH.** Every string here arrives from the host, already
// translated — B14 rule 35, and `G15`.
import type { ReactNode } from "react";

import { Button } from "./Button";
import { EditableTable } from "./EditableTable";
import type {
  EditableColumn,
  EditableGrouping,
  EditableRowGroup,
  EditableTableLabels,
} from "./EditableTable";
import { Panel } from "./Panel";

export type TableArrayColumn<Row> = EditableColumn<Row>;
export type TableArrayGroup = EditableRowGroup;

/**
 * One button on the footer row — `+ Add row`, `+ Add work order`,
 * `+ Add charge`, `+ Add template`, `Apply to all`.
 */
export interface TableArrayAction {
  /** Stable key. ⚠ **NEVER RENDERED** — B14 rule 31. */
  key: string;
  /** `+ Noun` opens a creator, `Verb ✓` commits (B14 rule 4). ≤ 3 words. */
  label: string;
  onClick: () => void;
  /**
   * The accent tier, for the one action a step is actually about — the common
   * selection's `Apply to all` is drawn filled and the add buttons are not.
   * Absent is the secondary tier every `+ Noun` takes.
   */
  primary?: boolean;
  /**
   * Why it cannot act, or `undefined` when it can. **BR-SHL-025: a control
   * that cannot act is DISABLED AND SAYS WHY, never hidden** — a button that
   * vanished when the last service was already a row reads as the product
   * having lost a feature.
   */
  blockedReason?: string;
  /**
   * **THE REASON IS DRAWN BESIDE THE BUTTON, NOT ONLY IN ITS TOOLTIP** — added
   * 2026-10-03 under B14 rule 36 with its first caller, the New plan form
   * (`CR-167-BRC10`, images 11 and 15: a greyed *+ Add service* with *All
   * added.* next to it — PO ruling 6). Absent keeps every existing table
   * exactly as it was: the reason in `title` alone.
   */
  showReason?: boolean;
}

interface Base<Row> {
  /** The panel's heading — *Units and service points*, *What is charged*.
   *  ≤ 3 words is the cap for a LABEL; these are the drawing's own headings. */
  title: string;
  /**
   * The fact on the heading's right.
   *
   * ⚠ **A FACT, NOT A CAPTION AND NOT RATIONALE** (B14 rule 33): it states
   * something true of the collection — *3 of 25* — and never why the screen
   * works the way it does.
   */
  fact?: ReactNode;
  columns: readonly TableArrayColumn<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row, index: number) => string;
  /** B14 rule 17 — what is missing AND how to fill it; the footer's add button
   *  under it is the how. */
  emptyText: string;
  /** The DOM handle a walkthrough finds this collection by. */
  collection: string;
  /** A refusal about a whole row, drawn as a band under it. */
  rowError?: (row: Row, index: number) => string | undefined;
  /** A refusal about one cell, drawn under that cell's control. The third
   *  argument is the column's `key`. */
  cellError?: (row: Row, index: number, columnKey: string) => string | undefined;
  /** A footer row inside the table, one cell per column key — the fee table's
   *  `Total` under `Amount`. See §3: it is rendered, never computed. */
  footerCells?: Partial<Record<string, ReactNode>>;
  /**
   * The line under the table, inside the panel.
   *
   * ⚠ **AN INSTRUCTION, CAPPED AT SIX WORDS PER SENTENCE** (B14 rule 33), and
   * **rationale is ZERO words** — *why* a row behaves as it does belongs in
   * the code and the register, never here.
   */
  note?: ReactNode;
  /**
   * **THE BLOCK AT THE RIGHT-HAND END OF THE FOOTER ROW — `step4-charges.png`.**
   *
   * The drawing puts `Total · Paid now · Remaining` on the same line as
   * `+ Add charge`, hard right. This renders it inside the footer fragment
   * with `ml-auto`, which is exactly where §2's note said the step-4 lane
   * would add it.
   *
   * ⚠ **IT LANDS WITH ITS CALLER, AND THAT IS WHY IT IS HERE NOW AND WAS NOT
   * HERE ON 2026-09-28.** `G13` refuses a prop that guards rendering and has
   * no non-test caller, so this file's own exception `E2` deliberately left it
   * out until a screen drew it. `NewConnectChargesStep.tsx` is that screen and
   * this commit is that commit — the repo's pattern for `numbered`,
   * `footerCells`, `rowRemoveBlocked` and `addRowPosition`, each of which
   * names the screen that wanted it.
   *
   * ⚠ **IT RENDERS WHAT IT IS HANDED AND ADDS NOTHING UP** — §3, and
   * `CLAUDE.md` hard rule 2. A total of money is the SERVER's to compute; a
   * kit component that summed its own money cells would be arithmetic in a
   * browser, in JavaScript numbers, which is `DEF-088` and `DEF-127`.
   *
   * ⚠ **IT NEEDS A FOOTER TO SIT IN.** `EditableTable` draws the footer row
   * only when `addRow` is given, so a caller passing this and no `actions`
   * gets nothing. That is stated rather than worked around: a trailing block
   * with no row of its own is a second footer, and B14 rule 20 is one table.
   */
  footerTrailing?: ReactNode;
  /**
   * **THE BLOCK AT THE LEFT-HAND START OF THE FOOTER ROW** — added 2026-10-04
   * under B14 rule 36 with its first caller, the rule builder (`CR-168-BRC10`
   * images 57 and 59): *Add a trigger…* / *Add a message…* / *Add an
   * escalation…* is a PICKER at the start of the footer row and `+ Add` sits
   * at its end. A picker is not a button, so `actions` cannot carry it. Absent
   * renders exactly what every existing table rendered.
   */
  footerLead?: ReactNode;
  /** Anything else that belongs under the table INSIDE the same panel. */
  children?: ReactNode;
  /** `EditableTable.rowDetail` — what an opened row shows under it (image 31,
   *  `CR-171-BRC10`). Absent renders exactly what every table rendered. */
  rowDetail?: (row: Row, index: number) => ReactNode | undefined;
  /** `EditableTable.rowNested` — a row hanging off the one above (image 30's
   *  sub-meter under its meter). Absent renders every row as before. */
  rowNested?: (row: Row, index: number) => boolean;
  /**
   * **THE `#` COLUMN** — image 30's *Field visit* draws one (`CR-171-BRC10`),
   * where §1's four drawings did not. Absent keeps it off, which is every
   * existing table.
   */
  numbered?: boolean;
  /**
   * **WHAT SITS ABOVE THE TABLE INSIDE THE SAME PANEL** — added 2026-10-03
   * under B14 rule 36 with its first caller, the New plan form's *Intended
   * for* (`CR-167-BRC10`, image 07: three ticks, then the notes table, in one
   * box). Absent renders exactly what every existing table rendered.
   */
  lead?: ReactNode;
}

type Grouped<Row> =
  | { groups?: undefined; groupOf?: undefined }
  | {
      /** The groups, in the order they are drawn. */
      groups: readonly TableArrayGroup[];
      /** Which group a row belongs in; matched against the group's `key`. */
      groupOf: (row: Row, index: number) => string;
    };

type Editable<Row> = {
  readOnly?: false;
  onChange: (rows: Row[]) => void;
  /** The ✕'s accessible name — B14 rule 15 puts row actions on icons. */
  removeLabel: string;
  /** Why this row's ✕ is refused, or `undefined` when it may go. */
  rowRemoveBlocked?: (row: Row, index: number) => string | undefined;
  /** A row's own icon actions, before its ✕ — see `EditableTable.rowActions`. */
  rowActions?: (row: Row, index: number) => ReactNode | undefined;
  /** The footer's buttons, left to right as drawn. Absent draws no footer row
   *  — a collection a clerk may remove from but not extend. */
  actions?: readonly TableArrayAction[];
};

// ⚠ **TWO PROPS THE DRAWINGS ASK FOR ARE DELIBERATELY NOT HERE, AND G13 IS
// WHY.** `step4-charges.png` puts `Total · Paid now · Remaining` at the right
// of the footer row beside `+ Add charge`, and `DisconnectTableArray` carries
// a running fact beside its button. Both were written here and both were
// REMOVED before this landed, because **G13 refuses a prop that guards
// rendering and has no non-test caller** — hard-won law 2, ratified by the PO
// on 2026-08-11, and `CLAUDE.md` says of it in so many words: *do not silence
// it*. The lawful alternative is an ALLOW entry with a revisit condition, and
// the gate's own docstring puts that on the daily PO batch as a loosening of a
// ratified decision.
//
// **THE REPO'S OWN PATTERN IS THAT A KIT PROP LANDS WITH ITS FIRST CALLER** —
// `EditableTable`'s `numbered`, `footerCells`, `rowRemoveBlocked` and
// `addRowPosition` each say so in their own note, each naming the screen that
// wanted it. So the step-4 lane adds `footerTrailing?: ReactNode` back in the
// commit that draws the totals, rendered inside the footer fragment below with
// `className="ml-auto"`, and a step lane wanting a running fact adds
// `footerFact` the same way. Until then `children` puts a block under the
// table inside the same panel.
//
// ⚠ A comment is a note and never a plan (hard-won law 1). This one is
// reported to the coordinator with the step-4 brief, not left to be found.

type ReadOnly = {
  readOnly: true;
  onChange?: undefined;
  removeLabel?: undefined;
  rowRemoveBlocked?: undefined;
  rowActions?: undefined;
  actions?: undefined;
};

export type TableArrayProps<Row> = Base<Row> & Grouped<Row> & (Editable<Row> | ReadOnly);

/**
 * ONE COLLECTION, DRAWN THE WAY ALL OF THEM ARE DRAWN.
 *
 * ⚠ **`numbered` AND `reorderable` ARE OFF, AND THAT IS THE DRAWING'S
 * DECISION.** None of the four drawn tables has a `#` column and none of them
 * has an order that means anything — whether Water sits above Sewer changes
 * nobody's supply — so a drag handle and two arrows would be three controls
 * claiming a fact the data does not hold. That is hard-won law 2 wearing its
 * other face: not a dead control, but a live one that means nothing.
 */
export function TableArray<Row>(props: TableArrayProps<Row>) {
  // The footer row, or nothing at all. `EditableTable`'s `addRow` slot is the
  // one that draws it — `flex flex-wrap items-end gap-2` with a rule above —
  // so a later `footerTrailing` belongs in this fragment with `ml-auto` and
  // needs no second flex container.
  const actions = props.readOnly === true ? undefined : props.actions;
  const footer =
    (actions === undefined || actions.length === 0) &&
    props.footerTrailing === undefined &&
    props.footerLead === undefined ? (
      undefined
    ) : (
      <>
        {props.footerLead !== undefined && (
          <div className="min-w-0" data-array-lead-footer={props.collection}>
            {props.footerLead}
          </div>
        )}
        {(actions ?? []).map((action) => (
          <Button
            key={action.key}
            variant={action.primary === true ? "primary" : "secondary"}
            size="sm"
            onClick={action.onClick}
            disabled={action.blockedReason !== undefined}
            // BR-SHL-025: the reason is READABLE, not merely implied by grey.
            title={action.blockedReason}
            data-array-action={action.key}
          >
            {action.label}
          </Button>
        ))}
        {(actions ?? []).map((action) =>
          action.showReason === true && action.blockedReason !== undefined ? (
            <span
              key={`${action.key}-reason`}
              className="self-center text-base font-semibold text-neutral-700"
              data-array-action-reason={action.key}
            >
              {action.blockedReason}
            </span>
          ) : null,
        )}
        {props.footerTrailing !== undefined && (
          <div className="ml-auto" data-array-trailing={props.collection}>
            {props.footerTrailing}
          </div>
        )}
      </>
    );

  // ⚠ **EVERY PROP IS PASSED BY NAME AND NOT THROUGH A SPREAD, AND THAT IS
  // G13's DOING.** The first draft assembled a `shared` object and spread it
  // into both calls — correct, and INVISIBLE: `G13` looks for a caller that
  // names the prop, so `EditableTable`'s `rowError` read as a feature nothing
  // supplies and the gate went red on a prop that was in fact wired. The gate
  // was right to: a spread hides wiring from a READER too, which is the
  // expensive half. Named props cost eleven lines and cannot lie.
  //
  // ⚠ **THE ONE SPREAD LEFT IS THE GROUPING PAIR, AND IT HAS TO BE.**
  // `EditableGrouping` makes `groups` without `groupOf` unrepresentable, which
  // is the whole point of it; two separate optional props written by name
  // cannot express that to the compiler. Neither is render-guarded, so nothing
  // is hidden from G13 by it.
  const grouping: EditableGrouping<Row> =
    props.groups === undefined ? {} : { groups: props.groups, groupOf: props.groupOf };
  const columns = props.columns as EditableColumn<Row>[];
  const rows = props.rows as Row[];

  return (
    <Panel
      as="section"
      title={props.title}
      trailing={
        props.fact === undefined ? undefined : (
          <span className="text-base text-neutral-700" data-array-note={props.collection}>
            {props.fact}
          </span>
        )
      }
      data-array={props.collection}
    >
      {props.lead !== undefined && (
        <div className="mb-4" data-array-lead={props.collection}>
          {props.lead}
        </div>
      )}
      {props.readOnly === true ? (
        <EditableTable<Row>
          readOnly
          caption=""
          numbered={props.numbered === true}
          reorderable={false}
          columns={columns}
          rows={rows}
          rowKey={props.rowKey}
          emptyText={props.emptyText}
          rowError={props.rowError}
          cellError={props.cellError}
          rowDetail={props.rowDetail}
          rowNested={props.rowNested}
          footerCells={props.footerCells}
          data-collection={props.collection}
          {...grouping}
        />
      ) : (
        <EditableTable<Row>
          caption=""
          numbered={props.numbered === true}
          reorderable={false}
          columns={columns}
          rows={rows}
          rowKey={props.rowKey}
          emptyText={props.emptyText}
          rowError={props.rowError}
          cellError={props.cellError}
          rowDetail={props.rowDetail}
          rowNested={props.rowNested}
          footerCells={props.footerCells}
          data-collection={props.collection}
          addRow={footer}
          onChange={props.onChange}
          rowRemoveBlocked={props.rowRemoveBlocked}
          rowActions={props.rowActions}
          labels={{ remove: props.removeLabel } satisfies EditableTableLabels}
          {...grouping}
        />
      )}
      {props.note !== undefined && (
        <p className="mt-2 mb-0 text-base text-neutral-700" data-array-hint={props.collection}>
          {props.note}
        </p>
      )}
      {props.children}
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE CELL CONTROLS
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **WHY THEY ARE COMPONENTS AND NOT A `<select>` TYPED INTO FOUR SCREENS.**
// B14 rule 43, PO verbatim: *"make them coponents - dont write stand alone
// code, engineer it"*. Four tables across five steps draw the same four
// controls; four hand-written `<select>`s are how a product acquires four
// different dropdowns, which is the drift rule 36 names by example.
//
// ⚠ **EVERY ONE TAKES A `label`, AND IT IS REQUIRED.** A cell has no visible
// label — the column header is the only word near it — and a column header
// does NOT name a form control to a screen reader. Without `aria-label` a
// clerk using one hears *"combo box"* nine times per row. Requiring it also
// means the word arrives from the catalogue rather than being invented here.
//
// ⚠ **`className="input"` AND NOT A PILE OF UTILITIES.** `FormModal.css`
// declares the product's one control — 36px, 6px/10px, 14px, the surface fill,
// the divider border — and `.view select` adds the shared chevron (B14 rule 8)
// to every `<select>` under `<main class="view">`. Writing sizes here would
// lose to those descendant rules anyway (`DEF-MET-4959`: four selects declared
// `min-h-8`, `px-2 py-1` and `text-sm` and rendered none of them). Reusing a
// declared class adds nothing to any stylesheet, so rule 21 is satisfied.

/** What every cell control needs. */
interface CellBase {
  /** The control's accessible name. ≤ 3 words (B14 rule 33), from the
   *  catalogue. It is not drawn — the column header is what a sighted clerk
   *  reads. */
  label: string;
  /**
   * Why this cell cannot be typed in, or `undefined` when it can.
   *
   * ⚠ **BR-SHL-025 — A REASON AND NOT A BOOLEAN.** `step3a-add-row.png` greys
   * Asset and Size on a new row and says why in its own words: *"Asset and
   * Size stay empty until a service is chosen, because their lists depend on
   * it."* A greyed box with no reason is the clerk guessing.
   */
  blockedReason?: string;
  /** The DOM handle a walkthrough finds this cell by. */
  name: string;
}

/** One option of a cell dropdown. */
export interface CellOption {
  /** What posts. ⚠ **NEVER RENDERED** — B14 rule 31. */
  value: string;
  /** All a clerk ever sees. */
  label: string;
  disabled?: boolean;
}

/**
 * A DROPDOWN IN A CELL — Service, Asset, Size, Kind, Occupancy, Basis,
 * Channel, Applies to.
 *
 * ⚠ **THE EMPTY OPTION IS REQUIRED AND CARRIES ITS OWN WORDS** — the drawing's
 * *Choose a service*. A `<select>` with no empty option silently posts its
 * first value for a clerk who never touched it, which on the units table is a
 * meter nobody asked for.
 */
export function CellSelect(
  props: CellBase & {
    value: string;
    onChange: (value: string) => void;
    options: readonly CellOption[];
    /** The first option's words — *Choose a service*. ≤ 3 words. */
    placeholder: string;
    /**
     * **THE CHOSEN NAME IS NEVER CUT OFF** (`DEF-CUS-9093`). A cell select is
     * `width: 100%` of a column the table sizes, so in a wide table it is
     * squeezed below its own text — New Connect's Asset cell read *Fire
     * service li* at 1440. With `fit`, its minimum width is its widest
     * option's (`min-w-max`), so the TABLE gives the column room and, when the
     * whole row cannot fit, scrolls inside its own box (`EditableTable`'s
     * `overflow-x-auto`) rather than hiding the word. Opt-in, for the cells
     * whose option names are what a clerk reads to decide; a long list of
     * free-text names (a work-order template) keeps the column's width.
     */
    fit?: boolean;
  },
) {
  return (
    <select
      className={props.fit === true ? "input min-w-max" : "input"}
      aria-label={props.label}
      value={props.value}
      disabled={props.blockedReason !== undefined}
      title={props.blockedReason}
      data-cell={props.name}
      onChange={(event) => props.onChange(event.target.value)}
    >
      <option value="">{props.placeholder}</option>
      {props.options.map((option) => (
        <option key={option.value} value={option.value} disabled={option.disabled === true}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/** A TYPED CELL — the unit label, a reference. */
export function CellText(
  props: CellBase & {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  },
) {
  return (
    <input
      type="text"
      className="input"
      aria-label={props.label}
      value={props.value}
      placeholder={props.placeholder}
      disabled={props.blockedReason !== undefined}
      title={props.blockedReason}
      data-cell={props.name}
      onChange={(event) => props.onChange(event.target.value)}
    />
  );
}

/**
 * A COUNTED CELL — Qty, and nothing else in these drawings.
 *
 * ⚠ **IT IS A COUNT AND NEVER MONEY** (hard rule 2). The value is carried as a
 * STRING and handed back as one: this control parses nothing, multiplies
 * nothing and rounds nothing. `.input-num` is the declared class that
 * right-aligns it and puts it on tabular numerals, which is the same posture
 * `DataTable`'s numeric column takes.
 */
export function CellNumber(
  props: CellBase & {
    value: string;
    onChange: (value: string) => void;
    /** A count cannot be negative; the drawings' smallest is 1. */
    min?: number;
  },
) {
  return (
    <input
      type="number"
      inputMode="numeric"
      className="input input-num"
      aria-label={props.label}
      value={props.value}
      min={props.min}
      disabled={props.blockedReason !== undefined}
      title={props.blockedReason}
      data-cell={props.name}
      onChange={(event) => props.onChange(event.target.value)}
    />
  );
}

/** A TICK BOX IN A CELL — the units table's `Completes`. */
export function CellTick(
  props: CellBase & {
    checked: boolean;
    onChange: (checked: boolean) => void;
  },
) {
  return (
    <input
      type="checkbox"
      aria-label={props.label}
      checked={props.checked}
      disabled={props.blockedReason !== undefined}
      title={props.blockedReason}
      data-cell={props.name}
      onChange={(event) => props.onChange(event.target.checked)}
    />
  );
}

/**
 * A CELL THAT IS A FACT AND NOT A CONTROL — `step4-charges.png`'s `Each` and
 * `Amount`, `step5-review.png`'s `When` and `State`.
 *
 * ⚠ **A READ-ONLY VALUE IS NOT A DISABLED INPUT, AND THAT IS A PO RULING.**
 * Verbatim, on the plan facts: *"we dont display it like this at other places
 * we will ahve to follow UI rules"*. A disabled box says *you could type here
 * but not yet*; a fact says *this is what it is*. `FactBlock` is the same
 * ruling one level up, for a block of them.
 *
 * ⚠ **IT DISPLAYS WHAT IT IS GIVEN.** A money figure arrives through
 * `MoneyCell`, which owns display precision (hard rule 2 — DISPLAY 2
 * decimals); nothing here formats, multiplies or rounds.
 */
export function CellStatic(props: { children: ReactNode; name: string }) {
  return (
    <span className="text-base text-text" data-cell={props.name}>
      {props.children}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the NEW CONNECT REDESIGN of 2026-09-28 · 05-prototype/new-connect-redesign-2026-09-28/{step3-units,step3a-add-row,step3b-add-work-order,step4-charges,step5-review}.png · B14 rules 15, 17, 20, 21, 31, 33, 36, 42, 43, 44 · BR-SHL-025 · hard rule 2
// generated: 2026-09-28 by lane COMPONENTS
// checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E=the five New Connect step lanes consume it F✔ G✔ H=n/a
// gates: tsc · vitest src/components/TableArray.dom.test.tsx · routeBUtilities (this file is on src/styles/route-b-migrated.txt) · G31
// exceptions:
//   E1 the row-highlight drawn around the new row in `step3a-add-row.png` and
//      `step3b-add-work-order.png` is NOT built. Both are explainer frames
//      titled "The new row" and the outline points at the row the prose is
//      about; nothing says the product draws it. Stated rather than invented
//      (UI method §2.5).
//   E2 ⊕ **`footerTrailing` LANDED 2026-09-29 WITH ITS CALLER** — the step-4
//      lane, `NewConnectChargesStep.tsx`'s `Total · Paid now · Remaining`
//      block, exactly as this exception said it would. G13 is satisfied
//      because the prop now has a non-test caller. **`footerFact` is STILL
//      NOT a prop**: no step draws one yet, and the same rule applies to it.
//      See §2's note, which is left standing as the reasoning.
//   E3 `features/customers/disconnect/DisconnectTableArray.tsx` is a second
//      implementation of this frame and is NOT merged into it here: one
//      attribute name (`data-array-add` vs `data-array-action`) is read by
//      four assertions in a live wizard's test and four lines of its
//      walkthrough, so merging them is a change to that wizard rather than to
//      the kit. Reported to the coordinator for its own row.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
