/**
 * The server's answer, written back onto the rows it answers — per item, never
 * per batch (R47).
 *
 *   accepted · duplicate · held_for_review  → SETTLED. The key is in the
 *       server's `acknowledged` list: it has the item. (`held_for_review` is
 *       the server's fourth answer: stored and flagged for the office, which
 *       the phone may let go — apps/work/sync.py, TECHNICIAN SYNC DESIGN (2).)
 *   refused → KEPT and SHOWN with the server's reason, never retried silently
 *       (R48). The server's savepoint took the receipt with it, so the same
 *       key may go again once the technician has acted.
 *   anything else — no answer for the key, or an answer without the ack —
 *       → back to pending and tried again. The ack list is the ONLY thing that
 *       lets an item go (`sync_batch`: "the phone removes an item from its
 *       outbox ONLY when its key is here").
 */
import type { TenantDb } from '../db/database';
import * as outbox from '../db/queries/outbox';
import * as photo from '../db/queries/photo';
import * as routeRead from '../db/queries/routeRead';
import * as syncState from '../db/queries/syncState';
import { deviceWide, scoped } from '../db/scoped';
import { nextAttemptAt } from './backoff';
import { DELTA_TABLE } from './delta';
import { lastErrorOf } from './syncReason';
import type { BatchAnswer, TransportError } from './transport';

export interface ReceiptTally {
  accepted: number;
  duplicate: number;
  held_for_review: number;
  refused: number;
  unanswered: number;
}

export function emptyTally(): ReceiptTally {
  return { accepted: 0, duplicate: 0, held_for_review: 0, refused: 0, unanswered: 0 };
}

export function applyBatchAnswer(
  db: TenantDb,
  sent: readonly outbox.OutboxRow[],
  answer: BatchAnswer,
  now: Date,
  random?: () => number,
): ReceiptTally {
  const receipt = deviceWide(db, 'receipt');
  const tally = emptyTally();
  const acked = new Set(answer.acknowledged ?? []);
  const byKey = new Map((answer.items ?? []).map((i) => [i.key, i]));
  const at = now.toISOString();
  db.transaction(() => {
    for (const row of sent) {
      const item = byKey.get(row.id);
      if (item?.result === 'refused') {
        outbox.refuse(receipt, row.id, item.detail ?? { message: 'refused' });
        routeRead.setStateByKey(receipt, row.id, 'refused');
        tally.refused += 1;
        continue;
      }
      if (item && acked.has(row.id) && item.result !== undefined) {
        const state = item.result;
        outbox.settle(receipt, row.id, state, at, item.detail ?? null);
        routeRead.setStateByKey(receipt, row.id, state);
        if (row.kind === 'photo') {
          const url = typeof item.detail?.upload_url === 'string' ? item.detail.upload_url : null;
          photo.setUploadUrlByDeclaration(receipt, row.id, url);
        }
        tally[state] += 1;
        continue;
      }
      const failures = outbox.attemptsOf(receipt, row.id) + 1;
      outbox.retryLater(receipt, row.id, nextAttemptAt(now, failures, random), 'no_receipt_for_item', true);
      routeRead.setStateByKey(receipt, row.id, 'pending');
      tally.unanswered += 1;
    }
    // DEF-FLD-10624 (B): the server ANSWERED, so this is when the phone last
    // reached it — FF-50's *Last reached the server* reads it. `touchPush`
    // existed from the first schema and nothing called it, so a send that
    // landed never moved the line; only a pull did.
    if (tally.accepted + tally.duplicate + tally.held_for_review + tally.refused > 0) {
      for (const technicianId of new Set(sent.map((r) => r.technician_id))) {
        const s = scoped(db, technicianId);
        syncState.touchPush(s, DELTA_TABLE, at, outbox.countUnsentMine(s));
      }
    }
  });
  return tally;
}

/**
 * An own-door item whose CAPTOR's capture token the server refused (lane
 * S-GAPS): back to pending, no attempt counted, no backoff — it goes after
 * that captor's next sign-in. Never `refuse()`: nothing is wrong with the item.
 */
export function waitForCaptor(db: TenantDb, sent: readonly outbox.OutboxRow[]): void {
  const receipt = deviceWide(db, 'receipt');
  db.transaction(() => {
    for (const row of sent) {
      outbox.retryLater(receipt, row.id, null, 'waiting_for_captor_sign_in', false);
      routeRead.setStateByKey(receipt, row.id, 'pending');
    }
  });
}

/** A rate-limited batch waits this long when the server named no wait. */
export const RATE_LIMITED_DEFAULT_WAIT_SECONDS = 60;

/**
 * When a 429'd batch may go again (`DEF-SHL-10621`): the server's own wait —
 * `params.retry_after_seconds`, which `core/errors.py` copies from the
 * `Retry-After` it sends — else a minute (the WAF's block carries no envelope).
 */
export function rateLimitedUntil(now: Date, err: TransportError): string {
  const params = (err.body as { params?: { retry_after_seconds?: unknown } } | undefined)?.params;
  const named = params?.retry_after_seconds;
  const seconds =
    typeof named === 'number' && Number.isFinite(named) && named > 0 ? named : RATE_LIMITED_DEFAULT_WAIT_SECONDS;
  return new Date(now.getTime() + seconds * 1000).toISOString();
}

/** The whole request failed. What that means depends on why. */
export function applyBatchFailure(
  db: TenantDb,
  sent: readonly outbox.OutboxRow[],
  err: TransportError,
  now: Date,
  random?: () => number,
): ReceiptTally {
  const receipt = deviceWide(db, 'receipt');
  const tally = emptyTally();
  db.transaction(() => {
    for (const row of sent) {
      if (err.kind === 'app_too_old') {
        // The server refused THIS BUILD, not the item (DEF-FLD-10355): kept
        // as pending, no attempt counted, no backoff — it sends after the
        // update. Never `refuse()`: a 426 is a 4xx and would read as one below.
        outbox.retryLater(receipt, row.id, null, 'waiting_for_app_update', false);
        routeRead.setStateByKey(receipt, row.id, 'pending');
        tally.unanswered += 1;
      } else if (err.status === 429) {
        // DEF-SHL-10621 — too many syncs from this phone (the server's A4
        // limit, or the firewall's). Not the item's fault and not a refusal:
        // kept as pending, no attempt counted, sent again once the server's
        // Retry-After has passed. Asked BEFORE the 4xx branch, which would
        // mark it refused. Nothing is lost.
        outbox.retryLater(receipt, row.id, rateLimitedUntil(now, err), 'rate_limited', false);
        routeRead.setStateByKey(receipt, row.id, 'pending');
        tally.unanswered += 1;
      } else if (err.kind === 'http' && err.status !== undefined && err.status >= 400 && err.status < 500) {
        // The server read the request and said no to all of it — a job that
        // is not this tenant's (J65 step 13: "marked failed and SHOWN rather
        // than silently dropped"), or a malformed batch. Shown on FF-50.
        outbox.refuse(receipt, row.id, { status: err.status, body: err.body ?? null, message: err.message });
        routeRead.setStateByKey(receipt, row.id, 'refused');
        tally.refused += 1;
      } else if (err.kind === 'auth' || err.kind === 'endpoint_missing') {
        // Not a failure of the item: sending waits (Security §1 — expiry
        // blocks sending, never capture). No attempt counted, no backoff.
        outbox.retryLater(receipt, row.id, null, err.kind === 'auth' ? 'waiting_for_sign_in' : `endpoint_missing: ${err.message}`, false);
        routeRead.setStateByKey(receipt, row.id, 'pending');
        tally.unanswered += 1;
      } else {
        // The connection died: we do not know what landed. Pending again; the
        // key turns whatever did land into a duplicate on the next send (R49).
        const failures = outbox.attemptsOf(receipt, row.id) + 1;
        // FB-022: with the server's trace_id when it sent one (`lastErrorOf`).
        outbox.retryLater(receipt, row.id, nextAttemptAt(now, failures, random), lastErrorOf(err), true);
        routeRead.setStateByKey(receipt, row.id, 'pending');
        tally.unanswered += 1;
      }
    }
  });
  return tally;
}
