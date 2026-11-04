/**
 * FF-34 Close's *Arrived* default when the technician never tapped Arrived
 * and ran no labour clock (DEF-FLD-10626; PO 2026-10-27, decision log: *default
 * Arrived to the first work saved on the job*).
 *
 * The FIRST WORK SAVED is the earliest act this technician captured on the
 * job — a tick, a reading, a part, a photo, a signature, a note. Not the
 * job's acceptance or decline, which can be hours before the visit; not a
 * crew clock, which FF-34 reads first from `crew_time`; not a close.
 * Read-only, scoped (R133).
 */
import type { ScopedRunner } from '../scoped';

export function firstWorkAt(s: ScopedRunner, workOrderId: string): string | null {
  return (
    s.get<{ at: string | null }>(
      `SELECT MIN(captured_at) AS at FROM outbox
        WHERE technician_id = :technician_id AND work_order_id = :work_order_id
          AND kind NOT IN ('job_accept','job_decline','hand_back','crew_time','close')`,
      { work_order_id: workOrderId },
    )?.at ?? null
  );
}
