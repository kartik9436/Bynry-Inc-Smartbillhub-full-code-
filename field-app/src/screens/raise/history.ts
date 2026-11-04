/**
 * An asset's past visits, as FF-39 and FF-40 render them.
 *
 * `asset.history` is a JSON blob rendered whole and never queried across
 * (R116; US-FLD-019 TC-3). ⚠ Its shape is the server's to define — the read
 * is `GET work/mobile/assets/{id}/history` (`07-endpoints.md` N10), not on the
 * branch — so this is the shape the screens EXPECT, written down so the
 * server lane can match it or change it here in one place: a list of visits,
 * newest first or not (they are sorted here), each optional field simply
 * absent when unknown. Unknown fields are ignored, never an error.
 *
 * The install date and the "where on the premises" note come from the
 * asset's `extra` (`installed_at`, `location_note`) for the same reason.
 */
import { fromJson } from '../../db/json';

export interface Visit {
  date: string;
  work: string;
  outcome: string | null;
  problem: string | null;
  done: string | null;
  parts: string | null;
  who: string | null;
  minutes: number | null;
  reading: { value: string; unit: string } | null;
}

const str = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null);

export function visitsOf(history: string | null): Visit[] {
  const raw = fromJson<unknown>(history);
  const list = Array.isArray(raw) ? raw : Array.isArray((raw as { visits?: unknown })?.visits) ? (raw as { visits: unknown[] }).visits : [];
  const out: Visit[] = [];
  for (const v of list) {
    if (!v || typeof v !== 'object') continue;
    const o = v as Record<string, unknown>;
    const date = str(o.date);
    const work = str(o.work);
    if (!date || !work) continue;
    const r = o.reading as Record<string, unknown> | undefined;
    out.push({
      date,
      work,
      outcome: str(o.outcome),
      problem: str(o.problem),
      done: str(o.done),
      parts: str(o.parts),
      who: str(o.who),
      minutes: typeof o.minutes === 'number' ? o.minutes : null,
      // A figure is never shown without its unit (hard rule 3).
      reading: r && str(r.value) && str(r.unit) ? { value: String(r.value), unit: String(r.unit) } : null,
    });
  }
  return out.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

/** The newest visit that took a reading (FF-39 LAST READ). */
export function lastRead(visits: readonly Visit[]): Visit | null {
  return visits.find((v) => v.reading !== null) ?? null;
}

export function extraOf(extra: string | null): { installedAt: string | null; locationNote: string | null } {
  const e = fromJson<Record<string, unknown>>(extra) ?? {};
  return { installedAt: str(e.installed_at), locationNote: str(e.location_note) };
}
