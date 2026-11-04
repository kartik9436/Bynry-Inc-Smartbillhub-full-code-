/**
 * Take ONE route off the handset — its stops, its readings and its settled
 * outbox and photo rows together — or refuse and keep it whole.
 *
 * Two callers, one rule, so the two can never disagree about what "nothing
 * unsent" means:
 *   - the retention purge (`purge.ts`, T-11) for a route turned in 14 days ago;
 *   - the route download (`sync/routes.ts`, DEF-FLD-10592) for a route the
 *     server no longer lists for this technician — reassigned or unassigned on
 *     Reads → cycle → Routes (PO 2026-10-24, MQ-033).
 *
 * ⚠ R60, PO ruled: "Nothing unsent is ever purged — at any age, under any
 * sign-in". A reading still `pending`, `sending` or `refused`, an outbox item
 * not yet answered, or a photograph not yet up keeps the WHOLE route here until
 * it is sent; the next download takes it then. Kept separate from `purge.ts`
 * because nothing in `src/sync/` may import the purge (`purge.test.ts`).
 *
 * The caller runs this inside its own transaction (one route, all or none).
 */
import * as outboxQ from './queries/outbox';
import * as photoQ from './queries/photo';
import * as routeQ from './queries/route';
import * as routeReadQ from './queries/routeRead';
import * as routeStopQ from './queries/routeStop';
import type { ScopedRunner } from './scoped';

/** Is anything captured on this route still waiting to reach the server? */
export function routeHasUnsentWork(s: ScopedRunner, routeId: string): boolean {
  const target = { routeId };
  return routeReadQ.unsentFor(s, routeId) > 0 || outboxQ.unsentFor(s, target) > 0 || photoQ.unsentFor(s, target) > 0;
}

/**
 * Drop the route when nothing on it is unsent. True when it was dropped.
 * FB-030: an uploaded photo may still have its FILE here (kept 3 days); its
 * path is pushed onto `orphans` for the caller to delete once the transaction
 * has committed, so the row never outlives a file the record could show.
 */
export function dropRouteIfSettled(s: ScopedRunner, routeId: string, orphans?: string[]): boolean {
  if (routeHasUnsentWork(s, routeId)) return false;
  const target = { routeId };
  orphans?.push(...photoQ.keptFilesFor(s, target));
  photoQ.deleteUploadedFor(s, target);
  outboxQ.deleteSettledFor(s, target);
  routeReadQ.deleteForRoute(s, routeId);
  routeStopQ.deleteForRoute(s, routeId);
  routeQ.deleteMine(s, routeId);
  return true;
}
