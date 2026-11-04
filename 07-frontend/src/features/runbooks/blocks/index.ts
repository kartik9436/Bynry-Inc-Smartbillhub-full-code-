// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b.
// Rules: `BR-RBS-021` (a thirteenth block needs THREE runbooks) · B14 rule 36.
// ───────────────────────────────────────────────────────
// **The twelve, in one place, so `RBS-006` (wave C2) composes rather than
// invents.** `RB-020`'s claim — adding runbook 23 needs one Python module and no
// frontend code — rests on this list being closed and complete.
//
// ⚠ **ALL TWELVE ARE BUILT. `records` LANDED WITH `C2` (2026-09-06), WHICH IS
// THE WAVE THAT OWNS ITS QUERY STATE** — it is the only block that PAGES
// (server-side, `NFR-3`, `per` clamped 50/100/200/500/1000), so it holds a
// toolbar, filters and a pager, and every one of those is a question about a
// QUERY. `C1b` deliberately did not build it: a block holding state nothing
// drives is a component with props nothing passes — dead UI that renders
// nothing while every test passes (hard-won law 2, four defects in one day).
// It takes its state as a REQUIRED prop from the renderer instead.
//
export { VerdictBlock } from "./VerdictBlock";
export { KpisBlock } from "./KpisBlock";
export { ChainBlock } from "./ChainBlock";
export { BreakdownBlock } from "./BreakdownBlock";
export { ReconciledBlock } from "./ReconciledBlock";
export { RankedBlock } from "./RankedBlock";
export { SentenceBlock } from "./SentenceBlock";
export { FactsBlock } from "./FactsBlock";
export { ActionBlock } from "./ActionBlock";
export { RowDecisionsBlock } from "./RowDecisionsBlock";
export { DownloadsBlock } from "./DownloadsBlock";
export { RecordsBlock } from "./RecordsBlock";
export type { RecordsBlockProps } from "./RecordsBlock";

export { ReportTable } from "./ReportTable";
export { ReportValueCell, reportValueText } from "./ReportValueCell";

export { BLOCK_TYPES } from "./types";
export type * from "./types";

/** The block names that have a component today — now all twelve.
 *  `blocks.test.tsx` asserts this list against `BLOCK_TYPES`, so the two cannot
 *  drift and a thirteenth cannot arrive unnoticed (`BR-RBS-021`). It read
 *  ELEVEN with `records` named as a stated absence until `C2` landed it; the
 *  absence had a test rather than a comment, which is why closing it went red
 *  here first and named itself. */
export const BLOCKS_BUILT = [
  "verdict",
  "kpis",
  "chain",
  "breakdown",
  "reconciled",
  "ranked",
  "sentence",
  "facts",
  "action",
  "row_decisions",
  "downloads",
  "records",
] as const;
