/**
 * The meter-reading route mode's server doors (integration lane, when the
 * metering lane's `field_reads_api.py` landed):
 *
 *   GET  work/mobile/routes?page=          RW-01 — the reader's routes
 *   GET  work/mobile/routes/{id}?page=     RW-03 — one page of STOPS, each
 *                                          with every meter and its registers
 *   POST work/mobile/routes/{id}/turn-in   RW-25 — never a gate (R60)
 *   GET  work/mobile/cant-read-reasons     RW-17 — the utility's own list (R82)
 *
 * `downloadRoutes` puts every assigned route on the phone (R104: the whole
 * route before the walk), page by page, each page in ONE transaction, and
 * the server wins on these mirrored rows (R58) — a reading already taken is
 * never overwritten (`routeRead.upsertFromServer` updates only unread rows).
 *
 * ⚠ WHAT THE SERVER DOES NOT SERVE, AND IS NOT INVENTED HERE: a badge or
 * device id (which asset field is the badge is undecided — the server's own
 * docstring), stop access notes and hazards (no server home yet), the
 * `photo_required` prompt. Those columns stay empty; the screens already say
 * what they do not know. (A utility that wants a photo, a note or any other
 * answer at a meter now builds a READ FORMAT — below.)
 *
 * READ FORMATS (MQ-033, `CR-192-BRC10` task 12). Each route names, per service,
 * the format version resolved route → cycle → service (`read_formats[]`), and
 * each route page carries those versions with their questions
 * (`read_format_versions[]`). The route keeps its resolution and each version
 * is kept ONCE by its id (`db/queries/readFormat.ts`) — a published version
 * never changes, so one already held is never fetched again and the walk asks
 * nothing of the network. A version a page names but did not carry is fetched
 * from `GET work/mobile/read-formats/versions/{id}`. A route with no format
 * stores nothing and reads exactly as before.
 *
 * ⚠ A ROUTE THE SERVER NO LONGER LISTS LEAVES THE PHONE (DEF-FLD-10592, MQ-033,
 * PO 2026-10-24: a route's reader is assigned and reassigned on Reads → cycle →
 * Routes). After a COMPLETE download — every page of `myRoutes` answered, the
 * last with no next page — a route on the handset that the list did not name
 * is removed with its stops and readings (`db/routeDrop.ts`, the purge's own
 * rule). EXCEPT one that still holds captures not yet sent (R60): it stays,
 * counted in `keptForUnsentWork`, until they are sent and a later download
 * takes it. A download cut short (an error, or a server that never stops
 * paging) removes nothing — a partial list is not proof a route was taken away.
 *
 * Ids: a stop is `<route>:<premises>`, a reading is `<route>:<asset>:<register>`
 * — one per register (hard rule 3: the unit is the register's, never assumed),
 * so a meter with two registers is two readings. A register served without a
 * unit is NOT stored (a reading never exists without its unit) and is counted.
 */
import type { TenantDb } from '../db/database';
import * as assetQ from '../db/queries/asset';
import * as customerQ from '../db/queries/customer';
import * as premiseQ from '../db/queries/premise';
import * as readFormatQ from '../db/queries/readFormat';
import * as routeQ from '../db/queries/route';
import * as routeReadQ from '../db/queries/routeRead';
import * as routeStopQ from '../db/queries/routeStop';
import * as searchQ from '../db/queries/searchIndex';
import * as settingsQ from '../db/queries/settings';
import { dropRouteIfSettled } from '../db/routeDrop';
import { scoped } from '../db/scoped';
import { hasReadsHistory, refillRouteHistory } from './routeHistory';

/** The settings key RW-17 reads its reasons from (`screens/reads/records.ts` LIST_KEYS.cantRead). */
export const CANT_READ_KEY = 'reads.cant_read_reasons';

export interface ServedRouteCard {
  id: string;
  code?: string | null;
  name?: string | null;
  route_type?: string | null;
  services?: string[] | null;
  area?: string | null;
  cycle?: string | null;
  notes?: string | null;
  window?: { start: string; end: string } | null;
  stops?: number;
  meters?: number;
  /** MQ-033 — per service, the resolved format, or `read_format: null` for none. */
  read_formats?: ServedRouteFormat[] | null;
}

/** `read_formats[]` on a route card (`read_formats.route_formats`). */
export interface ServedRouteFormat {
  service: string;
  source: string | null;
  read_format: { id: string; name: string; version_id: string; version_no: number } | null;
}

/** One published version with its questions (`read_formats.get_version`). */
export interface ServedReadFormatVersion {
  id: string;
  read_format_id: string;
  state?: string;
  version_no: number;
  read_format?: { id: string; name: string; service: string } | null;
  questions: readonly readFormatQ.StoredQuestion[];
}

export interface ServedRegister {
  register: string;
  unit: string | null;
  previous: { value: string; read_on: string } | null;
  expected: { low: string; high: string } | null;
}

export interface ServedMeter {
  asset_id: string;
  meter_no: string | null;
  serial_no: string | null;
  parent_meter_no: string | null;
  service: string | null;
  size_class: string | null;
  read_method: string | null;
  location_note: string | null;
  unit_label: string | null;
  account_no: string | null;
  customer_name: string | null;
  registers: ServedRegister[];
}

export interface ServedStop {
  premises_id: string;
  premise_no: string | null;
  position: number;
  walk_order: number | null;
  address: { line: string | null; city: string | null; state: string | null; postal_code: string | null } | null;
  point: { lat: string; lng: string } | null;
  meters: ServedMeter[];
}

export interface RoutesPage {
  results: ServedRouteCard[];
  next_page: number | null;
}

export interface RouteStopsPage {
  route: ServedRouteCard;
  /** MQ-033 — the versions `route.read_formats` names, with their questions, on every page. */
  read_format_versions?: ServedReadFormatVersion[] | null;
  stops: ServedStop[];
  next_page: number | null;
}

export interface TurnInBody {
  key: string;
  keys: string[];
  counts: Record<string, number>;
  captured_at: string;
}

export interface RoutesApi {
  myRoutes(page: number): Promise<RoutesPage>;
  routePage(routeId: string, page: number): Promise<RouteStopsPage>;
  turnIn(routeId: string, body: TurnInBody): Promise<unknown>;
  cantReadReasons(): Promise<{ results: Array<{ code: string; name: string; active?: boolean }> }>;
  /** MQ-033 — `GET work/mobile/read-formats/versions/{id}`, for a version a page named and did not carry. */
  readFormatVersion?(versionId: string): Promise<ServedReadFormatVersion>;
}

export const readId = (routeId: string, assetId: string, register: string) => `${routeId}:${assetId}:${register}`;
export const stopId = (routeId: string, premisesId: string) => `${routeId}:${premisesId}`;

/** The register a downloaded reading is for, from its id (null for one not from a download). */
export function registerOfReadId(id: string, routeId: string): string | null {
  if (!id.startsWith(`${routeId}:`)) return null;
  const rest = id.slice(routeId.length + 1).split(':');
  return rest.length === 2 ? (rest[1] ?? null) : null;
}

const num = (v: string | null | undefined): number | null => {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export interface DownloadSummary {
  routes: number;
  stops: number;
  readings: number;
  /** Registers served with no unit — not stored (hard rule 3). */
  skippedNoUnit: number;
  /** Routes no longer assigned to this technician, taken off the phone. */
  removed: number;
  /** Routes no longer assigned, KEPT because captures on them are unsent (R60). */
  keptForUnsentWork: number;
  /** FB-030 — turned-in routes no longer listed, KEPT as the reader's 14-day history. */
  keptAsHistory?: number;
  /** FB-030 — readings refilled from the server's 14-day history (first download only). */
  historyRefilled?: number;
}

/** FB-030 (PO 2026-10-31) — a turned-in route is the reader's reference for this long. */
export const HISTORY_DAYS = 14;

/** A route turned in inside the history window stays, listed or not; the purge takes it at 14 days. */
function isHistory(s: ReturnType<typeof scoped>, id: string, now: Date): boolean {
  const r = routeQ.getMine(s, id);
  if (!r || r.status !== 'turned_in' || !r.turned_in_at) return false;
  return now.getTime() - Date.parse(r.turned_in_at) < HISTORY_DAYS * 24 * 60 * 60 * 1000;
}

/** Every page there is, one after another. A server that keeps answering a next page is stopped at `max`.
 *  True only when the LAST page was reached (`next_page` null) — the proof a list is whole. */
async function eachPage<T extends { next_page: number | null }>(get: (page: number) => Promise<T>, use: (page: T) => void, max = 200): Promise<boolean> {
  let page: number | null = 1;
  let n = 0;
  while (page !== null && n < max) {
    const got: T = await get(page);
    use(got);
    page = got.next_page;
    n += 1;
  }
  return page === null;
}

/** Every route id this technician holds on the handset, page by page. */
function heldRouteIds(s: ReturnType<typeof scoped>): string[] {
  const ids: string[] = [];
  const size = 200;
  for (let offset = 0; ; offset += size) {
    const rows = routeQ.listMine(s, size, offset);
    ids.push(...rows.map((r) => r.id));
    if (rows.length < size) return ids;
  }
}

/** The route's resolution as the phone keeps it: services with a format only. */
export function resolvedFormats(card: ServedRouteCard): readFormatQ.RouteFormat[] {
  return (card.read_formats ?? []).flatMap((f) =>
    f && f.service && f.read_format?.version_id ? [{ service: f.service, source: f.source ?? null, version_id: f.read_format.version_id }] : [],
  );
}

export async function downloadRoutes(
  db: TenantDb,
  technicianId: string,
  api: RoutesApi,
  now: () => Date,
  files?: { delete(path: string): Promise<void> },
): Promise<DownloadSummary> {
  const s = scoped(db, technicianId);
  const summary: DownloadSummary = { routes: 0, stops: 0, readings: 0, skippedNoUnit: 0, removed: 0, keptForUnsentWork: 0 };
  const cards: ServedRouteCard[] = [];
  const listComplete = await eachPage((p) => api.myRoutes(p), (page) => cards.push(...page.results));

  const putCard = (card: ServedRouteCard, at: string) =>
    routeQ.upsert(
      s,
      {
        id: card.id,
        code: card.code ?? null,
        service: card.services?.join(', ') || null,
        area: card.area ?? null,
        readType: card.route_type ?? null,
        cycle: card.cycle ?? null,
        windowStart: card.window?.start ?? null,
        windowEnd: card.window?.end ?? null,
        notes: card.notes ?? null,
        assignedTo: technicianId,
        extra: card.name ? { name: card.name } : null,
      },
      at,
    );

  for (const card of cards) {
    summary.routes += 1;
    await eachPage(
      (p) => api.routePage(card.id, p),
      (page) => {
        const at = now().toISOString();
        db.transaction(() => {
          putCard(page.route ?? card, at);
          readFormatQ.setRouteFormats(s, card.id, resolvedFormats(page.route ?? card));
          for (const v of page.read_format_versions ?? []) readFormatQ.putVersion(db, v, at);
          for (const stop of page.stops) {
            const lat = num(stop.point?.lat);
            const lng = num(stop.point?.lng);
            premiseQ.upsert(
              db,
              {
                id: stop.premises_id,
                premiseNo: stop.premise_no,
                addressLine: stop.address?.line ?? null,
                locality: stop.address?.city ?? null,
                region: stop.address?.state ?? null,
                postalCode: stop.address?.postal_code ?? null,
                lat,
                lng,
              },
              at,
            );
            const sid = stopId(card.id, stop.premises_id);
            routeStopQ.upsert(s, { id: sid, routeId: card.id, premiseId: stop.premises_id, walkPosition: stop.walk_order ?? stop.position, lat, lng }, at);
            summary.stops += 1;
            const assetOfMeterNo = new Map(stop.meters.map((m) => [m.meter_no, m.asset_id]));
            for (const m of stop.meters) {
              const accountId = m.account_no ? `acct:${m.account_no}` : null;
              if (accountId) customerQ.upsert(db, { id: accountId, name: m.customer_name, accountNumber: m.account_no }, at);
              const parent = m.parent_meter_no ? assetOfMeterNo.get(m.parent_meter_no) ?? null : null;
              assetQ.upsert(
                db,
                {
                  id: m.asset_id,
                  serial: m.meter_no ?? m.serial_no,
                  size: m.size_class,
                  service: m.service,
                  parentAssetId: parent,
                  premiseId: stop.premises_id,
                  extra: {
                    meter_no: m.meter_no,
                    serial_no: m.serial_no,
                    ...(m.unit_label ? { unit_label: m.unit_label } : {}),
                    ...(m.location_note ? { location_note: m.location_note } : {}),
                    ...(m.read_method ? { read_method: m.read_method } : {}),
                  },
                },
                at,
              );
              // FF-41's offline search reads `search_index` (DEF-FLD-10604, MQ-046).
              searchQ.put(s, 'asset', m.asset_id, {
                serial: m.meter_no ?? m.serial_no,
                number: m.serial_no,
                address: stop.address?.line ?? null,
              });
              for (const r of m.registers) {
                if (!r.unit) {
                  summary.skippedNoUnit += 1;
                  continue;
                }
                routeReadQ.upsertFromServer(
                  s,
                  {
                    id: readId(card.id, m.asset_id, r.register),
                    routeId: card.id,
                    stopId: sid,
                    assetId: m.asset_id,
                    parentAssetId: parent,
                    accountId,
                    previousValue: r.previous?.value ?? null,
                    expectedMin: r.expected?.low ?? null,
                    expectedMax: r.expected?.high ?? null,
                    unit: r.unit,
                  },
                  at,
                );
                summary.readings += 1;
              }
            }
          }
        });
      },
    );
  }

  // DEF-FLD-10592 — a route the server no longer lists for this technician
  // leaves the phone, unless captures on it are still unsent (R60). Only on a
  // WHOLE list: every route page above has also answered, or this line is
  // never reached.
  if (listComplete) {
    const listed = new Set(cards.map((c) => c.id));
    for (const id of heldRouteIds(s)) {
      if (listed.has(id)) continue;
      // FB-030 — a route this reader turned in during the last 14 days is
      // their history (RW-28), not an assignment: it stays until the purge.
      if (isHistory(s, id, now())) {
        summary.keptAsHistory = (summary.keptAsHistory ?? 0) + 1;
        continue;
      }
      const orphans: string[] = [];
      if (db.transaction(() => dropRouteIfSettled(s, id, orphans))) summary.removed += 1;
      else summary.keptForUnsentWork += 1;
      for (const path of orphans) await files?.delete(path).catch(() => undefined);
    }
  }

  // MQ-033: a version a route names that no page carried, from its own door.
  // A failure leaves the route's questions out until the next download; the
  // reading itself is never held up for want of a form.
  const wanted = new Set(cards.flatMap((c) => readFormatQ.routeFormats(s, c.id).map((f) => f.version_id)));
  for (const id of wanted) {
    if (readFormatQ.hasVersion(db, id) || !api.readFormatVersion) continue;
    try {
      const v = await api.readFormatVersion(id);
      readFormatQ.putVersion(db, v, now().toISOString());
    } catch {
      /* asked again on the next download */
    }
  }

  // RW-17's list: the utility's own reasons, as served (R82). A failure here
  // leaves the list the phone already had.
  try {
    const reasons = await api.cantReadReasons();
    settingsQ.set(
      db,
      CANT_READ_KEY,
      reasons.results.filter((r) => r.active !== false).map((r) => ({ code: r.code, label: r.name })),
      now().toISOString(),
    );
  } catch {
    /* kept as it was */
  }

  // FB-030 — once per technician per store: the reader's own turned-in reads
  // of the last 14 days (a new phone, a reinstall, a remote sign-out). A
  // failure leaves it to be asked again on the next download.
  if (hasReadsHistory(api)) {
    try {
      summary.historyRefilled = (await refillRouteHistory(db, technicianId, api, now)).readings;
    } catch {
      /* asked again next time */
    }
  }
  return summary;
}
