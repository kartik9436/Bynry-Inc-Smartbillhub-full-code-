/**
 * `crew_time` on one order — FF-29 Crew and FF-32 Debrief read every
 * person's travel and labour on the job (R8: labour is per person). Scoped:
 * the rows are the signed-in technician's copy of the crew's time.
 *
 * Kept apart from `crewTime.ts` (FF-47's timesheet) so two waves never edit
 * the same file.
 */
import type { ScopedRunner } from '../scoped';
import type { CrewTimeRow } from './crewTime';

export function listForOrder(s: ScopedRunner, workOrderId: string): CrewTimeRow[] {
  return s.all<CrewTimeRow>(
    `SELECT * FROM crew_time WHERE technician_id = :technician_id AND work_order_id = :work_order_id
      ORDER BY started_at, id LIMIT 500`,
    { work_order_id: workOrderId },
  );
}

/**
 * R9: travel and labour are both correctable by the technician. A correction
 * replaces the person's clocks on this order with the corrected ones, inside
 * the capture of the correction itself (the act and its local change land
 * together; the outbox keeps every earlier act, so nothing unsent is lost).
 */
export function replaceForPerson(
  s: ScopedRunner,
  workOrderId: string,
  personId: string,
  rows: ReadonlyArray<{ id: string; kind: CrewTimeRow['kind']; startedAt: string; endedAt: string | null }>,
  outboxId: string,
): void {
  s.run(
    `DELETE FROM crew_time WHERE technician_id = :technician_id AND work_order_id = :work_order_id
        AND person_id = :person_id`,
    { work_order_id: workOrderId, person_id: personId },
  );
  for (const r of rows) {
    s.run(
      `INSERT INTO crew_time (technician_id, id, work_order_id, person_id, kind, started_at, ended_at, outbox_id)
       VALUES (:technician_id, :id, :work_order_id, :person_id, :kind, :started_at, :ended_at, :outbox_id)`,
      {
        id: r.id,
        work_order_id: workOrderId,
        person_id: personId,
        kind: r.kind,
        started_at: r.startedAt,
        ended_at: r.endedAt,
        outbox_id: outboxId,
      },
    );
  }
}

/** Stop a person's open clocks on this order (FF-29's × takes them off from now). */
export function endOpen(s: ScopedRunner, workOrderId: string, personId: string, at: string): number {
  return s.run(
    `UPDATE crew_time SET ended_at = :at
      WHERE technician_id = :technician_id AND work_order_id = :work_order_id
        AND person_id = :person_id AND ended_at IS NULL`,
    { work_order_id: workOrderId, person_id: personId, at },
  ).changes;
}
