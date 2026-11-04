// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint `P2.14` (p014) — *"AbsentFigure — a stated absence
//          with its reason. Referenced on 1·4, 2·2, 2·3 and 6·1 and it does not
//          exist [as `components/AbsentFigure.tsx`]. BR-SHL-025 requires the
//          reason to travel with the missing figure; today each site
//          improvises."*
// Rules:   BR-SHL-025 (a control or figure this deployment cannot honour is
//          stated WITH its reason, never hidden and never faked) ·
//          B14 rule 43 (a piece of UI used twice is a COMPONENT) ·
//          B14 rule 36 (the shared component kit is how you comply — where the
//          kit lacks a piece, ADD IT TO THE KIT) ·
//          B14 rule 32 (a screen has a description budget; a stated absence is
//          CLOSED by default) ·
//          B14 rule 31 (nothing internal is ever visible — the gap's CODE stays
//          in the code, the sentence is what a clerk reads)
// Tests:   src/features/ledger/financeSurface.test.tsx (the absence renderer) ·
//          src/features/metering/ImportResults.dom.test.tsx (DEF-127's zero)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY THIS MOVED OUT OF `features/ledger/financeShared.tsx`               ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// It was never a Finance component. Measured on the day it moved: **28 render
// sites across 8 files in THREE features** — ledger, payments and reports —
// and `features/payments/BadDebtPanel.tsx` imported it as
// `@/features/ledger/financeShared`, reaching across a feature boundary to
// borrow a renderer that a bad-debt panel has every right to own.
//
// **B14 rule 43 is the rule and rule 36 is the remedy:** a piece of UI used
// twice is a component, and where the kit lacks a piece you ADD IT TO THE KIT
// rather than let the second caller reach into the first one's feature folder.
// The blueprint recorded the gap against itself — *"This document named the
// component before checking it was real"* — which is the same habit one row
// further down from `P2.14` and worth keeping visible.
//
// ⚠ **NOTHING ABOUT THE RENDERING CHANGED IN THE MOVE.** Same markup, same
// classes, same closed-by-default disclosure, same `role="note"`. A move that
// also changes behaviour is two changes wearing one commit, and this one is
// deliberately only the first.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A BLANK CELL AND A ZERO SAY DIFFERENT THINGS, AND NEITHER SAYS WHY      ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// That sentence is `P2.14`'s outcome and it is the whole argument. `DEF-127`
// is the worked case: a count that could not be read was drawn as `0`, and a
// zero is a MEASUREMENT — it says *we looked and there were none*. An absence
// says *we could not look*. A blank cell says neither and invites the reader to
// guess. Only a named absence WITH its reason distinguishes the three, and
// `reason` is required here so that "render an absence silently" cannot be
// expressed in the type system.
import "../features/ledger/finance.css";

/**
 * Is this value one the books would not state?
 *
 * ⚠ **`null` AND `undefined` MEAN THE SAME THING HERE, DELIBERATELY.** A read
 * model that omits a member and one that sends it null are both saying *the
 * books do not state this*, so they must render the same. Money has its own
 * test — `MoneyCell.isAmountAbsent`, the same question typed for a decimal
 * string; this one is for the members that are not money: a ratio, a day
 * count, an aging bucket list.
 */
export function isFigureAbsent<T>(value: T | null | undefined): value is null | undefined {
  return value === null || value === undefined;
}

/**
 * A figure the books would not state, rendered as ABSENT with its reason.
 *
 * `reason` is REQUIRED and is a string, not an optional: the type is what makes
 * "render an absence silently" unexpressible. `role="note"` rather than
 * `role="alert"` — a named gap is a documented state of this deployment, not an
 * error that just happened.
 *
 * ⚖️ **CLOSED BY DEFAULT — B14 rule 32, and this component is why the rule was
 * needed (2026-09-01).** Three of S36's six KPI tiles resolve to this renderer,
 * and each printed *Not available* followed by a three-sentence paragraph
 * INSIDE a 180px tile. The strip went ragged, the two tiles that held a real
 * number were the shortest things on the row, and the PO photographed it. Their
 * ruling of 2026-08-31, said four times in twenty minutes: *"too much content -
 * desctiption is too much for clark to read"*.
 *
 * **Nothing is deleted and nothing is hidden from anyone who wants it.** The
 * label is the `<summary>`, so a closed tile reads *Not available* and the row
 * is a row again; the sentence is one click away. This is `RunGap`'s ratified
 * shape (`billing/billRunShared.tsx`), which the rule's own status line names
 * as the component that "holds by construction".
 *
 * ⚠ **THE `<details>` CARRIES NO CLASS, DELIBERATELY.** `.fin-absent` is
 * `display: flex`, and overriding `display` on a `<details>` is how the closed
 * state stops hiding its content in real browsers — the disclosure would be
 * open for every reader while every test still passed. Block layout stacks the
 * summary over the reason on its own, which is all `.fin-absent` was doing.
 *
 * ⚠ **THIS COMPONENT IS NOT ON `src/styles/route-b-migrated.txt`, SO IT USES
 * THE CLASSES `finance.css` ALREADY DECLARES AND ADDS NONE (B14 rule 21).**
 * The three classes it names — `.fin-absent-value`, `.fin-absent-reason` and
 * the `.fin-absent` it deliberately does not set — are declared there and
 * travelled with it, unchanged, so the move added nothing to any stylesheet.
 * The stylesheet import above is what keeps that true from this path.
 */
export function AbsentFigure(props: { label: string; reason: string }) {
  return (
    <details>
      <summary className="fin-absent-value">{props.label}</summary>
      <span className="fin-absent-reason" role="note">
        {props.reason}
      </span>
    </details>
  );
}
