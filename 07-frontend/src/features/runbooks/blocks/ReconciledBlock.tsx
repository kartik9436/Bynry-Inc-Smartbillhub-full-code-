// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 6 of the twelve.
// Screens: RBS-006-R2 · R4 · R9.  Rules: B14 rule 20 · 34 · 36 · hard rule 2.
// ───────────────────────────────────────────────────────
// Ours · theirs · difference, with a ties mark. `RBS-006-R9`'s TIE-OUT table.
//
// ⚠ **THE TWO COLUMN HEADINGS ARE B14 RULE 34 AND NOT THIS BLOCK'S TO CHOOSE.**
// Rule 34 (`CR-060` C11, ratified 2026-09-02) makes **Recorded** and **In the
// books** the ONE pair of words for *held here* and *in the books*, in all
// eleven catalogues — and `RBS-006-R9` draws exactly *Billed* / *In the books*.
// The headings therefore arrive pre-translated in `columns`, from the
// catalogues, and a literal here would ship English to a `fr-FR` tenant.
//
// ⚠ A TIE IS A MARK, NOT AN ABSENCE. The sheet draws a `Ties` pill where the two
// sides agree, rather than an empty difference cell — an empty cell reads as
// *not checked*, which is the opposite of what a tie-out is saying.
import { ReportTable } from "./ReportTable";
import type { BlockContext, ReconciledPayload } from "./types";

export function ReconciledBlock(props: { payload: ReconciledPayload; ctx: BlockContext }) {
  return (
    <section data-block="reconciled">
      <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
        {props.payload.heading}
      </h5>
      <ReportTable
        caption={props.payload.heading}
        columns={props.payload.columns}
        rows={props.payload.rows}
        ctx={props.ctx}
      />
    </section>
  );
}
