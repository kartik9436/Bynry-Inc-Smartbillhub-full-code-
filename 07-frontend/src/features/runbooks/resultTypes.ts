// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C2.
// Screens: RBS-006 (`S152`) at `/{tenant}/runbooks/{key}/runs/{id}`.
// Rules:   `BR-RBS-020` (the report is composed at close and FROZEN) ·
//          B14 rule 31 (no database id is ever the visible value of a field) ·
//          `NFR-3` (server pagination) · `07-endpoints.md` rows for
//          `GET /runs/{id}` and `GET /runs/{id}/report`.
// Defects: DEF-RBS-4284 (the engine and the renderer disagreeing on all six
//          payloads, with both suites green).
// ───────────────────────────────────────────────────────
// WHAT `RBS-006` DRAWS, AND WHY THE WIRE SHAPE IS THIS SHAPE.
//
// `contract.py` rules the direction one level down — *"the twelve shapes are
// the renderer's (wave C)"* — and the same argument applies here, one level up,
// and applies harder: the report is FROZEN at close, so a mapper would be
// re-shaping a stored artefact on every read and `BR-RBS-020`'s guarantee — a
// past run reopened draws exactly what it drew that day — would depend on the
// mapper never changing.
//
// ⚠ **THIS PARAGRAPH USED TO CITE `runbooksEndpoints.ts` AS ALREADY HAVING
// RULED IT FOR `RBS-004` TOO, AND THAT HALF WAS SETTLED THE OTHER WAY
// (`DEF-RBS-4308`, corrected here in the same commit that corrected it there).**
// The setup screen's payload is not the renderer's shape and never was: the
// endpoint serves FACTS and the screen composes the words, because a view model
// is translated chrome that has no business in Python. `features/runbooks/
// setupModel.ts` is that mapper. **The report is the case that genuinely has no
// mapper**, for the reason above, and it is the only one — so the citation is
// narrowed rather than deleted.
//
// So `report` is `ReportBlock[]` verbatim from `runbook_runs.report`, and the
// only thing this file adds is the RUN's own header facts, which are not in the
// report because they are not part of it.
import type { ReportBlock } from "./blocks/types";

/** The run's own facts — everything on `RBS-006`'s page head that the frozen
 *  report does not carry, because it is about the RUN rather than the result. */
export interface RunHeader {
  /** The runbook's human name — *Configuration check*. The `← ` kicker names
   *  where the page EXITS to (B14 rule 1), so this doubles as that label. */
  runbookName: string;
  /** Where the kicker goes back to. An ADDRESS, never a key to be assembled
   *  by the reader — `DEF-CWP-3925` is what a half-built address costs. */
  runbookTo: string;
  /** *Run · Today 08:12*.
   *
   *  ⚠ **THIS DOCSTRING SAID "composed by the server in the tenant's own zone"
   *  AND THAT WAS FALSE THE MOMENT `D1` LANDED.** `GET /runbooks/runs/{id}`
   *  serves `started_at` as an instant and no title at all, so the page composes
   *  this line from the tenant's zone and format — which it gets from
   *  `useTenantRegional()`, the SHELL's published settings, never from the
   *  admin-only regional endpoint (`DEF-SHL-4283`: nine components still read
   *  that one directly and a Billing Clerk meets a refusal on every one).
   *  Corrected rather than left standing: a comment claiming a guarantee is not
   *  the guarantee (hard-won law 1), and this file was written before the
   *  endpoint it describes existed. */
  title: string;
  /** How long it took — `12s` on `RBS-006-R1`'s fourth KPI tile.
   *
   *  ⚠ **IT IS NOT IN THE REPORT AND MUST NOT BE.** A duration is a fact about
   *  the RUN (`runbook_runs.started_at` / `finished_at`), not about the result,
   *  and the report is frozen at close. `configuration_check.report()` says the
   *  same thing from the other side and the divergence is stamped in
   *  `08-screen-layouts.md`. Absent while a run is still going. */
  took?: string;
  /** Whether a re-run is offered, and why not when it is not. B14 draws a
   *  control a user may not use as disabled WITH its reason, never hidden. */
  rerun: { enabled: true } | { enabled: false; reason: string };
}

/** What `GET /runs/{id}` + `GET /runs/{id}/report` give `RBS-006` together.
 *
 *  ⚠ `id` IS ABSENT ON PURPOSE. B14 rule 31 — no database id is ever the
 *  visible value of a field — and a view model that does not carry one cannot
 *  leak one. The id lives in the URL, where the router put it. */
export interface RunResultView {
  header: RunHeader;
  /** The frozen report, verbatim. `BR-RBS-020`. */
  report: ReportBlock[];
  /** The `records` block's server-side page, because that block is the only one
   *  that pages (`NFR-3`, `per` clamped 50/100/200/500/1000). The block's
   *  payload carries the CURRENT page and the total; these say which page it is,
   *  so a reload of a shared URL lands on the same rows. */
  records: { page: number; per: number; chip: string };
}
