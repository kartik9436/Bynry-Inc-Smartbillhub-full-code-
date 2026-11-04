/**
 * A utility's read formats on the handset (MQ-033, `CR-192-BRC10` task 12;
 * migration 0004): the PUBLISHED versions, kept by id and shared by every
 * reader on the phone (they hold the utility's questions, nobody's work), and
 * each route's resolved version per service (scoped, on `route`).
 *
 * A published version never changes on the server (BR-MET-1213), so a version
 * already held is kept as it is; the walk asks nothing of the network.
 */
import type { TenantDb } from '../database';
import { fromJson, toJson } from '../json';
import type { ScopedRunner } from '../scoped';

/** One question, as the server's `question_dict` serves it (`apps/metering/read_formats.py`). */
export interface StoredQuestion {
  id: string;
  seq: number;
  key: string;
  label: string;
  help_text: string | null;
  data_type: string;
  options: string[] | null;
  is_required: boolean;
  asked_when: string;
  show_if: { question_key: string; answer: unknown } | null;
  raise_work?: unknown;
}

export interface StoredVersion {
  id: string;
  read_format_id: string;
  name: string | null;
  service: string | null;
  version_no: number | null;
  questions: StoredQuestion[];
}

/** One route's resolution for one service — what `route.read_formats[]` named. */
export interface RouteFormat {
  service: string;
  source: string | null;
  version_id: string;
}

interface VersionRow {
  id: string;
  read_format_id: string;
  name: string | null;
  service: string | null;
  version_no: number | null;
  questions: string;
}

/** Keep a published version. One already held is left as it is (a published version never changes). */
export function putVersion(
  db: TenantDb,
  v: { id: string; read_format_id: string; version_no?: number | null; read_format?: { name?: string | null; service?: string | null } | null; questions: readonly unknown[] },
  now: string,
): void {
  db.ref.run(
    `INSERT INTO read_format_version (id, read_format_id, name, service, version_no, questions, updated_at)
     VALUES (:id, :read_format_id, :name, :service, :version_no, :questions, :now)
     ON CONFLICT (id) DO NOTHING`,
    {
      id: v.id,
      read_format_id: v.read_format_id,
      name: v.read_format?.name ?? null,
      service: v.read_format?.service ?? null,
      version_no: v.version_no ?? null,
      questions: toJson(v.questions) ?? '[]',
      now,
    },
  );
}

export function hasVersion(db: TenantDb, id: string): boolean {
  return db.ref.get<{ n: number }>('SELECT COUNT(*) AS n FROM read_format_version WHERE id = :id', { id })?.n === 1;
}

export function getVersion(db: TenantDb, id: string): StoredVersion | null {
  const row = db.ref.get<VersionRow>('SELECT id, read_format_id, name, service, version_no, questions FROM read_format_version WHERE id = :id', { id });
  if (!row) return null;
  const questions = (fromJson<StoredQuestion[]>(row.questions) ?? []).slice().sort((a, b) => a.seq - b.seq);
  return { ...row, questions };
}

/** Store the route's resolution as served; entries with no format are not kept. */
export function setRouteFormats(s: ScopedRunner, routeId: string, formats: readonly RouteFormat[]): void {
  s.run('UPDATE route SET read_formats = :formats WHERE technician_id = :technician_id AND id = :id', {
    id: routeId,
    formats: formats.length ? toJson(formats) : null,
  });
}

export function routeFormats(s: ScopedRunner, routeId: string): RouteFormat[] {
  const row = s.get<{ read_formats: string | null }>('SELECT read_formats FROM route WHERE technician_id = :technician_id AND id = :id', { id: routeId });
  return fromJson<RouteFormat[]>(row?.read_formats) ?? [];
}

/**
 * DEF-FLD-10598 — the route names a version this phone does not hold (its
 * download failed). Readings still save, without the questions, so RW-05
 * says so rather than reading silently.
 */
export function missingVersion(s: ScopedRunner, db: TenantDb, routeId: string): boolean {
  return routeFormats(s, routeId).some((f) => !hasVersion(db, f.version_id));
}

/**
 * `once_per_stop`: the answers already given at this stop (a stop is one
 * route's premises) by OTHER readings, with when each was taken — the caller
 * keeps the ones of the same capture day.
 */
export function answersAtStop(s: ScopedRunner, stopId: string, exceptReadId: string): Array<{ captured_at: string; answers: string }> {
  return s.all(
    `SELECT captured_at, answers FROM route_read
      WHERE technician_id = :technician_id AND stop_id = :stop_id AND id != :except
        AND answers IS NOT NULL AND captured_at IS NOT NULL
      ORDER BY captured_at LIMIT 500`,
    { stop_id: stopId, except: exceptReadId },
  );
}
