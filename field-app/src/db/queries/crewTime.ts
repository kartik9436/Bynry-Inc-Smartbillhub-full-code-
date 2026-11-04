/** `crew_time` — travel and labour, per person per order (R8). Scoped. */
import type { ScopedRunner } from '../scoped';

export interface CrewTimeRow {
  technician_id: string;
  id: string;
  work_order_id: string | null;
  person_id: string;
  kind: 'travel' | 'labour' | 'admin';
  started_at: string;
  ended_at: string | null;
  outbox_id: string | null;
}

export function insert(
  s: ScopedRunner,
  c: { id: string; workOrderId: string | null; personId: string; kind: CrewTimeRow['kind']; startedAt: string; endedAt?: string | null; outboxId?: string | null },
): void {
  s.run(
    `INSERT INTO crew_time (technician_id, id, work_order_id, person_id, kind, started_at, ended_at, outbox_id)
     VALUES (:technician_id, :id, :work_order_id, :person_id, :kind, :started_at, :ended_at, :outbox_id)`,
    {
      id: c.id,
      work_order_id: c.workOrderId,
      person_id: c.personId,
      kind: c.kind,
      started_at: c.startedAt,
      ended_at: c.endedAt,
      outbox_id: c.outboxId,
    },
  );
}

/** FF-47 Timesheet: by start time, in a range; paged. */
export function listBetween(s: ScopedRunner, from: string, to: string, limit = 200, offset = 0): CrewTimeRow[] {
  return s.all<CrewTimeRow>(
    `SELECT * FROM crew_time WHERE technician_id = :technician_id AND started_at >= :from AND started_at < :to
      ORDER BY started_at LIMIT :limit OFFSET :offset`,
    { from, to, limit, offset },
  );
}

export function deleteSettledForOrder(s: ScopedRunner, workOrderId: string): number {
  return s.run(
    `DELETE FROM crew_time
      WHERE technician_id = :technician_id AND work_order_id = :work_order_id
        AND (outbox_id IS NULL OR outbox_id NOT IN (
              SELECT id FROM outbox WHERE technician_id = :technician_id AND state IN ('pending','sending','refused')))`,
    { work_order_id: workOrderId },
  ).changes;
}

/** FF-48: the clock that is running for this technician, if any (one at a time). */
export function runningMine(s: ScopedRunner): CrewTimeRow | undefined {
  return s.get<CrewTimeRow>(
    `SELECT * FROM crew_time WHERE technician_id = :technician_id AND ended_at IS NULL
      ORDER BY started_at DESC LIMIT 1`,
  );
}

/** R9: the technician corrects a clock, or stops it (an end time on a running row). */
export function setTimes(s: ScopedRunner, id: string, startedAt: string, endedAt: string | null): number {
  return s.run(
    `UPDATE crew_time SET started_at = :started_at, ended_at = :ended_at
      WHERE technician_id = :technician_id AND id = :id`,
    { id, started_at: startedAt, ended_at: endedAt },
  ).changes;
}
