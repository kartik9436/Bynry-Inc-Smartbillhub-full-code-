/**
 * `work_order` — the closing side: what FF-34 writes on the handset when a
 * close is captured, and what FF-35 Completed lists. Scoped (R132).
 *
 * Kept apart from `workOrder.ts` so the closing wave and the day wave never
 * edit the same file. `closed_at` and `outcome` are the handset's own record
 * of the close until the server answers (`workOrder.ts`: an upsert from the
 * server never touches `closed_at`).
 *
 * FB-030 (PO 2026-10-31, decision log *"a technician's history is the last 14
 * days, kept on the phone"*):
 *   - a job closed on the web or another phone arrives COMPLETED on its card
 *     (`completed_at`, `outcome`), and `fillCloseFromServer` writes them —
 *     a value the phone already holds wins;
 *   - the close KEEPS its debrief (problem, done) and the signer's name and
 *     time under `body.record` (`recordClose`), which it used to discard;
 *   - a refilled job's record comes from its bundle (`setRecordIfAbsent`).
 */
import type { ScopedRunner } from '../scoped';
import type { WorkOrderRow } from './workOrder';

/** Who signed, or why they did not, and when. */
export type RecordSigner =
  | { kind: 'signed'; name: string; at: string | null }
  | { kind: 'refused'; reason: string; at: string | null };

/** What a closed job's record carries beyond its rows (`body.record`). */
export interface ClosedRecord {
  problem: string;
  done: string;
  signer: RecordSigner | null;
}

function writeRecord(s: ScopedRunner, id: string, record: ClosedRecord, onlyIfAbsent: boolean): void {
  s.run(
    `UPDATE work_order SET body = json_set(COALESCE(body, '{}'), '$.record', json(:record))
      WHERE technician_id = :technician_id AND id = :id
        ${onlyIfAbsent ? `AND json_extract(COALESCE(body, '{}'), '$.record') IS NULL` : ''}`,
    { id, record: JSON.stringify(record) },
  );
}

/** FF-34: the close is captured — the outcome and when, and what it said, in one statement each. */
export function recordClose(s: ScopedRunner, id: string, outcome: string, at: string, record?: ClosedRecord): void {
  s.run(
    `UPDATE work_order SET closed_at = :at, outcome = :outcome
      WHERE technician_id = :technician_id AND id = :id`,
    { id, at, outcome },
  );
  if (record) writeRecord(s, id, record, false);
}

/**
 * FB-030 — the server says the job is closed (`completed_at` on its card):
 * fill `closed_at` and `outcome` where the phone holds none. What the phone
 * already holds wins — its own close is the record of what it captured.
 */
export function fillCloseFromServer(s: ScopedRunner, id: string, completedAt: string, outcome: string | null): void {
  s.run(
    `UPDATE work_order SET closed_at = COALESCE(closed_at, :at), outcome = COALESCE(outcome, :outcome)
      WHERE technician_id = :technician_id AND id = :id`,
    { id, at: completedAt, outcome },
  );
}

/** FB-030 — a refilled job's record from its bundle; the phone's own close wins. */
export function setRecordIfAbsent(s: ScopedRunner, id: string, record: ClosedRecord): void {
  writeRecord(s, id, record, true);
}

/** The record a closed job keeps, or null. */
export function recordOf(row: Pick<WorkOrderRow, 'body'> | null | undefined): ClosedRecord | null {
  try {
    const body = row?.body ? (JSON.parse(row.body) as { record?: ClosedRecord | null }) : null;
    const r = body?.record;
    if (!r || typeof r !== 'object') return null;
    return {
      problem: typeof r.problem === 'string' ? r.problem : '',
      done: typeof r.done === 'string' ? r.done : '',
      signer: r.signer && (r.signer.kind === 'signed' || r.signer.kind === 'refused') ? r.signer : null,
    };
  } catch {
    return null;
  }
}

/**
 * FF-35 Completed: this technician's closed jobs since a moment (and, for
 * *Earlier*, before another), newest first. Paged (NFR-3); closed jobs are
 * kept 14 days (R62, FB-030), so the list is bounded by the purge, not by a
 * cap here.
 */
export function listClosedSince(
  s: ScopedRunner,
  opts: { since: string; before?: string | null; limit: number; offset?: number },
): WorkOrderRow[] {
  return s.all<WorkOrderRow>(
    `SELECT * FROM work_order
      WHERE technician_id = :technician_id AND closed_at IS NOT NULL AND closed_at >= :since
        AND (:before IS NULL OR closed_at < :before)
      ORDER BY closed_at DESC, number
      LIMIT :limit OFFSET :offset`,
    { since: opts.since, before: opts.before ?? null, limit: opts.limit, offset: opts.offset ?? 0 },
  );
}
