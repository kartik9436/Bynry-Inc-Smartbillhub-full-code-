/**
 * What FF-34 Close checks before it lets a job close: each thing on the job
 * that needs a photograph, and how many it has. Scoped.
 *
 * A photograph proves the thing it was DECLARED for (R6, R123): the outbox
 * row of kind `photo` carries `task_id` in its payload, and the photo row
 * points at that declaration. So a task's photographs are counted through the
 * declaration, never guessed from the job.
 */
import type { ScopedRunner } from '../scoped';

export interface PhotoNeed {
  id: string;
  label: string;
  photo_min_count: number;
  must_do: number;
  photos: number;
}

export function photoNeeds(s: ScopedRunner, workOrderId: string): PhotoNeed[] {
  return s.all<PhotoNeed>(
    `SELECT i.id, i.label, i.photo_min_count, i.must_do,
            (SELECT COUNT(*) FROM photo p
               JOIN outbox o ON o.id = p.declare_id AND o.technician_id = :technician_id
              WHERE p.technician_id = :technician_id AND json_extract(o.payload, '$.task_id') = i.id) AS photos
       FROM wo_item i
      WHERE i.technician_id = :technician_id AND i.work_order_id = :work_order_id AND i.photo_required = 1
      ORDER BY i.kind, i.position`,
    { work_order_id: workOrderId },
  );
}

/** The photographs taken with a captured act (FF-30: a note's photo). */
export function photosOfAct(s: ScopedRunner, outboxId: string): { id: string; local_path: string }[] {
  return s.all(
    `SELECT id, local_path FROM photo WHERE technician_id = :technician_id AND outbox_id = :outbox_id
      ORDER BY captured_at, id LIMIT 20`,
    { outbox_id: outboxId },
  );
}
