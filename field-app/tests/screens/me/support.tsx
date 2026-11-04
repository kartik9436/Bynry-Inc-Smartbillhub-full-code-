/**
 * The "me" wave's fixture: a real handset store (better-sqlite3, every query
 * the SQL it is), Dana signed in through the real session, the real
 * navigation tree (`tests/navigation/harness.tsx`), and the server doors as
 * fakes a test can inspect. Figures are the boards' (B14 rule 37: test data,
 * never facts the code builds to).
 *
 * The clock is pinned at 13:10 UTC on Wednesday 21 October 2026, and the
 * process runs in UTC so a time on screen is the time in the fixture.
 */
process.env.TZ = 'UTC';

import { CommonActions } from '@react-navigation/native';
import { act } from '@testing-library/react-native';

import type { TenantDb } from '../../../src/db/database';
import * as crewTime from '../../../src/db/queries/crewTime';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as photoQ from '../../../src/db/queries/photo';
import * as technicianQ from '../../../src/db/queries/technician';
import * as workOrder from '../../../src/db/queries/workOrder';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { routeTo } from '../../../src/navigation/routing';
import type { ScreenId } from '../../../src/navigation/screens';
import type { ShellStatusValue } from '../../../src/navigation/ShellStatus';
import { capture } from '../../../src/sync/outbox';
import type { ThemeMode } from '../../../src/theme';
import { MeShellStatus } from '../../../src/screens/me/availability';
import { createDbMeData } from '../../../src/screens/me/dbData';
import { GapError, GAPS } from '../../../src/screens/me/gaps';
import {
  type AlertItem,
  type MeServices,
  MeServicesProvider,
  notWiredServices,
  type ShiftWeek,
  type VanStock,
} from '../../../src/screens/me/services';
import { idSource, openStore } from '../../db/support/fixtures';
import { mountApp } from '../../navigation/harness';

export const DANA = 'tech-dana';
export const MARCO = 'tech-marco';
export const NOW = new Date('2026-10-21T13:10:00.000Z');
export const at = (hhmm: string) => `2026-10-21T${hhmm}:00.000Z`;

export function seedRoster(db: TenantDb): void {
  technicianQ.upsert(db, { id: DANA, name: 'D. Ortiz', role: 'Water II', employment: 'Employee' }, at('07:00'));
}

const ORDER = (id: string, number: string, type: string, start: string) => ({
  id,
  number,
  type,
  state: 'scheduled',
  dispatchState: 'scheduled',
  priorityCode: 'P3',
  priorityRank: 3,
  premiseId: null,
  windowStart: start,
  windowEnd: null,
  dueAt: null,
  estMinutes: 45,
  accessNotes: null,
  hazards: null,
  gateCode: null,
  extra: null,
  serverUpdatedAt: at('06:00'),
});

/** FF-44 TC-1: four done, seven left. */
export function seedOrders(db: TenantDb): void {
  const s = scoped(db, DANA);
  const done = ['4815', '4822', '4810', '4811'];
  done.forEach((n, i) => workOrder.upsertFromServer(s, ORDER(`wo-${n}`, `WO-${n}`, i === 1 ? 'Meter exchange' : 'Final read', at('08:00')), at('06:00')));
  ['4824', '4831', '4832', '4833', '4834', '4835', '4836'].forEach((n) =>
    workOrder.upsertFromServer(s, ORDER(`wo-${n}`, `WO-${n}`, 'Meter exchange', at('14:00')), at('06:00')),
  );
  done.forEach((n) => workOrder.markClosed(s, `wo-${n}`, at('12:00')));
}

/**
 * FF-47 TC-1: 5h 02m recorded — jobs 3h 38m · travel 54m · admin 30m — with
 * WO-4824 running since 12:28. The admin entries go through the REAL capture
 * path (`startAdmin` / `stopClock`), so their task is read back from the act.
 */
export function seedDay(db: TenantDb, ids: () => string): void {
  const data = createDbMeData(db, { newId: ids });
  const captor = { technicianId: DANA, capturedBy: DANA };
  data.startAdmin(captor, 'vehicleCheck', new Date(at('07:40')));
  data.stopClock(captor, new Date(at('08:00')));
  const s = scoped(db, DANA);
  const row = (id: string, kind: 'travel' | 'labour' | 'admin', wo: string | null, from: string, to: string | null) =>
    crewTime.insert(s, { id, workOrderId: wo, personId: DANA, kind, startedAt: at(from), endedAt: to ? at(to) : null });
  row('t1', 'travel', 'wo-4822', '08:00', '08:14');
  row('l1', 'labour', 'wo-4815', '08:14', '08:41');
  row('l2', 'labour', 'wo-4822', '08:46', '09:58');
  row('t2', 'travel', 'wo-4831', '09:58', '10:38');
  row('l3', 'labour', 'wo-4831', '10:38', '11:55');
  data.startAdmin(captor, 'depot', new Date(at('12:18')));
  data.stopClock(captor, new Date(at('12:28')));
  row('l4', 'labour', 'wo-4824', '12:28', null);
}

/** FF-50 TC-4: 62 photos, 24 up, 38 waiting, 41 MB left; completed work all sent. */
export function seedPhotos(db: TenantDb): void {
  const s = scoped(db, DANA);
  const receipt = deviceWide(db, 'receipt');
  for (let i = 0; i < 62; i += 1) {
    photoQ.insert(s, {
      id: `p${i}`,
      outboxId: `o${i}`,
      declareId: `d${i}`,
      workOrderId: 'wo-4822',
      routeId: null,
      localPath: `/photos/p${i}.jpg`,
      sha256: `sha${i}`,
      bytes: 1_078_948,
      capturedBy: DANA,
      capturedAt: at('09:00'),
      location: null,
    });
    if (i < 24) photoQ.markUploaded(receipt, `p${i}`, `r${i}`, at('10:00'));
  }
}

/** One reading the server refused, with its reason (R48). */
export function seedRefusal(db: TenantDb, ids: () => string): string {
  const { key } = capture(
    db,
    { technicianId: DANA, capturedBy: DANA },
    { kind: 'reading', workOrderId: 'wo-4822', payload: { value: '180' } },
    { newId: ids, clock: { now: () => new Date(at('09:30')) } },
  );
  outboxQ.refuse(deviceWide(db, 'receipt'), key, { message: 'Reading 180 is impossible for this meter' });
  return key;
}

export class FakeAlerts {
  items: AlertItem[] = [];
  acks: string[] = [];
  failAck = false;
  list = async () => this.items;
  acknowledge = async (_tech: string, id: string) => {
    if (this.failAck) throw new GapError(GAPS.alerts);
    this.acks.push(id);
    this.items = this.items.map((a) => (a.id === id ? { ...a, acknowledgedAt: NOW.toISOString() } : a));
  };
  markAllRead = async () => {
    this.items = this.items.map((a) => ({ ...a, read: true }));
  };
}

/** FF-42 TC-4 and FF-43 TC-1, the boards' alerts. The emergency reached the handset 48s before NOW. */
export function boardAlerts(): AlertItem[] {
  return [
    {
      id: 'em-1',
      kind: 'emergency',
      at: new Date(NOW.getTime() - 48_000).toISOString(),
      title: 'Gas leak reported',
      detail: null,
      note: null,
      read: false,
      workOrderNumber: 'WO-4850',
      acknowledgedAt: null,
      priority: 'P1',
      address: '14 Oak Street',
      locality: 'Austin, TX 78704',
      reportedAt: at('10:06'),
      reportedBy: 'caller',
      distanceMiles: 1.8,
      driveMinutes: 7,
      said: 'Strong smell at the side of the house. Two occupants have left the building.',
    },
    { id: 'a2', kind: 'jobCancelled', at: at('08:04'), title: 'Aaron Bruner has paid', detail: 'WO-4824 · do not disconnect', note: '$241.38 cleared 18 Oct · 22 Cedar Court', read: false, workOrderNumber: 'WO-4824' },
    { id: 'a3', kind: 'schedule', at: at('07:41'), title: 'WO-4831 moved to 14:00', detail: '88 Hillcrest Avenue', note: null, read: false, workOrderNumber: 'WO-4831' },
    { id: 'a4', kind: 'dispatch', at: '2026-10-20T16:00:00.000Z', title: 'Depot closes at 16:30 on Friday. Return van keys to the box.', detail: null, note: 'J. Okafor', read: true, workOrderNumber: null },
  ];
}

export function boardWeek(): ShiftWeek {
  return {
    current: { start: at('08:00'), end: at('16:30'), startedAt: at('08:08') },
    days: [
      { date: '2026-10-19', kind: 'shift', start: at('08:00'), end: at('16:30'), name: 'Day shift', note: 'Route 3' },
      { date: '2026-10-20', kind: 'shift', start: at('08:00'), end: at('16:30'), name: 'Day shift', note: 'Route 3' },
      { date: '2026-10-21', kind: 'shift', start: at('06:00'), end: at('14:30'), name: 'Early', note: 'Route 1' },
      { date: '2026-10-22', kind: 'timeOff', start: null, end: null, name: null, note: 'Approved 02 Oct' },
      { date: '2026-10-23', kind: 'holiday', start: null, end: null, name: 'Founders Day', note: 'depot closed' },
    ],
  };
}

export function boardVan(): VanStock {
  return {
    van: 'Van 14 · D. Ortiz',
    countedAt: at('07:44'),
    items: [
      { sku: 'MTR-W58', name: 'Water meter 5/8"', onHand: 0, neededToday: 1, unitPrice: { amount: '92.4000', currency: 'USD' } },
      { sku: 'MTR-W34', name: 'Water meter 3/4"', onHand: 4, neededToday: null, unitPrice: null },
      { sku: 'SEAL-W', name: 'Wire seal', onHand: 26, neededToday: null, unitPrice: null },
    ],
  };
}

export interface MeFixture {
  db: TenantDb;
  ids: () => string;
  services: MeServices;
  alerts: FakeAlerts;
}

export function makeFixture(overrides: Partial<MeServices> = {}): MeFixture {
  const db = openStore('silver-creek');
  const ids = idSource('me');
  seedRoster(db);
  const alerts = new FakeAlerts();
  const services = notWiredServices({
    data: createDbMeData(db, { newId: ids }),
    alerts,
    now: () => NOW,
    ...overrides,
  });
  return { db, ids, services, alerts };
}

/** The real app tree, signed in as Dana, with these services, opened at `id`. */
export async function openScreen(
  id: ScreenId,
  fixture: MeFixture,
  options: { theme?: ThemeMode; status?: ShellStatusValue } = {},
) {
  const app = await mountApp({
    theme: options.theme,
    status: options.status,
    wrap: (ui) => (
      <MeServicesProvider services={fixture.services}>
        <MeShellStatus base={options.status}>{ui}</MeShellStatus>
      </MeServicesProvider>
    ),
  });
  await app.findByTestId('screen-FF-63');
  const target = routeTo(id);
  await act(async () => {
    app.ref.dispatch(CommonActions.navigate(target.name, target.params));
  });
  // Let a screen's port reads (promises) settle.
  await act(async () => {
    await Promise.resolve();
  });
  return app;
}
