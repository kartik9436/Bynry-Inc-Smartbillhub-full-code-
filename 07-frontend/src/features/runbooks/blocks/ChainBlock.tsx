// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 3 of the twelve.
// Screens: RBS-006-R1 (ten cells) · R2 (nine) · R6 · R13.
// Rules: B14 rule 36 · `BR-RBS-027` / `RB-036` (Never reached).
// ───────────────────────────────────────────────────────
// Wave C's *goal a clerk can see* lands here: *Can we bill?* runs and the result
// draws a ten-cell chain, red at the earliest failure, with a red cell naming
// the blocker. The shape is `components/Chain.tsx`; this is the payload seam.
import { Chain } from "@/components/Chain";

import type { ChainPayload } from "./types";

export function ChainBlock(props: { payload: ChainPayload }) {
  return <Chain cells={props.payload.cells} label={props.payload.label} />;
}
