/**
 * Where a job IS, for *Navigate* on FF-15 and FF-25 (DEF-FLD-10582, MQ-015 —
 * Navigate was greyed on every job because no point reached the phone).
 *
 * The job's own point first — `extra.position`, the server's walk: the UNIT's
 * point where it has one, else its building's (hard rule 8, BR-MET-1162;
 * `sync/delta.ts` keeps it on the job so a unit's point never moves its
 * building's row). Failing that, the premise row's point. Neither → null, and
 * Navigate stays disabled: no point is ever invented.
 */
import { Platform } from 'react-native';

import { fromJson } from '../../db/json';

export interface JobPoint {
  lat: number;
  lng: number;
  source: 'unit' | 'premises' | null;
}

function finite(v: unknown): number | null {
  const n = typeof v === 'number' ? v : typeof v === 'string' && v !== '' ? Number(v) : NaN;
  return Number.isFinite(n) ? n : null;
}

export function jobPoint(
  orderExtra: string | Record<string, unknown> | null | undefined,
  premise: { lat: number | null; lng: number | null } | null | undefined,
): JobPoint | null {
  const extra = typeof orderExtra === 'string' ? fromJson<Record<string, unknown>>(orderExtra) : orderExtra;
  const own = (extra?.position ?? null) as { lat?: unknown; lng?: unknown; source?: unknown } | null;
  const lat = finite(own?.lat);
  const lng = finite(own?.lng);
  if (lat !== null && lng !== null) {
    return { lat, lng, source: own?.source === 'unit' || own?.source === 'premises' ? own.source : null };
  }
  const pLat = finite(premise?.lat);
  const pLng = finite(premise?.lng);
  return pLat !== null && pLng !== null ? { lat: pLat, lng: pLng, source: 'premises' } : null;
}

/**
 * The phone's own maps app at the point, labelled with the street address —
 * `geo:` on Android, `maps:` on iOS. The label is the ADDRESS and nothing else
 * (Security §5: no customer name, no order number goes to another company's
 * app).
 */
export function pointUrl(point: JobPoint, label: string | null, os: string = Platform.OS): string {
  const ll = `${point.lat},${point.lng}`;
  const q = label ? encodeURIComponent(label) : '';
  if (os === 'ios') return `maps:?ll=${ll}&q=${q || ll}`;
  return `geo:${ll}?q=${ll}${q ? `(${q})` : ''}`;
}
