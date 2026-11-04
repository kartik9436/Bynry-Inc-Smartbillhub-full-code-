/**
 * The day, as the day's screens read it (FF-10 Today, FF-12 Claim's day
 * length, FF-13 Map, FF-14 Stop, FF-63 Home, the menu's counts). Added by the
 * screen wave T-16 — SQL lives only in this folder (`tests/db/scoping.test.ts`).
 * Every function takes the SCOPED runner, so it can only ever see the
 * signed-in technician's rows (R132, R133).
 *
 * ⚠ EVERY STATEMENT IS WRITTEN OUT WHOLE, never assembled from a shared
 * fragment: the scoping test reads each function's SQL literals, and a
 * `${SELECT}` fragment would hide the statement from it — a check reporting
 * a pass over a scope it silently skips (CLAUDE.md law 7).
 *
 * ORDER, AND WHY: appointment window, then the deadline, then the number,
 * NULLs last on both time legs — priority is a badge, never a sort key (R1,
 * BR-WRK-035; the same order as `workOrder.listDay`). So WO-4824, a P1 in
 * 12:00–17:00, sits SECOND behind WO-4822's 08:00–12:00 (US-FLD-015 TC-2).
 *
 * "WHICH DAY" is decided by SQLite's `julianday()`, never by comparing ISO
 * strings, so `…T13:00:00-05:00` and `…T18:00:00Z` are the same moment.
 *
 * THE STATES are the server's seven dispatch states (BR-WRK-023,
 * `06-backend/apps/metering/connections.py`): queued · scheduled · en_route ·
 * on_site · complete · on_hold · cancelled. OPEN = not complete, not
 * cancelled, not closed on the handset.
 */
import type { ScopedRunner } from '../scoped';
import * as outboxQ from './outbox';
import * as photoQ from './photo';

export const DISPATCH = {
  queued: 'queued',
  scheduled: 'scheduled',
  enRoute: 'en_route',
  onSite: 'on_site',
  complete: 'complete',
  onHold: 'on_hold',
  cancelled: 'cancelled',
} as const;

/** Lists are read 50 at a time (NFR-3; the sync's own page size). */
export const PAGE_SIZE = 50;

export interface DayJob {
  id: string;
  number: string | null;
  type: string | null;
  dispatchState: string | null;
  priorityCode: string | null;
  windowStart: string | null;
  windowEnd: string | null;
  dueAt: string | null;
  estMinutes: number | null;
  premiseId: string | null;
  addressLine: string | null;
  locality: string | null;
  region: string | null;
  postalCode: string | null;
  lat: number | null;
  lng: number | null;
  customerName: string | null;
}

interface DayJobRow {
  id: string;
  number: string | null;
  type: string | null;
  dispatch_state: string | null;
  priority_code: string | null;
  window_start: string | null;
  window_end: string | null;
  due_at: string | null;
  est_minutes: number | null;
  premise_id: string | null;
  address_line: string | null;
  locality: string | null;
  region: string | null;
  postal_code: string | null;
  lat: number | null;
  lng: number | null;
  customer_name: string | null;
}

function toJob(r: DayJobRow): DayJob {
  return {
    id: r.id,
    number: r.number,
    type: r.type,
    dispatchState: r.dispatch_state,
    priorityCode: r.priority_code,
    windowStart: r.window_start,
    windowEnd: r.window_end,
    dueAt: r.due_at,
    estMinutes: r.est_minutes,
    premiseId: r.premise_id,
    addressLine: r.address_line,
    locality: r.locality,
    region: r.region,
    postalCode: r.postal_code,
    lat: r.lat,
    lng: r.lng,
    customerName: r.customer_name,
  };
}

/** Local midnight of `now` + `offsetDays`, and the midnight after, as ISO instants. */
export function dayBounds(now: Date, offsetDays: number): { from: string; to: string } {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays);
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays + 1);
  return { from: start.toISOString(), to: end.toISOString() };
}

/**
 * One day's OPEN jobs in window order, paged. On TODAY (`today: true`) it
 * also carries a job with neither a window nor a deadline, and an open job
 * from an earlier day — still the technician's to do, and nowhere else to
 * show it. A later day's tab carries only that day.
 */
export function listDay(
  s: ScopedRunner,
  opts: { from: string; to: string; today: boolean; limit?: number; offset?: number },
): DayJob[] {
  return s
    .all<DayJobRow>(
      `SELECT wo.id, wo.number, wo.type, wo.dispatch_state, wo.priority_code, wo.window_start, wo.window_end,
              wo.due_at, wo.est_minutes, wo.premise_id,
              p.address_line, p.locality, p.region, p.postal_code, p.lat, p.lng, c.name AS customer_name
         FROM work_order wo
         LEFT JOIN premise p ON p.id = wo.premise_id
         LEFT JOIN customer c ON c.id = wo.customer_id
        WHERE wo.technician_id = :technician_id
          AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
          AND (   (julianday(COALESCE(wo.window_start, wo.due_at)) >= julianday(:from)
                   AND julianday(COALESCE(wo.window_start, wo.due_at)) < julianday(:to))
               OR (:today = 1 AND wo.window_start IS NULL AND wo.due_at IS NULL)
               OR (:today = 1 AND julianday(COALESCE(wo.window_start, wo.due_at)) < julianday(:from)))
        ORDER BY wo.window_start IS NULL, julianday(wo.window_start), wo.due_at IS NULL, julianday(wo.due_at), wo.number
        LIMIT :limit OFFSET :offset`,
      { from: opts.from, to: opts.to, today: opts.today, limit: opts.limit ?? PAGE_SIZE, offset: opts.offset ?? 0 },
    )
    .map(toJob);
}

/**
 * FB-029's LATER tab (decision log 2026-10-31, PO C; `BR-FLD-00135`): every
 * open job of the technician's whose day starts at or after `from` — local
 * midnight starting day 3 — with NO upper limit, paged. A job at 00:00 on
 * day 3 is here and not on the day-after tab, because the day-after tab's
 * `to` is this `from` and both compare with `julianday()`.
 *
 * ORDER across days: the job's LOCAL day first (its window start, else its
 * deadline — the same date the screen puts the heading on, so each heading
 * appears once), then within a day exactly `listDay`'s order: appointment
 * window, deadline, number, NULLs last. `'localtime'` is the handset's own
 * zone, the same zone `dayBounds` and the headings use.
 */
export function listLater(s: ScopedRunner, opts: { from: string; limit?: number; offset?: number }): DayJob[] {
  return s
    .all<DayJobRow>(
      `SELECT wo.id, wo.number, wo.type, wo.dispatch_state, wo.priority_code, wo.window_start, wo.window_end,
              wo.due_at, wo.est_minutes, wo.premise_id,
              p.address_line, p.locality, p.region, p.postal_code, p.lat, p.lng, c.name AS customer_name
         FROM work_order wo
         LEFT JOIN premise p ON p.id = wo.premise_id
         LEFT JOIN customer c ON c.id = wo.customer_id
        WHERE wo.technician_id = :technician_id
          AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
          AND julianday(COALESCE(wo.window_start, wo.due_at)) >= julianday(:from)
        ORDER BY date(COALESCE(wo.window_start, wo.due_at), 'localtime'),
                 wo.window_start IS NULL, julianday(wo.window_start), wo.due_at IS NULL, julianday(wo.due_at), wo.number
        LIMIT :limit OFFSET :offset`,
      { from: opts.from, limit: opts.limit ?? PAGE_SIZE, offset: opts.offset ?? 0 },
    )
    .map(toJob);
}

/**
 * FB-029's ALL tab (decision log 2026-10-31, PO C; `BR-FLD-00135`): every
 * open job the technician holds — overdue and undated included — paged. The
 * same order as `listLater`; a job with neither a window nor a deadline sorts
 * LAST (coordinator judgment, the same entry: under a *No date* heading). A
 * job is in its day tab (or Later) AND here; the ruling accepts that.
 */
export function listAll(s: ScopedRunner, opts: { limit?: number; offset?: number }): DayJob[] {
  return s
    .all<DayJobRow>(
      `SELECT wo.id, wo.number, wo.type, wo.dispatch_state, wo.priority_code, wo.window_start, wo.window_end,
              wo.due_at, wo.est_minutes, wo.premise_id,
              p.address_line, p.locality, p.region, p.postal_code, p.lat, p.lng, c.name AS customer_name
         FROM work_order wo
         LEFT JOIN premise p ON p.id = wo.premise_id
         LEFT JOIN customer c ON c.id = wo.customer_id
        WHERE wo.technician_id = :technician_id
          AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
        ORDER BY COALESCE(wo.window_start, wo.due_at) IS NULL, date(COALESCE(wo.window_start, wo.due_at), 'localtime'),
                 wo.window_start IS NULL, julianday(wo.window_start), wo.due_at IS NULL, julianday(wo.due_at), wo.number
        LIMIT :limit OFFSET :offset`,
      { limit: opts.limit ?? PAGE_SIZE, offset: opts.offset ?? 0 },
    )
    .map(toJob);
}

/**
 * Open jobs by id, in window order — the rows behind a search-index hit list
 * (R41: local first). The ids come from `searchIndex.search`, which is itself
 * scoped, and this re-checks the technician on every row.
 */
export function jobsByIds(s: ScopedRunner, ids: readonly string[]): DayJob[] {
  if (ids.length === 0) return [];
  return s
    .all<DayJobRow>(
      `SELECT wo.id, wo.number, wo.type, wo.dispatch_state, wo.priority_code, wo.window_start, wo.window_end,
              wo.due_at, wo.est_minutes, wo.premise_id,
              p.address_line, p.locality, p.region, p.postal_code, p.lat, p.lng, c.name AS customer_name
         FROM work_order wo
         LEFT JOIN premise p ON p.id = wo.premise_id
         LEFT JOIN customer c ON c.id = wo.customer_id
        WHERE wo.technician_id = :technician_id
          AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
          AND wo.id IN (SELECT value FROM json_each(:ids))
        ORDER BY wo.window_start IS NULL, julianday(wo.window_start), wo.due_at IS NULL, julianday(wo.due_at), wo.number`,
      { ids: JSON.stringify(ids) },
    )
    .map(toJob);
}

/** One of the technician's jobs, open or not. */
export function getJob(s: ScopedRunner, id: string): DayJob | null {
  const row = s.get<DayJobRow>(
    `SELECT wo.id, wo.number, wo.type, wo.dispatch_state, wo.priority_code, wo.window_start, wo.window_end,
            wo.due_at, wo.est_minutes, wo.premise_id,
            p.address_line, p.locality, p.region, p.postal_code, p.lat, p.lng, c.name AS customer_name
       FROM work_order wo
       LEFT JOIN premise p ON p.id = wo.premise_id
       LEFT JOIN customer c ON c.id = wo.customer_id
      WHERE wo.technician_id = :technician_id AND wo.id = :id`,
    { id },
  );
  return row ? toJob(row) : null;
}

export interface DayCounts {
  /** Every open job today, on hold included (*8 left today*). */
  left: number;
  /** Completed today (*3 done*). */
  done: number;
  /** Of `left`, the ones on hold (*1 on hold*). */
  onHold: number;
  /** The open jobs' planned minutes — FF-10's *6h 20m*, FF-12's *your day grows by*. */
  plannedMinutes: number;
}

/**
 * Counted from rows, never a stored tally (US-FLD-078 §5). "Left" includes
 * the job on hold — it is still the technician's to do today; the board's
 * figures (8 left · 3 done · 1 on hold, and eleven jobs on the menu's Today)
 * only add up that way. Our reading, recorded here.
 *
 * ⚠ WHICH ROWS, AND WHY `today` IS REQUIRED (DEF-FLD-10804): the open legs
 * are `listDay`'s own predicate, so a tab's count counts exactly its cards.
 * Until 2026-10-31 this counted an undated job on EVERY day (the day-after
 * tab said *1 job* over an empty list) and left out the overdue jobs Today
 * lists. *Done* is still the day's own range only — a job finished on an
 * earlier day is not done today.
 */
export function dayCounts(s: ScopedRunner, bounds: { from: string; to: string; today: boolean }): DayCounts {
  const row = s.get<{ left: number | null; done: number | null; on_hold: number | null; planned: number | null }>(
    `SELECT
        SUM(CASE WHEN wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
                 THEN 1 ELSE 0 END) AS left,
        SUM(CASE WHEN (wo.closed_at IS NOT NULL OR wo.dispatch_state = 'complete')
                  AND julianday(COALESCE(wo.window_start, wo.due_at)) >= julianday(:from)
                  AND julianday(COALESCE(wo.window_start, wo.due_at)) < julianday(:to)
                 THEN 1 ELSE 0 END) AS done,
        SUM(CASE WHEN wo.closed_at IS NULL AND wo.dispatch_state = 'on_hold' THEN 1 ELSE 0 END) AS on_hold,
        SUM(CASE WHEN wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
                 THEN COALESCE(wo.est_minutes, 0) ELSE 0 END) AS planned
       FROM work_order wo
      WHERE wo.technician_id = :technician_id
        AND (   (julianday(COALESCE(wo.window_start, wo.due_at)) >= julianday(:from)
                 AND julianday(COALESCE(wo.window_start, wo.due_at)) < julianday(:to))
             OR (:today = 1 AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
                 AND (   (wo.window_start IS NULL AND wo.due_at IS NULL)
                      OR julianday(COALESCE(wo.window_start, wo.due_at)) < julianday(:from))))`,
    { from: bounds.from, to: bounds.to, today: bounds.today },
  );
  return {
    left: row?.left ?? 0,
    done: row?.done ?? 0,
    onHold: row?.on_hold ?? 0,
    plannedMinutes: row?.planned ?? 0,
  };
}

/** A list tab's figures (FB-029): its open jobs, the ones on hold among them, their planned minutes. */
export interface ListCounts {
  left: number;
  onHold: number;
  plannedMinutes: number;
}

/** Later's figures — counted over exactly `listLater`'s rows, every page, never the page shown. */
export function laterCounts(s: ScopedRunner, opts: { from: string }): ListCounts {
  const row = s.get<{ left: number | null; on_hold: number | null; planned: number | null }>(
    `SELECT COUNT(*) AS left,
            SUM(CASE WHEN wo.dispatch_state = 'on_hold' THEN 1 ELSE 0 END) AS on_hold,
            SUM(COALESCE(wo.est_minutes, 0)) AS planned
       FROM work_order wo
      WHERE wo.technician_id = :technician_id
        AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')
        AND julianday(COALESCE(wo.window_start, wo.due_at)) >= julianday(:from)`,
    { from: opts.from },
  );
  return { left: row?.left ?? 0, onHold: row?.on_hold ?? 0, plannedMinutes: row?.planned ?? 0 };
}

/** All's figures — counted over exactly `listAll`'s rows, every page. */
export function allCounts(s: ScopedRunner): ListCounts {
  const row = s.get<{ left: number | null; on_hold: number | null; planned: number | null }>(
    `SELECT COUNT(*) AS left,
            SUM(CASE WHEN wo.dispatch_state = 'on_hold' THEN 1 ELSE 0 END) AS on_hold,
            SUM(COALESCE(wo.est_minutes, 0)) AS planned
       FROM work_order wo
      WHERE wo.technician_id = :technician_id
        AND wo.closed_at IS NULL AND COALESCE(wo.dispatch_state, '') NOT IN ('complete', 'cancelled')`,
  );
  return { left: row?.left ?? 0, onHold: row?.on_hold ?? 0, plannedMinutes: row?.planned ?? 0 };
}

export interface ReadCounts {
  /** Meters on open routes with nothing captured yet. */
  left: number;
  /** Read, including read with a problem. */
  read: number;
  /** Could not be read. */
  couldNot: number;
}

/** FF-63's Reads tile, counted from `route_read` on routes not turned in. */
export function readCounts(s: ScopedRunner): ReadCounts {
  const row = s.get<{ left: number | null; read: number | null; could_not: number | null }>(
    `SELECT
        SUM(CASE WHEN rr.reader_status IS NULL THEN 1 ELSE 0 END) AS left,
        SUM(CASE WHEN rr.reader_status IN ('read', 'read_with_problem') THEN 1 ELSE 0 END) AS read,
        SUM(CASE WHEN rr.reader_status = 'could_not_read' THEN 1 ELSE 0 END) AS could_not
       FROM route_read rr
       JOIN route r ON r.technician_id = rr.technician_id AND r.id = rr.route_id
      WHERE rr.technician_id = :technician_id AND r.status <> 'turned_in'`,
  );
  return { left: row?.left ?? 0, read: row?.read ?? 0, couldNot: row?.could_not ?? 0 };
}

export interface StopToRead {
  stopId: string;
  routeCode: string | null;
  addressLine: string | null;
  meters: number;
  lat: number | null;
  lng: number | null;
  walkPosition: number;
}

/** Every stop with a meter still to read, routes in their window order, stops in walk order. Paged. */
export function stopsToRead(s: ScopedRunner, limit = PAGE_SIZE): StopToRead[] {
  return s
    .all<{
      stop_id: string;
      code: string | null;
      address_line: string | null;
      meters: number;
      lat: number | null;
      lng: number | null;
      walk_position: number;
    }>(
      `SELECT st.id AS stop_id, r.code, p.address_line, COUNT(rr.id) AS meters,
              COALESCE(st.lat, p.lat) AS lat, COALESCE(st.lng, p.lng) AS lng, st.walk_position
         FROM route_stop st
         JOIN route r ON r.technician_id = st.technician_id AND r.id = st.route_id
         JOIN route_read rr ON rr.technician_id = st.technician_id AND rr.stop_id = st.id AND rr.reader_status IS NULL
         LEFT JOIN premise p ON p.id = st.premise_id
        WHERE st.technician_id = :technician_id AND r.status <> 'turned_in'
        GROUP BY st.id
        ORDER BY r.window_start IS NULL, julianday(r.window_start), r.code, st.walk_position
        LIMIT :limit`,
      { limit },
    )
    .map((r) => ({
      stopId: r.stop_id,
      routeCode: r.code,
      addressLine: r.address_line,
      meters: r.meters,
      lat: r.lat,
      lng: r.lng,
      walkPosition: r.walk_position,
    }));
}

export interface WaitingToSend {
  /** Captured items not yet with the server (pending, sending, refused — R60), photo declarations excluded. */
  items: number;
  /** Photographs whose bytes are not uploaded yet. */
  photos: number;
  /** When the server last answered one of this technician's items, or null. */
  lastSentAt: string | null;
}

/** The sync strip — counted from the outbox and the photo queue (R32: a number, not a word). */
export function waitingToSend(s: ScopedRunner): WaitingToSend {
  // The counts are the outbox's and the photo table's own (DEF-FLD-10363: one
  // definition of "waiting", so Home and the sign-out sheet cannot disagree).
  const row = s.get<{ last_sent: string | null }>(
    `SELECT MAX(o.settled_at) AS last_sent FROM outbox o WHERE o.technician_id = :technician_id`,
  );
  return { items: outboxQ.countUnsentMine(s), photos: photoQ.countWaitingMine(s), lastSentAt: row?.last_sent ?? null };
}

export interface HoursToday {
  totalMinutes: number;
  byKind: { travel: number; labour: number; admin: number };
}

/**
 * *4h 52m today* — the technician's own `crew_time` started today, by kind.
 * A row still running counts up to `now`.
 */
export function hoursToday(s: ScopedRunner, bounds: { from: string; to: string }, now: Date): HoursToday {
  const rows = s.all<{ kind: 'travel' | 'labour' | 'admin'; minutes: number | null }>(
    `SELECT ct.kind, SUM((julianday(COALESCE(ct.ended_at, :now)) - julianday(ct.started_at)) * 1440) AS minutes
       FROM crew_time ct
      WHERE ct.technician_id = :technician_id
        AND julianday(ct.started_at) >= julianday(:from) AND julianday(ct.started_at) < julianday(:to)
      GROUP BY ct.kind`,
    { from: bounds.from, to: bounds.to, now: now.toISOString() },
  );
  const byKind = { travel: 0, labour: 0, admin: 0 };
  for (const r of rows) byKind[r.kind] = Math.max(0, Math.round(r.minutes ?? 0));
  return { totalMinutes: byKind.travel + byKind.labour + byKind.admin, byKind };
}
