/**
 * The pull: a delta against a watermark, never a full download (R56).
 *
 *  - The cursor is per technician per table (R134) — `sync_state`.
 *  - A page is applied and its cursor advanced in ONE transaction, so a crash
 *    re-pulls that page rather than skipping it; applying a page twice is
 *    harmless (upserts, and deletes of what is already gone).
 *  - TOMBSTONES REMOVE (R57): a job taken away arrives as `removed` and its
 *    mirror rows go on sight — work_order, wo_item, wo_reading and its search
 *    entry, in one transaction. CAPTURED work against it is NOT touched: the
 *    outbox, photos, activity and crew time still have to reach the server
 *    (Mobile data §10, "A job leaves your day").
 *  - The server wins on mirrored data (R58): an upsert overwrites the columns
 *    the server sends and never the handset's own (`closed_at`, captured values).
 *
 * The server's feed today covers WORK ORDERS ONLY (`apps/work/mobile.py
 * changes`): one cursor, stored under table `work_order`. Routes, assets and
 * the template catalogue have no feed yet — named in the lane report. A job's
 * OWN meter and point ride on its card (DEF-FLD-10582) and land in `asset`,
 * `premise` and the job's `extra.position` below.
 * The job card is not the whole job: tasks, readings and documents come from
 * `GET /work/mobile/jobs/{id}` (the bundle); an upsert marks the row
 * `needs_bundle` for that fetch, which is not built here.
 */
import type { TenantDb } from '../db/database';
import { fromJson } from '../db/json';
import * as assetQ from '../db/queries/asset';
import * as premiseQ from '../db/queries/premise';
import * as searchQ from '../db/queries/searchIndex';
import * as moneyLastQ from '../db/queries/moneyLast';
import * as syncStateQ from '../db/queries/syncState';
import * as technicianQ from '../db/queries/technician';
import * as workOrderQ from '../db/queries/workOrder';
import * as closedQ from '../db/queries/workOrderClosed';
import * as woItemQ from '../db/queries/woItem';
import * as woReadingQ from '../db/queries/woReading';
import { scoped, type ScopedRunner } from '../db/scoped';
import type { Clock } from './outbox';
import type { ChangesPage, JobCard, Transport } from './transport';

export const DELTA_TABLE = 'work_order';
export const PAGE_SIZE = 50;
/** Wire versions this build can read. Absent = the server as of 2026-10-21. */
export const KNOWN_SCHEMA_VERSIONS: readonly number[] = [1];

export class UnknownSchemaVersionError extends Error {
  constructor(readonly version: number) {
    super(`the server sent schema version ${version}; this build reads ${KNOWN_SCHEMA_VERSIONS.join(', ')}`);
    this.name = 'UnknownSchemaVersionError';
  }
}

const CARD_KEYS = new Set([
  'id', 'order_no', 'type', 'premise', 'window_start', 'window_end', 'due_at', 'est_minutes', 'priority',
  'state', 'dispatch_state', 'access_notes', 'hazards', 'gate_code', 'meter',
]);

/** An unknown field is kept, not dropped (Mobile data §9). */
function extraOf(card: JobCard): Record<string, unknown> | null {
  const extra: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(card)) if (!CARD_KEYS.has(k)) extra[k] = v;
  return Object.keys(extra).length ? extra : null;
}

/** A NUMERIC string off the wire as a position, or null — never NaN. */
function coord(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * DEF-FLD-10582 — the job's POINT, as the server walked it (hard rule 8,
 * BR-MET-1162): kept on the job (`extra.position`) because a UNIT's own point
 * is that unit's, never its building's — writing it onto the shared `premise`
 * row would move every other job in the building. The building's own point
 * goes on the premise row only when it is the building's (`source: premises`).
 */
function positionOf(premise: JobCard['premise']): { lat: number; lng: number; source: 'unit' | 'premises' | null } | null {
  const lat = coord(premise?.lat);
  const lng = coord(premise?.lng);
  if (lat === null || lng === null) return null;
  return { lat, lng, source: premise?.position_source ?? null };
}

/**
 * DEF-FLD-10582 — the card's meter into the asset store. Server wins on what
 * it sends; what it does not send (a route's sub-meter link, the history, a
 * badge) is kept. The NUMBER rides in `serial` with the true serial in
 * `extra`, exactly as the route sync stores a meter (`routes.ts`), so one
 * meter synced by both is one row that does not flip between two shapes.
 */
function applyMeter(db: TenantDb, s: ScopedRunner, meter: NonNullable<JobCard['meter']>, premise: JobCard['premise'] | null, now: string): void {
  const premiseId = premise?.id ?? null;
  const prev = assetQ.get(db, meter.id);
  const prevExtra = fromJson<Record<string, unknown>>(prev?.extra ?? null) ?? {};
  assetQ.upsert(
    db,
    {
      id: meter.id,
      serial: meter.asset_no ?? meter.serial_no ?? null,
      badge: prev?.badge ?? null,
      deviceId: prev?.device_id ?? null,
      model: meter.model ?? null,
      size: meter.size_class ?? null,
      service: meter.service ?? null,
      parentAssetId: prev?.parent_asset_id ?? null,
      premiseId: premiseId ?? prev?.premise_id ?? null,
      status: 'active',
      history: fromJson(prev?.history ?? null),
      extra: { ...prevExtra, meter_no: meter.asset_no ?? null, serial_no: meter.serial_no ?? null },
    },
    now,
  );
  // FF-41 searches the phone through `search_index`; a meter not indexed here
  // is on the phone and cannot be found offline (DEF-FLD-10604, MQ-046).
  searchQ.put(s, 'asset', meter.id, {
    serial: meter.asset_no ?? meter.serial_no ?? null,
    number: meter.serial_no ?? null,
    badge: prev?.badge ?? null,
    address: premise?.address ?? null,
  });
}

function applyUpsert(db: TenantDb, s: ScopedRunner, card: JobCard, at: string, now: string): void {
  const premise = card.premise ?? null;
  const position = positionOf(premise);
  if (premise?.id) {
    const own = position?.source === 'premises' ? position : null;
    premiseQ.upsert(
      db,
      { id: premise.id, premiseNo: premise.premise_no ?? null, addressLine: premise.address ?? null, lat: own?.lat ?? null, lng: own?.lng ?? null },
      now,
    );
  }
  const meter = card.meter?.id ? card.meter : null;
  if (meter) applyMeter(db, s, meter, premise, now);
  const extra = extraOf(card);
  workOrderQ.upsertFromServer(
    s,
    {
      id: card.id,
      number: card.order_no ?? null,
      type: card.type ?? null,
      state: card.state ?? null,
      dispatchState: card.dispatch_state ?? null,
      priorityCode: card.priority?.code ?? null,
      priorityRank: card.priority?.rank ?? null,
      premiseId: premise?.id ?? null,
      assetId: meter?.id ?? null,
      windowStart: card.window_start ?? null,
      windowEnd: card.window_end ?? null,
      dueAt: card.due_at ?? null,
      estMinutes: card.est_minutes ?? null,
      accessNotes: card.access_notes ?? null,
      hazards: card.hazards ?? null,
      gateCode: card.gate_code ?? null,
      extra: position ? { ...(extra ?? {}), position } : extra,
      serverUpdatedAt: at,
    },
    now,
  );
  // FB-030 (PO 2026-10-31) — a job closed on the web or another phone arrives
  // COMPLETED: it fills `closed_at` and `outcome`, so FF-35 shows it for its
  // 14 days. What the phone already holds wins (`fillCloseFromServer`).
  // `completed_at`, `outcome` and `accepted_at` also stay in `extra`, where
  // `acceptedAt` reads the office's acceptance.
  if (typeof card.completed_at === 'string' && card.completed_at !== '') {
    closedQ.fillCloseFromServer(s, card.id, card.completed_at, typeof card.outcome === 'string' && card.outcome !== '' ? card.outcome : null);
  }
  searchQ.put(s, 'work_order', card.id, { number: card.order_no ?? null, address: premise?.address ?? null });
}

/** A job taken away: its mirror goes, in one transaction; captured work stays. */
export function removeJobMirror(s: ScopedRunner, orderId: string): void {
  woItemQ.deleteForOrder(s, orderId);
  woReadingQ.deleteForOrder(s, orderId);
  searchQ.remove(s, 'work_order', orderId);
  workOrderQ.deleteMine(s, orderId);
}

export function applyChangesPage(db: TenantDb, technicianId: string, page: ChangesPage, now: Date): void {
  if (page.schema_version !== undefined && !KNOWN_SCHEMA_VERSIONS.includes(page.schema_version)) {
    // Refuse and say so, rather than store nulls (Mobile data §9).
    throw new UnknownSchemaVersionError(page.schema_version);
  }
  const s = scoped(db, technicianId);
  const at = now.toISOString();
  db.transaction(() => {
    for (const change of page.changes) {
      if (change.change === 'removed') {
        removeJobMirror(s, change.order_id);
        // FB-023 F1 — the last money figure leaves with the job it was read for.
        moneyLastQ.remove(db, technicianId, change.order_id);
      } else applyUpsert(db, s, change.job, change.at, at);
    }
    // FB-023 F3 — the server says whether this technician sees money; the
    // phone keeps it on its own roster row (`onSite/job.ts` `moneyRole`). A
    // word it does not know is not stored: the money then stays hidden.
    const employment = page.technician?.employment;
    if (employment === 'employee' || employment === 'contractor') {
      technicianQ.setEmployment(db, technicianId, employment, at);
    }
    syncStateQ.setCursor(s, DELTA_TABLE, page.next_cursor, at);
  });
}

export interface PullOptions {
  clock: Clock;
  pageSize?: number;
}

export interface PullSummary {
  pages: number;
  upserts: number;
  removals: number;
}

/** Pull every page of changes for the signed-in technician. */
export async function pullChanges(
  db: TenantDb,
  transport: Transport,
  technicianId: string,
  opts: PullOptions,
): Promise<PullSummary> {
  const s = scoped(db, technicianId);
  const summary: PullSummary = { pages: 0, upserts: 0, removals: 0 };
  for (;;) {
    const cursor = syncStateQ.get(s, DELTA_TABLE)?.cursor ?? null;
    const page = await transport.changes(cursor, opts.pageSize ?? PAGE_SIZE);
    applyChangesPage(db, technicianId, page, opts.clock.now());
    summary.pages += 1;
    for (const c of page.changes) {
      if (c.change === 'removed') summary.removals += 1;
      else summary.upserts += 1;
    }
    if (!page.has_more) return summary;
    if (page.next_cursor === cursor) {
      // A feed that says "more" without moving would loop for ever.
      throw new Error('the change feed reported more without advancing its cursor');
    }
  }
}
