/**
 * `outbox` — every act the technician performed, one row each, keyed by the
 * idempotency key minted at capture (R46). Scoped (R132).
 *
 * The send path reads across technicians on purpose (`deviceWide('send')`):
 * Dana's unsent work sends under her name while Marco is signed in, or while
 * nobody is (E2E-21). Every screen read is `scoped()`.
 */
import type { QueryRunner } from '../database';
import { toJson } from '../json';
import type { ScopedRunner } from '../scoped';
import type { SendState } from '../schema';

export type Channel = 'job' | 'route' | 'unrouted';

export interface OutboxRow {
  id: string;
  technician_id: string;
  work_order_id: string | null;
  route_id: string | null;
  /** The job's number when the act was captured (migration 0005, DEF-FLD-10623). */
  work_order_number: string | null;
  kind: string;
  channel: Channel;
  payload: string;
  seq: number;
  captured_by: string;
  captured_at: string;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
  fix_at: string | null;
  state: SendState;
  attempts: number;
  next_attempt_at: string | null;
  last_error: string | null;
  refusal: string | null;
  answer: string | null;
  settled_at: string | null;
}

export interface NewOutboxRow {
  id: string;
  workOrderId: string | null;
  /** The job's number as the phone holds it now — kept, because the mirror can go (DEF-FLD-10623). */
  workOrderNumber?: string | null;
  routeId: string | null;
  kind: string;
  channel: Channel;
  payload: unknown;
  seq: number;
  capturedBy: string;
  capturedAt: string;
  location: { lat: number; lng: number; accuracy_m: number; fix_at: string } | null;
}

/** The next capture position for this technician within this order or route. */
export function nextSeq(s: ScopedRunner, workOrderId: string | null, routeId: string | null): number {
  const row = s.get<{ n: number | null }>(
    `SELECT MAX(seq) AS n FROM outbox
      WHERE technician_id = :technician_id
        AND work_order_id IS :work_order_id AND route_id IS :route_id`,
    { work_order_id: workOrderId, route_id: routeId },
  );
  return (row?.n ?? 0) + 1;
}

/**
 * A capture position AHEAD of every item of this job not yet with the server
 * (DEF-FLD-10579): the job's accept must reach the server before any of its
 * work, because the server refuses that work until the job is accepted
 * (BR-WRK-059). Null when nothing is waiting — the next position is then fine.
 */
export function seqAheadOfUnsent(s: ScopedRunner, workOrderId: string): number | null {
  const row = s.get<{ n: number | null }>(
    `SELECT MIN(seq) AS n FROM outbox
      WHERE technician_id = :technician_id AND work_order_id = :work_order_id AND route_id IS NULL
        AND state IN ('pending','sending','refused')`,
    { work_order_id: workOrderId },
  );
  return row?.n == null ? null : row.n - 1;
}

/** This technician's acceptance acts on one job, newest first — the handset's
 *  mirror of *accepted* / *declined* until the server's card says so. */
export function acceptanceActsMine(s: ScopedRunner, workOrderId: string): OutboxRow[] {
  return s.all<OutboxRow>(
    `SELECT * FROM outbox WHERE technician_id = :technician_id AND work_order_id = :work_order_id
        AND kind IN ('job_accept','job_decline')
      ORDER BY captured_at DESC, seq DESC LIMIT 10`,
    { work_order_id: workOrderId },
  );
}

export function insert(s: ScopedRunner, row: NewOutboxRow): void {
  s.run(
    `INSERT INTO outbox (id, technician_id, work_order_id, work_order_number, route_id, kind, channel, payload, seq,
                         captured_by, captured_at, lat, lng, accuracy_m, fix_at, state)
     VALUES (:id, :technician_id, :work_order_id, :work_order_number, :route_id, :kind, :channel, :payload, :seq,
             :captured_by, :captured_at, :lat, :lng, :accuracy_m, :fix_at, 'pending')`,
    {
      id: row.id,
      work_order_id: row.workOrderId,
      work_order_number: row.workOrderNumber ?? null,
      route_id: row.routeId,
      kind: row.kind,
      channel: row.channel,
      payload: toJson(row.payload) ?? '{}',
      seq: row.seq,
      captured_by: row.capturedBy,
      captured_at: row.capturedAt,
      lat: row.location?.lat,
      lng: row.location?.lng,
      accuracy_m: row.location?.accuracy_m,
      fix_at: row.location?.fix_at,
    },
  );
}

/** FF-50: this technician's items, newest first, paged (NFR-3). */
export function listMine(
  s: ScopedRunner,
  opts: { states?: readonly SendState[]; limit: number; offset?: number },
): OutboxRow[] {
  const states = opts.states ?? [];
  const filter = states.length ? `AND state IN (${states.map((_, i) => `:st${i}`).join(',')})` : '';
  const params: Record<string, string | number> = { limit: opts.limit, offset: opts.offset ?? 0 };
  states.forEach((st, i) => (params[`st${i}`] = st));
  return s.all<OutboxRow>(
    `SELECT * FROM outbox WHERE technician_id = :technician_id ${filter}
      ORDER BY captured_at DESC, seq DESC LIMIT :limit OFFSET :offset`,
    params,
  );
}

export function getMine(s: ScopedRunner, id: string): OutboxRow | undefined {
  return s.get<OutboxRow>('SELECT * FROM outbox WHERE technician_id = :technician_id AND id = :id', { id });
}

/** RW-21: the findings this technician raised at one meter, newest first
 *  (BR-WRK-067) — their answer carries `finding`, open or the job it became. */
export function findingsAtMine(s: ScopedRunner, routeReadId: string, limit = 20): OutboxRow[] {
  return s.all<OutboxRow>(
    `SELECT * FROM outbox WHERE technician_id = :technician_id AND kind = 'route_finding'
        AND json_extract(payload, '$.route_read_id') = :route_read_id
      ORDER BY captured_at DESC, seq DESC LIMIT :limit`,
    { route_read_id: routeReadId, limit },
  );
}

/**
 * FB-003 (`screens/reads/position.ts`): the route readings and route photo
 * declarations saved with NO position, captured in `[from, fixAt]`, and not
 * yet given a late one — what a fix arriving at `fixAt` is attached to.
 */
export function awaitingPositionMine(
  s: ScopedRunner,
  from: string,
  fixAt: string,
): { id: string; kind: 'route_read' | 'photo'; route_id: string; captured_at: string; payload: string }[] {
  return s.all(
    `SELECT o.id, o.kind, o.route_id, o.captured_at, o.payload FROM outbox o
      WHERE o.technician_id = :technician_id AND o.channel = 'route'
        AND o.kind IN ('route_read', 'photo') AND o.lat IS NULL
        AND o.captured_at >= :from AND o.captured_at <= :fix_at
        AND NOT EXISTS (
          SELECT 1 FROM outbox p WHERE p.technician_id = :technician_id AND p.kind = 'route_position'
             AND json_extract(p.payload, '$.for_key') = o.id)
      ORDER BY o.seq`,
    { from, fix_at: fixAt },
  );
}

/** FB-003: the late position given to one act, by that act's key — the first one. */
export function latePositionMine(
  s: ScopedRunner,
  forKey: string,
): { lat: number | null; lng: number | null; accuracy_m: number | null; fix_at: string | null } | undefined {
  return s.get(
    `SELECT lat, lng, accuracy_m, fix_at FROM outbox
      WHERE technician_id = :technician_id AND kind = 'route_position' AND json_extract(payload, '$.for_key') = :for_key
      ORDER BY seq LIMIT 1`,
    { for_key: forKey },
  );
}

/** FF-50 *Raised*: the orders this technician raised in the field, newest
 *  first, each with the template it was raised from and — once the office has
 *  it — the number the server allocated (`raise_from_field`'s `order_no`, kept
 *  on the settled row's answer). DEF-FLD-10603: until this a raise's number
 *  reached the phone and was shown nowhere. */
export function raisesMine(
  s: ScopedRunner,
  limit: number,
): { id: string; state: SendState; captured_at: string; template_name: string | null; order_no: string | null }[] {
  return s.all(
    `SELECT o.id, o.state, o.captured_at, t.name AS template_name,
            json_extract(o.answer, '$.order_no') AS order_no
       FROM outbox o LEFT JOIN work_order_templates t ON t.id = json_extract(o.payload, '$.template_id')
      WHERE o.technician_id = :technician_id AND o.kind = 'raise'
      ORDER BY o.captured_at DESC, o.seq DESC LIMIT :limit`,
    { limit },
  );
}

/** *Create work order* answered: the finding's new state onto the settled row's
 *  answer, so the screen shows the job number from the phone's own store. */
export function setFindingAnswerMine(s: ScopedRunner, id: string, finding: unknown): void {
  s.run(
    `UPDATE outbox SET answer = json_set(COALESCE(answer, '{}'), '$.finding', json(:finding))
      WHERE technician_id = :technician_id AND id = :id AND kind = 'route_finding'`,
    { id, finding: toJson(finding) ?? 'null' },
  );
}

/**
 * THE one definition of "an item waiting to send" (DEF-FLD-10363). An ACT not
 * yet with the server — pending, sending, or refused and waiting on the
 * technician. A photograph's DECLARATION is not an item: the photograph is
 * counted once, as a photo (`photo.countWaiting…`). Before this, the sign-out
 * sheet counted the declaration as an item AND the photo, and Home did not —
 * the same handset said "4 items" on one screen and "3" on the other.
 * Every count of waiting items — Home, the sync screen, the route screen, the
 * shell's number, the sign-out sheet — goes through the two functions below.
 */
const WAITING_ITEM = `state IN ('pending','sending','refused') AND kind <> 'photo'`;

/** The sync number for this technician: items not yet with the server (R65). */
export function countUnsentMine(s: ScopedRunner): number {
  return s.get<{ n: number }>(`SELECT COUNT(*) AS n FROM outbox WHERE technician_id = :technician_id AND ${WAITING_ITEM}`)?.n ?? 0;
}

/** FB-033 — items of one kind this technician still has on their way to the
 *  server (pending or sending; a refused one has had its answer). */
export function countOnTheirWayMine(s: ScopedRunner, kind: string): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM outbox WHERE technician_id = :technician_id AND kind = :kind AND state IN ('pending','sending')`,
      { kind },
    )?.n ?? 0
  );
}

/** FF-50 "needs attention": still trying after this many failures, or refused. */
export function needsAttentionMine(s: ScopedRunner, failures: number): OutboxRow[] {
  return s.all<OutboxRow>(
    `SELECT * FROM outbox WHERE technician_id = :technician_id
        AND (state = 'refused' OR (state = 'pending' AND attempts >= :failures))
      ORDER BY captured_at LIMIT 500`,
    { failures },
  );
}

/**
 * *Send again* on a PENDING item that keeps failing (FB-022): its wait is
 * cleared so the next run sends it. Its failures are kept — it stays under
 * *Needs attention* until it actually goes — and nothing is discarded.
 */
export function retryNowMine(s: ScopedRunner, id: string): number {
  return s.run(
    `UPDATE outbox SET next_attempt_at = NULL
      WHERE technician_id = :technician_id AND id = :id AND state = 'pending'`,
    { id },
  ).changes;
}

/** The technician acts on a refusal: the same key goes again (the server's
 *  savepoint took the refused receipt with it, so the key is free). */
export function requeueRefused(s: ScopedRunner, id: string): number {
  return s.run(
    `UPDATE outbox SET state = 'pending', attempts = 0, next_attempt_at = NULL, last_error = NULL
      WHERE technician_id = :technician_id AND id = :id AND state = 'refused'`,
    { id },
  ).changes;
}

/**
 * The job is accepted on the server: every item of it that was refused ONLY
 * because it was not (`work.mobile.accept_the_job_first`) goes again, same key,
 * with no *Fix and send again* (DEF-FLD-10579). A refusal for any other reason
 * stays where the technician can see it (R48).
 */
export function requeueRefusedForAcceptance(s: ScopedRunner, workOrderId: string): number {
  return s.run(
    `UPDATE outbox SET state = 'pending', attempts = 0, next_attempt_at = NULL, last_error = NULL
      WHERE technician_id = :technician_id AND work_order_id = :work_order_id AND state = 'refused'
        AND COALESCE(json_extract(refusal, '$.message_key'), json_extract(refusal, '$.body.message_key'))
            = 'work.mobile.accept_the_job_first'`,
    { work_order_id: workOrderId },
  ).changes;
}

/** Unsent work held by every technician on this handset (the sign-out warning). */
export function countUnsentByTechnician(device: QueryRunner): { technician_id: string; n: number }[] {
  return device.all(
    `SELECT technician_id, COUNT(*) AS n FROM outbox
      WHERE ${WAITING_ITEM} GROUP BY technician_id ORDER BY technician_id`,
  );
}

// ── The send path (deviceWide 'send' / 'receipt') ──────────────────────────

export interface SendGroup {
  technician_id: string;
  channel: Channel;
  work_order_id: string | null;
  route_id: string | null;
  n: number;
}

/**
 * Groups with work due: one technician's items for one order (or route) on one
 * channel. A group is due when its FIRST waiting item (lowest `seq`) is due —
 * the same rule `nextBatch` sends by: it takes items up to the first one
 * backing off, so a later item can still never overtake an earlier one (R45:
 * a safety tick lands before the close it unlocks).
 *
 * DEF-FLD-10624 (D): until 2026-10-27 this read *"A group waits until EVERY
 * pending item in it is due"* (`HAVING MAX(next_attempt_at) <= now`). That
 * guarded nothing `nextBatch` did not already guard, and it held a whole job
 * — its accept, its safety check, its steps — behind ONE later item backing
 * off for up to ten minutes, which `nextBatch` was written to allow.
 */
export function dueGroups(send: QueryRunner, now: string): SendGroup[] {
  return send.all<SendGroup>(
    `SELECT o.technician_id, o.channel, o.work_order_id, o.route_id, COUNT(*) AS n
       FROM outbox o
      WHERE o.state = 'pending' AND o.channel != 'unrouted'
      GROUP BY o.technician_id, o.channel, o.work_order_id, o.route_id
     HAVING COALESCE((SELECT f.next_attempt_at FROM outbox f
                       WHERE f.state = 'pending' AND f.technician_id = o.technician_id
                         AND f.channel = o.channel AND f.work_order_id IS o.work_order_id
                         AND f.route_id IS o.route_id
                       ORDER BY f.seq LIMIT 1), '') <= :now
      ORDER BY MIN(o.captured_at)`,
    { now },
  );
}

/**
 * A MANUAL *Sync now* tries again at once (DEF-FLD-10624, C): the signed-in
 * technician's waiting items lose their backoff, so the press sends them
 * rather than waiting out up to ten minutes. Automatic runs keep backoff.
 * A server's own *wait* (a 429's Retry-After, `rate_limited`) is kept: that
 * is the server asking, not our guess. How many rows changed.
 */
export function clearBackoffMine(s: ScopedRunner): number {
  return s.run(
    `UPDATE outbox SET next_attempt_at = NULL
      WHERE technician_id = :technician_id AND state = 'pending' AND next_attempt_at IS NOT NULL
        AND COALESCE(last_error, '') <> 'rate_limited'`,
  ).changes;
}

/** The distinct saved failures of this technician's waiting items — FF-50's reason line (DEF-FLD-10624, A). */
export function pendingErrorsMine(s: ScopedRunner): (string | null)[] {
  return s
    .all<{ last_error: string | null }>(
      `SELECT DISTINCT last_error FROM outbox
        WHERE technician_id = :technician_id AND state IN ('pending','sending') AND last_error IS NOT NULL LIMIT 50`,
    )
    .map((r) => r.last_error);
}

/**
 * The next batch of a group, in capture order — ONLY what is DUE, and only up
 * to the first item that is backing off (DEF-FLD-10356). An item the server
 * left unanswered is put back with a `next_attempt_at` (`receipts.ts`); before
 * this, it was selected again at once and one run re-sent it without end, so
 * the photo phase and the pull never started and every later *Send now*
 * joined a run that never finished. Stopping at the first one backing off
 * (rather than skipping it) keeps a later item from overtaking an earlier one
 * (R45: a safety tick lands before the close it unlocks). A `NULL`
 * `next_attempt_at` is due — the 426 *update the app* path leaves it NULL and
 * counts no attempt (DEF-FLD-10355), and that run stops on its own.
 */
export function nextBatch(send: QueryRunner, g: SendGroup, limit: number, now: string): OutboxRow[] {
  return send.all<OutboxRow>(
    `SELECT * FROM outbox
      WHERE state = 'pending' AND technician_id = :technician_id AND channel = :channel
        AND work_order_id IS :work_order_id AND route_id IS :route_id
        AND seq < COALESCE((SELECT MIN(b.seq) FROM outbox b
                             WHERE b.state = 'pending' AND b.technician_id = :technician_id
                               AND b.channel = :channel AND b.work_order_id IS :work_order_id
                               AND b.route_id IS :route_id AND b.next_attempt_at > :now), 9223372036854775807)
      ORDER BY seq LIMIT :limit`,
    {
      technician_id: g.technician_id,
      channel: g.channel,
      work_order_id: g.work_order_id,
      route_id: g.route_id,
      limit,
      now,
    },
  );
}

export function markSending(send: QueryRunner, ids: readonly string[]): void {
  for (const id of ids) send.run(`UPDATE outbox SET state = 'sending' WHERE id = :id AND state = 'pending'`, { id });
}

/** A run that died mid-batch (a crash, a killed app) left rows `sending`; on
 *  the next run they are simply pending again, and the key makes a re-send a
 *  duplicate rather than a second act (R49). */
export function resetInterrupted(send: QueryRunner): number {
  return send.run(`UPDATE outbox SET state = 'pending' WHERE state = 'sending'`).changes;
}

/** Settled: the server has it (accepted, duplicate, held for review). */
export function settle(
  receipt: QueryRunner,
  id: string,
  state: 'accepted' | 'duplicate' | 'held_for_review',
  at: string,
  answer: unknown,
): void {
  receipt.run(
    `UPDATE outbox SET state = :state, settled_at = :at, answer = :answer, last_error = NULL, refusal = NULL
      WHERE id = :id`,
    { id, state, at, answer: toJson(answer) },
  );
}

/**
 * FB-019 (`DEF-FLD-10637`, `sync/outbox.settleEmptyPhotoActs`): the empty
 * `photo` acts 2.606.0 and earlier queued beside a photo added after saving —
 * route channel, refused, no `photo_id` of their own — whose every photograph
 * has its declaration settled. Device-wide: the send path, every technician.
 */
export function emptyPhotoActsSettleable(send: QueryRunner): string[] {
  return send
    .all<{ id: string }>(
      `SELECT o.id FROM outbox o
        WHERE o.kind = 'photo' AND o.channel = 'route' AND o.state = 'refused'
          AND json_extract(o.payload, '$.photo_id') IS NULL
          AND EXISTS (SELECT 1 FROM photo p WHERE p.technician_id = o.technician_id AND p.outbox_id = o.id)
          AND NOT EXISTS (
            SELECT 1 FROM photo p LEFT JOIN outbox d ON d.technician_id = p.technician_id AND d.id = p.declare_id
             WHERE p.technician_id = o.technician_id AND p.outbox_id = o.id
               AND (d.id IS NULL OR d.state NOT IN ('accepted', 'duplicate', 'held_for_review')))`,
    )
    .map((r) => r.id);
}

/** Refused: kept, shown, never retried silently (R48). `settled_at` stays NULL
 *  so nothing that ages rows by it can ever reach a refused one. */
export function refuse(receipt: QueryRunner, id: string, refusal: unknown): void {
  receipt.run(
    `UPDATE outbox SET state = 'refused', refusal = :refusal, settled_at = NULL, attempts = attempts + 1
      WHERE id = :id`,
    { id, refusal: toJson(refusal) },
  );
}

/** Not answered: back to pending, to try again later. */
export function retryLater(
  receipt: QueryRunner,
  id: string,
  nextAttemptAt: string | null,
  error: string,
  countsAsAttempt: boolean,
): void {
  receipt.run(
    `UPDATE outbox SET state = 'pending', next_attempt_at = :next, last_error = :error,
            attempts = attempts + :inc
      WHERE id = :id`,
    { id, next: nextAttemptAt, error, inc: countsAsAttempt ? 1 : 0 },
  );
}

export function attemptsOf(receipt: QueryRunner, id: string): number {
  return receipt.get<{ attempts: number }>('SELECT attempts FROM outbox WHERE id = :id', { id })?.attempts ?? 0;
}

/** Waiting on a server door that does not exist yet; stays pending, never sent. */
export function unroutedCount(device: QueryRunner): number {
  return (
    device.get<{ n: number }>(`SELECT COUNT(*) AS n FROM outbox WHERE channel = 'unrouted' AND state = 'pending'`)
      ?.n ?? 0
  );
}

// ── The purge (deviceWide 'purge') ──────────────────────────────────────────

/**
 * Settled rows older than the cutoff — and ONLY settled rows (R60). A row that
 * declares a photograph whose bytes have not been confirmed stays, because the
 * photo queue reads its answer to know where to send them.
 */
export function deleteSettledBefore(purge: QueryRunner, cutoff: string): number {
  return purge.run(
    `DELETE FROM outbox
      WHERE state IN ('accepted','duplicate','held_for_review')
        AND settled_at IS NOT NULL AND settled_at < :cutoff
        AND id NOT IN (SELECT declare_id FROM photo WHERE declare_id IS NOT NULL AND state != 'uploaded')`,
    { cutoff },
  ).changes;
}

/** Unsent rows for one technician's order or route (the cascade's guard). */
export function unsentFor(
  s: ScopedRunner,
  target: { workOrderId?: string; routeId?: string },
): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM outbox
        WHERE technician_id = :technician_id
          AND state IN ('pending','sending','refused')
          AND (work_order_id = :work_order_id OR route_id = :route_id)`,
      { work_order_id: target.workOrderId ?? null, route_id: target.routeId ?? null },
    )?.n ?? 0
  );
}

/** Settled rows of a cascade (closed order or turned-in route). */
export function deleteSettledFor(s: ScopedRunner, target: { workOrderId?: string; routeId?: string }): number {
  return s.run(
    `DELETE FROM outbox
      WHERE technician_id = :technician_id
        AND state IN ('accepted','duplicate','held_for_review')
        AND (work_order_id = :work_order_id OR route_id = :route_id)`,
    { work_order_id: target.workOrderId ?? null, route_id: target.routeId ?? null },
  ).changes;
}
