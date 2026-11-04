// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 5 of the twelve.
// Screens: RBS-006-R8 · R10 · R16 · R19 · R20 · R22.  Rules: B14 rule 20 · 36.
// ───────────────────────────────────────────────────────
// Group-by with counts: by class, tier, source, channel, type. `RBS-006-R19`'s
// ONE table is this block, not Records — the coverage table in
// `09-component-inventory.md` is what settles that, and it says runbooks 4, 13
// and 19 draw no Records table at all.
import { ReportTable } from "./ReportTable";
import type { BlockContext, BreakdownPayload } from "./types";

export function BreakdownBlock(props: { payload: BreakdownPayload; ctx: BlockContext }) {
  return (
    <section data-block="breakdown">
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
