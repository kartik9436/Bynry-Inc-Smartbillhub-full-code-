/**
 * A ROUTE CHANGED: the server's `route_change` push wakes the phone, which
 * downloads its routes (DEF-MET-10606, PO 2026-10-26 — *"we will send this in
 * notification"*).
 *
 * The office assigns, reassigns or unassigns a route's reader; the server
 * pushes the NEW reader and the OLD reader once each per change
 * (`06-backend/apps/work/route_push.py`). The push carries counts and, for a
 * single route, its code and name — never the route itself. **It is the
 * doorbell, never the parcel** (decision log 2026-10-04): on receipt the app
 * runs the same `downloadRoutes` the Reads tab runs, which adds a route now
 * assigned and drops one taken away (keeping one with unsent readings,
 * `DEF-FLD-10592`). A push lost on the way leaves it to the next download.
 *
 * This file has no native import, so the runtime (which downloads) and the
 * native layer (which listens) meet here without either importing the other:
 * `notifications.ts` calls `wakeRoutes`, `FieldRuntime` subscribes with
 * `onRouteWake`.
 *
 * THE WORDS are the handset's, from its catalogue, by kind (B14 rule 35 — the
 * payload carries no English): *New route: RT-001 · Silver Creek*, *5 new
 * routes*, *Route removed: RT-002*, *3 routes removed*.
 */

export const ROUTE_CHANGE_KIND = 'route_change';

type Data = Record<string, unknown> | null | undefined;

function str(v: unknown): string | null {
  return typeof v === 'string' && v.trim() !== '' ? v.trim() : typeof v === 'number' ? String(v) : null;
}

function count(v: unknown): number {
  const n = Number(str(v) ?? 0);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}

/** True for the SERVER's route-change push (not the handset's own worded copy). */
export function isRouteChangePush(data: Data): boolean {
  return !!data && data.kind === ROUTE_CHANGE_KIND && data.handset !== '1';
}

/** The one line the technician reads, in their language; null when the push names nothing. */
export function routeChangeText(data: Data, t: (key: string, opts?: Record<string, unknown>) => string): string | null {
  if (!data) return null;
  const gained = count(data.gained);
  const lost = count(data.lost);
  const code = str(data.route);
  const name = str(data.route_name);
  if (gained === 1 && code) {
    return name ? t('field.push.routes.newOneNamed', { code, name }) : t('field.push.routes.newOne', { code });
  }
  if (gained > 0) return t('field.push.routes.newMany', { n: gained });
  if (lost === 1 && code) return t('field.push.routes.removedOne', { code });
  if (lost > 0) return t('field.push.routes.removedMany', { n: lost });
  return null;
}

type Listener = (data: Record<string, unknown>) => void;
const listeners = new Set<Listener>();

/** Subscribe to route-change wake-ups. Returns the unsubscribe. */
export function onRouteWake(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** Called by the native layer for OUR utility's route-change push. Returns how many listeners heard it. */
export function wakeRoutes(data: Record<string, unknown>): number {
  let heard = 0;
  for (const fn of [...listeners]) {
    try {
      fn(data);
      heard += 1;
    } catch {
      /* a wake-up never throws into the notification layer */
    }
  }
  return heard;
}
