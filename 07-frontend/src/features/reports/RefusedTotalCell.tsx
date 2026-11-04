// ── Trace ──────────────────────────────────────────────
// Story:    CR-142-BRC07 Phase 2 · P2.22 (THE MONEY TASK — a footer that
//           cannot lawfully sum shows an em-dash and the reason, never a
//           number).  Screens: 2·1 footer · 2·1 group rows.
// Rules:    B14 rule 43 (a piece of UI is built as a COMPONENT; standalone
//           code inside a page is not reuse) · rule 33 (a FACT is ≤ 6 words;
//           RATIONALE is ZERO words on screen) · rule 44 (our UI standard
//           beats the drawing on how it is BUILT) · rule 21 (Tailwind
//           utilities; this file is on `route-b-migrated.txt`)
// Tests:    07-frontend/src/features/reports/refusedTotal.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { RefusedTotal } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * ONE FOOTER CELL THAT WILL NOT CARRY A NUMBER.
 *
 * Brief §7.2.2 p85, read as an image (B14 rule 42): *"A total that is not
 * lawful shows **an em-dash and its reason**, never a number."*
 *
 * ⚠ **THE REASON IS A FACT AND NOT RATIONALE, AND THE DIFFERENCE IS THE WHOLE
 * OF RULE 33.** *"Balances do not sum across time"* is a fact about this cell
 * — six words, and it tells a clerk what to change. *"Because a balance is a
 * stock rather than a flow, adding July's closing receivable to August's
 * counts…"* is rationale, it is ZERO words on screen, and it lives in
 * `apps/reports/additivity.py`'s docstring where a reader can find it.
 *
 * ⚠ **IT IS A COMPONENT BECAUSE IT IS RENDERED IN TWO PLACES** (rule 43): the
 * grand-total footer and every group subtotal `P2.17` inserts. The inline
 * version of this was 14 lines in `ReportTotalsRow` and the subtotal row would
 * have grown its own copy within a week, which is how one of them comes to say
 * something the other does not.
 *
 * ⚠ **THE SENTENCE COMES FROM THE CATALOGUE, KEYED BY `reason_code`**, so it
 * is said in the reader's own language (B14 rule 35 — a catalogue is written
 * in its own language, never translated from English). The server's English
 * `reason` is the fallback for a key not yet fanned in, which is a string
 * being late rather than a cell going blank.
 */
export function RefusedTotalCell(props: {
  total: RefusedTotal;
  t: Translator;
  /** ⚠ **FALSE on the grand-total footer, where the row says the reason ONCE
   *  for all its refused columns (B14 rule 32 — a screen has a description
   *  budget).** Default TRUE, because a GROUP SUBTOTAL is a single cell with
   *  no row to hang a sentence on, and a bare em-dash there is the one thing
   *  §7.2.2 forbids. The default is the safe one on purpose: a caller that
   *  forgets this prop gets the reason, never silence. */
  showReason?: boolean;
}) {
  const key = `reports.totals.${props.total.reason_code}`;
  const sentence = props.t(key);
  return (
    <span className="inline-flex items-baseline gap-1.5">
      {/* The em-dash IS the value. It is the server's character, never one
          typed here, so the CSV and the screen cannot show two different
          things (US-REP-003 TC-1's contract, one layer up). */}
      <span aria-hidden="true" className="text-base leading-none">
        {props.total.display}
      </span>
      {/* ⚠ NOT `title=` and NOT a tooltip. A reason a clerk has to hover for
          is a reason an auditor reading a printout never sees, and the CSV
          carries this same sentence in the same cell for that reason. */}
      {props.showReason === false ? null : (
        <span className="text-xs font-normal text-neutral-600">
          {sentence === key ? props.total.reason : sentence}
        </span>
      )}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 2 · P2.22 (05-prototype/09 Reports Build Brief.pdf p84, p85 read as images per B14 rule 42)
// screens: 2·1 footer · 2·1 group subtotals
// generated: 2026-09-27 by lane REP-P2-MODEL
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — refusedTotal.dom.test.tsx was shown red (the footer rendered `[object Object]`) before this component existed
// exceptions: (1) the reason is rendered INLINE and never as a `title` tooltip — a hovered reason is invisible on a printout, and the CSV carries the same sentence for the same reason · (2) no number of any kind is rendered, and the wire carries none to render
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
