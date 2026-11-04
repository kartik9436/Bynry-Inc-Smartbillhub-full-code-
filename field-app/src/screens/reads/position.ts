/**
 * FB-003 — the position is captured automatically, never by a button.
 *
 * PO ruling 2026-10-27 (decision log *"FB-003: the position is captured
 * automatically, never by a button (PO)"*), verbatim: *"no need of new button
 * , capture the position automatically ; if user has location permission not
 * enabled asked the user to give permission , when user takes the photo record
 * the lat,long positions"*, then *"go with recommendation, start"* on the two
 * figures put to them:
 *
 *   * SAVING — the best recent fix from the background watch; with none, wait
 *     up to **10 seconds** for one, then save without. The reader is never
 *     blocked longer (`fixForSave`).
 *   * SAVED WITHOUT ONE — the first fix within **5 minutes** of the save is
 *     sent as a SEPARATE fact, *"Position added at 18:35 ±10 m"*, never written
 *     as if present at save (hard rule 4, add-never-change; `BR-MET-1202`, the
 *     phone's position at capture). After 5 minutes nothing attaches: the
 *     reader has likely moved, and a far position is false evidence. The same
 *     for a photograph taken without a fix (`attachLatePositions`).
 *
 * Worked case put to the PO: a reading saved 18:32:48 with no fix; a ±10 m fix
 * arrives 18:35 → *"Position added at 18:35 ±10 m"*; a fix first arriving
 * 18:38 attaches nothing.
 *
 * WHERE THE "STILL WAITING FOR A POSITION" STATE LIVES: in the outbox, not in
 * memory. A reading or a route photograph's declaration with no position,
 * captured in the last 5 minutes and not yet given a late one, IS the list —
 * so an app restarted inside those 5 minutes still attaches the fix, and
 * nothing has to remember to clean a list up.
 *
 * ⚠ A JOB'S photographs (the `job` channel) are NOT covered: the job door
 * (`apps/work/sync`) has no item for a late position, and adding one is that
 * door's change. Reported, not built.
 */
import type { TenantDb } from '../../db/database';
import { fromJson } from '../../db/json';
import * as outboxQ from '../../db/queries/outbox';
import { scoped, type ScopedRunner } from '../../db/scoped';
import { FIX_STALE_MS } from '../../device';
import { capture, type Captor, type Clock } from '../../sync/outbox';
import type { Fix, LocationPort } from './ports';

/** How long a save waits for a first fix (PO 2026-10-27). */
export const SAVE_WAIT_MS = 10_000;
/** How long after the save a late fix may still be attached (PO 2026-10-27). */
export const LATE_POSITION_WINDOW_MS = 5 * 60_000;

/** A held fix young enough to be where the reader is now. */
function fresh(fix: Fix | null | undefined, nowMs: number): fix is Fix {
  return !!fix && nowMs - Date.parse(fix.fix_at) <= FIX_STALE_MS;
}

/**
 * The position a reading is saved with: the watch's held fix when it is
 * fresh; else the platform is asked, and the answer is waited for up to 10
 * seconds; else none. Never longer than `SAVE_WAIT_MS`.
 */
export async function fixForSave(location: LocationPort, now: () => number, waitMs: number = SAVE_WAIT_MS): Promise<Fix | null> {
  const held = location.last?.();
  if (fresh(held, now())) return held;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), waitMs);
  });
  try {
    return (await Promise.race([location.current().catch(() => null), timeout])) ?? null;
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

/**
 * A fix has arrived: give it to every reading and route photograph still
 * waiting for one, each as its own `route_position` act (a separate fact —
 * the reading's own row is never touched). Returns how many were attached.
 */
export function attachLatePositions(db: TenantDb, captor: Captor, fix: Fix, deps: { newId(): string; clock: Clock }): number {
  const s = scoped(db, captor.technicianId);
  let n = 0;
  const from = new Date(Date.parse(fix.fix_at) - LATE_POSITION_WINDOW_MS).toISOString();
  // Saved no more than 5 minutes before the fix, and not after it.
  for (const w of outboxQ.awaitingPositionMine(s, from, fix.fix_at)) {
    const payload = fromJson<Record<string, unknown>>(w.payload) ?? {};
    const forKind = w.kind === 'route_read' ? 'reading' : 'photo';
    capture(
      db,
      captor,
      {
        kind: 'route_position',
        routeId: w.route_id,
        payload: {
          for_key: w.id,
          for_kind: forKind,
          ...(typeof payload.route_read_id === 'string' ? { route_read_id: payload.route_read_id } : {}),
          ...(forKind === 'photo' && typeof payload.photo_id === 'string' ? { photo_id: payload.photo_id } : {}),
        },
        location: fix,
      },
      deps,
    );
    n += 1;
  }
  return n;
}

/** The late position given to one act (its capture key), if any — what RW-13 shows. */
export function latePositionOf(s: ScopedRunner, forKey: string | null): Fix | null {
  if (!forKey) return null;
  const row = outboxQ.latePositionMine(s, forKey);
  if (!row || row.lat === null || row.lng === null || row.accuracy_m === null || row.fix_at === null) return null;
  return { lat: row.lat, lng: row.lng, accuracy_m: row.accuracy_m, fix_at: row.fix_at };
}
