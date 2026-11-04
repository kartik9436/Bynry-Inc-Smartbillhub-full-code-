/**
 * `route_read` — a reading is a RECORD, not a number (R88). One row per meter
 * on the route, downloaded as `unread`, filled at capture. Scoped.
 *
 * The figure is a TEXT decimal and never exists without its unit (hard rules
 * 2, 3). The reader's status and the engine's verdict are never merged (R96):
 * only the reader's is here.
 */
import type { QueryRunner } from '../database';
import { optionalDecimal } from '../decimal';
import { toJson } from '../json';
import type { ScopedRunner } from '../scoped';

export interface RouteReadRow {
  technician_id: string;
  id: string;
  route_id: string;
  stop_id: string;
  asset_id: string;
  parent_asset_id: string | null;
  account_id: string | null;
  previous_value: string | null;
  expected_min: string | null;
  expected_max: string | null;
  photo_required: number;
  value: string | null;
  unit: string;
  register: string | null;
  reader_status: 'read' | 'could_not_read' | 'read_with_problem' | null;
  no_read_reason: string | null;
  warned_accepted: number;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
  fix_quality: 'good' | 'poor' | 'none' | null;
  metres_from_record: number | null;
  captured_at: string | null;
  captured_by: string | null;
  identified_by: 'scan' | 'listed' | 'typed' | null;
  off_route: number;
  read_method: string | null;
  remark: string | null;
  remark_source: 'voice' | 'typed' | null;
  capture_key: string | null;
  state: string;
  /** MQ-033 — the read-format version this reading was TAKEN under, and its answers (JSON, as sent). */
  read_format_version_id: string | null;
  answers: string | null;
  /** 0007 (FB-030) — the server's FB-022 flag on a refilled reading; NULL on the phone's own (derived). */
  lower_than_last?: number | null;
  updated_at: string;
}

/** FB-030 — one reading of the reader's 14-day history, as the server holds it. */
export interface RouteReadHistory {
  id: string;
  routeId: string;
  stopId: string;
  assetId: string;
  value: string | null;
  unit: string;
  register: string | null;
  readerStatus: 'read' | 'could_not_read' | 'read_with_problem' | null;
  noReadReason: string | null;
  remark: string | null;
  capturedAt: string;
  captureKey: string;
  lowerThanLast: boolean;
}

/**
 * FB-030 — a refilled reading (a new phone, a reinstall, a remote sign-out):
 * stored as ACCEPTED, exactly as the server holds it. A reading the handset
 * already has — by id or by capture key — is left as it is (its own capture
 * wins). Never without its unit (hard rule 3).
 */
export function insertHistory(s: ScopedRunner, r: RouteReadHistory, now: string): void {
  if (!r.unit) throw new Error('a reading never exists without its unit (hard rule 3)');
  s.run(
    `INSERT INTO route_read (technician_id, id, route_id, stop_id, asset_id, value, unit, register, reader_status,
                             no_read_reason, remark, captured_at, captured_by, capture_key, state, lower_than_last,
                             updated_at)
     SELECT :technician_id, :id, :route_id, :stop_id, :asset_id, :value, :unit, :register, :reader_status,
            :no_read_reason, :remark, :captured_at, :technician_id, :capture_key, 'accepted', :lower, :now
      WHERE NOT EXISTS (SELECT 1 FROM route_read WHERE capture_key = :capture_key)
     ON CONFLICT (technician_id, id) DO NOTHING`,
    {
      id: r.id,
      route_id: r.routeId,
      stop_id: r.stopId,
      asset_id: r.assetId,
      value: optionalDecimal(r.value, 'value'),
      unit: r.unit,
      register: r.register,
      reader_status: r.readerStatus,
      no_read_reason: r.noReadReason,
      remark: r.remark,
      captured_at: r.capturedAt,
      capture_key: r.captureKey,
      lower: r.lowerThanLast ? 1 : 0,
      now,
    },
  );
}

export function upsertFromServer(
  s: ScopedRunner,
  r: { id: string; routeId: string; stopId: string; assetId: string; parentAssetId?: string | null; accountId?: string | null; previousValue?: string | null; expectedMin?: string | null; expectedMax?: string | null; photoRequired?: boolean; unit: string },
  now: string,
): void {
  if (!r.unit) throw new Error('a reading never exists without its unit (hard rule 3)');
  s.run(
    `INSERT INTO route_read (technician_id, id, route_id, stop_id, asset_id, parent_asset_id, account_id,
                             previous_value, expected_min, expected_max, photo_required, unit, updated_at)
     VALUES (:technician_id, :id, :route_id, :stop_id, :asset_id, :parent_asset_id, :account_id,
             :previous_value, :expected_min, :expected_max, :photo_required, :unit, :now)
     ON CONFLICT (technician_id, id) DO UPDATE SET
       stop_id = excluded.stop_id, asset_id = excluded.asset_id, parent_asset_id = excluded.parent_asset_id,
       previous_value = excluded.previous_value, expected_min = excluded.expected_min,
       expected_max = excluded.expected_max, photo_required = excluded.photo_required,
       updated_at = excluded.updated_at
     WHERE route_read.state = 'unread'`,
    {
      id: r.id,
      route_id: r.routeId,
      stop_id: r.stopId,
      asset_id: r.assetId,
      parent_asset_id: r.parentAssetId,
      account_id: r.accountId,
      previous_value: optionalDecimal(r.previousValue, 'previous_value'),
      expected_min: optionalDecimal(r.expectedMin, 'expected_min'),
      expected_max: optionalDecimal(r.expectedMax, 'expected_max'),
      photo_required: r.photoRequired ?? false,
      unit: r.unit,
      now,
    },
  );
}

export interface RouteReadCapture {
  captureKey: string;
  value: string | null;
  unit: string;
  register?: string | null;
  readerStatus: 'read' | 'could_not_read' | 'read_with_problem';
  noReadReason?: string | null;
  warnedAccepted?: boolean;
  location?: { lat: number; lng: number; accuracy_m: number } | null;
  fixQuality?: 'good' | 'poor' | 'none' | null;
  metresFromRecord?: number | null;
  capturedAt: string;
  capturedBy: string;
  identifiedBy: 'scan' | 'listed' | 'typed';
  offRoute?: boolean;
  readMethod: string;
  remark?: string | null;
  remarkSource?: 'voice' | 'typed' | null;
  /** MQ-033 — the version and the answers, exactly as they travel on the item. */
  readFormatVersionId?: string | null;
  answers?: readonly unknown[] | null;
}

/** Fill the row at capture. Refused when the unit is not the row's own —
 *  never assumed, never converted (hard rule 3). */
export function recordCapture(s: ScopedRunner, id: string, c: RouteReadCapture): number {
  const changes = s.run(
    `UPDATE route_read SET value = :value, register = COALESCE(:register, register), reader_status = :reader_status,
            no_read_reason = :no_read_reason, warned_accepted = :warned_accepted,
            lat = :lat, lng = :lng, accuracy_m = :accuracy_m, fix_quality = :fix_quality,
            metres_from_record = :metres_from_record, captured_at = :captured_at, captured_by = :captured_by,
            identified_by = :identified_by, off_route = :off_route, read_method = :read_method,
            remark = :remark, remark_source = :remark_source, capture_key = :capture_key, state = 'pending',
            read_format_version_id = :read_format_version_id, answers = :answers,
            updated_at = :captured_at
      WHERE technician_id = :technician_id AND id = :id AND unit = :unit`,
    {
      id,
      value: optionalDecimal(c.value, 'value'),
      unit: c.unit,
      register: c.register,
      reader_status: c.readerStatus,
      no_read_reason: c.noReadReason,
      warned_accepted: c.warnedAccepted ?? false,
      lat: c.location?.lat,
      lng: c.location?.lng,
      accuracy_m: c.location?.accuracy_m,
      fix_quality: c.fixQuality,
      metres_from_record: c.metresFromRecord,
      captured_at: c.capturedAt,
      captured_by: c.capturedBy,
      identified_by: c.identifiedBy,
      off_route: c.offRoute ?? false,
      read_method: c.readMethod,
      remark: c.remark,
      remark_source: c.remarkSource,
      capture_key: c.captureKey,
      read_format_version_id: c.readFormatVersionId ?? null,
      answers: c.answers && c.answers.length ? toJson(c.answers) : null,
    },
  ).changes;
  if (changes !== 1) throw new Error(`no unread meter ${id} with unit ${c.unit} on this technician's route`);
  return changes;
}

/** Progress is DERIVED, never a stored counter (Mobile data §11, RW-22/23). */
export function progress(s: ScopedRunner, routeId: string): { total: number; read: number } {
  const row = s.get<{ total: number; read: number }>(
    `SELECT COUNT(*) AS total, SUM(CASE WHEN state != 'unread' THEN 1 ELSE 0 END) AS read
       FROM route_read WHERE technician_id = :technician_id AND route_id = :route_id`,
    { route_id: routeId },
  );
  return { total: row?.total ?? 0, read: row?.read ?? 0 };
}

export function getMine(s: ScopedRunner, id: string): RouteReadRow | undefined {
  return s.get<RouteReadRow>('SELECT * FROM route_read WHERE technician_id = :technician_id AND id = :id', { id });
}

/** The send state, copied from the outbox answer onto the reading it carried. */
export function setStateByKey(receipt: QueryRunner, captureKey: string, state: string): void {
  receipt.run('UPDATE route_read SET state = :state WHERE capture_key = :key', { key: captureKey, state });
}

export function unsentFor(s: ScopedRunner, routeId: string): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM route_read WHERE technician_id = :technician_id AND route_id = :route_id
          AND state IN ('pending','sending','refused')`,
      { route_id: routeId },
    )?.n ?? 0
  );
}

export function deleteForRoute(s: ScopedRunner, routeId: string): number {
  return s.run('DELETE FROM route_read WHERE technician_id = :technician_id AND route_id = :route_id', {
    route_id: routeId,
  }).changes;
}

/** RW-25's turn-in: every capture key this reader has on the route, so the
 *  server can say which never reached it. Paged by the caller's limit. */
export function captureKeysFor(s: ScopedRunner, routeId: string, limit = 5000): string[] {
  return s
    .all<{ capture_key: string }>(
      `SELECT capture_key FROM route_read
        WHERE technician_id = :technician_id AND route_id = :route_id AND capture_key IS NOT NULL
        ORDER BY captured_at, id LIMIT :limit`,
      { route_id: routeId, limit },
    )
    .map((r) => r.capture_key);
}
