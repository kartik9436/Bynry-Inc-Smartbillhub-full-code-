/**
 * FF-37 *Where* — the places a raise from Home, Scan or an asset may stand on,
 * searched ON THE PHONE first (R41) by address, account or meter
 * (DEF-FLD-10603, MQ-036).
 *
 * A raise with no job has no anchor of its own, and the server refuses an
 * order that stands on nothing (`BR-WRK-006`, `work.order.anchor_required`).
 * So the technician picks a place, and this is where the phone looks:
 *
 *   PREMISES — by address, locality or premises number. The address lives on
 *     the premises and nowhere else (hard rule 8), so every hit's words come
 *     from there.
 *   ACCOUNTS — by account number or customer name, through this technician's
 *     own jobs (the only place the phone joins an account to a premises).
 *   METERS   — by serial, badge or device ID.
 *
 * ⚠ ONLY THIS TECHNICIAN'S PLACES. `premise`, `customer` and `asset` are
 * reference tables shared by everyone who signs in on the handset (R132), so
 * each query reaches them THROUGH a scoped row — a job or a route stop of the
 * signed-in technician — and another technician's customers never surface.
 *
 * Bounded on purpose, and the screen says so (R42): the server half is
 * `GET work/mobile/assets/search` (N9), which already searches address and
 * account number as well as the meter's own numbers.
 */
import type { ScopedRunner } from '../scoped';

/** The anchors one place gives a raise (`raise_from_field`'s `premises_id`, `account_id`, `asset_id`). */
export interface PlaceAnchors {
  premiseId: string | null;
  accountId: string | null;
  assetId: string | null;
}

export interface PlaceHit extends PlaceAnchors {
  kind: 'premise' | 'account' | 'asset';
  /** A stable key for the list. */
  key: string;
  address: string | null;
  locality: string | null;
  accountNumber: string | null;
  serial: string | null;
}

const MINE = `(SELECT premise_id FROM work_order WHERE technician_id = :technician_id AND premise_id IS NOT NULL
              UNION SELECT premise_id FROM route_stop WHERE technician_id = :technician_id)`;

/** Places on this phone matching `text`, premises first, then accounts, then meters. */
export function searchPlaces(s: ScopedRunner, text: string, opts: { limit: number }): PlaceHit[] {
  const q = text.trim();
  if (q.length < 2) return [];
  const like = `%${q.replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
  const premises = s.all<{ id: string; address_line: string | null; locality: string | null }>(
    `SELECT p.id, p.address_line, p.locality FROM premise p
      WHERE p.id IN ${MINE}
        AND (p.address_line LIKE :like ESCAPE '\\' OR p.premise_no LIKE :like ESCAPE '\\' OR p.locality LIKE :like ESCAPE '\\')
      ORDER BY p.address_line, p.id LIMIT :limit`,
    { like, limit: opts.limit },
  );
  const accounts = s.all<{ account_id: string; premise_id: string | null; account_number: string | null; address_line: string | null; locality: string | null }>(
    `SELECT wo.account_id, MIN(wo.premise_id) AS premise_id, c.account_number, p.address_line, p.locality
       FROM work_order wo
       JOIN customer c ON c.id = wo.customer_id
       LEFT JOIN premise p ON p.id = wo.premise_id
      WHERE wo.technician_id = :technician_id AND wo.account_id IS NOT NULL
        AND (c.account_number LIKE :like ESCAPE '\\' OR c.name LIKE :like ESCAPE '\\')
      GROUP BY wo.account_id
      ORDER BY c.account_number, wo.account_id LIMIT :limit`,
    { like, limit: opts.limit },
  );
  const meters = s.all<{ id: string; serial: string | null; badge: string | null; device_id: string | null; premise_id: string | null; address_line: string | null; locality: string | null }>(
    `SELECT a.id, a.serial, a.badge, a.device_id, a.premise_id, p.address_line, p.locality
       FROM asset a LEFT JOIN premise p ON p.id = a.premise_id
      WHERE a.status = 'active'
        AND (a.premise_id IN ${MINE}
             OR a.id IN (SELECT asset_id FROM work_order WHERE technician_id = :technician_id AND asset_id IS NOT NULL))
        AND (a.serial LIKE :like ESCAPE '\\' OR a.badge LIKE :like ESCAPE '\\' OR a.device_id LIKE :like ESCAPE '\\')
      ORDER BY a.serial, a.id LIMIT :limit`,
    { like, limit: opts.limit },
  );
  const hits: PlaceHit[] = [
    ...premises.map<PlaceHit>((p) => ({
      kind: 'premise',
      key: `premise:${p.id}`,
      premiseId: p.id,
      accountId: null,
      assetId: null,
      address: p.address_line,
      locality: p.locality,
      accountNumber: null,
      serial: null,
    })),
    ...accounts.map<PlaceHit>((a) => ({
      kind: 'account',
      key: `account:${a.account_id}`,
      premiseId: a.premise_id,
      accountId: a.account_id,
      assetId: null,
      address: a.address_line,
      locality: a.locality,
      accountNumber: a.account_number,
      serial: null,
    })),
    ...meters.map<PlaceHit>((m) => ({
      kind: 'asset',
      key: `asset:${m.id}`,
      premiseId: m.premise_id,
      accountId: null,
      assetId: m.id,
      address: m.address_line,
      locality: m.locality,
      accountNumber: null,
      serial: m.serial ?? m.badge ?? m.device_id,
    })),
  ];
  return hits.slice(0, opts.limit);
}

/** The account number of an account this technician has a job for, or null. */
export function accountNumberOf(s: ScopedRunner, accountId: string): string | null {
  return (
    s.get<{ account_number: string | null }>(
      `SELECT c.account_number FROM work_order wo JOIN customer c ON c.id = wo.customer_id
        WHERE wo.technician_id = :technician_id AND wo.account_id = :account_id LIMIT 1`,
      { account_id: accountId },
    )?.account_number ?? null
  );
}
