// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6350 — the Approve window lists every check it runs, one row
//           each, ✓ / ✗ / ! (PO 2026-09-23: *"we are not showing all this issues
//           to user when they are processing hence they dont understand what is
//           happening"*).
// Rules:    B14 rule 36 + rule 43 (compose the kit; where it lacks a piece, ADD
//           IT TO THE KIT as its own component) · rule 21 (Tailwind utilities,
//           no stylesheet class; this file is on route-b-migrated.txt) · rule
//           31 (nothing internal on screen — the caller hands in words) · rule
//           33 (a label ≤ 3 words, a fact ≤ 6 — the caller's catalogue holds
//           them) · BR-SHL-025 (a blocked row says why, in words)
// Tests:    src/components/CheckList.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS A NEW KIT COMPONENT AND NOT `Chain`
// ══════════════════════════════════════════════════════════════════════════
// **The STATE vocabulary is `Chain`'s, imported rather than restated** —
// `ok` · `bad` · `noted` · `notReached` — so *what a check can say about
// itself* has one definition in the product, and the amber `noted` tone was
// added THERE (with its test) before it was used here.
//
// **The SHAPE is not `Chain`'s, and bending `Chain` to it would change a
// screen the PO has already seen.** `Chain` draws a run of STEPS: numbered
// cells in a wrapping grid, a coloured top border, the position above the
// name — *"the steps ran in this order and a screen reader should say so"*.
// A list of checks is none of that: the rows are independent (a free unit and
// a paid fee do not follow from each other), there is no position to draw,
// and the approved layout is one line per check — glyph, name, what it found —
// read top to bottom in a dialog, with a control beside the row that needs
// one (*Record that I searched*, *Same property*). A `layout` prop on `Chain`
// would be two visual decisions under one name, which is the collision B14
// rule 36 was ratified to stop.
//
// ⚠ **THE GLYPH IS NEVER THE ONLY SIGNAL.** ✓ ✗ ! are drawn for a sighted
// reader and hidden from a screen reader, which hears the caller's own word
// for the state instead (`stateLabels`) — a glyph read aloud as *"heavy check
// mark"* tells nobody anything, and colour alone fails a colour-blind clerk.
import type { ReactNode } from "react";

import type { ChainCellState } from "./Chain";

/** A check's outcome — `Chain`'s vocabulary. `pending` is not offered: a check
 *  list is drawn after the checks ran. */
export type CheckState = Exclude<ChainCellState, "pending">;

export interface CheckRow {
  /** Stable key for React and for a walkthrough. Never rendered (B14 rule 31). */
  id: string;
  /** The check's name, already translated — three words or fewer. */
  label: string;
  state: CheckState;
  /** What it found, already translated — six words or fewer. */
  fact: ReactNode;
  /** A control that answers this row — rendered under the fact. */
  action?: ReactNode;
}

export interface CheckListProps {
  rows: readonly CheckRow[];
  /** What the list is, for a screen reader. Already translated. */
  label: string;
  /** The reader's own word for each state, e.g. *Passed* · *Blocked*. */
  stateLabels: Record<CheckState, string>;
}

// ⚠ Whole strings per state — never `text-${tone}-700`. Tailwind's scanner
// cannot see an interpolated class, and `routeBUtilities.test.ts` compiles
// every one of these against the real theme (the `Chain` discipline).
const GLYPH: Record<CheckState, string> = { ok: "✓", bad: "✗", noted: "!", notReached: "–" };
const GLYPH_TONE: Record<CheckState, string> = {
  ok: "text-success-700",
  bad: "text-danger-700",
  noted: "text-warning-700",
  notReached: "text-neutral-600",
};
const FACT_TONE: Record<CheckState, string> = {
  ok: "text-neutral-900",
  bad: "font-semibold text-danger-700",
  noted: "text-neutral-900",
  notReached: "text-neutral-600",
};

/**
 * One row per check: ✓ passed · ✗ the blocker, named · ! noted, not blocking ·
 * – not reached, because an earlier check stopped it.
 */
export function CheckList(props: CheckListProps) {
  return (
    <ul className="m-0 list-none p-0" aria-label={props.label} data-check-list="">
      {props.rows.map((row) => (
        <li
          key={row.id}
          className="flex items-baseline gap-3 border-b border-b-divider py-2 text-md last:border-b-0"
          data-check={row.id}
          data-check-state={row.state}
        >
          <span
            aria-hidden="true"
            className={`w-4 shrink-0 text-center font-bold ${GLYPH_TONE[row.state]}`}
          >
            {GLYPH[row.state]}
          </span>
          <span className="sr-only">{props.stateLabels[row.state]}</span>
          <span className="w-28 shrink-0 text-neutral-700">{row.label}</span>
          <div className="min-w-0 flex-1">
            <span className={FACT_TONE[row.state]} data-check-fact="">
              {row.fact}
            </span>
            {row.action !== undefined && (
              <div className="mt-2 flex flex-wrap gap-2" data-check-action="">
                {row.action}
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6350 · decision log 2026-09-23 §4 (*"checks first as ✓ / ✗ / ! rows"*) · B14 rules 21, 31, 33, 36, 43
// generated: 2026-09-23 by lane APPROVE-CHECKS
// checklist: A=n/a B✔ C✔ D=n/a E✔(ApproveChecksModal renders it) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/CheckList.test.tsx · routeBUtilities (on src/styles/route-b-migrated.txt)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
