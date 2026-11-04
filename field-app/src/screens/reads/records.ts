/**
 * Which route, stop and meter a reading screen is about, and the few words a
 * record carries that have no column of their own.
 *
 * A screen opened with no record named — from the menu, from a door, by a
 * test — picks the reader's own first one: the first route still to turn in,
 * its first stop with something left in walk order, that stop's first unread
 * meter. It never invents one.
 *
 * ⚠ TWO VALUES THE DRAWINGS SHOW HAVE NO COLUMN ON THE HANDSET:
 *   - the route's NAME (*Maple Heights*) — `route` has a code, an area and a
 *     cycle and no name; it is read from the downloaded `extra.name`, and the
 *     code stands in when the download does not carry one;
 *   - the UNIT LABEL (*Unit A*, R79) — a unit refines a premises by label
 *     (hard rule 8) and the handset has no unit table; it is read from the
 *     asset's downloaded `extra.unit_label` and left out when absent.
 * Both are gaps in the route download (no route feed exists yet — see
 * `sync/transport.ts`), reported by the reads wave rather than guessed.
 */
import { fromJson } from '../../db/json';
import * as walkQ from '../../db/queries/readsWalk';
import type { ScopedRunner } from '../../db/scoped';
import type { ReadsParams } from './ReadsScreen';

export function routeName(r: Pick<walkQ.RouteCard, 'code' | 'extra' | 'id'>): string {
  const extra = fromJson<Record<string, unknown>>(r.extra) ?? {};
  return typeof extra.name === 'string' && extra.name ? extra.name : (r.code ?? r.id);
}

export function unitLabel(m: Pick<walkQ.MeterRead, 'asset_extra'>): string | null {
  const extra = fromJson<Record<string, unknown>>(m.asset_extra) ?? {};
  return typeof extra.unit_label === 'string' && extra.unit_label ? extra.unit_label : null;
}

/** A meter's own name on a board: its serial, else its badge. */
export function meterName(m: Pick<walkQ.MeterRead, 'serial' | 'badge' | 'asset_id'>): string {
  return m.serial ?? m.badge ?? m.asset_id;
}

/** The street part of an address, as the walk lists it. */
export function streetOf(stop: { address_line: string | null; id: string }): string {
  return stop.address_line ?? stop.id;
}

export function resolveRoute(s: ScopedRunner, p: ReadsParams): walkQ.RouteCard | null {
  if (p.routeId) return walkQ.routeCard(s, p.routeId) ?? null;
  if (p.stopId) {
    const st = walkQ.stop(s, p.stopId);
    if (st) return walkQ.routeCard(s, st.route_id) ?? null;
  }
  if (p.readId) {
    const m = walkQ.meter(s, p.readId);
    if (m) return walkQ.routeCard(s, m.route_id) ?? null;
  }
  const cards = walkQ.routeCards(s, 50);
  return cards.find((c) => c.status !== 'turned_in') ?? cards[0] ?? null;
}

export function resolveStop(s: ScopedRunner, p: ReadsParams, route: walkQ.RouteCard | null): walkQ.StopCard | null {
  if (p.stopId) return walkQ.stop(s, p.stopId) ?? null;
  if (p.readId) {
    const m = walkQ.meter(s, p.readId);
    if (m) return walkQ.stop(s, m.stop_id) ?? null;
  }
  if (!route) return null;
  return (
    walkQ.stops(s, route.id, { order: 'walk', filter: 'left', limit: 1 })[0] ??
    walkQ.stops(s, route.id, { order: 'walk', limit: 1 })[0] ??
    null
  );
}

export function resolveMeter(s: ScopedRunner, p: ReadsParams, stop: walkQ.StopCard | null): walkQ.MeterRead | null {
  if (p.readId) return walkQ.meter(s, p.readId) ?? null;
  if (!stop) return null;
  return walkQ.nextUnreadAtStop(s, stop.id, null) ?? walkQ.metersAtStop(s, stop.id, 1)[0] ?? null;
}

/** Everything a reading screen is about, resolved once. */
export function resolveAll(s: ScopedRunner, p: ReadsParams) {
  const route = resolveRoute(s, p);
  const stop = resolveStop(s, p, route);
  const meter = resolveMeter(s, p, stop);
  return { route, stop, meter };
}

/** A tenant list the download carries in `settings` — R82's reasons are DATA. */
export interface ListEntry {
  code: string;
  label: string;
}

export function asList(value: unknown): ListEntry[] | null {
  if (!Array.isArray(value)) return null;
  const out: ListEntry[] = [];
  for (const v of value) {
    if (v && typeof v === 'object' && typeof (v as ListEntry).code === 'string' && typeof (v as ListEntry).label === 'string') {
      out.push({ code: (v as ListEntry).code, label: (v as ListEntry).label });
    }
  }
  return out;
}

/** Where each downloaded list lives in `settings`. ⚠ No download fills them
 *  yet — the screens say so instead of using a list written in code. */
export const LIST_KEYS = {
  cantRead: 'reads.cant_read_reasons',
  raiseFindings: 'reads.raise_findings',
  raiseUrgency: 'reads.raise_urgency',
  services: 'reads.services',
  sizes: 'reads.meter_sizes',
} as const;
