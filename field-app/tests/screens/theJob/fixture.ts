/**
 * WO-4822, the boards' worked job, as rows in a real handset store
 * (better-sqlite3 behind the same driver interface). The figures are the
 * boards' illustrations (B14 rule 37), used here as test data: Sarah Miller,
 * 1400 Elm Street · Unit A, W-4471 with two sub-meters, four safety rows, seven
 * template steps plus one added in the field, two planned parts plus one
 * added, a five-question checklist with a branch, three readings.
 *
 * Times are the phone's LOCAL time (`local(9, 18)`), so `hhmm` reads 09:18 in
 * any time zone the suite runs in.
 */
import { type TenantDb } from '../../../src/db/database';
import * as activityQ from '../../../src/db/queries/activity';
import * as assetQ from '../../../src/db/queries/asset';
import * as crewTimeQ from '../../../src/db/queries/crewTime';
import * as customerQ from '../../../src/db/queries/customer';
import * as documentQ from '../../../src/db/queries/document';
import * as premiseQ from '../../../src/db/queries/premise';
import * as workOrderQ from '../../../src/db/queries/workOrder';
import * as woItemQ from '../../../src/db/queries/woItem';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { capturePhoto } from '../../../src/screens/theJob/actions';
import type { ReadyPhoto } from '../../../src/screens/theJob/camera';
import type { JobPortValue, JobServices } from '../../../src/screens/theJob/JobPort';
import { idSource, openStore } from '../../db/support/fixtures';
import { FakeCamera, FakeShrink } from './fakes';

export const DANA = 'tech-dana';
export const MARCO = 'tech-marco';
export const WO = 'wo-4822';

/** The phone's local clock on 20 October 2026. */
export function local(h: number, m: number): Date {
  return new Date(2026, 9, 20, h, m, 0, 0);
}

export class SettableClock {
  constructor(public at: Date) {}
  now(): Date {
    return new Date(this.at.getTime());
  }
  set(h: number, m: number): void {
    this.at = local(h, m);
  }
}

export interface JobFixture {
  db: TenantDb;
  clock: SettableClock;
  camera: FakeCamera;
  shrink: FakeShrink;
  services: JobServices;
  /** The same services as the screens see them, for calling actions directly. */
  port(): JobPortValue;
}

export function makeServices(tenant = 'silver-creek'): JobFixture {
  const db = openStore(tenant);
  const clock = new SettableClock(local(9, 58));
  const camera = new FakeCamera();
  const shrink = new FakeShrink();
  const services: JobServices = {
    db,
    captor: () => ({ technicianId: DANA, capturedBy: DANA }),
    displayName: 'D. Ortiz',
    clock,
    newId: idSource('k'),
    camera,
    shrink,
    location: () => ({ lat: 30.2651, lng: -97.7494, accuracy_m: 4, fix_at: clock.now().toISOString() }),
    tenantName: 'Silver Creek Water',
  };
  const port = (): JobPortValue => ({
    ...services,
    camera,
    shrink,
    files: { pick: () => Promise.resolve(null) },
    location: services.location ?? (() => null),
    tenantName: services.tenantName ?? '',
    crashes: null,
    openJobId: WO,
    setOpenJobId: () => undefined,
    version: 0,
    changed: () => undefined,
  });
  return { db, clock, camera, shrink, services, port };
}

export function photo(n: number): ReadyPhoto {
  return { localPath: `file:///photos/p${n}.jpg`, sha256: `sha-${n}`, bytes: 84 * 1024, width: 1600, height: 1200, overCeiling: false };
}

/** Seed WO-4822. Returns the fixture with the store filled. */
export function seedWO4822(f: JobFixture = makeServices()): JobFixture {
  const { db } = f;
  const now = local(7, 0).toISOString();
  const s = scoped(db, DANA);

  premiseQ.upsert(db, { id: 'prem-1400', addressLine: '1400 Elm Street · Unit A', locality: 'Austin', region: 'TX', postalCode: '78704', lat: 30.2651, lng: -97.7494 }, now);
  premiseQ.upsert(db, { id: 'prem-218', addressLine: '218 Pecan Grove', locality: 'Austin', region: 'TX' }, now);
  customerQ.upsert(db, { id: 'cust-sarah', name: 'Sarah Miller', accountNumber: 'ACC-10188' }, now);
  assetQ.upsert(db, { id: 'asset-w4471', serial: 'W-4471', badge: '88-2041', model: 'Neptune T-10', size: '5/8"', premiseId: 'prem-1400' }, now);
  assetQ.upsert(db, { id: 'asset-w4471a', serial: 'W-4471-A', parentAssetId: 'asset-w4471', premiseId: 'prem-1400' }, now);
  assetQ.upsert(db, { id: 'asset-w4471b', serial: 'W-4471-B', parentAssetId: 'asset-w4471', premiseId: 'prem-1400' }, now);
  assetQ.upsert(db, { id: 'asset-mtr0903', serial: 'MTR-0903', size: '5/8"', premiseId: 'prem-1400', status: 'pending' }, now);
  assetQ.upsert(db, { id: 'asset-elsewhere', serial: 'MTR-9999', premiseId: 'prem-218' }, now);

  workOrderQ.upsertFromServer(
    s,
    {
      id: WO,
      number: 'WO-4822',
      type: 'Meter exchange · residential',
      state: 'in_progress',
      dispatchState: 'On site',
      priorityCode: 'P3',
      priorityRank: 3,
      premiseId: 'prem-1400',
      windowStart: local(8, 0).toISOString(),
      windowEnd: local(12, 0).toISOString(),
      dueAt: null,
      estMinutes: 45,
      accessNotes: null,
      hazards: null,
      gateCode: null,
      // On site: taken (DEF-FLD-10579 — the card says so, so FF-15 offers Hand back, not Decline).
      extra: { technician_acceptance: { state: 'accepted', at: now, reason: null } },
      serverUpdatedAt: now,
    },
    now,
  );
  // The job fetch that fills these is not built yet (decision log, Phase 1
  // database and sync: "filling task/reading mirrors from the job fetch").
  s.run(
    `UPDATE work_order SET customer_id = 'cust-sarah', asset_id = 'asset-w4471', template_id = 'tpl-mx',
            template_version = '3'
      WHERE technician_id = :technician_id AND id = :id`,
    { id: WO },
  );

  const safety = ['Main shut-off located and closed', 'Gloves and eye protection on', 'Cones set if in roadway', 'Meter pit clear of water'];
  safety.forEach((label, i) => woItemQ.upsert(s, { id: `safety-${i + 1}`, workOrderId: WO, kind: 'safety', position: i + 1, label }, now));

  const tasks: woItemQ.WoItemInput[] = [
    { id: 'task-1', workOrderId: WO, kind: 'task', position: 1, label: 'Photograph meter in place', photoRequired: true, photoMinCount: 2, state: 'done', detail: { minutes: 2, photo_labels: ['Before', 'After'] } },
    { id: 'task-2', workOrderId: WO, kind: 'task', position: 2, label: 'Record closing read', state: 'done', detail: { minutes: 3 } },
    { id: 'task-3', workOrderId: WO, kind: 'task', position: 3, label: 'Remove old meter', state: 'done', detail: { minutes: 8 } },
    { id: 'task-4', workOrderId: WO, kind: 'task', position: 4, label: 'Fit new meter and seal', mustDo: true, photoMinCount: 3, detail: { minutes: 10 } },
    { id: 'task-5', workOrderId: WO, kind: 'task', position: 5, label: 'Replace corroded coupling', addedInField: true, reason: 'Old coupling corroded through, would not reseal.', detail: { minutes: 15, added_by: 'D. Ortiz', added_at: local(9, 31).toISOString() } },
    { id: 'task-6', workOrderId: WO, kind: 'task', position: 6, label: 'Open main and check for leaks', detail: { minutes: 6 } },
    { id: 'task-7', workOrderId: WO, kind: 'task', position: 7, label: 'Record opening read', detail: { minutes: 3 } },
    { id: 'task-8', workOrderId: WO, kind: 'task', position: 8, label: 'Photograph new meter fitted', photoRequired: true, photoMinCount: 2, detail: { minutes: 5 } },
  ];
  for (const t of tasks) {
    woItemQ.upsert(s, t, now);
    if (t.state) woItemQ.setState(s, t.id, t.state);
  }

  const materials: woItemQ.WoItemInput[] = [
    { id: 'mat-seal', workOrderId: WO, kind: 'material', position: 1, label: 'Wire seal', state: 'used', detail: { code: 'SEAL-W', planned: 1, used: 1, van: 26 } },
    { id: 'mat-meter', workOrderId: WO, kind: 'material', position: 2, label: 'Water meter 5/8"', detail: { code: 'MTR-W58', planned: 1, used: 0, van: 0, serial: 'W-9044' } },
    { id: 'mat-kit', workOrderId: WO, kind: 'material', position: 3, label: 'Meter coupling kit', addedInField: true, reason: 'Old coupling corroded, would not reseal.', state: 'used', detail: { code: 'CPL-58', used: 1, unit_cost: '18.5000', added_by: 'D. Ortiz', added_at: local(9, 31).toISOString() } },
  ];
  for (const m of materials) {
    woItemQ.upsert(s, m, now);
    if (m.state) woItemQ.setState(s, m.id, m.state);
  }

  const questions: woItemQ.WoItemInput[] = [
    { id: 'q1', workOrderId: WO, kind: 'checklist', position: 1, label: 'Did you speak to the customer?', state: 'yes', detail: { answer_type: 'yes_no' } },
    { id: 'q2', workOrderId: WO, kind: 'checklist', position: 2, label: 'Were they happy with the work?', state: 'yes', detail: { answer_type: 'yes_no', show_if: { item_id: 'q1', answer: 'yes' } } },
    { id: 'q3', workOrderId: WO, kind: 'checklist', position: 3, label: 'New meter start read', state: '0', detail: { answer_type: 'number', unit: 'gal' } },
    { id: 'q4', workOrderId: WO, kind: 'checklist', position: 4, label: 'Was the old seal intact?', detail: { answer_type: 'yes_no', hints: { no: 'No opens a tamper report' } } },
    { id: 'q5', workOrderId: WO, kind: 'checklist', position: 5, label: 'Did you leave a door hanger?', detail: { answer_type: 'yes_no' } },
  ];
  for (const q of questions) {
    woItemQ.upsert(s, q, now);
    if (q.state) woItemQ.setState(s, q.id, q.state);
  }

  woReadingQ.upsert(s, { id: 'r-master', workOrderId: WO, position: 1, prompt: 'Closing read', unit: 'gal', minValue: '40000', maxValue: '50000', previousValue: '48180', photoRequired: true }, now);
  woReadingQ.upsert(s, { id: 'r-sub-a', workOrderId: WO, position: 2, prompt: 'Closing read · Unit A', unit: 'gal', minValue: '10000', maxValue: '14000', previousValue: '12210' }, now);
  woReadingQ.upsert(s, { id: 'r-sub-b', workOrderId: WO, position: 3, prompt: 'Closing read · Unit B', unit: 'gal', photoRequired: true }, now);
  woReadingQ.recordValue(s, 'r-sub-a', { value: '12564', unit: 'gal', flagged: false, unableToRead: false, capturedAt: local(9, 25).toISOString() });

  // The clocks: travel 08:00 → 08:14, labour from 08:46 still running; Marco 08:46 → 09:58.
  crewTimeQ.insert(s, { id: 'ct-travel', workOrderId: WO, personId: DANA, kind: 'travel', startedAt: local(8, 0).toISOString(), endedAt: local(8, 14).toISOString() });
  crewTimeQ.insert(s, { id: 'ct-labour', workOrderId: WO, personId: DANA, kind: 'labour', startedAt: local(8, 46).toISOString() });
  crewTimeQ.insert(s, { id: 'ct-marco', workOrderId: WO, personId: MARCO, kind: 'labour', startedAt: local(8, 46).toISOString(), endedAt: local(9, 58).toISOString() });

  for (let i = 0; i < 9; i++) {
    activityQ.insert(s, { id: `act-${i}`, workOrderId: WO, kind: i < 3 ? 'remark' : 'status', status: i < 3 ? null : 'note', text: `event ${i}`, author: DANA, at: local(8, i).toISOString() });
  }

  documentQ.upsert(db, { id: 'doc-sop', ownerKind: 'work_order', ownerId: WO, title: 'Meter exchange SOP', source: 'server' }, now);
  documentQ.upsert(db, { id: 'doc-msds', ownerKind: 'work_order', ownerId: WO, title: 'Sealant safety sheet', source: 'server' }, now);
  documentQ.upsert(db, { id: 'doc-tpl', ownerKind: 'template', ownerId: 'tpl-mx', title: 'Template notes', source: 'server' }, now);

  // Photographs, taken on their step through the real capture path.
  const port = f.port();
  f.clock.set(9, 18);
  capturePhoto(port, WO, photo(1), { task_id: 'task-1' });
  f.clock.set(9, 52);
  capturePhoto(port, WO, photo(2), { task_id: 'task-1' });
  f.clock.set(10, 41);
  capturePhoto(port, WO, photo(3), { task_id: 'task-4' });
  f.clock.set(10, 58);
  return f;
}
