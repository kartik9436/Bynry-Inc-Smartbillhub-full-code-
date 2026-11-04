/**
 * TAKING A JOB, OR NOT — DEF-FLD-10579 (beta report MQ-026).
 *
 * The server takes a job's work only from the technician who ACCEPTED it
 * (`apps/work/mobile.require_captor_holds_job`, BR-WRK-059), and until this
 * the phone never accepted anything: every item came back *Accept the job
 * first*. The PO's ruling (decision log 2026-10-24, *"MQ-026: STARTING A JOB
 * ACCEPTS IT; A NOT-YET-STARTED JOB CAN BE DECLINED WITH A REASON"*), verbatim:
 * *"B. Starting the job counts as accepting (recommended)- i am okay with this
 * option but then reject icon or button should be there, to give a option to
 * technician to refuse the job"*. So:
 *
 *  - **Start accepts.** The first *Start* (FF-10's card), *Open the job*
 *    (FF-14) or *Continue* (FF-15) on a job not yet accepted captures a
 *    `job_accept` item AHEAD of every unsent item of that job, so it reaches
 *    the server first — offline too: it waits in the outbox like any act. The
 *    server's accept is idempotent, so a job accepted elsewhere costs one
 *    harmless call; a job accepted HERE sends nothing more.
 *  - **Decline, before starting.** A reason from a short list (or *Other*
 *    with a note); the job stays on the list marked *Declined* until the
 *    dispatcher moves it (the feed then removes it). After starting, *Hand
 *    back* (FF-58) is the only way out — the server refuses a decline once
 *    accepted (`work.mobile.job_already_accepted`).
 *
 * WHERE THE STATE LIVES — no new column: the handset's own acts (the outbox
 * rows) and the server's card (`technician_acceptance`, which the feed keeps in
 * `work_order.extra`). An act not yet sent always wins (the technician's latest
 * word); otherwise the newer of the settled act and the server's card, so a
 * job the dispatcher gives back after a decline reads as new again.
 *
 * The reasons: the server keeps no list (`decline_job` stores free text), so
 * these are the handset's, sent as their code like FF-58's hand-back reasons.
 */
import type { TenantDb } from '../../db/database';
import type { ScopedRunner } from '../../db/scoped';
import { acceptanceOf } from '../../sync/jobAcceptance';
import { capture, type CaptureDeps, type Captor } from '../../sync/outbox';

// Where a job stands lives beside `capture`, which reads it too (DEF-FLD-10612).
export { acceptanceOf, type Acceptance } from '../../sync/jobAcceptance';

export const DECLINE_REASONS = ['time', 'reach', 'skill', 'unsafe', 'other'] as const;
export type DeclineReason = (typeof DECLINE_REASONS)[number];

/**
 * *Start*: accept the job if it is not accepted yet. True when an accept was
 * queued. Never for a declined job — the server refuses it, and taking a
 * declined job back is a call to the dispatcher. Since DEF-FLD-10612 the
 * first work saved on the job queues the accept too (`outbox.capture`); either
 * way round there is ONE accept, because each finds the other's waiting.
 */
export function acceptOnStart(db: TenantDb, s: ScopedRunner, captor: Captor, workOrderId: string, deps: CaptureDeps): boolean {
  if (acceptanceOf(s, workOrderId) !== 'pending') return false;
  capture(db, captor, { kind: 'job_accept', workOrderId, payload: {}, first: true }, deps);
  return true;
}

/** *Decline*: a reason, and a note for *Other*. Refused (false) with no reason or an empty *Other*. */
export function declineJob(
  db: TenantDb,
  s: ScopedRunner,
  captor: Captor,
  workOrderId: string,
  answer: { reason: DeclineReason | null; note: string },
  deps: CaptureDeps,
): boolean {
  const note = answer.note.trim();
  if (!canDecline(answer.reason, note)) return false;
  if (acceptanceOf(s, workOrderId) !== 'pending') return false;
  capture(db, captor, { kind: 'job_decline', workOrderId, payload: { reason: answer.reason, note: note || null } }, deps);
  return true;
}

/** A reason is picked, and *Other* says what it is. */
export function canDecline(reason: DeclineReason | null, note: string): boolean {
  return reason !== null && (reason !== 'other' || note.trim() !== '');
}
