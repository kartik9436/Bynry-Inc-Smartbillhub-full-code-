/** `wo_item` — one row per thing to do on a job, whatever its kind (R130). Scoped. */
import { toJson } from '../json';
import type { ScopedRunner } from '../scoped';

export type WoItemKind = 'task' | 'material' | 'safety' | 'checklist';

export interface WoItemRow {
  technician_id: string;
  id: string;
  work_order_id: string;
  kind: WoItemKind;
  position: number;
  label: string;
  must_do: number;
  photo_required: number;
  photo_min_count: number;
  added_in_field: number;
  reason: string | null;
  state: string | null;
  detail: string | null;
  updated_at: string;
}

export interface WoItemInput {
  id: string;
  workOrderId: string;
  kind: WoItemKind;
  position: number;
  label: string;
  mustDo?: boolean;
  photoRequired?: boolean;
  photoMinCount?: number;
  addedInField?: boolean;
  reason?: string | null;
  state?: string | null;
  detail?: unknown;
}

export function upsert(s: ScopedRunner, item: WoItemInput, now: string): void {
  s.run(
    `INSERT INTO wo_item (technician_id, id, work_order_id, kind, position, label, must_do, photo_required,
                          photo_min_count, added_in_field, reason, state, detail, updated_at)
     VALUES (:technician_id, :id, :work_order_id, :kind, :position, :label, :must_do, :photo_required,
             :photo_min_count, :added_in_field, :reason, :state, :detail, :now)
     ON CONFLICT (technician_id, id) DO UPDATE SET
       kind = excluded.kind, position = excluded.position, label = excluded.label, must_do = excluded.must_do,
       photo_required = excluded.photo_required, photo_min_count = excluded.photo_min_count,
       added_in_field = excluded.added_in_field, reason = excluded.reason, detail = excluded.detail,
       updated_at = excluded.updated_at`,
    {
      id: item.id,
      work_order_id: item.workOrderId,
      kind: item.kind,
      position: item.position,
      label: item.label,
      must_do: item.mustDo ?? false,
      photo_required: item.photoRequired ?? false,
      photo_min_count: item.photoMinCount ?? 0,
      added_in_field: item.addedInField ?? false,
      reason: item.reason ?? null,
      state: item.state ?? null,
      detail: toJson(item.detail),
      now,
    },
  );
}

/** The handset's own change to a row it is working (a tick). */
export function setState(s: ScopedRunner, id: string, state: string): void {
  s.run('UPDATE wo_item SET state = :state WHERE technician_id = :technician_id AND id = :id', { id, state });
}

export function listForOrder(s: ScopedRunner, workOrderId: string, kind?: WoItemKind): WoItemRow[] {
  return s.all<WoItemRow>(
    `SELECT * FROM wo_item WHERE technician_id = :technician_id AND work_order_id = :work_order_id
        AND (:kind IS NULL OR kind = :kind)
      ORDER BY kind, position`,
    { work_order_id: workOrderId, kind: kind ?? null },
  );
}

export function deleteForOrder(s: ScopedRunner, workOrderId: string): number {
  return s.run('DELETE FROM wo_item WHERE technician_id = :technician_id AND work_order_id = :work_order_id', {
    work_order_id: workOrderId,
  }).changes;
}
