/**
 * WHERE A JOB STANDS FOR THIS TECHNICIAN — taken, turned down, or neither —
 * and THE RULE THAT ANY WORK ON IT TAKES IT (DEF-FLD-10612, beta MQ-027).
 *
 * The server takes a job's work only from the technician who ACCEPTED it
 * (`apps/work/mobile.require_captor_holds_job`, BR-WRK-059). DEF-FLD-10579
 * queued that accept from three buttons (Today's *Start*, the stop's *Start*,
 * FF-15's *Continue*), so work saved by any other way in — a safety tick on
 * FF-15's Safety row, a photo, a note, the tablet's job pane, a job opened
 * from a notification — was refused *Accept the job first*. The PO's ruling
 * (decision log 2026-10-26, *"MQ-027"*), verbatim: *"if technician is starting
 * the job , that means it have accepted it , so this issue should not be there
 * as accept the job first"*. So the accept is attached where ALL work is saved
 * — `outbox.capture` asks `needsAccept` below — and the three buttons stay as
 * they were: with an accept already waiting they queue nothing more.
 *
 * WHERE THE STATE LIVES — no new column: the handset's own acts (the outbox
 * rows) and the server's card (`technician_acceptance`, which the feed keeps
 * in `work_order.extra`). An act not yet sent always wins (the technician's
 * latest word); otherwise the newer of the settled act and the server's card,
 * so a job the dispatcher gives back after a decline reads as new again.
 *
 * This lives under `sync/` and not beside the screens because `capture` reads
 * it, and the screens' module (`screens/theDay/acceptance.ts`) imports
 * `capture` — one direction only.
 */
import { fromJson } from '../db/json';
import * as outboxQ from '../db/queries/outbox';
import * as workOrderQ from '../db/queries/workOrder';
import type { ScopedRunner } from '../db/scoped';

export type Acceptance = 'pending' | 'accepted' | 'declined';

const UNSENT = new Set(['pending', 'sending']);
const SETTLED = new Set(['accepted', 'duplicate', 'held_for_review']);

const actState = (kind: string): Acceptance => (kind === 'job_accept' ? 'accepted' : 'declined');

function serverAcceptance(extra: string | null): Acceptance | null {
  const state = fromJson<{ technician_acceptance?: { state?: unknown } | null }>(extra)?.technician_acceptance?.state;
  return state === 'accepted' || state === 'declined' || state === 'pending' ? state : null;
}

/** Has this technician taken this job, turned it down, or neither yet? */
export function acceptanceOf(s: ScopedRunner, workOrderId: string): Acceptance {
  const acts = outboxQ.acceptanceActsMine(s, workOrderId).filter((r) => r.state !== 'refused');
  const unsent = acts.find((r) => UNSENT.has(r.state));
  if (unsent) return actState(unsent.kind);
  const settled = acts.find((r) => SETTLED.has(r.state)) ?? null;
  const order = workOrderQ.getMine(s, workOrderId);
  const fromServer = order ? serverAcceptance(order.extra) : null;
  if (settled && (!fromServer || !order?.server_updated_at || (settled.settled_at ?? '') >= order.server_updated_at)) {
    return actState(settled.kind);
  }
  return fromServer ?? 'pending';
}

/**
 * The kinds that are WORK ON THE JOB, so saving one takes the job: every item
 * the job's sync carries, a note or a paper, and time on the job (travel and
 * labour on `crew_time`). Not the accept or the decline themselves, not a crew
 * join or leave (that is about a person, not the job's work), not a hand-back
 * (giving it up) and not a raise (a new job).
 */
const JOB_WORK = new Set([
  'safety_tick',
  'task_tick',
  'reading',
  'material',
  'attachment',
  'signature',
  'close',
  'photo',
  'remark',
  'document',
]);

export function isJobWork(kind: string, payload: Record<string, unknown>): boolean {
  if (JOB_WORK.has(kind)) return true;
  return kind === 'crew_time' && (payload.kind === 'travel' || payload.kind === 'labour');
}

/**
 * Should saving work on this job queue its accept first? Only for a job this
 * phone holds, not yet taken and not declined (a declined job's work is SAVED
 * — nothing is ever dropped — but taking it back is a call to the dispatcher),
 * and not when an accept for it was already refused and the server has said
 * nothing newer since: that refusal is the job's answer, shown on FF-50, and a
 * second accept per tick would only stack refusals. *Start* still tries again.
 */
export function needsAccept(s: ScopedRunner, workOrderId: string): boolean {
  const order = workOrderQ.getMine(s, workOrderId);
  if (!order) return false;
  if (acceptanceOf(s, workOrderId) !== 'pending') return false;
  const refused = outboxQ.acceptanceActsMine(s, workOrderId).find((r) => r.kind === 'job_accept' && r.state === 'refused');
  if (refused && (!order.server_updated_at || refused.captured_at >= order.server_updated_at)) return false;
  return true;
}
