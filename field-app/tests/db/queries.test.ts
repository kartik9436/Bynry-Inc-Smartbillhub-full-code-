/**
 * @jest-environment node
 *
 * The query layer's own promises: a figure is a decimal string that comes back
 * exactly as written; a unit is never assumed; a scan matches serial, then
 * badge, then device id (R43); the day list never sorts by priority.
 */
import { rawRunner } from '../../src/db/database';
import * as assetQ from '../../src/db/queries/asset';
import * as dayQ from '../../src/db/queries/day';
import * as routeReadQ from '../../src/db/queries/routeRead';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as woReadingQ from '../../src/db/queries/woReading';
import { scoped } from '../../src/db/scoped';
import { openStore } from './support/fixtures';

const NOW = '2026-10-21T08:00:00.000Z';

function wo(id: string, over: Partial<workOrderQ.WorkOrderFromServer> = {}): workOrderQ.WorkOrderFromServer {
  return {
    id, number: id.toUpperCase(), type: null, state: null, dispatchState: null, priorityCode: null, priorityRank: null,
    premiseId: null, windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, accessNotes: null,
    hazards: null, gateCode: null, extra: null, serverUpdatedAt: null, ...over,
  };
}

describe('figures and units', () => {
  const db = openStore();
  const s = scoped(db, 'dana');

  beforeAll(() => {
    routeReadQ.upsertFromServer(s, { id: 'm-1', routeId: 'r-1', stopId: 's-1', assetId: 'a-1', unit: 'kWh', previousValue: '48210.50' }, NOW);
  });

  test('a reading comes back exactly as written — 48210.50, not 48210.5', () => {
    routeReadQ.recordCapture(s, 'm-1', {
      captureKey: 'k-1', value: '48298.50', unit: 'kWh', readerStatus: 'read', capturedAt: NOW, capturedBy: 'dana',
      identifiedBy: 'scan', readMethod: 'manual',
    });
    const row = routeReadQ.getMine(s, 'm-1');
    expect(row?.value).toBe('48298.50');
    expect(row?.previous_value).toBe('48210.50');
    expect(rawRunner(db).get<{ t: string }>(`SELECT typeof(value) AS t FROM route_read WHERE id = 'm-1'`)?.t).toBe('text');
  });

  test('a float or an exponent is refused before it lands', () => {
    expect(() => routeReadQ.upsertFromServer(s, { id: 'm-2', routeId: 'r-1', stopId: 's-1', assetId: 'a-2', unit: 'kWh', previousValue: '1e3' }, NOW)).toThrow(/decimal string/);
  });

  test('a unit that is not the meter’s own is refused, never converted (hard rule 3)', () => {
    routeReadQ.upsertFromServer(s, { id: 'm-3', routeId: 'r-1', stopId: 's-1', assetId: 'a-3', unit: 'kWh' }, NOW);
    expect(() =>
      routeReadQ.recordCapture(s, 'm-3', {
        captureKey: 'k-3', value: '10', unit: 'MWh', readerStatus: 'read', capturedAt: NOW, capturedBy: 'dana',
        identifiedBy: 'typed', readMethod: 'manual',
      }),
    ).toThrow(/unit/);
    woReadingQ.upsert(s, { id: 'r-1', workOrderId: 'wo-1', position: 1, prompt: 'Final read', unit: 'gal' }, NOW);
    expect(woReadingQ.recordValue(s, 'r-1', { value: '10', unit: 'L', flagged: false, unableToRead: false, capturedAt: NOW })).toBe(0);
    expect(() => woReadingQ.upsert(s, { id: 'r-2', workOrderId: 'wo-1', position: 2, prompt: 'x', unit: '' }, NOW)).toThrow(/unit/);
  });

  test('progress is derived, never a stored counter', () => {
    expect(routeReadQ.progress(s, 'r-1')).toEqual({ total: 2, read: 1 });
  });
});

describe('scan order', () => {
  const db = openStore();
  test('serial, then badge, then device id (R43)', () => {
    assetQ.upsert(db, { id: 'a-badge', badge: 'X100' }, NOW);
    assetQ.upsert(db, { id: 'a-serial', serial: 'X100' }, NOW);
    assetQ.upsert(db, { id: 'a-device', deviceId: 'Z9' }, NOW);
    expect(assetQ.matchScannedCode(db, 'X100')).toMatchObject({ asset: { id: 'a-serial' }, matchedOn: 'serial' });
    expect(assetQ.matchScannedCode(db, 'Z9')).toMatchObject({ asset: { id: 'a-device' }, matchedOn: 'device_id' });
    expect(assetQ.matchScannedCode(db, 'nothing')).toBeNull();
  });
});

describe('the day list', () => {
  const db = openStore();
  const s = scoped(db, 'dana');
  test('appointment first, priority never reorders, unscheduled last (BR-WRK-035)', () => {
    workOrderQ.upsertFromServer(s, wo('wo-a', { windowStart: '2026-10-21T09:00:00Z', priorityRank: 3 }), NOW);
    workOrderQ.upsertFromServer(s, wo('wo-p1', { windowStart: '2026-10-21T13:00:00Z', priorityCode: 'P1', priorityRank: 1 }), NOW);
    workOrderQ.upsertFromServer(s, wo('wo-none', { dueAt: '2026-10-22T00:00:00Z' }), NOW);
    const ids = workOrderQ.listDay(s, { before: '2026-10-22T00:00:00Z', limit: 10 }).map((w) => w.id);
    expect(ids).toEqual(['wo-a', 'wo-p1', 'wo-none']);
  });
  test('an upsert never overwrites what the handset owns (closed_at)', () => {
    workOrderQ.markClosed(s, 'wo-a', NOW);
    workOrderQ.upsertFromServer(s, wo('wo-a', { windowStart: '2026-10-21T10:00:00Z' }), NOW);
    expect(workOrderQ.getMine(s, 'wo-a')).toMatchObject({ closed_at: NOW, window_start: '2026-10-21T10:00:00Z' });
  });
});

/**
 * FB-029 (decision log 2026-10-31, PO C): the job list's Later and All tabs,
 * and the side finding that a tab's count must count exactly its cards
 * (DEF-FLD-10804). The clock is Friday 31 October, local time; "day 3" is
 * Monday 3 November and its midnight belongs to Later, not to the day after.
 */
describe('FB-029: Later and All (DEF-FLD-10804)', () => {
  const FRI = new Date(2026, 9, 31, 9, 0);
  const at = (day: number, h = 0, m = 0) => new Date(2026, 9, day, h, m).toISOString();
  const db = openStore();
  const s = scoped(db, 'dana');
  const marco = scoped(db, 'marco');
  const T = FRI.toISOString();
  const laterFrom = () => dayQ.dayBounds(FRI, 3).from;

  beforeAll(() => {
    workOrderQ.upsertFromServer(s, wo('wo-over', { windowStart: at(29, 10), estMinutes: 10 }), T); // overdue
    workOrderQ.upsertFromServer(s, wo('wo-undated', { estMinutes: 20 }), T); // no date at all
    workOrderQ.upsertFromServer(s, wo('wo-d0', { windowStart: at(31, 13), estMinutes: 30 }), T);
    workOrderQ.upsertFromServer(s, wo('wo-d2', { windowStart: at(33, 10), estMinutes: 40 }), T); // Sun 2 Nov
    workOrderQ.upsertFromServer(s, wo('wo-d2late', { dueAt: at(33, 23, 59), estMinutes: 5 }), T); // last minute of day 2
    workOrderQ.upsertFromServer(s, wo('wo-d3mid', { dueAt: at(34, 0, 0), estMinutes: 50 }), T); // 00:00 Mon 3 Nov
    workOrderQ.upsertFromServer(s, wo('wo-d3', { windowStart: at(34, 8), dueAt: at(34, 17), estMinutes: 60 }), T);
    workOrderQ.upsertFromServer(s, wo('wo-d10', { windowStart: at(41, 9), priorityCode: 'P1', priorityRank: 1, estMinutes: 70 }), T);
    workOrderQ.upsertFromServer(s, wo('wo-d60', { dueAt: at(91, 12), estMinutes: 80 }), T); // Tue 30 Dec
    // Not open: complete, cancelled, closed on the handset — in no tab.
    workOrderQ.upsertFromServer(s, wo('wo-done', { windowStart: at(41, 10), dispatchState: 'complete' }), T);
    workOrderQ.upsertFromServer(s, wo('wo-cancel', { windowStart: at(41, 11), dispatchState: 'cancelled' }), T);
    workOrderQ.upsertFromServer(s, wo('wo-closed', { windowStart: at(41, 12) }), T);
    workOrderQ.markClosed(s, 'wo-closed', T);
    // Marco's job ten days out is his, never Dana's.
    workOrderQ.upsertFromServer(marco, wo('wo-marco', { windowStart: at(41, 9) }), T);
  });

  const ids = (jobs: { id: string }[]) => jobs.map((j) => j.id);

  test('Later: every open job from 00:00 on day 3, no upper limit, by day then window then due then number', () => {
    expect(ids(dayQ.listLater(s, { from: laterFrom() }))).toEqual(['wo-d3', 'wo-d3mid', 'wo-d10', 'wo-d60']);
  });

  test('a job at 00:00 on day 3 is in Later, not on the day-after tab; 23:59 on day 2 is on the day after', () => {
    const dayAfter = dayQ.listDay(s, { ...dayQ.dayBounds(FRI, 2), today: false });
    expect(ids(dayAfter)).toEqual(['wo-d2', 'wo-d2late']);
    expect(ids(dayQ.listLater(s, { from: laterFrom() }))).toContain('wo-d3mid');
  });

  test('All: every open job, overdue first by its date, undated last', () => {
    expect(ids(dayQ.listAll(s, {}))).toEqual([
      'wo-over', 'wo-d0', 'wo-d2', 'wo-d2late', 'wo-d3', 'wo-d3mid', 'wo-d10', 'wo-d60', 'wo-undated',
    ]);
  });

  test('completed, cancelled, closed and another technician’s jobs are in neither', () => {
    const both = [...ids(dayQ.listLater(s, { from: laterFrom() })), ...ids(dayQ.listAll(s, {}))];
    for (const gone of ['wo-done', 'wo-cancel', 'wo-closed', 'wo-marco']) expect(both).not.toContain(gone);
    expect(ids(dayQ.listAll(marco, {}))).toEqual(['wo-marco']);
  });

  test('paging: 50 at a time by default, and pages join up with nothing lost or repeated', () => {
    const all = ids(dayQ.listAll(s, {}));
    const pages = [0, 2, 4, 6, 8].flatMap((offset) => ids(dayQ.listAll(s, { limit: 2, offset })));
    expect(pages).toEqual(all);
    const later = ids(dayQ.listLater(s, { from: laterFrom() }));
    const laterPages = [0, 3].flatMap((offset) => ids(dayQ.listLater(s, { from: laterFrom(), limit: 3, offset })));
    expect(laterPages).toEqual(later);
    const many = scoped(db, 'pat');
    for (let i = 0; i < 60; i += 1) {
      workOrderQ.upsertFromServer(many, wo(`wo-p${String(i).padStart(2, '0')}`, { windowStart: at(45, 9) }), T);
    }
    expect(dayQ.listAll(many, {})).toHaveLength(dayQ.PAGE_SIZE);
    expect(dayQ.listLater(many, { from: laterFrom() })).toHaveLength(dayQ.PAGE_SIZE);
    expect(dayQ.allCounts(many).left).toBe(60);
  });

  test('every tab counts exactly its own cards — an undated job only on Today, an overdue one on Today too', () => {
    for (const offset of [0, 1, 2]) {
      const bounds = { ...dayQ.dayBounds(FRI, offset), today: offset === 0 };
      const listed = dayQ.listDay(s, bounds);
      const counted = dayQ.dayCounts(s, bounds);
      expect(`day ${offset}: ${counted.left}`).toBe(`day ${offset}: ${listed.length}`);
      expect(counted.plannedMinutes).toBe(listed.reduce((n, j) => n + (j.estMinutes ?? 0), 0));
    }
    expect(dayQ.laterCounts(s, { from: laterFrom() })).toMatchObject({ left: 4, plannedMinutes: 50 + 60 + 70 + 80 });
    expect(dayQ.allCounts(s)).toMatchObject({ left: 9, plannedMinutes: 10 + 20 + 30 + 40 + 5 + 50 + 60 + 70 + 80 });
  });
});
