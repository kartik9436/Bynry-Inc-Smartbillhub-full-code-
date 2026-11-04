/**
 * FB-030 (PO 2026-10-31, decision log *"a technician's history is the last 14
 * days, kept on the phone"*, coordinator judgment (2)) — the REFILL of the
 * reader's own turned-in readings, so a new phone, a reinstall or a remote
 * sign-out still has RW-28's reference:
 *
 *   GET work/mobile/reads/history?page=   (`metering/field_history.py`)
 *
 * Asked ONCE per technician per store: when the handset has no record that it
 * asked (`sync_state` row `route_history`), every page is read and stored, and
 * the row is written only after the LAST page — a refill cut short is asked
 * again next time, and applying a page twice changes nothing (every write is
 * an insert-if-absent). After that, the phone's own captures ARE the history,
 * and the purge takes them at 14 days.
 *
 * What lands: the route as TURNED IN (with its turn-in time), its stop, the
 * meter and its premises, the reading as ACCEPTED with its unit (hard rule 3),
 * its status, can't-read reason, note, time and FB-022's lower-than-last flag,
 * and its photographs as rows with no file (loaded on tap, never stored). What
 * the handset already holds is never overwritten — its own capture wins.
 *
 * No money, no speed (R120): nothing here is a rate or a count per hour.
 */
import type { TenantDb } from '../db/database';
import * as assetQ from '../db/queries/asset';
import * as photoQ from '../db/queries/photo';
import * as premiseQ from '../db/queries/premise';
import * as routeQ from '../db/queries/route';
import * as routeReadQ from '../db/queries/routeRead';
import * as routeStopQ from '../db/queries/routeStop';
import * as syncStateQ from '../db/queries/syncState';
import { scoped } from '../db/scoped';

/** The `sync_state` row that says the refill has been done for this technician. */
export const HISTORY_TABLE = 'route_history';

export interface ServedHistoryRead {
  key: string;
  route: { id: string; code: string | null; name: string | null; cycle: string | null; turned_in_at: string | null };
  asset_id: string | null;
  meter_no: string | null;
  serial_no: string | null;
  premises_id: string | null;
  premise_no: string | null;
  address: string | null;
  register: string | null;
  value: string | null;
  unit: string | null;
  reader_status: 'read' | 'could_not_read' | 'read_with_problem' | null;
  cant_read_reason: string | null;
  cant_read_reason_name?: string | null;
  remark: string | null;
  captured_at: string;
  lower_than_last: boolean;
  photo_ids: string[];
}

export interface HistoryPage {
  count: number;
  next_page: number | null;
  results: ServedHistoryRead[];
}

export interface ReadsHistoryApi {
  readsHistory(page: number): Promise<HistoryPage>;
}

export function hasReadsHistory(x: unknown): x is ReadsHistoryApi {
  return !!x && typeof (x as ReadsHistoryApi).readsHistory === 'function';
}

export interface RefillSummary {
  asked: boolean;
  readings: number;
  /** Served without a unit — not stored (hard rule 3). */
  skippedNoUnit: number;
}

const readIdOf = (routeId: string, assetId: string, register: string | null) => `${routeId}:${assetId}:${register ?? 'total'}`;

/** Refill the reader's 14-day history once. A failure leaves it to ask again next time. */
export async function refillRouteHistory(
  db: TenantDb,
  technicianId: string,
  api: ReadsHistoryApi,
  now: () => Date,
  maxPages = 1000,
): Promise<RefillSummary> {
  const s = scoped(db, technicianId);
  const summary: RefillSummary = { asked: false, readings: 0, skippedNoUnit: 0 };
  if (syncStateQ.get(s, HISTORY_TABLE)) return summary;
  summary.asked = true;
  let page: number | null = 1;
  let pages = 0;
  while (page !== null && pages < maxPages) {
    const got: HistoryPage = await api.readsHistory(page);
    const at = now().toISOString();
    db.transaction(() => {
      for (const r of got.results) {
        if (!r.asset_id || !r.premises_id) continue;
        if (!r.unit) {
          summary.skippedNoUnit += 1;
          continue;
        }
        routeQ.upsertHistory(
          s,
          { id: r.route.id, code: r.route.code, name: r.route.name, cycle: r.route.cycle, turnedInAt: r.route.turned_in_at },
          at,
        );
        premiseQ.upsert(db, { id: r.premises_id, premiseNo: r.premise_no, addressLine: r.address, lat: null, lng: null }, at);
        if (!assetQ.get(db, r.asset_id)) {
          assetQ.upsert(
            db,
            {
              id: r.asset_id,
              serial: r.meter_no ?? r.serial_no,
              premiseId: r.premises_id,
              extra: { meter_no: r.meter_no, serial_no: r.serial_no },
            },
            at,
          );
        }
        const stop = `${r.route.id}:${r.premises_id}`;
        routeStopQ.insertIfAbsent(s, { id: stop, routeId: r.route.id, premiseId: r.premises_id }, at);
        const id = readIdOf(r.route.id, r.asset_id, r.register);
        routeReadQ.insertHistory(
          s,
          {
            id,
            routeId: r.route.id,
            stopId: stop,
            assetId: r.asset_id,
            value: r.value,
            unit: r.unit,
            register: r.register,
            readerStatus: r.reader_status,
            noReadReason: r.cant_read_reason,
            remark: r.remark,
            capturedAt: r.captured_at,
            captureKey: r.key,
            lowerThanLast: r.lower_than_last === true,
          },
          at,
        );
        for (const photoId of r.photo_ids ?? []) {
          photoQ.insertRemote(s, { id: photoId, routeId: r.route.id, routeReadId: id, capturedAt: r.captured_at, at });
        }
        summary.readings += 1;
      }
    });
    page = got.next_page;
    pages += 1;
  }
  if (page === null) syncStateQ.setCursor(s, HISTORY_TABLE, 'done', now().toISOString());
  return summary;
}
