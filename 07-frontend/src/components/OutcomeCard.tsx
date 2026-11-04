// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a, block 8 (Sentence)
//           of the twelve. Screens: RBS-006-R4 (*Read this aloud*) · R6 (the
//           stop card) · R11 · and every setup renderer's *Produces:* callout
// Rules:    B14 rule 36 · B14 rule 21 + its per-file clause · B14 rule 32 (one
//           sentence per section) · B14 rule 33 (LABEL ≤ 3 words · FACT ≤ 6 ·
//           INSTRUCTION ≤ 6 per sentence · CONSEQUENCE ≤ 6 per sentence, at
//           most two · RATIONALE = zero words on screen)
// Tests:    src/components/OutcomeCard.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 5 §4
//           and Part 4 §1 (the word-budget decision this component WAITS on) ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **ONE CARD, THREE TONES, AND THE KIT COVERED NONE OF THEM.**
// `09-component-inventory.md` Part 5 §4 measured it: *"`WarningBox`, `Panel` and
// `ConsequenceBox` each cover part of this and none covers the shape."* The
// shape is a left rail, a small uppercase label above, and one block of copy —
// `RBS-006-R4`'s green **READ THIS ALOUD** with the sentence a clerk says down
// the phone, `RBS-006-R6`'s red stop card, `RBS-006-R11`'s muted notice.
//
// ⚠ **`WarningBox` IS NOT THIS AND MUST NOT BE STRETCHED INTO IT.** Its own
// docstring refuses an `info` tone on the stated ground that *"a box that is
// sometimes merely interesting is a box people stop reading"*. That is right for
// a DATED WARNING and wrong here: the Sentence block's commonest tone is the
// quiet one — what the customer receives, read aloud, nothing to act on. Two
// components, two jobs; widening the warning box would have cost it the property
// its docstring is defending.
//
// ⚠ **THE WORD BUDGET IS A STATED ABSENCE, NOT AN OVERSIGHT.**
// Part 4 §1 measured the setup renderer's *Produces:* callout at **14 to 88
// words, median 25.5, all 28 over rule 33's six-word cap**, and left the
// decision open between *(a) it is a FACT list and must be cut* and *(b) it is
// not clerk-facing copy at all but a template-library description*. That
// decision *"belongs in the module's `02-business-rules.md`"* and is owed by
// the wave that draws `RBS-004`'s Outcome box (`C3`), not by this component:
// the same card renders `RBS-006-R4`'s four-word **READ THIS ALOUD** label and
// a quoted sentence a clerk speaks, which no cap governs. **So this component
// counts nothing and truncates nothing** — a component that silently trimmed
// copy would make the divergence invisible instead of settling it, and the
// measurement above is what makes it settleable.
import type { ReactNode } from "react";

/**
 * `success` — *What the customer receives*, *Read this aloud*, *Produces:*.
 *             The commonest tone: something happened or will happen and it is
 *             fine.
 * `danger`  — the **stop card**. `RBS-006-R6` — the run found a reason not to
 *             proceed and the reader must act.
 * `muted`   — a notice. Context that is true and needs nothing.
 */
export type OutcomeTone = "success" | "danger" | "muted";

// ⚠ Whole strings per tone, never an interpolation — and each asked of the real
// Tailwind compiler rather than read off the palette (DEF-SHL-4281).
// `runbookKitClasses.test.ts` compiles all three and fails on a colour this
// theme has not declared.
const RAIL_TONE: Record<OutcomeTone, string> = {
  success: "border-l-success-500 bg-success-100",
  danger: "border-l-danger-500 bg-danger-100",
  // The muted tone gets NO tint. `neutral-100` is very nearly the page ground,
  // so a filled muted card would read as a rendering accident rather than as a
  // deliberate quiet; the rail alone carries it.
  muted: "border-l-neutral-400 bg-transparent",
};

const LABEL_TONE: Record<OutcomeTone, string> = {
  success: "text-success-700",
  danger: "text-danger-700",
  muted: "text-neutral-600",
};

export interface OutcomeCardProps {
  tone: OutcomeTone;
  /** The small uppercase label above the copy — *READ THIS ALOUD*, *PRODUCES*.
   *  Three words or fewer (B14 rule 33's LABEL cap). Omit it where the copy
   *  speaks for itself; `RBS-006-R11`'s notice has none. */
  label?: string;
  /** The copy. A `ReactNode` because `RBS-006-R6`'s stop card bolds the half
   *  that is the instruction, and because money and dates inside it arrive
   *  already formatted by `MoneyCell` and `DateCell` — this card must never
   *  format either (BR-SHL-023, one formatting path). */
  children: ReactNode;
  /** What a reader may do about it. A stop card with no way past it is a dead
   *  end; `RBS-006-R6` draws the fix route here. */
  action?: ReactNode;
}

/**
 * The Sentence block. `RBS-006-R4` region 6, `RBS-006-R6`'s stop card.
 *
 * `role="note"` on every tone, including danger: this is the report of a run
 * that has already finished, not an alert that just fired. A screen reader
 * reaches it in the page's own order.
 */
export function OutcomeCard(props: OutcomeCardProps) {
  return (
    <div
      className={`${RAIL_TONE[props.tone]} flex max-w-[720px] flex-col gap-2 border-l-4 px-4 py-3`}
      role="note"
      data-outcome=""
      data-outcome-tone={props.tone}
    >
      {props.label !== undefined && (
        <span
          className={`${LABEL_TONE[props.tone]} text-xs font-extrabold tracking-wider uppercase`}
          data-outcome-label=""
        >
          {props.label}
        </span>
      )}
      <div className="text-md text-neutral-900" data-outcome-body="">
        {props.children}
      </div>
      {props.action !== undefined && (
        <div className="flex gap-2" data-outcome-action="">
          {props.action}
        </div>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1a · 09-component-inventory.md Part 5 §4 · frames RBS-006-R4/R6/R11
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the Sentence block composes it) F✔ G✔ H=n/a
// gates: vitest src/components/OutcomeCard.test.tsx · runbookKitClasses · routeBUtilities · G31 · tsc
// exceptions: the word budget is a STATED ABSENCE (Part 4 §1), owed by wave C3 which draws the setup renderer's Produces box — this component counts and truncates nothing, deliberately
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
