// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a, block 3 of the
//           twelve. Screens: RBS-006-R1 (ten cells) · R2 (nine) · R6 · R13 ·
//           and RBS-005.8's refusal shape
// Rules:    B14 rule 36 · B14 rule 21 + its per-file clause · B14 rule 31 (no
//           database id, rule number or route is ever the visible value of a
//           field) · B14 rule 32 (one sentence per section) ·
//           `BR-RBS-027` / `RB-036` (a `requires` Check that fails leaves every
//           later step reading **Never reached**)
// Tests:    src/components/Chain.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 5 §2 ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **THE TEN-CELL CHAIN, RED AT THE EARLIEST FAILURE.** `RBS-006-R1` draws it:
// ten cells wrapping across the width, each carrying its position in small grey
// above its name, a coloured top border, and a danger tint where the step
// failed. It is wave C's *goal a clerk can see* — *Can we bill?* runs and the
// result draws a ten-cell chain, red at the earliest failure.
//
// ⚠ **A `notReached` CELL SAYS SO RATHER THAN SITTING BLANK, AND THAT IS THE
// WHOLE REASON THIS IS A COMPONENT.** `RB-036` and `BR-RBS-027`: when a
// runbook's `requires` Check fails, every later step reads **Never reached** —
// and a blank cell and a passed cell look identical at a glance, which is how a
// clerk concludes a step was fine when it never ran. The state is drawn as a
// word, in the reader's own language, handed in by the caller.
//
// ⚠ **THE POSITION IS A COUNTER, NOT AN ID.** B14 rule 31 forbids a database id
// as the visible value of a field; `1`…`10` here is the step's place in the
// chain and the sheets draw it, so it stays — but a step id, a rule number or a
// route must never reach `label`. The block that composes this is where that is
// enforced, because only it knows what it is holding.
import type { ReactNode } from "react";

/**
 * What happened to one step.
 *
 * `ok`         — it ran and it was clear.
 * `bad`        — it ran and it found the blocker. The cell NAMES it.
 * `notReached` — it never ran, because something earlier stopped the run.
 * `pending`    — it has not run yet. `RBS-004`'s step list draws this as
 *                *waiting*; a finished run never carries one.
 * `noted`      — it ran and found something a person should see that does
 *                NOT stop anything: *2 documents not checked*. ⊕ Added
 *                2026-09-23 (`DEF-CUS-6350`) under B14 rule 36/43 — *where the
 *                kit lacks a piece a screen needs, add it to the kit* — for the
 *                Approve window's amber *noted, not blocking* rows. Amber, never
 *                red: red is a blocker, and a notice drawn as one teaches a
 *                clerk to stop reading the colour.
 */
export type ChainCellState = "ok" | "bad" | "noted" | "notReached" | "pending";

// ⚠ Whole strings per state — never `border-t-${state}`. And every token was
// asked of the real Tailwind compiler rather than read off the palette
// (DEF-SHL-4281): `runbookKitClasses.test.ts` compiles each of these and fails
// on a colour this theme has not declared, which is the failure `WarningBox.tsx`
// is shipping today with every check green over it.
const CELL_STATE: Record<ChainCellState, string> = {
  ok: "border-t-success-500 bg-neutral-100",
  bad: "border-t-danger-500 bg-danger-100",
  noted: "border-t-warning-500 bg-warning-100",
  // `notReached` is deliberately the same grey as `pending`. It did not fail —
  // nobody knows what it would have done, and colouring it red would report a
  // blocker the run never found.
  notReached: "border-t-neutral-400 bg-neutral-100",
  pending: "border-t-neutral-400 bg-neutral-100",
};

export interface ChainCell {
  /** Stable key for React. Never rendered — B14 rule 31. */
  id: string;
  /** The step's place in the chain, drawn small and grey above the name. */
  position: number;
  /** The step's name, already translated: *Rate coverage* · *Account chain*. */
  label: string;
  state: ChainCellState;
  /** What a `bad` cell says. `RBS-006-R1`'s red *Tax* cell is the blocker's
   *  home — *a red cell names the blocker*, and a `notReached` cell carries its
   *  own **Never reached** here rather than sitting blank. Six words or fewer
   *  (B14 rule 33's refusal cap). */
  note?: ReactNode;
}

export interface ChainProps {
  cells: readonly ChainCell[];
  /** What the whole chain is, for a screen reader: *Ten steps, three failed.*
   *  Already translated. */
  label: string;
}

/**
 * The Chain block. `RBS-006-R1` region 3.
 *
 * An ordered list, because that is what it is — the steps ran in this order and
 * a screen reader should say so. It wraps rather than scrolls: ten cells at
 * 160px each do not fit a narrow window, and a chain you have to scroll to see
 * the red end of is a chain that has stopped answering its own question.
 */
export function Chain(props: ChainProps) {
  return (
    <ol
      // ⚠ A GRID, NOT `flex flex-wrap`, AND ONLY LOOKING FOUND IT.
      // The first draft was `flex flex-wrap` with `flex-1` on each cell, which
      // passes every assertion in `Chain.test.tsx` — ten cells, three red, the
      // blockers named — and renders WRONG: flex distributes the free space
      // along each line, so the LAST line stretches. At 1132px the ten cells
      // broke 7 + 3 and *Reads* drew 390px wide beside a 158px *Services*.
      // `RBS-006-R1` draws every cell at one width, wrapped cells included.
      // A grid track sizes the columns once for the whole grid, so the last row
      // keeps the first row's width and simply ends early.
      // Found by rendering it in a real browser and reading the picture — hard-won
      // law 6, and nothing else in this repo could have seen it: jsdom has no
      // layout engine, so `toContain("flex-1")` is unfalsifiable there.
      className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-2 p-0"
      aria-label={props.label}
      data-chain=""
    >
      {props.cells.map((cell) => (
        <li
          key={cell.id}
          className={`${CELL_STATE[cell.state]} border border-neutral-300 border-t-4 px-3 py-2`}
          data-chain-cell=""
          data-chain-state={cell.state}
        >
          <span className="block text-xs text-neutral-600 tabular-nums">{cell.position}</span>
          <span className="block text-base text-neutral-900">{cell.label}</span>
          {cell.note !== undefined && (
            <span className="block text-xs text-neutral-700" data-chain-note="">
              {cell.note}
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1a · 09-component-inventory.md Part 5 §2 · frames RBS-006-R1/R2/R6/R13
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the Chain block composes it) F✔ G✔ H=n/a
// gates: vitest src/components/Chain.test.tsx · runbookKitClasses · routeBUtilities · G31 · tsc
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
