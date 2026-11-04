/**
 * The reading screens' fixture: the design's own test data (EP-FLD-10…14 §4
 * — Maple Heights WLK-07, 1318 Maple, Carla Ruiz, MTR-0471), written into a
 * real handset store through the real query layer. Figures are the boards'
 * illustrations (B14 rule 37) used as test data only.
 *
 * Positions: the reader stands at 1318 Maple's recorded point; the stops lie
 * due north at the distances RW-05 draws (40, 70, 150, 240, 310 m), so
 * nearest-first can be checked to the metre without a signal (R76).
 */
import type { TenantDb } from '../../../src/db/database';
import * as assetQ from '../../../src/db/queries/asset';
import * as customerQ from '../../../src/db/queries/customer';
import * as premiseQ from '../../../src/db/queries/premise';
import * as routeQ from '../../../src/db/queries/route';
import * as routeReadQ from '../../../src/db/queries/routeRead';
import * as routeStopQ from '../../../src/db/queries/routeStop';
import * as settingsQ from '../../../src/db/queries/settings';
import { scoped } from '../../../src/db/scoped';
import { LIST_KEYS } from '../../../src/screens/reads/records';

export const RAY = 'ray';
export const NOW = '2026-10-20T10:42:18.000Z';
export const HERE = { lat: 30.267153, lng: -97.743061, accuracy_m: 4 };

const M_PER_DEG_LAT = 111_320;
const north = (m: number) => ({ lat: HERE.lat + m / M_PER_DEG_LAT, lng: HERE.lng });

/** The eight seeded reasons, as the server would serve them (R82). */
export const SEEDED_REASONS = [
  { code: 'dog', label: 'Dog' },
  { code: 'locked', label: 'Locked' },
  { code: 'no_access', label: 'No access' },
  { code: 'buried', label: 'Buried or covered' },
  { code: 'obstructed', label: 'Obstructed' },
  { code: 'not_found', label: 'Meter not found' },
  { code: 'unsafe', label: 'Unsafe' },
  { code: 'illegible', label: 'Illegible' },
];

export function seedMapleHeights(db: TenantDb, opts: { technician?: string; lists?: boolean } = {}): void {
  const s = scoped(db, opts.technician ?? RAY);
  const now = NOW;
  routeQ.upsert(
    s,
    {
      id: 'wlk-07',
      code: 'WLK-07',
      service: 'Water',
      area: 'North',
      readType: 'walk',
      cycle: 'WTR-M Oct',
      windowStart: '2026-10-20T00:00:00.000Z',
      windowEnd: '2026-10-24T23:00:00.000Z',
      notes: 'Gate code 4417 at the rear of 1200–1240 Maple.',
      assignedTo: opts.technician ?? RAY,
      extra: { name: 'Maple Heights' },
    },
    now,
  );
  routeQ.upsert(s, { id: 'drv-02', code: 'DRV-02', service: 'Electric', readType: 'drive', windowEnd: '2026-10-24T23:00:00.000Z', extra: { name: 'Riverside East' } }, now);

  const premises: Array<[string, string, number]> = [
    ['p1318', '1318 Maple Street', 40],
    ['p1322', '1322 Maple Street', 70],
    ['p1240', '1240 Maple Street', 150],
    ['p1206', '1206 Maple Street', 240],
    ['p42', '42 Birch Lane', 310],
  ];
  for (const [id, line, m] of premises) premiseQ.upsert(db, { id, addressLine: line, locality: 'Austin', ...north(m) }, now);

  const stops: Array<[string, string, number, string | null, string | null]> = [
    ['s1318', 'p1318', 12, 'Two dogs. Meters are at the front.', 'Gate 4417. In the pit by the driveway.'],
    ['s1322', 'p1322', 13, null, null],
    ['s1240', 'p1240', 9, null, null],
    ['s1206', 'p1206', 10, null, null],
    ['s42', 'p42', 31, null, null],
  ];
  for (const [id, premiseId, pos, hazard, notes] of stops) {
    routeStopQ.upsert(s, { id, routeId: 'wlk-07', premiseId, walkPosition: pos, hazard, accessNotes: notes, ...north(premises.find((p) => p[0] === premiseId)?.[2] ?? 0) }, now);
  }

  customerQ.upsert(db, { id: 'c-carla', name: 'Carla Ruiz', accountNumber: 'ACC-10294' }, now);
  customerQ.upsert(db, { id: 'c-desmond', name: 'Desmond Oyelaran', accountNumber: 'ACC-10311' }, now);
  customerQ.upsert(db, { id: 'c-hoa', name: 'Maple Heights HOA', accountNumber: 'ACC-10002' }, now);

  const asset = (id: string, serial: string, badge: string, premiseId: string, extra: Record<string, unknown>, parent?: string) =>
    assetQ.upsert(db, { id, serial, badge, premiseId, size: '5/8"', service: 'water', parentAssetId: parent ?? null, extra }, now);
  asset('a0471', 'MTR-0471', '88241', 'p1318', { unit_label: 'Unit A' });
  asset('a0472', 'MTR-0472', '88242', 'p1318', { unit_label: 'Unit B' });
  asset('a0470', 'MTR-0470', '88240', 'p1318', { unit_label: 'Common' });
  asset('a0470a', 'MTR-0470-A', '88250', 'p1318', { unit_label: 'Unit 1' }, 'a0470');
  asset('a0470b', 'MTR-0470-B', '88251', 'p1318', { unit_label: 'Unit 2' }, 'a0470');
  asset('a0470c', 'MTR-0470-C', '88252', 'p1318', { unit_label: 'Unit 3' }, 'a0470');
  asset('a1322', 'MTR-0480', '88300', 'p1322', {});
  asset('a1240', 'MTR-0490', '88310', 'p1240', {});
  asset('a1206', 'MTR-0500', '88320', 'p1206', {});
  asset('a42', 'MTR-0510', '88330', 'p42', {});
  // Known to the system, on no route (RW-19), and one recorded four doors down (RW-18).
  asset('a0903', 'MTR-0903', '90118', 'p1318', { unit_label: 'Unit C', unit: 'gal' });
  asset('a0533', 'MTR-0533', '90876', 'p1206', {});

  const read = (id: string, stopId: string, assetId: string, account: string | null, prev: string, min: string | null, max: string | null, parent?: string, photo?: boolean) =>
    routeReadQ.upsertFromServer(
      s,
      { id, routeId: 'wlk-07', stopId, assetId, accountId: account, previousValue: prev, expectedMin: min, expectedMax: max, unit: 'gal', parentAssetId: parent ?? null, photoRequired: photo ?? false },
      now,
    );
  read('r0471', 's1318', 'a0471', 'c-carla', '48210', '40000', '56000');
  read('r0472', 's1318', 'a0472', 'c-desmond', '30100', '25000', '36000');
  read('r0470', 's1318', 'a0470', 'c-hoa', '88000', '85000', '99000');
  read('r0470a', 's1318', 'a0470a', null, '30000', null, null, 'a0470');
  read('r0470b', 's1318', 'a0470b', null, '28900', null, null, 'a0470');
  read('r0470c', 's1318', 'a0470c', null, '29000', null, null, 'a0470');
  read('r1322', 's1322', 'a1322', null, '1000', '900', '1500', undefined, true);
  read('r1240', 's1240', 'a1240', null, '2000', '1900', '2500');
  read('r1206', 's1206', 'a1206', null, '3000', '2900', '3500');
  read('r42', 's42', 'a42', null, '4000', '3900', '4500');

  if (opts.lists ?? true) settingsQ.set(db, LIST_KEYS.cantRead, SEEDED_REASONS, now);
}
