/**
 * WHY NOTHING WENT, IN ONE SHORT FACT (DEF-FLD-10624 — A; B14 rule 33: a fact
 * is at most six words a sentence).
 *
 * FF-50 said nothing when a run failed or sent nothing: the PO watched
 * *"16 waiting"* for fifteen minutes with no word of why. Two sources, in order:
 *  1. the run just asked for (`SyncRunOutcome.reason`, from the run's result);
 *  2. failing that, the waiting items' own saved `last_error`
 *     (`receipts.ts` writes it on every failure) — so the reason is there when
 *     the screen opens, not only after a press.
 */
import type { SyncResult } from './engine';
import type { SyncFailure } from './transport';

export type SyncReason =
  | 'offline'
  | 'noSignal'
  | 'signIn'
  | 'signInToSend'
  | 'server'
  | 'unconfirmed'
  | 'downloadServer'
  | 'timedOut'
  | 'certificate'
  | 'outdated'
  | 'update'
  | 'rateLimited';

/** What a run did, for the screen that asked for it. */
export interface SyncRunOutcome {
  /** Why it stopped or sent nothing; null — nothing to say. */
  reason: SyncReason | null;
  /** Items the server took (accepted, duplicate, held for review). */
  sent: number;
}

export const REASON_KEY: Record<SyncReason, string> = {
  offline: 'field.ff50.reason.offline',
  noSignal: 'field.ff50.reason.noSignal',
  signIn: 'field.ff50.reason.signIn',
  signInToSend: 'field.ff50.reason.signInToSend',
  server: 'field.ff50.reason.server',
  // FB-022 (DEF-FLD-10795): a 200 with no receipt for the item is not a 5xx,
  // and a download the server failed is not a send it failed.
  unconfirmed: 'field.ff50.reason.unconfirmed',
  downloadServer: 'field.ff50.reason.downloadServer',
  timedOut: 'field.ff50.reason.timedOut',
  // The same words FF-08 already says for these three (one sentence, one key).
  certificate: 'field.firstSync.reason.certificate',
  outdated: 'field.firstSync.reason.outdated',
  update: 'field.firstSync.reason.update',
  rateLimited: 'field.ff50.reason.rateLimited',
};

/** Most important first: the one the technician can act on wins. */
const PRIORITY: readonly SyncReason[] = ['signInToSend', 'signIn', 'update', 'certificate', 'outdated', 'rateLimited', 'server', 'unconfirmed', 'downloadServer', 'timedOut', 'noSignal', 'offline'];

export function firstReason(reasons: readonly (SyncReason | null | undefined)[]): SyncReason | null {
  for (const r of PRIORITY) if (reasons.includes(r)) return r;
  return null;
}

/** A step's failure (kind and status, never its text) as a reason. */
export function reasonOfFailure(f: Pick<SyncFailure, 'kind' | 'status'>): SyncReason {
  return reasonOf(f, 'server');
}

/** A DOWNLOAD step's failure: the server's fault there says *download*, never the send's words (FB-022). */
export function reasonOfDownloadFailure(f: Pick<SyncFailure, 'kind' | 'status'>): SyncReason {
  return reasonOf(f, 'downloadServer');
}

function reasonOf(f: Pick<SyncFailure, 'kind' | 'status'>, server: 'server' | 'downloadServer'): SyncReason {
  if (f.kind === 'auth') return 'signIn';
  if (f.kind === 'certificate') return 'certificate';
  if (f.kind === 'endpoint_missing') return 'outdated';
  if (f.kind === 'app_too_old') return 'update';
  if (f.status === 429) return 'rateLimited';
  if (f.status !== undefined && f.status >= 500) return server;
  return f.kind === 'network' ? 'noSignal' : server;
}

/** A waiting item's saved `last_error` (`receipts.ts`) as a reason. */
export function reasonOfLastError(lastError: string | null | undefined): SyncReason | null {
  if (!lastError) return null;
  if (lastError === 'waiting_for_sign_in' || lastError === 'waiting_for_captor_sign_in') return 'signIn';
  if (lastError === 'waiting_for_app_update') return 'update';
  if (lastError === 'rate_limited') return 'rateLimited';
  if (lastError.startsWith('endpoint_missing')) return 'outdated';
  if (lastError === 'no_receipt_for_item') return 'unconfirmed';
  if (/^HTTP 5\d\d/.test(lastError)) return 'server';
  return 'noSignal';
}

/**
 * The engine's result as a reason; null when it stopped for nothing it can
 * name. `technicianId` — who is signed in: THEIR work skipped for want of a
 * capture credential says *Sign in again to send* (DEF-FLD-10629, G); another
 * captor's is shown under that person's name, not as this run's reason.
 */
export function reasonOfResult(result: SyncResult, technicianId?: string | null): SyncReason | null {
  const d = result.data;
  if (technicianId && (d.skippedNoTokenBy?.[technicianId] ?? 0) > 0) return 'signInToSend';
  if (result.stoppedForAuth || d.waitingForCaptor > 0) return 'signIn';
  if (result.stoppedForUpdate) return 'update';
  const f = result.failures;
  return firstReason([f?.pull, f?.bundles, f?.templates].map((x) => (x ? reasonOfDownloadFailure(x) : null)));
}

/**
 * THE SERVER'S TRACE ID, KEPT (FB-022, DEF-FLD-10793). `core/errors.py` puts
 * a `trace_id` on every error envelope, and on a 500 it is the ONLY way to
 * find the log line. The phone saved just `HTTP 500`, so a reporter had
 * nothing to quote. The saved failure is now `HTTP 500 trace_id=<hex>`; the
 * prefix is unchanged, so every reader of `last_error` reads it as before.
 * An HTML 5xx from a proxy carries no envelope and no id: saved as before.
 */
export function lastErrorOf(err: { message: string; body?: unknown }): string {
  const trace = (err.body as { trace_id?: unknown } | null | undefined)?.trace_id;
  return typeof trace === 'string' && /^[0-9a-f-]{8,64}$/i.test(trace) ? `${err.message} trace_id=${trace}` : err.message;
}

/**
 * The reference FF-50 shows (`7F3A-9C21`): the first eight of the trace id,
 * upper case, in two fours — short enough to read over a phone (rule 33), and
 * enough to find the line: the server logs `trace_id=<hex>`, so DevOps
 * searches `grep -i 'trace_id=7f3a9c21'`. Null when the failure carries none.
 */
export function referenceOf(lastError: string | null | undefined): string | null {
  const m = lastError ? /trace_id=([0-9a-f]{8})/i.exec(lastError.replace(/-/g, '')) : null;
  if (!m) return null;
  const hex = m[1]!.toUpperCase();
  return `${hex.slice(0, 4)}-${hex.slice(4)}`;
}
