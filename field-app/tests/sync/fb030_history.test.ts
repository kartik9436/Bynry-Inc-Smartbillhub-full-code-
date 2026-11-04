/**
 * @jest-environment node
 *
 * FB-030 (DEF-FLD-10806; PO 2026-10-31, decision log *"a technician's history
 * is the last 14 days, kept on the phone"* and its *"photos 3 days"*
 * follow-up) — the data half:
 *
 *   - a card the server says is COMPLETED fills `closed_at` and `outcome`, and
 *     what the phone already holds wins;
 *   - the close keeps its debrief and signer; a refilled job's record comes
 *     from its bundle and never overwrites the phone's own;
 *   - the purge: records at 14 days, photo FILES at 3 days after the close or
 *     the turn-in, never before the server confirmed them;
 *   - the reads history refill: once, every page, with units and FB-022's flag;
 *   - a turned-in route of the last 14 days is history, not an assignment the
 *     route download may drop;
 *   - a second technician on the same phone sees none of it.
 *
 * RED FIRST (law 7): at 7af7fbd1f every case here failed — no fill from the
 * card, no `record`, the upload deleted the file, no photo-file step in the
 * purge, no refill, and the route download dropped the turned-in route.
 */
import type { TenantDb } from '../../src/db/database';
import * as outboxQ from '../../src/db/queries/outbox';
import * as photoQ from '../../src/db/queries/photo';
import * as readsWalkQ from '../../src/db/queries/readsWalk';
import * as routeQ from '../../src/db/queries/route';
import * as routeReadQ from '../../src/db/queries/routeRead';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as closedQ from '../../src/db/queries/workOrderClosed';
import * as woReadingQ from '../../src/db/queries/woReading';
import { purgeOnAppStart } from '../../src/db/purge';
import { deviceWide, scoped } from '../../src/db/scoped';
import { applyChangesPage } from '../../src/sync/delta';
import { applyBundle } from '../../src/sync/extras';
import type { WireBundle } from '../../src/sync/fieldApi';
import { capture } from '../../src/sync/outbox';
import { type HistoryPage, refillRouteHistory, type ServedHistoryRead } from '../../src/sync/routeHistory';
import { downloadRoutes, type RoutesApi } from '../../src/sync/routes';
import type { JobCard } from '../../src/sync/transport';
import { FakeClock, idSource, MemoryFiles, openStore } from '../db/support/fixtures';

const DAY = 24 * 60 * 60 * 1000;
const dana = { technicianId: 'dana', capturedBy: 'dana' };

function setup() {
  const clock = new FakeClock(Date.parse('2026-10-31T12:00:00.000Z'));
  const db = openStore('north', undefined, clock);
  return { clock, db, deps: { newId: idSource('k'), clock }, files: new MemoryFiles() };
}

const card = (id: string, over: Partial<JobCard> = {}): JobCard => ({
  id,
  order_no: `WO-${id}`,
  type: 'Meter exchange',
  premise: { id: `p-${id}`, premise_no: 'PR-1', address: '221 Oak Ave' },
  state: 'completed',
  dispatch_state: 'complete',
  ...over,
});

function feed(db: TenantDb, technicianId: string, cards: JobCard[], now: Date): void {
  applyChangesPage(
    db,
    technicianId,
    { changes: cards.map((job) => ({ change: 'upsert' as const, order_id: job.id, at: now.toISOString(), job })), count: cards.length, next_cursor: 'c', has_more: false },
    now,
  );
}

describe('FB-030 · a job closed elsewhere', () => {
  test('a server-completed card fills closed_at and outcome, and the office acceptance reads from it', () => {
    const { db, clock } = setup();
    feed(db, 'dana', [card('1', { completed_at: '2026-10-30T15:00:00Z', outcome: 'partially_done', accepted_at: '2026-10-31T09:00:00Z' })], clock.now());
    const row = workOrderQ.getMine(scoped(db, 'dana'), '1')!;
    expect(row).toMatchObject({ closed_at: '2026-10-30T15:00:00Z', outcome: 'partially_done' });
    expect(JSON.parse(row.extra!).accepted_at).toBe('2026-10-31T09:00:00Z');
    expect(closedQ.listClosedSince(scoped(db, 'dana'), { since: '2026-10-30T00:00:00Z', limit: 10 }).map((r) => r.id)).toEqual(['1']);
  });

  test('what the phone already holds wins over the card', () => {
    const { db, clock } = setup();
    const s = scoped(db, 'dana');
    feed(db, 'dana', [card('1', { state: 'in_progress', dispatch_state: 'on_site' })], clock.now());
    closedQ.recordClose(s, '1', 'passed', '2026-10-31T11:00:00Z');
    feed(db, 'dana', [card('1', { completed_at: '2026-10-31T11:05:00Z', outcome: 'failed' })], clock.now());
    expect(workOrderQ.getMine(s, '1')).toMatchObject({ closed_at: '2026-10-31T11:00:00Z', outcome: 'passed' });
  });

  test('an open card fills nothing', () => {
    const { db, clock } = setup();
    feed(db, 'dana', [card('1', { state: 'planned', dispatch_state: 'scheduled' })], clock.now());
    expect(workOrderQ.getMine(scoped(db, 'dana'), '1')).toMatchObject({ closed_at: null, outcome: null });
  });
});

describe('FB-030 · the record', () => {
  test('the close keeps the debrief and the signer', () => {
    const { db } = setup();
    const s = scoped(db, 'dana');
    workOrderQ.upsertFromServer(s, { id: '1', number: 'WO-1', type: null, state: null, dispatchState: null, priorityCode: null, priorityRank: null, premiseId: null, windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, accessNotes: null, hazards: null, gateCode: null, extra: null, serverUpdatedAt: null }, 'x');
    closedQ.recordClose(s, '1', 'passed', '2026-10-31T11:00:00Z', {
      problem: 'Seized valve',
      done: 'Replaced it',
      signer: { kind: 'signed', name: 'Sarah Miller', at: '2026-10-31T10:58:00Z' },
    });
    expect(closedQ.recordOf(workOrderQ.getMine(s, '1'))).toEqual({
      problem: 'Seized valve',
      done: 'Replaced it',
      signer: { kind: 'signed', name: 'Sarah Miller', at: '2026-10-31T10:58:00Z' },
    });
  });

  test('a refilled job takes its record, values and photos from the bundle — and never overwrites the phone’s', () => {
    const { db, clock } = setup();
    const s = scoped(db, 'dana');
    feed(db, 'dana', [card('1', { completed_at: '2026-10-29T15:00:00Z', outcome: 'passed' })], clock.now());
    const bundle: WireBundle = {
      order_id: '1',
      order_no: 'WO-1',
      template_id: null,
      template_version: null,
      safety: [],
      tasks: [],
      materials: [],
      readings: [{ id: 'rd-1', seq: 1, prompt: 'Final read', unit_of_measure: 'kWh', min_value: null, max_value: null, value: '48210.5', captured_at: '2026-10-29T14:50:00Z' }],
      record: {
        completed_at: '2026-10-29T15:00:00Z',
        outcome: 'passed',
        problem: 'Seized valve',
        done: 'Replaced it',
        signature: { kind: 'refused', reason: 'Nobody home', at: '2026-10-29T14:58:00Z' },
        photos: [{ photo_id: 'ph-1', taken_at: '2026-10-29T14:40:00Z' }],
      },
    };
    applyBundle(db, 'dana', bundle, clock.now());
    expect(closedQ.recordOf(workOrderQ.getMine(s, '1'))).toEqual({
      problem: 'Seized valve',
      done: 'Replaced it',
      signer: { kind: 'refused', reason: 'Nobody home', at: '2026-10-29T14:58:00Z' },
    });
    expect(woReadingQ.listForOrder(s, '1')[0]).toMatchObject({ value: '48210.5', unit: 'kWh' });
    expect(photoQ.getMine(s, 'ph-1')).toMatchObject({ state: 'uploaded', file_deleted: 1, work_order_id: '1' });

    // The phone's own record wins over a later bundle.
    closedQ.recordClose(s, '1', 'passed', '2026-10-29T15:00:00Z', { problem: 'Mine', done: 'Mine', signer: null });
    applyBundle(db, 'dana', bundle, clock.now());
    expect(closedQ.recordOf(workOrderQ.getMine(s, '1'))?.problem).toBe('Mine');
  });

  test('an open job’s bundle writes no record', () => {
    const { db, clock } = setup();
    const s = scoped(db, 'dana');
    feed(db, 'dana', [card('1', { state: 'planned' })], clock.now());
    applyBundle(db, 'dana', { order_id: '1', order_no: 'WO-1', template_id: null, template_version: null, safety: [], tasks: [], materials: [], readings: [], record: null }, clock.now());
    expect(closedQ.recordOf(workOrderQ.getMine(s, '1'))).toBeNull();
  });
});

describe('FB-030 · the purge', () => {
  function closedJobWithPhoto(db: TenantDb, deps: { newId: () => string; clock: FakeClock }, files: MemoryFiles, at: string) {
    const s = scoped(db, 'dana');
    feed(db, 'dana', [card('wo-1', { completed_at: at, outcome: 'passed' })], new Date(at));
    files.add('/p/1.jpg');
    const out = capture(db, dana, {
      kind: 'reading', workOrderId: 'wo-1', payload: {},
      photos: [{ localPath: '/p/1.jpg', sha256: 'a'.repeat(64), bytes: 1, target: { reading_id: 'r' } }],
    }, deps);
    return { s, out };
  }

  test('photo FILES go 3 days after the close, the row stays with the record, and the record goes at 14 days', async () => {
    const { db, deps, files, clock } = setup();
    const { s, out } = closedJobWithPhoto(db, deps, files, clock.iso());
    outboxQ.settle(deviceWide(db, 'receipt'), out.key, 'accepted', clock.iso(), null);
    for (const r of s.all<{ id: string }>(`SELECT id FROM outbox WHERE technician_id = :technician_id AND state = 'pending'`)) {
      outboxQ.settle(deviceWide(db, 'receipt'), r.id, 'accepted', clock.iso(), null);
    }
    photoQ.markUploaded(deviceWide(db, 'receipt'), out.photoIds[0]!, 'att-1', clock.iso());

    clock.advance(2 * DAY + 23 * 60 * 60 * 1000); // 2 days 23 hours
    await purgeOnAppStart(db, { now: clock.now(), files });
    expect(files.deleted).toEqual([]);

    clock.advance(2 * 60 * 60 * 1000); // past 3 days
    const r3 = await purgeOnAppStart(db, { now: clock.now(), files });
    expect(r3.photoFiles).toBe(1);
    expect(files.deleted).toEqual(['/p/1.jpg']);
    expect(photoQ.getMine(s, out.photoIds[0]!)).toMatchObject({ state: 'uploaded', file_deleted: 1 });
    expect(workOrderQ.getMine(s, 'wo-1')).toBeDefined();

    clock.advance(10 * DAY); // day 13
    await purgeOnAppStart(db, { now: clock.now(), files });
    expect(workOrderQ.getMine(s, 'wo-1')).toBeDefined();
    expect(photoQ.getMine(s, out.photoIds[0]!)).toBeDefined();

    clock.advance(2 * DAY); // day 15
    const r15 = await purgeOnAppStart(db, { now: clock.now(), files });
    expect(r15.closedJobs).toBe(1);
    expect(workOrderQ.getMine(s, 'wo-1')).toBeUndefined();
    expect(photoQ.getMine(s, out.photoIds[0]!)).toBeUndefined();
  });

  test('a photo the server has NOT confirmed keeps its file, at any age', async () => {
    const { db, deps, files, clock } = setup();
    const { s, out } = closedJobWithPhoto(db, deps, files, clock.iso());
    clock.advance(30 * DAY);
    const r = await purgeOnAppStart(db, { now: clock.now(), files });
    expect(r.photoFiles).toBe(0);
    expect(files.deleted).toEqual([]);
    expect(photoQ.getMine(s, out.photoIds[0]!)).toMatchObject({ file_deleted: 0 });
    expect(workOrderQ.getMine(s, 'wo-1')).toBeDefined();
  });

  test('a route photo’s file goes 3 days after the turn-in; an open route’s stays', async () => {
    const { db, deps, files, clock } = setup();
    const s = scoped(db, 'dana');
    for (const r of ['r-in', 'r-open']) {
      routeQ.upsert(s, { id: r }, clock.iso());
      files.add(`/p/${r}.jpg`);
      const out = capture(db, dana, {
        kind: 'route_read', routeId: r, payload: {},
        photos: [{ localPath: `/p/${r}.jpg`, sha256: 'b'.repeat(64), bytes: 1, target: {} }],
      }, deps);
      photoQ.markUploaded(deviceWide(db, 'receipt'), out.photoIds[0]!, `att-${r}`, clock.iso());
    }
    routeQ.markTurnedIn(s, 'r-in', clock.iso());
    clock.advance(4 * DAY);
    await purgeOnAppStart(db, { now: clock.now(), files });
    expect(files.deleted).toEqual(['/p/r-in.jpg']);
    expect(routeQ.getMine(s, 'r-in')).toBeDefined();
  });
});

const served = (key: string, over: Partial<ServedHistoryRead> = {}): ServedHistoryRead => ({
  key,
  route: { id: 'rt-1', code: 'WLK-07', name: 'Maple Heights', cycle: 'CY-10', turned_in_at: '2026-10-28T16:00:00Z' },
  asset_id: `a-${key}`,
  meter_no: `MTR-${key}`,
  serial_no: null,
  premises_id: 'p-1318',
  premise_no: 'PR-1318',
  address: '1318 Maple St',
  register: 'total',
  value: '48400.000000',
  unit: 'kWh',
  reader_status: 'read',
  cant_read_reason: null,
  remark: null,
  captured_at: '2026-10-28T10:42:18Z',
  lower_than_last: false,
  photo_ids: [],
  ...over,
});

class HistoryServer {
  pages: HistoryPage[] = [];
  asked: number[] = [];
  async readsHistory(page: number): Promise<HistoryPage> {
    this.asked.push(page);
    return this.pages[page - 1]!;
  }
}

describe('FB-030 · the reads history refill', () => {
  test('a new phone is refilled once, every page, with units, the flag, the reason and the photos', async () => {
    const { db, clock } = setup();
    const api = new HistoryServer();
    api.pages = [
      { count: 3, next_page: 2, results: [served('1'), served('2', { lower_than_last: true, photo_ids: ['ph-9'] })] },
      { count: 3, next_page: null, results: [served('3', { value: null, reader_status: 'could_not_read', cant_read_reason: 'dog' }), served('4', { unit: null })] },
    ];
    const r = await refillRouteHistory(db, 'ray', api, () => clock.now());
    expect(r).toEqual({ asked: true, readings: 3, skippedNoUnit: 1 });
    const s = scoped(db, 'ray');
    expect(routeQ.getMine(s, 'rt-1')).toMatchObject({ status: 'turned_in', turned_in_at: '2026-10-28T16:00:00Z' });
    const taken = readsWalkQ.takenOnRoute(s, 'rt-1');
    expect(taken.map((m) => [m.serial, m.value, m.unit, m.lower_than_last])).toEqual([
      ['MTR-1', '48400.000000', 'kWh', 0],
      ['MTR-2', '48400.000000', 'kWh', 1],
      ['MTR-3', null, 'kWh', 0],
    ]);
    expect(taken[2]).toMatchObject({ reader_status: 'could_not_read', no_read_reason: 'dog', address_line: '1318 Maple St' });
    expect(photoQ.getMine(s, 'ph-9')).toMatchObject({ file_deleted: 1, route_read_id: taken[1]!.id });

    // Asked once: a second sync asks nothing.
    await refillRouteHistory(db, 'ray', api, () => clock.now());
    expect(api.asked).toEqual([1, 2]);
  });

  test('a refill cut short is asked again', async () => {
    const { db, clock } = setup();
    const api = new HistoryServer();
    api.pages = [{ count: 2, next_page: 2, results: [served('1')] }];
    await expect(refillRouteHistory(db, 'ray', api, () => clock.now())).rejects.toThrow();
    api.pages.push({ count: 2, next_page: null, results: [served('2')] });
    const r = await refillRouteHistory(db, 'ray', api, () => clock.now());
    expect(r.readings).toBe(2);
    expect(readsWalkQ.takenOnRoute(scoped(db, 'ray'), 'rt-1')).toHaveLength(2);
  });

  test('switch technician: a second technician on the phone sees none of it', async () => {
    const { db, clock } = setup();
    const api = new HistoryServer();
    api.pages = [{ count: 1, next_page: null, results: [served('1')] }];
    await refillRouteHistory(db, 'ray', api, () => clock.now());
    feed(db, 'ray', [card('9', { completed_at: '2026-10-30T15:00:00Z', outcome: 'passed' })], clock.now());
    const marco = scoped(db, 'marco');
    expect(readsWalkQ.mineCards(marco, { period: 'week', weekFrom: '2026-10-01T00:00:00Z', latest: null, limit: 50 })).toEqual([]);
    expect(readsWalkQ.takenOnRoute(marco, 'rt-1')).toEqual([]);
    expect(closedQ.listClosedSince(marco, { since: '2026-10-01T00:00:00Z', limit: 50 })).toEqual([]);
    expect(routeReadQ.getMine(marco, 'rt-1:a-1:total')).toBeUndefined();
  });
});

describe('FB-030 · the route download keeps history', () => {
  const empty: RoutesApi = {
    myRoutes: async () => ({ results: [], next_page: null }) as never,
    routePage: async () => ({ stops: [], next_page: null }) as never,
    turnIn: async () => ({}),
    cantReadReasons: async () => ({ results: [] }),
  };

  test('a route turned in 3 days ago that the server no longer lists stays; one turned in 15 days ago goes', async () => {
    const { db, clock } = setup();
    const s = scoped(db, 'ray');
    routeQ.upsert(s, { id: 'recent' }, clock.iso());
    routeQ.markTurnedIn(s, 'recent', new Date(clock.now().getTime() - 3 * DAY).toISOString());
    routeQ.upsert(s, { id: 'old' }, clock.iso());
    routeQ.markTurnedIn(s, 'old', new Date(clock.now().getTime() - 15 * DAY).toISOString());
    routeQ.upsert(s, { id: 'walking' }, clock.iso());
    const r = await downloadRoutes(db, 'ray', empty, () => clock.now());
    expect(r).toMatchObject({ removed: 2, keptAsHistory: 1 });
    expect(routeQ.getMine(s, 'recent')).toBeDefined();
    expect(routeQ.getMine(s, 'old')).toBeUndefined();
    expect(routeQ.getMine(s, 'walking')).toBeUndefined();
  });
});
