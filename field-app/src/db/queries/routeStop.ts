/** `route_stop` — one row per premises on a route; the stop is the address
 *  (R74). Its point is downloaded so nearest-first needs no signal (R76). Scoped. */
import type { ScopedRunner } from '../scoped';

export interface RouteStopRow {
  technician_id: string;
  id: string;
  route_id: string;
  premise_id: string;
  walk_position: number;
  lat: number | null;
  lng: number | null;
  access_notes: string | null;
  hazard: string | null;
  updated_at: string;
}

/** FB-030 — a refilled history stop; a stop the handset already holds is left alone. */
export function insertIfAbsent(s: ScopedRunner, st: { id: string; routeId: string; premiseId: string }, now: string): void {
  s.run(
    `INSERT INTO route_stop (technician_id, id, route_id, premise_id, walk_position, updated_at)
     VALUES (:technician_id, :id, :route_id, :premise_id,
             (SELECT COUNT(*) + 1 FROM route_stop WHERE technician_id = :technician_id AND route_id = :route_id), :now)
     ON CONFLICT (technician_id, id) DO NOTHING`,
    { id: st.id, route_id: st.routeId, premise_id: st.premiseId, now },
  );
}

export function upsert(
  s: ScopedRunner,
  st: { id: string; routeId: string; premiseId: string; walkPosition: number; lat?: number | null; lng?: number | null; accessNotes?: string | null; hazard?: string | null },
  now: string,
): void {
  s.run(
    `INSERT INTO route_stop (technician_id, id, route_id, premise_id, walk_position, lat, lng, access_notes, hazard, updated_at)
     VALUES (:technician_id, :id, :route_id, :premise_id, :walk_position, :lat, :lng, :access_notes, :hazard, :now)
     ON CONFLICT (technician_id, id) DO UPDATE SET
       route_id = excluded.route_id, premise_id = excluded.premise_id, walk_position = excluded.walk_position,
       lat = excluded.lat, lng = excluded.lng, access_notes = excluded.access_notes, hazard = excluded.hazard,
       updated_at = excluded.updated_at`,
    {
      id: st.id,
      route_id: st.routeId,
      premise_id: st.premiseId,
      walk_position: st.walkPosition,
      lat: st.lat,
      lng: st.lng,
      access_notes: st.accessNotes,
      hazard: st.hazard,
      now,
    },
  );
}

/** The office's walk order (R75 keeps it one tap away); paged. */
export function listInWalkOrder(s: ScopedRunner, routeId: string, limit = 100, offset = 0): RouteStopRow[] {
  return s.all<RouteStopRow>(
    `SELECT * FROM route_stop WHERE technician_id = :technician_id AND route_id = :route_id
      ORDER BY walk_position LIMIT :limit OFFSET :offset`,
    { route_id: routeId, limit, offset },
  );
}

export function deleteForRoute(s: ScopedRunner, routeId: string): number {
  return s.run('DELETE FROM route_stop WHERE technician_id = :technician_id AND route_id = :route_id', {
    route_id: routeId,
  }).changes;
}
