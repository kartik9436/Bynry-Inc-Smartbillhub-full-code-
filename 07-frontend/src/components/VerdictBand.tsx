// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a, block 1 of the
//           twelve. Screens: RBS-006-R2 · R3 · R9 · R12 · R13 (five runbooks)
// Rules:    B14 rule 36 (compose the kit — this is a KIT component, not a
//           runbooks-local shape) · B14 rule 6 (a commit button that CLOSES or
//           SENDS is the danger tier, never the standard primary) · B14 rule 21
//           + its per-file clause · B14 rule 33 (a refusal caps at six words) ·
//           B14 rule 34 (**Recorded** / **In the books**, the one pair) ·
//           `BR-RBS-020` (the report is composed at close and FROZEN)
// Tests:    src/components/VerdictBand.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 5 §1
//           (which named this before any code existed) ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **THE ONE-WORD ANSWER, ABOVE EVERYTHING ELSE ON THE PAGE.**
// `RBS-006-R9` draws it exactly: a filled chip reading **NOT BALANCED**, then
// *6 of 9 steps clear* in bold, then *Tax off by $14.25 · $312.00 unapplied ·
// 3 bank lines unmatched* in grey — and on the balanced variant the same band
// reads **BALANCED**, *9 of 9 steps clear*, with **Close period ✓** on the right.
//
// ⚠ **THE WORD IS THE RUNBOOK'S, NOT THIS COMPONENT'S.** Across the five sheets
// it is *No-go*, *Not balanced*, *Balanced*, *Found*, *Not ready* and
// *14 eligible* — six different words for three tones. A component that mapped
// tone → word would have to know every runbook, which is the exact thing
// `12-the-contract.md` says a renderer must not do: *"the renderer knows twelve
// names"* and nothing about runbook 9. So the caller hands the word in,
// already translated, and the tone only colours it.
//
// ⚠ **THE COMMIT BUTTON IS THE DANGER TIER AND THAT IS NOT DECORATION.**
// B14 rule 6 reserves it for a commit a person must think about, and
// `RBS-006-R9`'s own caption says why: *"Only now does the Close button enable —
// and it is a person, named in the audit, who presses it."* This component does
// not decide when it enables (`BR-RBS-030`: closing a period stays a named
// person's act, `OQ-RBS-1736` CLOSED 2026-09-06) — it renders the control the
// caller hands it, so the enabling condition lives with the runbook that owns it.
import type { ReactNode } from "react";

/**
 * How the run came out. Three tones, and they are the run's OUTCOME rather than
 * a severity: `warning` is *"14 eligible · 9 removed since the letter"* — not a
 * problem, a number that needs a person to look.
 */
export type VerdictTone = "success" | "warning" | "danger";

// ⚠ WHOLE STRINGS PER TONE, NEVER `bg-${tone}-500`. Tailwind's scanner cannot
// see an interpolation, and a class it never emitted renders as NOTHING while
// `toContain` still passes.
//
// ⚠ AND EVERY TOKEN BELOW WAS ASKED OF THE REAL COMPILER, NOT READ OFF THE
// PALETTE (DEF-SHL-4281). `WarningBox.tsx` asks for `border-danger`, which this
// theme does not declare, so its danger tone draws with no colour at all — and
// the check written for exactly that shape is green over it, because its
// `kit_constant` grammar cannot see a constant with a TYPE ANNOTATION like this
// one. `runbookKitClasses.test.ts` is this kit's own answer: it compiles every
// string in every one of these maps and fails on a token the theme has not got.
const CHIP_TONE: Record<VerdictTone, string> = {
  success: "bg-success-500 text-neutral-100",
  warning: "bg-warning-500 text-neutral-900",
  danger: "bg-danger-500 text-neutral-100",
};

export interface VerdictBandProps {
  /** The one bold word, already in the reader's language. `No-go` · `Balanced`
   *  · `Not ready` — the runbook's own word, never derived from the tone. */
  word: string;
  tone: VerdictTone;
  /** The count line: *6 of 9 steps clear*. Bold, beside the word. */
  count: ReactNode;
  /** The detail line: *Tax off by $14.25 · $312.00 unapplied*. One sentence
   *  (B14 rule 32); money in it arrives already through `MoneyCell`. */
  detail?: ReactNode;
  /** The commit control, when the run offers one. **Hand in a danger-tier
   *  Button** — rule 6 — and hand in its disabled state with it: this component
   *  never decides whether a period may close. */
  action?: ReactNode;
}

/**
 * The Verdict block. `RBS-006-R9` region 2, and `RBS-006-R2` region 2.
 *
 * `role="status"` rather than `alert`: a screen reader reaches this in the
 * page's own order. The run has finished; nothing is firing.
 */
export function VerdictBand(props: VerdictBandProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 border border-neutral-300 bg-neutral-100 px-4 py-3"
      role="status"
      data-verdict=""
      data-verdict-tone={props.tone}
    >
      <span
        className={`${CHIP_TONE[props.tone]} px-3 py-1 text-sm font-extrabold tracking-wider uppercase`}
        data-verdict-word=""
      >
        {props.word}
      </span>
      <span className="text-md font-bold text-neutral-900" data-verdict-count="">
        {props.count}
      </span>
      {props.detail !== undefined && (
        <span className="text-base text-neutral-700" data-verdict-detail="">
          {props.detail}
        </span>
      )}
      {props.action !== undefined && (
        <span className="ms-auto" data-verdict-action="">
          {props.action}
        </span>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1a · 09-component-inventory.md Part 5 §1 · frames RBS-006-R2/R3/R9/R12/R13
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the Verdict block composes it) F✔ G✔ H=n/a
// gates: vitest src/components/VerdictBand.test.tsx · runbookKitClasses (every tone asked of the real compiler) · routeBUtilities · G31 · tsc
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
