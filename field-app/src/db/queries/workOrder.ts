/**
 * `work_order` — the day and the next three, per technician (R132). Mirror:
 * the server wins on every column it sends (R58); `closed_at` is the handset's
 * own and an upsert never touches it.
 */
import type { QueryRunner } from '../database';
import { toJson } from '../json';
import type { ScopedRunner } from '../scoped';

export interface WorkOrderRow {
  technician_id: string;
  id: string;
  number: string | null;
  type: string | null;
  state: string | null;
  dispatch_state: string | null;
  outcome: string | null;
  priority_code: string | null;
  priority_rank: number | null;
  template_id: string | null;
  template_version: string | null;
  premise_id: string | null;
  customer_id: string | null;
  account_id: string | null;
  asset_id: string | null;
  window_start: string | null;
  window_end: string | null;
  due_at: string | null;
  est_minutes: number | null;
  access_notes: string | null;
  hazards: string | null;
  gate_code: string | null;
  closed_at: string | null;
  needs_bundle: number;
  body: string | null;
  extra: string | null;
  server_updated_at: string | null;
  updated_at: string;
}

/** What the server's job card gives (apps/work/mobile.py `_job_card`). */
export interface WorkOrderFromServer {
  id: string;
  number: string | null;
  type: string | null;
  state: string | null;
  dispatchState: string | null;
  priorityCode: string | null;
  priorityRank: number | null;
  premiseId: string | null;
  /** The card's meter (DEF-FLD-10582). Server wins: absent → none. */
  assetId?: string | null;
  windowStart: string | null;
  windowEnd: string | null;
  dueAt: string | null;
  estMinutes: number | null;
  accessNotes: string | null;
  hazards: string | null;
  gateCode: string | null;
  extra: Record<string, unknown> | null;
  serverUpdatedAt: string | null;
}

export function upsertFromServer(s: ScopedRunner, w: WorkOrderFromServer, now: string): void {
  s.run(
    `INSERT INTO work_order (technician_id, id, number, type, state, dispatch_state, priority_code, priority_rank,
                             premise_id, asset_id, window_start, window_end, due_at, est_minutes, access_notes, hazards,
                             gate_code, needs_bundle, extra, server_updated_at, updated_at)
     VALUES (:technician_id, :id, :number, :type, :state, :dispatch_state, :priority_code, :priority_rank,
             :premise_id, :asset_id, :window_start, :window_end, :due_at, :est_minutes, :access_notes, :hazards,
             :gate_code, 1, :extra, :server_updated_at, :now)
     ON CONFLICT (technician_id, id) DO UPDATE SET
       number = excluded.number, type = excluded.type, state = excluded.state,
       dispatch_state = excluded.dispatch_state, priority_code = excluded.priority_code,
       priority_rank = excluded.priority_rank, premise_id = excluded.premise_id, asset_id = excluded.asset_id,
       window_start = excluded.window_start, window_end = excluded.window_end, due_at = excluded.due_at,
       est_minutes = excluded.est_minutes, access_notes = excluded.access_notes, hazards = excluded.hazards,
       gate_code = excluded.gate_code, needs_bundle = 1, extra = excluded.extra,
       server_updated_at = excluded.server_updated_at, updated_at = excluded.updated_at`,
    {
      id: w.id,
      number: w.number,
      type: w.type,
      state: w.state,
      dispatch_state: w.dispatchState,
      priority_code: w.priorityCode,
      priority_rank: w.priorityRank,
      premise_id: w.premiseId,
      asset_id: w.assetId ?? null,
      window_start: w.windowStart,
      window_end: w.windowEnd,
      due_at: w.dueAt,
      est_minutes: w.estMinutes,
      access_notes: w.accessNotes,
      hazards: w.hazards,
      gate_code: w.gateCode,
      extra: toJson(w.extra),
      server_updated_at: w.serverUpdatedAt,
      now,
    },
  );
}

/** The bundle's customer (`sync/extras.ts`, DEF-FLD-10582). Server wins: none → null. */
export function setCustomer(s: ScopedRunner, id: string, customerId: string | null): void {
  s.run('UPDATE work_order SET customer_id = :customer_id WHERE technician_id = :technician_id AND id = :id', {
    id,
    customer_id: customerId,
  });
}

/** FB-023 — the bundle's `account_id`. Server wins: none → null. Never used to
 *  read money (the money door is per job), kept so the job names its account. */
export function setAccount(s: ScopedRunner, id: string, accountId: string | null): void {
  s.run('UPDATE work_order SET account_id = :account_id WHERE technician_id = :technician_id AND id = :id', {
    id,
    account_id: accountId,
  });
}

/**
 * FB-023 F4/F6 — the job's copy of its template's *What the technician sees
 * on the job* ticks, kept in `body` (the template snapshot column, read whole)
 * under `details`. The change feed never writes `body`, so a card update does
 * not wipe them between a feed and the next bundle.
 */
export function setDetails(s: ScopedRunner, id: string, details: Record<string, unknown> | null): void {
  s.run(
    `UPDATE work_order SET body = json_set(COALESCE(body, '{}'), '$.details', json(:details))
      WHERE technician_id = :technician_id AND id = :id`,
    { id, details: JSON.stringify(details) },
  );
}

/** The five ticks; each reads TRUE unless the job's copy says `false`. */
export interface JobShows {
  accountSummary: boolean;
  assetCard: boolean;
  accessNotes: boolean;
  appointment: boolean;
  balancePayments: boolean;
}

export function showsOf(row: Pick<WorkOrderRow, 'body'> | null | undefined): JobShows {
  let d: Record<string, unknown> = {};
  try {
    const body = row?.body ? (JSON.parse(row.body) as { details?: Record<string, unknown> | null }) : null;
    d = body?.details ?? {};
  } catch {
    d = {};
  }
  const on = (k: string) => d[k] !== false;
  return {
    accountSummary: on('show_account_summary'),
    assetCard: on('show_asset_card'),
    accessNotes: on('show_access_notes'),
    appointment: on('show_appointment'),
    balancePayments: on('show_balance_payments'),
  };
}

/** FB-028 — what a job RAISED ON SITE carries in its details: the template's
 *  Reconnect limit (4 places, or null), and whether its raiser holds the
 *  template's skill (W3 = C: the phone warns, nothing refuses). */
export interface FieldRaise {
  raisedOnSite: boolean;
  reconnectLimit: string | null;
  skillMissing: string | null;
  /** The job's unit, when it stands on one — sent with a raise carried from it. */
  unitId: string | null;
}

export function fieldRaiseOf(row: Pick<WorkOrderRow, 'body'> | null | undefined): FieldRaise {
  let d: Record<string, unknown> = {};
  try {
    const body = row?.body ? (JSON.parse(row.body) as { details?: Record<string, unknown> | null }) : null;
    d = body?.details ?? {};
  } catch {
    d = {};
  }
  const limit = typeof d.reconnect_limit === 'string' && d.reconnect_limit.trim() !== '' ? d.reconnect_limit : null;
  const advice = (d.skill_advice ?? null) as { skill?: { name?: string } | null; has_skill?: boolean } | null;
  const skill = advice && advice.has_skill === false ? (advice.skill?.name ?? null) : null;
  const unitId = typeof d.unit_id === 'string' && d.unit_id !== '' ? d.unit_id : null;
  return { raisedOnSite: d.raised_on_site === true, reconnectLimit: limit, skillMissing: skill, unitId };
}

export function getMine(s: ScopedRunner, id: string): WorkOrderRow | undefined {
  return s.get<WorkOrderRow>('SELECT * FROM work_order WHERE technician_id = :technician_id AND id = :id', { id });
}

/**
 * FF-10 Today: appointment first, then the deadline, then the number — NULLs
 * last on both time legs; priority is a badge and never a sort key
 * (BR-WRK-035, R1). Paged (NFR-3).
 */
export function listDay(s: ScopedRunner, opts: { before: string; limit: number; offset?: number }): WorkOrderRow[] {
  return s.all<WorkOrderRow>(
    `SELECT * FROM work_order
      WHERE technician_id = :technician_id
        AND (window_start IS NULL OR window_start < :before)
        AND closed_at IS NULL
      ORDER BY window_start IS NULL, window_start, due_at IS NULL, due_at, number
      LIMIT :limit OFFSET :offset`,
    { before: opts.before, limit: opts.limit, offset: opts.offset ?? 0 },
  );
}

export function markClosed(s: ScopedRunner, id: string, at: string): void {
  s.run('UPDATE work_order SET closed_at = :at WHERE technician_id = :technician_id AND id = :id', { id, at });
}

/** A tombstone or a cascade: the mirror row only. */
/**
 * FB-031 (DEF-FLD-10805) — fetch this job's bundle again at the next sync: a
 * help document's download was refused or its link had expired, and only a
 * fresh bundle carries a fresh one. Until then only the change feed set it.
 */
export function markNeedsBundle(s: ScopedRunner, id: string): void {
  s.run('UPDATE work_order SET needs_bundle = 1 WHERE technician_id = :technician_id AND id = :id', { id });
}

/**
 * Jobs whose bundle (`GET work/mobile/jobs/{id}`) has not been fetched since
 * the card last changed — open ones first. FB-030: a CLOSED job is fetched
 * too, so a job refilled onto a new phone (or closed elsewhere) carries its
 * steps, readings and record; the handset's own ticks and values are never
 * overwritten by it (`woItem.upsert`, `woReading.fillValueIfEmpty`).
 */
export function needingBundle(s: ScopedRunner, limit: number): { id: string }[] {
  return s.all<{ id: string }>(
    `SELECT id FROM work_order WHERE technician_id = :technician_id AND needs_bundle = 1
      ORDER BY closed_at IS NOT NULL, window_start, due_at, number LIMIT :limit`,
    { limit },
  );
}

/**
 * The bundle is on the handset (`sync/extras.ts`). Its `technician_acceptance`
 * (DEF-FLD-10579) is kept in `extra` where the card's own copy lives, so a job
 * accepted on the web or earlier reads as taken and offers no Decline; absent
 * (an older server), `extra` is left as the card wrote it.
 */
export function markBundled(
  s: ScopedRunner,
  id: string,
  template: { id: string | null; version: string | null },
  acceptance?: unknown,
): void {
  s.run(
    `UPDATE work_order SET needs_bundle = 0, template_id = COALESCE(:template_id, template_id),
            template_version = COALESCE(:template_version, template_version),
            extra = CASE WHEN :acceptance IS NULL THEN extra
                         ELSE json_set(COALESCE(extra, '{}'), '$.technician_acceptance', json(:acceptance)) END
      WHERE technician_id = :technician_id AND id = :id`,
    {
      id,
      template_id: template.id,
      template_version: template.version,
      acceptance: acceptance && typeof acceptance === 'object' ? JSON.stringify(acceptance) : null,
    },
  );
}

/** FF-36: the server reopened the close (N21) — the job is open on the handset again. */
export function markReopened(s: ScopedRunner, id: string): void {
  s.run(
    `UPDATE work_order SET closed_at = NULL, state = 'in_progress', outcome = NULL
      WHERE technician_id = :technician_id AND id = :id`,
    { id },
  );
}

export function deleteMine(s: ScopedRunner, id: string): number {
  return s.run('DELETE FROM work_order WHERE technician_id = :technician_id AND id = :id', { id }).changes;
}

/** Closed before the cutoff, every technician (the purge looks; the cascade
 *  then runs scoped to each row's own technician). */
export function closedBefore(purge: QueryRunner, cutoff: string): { technician_id: string; id: string }[] {
  return purge.all(
    `SELECT technician_id, id FROM work_order WHERE closed_at IS NOT NULL AND closed_at < :cutoff
      ORDER BY closed_at`,
    { cutoff },
  );
}

/** FF-44 *Today · done*: this technician's orders closed in a range. */
export function countClosedBetween(s: ScopedRunner, from: string, to: string): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM work_order
        WHERE technician_id = :technician_id AND closed_at >= :from AND closed_at < :to`,
      { from, to },
    )?.n ?? 0
  );
}

/** FF-44 *Today · left*: open orders whose window starts before the cutoff (or has none). */
export function countOpenBefore(s: ScopedRunner, before: string): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM work_order
        WHERE technician_id = :technician_id AND closed_at IS NULL
          AND (window_start IS NULL OR window_start < :before)`,
      { before },
    )?.n ?? 0
  );
}

/** FF-50 *On this phone · Jobs*: open orders, and how many have their bundle on the handset. */
export function bundleCounts(s: ScopedRunner): { total: number; ready: number } {
  const row = s.get<{ total: number; ready: number | null }>(
    `SELECT COUNT(*) AS total, SUM(CASE WHEN needs_bundle = 0 THEN 1 ELSE 0 END) AS ready
       FROM work_order WHERE technician_id = :technician_id AND closed_at IS NULL`,
  );
  return { total: row?.total ?? 0, ready: row?.ready ?? 0 };
}
