// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 7 of the twelve.
// Screens: RBS-006-R4 · RBS-006-R16.  Rules: B14 rule 36 · hard rule 2 · 3.
// ───────────────────────────────────────────────────────
// ⚠ THE VALUE IS FORMATTED BY `ReportValueCell`, NOT BY THIS BLOCK. The rows on
// `RBS-006-R4` are money (`+$46.40`) and on `RBS-006-R16` they are money AND a
// percentage side by side — which is exactly the case where one helper is wrong
// in one of the two directions on every row.
//
// ⚠ AND THE ORDER IS THE RUNBOOK'S. `ContributionBars` draws rows as given and
// never re-sorts; `RBS-006-R16` ranks by contribution and `RBS-006-R4` by money,
// so a component that sorted would silently disagree with one of them.
import { ContributionBars } from "@/components/ContributionBars";

import { ReportValueCell } from "./ReportValueCell";
import type { BlockContext, RankedPayload } from "./types";

export function RankedBlock(props: { payload: RankedPayload; ctx: BlockContext }) {
  return (
    <section data-block="ranked">
      <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
        {props.payload.heading}
      </h5>
      <ContributionBars
        label={props.payload.heading}
        rows={props.payload.rows.map((row) => ({
          id: row.id,
          label: row.label,
          detail: row.detail,
          weight: row.weight,
          value: <ReportValueCell value={row.value} ctx={props.ctx} />,
        }))}
      />
    </section>
  );
}
