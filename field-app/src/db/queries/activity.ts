/** `activity` — every timestamped event on a job, one table (status | remark). Scoped. */
import type { ScopedRunner } from '../scoped';

export interface ActivityRow {
  technician_id: string;
  id: string;
  work_order_id: string;
  kind: 'status' | 'remark';
  status: string | null;
  text: string | null;
  author: string | null;
  at: string;
  outbox_id: string | null;
}

export function insert(
  s: ScopedRunner,
  a: { id: string; workOrderId: string; kind: 'status' | 'remark'; status?: string | null; text?: string | null; author?: string | null; at: string; outboxId?: string | null },
): void {
  s.run(
    `INSERT INTO activity (technician_id, id, work_order_id, kind, status, text, author, at, outbox_id)
     VALUES (:technician_id, :id, :work_order_id, :kind, :status, :text, :author, :at, :outbox_id)`,
    {
      id: a.id,
      work_order_id: a.workOrderId,
      kind: a.kind,
      status: a.status,
      text: a.text,
      author: a.author,
      at: a.at,
      outbox_id: a.outboxId,
    },
  );
}

export function listForOrder(s: ScopedRunner, workOrderId: string, limit = 200): ActivityRow[] {
  return s.all<ActivityRow>(
    `SELECT * FROM activity WHERE technician_id = :technician_id AND work_order_id = :work_order_id
      ORDER BY at LIMIT :limit`,
    { work_order_id: workOrderId, limit },
  );
}

/** Part of a closed order's cascade: only rows whose act is settled or local-only. */
export function deleteSettledForOrder(s: ScopedRunner, workOrderId: string): number {
  return s.run(
    `DELETE FROM activity
      WHERE technician_id = :technician_id AND work_order_id = :work_order_id
        AND (outbox_id IS NULL OR outbox_id NOT IN (
              SELECT id FROM outbox WHERE technician_id = :technician_id AND state IN ('pending','sending','refused')))`,
    { work_order_id: workOrderId },
  ).changes;
}
