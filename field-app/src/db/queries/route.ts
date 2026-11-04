/** `route` — a read route assigned to a reader. Scoped. One reader per route
 *  for now, and nothing here assumes it (R87). */
import type { QueryRunner } from '../database';
import { toJson } from '../json';
import type { ScopedRunner } from '../scoped';

export interface RouteRow {
  technician_id: string;
  id: string;
  code: string | null;
  service: string | null;
  area: string | null;
  read_type: string | null;
  cycle: string | null;
  window_start: string | null;
  window_end: string | null;
  notes: string | null;
  assigned_to: string | null;
  status: 'assigned' | 'in_progress' | 'turned_in';
  turned_in_at: string | null;
  extra: string | null;
  /** MQ-033 — the resolved read format per service (JSON; `readFormat.routeFormats`). */
  read_formats: string | null;
  updated_at: string;
}

export function upsert(
  s: ScopedRunner,
  r: { id: string; code?: string | null; service?: string | null; area?: string | null; readType?: string | null; cycle?: string | null; windowStart?: string | null; windowEnd?: string | null; notes?: string | null; assignedTo?: string | null; extra?: Record<string, unknown> | null },
  now: string,
): void {
  s.run(
    `INSERT INTO route (technician_id, id, code, service, area, read_type, cycle, window_start, window_end, notes,
                        assigned_to, extra, updated_at)
     VALUES (:technician_id, :id, :code, :service, :area, :read_type, :cycle, :window_start, :window_end, :notes,
             :assigned_to, :extra, :now)
     ON CONFLICT (technician_id, id) DO UPDATE SET
       code = excluded.code, service = excluded.service, area = excluded.area, read_type = excluded.read_type,
       cycle = excluded.cycle, window_start = excluded.window_start, window_end = excluded.window_end,
       notes = excluded.notes, assigned_to = excluded.assigned_to, extra = excluded.extra,
       updated_at = excluded.updated_at`,
    {
      id: r.id,
      code: r.code,
      service: r.service,
      area: r.area,
      read_type: r.readType,
      cycle: r.cycle,
      window_start: r.windowStart,
      window_end: r.windowEnd,
      notes: r.notes,
      assigned_to: r.assignedTo,
      extra: toJson(r.extra),
      now,
    },
  );
}

export function listMine(s: ScopedRunner, limit = 50, offset = 0): RouteRow[] {
  return s.all<RouteRow>(
    `SELECT * FROM route WHERE technician_id = :technician_id ORDER BY window_start, code LIMIT :limit OFFSET :offset`,
    { limit, offset },
  );
}

/** FF-50 *On this phone* (DEF-FLD-10629, J): the reader's open routes and their meters. */
export function countsMine(s: ScopedRunner): { routes: number; meters: number } {
  const row = s.get<{ routes: number; meters: number | null }>(
    `SELECT COUNT(*) AS routes,
            SUM((SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = r.technician_id AND rr.route_id = r.id)) AS meters
       FROM route r WHERE r.technician_id = :technician_id AND r.status != 'turned_in'`,
  );
  return { routes: row?.routes ?? 0, meters: row?.meters ?? 0 };
}

export function markTurnedIn(s: ScopedRunner, id: string, at: string): void {
  s.run(
    `UPDATE route SET status = 'turned_in', turned_in_at = :at WHERE technician_id = :technician_id AND id = :id`,
    { id, at },
  );
}

export function getMine(s: ScopedRunner, id: string): RouteRow | undefined {
  return s.get<RouteRow>('SELECT * FROM route WHERE technician_id = :technician_id AND id = :id', { id });
}

/**
 * FB-030 — a route refilled from the reader's 14-day history
 * (`sync/routeHistory.ts`): stored as turned in, at the server's time. A
 * route the handset already holds keeps its own status and time.
 */
export function upsertHistory(
  s: ScopedRunner,
  r: { id: string; code: string | null; name: string | null; cycle: string | null; turnedInAt: string | null },
  now: string,
): void {
  s.run(
    `INSERT INTO route (technician_id, id, code, cycle, assigned_to, status, turned_in_at, extra, updated_at)
     VALUES (:technician_id, :id, :code, :cycle, :technician_id, 'turned_in', :turned_in_at, :extra, :now)
     ON CONFLICT (technician_id, id) DO NOTHING`,
    {
      id: r.id,
      code: r.code,
      cycle: r.cycle,
      turned_in_at: r.turnedInAt ?? now,
      extra: toJson(r.name ? { name: r.name } : null),
      now,
    },
  );
}

export function deleteMine(s: ScopedRunner, id: string): number {
  return s.run('DELETE FROM route WHERE technician_id = :technician_id AND id = :id', { id }).changes;
}

export function turnedInBefore(purge: QueryRunner, cutoff: string): { technician_id: string; id: string }[] {
  return purge.all(
    `SELECT technician_id, id FROM route WHERE status = 'turned_in' AND turned_in_at < :cutoff ORDER BY turned_in_at`,
    { cutoff },
  );
}
