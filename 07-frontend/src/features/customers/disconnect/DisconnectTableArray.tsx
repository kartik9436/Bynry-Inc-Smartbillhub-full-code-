// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 (`DEF-CUS-6750`…`DEF-CUS-6753`, MAINTENANCE — `12-governance/22-product-maintenance-process.md`) — **THE TABLE ARRAY, ONCE.** The disconnect wizard's
//           four steps and their four master variants draw the same collection
//           shape EIGHT times; this is the one implementation all eight use.
// Rules:    **B14 rule 43** (a piece of UI is built as a COMPONENT; standalone
//           code inside a page is not reuse — PO: *"make them coponents - dont
//           write stand alone code, engineer it"*) · **rule 36** (extend the
//           kit, never copy it into a screen) · **rule 20** (ONE table type) ·
//           rule 21 (Tailwind utilities; this file is on
//           `src/styles/route-b-migrated.txt`) · rule 33 (a label ≤ 3 words, a
//           fact ≤ 6) · rule 15 (icons for row actions)
// Tests:    ../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY THIS WRAPS `EditableTable` RATHER THAN BEING A SECOND TABLE
// ══════════════════════════════════════════════════════════════════════════
// B14 rule 20 is ONE table type and §13 of the UI method is explicit that a
// second table is a defect rather than a contribution. `EditableTable` already
// holds everything the eight drawn collections need — rows a clerk may remove,
// an inline add row, a read-only mode for the same rows shown as a RECORD, a
// per-row refusal with its reason, and the A12 scroll box. What it does not
// hold is the FRAME the drawings put around it: a panel, a heading, a
// right-hand fact and an add row that carries a running fact beside its button.
//
// **So this adds the frame and delegates the table.** Every drawn collection is
// one call: step 1's `Which services`, step 2's `What was checked` and the
// master's `Occupants who hold a protection`, step 3's `Who goes` and the
// master's `Notice`, and step 4's read-only repeats of two of them.
//
// ⚠ **`numbered={false}` AND `reorderable={false}` ON EVERY CALL, AND BOTH ARE
// THE DRAWING'S DECISION RATHER THAN TASTE.** None of the eight draws a `#`
// column and none of them has an order that means anything — whether Water sits
// above Sewer changes nobody's supply — so a drag handle and two arrows would
// be three controls claiming a fact the data does not hold. That is hard-won
// law 2 wearing its other face: not a dead control, but a live one that means
// nothing.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE RUNNING FACT IS THE POINT OF THE ADD ROW
// ══════════════════════════════════════════════════════════════════════════
// Every drawn add row is a button and a sentence: `+ Add a service` ·
// *One service will be cut* · `+ Add a check` · *Four more available* ·
// `+ Add a service point` · *One work order will be raised*. The sentence is
// **derived from the rows above it**, never typed, so a clerk who changes a
// treatment sees the consequence change under their hand. It is a FACT and is
// capped at six words (B14 rule 33), and it is NOT rationale — it says what
// will happen, never why the screen works this way.
import type { ReactNode } from "react";

import { Button } from "@/components/Button";
import { EditableTable } from "@/components/EditableTable";
import type { EditableColumn } from "@/components/EditableTable";
import { Panel } from "@/components/Panel";

export type DisconnectArrayColumn<Row> = EditableColumn<Row>;

interface Base<Row> {
  /** The panel's heading — *Which services*, *What was checked*, *Who goes*.
   *  Three words or fewer (B14 rule 33). */
  title: string;
  /**
   * The fact on the heading's right — *One decision per service*, *Nothing here
   * blocks the cut*, *3 of 25*.
   *
   * ⚠ **IT IS A FACT AND NOT A CAPTION.** `Nothing here blocks the cut` states
   * what `BR-CUS-1096` makes true; it does not explain the ruling, which would
   * be rationale and is zero words on screen.
   */
  fact?: ReactNode;
  columns: readonly DisconnectArrayColumn<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row, index: number) => string;
  /** B14 rule 17 — what is missing AND how to fill it; the add row under it is
   *  the how. */
  emptyText: string;
  /** The DOM handle a walkthrough finds this collection by. */
  collection: string;
  /** Anything that belongs under the table INSIDE the same panel — step 2's
   *  `What happened` box. */
  children?: ReactNode;
}

type Editable<Row> = Base<Row> & {
  readOnly?: false;
  onChange: (rows: Row[]) => void;
  /** The ✕'s accessible name. */
  removeLabel: string;
  /** `+ Add a service`. Absent draws no add row — a collection a clerk may
   *  remove from but not extend. */
  addLabel?: string;
  onAdd?: () => void;
  /** The running fact beside the add button. Derived from the rows. */
  addFact?: ReactNode;
  /**
   * Why `+ Add a …` cannot act, or `undefined` when it can.
   *
   * ⚠ **`BR-SHL-025` — A CONTROL THAT CANNOT ACT IS DISABLED AND SAYS WHY, NEVER
   * HIDDEN.** Step 1 runs out of services to add once every service on the
   * account is already a row, and a button that silently vanished at that point
   * would read as the product having lost a feature.
   */
  addBlockedReason?: string;
};

type ReadOnly<Row> = Base<Row> & {
  readOnly: true;
  onChange?: undefined;
  removeLabel?: undefined;
  addLabel?: undefined;
  onAdd?: undefined;
  addFact?: undefined;
  addBlockedReason?: undefined;
};

export type DisconnectTableArrayProps<Row> = Editable<Row> | ReadOnly<Row>;

/**
 * One collection of the disconnect wizard, drawn the way all eight are drawn.
 *
 * ⚠ **THE READ-ONLY SHAPE IS THE SAME COMPONENT AND THAT IS ITEM 3.5.** Step
 * 3's field work *"repeats on the review screen"*, and a second table drawn
 * beside this one is how one set of rows comes to read two different ways on
 * two screens of one wizard. `EditableTable`'s own `readOnly` was added for
 * exactly this, one kit level down.
 */
export function DisconnectTableArray<Row>(props: DisconnectTableArrayProps<Row>) {
  const addRow =
    props.readOnly === true || props.addLabel === undefined ? undefined : (
      <>
        <Button
          variant="secondary"
          size="sm"
          onClick={props.onAdd}
          disabled={props.addBlockedReason !== undefined}
          // BR-SHL-025: the reason is READABLE rather than merely implied by a
          // greyed control.
          title={props.addBlockedReason}
          data-array-add={props.collection}
        >
          {props.addLabel}
        </Button>
        {props.addFact !== undefined && (
          <span className="text-base text-neutral-700" data-array-fact={props.collection}>
            {props.addFact}
          </span>
        )}
      </>
    );

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
      {props.readOnly === true ? (
        <EditableTable<Row>
          readOnly
          caption=""
          numbered={false}
          reorderable={false}
          columns={props.columns as EditableColumn<Row>[]}
          rows={props.rows as Row[]}
          rowKey={props.rowKey}
          emptyText={props.emptyText}
          data-collection={props.collection}
        />
      ) : (
        <EditableTable<Row>
          caption=""
          numbered={false}
          reorderable={false}
          columns={props.columns as EditableColumn<Row>[]}
          rows={props.rows as Row[]}
          rowKey={props.rowKey}
          emptyText={props.emptyText}
          addRow={addRow}
          onChange={props.onChange}
          labels={{ remove: props.removeLabel }}
          data-collection={props.collection}
        />
      )}
      {props.children}
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the DISCONNECT WIZARD REBUILD of 2026-09-25 (`DEF-CUS-6750`…`DEF-CUS-6753`, MAINTENANCE — `12-governance/22-product-maintenance-process.md`) · B14 rules 15, 17, 20, 21, 33, 36, 43 · BR-SHL-025
// generated: 2026-09-25 by lane WIZARD
// gates: tsc · vitest src/features/customers/DisconnectWizard.test.tsx ·
//        routeBUtilities (this file is on src/styles/route-b-migrated.txt)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
