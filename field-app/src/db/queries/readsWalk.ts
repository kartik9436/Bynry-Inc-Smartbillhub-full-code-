/**
 * What the meter-reading screens (RW-01 … RW-29) read, joined the way they
 * show it. Every statement is scoped to the reader (R133): the technician's
 * tables are filtered on `:technician_id`, and the reference tables they join
 * (premise, asset, customer) belong to nobody.
 *
 * Counts are DERIVED from the readings every time (Mobile data §11, RW-22:
 * *"counted from the readings themselves, never a stored tally"*).
 *
 * Added by the reads wave. One file, so the per-table files (`route.ts`,
 * `routeStop.ts`, `routeRead.ts`) stay what they are.
 */
import type { ScopedRunner } from '../scoped';

/** A route as RW-01, RW-02 and RW-28 draw it. */
export interface RouteCard {
  id: string;
  code: string | null;
  service: string | null;
  area: string | null;
  read_type: string | null;
  cycle: string | null;
  window_start: string | null;
  window_end: string | null;
  notes: string | null;
  status: 'assigned' | 'in_progress' | 'turned_in';
  turned_in_at: string | null;
  extra: string | null;
  stops: number;
  meters: number;
  subs: number;
  done: number;
  read: number;
  could_not: number;
  flagged: number;
  refused: number;
  last_captured_at: string | null;
}

const CARD_COLUMNS = `
  r.id, r.code, r.service, r.area, r.read_type, r.cycle, r.window_start, r.window_end, r.notes, r.status,
  r.turned_in_at, r.extra,
  (SELECT COUNT(*) FROM route_stop st WHERE st.technician_id = :technician_id AND st.route_id = r.id) AS stops,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id) AS meters,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id
      AND rr.parent_asset_id IS NOT NULL) AS subs,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id
      AND rr.state != 'unread') AS done,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id
      AND rr.reader_status IN ('read','read_with_problem')) AS read,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id
      AND rr.reader_status = 'could_not_read') AS could_not,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id
      AND rr.warned_accepted = 1) AS flagged,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id
      AND rr.state = 'refused') AS refused,
  (SELECT MAX(rr.captured_at) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = r.id)
      AS last_captured_at`;

/** RW-01 / RW-28: the reader's routes, one page. */
export function routeCards(s: ScopedRunner, limit = 50, offset = 0): RouteCard[] {
  return s.all<RouteCard>(
    `SELECT ${CARD_COLUMNS} FROM route r WHERE r.technician_id = :technician_id
      ORDER BY r.status = 'turned_in', r.window_start, r.code LIMIT :limit OFFSET :offset`,
    { limit, offset },
  );
}

export function routeCard(s: ScopedRunner, id: string): RouteCard | undefined {
  return s.get<RouteCard>(`SELECT ${CARD_COLUMNS} FROM route r WHERE r.technician_id = :technician_id AND r.id = :id`, {
    id,
  });
}

/** A stop — the address (R74) — with what is left at it. */
export interface StopCard {
  id: string;
  route_id: string;
  premise_id: string;
  walk_position: number;
  lat: number | null;
  lng: number | null;
  access_notes: string | null;
  hazard: string | null;
  address_line: string | null;
  locality: string | null;
  meters: number;
  unread: number;
  could_not: number;
  last_reason: string | null;
  last_captured_at: string | null;
}

const STOP_COLUMNS = `
  st.id, st.route_id, st.premise_id, st.walk_position,
  COALESCE(st.lat, p.lat) AS lat, COALESCE(st.lng, p.lng) AS lng,
  st.access_notes, st.hazard, p.address_line, p.locality,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.stop_id = st.id) AS meters,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.stop_id = st.id
      AND rr.state = 'unread') AS unread,
  (SELECT COUNT(*) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.stop_id = st.id
      AND rr.reader_status = 'could_not_read') AS could_not,
  (SELECT rr.no_read_reason FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.stop_id = st.id
      AND rr.reader_status = 'could_not_read' ORDER BY rr.captured_at DESC LIMIT 1) AS last_reason,
  (SELECT MAX(rr.captured_at) FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.stop_id = st.id)
      AS last_captured_at`;

export type StopFilter = 'all' | 'left' | 'not_read' | 'came_back' | 'flagged';

const STOP_FILTERS: Record<StopFilter, string> = {
  all: '1 = 1',
  // RW-05 and RW-23 "Not read": something at the address still has no reading,
  // or a reading the reader could not take.
  left: 'unread > 0 OR could_not > 0',
  not_read: 'unread > 0 OR could_not > 0',
  // RW-23 "Came back to": an address left with a reason, to come back to.
  came_back: 'could_not > 0',
  flagged: `EXISTS (SELECT 1 FROM route_read f WHERE f.technician_id = :technician_id AND f.stop_id = x.id
                     AND f.warned_accepted = 1)`,
};

/**
 * RW-05 / RW-23: the stops of a route. `order` is either the office's walk
 * order, or nearest to `from` — computed here from the points that came down
 * with the route, so it needs no signal (R76). `k` is cos²(latitude), so a
 * degree of longitude is weighed as the shorter distance it is.
 */
export function stops(
  s: ScopedRunner,
  routeId: string,
  opts: { order: 'walk' | 'nearest'; from?: { lat: number; lng: number } | null; filter?: StopFilter; limit?: number; offset?: number },
): StopCard[] {
  const from = opts.order === 'nearest' ? opts.from ?? null : null;
  const k = from ? Math.cos((from.lat * Math.PI) / 180) ** 2 : 1;
  const orderBy = from
    ? `CASE WHEN lat IS NULL THEN 1 ELSE 0 END,
       (lat - :lat) * (lat - :lat) + (lng - :lng) * (lng - :lng) * :k, walk_position`
    : 'walk_position';
  return s.all<StopCard>(
    `SELECT * FROM (SELECT ${STOP_COLUMNS} FROM route_stop st LEFT JOIN premise p ON p.id = st.premise_id
                     WHERE st.technician_id = :technician_id AND st.route_id = :route_id) x
      WHERE ${STOP_FILTERS[opts.filter ?? 'all']}
      ORDER BY ${orderBy} LIMIT :limit OFFSET :offset`,
    {
      route_id: routeId,
      lat: from?.lat ?? 0,
      lng: from?.lng ?? 0,
      k,
      limit: opts.limit ?? 1000,
      offset: opts.offset ?? 0,
    },
  );
}

export function stop(s: ScopedRunner, id: string): StopCard | undefined {
  return s.get<StopCard>(
    `SELECT ${STOP_COLUMNS} FROM route_stop st LEFT JOIN premise p ON p.id = st.premise_id
      WHERE st.technician_id = :technician_id AND st.id = :id`,
    { id },
  );
}

/** How many stops a filter holds — the counts on RW-23's tabs. */
export function stopCount(s: ScopedRunner, routeId: string, filter: StopFilter): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM (SELECT ${STOP_COLUMNS} FROM route_stop st LEFT JOIN premise p ON p.id = st.premise_id
                     WHERE st.technician_id = :technician_id AND st.route_id = :route_id) x
        WHERE ${STOP_FILTERS[filter]}`,
      { route_id: routeId },
    )?.n ?? 0
  );
}

/** A meter on the route, with what the stop and the reading show of it. */
export interface MeterRead {
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
  serial: string | null;
  badge: string | null;
  device_id: string | null;
  size: string | null;
  asset_service: string | null;
  asset_extra: string | null;
  customer_name: string | null;
  account_number: string | null;
  address_line: string | null;
  stop_lat: number | null;
  stop_lng: number | null;
  premise_id: string | null;
  /** MQ-033 — see `routeRead.RouteReadRow`. */
  read_format_version_id: string | null;
  answers: string | null;
  /** 0007 (FB-030) — the server's FB-022 flag on a refilled reading; NULL on the phone's own. */
  lower_than_last: number | null;
}

const METER_COLUMNS = `
  rr.id, rr.route_id, rr.stop_id, rr.asset_id, rr.parent_asset_id, rr.account_id, rr.previous_value,
  rr.expected_min, rr.expected_max, rr.photo_required, rr.value, rr.unit, rr.reader_status, rr.no_read_reason,
  rr.warned_accepted, rr.lat, rr.lng, rr.accuracy_m, rr.fix_quality, rr.metres_from_record, rr.captured_at,
  rr.captured_by, rr.identified_by, rr.off_route, rr.read_method, rr.remark, rr.remark_source, rr.capture_key, rr.state,
  rr.read_format_version_id, rr.answers, rr.lower_than_last,
  a.serial, a.badge, a.device_id, a.size, a.service AS asset_service, a.extra AS asset_extra,
  c.name AS customer_name, c.account_number,
  p.address_line, COALESCE(st.lat, p.lat) AS stop_lat, COALESCE(st.lng, p.lng) AS stop_lng, st.premise_id`;

const METER_FROM = `
  FROM route_read rr
  LEFT JOIN asset a ON a.id = rr.asset_id
  LEFT JOIN customer c ON c.id = rr.account_id
  LEFT JOIN route_stop st ON st.technician_id = :technician_id AND st.id = rr.stop_id
  LEFT JOIN premise p ON p.id = st.premise_id`;

/** RW-06 / RW-12: every meter at one address — masters before their subs. */
export function metersAtStop(s: ScopedRunner, stopId: string, limit = 200, offset = 0): MeterRead[] {
  return s.all<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM}
      WHERE rr.technician_id = :technician_id AND rr.stop_id = :stop_id
      ORDER BY rr.parent_asset_id IS NOT NULL, a.serial, rr.id LIMIT :limit OFFSET :offset`,
    { stop_id: stopId, limit, offset },
  );
}

export function meter(s: ScopedRunner, id: string): MeterRead | undefined {
  return s.get<MeterRead>(`SELECT ${METER_COLUMNS} ${METER_FROM} WHERE rr.technician_id = :technician_id AND rr.id = :id`, {
    id,
  });
}

/** The meter on a route a scanned or listed asset is — RW-11's match. */
export function meterForAsset(s: ScopedRunner, routeId: string, assetId: string): MeterRead | undefined {
  return s.get<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM}
      WHERE rr.technician_id = :technician_id AND rr.route_id = :route_id AND rr.asset_id = :asset_id`,
    { route_id: routeId, asset_id: assetId },
  );
}

/** Any meter of mine for an asset, on any route on this phone. */
export function anyMeterForAsset(s: ScopedRunner, assetId: string): MeterRead | undefined {
  return s.get<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM} WHERE rr.technician_id = :technician_id AND rr.asset_id = :asset_id
      ORDER BY rr.off_route, rr.id LIMIT 1`,
    { asset_id: assetId },
  );
}

/** RW-12: a master's sub-meters, by the master's asset. */
export function subsOf(s: ScopedRunner, routeId: string, masterAssetId: string, limit = 200, offset = 0): MeterRead[] {
  return s.all<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM}
      WHERE rr.technician_id = :technician_id AND rr.route_id = :route_id AND rr.parent_asset_id = :master
      ORDER BY a.serial, rr.id LIMIT :limit OFFSET :offset`,
    { route_id: routeId, master: masterAssetId, limit, offset },
  );
}

/** The next meter to read at a stop after `afterId`, or the first unread one. */
export function nextUnreadAtStop(s: ScopedRunner, stopId: string, exceptId: string | null): MeterRead | undefined {
  return s.get<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM}
      WHERE rr.technician_id = :technician_id AND rr.stop_id = :stop_id AND rr.state = 'unread'
        AND rr.id != :except
      ORDER BY rr.parent_asset_id IS NOT NULL, a.serial, rr.id LIMIT 1`,
    { stop_id: stopId, except: exceptId ?? '' },
  );
}

function likeTerm(text: string): string {
  return `%${text.replace(/[\\%_]/g, (m) => `\\${m}`)}%`;
}

/** RW-08: serial, badge, device ID, address or account — of what is on this phone. */
export function findOnPhone(s: ScopedRunner, text: string, limit = 50, offset = 0): MeterRead[] {
  const term = likeTerm(text.trim());
  return s.all<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM}
      WHERE rr.technician_id = :technician_id
        AND (a.serial LIKE :term ESCAPE '\\' OR a.badge LIKE :term ESCAPE '\\' OR a.device_id LIKE :term ESCAPE '\\'
             OR p.address_line LIKE :term ESCAPE '\\' OR c.account_number LIKE :term ESCAPE '\\'
             OR c.name LIKE :term ESCAPE '\\')
      ORDER BY a.serial, rr.id LIMIT :limit OFFSET :offset`,
    { term, limit, offset },
  );
}

/** RW-22 / RW-25 / RW-26 / RW-27: the route, counted from its readings. */
export interface RouteTally {
  total: number;
  done: number;
  read: number;
  could_not: number;
  flagged: number;
  unread: number;
  pending: number;
  sending: number;
  accepted: number;
  duplicate: number;
  refused: number;
  held: number;
  raised: number;
  started_at: string | null;
}

export function tally(s: ScopedRunner, routeId: string): RouteTally {
  const row = s.get<RouteTally>(
    `SELECT COUNT(*) AS total,
            COALESCE(SUM(rr.state != 'unread'), 0) AS done,
            COALESCE(SUM(rr.reader_status IN ('read','read_with_problem')), 0) AS read,
            COALESCE(SUM(rr.reader_status = 'could_not_read'), 0) AS could_not,
            COALESCE(SUM(rr.warned_accepted = 1), 0) AS flagged,
            COALESCE(SUM(rr.state = 'unread'), 0) AS unread,
            COALESCE(SUM(rr.state = 'pending'), 0) AS pending,
            COALESCE(SUM(rr.state = 'sending'), 0) AS sending,
            COALESCE(SUM(rr.state = 'accepted'), 0) AS accepted,
            COALESCE(SUM(rr.state = 'duplicate'), 0) AS duplicate,
            COALESCE(SUM(rr.state = 'refused'), 0) AS refused,
            COALESCE(SUM(rr.state = 'held_for_review'), 0) AS held,
            (SELECT COUNT(*) FROM outbox o WHERE o.technician_id = :technician_id AND o.kind = 'route_finding'
                AND o.route_id = :route_id) AS raised,
            MIN(rr.captured_at) AS started_at
       FROM route_read rr WHERE rr.technician_id = :technician_id AND rr.route_id = :route_id`,
    { route_id: routeId },
  );
  return (
    row ?? {
      total: 0, done: 0, read: 0, could_not: 0, flagged: 0, unread: 0, pending: 0, sending: 0, accepted: 0,
      duplicate: 0, refused: 0, held: 0, raised: 0, started_at: null,
    }
  );
}

/** RW-22 *By the hour*: when each reading was taken, bucketed by the screen. */
export function captureTimes(s: ScopedRunner, routeId: string, limit = 5000): string[] {
  return s
    .all<{ captured_at: string }>(
      `SELECT rr.captured_at FROM route_read rr
        WHERE rr.technician_id = :technician_id AND rr.route_id = :route_id AND rr.captured_at IS NOT NULL
        ORDER BY rr.captured_at LIMIT :limit`,
      { route_id: routeId, limit },
    )
    .map((r) => r.captured_at);
}

/** RW-24 / RW-22: the route's photographs, with the address each was taken at. */
export interface RoutePhoto {
  id: string;
  local_path: string;
  state: 'pending' | 'uploading' | 'uploaded' | 'failed';
  captured_at: string;
  lat: number | null;
  lng: number | null;
  bytes: number;
  read_id: string | null;
  no_read_reason: string | null;
  warned_accepted: number | null;
  stop_id: string | null;
  address_line: string | null;
}

export function photos(s: ScopedRunner, routeId: string, limit = 200, offset = 0): RoutePhoto[] {
  return s.all<RoutePhoto>(
    `SELECT ph.id, ph.local_path, ph.state, ph.captured_at, ph.lat, ph.lng, ph.bytes,
            rr.id AS read_id, rr.no_read_reason, rr.warned_accepted, st.id AS stop_id, p.address_line
       FROM photo ph
       LEFT JOIN route_read rr ON rr.technician_id = :technician_id AND rr.id = ph.route_read_id
       LEFT JOIN route_stop st ON st.technician_id = :technician_id AND st.id = rr.stop_id
       LEFT JOIN premise p ON p.id = st.premise_id
      WHERE ph.technician_id = :technician_id AND ph.route_id = :route_id
      ORDER BY st.walk_position, ph.captured_at LIMIT :limit OFFSET :offset`,
    { route_id: routeId, limit, offset },
  );
}

/** One photograph of one reading, for its thumbnails and its viewer. */
export interface ReadingPhoto {
  id: string;
  local_path: string;
  file_deleted: number;
  captured_at: string;
}

/**
 * Every photograph of ONE reading, oldest first — saved with it, added after
 * it was saved, or kept from before it was changed (DEF-FLD-10631, FB-003). A
 * photo names its reading itself (`photo.route_read_id`, migration 0006);
 * the reading's capture key is never the join, because it changes when the
 * reading is saved again and a photo added later is its own act.
 */
export function readingPhotos(s: ScopedRunner, readId: string, limit = 50): ReadingPhoto[] {
  return s.all<ReadingPhoto>(
    `SELECT ph.id, ph.local_path, ph.file_deleted, ph.captured_at
       FROM photo ph
      WHERE ph.technician_id = :technician_id AND ph.route_read_id = :read_id
      ORDER BY ph.captured_at, ph.rowid LIMIT :limit`,
    { read_id: readId, limit },
  );
}

/** How many photographs ONE reading has — every one, not a page of them. */
export function readingPhotoCount(s: ScopedRunner, readId: string): number {
  return (
    s.get<{ n: number }>(
      'SELECT COUNT(*) AS n FROM photo ph WHERE ph.technician_id = :technician_id AND ph.route_read_id = :read_id',
      { read_id: readId },
    )?.n ?? 0
  );
}

export function photoCounts(s: ScopedRunner, routeId: string): { total: number; sent: number; waiting: number; bytes_waiting: number } {
  return (
    s.get<{ total: number; sent: number; waiting: number; bytes_waiting: number }>(
      `SELECT COUNT(*) AS total, COALESCE(SUM(ph.state = 'uploaded'), 0) AS sent,
              COALESCE(SUM(ph.state != 'uploaded'), 0) AS waiting,
              COALESCE(SUM(CASE WHEN ph.state != 'uploaded' THEN ph.bytes ELSE 0 END), 0) AS bytes_waiting
         FROM photo ph WHERE ph.technician_id = :technician_id AND ph.route_id = :route_id`,
      { route_id: routeId },
    ) ?? { total: 0, sent: 0, waiting: 0, bytes_waiting: 0 }
  );
}

/** RW-27: what the server refused, with its reason, so the reader can act. */
export interface Refusal {
  read_id: string;
  serial: string | null;
  refusal: string | null;
}

export function refusals(s: ScopedRunner, routeId: string, limit = 50, offset = 0): Refusal[] {
  return s.all<Refusal>(
    `SELECT rr.id AS read_id, a.serial, o.refusal
       FROM route_read rr
       LEFT JOIN outbox o ON o.technician_id = :technician_id AND o.id = rr.capture_key
       LEFT JOIN asset a ON a.id = rr.asset_id
      WHERE rr.technician_id = :technician_id AND rr.route_id = :route_id AND rr.state = 'refused'
      ORDER BY rr.captured_at LIMIT :limit OFFSET :offset`,
    { route_id: routeId, limit, offset },
  );
}

/** RW-01's sync line: the last time the server answered anything of mine. */
export function lastSentAt(s: ScopedRunner): string | null {
  return s.get<{ at: string | null }>('SELECT MAX(o.settled_at) AS at FROM outbox o WHERE o.technician_id = :technician_id')?.at ?? null;
}

/**
 * RW-19 *Read it anyway*: a meter the system knows, not on this route, gets a
 * reading row of its own marked off-route (R84). The office decides where it
 * belongs; the handset never moves it onto the route.
 */
export function insertOffRoute(
  s: ScopedRunner,
  r: { id: string; routeId: string; stopId: string; assetId: string; accountId: string | null; previousValue: string | null; unit: string },
  now: string,
): void {
  if (!r.unit) throw new Error('a reading never exists without its unit (hard rule 3)');
  s.run(
    `INSERT INTO route_read (technician_id, id, route_id, stop_id, asset_id, account_id, previous_value, unit,
                             off_route, updated_at)
     VALUES (:technician_id, :id, :route_id, :stop_id, :asset_id, :account_id, :previous_value, :unit, 1, :now)`,
    {
      id: r.id,
      route_id: r.routeId,
      stop_id: r.stopId,
      asset_id: r.assetId,
      account_id: r.accountId,
      previous_value: r.previousValue,
      unit: r.unit,
      now,
    },
  );
}

/** RW-25 Turn it in: the route moves to in progress on its first reading. */
export function markInProgress(s: ScopedRunner, routeId: string, at: string): void {
  s.run(
    `UPDATE route SET status = 'in_progress', updated_at = :at
      WHERE technician_id = :technician_id AND id = :id AND status = 'assigned'`,
    { id: routeId, at },
  );
}

// ── FB-030 · RW-28 My reads, paged, and its drill into each reading ─────────

/** RW-28's three tabs (R120: what was read, never how fast). */
export type MinePeriod = 'week' | 'cycle' | 'earlier';

const MINE_PERIOD = `
  CASE WHEN COALESCE(c.last_captured_at, c.turned_in_at) >= :week_from THEN 'week'
       WHEN :latest IS NOT NULL AND c.cycle = :latest THEN 'cycle'
       ELSE 'earlier' END`;

/** The cycle of the reader's latest route — what *This cycle* means. */
export function latestCycle(s: ScopedRunner): string | null {
  return (
    s.get<{ cycle: string | null }>(
      `SELECT cycle FROM route WHERE technician_id = :technician_id ORDER BY window_start DESC, code LIMIT 1`,
    )?.cycle ?? null
  );
}

/**
 * FB-030 — RW-28's routes for one tab, ONE PAGE, paged in SQL with no cap
 * (NFR-3, NFR-5). It read the first 200 routes and filtered them in the
 * screen until then. Only routes with something read on them; newest first.
 */
export function mineCards(
  s: ScopedRunner,
  opts: { period: MinePeriod; weekFrom: string; latest: string | null; limit: number; offset?: number },
): RouteCard[] {
  return s.all<RouteCard>(
    `SELECT * FROM (SELECT ${CARD_COLUMNS} FROM route r WHERE r.technician_id = :technician_id) c
      WHERE c.done > 0 AND ${MINE_PERIOD} = :period
      ORDER BY COALESCE(c.last_captured_at, c.turned_in_at) DESC, c.code, c.id
      LIMIT :limit OFFSET :offset`,
    { period: opts.period, week_from: opts.weekFrom, latest: opts.latest, limit: opts.limit, offset: opts.offset ?? 0 },
  );
}

/** RW-28's totals for one tab, over EVERY route in it (not one page). */
export function mineTotals(
  s: ScopedRunner,
  opts: { period: MinePeriod; weekFrom: string; latest: string | null },
): { routes: number; read: number; could_not: number } {
  const row = s.get<{ routes: number; read: number | null; could_not: number | null }>(
    `SELECT COUNT(*) AS routes, SUM(c.read) AS read, SUM(c.could_not) AS could_not
       FROM (SELECT ${CARD_COLUMNS} FROM route r WHERE r.technician_id = :technician_id) c
      WHERE c.done > 0 AND ${MINE_PERIOD} = :period`,
    { period: opts.period, week_from: opts.weekFrom, latest: opts.latest },
  );
  return { routes: row?.routes ?? 0, read: row?.read ?? 0, could_not: row?.could_not ?? 0 };
}

/** FB-030 — every reading TAKEN on one route (unread meters are not history), in the order taken. Paged. */
export function takenOnRoute(s: ScopedRunner, routeId: string, limit = 50, offset = 0): MeterRead[] {
  return s.all<MeterRead>(
    `SELECT ${METER_COLUMNS} ${METER_FROM}
      WHERE rr.technician_id = :technician_id AND rr.route_id = :route_id AND rr.state != 'unread'
      ORDER BY rr.captured_at, rr.id LIMIT :limit OFFSET :offset`,
    { route_id: routeId, limit, offset },
  );
}
