// ── Trace ──────────────────────────────────────────────
// Change:   Meter Reads blueprint **entry 20**, the Still-to-read tab's bulk
//           bar. p045 item 2, verbatim: *"The bulk bar · `POST
//           /reads/bulk-estimate`, **served since CR-038 and called by
//           nothing**. The code deferred it to 'W1's completeness surface';
//           this is that surface."*
// Rules:    BR-MET-026 (the trailing-average estimate) · BR-MET-027 (two
//           consecutive estimates, then a person goes out) · BR-MET-058 (a
//           register's OWN history, never another's) · BR-MET-062 (a demand
//           peak is never estimated) · BR-SHL-025 (a refusal is an ANSWER, with
//           its reason, never a silent skip) · B14 rule 31 (a meter shows its
//           number, never its uuid)
// Tests:    07-frontend/src/features/metering/BulkEstimateModal.test.tsx
// ───────────────────────────────────────────────────────
//
// ONE TYPED WRAPPER, FOR ONE SERVED ROUTE THAT NO SCREEN HAS EVER CALLED.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE AND NOT AN APPENDIX TO `api/endpoints.ts`
// ══════════════════════════════════════════════════════════════════════════
// The reason `readsFieldWorkEndpoints.ts`, `serviceRequestEndpoints.ts` and
// `bankRecEndpoints.ts` each give in their own headers: `endpoints.ts` is
// ~19,000 lines, every lane appends to it, and on any given afternoon it holds
// two or three lanes' half-finished work. One family, one file, one lane's diff
// — which is CLAUDE.md law 11's mechanism five (`DEF-168`) avoided rather than
// survived. Nothing here re-exports or shadows anything `endpoints.ts` publishes.
//
// ⚠ **A BULK BUTTON IS A DIFFERENT SURFACE, NEVER A DIFFERENT PIPELINE.** The
// server's own words: every target goes through `estimate_missing_read`, so the
// arithmetic, the consecutive-estimate limit and the per-channel history are the
// SAME code the single-row dialog runs. **Nothing on this side computes a
// quantity, chooses a unit or picks a rounding** — `Q7`'s standing instruction,
// and B4/B5 are ❄️ FROZEN.
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

/** One missing record to fill: a meter, a register, and the date it is owed for.
 *
 *  ⚠ **A RECORD IS `(meter, channel, date)` AND NOT A METER.** A time-of-use
 *  meter short of three windows is THREE targets, which is why the screen
 *  expands each ticked meter over its own `missing_channels` rather than sending
 *  one row per tick. */
export interface BulkEstimateTarget {
  /** The asset uuid — the ANCHOR, never drawn (B14 rule 31). */
  asset_id: string;
  /** `MTR-0463` — sent so the server can name the row back in its answer, and
   *  it is what the outcome renders. */
  meter_no: string | null;
  /** `total`, `tou_mid`, `demand`… — `models.CHANNELS`. */
  channel: string;
  /** `YYYY-MM-DD`, the calendar date the record belongs to. */
  read_at: string;
}

/** One record the run created. */
export interface BulkEstimateMade {
  meter: string | null;
  channel: string;
  read_at: string | null;
  /** The server's own `<quantity> <unit>` where it composes one — hard rule 3:
   *  a consumption never reaches a screen without its unit, and `null` is the
   *  honest answer rather than a bare number. */
  usage_display?: string | null;
}

/** One the rules REFUSED, with the reason a clerk can act on.
 *
 *  ⚠ **A REFUSAL IS AN ANSWER AND IS RENDERED AS ONE (`BR-MET-026`'s posture at
 *  scale).** *"no history — field visit"* is the case the drawing's floor note
 *  names on the row before the tick; forty of them are forty answers. */
export interface BulkEstimateRefusal {
  meter: string | null;
  channel: string;
  read_at: string | null;
  /** The catalogue CODE, e.g. `BIZ_STATE`. Internal — never rendered (rule 31). */
  reason?: string | null;
  /** The translatable key the server chose, so the row says why in the clerk's
   *  own language (`G18`: no raw key reaches a user — the screen resolves it and
   *  falls back to the server's generic sentence when it holds no such key). */
  message_key?: string | null;
}

export interface BulkEstimateResult {
  estimated: BulkEstimateMade[];
  refused: BulkEstimateRefusal[];
}

/** `POST /reads/bulk-estimate` — BR-MET-026/027/058, one reason for the run.
 *
 *  ⚠ **THE REASON IS REQUIRED BY THIS WRAPPER EVEN THOUGH THE RULE ONLY ASKS FOR
 *  ONE ON AN OVERRIDE.** `BR-MET-030` demands a reason and an audit row for an
 *  estimate override; a bulk action that stored none would be the rule with its
 *  evidence removed — the argument the upload wizard's own bulk disposition
 *  already makes one screen over. */
export async function bulkEstimateReads(
  payload: { reason: string; targets: readonly BulkEstimateTarget[] },
  client: ApiClient = api,
): Promise<BulkEstimateResult> {
  const response = await client.post<BulkEstimateResult>("/reads/bulk-estimate", {
    reason: payload.reason,
    targets: [...payload.targets],
  });
  // ⚠ **THROW RATHER THAN DEFAULT TO TWO EMPTY LISTS**, the same shape
  // `raiseMeterFieldWork` takes one file over. `{estimated: [], refused: []}` is
  // a real and meaningful answer — *nothing could be filled and nothing was
  // refused* — so manufacturing it from a missing body would report an act that
  // never happened (`DEF-708`'s shape) over a POST that may well have written.
  if (response.data === null) {
    throw new Error("empty body where the bulk-estimate result was promised");
  }
  return {
    estimated: response.data.estimated ?? [],
    refused: response.data.refused ?? [],
  };
}
