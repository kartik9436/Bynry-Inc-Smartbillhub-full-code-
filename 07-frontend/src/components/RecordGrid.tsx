// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a. The `Records`
//           block's GRID DISPLAY MODE — the same records the table draws, laid
//           out as cells instead of rows.
//           Screens: the coverage grid (runbook 23). Its SETUP sheet is
//           `RBS-004-R24`; its RESULT frame is **not drawn** — see below
// Rules:    B14 rule 36 · B14 rule 21 + its per-file clause · B14 rule 31 (no
//           database id is ever the visible value of a field) · B14 rule 17
//           (an empty state says what is missing and what fills it) ·
//           hard-won law 2 (built is not wired — and its 2026-09-05 mirror, a
//           live screen behind a dead control)
// Tests:    src/components/RecordGrid.dom.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 1
//           row 4 · 04-docs/05-modules/17-runbooks/08-screen-layouts.md (the
//           stamped absence — this component has no build sheet) ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **WHY THIS IS PHASE-1 WORK AND NOT PHASE-5 WORK.** `10-execution-plan.md`
// wave C task C1a says it in one line: *"phase 2's coverage grid IS that grid
// mode"*, so deferring it would make `EP-RBS-02` unbuildable. It is one
// display mode of the `Records` block, not a screen: the same records, the same
// pagination, drawn as cells.
//
// ⚠ **THERE IS NO BUILD SHEET FOR IT, AND THAT IS STATED RATHER THAN QUIETLY
// INVENTED.** `RBS-004-R24` draws the coverage grid's SETUP; there is no
// `RBS-006-R24` among the 48 result sheets, exactly as wave `F1` records for
// runbook 23 — *"its result screen is NOT DRAWN in the source, so there is no
// build sheet to compare against and law 6 cannot be performed."* What this
// component is built from is the one sentence the pack does give, in
// `RBS-004-R24`'s own Outcome box: *"A grid: 21 clean · 2 estimated · 2 refused,
// each cell opening that account's test bill with the engine's own refusal
// sentence."* Every element here traces to that sentence and nothing else is
// added. The absence is stamped in `08-screen-layouts.md` so the lane that
// finally draws the frame corrects the code rather than rediscovering the gap.
//
// ⚠ **EVERY CELL IS A REAL DOOR, AND THE MIRROR OF LAW 2 IS WHY THAT IS A
// REQUIREMENT AND NOT A FEATURE.** *"each cell opening that account's test
// bill"* — so `to` is REQUIRED on every cell. `DEF-CWP-3925` is the case
// against the alternative: the customer portal's front page had two working
// doors out of eight, five cards and three nav words all still refusing over
// holds that had expired days earlier, and **G13 cannot see it** — it asks
// whether a prop is passed, never whether a refusal is still true. A grid of
// 25 cells that do not open is that defect twenty-five times over, so this
// component cannot express one: there is no `disabled` cell and no cell without
// a destination.
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

/**
 * How one record came out. Three states, and they are the coverage grid's own
 * words: *clean*, *estimated*, *refused*.
 *
 * The names are the OUTCOME rather than a severity, for the same reason
 * `VerdictTone` is: an estimated bill is not a lesser failure, it is a
 * different fact.
 */
export type RecordGridState = "clean" | "estimated" | "refused";

// ⚠ Whole strings per state, never an interpolation — and every token asked of
// the real Tailwind compiler rather than read off the palette (DEF-SHL-4281).
const CELL_STATE: Record<RecordGridState, string> = {
  clean: "border-success-500 bg-success-100 text-success-700",
  estimated: "border-warning-500 bg-warning-100 text-warning-700",
  refused: "border-danger-500 bg-danger-100 text-danger-700",
};

export interface RecordGridCell {
  /** Stable key. Never rendered — B14 rule 31. */
  id: string;
  /** What a reader sees in the cell: the account's NAME, never its id
   *  (B14 rule 31, and `RBS-004`'s Activity tab carries the same constraint). */
  label: string;
  state: RecordGridState;
  /** Where the cell opens — *that account's test bill*. REQUIRED; see the
   *  header for why there is no cell without one. */
  to: string;
  /** The engine's own sentence, on a refused cell. It is the title AND the
   *  accessible description, so the reason is reachable without a hover — a
   *  refusal a mouse-only reader can get to is a refusal half the readers
   *  cannot. Six words or fewer (B14 rule 33). */
  reason?: string;
}

export interface RecordGridProps {
  cells: readonly RecordGridCell[];
  /** What the grid is, for a screen reader: *25 accounts priced.* Already
   *  translated. */
  label: string;
  /** B14 rule 17: what is missing and the action that fills it. REQUIRED, so a
   *  grid with nothing in it cannot render as a blank rectangle. */
  empty: ReactNode;
}

/**
 * The `Records` block in grid mode.
 *
 * A list, because that is what it is — a set of records with no meaningful
 * left-to-right order. `grid-cols-[repeat(auto-fill,minmax(120px,1fr))]` wraps
 * to the window rather than to a fixed 5×5, so 25 accounts and 400 accounts
 * both lay out and neither needs a second component.
 */
export function RecordGrid(props: RecordGridProps) {
  if (props.cells.length === 0) {
    return (
      <div
        className="border border-dashed border-neutral-400 px-4 py-6 text-center text-md text-neutral-700"
        data-record-grid=""
        data-record-grid-empty=""
      >
        {props.empty}
      </div>
    );
  }
  return (
    <ul
      className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-2 p-0"
      aria-label={props.label}
      data-record-grid=""
    >
      {props.cells.map((cell) => (
        <li key={cell.id}>
          <Link
            to={cell.to}
            className={`${CELL_STATE[cell.state]} flex min-h-[52px] flex-col justify-center border px-2 py-1 text-base no-underline`}
            title={cell.reason}
            data-record-cell=""
            data-record-state={cell.state}
          >
            <span className="truncate">{cell.label}</span>
            {cell.reason !== undefined && (
              <span className="text-xs" data-record-reason="">
                {cell.reason}
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1a · 09-component-inventory.md Part 1 row 4 · RBS-004-R24's Outcome box (no result frame exists)
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the Records block's grid mode) F✔ G✔ H=n/a
// gates: vitest src/components/RecordGrid.dom.test.tsx · runbookKitClasses · routeBUtilities · G31 · tsc
// exceptions: NO BUILD SHEET EXISTS for the coverage grid's result — law 6 cannot be performed against a frame that was never drawn. Stamped in 08-screen-layouts.md; wave F1 draws the frames for runbook 23 and this component is corrected against them then.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
