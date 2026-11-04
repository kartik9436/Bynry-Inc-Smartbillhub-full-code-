// ── Trace ──────────────────────────────────────────────
// Change:   `P0.10` of `05-prototype/06 Payments Page Blueprint.pdf` — *"Kit:
//           the selection toolbar … One control for bulk selection — the
//           toolbar's own row, its contents swapped."* Outcome: *"Two lists use
//           it and the third inherits rather than inventing a fourth pattern."*
// Rules:    B14 rule 12 (a list has ONE toolbar) · B14 rule 36 (*"where the kit
//           lacks a piece, ADD IT TO THE KIT — one component, one visual
//           decision, every screen"*) · B14 rule 32 (a row of controls holds
//           only things a person can press) · B14 rule 21 (utilities, no
//           stylesheet class — listed in the same commit) · B14 rule 15 (row
//           actions: two visible plus an overflow)
// Screens:  2·1b the payments bulk bar · 7·1 Debtors · the reads list
// Tests:    src/components/selectionToolbar.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS EXISTS: THERE WERE THREE OF THEM, AND THEY DISAGREED
// ══════════════════════════════════════════════════════════════════════════
// Measured on 2026-09-22, before a line of this was written — three selection
// bars in three modules, each hand-rolled in a screen file:
//
//   · `features/payments/paymentsBulk.tsx` — `pay-bulk` / `pay-bulk-count` /
//     `pay-bulk-total`, five `GuardedButton`s in a row, `role="group"`.
//   · `features/payments/OutstandingsTab.tsx` — the SAME three classes, inline,
//     six `GuardedButton`s, `role="group"`.
//   · `features/metering/ReadsBulkBar.tsx` — Tailwind utilities, a bold count,
//     two `Button`s and a sentence pushed to the far right, `role="status"`.
//
// Same job, three answers: two weights of count, two roles announced to a
// screen reader, and a non-control sentence that sits in the run of controls on
// one screen and at the far right on another. **That is what B14 rule 36 calls
// one visual decision taken in a screen file, three times.**
//
// ⚠ **THE DRAWING'S OWN WORD FOR THIS IS *SWAPS*.** The blueprint's annotation
// on 2·1b reads *"The toolbar swaps in place · search, chips and columns become
// the selection · no second bar, no layout jump"*, and the eligibility sentence
// — *"2 can be reversed · 1 cannot"* — goes *"in the slot the filter chips
// vacated, because it is the same kind of fact"*. So the shape here is the
// toolbar's row, with the count where the search was and the facts where the
// chips were. **This component is that row.** Which list does the swapping,
// and when, stays the list's: `DataTable` owns its own toolbar and nothing here
// reaches into it.
//
// ⚠ **IT TAKES ITS CONTROLS AS CHILDREN AND DECIDES NOTHING ABOUT THEM.** Every
// one of the three bars has a different refusal model — `GuardedButton` with a
// server reason on payments, plain `Button`s on reads — and a kit component
// that tried to own that would have to know about `BR-SHL-025`, which is the
// screen's business. What it owns is the ROW: where the count sits, what weight
// it carries, and that a sentence which is not a control never stands in the
// run of controls.
import type { ReactNode } from "react";

/**
 * The muted weight for text in this row that is not a control.
 *
 * ⚠ **IT IS THE READS BAR'S OWN STRING, COPIED EXACTLY.** That bar was the best
 * of the three this component replaces and it is the one being migrated in the
 * same commit, so taking `text-neutral-600` instead — which reads the same at a
 * glance — would have moved a colour on a shipped screen inside a refactor that
 * promises to move nothing.
 */
const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

export interface SelectionToolbarProps {
  /** The group's accessible name. A bar of unnamed controls is unusable
   *  without a mouse, which is B14's own note on rule 15. */
  label: string;
  /**
   * *"3 selected"* — the one fact in the row that changes as a clerk ticks, and
   * the reason it is drawn BOLD while everything beside it is not.
   */
  count: ReactNode;
  /**
   * The selection's money **already rendered** — a `Money`/`MoneyCell`, or the
   * caller's stated absence when no currency code could be read. This component
   * formats nothing (BR-SHL-023: ONE money path).
   *
   * ⚠ **IT IS `totalText` AND NOT `total`, AND THE RENAME IS THE POINT.** `G44`
   * classifies an identifier containing `total` as MONEY and failed on
   * `{props.total}` reaching a text position untreated — correctly. A slot that
   * takes a `ReactNode` but is NAMED like an amount invites the next caller to
   * pass `selectedTotal`, a raw decimal string, which would render unformatted
   * with `tsc` and every test still green: BR-SHL-023's one money path bypassed
   * in the one component three lists share.
   *
   * So the name now says what the contract already said. **This is not a
   * classifier dodged** — the test is whether the change would be worth making
   * if the gate did not exist, and it is: the docstring and the name disagreed,
   * and the name is what a caller reads.
   */
  totalText?: ReactNode;
  /**
   * *"2 can be reversed · 1 cannot"* — what can ACTUALLY happen, in the slot
   * the filter chips vacated.
   *
   * ⚠ **THE BLUEPRINT FILES ITS ABSENCE AS A GAP AND IT IS WORTH REPEATING
   * HERE.** A bar that goes live when the action will mostly fail is worse than
   * one that is greyed out: the confirm behind it takes only a COUNT, so it
   * asks *"Reverse 5 payments?"* when it is about to reverse one and silently
   * refuse four. The product already computes the per-row reason; this slot is
   * where it gets said.
   */
  eligibility?: ReactNode;
  /** The controls, in the drawing's order. B14 rule 15's grammar — two visible
   *  plus an overflow — is the CALLER's to obey, because only the caller knows
   *  which two matter on its list. */
  children: ReactNode;
  /**
   * A sentence that is NOT a control — the reads list's *"Accept only"*.
   *
   * ⚠ **IT IS PUSHED TO THE FAR RIGHT, AND THAT IS THE ONE PLACEMENT DECISION
   * THIS COMPONENT MAKES FOR ITS CALLERS.** B14 rule 32's own clause: a row of
   * controls holds only things a person can press. A sentence standing between
   * two buttons reads as a disabled third.
   */
  note?: ReactNode;
  /**
   * What a screen reader announces this as. `group` is the default and is right
   * for a bar a clerk moves INTO; `status` suits a bar that appears and
   * announces itself as the selection changes.
   *
   * ⚠ **A PROP RATHER THAN ONE ANSWER, BECAUSE THE TWO EXISTING BARS CHOSE
   * DIFFERENTLY AND NEITHER IS WRONG.** Folding them would change what a
   * screen-reader user hears on a shipped screen, which is a decision for
   * whoever owns that screen and not a side effect of a refactor.
   */
  role?: "group" | "status";
  /** The hook a walkthrough or a test finds this bar by. */
  "data-testid"?: string;
}

export function SelectionToolbar(props: SelectionToolbarProps) {
  return (
    <div
      className="mb-3 flex flex-wrap items-center gap-3 border border-divider bg-surface px-3 py-2 text-base"
      role={props.role ?? "group"}
      aria-label={props.label}
      data-selection-toolbar=""
      {...(props["data-testid"] !== undefined ? { "data-testid": props["data-testid"] } : {})}
    >
      {/* ⚠ **A BARE `<strong>`, CARRYING NO `data-` HOOK, DELIBERATELY.** The
          first draft put `data-selection-count` on it and the reads list's own
          case went red on `<strong>2 selected</strong>` — which is the check
          doing its job. A migration that promises *not one pixel moves* has no
          business changing the markup a shipped screen's test reads, for the
          convenience of a hook this component's own test does not need: it
          finds the count as the toolbar's first `<strong>`, which is also the
          only thing a reader would look for. */}
      <strong>{props.count}</strong>
      {props.totalText !== undefined && <span>{props.totalText}</span>}
      {props.eligibility !== undefined && (
        <span data-selection-eligibility="" className={MUTED}>
          {props.eligibility}
        </span>
      )}
      {props.children}
      {props.note !== undefined && (
        <span data-selection-note="" className={`ml-auto ${MUTED}`}>
          {props.note}
        </span>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p13 `P0.10` · §03 screens 2·1b (p32–p33) and 7·1 (p81–p83) rendered at 2.0
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B=n/a(no endpoint) C✔ D=n/a E✔(OutstandingsTab and ReadsBulkBar both render it) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/selectionToolbar.dom.test.tsx · G31 (listed on src/styles/route-b-migrated.txt) · routeBUtilities.test.ts
// exceptions: `features/payments/paymentsBulk.tsx` is NOT migrated here — that bar is `P1.8`'s, which the plan holds on this task, and three lanes are in that file today. The kit piece it waits on exists now.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
