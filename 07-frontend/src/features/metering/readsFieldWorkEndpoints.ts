// ── Trace ──────────────────────────────────────────────
// Change:   the Reads→Work door — PO ruling 2026-09-14, verbatim *"please build
//           this"*, reversing that morning's `Q2` deferral.
//           Drawing: blueprint p028 (the upload wizard's stage-3 shortfall, its
//           DECISION cell carrying `Estimate all` and `Send someone out`) and
//           p047, whose control table reads: *"Send someone out · On the
//           shortfall · Raises a visit for the ticked meters · The **work**
//           module — and this is the one action that crosses a module
//           boundary"*.
// Rules:    BR-WRK-016 (the offer is the utility's OWN published templates) ·
//           BR-WRK-024 (every order carries its source — `meter_read`) ·
//           BR-WRK-055 (a failed raise never fails the flow) · BR-MET-023 /
//           BR-MET-027 / BR-MET-062 (a missing reading's answer is a field
//           visit, and for a demand peak it is the only one) · B14 rule 31 (a
//           work order shows its `WO-…` number, never a uuid)
// Tests:    07-frontend/src/features/metering/SendSomeoneOutModal.test.tsx
// Impacts:  06-backend/apps/work/api.py (`GET /work/flows/{kind}/{id}/proposed`,
//           `POST /work/flows/meter-read/raise`)
// ───────────────────────────────────────────────────────
//
// THE TWO TYPED WRAPPERS THE *SEND SOMEONE OUT* DIALOG NEEDS.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE AND NOT AN APPENDIX TO `api/endpoints.ts`
// ══════════════════════════════════════════════════════════════════════════
// The reason `serviceRequestEndpoints.ts` and `bankRecEndpoints.ts` each give in
// their own headers: `endpoints.ts` is ~13,000 lines, every lane appends to it,
// and on any given afternoon it holds two or three lanes' half-finished work.
// One family, one file, one lane's diff — which is CLAUDE.md law 11's mechanism
// five (`DEF-168`) avoided rather than survived. Nothing here re-exports or
// shadows anything `endpoints.ts` publishes.
//
// ⚠ **THE OFFER TYPE IS THE KIT'S, NOT A SECOND COPY.** `FieldWorkOffer` is
// declared in `components/RaiseFieldWork.tsx` and is what the same endpoint
// already serves the five customer flows. Re-typing it here would be two shapes
// for one payload, free to drift the first time the server adds a field — which
// is hard-won law 5 in TypeScript.
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { FieldWorkOffer } from "@/components/RaiseFieldWork";

/** One order this door raised, as `POST /work/flows/meter-read/raise` serves it. */
export interface RaisedFieldWorkOrder {
  /** ⚠ A uuid. It NEVER reaches a screen (B14 rule 31) — `order_no` is what a
   *  person is shown. It is typed because it IS served, and hiding a served
   *  field is how a lane ends up re-deriving it. */
  id: string;
  /** `WO-26-0117` — the visible reference, and the only one. */
  order_no: string;
  name: string;
  source: string | null;
  /** The METER's own number (`MTR-0463`), stamped so a person can find the
   *  visit from the meter later. */
  source_ref: string | null;
}

/** One meter that did NOT get its visit, and why. `BR-WRK-055`: this is DATA
 *  rather than an error, because the other meters were fine and a clerk has to
 *  see both halves of that in one answer. */
export interface UnraisedFieldWork {
  /** ⚠ A uuid, and it is NOT drawn. The dialog resolves it back to the meter
   *  NUMBER it already holds (B14 rule 31); the id only matches the two lists. */
  meter_id: string;
  code: string;
  message_key: string;
  detail?: string;
}

export interface RaiseFieldWorkResult {
  raised: RaisedFieldWorkOrder[];
  count: number;
  not_raised: UnraisedFieldWork[];
  /** The platform's ONE sentence for a raise that could not happen — Work owns
   *  the words, so a clerk never meets two spellings of the same fact. `null`
   *  when every ticked meter got its visit. */
  warning: { code: string; message_key: string; detail?: string } | null;
}

/**
 * `GET /work/flows/meter_read/{assetId}/proposed` — what this meter could raise.
 *
 * **WRITES NOTHING.** That is `from_flows`' first rule and the reason this door
 * is safe: the offer is a read, and only a person ticking a template and
 * pressing the commit causes a job to exist.
 *
 * The answer is the utility's **own published templates** for the service this
 * meter runs (`BR-WRK-016`) — never a list this product invented. A tenant that
 * has published none is offered none, and the panel says so, which is the
 * truthful answer rather than a gap.
 */
export async function proposeMeterFieldWork(
  assetId: string,
  client: ApiClient = api,
): Promise<FieldWorkOffer> {
  // ⚠ `DEF-MET-9685` — `meter_read`, the FLOW TOKEN the server's generic
  // `/work/flows/<flow_kind>/<flow_id>/proposed` route takes. Only the RAISE
  // below has the fixed `meter-read` segment; this read spelled it that way
  // from 2026-09-14 and every press answered 422 `unknownFlow`.
  const response = await client.get<FieldWorkOffer>(
    `/work/flows/meter_read/${encodeURIComponent(assetId)}/proposed`,
  );
  if (response.data === null) {
    throw new Error("empty body where the offer was promised");
  }
  return response.data;
}

/**
 * `POST /work/flows/meter-read/raise` — send somebody out to these meters.
 *
 * ⚠ **A 200 DOES NOT MEAN EVERY METER GOT ITS VISIT.** `BR-WRK-055`: one meter
 * whose premises cannot be resolved must not cost the other eleven theirs, so
 * the server answers `raised` AND `not_raised` and the caller renders both. A
 * screen that read only `raised` would tell a clerk that five visits were
 * booked when four were — which is `DEF-708`'s shape, an act reported that
 * never happened.
 *
 * ⚠ **AN EMPTY `templateIds` IS NOT AN ERROR.** A clerk who ticked nothing has
 * answered the question; nothing is raised and the answer says so.
 */
export async function raiseMeterFieldWork(
  args: { meters: readonly string[]; templateIds: readonly string[] },
  client: ApiClient = api,
): Promise<RaiseFieldWorkResult> {
  const response = await client.post<RaiseFieldWorkResult>("/work/flows/meter-read/raise", {
    meters: [...args.meters],
    template_ids: [...args.templateIds],
  });
  if (response.data === null) {
    throw new Error("empty body where the raise result was promised");
  }
  return response.data;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the Reads→Work door (decision log 2026-09-14)
// generated: 2026-09-14 by the Meter Reads field-visit lane
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
