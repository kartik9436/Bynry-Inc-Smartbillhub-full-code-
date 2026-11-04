/**
 * The reads and the handset-own writes the job screens need (T-18, T-19 —
 * FF-15…FF-24, FF-58…FF-60) that no one-table file already had. Kept in ONE
 * file owned by the job screens so the screen waves never edit the same lines
 * of a shared query file; every statement here is one table's, or a join from a
 * scoped row, and every scoped one filters on `:technician_id` (R133).
 */
import type { TenantDb } from '../database';
import { toJson } from '../json';
import type { ScopedRunner } from '../scoped';
import type { AssetRow } from './asset';
import type { CrewTimeRow } from './crewTime';

/** A photograph on this order, with what it proves (read from its declaration, R123). */
export interface OrderPhotoRow {
  id: string;
  local_path: string;
  bytes: number;
  captured_by: string;
  captured_at: string;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
  state: string;
  file_deleted: number;
  task_id: string | null;
  reading_id: string | null;
}

/** FF-17 / FF-20 / FF-21 / FF-22: every photograph of one order, oldest first. Paged (NFR-3). */
export function photosForOrder(s: ScopedRunner, workOrderId: string, limit = 500, offset = 0): OrderPhotoRow[] {
  return s.all<OrderPhotoRow>(
    `SELECT p.id, p.local_path, p.bytes, p.captured_by, p.captured_at, p.lat, p.lng, p.accuracy_m, p.state,
            p.file_deleted,
            json_extract(d.payload, '$.task_id') AS task_id,
            json_extract(d.payload, '$.reading_id') AS reading_id
       FROM photo p
       LEFT JOIN outbox d ON d.id = p.declare_id AND d.technician_id = :technician_id
      WHERE p.technician_id = :technician_id AND p.work_order_id = :work_order_id
      ORDER BY p.captured_at, p.id
      LIMIT :limit OFFSET :offset`,
    { work_order_id: workOrderId, limit, offset },
  );
}

/** FF-15 TIME and CREW: this order's clock segments, oldest first (R8, R9). */
export function crewTimeForOrder(s: ScopedRunner, workOrderId: string): CrewTimeRow[] {
  return s.all<CrewTimeRow>(
    `SELECT * FROM crew_time WHERE technician_id = :technician_id AND work_order_id = :work_order_id
      ORDER BY started_at, id LIMIT 500`,
    { work_order_id: workOrderId },
  );
}

/** Stop a running segment (Pause). Only an open one: a stopped clock is not re-stopped. */
export function endCrewTime(s: ScopedRunner, id: string, at: string): number {
  return s.run(
    `UPDATE crew_time SET ended_at = :at WHERE technician_id = :technician_id AND id = :id AND ended_at IS NULL`,
    { id, at },
  ).changes;
}

/** *Correct time* (R9): the technician's own correction of a segment's ends. */
export function correctCrewTime(s: ScopedRunner, id: string, startedAt: string, endedAt: string | null): number {
  return s.run(
    `UPDATE crew_time SET started_at = :started_at, ended_at = :ended_at
      WHERE technician_id = :technician_id AND id = :id`,
    { id, started_at: startedAt, ended_at: endedAt },
  ).changes;
}

/** A tick, an answer or a quantity: the item's state and its kind's own detail together. */
export function setItemStateAndDetail(s: ScopedRunner, id: string, state: string | null, detail: unknown): number {
  return s.run(
    `UPDATE wo_item SET state = :state, detail = :detail WHERE technician_id = :technician_id AND id = :id`,
    { id, state, detail: toJson(detail) },
  ).changes;
}

/** FF-15 NOTES and ACTIVITY: how many of each. */
export function activityCounts(s: ScopedRunner, workOrderId: string): { events: number; remarks: number } {
  const row = s.get<{ events: number; remarks: number | null }>(
    `SELECT COUNT(*) AS events, SUM(CASE WHEN kind = 'remark' THEN 1 ELSE 0 END) AS remarks
       FROM activity WHERE technician_id = :technician_id AND work_order_id = :work_order_id`,
    { work_order_id: workOrderId },
  );
  return { events: row?.events ?? 0, remarks: row?.remarks ?? 0 };
}

/** The acts of one kind captured on this order, oldest first — what a screen
 *  shows that only its own capture holds (a typed paper's words, an added
 *  reading's reason). */
export function capturedOfKind(
  s: ScopedRunner,
  workOrderId: string,
  kind: string,
): { id: string; payload: string; captured_at: string; captured_by: string; state: string }[] {
  return s.all(
    `SELECT id, payload, captured_at, captured_by, state FROM outbox
      WHERE technician_id = :technician_id AND work_order_id = :work_order_id AND kind = :kind
      ORDER BY seq LIMIT 500`,
    { work_order_id: workOrderId, kind },
  );
}

/** FF-59: only meters at this premises are offered (US-FLD-072 TC-3). Paged. */
export function assetsAtPremise(db: TenantDb, premiseId: string, limit = 200): AssetRow[] {
  return db.ref.all<AssetRow>(
    `SELECT * FROM asset WHERE premise_id = :premise_id ORDER BY parent_asset_id IS NOT NULL, serial, id LIMIT :limit`,
    { premise_id: premiseId, limit },
  );
}

/** FF-15 ASSET: "2 sub-meters". */
export function subMeterCount(db: TenantDb, assetId: string): number {
  return (
    db.ref.get<{ n: number }>('SELECT COUNT(*) AS n FROM asset WHERE parent_asset_id = :id', { id: assetId })?.n ?? 0
  );
}
