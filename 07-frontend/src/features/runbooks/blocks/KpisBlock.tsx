// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 2 of the twelve.
// Screens: every runbook EXCEPT 6 and 13.  Rules: B14 rule 36 · hard rule 2.
// ───────────────────────────────────────────────────────
// ⚠ *"every runbook except 6 and 13"* and NOT *"all 21"*.
// `09-component-inventory.md`: the specification's block table says all 21 and
// the coverage table says otherwise, and the DRAWINGS settle it — `RBS-006-R6`
// and `RBS-006-R13` draw no KPI strip at all. A block that always renders would
// put an empty strip on two screens; an absent `kpis` block draws nothing,
// which is what those two sheets show.
//
// ⚠ A MONEY TILE CARRIES ITS BASIS AND `KpiTile` MAKES THAT REQUIRED — so no
// unlabeled money number can reach a tile (BR-REP-001). A money value therefore
// arrives here as a `money` cell and is handed to `KPIStrip`'s own money slot
// rather than pre-rendered, which is the only path that keeps the basis label.
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";

import { ReportValueCell } from "./ReportValueCell";
import type { BlockContext, KpisPayload } from "./types";

export function KpisBlock(props: { payload: KpisPayload; ctx: BlockContext }) {
  const kpis: KpiTile[] = props.payload.tiles.map((tile) =>
    tile.value.kind === "money"
      ? {
          id: tile.id,
          label: tile.label,
          money: {
            amount: tile.value.amount,
            currency: tile.value.currency,
            // ⚠ FROM THE PAYLOAD — `DEF-RBS-4350`. This was `"posting"` for
            // every money tile in the product, so a runbook that posts nothing
            // laid "Posting date" under its own total. The fallback is the
            // signed default for a billing-side figure (`BR-REP-001`) and the
            // conformance suite makes it unreachable for any shipped runbook.
            basis: tile.basis ?? ("posting" as const),
            locale: props.ctx.locale,
          },
          detail: tile.detail,
        }
      : {
          id: tile.id,
          label: tile.label,
          value: <ReportValueCell value={tile.value} ctx={props.ctx} />,
          detail: tile.detail,
        },
  );
  return <KPIStrip kpis={kpis} />;
}
